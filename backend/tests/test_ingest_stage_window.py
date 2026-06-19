"""Stage-window (--from/--to) tests: validation + window semantics (Section 3).

The ``ingest run --from/--to STAGE`` window slices the pipeline
(``fetch`` -> ``enrich`` -> ``publish``). These tests prove:

* the :class:`StageWindow` type + its order invariant (from must not follow to);
* the default (no window) is byte-identical to an explicit full window;
* ``--to fetch`` warms the claim-check cache and emits NO datapoints;
* the ORACLE: ``--to fetch`` then ``--from enrich`` (same indicator) produces the
  SAME datapoints as a full run -- proving the window re-uses the cache without
  re-fetching;
* ``--from enrich`` on a cold cache FAILS LOUD;
* a non-default window against a non-fetchable adapter is refused;
* the CLI exits 2 on an invalid stage or an inverted (from > to) window.

The fetchable ``rbi-hbs-health`` cohort is driven through ``operator_staged``
(no network), reusing the Row-5 delta/resume fixture shape. Catalogue rows are
injected (the Row-4 precedent), so no test walks the real taxonomy. Every root
is a ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from yen_gov.canonical.adapters.rbi_hbs_health import RbiHbsHealthAdapter
from yen_gov.canonical.ingest import state
from yen_gov.canonical.ingest.cli import ingest_app
from yen_gov.canonical.ingest.fetch import CACHE_DIR_REL, FetchError
from yen_gov.canonical.ingest.orchestrator import (
    IngestUsageError,
    Stage,
    StageWindow,
    orchestrate,
)
from yen_gov.canonical.ingest.registry import OrchestrateConfig
from yen_gov.core.logging import StructuredLogger

runner = CliRunner()

_SLUG = "rbi-hbs-health"
_GOV_CSV_REL = "datasets/data/datapoints/geo/government-hospitals.csv"
_YEARS = (2019, 2020, 2021, 2022)

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "odisha,Odisha,IN,state,IN-OD|S18|lgd:21,21,21\n"
)
_INDICATORS = [
    {"indicator_id": "government-hospitals", "concept_id": "government-hospitals"},
]
_CONCEPTS = [
    {
        "concept_id": "government-hospitals",
        "unit_canonical": "hospitals",
        "normalisation": "absolute",
    },
]

# total-fertility-rate is owned by the NON-fetchable rbi-handbook adapter; used
# to prove a stage window is refused on an adapter with no cache seam.
_TFR_INDICATORS = [
    {"indicator_id": "total-fertility-rate", "concept_id": "total-fertility-rate"}
]
_TFR_CONCEPTS = [
    {
        "concept_id": "total-fertility-rate",
        "unit_canonical": "children per woman",
        "normalisation": "ratio",
    }
]


def _health_csv(year: int) -> str:
    ap = 190 + (year - 2019)
    return (
        "state,government_hospitals,hospital_beds\n"
        f"Andhra Pradesh,{ap},16500\n"
        "Kerala,1280,38004\n"
        "Odisha,1735,17000\n"
        "All India,25778,713986\n"
    )


def _stage(repo: Path) -> Path:
    geo = repo / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    staging = repo / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    for year in _YEARS:
        (staging / f"health-{year}.csv").write_text(
            _health_csv(year), encoding="utf-8"
        )
    return staging


def _run(
    repo: Path,
    *,
    run_id: str,
    indicator: str = "government-hospitals",
    staging: Path | None,
    registry,
    resume: bool = False,
    stage_window: StageWindow | None = None,
):
    logger = StructuredLogger(run_id=run_id, runtime_root=repo, echo=False)
    try:
        result = orchestrate(
            indicator=indicator,
            repo_root=repo,
            config=OrchestrateConfig(staging_dir=staging),
            logger=logger,
            registry=registry,
            resume=resume,
            stage_window=stage_window,
            indicators=_INDICATORS,
            concepts=_CONCEPTS,
        )
    finally:
        logger.close()
    return result


def _cache_file(repo: Path, year: int) -> Path:
    return repo / Path(CACHE_DIR_REL) / _SLUG / f"health-{year}.csv"


def _completed_years(repo: Path) -> list[int]:
    cp = state.load(_SLUG, repo)
    return [y["year"] for y in cp["years"] if y.get("completed")]


# --------------------------------------------------------------------------- #
# the StageWindow type + its order invariant
# --------------------------------------------------------------------------- #


class TestStageWindowModel:
    def test_default_is_the_full_flow(self):
        window = StageWindow()
        assert window.from_stage == Stage.fetch
        assert window.to_stage == Stage.publish
        assert window.runs_fetch is True
        assert window.runs_process is True
        assert window.is_full is True

    def test_to_fetch_runs_fetch_only(self):
        window = StageWindow(to_stage=Stage.fetch)
        assert window.runs_fetch is True
        assert window.runs_process is False
        assert window.is_full is False

    def test_from_enrich_skips_fetch(self):
        window = StageWindow(from_stage=Stage.enrich)
        assert window.runs_fetch is False
        assert window.runs_process is True
        assert window.is_full is False

    def test_from_publish_skips_fetch_runs_process(self):
        window = StageWindow(from_stage=Stage.publish)
        assert window.runs_fetch is False
        assert window.runs_process is True

    def test_inverted_window_is_rejected(self):
        # publish comes after fetch in stage order, so from=publish/to=fetch
        # inverts the window and must be refused at construction.
        with pytest.raises(ValidationError):
            StageWindow(from_stage=Stage.publish, to_stage=Stage.fetch)

    def test_enrich_to_fetch_is_rejected(self):
        with pytest.raises(ValidationError):
            StageWindow(from_stage=Stage.enrich, to_stage=Stage.fetch)


# --------------------------------------------------------------------------- #
# default (no window) is byte-identical to an explicit full window
# --------------------------------------------------------------------------- #


class TestDefaultUnchanged:
    def test_no_window_matches_explicit_full_window(self, tmp_path):
        root_a = tmp_path / "a"
        staging_a = _stage(root_a)
        _run(
            root_a,
            run_id="20260619-cccc0001",
            staging=staging_a,
            registry={_SLUG: RbiHbsHealthAdapter()},
            stage_window=None,  # the windowless default
        )
        root_b = tmp_path / "b"
        staging_b = _stage(root_b)
        _run(
            root_b,
            run_id="20260619-cccc0002",
            staging=staging_b,
            registry={_SLUG: RbiHbsHealthAdapter()},
            stage_window=StageWindow(),  # the explicit full window
        )
        assert (
            (root_a / _GOV_CSV_REL).read_bytes()
            == (root_b / _GOV_CSV_REL).read_bytes()
        )


# --------------------------------------------------------------------------- #
# --to fetch: warm the cache, emit no datapoints, mark nothing completed
# --------------------------------------------------------------------------- #


class TestToFetch:
    def test_fetch_only_warms_cache_and_emits_no_datapoints(self, tmp_path):
        staging = _stage(tmp_path)
        result = _run(
            tmp_path,
            run_id="20260619-cccc0003",
            staging=staging,
            registry={_SLUG: RbiHbsHealthAdapter()},
            stage_window=StageWindow(to_stage=Stage.fetch),
        )
        # nothing published: no results, no datapoints CSV on disk.
        assert result.results == ()
        assert not (tmp_path / _GOV_CSV_REL).is_file()
        # ...but every per-year claim-check is warm for a later --from enrich.
        for year in _YEARS:
            assert _cache_file(tmp_path, year).is_file()
        # no year is marked completed (fetch-only is not "done").
        assert _completed_years(tmp_path) == []


# --------------------------------------------------------------------------- #
# ORACLE: --to fetch then --from enrich == a full run (cache re-used)
# --------------------------------------------------------------------------- #


class TestFromEnrichReusesCache:
    def test_to_fetch_then_from_enrich_equals_full_run(self, tmp_path):
        # baseline: a single full run on its own root.
        root_full = tmp_path / "full"
        staging_full = _stage(root_full)
        _run(
            root_full,
            run_id="20260619-cccc0004",
            staging=staging_full,
            registry={_SLUG: RbiHbsHealthAdapter()},
        )
        full_bytes = (root_full / _GOV_CSV_REL).read_bytes()

        # windowed: --to fetch (warm cache), then --from enrich (no staging).
        root_win = tmp_path / "win"
        staging_win = _stage(root_win)
        fetch_only = _run(
            root_win,
            run_id="20260619-cccc0005",
            staging=staging_win,
            registry={_SLUG: RbiHbsHealthAdapter()},
            stage_window=StageWindow(to_stage=Stage.fetch),
        )
        assert fetch_only.results == ()
        assert not (root_win / _GOV_CSV_REL).is_file()

        # --from enrich with NO staging dir: it must read the warm cache, never
        # the network or staging, and reproduce the full run's datapoints.
        enrich = _run(
            root_win,
            run_id="20260619-cccc0006",
            staging=None,
            registry={_SLUG: RbiHbsHealthAdapter()},
            stage_window=StageWindow(from_stage=Stage.enrich),
        )
        win_bytes = (root_win / _GOV_CSV_REL).read_bytes()
        assert win_bytes == full_bytes
        # the enrich window published + completed every year.
        assert len(enrich.results) == 1
        assert sorted(_completed_years(root_win)) == list(_YEARS)

    def test_from_enrich_cold_cache_fails_loud(self, tmp_path):
        # no prior fetch -> the claim-check cache is cold -> fail loud.
        (tmp_path / "datasets" / "data" / "entities").mkdir(
            parents=True, exist_ok=True
        )
        (tmp_path / "datasets" / "data" / "entities" / "geo.csv").write_text(
            _GEO_CSV, encoding="utf-8"
        )
        with pytest.raises(FetchError, match="no cached raw"):
            _run(
                tmp_path,
                run_id="20260619-cccc0007",
                staging=None,
                registry={_SLUG: RbiHbsHealthAdapter()},
                stage_window=StageWindow(from_stage=Stage.enrich),
            )


# --------------------------------------------------------------------------- #
# a non-default window is refused on a non-fetchable adapter
# --------------------------------------------------------------------------- #


class TestNonFetchableRefusesWindow:
    def test_window_on_non_fetchable_adapter_raises(self, tmp_path):
        # total-fertility-rate is owned by rbi-handbook, which fuses
        # fetch+enrich+publish in run_indicator (no cache seam).
        logger = StructuredLogger(
            run_id="20260619-cccc0008", runtime_root=tmp_path, echo=False
        )
        try:
            with pytest.raises(IngestUsageError, match="not fetchable"):
                orchestrate(
                    indicator="total-fertility-rate",
                    repo_root=tmp_path,
                    config=OrchestrateConfig(staging_dir=None),
                    logger=logger,
                    stage_window=StageWindow(to_stage=Stage.fetch),
                    indicators=_TFR_INDICATORS,
                    concepts=_TFR_CONCEPTS,
                )
        finally:
            logger.close()

    def test_full_window_on_non_fetchable_is_allowed_through(self, tmp_path):
        # the default full window must NOT trip the refusal -- it should reach
        # run_indicator (which then fails only for the missing --staging-dir).
        from yen_gov.canonical.ingest.registry import IngestConfigError

        logger = StructuredLogger(
            run_id="20260619-cccc0009", runtime_root=tmp_path, echo=False
        )
        try:
            with pytest.raises(IngestConfigError, match="staging-dir"):
                orchestrate(
                    indicator="total-fertility-rate",
                    repo_root=tmp_path,
                    config=OrchestrateConfig(staging_dir=None),
                    logger=logger,
                    stage_window=StageWindow(),  # full
                    indicators=_TFR_INDICATORS,
                    concepts=_TFR_CONCEPTS,
                )
        finally:
            logger.close()


# --------------------------------------------------------------------------- #
# CLI: invalid stage + inverted window both exit 2; --help lists the flags
# --------------------------------------------------------------------------- #


class TestCliStageWindow:
    def test_run_help_lists_from_and_to(self):
        result = runner.invoke(ingest_app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--from" in result.output
        assert "--to" in result.output

    def test_invalid_stage_exits_two(self, tmp_path):
        result = runner.invoke(
            ingest_app,
            [
                "run",
                "--from",
                "bogus",
                "--indicator",
                "government-hospitals",
                "--root",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 2

    def test_from_after_to_exits_two(self, tmp_path):
        result = runner.invoke(
            ingest_app,
            [
                "run",
                "--from",
                "publish",
                "--to",
                "fetch",
                "--indicator",
                "government-hospitals",
                "--root",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 2
        assert "must not be after" in result.output
