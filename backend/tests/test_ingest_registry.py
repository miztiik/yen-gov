"""Contract tests for the ingest adapter registry + protocol (Row 4).

No real-corpus walk (CLAUDE.md section 10): in-memory openpyxl workbooks +
``tmp_path`` repos mirror the real RBI Handbook staging, reusing the layouts
proven in ``test_canonical_rbi_handbook.py``.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from openpyxl import Workbook

from yen_gov.canonical.ingest.registry import (
    Adapter,
    AdapterRunResult,
    IngestConfigError,
    OrchestrateConfig,
    RbiHandbookAdapter,
    default_registry,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "odisha,Odisha,IN,state,IN-OD|S18|lgd:21,21,21\n"
    "jammu-and-kashmir,Jammu & Kashmir,IN,state,IN-JK|U08|lgd:1,1,1\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
)
_TFR_ROWS: list[list[object]] = [
    ["Table 6: State-Wise Total Fertility Rate", None, None, None],
    ["State", 2016, 2017, 2018],
    ["1. Andhra Pradesh", 1.7, 1.6, 1.6],
    ["2. Kerala", 1.8, 1.7, 1.7],
    ["Orissa", 2.1, 2.0, 1.9],
    ["Jammu & Kashmir", 2.0, "N.A.", 1.5],
    ["All India", 2.3, 2.2, 2.0],
    ["Source: SRS Statistical Report 2024", None, None, None],
]


def _wb_bytes(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _stage_tfr(repo_root: Path) -> Path:
    """Write geo.csv + a staged TFR workbook; return the staging dir."""
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    staging = repo_root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "table-total-fertility-rate.xlsx").write_bytes(_wb_bytes(_TFR_ROWS))
    return staging


class TestDefaultRegistry:
    def test_contains_rbi_handbook(self):
        registry = default_registry()
        assert set(registry) == {"rbi-handbook"}
        assert isinstance(registry["rbi-handbook"], RbiHandbookAdapter)

    def test_rbi_adapter_satisfies_protocol(self):
        assert isinstance(RbiHandbookAdapter(), Adapter)

    def test_plain_object_is_not_an_adapter(self):
        assert not isinstance(object(), Adapter)


class TestRbiSourceSpecs:
    def test_groups_into_two_citations(self):
        specs = RbiHandbookAdapter().source_specs()
        # SRS vital rates (one citation, 4 indicators) + SRS abridged life
        # tables (a distinct citation, 1 indicator). A flat indicator list
        # would erase this provenance grouping.
        assert len(specs) == 2
        vital = next(s for s in specs if "Life Tables" not in s.title)
        life = next(s for s in specs if "Life Tables" in s.title)
        assert {i.indicator_id for i in vital.indicators} == {
            "total-fertility-rate",
            "crude-birth-rate-per-1000",
            "crude-death-rate-per-1000",
            "infant-mortality-rate-per-1000",
        }
        assert {i.indicator_id for i in life.indicators} == {
            "life-expectancy-at-birth-years"
        }

    def test_every_source_spec_slug_matches_adapter(self):
        for source_spec in RbiHandbookAdapter().source_specs():
            assert source_spec.adapter_slug == "rbi-handbook"

    def test_indicator_spec_measurement_tuple(self):
        specs = RbiHandbookAdapter().source_specs()
        tfr = next(
            ind
            for source_spec in specs
            for ind in source_spec.indicators
            if ind.indicator_id == "total-fertility-rate"
        )
        assert isinstance(tfr, IndicatorSpec)
        # spec.unit is the CANONICAL unit (catalogue_fk compares it to
        # concept.unit_canonical).
        assert tfr.unit == "children per woman"
        assert tfr.normalisation == "ratio"
        assert tfr.price_basis is None
        assert tfr.sampling_frame is None


class TestRunIndicator:
    def test_requires_staging_dir(self, tmp_path):
        with pytest.raises(IngestConfigError):
            RbiHandbookAdapter().run_indicator(
                "total-fertility-rate",
                repo_root=tmp_path,
                config=OrchestrateConfig(),
            )

    def test_unknown_indicator_raises_keyerror(self, tmp_path):
        staging = _stage_tfr(tmp_path)
        with pytest.raises(KeyError):
            RbiHandbookAdapter().run_indicator(
                "not-an-rbi-indicator",
                repo_root=tmp_path,
                config=OrchestrateConfig(staging_dir=staging),
            )

    def test_drives_ingest_and_reports_repo_relative(self, tmp_path):
        staging = _stage_tfr(tmp_path)
        result = RbiHandbookAdapter().run_indicator(
            "total-fertility-rate",
            repo_root=tmp_path,
            config=OrchestrateConfig(staging_dir=staging),
        )
        assert isinstance(result, AdapterRunResult)
        assert result.adapter_slug == "rbi-handbook"
        assert result.indicator_id == "total-fertility-rate"
        # repo-relative POSIX, no surviving drive letter (CLAUDE.md section 2).
        assert (
            result.output_ref
            == "datasets/data/datapoints/geo/total-fertility-rate.csv"
        )
        assert ":" not in result.output_ref
        assert (result.time_min, result.time_max) == (2016, 2018)
        assert result.row_count > 0
        assert result.entity_count > 0
        assert result.source_id.startswith("src-")
        assert (tmp_path / result.output_ref).is_file()
