"""Pure parsers for the ICED v0 fuel + power-purchase endpoint family.

Each parser returns ``(rows, skipped_unmapped)``. Rows are deduped
last-write-wins. ``ENTITY_MAP`` lookup is case-insensitive
(coal endpoint emits UPPERCASE state names; PPA emits Title Case).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from yen_gov.sources.iced_common import (
    ICEDShapeError,
    coerce_numeric,
    fy_to_period,
    lookup_entity,
)


def _rows_container(decoded: Any, endpoint_label: str) -> list[Any]:
    if isinstance(decoded, list):
        return decoded
    if isinstance(decoded, dict):
        rows = decoded.get("data")
        if isinstance(rows, list):
            return rows
    raise ICEDShapeError(
        f"expected {endpoint_label} to return a list or {{'data': [...]}}, "
        f"got {type(decoded).__name__}"
    )


def _row(entity_id: str, period: str, value: float, facet: str | None = None) -> dict[str, Any]:
    out = {"entity_id": entity_id, "time": period, "value": value}
    if facet is not None:
        out["facet"] = facet
    return out


# ---------------------------------------------------------------------------
# /energy/fuel-sources/coal/consumption-domestic-state
# ---------------------------------------------------------------------------

# Upstream emits 5 ``type`` values: RAW COAL, WASHED COAL, MIDDLINGS,
# LIGNITE, and a precomputed TOTAL COAL (only present for the most-recent
# few FYs). We aggregate the 4 component types per (state, year) -- this
# yields a complete time series, where the precomputed TOTAL COAL is only
# partial. TOTAL COAL rows are dropped to avoid double-counting.
_COAL_COMPONENT_TYPES: frozenset[str] = frozenset({
    "RAW COAL", "WASHED COAL", "MIDDLINGS", "LIGNITE",
})


def parse_coal_consumption_state(decoded: Any) -> tuple[list[dict[str, Any]], int]:
    """Per-state coal consumption (Mt), aggregated across coal grades.

    Returns ``(rows, skipped_unmapped)``. Single value per (state, year);
    no facet (the type/grade dimension is summed away because for state-
    level "how much coal does this state burn?" the grade is incidental).
    """
    items = _rows_container(decoded, "/energy/fuel-sources/coal/consumption-domestic-state")
    aggregator: dict[tuple[str, str], float] = defaultdict(float)
    seen_unmapped: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        coal_type = (raw.get("type") or "").strip().upper()
        if coal_type not in _COAL_COMPONENT_TYPES:
            continue
        state_label = raw.get("state") or ""
        entity_id = lookup_entity(state_label)
        if not entity_id:
            if state_label.strip():
                seen_unmapped.add(state_label.strip())
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("total"))
        if value is None:
            continue
        aggregator[(entity_id, period)] += value
    rows = [
        _row(entity_id, period, round(total, 4))
        for (entity_id, period), total in aggregator.items()
    ]
    rows.sort(key=lambda r: (r["entity_id"], r["time"]))
    return rows, len(seen_unmapped)


# ---------------------------------------------------------------------------
# /energy/fuel-sources/oil/consumptionStateProductTrend
# ---------------------------------------------------------------------------

# Upstream 7 product types, lightly normalised here to lowercase-hyphen
# slugs that fit the existing source-vocabulary (matching coal/oil-gas/
# solar/etc. style used elsewhere). Slugs become indicator facets.
_OIL_PRODUCT_SLUG: dict[str, str] = {
    "DIESEL/ HSD": "diesel-hsd",
    "DIESEL/HSD": "diesel-hsd",
    "PETROL": "petrol",
    "LPG": "lpg",
    "SKO (KEROSENE)": "kerosene",
    "NAPHTHA": "naphtha",
    "PETROLEUM COKE": "petroleum-coke",
    "OTHERS": "others",
}


def parse_oil_consumption_state(decoded: Any) -> tuple[list[dict[str, Any]], int]:
    """Per-state oil-product consumption (kt), faceted by product.

    Returns ``(rows, skipped_unmapped)``. Faceted rows: facet = one of
    ``diesel-hsd``, ``petrol``, ``lpg``, ``kerosene``, ``naphtha``,
    ``petroleum-coke``, ``others``. The ``OTHERS`` *state* bucket and
    the ``IN`` *region* (national aggregate) rows are dropped because
    they cannot be mapped to a real ECI entity.
    """
    items = _rows_container(decoded, "/energy/fuel-sources/oil/consumptionStateProductTrend")
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    seen_unmapped: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        # Drop national-aggregate rows (region == "IN").
        if (raw.get("region") or "").strip().upper() == "IN":
            continue
        product = (raw.get("type") or "").strip().upper()
        product_slug = _OIL_PRODUCT_SLUG.get(product)
        if product_slug is None:
            continue
        state_label = raw.get("state") or ""
        entity_id = lookup_entity(state_label)
        if not entity_id:
            if state_label.strip():
                seen_unmapped.add(state_label.strip())
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("quantity"))
        if value is None:
            continue
        out[(entity_id, period, product_slug)] = _row(entity_id, period, value, product_slug)
    rows = sorted(out.values(), key=lambda r: (r["entity_id"], r["time"], r["facet"]))
    return rows, len(seen_unmapped)


# ---------------------------------------------------------------------------
# /statelevel-power-purchase-quantum-and-cost
# ---------------------------------------------------------------------------


def parse_ppa_share(decoded: Any) -> tuple[list[dict[str, Any]], int]:
    """Per-state share (%) of electricity purchased by generation source.

    Returns ``(rows, skipped_unmapped)``. Faceted by source slug
    (already lowercase-hyphen in upstream: coal, oil-gas, hydro, solar,
    wind, nuclear, small-hydro, bio-power, trading-and-others, ...).
    Value = ``purchasePercentage`` (% of total power purchased from this
    source by this state in this FY). The ``totalCost`` field is not
    emitted -- it has many nulls and ambiguous units in upstream.

    Rows whose ``state`` is the empty string (national aggregate) are
    dropped because they cannot be mapped to a real ECI entity.
    """
    items = _rows_container(decoded, "/statelevel-power-purchase-quantum-and-cost")
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    seen_unmapped: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        state_label = raw.get("state") or ""
        if not state_label.strip():
            continue  # national aggregate; not a state choropleth row.
        entity_id = lookup_entity(state_label)
        if not entity_id:
            seen_unmapped.add(state_label.strip())
            continue
        source = (raw.get("source") or "").strip()
        if not source:
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("purchasePercentage"))
        if value is None:
            continue
        out[(entity_id, period, source)] = _row(entity_id, period, value, source)
    rows = sorted(out.values(), key=lambda r: (r["entity_id"], r["time"], r["facet"]))
    return rows, len(seen_unmapped)
