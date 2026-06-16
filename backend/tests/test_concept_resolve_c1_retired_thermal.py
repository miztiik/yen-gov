"""Tier-A pins for PR-Z3bconcept-resolve cluster 1 (retired thermal capacity).

The 2 country-grain ``india-thermal-capacity-retired-mw-{coal,gas}`` rows
previously FK'd to the *installed-capacity* concepts (``coal-mw-absolute``
+ ``gas-absolute``), tripping ``tier_b_one_indicator_per_concept`` on
``(concept_id, entity_kinds=['country'])`` clusters. Per guardrail #13
(Hans identity rule: identity is what is MEASURED), retirements are a
FLOW measure distinct from the installed STOCK measure, so they get
their own concepts.

These pins guard against accidental remap back to the stock concepts.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDICATORS = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"
CONCEPTS = REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"


def _rows() -> list[dict]:
    return json.loads(INDICATORS.read_text(encoding="utf-8"))["indicators"]


def _concept_ids() -> set[str]:
    return {
        c["concept_id"]
        for c in json.loads(CONCEPTS.read_text(encoding="utf-8"))["concepts"]
    }


def test_retired_coal_indicator_uses_retired_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "india-thermal-capacity-retired-mw-coal")
    assert row["concept_id"] == "coal-mw-retired"


def test_retired_gas_indicator_uses_retired_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "india-thermal-capacity-retired-mw-gas")
    assert row["concept_id"] == "gas-mw-retired"


def test_retired_thermal_concepts_exist():
    cids = _concept_ids()
    assert "coal-mw-retired" in cids
    assert "gas-mw-retired" in cids


def test_country_installed_capacity_stock_concepts_removed_by_facet_collapse():
    """geo-facet PR (TODO/20260616-geo-facet-dimension-column-plan.md): the
    per-fuel country-grain stock concepts (coal-mw-absolute, gas-absolute, ...)
    collapse into the faceted installed-capacity-mw measure (fuel_type is now a
    dimension column on geo_by_fuel/*.csv). The retired-FLOW concepts stay
    separate (distinct measure per the Hans identity rule #13)."""
    cids = _concept_ids()
    for removed in ("coal-mw-absolute", "gas-absolute"):
        assert removed not in cids, (
            f"{removed} should be removed by the facet collapse (fuel is now a "
            f"dimension on geo_by_fuel, not a per-fuel concept)"
        )
    for kept in ("coal-mw-retired", "gas-mw-retired"):
        assert kept in cids
    parent = next(r for r in _rows() if r["indicator_id"] == "installed-capacity-mw")
    assert parent["concept_id"] == "all-india-installed-capacity"
