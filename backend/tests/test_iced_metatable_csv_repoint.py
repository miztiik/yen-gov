"""B1.4.4 writer-unit gate: iced_metatable row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.4 of
``TODO/20260604-b1.4-iced-repoint-subplan.md``: the iced_metatable ingest
splits its three facet-keyed parser outputs (generation, PLF, CO2) into
one ``variable_id`` per facet, emits each via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, reduces fiscal-year ``YYYY-MM``
periods to integer years, and stamps every row with the deterministic
``source_id`` derived from each indicator's citation triple.

Mirrors the shape of ``test_iced_fuel_csv_repoint.py`` (B1.4.3, PR #637).
No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.iced_metatable.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_GEN,
    _CSV_SOURCE_TITLE_PLF,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_GEN,
    _CSV_VARIABLE_PREFIX_PLF,
    _period_to_year_int,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _parsed_gen_rows() -> list[dict[str, object]]:
    # Mirrors `parse_gen_metatable` output: facet = fuel source.
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 100.0, "facet": "Coal"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 25.0, "facet": "Solar"},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 50.0, "facet": "Coal"},
    ]


def _parsed_plf_rows() -> list[dict[str, object]]:
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 65.0, "facet": "Coal"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 20.0, "facet": "Solar"},
    ]


def test_build_csv_variables_facet_splits_per_source():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_GEN, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_gen_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_GEN,
    )
    assert set(by_variable.keys()) == {
        "electricity-generation-gwh-coal",
        "electricity-generation-gwh-solar",
    }
    coal = by_variable["electricity-generation-gwh-coal"]
    assert len(coal) == 2
    for row in coal:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


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
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_PLF, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_plf_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_PLF,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    coal_path = out_dir / "plant-load-factor-pct-coal.csv"
    solar_path = out_dir / "plant-load-factor-pct-solar.csv"
    assert coal_path.exists()
    assert solar_path.exists()

    text = coal_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with coal_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    assert [(r["entity_id"], r["time"]) for r in parsed] == [("IN-S22", "2020")]
    assert parsed[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
