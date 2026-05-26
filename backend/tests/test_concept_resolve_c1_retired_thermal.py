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


def test_country_installed_capacity_concepts_no_longer_have_retired_siblings():
    """The 2 country-grain installed-capacity concepts must not have any
    other indicator at entity_kinds=['country'] FK'd to them."""
    for stock_cid in ("coal-mw-absolute", "gas-absolute"):
        siblings = [
            r["indicator_id"]
            for r in _rows()
            if r.get("concept_id") == stock_cid and r.get("entity_kinds") == ["country"]
        ]
        assert len(siblings) == 1, (
            f"concept {stock_cid} at country-grain should have exactly 1 FK "
            f"after PR-Z3bconcept-resolve cluster 1; got: {siblings}"
        )
