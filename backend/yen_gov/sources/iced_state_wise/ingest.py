"""Orchestrator for the ICED state-wise deep-dive ingest.

For each fiscal year 2015-16 .. 2025-26 we hit the API once for all 37
entities, cache the encrypted body to ``.runtime/raw/iced/<FY>.b64``,
decrypt it, then walk the indicator catalogue (``INDICATOR_SPECS``) to
assemble per-indicator artifacts under
``datasets/indicators/in/<topic>/state_<slug>.json``.

Network: 11 small GETs (one per FY). Polite: a small delay between
requests, exponential retry on transient failures, browser-style
headers (the API rejects naive python-urllib UAs in some configs).

The cached encrypted bodies are deliberately kept in their original
ciphertext form. That way (a) re-runs are offline, (b) anyone curious
can replay the decryption deterministically, (c) we never persist
anything we couldn't have observed by sniffing the wire.
"""
from __future__ import annotations

import json
import time as _time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from yen_gov.core.io import Source, write_artifact

from .parsers import (
    ENTITY_MAP,
    ICEDShapeError,
    IndicatorSpec,
    ParsedRow,
    ParsedYear,
    decrypt_response,
    extract_rows,
)


API_URL = "https://icedapi.niti.gov.in/analytics/stateWiseDeepDive"

# Page-side referer (the API checks Origin/Referer on some networks).
PAGE_URL = "https://iced.niti.gov.in/analytics/state-wise-deep-dive"

CACHE_REL_DIR = ".runtime/raw/iced"

# Years available from the page's FY <select> (recon 2026-05-14).
FY_LABELS: tuple[str, ...] = (
    "2015-16", "2016-17", "2017-18", "2018-19", "2019-20",
    "2020-21", "2021-22", "2022-23", "2023-24", "2024-25",
    "2025-26",
)

# Browser-style user agent — the upstream rejects bare python-urllib.
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://iced.niti.gov.in",
    "Referer": "https://iced.niti.gov.in/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    ),
}


# ---------------------------------------------------------------------------
# Indicator catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorMeta:
    """Display + governance metadata for one indicator."""

    spec: IndicatorSpec
    title: str
    description: str
    notes: str
    topic: str               # filesystem topic dir (e.g. "energy", "economy")
    leaf: str                # filename leaf (without .json)
    entity_kind: str         # "state" | "country"  (we ship "state" — All India joins as IN)
    value_kind: str          # currency | count | rate | share | index | duration | raw
    unit: str
    direction: str           # higher_is_better | lower_is_better | neutral
    icon: str
    scale_hint: str = "linear"


# ICED returns 13 well-populated indicators across 11 FYs × 36 entities.
# Per the page header the dataset was "Last Updated: 28-04-2026", and the
# 2025-26 row often shows N.A. for indicators not yet published.
INDICATOR_SPECS: tuple[IndicatorMeta, ...] = (
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_installed_capacity_geographical_mw",
            api_key="Installed Capacity*(Geographical location based)",
        ),
        title="Installed electricity capacity (geographical, by state)",
        description=(
            "Total installed electricity generating capacity physically "
            "located in the state, summed across all utility/non-utility "
            "and renewable/non-renewable plants. 'Geographical' here means "
            "every plant counts toward the state where it sits, regardless "
            "of who owns it or where the power is dispatched."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard (state-wise deep-dive), "
            "row 'Installed Capacity (Geographical location based)'. The "
            "underlying data is published by the Central Electricity "
            "Authority. Compare with the *_with_alloc indicator for the "
            "share-allocated version (which reflects who has rights to the "
            "output, not where the steel-and-concrete sits)."
        ),
        topic="energy", leaf="state_installed_capacity_geographical_mw",
        entity_kind="state", value_kind="raw", unit="MW",
        direction="higher_is_better", icon="bolt",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_installed_capacity_with_alloc_mw",
            api_key=(
                "Installed Capacity*(Including Allocated Shares in Joint & "
                "Central Sector Utilities)"
            ),
            api_key_subkey="data",
        ),
        title="Installed electricity capacity (with allocated shares, by state)",
        description=(
            "Same as the geographical-location capacity, but with each "
            "state credited its share of joint-sector and central-sector "
            "plants according to the regional allocation formulas. This is "
            "the figure you should use when comparing 'how much electricity "
            "does this state have rights to' rather than 'how much physical "
            "capacity is sited there'."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Installed Capacity "
            "(Including Allocated Shares in Joint & Central Sector "
            "Utilities)'. The all-India total equals the geographical-"
            "location total (as it must) but the per-state breakdown can "
            "diverge sharply for states that import or export power "
            "through central-sector PPAs."
        ),
        topic="energy", leaf="state_installed_capacity_with_alloc_mw",
        entity_kind="state", value_kind="raw", unit="MW",
        direction="higher_is_better", icon="bolt",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_rooftop_solar_capacity_mw",
            api_key="Rooftop Solar Capacity",
        ),
        title="Rooftop solar installed capacity (by state)",
        description=(
            "Total cumulative installed rooftop solar PV capacity in the "
            "state, across residential, commercial, industrial and public "
            "buildings. Typically much smaller than utility-scale solar "
            "but politically and distributionally important — rooftop "
            "solar is owned by the building owner, not by a utility."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Rooftop Solar "
            "Capacity'. Underlying figures published by MNRE."
        ),
        topic="energy", leaf="state_rooftop_solar_capacity_mw",
        entity_kind="state", value_kind="raw", unit="MW",
        direction="higher_is_better", icon="sun",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_electricity_generation_mu",
            api_key="Generation",
        ),
        title="Annual electricity generation (by state)",
        description=(
            "Gross electricity generated in the state during the fiscal "
            "year, in million units (MU = GWh). Captures actual production "
            "regardless of where the power was eventually consumed."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Generation'. Read "
            "alongside Installed Capacity (Geographical) — generation "
            "/ (capacity × hours-in-year) is the state-level capacity "
            "utilisation ratio."
        ),
        topic="energy", leaf="state_electricity_generation_mu",
        entity_kind="state", value_kind="raw", unit="MU",
        direction="neutral", icon="zap",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_electricity_peak_demand_mw",
            api_key="Peak Demand",
        ),
        title="Annual peak electricity demand (by state)",
        description=(
            "The single highest 15-minute system demand the state's grid "
            "served at any moment during the fiscal year. The companion "
            "API field 'Peak Demand Date' tells you when it occurred — "
            "almost always a hot afternoon for southern/western states "
            "and a cold morning for northern/north-eastern states."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Peak Demand'. "
            "Underlying figures published by CEA. The accompanying "
            "'Peak Demand Date' string is not ingested as a separate "
            "indicator (it would need value_kind=raw and date semantics)."
        ),
        topic="energy", leaf="state_electricity_peak_demand_mw",
        entity_kind="state", value_kind="raw", unit="MW",
        direction="neutral", icon="activity",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_electricity_sales_mu",
            api_key="Electricity Sales",
        ),
        title="Annual electricity sales (by state)",
        description=(
            "Total electricity actually billed to end-consumers (all "
            "categories: domestic, commercial, industrial, agricultural, "
            "public lighting, etc.) in the state, in million units. The "
            "gap between 'Generation' and 'Electricity Sales' is the AT&C "
            "loss in absolute terms."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Electricity Sales'. "
            "Underlying figures from the PFC State Distribution Utilities "
            "report. Includes intra-state imports — consumption can "
            "exceed in-state generation."
        ),
        topic="energy", leaf="state_electricity_sales_mu",
        entity_kind="state", value_kind="raw", unit="MU",
        direction="neutral", icon="plug",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_atc_losses_pct",
            api_key="AT&C Losses",
        ),
        title="Aggregate Technical & Commercial losses (%, by state)",
        description=(
            "Combined technical losses (transmission + distribution heat "
            "and ageing-equipment losses) and commercial losses (theft + "
            "billing/collection inefficiencies) as a percentage of total "
            "energy input to the distribution system. The headline measure "
            "of distribution-utility operational health: lower is better."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'AT&C Losses'. "
            "Calculated by PFC. The Government's UDAY targets envisaged "
            "AT&C losses below 15% all-India by 2018-19; the actual all-"
            "India figure has hovered around 15% since then."
        ),
        topic="energy", leaf="state_atc_losses_pct",
        entity_kind="state", value_kind="share", unit="%",
        direction="lower_is_better", icon="trending-down",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="energy/state_acs_arr_gap_inr_per_kwh",
            api_key="ACS-ARR (Electricity Sales) Gap",
        ),
        title="ACS-ARR gap on electricity sales (Rs/kWh, by state)",
        description=(
            "Average Cost of Supply minus Average Revenue Realised, per "
            "unit of electricity sold. Positive = the utility loses money "
            "on every unit it sells (cost > revenue). Negative = surplus. "
            "Zero is the policy goal under UDAY/RDSS — utilities should "
            "neither subsidise consumption nor extract rent."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'ACS-ARR (Electricity "
            "Sales) Gap'. Calculated by PFC from utility tariff orders + "
            "audited accounts. Note the opposite sign convention from "
            "fiscal-deficit indicators: here a *negative* number is the "
            "surplus side."
        ),
        topic="energy", leaf="state_acs_arr_gap_inr_per_kwh",
        entity_kind="state", value_kind="currency", unit="INR/kWh",
        direction="lower_is_better", icon="dollar-sign",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="economy/state_gdp_constant_2011_12_inr_lakh_crore",
            api_key="GDP (Base: 2011-12) Constant Price",
        ),
        title="State GDP (constant prices, base 2011-12)",
        description=(
            "Gross Domestic Product of the state at constant 2011-12 "
            "prices, in Lakh Crore Rupees (1 Lakh Crore = 1 trillion). "
            "Constant-price GDP strips out inflation and reflects only "
            "real-volume growth."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'GDP (Base: 2011-12) "
            "Constant Price'. Underlying figures from MoSPI's National "
            "Statistical Office. The dashboard's unit annotation "
            "('Crores') and the on-page header ('Lakh Crore') disagree; "
            "spot-checks against MoSPI's published all-India GDP series "
            "confirm the values are in **Lakh Crore** (Rs trillions)."
        ),
        topic="economy", leaf="state_gdp_constant_2011_12_inr_lakh_crore",
        entity_kind="state", value_kind="currency", unit="INR (lakh crore)",
        direction="higher_is_better", icon="trending-up",
    ),
    # PR-B6-row9: state_gdp_current_inr_lakh_crore retired (exact unit-converted
    # subset of economy/gdp_inr_crore current facet; cross-grain shard now owns
    # both country + state rows). state_gdp_constant_2011_12_inr_lakh_crore
    # remains here pending future ICED-vs-MoSPI vintage reconciliation.
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="economy/sectoral_gva_inr_crore",
            api_key="Sectoral GVA (Base: 2011-12) Constant Price",
            # Companion API key for the `current` facet is wired via
            # SECTORAL_GVA_FACET_SOURCES below; this meta's `api_key` provides
            # the `constant` facet rows. Both keys are fetched per FY and
            # merged into one shard with `rows[].facet` + unit conversion
            # (publisher Lakh Crore -> crore, x 1e5).
        ),
        title="State Sectoral GVA (\u20b9 crore, current and constant prices)",
        description=(
            "Gross Value Added across all economic sectors (primary + "
            "secondary + tertiary) at both nominal (current) and inflation-"
            "stripped (constant 2011-12) prices, in \u20b9 crore. GVA = GDP "
            "minus net product taxes; the cleaner production-side measure "
            "for cross-sector and cross-state comparisons. Use 'current' for "
            "share-of-national rankings or tax-base sizing; use 'constant' "
            "for real-economy trend tracking."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, rows 'Sectoral GVA (Base: "
            "2011-12) Current Price' and 'Sectoral GVA (Base: 2011-12) "
            "Constant Price' (NSO/MoSPI underlying). Publisher dashboard "
            "reports Lakh Crore; this shard converts to plain crore "
            "(\u00d7 1e5) for consistency with peer economy indicators "
            "(NSDP, India GDP). The 2025-26 row is typically N.A. while "
            "NSO finalises that year's accounts."
        ),
        topic="economy", leaf="sectoral_gva_inr_crore",
        entity_kind="state", value_kind="currency", unit="INR (crore)",
        direction="higher_is_better", icon="bar-chart",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="demography/state_population_lakhs",
            api_key="Population",
        ),
        title="State population (Lakhs)",
        description=(
            "Estimated total resident population of the state in Lakhs "
            "(1 Lakh = 100,000). Inter-censal estimates from MoSPI; the "
            "next decadal Census will reset the baseline."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Population'. The "
            "values are inter-censal estimates — treat the per-year "
            "deltas as projections, not measured changes. The most recent "
            "Census of India was 2011; the 2021 round was deferred."
        ),
        topic="demography", leaf="state_population_lakhs",
        entity_kind="state", value_kind="count", unit="Lakhs",
        direction="neutral", icon="users",
    ),
)


# Companion API keys merged into the `economy/sectoral_gva_inr_crore` faceted
# shard at write time. The primary IndicatorMeta above declares the
# `constant` facet's api_key; this dict maps additional facet values to the
# extra api_keys whose rows must also be fetched per FY. Per ADR-0044 + the
# Rosling rule (vintage-on-rows): one indicator id, two facets, base year
# tracked on row.vintage.
SECTORAL_GVA_FACET_SOURCES: dict[str, dict[str, str]] = {
    "economy/sectoral_gva_inr_crore": {
        # facet_value -> ICED api_key
        "constant": "Sectoral GVA (Base: 2011-12) Constant Price",
        "current": "Sectoral GVA (Base: 2011-12) Current Price",
    },
}
# Publisher unit -> shard unit conversion factor for each collapsed group.
# ICED dashboard reports Sectoral GVA in Lakh Crore; the shard normalises to
# plain crore (1 lakh crore = 1e5 crore) for parity with peer indicators.
SECTORAL_GVA_VALUE_SCALE: float = 1.0e5
SECTORAL_GVA_VINTAGE_LABEL: str = "Base 2011-12"


# ---------------------------------------------------------------------------
# HTTP / cache layer
# ---------------------------------------------------------------------------


class ICEDFetchError(RuntimeError):
    """Network-layer failure that exhausted retries."""


def _fetch_one(fy_label: str, *, all_states: list[str], retries: int = 3, sleep: float = 1.5) -> bytes:
    """GET one FY × all-states response. Returns the raw HTTP body bytes.

    The body is a JSON-encoded string (the encrypted ciphertext); the
    decryption happens in ``parsers.decrypt_response``.
    """
    qs = urllib.parse.urlencode(
        {"year": fy_label, "state": ",".join(all_states)},
        quote_via=urllib.parse.quote,
    )
    url = f"{API_URL}?{qs}"
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt + 1 < retries:
                _time.sleep(sleep * (attempt + 1))
                continue
    raise ICEDFetchError(
        f"GET {url!r} failed after {retries} attempts: {last_err!r}"
    )


def _resolve_cache_path(*, repo_root: Path, fy_label: str) -> Path:
    return repo_root / CACHE_REL_DIR / f"stateWiseDeepDive_{fy_label}.json"


def _ensure_cache(
    *,
    repo_root: Path,
    fy_label: str,
    all_states: list[str],
    refresh: bool,
) -> tuple[bytes, datetime]:
    """Return ``(raw_body, fetched_at)`` for one FY; populate cache on miss.

    The cached file is the verbatim HTTP response body (a quoted CryptoJS
    ciphertext). We deliberately don't write the decrypted JSON to disk —
    that would mean publishing data we received behind a custom encoding
    scheme, which is an unnecessary signal.
    """
    cache_path = _resolve_cache_path(repo_root=repo_root, fy_label=fy_label)
    if cache_path.exists() and not refresh:
        body = cache_path.read_bytes()
        ts = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
        return body, ts
    body = _fetch_one(fy_label=fy_label, all_states=all_states)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(body)
    # Derive the source timestamp from the cache file's mtime symmetrically
    # with the cache-hit branch above. Using ``datetime.now()`` here would
    # leak operator wall-clock into artifact content (CLAUDE.md §10
    # anti-pattern), making re-runs that re-fetch byte-identical bodies
    # advance the ``fetched_at`` stamp and churn ``git status``.
    ts = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    return body, ts


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorIngestResult:
    indicator_id: str
    artifact_path: Path
    fy_count: int
    row_count: int


@dataclass(frozen=True)
class IngestResult:
    indicators: tuple[IndicatorIngestResult, ...]
    fetched_at: datetime
    fy_labels: tuple[str, ...]


def _coverage_temporal(rows: Iterable[ParsedRow]) -> str:
    times = sorted({r.time for r in rows})
    if not times:
        return "unknown"
    return f"{times[0]}..{times[-1]}"


def _coverage_spatial(rows: Iterable[ParsedRow]) -> str:
    eids = {r.entity_id for r in rows}
    n_states = sum(1 for e in eids if e.startswith("S"))
    n_uts = sum(1 for e in eids if e.startswith("U"))
    has_in = "IN" in eids
    parts: list[str] = []
    if has_in:
        parts.append("All-India aggregate")
    if n_states:
        parts.append(f"{n_states} states")
    if n_uts:
        parts.append(f"{n_uts} UTs")
    return "; ".join(parts) if parts else "no entities"


def _build_payload(
    *,
    meta: IndicatorMeta,
    rows: list[ParsedRow],
    fetched_at: datetime,
) -> dict[str, Any]:
    fy_count = len({r.time for r in rows})
    return {
        "license": {
            "id": "GoI-Open",
            "name": "Government of India open publication (NITI Aayog ICED)",
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": _coverage_spatial(rows),
            "temporal": _coverage_temporal(rows),
            "admin_level": "state",
        },
        "indicator": {
            "id": meta.spec.indicator_id,
            "title": meta.title,
            "description": meta.description,
            "entity_kind": meta.entity_kind,
            "time_grain": "fiscal_year",
            "value_kind": meta.value_kind,
            "direction": meta.direction,
            "scale_hint": meta.scale_hint,
            "unit": meta.unit,
            "icon": meta.icon,
            "attribution_geography": "where_administered",
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "state",
            "methodology_vintage": (
                f"NITI Aayog ICED state-wise deep-dive API; payload "
                f"fetched {fetched_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}; "
                f"{fy_count} fiscal years, {len(rows)} rows."
            ),
            "notes": meta.notes,
        },
        "rows": [
            {"entity_id": r.entity_id, "time": r.time, "value": r.value}
            for r in rows
        ],
    }


def _build_collapsed_payload(
    *,
    meta: IndicatorMeta,
    facet_groups: list[tuple[str, list[ParsedRow]]],
    fetched_at: datetime,
    value_scale: float,
    vintage_label: str,
    facet_labels: dict[str, str],
) -> dict[str, Any]:
    """Merge multi-facet rows into one shard with rows[].facet + .vintage.

    Per ADR-0044 + the Rosling rule: one indicator id, faceted by basis
    (current / constant), base year tracked on each row's `vintage`. Values
    are scaled from publisher unit to shard unit at write time (e.g. ICED
    publishes Sectoral GVA in Lakh Crore; this shard normalises to crore by
    `value_scale = 1e5`).
    """
    merged: list[dict[str, Any]] = []
    for facet_value, rows in facet_groups:
        for r in rows:
            merged.append({
                "entity_id": r.entity_id,
                "time": r.time,
                "value": round(r.value * value_scale, 2),
                "facet": facet_value,
                "vintage": vintage_label,
            })
    merged.sort(key=lambda x: (x["entity_id"], x["time"], x["facet"]))

    eids = {m["entity_id"] for m in merged}
    n_states = sum(1 for e in eids if e.startswith("S"))
    n_uts = sum(1 for e in eids if e.startswith("U"))
    spatial_parts: list[str] = []
    if "IN" in eids:
        spatial_parts.append("All-India aggregate")
    if n_states:
        spatial_parts.append(f"{n_states} states")
    if n_uts:
        spatial_parts.append(f"{n_uts} UTs")
    times = sorted({m["time"] for m in merged})
    temporal = f"{times[0]}..{times[-1]}" if times else "unknown"
    fy_count = len(times)
    return {
        "license": {
            "id": "GoI-Open",
            "name": "Government of India open publication (NITI Aayog ICED)",
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": "; ".join(spatial_parts) if spatial_parts else "no entities",
            "temporal": temporal,
            "admin_level": "state",
        },
        "indicator": {
            "id": meta.spec.indicator_id,
            "title": meta.title,
            "description": meta.description,
            "entity_kind": meta.entity_kind,
            "time_grain": "fiscal_year",
            "value_kind": meta.value_kind,
            "direction": meta.direction,
            "scale_hint": meta.scale_hint,
            "unit": meta.unit,
            "short_unit": "\u20b9Cr",
            "icon": meta.icon,
            "attribution_geography": "where_administered",
            "comparability": "comparable_with_normalisation",
            "implementing_authority": "state",
            "methodology_vintage": (
                f"NITI Aayog ICED state-wise deep-dive API; publisher base 2011-12; "
                f"payload fetched {fetched_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}; "
                f"{fy_count} fiscal years, {len(merged)} rows; "
                f"unit converted from publisher Lakh Crore to crore "
                f"(\u00d7 {int(value_scale):g})."
            ),
            "facet_labels": facet_labels,
            "notes": meta.notes,
        },
        "rows": merged,
    }


def ingest(
    *,
    repo_root: Path,
    schema_dir: Path,
    refresh: bool = False,
    only_fys: tuple[str, ...] | None = None,
) -> IngestResult:
    """Fetch (or read cache) for all FYs, decrypt, parse, write artifacts."""
    indicator_schema_path = schema_dir / "indicator.schema.json"
    indicator_schema = json.loads(indicator_schema_path.read_text(encoding="utf-8"))

    fy_labels = tuple(only_fys) if only_fys else FY_LABELS
    all_states = list(ENTITY_MAP.keys())

    # Per-indicator accumulator: rows across all FYs.
    rows_by_indicator: dict[str, list[ParsedRow]] = {
        m.spec.indicator_id: [] for m in INDICATOR_SPECS
    }
    # Companion accumulator for the non-primary facets of collapsed groups.
    # Key shape: (out_indicator_id, facet_value) -> rows. The primary facet
    # for each group lives in rows_by_indicator under the out_indicator_id;
    # this dict carries the additional facets (e.g. `current` for sectoral
    # GVA, since the primary IndicatorMeta declares `constant`).
    extra_facet_rows: dict[tuple[str, str], list[ParsedRow]] = {}
    _primary_facet_by_group: dict[str, str] = {}
    for _out_id, _facet_map in SECTORAL_GVA_FACET_SOURCES.items():
        _primary_api_key = next(
            (m.spec.api_key for m in INDICATOR_SPECS if m.spec.indicator_id == _out_id),
            None,
        )
        for _facet_value, _api_key in _facet_map.items():
            if _api_key == _primary_api_key:
                _primary_facet_by_group[_out_id] = _facet_value
                continue
            extra_facet_rows[(_out_id, _facet_value)] = []
    latest_fetch = datetime.fromtimestamp(0, tz=timezone.utc)

    for fy in fy_labels:
        body, ts = _ensure_cache(
            repo_root=repo_root,
            fy_label=fy,
            all_states=all_states,
            refresh=refresh,
        )
        if ts > latest_fetch:
            latest_fetch = ts
        try:
            decrypted = decrypt_response(body)
        except ICEDShapeError as e:
            raise ICEDShapeError(f"FY={fy}: {e}") from e
        for meta in INDICATOR_SPECS:
            try:
                year = extract_rows(spec=meta.spec, fy_label=fy, decrypted=decrypted)
            except ICEDShapeError:
                # Tolerate a missing indicator in one FY (older years sometimes
                # drop a column). The downstream artifact still ships with the
                # other FYs covered.
                continue
            rows_by_indicator[meta.spec.indicator_id].extend(year.rows)

        # Companion fetches for non-primary facets of collapsed groups.
        for (out_id, facet_value), accum in extra_facet_rows.items():
            api_key = SECTORAL_GVA_FACET_SOURCES[out_id][facet_value]
            companion_spec = IndicatorSpec(
                indicator_id=f"{out_id}#facet={facet_value}",
                api_key=api_key,
            )
            try:
                year = extract_rows(spec=companion_spec, fy_label=fy, decrypted=decrypted)
            except ICEDShapeError:
                continue
            accum.extend(year.rows)

    out_root = repo_root / "datasets" / "indicators" / "in"
    # Per ADR-0041, energy indicators promoted to meadow tier write to
    # `datasets/<family>/_meadow/<source>/<vintage>/<file>.json`. The set
    # grows PR-by-PR until C4.7 finalisation; then the legacy branch dies.
    _meadow_root = repo_root / "datasets" / "energy" / "_meadow" / "iced" / "2024-25"
    meadow_promoted: dict[str, Path] = {
        "energy/state_electricity_generation_mu": (
            _meadow_root / "state_electricity_generation_mu.json"
        ),
        # PR 7c-2 (distribution family, iced_state_wise side):
        "energy/state_electricity_sales_mu": (
            _meadow_root / "state_electricity_sales_mu.json"
        ),
        "energy/state_atc_losses_pct": (
            _meadow_root / "state_atc_losses_pct.json"
        ),
        "energy/state_acs_arr_gap_inr_per_kwh": (
            _meadow_root / "state_acs_arr_gap_inr_per_kwh.json"
        ),
        # PR 7c-4 (installed_capacity family, iced_state_wise side):
        "energy/state_installed_capacity_geographical_mw": (
            _meadow_root / "state_installed_capacity_geographical_mw.json"
        ),
        "energy/state_installed_capacity_with_alloc_mw": (
            _meadow_root / "state_installed_capacity_with_alloc_mw.json"
        ),
    }
    results: list[IndicatorIngestResult] = []
    for meta in INDICATOR_SPECS:
        rows = rows_by_indicator[meta.spec.indicator_id]
        if not rows:
            # All FYs returned N.A. — refuse to ship an empty artifact.
            raise ICEDShapeError(
                f"indicator {meta.spec.indicator_id!r}: zero rows extracted "
                f"across {len(fy_labels)} FYs. Either the API key changed "
                f"({meta.spec.api_key!r}) or all values are null tokens."
            )
        # Sort: state code, then time ascending.
        rows.sort(key=lambda r: (r.entity_id, r.time))

        if meta.spec.indicator_id in SECTORAL_GVA_FACET_SOURCES:
            # Faceted collapse: merge primary + extras, unit-convert, write
            # one shard with rows[].facet + rows[].vintage.
            primary_facet = _primary_facet_by_group[meta.spec.indicator_id]
            facet_groups: list[tuple[str, list[ParsedRow]]] = [(primary_facet, rows)]
            for fv in SECTORAL_GVA_FACET_SOURCES[meta.spec.indicator_id]:
                if fv == primary_facet:
                    continue
                extra = extra_facet_rows.get((meta.spec.indicator_id, fv), [])
                if not extra:
                    raise ICEDShapeError(
                        f"collapsed indicator {meta.spec.indicator_id!r}: "
                        f"facet {fv!r} returned zero rows across "
                        f"{len(fy_labels)} FYs."
                    )
                facet_groups.append((fv, extra))
            payload = _build_collapsed_payload(
                meta=meta,
                facet_groups=facet_groups,
                fetched_at=latest_fetch,
                value_scale=SECTORAL_GVA_VALUE_SCALE,
                vintage_label=SECTORAL_GVA_VINTAGE_LABEL,
                facet_labels={
                    "current": "Current prices",
                    "constant": "Constant prices (base 2011-12)",
                },
            )
        else:
            payload = _build_payload(meta=meta, rows=rows, fetched_at=latest_fetch)

        meadow_path = meadow_promoted.get(meta.spec.indicator_id)
        if meadow_path is not None:
            path = meadow_path
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            topic_dir = out_root / meta.topic
            topic_dir.mkdir(parents=True, exist_ok=True)
            path = topic_dir / f"{meta.leaf}.json"
        write_artifact(
            path=path,
            schema_id=indicator_schema["$id"],
            schema_version=indicator_schema["x-version"],
            payload=payload,
            sources=[Source(url=PAGE_URL, fetched_at=latest_fetch)],
            schema_for_validation=indicator_schema,
        )
        fy_count = len({r["time"] for r in payload["rows"]})
        row_count = len(payload["rows"])
        results.append(
            IndicatorIngestResult(
                indicator_id=meta.spec.indicator_id,
                artifact_path=path,
                fy_count=fy_count,
                row_count=row_count,
            )
        )

    return IngestResult(
        indicators=tuple(results),
        fetched_at=latest_fetch,
        fy_labels=fy_labels,
    )
