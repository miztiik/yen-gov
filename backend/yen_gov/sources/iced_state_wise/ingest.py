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
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="economy/state_gdp_current_inr_lakh_crore",
            api_key="GDP (Base: 2011-12) Current Price",
        ),
        title="State GDP (current prices)",
        description=(
            "Gross Domestic Product of the state at current (nominal) "
            "prices, in Lakh Crore Rupees. The 'sticker' value of all "
            "goods and services produced in the state — useful for "
            "tax-base sizing, but inflation-distorted across years."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'GDP (Base: 2011-12) "
            "Current Price'. Same unit-annotation caveat as the constant-"
            "price indicator: values are in **Lakh Crore**."
        ),
        topic="economy", leaf="state_gdp_current_inr_lakh_crore",
        entity_kind="state", value_kind="currency", unit="INR (lakh crore)",
        direction="higher_is_better", icon="trending-up",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="economy/state_sectoral_gva_constant_2011_12_inr_lakh_crore",
            api_key="Sectoral GVA (Base: 2011-12) Constant Price",
        ),
        title="State Sectoral GVA (constant prices, base 2011-12)",
        description=(
            "Gross Value Added across all economic sectors (primary + "
            "secondary + tertiary) at constant 2011-12 prices. GVA "
            "= GDP - net product taxes; the cleaner production-side "
            "measure for cross-sector and cross-state comparisons."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Sectoral GVA (Base: "
            "2011-12) Constant Price'. Lakh Crore Rupees (see GDP "
            "indicators for the unit-annotation caveat)."
        ),
        topic="economy",
        leaf="state_sectoral_gva_constant_2011_12_inr_lakh_crore",
        entity_kind="state", value_kind="currency", unit="INR (lakh crore)",
        direction="higher_is_better", icon="bar-chart",
    ),
    IndicatorMeta(
        spec=IndicatorSpec(
            indicator_id="economy/state_sectoral_gva_current_inr_lakh_crore",
            api_key="Sectoral GVA (Base: 2011-12) Current Price",
        ),
        title="State Sectoral GVA (current prices)",
        description=(
            "Gross Value Added at nominal (current) prices in Lakh Crore "
            "Rupees. Inflation-influenced — for real-economy trend "
            "tracking prefer the constant-price indicator."
        ),
        notes=(
            "Source: NITI Aayog ICED dashboard, row 'Sectoral GVA (Base: "
            "2011-12) Current Price'."
        ),
        topic="economy", leaf="state_sectoral_gva_current_inr_lakh_crore",
        entity_kind="state", value_kind="currency", unit="INR (lakh crore)",
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

    out_root = repo_root / "datasets" / "indicators" / "in"
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
        payload = _build_payload(meta=meta, rows=rows, fetched_at=latest_fetch)

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
        fy_count = len({r.time for r in rows})
        results.append(
            IndicatorIngestResult(
                indicator_id=meta.spec.indicator_id,
                artifact_path=path,
                fy_count=fy_count,
                row_count=len(rows),
            )
        )

    return IngestResult(
        indicators=tuple(results),
        fetched_at=latest_fetch,
        fy_labels=fy_labels,
    )
