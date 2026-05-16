"""Phase 3 backfill: populate v1.5 governance fields on the 5 highest-leverage artifacts.

Per TODO/PER-INDICATOR-DOCS-PLAN.md §"Backfill order (highest-leverage first)":

1. fiscal/state_pension_expenditure_inr_crore — revision_tier_by_period + excludes
2. fiscal/outstanding_debt_pct_gsdp           — denominator (object) + excludes
3. prices/national_wpi_all_commodities_index_annual — renderer_rules
4. economy/state_per_capita_nsdp_constant_2011_12_inr — denominator (object)
5. economy/state_per_capita_nsdp_current_inr  — denominator (object)

Plus the long-form siblings (constant_inr_long, current_inr_long) for parity.

Idempotent: skips an artifact whose target field is already populated (only
fills nulls / absent keys; never overwrites). Run as:

    python tools/backfill_v15_governance.py

Validate after:

    python -m yen_gov validate --root .
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDICATORS_DIR = ROOT / "datasets" / "indicators" / "in"

# Insertion order for the indicator block — keeps the JSON readable and
# matches the schema's logical grouping (identity → semantics → governance).
# Any key not in this list keeps its original position.
INDICATOR_KEY_ORDER = [
    "id", "title", "description", "scale", "scale_hint", "unit",
    "denominator", "notes", "icon",
    "attribution_geography", "comparability", "funding_split",
    "implementing_authority", "methodology_vintage",
    "chart_type", "default_mode", "facet_labels",
    "revision_tier_by_period", "excludes", "renderer_rules",
    "series_breaks",
    "value_kind", "time_grain", "entity_kind", "facets", "direction",
]


def reorder(ind: dict) -> "OrderedDict[str, object]":
    """Re-key the indicator dict in our canonical order; unknown keys appended."""
    known = [k for k in INDICATOR_KEY_ORDER if k in ind]
    extra = [k for k in ind if k not in INDICATOR_KEY_ORDER]
    return OrderedDict((k, ind[k]) for k in known + extra)


def patch_pension(doc: dict) -> bool:
    ind = doc["indicator"]
    changed = False
    if not ind.get("revision_tier_by_period"):
        # RBI HBS-IS Table 171 publishes pensions under (A)/(RE)/(BE) suffixes;
        # the strip happens at parse time. The 2024-25 edition's vintage is
        # FY23 = Actual, FY24 = Revised Estimate, FY25 = Budget Estimate.
        ind["revision_tier_by_period"] = [
            {"from": "2022-04", "tier": "A",
             "note": "Actual (audited)"},
            {"from": "2023-04", "tier": "RE",
             "note": "Revised Estimate — will be revised to Actual in the next HBS-IS edition"},
            {"from": "2024-04", "tier": "BE",
             "note": "Budget Estimate — citizen should treat as plan, not outturn"},
        ]
        changed = True
    if not ind.get("excludes"):
        ind["excludes"] = [
            "IGNOAPS / IGNWPS social pensions excluded — these are central social-security transfers, not state-employer pensions",
            "NPS contribution flows excluded — captures only pre-NPS-hire defined-benefit retirement and family pensions",
            "State pension fund corpus contributions excluded — measures actual paid pensions, not actuarial accruals",
        ]
        changed = True
    return changed


def patch_debt(doc: dict) -> bool:
    ind = doc["indicator"]
    changed = False
    if ind.get("denominator") in (None, "", {}):
        ind["denominator"] = {
            "what": "GSDP at current prices",
            "price_basis": "current",
            "source_artifact": "economy/state_gdp_current_inr_lakh_crore",
            "note": "Each state's own MoSPI base year — sub-1pp YoY moves are inside the noise band",
        }
        changed = True
    if not ind.get("excludes"):
        ind["excludes"] = [
            "Off-budget borrowings excluded — captures consolidated debt as reported by RBI, not the wider 'extended debt' some states carry",
            "PSU debt excluded unless explicitly guaranteed by the state government",
        ]
        changed = True
    # Promote the deprecated comparability token to the v1.5 ladder.
    if ind.get("comparability") == "comparable_across_states":
        ind["comparability"] = "comparable_across_states_and_time"
        changed = True
    return changed


def patch_wpi(doc: dict) -> bool:
    ind = doc["indicator"]
    changed = False
    if not ind.get("renderer_rules"):
        ind["renderer_rules"] = ["no_growth_across_break"]
        changed = True
    # Promote deprecated comparability token.
    if ind.get("comparability") == "comparable_with_normalisation":
        # 5 base splices spanning 51 years — direction-of-change only.
        ind["comparability"] = "directional_only"
        changed = True
    return changed


def patch_per_capita_nsdp(doc: dict, *, basis: str, base_year: str | None) -> bool:
    """Add population denominator to a per-capita NSDP indicator.

    `basis` is "current" or "constant"; `base_year` is the MoSPI base for
    constant series (e.g. "2011-12"), or None for current-prices.
    """
    ind = doc["indicator"]
    changed = False
    if ind.get("denominator") in (None, "", {}):
        denom: dict[str, str] = {
            "what": "state mid-year population (MoSPI / RGI)",
            "price_basis": basis,
            "source_artifact": "demography/state_population_lakhs",
            "note": "Per-capita = NSDP ÷ state mid-year population estimate",
        }
        if base_year:
            denom["base_year"] = base_year
        ind["denominator"] = denom
        changed = True
    if ind.get("comparability") == "comparable_across_states":
        # Per-capita NSDP IS comparable across states AND through time within
        # a single base; promote to the v1.5 ladder accordingly.
        ind["comparability"] = "comparable_across_states_and_time"
        changed = True
    return changed


PATCHES: list[tuple[str, callable]] = [
    ("fiscal/state_pension_expenditure_inr_crore.json",
     patch_pension),
    ("fiscal/outstanding_debt_pct_gsdp.json",
     patch_debt),
    ("prices/national_wpi_all_commodities_index_annual.json",
     patch_wpi),
    ("economy/state_per_capita_nsdp_constant_2011_12_inr.json",
     lambda d: patch_per_capita_nsdp(d, basis="constant", base_year="2011-12")),
    ("economy/state_per_capita_nsdp_constant_inr_long.json",
     lambda d: patch_per_capita_nsdp(d, basis="constant", base_year=None)),
    ("economy/state_per_capita_nsdp_current_inr.json",
     lambda d: patch_per_capita_nsdp(d, basis="current", base_year=None)),
    ("economy/state_per_capita_nsdp_current_inr_long.json",
     lambda d: patch_per_capita_nsdp(d, basis="current", base_year=None)),
]


def main() -> int:
    touched = 0
    skipped = 0
    for rel, patch in PATCHES:
        path = INDICATORS_DIR / rel
        if not path.is_file():
            print(f"  MISS  {rel} (not found)")
            continue
        with path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
        before = json.dumps(doc, sort_keys=True)
        if patch(doc):
            doc["indicator"] = reorder(doc["indicator"])
        after = json.dumps(doc, sort_keys=True)
        if before == after:
            print(f"  skip  {rel}")
            skipped += 1
            continue
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"  ok    {rel}")
        touched += 1
    print(f"backfilled {touched} / {len(PATCHES)} artifact(s); {skipped} already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
