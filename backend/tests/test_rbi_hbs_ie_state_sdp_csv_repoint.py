"""B1.5.5 writer-unit gate: rbi_hbs_ie_state_sdp row-builder + write_csv.

Locks the contract for sub-row B1.5.5 of
``TODO/20260604-b1.5-rbi-repoint-subplan.md``: each state SDP table
(T05 / T06 / T09 / T10) maps to one kebab-case ``variable_id`` file
(per-price-basis split because the writer does not yet support facet
columns), is emitted via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, and stamps every row with the
deterministic ``source_id`` derived from a per-table citation triple.

No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.rbi_hbs_ie_state_sdp.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_BY_TABLE,
    _CSV_SOURCE_VINTAGE,
    _VARIABLE_ID_NSDP_CONSTANT,
    _VARIABLE_ID_NSDP_CURRENT,
    _VARIABLE_ID_PER_CAPITA_CONSTANT,
    _VARIABLE_ID_PER_CAPITA_CURRENT,
    _csv_source_id_for_table,
    _fy_start_year,
    build_csv_rows,
    emit_csv_variable,
)


def _parser_rows() -> list[dict[str, object]]:
    return [
        {"entity_id": "S22", "time": "2020-04", "value": 1234.5, "vintage": "Base 2011-12"},
        {"entity_id": "S01", "time": "2020-04", "value": 678.9, "vintage": "Base 2011-12"},
        {"entity_id": "IN", "time": "2019-04", "value": 99999.0, "vintage": "Base 2011-12"},
    ]


def test_fy_start_year_lifts_april_stamp_to_int_year():
    assert _fy_start_year("2020-04") == 2020
    assert _fy_start_year("1999-04") == 1999


def test_variable_ids_are_grain_safe_and_ban_safe():
    for vid in (
        _VARIABLE_ID_NSDP_CURRENT,
        _VARIABLE_ID_NSDP_CONSTANT,
        _VARIABLE_ID_PER_CAPITA_CURRENT,
        _VARIABLE_ID_PER_CAPITA_CONSTANT,
    ):
        assert "__" not in vid
        assert not vid.startswith(("state-", "district-", "national-"))


def test_source_id_is_per_table_and_deterministic():
    for key in ("T05", "T06", "T09", "T10"):
        assert _csv_source_id_for_table(key) == derive_source_id(
            _CSV_SOURCE_PRODUCER,
            _CSV_SOURCE_TITLE_BY_TABLE[key],
            _CSV_SOURCE_VINTAGE,
        )
    # Distinct titles -> distinct hashes.
    assert _csv_source_id_for_table("T05") != _csv_source_id_for_table("T06")


def test_build_csv_rows_projects_and_sorts():
    source_id = _csv_source_id_for_table("T05")
    out = build_csv_rows(_parser_rows(), source_id=source_id)
    assert [(r["entity_id"], r["time"]) for r in out] == [
        ("IN", 2019),
        ("S01", 2020),
        ("S22", 2020),
    ]
    for row in out:
        assert row["source_id"] == source_id
        assert isinstance(row["time"], int)
        assert set(row.keys()) == {"entity_id", "time", "value", "source_id"}


def test_emit_csv_variable_writes_canonical_shape(tmp_path: Path):
    source_id = _csv_source_id_for_table("T05")
    rows = build_csv_rows(_parser_rows(), source_id=source_id)
    written = emit_csv_variable(
        repo_root=tmp_path,
        variable_id=_VARIABLE_ID_NSDP_CURRENT,
        rows=rows,
    )
    assert written == tmp_path / _CSV_OUT_REL_DIR / f"{_VARIABLE_ID_NSDP_CURRENT}.csv"
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text
    with written.open(encoding="utf-8", newline="") as fh:
        out_rows = list(csv.DictReader(fh))
    assert [r["entity_id"] for r in out_rows] == ["IN", "S01", "S22"]
    assert [r["time"] for r in out_rows] == ["2019", "2020", "2020"]
    assert out_rows[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
