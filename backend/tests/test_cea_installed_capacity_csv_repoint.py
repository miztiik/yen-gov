"""B1.6.1 writer-unit gate: cea_installed_capacity row-builder + write_csv.

Locks the contract for sub-row B1.6.1 of
``TODO/20260604-b1.6-misc-repoint-subplan.md``: each of the seven
SHIPPED_COLUMNS fuel facets maps 1:1 to a kebab-case ``variable_id``
(one-variable-per-facet interim while csv_writer lacks facet column
support), is emitted via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, and stamps every row with the
deterministic ``source_id`` derived from one shared citation triple
(producer / title / vintage = the monthly Executive Summary publication
keyed by the workbook snapshot period).

No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.cea_installed_capacity.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE,
    _INDICATOR_TO_VARIABLE_ID,
    _slug_segment,
    _snapshot_to_time,
    build_csv_variables,
    emit_csv_variables,
)
from yen_gov.sources.cea_installed_capacity.parsers import (
    SHIPPED_COLUMNS,
    FuelColumn,
    ParsedRow,
)


def _column() -> FuelColumn:
    return FuelColumn("energy/installed_capacity_coal_mw", 3, "Coal")


def _rows() -> list[ParsedRow]:
    return [
        ParsedRow(entity_id="S22", time="2026-01", value=12345.6),
        ParsedRow(entity_id="S01", time="2026-01", value=2345.6),
    ]


def test_snapshot_to_time_encodes_year_month_as_integer():
    assert _snapshot_to_time("2026-01") == 202601
    assert _snapshot_to_time("2024-12") == 202412


def test_slug_segment_is_kebab_and_ban_safe():
    assert _slug_segment("Total Thermal") == "total-thermal"
    assert _slug_segment("RES (MNRE)") == "res-mnre"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_indicator_variable_id_map_covers_all_shipped_columns():
    assert {c.indicator_id for c in SHIPPED_COLUMNS} == set(
        _INDICATOR_TO_VARIABLE_ID.keys()
    )
    for vid in _INDICATOR_TO_VARIABLE_ID.values():
        assert "__" not in vid
        assert not vid.startswith(("state-", "district-", "national-"))


def test_build_csv_variables_maps_one_variable_per_column_with_canonical_columns():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, "2026-01"
    )
    by_variable = build_csv_variables(
        _column(), _rows(),
        snapshot_period="2026-01",
        source_id=source_id,
    )

    assert set(by_variable.keys()) == {"installed-capacity-mw-coal"}
    rows = by_variable["installed-capacity-mw-coal"]
    assert len(rows) == 2
    assert {tuple(sorted(r.keys())) for r in rows} == {
        ("entity_id", "source_id", "time", "value")
    }
    for row in rows:
        assert isinstance(row["time"], int)
        assert row["time"] == 202601
        assert row["source_id"] == source_id


def test_emit_csv_variables_writes_one_file_per_variable(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, "2026-01"
    )
    by_variable = build_csv_variables(
        _column(), _rows(),
        snapshot_period="2026-01",
        source_id=source_id,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 1
    target = tmp_path / _CSV_OUT_REL_DIR / "installed-capacity-mw-coal.csv"
    assert target.exists()

    text = target.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with target.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed_rows = list(reader)
    # Deterministic sort on PK (entity_id, time).
    assert [r["entity_id"] for r in parsed_rows] == ["S01", "S22"]
    assert parsed_rows[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
