"""Path-B migrate: collapse 4 country-grain Centre-transfer shards into 1 facetted shard.

PR-B7 (carved subset: row 3 only) of
TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md.

Sources (deleted on success), all `entity_kind=country` (all-India, 1 row per FY):
  - datasets/indicators/in/fiscal/centre_transfers_to_states_net.json
  - datasets/indicators/in/fiscal/centre_transfers_to_states_gross.json
  - datasets/indicators/in/fiscal/centre_transfers_to_states_tax_devolution.json
  - datasets/indicators/in/fiscal/centre_transfers_to_states_grants.json

Target:
  - datasets/indicators/in/fiscal/centre_transfers_inr_crore.json
    indicator.id = "fiscal/centre_transfers_inr_crore"
    rows[].facet in {"net", "gross", "tax_devolution", "grants"}
    indicator.facet_labels declares human-readable labels.

Standing-reference rows 1+2 (the 2 state-grain shards `fiscal/net_transfers_from_centre`
and `fiscal/centre_transfers_gross`) are NOT touched by this PR — they are written by
`backend/yen_gov/sources/rbi_xlsx/*.py` adapters which need a coordinated rename;
deferred to a follow-up PR-B7-tail.

STAY-SPLIT (Hans pin): `fiscal/states_combined_*_deficit` vs `fiscal/union_*_deficit`
are NOT collapsed — different fiscal entities, not different scopes of one fact.

Idempotent: if all source shards are gone and target exists, exit 0 noop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FISCAL_DIR = REPO_ROOT / "datasets" / "indicators" / "in" / "fiscal"

FACET_SOURCES: list[tuple[str, str, str]] = [
    # (facet_id, source_shard_basename, facet_label)
    ("net", "centre_transfers_to_states_net.json", "Net (after loan/interest claw-back)"),
    ("gross", "centre_transfers_to_states_gross.json", "Gross (envelope total)"),
    (
        "tax_devolution",
        "centre_transfers_to_states_tax_devolution.json",
        "Tax devolution (Finance Commission)",
    ),
    ("grants", "centre_transfers_to_states_grants.json", "Grants (discretionary + scheme)"),
]

TARGET_BASENAME = "centre_transfers_inr_crore.json"
TARGET_ID = "fiscal/centre_transfers_inr_crore"


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
    target = FISCAL_DIR / TARGET_BASENAME
    source_paths = [FISCAL_DIR / b for _, b, _ in FACET_SOURCES]
    existing_sources = [p for p in source_paths if p.exists()]

    if not existing_sources and target.exists():
        print(f"[path_b_fiscal] noop: target {target.name} already present, no source shards")
        return 0

    if not existing_sources:
        print("[path_b_fiscal] ERROR: no source shards and no target", file=sys.stderr)
        return 1

    missing = [p for p in source_paths if not p.exists()]
    if missing:
        print(
            f"[path_b_fiscal] ERROR: partial state, missing: {[p.name for p in missing]}",
            file=sys.stderr,
        )
        return 1

    shards = {facet_id: _load(FISCAL_DIR / basename) for facet_id, basename, _ in FACET_SOURCES}

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

    net = shards["net"]

    out = {
        "$schema": net["$schema"],
        "$schema_version": net["$schema_version"],
        "sources": merged_sources,
        "license": net["license"],
        "coverage": net["coverage"],
        "indicator": {
            "id": TARGET_ID,
            "title": "Centre-to-States transfers (all-India, by flow)",
            "description": (
                "All-India Centre-to-States fiscal transfers from RBI's State Finances "
                "Appendix Table 2, faceted by flow: Net (Item VI = Gross minus loan "
                "repayments and interest), Gross (Item IV = I+II+III, envelope total), "
                "Tax devolution (Item I, States' share of central tax pool under the "
                "Finance Commission formula), and Grants (Item II, discretionary + "
                "scheme + statutory grants). The four flows are NOT independent — Gross "
                "decomposes as Tax devolution + Grants + Loans; Net = Gross minus "
                "loan/interest claw-back. Pick a flow via the facet picker."
            ),
            "entity_kind": "country",
            "time_grain": "fiscal_year",
            "value_kind": "currency",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "INR (crore)",
            "short_unit": "\u20b9cr",
            "icon": "landmark",
            "attribution_geography": "where_administered",
            "comparability": "comparable_with_normalisation",
            "funding_split": {
                "centre_pct": 100,
                "state_pct": 0,
                "source": "definition (own vs centrally-transferred)",
            },
            "implementing_authority": "centre",
            "methodology_vintage": (
                "RBI State Finances: A Study of Budgets, Appendix Table 2 "
                "(Devolution and Transfer of Resources from the Centre); 2024-25 edition"
            ),
            "facet_labels": facet_labels,
            "notes": (
                "Values are in nominal \u20b9 Crore (1 Crore = 10 million); they are NOT "
                "inflation-adjusted. The latest two years are typically RE / BE only. "
                "From 2017-18 onwards the figures include Delhi and Puducherry. "
                "Collapsed from 4 sibling shards "
                "(centre_transfers_to_states_{net,gross,tax_devolution,grants}) by "
                "tools/migrate/path_b_fiscal.py per plan-doc PR-B7 (row 3). The two "
                "state-grain shards `fiscal/net_transfers_from_centre` and "
                "`fiscal/centre_transfers_gross` stay split (state-level series, written "
                "by separate adapters; folding requires a coordinated source-module "
                "rename, deferred to PR-B7-tail). STAY-SPLIT: "
                "`fiscal/states_combined_*_deficit` vs `fiscal/union_*_deficit` are NOT "
                "collapsed — different fiscal entities, not different scopes of one fact."
            ),
        },
        "rows": rows,
        "series_spec": {
            "description": (
                "All-India Centre-to-States transfers, faceted by flow. Pick a flow "
                "via the facet picker; the facet picker carries the citizen-readable "
                "label declared in indicator.facet_labels."
            )
        },
        "methodology": net.get("methodology", {}),
        "divergence": None,
    }

    with target.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[path_b_fiscal] wrote {target.relative_to(REPO_ROOT)} ({len(rows)} rows)")

    for p in source_paths:
        p.unlink()
        print(f"[path_b_fiscal] deleted {p.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
