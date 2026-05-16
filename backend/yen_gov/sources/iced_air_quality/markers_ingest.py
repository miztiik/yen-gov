"""Fetch, aggregate, and write state-year PM2.5 mean from NAMP markers.

Today's surface: the PM2.5 indicator. NO2/SO2/PM10 follow as mechanical
derivations once the loop is proven (same fetch, same parser called
with a different ``pollutant`` argument, same writer).

Network boundary: :class:`yen_gov.sources.iced_common.IcedClient`.
Pure aggregation logic lives in :mod:`.markers_parsers` so this module
stays small.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient, ICEDShapeError

from .markers_parsers import (
    COVID_GAP_YEAR,
    NO2_FIELD,
    PM25_FIELD,
    StateYearMean,
    aggregate_state_year_mean,
    emit_indicator_rows,
)

# Endpoint catalogue name: aq_aqi_map_markers (see iced_common.endpoints).
MARKERS_API_PATH = "/climate-environment/environment/air-quality/aqi-map-markers"
MARKERS_API_URL = f"https://icedapi.niti.gov.in{MARKERS_API_PATH}"

# Upstream authority: CPCB's National Air-quality Monitoring Programme.
# This is the actual measurement network; ICED re-ships the per-station
# annual-mean CSVs that CPCB publishes under data/AQ_CPCB_UTF8/. The
# tracker page is the most stable URL — the per-year CSV filenames
# rotate. Listed in `sources` per Hans's dual-provenance rule.
CPCB_NAMP_URL = "https://cpcb.nic.in/national-air-quality-monitoring-programme/"

# Earliest year PM2.5 measurements appear in the NAMP file. Hard-coded
# from the cpcb-dates metadata endpoint (and confirmed by the captured
# 2026-05-15 snapshot: zero PM2.5 rows in 2010-2013, first values in
# 2014). Pre-2014 station-years are excluded from the indicator (no
# data, not zero).
PM25_SERIES_START_YEAR = 2014


PM25_INDICATOR_ID = "environment/state_pm25_annual_mean_ug_m3"
PM25_INDICATOR_TITLE = "PM2.5 — annual mean (state)"

# Citizen-facing description. The chart's source card will render the
# `notes` block separately for caveats; description is the one-line
# definition.
PM25_INDICATOR_DESCRIPTION = (
    "Annual mean concentration of fine particulate matter (PM2.5) in "
    "micrograms per cubic metre, averaged across all CPCB monitoring "
    "stations in each state. PM2.5 is fine enough to lodge in the "
    "lungs and bloodstream — the WHO 2021 guideline is 5 µg/m³ annual "
    "mean; India's national standard is 40 µg/m³."
)

PM25_INDICATOR_NOTES = (
    "Method: per (state, year), unweighted arithmetic mean of CPCB "
    "station-year annual means; null station-years dropped (not coerced "
    "to zero). The CPCB monitor network is uneven (urban-biased, dense "
    "in metros and sparse in rural and small-town India), so cross-"
    "state ranking from this number is dishonest — read it as 'what "
    "stations in this state, where they exist, are recording on "
    "average'. PM2.5 measurements begin in 2014 across the network; "
    "the 2020 year is empty in the snapshot (COVID-era monitoring "
    "disruption) and is declared as a series break. ICED is a re-"
    "publisher; the underlying station-year file is CPCB's NAMP — "
    "both URLs appear in `sources`."
)


@dataclass(frozen=True)
class MarkersIngestResult:
    """One-line result summary for the CLI / admin pipeline panel."""

    indicator_id: str
    artifact_path: Path
    pollutant: str
    state_year_row_count: int
    year_min: int
    year_max: int
    fetched_at: datetime


def ingest_pm25(
    *,
    repo_root: Path,
    refresh: bool = False,
) -> MarkersIngestResult:
    """Fetch markers, aggregate PM2.5 to state-year, write artifact.

    Args:
        repo_root: workspace root.
        refresh: if True, bypass the on-disk cache and re-fetch.
    """
    runtime_root = repo_root / ".runtime"
    client = IcedClient(host="https://icedapi.niti.gov.in", runtime_root=runtime_root)
    response = client.get(MARKERS_API_PATH)
    fetched_at = response.fetched_at

    parsed_all = aggregate_state_year_mean(response.decrypted, pollutant=PM25_FIELD)
    parsed = [r for r in parsed_all if r.year >= PM25_SERIES_START_YEAR]
    if not parsed:
        raise ICEDShapeError(
            "PM2.5 aggregation returned zero state-year rows after "
            f"trimming to >= {PM25_SERIES_START_YEAR} — refusing to ship "
            "empty artifact."
        )

    payload = _build_pm25_payload(parsed=parsed)

    indicator_schema = schema_doc("indicator.schema.json")
    out_path = (
        repo_root
        / "datasets"
        / "indicators"
        / "in"
        / "environment"
        / "state_pm25_annual_mean_ug_m3.json"
    )
    write_artifact(
        path=out_path,
        schema_id=schema_id("indicator.schema.json"),
        schema_version=schema_version("indicator.schema.json"),
        payload=payload,
        sources=[
            Source(url=MARKERS_API_URL, fetched_at=fetched_at),
            Source(url=CPCB_NAMP_URL, fetched_at=fetched_at),
        ],
        schema_for_validation=indicator_schema,
    )

    years = [r.year for r in parsed]
    return MarkersIngestResult(
        indicator_id=PM25_INDICATOR_ID,
        artifact_path=out_path,
        pollutant=PM25_FIELD,
        state_year_row_count=len(parsed),
        year_min=min(years),
        year_max=max(years),
        fetched_at=fetched_at,
    )


def _build_pm25_payload(*, parsed: list[StateYearMean]) -> dict:
    """Compose the schema-required payload (everything except $schema/sources)."""
    rows = emit_indicator_rows(parsed)
    states = sorted({r.entity_id for r in parsed})
    years = [r.year for r in parsed]

    return {
        "license": {
            "id": "GoI-Open",
            "name": (
                "Government of India open publication "
                "(NITI Aayog ICED, re-publishing CPCB NAMP)"
            ),
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": f"{len(states)} states/UTs with CPCB stations recording PM2.5",
            "temporal": f"{min(years)}–{max(years)} (annual; 2020 absent — see notes)",
            "admin_level": "state",
        },
        "indicator": {
            "id": PM25_INDICATOR_ID,
            "title": PM25_INDICATOR_TITLE,
            "description": PM25_INDICATOR_DESCRIPTION,
            "entity_kind": "state",
            "time_grain": "year",
            "value_kind": "raw",
            "direction": "lower_is_better",
            "scale_hint": "linear",
            "unit": "µg/m³",
            "icon": "wind",
            "notes": PM25_INDICATOR_NOTES,
            "attribution_geography": "where_consumed",
            "comparability": "not_comparable_across_states",
            "implementing_authority": "centre",
            "methodology_vintage": (
                "CPCB NAMP per-station annual mean (re-published via "
                "ICED aqi-map-markers); state aggregation = unweighted "
                "arithmetic mean of station-year means; null station-"
                "years dropped, not coerced to zero; pre-2014 trimmed "
                "(no PM2.5 measurements before 2014)."
            ),
            "chart_type": "choropleth",
            "series_breaks": [
                {
                    "at_time": str(COVID_GAP_YEAR),
                    "kind": "coverage_change",
                    "note": (
                        "PM2.5 (and other pollutant) measurements are "
                        "absent for 2020 in the captured snapshot — "
                        "COVID-era disruption to the CPCB monitoring "
                        "network. Trends spanning 2019–2021 should not "
                        "be computed across this gap."
                    ),
                },
            ],
        },
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# NO2 — sibling of PM2.5 from the same NAMP markers feed.
#
# Sequencing (Hans + Fowler 2026-05-16, per the PM2.5 handover): NO2
# follows PM2.5 because vehicle exhaust and thermal-plant flue gas are
# concentrated in metros where the CPCB monitor network is densest, so
# the indicator at least *records* the modal Indian NO2 experience even
# if it under-samples the rural margin. Comparability is still honest
# (`directional_only`) — the chart shows direction-of-change in a state,
# not cross-state ranking.
#
# Series start year: 2010 (verified against the captured snapshot —
# NO2 column is non-null from 2010 forward, unlike PM2.5 which begins
# in 2014). The 2020 COVID gap that PM2.5 hit does NOT appear for NO2
# in the snapshot (NO2 values are present for 2020), so we do NOT
# declare a 2020 series_break here. `renderer_rules` still carries
# `no_growth_across_break` as a defensive policy for any future break.
# ---------------------------------------------------------------------------

NO2_SERIES_START_YEAR = 2010

NO2_INDICATOR_ID = "environment/state_no2_annual_mean_ug_m3"
NO2_INDICATOR_TITLE = "NO₂ — annual mean (state)"

NO2_INDICATOR_DESCRIPTION = (
    "Annual mean concentration of nitrogen dioxide (NO₂) in micrograms "
    "per cubic metre, averaged across all CPCB monitoring stations in "
    "each state. NO₂ is a respiratory irritant produced by combustion "
    "— vehicle exhaust (especially diesel) and thermal-plant flue gas "
    "dominate. The WHO 2021 annual guideline is 10 µg/m³; India's "
    "national standard (NAAQS) is 40 µg/m³."
)

NO2_INDICATOR_NOTES = (
    "Method: per (state, year), unweighted arithmetic mean of CPCB "
    "station-year annual means; null station-years dropped (not coerced "
    "to zero). Sources of NO₂ are concentrated in metros and along "
    "highways — vehicle exhaust (especially diesel) and thermal-plant "
    "flue gas. The CPCB monitor network is urban-biased and uneven, so "
    "cross-state ranking from this number is dishonest; read the chart "
    "as 'direction of change within a state', not a leaderboard. The "
    "2020 dip visible in many states reflects COVID lockdown traffic "
    "collapse — a real signal, but read with caution because the "
    "monitor coverage was also disrupted. ICED is a re-publisher; the "
    "underlying station-year file is CPCB's NAMP — both URLs appear in "
    "`sources`."
)

NO2_INDICATOR_EXCLUDES = [
    "Indoor air — NAMP measures only outdoor ambient air",
    "Station-years dropped by CPCB for below-threshold data completeness",
]


def ingest_no2(
    *,
    repo_root: Path,
    refresh: bool = False,
) -> MarkersIngestResult:
    """Fetch markers, aggregate NO2 to state-year, write artifact.

    Args:
        repo_root: workspace root.
        refresh: if True, bypass the on-disk cache and re-fetch.
    """
    runtime_root = repo_root / ".runtime"
    client = IcedClient(host="https://icedapi.niti.gov.in", runtime_root=runtime_root)
    response = client.get(MARKERS_API_PATH)
    fetched_at = response.fetched_at

    parsed_all = aggregate_state_year_mean(response.decrypted, pollutant=NO2_FIELD)
    parsed = [r for r in parsed_all if r.year >= NO2_SERIES_START_YEAR]
    if not parsed:
        raise ICEDShapeError(
            "NO2 aggregation returned zero state-year rows after "
            f"trimming to >= {NO2_SERIES_START_YEAR} — refusing to ship "
            "empty artifact."
        )

    payload = _build_no2_payload(parsed=parsed)

    indicator_schema = schema_doc("indicator.schema.json")
    out_path = (
        repo_root
        / "datasets"
        / "indicators"
        / "in"
        / "environment"
        / "state_no2_annual_mean_ug_m3.json"
    )
    write_artifact(
        path=out_path,
        schema_id=schema_id("indicator.schema.json"),
        schema_version=schema_version("indicator.schema.json"),
        payload=payload,
        sources=[
            Source(url=MARKERS_API_URL, fetched_at=fetched_at),
            Source(url=CPCB_NAMP_URL, fetched_at=fetched_at),
        ],
        schema_for_validation=indicator_schema,
    )

    years = [r.year for r in parsed]
    return MarkersIngestResult(
        indicator_id=NO2_INDICATOR_ID,
        artifact_path=out_path,
        pollutant=NO2_FIELD,
        state_year_row_count=len(parsed),
        year_min=min(years),
        year_max=max(years),
        fetched_at=fetched_at,
    )


def _build_no2_payload(*, parsed: list[StateYearMean]) -> dict:
    """Compose the schema-required payload (everything except $schema/sources)."""
    rows = emit_indicator_rows(parsed)
    states = sorted({r.entity_id for r in parsed})
    years = [r.year for r in parsed]

    return {
        "license": {
            "id": "GoI-Open",
            "name": (
                "Government of India open publication "
                "(NITI Aayog ICED, re-publishing CPCB NAMP)"
            ),
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": f"{len(states)} states/UTs with CPCB stations recording NO₂",
            "temporal": f"{min(years)}–{max(years)} (annual)",
            "admin_level": "state",
        },
        "indicator": {
            "id": NO2_INDICATOR_ID,
            "title": NO2_INDICATOR_TITLE,
            "description": NO2_INDICATOR_DESCRIPTION,
            "entity_kind": "state",
            "time_grain": "year",
            "value_kind": "raw",
            "direction": "lower_is_better",
            "scale_hint": "linear",
            "unit": "µg/m³",
            "icon": "wind",
            "notes": NO2_INDICATOR_NOTES,
            "attribution_geography": "where_consumed",
            "comparability": "directional_only",
            "implementing_authority": "centre",
            "methodology_vintage": (
                "CPCB NAMP per-station annual mean (re-published via "
                "ICED aqi-map-markers); state aggregation = unweighted "
                "arithmetic mean of station-year means; null station-"
                "years dropped, not coerced to zero."
            ),
            "chart_type": "choropleth",
            "excludes": NO2_INDICATOR_EXCLUDES,
            "renderer_rules": ["no_rank_table", "no_growth_across_break"],
        },
        "rows": rows,
    }
