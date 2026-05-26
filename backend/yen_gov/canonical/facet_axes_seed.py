"""Hand-authored taxonomy seed: facet axes (D31).

This module is the *source of truth* for the facet-axes controlled vocabulary
that yen-gov uses to validate ``dimension_values`` keys on parent indicator
catalogue rows (see ``docs/architecture/data/canonical-store.md`` §6 — facet
axes registry / D31). It supersedes ``datasets/taxonomy/facet-axes.json`` and
``datasets/schemas/facet-axes.schema.json`` (both retired in PR-Q.2,
2026-05-19).

**Why a Python module instead of JSON/YAML?** See TODO row 1.8d-ii §B-§D for
the full persona debate; condensed:

* Pydantic models validate the ``FACET_AXES`` literal at import time, so a
  typo in a ``value_id`` raises ``ValidationError`` *before* any parquet
  write — type checking without needing mypy/Ruff configured.
* Rationale comments (``# why CSS vs CS — see 15th FC ch. 11``) sit next
  to the value they explain, just like YAML side-comments.
* OWID precedent: ``etl/data_helpers/geo.py`` ships ``REGIONS`` and
  ``INCOME_GROUPS`` as Python dict literals for exactly this pattern
  (typed registry constants, distinct from per-dataset metadata which OWID
  ships as YAML). See CLAUDE.md §0a (OWID is the canonical reference).

**Migration cost**: zero lock-in. The data shape (axes-with-values) is the
contract; the format is packaging. Switching to YAML/JSON/SQL later is a
~half-day mechanical refactor — replace the ``FACET_AXES = [...]`` literal
with ``FACET_AXES = [FacetAxis(**raw) for raw in load_yaml(path)]`` and
export the current list via ``yaml.safe_dump([a.model_dump() for a in
FACET_AXES])``. Reversible with one revert.

**On-disk shape** (denormalized one row per ``(axis_id, value_id)``):

    axis_id : VARCHAR
    axis_label : VARCHAR
    axis_description : VARCHAR
    allow_compute_on_read_total : BOOLEAN
    value_id : VARCHAR
    value_label : VARCHAR
    value_description : VARCHAR (nullable)
    deprecated : BOOLEAN

Chosen over a nested LIST<STRUCT> shape because DuckDB-WASM facet pickers
in the frontend (Phase 2 Energy onward) want one ``FROM`` clause and
``SELECT DISTINCT axis_id, axis_label`` trivially recovers the parent
shape when needed.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
from pydantic import BaseModel, ConfigDict, Field

# Bumped independently of the retired facet-axes.schema.json (which targeted
# the nested JSON shape). 1.0 = initial denormalized parquet contract.
FACET_AXES_ROW_SCHEMA_VERSION = "1.0"

FACET_AXES_PARQUET_COLUMNS = (
    "axis_id",
    "axis_label",
    "axis_description",
    "allow_compute_on_read_total",
    "value_id",
    "value_label",
    "value_description",
    "deprecated",
)


class FacetAxisValue(BaseModel):
    """One allowed value within a facet axis.

    ``value_id`` is the literal that appears in indicator-catalogue
    ``dimension_values`` STRUCT entries (e.g. ``"coal"``,
    ``"solar_utility"``). ``label`` is the citizen-readable string the
    renderer puts in legends. ``description`` is an optional editorial
    note (e.g. methodology caveat). ``deprecated=True`` grandfathers a
    value: existing rows stay legal but no new ingest should use it; the
    catalogue validator (when wired in Phase 2) warns but does not reject.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$", max_length=40)
    label: str = Field(min_length=1)
    description: str | None = None
    deprecated: bool = False


class FacetAxis(BaseModel):
    """One faceting axis (e.g. ``fuel_type``, ``head_of_account``).

    ``axis_id`` is the STRUCT key on parent indicator-catalogue rows.
    ``label`` and ``description`` carry the citizen-readable framing.
    ``allow_compute_on_read_total`` (per D33.8) — when True, the
    renderer MAY synthesise a ``"total"`` row via SUM/GROUP BY over the
    children; when False, a published total was authoritative and must
    be carried as its own indicator (not derived from sub-values).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    axis_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    description: str = Field(min_length=10)
    allow_compute_on_read_total: bool
    values: list[FacetAxisValue] = Field(min_length=1)


# ---------------------------------------------------------------------------
# THE REGISTRY (hand-authored — Hans + Max sign-off per TODO 1.8d-ii §D).
# Ported verbatim from datasets/taxonomy/facet-axes.json v1.0 (2026-05-18).
# Add new axes by appending a FacetAxis literal here in the same PR as the
# indicator-catalogue rows that use the axis. Per-axis rationale comments
# document the editorial choice and any Hans/Max sign-off date.
# ---------------------------------------------------------------------------

FACET_AXES: list[FacetAxis] = [
    FacetAxis(
        axis_id="fuel_type",
        label="Fuel type",
        description=(
            "Energy source for generation / consumption indicators (installed "
            "capacity, generation MU, primary energy supply). Children of a "
            "parent like 'state-installed-capacity-mw' carry one of these values."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="coal", label="Coal"),
            FacetAxisValue(value_id="lignite", label="Lignite"),
            FacetAxisValue(value_id="gas", label="Natural gas"),
            FacetAxisValue(value_id="diesel", label="Diesel"),
            FacetAxisValue(
                value_id="oil",
                label="Oil",
                description=(
                    "Primary-energy crude-oil + petroleum-products aggregate "
                    "(distinct from `diesel` which is a refined-product cut). "
                    "Used by `india-primary-energy-supply-mtoe-oil` (PR-U). "
                    "Publisher label `oil` maps 1:1; no SUB_FUEL_TO_CANONICAL "
                    "collapse step."
                ),
            ),
            FacetAxisValue(value_id="nuclear", label="Nuclear"),
            FacetAxisValue(value_id="hydro", label="Large hydro"),
            FacetAxisValue(
                value_id="solar",
                label="Solar (all)",
                description=(
                    "Combined utility + rooftop. Split via solar_utility / "
                    "solar_rooftop when adapter resolves the breakdown."
                ),
            ),
            FacetAxisValue(value_id="solar_utility", label="Solar (utility scale)"),
            FacetAxisValue(value_id="solar_rooftop", label="Solar (rooftop)"),
            FacetAxisValue(value_id="wind", label="Wind"),
            FacetAxisValue(value_id="biomass", label="Biomass"),
            FacetAxisValue(value_id="small_hydro", label="Small hydro"),
            FacetAxisValue(value_id="waste_to_energy", label="Waste-to-energy"),
            FacetAxisValue(value_id="renewable_other", label="Other renewables"),
            FacetAxisValue(
                value_id="renewable",
                label="Renewables (aggregate)",
                description=(
                    "Top-level renewables aggregate (used when publisher emits "
                    "a single RE bucket instead of breaking into solar / wind / "
                    "biomass etc). Publisher label `renewables` (plural) collapses "
                    "to canonical `renewable` (singular) per indicator-naming.md. "
                    "Used by `india-primary-energy-supply-mtoe-renewable` (PR-U)."
                ),
            ),
            FacetAxisValue(
                value_id="hybrid_bundled",
                label="Hybrid (bundled)",
                description=(
                    "Bundled hybrid PPAs (e.g. wind + solar + storage sold as "
                    "one contract). A procurement-channel category rather than "
                    "a pure fuel; carried on the fuel_type axis for renderer "
                    "reuse. Used by `state-power-purchase-share-pct-hybrid-bundled` "
                    "(PR-W). No SUB_FUEL_TO_CANONICAL collapse target -- the "
                    "bundle is irreducible at publisher grain."
                ),
            ),
            FacetAxisValue(
                value_id="trading_other",
                label="Trading and others",
                description=(
                    "Electricity bought via power exchanges (IEX / PXIL) or "
                    "unscheduled-interchange (UI) mechanisms -- source-agnostic "
                    "at procurement time. A procurement-channel category rather "
                    "than a pure fuel; carried on the fuel_type axis for "
                    "renderer reuse. Used by "
                    "`state-power-purchase-share-pct-trading-other` (PR-W)."
                ),
            ),
        ],
    ),
    FacetAxis(
        axis_id="sector",
        label="Sector",
        description=(
            "End-use / industry sector. Distinct from head_of_account "
            "(fiscal-classification axis) and from category (citizen-facing "
            "rollup). Used for electricity-consumption-by-sector, "
            "GVA-by-industry, employment-by-sector."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="agriculture", label="Agriculture"),
            FacetAxisValue(value_id="industry", label="Industry"),
            FacetAxisValue(value_id="manufacturing", label="Manufacturing"),
            FacetAxisValue(value_id="services", label="Services"),
            FacetAxisValue(value_id="domestic", label="Domestic / residential"),
            FacetAxisValue(value_id="commercial", label="Commercial"),
            FacetAxisValue(value_id="transport", label="Transport"),
            FacetAxisValue(value_id="construction", label="Construction"),
            FacetAxisValue(value_id="mining", label="Mining and quarrying"),
            FacetAxisValue(value_id="public_admin", label="Public administration"),
        ],
    ),
    FacetAxis(
        axis_id="head_of_account",
        label="Head of account",
        description=(
            "Fiscal-classification axis for revenue / expenditure indicators "
            "(constitutional split — revenue vs capital, plan vs non-plan). "
            "Citizen-readable framing; not raw COFOG codes."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="revenue_receipts", label="Revenue receipts"),
            FacetAxisValue(value_id="capital_receipts", label="Capital receipts"),
            FacetAxisValue(value_id="revenue_expenditure", label="Revenue expenditure"),
            FacetAxisValue(value_id="capital_expenditure", label="Capital expenditure"),
            FacetAxisValue(value_id="fiscal_deficit", label="Fiscal deficit"),
            FacetAxisValue(value_id="revenue_deficit", label="Revenue deficit"),
            FacetAxisValue(value_id="primary_deficit", label="Primary deficit"),
        ],
    ),
    FacetAxis(
        axis_id="transfer_type",
        label="Centre-to-state transfer type",
        description=(
            "Per Finance Commission framework: tax devolution vs grants-in-aid "
            "vs centrally sponsored schemes (CSS) vs central sector schemes (CS). "
            "Critical for centre-vs-state attribution per Hans governance lens."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="tax_devolution", label="Tax devolution (Article 270)"),
            FacetAxisValue(value_id="grants_in_aid", label="Grants-in-aid (Article 275 / FC awards)"),
            # CSS vs CS — distinct funding-share regimes; CSS is centre-state
            # cost-sharing (~60:40 typical), CS is 100% centre-funded.
            # See 15th FC ch. 11 for the canonical framing.
            FacetAxisValue(value_id="css", label="Centrally sponsored schemes"),
            FacetAxisValue(value_id="cs", label="Central sector schemes"),
            FacetAxisValue(value_id="finance_commission_grants", label="Finance Commission grants"),
            FacetAxisValue(value_id="special_assistance", label="Special assistance / loans"),
        ],
    ),
    FacetAxis(
        axis_id="gender",
        label="Gender",
        description=(
            "Citizen-readable gender split for demographic / labour / NFHS-style "
            "indicators. 'transgender' included when the source publishes it "
            "(Census 2011 onwards); rendered alongside, never aggregated into "
            "'other'."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="male", label="Male"),
            FacetAxisValue(value_id="female", label="Female"),
            FacetAxisValue(
                value_id="transgender",
                label="Transgender",
                description=(
                    "Census 2011 introduced this category; earlier vintages do "
                    "not publish it."
                ),
            ),
        ],
    ),
    FacetAxis(
        axis_id="residence",
        label="Residence",
        description=(
            "Rural vs urban split. Census-canonical definition; the publisher's "
            "rural/urban classification is preserved verbatim (different surveys "
            "use slightly different boundaries — NSO vs Census vs NFHS)."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="rural", label="Rural"),
            FacetAxisValue(value_id="urban", label="Urban"),
        ],
    ),
    FacetAxis(
        axis_id="prices_basis",
        label="Prices basis",
        description=(
            "Constant-prices vs current-prices for GVA / GSDP / consumption "
            "indicators. Per D33.1 — base-year revisions for constant-prices "
            "series get methodology_version + visible break marker per D32."
        ),
        allow_compute_on_read_total=False,
        values=[
            FacetAxisValue(value_id="current", label="Current prices"),
            FacetAxisValue(
                value_id="constant",
                label="Constant prices",
                description=(
                    "Always paired with a base-year via methodology_version "
                    "(e.g. 'gsdp-base-2011-12')."
                ),
            ),
        ],
    ),
    FacetAxis(
        axis_id="methodology_version",
        label="Methodology version",
        description=(
            "FK back to methodology-breaks.json. Per D28 — composes with "
            "id-encoded breaks in D30. Lets a parent indicator carry siblings "
            "on different methodology vintages with the chart rendering "
            "visible vertical break markers per D32."
        ),
        allow_compute_on_read_total=False,
        values=[
            FacetAxisValue(value_id="gsdp-base-2011-12", label="GSDP base 2011-12 (NAS)"),
            FacetAxisValue(
                value_id="gsdp-base-2004-05",
                label="GSDP base 2004-05 (NAS — deprecated)",
                deprecated=True,
            ),
            FacetAxisValue(value_id="cpi-base-2012", label="CPI base 2012"),
            FacetAxisValue(value_id="iip-base-2011-12", label="IIP base 2011-12"),
            FacetAxisValue(value_id="census-2011-frame", label="Census 2011 sampling frame"),
            FacetAxisValue(value_id="nfhs-5-frame", label="NFHS-5 (2019-21) sampling frame"),
        ],
    ),
    FacetAxis(
        axis_id="category",
        label="Social category",
        description=(
            "SC / ST / OBC / general split for indicators that publish this "
            "break (SECC, NFHS, NSO labour, education enrollment). The "
            "aggregation rule is publisher-specific (some publish 'others' as "
            "residual, some publish all four; the adapter preserves the "
            "published shape)."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="sc", label="Scheduled Caste"),
            FacetAxisValue(value_id="st", label="Scheduled Tribe"),
            FacetAxisValue(value_id="obc", label="Other Backward Classes"),
            FacetAxisValue(value_id="general", label="General"),
            FacetAxisValue(value_id="others", label="Others (publisher residual)"),
        ],
    ),
    FacetAxis(
        axis_id="crime_category",
        label="Crime category",
        description=(
            "Citizen-readable rollup of NCRB crime categories. Sub-categories "
            "within IPC vs SLL preserved separately so the user can drill from "
            "category to subhead without losing the IPC/SLL distinction."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="ipc_total", label="IPC crimes (total)"),
            FacetAxisValue(value_id="sll_total", label="SLL crimes (total)"),
            FacetAxisValue(value_id="crimes_against_women", label="Crimes against women"),
            FacetAxisValue(value_id="crimes_against_children", label="Crimes against children"),
            FacetAxisValue(value_id="crimes_against_sc", label="Crimes against SC"),
            FacetAxisValue(value_id="crimes_against_st", label="Crimes against ST"),
            FacetAxisValue(value_id="economic_offences", label="Economic offences"),
            FacetAxisValue(value_id="cyber_crimes", label="Cyber crimes"),
        ],
    ),
    FacetAxis(
        axis_id="cpi_category",
        label="CPI category",
        description=(
            "Per D33.7 — CPI sub-indices including combined_yoy as a facet "
            "value alongside food/fuel/housing/general. Aggregates published "
            "by the source, NEVER re-derived from sub-indices."
        ),
        allow_compute_on_read_total=False,
        values=[
            FacetAxisValue(value_id="general", label="CPI General"),
            FacetAxisValue(
                value_id="combined_yoy",
                label="CPI Combined (YoY)",
                description=(
                    "Headline YoY combined CPI as published by MoSPI/RBI — "
                    "first-class facet, not derived."
                ),
            ),
            FacetAxisValue(value_id="food", label="CPI Food and beverages"),
            FacetAxisValue(value_id="fuel", label="CPI Fuel and light"),
            FacetAxisValue(value_id="housing", label="CPI Housing"),
            FacetAxisValue(value_id="clothing", label="CPI Clothing and footwear"),
            FacetAxisValue(value_id="miscellaneous", label="CPI Miscellaneous"),
            FacetAxisValue(value_id="core", label="CPI Core (excl. food + fuel)"),
        ],
    ),
    FacetAxis(
        axis_id="loss_type",
        label="Distribution loss type",
        description=(
            "Per D33.2 — one parent indicator 'state-distribution-losses-pct' "
            "faceted by loss-measurement methodology. AT&C is the default "
            "(aggregate technical and commercial); T&D is the legacy measure; "
            "distribution-only is the narrow technical subset."
        ),
        allow_compute_on_read_total=False,
        values=[
            FacetAxisValue(
                value_id="at_and_c",
                label="AT&C loss",
                description=(
                    "Aggregate Technical and Commercial loss (default; PFC "
                    "discom dashboard canonical)."
                ),
            ),
            FacetAxisValue(
                value_id="t_and_d",
                label="T&D loss",
                description="Transmission and Distribution loss (legacy; pre-AT&C era).",
            ),
            FacetAxisValue(value_id="distribution_only", label="Distribution-only technical loss"),
        ],
    ),
    FacetAxis(
        axis_id="allocation_basis",
        label="Allocation basis (geographic vs contractual)",
        description=(
            "Open question Q1 flagged in migration ledger §5 — used by CEA "
            "installed capacity (geographical-sited vs contractually-allocated "
            "share). Registered now so the energy ingest in Phase 2 has the "
            "surface; the canonical decision (whether to consolidate or keep "
            "as two parents) is owned by Max + Hans."
        ),
        allow_compute_on_read_total=False,
        values=[
            FacetAxisValue(
                value_id="geographical",
                label="Geographically sited",
                description=(
                    "Capacity physically located in the entity (where_produced "
                    "framing)."
                ),
            ),
            FacetAxisValue(
                value_id="contractual",
                label="Contractually allocated",
                description=(
                    "Entity's allocated SHARE of central-sector / pooled "
                    "capacity (where_allocated framing). Per "
                    "D-attribution-geography clarification 4.2."
                ),
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # P.1.B (DISCOM finance + demand/supply lift).
    # ------------------------------------------------------------------
    FacetAxis(
        axis_id="efficiency_dimension",
        label="Distribution efficiency dimension",
        description=(
            "Decomposes overall distribution efficiency into its three "
            "ICED-published sub-indicators: billing efficiency, collection "
            "efficiency, and T&D loss. The first two multiply (after "
            "rescaling) to give the commercial half of AT&C losses; the "
            "third is the technical half. allow_compute_on_read_total is "
            "False because percentages are not additive across dimensions."
        ),
        allow_compute_on_read_total=False,
        values=[
            FacetAxisValue(
                value_id="billing",
                label="Billing efficiency",
                description=(
                    "Share of energy actually billed to a consumer, out of "
                    "total energy input to the distribution system. "
                    "100% = every kWh that enters the grid was billed."
                ),
            ),
            FacetAxisValue(
                value_id="collection",
                label="Collection efficiency",
                description=(
                    "Share of billed revenue actually collected from "
                    "consumers. 100% = every rupee billed was paid."
                ),
            ),
            FacetAxisValue(
                value_id="td_loss",
                label="T&D loss",
                description=(
                    "Transmission and Distribution loss as % of energy "
                    "input -- the technical half of AT&C losses (heat / "
                    "ageing / unmetered consumption losses on the wires)."
                ),
            ),
        ],
    ),
    FacetAxis(
        axis_id="rpo_segment",
        label="RPO compliance segment",
        description=(
            "Three-segment decomposition of state Renewable Purchase "
            "Obligation compliance: solar (solar-specific RPO target), "
            "non-solar (other-renewables RPO target), total (combined). "
            "Targets and compliance are reported separately by ICED for "
            "each segment; the total is NOT the sum of the parts (it is "
            "the combined-target compliance ratio), so "
            "allow_compute_on_read_total is False."
        ),
        allow_compute_on_read_total=False,
        values=[
            FacetAxisValue(
                value_id="solar",
                label="Solar RPO",
                description=(
                    "Compliance with the solar-specific portion of the "
                    "state's Renewable Purchase Obligation target."
                ),
            ),
            FacetAxisValue(
                value_id="non_solar",
                label="Non-solar RPO",
                description=(
                    "Compliance with the non-solar (wind + biomass + "
                    "small-hydro) portion of the state's RPO target. "
                    "Legacy shard uses the hyphenated label 'non-solar' "
                    "on its `facet` field; the canonical value_id uses "
                    "snake_case per the facet-axes value_id regex."
                ),
            ),
            FacetAxisValue(
                value_id="total",
                label="Total RPO",
                description=(
                    "Combined-target RPO compliance (NOT the sum of solar "
                    "+ non-solar -- the combined target is its own "
                    "regulatory ratio)."
                ),
            ),
        ],
    ),
    FacetAxis(
        axis_id="species",
        label="Livestock species",
        description=(
            "Animal species axis for NDLM (National Digital Livestock "
            "Mission, Bharat Pashudhan) indicators. Closed enum of 10 "
            "species NDLM publishes per district per vintage. The parent "
            "indicator (e.g. ``district-pashu-aadhaar-count``) is "
            "compute-on-read: its value is the sum of all 10 species "
            "children, per Hans D33.8 convention. A future vintage that "
            "adds an 11th species MUST extend this enum AND the indicator "
            "catalogue in lockstep."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="cattle",  label="Cattle"),
            FacetAxisValue(value_id="buffalo", label="Buffalo"),
            FacetAxisValue(value_id="yak",     label="Yak"),
            FacetAxisValue(value_id="mithun",  label="Mithun"),
            FacetAxisValue(value_id="sheep",   label="Sheep"),
            FacetAxisValue(value_id="goat",    label="Goat"),
            FacetAxisValue(value_id="pig",     label="Pig"),
            FacetAxisValue(value_id="horse",   label="Horse"),
            FacetAxisValue(value_id="donkey",  label="Donkey"),
            FacetAxisValue(value_id="mule",    label="Mule"),
        ],
    ),
    FacetAxis(
        axis_id="landholding",
        label="Land-holding bracket",
        description=(
            "Self-declared agricultural land holding axis for NDLM Owner "
            "Registration (Bharat Pashudhan). Closed enum of 6 brackets "
            "the publisher emits per district per vintage: "
            "landless_marginal (<1 Ha), small (1.0-1.99 Ha), semi_medium "
            "(2.0-3.99 Ha), medium (4.0-9.99 Ha), large (>=10 Ha), and "
            "not_specified (registrations without a declared bracket). "
            "The parent indicator (``district-livestock-owner-reg-count``) "
            "is compute-on-read per Hans D33.8 - its value is the SUM of "
            "all 6 brackets. Bracket definitions follow the Agriculture "
            "Census 2015-16 categorisation; a future vintage that rebases "
            "the brackets MUST extend this enum AND mark the prior set "
            "deprecated rather than mutating in place."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(
                value_id="landless_marginal",
                label="Landless / marginal (<1 Ha)",
            ),
            FacetAxisValue(
                value_id="small",
                label="Small (1.0-1.99 Ha)",
            ),
            FacetAxisValue(
                value_id="semi_medium",
                label="Semi-medium (2.0-3.99 Ha)",
            ),
            FacetAxisValue(
                value_id="medium",
                label="Medium (4.0-9.99 Ha)",
            ),
            FacetAxisValue(
                value_id="large",
                label="Large (>=10 Ha)",
            ),
            FacetAxisValue(
                value_id="not_specified",
                label="Not specified",
                description=(
                    "Registrations without a declared land-holding "
                    "bracket; preserved verbatim rather than imputed."
                ),
            ),
        ],
    ),
    FacetAxis(
        axis_id="oil_product",
        label="Oil product",
        description=(
            "Refined petroleum product axis for state-wise oil-consumption "
            "indicators (NITI Aayog ICED /energy/fuel-sources/oil/ "
            "consumptionStateProductTrend). Closed enum of 7 products the "
            "publisher emits per state per fiscal year. The parent indicator "
            "(``state-oil-product-consumption-kt``) is compute-on-read per "
            "Hans D33.8 - its value is the SUM of all 7 product children. "
            "Unlike the fuel_type axis there is no publisher-sub-bucket "
            "collapse step; the 7 publisher labels (DIESEL/HSD, PETROL, LPG, "
            "SKO, NAPHTHA, PETROLEUM COKE, OTHERS) map 1:1 onto canonical "
            "value_ids. Diesel dominates national consumption (transport + "
            "agricultural pumps); LPG tracks household-policy coverage (PMUY); "
            "petroleum-coke is a refinery by-product used in cement/glass and "
            "is air-quality-regulated in NCR."
        ),
        allow_compute_on_read_total=True,
        values=[
            FacetAxisValue(value_id="diesel-hsd",     label="Diesel (HSD)"),
            FacetAxisValue(value_id="petrol",         label="Petrol"),
            FacetAxisValue(value_id="lpg",            label="LPG"),
            FacetAxisValue(value_id="kerosene",       label="Kerosene (SKO)"),
            FacetAxisValue(value_id="naphtha",        label="Naphtha"),
            FacetAxisValue(value_id="petroleum-coke", label="Petroleum coke"),
            FacetAxisValue(
                value_id="others",
                label="Others",
                description=(
                    "Publisher catch-all for products that do not fit the "
                    "6 named buckets (e.g. fuel oil, ATF, lubricants); "
                    "preserved verbatim, never imputed into a named bucket."
                ),
            ),
        ],
    ),
]


def _denormalized_rows() -> list[tuple]:
    """Flatten ``FACET_AXES`` into one row per ``(axis_id, value_id)``.

    Column order matches ``FACET_AXES_PARQUET_COLUMNS``. ``value_description``
    is nullable; everything else is non-null.
    """
    rows: list[tuple] = []
    for axis in FACET_AXES:
        for value in axis.values:
            rows.append(
                (
                    axis.axis_id,
                    axis.label,
                    axis.description,
                    axis.allow_compute_on_read_total,
                    value.value_id,
                    value.label,
                    value.description,
                    value.deprecated,
                )
            )
    return rows


def compile_to_parquet(out_path: Path) -> int:
    """Emit the denormalized facet-axes parquet at ``out_path``.

    Returns the number of rows written. Sort order is deterministic
    ``(axis_id, value_id)`` so a re-run with unchanged ``FACET_AXES``
    produces byte-identical output (Holy Law #10 / CLAUDE.md anti-pattern
    "data-row content uses datetime.now()" carve-out).

    Caller is responsible for ensuring ``out_path.parent`` exists.
    """
    out_path = Path(out_path)
    rows = _denormalized_rows()
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE facet_axes (
                axis_id VARCHAR NOT NULL,
                axis_label VARCHAR NOT NULL,
                axis_description VARCHAR NOT NULL,
                allow_compute_on_read_total BOOLEAN NOT NULL,
                value_id VARCHAR NOT NULL,
                value_label VARCHAR NOT NULL,
                value_description VARCHAR,
                deprecated BOOLEAN NOT NULL
            )
            """
        )
        con.executemany(
            "INSERT INTO facet_axes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.execute(
            f"""
            COPY (
                SELECT * FROM facet_axes
                ORDER BY axis_id, value_id
            ) TO '{out_path.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    return len(rows)
