"""Writer-unit gate: iced_power row-builders + write_csv round-trip.

The capacity-metatable feed now emits the FACETED ``geo_by_fuel`` shape
(plan TODO/20260617-cea-iced-faceted-ingestion-plan.md, Row 3): raw ICED
sub-fuels collapse onto the canonical 5-bucket ``fuel_type`` axis
(``small-hydro``/``solar``/``wind`` -> ``renewable``; ``oil-gas`` -> ``gas``),
colliding renewables SUM, a publisher total maps to ``all``, ECI st_codes
resolve to LGD slugs, and one faceted file passes ``validate_csv``.

The deferred per-facet path (generation/retired, R-E/R-F) and the unfaceted
peak path keep their ``geo/*.csv`` build/emit, still exercised here so the
generic helpers stay covered.

No mocks (Holy Law #7); ``tmp_path`` fixtures only (CLAUDE.md anti-pattern on
walking the real corpus).
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.sources.iced_power.ingest import (
    _CAPACITY_FACETED_FILE_CLASS,
    _CAPACITY_FACETED_VARIABLE_ID,
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_CAPACITY,
    _CSV_SOURCE_TITLE_GEN,
    _CSV_SOURCE_TITLE_PEAK,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_GEN,
    _CSV_VARIABLE_PREFIX_PEAK,
    _period_to_year_int,
    _slug_segment,
    build_capacity_faceted_rows,
    build_csv_variables,
    emit_capacity_faceted,
    emit_csv_variables,
)

# entity_id FK target for the faceted-capacity validate_csv check.
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
    "jharkhand,Jharkhand,IN,state,IN-JH|S27|lgd:20,20,20\n"
)


# --- faceted capacity (Row 3) ----------------------------------------------


def _parsed_capacity_rows() -> list[dict[str, object]]:
    # Mirrors parse_capacity_metatable output: entity_id = ECI st_code,
    # facet = raw fuel source (kebab-case as ICED ships it).
    return [
        {"entity_id": "S22", "time": "2020-04", "value": 1500.0, "facet": "coal"},
        {"entity_id": "S22", "time": "2020-04", "value": 300.0, "facet": "small-hydro"},
        {"entity_id": "S22", "time": "2020-04", "value": 200.0, "facet": "solar"},
        {"entity_id": "S22", "time": "2020-04", "value": 50.0, "facet": "oil-gas"},
        {"entity_id": "S27", "time": "2020-04", "value": 800.0, "facet": "coal"},
        {"entity_id": "S22", "time": "2020-04", "value": 2050.0, "facet": "total"},
    ]


def _capacity_source_id() -> str:
    return derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_CAPACITY, _CSV_SOURCE_VINTAGE
    )


def _stage_fk_targets(repo_root: Path, source_id: str) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n"
        f"{source_id},{_CSV_SOURCE_PRODUCER},{_CSV_SOURCE_TITLE_CAPACITY},"
        f"{_CSV_SOURCE_VINTAGE},\n",
        encoding="utf-8",
    )


def test_capacity_collapses_sub_fuels_and_sums():
    rows = build_capacity_faceted_rows(_parsed_capacity_rows(), source_id=_capacity_source_id())
    by_key = {(r["entity_id"], r["fuel_type"]): r["value"] for r in rows}
    # small-hydro (300) + solar (200) collapse to one renewable row = 500.
    assert by_key[("tamil-nadu", "renewable")] == 500.0
    # oil-gas -> gas.
    assert by_key[("tamil-nadu", "gas")] == 50.0
    assert by_key[("tamil-nadu", "coal")] == 1500.0
    # publisher total -> all (NOT a synthesised sum of parts).
    assert by_key[("tamil-nadu", "all")] == 2050.0
    assert by_key[("jharkhand", "coal")] == 800.0


def test_capacity_translates_entity_and_time_and_columns():
    sid = _capacity_source_id()
    rows = build_capacity_faceted_rows(_parsed_capacity_rows(), source_id=sid)
    assert {r["entity_id"] for r in rows} == {"tamil-nadu", "jharkhand"}
    assert all(r["time"] == 2020 for r in rows)
    assert all(r["source_id"] == sid for r in rows)
    assert all(
        set(r) == {"entity_id", "time", "fuel_type", "value", "source_id"} for r in rows
    )
    # fuel_type members are a subset of the closed enum.
    assert {r["fuel_type"] for r in rows} <= {
        "coal", "gas", "hydro", "nuclear", "renewable", "all",
    }


def test_capacity_emit_one_faceted_file_that_validates(tmp_path: Path):
    sid = _capacity_source_id()
    _stage_fk_targets(tmp_path, sid)
    rows = build_capacity_faceted_rows(_parsed_capacity_rows(), source_id=sid)

    out = emit_capacity_faceted(repo_root=tmp_path, rows=rows)

    assert out == (
        tmp_path
        / "datasets/data/datapoints/geo_by_fuel"
        / f"{_CAPACITY_FACETED_VARIABLE_ID}.csv"
    )
    assert out.read_text(encoding="utf-8").splitlines()[0] == (
        "entity_id,time,fuel_type,value,source_id"
    )
    validate_csv(path=out, file_class=_CAPACITY_FACETED_FILE_CLASS, repo_root=tmp_path)


# --- deferred per-facet path (generation/retired, R-E/R-F) ------------------


def _parsed_generation_rows() -> list[dict[str, object]]:
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 1500.0, "facet": "coal"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 300.0, "facet": "small-hydro"},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 800.0, "facet": "coal"},
    ]


def test_generation_build_csv_variables_facet_splits_per_source():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_GEN, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_generation_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_GEN,
    )
    assert set(by_variable.keys()) == {
        "electricity-generation-snapshot-gwh-coal",
        "electricity-generation-snapshot-gwh-small-hydro",
    }
    coal = by_variable["electricity-generation-snapshot-gwh-coal"]
    assert len(coal) == 2
    for row in coal:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == ("entity_id", "source_id", "time", "value")


def test_generation_emit_writes_one_file_per_facet(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_GEN, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_generation_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_GEN,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)
    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    coal_path = out_dir / "electricity-generation-snapshot-gwh-coal.csv"
    assert coal_path.exists()
    text = coal_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text


# --- unfaceted peak path ----------------------------------------------------


def _parsed_peak_rows() -> list[dict[str, object]]:
    # Mirrors parse_power_statistics()[1]: no facet column. Entity-key slug
    # translation is Row 4's scope; the build helper passes entity_id through.
    return [
        {"entity_id": "IN-S22", "time": "2024-04", "value": 16500.0},
        {"entity_id": "IN-S27", "time": "2024-04", "value": 28000.0},
    ]


def test_peak_build_csv_variables_collapses_to_single_variable():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_PEAK, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_peak_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_PEAK,
    )
    assert set(by_variable.keys()) == {"peak-electricity-demand-mw"}
    rows = by_variable["peak-electricity-demand-mw"]
    assert [(r["entity_id"], r["time"]) for r in rows] == [
        ("IN-S22", 2024),
        ("IN-S27", 2024),
    ]


# --- generic helpers --------------------------------------------------------


def test_period_to_year_int_reduces_fiscal_year_to_start_year():
    assert _period_to_year_int("2024-04") == 2024
    assert _period_to_year_int("2009-04") == 2009


def test_slug_segment_is_kebab_and_ban_safe():
    assert _slug_segment("Coal") == "coal"
    assert _slug_segment("Oil & Gas") == "oil-gas"
    assert _slug_segment("Small Hydro") == "small-hydro"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_geo_file_class_unchanged_for_deferred_paths():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
    assert _CAPACITY_FACETED_FILE_CLASS == "datasets/data/datapoints/geo_by_fuel/*.csv"
