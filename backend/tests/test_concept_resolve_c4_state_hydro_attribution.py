"""Tier-A pins for PR-Z3bconcept-resolve cluster 4 (state-grain hydro-MW attribution).

Mirror of cluster 3 (state gas). The 3 state-grain
``state-installed-capacity-{geographical,allocated,snapshot}-mw-hydro`` rows
previously all FK'd to the single ``hydro-mw-absolute`` concept, tripping
``tier_b_one_indicator_per_concept`` on the ``(hydro-mw-absolute, ['state'])``
cluster. Per guardrail #13 (Hans identity rule: identity is what is MEASURED),
the three attribution methods (physical siting / beneficiary allocation /
CEA-monthly snapshot) are distinct measures, so each gets its own concept_id.

After this PR, ``hydro-mw-absolute`` is country-grain only (CEA national snapshot).

These pins guard against accidental remap back to the shared concept.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDICATORS = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"
CONCEPTS = REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"


def _rows() -> list[dict]:
    return json.loads(INDICATORS.read_text(encoding="utf-8"))["indicators"]


def _concepts() -> list[dict]:
    return json.loads(CONCEPTS.read_text(encoding="utf-8"))["concepts"]


def _concept_ids() -> set[str]:
    return {c["concept_id"] for c in _concepts()}


def test_state_hydro_geographical_uses_geographical_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "installed-capacity-geographical-mw-hydro")
    assert row["concept_id"] == "hydro-mw-geographical"


def test_state_hydro_allocated_uses_allocated_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "state-installed-capacity-allocated-mw-hydro")
    assert row["concept_id"] == "hydro-mw-allocated"


def test_state_hydro_snapshot_uses_snapshot_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "state-installed-capacity-snapshot-mw-hydro")
    assert row["concept_id"] == "hydro-mw-snapshot"


def test_state_hydro_attribution_concepts_exist():
    cids = _concept_ids()
    for cid in ("hydro-mw-geographical", "hydro-mw-allocated", "hydro-mw-snapshot"):
        assert cid in cids


def test_hydro_mw_absolute_now_country_grain_only():
    """After PR-Z3bconcept-resolve cluster 4, hydro-mw-absolute is country-only;
    the three state-grain rows moved to their own attribution concepts."""
    concept = next(c for c in _concepts() if c["concept_id"] == "hydro-mw-absolute")
    assert concept["entity_kinds"] == ["country"]
    state_fks = [
        r["indicator_id"]
        for r in _rows()
        if r.get("concept_id") == "hydro-mw-absolute" and r.get("entity_kinds") == ["state"]
    ]
    assert state_fks == [], (
        f"hydro-mw-absolute should have no state-grain FK after cluster 4; got: {state_fks}"
    )
