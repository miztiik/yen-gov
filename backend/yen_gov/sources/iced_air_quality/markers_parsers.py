"""Pure parser for ICED's ``/climate-environment/.../aqi-map-markers``.

Source-of-record for the four NAMP-derived state-year air-quality
indicators. Today this module ships exactly one (PM2.5); NO2, SO2, PM10
follow as mechanical derivations once the loop is proven.

What the endpoint returns:

  Per-station annual mean rows from CPCB's NAMP file
  ``data/AQ_CPCB_UTF8/AQM_<year>_Annual_mean.csv``, re-shipped through
  ICED. 8,453 rows × {_id, state, city, location, lat, lng, year, so2,
  no2, pm10, pm25, file}. Time coverage: SO2/NO2/PM10 from 2010, PM2.5
  from 2014 (matches the cpcb-dates metadata endpoint). 2020 is empty
  in the snapshot — COVID monitoring disruption, declared as a
  series_break in the artifact.

What this module is responsible for:

  *Aggregation method choice*. Hans 2026-05-15 was explicit: the
  aggregation method is a published claim we make about Indian air
  quality, and must live in versioned code we can audit, NOT in NITI's
  server. ICED's own ``aqm-cities`` endpoint pre-aggregates this data
  to city level with an opaque method; we ignore it for the value
  indicator and use it only as a cross-check fixture.

  Method (PM2.5, lockable, reproduce-able):
    1. Drop rows where the pollutant is null/N.A. (distinct from zero).
    2. Per (state, year), unweighted arithmetic mean of the surviving
       per-station annual means.
    3. No imputation, no weighting by station-days, no winsorisation.
    4. Round to 2 dp for diff stability of the artifact.

  Why unweighted: per-day validity counts are not available at this
  feed level (CPCB ships only the annual mean), so any weighting would
  have to use proxies (population? area?) that introduce their own
  arguments. Unweighted is the simplest defensible default; documented
  in `methodology_vintage` and pinned in tests.

  Why state-year (not city-year, not station-level): matches every
  other indicator's `entity_kind: "state"` so the existing state-
  choropleth renderer picks it up with zero new UI. City-year and
  station-level point datasets are explicit follow-up commits with
  different schemas.

What this module is NOT responsible for:

  *Comparability framing*. The indicator's `comparability` flag is set
  to `not_comparable_across_states` in the artifact (the NAMP monitor
  network is uneven and urban-biased — ranking states from this is
  dishonest). That is set in :mod:`.ingest`, not here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from yen_gov.sources.iced_common import ENTITY_MAP, ICEDShapeError


# Pollutant column names on the markers row. Pinned here so a typo in
# the field name fails loudly rather than silently producing zero rows.
PM25_FIELD = "pm25"
NO2_FIELD = "no2"
SO2_FIELD = "so2"
PM10_FIELD = "pm10"

# Null tokens ICED uses interchangeably for "not measured at this
# station-year". `0` is NOT in here — a measured zero (rare for
# pollutants but real) is meaningful and must not be coerced to null.
_NULL_TOKENS: frozenset[Any] = frozenset({None, "N.A.", "N.A", "NA", "n.a.",
                                          "na", "-", "", "..", "...", "*"})

# COVID year — every PM/NO2/SO2 column on the 2020 station-year rows is
# null in the captured snapshot (monitoring disruption). Documented as a
# series_break in the indicator artifact.
COVID_GAP_YEAR = 2020


@dataclass(frozen=True)
class StateYearMean:
    """One row of an aggregated state-year pollutant indicator."""

    entity_id: str          # ECI state code
    state_name: str         # ICED's spelling, kept for diagnostics
    year: int
    n_stations: int         # surviving stations after null drop
    mean_value: float       # unweighted arithmetic mean, μg/m³


def _coerce_pollutant(raw: Any) -> float | None:
    """Convert one cell to float, or None for null tokens.

    Distinct from :func:`iced_common.entities.coerce_numeric`: pollutant
    cells in the markers feed don't carry Indian-grouped commas (values
    are small integers/decimals), so this is a thinner, fail-safer
    coerce that won't silently swallow malformed input.
    """
    if raw in _NULL_TOKENS:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text in _NULL_TOKENS:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _check_outer_envelope(decrypted: Any) -> list[dict]:
    """Validate the ``{status, data: [...]}`` envelope and return the rows."""
    if not isinstance(decrypted, dict):
        raise ICEDShapeError(
            f"aqi-map-markers response is not a dict: {type(decrypted).__name__}"
        )
    if "data" not in decrypted:
        raise ICEDShapeError(
            f"aqi-map-markers response missing 'data': keys={list(decrypted)}"
        )
    rows = decrypted["data"]
    if not isinstance(rows, list):
        raise ICEDShapeError(
            f"aqi-map-markers response.data is not a list: {type(rows).__name__}"
        )
    return rows


def aggregate_state_year_mean(
    decrypted: dict[str, Any],
    *,
    pollutant: str,
) -> list[StateYearMean]:
    """Aggregate station-year rows into one (state, year) row per pollutant.

    Args:
        decrypted: full decrypted response from
            ``/climate-environment/environment/air-quality/aqi-map-markers``.
        pollutant: one of ``pm25 / no2 / so2 / pm10`` — the column to
            aggregate. Pinned constants live at module top.

    Returns:
        Sorted list (by entity_id, year ascending) of
        :class:`StateYearMean`. Empty cells (every station-year null
        for the requested pollutant) are dropped — a state with
        zero surviving stations does NOT appear as ``mean=0``.
    """
    if pollutant not in (PM25_FIELD, NO2_FIELD, SO2_FIELD, PM10_FIELD):
        raise ValueError(
            f"unknown pollutant {pollutant!r}; expected one of "
            f"{(PM25_FIELD, NO2_FIELD, SO2_FIELD, PM10_FIELD)}"
        )

    station_rows = _check_outer_envelope(decrypted)

    # Gather: (entity_id, year) -> list of float values (one per station).
    # Keyed on entity_id (not state name) so multiple ICED spellings that
    # map to the same ECI entity (e.g. "Tamilnadu" + "Tamil Nadu" → S22,
    # or pre/post-2020 DNH+DD halves → U03) collapse into a single row.
    bucket: dict[tuple[str, int], list[float]] = defaultdict(list)
    # Remember a representative ICED spelling per entity_id for diagnostics.
    name_for_entity: dict[str, str] = {}
    unknown_states: set[str] = set()

    for row in station_rows:
        if not isinstance(row, dict):
            continue
        state = row.get("state")
        if not isinstance(state, str) or not state.strip():
            continue
        state = state.strip()
        if state not in ENTITY_MAP:
            unknown_states.add(state)
            continue
        entity_id = ENTITY_MAP[state]
        year = row.get("year")
        if not isinstance(year, int):
            # ICED ships year as int; defend against future str-isation.
            try:
                year = int(year)
            except (TypeError, ValueError):
                continue
        v = _coerce_pollutant(row.get(pollutant))
        if v is None:
            continue
        bucket[(entity_id, year)].append(v)
        name_for_entity.setdefault(entity_id, state)

    if unknown_states:
        raise ICEDShapeError(
            "aqi-map-markers contains state spellings not in ENTITY_MAP — "
            f"add them as aliases in iced_common.entities: {sorted(unknown_states)}"
        )

    out: list[StateYearMean] = []
    for (entity_id, year), vals in bucket.items():
        if not vals:                                 # paranoia; defaultdict(list)
            continue
        out.append(
            StateYearMean(
                entity_id=entity_id,
                state_name=name_for_entity[entity_id],
                year=year,
                n_stations=len(vals),
                mean_value=round(sum(vals) / len(vals), 2),
            )
        )
    out.sort(key=lambda r: (r.entity_id, r.year))
    return out


def emit_indicator_rows(parsed: list[StateYearMean]) -> list[dict[str, Any]]:
    """Convert :class:`StateYearMean` objects to indicator-schema row dicts."""
    return [
        {
            "entity_id": r.entity_id,
            "time": str(r.year),
            "value": r.mean_value,
        }
        for r in parsed
    ]
