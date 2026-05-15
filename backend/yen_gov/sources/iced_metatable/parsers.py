"""Pure parsers for the ICED v1 ``*-metatable-data`` endpoint family.

Each parser is pure: takes the already-decoded JSON payload (the v1
``*-metatable-data`` endpoints return plain JSON, so the input is already a
dict or list, not an AES envelope) and returns canonical indicator rows.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from yen_gov.sources.iced_common import (
    ENTITY_MAP,
    ICEDShapeError,
    coerce_numeric,
    fy_to_period,
)


# ICED `source` slugs are already lowercase-hyphenated (`coal`, `oil-gas`,
# `bio-power`, `small-hydro`, `solar`, `wind`, `hydro`, `nuclear`). They are
# already a fine controlled vocabulary — we keep them as-is.


def _rows_container(decoded: Any, endpoint_label: str) -> list[Any]:
    """Some metatable endpoints wrap rows in ``{"data": [...]}``, others
    return a bare list. Normalise to ``list``."""
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


def _row(entity_id: str, period: str, value: float, facet: str) -> dict[str, Any]:
    return {"entity_id": entity_id, "time": period, "value": value, "facet": facet}


def _sort(rows: dict[tuple[str, str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows.values(), key=lambda r: (r["entity_id"], r["time"], r["facet"]))


# ---------------------------------------------------------------------------
# parse_gen_metatable
# ---------------------------------------------------------------------------


def parse_gen_metatable(decoded: Any) -> tuple[list[dict[str, Any]], int]:
    """Per-state electricity generation by fuel source (MU = GWh).

    Returns ``(rows, skipped_unmapped)``. ``rows`` are deduped last-write-wins
    on ``(entity_id, time, facet)``. The ICED ``"Others"`` bucket (rows whose
    ``state`` is the catch-all for un-attributable generation) is dropped: it
    cannot be mapped to a real ECI entity_id and is misleading on a
    per-state choropleth.
    """
    items = _rows_container(decoded, "/v1/gen-metatable-data")
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        state_label = (raw.get("state") or "").strip()
        source = (raw.get("source") or "").strip()
        if not state_label or not source:
            continue
        entity_id = ENTITY_MAP.get(state_label)
        if not entity_id:
            skipped += 1
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("generation"))
        if value is None:
            continue
        out[(entity_id, period, source)] = _row(entity_id, period, value, source)
    return _sort(out), skipped


# ---------------------------------------------------------------------------
# parse_plf_metatable
# ---------------------------------------------------------------------------


def parse_plf_metatable(decoded: Any) -> tuple[list[dict[str, Any]], int]:
    """Per-state Plant Load Factor (%) by fuel source.

    Same shape as ``gen-metatable``; value field is ``plf`` (already a
    percentage, 0..100). Returns ``(rows, skipped_unmapped)``.
    """
    items = _rows_container(decoded, "/v1/plf-metatable-data")
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        state_label = (raw.get("state") or "").strip()
        source = (raw.get("source") or "").strip()
        if not state_label or not source:
            continue
        entity_id = ENTITY_MAP.get(state_label)
        if not entity_id:
            skipped += 1
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("plf"))
        if value is None:
            continue
        out[(entity_id, period, source)] = _row(entity_id, period, value, source)
    return _sort(out), skipped


# ---------------------------------------------------------------------------
# parse_co_emission_metatable
# ---------------------------------------------------------------------------


def parse_co_emission_metatable(decoded: Any) -> tuple[list[dict[str, Any]], int]:
    """Per-state CO2 emissions from fossil-fired power, faceted by fuel source.

    Upstream is plant-unit granularity (~11.2k rows across 280 plants × 18 FYs ×
    {coal, oil-gas}). We aggregate to state × year × source by SUM of
    per-unit ``value`` (which is per-unit annual CO2 in million tonnes — the
    headline plant Lara STPS Unit 2 emits ~6.6 MtCO2/yr at 800 MW
    supercritical, which checks out at ~0.8 kgCO2/kWh × 8 TWh).

    Returns ``(rows, skipped_unmapped)``; rows are deduped/aggregated in a
    single pass keyed on ``(entity_id, time, source)``.
    """
    items = _rows_container(decoded, "/v1/co-emission-metatable-data")
    aggregator: dict[tuple[str, str, str], float] = defaultdict(float)
    skipped = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        state_label = (raw.get("state") or "").strip()
        source = (raw.get("source") or "").strip()
        if not state_label or not source:
            continue
        entity_id = ENTITY_MAP.get(state_label)
        if not entity_id:
            skipped += 1
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("value"))
        if value is None:
            continue
        aggregator[(entity_id, period, source)] += value
    rows = [
        _row(entity_id, period, round(total, 6), source)
        for (entity_id, period, source), total in aggregator.items()
    ]
    rows.sort(key=lambda r: (r["entity_id"], r["time"], r["facet"]))
    return rows, skipped
