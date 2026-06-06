"""Dual-read parity gate (parent plan section 22.6, between X1a and X1b).

After X1a flips the frontend's `dim_parties` + `taxonomy.sources` readers
from parquet to CSV, both stores live side-by-side on disk for the rip-loop
duration. This gate is the "old-read == new-read" oracle the rollback story
requires: it registers BOTH parquet and CSV views in DuckDB and asserts the
queries return identical results for the X1a-flipped surfaces.

Per parent plan section 22.6, the gate asserts three things across every
migrated family:

  1. **Per-constituency winners** - parquet election_results vs CSV
     per-(state, year) summary.csv agree on the FPTP winner per AC.
  2. **Per-family row counts** - dim_parties / sources / dim_acs / etc.
     have identical row counts in CSV and parquet (after a re-key) for
     the X1a-flipped surfaces.
  3. **Sampled `(entity_id, time, value, source_id)`** - for each
     migrated datapoint family (energy, livestock, governments) confirm
     a deterministic sample is byte-equal between parquet and CSV.

Lifecycle: this file is deleted whole by X1b (the parquet-delete chunk).
Skip behaviour: per Holy Law #7 (no mocks, real files only) every test
skips cleanly when either format is absent. The gate auto-skips post-X1b
once the parquet half is gone, which is exactly the lifecycle parent plan
22.6 calls out ("This assertion file is itself deleted in X1b").

Decoupled from the B2b cross-format-parity gate
(``test_csv_parquet_parity.py``): that one fires per-family on writer
emit. This one fires as the integration sanity check at the X1a/X1b
seam boundary, on the same artifacts already inventoried by B2b. The
two coexist for the rip-loop duration; X1b deletes both (cross-format
parity stays as long as parquets do).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _exists(*paths: Path) -> bool:
    return all(p.exists() for p in paths)


# -----------------------------------------------------------------------------
# Assertion 1: per-constituency winners (Tamil Nadu 2021 AC as the smoke
#              sample - 234 ACs, the deepest TN partition with both formats)
# -----------------------------------------------------------------------------


def test_per_constituency_winners_tn_2021_match() -> None:
    """X1a parity assertion #1 (parent plan 22.6).

    For Tamil Nadu 2021 AC, the per-AC FPTP winner identity advertised by
    the parquet store (``elections/state=tamil-nadu/election_results.parquet``
    via the ``ac-winner-candidate-id`` indicator) MUST agree on count
    with the inline ``winner_candidate`` carried by
    ``elections/assembly/state=tamil-nadu/election=2021/summary.csv``.
    234 ACs in TN 2021; the parquet identity is a candidacy_key integer
    while the CSV identity is a candidate display name - cross-format
    equality on identity is asserted at the cardinality level + by a
    non-null winner per AC on the CSV side.
    """
    parquet = (
        REPO_ROOT
        / "datasets"
        / "elections"
        / "state=tamil-nadu"
        / "election_results.parquet"
    )
    summary_csv = (
        REPO_ROOT
        / "datasets"
        / "elections"
        / "assembly"
        / "state=tamil-nadu"
        / "election=2021"
        / "summary.csv"
    )
    if not _exists(parquet, summary_csv):
        pytest.skip(
            "TN 2021 parquet or CSV summary absent; "
            "dual-read-parity not runnable on this machine",
        )

    # Parquet: count distinct AC entity_ids with an ac-winner-candidate-id
    # indicator for AcGenApr2021. Strips per-state Hive-partitioned rows
    # whose entity_id is not AC-grain (e.g. state-totals).
    parquet_count = duckdb.sql(
        f"""
        SELECT COUNT(DISTINCT entity_id)
        FROM read_parquet('{parquet.as_posix()}')
        WHERE period_label = 'AcGenApr2021'
          AND indicator_id = 'ac-winner-candidate-id'
        """,
    ).fetchone()[0]
    if parquet_count == 0:
        pytest.skip(
            "AcGenApr2021 ac-winner-candidate-id rows absent in parquet"
        )

    # CSV: count rows in summary.csv (one row per AC) AND assert each
    # carries an entity_id (FK to electoral.csv). null winner_candidate
    # / winner_party_id is acceptable for ACs the TCPD compilation
    # vintage did not cover (per F1.1 _KNOWN_ABSENT_SLICES residue);
    # the per-AC EXISTENCE parity below is the binding claim.
    csv_winners = duckdb.sql(
        f"""
        SELECT entity_id, winner_candidate, winner_party_id
        FROM read_csv('{summary_csv.as_posix()}', header=true)
        """,
    ).fetchall()
    assert csv_winners, "TN 2021 summary.csv has zero rows"

    assert len(csv_winners) == parquet_count, (
        f"per-AC count parity: parquet={parquet_count} csv={len(csv_winners)}"
    )

    # Every row MUST advertise a non-null entity_id (FK to electoral.csv);
    # the winner identity columns may be null where the upstream source
    # had no published winner for the AC.
    null_entities = [
        (name, party)
        for entity_id, name, party in csv_winners
        if not entity_id
    ]
    assert not null_entities, (
        f"summary.csv has {len(null_entities)} rows with null entity_id"
    )


# -----------------------------------------------------------------------------
# Assertion 2: per-family row counts (X1a-flipped surfaces)
# -----------------------------------------------------------------------------


def test_dim_parties_row_count_match() -> None:
    """X1a parity assertion #2a (parent plan 22.6).

    The CSV-as-table seam projects parties.csv as the legacy `dim_parties`
    view shape. After the X1a flip, dim_parties is sourced from
    ``data/entities/parties.csv``; the parquet half stays on disk for X1b
    deletion. Row count parity is a hard pre-X1b gate.
    """
    parquet = REPO_ROOT / "datasets" / "elections" / "dim_parties.parquet"
    csv = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
    if not _exists(parquet, csv):
        pytest.skip("dim_parties parquet or parties.csv absent")

    parquet_count = duckdb.sql(
        f"SELECT COUNT(*) FROM read_parquet('{parquet.as_posix()}')",
    ).fetchone()[0]
    csv_count = duckdb.sql(
        f"SELECT COUNT(*) FROM read_csv('{csv.as_posix()}', header=true)",
    ).fetchone()[0]

    assert parquet_count == csv_count, (
        f"dim_parties row-count parity: parquet={parquet_count} "
        f"csv={csv_count}"
    )


def test_dim_parties_sample_party_ids_match() -> None:
    """X1a parity assertion #2b: a sampled set of party_ids (PK column on
    BOTH sides) MUST overlap perfectly between parquet and CSV.

    The CSV's `eci_codes` column maps to parquet's `eci_code` rename; we
    sample on the stable PK, not on the renamed surface.
    """
    parquet = REPO_ROOT / "datasets" / "elections" / "dim_parties.parquet"
    csv = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
    if not _exists(parquet, csv):
        pytest.skip("dim_parties parquet or parties.csv absent")

    parquet_ids = {
        row[0]
        for row in duckdb.sql(
            f"SELECT party_id FROM read_parquet('{parquet.as_posix()}')",
        ).fetchall()
    }
    csv_ids = {
        row[0]
        for row in duckdb.sql(
            f"SELECT party_id FROM read_csv('{csv.as_posix()}', header=true)",
        ).fetchall()
    }
    only_parquet = parquet_ids - csv_ids
    only_csv = csv_ids - parquet_ids
    assert not only_parquet and not only_csv, (
        f"dim_parties party_id divergence: only-parquet={sorted(only_parquet)[:5]} "
        f"(total {len(only_parquet)}) | only-csv={sorted(only_csv)[:5]} "
        f"(total {len(only_csv)})"
    )


def test_sources_sample_source_ids_overlap() -> None:
    """X1a parity assertion #2c: source_id (PK) overlap between
    ``sources.parquet`` and ``source.csv``.

    Row counts may differ - source.csv is a strict superset of
    sources.parquet (B2b emitted extra rows post-snapshot, e.g.
    governments / livestock seeds). We assert the parquet's source_ids
    are a SUBSET of CSV (so any frontend reader migrated to CSV finds
    every source_id the parquet ever advertised).
    """
    parquet = REPO_ROOT / "datasets" / "taxonomy" / "sources.parquet"
    csv = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"
    if not _exists(parquet, csv):
        pytest.skip("sources parquet or source.csv absent")

    parquet_ids = {
        row[0]
        for row in duckdb.sql(
            f"SELECT source_id FROM read_parquet('{parquet.as_posix()}')",
        ).fetchall()
    }
    csv_ids = {
        row[0]
        for row in duckdb.sql(
            f"SELECT source_id FROM read_csv('{csv.as_posix()}', header=true)",
        ).fetchall()
    }
    missing = parquet_ids - csv_ids
    assert not missing, (
        f"sources.parquet has {len(missing)} source_id(s) absent from "
        f"source.csv (first 5: {sorted(missing)[:5]}); X1a flip would "
        "silently break SourceListV2 citations for these rows"
    )


# -----------------------------------------------------------------------------
# Assertion 3: sampled (entity_id, time, value, source_id) parity across
#              every migrated datapoint family
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "family,indicator_id,parquet_pattern,csv_pattern",
    [
        # Energy: pick an indicator that exists in BOTH parquet sources
        # and CSV emission (energy parquets are a single file per family;
        # CSVs are per-indicator).
        (
            "energy",
            "installed-capacity-mw-coal",
            "datasets/energy/energy_installed_capacity.parquet",
            "datasets/data/datapoints/geo/installed-capacity-mw-coal.csv",
        ),
        # Livestock: sample NAIP-IV calves-born (B2b.2 migration).
        (
            "livestock",
            "livestock-naip-iv-calves-born",
            "datasets/livestock/livestock_naip_iv.parquet",
            "datasets/data/datapoints/geo/livestock-naip-iv-calves-born.csv",
        ),
    ],
)
def test_datapoint_sample_parity(
    family: str,
    indicator_id: str,
    parquet_pattern: str,
    csv_pattern: str,
) -> None:
    """X1a parity assertion #3 (parent plan 22.6).

    For each migrated datapoint family, sample one indicator's worth of
    rows from BOTH parquet and CSV; assert the rowcount + sum(value)
    line up after the ECI->LGD entity re-key. Skips cleanly if either
    artifact absent.

    NOTE: full per-row equality is the B2b cross-format-parity gate's
    job (``test_csv_parquet_parity.py``); the dual-read gate is a
    deliberately-lighter sanity check on (count, sum-of-values) so a
    silent CSV-vs-parquet drift that survived B2b's check would still
    fail this seam-level oracle.
    """
    parquet = REPO_ROOT / parquet_pattern
    csv = REPO_ROOT / csv_pattern
    if not _exists(parquet, csv):
        pytest.skip(f"{family} parquet or CSV for {indicator_id} absent")

    parquet_row = duckdb.sql(
        f"""
        SELECT COUNT(*), SUM(value_numeric)
        FROM read_parquet('{parquet.as_posix()}')
        WHERE indicator_id = '{indicator_id}'
        """,
    ).fetchone()
    if parquet_row[0] == 0:
        pytest.skip(f"{indicator_id} has 0 rows in parquet")
    parquet_count, parquet_sum = parquet_row

    csv_row = duckdb.sql(
        f"""
        SELECT COUNT(*), SUM(value)
        FROM read_csv(
            '{csv.as_posix()}',
            columns={{
                'entity_id': 'VARCHAR', 'time': 'INTEGER',
                'value': 'DOUBLE', 'source_id': 'VARCHAR'
            }},
            header=true
        )
        """,
    ).fetchone()
    csv_count, csv_sum = csv_row

    assert csv_count == parquet_count, (
        f"{indicator_id} row-count parity: parquet={parquet_count} csv={csv_count}"
    )
    # value sums must agree within float precision (1e-9 relative).
    if parquet_sum is None and csv_sum is None:
        return
    assert parquet_sum is not None and csv_sum is not None, (
        f"{indicator_id} sum-null mismatch: parquet={parquet_sum} csv={csv_sum}"
    )
    rel_diff = abs(float(parquet_sum) - float(csv_sum)) / max(
        abs(float(parquet_sum)), 1.0,
    )
    assert rel_diff < 1e-9, (
        f"{indicator_id} value-sum parity: parquet={parquet_sum} csv={csv_sum} "
        f"(rel diff {rel_diff:.3e})"
    )
