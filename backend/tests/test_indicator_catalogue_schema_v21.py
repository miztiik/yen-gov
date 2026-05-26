"""Schema + backfill assertions for indicator-catalogue.schema.json v2.1
(PR-Z3b-tail-actionC update_period_days backfill).

Per TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #18: every indicator MUST declare ``update_period_days``
(publisher refresh cadence in days). v2.1 schema bump is ADDITIVE
(optional integer field, minimum=1); all 183 existing rows are
backfilled in the same commit via cadence-derivation so the DARK
``tier_b_indicator_freshness_declared`` check can be chained live in a
follow-up PR without staging churn.

Walks the REAL ``datasets/taxonomy/indicators.json`` -- this is a Tier-A
contract test on the canonical artifact, not a tmp_path Tier-B check.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "indicator-catalogue.schema.json"
CATALOGUE_PATH = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _catalogue() -> dict:
    return json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))


def test_schema_declares_update_period_days_property():
    props = _schema()["properties"]["indicators"]["items"]["properties"]
    upd = props["update_period_days"]
    assert upd["type"] == "integer"
    assert upd["minimum"] == 1


def test_update_period_days_is_optional_in_required_list():
    required = _schema()["properties"]["indicators"]["items"]["required"]
    assert "update_period_days" not in required, (
        "v2.1 field is optional during v2.0->v2.1 transition; "
        "intent-required is enforced via Tier-B "
        "tier_b_indicator_freshness_declared once chained live."
    )


def test_catalogue_schema_version_is_2_1():
    assert _catalogue()["$schema_version"] == "2.1"


def test_all_183_rows_carry_positive_update_period_days():
    inds = _catalogue()["indicators"]
    assert len(inds) == 183
    missing = [r["indicator_id"] for r in inds if "update_period_days" not in r]
    assert missing == [], f"rows missing update_period_days: {missing}"
    non_positive = [
        r["indicator_id"]
        for r in inds
        if not isinstance(r["update_period_days"], int)
        or r["update_period_days"] < 1
    ]
    assert non_positive == [], f"rows with non-positive value: {non_positive}"


def test_cadence_derived_values_match_carve_out_mapping():
    """Each row's update_period_days must be the canonical cadence-derived
    value documented in the v2.1 changelog (annual_fy=365, monthly_cy=30,
    ad_hoc=365 default annual review).
    """
    expected = {
        "annual_fy": 365,
        "annual_cy": 365,
        "quarterly_fy": 92,
        "quarterly_cy": 92,
        "monthly_fy": 30,
        "monthly_cy": 30,
        "weekly": 7,
        "daily": 1,
        "decennial": 3650,
        "ad_hoc": 365,
    }
    drift = []
    for r in _catalogue()["indicators"]:
        want = expected[r["cadence"]]
        got = r["update_period_days"]
        if got != want:
            drift.append((r["indicator_id"], r["cadence"], want, got))
    assert drift == [], f"cadence-derivation drift: {drift}"
