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
    PM10_FIELD,
    PM25_FIELD,
    SO2_FIELD,
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


# ---------------------------------------------------------------------------
# SO2 — sibling of PM2.5/NO2 from the same NAMP markers feed.
#
# Sequencing (Hans + Fowler 2026-05-16): SO2 is the lowest-magnitude of
# the four pollutants in most Indian states (typical state-year means
# in single digits µg/m³) because India's coal-fired plants historically
# burn low-sulphur Indian coal and most metros have phased out furnace
# oil. The honest signal here is *where SO2 is unusually high* —
# typically near old thermal plants without flue-gas desulphurisation
# (FGD), and near oil refineries. The chart is read for direction and
# anomaly, not for ranking — `comparability: directional_only`.
#
# Series start year: 2010 (verified against snapshot — SO2 column is
# non-null from 2010). 2020 is present in the snapshot for SO2 (no
# series_break), but `renderer_rules` still carries
# `no_growth_across_break` defensively against future revisions.
# ---------------------------------------------------------------------------

SO2_SERIES_START_YEAR = 2010

SO2_INDICATOR_ID = "environment/state_so2_annual_mean_ug_m3"
SO2_INDICATOR_TITLE = "SO₂ — annual mean (state)"

SO2_INDICATOR_DESCRIPTION = (
    "Annual mean concentration of sulphur dioxide (SO₂) in micrograms "
    "per cubic metre, averaged across all CPCB monitoring stations in "
    "each state. SO₂ is produced by burning sulphur-bearing fuels — "
    "coal-fired thermal plants without flue-gas desulphurisation (FGD) "
    "and oil refineries are the dominant Indian sources. The WHO 2021 "
    "guideline addresses 24-hour exposure (40 µg/m³) and does not set "
    "an annual mean; India's national standard (NAAQS) is 50 µg/m³ "
    "annual mean."
)

SO2_INDICATOR_NOTES = (
    "Method: per (state, year), unweighted arithmetic mean of CPCB "
    "station-year annual means; null station-years dropped (not coerced "
    "to zero). Indian SO₂ levels are typically low in absolute terms "
    "(low-sulphur domestic coal; most metros have phased out furnace "
    "oil) — the honest signal is *where SO₂ is unusually high*, near "
    "old un-retrofitted thermal plants and refineries. The CPCB "
    "monitor network is urban-biased and uneven, so cross-state "
    "ranking from this number is dishonest; read the chart as "
    "'direction of change within a state', not a leaderboard. ICED is "
    "a re-publisher; the underlying station-year file is CPCB's NAMP "
    "— both URLs appear in `sources`."
)

SO2_INDICATOR_EXCLUDES = [
    "Indoor air — NAMP measures only outdoor ambient air",
    "Station-years dropped by CPCB for below-threshold data completeness",
    "Point-source plumes from individual stacks — only ambient air is sampled",
]


def ingest_so2(
    *,
    repo_root: Path,
    refresh: bool = False,
) -> MarkersIngestResult:
    """Fetch markers, aggregate SO2 to state-year, write artifact."""
    runtime_root = repo_root / ".runtime"
    client = IcedClient(host="https://icedapi.niti.gov.in", runtime_root=runtime_root)
    response = client.get(MARKERS_API_PATH)
    fetched_at = response.fetched_at

    parsed_all = aggregate_state_year_mean(response.decrypted, pollutant=SO2_FIELD)
    parsed = [r for r in parsed_all if r.year >= SO2_SERIES_START_YEAR]
    if not parsed:
        raise ICEDShapeError(
            "SO2 aggregation returned zero state-year rows after "
            f"trimming to >= {SO2_SERIES_START_YEAR} — refusing to ship "
            "empty artifact."
        )

    payload = _build_so2_payload(parsed=parsed)

    indicator_schema = schema_doc("indicator.schema.json")
    out_path = (
        repo_root
        / "datasets"
        / "indicators"
        / "in"
        / "environment"
        / "state_so2_annual_mean_ug_m3.json"
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
        indicator_id=SO2_INDICATOR_ID,
        artifact_path=out_path,
        pollutant=SO2_FIELD,
        state_year_row_count=len(parsed),
        year_min=min(years),
        year_max=max(years),
        fetched_at=fetched_at,
    )


def _build_so2_payload(*, parsed: list[StateYearMean]) -> dict:
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
            "spatial": f"{len(states)} states/UTs with CPCB stations recording SO₂",
            "temporal": f"{min(years)}–{max(years)} (annual)",
            "admin_level": "state",
        },
        "indicator": {
            "id": SO2_INDICATOR_ID,
            "title": SO2_INDICATOR_TITLE,
            "description": SO2_INDICATOR_DESCRIPTION,
            "entity_kind": "state",
            "time_grain": "year",
            "value_kind": "raw",
            "direction": "lower_is_better",
            "scale_hint": "linear",
            "unit": "µg/m³",
            "icon": "wind",
            "notes": SO2_INDICATOR_NOTES,
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
            "excludes": SO2_INDICATOR_EXCLUDES,
            "renderer_rules": ["no_rank_table", "no_growth_across_break"],
        },
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# PM10 — sibling of PM2.5/NO2/SO2 from the same NAMP markers feed.
#
# PM10 is the coarse particulate fraction (particles ≤10 µm) and
# *includes* the PM2.5 fraction by definition. The extra mass between
# PM2.5 and PM10 is dominated in India by road dust, construction
# activity, and seasonal crop-residue burning — so PM10 tracks PM2.5
# in metros but runs much higher in dry/dusty regions (Rajasthan,
# parts of Haryana, Punjab in burning season). Reading PM10 alongside
# PM2.5 separates "combustion soot" (PM2.5-dominant) from "dust and
# coarse aerosols" (PM10 ≫ PM2.5).
#
# Series start year: 2010. 2020 IS present in the snapshot, so no
# series_break declared; `renderer_rules` carries
# `no_growth_across_break` defensively.
# ---------------------------------------------------------------------------

PM10_SERIES_START_YEAR = 2010

PM10_INDICATOR_ID = "environment/state_pm10_annual_mean_ug_m3"
PM10_INDICATOR_TITLE = "PM10 — annual mean (state)"

PM10_INDICATOR_DESCRIPTION = (
    "Annual mean concentration of inhalable particulate matter (PM10, "
    "particles ≤10 µm diameter) in micrograms per cubic metre, "
    "averaged across all CPCB monitoring stations in each state. PM10 "
    "includes the PM2.5 fine fraction plus coarser particles — road "
    "dust, construction, and crop-residue burning dominate the extra "
    "mass. The WHO 2021 annual guideline is 15 µg/m³; India's "
    "national standard (NAAQS) is 60 µg/m³."
)

PM10_INDICATOR_NOTES = (
    "Method: per (state, year), unweighted arithmetic mean of CPCB "
    "station-year annual means; null station-years dropped (not coerced "
    "to zero). PM10 includes the PM2.5 fraction by definition; the "
    "extra mass between PM2.5 and PM10 in India is dominated by road "
    "dust, construction activity, and seasonal crop-residue burning, "
    "so PM10 runs much higher than PM2.5 in dry/dusty regions even "
    "where combustion sources are modest. The CPCB monitor network is "
    "urban-biased and uneven, so cross-state ranking from this number "
    "is dishonest; read the chart as 'direction of change within a "
    "state', not a leaderboard. ICED is a re-publisher; the underlying "
    "station-year file is CPCB's NAMP — both URLs appear in `sources`."
)

PM10_INDICATOR_EXCLUDES = [
    "Indoor air — NAMP measures only outdoor ambient air",
    "Station-years dropped by CPCB for below-threshold data completeness",
    "Sub-2.5 µm fraction is counted in PM10 here AND separately in the "
    "state_pm25_annual_mean_ug_m3 indicator — do not sum PM10 and PM2.5",
]


def ingest_pm10(
    *,
    repo_root: Path,
    refresh: bool = False,
) -> MarkersIngestResult:
    """Fetch markers, aggregate PM10 to state-year, write artifact."""
    runtime_root = repo_root / ".runtime"
    client = IcedClient(host="https://icedapi.niti.gov.in", runtime_root=runtime_root)
    response = client.get(MARKERS_API_PATH)
    fetched_at = response.fetched_at

    parsed_all = aggregate_state_year_mean(response.decrypted, pollutant=PM10_FIELD)
    parsed = [r for r in parsed_all if r.year >= PM10_SERIES_START_YEAR]
    if not parsed:
        raise ICEDShapeError(
            "PM10 aggregation returned zero state-year rows after "
            f"trimming to >= {PM10_SERIES_START_YEAR} — refusing to ship "
            "empty artifact."
        )

    payload = _build_pm10_payload(parsed=parsed)

    indicator_schema = schema_doc("indicator.schema.json")
    out_path = (
        repo_root
        / "datasets"
        / "indicators"
        / "in"
        / "environment"
        / "state_pm10_annual_mean_ug_m3.json"
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
        indicator_id=PM10_INDICATOR_ID,
        artifact_path=out_path,
        pollutant=PM10_FIELD,
        state_year_row_count=len(parsed),
        year_min=min(years),
        year_max=max(years),
        fetched_at=fetched_at,
    )


def _build_pm10_payload(*, parsed: list[StateYearMean]) -> dict:
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
            "spatial": f"{len(states)} states/UTs with CPCB stations recording PM10",
            "temporal": f"{min(years)}–{max(years)} (annual)",
            "admin_level": "state",
        },
        "indicator": {
            "id": PM10_INDICATOR_ID,
            "title": PM10_INDICATOR_TITLE,
            "description": PM10_INDICATOR_DESCRIPTION,
            "entity_kind": "state",
            "time_grain": "year",
            "value_kind": "raw",
            "direction": "lower_is_better",
            "scale_hint": "linear",
            "unit": "µg/m³",
            "icon": "wind",
            "notes": PM10_INDICATOR_NOTES,
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
            "excludes": PM10_INDICATOR_EXCLUDES,
            "renderer_rules": ["no_rank_table", "no_growth_across_break"],
        },
        "rows": rows,
    }
