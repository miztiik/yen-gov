"""Tests for the splice break-row gate (Row 6).

Covers ``find_seams`` / ``load_methodology_breaks`` / ``check_splice`` units,
the Row-6 splice ORACLE (refuse -> author a break row at the seam -> publish ONE
series with each row's ``source_id`` intact), and the orchestrator wiring (a
driven adapter that emits a mid-series ``source_id`` change makes ``orchestrate``
refuse until a covering break exists). Disjoint-entity multi-source does NOT
trigger the gate. tmp_path fixtures; no corpus walk.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.ingest.messages import CanonicalBatch, CanonicalObservationRow
from yen_gov.canonical.ingest.orchestrator import (
    apply_publish_gates,
    compute_status,
    orchestrate,
)
from yen_gov.canonical.ingest.registry import (
    AdapterRunResult,
    OrchestrateConfig,
    summarise_indicator_csv,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec, SourceSpec
from yen_gov.canonical.ingest.splice_guard import (
    MethodologyBreak,
    SpliceBreakRowError,
    check_splice,
    find_seams,
    load_methodology_breaks,
)

_GEO_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_SRC_A = "src-aaaaaaaaaaaa"
_SRC_B = "src-bbbbbbbbbbbb"


def _obs(entity_id: str, time: int, source_id: str, value: float = 1.0) -> CanonicalObservationRow:
    return CanonicalObservationRow(
        entity_id=entity_id, time=time, value=value, source_id=source_id
    )


# --------------------------------------------------------------------------- #
# find_seams
# --------------------------------------------------------------------------- #


class TestFindSeams:
    def test_single_source_series_has_no_seam(self):
        rows = [_obs("kerala", t, _SRC_A) for t in (2010, 2011, 2012)]
        assert find_seams(rows) == {}

    def test_mid_series_source_change_is_a_seam(self):
        rows = [
            _obs("kerala", 2013, _SRC_A),
            _obs("kerala", 2014, _SRC_A),
            _obs("kerala", 2015, _SRC_B),
            _obs("kerala", 2016, _SRC_B),
        ]
        assert find_seams(rows) == {"kerala": [2015]}

    def test_disjoint_entity_multi_source_does_not_trigger(self):
        # Each entity is single-source: a legitimate multi-publisher PANEL, not
        # a spliced series. No seam on any single line.
        rows = [
            _obs("kerala", 2015, _SRC_A),
            _obs("kerala", 2016, _SRC_A),
            _obs("goa", 2015, _SRC_B),
            _obs("goa", 2016, _SRC_B),
        ]
        assert find_seams(rows) == {}

    def test_unsorted_rows_are_ordered_before_scanning(self):
        rows = [
            _obs("kerala", 2016, _SRC_B),
            _obs("kerala", 2014, _SRC_A),
            _obs("kerala", 2015, _SRC_B),
        ]
        assert find_seams(rows) == {"kerala": [2015]}


# --------------------------------------------------------------------------- #
# load_methodology_breaks
# --------------------------------------------------------------------------- #


class TestLoadBreaks:
    def test_injected_rows_index_by_version(self):
        breaks = load_methodology_breaks(
            breaks=[
                {"methodology_version": "mv-x", "at_year": "2015", "at_period_seq": "4"},
                {"methodology_version": "mv-y", "at_year": 2012},
            ]
        )
        assert breaks["mv-x"].at_year == 2015
        assert breaks["mv-x"].at_period_seq == 4
        assert breaks["mv-y"].at_year == 2012
        assert breaks["mv-y"].at_period_seq == 1

    def test_missing_file_yields_empty(self, tmp_path):
        assert load_methodology_breaks(breaks_path=tmp_path / "nope.csv") == {}

    def test_reads_a_fixture_csv(self, tmp_path):
        path = tmp_path / "methodology_breaks.csv"
        path.write_text(
            "methodology_version,at_year,at_period_seq\nmv-z,2018,1\n",
            encoding="utf-8",
        )
        breaks = load_methodology_breaks(breaks_path=path)
        assert breaks["mv-z"].at_year == 2018


# --------------------------------------------------------------------------- #
# check_splice
# --------------------------------------------------------------------------- #


class TestCheckSplice:
    def test_no_seam_passes_without_any_break(self):
        rows = [_obs("kerala", t, _SRC_A) for t in (2010, 2011)]
        assert check_splice(
            rows, indicator_id="x", methodology_break_ids=None, breaks={}
        ) == ()

    def test_uncovered_seam_raises(self):
        rows = [_obs("kerala", 2014, _SRC_A), _obs("kerala", 2015, _SRC_B)]
        with pytest.raises(SpliceBreakRowError):
            check_splice(
                rows, indicator_id="x", methodology_break_ids=[], breaks={}
            )

    def test_seam_covered_by_a_break_at_the_seam_year_passes(self):
        rows = [_obs("kerala", 2014, _SRC_A), _obs("kerala", 2015, _SRC_B)]
        breaks = {"mv-seam": MethodologyBreak(methodology_version="mv-seam", at_year=2015)}
        assert check_splice(
            rows, indicator_id="x", methodology_break_ids=["mv-seam"], breaks=breaks
        ) == (2015,)

    def test_break_at_wrong_year_does_not_cover_the_seam(self):
        rows = [_obs("kerala", 2014, _SRC_A), _obs("kerala", 2015, _SRC_B)]
        breaks = {"mv-seam": MethodologyBreak(methodology_version="mv-seam", at_year=2012)}
        with pytest.raises(SpliceBreakRowError):
            check_splice(
                rows, indicator_id="x", methodology_break_ids=["mv-seam"], breaks=breaks
            )

    def test_dangling_fk_does_not_cover_the_seam(self):
        rows = [_obs("kerala", 2014, _SRC_A), _obs("kerala", 2015, _SRC_B)]
        # The indicator declares a break id, but it resolves to nothing.
        with pytest.raises(SpliceBreakRowError):
            check_splice(
                rows, indicator_id="x", methodology_break_ids=["mv-missing"], breaks={}
            )


# --------------------------------------------------------------------------- #
# THE SPLICE ORACLE (publish-seam composite): refuse -> break -> publish
# --------------------------------------------------------------------------- #


def _seed_source_a(repo_root: Path, indicator_id: str, years: range) -> None:
    path = repo_root / "datasets" / "data" / "datapoints" / "geo" / f"{indicator_id}.csv"
    write_csv(
        path=path,
        file_class=_GEO_FILE_CLASS,
        rows=[
            {"entity_id": "kerala", "time": t, "value": float(t), "source_id": _SRC_A}
            for t in years
        ],
    )


def _continuation_batch(indicator_id: str, years: range) -> CanonicalBatch:
    return CanonicalBatch(
        indicator_id=indicator_id,
        observation_rows=[_obs("kerala", t, _SRC_B, value=float(t)) for t in years],
    )


class TestSpliceOracle:
    def test_refuses_until_break_then_publishes_one_series_source_ids_intact(self, tmp_path):
        indicator_id = "test-spliced-series-mw"
        _seed_source_a(tmp_path, indicator_id, range(2010, 2015))  # 2010-2014 src A
        batch = _continuation_batch(indicator_id, range(2015, 2020))  # 2015-2019 src B

        # (1) REFUSE: a mid-series source change with no covering break.
        with pytest.raises(SpliceBreakRowError):
            apply_publish_gates(
                batch, repo_root=tmp_path, methodology_break_ids=None, breaks=None
            )

        # (2) Author a methodology_breaks row at the seam year + declare its FK.
        decision = apply_publish_gates(
            batch,
            repo_root=tmp_path,
            methodology_break_ids=["mv-seam-2015"],
            breaks=[{"methodology_version": "mv-seam-2015", "at_year": 2015}],
        )
        assert decision.seam_years == (2015,)

        # (3) Publish ONE series; each row keeps the source_id that supplied it.
        out = tmp_path / "datasets" / "data" / "datapoints" / "geo" / f"{indicator_id}.csv"
        write_csv(
            path=out,
            file_class=_GEO_FILE_CLASS,
            rows=[r.model_dump() for r in decision.rows],
        )
        by_year = {}
        import csv as _csv

        with out.open(encoding="utf-8", newline="") as fh:
            for row in _csv.DictReader(fh):
                by_year[int(row["time"])] = row["source_id"]
        assert by_year[2014] == _SRC_A
        assert by_year[2015] == _SRC_B
        assert all(by_year[y] == _SRC_A for y in range(2010, 2015))
        assert all(by_year[y] == _SRC_B for y in range(2015, 2020))


# --------------------------------------------------------------------------- #
# orchestrator wiring: the PUBLISH-seam provenance gate refuses an unmarked splice
# --------------------------------------------------------------------------- #


class _SpliceAdapter:
    """A driven adapter that emits a single-entity series spanning two sources."""

    adapter_slug = "splice-src"

    def __init__(self, indicator_id: str) -> None:
        self._indicator_id = indicator_id

    def source_specs(self) -> tuple[SourceSpec, ...]:
        return (
            SourceSpec(
                adapter_slug="splice-src",
                producer="Splice Producer",
                title="Splice Title",
                vintage="2026",
                url=None,
                indicators=(
                    IndicatorSpec(
                        indicator_id=self._indicator_id,
                        unit="mw",
                        normalisation="absolute",
                    ),
                ),
            ),
        )

    def run_indicator(self, indicator_id, *, repo_root, config) -> AdapterRunResult:
        path = (
            repo_root / "datasets" / "data" / "datapoints" / "geo" / f"{indicator_id}.csv"
        )
        rows = [
            {"entity_id": "kerala", "time": t, "value": float(t), "source_id": _SRC_A}
            for t in range(2010, 2015)
        ] + [
            {"entity_id": "kerala", "time": t, "value": float(t), "source_id": _SRC_B}
            for t in range(2015, 2020)
        ]
        write_csv(path=path, file_class=_GEO_FILE_CLASS, rows=rows)
        return summarise_indicator_csv(repo_root, indicator_id, adapter_slug="splice-src")


def _splice_catalogue(*, with_break_id: bool) -> tuple[list[dict], list[dict]]:
    indicator = {"indicator_id": "spliced-capacity-mw", "concept_id": "cap"}
    if with_break_id:
        indicator["methodology_break_ids"] = ["mv-seam-2015"]
    concepts = [{"concept_id": "cap", "unit_canonical": "mw", "normalisation": "absolute"}]
    return [indicator], concepts


class TestOrchestratorSpliceWiring:
    def test_orchestrate_refuses_an_unmarked_splice(self, tmp_path):
        indicator_id = "spliced-capacity-mw"
        indicators, concepts = _splice_catalogue(with_break_id=False)
        with pytest.raises(SpliceBreakRowError):
            orchestrate(
                indicator=indicator_id,
                repo_root=tmp_path,
                config=OrchestrateConfig(),
                registry={"splice-src": _SpliceAdapter(indicator_id)},
                indicators=indicators,
                concepts=concepts,
            )

    def test_orchestrate_publishes_when_the_seam_is_covered(self, tmp_path):
        indicator_id = "spliced-capacity-mw"
        indicators, concepts = _splice_catalogue(with_break_id=True)
        result = orchestrate(
            indicator=indicator_id,
            repo_root=tmp_path,
            config=OrchestrateConfig(),
            registry={"splice-src": _SpliceAdapter(indicator_id)},
            indicators=indicators,
            concepts=concepts,
            methodology_breaks=[{"methodology_version": "mv-seam-2015", "at_year": 2015}],
        )
        assert result.results[0].indicator_id == indicator_id
        # status surfaces the splice provenance the gate verified.
        status = compute_status(
            indicator=indicator_id,
            repo_root=tmp_path,
            registry={"splice-src": _SpliceAdapter(indicator_id)},
        )
        assert status.is_spliced
        assert status.seam_years == (2015,)
        assert {c.source_id for c in status.coverage} == {_SRC_A, _SRC_B}
