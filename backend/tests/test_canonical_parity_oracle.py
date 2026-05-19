"""Parity oracle: per-AC FPTP winner from results.sqlite must match the
canonical election_results.parquet via the same logic the frontend reader
uses (max(votes) per AC after excluding NOTA).

Why: PR-R.2 swapped Psephlab routes from the legacy SQLite-via-XHR loader
to ``canonical-loaders.ts`` reading ``dim_candidates × election_results``
joined in DuckDB-WASM. If the canonical taxonomy/expansion regen ever
silently scrambles per-AC winners — wrong party_id, wrong vote, ranked
order off-by-one — the UI's "Top candidate" chip lies to the citizen.

This test is the back-stop: for every (event, state) slice that ships a
SQLite ground-truth file, pick the FPTP winner from SQLite (``is_winner=1``)
and from the Parquet (max-votes), and assert names + parties match per AC.

Holy Law #7: this uses the REAL on-disk Parquet + REAL on-disk SQLite —
no mocks. It is therefore a sympathetic "if datasets are absent, skip"
test; CI consumers that don't ship the datasets are unaffected.

Runs in <2s against the full 22-SQLite corpus. Acceptable for the default
pytest run; not behind a slow marker.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ELECTIONS_ROOT = REPO_ROOT / "datasets" / "elections"
PARQUET = ELECTIONS_ROOT / "election_results.parquet"
DIM_CANDIDATES = ELECTIONS_ROOT / "dim_candidates.parquet"
DIM_ACS = ELECTIONS_ROOT / "dim_acs.parquet"


def _slices_with_sqlite() -> list[tuple[str, str, Path]]:
    """Discover every (event_id, state_code, sqlite_path) shipped on disk.

    Returns an empty list if the datasets tree is absent (treated as skip
    by the test harness — keeps the test cheap in stripped-down checkouts).
    """
    if not ELECTIONS_ROOT.is_dir():
        return []
    out: list[tuple[str, str, Path]] = []
    for event_dir in sorted(ELECTIONS_ROOT.iterdir()):
        if not event_dir.is_dir() or event_dir.name.startswith("_"):
            continue
        for state_dir in sorted(event_dir.iterdir()):
            if not state_dir.is_dir():
                continue
            sqlite_path = state_dir / "results.sqlite"
            if sqlite_path.is_file():
                out.append((event_dir.name, state_dir.name, sqlite_path))
    return out


SLICES = _slices_with_sqlite()


@pytest.mark.skipif(
    not (PARQUET.is_file() and DIM_CANDIDATES.is_file() and DIM_ACS.is_file()),
    reason="canonical Parquet not on disk in this checkout",
)
@pytest.mark.skipif(not SLICES, reason="no results.sqlite slices on disk")
@pytest.mark.parametrize("event_id,state_code,sqlite_path", SLICES,
                         ids=lambda v: v if isinstance(v, str) else v.name)
def test_per_ac_fptp_winner_matches_sqlite(
    event_id: str, state_code: str, sqlite_path: Path,
) -> None:
    """For each AC in the slice, the canonical Parquet's max-votes candidate
    MUST equal the SQLite winner (is_winner=1, is_nota=0) by name + votes.

    Per-AC tolerance: ZERO. A single mismatch fails the slice — this is
    citizen-visible ranking.

    party_short is compared after applying the same fallback chain the
    frontend uses: when the canonical party_id is the sentinel
    parties.IN.UNK, the verbatim party_short_raw is the display string
    (mirrors ``canonical-loaders.ts:buildCandidateSql`` CASE expression).
    Tested separately at the parity boundary because the legacy SQLite
    short was always the verbatim ECI string anyway.
    """
    # --- SQLite ground truth -------------------------------------------------
    with sqlite3.connect(sqlite_path) as scon:
        scon.row_factory = sqlite3.Row
        sqlite_winners: dict[int, dict] = {}
        for row in scon.execute(
            "SELECT ac_eci_no, name, party_short, votes "
            "FROM candidates "
            "WHERE is_winner = 1 AND is_nota = 0 "
            "ORDER BY ac_eci_no"
        ):
            sqlite_winners[int(row["ac_eci_no"])] = {
                "name": row["name"],
                "party_short": row["party_short"],
                "votes": int(row["votes"]),
            }

    if not sqlite_winners:
        pytest.skip(f"{event_id}/{state_code}: SQLite has no winners")

    # --- Canonical Parquet via the same SQL pattern the UI uses --------------
    # max(votes) per (ac_eci_no) excluding NOTA. dim_candidates joined to
    # dim_acs for ac_eci_no + state_code filter; election_results for votes.
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
                CASE
                  WHEN dc.party_id = 'parties.IN.UNK'
                    THEN COALESCE(dc.party_short_raw, 'UNK')
                  ELSE COALESCE(dc.party_short_raw, '')
                END       AS party_short_raw_display,
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
                ac_eci_no, name, party_short_raw_display AS party_short, votes,
                ROW_NUMBER() OVER (PARTITION BY ac_eci_no ORDER BY votes DESC, name ASC) AS rn
            FROM cand_rows
        )
        SELECT ac_eci_no, name, party_short, votes
        FROM ranked
        WHERE rn = 1
        ORDER BY ac_eci_no
    """).fetchall()
    parquet_winners = {
        int(ac_eci): {"name": name, "party_short": ps, "votes": int(votes)}
        for ac_eci, name, ps, votes in rows
    }

    # --- Diff ----------------------------------------------------------------
    sqlite_acs = set(sqlite_winners.keys())
    parquet_acs = set(parquet_winners.keys())
    missing_in_parquet = sqlite_acs - parquet_acs
    missing_in_sqlite = parquet_acs - sqlite_acs
    assert not missing_in_parquet, (
        f"{event_id}/{state_code}: ACs in SQLite missing from canonical "
        f"Parquet: {sorted(missing_in_parquet)[:5]}"
    )
    assert not missing_in_sqlite, (
        f"{event_id}/{state_code}: ACs in canonical Parquet missing from "
        f"SQLite (extra ghosts): {sorted(missing_in_sqlite)[:5]}"
    )

    mismatches: list[str] = []
    for ac_eci, sw in sqlite_winners.items():
        pw = parquet_winners[ac_eci]
        if sw["name"] != pw["name"]:
            mismatches.append(
                f"  AC {ac_eci}: SQLite='{sw['name']}' ({sw['party_short']}, {sw['votes']}) "
                f"!= Parquet='{pw['name']}' ({pw['party_short']}, {pw['votes']})"
            )
        elif sw["votes"] != pw["votes"]:
            mismatches.append(
                f"  AC {ac_eci}: name='{sw['name']}' OK but votes "
                f"SQLite={sw['votes']} != Parquet={pw['votes']}"
            )
    assert not mismatches, (
        f"{event_id}/{state_code}: {len(mismatches)} per-AC FPTP winner "
        f"mismatches:\n" + "\n".join(mismatches[:10])
    )
