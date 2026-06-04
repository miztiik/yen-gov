"""B1.4.3 writer-unit gate: iced_fuel row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.3 of
``docs/archive/plans/20260604-b1.4-iced-repoint-subplan.md``: the iced_fuel ingest splits
its parser output (one facet-less indicator + two facet-keyed indicators)
into one ``variable_id`` per facet, emits each via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, reduces fiscal-year ``YYYY-MM``
periods to integer years, and stamps every row with the deterministic
``source_id`` derived from each indicator's citation triple.

Mirrors the shape of ``test_iced_ghg_csv_repoint.py`` (B1.4.1, PR #635)
and ``test_iced_macro_csv_repoint.py`` (B1.4.2, PR #636). No mocks
(Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on walking
the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.iced_fuel.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_COAL,
    _CSV_SOURCE_TITLE_OIL,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_COAL,
    _CSV_VARIABLE_PREFIX_OIL,
    _period_to_year_int,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _parsed_coal_rows() -> list[dict[str, object]]:
    # Mirrors `parse_coal_consumption_state` output: NO facet (grade is
    # summed away upstream).
    return [
        {"entity_id": "IN-S22", "time": "2010-04", "value": 12.5},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 25.0},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 8.0},
    ]


def _parsed_oil_rows() -> list[dict[str, object]]:
    # Mirrors `parse_oil_consumption_state` output: faceted by product slug
    # (parser pre-kebab-cased).
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 100.0, "facet": "diesel-hsd"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 50.0, "facet": "petrol"},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 30.0, "facet": "diesel-hsd"},
    ]


def test_build_csv_variables_no_facet_collapses_to_prefix():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_COAL, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_coal_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_COAL,
    )
    assert set(by_variable.keys()) == {"coal-consumption-mt"}
    rows = by_variable["coal-consumption-mt"]
    assert len(rows) == 3
    assert {tuple(sorted(r.keys())) for r in rows} == {
        ("entity_id", "source_id", "time", "value")
    }
    for row in rows:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id


def test_build_csv_variables_facet_splits_per_facet():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_OIL, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_oil_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_OIL,
    )
    assert set(by_variable.keys()) == {
        "oil-product-consumption-kt-diesel-hsd",
        "oil-product-consumption-kt-petrol",
    }
    diesel = by_variable["oil-product-consumption-kt-diesel-hsd"]
    assert len(diesel) == 2
    for row in diesel:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id


def test_period_to_year_int_reduces_fiscal_year_to_start_year():
    # `fy_to_period("2024-25") == "2024-04"` -> 2024 (FY start year).
    assert _period_to_year_int("2024-04") == 2024
    assert _period_to_year_int("2005-04") == 2005


def test_slug_segment_is_kebab_and_ban_safe():
    # Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes.
    assert _slug_segment("diesel-hsd") == "diesel-hsd"
    assert _slug_segment("Trading & Others") == "trading-others"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_emit_csv_variables_writes_facetless_indicator(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_COAL, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_coal_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_COAL,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 1
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    coal_path = out_dir / "coal-consumption-mt.csv"
    assert coal_path.exists()

    text = coal_path.read_text(encoding="utf-8")
    # Header order matches the file class's declared column order.
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    # Trailing newline + LF line endings (writer contract).
    assert text.endswith("\n")
    assert "\r" not in text

    with coal_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    # Deterministic sort on PK (entity_id, time).
    assert [(r["entity_id"], r["time"]) for r in parsed] == [
        ("IN-S22", "2010"),
        ("IN-S22", "2020"),
        ("IN-S27", "2020"),
    ]
    assert parsed[0]["source_id"] == source_id


def test_emit_csv_variables_writes_one_file_per_facet(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_OIL, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_oil_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_OIL,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    assert (out_dir / "oil-product-consumption-kt-diesel-hsd.csv").exists()
    assert (out_dir / "oil-product-consumption-kt-petrol.csv").exists()


def test_file_class_matches_writer_glob():
    # Trip-wire: if the file class string drifts, this guard catches it
    # before the per-family PR ships against a stale glob.
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
