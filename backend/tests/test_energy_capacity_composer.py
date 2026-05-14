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


def test_every_row_has_facet_set(composed):
    for r in composed["rows"]:
        assert r.get("facet") is not None
        assert r["facet"] in {*LEAF_INPUTS.keys(), OTHER_THERMAL_FACET}


def test_facets_are_the_expected_six(composed):
    facets = {r["facet"] for r in composed["rows"]}
    assert facets <= {*LEAF_INPUTS.keys(), OTHER_THERMAL_FACET}
    assert "coal" in facets and "gas" in facets and "renewable" in facets


def test_sources_are_unioned_and_deduped(composed):
    seen = set()
    for s in composed["sources"]:
        key = (s["url"], s["fetched_at"])
        assert key not in seen, f"duplicate source entry: {key}"
        seen.add(key)
    assert len(seen) >= 1


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
