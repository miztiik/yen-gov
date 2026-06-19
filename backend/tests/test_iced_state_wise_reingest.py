"""Tier-B gate: ICED state-wise deep-dive -> single-value energy re-ingest.

Graduates the orphan single-value ICED state-wise energy indicators to LIVE
re-ingest: each decrypted per-FY response carries parallel ``states`` /
indicator-key arrays; the multi-FY ingest accumulates the per-state column
across fiscal years, re-keys ECI state codes to LGD slugs (``IN`` passthrough),
reduces ``YYYY-04`` fiscal-year periods to integer years, and emits one
``geo/<variable_id>.csv`` per target. No mocks (Holy Law #7); tmp_path fixtures
only. The triples reproduce the on-disk source_ids so a re-emit is idempotent
with the committed files.

SCOPE: three single-source targets - rooftop-solar-capacity-mw,
electricity-sales-mu, and installed-capacity-allocated-iced-mw (the ICED half
of the publisher-split allocated measure). Each target owns its whole file, so
the re-ingest emits via plain ``write_csv``. The RBI Handbook Table 140
statewise-total half of the legacy blended installed-capacity-allocated-mw is a
separate file (installed-capacity-statewise-total-rbi-mw.csv) after the
2026-06-19 RBI/ICED publisher-split (plan SC-1) and has no live emitter. See
``yen_gov.sources.iced_state_wise.ingest`` (multi-FY re-ingest section).

Mirrors ``test_iced_coal_consumption_reingest.py``.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.sources.iced_state_wise.ingest import (
    _CSV_FILE_CLASS,
    _CSV_SOURCE_PRODUCER,
    _STATE_WISE_TARGETS,
    build_state_wise_rows,
    ingest_state_wise,
)
from yen_gov.sources.iced_state_wise.parsers import extract_rows

# On-disk source_ids the re-ingest reproduces (verified against
# datasets/data/datapoints/geo/<id>.csv + datasets/data/entities/source.csv).
_ROOFTOP_SOURCE_ID = "src-018bb42f9519"
_SALES_SOURCE_ID = "src-bb1d7bec8b34"
# Allocated shares the ICED "State-wise Deep Dive API" citation triple with
# sales, so it reproduces the SAME source_id. After the 2026-06-19 RBI/ICED
# publisher-split (plan SC-1) the allocated target is a single-source ICED-only
# file; the RBI Handbook Table 140 statewise-total half is a separate file.
_ALLOC_SOURCE_ID = "src-bb1d7bec8b34"

# On-disk filenames (== variable_id) for the three included targets.
_ROOFTOP_VAR = "rooftop-solar-capacity-mw"
_SALES_VAR = "electricity-sales-mu"
_ALLOC_VAR = "installed-capacity-allocated-iced-mw"

# The allocated indicator's API key carries a sub-dict {"data": [...]} parallel
# to `states` (api_key_subkey="data"); copied VERBATIM from the catalogue spec.
_ALLOC_API_KEY = (
    "Installed Capacity*(Including Allocated Shares in Joint & "
    "Central Sector Utilities)"
)

# Minimal geo.csv FK target: the two state slugs the fixture resolves to
# (S13 -> maharashtra, S22 -> tamil-nadu) plus the national rollup. Rows
# shaped like datasets/data/entities/geo.csv.
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "maharashtra,Maharashtra,IN,state,IN-MH|S13|lgd:27,27,27\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
)


def _target(variable_id: str):
    (match,) = [t for t in _STATE_WISE_TARGETS if t.variable_id == variable_id]
    return match


def _source_id(variable_id: str) -> str:
    target = _target(variable_id)
    return derive_source_id(
        _CSV_SOURCE_PRODUCER, target.source_title, target.source_vintage
    )


def _stage_fk_targets(repo_root: Path) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    lines = ["source_id,producer,title,vintage,url"]
    seen: set[str] = set()
    for var in (_ROOFTOP_VAR, _SALES_VAR, _ALLOC_VAR):
        target = _target(var)
        sid = _source_id(var)
        if sid in seen:  # sales + allocated share the State-wise Deep Dive id
            continue
        seen.add(sid)
        lines.append(
            f"{sid},{_CSV_SOURCE_PRODUCER},{target.source_title},"
            f"{target.source_vintage},"
        )
    (entities / "source.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fy_response(
    rooftop: list[float],
    sales: list[float],
    allocated: list[float] | None = None,
) -> dict:
    # One decrypted state-wise response: parallel `states` + indicator arrays.
    # "All India" -> IN; "Maharashtra" -> S13 -> maharashtra; "Tamil Nadu" ->
    # S22 -> tamil-nadu. The allocated indicator is a sub-dict {"data": [...]}
    # (api_key_subkey="data"); omitted when `allocated` is None.
    payload: dict = {
        "states": ["All India", "Maharashtra", "Tamil Nadu"],
        "Rooftop Solar Capacity": rooftop,
        "Electricity Sales": sales,
    }
    if allocated is not None:
        payload[_ALLOC_API_KEY] = {"data": allocated}
    return {"data": payload}


def _stage_two_fy(staging_dir: Path) -> None:
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "2023-24.json").write_text(
        json.dumps(_fy_response(
            [100.0, 30.0, 20.0], [9000.0, 3000.0, 2000.0],
            allocated=[50000.0, 40000.0, 30000.0],
        )),
        encoding="utf-8",
    )
    (staging_dir / "2024-25.json").write_text(
        json.dumps(_fy_response(
            [120.0, 36.0, 24.0], [9500.0, 3200.0, 2100.0],
            allocated=[52000.0, 41000.0, 31000.0],
        )),
        encoding="utf-8",
    )


def test_targets_map_to_on_disk_filenames():
    # The registry's variable_ids are the EXACT on-disk geo/*.csv filenames.
    got = {t.variable_id for t in _STATE_WISE_TARGETS}
    assert got == {_ROOFTOP_VAR, _SALES_VAR, _ALLOC_VAR}
    # installed-capacity-allocated-iced-mw is the ICED-only half of the
    # publisher-split allocated measure, emitted via plain write_csv.
    assert _ALLOC_VAR in got


def test_source_ids_reproduce_on_disk():
    # Pinned so a re-emit is idempotent with the committed files.
    assert _source_id(_ROOFTOP_VAR) == _ROOFTOP_SOURCE_ID
    assert _source_id(_SALES_VAR) == _SALES_SOURCE_ID
    # Allocated shares the ICED State-wise Deep Dive triple with sales.
    assert _source_id(_ALLOC_VAR) == _ALLOC_SOURCE_ID
    assert _ALLOC_SOURCE_ID == _SALES_SOURCE_ID


def test_build_state_wise_rows_translates_eci_to_slug_and_year():
    decoded = _fy_response([100.0, 30.0, 20.0], [9000.0, 3000.0, 2000.0])
    parsed = extract_rows(
        spec=_target(_ROOFTOP_VAR).spec, fy_label="2024-25", decrypted=decoded
    )
    rows = build_state_wise_rows([parsed], source_id="src-x")
    by_entity = {r["entity_id"]: r for r in rows}
    # ECI st_codes (S13/S22) re-keyed to LGD slugs; All India -> IN.
    assert set(by_entity) == {"IN", "maharashtra", "tamil-nadu"}
    assert by_entity["maharashtra"]["value"] == pytest.approx(30.0)
    # FY "2024-04" reduced to integer start year.
    assert all(r["time"] == 2024 for r in rows)
    assert all(isinstance(r["time"], int) for r in rows)
    assert all(r["source_id"] == "src-x" for r in rows)


def test_ingest_state_wise_end_to_end_validates(tmp_path: Path):
    _stage_fk_targets(tmp_path)
    staging = tmp_path / "staging"
    _stage_two_fy(staging)

    result = ingest_state_wise(repo_root=tmp_path, staging_dir=staging)

    # Three targets emitted, both FYs processed, nothing missing (every FY
    # carries all three indicators).
    assert {t.variable_id for t in result.targets} == {
        _ROOFTOP_VAR, _SALES_VAR, _ALLOC_VAR,
    }
    assert result.fy_labels == ("2023-24", "2024-25")
    assert result.skipped_missing == 0

    geo_dir = tmp_path / "datasets/data/datapoints/geo"
    for var, expected_sid in (
        (_ROOFTOP_VAR, _ROOFTOP_SOURCE_ID),
        (_SALES_VAR, _SALES_SOURCE_ID),
        (_ALLOC_VAR, _ALLOC_SOURCE_ID),
    ):
        out = geo_dir / f"{var}.csv"
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert text.splitlines()[0] == "entity_id,time,value,source_id"
        parsed = list(csv.DictReader(text.splitlines()))
        # 3 entities x 2 FYs = 6 rows; entities are slugs; source_id reproduced.
        assert len(parsed) == 6
        assert {r["entity_id"] for r in parsed} == {
            "IN", "maharashtra", "tamil-nadu",
        }
        assert all(r["source_id"] == expected_sid for r in parsed)
        validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)


def test_missing_indicator_in_one_fy_is_skipped_not_fatal(tmp_path: Path):
    # A FY response missing some indicator keys: those (target, FY) extracts
    # are skipped (counted), and the present indicators + FYs still emit.
    _stage_fk_targets(tmp_path)
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "2024-25.json").write_text(
        json.dumps(_fy_response(
            [120.0, 36.0, 24.0], [9500.0, 3200.0, 2100.0],
            allocated=[52000.0, 41000.0, 31000.0],
        )),
        encoding="utf-8",
    )
    # 2025-26: only Electricity Sales present (Rooftop Solar Capacity AND the
    # allocated capacity sub-dict both missing).
    (staging / "2025-26.json").write_text(
        json.dumps({
            "data": {
                "states": ["All India", "Maharashtra", "Tamil Nadu"],
                "Electricity Sales": [9900.0, 3300.0, 2200.0],
            }
        }),
        encoding="utf-8",
    )

    result = ingest_state_wise(repo_root=tmp_path, staging_dir=staging)

    # Rooftop + allocated each missing from exactly one FY (2025-26) -> 2 skips.
    assert result.skipped_missing == 2
    rooftop = next(t for t in result.targets if t.variable_id == _ROOFTOP_VAR)
    sales = next(t for t in result.targets if t.variable_id == _SALES_VAR)
    allocated = next(t for t in result.targets if t.variable_id == _ALLOC_VAR)
    # Rooftop + allocated emitted only the FY that carried them (3 rows each);
    # sales both FYs (6).
    assert rooftop.row_count == 3
    assert allocated.row_count == 3
    assert sales.row_count == 6


def test_allocated_target_emits_single_source_iced_file(tmp_path: Path):
    # After the 2026-06-19 RBI/ICED publisher-split (plan SC-1) the allocated
    # target owns the ICED-only file installed-capacity-allocated-iced-mw.csv
    # outright (plain write_csv, no merge-preserving upsert). Every emitted row
    # carries the single ICED source_id; the RBI Handbook half lives in a
    # separate file this re-ingest never touches.
    _stage_fk_targets(tmp_path)
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "2015-16.json").write_text(
        json.dumps(_fy_response(
            [100.0, 30.0, 20.0], [9000.0, 3000.0, 2000.0],
            allocated=[60000.0, 45000.0, 35000.0],
        )),
        encoding="utf-8",
    )
    (staging / "2016-17.json").write_text(
        json.dumps(_fy_response(
            [110.0, 33.0, 22.0], [9100.0, 3100.0, 2050.0],
            allocated=[61000.0, 46000.0, 36000.0],
        )),
        encoding="utf-8",
    )

    ingest_state_wise(repo_root=tmp_path, staging_dir=staging)

    # source_id reproduction (explicit, per the task): unchanged ICED triple.
    derived = derive_source_id(
        _CSV_SOURCE_PRODUCER,
        _target(_ALLOC_VAR).source_title,
        _target(_ALLOC_VAR).source_vintage,
    )
    assert derived == _ALLOC_SOURCE_ID == "src-bb1d7bec8b34"

    alloc_path = tmp_path / "datasets/data/datapoints/geo" / f"{_ALLOC_VAR}.csv"
    parsed = list(csv.DictReader(alloc_path.read_text(encoding="utf-8").splitlines()))
    # 3 entities x 2 FYs = 6 rows; the file is single-source ICED only.
    assert len(parsed) == 6
    assert {r["source_id"] for r in parsed} == {_ALLOC_SOURCE_ID}
    assert {int(r["time"]) for r in parsed} == {2015, 2016}
    validate_csv(path=alloc_path, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)
