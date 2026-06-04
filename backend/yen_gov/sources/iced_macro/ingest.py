"""Orchestrator for the ICED macro adapter.

Fetches three endpoints and emits three indicator artifacts under
``datasets/indicators/in/economy/``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import (
    parse_balance_trendline,
    parse_gdp_trend,
    parse_gva_trend_national_constant,
    parse_industrial_production,
)

# B1.4.2 - canonical CSV citation triples + variable_id prefixes per indicator.
# All four iced_macro indicators are NITI Aayog ICED endpoints (same producer
# string used across the family per `canonical/adapters/energy/_shared.py`);
# vintage = operator snapshot FY per ADR-0042. derive_source_id() hashes the
# triple at write time; the row in `datasets/data/entities/source.csv` is
# populated by B2a (sub-plan §"Pre-flight"). variable_ids honour parent plan
# section 21.6 / 21.12 (no `__`) and ADR-0044 (no grain prefix); per-facet
# split because csv_writer does not yet accept facet columns (sub-plan
# §B1.4.1..9 point 7). concept_id binding for all four indicators is DEFERRED
# to B2a; recorded as a per-PR DEFER marker in the PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_VINTAGE = "2024-25"

_CSV_SOURCE_TITLE_GDP = (
    "GDP Trend (national + per-state, current & constant prices) API"
)
_CSV_VARIABLE_PREFIX_GDP = "gdp-inr-crore"

_CSV_SOURCE_TITLE_IIP = (
    "Industrial Production Index (IIP, 2011-12 base) API"
)
_CSV_VARIABLE_PREFIX_IIP = "iip-index-2011-12"

_CSV_SOURCE_TITLE_GVA = (
    "GVA by Industry (national, constant 2011-12 prices) API"
)
_CSV_VARIABLE_PREFIX_GVA = "gva-by-industry-constant-inr-crore"

_CSV_SOURCE_TITLE_BOP = "India External-Sector Balance Trendline API"
_CSV_VARIABLE_PREFIX_BOP = "india-external-balance-inr-crore"


@dataclass(frozen=True)
class IndicatorEmitResult:
    indicator_id: str
    artifact_path: Path
    row_count: int
    time_min: str
    time_max: str
    skipped_unmapped: int = 0


@dataclass(frozen=True)
class IngestSummary:
    fetched_at: datetime
    results: tuple[IndicatorEmitResult, ...]


LICENSE_ICED = {
    "id": "GoI-OpenData",
    "name": "Government of India Open Data License",
    "url": "https://www.data.gov.in/government-open-data-license-india",
    "redistributable": True,
}

API_HOST = "https://icedapi.niti.gov.in"


# ---------------------------------------------------------------------------
# Indicator metadata
# ---------------------------------------------------------------------------


def _indicator_gdp() -> dict[str, Any]:
    # PR-B6-row9: cross-grain collapse — country (India) + state (per-state GSDP)
    # rows ship in one shard with entity_kinds=[country, state].
    return {
        "id": "economy/gdp_inr_crore",
        "title": "GDP (₹ crore, current and constant prices)",
        "description": (
            "Gross Domestic Product / Gross State Domestic Product in ₹ "
            "crore, faceted by price basis: 'current' (nominal, "
            "contemporaneous prices) and 'constant' (real, base 2011-12). "
            "Covers India national totals (1950-51 to 2024-25, 75 fiscal "
            "years) and per-state GSDP (2011-12 to 2024-25). Use the "
            "constant series for growth-rate analysis; the current series "
            "for nominal-share comparisons. State coverage varies — small "
            "states/UTs only enter the series after they were carved out "
            "(Telangana from 2014-15, Ladakh from 2019-20)."
        ),
        "description_short": (
            "Gross Domestic Product (output produced in a year) in ₹ crore, "
            "at both country (India) and state grain. Series at current "
            "prices (today's rupees) and at constant 2011-12 prices "
            "(inflation-adjusted)."
        ),
        "entity_kind": "country",
        "entity_kinds": ["country", "state"],
        "default_entity_kind": "country",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "INR crore",
        "icon": "trending-up",
        "attribution_geography": "where_produced",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "MoSPI / National Statistical Office national GDP back-series + "
            "per-state GSDP series compiled by State Directorates of "
            "Economics & Statistics under MoSPI methodology. Constant prices "
            "rebased to 2011-12. Pre-2011 national constant series is the "
            "back-cast MoSPI publishes; methodology shifted in 2015 (NSS68 "
            "→ 2011-12 base) — treat the pre-2011 back-cast as a chained "
            "estimate."
        ),
        "chart_type": "stacked-trend",
        "notes": (
            "State totals will not sum exactly to national GDP because of "
            "differences in base years and revision timing across the 36 "
            "state-level series. ICED's upstream priceType field has values "
            "'gross', 'export', 'import' — only 'gross' is the GDP headline "
            "we ship; the other two are deflator-calculation auxiliaries."
        ),
        "series_breaks": [
            {
                "at_time": "2011-04",
                "kind": "rebase",
                "note": "Constant-price base year switches to 2011-12; pre-2011 national figures are back-cast.",
            },
            {
                "at_time": "2014-04",
                "kind": "coverage_change",
                "note": "Telangana bifurcated from Andhra Pradesh; pre-2014 AP rows include Telangana.",
            },
            {
                "at_time": "2019-04",
                "kind": "coverage_change",
                "note": "Ladakh bifurcated from J&K; pre-2019 J&K rows include Ladakh.",
            },
        ],
    }


def _indicator_iip() -> dict[str, Any]:
    return {
        "id": "economy/iip_index",
        "title": "Index of Industrial Production (IIP), base 2011-12 = 100",
        "description": (
            "National Index of Industrial Production, faceted by category "
            "(sectoral: Mining/Manufacturing/Electricity, plus the General "
            "all-industry index, plus use-based: Capital, Consumer "
            "durables, Consumer non-durables, Intermediate, Infrastructure, "
            "Primary). All values relative to 2011-12 = 100. Annual 2012-13 "
            "to 2024-25."
        ),
        "entity_kind": "country",
        "time_grain": "fiscal_year",
        "value_kind": "index",
        "direction": "higher_is_better",
        "scale_hint": "linear",
        "unit": "index (2011-12=100)",
        "icon": "factory",
        "attribution_geography": "where_produced",
        "comparability": "not_comparable_across_states",
        "implementing_authority": "centre",
        "methodology_vintage": "MoSPI Central Statistics Office, base 2011-12.",
        "chart_type": "stacked-trend",
        "notes": (
            "Mixed sectoral + use-based facets in one indicator — ICED ships "
            "them in the same payload. Renderers should let the user pick "
            "which classification (sectoral vs use-based) to compare within."
        ),
    }


def _indicator_gva_constant() -> dict[str, Any]:
    return {
        "id": "economy/gva_by_industry_constant_inr_crore",
        "title": "GVA by industry (constant 2011-12 prices, ₹ crore)",
        "description": (
            "National Gross Value Added at constant 2011-12 prices, ₹ crore, "
            "faceted by industry. Includes the 'GVA at basic prices' and "
            "'NVA at basic prices' rollups alongside eight production-side "
            "sectors (agriculture, mining, manufacturing, electricity & "
            "utilities, construction, trade-hotels-transport-comms, "
            "financial-real-estate-services, public-admin-and-other-services). "
            "Annual 2011-12 to 2024-25."
        ),
        "entity_kind": "country",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "INR crore",
        "icon": "trending-up",
        "attribution_geography": "where_produced",
        "comparability": "not_comparable_across_states",
        "implementing_authority": "centre",
        "methodology_vintage": (
            "MoSPI / NSO national accounts, constant prices base 2011-12. "
            "GVA = GDP minus net product taxes; NVA = GVA minus consumption "
            "of fixed capital."
        ),
        "chart_type": "stacked-trend",
        "notes": (
            "Only the constant-price series ships in this artifact; the "
            "current-price companion can be added later if needed. State-"
            "level GVA is not shipped — the upstream payload mixes "
            "sector-group rollups (Primary/Secondary/Tertiary) with "
            "per-industry rows in a denser shape that needs its own design."
        ),
    }


def _indicator_india_external_balance() -> dict[str, Any]:
    return {
        "id": "economy/india_external_balance_inr_crore",
        "title": "India external-sector balance (₹ crore)",
        "description": (
            "India's balance-of-payments headline items — Trade Balance, "
            "Invisibles (Net), Current Account Balance, Loans (Net), Total "
            "Foreign Investment, Overall Balance — in ₹ crore. Negative "
            "values indicate a deficit / net outflow. Annual fiscal year, "
            "sparse early years (2000-01, 2010-11) then continuous from "
            "2011-12 onward."
        ),
        "entity_kind": "country",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "INR crore",
        "icon": "globe",
        "attribution_geography": "where_produced",
        "comparability": "not_comparable_across_states",
        "implementing_authority": "centre",
        "methodology_vintage": (
            "RBI Balance of Payments statistics, republished by NITI Aayog "
            "ICED. Most-recent two fiscal years are typically 'Preliminary' "
            "and subject to revision — surfaced via vintage='preliminary' "
            "on those rows. Partial-year rows (Apr-Sep) are dropped to keep "
            "the series annual-comparable."
        ),
        "chart_type": "stacked-trend",
        "notes": (
            "Trade Balance + Invisibles (Net) ≈ Current Account Balance; "
            "Current Account + Capital Account ≈ Overall Balance. Don't "
            "sum the facets blindly — Loans (Net) and Total Foreign "
            "Investment are sub-components of the capital account, already "
            "folded into Overall Balance."
        ),
    }


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a `variable_id`.

    Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes. We
    lower-case, replace any non-alphanumeric run with a single `-`, and
    strip leading/trailing `-`. Mirrors the helper in
    ``backend/yen_gov/sources/iced_ghg/ingest.py`` (B1.4.1, PR #635).
    """
    out: list[str] = []
    prev_dash = True
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def _period_to_year_int(period: str) -> int:
    """Reduce an iced_common ``YYYY-MM`` period to its fiscal-year start year.

    ``parsers.parse_*`` here all emit ``fy_to_period`` output (``YYYY-04``)
    for fiscal years. The canonical CSV column class
    ``datasets/data/datapoints/geo/*.csv`` declares ``time`` as integer
    (`docs/architecture/data/csv-column-contract.md` section 3.3:
    "year (calendar or fiscal as declared by the concept)"). FY 2024-25
    -> ``2024``. Raises ``ValueError`` on malformed input rather than
    silently truncating.
    """
    if not (isinstance(period, str) and len(period) >= 4 and period[:4].isdigit()):
        raise ValueError(f"unexpected time format {period!r}; expected 'YYYY-MM'")
    return int(period[:4])


def build_csv_variables(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
    variable_prefix: str,
) -> dict[str, list[dict[str, Any]]]:
    """Split parser output into per-facet CSV row lists keyed by `variable_id`.

    Each iced_macro indicator carries a ``facet`` column (parser output);
    csv_writer does not yet support facet columns, so we split into one
    ``variable_id`` per facet value: ``<variable_prefix>-<facet-slug>``.
    Each output row carries the canonical 4 columns declared on file
    class ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``.
    """
    by_variable: dict[str, list[dict[str, Any]]] = {}
    for row in parsed_rows:
        facet = row["facet"]
        variable_id = f"{variable_prefix}-{_slug_segment(facet)}"
        by_variable.setdefault(variable_id, []).append({
            "entity_id": row["entity_id"],
            "time": _period_to_year_int(row["time"]),
            "value": row["value"],
            "source_id": source_id,
        })
    return by_variable


def emit_csv_variables(
    *, repo_root: Path, by_variable: dict[str, list[dict[str, Any]]]
) -> tuple[Path, ...]:
    """Write each `variable_id` to `datasets/data/datapoints/geo/<id>.csv`."""
    written: list[Path] = []
    out_dir = repo_root / _CSV_OUT_REL_DIR
    for variable_id, rows in sorted(by_variable.items()):
        path = write_csv(
            path=out_dir / f"{variable_id}.csv",
            file_class=_CSV_FILE_CLASS,
            rows=rows,
        )
        written.append(path)
    return tuple(written)


def _emit_csv_for(
    *,
    repo_root: Path,
    parsed_rows: list[dict[str, Any]],
    title: str,
    variable_prefix: str,
) -> tuple[Path, ...]:
    """Canonical CSV emission ALONGSIDE the legacy meadow/indicator JSON.

    B1.4.2 - both stores coexist (parent plan section 23.1); reader flip is
    X1a. ``source_id`` derived via ADR-0042 from (producer, title, vintage);
    one ``variable_id`` per facet (csv_writer facet-column support deferred).
    """
    source_id = derive_source_id(_CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE)
    by_variable = build_csv_variables(
        parsed_rows, source_id=source_id, variable_prefix=variable_prefix
    )
    return emit_csv_variables(repo_root=repo_root, by_variable=by_variable)


def _emit(
    *,
    repo_root: Path,
    schema_for_validation: dict,
    schema_id_str: str,
    schema_version_str: str,
    indicator_meta: dict[str, Any],
    rows: list[dict[str, Any]],
    sources: list[Source],
    out_rel: str,
    spatial: str,
    skipped_unmapped: int = 0,
) -> IndicatorEmitResult:
    times = sorted({r["time"] for r in rows})
    coverage_temporal = f"{times[0]}..{times[-1]}" if times else "unknown"
    payload = {
        "coverage": {
            "spatial": spatial,
            "temporal": coverage_temporal,
            "admin_level": None if indicator_meta["entity_kind"] == "country" else "state",
        },
        "license": LICENSE_ICED,
        "indicator": indicator_meta,
        "rows": rows,
    }
    artifact_path = repo_root / out_rel
    write_artifact(
        path=artifact_path,
        schema_id=schema_id_str,
        schema_version=schema_version_str,
        payload=payload,
        sources=sources,
        schema_for_validation=schema_for_validation,
    )
    return IndicatorEmitResult(
        indicator_id=indicator_meta["id"],
        artifact_path=artifact_path,
        row_count=len(rows),
        time_min=times[0] if times else "",
        time_max=times[-1] if times else "",
        skipped_unmapped=skipped_unmapped,
    )


def ingest_iced_macro(*, repo_root: Path, client: IcedClient | None = None) -> IngestSummary:
    if client is None:
        client = IcedClient(host=API_HOST, polite_delay=0.5)
    schema_for_validation = schema_doc("indicator.schema.json")
    sid = schema_id("indicator.schema.json")
    sver = schema_version("indicator.schema.json")

    results: list[IndicatorEmitResult] = []

    # GDP (PR-B6-row9: country + state rows in one cross-grain shard)
    gdp_resp = client.get("/economy-demography/key-economic-indicators/gdp-trend")
    gdp_src = [Source(url=gdp_resp.url, fetched_at=gdp_resp.fetched_at)]
    gdp_parsed = parse_gdp_trend(gdp_resp.decrypted)
    gdp_rows = list(gdp_parsed.national) + list(gdp_parsed.state)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_gdp(),
        rows=gdp_rows,
        sources=gdp_src, out_rel="datasets/indicators/in/economy/gdp_inr_crore.json",
        spatial="India (national + states + UTs)",
        skipped_unmapped=gdp_parsed.skipped_unmapped,
    ))
    _emit_csv_for(
        repo_root=repo_root, parsed_rows=gdp_rows,
        title=_CSV_SOURCE_TITLE_GDP, variable_prefix=_CSV_VARIABLE_PREFIX_GDP,
    )

    # IIP
    iip_resp = client.get("/economy-demography/key-economic-indicators/industrial-production")
    iip_rows = parse_industrial_production(iip_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_iip(), rows=iip_rows,
        sources=[Source(url=iip_resp.url, fetched_at=iip_resp.fetched_at)],
        out_rel="datasets/indicators/in/economy/iip_index.json",
        spatial="India (national)",
    ))
    _emit_csv_for(
        repo_root=repo_root, parsed_rows=iip_rows,
        title=_CSV_SOURCE_TITLE_IIP, variable_prefix=_CSV_VARIABLE_PREFIX_IIP,
    )

    # GVA national constant
    gva_resp = client.get("/economy-demography/key-economic-indicators/gva-trend")
    gva_rows = parse_gva_trend_national_constant(gva_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_gva_constant(), rows=gva_rows,
        sources=[Source(url=gva_resp.url, fetched_at=gva_resp.fetched_at)],
        out_rel="datasets/indicators/in/economy/gva_by_industry_constant_inr_crore.json",
        spatial="India (national)",
    ))
    _emit_csv_for(
        repo_root=repo_root, parsed_rows=gva_rows,
        title=_CSV_SOURCE_TITLE_GVA, variable_prefix=_CSV_VARIABLE_PREFIX_GVA,
    )

    # External-sector balance (BoP)
    bop_resp = client.get("/economy-demography/key-economic-indicators/balance-trendline")
    bop_rows = parse_balance_trendline(bop_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_india_external_balance(), rows=bop_rows,
        sources=[Source(url=bop_resp.url, fetched_at=bop_resp.fetched_at)],
        out_rel="datasets/indicators/in/economy/india_external_balance_inr_crore.json",
        spatial="India (national)",
    ))
    _emit_csv_for(
        repo_root=repo_root, parsed_rows=bop_rows,
        title=_CSV_SOURCE_TITLE_BOP, variable_prefix=_CSV_VARIABLE_PREFIX_BOP,
    )

    # PR-A5a: derive orchestrator fetched_at from upstream per-fetch timestamps
    # instead of wall-clock datetime.now(). Deterministic given deterministic
    # upstream IcedClient (out-of-lane follow-up to harden iced_common/client.py).
    return IngestSummary(
        fetched_at=max(
            gdp_resp.fetched_at,
            iip_resp.fetched_at,
            gva_resp.fetched_at,
            bop_resp.fetched_at,
        ),
        results=tuple(results),
    )
