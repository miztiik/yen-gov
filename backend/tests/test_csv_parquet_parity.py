"""Cross-format parity gate (parent plan section 22.6).

Each ``test_<family>`` queries the SAME logical question against
(a) the surviving parquet artifacts and (b) the newly-emitted long-format
CSV siblings, asserting identical row counts + per-cell equality after a
typed read. No mocks (Holy Law #7); both sides read REAL on-disk artifacts.
Tests skip cleanly when either side is missing on this machine.

This is the deletion-safety gate for chunk B2b: the CSV values must match
the parquet values before any parquet writer is removed by chunk B3 /
parquet store deleted by chunk X1b.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _exists(*paths: Path) -> bool:
    return all(p.exists() for p in paths)


@pytest.fixture(scope="module")
def lgd_eci_to_slug() -> dict[str, str]:
    from yen_gov.canonical.reingest.energy_datapoints import load_eci_to_slug

    register = REPO_ROOT / "datasets" / "taxonomy" / "lgd_states.json"
    if not register.exists():
        pytest.skip(f"missing {register}")
    return load_eci_to_slug(register)


def test_energy(lgd_eci_to_slug: dict[str, str]) -> None:
    """B2b.1 cross-format parity: every (entity, year, indicator) row in the
    six energy parquets MUST appear as exactly one row in
    ``datasets/data/datapoints/geo/<indicator_id>.csv`` with matching value
    and source_id (after the ECI -> LGD entity re-key).
    """
    parquet_dir = REPO_ROOT / "datasets" / "energy"
    csv_dir = REPO_ROOT / "datasets" / "data" / "datapoints" / "geo"
    parquet_paths = sorted(parquet_dir.glob("*.parquet"))
    if not parquet_paths:
        pytest.skip(f"no parquets under {parquet_dir}")
    if not csv_dir.exists():
        pytest.skip(f"missing CSV target {csv_dir}")

    parquet_glob = (parquet_dir / "*.parquet").as_posix()
    parquet_rows = duckdb.sql(
        "SELECT entity_id, year, indicator_id, value_numeric, source_id "
        f"FROM read_parquet('{parquet_glob}') "
        "ORDER BY indicator_id, entity_id, year"
    ).fetchall()
    if not parquet_rows:
        pytest.skip("parquet corpus empty")

    indicator_ids = sorted({r[2] for r in parquet_rows})
    csv_files = {i: csv_dir / f"{i}.csv" for i in indicator_ids}
    missing = [i for i, p in csv_files.items() if not p.exists()]
    assert not missing, (
        f"{len(missing)} energy indicator CSV(s) absent under {csv_dir} "
        f"(first: {missing[:3]}); B2b.1 emit not run?"
    )

    csv_index: dict[tuple[str, int, str], tuple[float | None, str]] = {}
    for indicator_id, csv_path in csv_files.items():
        rows = duckdb.sql(
            "SELECT entity_id, time, value, source_id FROM read_csv("
            f"'{csv_path.as_posix()}', "
            "columns={'entity_id': 'VARCHAR', 'time': 'INTEGER', "
            "'value': 'DOUBLE', 'source_id': 'VARCHAR'}, header=true)"
        ).fetchall()
        for entity_id, time, value, source_id in rows:
            key = (entity_id, int(time), indicator_id)
            assert key not in csv_index, (
                f"CSV duplicate PK row in {csv_path.name}: {key}"
            )
            csv_index[key] = (value, source_id)

    assert len(csv_index) == len(parquet_rows), (
        f"row-count parity failed: parquet={len(parquet_rows)} vs csv={len(csv_index)}"
    )

    mismatches: list[str] = []
    for eci_entity_id, year, indicator_id, parquet_value, source_id in parquet_rows:
        lgd_entity_id = (
            "IN"
            if eci_entity_id == "IN"
            else lgd_eci_to_slug.get(eci_entity_id.removeprefix("IN-"), eci_entity_id)
        )
        key = (lgd_entity_id, int(year), indicator_id)
        if key not in csv_index:
            mismatches.append(f"missing csv row for {key}")
            continue
        csv_value, csv_source_id = csv_index[key]
        if csv_value is None or parquet_value is None:
            if csv_value is not parquet_value:
                mismatches.append(f"{key}: null-mismatch parquet={parquet_value} csv={csv_value}")
        elif float(csv_value) != float(parquet_value):
            mismatches.append(
                f"{key}: value parquet={parquet_value!r} csv={csv_value!r}"
            )
        if csv_source_id != source_id:
            mismatches.append(
                f"{key}: source_id parquet={source_id!r} csv={csv_source_id!r}"
            )
        if len(mismatches) >= 5:
            break

    assert not mismatches, "cross-format parity violations:\n  " + "\n  ".join(mismatches)


@pytest.fixture(scope="module")
def lgd_district_to_entity() -> dict[str, str]:
    from yen_gov.canonical.reingest.livestock_datapoints import (
        load_lgd_district_to_geo_entity,
    )

    geo_csv = REPO_ROOT / "datasets" / "data" / "entities" / "geo.csv"
    if not geo_csv.exists():
        pytest.skip(f"missing {geo_csv}")
    return load_lgd_district_to_geo_entity(geo_csv)


def test_livestock(
    lgd_eci_to_slug: dict[str, str],
    lgd_district_to_entity: dict[str, str],
) -> None:
    """B2b.2 cross-format parity: every (entity, year, indicator) row in the
    three livestock parquets MUST appear as exactly one row in
    ``datasets/data/datapoints/geo/<indicator_id>.csv`` with matching value
    and source_id (after the ECI -> LGD state slug AND
    LGD-district -> ``state/district`` re-keys).
    """
    parquet_dir = REPO_ROOT / "datasets" / "livestock"
    csv_dir = REPO_ROOT / "datasets" / "data" / "datapoints" / "geo"
    parquet_paths = sorted(parquet_dir.glob("*.parquet"))
    if not parquet_paths:
        pytest.skip(f"no parquets under {parquet_dir}")
    if not csv_dir.exists():
        pytest.skip(f"missing CSV target {csv_dir}")

    parquet_glob = (parquet_dir / "*.parquet").as_posix()
    parquet_rows = duckdb.sql(
        "SELECT entity_id, year, indicator_id, value_numeric, source_id "
        f"FROM read_parquet('{parquet_glob}') "
        "ORDER BY indicator_id, entity_id, year"
    ).fetchall()
    if not parquet_rows:
        pytest.skip("parquet corpus empty")

    indicator_ids = sorted({r[2] for r in parquet_rows})
    csv_files = {i: csv_dir / f"{i}.csv" for i in indicator_ids}
    missing = [i for i, p in csv_files.items() if not p.exists()]
    assert not missing, (
        f"{len(missing)} livestock indicator CSV(s) absent under {csv_dir} "
        f"(first: {missing[:3]}); B2b.2 emit not run?"
    )

    csv_index: dict[tuple[str, int, str], tuple[float | None, str]] = {}
    for indicator_id, csv_path in csv_files.items():
        rows = duckdb.sql(
            "SELECT entity_id, time, value, source_id FROM read_csv("
            f"'{csv_path.as_posix()}', "
            "columns={'entity_id': 'VARCHAR', 'time': 'INTEGER', "
            "'value': 'DOUBLE', 'source_id': 'VARCHAR'}, header=true)"
        ).fetchall()
        for entity_id, time, value, source_id in rows:
            key = (entity_id, int(time), indicator_id)
            assert key not in csv_index, (
                f"CSV duplicate PK row in {csv_path.name}: {key}"
            )
            csv_index[key] = (value, source_id)

    def remap(eci_entity_id: str) -> str:
        if eci_entity_id == "IN":
            return "IN"
        tail = eci_entity_id.removeprefix("IN-")
        if "-D" in tail:
            _state_code, _, district_id = tail.partition("-D")
            return lgd_district_to_entity.get(district_id, eci_entity_id)
        return lgd_eci_to_slug.get(tail, eci_entity_id)

    assert len(csv_index) == len(parquet_rows), (
        f"row-count parity failed: parquet={len(parquet_rows)} vs csv={len(csv_index)}"
    )

    mismatches: list[str] = []
    for eci_entity_id, year, indicator_id, parquet_value, source_id in parquet_rows:
        lgd_entity_id = remap(eci_entity_id)
        key = (lgd_entity_id, int(year), indicator_id)
        if key not in csv_index:
            mismatches.append(f"missing csv row for {key}")
            continue
        csv_value, csv_source_id = csv_index[key]
        if csv_value is None or parquet_value is None:
            if csv_value is not parquet_value:
                mismatches.append(
                    f"{key}: null-mismatch parquet={parquet_value} csv={csv_value}"
                )
        elif float(csv_value) != float(parquet_value):
            mismatches.append(
                f"{key}: value parquet={parquet_value!r} csv={csv_value!r}"
            )
        if csv_source_id != source_id:
            mismatches.append(
                f"{key}: source_id parquet={source_id!r} csv={csv_source_id!r}"
            )
        if len(mismatches) >= 5:
            break

    assert not mismatches, "cross-format parity violations:\n  " + "\n  ".join(mismatches)
