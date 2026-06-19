"""Delta-skip + dedup tests (Row 5) driven through the orchestrator.

The fetchable ``rbi-hbs-health`` cohort is exercised end to end via the
``operator_staged`` path (no network) so the committed year-checkpoint, the
``fetch.skipped`` events, and the per-year re-emit are all observable. Catalogue
rows are injected as fixtures (the Row-4 precedent), so no test walks the real
taxonomy. Every root is a ``tmp_path``.

Gates covered:
* two indicators sharing a unit fetch once;
* a 2nd run with unchanged years emits ``fetch.skipped`` + zero new output bytes;
* a ``spec_version`` bump re-emits (re-processes) every year.
Oracle covered:
* run twice -> run 2 ``fetch.skipped`` + the output CSV mtime is untouched;
* mutating one year's raw fixture re-emits exactly that year.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from yen_gov.canonical.adapters.rbi_hbs_health import RbiHbsHealthAdapter
from yen_gov.canonical.ingest import state
from yen_gov.canonical.ingest.orchestrator import orchestrate
from yen_gov.canonical.ingest.registry import OrchestrateConfig
from yen_gov.core.logging import StructuredLogger

_SLUG = "rbi-hbs-health"
_GOV_CSV_REL = "datasets/data/datapoints/geo/government-hospitals.csv"
_BEDS_CSV_REL = "datasets/data/datapoints/geo/hospital-beds.csv"

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "odisha,Odisha,IN,state,IN-OD|S18|lgd:21,21,21\n"
)

_INDICATORS = [
    {"indicator_id": "government-hospitals", "concept_id": "government-hospitals"},
    {"indicator_id": "hospital-beds", "concept_id": "hospital-beds"},
]
_CONCEPTS = [
    {
        "concept_id": "government-hospitals",
        "unit_canonical": "hospitals",
        "normalisation": "absolute",
    },
    {
        "concept_id": "hospital-beds",
        "unit_canonical": "beds",
        "normalisation": "absolute",
    },
]

_YEARS = (2019, 2020, 2021, 2022)


def _health_csv(year: int, *, ap_hospitals: int | None = None) -> str:
    ap = ap_hospitals if ap_hospitals is not None else 190 + (year - 2019)
    return (
        "state,government_hospitals,hospital_beds\n"
        f"Andhra Pradesh,{ap},16500\n"
        "Kerala,1280,38004\n"
        "Odisha,1735,17000\n"
        "All India,25778,713986\n"
    )


def _stage(repo: Path, years: tuple[int, ...] = _YEARS) -> Path:
    geo = repo / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    staging = repo / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    for year in years:
        (staging / f"health-{year}.csv").write_text(
            _health_csv(year), encoding="utf-8"
        )
    return staging


def _events(repo: Path, run_id: str) -> list[dict]:
    log = repo / ".runtime" / "logs" / run_id / "yen-gov.log"
    out: list[dict] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _run(
    repo: Path,
    *,
    run_id: str,
    indicator: str | None = None,
    adapter_scope: str | None = None,
    staging: Path,
    registry,
    resume: bool = False,
):
    logger = StructuredLogger(run_id=run_id, runtime_root=repo, echo=False)
    try:
        result = orchestrate(
            indicator=indicator,
            adapter=adapter_scope,
            repo_root=repo,
            config=OrchestrateConfig(staging_dir=staging),
            logger=logger,
            registry=registry,
            resume=resume,
            indicators=_INDICATORS,
            concepts=_CONCEPTS,
        )
    finally:
        logger.close()
    return result, _events(repo, run_id)


def _value_for(repo: Path, rel: str, entity_id: str, time: int) -> float:
    with (repo / rel).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["entity_id"] == entity_id and int(row["time"]) == time:
                return float(row["value"])
    raise AssertionError(f"no row for {entity_id} {time} in {rel}")


# --------------------------------------------------------------------------- #
# first run: emits + records a complete checkpoint
# --------------------------------------------------------------------------- #


class TestFirstRun:
    def test_emits_and_records_all_years(self, tmp_path):
        staging = _stage(tmp_path)
        adapter = RbiHbsHealthAdapter()
        result, events = _run(
            tmp_path,
            run_id="20260619-aaaa0001",
            indicator="government-hospitals",
            staging=staging,
            registry={_SLUG: adapter},
        )
        assert (tmp_path / _GOV_CSV_REL).is_file()
        # every year processed (no skips on a fresh run).
        assert [e for e in events if e["event"] == "fetch.skipped"] == []
        assert sorted(y for _, y in adapter.processed) == list(_YEARS)
        cp = state.load(_SLUG, tmp_path)
        assert [y["year"] for y in cp["years"]] == list(_YEARS)
        assert all(y["completed"] for y in cp["years"])
        assert cp["spec_version"] == "v1"
        res = result.results[0]
        assert (res.time_min, res.time_max) == (2019, 2022)


# --------------------------------------------------------------------------- #
# the dedup gate: two indicators share one cache unit, fetched once
# --------------------------------------------------------------------------- #


class TestDedup:
    def test_two_indicators_share_one_fetch_per_year(self, tmp_path):
        staging = _stage(tmp_path)
        adapter = RbiHbsHealthAdapter()
        _result, events = _run(
            tmp_path,
            run_id="20260619-aaaa0002",
            adapter_scope=_SLUG,  # both indicators
            staging=staging,
            registry={_SLUG: adapter},
        )
        # both CSVs emitted.
        assert (tmp_path / _GOV_CSV_REL).is_file()
        assert (tmp_path / _BEDS_CSV_REL).is_file()
        # 4 years x 2 indicators = 8 process_year calls...
        assert len(adapter.processed) == 8
        # ...but the shared per-year file is fetched ONCE per year (4), not 8.
        completed = [e for e in events if e["event"] == "fetch.completed"]
        assert len(completed) == 4


# --------------------------------------------------------------------------- #
# delta: a 2nd run with unchanged years skips + leaves the output untouched
# --------------------------------------------------------------------------- #


class TestSecondRunSkips:
    def test_unchanged_run_skips_all_years_and_does_not_touch_csv(self, tmp_path):
        staging = _stage(tmp_path)
        registry = {_SLUG: RbiHbsHealthAdapter()}
        _run(
            tmp_path,
            run_id="20260619-aaaa0003",
            indicator="government-hospitals",
            staging=staging,
            registry=registry,
        )
        csv_path = tmp_path / _GOV_CSV_REL
        mtime_before = csv_path.stat().st_mtime_ns
        bytes_before = csv_path.read_bytes()

        adapter2 = RbiHbsHealthAdapter()
        _result, events = _run(
            tmp_path,
            run_id="20260619-aaaa0004",
            indicator="government-hospitals",
            staging=staging,
            registry={_SLUG: adapter2},
        )
        # every year skipped; nothing re-processed.
        skipped = sorted(e["year"] for e in events if e["event"] == "fetch.skipped")
        assert skipped == list(_YEARS)
        assert adapter2.processed == []
        # the output CSV is byte- and mtime-untouched (zero new output bytes).
        assert csv_path.stat().st_mtime_ns == mtime_before
        assert csv_path.read_bytes() == bytes_before
        # the staleness clock still advanced on the skip (never hides staleness).
        cp = state.load(_SLUG, tmp_path)
        assert all(y["completed"] for y in cp["years"])


# --------------------------------------------------------------------------- #
# delta: mutating one year's raw fixture re-emits exactly that year
# --------------------------------------------------------------------------- #


class TestReopenOneYear:
    def test_mutating_one_year_reemits_only_that_year(self, tmp_path):
        staging = _stage(tmp_path)
        _run(
            tmp_path,
            run_id="20260619-aaaa0005",
            indicator="government-hospitals",
            staging=staging,
            registry={_SLUG: RbiHbsHealthAdapter()},
        )
        # publisher revises 2020 only.
        (staging / "health-2020.csv").write_text(
            _health_csv(2020, ap_hospitals=999), encoding="utf-8"
        )
        adapter2 = RbiHbsHealthAdapter()
        _result, events = _run(
            tmp_path,
            run_id="20260619-aaaa0006",
            indicator="government-hospitals",
            staging=staging,
            registry={_SLUG: adapter2},
        )
        skipped = sorted(e["year"] for e in events if e["event"] == "fetch.skipped")
        assert skipped == [2019, 2021, 2022]  # exactly the unchanged years
        assert adapter2.processed == [("government-hospitals", 2020)]
        # the revised value is now on disk; the untouched years are unchanged.
        assert _value_for(tmp_path, _GOV_CSV_REL, "andhra-pradesh", 2020) == 999.0
        assert _value_for(tmp_path, _GOV_CSV_REL, "andhra-pradesh", 2019) == 190.0


# --------------------------------------------------------------------------- #
# delta: a spec_version bump re-opens every year
# --------------------------------------------------------------------------- #


class TestSpecBump:
    def test_spec_bump_reprocesses_all_years(self, tmp_path):
        staging = _stage(tmp_path)
        _run(
            tmp_path,
            run_id="20260619-aaaa0007",
            indicator="government-hospitals",
            staging=staging,
            registry={_SLUG: RbiHbsHealthAdapter(spec_version="v1")},
        )
        # same raw bytes, but the adapter's spec_version bumped -> re-open all.
        bumped = RbiHbsHealthAdapter(spec_version="v2")
        _result, events = _run(
            tmp_path,
            run_id="20260619-aaaa0008",
            indicator="government-hospitals",
            staging=staging,
            registry={_SLUG: bumped},
        )
        # no year is skipped despite the raw payload being unchanged.
        assert [e for e in events if e["event"] == "fetch.skipped"] == []
        assert sorted(y for _, y in bumped.processed) == list(_YEARS)
        cp = state.load(_SLUG, tmp_path)
        assert cp["spec_version"] == "v2"
