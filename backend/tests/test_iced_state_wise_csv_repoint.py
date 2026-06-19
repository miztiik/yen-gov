"""B1.4.8 writer-unit gate: iced_state_wise row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.8 of
``docs/archive/plans/20260604-b1.4-iced-repoint-subplan.md``: the iced_state_wise
ingest emits each non-faceted indicator (installed capacity, generation,
peak demand, sales, AT&C losses, ACS-ARR gap, GDP constant, rooftop
solar, population) as a single ``variable_id`` and the faceted
Sectoral GVA shard splits into one ``variable_id`` per facet (current
/ constant). Each emission goes through the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, reduces ``YYYY-04`` fiscal-year
periods to integer years, and stamps every row with the deterministic
``source_id`` derived from each indicator's citation triple.

Mirrors the shape of ``test_iced_discom_csv_repoint.py`` (B1.4.7,
PR #641). No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md
anti-pattern on walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.adapters.iced_state_wise.ingest import (
    _CSV_FILE_CLASS,
    _CSV_INDICATOR_EMIT,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_VINTAGE,
    _period_to_year_int,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _unfaceted_payload_rows() -> list[dict[str, object]]:
    # Mirrors `_build_payload`: rows with {entity_id, time, value}.
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 1234.5},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 5678.9},
        {"entity_id": "IN", "time": "2021-04", "value": 99999.0},
    ]


def _faceted_payload_rows() -> list[dict[str, object]]:
    # Mirrors `_build_collapsed_payload`: rows with facet + vintage.
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 100.0,
         "facet": "current", "vintage": "Base 2011-12"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 80.0,
         "facet": "constant", "vintage": "Base 2011-12"},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 200.0,
         "facet": "current", "vintage": "Base 2011-12"},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 160.0,
         "facet": "constant", "vintage": "Base 2011-12"},
    ]


def test_build_csv_variables_unfaceted_collapses_to_single_variable():
    title, prefix = _CSV_INDICATOR_EMIT[
        "energy/state_installed_capacity_geographical_mw"
    ]
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _unfaceted_payload_rows(),
        source_id=source_id,
        variable_prefix=prefix,
    )
    assert set(by_variable.keys()) == {"installed-capacity-geographical-mw"}
    rows = by_variable["installed-capacity-geographical-mw"]
    assert [(r["entity_id"], r["time"]) for r in rows] == [
        ("IN-S22", 2020),
        ("IN-S27", 2020),
        ("IN", 2021),
    ]
    for row in rows:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


def test_build_csv_variables_facet_splits_per_axis():
    title, prefix = _CSV_INDICATOR_EMIT["economy/sectoral_gva_inr_crore"]
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _faceted_payload_rows(),
        source_id=source_id,
        variable_prefix=prefix,
    )
    assert set(by_variable.keys()) == {
        "sectoral-gva-inr-crore-current",
        "sectoral-gva-inr-crore-constant",
    }
    current = by_variable["sectoral-gva-inr-crore-current"]
    assert len(current) == 2
    for row in current:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        # facet/vintage are NOT propagated to CSV rows (csv_writer facet
        # support deferred per sub-plan B1.4.1..9 #7).
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


def test_period_to_year_int_reduces_fiscal_year_to_start_year():
    assert _period_to_year_int("2020-04") == 2020
    assert _period_to_year_int("2018") == 2018


def test_slug_segment_is_kebab_and_ban_safe():
    assert _slug_segment("Current") == "current"
    assert _slug_segment("Constant Price") == "constant-price"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_emit_csv_variables_writes_one_file_per_facet(tmp_path: Path):
    title, prefix = _CSV_INDICATOR_EMIT["economy/sectoral_gva_inr_crore"]
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _faceted_payload_rows(),
        source_id=source_id,
        variable_prefix=prefix,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    current_path = out_dir / "sectoral-gva-inr-crore-current.csv"
    constant_path = out_dir / "sectoral-gva-inr-crore-constant.csv"
    assert current_path.exists()
    assert constant_path.exists()

    text = current_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with current_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    assert [(r["entity_id"], r["time"]) for r in parsed] == [
        ("IN-S22", "2020"),
        ("IN-S27", "2020"),
    ]
    assert parsed[0]["source_id"] == source_id


def test_emit_csv_variables_writes_unfaceted_single_file(tmp_path: Path):
    title, prefix = _CSV_INDICATOR_EMIT["demography/state_population_lakhs"]
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _unfaceted_payload_rows(),
        source_id=source_id,
        variable_prefix=prefix,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 1
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    pop_path = out_dir / "population-lakhs.csv"
    assert pop_path.exists()
    assert written[0] == pop_path


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"


def test_emit_table_covers_every_indicator_spec():
    # Guard: every iced_state_wise indicator_id is mapped to a citation
    # triple and a kebab variable prefix. Adding a new INDICATOR_SPECS
    # row without a _CSV_INDICATOR_EMIT entry would silently skip CSV
    # emission at runtime; this test fails fast.
    from yen_gov.canonical.adapters.iced_state_wise.ingest import INDICATOR_SPECS

    declared = {m.spec.indicator_id for m in INDICATOR_SPECS}
    mapped = set(_CSV_INDICATOR_EMIT.keys())
    assert declared == mapped, (
        f"missing CSV emit mapping: {declared - mapped}; "
        f"orphan mapping: {mapped - declared}"
    )
