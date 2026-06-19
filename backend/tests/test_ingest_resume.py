"""Resume tests (Row 5): a mid-run failure leaves a partial checkpoint; a
re-run (or ``--resume``) continues from the last completed year.

The fetchable ``rbi-hbs-health`` cohort is driven through ``operator_staged`` (no
network); a subclass raises mid-loop to simulate an upstream/agent failure. The
checkpoint is persisted in a ``finally``, so the completed years survive the
crash and the resume run skips exactly them. Every root is a ``tmp_path``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.rbi_hbs_health import RbiHbsHealthAdapter
from yen_gov.canonical.ingest import state
from yen_gov.canonical.ingest.orchestrator import orchestrate
from yen_gov.canonical.ingest.registry import OrchestrateConfig
from yen_gov.core.logging import StructuredLogger

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


class _FailingHealthAdapter(RbiHbsHealthAdapter):
    """Raises mid-loop on ``fail_year`` to simulate a crash partway through."""

    def __init__(self, *, fail_year: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._fail_year = fail_year

    def process_year(self, indicator_id, *, fetched, repo_root, config):
        if fetched.cache_key.year == self._fail_year:
            raise RuntimeError(f"simulated mid-run failure at {self._fail_year}")
        return super().process_year(
            indicator_id, fetched=fetched, repo_root=repo_root, config=config
        )


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


def _times(repo: Path, rel: str) -> set[int]:
    with (repo / rel).open(encoding="utf-8", newline="") as fh:
        return {int(row["time"]) for row in csv.DictReader(fh)}


def _completed_years(repo: Path) -> list[int]:
    cp = state.load(_SLUG, repo)
    return [y["year"] for y in cp["years"] if y.get("completed")]


def _events(repo: Path, run_id: str) -> list[dict]:
    log = repo / ".runtime" / "logs" / run_id / "yen-gov.log"
    out: list[dict] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _run(repo: Path, *, run_id: str, registry, resume: bool = False):
    logger = StructuredLogger(run_id=run_id, runtime_root=repo, echo=False)
    try:
        result = orchestrate(
            indicator="government-hospitals",
            repo_root=repo,
            config=OrchestrateConfig(staging_dir=repo / "staging"),
            logger=logger,
            registry=registry,
            resume=resume,
            indicators=_INDICATORS,
            concepts=_CONCEPTS,
        )
    finally:
        logger.close()
    return result, _events(repo, run_id)


# --------------------------------------------------------------------------- #
# mid-run failure leaves the completed years recorded
# --------------------------------------------------------------------------- #


class TestMidRunFailure:
    def test_failure_persists_partial_checkpoint(self, tmp_path):
        _stage(tmp_path)
        logger = StructuredLogger(
            run_id="20260619-bbbb0001", runtime_root=tmp_path, echo=False
        )
        with pytest.raises(RuntimeError):
            try:
                orchestrate(
                    indicator="government-hospitals",
                    repo_root=tmp_path,
                    config=OrchestrateConfig(staging_dir=tmp_path / "staging"),
                    logger=logger,
                    registry={_SLUG: _FailingHealthAdapter(fail_year=2021)},
                    indicators=_INDICATORS,
                    concepts=_CONCEPTS,
                )
            finally:
                logger.close()
        # 2019 + 2020 completed before the crash at 2021; 2021/2022 not recorded.
        assert _completed_years(tmp_path) == [2019, 2020]
        assert _times(tmp_path, _GOV_CSV_REL) == {2019, 2020}


# --------------------------------------------------------------------------- #
# resume continues from the last completed year
# --------------------------------------------------------------------------- #


class TestResume:
    def test_resume_completes_remaining_years(self, tmp_path):
        _stage(tmp_path)
        # run 1 crashes at 2021.
        logger = StructuredLogger(
            run_id="20260619-bbbb0002", runtime_root=tmp_path, echo=False
        )
        with pytest.raises(RuntimeError):
            try:
                orchestrate(
                    indicator="government-hospitals",
                    repo_root=tmp_path,
                    config=OrchestrateConfig(staging_dir=tmp_path / "staging"),
                    logger=logger,
                    registry={_SLUG: _FailingHealthAdapter(fail_year=2021)},
                    indicators=_INDICATORS,
                    concepts=_CONCEPTS,
                )
            finally:
                logger.close()

        # run 2 --resume with a healthy adapter completes the remaining years.
        adapter2 = RbiHbsHealthAdapter()
        _result, events = _run(
            tmp_path,
            run_id="20260619-bbbb0003",
            registry={_SLUG: adapter2},
            resume=True,
        )
        skipped = sorted(e["year"] for e in events if e["event"] == "fetch.skipped")
        assert skipped == [2019, 2020]  # the already-completed years
        assert sorted(y for _, y in adapter2.processed) == [2021, 2022]  # remaining
        assert _times(tmp_path, _GOV_CSV_REL) == {2019, 2020, 2021, 2022}
        assert _completed_years(tmp_path) == [2019, 2020, 2021, 2022]
        # the resume affordance is logged.
        assert any(e["event"] == "ingest.resume" for e in events)

    def test_plain_run_resumes_identically_to_resume_flag(self, tmp_path):
        """Plain ``run`` is idempotent with the same effect as ``--resume``."""
        _stage(tmp_path)
        # crash at 2020 this time.
        logger = StructuredLogger(
            run_id="20260619-bbbb0004", runtime_root=tmp_path, echo=False
        )
        with pytest.raises(RuntimeError):
            try:
                orchestrate(
                    indicator="government-hospitals",
                    repo_root=tmp_path,
                    config=OrchestrateConfig(staging_dir=tmp_path / "staging"),
                    logger=logger,
                    registry={_SLUG: _FailingHealthAdapter(fail_year=2020)},
                    indicators=_INDICATORS,
                    concepts=_CONCEPTS,
                )
            finally:
                logger.close()
        assert _completed_years(tmp_path) == [2019]

        # plain run (resume=False) continues from the checkpoint just the same.
        adapter2 = RbiHbsHealthAdapter()
        _run(
            tmp_path,
            run_id="20260619-bbbb0005",
            registry={_SLUG: adapter2},
            resume=False,
        )
        assert sorted(y for _, y in adapter2.processed) == [2020, 2021, 2022]
        assert _completed_years(tmp_path) == [2019, 2020, 2021, 2022]
        assert _times(tmp_path, _GOV_CSV_REL) == {2019, 2020, 2021, 2022}
