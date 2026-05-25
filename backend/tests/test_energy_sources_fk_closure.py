"""FK-closure test — every source_id on any energy fact-table appears in
``datasets/taxonomy/sources.parquet``.

The writer's _validate_fks gate enforces this at write time (and aborts
the emit if violated). This test is the at-rest belt-and-suspenders:
after lift, every (entity_id × year × indicator_id) row's source_id
must FK-close into the citation ledger so the citizen-facing footnote
renderer can always look up the (producer, title, vintage) triple.

Reads the 4 P.1.A fact-tables + sources.parquet via DuckDB; deliberately
no in-memory Python join (Parquet → DuckDB → result; same code path the
frontend reader uses).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENERGY_DIR = REPO_ROOT / "datasets" / "energy"
SOURCES = REPO_ROOT / "datasets" / "taxonomy" / "sources.parquet"
P1A_STEMS = [
    "energy_installed_capacity",
    "energy_generation",
    "energy_demand_supply",
    "energy_distribution_performance",
]


pytestmark = pytest.mark.skipif(
    not SOURCES.is_file()
    or not all((ENERGY_DIR / f"{s}.parquet").is_file() for s in P1A_STEMS),
    reason=(
        "energy parquets or taxonomy/sources.parquet not on disk; "
        "run `python -m yen_gov emit-taxonomy --root .` "
        "then `python -m yen_gov lift-energy --root .`"
    ),
)


@pytest.mark.parametrize("stem", P1A_STEMS)
def test_every_observation_source_id_resolves(stem: str) -> None:
    """For each fact-table, EVERY observation.source_id MUST exist as a
    row in sources.parquet — no dangling FKs. Returns the set of
    unresolved ids (empty = pass)."""
    parquet = ENERGY_DIR / f"{stem}.parquet"
    con = duckdb.connect(":memory:")
    try:
        unresolved = con.execute(
            f"""
            SELECT DISTINCT obs.source_id
            FROM read_parquet('{parquet.as_posix()}') AS obs
            LEFT JOIN read_parquet('{SOURCES.as_posix()}') AS src
              ON obs.source_id = src.source_id
            WHERE src.source_id IS NULL
            """
        ).fetchall()
    finally:
        con.close()
    assert not unresolved, (
        f"{stem}.parquet has dangling source_id FK(s) — every row's source_id "
        f"MUST exist in taxonomy/sources.parquet. Unresolved: "
        f"{sorted(r[0] for r in unresolved)!r}"
    )


def test_all_p1a_p1b_energy_source_ids_present() -> None:
    """Sanity: the 15 energy citation triples (7 P.1.A + 5 P.1.B + 1 P.1.C
    PR-Q + 1 P.1.C PR-R + 1 P.1.C PR-S) all made it into sources.parquet.
    If this fails, ``emit-taxonomy`` did not run ``_upsert_energy_sources``
    or the citation hashes drifted upstream."""
    expected = {
        # P.1.A (7) — 3 ICED ids rotated under ADR-0042 (vintage "" → "2024-25").
        "src-092a5dc7af3f",  # CEA Monthly Executive Summary on Power Sector
        "src-1240f07df0ac",  # ICED capacity-metatable-data
        "src-bb1d7bec8b34",  # ICED Deep Dive (per-capita + ATC + sales + ACS-ARR)
        "src-ddbfadd51428",  # ICED gen-metatable-data
        "src-99ac1fee8a50",  # RBI Hbk Table 142 — Peak Demand
        "src-9c02616a7166",  # RBI Hbk Table 142 — Peak Met
        "src-3d1d55f8a94b",  # RBI Hbk Table 140 — Installed Capacity
        # P.1.B (5) — DISCOM finance + demand/supply lift.
        # 2 ICED ids rotated under ADR-0042 (vintage "" → "2024-25").
        "src-650b1c25d1f7",  # ICED distribution-perf (billing/collection/td-loss)
        "src-0ea63ed47704",  # ICED distribution-RPO (solar/non-solar/total)
        "src-f7ce9960caba",  # RBI Hbk Table 141 — Power Requirement
        "src-97a3c47d092f",  # RBI Hbk Table 139 — Power Availability
        "src-9a38005d8713",  # RBI Hbk Table 138 — Per-Capita Availability
        # P.1.C PR-Q (1) — first canonical fuel-consumption lift.
        "src-c222a8e2cd61",  # ICED state-coal-consumption-mt
        # P.1.C PR-R (1) — rooftop solar capacity lift.
        "src-018bb42f9519",  # ICED state-rooftop-solar-capacity-mw
        # P.1.C PR-S (1) — thermal capacity retired lift (national-only,
        # Pattern A-facet on the 5-bucket fuel_type axis).
        "src-fd152bd3c6c6",  # ICED india-thermal-capacity-retired-mw
    }
    con = duckdb.connect(":memory:")
    try:
        present = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT source_id FROM read_parquet('{SOURCES.as_posix()}') "
                f"WHERE source_id IN ({', '.join(repr(s) for s in expected)})"
            ).fetchall()
        }
    finally:
        con.close()
    missing = expected - present
    assert not missing, (
        f"taxonomy/sources.parquet missing {len(missing)} of the 15 P.1.A+P.1.B+P.1.C "
        f"energy citation rows: {sorted(missing)!r}. Re-run "
        f"`python -m yen_gov emit-taxonomy --root .`"
    )
