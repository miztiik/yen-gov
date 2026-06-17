"""Row 2 writer-unit gate: CEA installed-capacity -> faceted geo_by_fuel CSV.

Locks the faceted-emit contract for the CEA Installed Capacity adapter
(plan TODO/20260617-cea-iced-faceted-ingestion-plan.md, Row 2): the
workbook fuel columns map to the canonical ``fuel_type`` enum (Grand Total
-> ``all``; Total Thermal dropped per R-C; Coal/Gas/Nuclear/Hydro/RES ->
the 5-bucket axis), ECI st_codes translate to LGD slugs via the existing
``eci_to_lgd_slug`` bridge, the snapshot reduces to the integer report
year, and the adapter emits ONE faceted file
``geo_by_fuel/installed-capacity-snapshot-mw.csv`` that passes
``validate_csv`` (header + enum + composite-PK + FK closure).

No mocks (Holy Law #7); ``tmp_path`` fixtures only (CLAUDE.md anti-pattern
on walking the real corpus). FK targets (geo.csv + source.csv) are staged
in ``tmp_path``; variables.csv is intentionally omitted (the validator
skips the datapoint-filename check when it is absent).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.sources.cea_installed_capacity.ingest import (
    _CSV_FILE_CLASS,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE,
    _DROPPED_INDICATOR,
    _FACETED_VARIABLE_ID,
    _INDICATOR_TO_FUEL_TYPE,
    _snapshot_to_year,
    _to_slug,
    build_faceted_rows,
    emit_faceted,
)
from yen_gov.sources.cea_installed_capacity.parsers import (
    SHIPPED_COLUMNS,
    ParsedRow,
    ParsedWorkbook,
)

_SNAPSHOT = "2026-03"

# entity_id FK target: the two states the fixture exercises (+ India).
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
)


def _parsed() -> ParsedWorkbook:
    def rows(*pairs: tuple[str, float]) -> list[ParsedRow]:
        return [ParsedRow(entity_id=e, time=_SNAPSHOT, value=v) for e, v in pairs]

    return ParsedWorkbook(
        snapshot_period=_SNAPSHOT,
        rows_by_indicator={
            "energy/installed_capacity_total_mw": rows(("S22", 30000.0), ("S01", 25000.0)),
            "energy/installed_capacity_thermal_mw": rows(("S22", 12000.0)),  # DROPPED
            "energy/installed_capacity_coal_mw": rows(("S22", 10000.0), ("S01", 8000.0)),
            "energy/installed_capacity_gas_mw": rows(("S22", 2000.0)),
            "energy/installed_capacity_nuclear_mw": rows(("S22", 1000.0)),
            "energy/installed_capacity_hydro_mw": rows(("S01", 3000.0)),
            "energy/installed_capacity_renewable_mw": rows(("S22", 15000.0), ("S01", 14000.0)),
        },
        state_count=2,
    )


def _source_id() -> str:
    return derive_source_id(_CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _SNAPSHOT)


def _stage_fk_targets(repo_root: Path, source_id: str) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n"
        f"{source_id},{_CSV_SOURCE_PRODUCER},{_CSV_SOURCE_TITLE},{_SNAPSHOT},\n",
        encoding="utf-8",
    )


# --- mapping integrity ------------------------------------------------------


def test_fuel_type_map_partitions_shipped_columns():
    # Every workbook column is either mapped to a fuel_type or explicitly
    # dropped -- no column is silently unhandled.
    shipped = {c.indicator_id for c in SHIPPED_COLUMNS}
    assert set(_INDICATOR_TO_FUEL_TYPE) | {_DROPPED_INDICATOR} == shipped


def test_fuel_type_codomain_is_enum_subset():
    assert set(_INDICATOR_TO_FUEL_TYPE.values()) == {
        "all",
        "coal",
        "gas",
        "nuclear",
        "hydro",
        "renewable",
    }


def test_thermal_is_the_dropped_indicator():
    assert _DROPPED_INDICATOR == "energy/installed_capacity_thermal_mw"
    assert _DROPPED_INDICATOR not in _INDICATOR_TO_FUEL_TYPE


# --- helpers ----------------------------------------------------------------


def test_snapshot_reduces_to_report_year_int():
    assert _snapshot_to_year("2026-03") == 2026
    assert _snapshot_to_year("2024-12") == 2024


def test_snapshot_rejects_malformed():
    with pytest.raises(ValueError):
        _snapshot_to_year("2026")


def test_to_slug_translates_and_passes_country_through():
    assert _to_slug("S22") == "tamil-nadu"
    assert _to_slug("IN") == "IN"


# --- build ------------------------------------------------------------------


def test_build_emits_faceted_rows():
    rows = build_faceted_rows(_parsed(), source_id=_source_id())
    # 6 mapped columns, thermal dropped; per the fixture: all(2)+coal(2)+gas(1)
    # +nuclear(1)+hydro(1)+renewable(2) = 9 rows.
    assert len(rows) == 9
    assert {r["fuel_type"] for r in rows} == {
        "all",
        "coal",
        "gas",
        "nuclear",
        "hydro",
        "renewable",
    }
    assert "thermal" not in {r["fuel_type"] for r in rows}


def test_build_translates_entity_and_time_and_source():
    sid = _source_id()
    rows = build_faceted_rows(_parsed(), source_id=sid)
    assert {r["entity_id"] for r in rows} == {"tamil-nadu", "andhra-pradesh"}
    assert all(r["time"] == 2026 for r in rows)
    assert all(r["source_id"] == sid for r in rows)
    assert all(set(r) == {"entity_id", "time", "fuel_type", "value", "source_id"} for r in rows)


# --- emit + validate --------------------------------------------------------


def test_emit_one_faceted_file_that_validates(tmp_path: Path):
    sid = _source_id()
    _stage_fk_targets(tmp_path, sid)
    rows = build_faceted_rows(_parsed(), source_id=sid)

    out = emit_faceted(repo_root=tmp_path, rows=rows)

    assert out == (
        tmp_path
        / "datasets/data/datapoints/geo_by_fuel"
        / f"{_FACETED_VARIABLE_ID}.csv"
    )
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header == "entity_id,time,fuel_type,value,source_id"

    # FK + enum + composite-PK closure.
    validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)
