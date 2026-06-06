"""Indicator metadata + canonical CSV emission for the ICED state-wise family.

The legacy network-fetch + folded-indicator-JSON path (``ingest``) was
retired in B4-pt2.1 per parent plan section 21.4 ("network-fetch code is
deleted; ingest reads local TCPD / source CSV"). What remains is the
INDICATOR_SPECS catalog + the B1.4.8 canonical CSV emission exercised by
``backend/tests/test_iced_state_wise_csv_repoint.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

from .parsers import (
    ENTITY_MAP,
    ICEDShapeError,
    IndicatorSpec,
    ParsedRow,
    ParsedYear,
    decrypt_response,
    extract_rows,
)


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
# Canonical CSV emission (B1.4.8)
# ---------------------------------------------------------------------------
#
# Re-points every indicator emitted by this ingest onto
# `yen_gov.canonical.csv_writer.write_csv` ALONGSIDE the legacy
# `write_artifact` meadow-JSON path (parent plan section 23.1; instead-of
# is deferred to B3). `source_id` is derived via ADR-0042 from
# (producer, title, vintage); variable_ids honour parent plan section
# 21.6 / 21.12 (no `__`) and ADR-0044 (no grain prefix). The faceted
# Sectoral GVA indicator splits into one variable_id per facet
# (csv_writer facet-column support deferred per sub-plan B1.4.1..9 #7).
# concept_id binding DEFERRED to B2a; recorded as DEFER marker in the
# PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_VINTAGE = "2024-25"

# Map every iced_state_wise indicator_id to its (citation title,
# kebab-case variable prefix). The prefix drops the grain (state_*)
# prefix per ADR-0044 since grain lives on `entity_id` not on id.
_CSV_INDICATOR_EMIT: dict[str, tuple[str, str]] = {
    "energy/state_installed_capacity_geographical_mw": (
        "ICED state-wise deep-dive: installed electricity capacity "
        "(geographical location based)",
        "installed-capacity-geographical-mw",
    ),
    "energy/state_installed_capacity_with_alloc_mw": (
        "ICED state-wise deep-dive: installed electricity capacity "
        "(with allocated shares)",
        "installed-capacity-with-allocated-shares-mw",
    ),
    "energy/state_rooftop_solar_capacity_mw": (
        "ICED state-wise deep-dive: rooftop solar installed capacity",
        "rooftop-solar-capacity-mw",
    ),
    "energy/state_electricity_generation_mu": (
        "ICED state-wise deep-dive: annual electricity generation",
        "electricity-generation-mu",
    ),
    "energy/state_electricity_peak_demand_mw": (
        "ICED state-wise deep-dive: annual peak electricity demand",
        "electricity-peak-demand-mw",
    ),
    "energy/state_electricity_sales_mu": (
        "ICED state-wise deep-dive: annual electricity sales",
        "electricity-sales-mu",
    ),
    "energy/state_atc_losses_pct": (
        "ICED state-wise deep-dive: aggregate technical and commercial losses",
        "atc-losses-pct",
    ),
    "energy/state_acs_arr_gap_inr_per_kwh": (
        "ICED state-wise deep-dive: ACS-ARR gap on electricity sales",
        "acs-arr-gap-inr-per-kwh",
    ),
    "economy/state_gdp_constant_2011_12_inr_lakh_crore": (
        "ICED state-wise deep-dive: state GDP constant 2011-12 prices",
        "gdp-constant-2011-12-inr-lakh-crore",
    ),
    "economy/sectoral_gva_inr_crore": (
        "ICED state-wise deep-dive: sectoral GVA (current and constant prices)",
        "sectoral-gva-inr-crore",
    ),
    "demography/state_population_lakhs": (
        "ICED state-wise deep-dive: state population",
        "population-lakhs",
    ),
}


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a ``variable_id``.

    Mirrors sibling iced_* ingests (B1.4.1..7). Parent plan section
    21.6 / 21.12 ban ``__``; ADR-0044 bans grain prefixes.
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
    """Reduce ``YYYY-MM`` or ``YYYY`` to integer year.

    The canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer. iced_state_wise parsers emit
    ``YYYY-04`` (fiscal-year start) via ``fy_to_period``.
    """
    if not (isinstance(period, str) and len(period) >= 4 and period[:4].isdigit()):
        raise ValueError(
            f"unexpected time format {period!r}; expected 'YYYY' or 'YYYY-MM'"
        )
    return int(period[:4])


def build_csv_variables(
    payload_rows: list[dict[str, Any]],
    *,
    source_id: str,
    variable_prefix: str,
) -> dict[str, list[dict[str, Any]]]:
    """Split payload rows into per-facet CSV row lists keyed by ``variable_id``.

    Faceted indicators (Sectoral GVA: current / constant) split into one
    ``variable_id`` per facet value: ``<variable_prefix>-<facet-slug>``.
    Non-faceted indicators collapse to a single ``variable_id ==
    variable_prefix``. Each output row carries the canonical 4 columns
    declared on file class ``datasets/data/datapoints/geo/*.csv``:
    ``entity_id``, ``time``, ``value``, ``source_id``.
    """
    by_variable: dict[str, list[dict[str, Any]]] = {}
    for row in payload_rows:
        facet = row.get("facet")
        if facet is None:
            variable_id = variable_prefix
        else:
            variable_id = f"{variable_prefix}-{_slug_segment(str(facet))}"
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
    """Write each ``variable_id`` to ``datasets/data/datapoints/geo/<id>.csv``."""
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
    indicator_id: str,
    payload_rows: list[dict[str, Any]],
) -> tuple[Path, ...]:
    """Canonical CSV emission ALONGSIDE the legacy meadow indicator JSON.

    B1.4.8 - both stores coexist (parent plan section 23.1); reader flip
    is X1a. ``source_id`` derived via ADR-0042 from
    (producer, title, vintage); one ``variable_id`` per facet
    (csv_writer facet-column support deferred).
    """
    title, variable_prefix = _CSV_INDICATOR_EMIT[indicator_id]
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        payload_rows, source_id=source_id, variable_prefix=variable_prefix
    )
    return emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
