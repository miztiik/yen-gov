"""Composer: installed capacity by source (facetted).

Reads the per-fuel CEA Installed Capacity artifacts emitted by
``yen_gov.sources.cea_installed_capacity`` and emits ONE facetted
indicator at ``datasets/indicators/in/energy/installed_capacity_by_source_mw.json``.

Per ADR-0024 (backend Aggregator, not frontend adapter): the energy-mix
StackedTrend reads one file. The composer is the single, tested place
where N CEA leaves are joined into one canonical view.

CEA shape (reconciled in ADR-0024 §"Reconciliation with the actual CEA
per-fuel files"):

  Leaf inputs:        coal, gas, hydro, nuclear, renewable
  Umbrella inputs:    thermal (= coal + lignite + gas + diesel),
                      total   (grand total)
  Derived facet:      other_thermal = thermal - coal - gas
                      (the lignite + diesel residual; collapsed into
                      a state-level "other" when below the floor.)

Composed facets emitted:  coal, gas, nuclear, hydro, renewable, other_thermal
Excluded from stack:      thermal (parent rollup), total (cross-check only)

Invariant validated in pytest:
  for every (entity_id, time):  abs(sum(leaf facets) - total) <= 0.5% * total

The composer is a pure function from filesystem state to filesystem
state; no network, no environment overrides. Re-running it is
idempotent — the output bytes are stable for a given input set.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version

# ---------------------------------------------------------------------------
# Constants — per the ADR-0024 reconciliation
# ---------------------------------------------------------------------------

LEAF_INPUTS: dict[str, str] = {
    # facet_id -> input file basename (under datasets/indicators/in/energy/)
    "coal":      "installed_capacity_coal_mw.json",
    "gas":       "installed_capacity_gas_mw.json",
    "hydro":     "installed_capacity_hydro_mw.json",
    "nuclear":   "installed_capacity_nuclear_mw.json",
    "renewable": "installed_capacity_renewable_mw.json",
}
THERMAL_INPUT = "installed_capacity_thermal_mw.json"
TOTAL_INPUT = "installed_capacity_total_mw.json"

OTHER_THERMAL_FACET = "other_thermal"
OUTPUT_BASENAME = "installed_capacity_by_source_mw.json"

# Citizen-facing labels for each facet value (indicator schema 1.4 — lifted
# out of the frontend topic page so the renderer is data-driven). Keep keys
# in sync with LEAF_INPUTS + OTHER_THERMAL_FACET.
FACET_LABELS: dict[str, str] = {
    "coal":          "Coal",
    "gas":           "Gas",
    "hydro":         "Hydro",
    "nuclear":       "Nuclear",
    "renewable":     "Renewable",
    OTHER_THERMAL_FACET: "Other thermal",
}

INPUT_DIR_RELPATH = "datasets/indicators/in/energy"
OUTPUT_PATH_RELPATH = f"{INPUT_DIR_RELPATH}/{OUTPUT_BASENAME}"

# Tolerance used by pytest to assert sum(leaves) ~= total
SUM_TOLERANCE_FRACTION = 0.005  # 0.5%

# Below this fraction, other_thermal is dropped (treated as numerical noise)
MIN_OTHER_THERMAL_FRACTION = 0.001  # 0.1%

# Schema metadata is sourced via core.schema_registry (single source of truth
# per CLAUDE.md §11). Do NOT hand-type SCHEMA_VERSION / SCHEMA_ID here —
# bump the schema file's `x-version` and this composer picks it up for free.
INDICATOR_SCHEMA_FILENAME = "indicator.schema.json"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _load_indicator(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"composer input missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _index_rows(doc: dict[str, Any]) -> dict[tuple[str, str], float]:
    """Return ``{(entity_id, time): value}`` for present numeric rows."""
    out: dict[tuple[str, str], float] = {}
    for row in doc.get("rows", []):
        v = row.get("value")
        if v is None:
            continue
        out[(row["entity_id"], row["time"])] = float(v)
    return out


def _union_keys(*indices: dict[tuple[str, str], float]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for idx in indices:
        seen.update(idx.keys())
    return sorted(seen)


def _union_sources(docs: list[dict[str, Any]]) -> list[Source]:
    """Union of input ``sources`` arrays, dedup on (url, fetched_at)."""
    seen: set[tuple[str, str]] = set()
    out: list[Source] = []
    for doc in docs:
        for s in doc.get("sources", []):
            key = (s["url"], s["fetched_at"])
            if key in seen:
                continue
            seen.add(key)
            out.append(
                Source(
                    url=s["url"],
                    fetched_at=datetime.fromisoformat(s["fetched_at"].replace("Z", "+00:00")),
                )
            )
    return out


def build_facetted_rows(
    *,
    leaf_indices: dict[str, dict[tuple[str, str], float]],
    thermal_index: dict[tuple[str, str], float],
    total_index: dict[tuple[str, str], float],
) -> list[dict[str, Any]]:
    """Build long-form facetted rows from per-fuel indices.

    For every (entity, time) in the union of inputs, emit:
      - one row per LEAF_INPUTS facet present (with value, may be 0)
      - one ``other_thermal`` row with value = thermal - coal - gas
        (clamped to >= 0; dropped if below MIN_OTHER_THERMAL_FRACTION
        of the total). Null when thermal/coal/gas are not all present.
    """
    rows: list[dict[str, Any]] = []
    keys = _union_keys(*leaf_indices.values(), thermal_index, total_index)

    for entity_id, time in keys:
        # Leaf facets — emit only when the value is genuinely present.
        for facet, idx in leaf_indices.items():
            if (entity_id, time) in idx:
                rows.append({
                    "entity_id": entity_id,
                    "time": time,
                    "value": idx[(entity_id, time)],
                    "facet": facet,
                })

        # Derived other_thermal = thermal - coal - gas
        thermal = thermal_index.get((entity_id, time))
        coal = leaf_indices["coal"].get((entity_id, time))
        gas = leaf_indices["gas"].get((entity_id, time))
        total = total_index.get((entity_id, time))

        if thermal is not None and coal is not None and gas is not None:
            residual = max(0.0, thermal - coal - gas)
            denom = total if total and total > 0 else thermal
            if denom > 0 and (residual / denom) >= MIN_OTHER_THERMAL_FRACTION:
                rows.append({
                    "entity_id": entity_id,
                    "time": time,
                    "value": round(residual, 6),
                    "facet": OTHER_THERMAL_FACET,
                })

    return rows


def assert_sum_invariant(
    rows: list[dict[str, Any]],
    total_index: dict[tuple[str, str], float],
    *,
    tolerance: float = SUM_TOLERANCE_FRACTION,
) -> list[str]:
    """Return human-readable error messages for any cell where
    sum(leaf facets) deviates from the cross-check total by > tolerance.

    Empty list = invariant holds. Used by pytest; safe to call from CLI
    too (composer prints these as warnings before writing).
    """
    sums: dict[tuple[str, str], float] = {}
    for r in rows:
        if r.get("facet") is None:
            continue
        sums.setdefault((r["entity_id"], r["time"]), 0.0)
        if r["value"] is not None:
            sums[(r["entity_id"], r["time"])] += float(r["value"])

    errors: list[str] = []
    for (entity, time), total in total_index.items():
        if total is None or total <= 0:
            continue
        leaf_sum = sums.get((entity, time), 0.0)
        delta = abs(leaf_sum - total)
        if delta / total > tolerance:
            errors.append(
                f"sum invariant breached at ({entity}, {time}): "
                f"sum(leaves)={leaf_sum:.3f} vs total={total:.3f} "
                f"({delta / total * 100:.2f}% off)"
            )
    return errors


# ---------------------------------------------------------------------------
# Composer entry point
# ---------------------------------------------------------------------------

def compose(*, repo_root: Path) -> Path:
    """Read 7 CEA per-fuel artifacts; emit the composed facetted indicator.

    Returns the path of the written artifact.
    Raises ValueError if the sum invariant is breached on any cell.
    """
    in_dir = repo_root / INPUT_DIR_RELPATH

    leaf_docs: dict[str, dict[str, Any]] = {
        facet: _load_indicator(in_dir / fname)
        for facet, fname in LEAF_INPUTS.items()
    }
    thermal_doc = _load_indicator(in_dir / THERMAL_INPUT)
    total_doc = _load_indicator(in_dir / TOTAL_INPUT)

    leaf_indices = {facet: _index_rows(doc) for facet, doc in leaf_docs.items()}
    thermal_index = _index_rows(thermal_doc)
    total_index = _index_rows(total_doc)

    rows = build_facetted_rows(
        leaf_indices=leaf_indices,
        thermal_index=thermal_index,
        total_index=total_index,
    )
    errors = assert_sum_invariant(rows, total_index)
    if errors:
        joined = "\n  ".join(errors[:10])
        raise ValueError(
            f"composer sum invariant failed for {len(errors)} cell(s):\n  {joined}"
        )

    # Coverage is the union; pull entity_count + period from the total doc
    # for a stable, single-source-of-truth header.
    entity_count = len({k[0] for k in total_index})
    snapshot_period = total_doc.get("coverage", {}).get("temporal", "")

    payload = _build_payload(
        rows=rows,
        snapshot_period=snapshot_period,
        entity_count=entity_count,
        thermal_doc=thermal_doc,
    )

    schema = schema_doc(INDICATOR_SCHEMA_FILENAME)
    sources = _union_sources(list(leaf_docs.values()) + [thermal_doc, total_doc])

    out_path = repo_root / OUTPUT_PATH_RELPATH
    return write_artifact(
        path=out_path,
        schema_id=schema_id(INDICATOR_SCHEMA_FILENAME),
        schema_version=schema_version(INDICATOR_SCHEMA_FILENAME),
        payload=payload,
        sources=sources,
        schema_for_validation=schema,
    )


def _build_payload(
    *,
    rows: list[dict[str, Any]],
    snapshot_period: str,
    entity_count: int,
    thermal_doc: dict[str, Any],
) -> dict[str, Any]:
    """Construct the indicator payload (no $schema/$schema_version/sources)."""
    methodology = thermal_doc.get("indicator", {}).get(
        "methodology_vintage",
        f"CEA Monthly Executive Summary, IC sheet, snapshot {snapshot_period}",
    )
    return {
        "license": {
            "id": "GoI-Open",
            "name": "Government of India open publication",
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": f"{entity_count} states/UTs (all CEA-reported per-state entities)",
            "temporal": snapshot_period,
            "admin_level": "state",
        },
        "indicator": {
            "id": "energy/installed_capacity_by_source_mw",
            "title": "Installed capacity by source (fuel mix)",
            "description": (
                "Installed electricity-generation capacity per state, "
                "broken down by fuel source: coal, gas, nuclear, hydro "
                "(large), renewable (solar + wind + small hydro + biomass "
                "+ WtE per MNRE), and a residual 'other_thermal' bucket "
                "(lignite + diesel) where applicable. Composed by joining "
                "the seven CEA per-fuel installed-capacity artifacts."
            ),
            "entity_kind": "state",
            "time_grain": "month",
            "value_kind": "raw",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "MW",
            "icon": "zap",
            "attribution_geography": "where_produced",
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "joint",
            "methodology_vintage": methodology,
            "chart_type": "stacked-trend",
            "default_mode": "percent",
            "facet_labels": dict(FACET_LABELS),
            "notes": (
                "Composed from the per-fuel CEA artifacts. The residual "
                "'other_thermal' facet is derived as thermal − coal − gas "
                "(lignite + diesel); it is dropped per-state when the "
                "residual is < 0.1% of that state's total. Capacity is "
                "**nameplate** MW, not generation. Read this as 'how is "
                "this state's plant fleet composed', not 'where is its "
                "electricity coming from this hour' — generation depends "
                "on plant load factor and dispatch decisions."
            ),
        },
        "rows": rows,
    }
