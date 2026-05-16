"""Tests for the energy_capacity_by_source composer (per ADR-0024).

These run against the real on-disk fuel artifacts under
``datasets/indicators/in/energy/`` — not mocks (Holy Law #7). They
assert the canonical invariants the composer exists to enforce.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.composers.energy_capacity_by_source import (
    FACET_LABELS,
    INDICATOR_SCHEMA_FILENAME,
    LEAF_INPUTS,
    OTHER_THERMAL_FACET,
    OUTPUT_PATH_RELPATH,
    SUM_TOLERANCE_FRACTION,
    THERMAL_INPUT,
    TOTAL_INPUT,
    INPUT_DIR_RELPATH,
    _index_rows,
    _load_indicator,
    assert_sum_invariant,
    build_facetted_rows,
    compose,
)
from yen_gov.core.schema_registry import schema_version


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def composed() -> dict:
    out = compose(repo_root=REPO_ROOT)
    return json.loads(out.read_text(encoding="utf-8"))


def test_composer_writes_to_expected_path():
    out = compose(repo_root=REPO_ROOT)
    assert out == REPO_ROOT / OUTPUT_PATH_RELPATH
    assert out.exists()


def test_composed_artifact_has_correct_schema_stamp(composed):
    assert composed["$schema_version"] == schema_version(INDICATOR_SCHEMA_FILENAME)
    assert composed["$schema"].endswith("indicator.schema.json")


def test_composed_artifact_carries_render_hints(composed):
    ind = composed["indicator"]
    assert ind["chart_type"] == "stacked-trend"
    assert ind["default_mode"] == "percent"


def test_composed_artifact_emits_facet_labels(composed):
    # Schema 1.4 / Phase 4 C2: composer is the source-of-truth for facet
    # labels. The frontend reads these and falls back to humanise() only
    # when absent — so the keys must cover every facet that can appear in
    # rows[].facet.
    ind = composed["indicator"]
    labels = ind["facet_labels"]
    assert isinstance(labels, dict) and labels
    assert set(labels.keys()) == set(FACET_LABELS.keys())
    assert all(isinstance(v, str) and v for v in labels.values())
    # Spot-check the residual bucket — the historical bug-source the
    # hardcoded literal in TopicLanding.svelte used to paper over.
    assert labels[OTHER_THERMAL_FACET] == "Other thermal"


def test_every_row_has_facet_set(composed):
    for r in composed["rows"]:
        assert r.get("facet") is not None
        assert r["facet"] in {*LEAF_INPUTS.keys(), OTHER_THERMAL_FACET}


def test_facets_are_the_expected_six(composed):
    facets = {r["facet"] for r in composed["rows"]}
    assert facets <= {*LEAF_INPUTS.keys(), OTHER_THERMAL_FACET}
    assert "coal" in facets and "gas" in facets and "renewable" in facets


def test_sources_are_unioned_and_deduped(composed):
    """Sources are deduped by URL alone (not by (url, fetched_at)) and sorted.

    Dedup-by-URL is the canonical contract — see ``_union_sources`` docstring
    and CLAUDE.md \u00a710. A tuple key would smear ``fetched_at`` churn from
    upstream re-polls into the composed artifact, breaking byte-stability.
    """
    sources = composed["sources"]
    urls = [s["url"] for s in sources]
    assert len(urls) == len(set(urls)), f"duplicate URL in composed sources: {urls}"
    assert urls == sorted(urls), "composed sources must be sorted by URL for determinism"
    assert len(sources) >= 1


def test_sum_invariant_holds_on_real_data():
    in_dir = REPO_ROOT / INPUT_DIR_RELPATH
    leaf_indices = {
        facet: _index_rows(_load_indicator(in_dir / fname))
        for facet, fname in LEAF_INPUTS.items()
    }
    thermal_index = _index_rows(_load_indicator(in_dir / THERMAL_INPUT))
    total_index = _index_rows(_load_indicator(in_dir / TOTAL_INPUT))

    rows = build_facetted_rows(
        leaf_indices=leaf_indices,
        thermal_index=thermal_index,
        total_index=total_index,
    )
    errors = assert_sum_invariant(rows, total_index, tolerance=SUM_TOLERANCE_FRACTION)
    assert errors == [], f"sum invariant breaches: {errors}"


def test_assert_sum_invariant_flags_synthetic_breach():
    rows = [
        {"entity_id": "X", "time": "T", "value": 10, "facet": "coal"},
        {"entity_id": "X", "time": "T", "value": 10, "facet": "gas"},
    ]
    total_index = {("X", "T"): 100.0}
    errors = assert_sum_invariant(rows, total_index, tolerance=0.005)
    assert len(errors) == 1
    assert "X" in errors[0]


def test_other_thermal_dropped_when_residual_negligible():
    leaf = {
        "coal": {("X", "T"): 50.0},
        "gas": {("X", "T"): 50.0},
        "hydro": {},
        "nuclear": {},
        "renewable": {},
    }
    rows = build_facetted_rows(
        leaf_indices=leaf,
        thermal_index={("X", "T"): 100.0},
        total_index={("X", "T"): 100.0},
    )
    facets = {r["facet"] for r in rows}
    assert OTHER_THERMAL_FACET not in facets


def test_other_thermal_kept_when_residual_meaningful():
    leaf = {
        "coal": {("TN", "T"): 9000.0},
        "gas": {("TN", "T"): 1000.0},
        "hydro": {},
        "nuclear": {},
        "renewable": {},
    }
    rows = build_facetted_rows(
        leaf_indices=leaf,
        thermal_index={("TN", "T"): 12000.0},
        total_index={("TN", "T"): 12000.0},
    )
    other = [r for r in rows if r["facet"] == OTHER_THERMAL_FACET]
    assert len(other) == 1
    assert other[0]["value"] == pytest.approx(2000.0, rel=1e-6)


def test_union_sources_dedups_by_url_keeping_earliest_fetched_at():
    """Regression guard for the 2026-05-16 fetched_at-smear-one-layer-up bug.

    Two source entries sharing a URL but differing only in ``fetched_at``
    (the symptom of an upstream re-poll producing byte-identical bytes
    but a fresh wall-clock stamp before the composer-level fix) must
    collapse to ONE entry in the composed output, with ``fetched_at`` set
    to the earlier of the two. Otherwise every re-ingest of a fuel
    artifact churns this composed artifact's ``sources[]`` even when the
    upstream bytes are unchanged.

    Output must also be sorted by URL for deterministic byte-equal
    re-emits (no ordering-noise from set/dict iteration).
    """
    from yen_gov.composers.energy_capacity_by_source import _union_sources

    docs = [
        {
            "sources": [
                {"url": "https://example.gov.in/b.htm", "fetched_at": "2026-05-10T00:00:00Z"},
                {"url": "https://example.gov.in/a.htm", "fetched_at": "2026-05-15T00:00:00Z"},
            ]
        },
        {
            "sources": [
                # Same URL as above, later re-poll — must be discarded.
                {"url": "https://example.gov.in/a.htm", "fetched_at": "2026-05-16T00:00:00Z"},
                {"url": "https://example.gov.in/c.htm", "fetched_at": "2026-05-12T00:00:00Z"},
            ]
        },
    ]
    out = _union_sources(docs)
    urls = [s.url for s in out]
    assert urls == [
        "https://example.gov.in/a.htm",
        "https://example.gov.in/b.htm",
        "https://example.gov.in/c.htm",
    ]
    by_url = {s.url: s.fetched_at.isoformat() for s in out}
    # Earliest fetched_at wins for the re-polled URL.
    assert by_url["https://example.gov.in/a.htm"].startswith("2026-05-15")
