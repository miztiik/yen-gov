"""B1.4.2 writer-unit gate: iced_macro row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.2 of
``TODO/20260604-b1.4-iced-repoint-subplan.md``: the iced_macro ingest splits
its facet-keyed parser output into one ``variable_id`` per facet, emits
each via the canonical ``yen_gov.canonical.csv_writer.write_csv`` against
file class ``datasets/data/datapoints/geo/*.csv``, reduces fiscal-year
``YYYY-MM`` periods to integer years, and stamps every row with the
deterministic ``source_id`` derived from each indicator's citation triple.

Mirrors the shape of ``test_iced_ghg_csv_repoint.py`` (B1.4.1, PR #635).
No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.iced_macro.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_GDP,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_GDP,
    _period_to_year_int,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _parsed_gdp_rows() -> list[dict[str, object]]:
    # Mirrors the shape of `parse_gdp_trend` output (national + state,
    # post fy_to_period normalisation to YYYY-MM).
    return [
        {"entity_id": "IN", "time": "2010-04", "value": 100.5, "facet": "current"},
        {"entity_id": "IN", "time": "2020-04", "value": 200.0, "facet": "current"},
        {"entity_id": "IN", "time": "2020-04", "value": 180.0, "facet": "constant"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 60.0, "facet": "constant"},
    ]


def test_build_csv_variables_splits_per_facet_with_canonical_columns():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_GDP, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_gdp_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_GDP,
    )

    assert set(by_variable.keys()) == {
        "gdp-inr-crore-current",
        "gdp-inr-crore-constant",
    }
    constant = by_variable["gdp-inr-crore-constant"]
    assert len(constant) == 2
    assert {tuple(sorted(r.keys())) for r in constant} == {
        ("entity_id", "source_id", "time", "value")
    }
    for row in constant:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id


def test_period_to_year_int_reduces_fiscal_year_to_start_year():
    # `fy_to_period("2024-25") == "2024-04"` -> 2024 (FY start year).
    assert _period_to_year_int("2024-04") == 2024
    assert _period_to_year_int("1950-04") == 1950


def test_slug_segment_is_kebab_and_ban_safe():
    # Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes.
    assert _slug_segment("current") == "current"
    assert _slug_segment("Capital Goods") == "capital-goods"
    assert _slug_segment("Trade-Hotels & Transport") == "trade-hotels-transport"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_emit_csv_variables_writes_one_file_per_variable(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_GDP, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_gdp_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_GDP,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    constant_path = out_dir / "gdp-inr-crore-constant.csv"
    current_path = out_dir / "gdp-inr-crore-current.csv"
    assert constant_path.exists()
    assert current_path.exists()

    text = constant_path.read_text(encoding="utf-8")
    # Header order matches the file class's declared column order.
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    # Trailing newline + LF line endings (writer contract).
    assert text.endswith("\n")
    assert "\r" not in text

    with constant_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    # Deterministic sort on PK (entity_id, time).
    assert [(r["entity_id"], r["time"]) for r in parsed] == [
        ("IN", "2020"),
        ("IN-S22", "2020"),
    ]
    assert parsed[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    # Trip-wire: if the file class string drifts, this guard catches it
    # before the per-family PR ships against a stale glob.
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
