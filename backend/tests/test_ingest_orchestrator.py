"""Orchestrator contract + the rbi_handbook refactor-safety oracle (Row 4).

Covers the Row-4 gates and the one oracle:

* **Equivalence gate.** ``run --indicator X`` == ``--adapter Y --indicator X``.
* **No ``adapter_slug`` branching.** Proven two ways: by source inspection
  (the engine module mentions no adapter by name) AND by design (a fresh fake
  adapter dispatches through the same code path with zero engine edits).
* **Status year spans.** ``status`` reports per-source year spans.
* **Oracle.** rbi_handbook's emitted CSV is byte-identical whether driven by
  the existing direct ``ingest()`` or through the orchestrator; the
  orchestrator's log lines are byte-identical run-to-run (ts dropped -- it is
  control-plane telemetry, not part of the artifact contract). The direct path
  emits no structured log, so log byte-identity is proven across orchestrator
  runs; the CSV byte-identity is the direct-vs-orchestrated refactor-safety leg.

No real-corpus walk: catalogue rows are injected as fixtures so the FK +
concept-compatibility checks never read the taxonomy SOT.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from yen_gov.canonical.adapters.rbi_handbook import (
    ingest as rbi_ingest,
    spec_by_indicator_id,
)
from yen_gov.canonical.ingest import orchestrator as orchestrator_mod
from yen_gov.canonical.ingest.catalogue_fk import (
    CatalogueFkError,
    ConceptCompatibilityError,
)
from yen_gov.canonical.ingest.orchestrator import (
    IngestUsageError,
    build_indicator_index,
    compute_status,
    orchestrate,
)
from yen_gov.canonical.ingest.registry import (
    AdapterRunResult,
    OrchestrateConfig,
    default_registry,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec, SourceSpec
from yen_gov.core.logging import StructuredLogger

_TFR_CSV_REL = "datasets/data/datapoints/geo/total-fertility-rate.csv"

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
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    staging = repo_root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "table-total-fertility-rate.xlsx").write_bytes(_wb_bytes(_TFR_ROWS))
    return staging


def _catalogue() -> tuple[list[dict], list[dict]]:
    """Inject a catalogue that makes total-fertility-rate FK-compatible."""
    indicators = [
        {"indicator_id": "total-fertility-rate", "concept_id": "total-fertility-rate"}
    ]
    concepts = [
        {
            "concept_id": "total-fertility-rate",
            "unit_canonical": "children per woman",
            "normalisation": "ratio",
        }
    ]
    return indicators, concepts


def _result_fields(result) -> list[tuple]:
    return [
        (
            r.adapter_slug,
            r.indicator_id,
            r.output_ref,
            r.row_count,
            r.entity_count,
            r.time_min,
            r.time_max,
            r.source_id,
        )
        for r in result.results
    ]


def _norm_log(path: Path) -> list[dict]:
    """Read JSON-lines, dropping the volatile ``ts`` (control-plane telemetry)."""
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        obj.pop("ts", None)
        out.append(obj)
    return out


class _FakeAdapter:
    """A second adapter; its only job is to prove polymorphic dispatch."""

    adapter_slug = "fake-src"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def source_specs(self) -> tuple[SourceSpec, ...]:
        return (
            SourceSpec(
                adapter_slug="fake-src",
                producer="Fake Producer",
                title="Fake Title",
                vintage="2026",
                url=None,
                indicators=(
                    IndicatorSpec(
                        indicator_id="fake-ind",
                        unit="u",
                        normalisation="absolute",
                    ),
                ),
            ),
        )

    def run_indicator(self, indicator_id, *, repo_root, config) -> AdapterRunResult:
        self.calls.append(indicator_id)
        return AdapterRunResult(
            adapter_slug="fake-src",
            indicator_id=indicator_id,
            output_ref="datasets/data/datapoints/geo/fake-ind.csv",
            row_count=1,
            entity_count=1,
            time_min=2000,
            time_max=2000,
            source_id="src-000000000000",
        )


def _fake_catalogue() -> tuple[list[dict], list[dict]]:
    return (
        [{"indicator_id": "fake-ind", "concept_id": "fake-concept"}],
        [
            {
                "concept_id": "fake-concept",
                "unit_canonical": "u",
                "normalisation": "absolute",
            }
        ],
    )


# --------------------------------------------------------------------------- #
# derived index
# --------------------------------------------------------------------------- #


class TestDerivedIndex:
    def test_maps_every_rbi_indicator_to_the_adapter(self):
        index = build_indicator_index(default_registry())
        assert index["total-fertility-rate"] == ["rbi-handbook"]
        assert {
            "total-fertility-rate",
            "crude-birth-rate-per-1000",
            "crude-death-rate-per-1000",
            "infant-mortality-rate-per-1000",
            "life-expectancy-at-birth-years",
        } <= set(index)


# --------------------------------------------------------------------------- #
# the critical gate: zero `if adapter_slug ==`
# --------------------------------------------------------------------------- #


class TestNoAdapterSlugBranching:
    def test_engine_source_has_no_adapter_branch(self):
        src = Path(orchestrator_mod.__file__).read_text(encoding="utf-8")
        assert "if adapter_slug ==" not in src
        assert 'adapter_slug == "' not in src
        # the engine module names no specific adapter (no rbi_handbook / slug).
        assert "rbi-handbook" not in src
        assert "rbi_handbook" not in src

    def test_dispatches_a_fresh_adapter_with_no_engine_changes(self, tmp_path):
        fake = _FakeAdapter()
        indicators, concepts = _fake_catalogue()
        result = orchestrate(
            indicator="fake-ind",
            repo_root=tmp_path,
            config=OrchestrateConfig(),
            registry={"fake-src": fake},
            indicators=indicators,
            concepts=concepts,
        )
        assert fake.calls == ["fake-ind"]
        assert result.results[0].adapter_slug == "fake-src"
        assert result.fanout_line.startswith("fake-ind <- [fake-src")


# --------------------------------------------------------------------------- #
# target resolution
# --------------------------------------------------------------------------- #


class TestTargetResolution:
    def test_no_scope_raises(self, tmp_path):
        with pytest.raises(IngestUsageError):
            orchestrate(repo_root=tmp_path, config=OrchestrateConfig())

    def test_unknown_indicator_raises(self, tmp_path):
        with pytest.raises(IngestUsageError):
            orchestrate(
                indicator="not-real", repo_root=tmp_path, config=OrchestrateConfig()
            )

    def test_unknown_adapter_raises(self, tmp_path):
        with pytest.raises(IngestUsageError):
            orchestrate(
                adapter="not-real", repo_root=tmp_path, config=OrchestrateConfig()
            )

    def test_adapter_filter_excludes_indicator_owner(self, tmp_path):
        registry = {**default_registry(), "fake-src": _FakeAdapter()}
        # total-fertility-rate is owned by rbi-handbook, not fake-src.
        with pytest.raises(IngestUsageError):
            orchestrate(
                indicator="total-fertility-rate",
                adapter="fake-src",
                repo_root=tmp_path,
                config=OrchestrateConfig(),
                registry=registry,
            )


# --------------------------------------------------------------------------- #
# registration FK + concept-compatibility preamble
# --------------------------------------------------------------------------- #


class TestRegistrationFkCheck:
    def test_indicator_absent_from_catalogue_raises(self, tmp_path):
        with pytest.raises(CatalogueFkError):
            orchestrate(
                indicator="total-fertility-rate",
                repo_root=tmp_path,
                config=OrchestrateConfig(),
                indicators=[],
                concepts=[],
            )

    def test_concept_mismatch_raises(self, tmp_path):
        indicators = [
            {"indicator_id": "total-fertility-rate", "concept_id": "total-fertility-rate"}
        ]
        concepts = [
            {
                "concept_id": "total-fertility-rate",
                "unit_canonical": "WRONG UNIT",
                "normalisation": "ratio",
            }
        ]
        with pytest.raises(ConceptCompatibilityError):
            orchestrate(
                indicator="total-fertility-rate",
                repo_root=tmp_path,
                config=OrchestrateConfig(),
                indicators=indicators,
                concepts=concepts,
            )

    def test_fk_failure_precedes_any_write(self, tmp_path):
        # An FK failure in the preamble must abort before driving the adapter,
        # so no datapoints CSV is written.
        staging = _stage_tfr(tmp_path)
        with pytest.raises(CatalogueFkError):
            orchestrate(
                indicator="total-fertility-rate",
                repo_root=tmp_path,
                config=OrchestrateConfig(staging_dir=staging),
                indicators=[],
                concepts=[],
            )
        assert not (tmp_path / _TFR_CSV_REL).exists()


# --------------------------------------------------------------------------- #
# equivalence gate
# --------------------------------------------------------------------------- #


class TestEquivalence:
    def test_indicator_equals_adapter_plus_indicator(self, tmp_path):
        indicators, concepts = _catalogue()
        repo1 = tmp_path / "by_indicator"
        repo2 = tmp_path / "by_adapter_and_indicator"
        staging1 = _stage_tfr(repo1)
        staging2 = _stage_tfr(repo2)

        result1 = orchestrate(
            indicator="total-fertility-rate",
            repo_root=repo1,
            config=OrchestrateConfig(staging_dir=staging1),
            indicators=indicators,
            concepts=concepts,
        )
        result2 = orchestrate(
            indicator="total-fertility-rate",
            adapter="rbi-handbook",
            repo_root=repo2,
            config=OrchestrateConfig(staging_dir=staging2),
            indicators=indicators,
            concepts=concepts,
        )

        assert _result_fields(result1) == _result_fields(result2)
        assert (repo1 / _TFR_CSV_REL).read_bytes() == (repo2 / _TFR_CSV_REL).read_bytes()


# --------------------------------------------------------------------------- #
# THE ORACLE: byte-identical direct vs orchestrated
# --------------------------------------------------------------------------- #


class TestRbiByteIdenticalOracle:
    def test_csv_byte_identical_direct_vs_orchestrated(self, tmp_path):
        indicators, concepts = _catalogue()
        # before: the EXISTING direct path.
        repo_a = tmp_path / "direct"
        staging_a = _stage_tfr(repo_a)
        direct = rbi_ingest(
            repo_root=repo_a,
            staging_dir=staging_a,
            specs=(spec_by_indicator_id("total-fertility-rate"),),
        )
        csv_direct = (repo_a / _TFR_CSV_REL).read_bytes()

        # after: through the orchestrator.
        repo_b = tmp_path / "orchestrated"
        staging_b = _stage_tfr(repo_b)
        logger = StructuredLogger(
            run_id="20260619-aaaaaaaa", runtime_root=repo_b, echo=False
        )
        result = orchestrate(
            indicator="total-fertility-rate",
            repo_root=repo_b,
            config=OrchestrateConfig(staging_dir=staging_b),
            indicators=indicators,
            concepts=concepts,
            logger=logger,
        )
        logger.close()
        csv_orch = (repo_b / _TFR_CSV_REL).read_bytes()

        # leg 1: the emitted CSV is byte-identical.
        assert csv_direct == csv_orch

        # the orchestrated outcome faithfully reproduces the direct one.
        table = direct.tables[0]
        res = result.results[0]
        assert (
            res.indicator_id,
            res.row_count,
            res.entity_count,
            res.time_min,
            res.time_max,
            res.source_id,
        ) == (
            table.indicator_id,
            table.row_count,
            table.entity_count,
            table.time_min,
            table.time_max,
            table.source_id,
        )

    def test_log_lines_byte_identical_run_to_run(self, tmp_path):
        indicators, concepts = _catalogue()

        def run_into(name: str) -> list[dict]:
            repo = tmp_path / name
            staging = _stage_tfr(repo)
            logger = StructuredLogger(
                run_id="20260619-bbbbbbbb", runtime_root=repo, echo=False
            )
            orchestrate(
                indicator="total-fertility-rate",
                repo_root=repo,
                config=OrchestrateConfig(staging_dir=staging),
                indicators=indicators,
                concepts=concepts,
                logger=logger,
            )
            logger.close()
            return _norm_log(
                repo / ".runtime" / "logs" / "20260619-bbbbbbbb" / "yen-gov.log"
            )

        lines_before = run_into("run_before")
        lines_after = run_into("run_after")
        # leg 2: identical normalized log lines across runs.
        assert lines_before == lines_after

        published = next(o for o in lines_before if o.get("event") == "ingest.published")
        assert published["stage"] == "publish"
        assert published["output"] == _TFR_CSV_REL  # repo-relative POSIX
        assert ":" not in published["output"]
        assert published["rows"] >= 1
        # the fan-out line is logged before the publish line.
        assert lines_before[0]["event"] == "ingest.fanout"


# --------------------------------------------------------------------------- #
# status: per-source year spans
# --------------------------------------------------------------------------- #


class TestStatus:
    def test_per_source_year_spans(self, tmp_path):
        staging = _stage_tfr(tmp_path)
        rbi_ingest(
            repo_root=tmp_path,
            staging_dir=staging,
            specs=(spec_by_indicator_id("total-fertility-rate"),),
        )
        status = compute_status(indicator="total-fertility-rate", repo_root=tmp_path)
        assert status.adapters == ("rbi-handbook",)
        assert status.has_coverage
        assert len(status.coverage) == 1
        coverage = status.coverage[0]
        assert (coverage.year_min, coverage.year_max) == (2016, 2018)
        assert coverage.observation_count >= 1
        assert coverage.source_id.startswith("src-")
        assert coverage.producer  # named from entities/source.csv
        assert status.update_period_days == 365

    def test_no_coverage_when_not_ingested(self, tmp_path):
        status = compute_status(indicator="total-fertility-rate", repo_root=tmp_path)
        assert status.adapters == ("rbi-handbook",)
        assert not status.has_coverage
        assert status.coverage == ()
