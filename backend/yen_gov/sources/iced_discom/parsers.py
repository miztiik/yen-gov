"""Pure parsers for the ICED v0 DISCOM endpoint family.

Each parser is pure: takes the already-decrypted JSON payload and returns
canonical indicator rows ``(rows, skipped_unmapped)``. Rows are deduped
last-write-wins on ``(entity_id, time, facet)``.
"""
from __future__ import annotations

from typing import Any

from yen_gov.sources.iced_common import (
    ENTITY_MAP,
    ICEDShapeError,
    coerce_numeric,
    fy_to_period,
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
# /energy/electricity/distribution/operationalPerformanceStates
# ---------------------------------------------------------------------------

# The four categories the upstream emits. We split these into separate
# indicator artifacts because each carries an independent meaning and
# direction (lower is better for losses, higher is better for efficiency).
OPPERF_CATEGORIES = (
    "transmission-and-distribution-loss",
    "billing-efficiency",
    "collection-efficiency",
    "aggregate-technical-and-commercial-loss",
)


def parse_opperf_states(decoded: Any) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """Per-state operational performance metrics, split by category.

    Returns ``(by_category, skipped_unmapped)`` where ``by_category`` maps
    each category slug to a sorted list of canonical rows (no facet — each
    category is its own indicator artifact). The ``aggregate-technical-
    and-commercial-loss`` bucket is also returned (callers may or may not
    emit it; see ingest.py — we currently skip it because a richer
    state-level ATC artifact already exists at
    ``energy/state_atc_losses_pct``).
    """
    items = _rows_container(decoded, "/energy/electricity/distribution/operationalPerformanceStates")
    out: dict[str, dict[tuple[str, str], dict[str, Any]]] = {
        cat: {} for cat in OPPERF_CATEGORIES
    }
    skipped = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        category = (raw.get("category") or "").strip()
        if category not in out:
            continue
        state_label = (raw.get("state") or "").strip()
        if not state_label:
            continue
        entity_id = ENTITY_MAP.get(state_label)
        if not entity_id:
            skipped += 1
            continue
        try:
            period = fy_to_period(str(raw.get("fyear") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("value"))
        if value is None:
            continue
        out[category][(entity_id, period)] = _row(entity_id, period, value)
    by_category = {
        cat: sorted(rows.values(), key=lambda r: (r["entity_id"], r["time"]))
        for cat, rows in out.items()
    }
    return by_category, skipped


# ---------------------------------------------------------------------------
# /energy/electricity/distribution/rpo
# ---------------------------------------------------------------------------

# RPO compliance is reported per state per FY along three axes: solar,
# non-solar, and total. We emit a single faceted indicator with
# ``facet in {solar, non-solar, total}`` and ``value`` = compliance %
# against target. ``totalCompliance`` and the per-axis fields are already
# percent-of-target, so the RPO=100% line is the policy goal.

RPO_FACETS: tuple[tuple[str, str], ...] = (
    ("solar", "solarCompliance"),
    ("non-solar", "nonSolarCompliance"),
    ("total", "totalCompliance"),
)


def parse_rpo(decoded: Any) -> tuple[list[dict[str, Any]], int]:
    """Per-state RPO compliance (% of target), faceted by solar/non-solar/total.

    Returns ``(rows, skipped_unmapped)``. Rows are deduped last-write-wins
    on ``(entity_id, time, facet)``. Upstream ``rpoCompliance`` (a
    ratio-against-target with no upper bound — values can exceed 100) is
    intentionally NOT emitted; we use the bounded ``solar/nonSolar/
    totalCompliance`` percent fields, which are the citizen-readable form.
    """
    items = _rows_container(decoded, "/energy/electricity/distribution/rpo")
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        state_label = (raw.get("state") or "").strip()
        if not state_label:
            continue
        entity_id = ENTITY_MAP.get(state_label)
        if not entity_id:
            skipped += 1
            continue
        try:
            period = fy_to_period(str(raw.get("fyear") or ""))
        except ValueError:
            continue
        for facet, key in RPO_FACETS:
            value = coerce_numeric(raw.get(key))
            if value is None:
                continue
            out[(entity_id, period, facet)] = _row(entity_id, period, value, facet)
    rows = sorted(out.values(), key=lambda r: (r["entity_id"], r["time"], r["facet"]))
    return rows, skipped
