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

def test_governments() -> None:
    """B2b.3 cross-format parity: term-shape per plan section 20.4.

    Asserts the three emitted CSVs reconstruct the two surviving parquets:

    * `entities/office.csv` row count == `dim_offices.parquet` row
      count; `(office_id, name, office_kind)` carry through verbatim (with
      `office_kind` lower-cased); `jurisdiction_entity_id` re-keys to the
      LGD slug.
    * `entities/holder.csv` row count == `COUNT(DISTINCT person_slug)`
      in the holdings parquet.
    * `datapoints/office_holdings.csv` row count ==
      `governments_office_holdings.parquet` row count; per-row
      `(office_id, term_start)` PK + `(holder_id, term_end, source_id)`
      payload matches after the ECI -> party_id re-key.
    """
    parquet_dir = REPO_ROOT / "datasets" / "governments"
    data_dir = REPO_ROOT / "datasets" / "data"
    office_parquet = parquet_dir / "dim_offices.parquet"
    holdings_parquet = parquet_dir / "governments_office_holdings.parquet"
    office_csv = data_dir / "entities" / "office.csv"
    holder_csv = data_dir / "entities" / "holder.csv"
    holdings_csv = data_dir / "datapoints" / "office_holdings.csv"
    geo_csv = data_dir / "entities" / "geo.csv"
    party_csv = data_dir / "entities" / "party.csv"

    if not _exists(office_parquet, holdings_parquet):
        pytest.skip("governments parquets absent")
    if not _exists(office_csv, holder_csv, holdings_csv):
        pytest.skip("B2b.3 emit not run; CSVs absent")
    if not _exists(geo_csv, party_csv):
        pytest.skip("entity catalogue CSVs absent")

    from yen_gov.canonical.reingest.governments_term_shape import (
        load_eci_state_to_geo_entity,
        load_party_eci_to_party_id,
    )

    eci_state_to_geo = load_eci_state_to_geo_entity(geo_csv)
    party_eci_to_id = load_party_eci_to_party_id(party_csv)

    office_parquet_rows = duckdb.sql(
        "SELECT office_id, entity_id, role, label "
        f"FROM read_parquet('{office_parquet.as_posix()}') "
        "ORDER BY office_id"
    ).fetchall()
    office_csv_rows = duckdb.sql(
        "SELECT office_id, name, office_kind, jurisdiction_entity_id, portfolio "
        f"FROM read_csv('{office_csv.as_posix()}', "
        "columns={'office_id': 'VARCHAR', 'name': 'VARCHAR', "
        "'office_kind': 'VARCHAR', 'jurisdiction_entity_id': 'VARCHAR', "
        "'portfolio': 'VARCHAR'}, header=true) "
        "ORDER BY office_id"
    ).fetchall()
    assert len(office_csv_rows) == len(office_parquet_rows), (
        f"office row-count parity: parquet={len(office_parquet_rows)} "
        f"vs csv={len(office_csv_rows)}"
    )
    office_csv_by_id = {r[0]: r for r in office_csv_rows}
    office_mismatches: list[str] = []
    for office_id, entity_id, role, label in office_parquet_rows:
        csv_row = office_csv_by_id.get(office_id)
        if csv_row is None:
            office_mismatches.append(f"missing csv office {office_id!r}")
            continue
        expected_jurisdiction = (
            "IN" if entity_id == "IN" else eci_state_to_geo.get(
                entity_id.removeprefix("IN-"), entity_id
            )
        )
        if csv_row[1] != label:
            office_mismatches.append(
                f"{office_id}: name parquet={label!r} csv={csv_row[1]!r}"
            )
        if csv_row[2] != str(role).lower():
            office_mismatches.append(
                f"{office_id}: office_kind parquet={role!r} csv={csv_row[2]!r}"
            )
        if csv_row[3] != expected_jurisdiction:
            office_mismatches.append(
                f"{office_id}: jurisdiction parquet={entity_id!r} "
                f"expected={expected_jurisdiction!r} csv={csv_row[3]!r}"
            )
        if csv_row[4] is not None:
            office_mismatches.append(
                f"{office_id}: portfolio expected null, got {csv_row[4]!r}"
            )
        if len(office_mismatches) >= 5:
            break
    assert not office_mismatches, (
        "office.csv parity violations:\n  " + "\n  ".join(office_mismatches)
    )

    distinct_holders = duckdb.sql(
        "SELECT person_slug, ANY_VALUE(person_name) AS person_name, "
        "ANY_VALUE(CAST(party_eci_code AS VARCHAR)) AS party_eci_code "
        f"FROM read_parquet('{holdings_parquet.as_posix()}') "
        "WHERE person_slug IS NOT NULL "
        "GROUP BY person_slug ORDER BY person_slug"
    ).fetchall()
    holder_csv_rows = duckdb.sql(
        "SELECT holder_id, person_name, party_id "
        f"FROM read_csv('{holder_csv.as_posix()}', "
        "columns={'holder_id': 'VARCHAR', 'person_name': 'VARCHAR', "
        "'party_id': 'VARCHAR'}, header=true) ORDER BY holder_id"
    ).fetchall()
    assert len(holder_csv_rows) == len(distinct_holders), (
        f"holder row-count parity: distinct-slugs={len(distinct_holders)} "
        f"vs csv={len(holder_csv_rows)}"
    )
    holder_csv_by_id = {r[0]: r for r in holder_csv_rows}
    holder_mismatches: list[str] = []
    for slug, person_name, eci in distinct_holders:
        csv_row = holder_csv_by_id.get(slug)
        if csv_row is None:
            holder_mismatches.append(f"missing csv holder {slug!r}")
            continue
        if csv_row[1] != person_name:
            holder_mismatches.append(
                f"{slug}: person_name parquet={person_name!r} csv={csv_row[1]!r}"
            )
        expected_party = None if eci is None else party_eci_to_id.get(eci)
        if csv_row[2] != expected_party:
            holder_mismatches.append(
                f"{slug}: party_id eci={eci!r} expected={expected_party!r} "
                f"csv={csv_row[2]!r}"
            )
        if len(holder_mismatches) >= 5:
            break
    assert not holder_mismatches, (
        "holder.csv parity violations:\n  " + "\n  ".join(holder_mismatches)
    )

    holdings_parquet_rows = duckdb.sql(
        "SELECT office_id, "
        "strftime(start_date, '%Y-%m-%d') AS term_start, "
        "person_slug, "
        "CASE WHEN end_date IS NULL THEN NULL "
        "ELSE strftime(end_date, '%Y-%m-%d') END AS term_end, "
        "source_id "
        f"FROM read_parquet('{holdings_parquet.as_posix()}') "
        "ORDER BY office_id, term_start"
    ).fetchall()
    holdings_csv_rows = duckdb.sql(
        "SELECT office_id, term_start, holder_id, term_end, source_id "
        f"FROM read_csv('{holdings_csv.as_posix()}', "
        "columns={'office_id': 'VARCHAR', 'term_start': 'VARCHAR', "
        "'holder_id': 'VARCHAR', 'term_end': 'VARCHAR', "
        "'source_id': 'VARCHAR'}, header=true) "
        "ORDER BY office_id, term_start"
    ).fetchall()
    assert len(holdings_csv_rows) == len(holdings_parquet_rows), (
        f"holdings row-count parity: parquet={len(holdings_parquet_rows)} "
        f"vs csv={len(holdings_csv_rows)}"
    )
    csv_index: dict[tuple[str, str], tuple[str | None, str | None, str]] = {}
    for office_id, term_start, holder_id, term_end, source_id in holdings_csv_rows:
        key = (office_id, term_start)
        assert key not in csv_index, f"holdings duplicate PK {key}"
        csv_index[key] = (holder_id, term_end, source_id)

    holdings_mismatches: list[str] = []
    for office_id, term_start, person_slug, term_end, source_id in holdings_parquet_rows:
        key = (office_id, term_start)
        if key not in csv_index:
            holdings_mismatches.append(f"missing csv holdings row {key}")
            continue
        csv_holder, csv_term_end, csv_source_id = csv_index[key]
        if csv_holder != person_slug:
            holdings_mismatches.append(
                f"{key}: holder parquet={person_slug!r} csv={csv_holder!r}"
            )
        if csv_term_end != term_end:
            holdings_mismatches.append(
                f"{key}: term_end parquet={term_end!r} csv={csv_term_end!r}"
            )
        if csv_source_id != source_id:
            holdings_mismatches.append(
                f"{key}: source_id parquet={source_id!r} csv={csv_source_id!r}"
            )
        if len(holdings_mismatches) >= 5:
            break
    assert not holdings_mismatches, (
        "office_holdings.csv parity violations:\n  "
        + "\n  ".join(holdings_mismatches)
    )


def test_methodology_breaks() -> None:
    """B2b.4.1 cross-format parity: every row in
    ``datasets/taxonomy/methodology_breaks.parquet`` MUST appear as exactly
    one row in ``datasets/data/methodology_breaks.csv`` with verbatim
    column equality (no re-keys; 1:1 projection across all seven columns).
    """
    parquet_path = (
        REPO_ROOT / "datasets" / "taxonomy" / "methodology_breaks.parquet"
    )
    csv_path = REPO_ROOT / "datasets" / "data" / "methodology_breaks.csv"
    if not parquet_path.exists():
        pytest.skip(f"missing {parquet_path}")
    if not csv_path.exists():
        pytest.skip(f"missing {csv_path}; B2b.4.1 emit not run")

    cols = (
        "methodology_version",
        "at_year",
        "at_period_seq",
        "kind",
        "note",
        "publisher_url",
        "supersedes_methodology_version",
    )
    parquet_rows = duckdb.sql(
        "SELECT methodology_version, at_year, at_period_seq, kind, note, "
        "publisher_url, supersedes_methodology_version "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY methodology_version, at_year, at_period_seq"
    ).fetchall()
    csv_rows = duckdb.sql(
        "SELECT methodology_version, at_year, at_period_seq, kind, note, "
        "publisher_url, supersedes_methodology_version FROM read_csv("
        f"'{csv_path.as_posix()}', "
        "columns={'methodology_version': 'VARCHAR', 'at_year': 'INTEGER', "
        "'at_period_seq': 'INTEGER', 'kind': 'VARCHAR', 'note': 'VARCHAR', "
        "'publisher_url': 'VARCHAR', "
        "'supersedes_methodology_version': 'VARCHAR'}, header=true) "
        "ORDER BY methodology_version, at_year, at_period_seq"
    ).fetchall()

    assert len(csv_rows) == len(parquet_rows), (
        f"row-count parity failed: parquet={len(parquet_rows)} "
        f"vs csv={len(csv_rows)}"
    )

    mismatches: list[str] = []
    for parquet_row, csv_row in zip(parquet_rows, csv_rows, strict=True):
        for idx, name in enumerate(cols):
            if parquet_row[idx] != csv_row[idx]:
                mismatches.append(
                    f"{parquet_row[0]!r}@{parquet_row[1]}/{parquet_row[2]}: "
                    f"{name} parquet={parquet_row[idx]!r} csv={csv_row[idx]!r}"
                )
        if len(mismatches) >= 5:
            break
    assert not mismatches, (
        "methodology_breaks.csv parity violations:\n  "
        + "\n  ".join(mismatches)
    )
