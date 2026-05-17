"""Pure parsers for the ICED power-sector adapter.

Five parsers, one per emitted indicator. Each consumes one already-
fetched response (decrypted dict for the AES endpoints,
already-JSON-parsed list/dict for the v1 JSON-direct endpoints) and
returns ``list[dict]`` of canonical indicator rows ready for
``write_artifact``. No I/O. No fetching.

ICED-specific quirks every parser handles:

* Year format is ``"YYYY-YY"`` (Indian fiscal year) for the per-state
  state-wise feeds, and ``"YYYY"`` (calendar year) for the pipeline
  feed. We normalise to ``YYYY-04`` for fiscal_year indicators and
  bare ``YYYY`` for the year-grain indicator.
* State names that don't map to any ECI code (e.g. legacy spellings
  not yet in :data:`ENTITY_MAP`, or aggregate rows like "All India"
  on a state-only feed) are dropped silently with a counter so the
  artifact still ships with the entities that do map.
* Source names are kebab-case in ICED ("oil-gas", "small-hydro",
  "bio-power"). We pass them through unchanged for the ``facet``
  field â€” the renderer is the right layer to decide display casing.
"""
from __future__ import annotations

import re
from typing import Any

from yen_gov.sources.iced_common import ENTITY_MAP, ICEDShapeError, coerce_numeric, parser_kit


# ---------------------------------------------------------------------------
# 1. capacity-metatable-data â†’ state_installed_capacity_by_source_mw
# ---------------------------------------------------------------------------



def parse_capacity_metatable(decrypted: Any) -> tuple[list[dict[str, Any]], int]:
    """Parse ``/v1/capacity-metatable-data`` â†’ per-state per-fuel capacity rows.

    Returns ``(rows, skipped_unmapped_state_count)``. Each row has facet
    set to the fuel source string (kebab-case as ICED ships it).

    Expected shape: ``list[ {state, fyear, source, capacity} ]``. Rejects
    anything else with :class:`ICEDShapeError`.
    """
    if not isinstance(decrypted, list):
        raise ICEDShapeError(
            f"capacity-metatable-data: expected top-level list, got {type(decrypted).__name__}"
        )
    rows: list[dict[str, Any]] = []
    skipped = 0
    for item in decrypted:
        if not isinstance(item, dict):
            continue
        state_name = item.get("state")
        entity_id = ENTITY_MAP.get(state_name) if isinstance(state_name, str) else None
        if entity_id is None:
            skipped += 1
            continue
        period = parser_kit.fy_to_period(item.get("fyear"))
        if period is None:
            continue
        source = item.get("source")
        if not isinstance(source, str) or not source:
            continue
        capacity = coerce_numeric(item.get("capacity"))
        if capacity is None:
            continue
        rows.append(parser_kit.row(entity_id=entity_id, time=period, value=capacity, facet=source))
    return parser_kit.dedup_sort(rows), skipped


# ---------------------------------------------------------------------------
# 2 + 3. powerStatistics â†’ generation_by_source + peak_demand
# ---------------------------------------------------------------------------


def parse_power_statistics(decrypted: Any) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    """Parse ``/energy/powerStatistics`` envelope.

    Returns ``(generation_rows, peak_demand_rows, skipped_unmapped_states)``.

    The endpoint returns one snapshot row per state for the latest fiscal
    year, where each row carries:

    * ``state``                â€” state name
    * ``fyear``                â€” ``"YYYY-YYYY"``
    * ``peakDemand``           â€” MW (already in megawatts)
    * ``energyMet``            â€” MU (gigawatt-hours, but called MU upstream)
    * ``data: list[{source, capacity, generation}]``
                                â€” per-fuel breakdown for that state-year

    We emit two indicators from this:

    * ``state_electricity_generation_by_source_gwh`` â€” facet = source,
      value = ``generation`` (MU, equivalent to GWh).
    * ``state_peak_electricity_demand_mw`` â€” value = ``peakDemand``.

    The ``data[].capacity`` field overlaps with capacity-metatable-data
    (and is more recent â€” only one fiscal year â€” so capacity-metatable
    is the long-history canonical source). We do NOT emit a separate
    capacity artifact from here; the metatable feed wins.
    """
    if not isinstance(decrypted, dict):
        raise ICEDShapeError(
            f"powerStatistics: expected top-level dict, got {type(decrypted).__name__}"
        )
    state_block = decrypted.get("stateWiseData")
    if not isinstance(state_block, list):
        raise ICEDShapeError(
            "powerStatistics: missing or non-list 'stateWiseData' key"
        )

    generation_rows: list[dict[str, Any]] = []
    peak_rows: list[dict[str, Any]] = []
    skipped = 0

    for item in state_block:
        if not isinstance(item, dict):
            continue
        state_name = item.get("state")
        entity_id = ENTITY_MAP.get(state_name) if isinstance(state_name, str) else None
        if entity_id is None:
            skipped += 1
            continue

        # ICED here ships fyear as "2025-2026" (full 4-4) â€” accept that too.
        raw_fy = item.get("fyear")
        period = parser_kit.fy_to_period(raw_fy)
        if period is None and isinstance(raw_fy, str):
            # Try "YYYY-YYYY" â†’ take the start year.
            m = re.match(r"^(\d{4})-\d{4}$", raw_fy.strip())
            if m:
                period = f"{int(m.group(1)):04d}-04"
        if period is None:
            continue

        # Peak demand
        peak = coerce_numeric(item.get("peakDemand"))
        if peak is not None:
            peak_rows.append(parser_kit.row(entity_id=entity_id, time=period, value=peak))

        # Per-source generation
        sub = item.get("data")
        if isinstance(sub, list):
            for s in sub:
                if not isinstance(s, dict):
                    continue
                source = s.get("source")
                gen = coerce_numeric(s.get("generation"))
                if not isinstance(source, str) or not source or gen is None:
                    continue
                generation_rows.append(
                    parser_kit.row(entity_id=entity_id, time=period, value=gen, facet=source)
                )

    return parser_kit.dedup_sort(generation_rows), parser_kit.dedup_sort(peak_rows), skipped


# ---------------------------------------------------------------------------
# 4. retired-capacity-plants â†’ india_thermal_capacity_retired_mw
# ---------------------------------------------------------------------------


def parse_retired_capacity(decrypted: Any) -> list[dict[str, Any]]:
    """Parse ``/v1/retired-capacity-plants`` â†’ national rows (entity_id="IN").

    Expected shape (already-JSON-parsed): ``{"data": [ {totalCapacity, year, source}, ... ]}``.
    Each row is the total MW of plants of one fuel source retired in one
    fiscal year, nationally. Faceted by source.
    """
    if isinstance(decrypted, dict) and "data" in decrypted:
        items = decrypted["data"]
    elif isinstance(decrypted, list):
        items = decrypted
    else:
        raise ICEDShapeError(
            f"retired-capacity-plants: expected dict with 'data' key or list, "
            f"got {type(decrypted).__name__}"
        )
    if not isinstance(items, list):
        raise ICEDShapeError(
            f"retired-capacity-plants: 'data' must be a list, got {type(items).__name__}"
        )

    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        period = parser_kit.fy_to_period(item.get("year"))
        if period is None:
            continue
        source = item.get("source")
        if not isinstance(source, str) or not source:
            continue
        cap = coerce_numeric(item.get("totalCapacity"))
        if cap is None:
            continue
        rows.append(parser_kit.row(entity_id="IN", time=period, value=cap, facet=source))
    return parser_kit.dedup_sort(rows)


# ---------------------------------------------------------------------------
# 5. plantPipelineInfo â†’ india_capacity_pipeline_gw
# ---------------------------------------------------------------------------


def parse_pipeline(decrypted: Any) -> list[dict[str, Any]]:
    """Parse ``/v1/plantPipelineInfo`` â†’ national rows (entity_id="IN").

    Expected shape: ``{"category": ["YYYY", ...], "seriesData": [{"name": str, "data": [num, ...]}, ...]}``.
    Time grain is calendar year. Faceted by series name (e.g.
    ``"Under Construction and likely to be commissioned"`` vs
    ``"Under Construction but on Hold"``).
    """
    if not isinstance(decrypted, dict):
        raise ICEDShapeError(
            f"plantPipelineInfo: expected top-level dict, got {type(decrypted).__name__}"
        )
    category = decrypted.get("category")
    series = decrypted.get("seriesData")
    if not isinstance(category, list) or not isinstance(series, list):
        raise ICEDShapeError(
            "plantPipelineInfo: missing 'category' or 'seriesData' arrays"
        )

    years = [parser_kit.fy_to_period(y, time_grain="year") for y in category]
    rows: list[dict[str, Any]] = []
    for s in series:
        if not isinstance(s, dict):
            continue
        name = s.get("name")
        data = s.get("data")
        if not isinstance(name, str) or not isinstance(data, list):
            continue
        for i, raw in enumerate(data):
            if i >= len(years):
                break
            period = years[i]
            if period is None:
                continue
            value = coerce_numeric(raw)
            if value is None:
                continue
            rows.append(parser_kit.row(entity_id="IN", time=period, value=value, facet=name))
    return parser_kit.dedup_sort(rows)
