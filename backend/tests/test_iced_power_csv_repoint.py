"""B1.4.5 writer-unit gate: iced_power row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.5 of
``TODO/20260604-b1.4-iced-repoint-subplan.md``: the iced_power ingest
splits its faceted parser outputs (capacity, generation, retired) into
one ``variable_id`` per facet, emits each via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, reduces fiscal-year ``YYYY-MM``
periods to integer years, and stamps every row with the deterministic
``source_id`` derived from each indicator's citation triple. The peak
demand indicator (non-faceted) collapses to a single ``variable_id``.

Mirrors the shape of ``test_iced_metatable_csv_repoint.py`` (B1.4.4,
PR #638). No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md
anti-pattern on walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.iced_power.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_CAPACITY,
    _CSV_SOURCE_TITLE_PEAK,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_CAPACITY,
    _CSV_VARIABLE_PREFIX_PEAK,
    _period_to_year_int,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _parsed_capacity_rows() -> list[dict[str, object]]:
    # Mirrors `parse_capacity_metatable` output: facet = fuel source.
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 1500.0, "facet": "coal"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 300.0, "facet": "small-hydro"},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 800.0, "facet": "coal"},
    ]


def _parsed_peak_rows() -> list[dict[str, object]]:
    # Mirrors `parse_power_statistics()[1]`: no facet column.
    return [
        {"entity_id": "IN-S22", "time": "2024-04", "value": 16500.0},
        {"entity_id": "IN-S27", "time": "2024-04", "value": 28000.0},
    ]


def test_build_csv_variables_facet_splits_per_source():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_CAPACITY, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_capacity_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_CAPACITY,
    )
    assert set(by_variable.keys()) == {
        "installed-capacity-mw-coal",
        "installed-capacity-mw-small-hydro",
    }
    coal = by_variable["installed-capacity-mw-coal"]
    assert len(coal) == 2
    for row in coal:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


def test_build_csv_variables_unfaceted_collapses_to_single_variable():
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


def test_period_to_year_int_reduces_fiscal_year_to_start_year():
    assert _period_to_year_int("2024-04") == 2024
    assert _period_to_year_int("2009-04") == 2009


def test_slug_segment_is_kebab_and_ban_safe():
    assert _slug_segment("Coal") == "coal"
    assert _slug_segment("Oil & Gas") == "oil-gas"
    assert _slug_segment("Small Hydro") == "small-hydro"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_emit_csv_variables_writes_one_file_per_facet(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_CAPACITY, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_capacity_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_CAPACITY,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    coal_path = out_dir / "installed-capacity-mw-coal.csv"
    hydro_path = out_dir / "installed-capacity-mw-small-hydro.csv"
    assert coal_path.exists()
    assert hydro_path.exists()

    text = coal_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with coal_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    assert [(r["entity_id"], r["time"]) for r in parsed] == [
        ("IN-S22", "2020"),
        ("IN-S27", "2020"),
    ]
    assert parsed[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
