"""Tier-B gate: ICED state-wise deep-dive -> single-value energy re-ingest.

Graduates the orphan single-value ICED state-wise energy indicators to LIVE
re-ingest: each decrypted per-FY response carries parallel ``states`` /
indicator-key arrays; the multi-FY ingest accumulates the per-state column
across fiscal years, re-keys ECI state codes to LGD slugs (``IN`` passthrough),
reduces ``YYYY-04`` fiscal-year periods to integer years, and emits one
``geo/<variable_id>.csv`` per target. No mocks (Holy Law #7); tmp_path fixtures
only. The triples reproduce the on-disk source_ids so a re-emit is idempotent
with the committed files.

SCOPE: two single-source ICED targets (rooftop-solar-capacity-mw,
electricity-sales-mu). installed-capacity-allocated-mw is EXCLUDED -- its
on-disk file is a dual-source historical merge (RBI Handbook Table 140 for
FY2004-2014 + ICED State-wise Deep Dive for FY2015+); a clean ICED-only re-emit
would truncate the RBI history, so it is left to the RBI Handbook ingest. See
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

# On-disk filenames (== variable_id) for the two included targets.
_ROOFTOP_VAR = "rooftop-solar-capacity-mw"
_SALES_VAR = "electricity-sales-mu"

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
    for var in (_ROOFTOP_VAR, _SALES_VAR):
        target = _target(var)
        lines.append(
            f"{_source_id(var)},{_CSV_SOURCE_PRODUCER},{target.source_title},"
            f"{target.source_vintage},"
        )
    (entities / "source.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fy_response(rooftop: list[float], sales: list[float]) -> dict:
    # One decrypted state-wise response: parallel `states` + indicator arrays.
    # "All India" -> IN; "Maharashtra" -> S13 -> maharashtra; "Tamil Nadu" ->
    # S22 -> tamil-nadu.
    return {
        "data": {
            "states": ["All India", "Maharashtra", "Tamil Nadu"],
            "Rooftop Solar Capacity": rooftop,
            "Electricity Sales": sales,
        }
    }


def _stage_two_fy(staging_dir: Path) -> None:
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "2023-24.json").write_text(
        json.dumps(_fy_response([100.0, 30.0, 20.0], [9000.0, 3000.0, 2000.0])),
        encoding="utf-8",
    )
    (staging_dir / "2024-25.json").write_text(
        json.dumps(_fy_response([120.0, 36.0, 24.0], [9500.0, 3200.0, 2100.0])),
        encoding="utf-8",
    )


def test_targets_map_to_on_disk_filenames():
    # The registry's variable_ids are the EXACT on-disk geo/*.csv filenames.
    got = {t.variable_id for t in _STATE_WISE_TARGETS}
    assert got == {_ROOFTOP_VAR, _SALES_VAR}
    # installed-capacity-allocated-mw is intentionally absent (dual-source).
    assert "installed-capacity-allocated-mw" not in got


def test_source_ids_reproduce_on_disk():
    # Pinned so a re-emit is idempotent with the committed files.
    assert _source_id(_ROOFTOP_VAR) == _ROOFTOP_SOURCE_ID
    assert _source_id(_SALES_VAR) == _SALES_SOURCE_ID


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

    # Two targets emitted (allocated excluded), both FYs processed, nothing
    # missing (every FY carries both indicators).
    assert {t.variable_id for t in result.targets} == {_ROOFTOP_VAR, _SALES_VAR}
    assert result.fy_labels == ("2023-24", "2024-25")
    assert result.skipped_missing == 0

    geo_dir = tmp_path / "datasets/data/datapoints/geo"
    for var, expected_sid in (
        (_ROOFTOP_VAR, _ROOFTOP_SOURCE_ID),
        (_SALES_VAR, _SALES_SOURCE_ID),
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
    # A FY response missing one indicator key is skipped (counted), and the
    # other indicator + the present FYs still emit.
    _stage_fk_targets(tmp_path)
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "2024-25.json").write_text(
        json.dumps(_fy_response([120.0, 36.0, 24.0], [9500.0, 3200.0, 2100.0])),
        encoding="utf-8",
    )
    # 2025-26: only Electricity Sales present (Rooftop Solar Capacity missing).
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

    # Rooftop missing from exactly one FY (2025-26) -> one skip.
    assert result.skipped_missing == 1
    rooftop = next(t for t in result.targets if t.variable_id == _ROOFTOP_VAR)
    sales = next(t for t in result.targets if t.variable_id == _SALES_VAR)
    # Rooftop emitted only the FY that carried it (3 rows); sales both (6).
    assert rooftop.row_count == 3
    assert sales.row_count == 6
