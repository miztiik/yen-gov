"""Schema + backfill assertions for indicator-catalogue.schema.json v2.1
(PR-Z3b-tail-actionC update_period_days backfill).

Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #18: every current indicator MUST declare ``update_period_days``
(publisher refresh cadence in days). v2.1 schema bump is ADDITIVE
(optional integer field, minimum=1); catalogue rows are backfilled via
cadence-derivation so the DARK
``tier_b_indicator_freshness_declared`` check can be chained live in a
follow-up PR without staging churn.

Walks the REAL ``datasets/taxonomy/indicators.json`` -- this is a Tier-A
contract test on the canonical artifact, not a tmp_path Tier-B check.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.core.schema_registry import schema_version


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


def test_catalogue_schema_version_is_current():
    assert _catalogue()["$schema_version"] == schema_version("indicator-catalogue.schema.json")


def test_all_current_rows_carry_positive_update_period_days():
    inds = _catalogue()["indicators"]
    missing = [r["indicator_id"] for r in inds if "update_period_days" not in r]
    assert missing == [], f"rows missing update_period_days: {missing}"
    non_positive = [
        r["indicator_id"]
        for r in inds
        if not isinstance(r["update_period_days"], int)
        or r["update_period_days"] < 1
    ]
    assert non_positive == [], f"rows with non-positive value: {non_positive}"


def test_named_cadence_rows_match_canonical_period():
    """A NAMED-cadence row's update_period_days must equal its canonical
    period. ``ad_hoc`` is exempt: it is the irregular catch-all whose refresh
    period is operator-declared truth, not cadence-derivable.

    Elections are the canonical ad_hoc case and the reason the exemption
    must be permanent: they are NEVER on a fixed cycle. A government can
    collapse, an assembly can be dissolved early, or President's rule can
    force a poll years ahead of the nominal term. So an election indicator's
    update_period_days (e.g. the pc-* Lok Sabha rows carry 1825) is a NOMINAL
    upper-bound, never a staleness deadline -- no ``N-month / 2 * cadence``
    freshness check may ever be applied to an ad_hoc / election series.
    Presence + positivity for ad_hoc rows is covered by
    test_all_current_rows_carry_positive_update_period_days.

    The original v2.1 form pinned update_period_days as a pure function of
    cadence for EVERY bucket including ad_hoc. That froze a one-time backfill
    heuristic into a permanent invariant, making the field redundant and
    rejecting truthful real-world cadences. Do NOT re-add an ad_hoc entry to
    the map below.
    """
    derivable = {
        "annual_fy": 365,
        "annual_cy": 365,
        "quarterly_fy": 92,
        "quarterly_cy": 92,
        "monthly_fy": 30,
        "monthly_cy": 30,
        "weekly": 7,
        "daily": 1,
        "decennial": 3650,
    }
    drift = []
    for r in _catalogue()["indicators"]:
        if r["cadence"] == "ad_hoc":
            continue  # irregular; period is declared, not derived
        want = derivable[r["cadence"]]
        got = r["update_period_days"]
        if got != want:
            drift.append((r["indicator_id"], r["cadence"], want, got))
    assert drift == [], f"cadence-derivation drift: {drift}"
