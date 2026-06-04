"""B1.6.2 writer-unit gate: datagovin_ogd row-builder + write_csv.

Locks the contract for sub-row B1.6.2 of
``docs/archive/plans/20260604-b1.6-misc-repoint-subplan.md``: each shipped OGD
indicator maps 1:1 to a kebab-case ``variable_id`` (no facets - one
resource per indicator), is emitted via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, and stamps every row with the
deterministic ``source_id`` derived from the per-resource citation
triple (producer / title / vintage per ADR-0042).

No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.datagovin_ogd.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _INDICATOR_TO_CSV,
    _fy_period_to_time,
    build_csv_variables,
    emit_csv_variables,
)
from yen_gov.sources.datagovin_ogd.parsers import (
    SHIPPED_SPECS,
    IndicatorSpec,
    ParsedIndicator,
    ParsedRow,
)


def _spec() -> IndicatorSpec:
    return SHIPPED_SPECS[0]


def _parsed() -> ParsedIndicator:
    return ParsedIndicator(
        rows=(
            ParsedRow(entity_id="S22", time="2016-04", value=12345.6),
            ParsedRow(entity_id="S01", time="2016-04", value=2345.6),
            ParsedRow(entity_id="S22", time="2017-04", value=13456.7),
        ),
        unmatched_states=(),
        record_count=3,
    )


def test_fy_period_to_time_encodes_year_month_as_integer():
    assert _fy_period_to_time("2016-04") == 201604
    assert _fy_period_to_time("2022-04") == 202204
    assert _fy_period_to_time("2017-04") == 201704


def test_indicator_csv_map_covers_all_shipped_specs():
    assert {s.indicator_id for s in SHIPPED_SPECS} == set(
        _INDICATOR_TO_CSV.keys()
    )
    for entry in _INDICATOR_TO_CSV.values():
        vid = entry["variable_id"]
        assert "__" not in vid
        assert not vid.startswith(("state-", "district-", "national-"))


def test_build_csv_variables_maps_one_variable_per_indicator_with_canonical_columns():
    csv_meta = _INDICATOR_TO_CSV[_spec().indicator_id]
    source_id = derive_source_id(
        csv_meta["producer"], csv_meta["title"], csv_meta["vintage"],
    )
    by_variable = build_csv_variables(
        _spec(), _parsed(), source_id=source_id,
    )

    assert set(by_variable.keys()) == {"centre-transfers-inr-crore-gross"}
    rows = by_variable["centre-transfers-inr-crore-gross"]
    assert len(rows) == 3
    assert {tuple(sorted(r.keys())) for r in rows} == {
        ("entity_id", "source_id", "time", "value")
    }
    for row in rows:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id


def test_emit_csv_variables_writes_one_file_per_variable(tmp_path: Path):
    csv_meta = _INDICATOR_TO_CSV[_spec().indicator_id]
    source_id = derive_source_id(
        csv_meta["producer"], csv_meta["title"], csv_meta["vintage"],
    )
    by_variable = build_csv_variables(
        _spec(), _parsed(), source_id=source_id,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 1
    target = tmp_path / _CSV_OUT_REL_DIR / "centre-transfers-inr-crore-gross.csv"
    assert target.exists()

    text = target.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with target.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed_rows = list(reader)
    # Deterministic sort on PK (entity_id, time).
    assert [(r["entity_id"], r["time"]) for r in parsed_rows] == [
        ("S01", "201604"),
        ("S22", "201604"),
        ("S22", "201704"),
    ]
    assert parsed_rows[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
