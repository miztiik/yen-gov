"""Path-B migrate: collapse 4 state CPI inflation shards into 1 facetted shard.

PR-B8 of docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md.

Sources (deleted on success):
  - datasets/indicators/in/prices/state_cpi_general_inflation_pct.json
  - datasets/indicators/in/prices/state_cpi_food_inflation_pct.json
  - datasets/indicators/in/prices/state_cpi_fuel_inflation_pct.json
  - datasets/indicators/in/prices/state_cpi_housing_urban_inflation_pct.json

Target:
  - datasets/indicators/in/prices/cpi_inflation_pct.json
    indicator.id = "prices/cpi_inflation_pct"
    rows[].facet in {"general", "food", "fuel", "housing_urban"}
    indicator.facet_labels declares human-readable labels.

CPI vs WPI vs CPI-IW stay split (different baskets / publishers); only the
4 state-CPI sub-baskets collapse per plan-doc standing-reference row 13.

Idempotent: if all source shards are gone and target exists, exit 0 noop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRICES_DIR = REPO_ROOT / "datasets" / "indicators" / "in" / "prices"

FACET_SOURCES: list[tuple[str, str, str]] = [
    # (facet_id, source_shard_basename, facet_label)
    ("general", "state_cpi_general_inflation_pct.json", "General"),
    ("food", "state_cpi_food_inflation_pct.json", "Food and Beverages"),
    ("fuel", "state_cpi_fuel_inflation_pct.json", "Fuel and Light"),
    ("housing_urban", "state_cpi_housing_urban_inflation_pct.json", "Housing (Urban)"),
]

TARGET_BASENAME = "cpi_inflation_pct.json"
TARGET_ID = "prices/cpi_inflation_pct"


def _load(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dedup_sources(seq: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for s in seq:
        key = s.get("url", "") + "|" + s.get("name", "")
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def main() -> int:
    target = PRICES_DIR / TARGET_BASENAME
    source_paths = [PRICES_DIR / b for _, b, _ in FACET_SOURCES]
    existing_sources = [p for p in source_paths if p.exists()]

    if not existing_sources and target.exists():
        print(f"[path_b_prices] noop: target {target.name} already present, no source shards")
        return 0

    if not existing_sources:
        print(f"[path_b_prices] ERROR: no source shards and no target", file=sys.stderr)
        return 1

    missing = [p for p in source_paths if not p.exists()]
    if missing:
        print(
            f"[path_b_prices] ERROR: partial state, missing: {[p.name for p in missing]}",
            file=sys.stderr,
        )
        return 1

    shards = {facet_id: _load(PRICES_DIR / basename) for facet_id, basename, _ in FACET_SOURCES}

    merged_sources: list[dict] = []
    for facet_id, _, _ in FACET_SOURCES:
        merged_sources.extend(shards[facet_id]["sources"])
    merged_sources = _dedup_sources(merged_sources)

    facet_labels = {facet_id: label for facet_id, _, label in FACET_SOURCES}

    rows: list[dict] = []
    for facet_id, _, _ in FACET_SOURCES:
        for r in shards[facet_id]["rows"]:
            new_row = {
                "entity_id": r["entity_id"],
                "time": r["time"],
                "value": r["value"],
                "facet": facet_id,
            }
            rows.append(new_row)

    general = shards["general"]
    methodology = dict(general["methodology"])
    methodology["definition"] = (
        "State-wise CPI inflation, faceted by sub-basket: General (headline), "
        "Food and Beverages, Fuel and Light, Housing (Urban-only). Annual average "
        "of monthly YoY %, fiscal year. Source: RBI Handbook of Statistics on "
        "Indian States 2024-25 — Tables 108 (General), 109 (Food), 110 (Fuel), "
        "111 (Housing Urban). RBI publishes already as YoY % inflation so no "
        "computation is applied. Housing is urban-only because NSO does not "
        "publish a rural housing CPI sub-index (rural housing in CPI methodology "
        "is imputed differently)."
    )
    methodology["notes"] = []

    out = {
        "$schema": general["$schema"],
        "$schema_version": general["$schema_version"],
        "sources": merged_sources,
        "license": general["license"],
        "coverage": general["coverage"],
        "indicator": {
            "id": TARGET_ID,
            "title": "State-wise CPI inflation (by sub-basket)",
            "description": (
                "State-wise CPI year-on-year inflation, faceted by sub-basket: "
                "General (headline), Food and Beverages, Fuel and Light, and Housing "
                "(urban-only). Citizens experience inflation as a sub-basket mix, "
                "not as a single number — food drives household cash-pressure, fuel "
                "tracks SERC tariff orders and LPG policy, housing is mostly urban "
                "rent revisions. State variation reflects commodity weights and "
                "local price formation, not state-government policy (monetary policy "
                "is set centrally by the RBI under a Union List mandate)."
            ),
            "description_short": (
                "State CPI year-on-year inflation %, by sub-basket (General / Food / "
                "Fuel / Housing-Urban). The cost-of-living signal a household actually "
                "feels — pick a sub-basket via the facet picker."
            ),
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": "rate",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "% YoY",
            "short_unit": "% YoY",
            "icon": "trending-up",
            "attribution_geography": "where_resident",
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "centre",
            "methodology_vintage": "RBI Handbook 2024-25 edition",
            "facet_labels": facet_labels,
            "notes": (
                "Source: RBI Handbook of Statistics on Indian States 2024-25, "
                "Tables 108-111. Collapsed from 4 sibling shards "
                "(state_cpi_{general,food,fuel,housing_urban}_inflation_pct) by "
                "tools/migrate/path_b_prices.py per plan-doc PR-B8. CPI vs WPI vs "
                "CPI-IW stay split (different baskets / publishers)."
            ),
        },
        "rows": rows,
        "series_spec": {
            "description": (
                "State-wise CPI YoY inflation faceted by sub-basket. Pick a sub-basket "
                "via the facet picker; the facet picker carries the citizen-readable "
                "label declared in indicator.facet_labels."
            )
        },
        "methodology": methodology,
        "divergence": None,
    }

    with target.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[path_b_prices] wrote {target.relative_to(REPO_ROOT)} ({len(rows)} rows)")

    for p in source_paths:
        p.unlink()
        print(f"[path_b_prices] deleted {p.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
