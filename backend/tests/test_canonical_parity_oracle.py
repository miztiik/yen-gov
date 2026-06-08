"""Parity oracle: per-AC FPTP winner from a pinned fixture must match the
canonical long-format candidacies.csv via the same logic the frontend reader
uses (max(votes) per AC; NOTA is excluded by construction because
candidacies.csv carries only registered candidates - NOTA totals live in
summary.csv).

History
-------
- Pre-PR-R.3 (1.8e closure): test read live ``results.sqlite`` ground truth
  alongside the parquet store.
- PR-R.3: SQLite ground truth deleted; fixture lifted into
  ``backend/tests/fixtures/canonical_winners_2026_05_19.json`` so the
  trust anchor moves from on-disk SQLite to checked-in JSON. The question
  ("does the canonical store still produce the same per-AC winners as the
  trusted ground truth?") is unchanged.
- F1.1 (parent plan
  ``TODO/20260603-data-and-charting-platform-reset-plan.md`` chunk F1 +
  sub-plan ``TODO/20260605-f1-csv-loaders-and-oracle-rewrite-subplan.md``):
  the SQL flips from a 4-way ``read_parquet(...)`` JOIN
  (``election_results.parquet`` x ``elections_candidacies.parquet`` x
  ``dim_persons.parquet`` x ``dim_acs.parquet``) to a per-(state, year) CSV
  scan against
  ``datasets/elections/assembly/state=<slug>/election=<yr>/candidacies.csv``
  (per plan section 21.3, emitted by B2b.5.2-5.3).
- F1.1 Path A (2026-06-06): the user verdict on the fixture-vs-CSV drift
  was BACKFILL. The mashed CSV (post-tool
  ``tools.elections.backfill_from_legacy``) becomes the source of truth; the
  fixture re-anchored on TCPD-derived winners + re-keyed from ECI legacy
  state_code ("S03") to LGD state slug ("assam"). This test was updated
  to consume the new slug-keyed fixture; the 22-entry ECI map that the
  pre-Path-A rewrite carried is GONE (it now lives only in the one-shot
  backfill tool's recovery story per F1.1 Phase 4).

Fixture key shape
-----------------
``"<event_id>/<lgd_state_slug>"`` (e.g. ``"AcGenApr2016/assam"``). The
CSV path is ``datasets/elections/assembly/state=<slug>/election=<yr>/...``
where the year is the 4-digit suffix on the event_id.

oracle-non-skip gate
--------------------
Per parent plan section 22.6 ``oracle-non-skip``: the CSV oracle MUST
actively execute. The OLD broad ``skipif parquet absent`` skip is replaced
with a per-slice presence filter (some fixture slices reference elections
whose CSVs are not yet shipped in this corpus - see ``_KNOWN_ABSENT_SLICES``
below) AND a top-level ``test_oracle_non_skip_gate`` that hard-FAILS if
the run-set drops below the expected floor. This is the false-green guard
for the post-X1b world: a blanket skip ("CSV absent") would mask a real
deletion regression.

Holy Law #7: uses the REAL on-disk CSV + a checked-in real-data fixture -
no mocks.

Runs in <2s against the 35 currently-on-disk slices of the 41-slice
fixture (post-F1.1 Path A backfill).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ELECTIONS_ASSEMBLY_ROOT = REPO_ROOT / "datasets" / "elections" / "assembly"
FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "canonical_winners_2026_05_19.json"

# Hand-authored ``read_csv(columns=...)`` map per parent plan section 22.4
# contract invariant 1 (typed read at the boundary). Mirrors the
# ``candidacies.csv`` header order shipped by B2b.5.x. When the central
# per-file CSV column registry lands (parent plan section 23.2), this map
# moves there and is imported.
_CANDIDACIES_COLUMNS: dict[str, str] = {
    "entity_id": "VARCHAR",
    "state": "VARCHAR",
    "election_year": "INTEGER",
    "constituency_no": "INTEGER",
    "constituency_name": "VARCHAR",
    "candidate_name": "VARCHAR",
    "party_id": "VARCHAR",
    "party_short_raw": "VARCHAR",
    "votes": "BIGINT",
    "vote_share_pct": "DOUBLE",
    "position": "INTEGER",
    "result": "VARCHAR",
    "sex": "VARCHAR",
    "age": "INTEGER",
    "education": "VARCHAR",
    "profession": "VARCHAR",
    "candidate_type": "VARCHAR",
    "source_id": "VARCHAR",
}


def _event_year(event_id: str) -> int:
    """Extract the 4-digit year suffix from an ECI event id (AcGenApr2016 -> 2016)."""
    match = re.search(r"(\d{4})$", event_id)
    if match is None:
        raise ValueError(f"event_id has no 4-digit year suffix: {event_id!r}")
    return int(match.group(1))


def _load_fixture() -> dict[tuple[str, str], dict[int, dict]]:
    """Return ``{(event_id, state_slug): {ac_eci_no: {name, party_short, votes}}}``.

    Empty dict if fixture is absent - treated as hard failure at module
    load via the oracle-non-skip gate.
    """
    if not FIXTURE.is_file():
        return {}
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict[int, dict]] = {}
    for key, winners in payload.get("slices", {}).items():
        event_id, state_slug = key.split("/", 1)
        out[(event_id, state_slug)] = {
            int(ac): {
                "name": w["name"],
                "party_short": w["party_short"],
                "votes": int(w["votes"]),
            }
            for ac, w in winners.items()
        }
    return out


_FIXTURE = _load_fixture()


def _slice_csv_path(event_id: str, state_slug: str) -> Path:
    """Return the per-slice candidacies.csv path under the new layout."""
    year = _event_year(event_id)
    return (
        ELECTIONS_ASSEMBLY_ROOT
        / f"state={state_slug}"
        / f"election={year}"
        / "candidacies.csv"
    )


# Slices the fixture knows about but whose CSVs are NOT in this corpus.
# These are EXPECTED absences (not regressions) and are filtered out of
# the parametrize set so the per-slice tests don't fail spuriously. The
# oracle-non-skip gate's floor (MIN_SLICES_FOR_NON_SKIP) is derived AFTER
# this exclusion so a real CSV regression - one that drops a previously
# shipped slice - still trips the gate.
#
# Post-F1.1 Path A (2026-06-06): Delhi 2020 (AcGenFeb2020/delhi) MOVED OUT
# of this set; the LGD-spine extension lets emit_state_assembly bind every
# Delhi AC the fixture references, and the Delhi candidacies.csv now ships
# under the assembly/ layout. The 6 remaining slices are GENUINE upstream
# gaps - TCPD's All_States_AE.csv (vintage 2026-06-05) does not yet
# include the 2026 assembly cycle or Rajasthan's November-2023 election.
_KNOWN_ABSENT_SLICES: frozenset[tuple[str, str]] = frozenset(
    {
        # AcGenMay2026/* - 2026 assembly cycle not in TCPD AE vintage 2026-06-05
        ("AcGenMay2026", "assam"),
        ("AcGenMay2026", "kerala"),
        ("AcGenMay2026", "tamil-nadu"),
        ("AcGenMay2026", "west-bengal"),
        ("AcGenMay2026", "puducherry"),
        # AcGenNov2023/rajasthan - TCPD AE compilation stops at 2021 for
        # Rajasthan (verified via DuckDB scan against
        # datasets/ephemeral/All_States_AE.csv in the F1.1 Path A receipt).
        ("AcGenNov2023", "rajasthan"),
    }
)


_SLICE_PATHS: dict[tuple[str, str], Path] = {
    key: _slice_csv_path(*key)
    for key in _FIXTURE.keys()
    if key not in _KNOWN_ABSENT_SLICES
}
SLICES: list[tuple[str, str]] = sorted(
    k for k, p in _SLICE_PATHS.items() if p.is_file()
)

# Floor for oracle-non-skip. The post-F1.1-Path-A corpus has 35 of the
# 41 fixture slices on disk (41 - 6 known-absent = 35). If a future
# corpus refresh adds the 6 known-absent slices the floor rises; if a
# corpus regression drops one of the 35, this trips.
MIN_SLICES_FOR_NON_SKIP = 35


def test_oracle_non_skip_gate() -> None:
    """Parent plan section 22.6 oracle-non-skip: the CSV oracle MUST
    actively execute.

    A blanket skip (e.g. ``skipif csv absent`` quietly reading as false-
    green) would mask a real deletion or rebuild regression after X1b
    flips the parquet store off. This gate fails LOUD if the per-slice
    run-set drops below the expected floor.
    """
    assert _FIXTURE, "parity fixture absent on disk: " + FIXTURE.as_posix()
    assert len(SLICES) >= MIN_SLICES_FOR_NON_SKIP, (
        f"oracle-non-skip violation: only {len(SLICES)} of "
        f"{len(_SLICE_PATHS)} expected slices have on-disk CSV "
        f"(floor {MIN_SLICES_FOR_NON_SKIP}). This is the false-green guard "
        f"for the post-X1b world; a missing slice usually means a "
        f"candidacies.csv was deleted or a state-year was dropped from "
        f"the elections corpus."
    )


@pytest.mark.parametrize(
    "event_id,state_slug",
    SLICES,
    ids=lambda v: v,
)
def test_per_ac_fptp_winner_matches_fixture(event_id: str, state_slug: str) -> None:
    """For each AC in the slice, the per-state candidacies.csv's max-votes
    candidate MUST equal the snapshotted winner by name + votes.

    Per-AC tolerance: ZERO. A single mismatch fails the slice - this is
    citizen-visible ranking.

    NOTA: ``candidacies.csv`` carries only registered candidates by
    construction (NOTA totals live in ``summary.csv``); the pre-rewrite
    ``WHERE indicator_id = 'candidate-votes-polled'`` filter is therefore
    structurally equivalent to "no filter" in the new shape.

    party_short is NOT compared between fixture and CSV here: the
    legacy SQLite carried the verbatim ECI string, the CSV ``party_id``
    field is curated and not always populated yet (party resolution rides
    a separate B2b.5.x sub-row). Name + votes uniquely identify the
    winner; the party-label fallback chain is covered by the pinned
    vitest in ``frontend/src/lib/psephlab/canonical-loaders.test.ts``.
    """
    fixture_winners = _FIXTURE[(event_id, state_slug)]
    if not fixture_winners:
        pytest.skip(f"{event_id}/{state_slug}: fixture has no winners")

    csv_path = _SLICE_PATHS[(event_id, state_slug)]
    columns_sql = "{" + ", ".join(
        f"'{name}': '{dtype}'" for name, dtype in _CANDIDACIES_COLUMNS.items()
    ) + "}"

    con = duckdb.connect(":memory:")
    rows = con.execute(f"""
        WITH cand_rows AS (
            SELECT
                constituency_no,
                candidate_name AS name,
                votes
            FROM read_csv('{csv_path.as_posix()}', columns={columns_sql})
        ),
        ranked AS (
            SELECT
                constituency_no AS ac_eci_no,
                name,
                votes,
                ROW_NUMBER() OVER (
                    PARTITION BY constituency_no
                    ORDER BY votes DESC, name ASC
                ) AS rn
            FROM cand_rows
        )
        SELECT ac_eci_no, name, votes
        FROM ranked
        WHERE rn = 1
        ORDER BY ac_eci_no
    """).fetchall()
    csv_winners = {
        int(ac_eci): {"name": name, "votes": int(votes)}
        for ac_eci, name, votes in rows
    }

    fixture_acs = set(fixture_winners.keys())
    csv_acs = set(csv_winners.keys())
    missing_in_csv = fixture_acs - csv_acs
    missing_in_fixture = csv_acs - fixture_acs
    assert not missing_in_csv, (
        f"{event_id}/{state_slug}: ACs in fixture missing from canonical "
        f"CSV: {sorted(missing_in_csv)[:5]}"
    )
    assert not missing_in_fixture, (
        f"{event_id}/{state_slug}: ACs in canonical CSV missing from "
        f"fixture (extra ghosts): {sorted(missing_in_fixture)[:5]}"
    )

    mismatches: list[str] = []
    for ac_eci, fw in fixture_winners.items():
        cw = csv_winners[ac_eci]
        if fw["name"] != cw["name"]:
            mismatches.append(
                f"  AC {ac_eci}: fixture='{fw['name']}' ({fw['votes']}) "
                f"!= CSV='{cw['name']}' ({cw['votes']})"
            )
        elif fw["votes"] != cw["votes"]:
            mismatches.append(
                f"  AC {ac_eci}: name='{fw['name']}' OK but votes "
                f"fixture={fw['votes']} != CSV={cw['votes']}"
            )
    assert not mismatches, (
        f"{event_id}/{state_slug}: {len(mismatches)} per-AC FPTP winner "
        f"mismatches:\n" + "\n".join(mismatches[:10])
    )
