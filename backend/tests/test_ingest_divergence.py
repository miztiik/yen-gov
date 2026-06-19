"""Tests for the UPSERT-seam divergence gate (Row 6).

Covers the unit behaviour (tolerance source, same-source skip, null skip,
resolution escape) and the Row-6 divergence ORACLE driven through the
publish-seam composite: a >tolerance overlap-year disagreement fails loud; a
within-tolerance one publishes. tmp_path fixtures; no corpus walk.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.ingest.divergence import (
    DEFAULT_DIVERGENCE_TOLERANCE,
    DivergenceError,
    DivergenceResolution,
    check_divergence,
    concept_tolerance,
)
from yen_gov.canonical.ingest.messages import CanonicalBatch, CanonicalObservationRow
from yen_gov.canonical.ingest.orchestrator import apply_publish_gates

_GEO_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_SRC_A = "src-aaaaaaaaaaaa"
_SRC_B = "src-bbbbbbbbbbbb"


def _obs(entity_id: str, time: int, value: float | None, source_id: str) -> CanonicalObservationRow:
    return CanonicalObservationRow(
        entity_id=entity_id, time=time, value=value, source_id=source_id
    )


# --------------------------------------------------------------------------- #
# tolerance source (the Hans + Max ruling)
# --------------------------------------------------------------------------- #


class TestConceptTolerance:
    def test_default_when_concept_absent_or_silent(self):
        assert concept_tolerance(None) == DEFAULT_DIVERGENCE_TOLERANCE
        assert concept_tolerance({"concept_id": "x"}) == DEFAULT_DIVERGENCE_TOLERANCE

    def test_per_concept_override_is_honoured(self):
        assert concept_tolerance({"divergence_tolerance": 0.05}) == 0.05

    def test_negative_override_is_rejected(self):
        with pytest.raises(DivergenceError):
            concept_tolerance({"divergence_tolerance": -0.1})


# --------------------------------------------------------------------------- #
# unit behaviour
# --------------------------------------------------------------------------- #


class TestCheckDivergence:
    def test_over_tolerance_cross_source_fails(self):
        existing = [_obs("kerala", 2011, 20.0, _SRC_A)]
        incoming = [_obs("kerala", 2011, 24.0, _SRC_B)]  # +20% >> 1%
        with pytest.raises(DivergenceError):
            check_divergence(incoming, existing)

    def test_within_tolerance_passes(self):
        existing = [_obs("kerala", 2011, 20.0, _SRC_A)]
        incoming = [_obs("kerala", 2011, 20.1, _SRC_B)]  # +0.5% < 1%
        assert check_divergence(incoming, existing) == ()

    def test_same_source_revision_is_not_a_divergence(self):
        existing = [_obs("kerala", 2011, 20.0, _SRC_A)]
        incoming = [_obs("kerala", 2011, 99.0, _SRC_A)]  # same source revising itself
        assert check_divergence(incoming, existing) == ()

    def test_null_carries_no_claim(self):
        existing = [_obs("kerala", 2011, 20.0, _SRC_A)]
        incoming = [_obs("kerala", 2011, None, _SRC_B)]
        assert check_divergence(incoming, existing) == ()

    def test_brand_new_cell_has_no_incumbent(self):
        existing = [_obs("kerala", 2010, 20.0, _SRC_A)]
        incoming = [_obs("kerala", 2011, 9999.0, _SRC_B)]  # different cell
        assert check_divergence(incoming, existing) == ()

    def test_recorded_resolution_permits_and_returns_the_audit_row(self):
        existing = [_obs("kerala", 2011, 20.0, _SRC_A)]
        incoming = [_obs("kerala", 2011, 24.0, _SRC_B)]
        resolution = DivergenceResolution(
            entity_id="kerala",
            time=2011,
            winning_source_id=_SRC_B,
            reason="SRS supersedes the older Census estimate per the precedence rule",
        )
        applied = check_divergence(incoming, existing, resolutions=[resolution])
        assert applied == (resolution,)

    def test_override_tolerance_widens_the_band(self):
        existing = [_obs("kerala", 2011, 20.0, _SRC_A)]
        incoming = [_obs("kerala", 2011, 20.3, _SRC_B)]  # +1.5%: fails at 1%
        with pytest.raises(DivergenceError):
            check_divergence(incoming, existing)
        # ...but passes when the concept declares a 2% tolerance.
        assert check_divergence(
            incoming, existing, concept={"divergence_tolerance": 0.02}
        ) == ()


# --------------------------------------------------------------------------- #
# THE DIVERGENCE ORACLE (through the publish-seam composite)
# --------------------------------------------------------------------------- #


def _seed_source_a(repo_root: Path, indicator_id: str, cells: dict[int, float]) -> None:
    path = repo_root / "datasets" / "data" / "datapoints" / "geo" / f"{indicator_id}.csv"
    write_csv(
        path=path,
        file_class=_GEO_FILE_CLASS,
        rows=[
            {"entity_id": "kerala", "time": t, "value": v, "source_id": _SRC_A}
            for t, v in cells.items()
        ],
    )


class TestDivergenceOracle:
    def test_over_tolerance_overlap_year_fails_loud(self, tmp_path):
        indicator_id = "test-divergence-metric"
        _seed_source_a(tmp_path, indicator_id, {2010: 10.0, 2011: 20.0, 2012: 30.0})
        batch = CanonicalBatch(
            indicator_id=indicator_id,
            observation_rows=[
                _obs("kerala", 2010, 10.05, _SRC_B),  # +0.5% ok
                _obs("kerala", 2011, 24.0, _SRC_B),  # +20% FAILS
                _obs("kerala", 2012, 30.1, _SRC_B),  # +0.33% ok
            ],
        )
        with pytest.raises(DivergenceError):
            apply_publish_gates(batch, repo_root=tmp_path)

    def test_within_tolerance_overlap_publishes(self, tmp_path):
        indicator_id = "test-divergence-metric"
        _seed_source_a(tmp_path, indicator_id, {2010: 10.0, 2011: 20.0, 2012: 30.0})
        batch = CanonicalBatch(
            indicator_id=indicator_id,
            observation_rows=[
                _obs("kerala", 2010, 10.05, _SRC_B),
                _obs("kerala", 2011, 20.1, _SRC_B),
                _obs("kerala", 2012, 30.1, _SRC_B),
            ],
        )
        decision = apply_publish_gates(batch, repo_root=tmp_path)
        # All cells collapse to source B (a full overwrite within tolerance), so
        # there is no seam and one clean series remains.
        assert decision.seam_years == ()
        assert {r.source_id for r in decision.rows} == {_SRC_B}
