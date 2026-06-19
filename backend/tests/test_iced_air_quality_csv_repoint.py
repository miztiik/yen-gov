"""B1.4.9 writer-unit gate: iced_air_quality + markers CSV repoint.

Locks the contract for sub-row B1.4.9 of
``docs/archive/plans/20260604-b1.4-iced-repoint-subplan.md``: the five iced_air_quality
write_artifact sites (FGD + PM2.5 + NO2 + SO2 + PM10) each also emit a
single canonical long-format CSV under
``datasets/data/datapoints/geo/<variable_id>.csv`` via
``yen_gov.canonical.csv_writer.write_csv``. Times reduce to integer
year; every row carries the deterministic ``source_id`` derived from
its (producer, title, vintage) triple.

Mirrors the shape of ``test_iced_state_wise_csv_repoint.py`` (B1.4.8,
PR #642). No mocks (Holy Law #7); uses ``tmp_path``.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.adapters.iced_air_quality.ingest import (
    _CSV_FILE_CLASS as FGD_FILE_CLASS,
    _CSV_OUT_REL_DIR as FGD_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER as FGD_PRODUCER,
    _CSV_SOURCE_TITLE_FGD,
    _CSV_SOURCE_VINTAGE_FGD,
    _CSV_VARIABLE_ID_FGD,
    _emit_csv_fgd,
    _period_to_year_int as fgd_period_to_year,
    build_csv_rows_fgd,
)
from yen_gov.canonical.adapters.iced_air_quality.markers_ingest import (
    NO2_INDICATOR_ID,
    PM10_INDICATOR_ID,
    PM25_INDICATOR_ID,
    SO2_INDICATOR_ID,
    _CSV_FILE_CLASS as MARKERS_FILE_CLASS,
    _CSV_INDICATOR_EMIT,
    _CSV_OUT_REL_DIR as MARKERS_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER as MARKERS_PRODUCER,
    _CSV_SOURCE_VINTAGE as MARKERS_VINTAGE,
    _emit_csv_for as markers_emit_csv_for,
    _period_to_year_int as markers_period_to_year,
    build_csv_rows_markers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fgd_payload_rows() -> list[dict]:
    # Mirrors `_build_payload` rows: {entity_id, value, time=snapshot_date}.
    return [
        {"entity_id": "IN-S22", "time": "2026-05-15", "value": 42.5},
        {"entity_id": "IN-S27", "time": "2026-05-15", "value": 17.25},
    ]


def _markers_payload_rows() -> list[dict]:
    # Mirrors `emit_indicator_rows`: {entity_id, time=str(year), value}.
    return [
        {"entity_id": "IN-S22", "time": "2014", "value": 55.0},
        {"entity_id": "IN-S22", "time": "2015", "value": 60.5},
        {"entity_id": "IN-S27", "time": "2014", "value": 35.0},
    ]


# ---------------------------------------------------------------------------
# Shared invariants
# ---------------------------------------------------------------------------


def test_file_classes_match_writer_glob():
    assert FGD_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
    assert MARKERS_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"


def test_fgd_period_to_year_handles_iso_date_month_and_year():
    assert fgd_period_to_year("2026-05-15") == 2026
    assert fgd_period_to_year("2020-04") == 2020
    assert fgd_period_to_year("2019") == 2019


def test_markers_period_to_year_handles_year_strings():
    assert markers_period_to_year("2014") == 2014
    assert markers_period_to_year("2020-04") == 2020


# ---------------------------------------------------------------------------
# FGD (iced_air_quality/ingest.py)
# ---------------------------------------------------------------------------


def test_build_csv_rows_fgd_keys_match_file_class():
    source_id = derive_source_id(
        FGD_PRODUCER, _CSV_SOURCE_TITLE_FGD, _CSV_SOURCE_VINTAGE_FGD
    )
    rows = build_csv_rows_fgd(_fgd_payload_rows(), source_id=source_id)
    assert [(r["entity_id"], r["time"]) for r in rows] == [
        ("IN-S22", 2026),
        ("IN-S27", 2026),
    ]
    for row in rows:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


def test_emit_csv_fgd_writes_single_file(tmp_path: Path):
    written = _emit_csv_fgd(
        repo_root=tmp_path, payload_rows=_fgd_payload_rows()
    )
    out_path = (
        tmp_path / FGD_OUT_REL_DIR / f"{_CSV_VARIABLE_ID_FGD}.csv"
    )
    assert written == out_path
    assert out_path.exists()

    text = out_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with out_path.open(encoding="utf-8", newline="") as fh:
        parsed = list(csv.DictReader(fh))
    assert [(r["entity_id"], r["time"]) for r in parsed] == [
        ("IN-S22", "2026"),
        ("IN-S27", "2026"),
    ]
    expected_source_id = derive_source_id(
        FGD_PRODUCER, _CSV_SOURCE_TITLE_FGD, _CSV_SOURCE_VINTAGE_FGD
    )
    assert all(r["source_id"] == expected_source_id for r in parsed)


def test_fgd_variable_id_is_kebab_and_ban_safe():
    assert "__" not in _CSV_VARIABLE_ID_FGD
    assert _CSV_VARIABLE_ID_FGD == _CSV_VARIABLE_ID_FGD.lower()
    # ADR-0044: no grain prefix.
    assert not _CSV_VARIABLE_ID_FGD.startswith(("state-", "district-", "national-"))


# ---------------------------------------------------------------------------
# Markers (PM2.5 / NO2 / SO2 / PM10)
# ---------------------------------------------------------------------------


def test_build_csv_rows_markers_collapses_to_canonical_columns():
    title, _ = _CSV_INDICATOR_EMIT[PM25_INDICATOR_ID]
    source_id = derive_source_id(MARKERS_PRODUCER, title, MARKERS_VINTAGE)
    rows = build_csv_rows_markers(
        _markers_payload_rows(), source_id=source_id
    )
    assert [(r["entity_id"], r["time"]) for r in rows] == [
        ("IN-S22", 2014),
        ("IN-S22", 2015),
        ("IN-S27", 2014),
    ]
    for row in rows:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


def test_markers_emit_writes_one_file_per_indicator(tmp_path: Path):
    written = markers_emit_csv_for(
        repo_root=tmp_path,
        indicator_id=NO2_INDICATOR_ID,
        payload_rows=_markers_payload_rows(),
    )
    _, variable_id = _CSV_INDICATOR_EMIT[NO2_INDICATOR_ID]
    out_path = tmp_path / MARKERS_OUT_REL_DIR / f"{variable_id}.csv"
    assert written == out_path
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")


def test_markers_emit_table_covers_all_four_pollutant_indicators():
    declared = {
        PM25_INDICATOR_ID,
        NO2_INDICATOR_ID,
        SO2_INDICATOR_ID,
        PM10_INDICATOR_ID,
    }
    mapped = set(_CSV_INDICATOR_EMIT.keys())
    assert declared == mapped, (
        f"missing CSV emit mapping: {declared - mapped}; "
        f"orphan mapping: {mapped - declared}"
    )


def test_markers_variable_ids_are_kebab_and_ban_safe():
    for _, variable_id in _CSV_INDICATOR_EMIT.values():
        assert "__" not in variable_id
        assert variable_id == variable_id.lower()
        assert not variable_id.startswith(
            ("state-", "district-", "national-")
        )
