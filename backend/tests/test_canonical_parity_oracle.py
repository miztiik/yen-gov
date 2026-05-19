"""Parity oracle: per-AC FPTP winner from a pinned fixture must match the
canonical election_results.parquet via the same logic the frontend reader
uses (max(votes) per AC after excluding NOTA).

History: pre-PR-R.3 (1.8e closure) this read live ``results.sqlite`` ground
truth alongside the Parquet. PR-R.3 deletes those 41 SQLite files; the
oracle therefore retargets at a checked-in JSON fixture
(``backend/tests/fixtures/canonical_winners_2026_05_19.json``) snapshotted
from the SQLites at the PR-R.2 boundary via
``tools/snapshot_canonical_parity_oracle_fixture.py``. The question the
oracle answers is unchanged ("does the canonical store still produce the
same per-AC winners as the trusted ground truth") — only the home of the
ground truth moves from on-disk SQLite to on-disk JSON.

The fixture is immutable in normal operation. Re-snapshotting requires
restoring the legacy SQLites first and is explicitly out of scope for any
ingest / backfill PR.

Why: PR-R.2 swapped Psephlab routes from the legacy SQLite-via-XHR loader
to ``canonical-loaders.ts`` reading ``dim_candidates × election_results``
joined in DuckDB-WASM. If a future canonical-store rebuild ever silently
scrambles per-AC winners — wrong party_id, wrong vote, ranked order
off-by-one — the UI's "Top candidate" chip lies to the citizen. This test
is the back-stop.

Holy Law #7: uses the REAL on-disk Parquet + a checked-in real-data fixture
— no mocks. Skipped cleanly when the canonical Parquet is absent.

Runs in <2s against the full 41-slice corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ELECTIONS_ROOT = REPO_ROOT / "datasets" / "elections"
PARQUET = ELECTIONS_ROOT / "election_results.parquet"
DIM_CANDIDATES = ELECTIONS_ROOT / "dim_candidates.parquet"
DIM_ACS = ELECTIONS_ROOT / "dim_acs.parquet"
FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "canonical_winners_2026_05_19.json"


def _load_fixture() -> dict[tuple[str, str], dict[int, dict]]:
    """Return {(event_id, state_code): {ac_eci_no: {name, party_short, votes}}}.

    Empty dict if fixture is absent — treated as skip by the harness.
    """
    if not FIXTURE.is_file():
        return {}
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict[int, dict]] = {}
    for key, winners in payload.get("slices", {}).items():
        event_id, state_code = key.split("/", 1)
        out[(event_id, state_code)] = {
            int(ac): {
                "name": w["name"],
                "party_short": w["party_short"],
                "votes": int(w["votes"]),
            }
            for ac, w in winners.items()
        }
    return out


_FIXTURE = _load_fixture()
SLICES = sorted(_FIXTURE.keys())


@pytest.mark.skipif(
    not (PARQUET.is_file() and DIM_CANDIDATES.is_file() and DIM_ACS.is_file()),
    reason="canonical Parquet not on disk in this checkout",
)
@pytest.mark.skipif(not SLICES, reason="parity fixture not on disk")
@pytest.mark.parametrize("event_id,state_code", SLICES,
                         ids=lambda v: v)
def test_per_ac_fptp_winner_matches_fixture(event_id: str, state_code: str) -> None:
    """For each AC in the slice, the canonical Parquet's max-votes candidate
    MUST equal the snapshotted winner by name + votes.

    Per-AC tolerance: ZERO. A single mismatch fails the slice — this is
    citizen-visible ranking.

    party_short is NOT compared between fixture and Parquet here: the
    legacy SQLite carried the verbatim ECI string, the canonical Parquet
    carries the curated party_id with the verbatim short on
    ``party_short_raw``. Name + votes uniquely identify the winner;
    the party-label fallback chain (CASE WHEN party_id = 'parties.IN.UNK'
    THEN COALESCE(party_short_raw, ...)) is covered by the pinned vitest
    in frontend/src/lib/psephlab/canonical-loaders.test.ts.
    """
    fixture_winners = _FIXTURE[(event_id, state_code)]
    if not fixture_winners:
        pytest.skip(f"{event_id}/{state_code}: fixture has no winners")

    con = duckdb.connect(":memory:")
    rows = con.execute(f"""
        WITH cand_votes AS (
            SELECT
                o.entity_id AS candidate_id,
                MAX(o.value_numeric) AS votes
            FROM read_parquet('{PARQUET.as_posix()}') o
            WHERE o.period_label = '{event_id}'
              AND o.indicator_id = 'candidate-votes-polled'
            GROUP BY o.entity_id
        ),
        cand_rows AS (
            SELECT
                da.eci_no AS ac_eci_no,
                dc.name   AS name,
                cv.votes  AS votes
            FROM read_parquet('{DIM_CANDIDATES.as_posix()}') dc
            JOIN read_parquet('{DIM_ACS.as_posix()}') da
              ON da.ac_id = dc.ac_id
            JOIN cand_votes cv ON cv.candidate_id = dc.candidate_id
            WHERE dc.period_label = '{event_id}'
              AND da.state_code   = '{state_code}'
        ),
        ranked AS (
            SELECT
                ac_eci_no, name, votes,
                ROW_NUMBER() OVER (PARTITION BY ac_eci_no ORDER BY votes DESC, name ASC) AS rn
            FROM cand_rows
        )
        SELECT ac_eci_no, name, votes
        FROM ranked
        WHERE rn = 1
        ORDER BY ac_eci_no
    """).fetchall()
    parquet_winners = {
        int(ac_eci): {"name": name, "votes": int(votes)}
        for ac_eci, name, votes in rows
    }

    fixture_acs = set(fixture_winners.keys())
    parquet_acs = set(parquet_winners.keys())
    missing_in_parquet = fixture_acs - parquet_acs
    missing_in_fixture = parquet_acs - fixture_acs
    assert not missing_in_parquet, (
        f"{event_id}/{state_code}: ACs in fixture missing from canonical "
        f"Parquet: {sorted(missing_in_parquet)[:5]}"
    )
    assert not missing_in_fixture, (
        f"{event_id}/{state_code}: ACs in canonical Parquet missing from "
        f"fixture (extra ghosts): {sorted(missing_in_fixture)[:5]}"
    )

    mismatches: list[str] = []
    for ac_eci, fw in fixture_winners.items():
        pw = parquet_winners[ac_eci]
        if fw["name"] != pw["name"]:
            mismatches.append(
                f"  AC {ac_eci}: fixture='{fw['name']}' ({fw['votes']}) "
                f"!= Parquet='{pw['name']}' ({pw['votes']})"
            )
        elif fw["votes"] != pw["votes"]:
            mismatches.append(
                f"  AC {ac_eci}: name='{fw['name']}' OK but votes "
                f"fixture={fw['votes']} != Parquet={pw['votes']}"
            )
    assert not mismatches, (
        f"{event_id}/{state_code}: {len(mismatches)} per-AC FPTP winner "
        f"mismatches:\n" + "\n".join(mismatches[:10])
    )
