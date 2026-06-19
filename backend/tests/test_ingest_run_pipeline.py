"""Oracle: the single-series ``run_pipeline`` extraction is byte-neutral.

The plan Row-11 gate is that the TWO existing single-series callers
(``rbi_handbook`` full-workbook REPLACE + the ``rbi_hbs_health`` per-year
UPSERT) emit byte-identical CSV before and after being routed through the
shared ``run_pipeline``. The goldens under ``golden/run_pipeline/`` were
captured from the PRE-extraction code on the deterministic fixtures in
``_run_pipeline_fixtures``; this test re-runs the POST-extraction callers on
the SAME fixtures and asserts every emitted file is byte-identical.

It also covers ``run_pipeline`` directly (replace vs upsert, the empty-series
fail-loud) and proves the greenfield SDG adapter -- the third single-series
caller -- runs idempotently through it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import _run_pipeline_fixtures as fx
from yen_gov.canonical.ingest.run_pipeline import (
    Citation,
    Observation,
    run_pipeline,
)

_GOLDEN_ROOT = Path(__file__).resolve().parent / "golden" / "run_pipeline"


def _assert_byte_identical(repo_root: Path, emitted: tuple[str, ...], golden_dir: str) -> None:
    for rel in emitted:
        got = (repo_root / rel).read_bytes()
        want = (_GOLDEN_ROOT / golden_dir / Path(rel).name).read_bytes()
        assert got == want, (
            f"{rel}: refactored emit diverged from the pre-extraction golden "
            f"(golden/run_pipeline/{golden_dir}/{Path(rel).name})"
        )


class TestByteIdentity:
    """The two existing callers emit byte-identical CSV across the extraction."""

    def test_rbi_handbook_byte_identical(self, tmp_path):
        fx.run_rbi_handbook(tmp_path)
        _assert_byte_identical(tmp_path, fx.RBI_HANDBOOK_EMITTED, "rbi_handbook")

    def test_rbi_hbs_health_byte_identical(self, tmp_path):
        fx.run_rbi_hbs_health(tmp_path)
        _assert_byte_identical(tmp_path, fx.RBI_HBS_HEALTH_EMITTED, "rbi_hbs_health")

    def test_rbi_handbook_idempotent_rerun(self, tmp_path):
        # A second identical run is a no-op: the goldens still match exactly.
        fx.run_rbi_handbook(tmp_path)
        fx.run_rbi_handbook(tmp_path)
        _assert_byte_identical(tmp_path, fx.RBI_HANDBOOK_EMITTED, "rbi_handbook")

    def test_rbi_hbs_health_idempotent_rerun(self, tmp_path):
        fx.run_rbi_hbs_health(tmp_path)
        fx.run_rbi_hbs_health(tmp_path)
        _assert_byte_identical(tmp_path, fx.RBI_HBS_HEALTH_EMITTED, "rbi_hbs_health")


class TestRunPipelineUnit:
    """Direct coverage of the shared pipeline primitive."""

    _CITATION = Citation(
        producer="Test Producer",
        title="Test Series",
        vintage="2024",
        url="https://example.gov.in",
    )

    def _geo(self, repo_root: Path) -> None:
        fx.write_geo(repo_root)

    def test_replace_writes_datapoints_and_source(self, tmp_path):
        self._geo(tmp_path)
        outcome = run_pipeline(
            repo_root=tmp_path,
            indicator_id="unit-replace",
            observations=[
                Observation("kerala", 2020, 1.0),
                Observation("kerala", 2021, 2.0),
            ],
            citation=self._CITATION,
            datapoints_mode="replace",
        )
        out = tmp_path / "datasets/data/datapoints/geo/unit-replace.csv"
        assert out.read_text(encoding="utf-8").splitlines()[0] == (
            "entity_id,time,value,source_id"
        )
        assert outcome.row_count == 2
        assert outcome.entity_count == 1
        assert (outcome.time_min, outcome.time_max) == (2020, 2021)
        assert outcome.source_id.startswith("src-")
        source = (tmp_path / "datasets/data/entities/source.csv").read_text(
            encoding="utf-8"
        )
        assert outcome.source_id in source
        assert "Test Producer" in source

    def test_upsert_merges_without_dropping_prior_years(self, tmp_path):
        self._geo(tmp_path)
        run_pipeline(
            repo_root=tmp_path,
            indicator_id="unit-upsert",
            observations=[Observation("kerala", 2019, 1.0)],
            citation=self._CITATION,
            datapoints_mode="upsert",
        )
        run_pipeline(
            repo_root=tmp_path,
            indicator_id="unit-upsert",
            observations=[Observation("kerala", 2020, 2.0)],
            citation=self._CITATION,
            datapoints_mode="upsert",
        )
        out = tmp_path / "datasets/data/datapoints/geo/unit-upsert.csv"
        rows = out.read_text(encoding="utf-8").splitlines()[1:]
        # Both years survive: the second upsert did not wipe the first.
        assert any(r.startswith("kerala,2019,") for r in rows)
        assert any(r.startswith("kerala,2020,") for r in rows)

    def test_empty_observations_fail_loud(self, tmp_path):
        self._geo(tmp_path)
        with pytest.raises(ValueError, match="no observations"):
            run_pipeline(
                repo_root=tmp_path,
                indicator_id="unit-empty",
                observations=[],
                citation=self._CITATION,
            )


class TestSdgThirdCaller:
    """The greenfield SDG adapter is the third single-series run_pipeline caller."""

    _GEO = (
        "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
        "IN,India,,country,IN|IND|356,,\n"
        "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01,28,28\n"
        "assam,Assam,IN,state,IN-AS|S03,18,18\n"
        "bihar,Bihar,IN,state,IN-BR|S04,10,10\n"
        "gujarat,Gujarat,IN,state,IN-GJ|S06,24,24\n"
        "himachal-pradesh,Himachal Pradesh,IN,state,IN-HP|S08,2,2\n"
        "jharkhand,Jharkhand,IN,state,IN-JH|S07,20,20\n"
        "karnataka,Karnataka,IN,state,IN-KA|S10,29,29\n"
        "kerala,Kerala,IN,state,IN-KL|S11,32,32\n"
        "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22,33,33\n"
        "uttar-pradesh,Uttar Pradesh,IN,state,IN-UP|S24,9,9\n"
    )

    _FIXTURE = (
        Path(__file__).resolve().parents[2]
        / "docs/research/niti-sdg-index-ingest/sdg-india-index-2020-21.csv"
    )

    _EMITTED = (
        "datasets/data/datapoints/geo/sdg-india-index-score.csv",
        "datasets/data/variables.csv",
        "datasets/data/concepts.csv",
        "datasets/data/entities/source.csv",
    )

    def _run(self, repo_root: Path) -> None:
        from yen_gov.canonical.adapters.niti_sdg_index import SHIPPED_SPEC, ingest

        geo = repo_root / "datasets/data/entities/geo.csv"
        geo.parent.mkdir(parents=True, exist_ok=True)
        geo.write_text(self._GEO, encoding="utf-8")
        staging = repo_root / "_staging"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / SHIPPED_SPEC.staging_filename).write_bytes(
            self._FIXTURE.read_bytes()
        )
        ingest(repo_root=repo_root, staging_dir=staging)

    def test_sdg_runs_idempotently_through_run_pipeline(self, tmp_path):
        self._run(tmp_path)
        first = {rel: (tmp_path / rel).read_bytes() for rel in self._EMITTED}
        # A second identical run through run_pipeline is a byte-for-byte no-op.
        self._run(tmp_path)
        for rel in self._EMITTED:
            assert (tmp_path / rel).read_bytes() == first[rel], (
                f"{rel}: SDG re-run through run_pipeline was not idempotent"
            )

