"""ICED peak-demand entity-key fix (ECI st_code -> LGD slug).

The ICED peak-demand series is a single-value
``geo/peak-electricity-demand-iced-mw.csv`` (the ICED half of the publisher-
split peak-demand measure, per plan SC-1); the entity output is re-pointed
through the ECI -> LGD-slug translation so the rows FK-close against
``entities/geo.csv`` (the parser emits ECI st_codes; geo.csv keys on slugs).

No mocks (Holy Law #7); ``tmp_path`` fixtures only. FK targets (geo.csv +
source.csv) are staged in ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.adapters.iced_power.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_PEAK,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_PEAK,
    build_peak_rows,
    emit_csv_variables,
    ingest_peak,
)

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
    "jharkhand,Jharkhand,IN,state,IN-JH|S27|lgd:20,20,20\n"
)


def _peak_source_id() -> str:
    return derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_PEAK, _CSV_SOURCE_VINTAGE
    )


def _stage_fk_targets(repo_root: Path, source_id: str) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n"
        f"{source_id},{_CSV_SOURCE_PRODUCER},{_CSV_SOURCE_TITLE_PEAK},"
        f"{_CSV_SOURCE_VINTAGE},\n",
        encoding="utf-8",
    )


def _parsed_peak_rows() -> list[dict[str, object]]:
    # Mirrors parse_power_statistics()[1]: single-value, entity_id = ECI st_code.
    return [
        {"entity_id": "S22", "time": "2023-04", "value": 16500.0},
        {"entity_id": "S27", "time": "2023-04", "value": 9000.0},
    ]


def test_build_peak_translates_eci_to_slug():
    sid = _peak_source_id()
    by_variable = build_peak_rows(_parsed_peak_rows(), source_id=sid)
    assert set(by_variable) == {"peak-electricity-demand-iced-mw"}
    rows = by_variable["peak-electricity-demand-iced-mw"]
    assert {r["entity_id"] for r in rows} == {"tamil-nadu", "jharkhand"}
    assert all(r["time"] == 2023 for r in rows)
    assert all(r["source_id"] == sid for r in rows)
    assert all(
        set(r) == {"entity_id", "time", "value", "source_id"} for r in rows
    )


def test_build_peak_stays_single_value():
    # Peak is NOT faceted -- no fuel_type column ever appears.
    rows = build_peak_rows(_parsed_peak_rows(), source_id=_peak_source_id())[
        _CSV_VARIABLE_PREFIX_PEAK
    ]
    assert all("fuel_type" not in r for r in rows)


def test_peak_emit_validates(tmp_path: Path):
    sid = _peak_source_id()
    _stage_fk_targets(tmp_path, sid)
    by_variable = build_peak_rows(_parsed_peak_rows(), source_id=sid)

    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 1
    out = written[0]
    assert out == tmp_path / _CSV_OUT_REL_DIR / "peak-electricity-demand-iced-mw.csv"
    assert out.read_text(encoding="utf-8").splitlines()[0] == (
        "entity_id,time,value,source_id"
    )
    validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)


def test_ingest_peak_end_to_end_emits_slug_keyed_rows(tmp_path: Path):
    sid = _peak_source_id()
    _stage_fk_targets(tmp_path, sid)
    raw = {
        "stateWiseData": [
            {"state": "Tamil Nadu", "fyear": "2023-2024", "peakDemand": 16500, "data": []},
            {"state": "Jharkhand", "fyear": "2023-2024", "peakDemand": 9000, "data": []},
            {"state": "All India", "fyear": "2023-2024", "peakDemand": 240000, "data": []},
        ]
    }
    raw_path = tmp_path / "power_statistics.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    result = ingest_peak(repo_root=tmp_path, raw_json_path=raw_path)

    assert result.variable_id == "peak-electricity-demand-iced-mw"
    assert result.row_count == 3
    out = tmp_path / _CSV_OUT_REL_DIR / "peak-electricity-demand-iced-mw.csv"
    text = out.read_text(encoding="utf-8")
    assert "tamil-nadu" in text and "jharkhand" in text
    # "All India" passes through to the IN country rollup.
    assert any(line.startswith("IN,") for line in text.splitlines())
    validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)
