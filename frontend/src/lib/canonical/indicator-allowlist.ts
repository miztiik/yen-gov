// Canonical-backed indicator allowlist (Phase B of P.1.A C4.7).
//
// This module is the single-source-of-truth for which catalogue artifacts
// have already been migrated from the legacy per-shard JSON loader
// (`/data/indicators/in/<topic>/<id>.json`) to a DuckDB-WASM query against
// the canonical Parquet store (`/data/<family>/<table>.parquet`).
//
// Doctrine
// --------
// Phase B intentionally ships as a one-indicator allowlist, not a generic
// "every indicator now reads canonical" refactor. Per
// TODO/20260524-p1a-data-reacquisition-plan.md §3 C4.7, the canonical-aware
// indicator reader is a much larger Level-5 design that earns its own ADR
// and a panel decision (Hans + Max + Gregor) on the canonical-back flag
// column for `taxonomy/indicators.parquet`. Until then, we add indicators
// to the allowlist one at a time as each P.* phase ships its FE
// reader-switch sub-PR.
//
// Two descriptor shapes (PR 7c.5)
// -------------------------------
// 1. `kind: "single"` — the legacy shard maps 1:1 to a single canonical
//    `indicator_id` in one fact-table. The adapter issues one SQL query
//    filtered by `indicator_id = '<canonical_indicator_id>'` and emits
//    one row per (entity, period). This is the PR 7a / 7c.5-simple shape.
//
// 2. `kind: "facet-multiplexed"` — the legacy shard emitted ONE artifact
//    file with a `rows[].facet` field discriminating N citizen-readable
//    segments (e.g. RPO compliance with `solar` / `non-solar` / `total`).
//    The canonical store materialises each segment as a separate
//    `indicator_id` child of a compute-on-read parent (e.g.
//    `state-rpo-compliance-pct-solar` etc., parented by
//    `state-rpo-compliance-pct` which carries `source_id = null` per
//    indicator-naming.md D29). The adapter issues ONE SQL query
//    `WHERE indicator_id IN (<child_1>, <child_2>, …)`, fuses the rows
//    into one `IndicatorArtifact` with `rows[].facet =
//    <legacy_facet_label>` (the legacy hyphenated display form, NOT the
//    canonical snake_case `value_id`), and reports `indicator.id =
//    canonical_parent_indicator_id`. Provenance and temporal coverage
//    derive from the CHILD rows; the parent row carries no observations
//    and no source_id.
//
//    Gregor note (canonical-rename slugs): the legacy `topics.json`
//    artifact slug is the unmigrated kebab-snake hybrid (e.g.
//    `energy/state_rpo_compliance_pct`); the canonical store names
//    differ both in shape (kebab `state-rpo-compliance-pct`) and
//    sometimes in unit-suffix or basis-suffix (e.g.
//    `state_electricity_generation_mu` -> `state-electricity-generation-gwh`,
//    `state_distribution_billing_efficiency_pct` ->
//    `state-distribution-efficiency-pct-billing` flips the modifier
//    order). The allowlist is the single source of truth for these
//    renames; until the catalogue regenerates topics.json against the
//    canonical taxonomy (a Level-5 chore deferred behind the canonical
//    reader ADR), this file is the rename ledger.
//
// Adding a new entry
// ------------------
// 1. Verify the canonical fact-table carries the indicator: query
//    `read_parquet('datasets/<family>/<table>.parquet')` with the
//    `indicator_id` filter; assert non-zero rows.
// 2. Verify the manifest entry exists for `<family>.<table>`.
// 3. Hand-author the IndicatorMeta block. Cite the canonical
//    taxonomy/indicators.parquet row as the citizen-facing label
//    source; do NOT copy verbatim from the soon-to-retire legacy shard
//    metadata (the canonical metadata is what Hans/Max designed for the
//    long-arc, multi-year citizen surface).
// 4. Add an entry to `CANONICAL_BACKED_INDICATORS`.
// 5. Update the per-entry vitest assertions in
//    `indicator-from-canonical.test.ts`.
// 6. §13 browser-smoke every state page that mounts the IndicatorCard
//    for this artifact before merging.

import type { IndicatorMeta } from "../indicators";

interface CanonicalIndicatorDescriptorBase {
  /** Legacy catalogue artifact id (e.g. `energy/state_peak_electricity_demand_mw`). */
  legacy_artifact_id: string;
  /** Manifest table id (e.g. `energy.energy_demand_supply`). */
  table_id: string;
  /** Static IndicatorMeta block — what the citizen sees as the card header.
   *  Source: `datasets/taxonomy/indicators.parquet` row for the descriptor's
   *  canonical (single) or parent (facet-multiplexed) `indicator_id`. */
  meta: IndicatorMeta;
  /** Optional citizen-readable caveats surfaced by `AboutThisData.svelte`'s
   *  "Known caveats" section. One bullet per entry; keep each <= ~180 chars.
   *  Use this to lift mid-paragraph honesty cues out of `meta.description`
   *  / `meta.notes` into a discrete, scannable list (e.g. the RPO `total`
   *  segment is NOT the sum of solar + non-solar). Adapter copies these
   *  into the rebuilt artifact's `methodology.known_caveats[]`. */
  caveats?: ReadonlyArray<string>;
}

export interface CanonicalSingleIndicatorDescriptor
  extends CanonicalIndicatorDescriptorBase {
  kind: "single";
  /** Canonical fact-table `indicator_id` (kebab-case per indicator-naming.md D30). */
  canonical_indicator_id: string;
}

/** One legacy-shard facet → one canonical child indicator_id mapping.
 *  `legacy_facet_label` MUST be the legacy hyphenated display form (e.g.
 *  `"non-solar"`), NOT the canonical snake_case `value_id` from
 *  `taxonomy/facet-axes.parquet` (`"non_solar"`). The IndicatorCard's
 *  facet-picker reads the legacy label verbatim. */
export interface CanonicalFacetMapping {
  canonical_child_id: string;
  legacy_facet_label: string;
}

export interface CanonicalFacetMultiplexedDescriptor
  extends CanonicalIndicatorDescriptorBase {
  kind: "facet-multiplexed";
  /** Parent indicator_id in `taxonomy/indicators.parquet` (compute-on-read;
   *  `source_id = null` per indicator-naming.md D29). The renderer reports
   *  this as `indicator.id` on the fused artifact. */
  canonical_parent_indicator_id: string;
  /** Facet-axis id from `taxonomy/facet-axes.parquet` (e.g. `rpo_segment`).
   *  Carried for downstream tooling — the adapter itself ignores it
   *  because the facet label is already pre-baked on each mapping row. */
  facet_axis_id: string;
  /** Ordered list of child indicator_ids and their legacy facet labels. */
  facet_values: ReadonlyArray<CanonicalFacetMapping>;
}

export type CanonicalIndicatorDescriptor =
  | CanonicalSingleIndicatorDescriptor
  | CanonicalFacetMultiplexedDescriptor;

export const CANONICAL_BACKED_INDICATORS: ReadonlyArray<CanonicalIndicatorDescriptor> = [
  // C4.7 Phase B — peak electricity demand (RBI Handbook Table 142 FY13–FY24
  // + NITI ICED state-wise deep-dive FY25 extension; 430 rows, 35 entities).
  // See TODO/20260524-p1a-data-reacquisition-plan.md §3 C4.7 Phase A status.
  {
    kind: "single",
    legacy_artifact_id: "energy/state_peak_electricity_demand_mw",
    canonical_indicator_id: "state-peak-electricity-demand-mw",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "state-peak-electricity-demand-mw",
      title: "State-wise peak power demand (MW)",
      description:
        "Highest single-instant electricity demand observed in the state during the fiscal year (MW). 'Peak' is system-wide simultaneous demand recorded by the State Load Despatch Centre — typically a summer afternoon (north / west) or winter evening (Punjab, Delhi).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      short_unit: "MW",
      icon: "activity",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "RBI Handbook of Statistics on Indian States 2024-25 edition, Table 142 (FY13–FY24). NITI Aayog ICED state-wise deep-dive (FY25 extension). Originating data: Central Electricity Authority, Ministry of Power.",
      notes:
        "Read alongside Peak Supplied (state-peak-electricity-supplied-mw) — the gap is the unmet peak demand, more operationally critical than the energy-deficit % because shortages force load-shedding. RBI Handbook relabelled 'Surplus / Deficit' to 'Demand Not Met' from FY 2019-20 onwards; underlying definition is unchanged.",
    },
    caveats: [
      "Peak demand is the highest single-instant load observed — a one-hour summer evening spike, not an average. A state can have a high peak yet a moderate annual energy requirement.",
      "Read against state-peak-electricity-supplied-mw: the gap is unmet demand that forced load-shedding. A rising peak with a rising gap is a worse signal than a rising peak alone.",
      "RBI Handbook relabelled 'Surplus/Deficit' to 'Demand Not Met' from FY 2019-20; the column name changes but the underlying definition does not — do not read the rename as a methodology break.",
    ],
  },

  // PR-F (2026-05-25) — close 4 /t/energy 404s flagged by user smoke.
  // The legacy topics.json energy block references THREE short-name shards
  // that have no allowlist route + ONE meadow-only orphan; this PR adds 2
  // allowlist entries (peak_met → state-peak-electricity-supplied-mw,
  // per_capita_consumption_kwh → state-per-capita-electricity-consumption-kwh)
  // and the matching topics.json prune drops 2 entries (state_peak_demand_mw
  // duplicate of state_peak_electricity_demand_mw, state_renewable_grid_capacity_mw
  // subsumed-by-renewable-child orphan).
  //
  // Meta blocks sourced verbatim from datasets/taxonomy/indicators.json
  // rows 1337-1366 per the allowlist authoring doctrine (lines 47-75).

  // --- Peak supplied (Peak Met, RBI Handbook Table 142 Peak Met column) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_peak_met_mw",
    canonical_indicator_id: "state-peak-electricity-supplied-mw",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "state-peak-electricity-supplied-mw",
      title: "State-wise peak power supplied (MW)",
      description:
        "Maximum instantaneous power actually supplied in the state during the fiscal year (MW). The pair (peak_demand, peak_supplied) tells the load-shedding story: supplied < demand in any year means the grid dropped load to keep frequency stable.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "MW",
      short_unit: "MW",
      icon: "zap",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "RBI Handbook of Statistics on Indian States 2024-25 edition, Table 142 (Peak Met column). Originating data: Central Electricity Authority.",
      notes:
        "India's all-India peak deficit fell from ~12% in FY05 to under 1% from FY18 onwards, but state-level shortfalls persist — Bihar, UP, Punjab, J&K, and Andhra Pradesh routinely under-met their own peak in the FY13-FY25 window.",
    },
  },

  // --- Per-capita consumption (ICED state-wise composition; distinct from Per-capita availability) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_per_capita_electricity_consumption_kwh",
    canonical_indicator_id: "state-per-capita-electricity-consumption-kwh",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "state-per-capita-electricity-consumption-kwh",
      title: "Electricity used per person (kWh/year)",
      description:
        "Electricity consumption per person per year, in kilowatt-hours. Proxy for BOTH energy access (electrified homes) AND industrial intensity (heavy-industry load) — read alongside per-capita income to disambiguate.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "rate",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "kWh per person per year",
      icon: "zap",
      attribution_geography: "where_consumed",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "ICED composition: state electricity sales (CEA) divided by state population (Census 2011 + linear projection).",
      notes:
        "A high value can mean many electrified domestic consumers (Kerala) OR a heavy-industry economy (Chhattisgarh, Odisha) OR both (Gujarat). A low value can mean a rural agrarian economy (Bihar, Assam) OR poor access (UP). The denominator (population) is Census 2011 + projection, so values for the 2020s are subject to mid-decade re-basing once Census 2027 data lands. Note: distinct from per-capita availability (RBI Handbook T138) — availability is power DELIVERED to the state (including T&D + commercial losses); consumption is power actually BILLED to end-users.",
    },
    caveats: [
      "'Per person' includes industrial + agricultural pumping, not just households. Gujarat's high number is Surat-Vapi industrial corridors; Punjab's is subsidised tubewell electricity. Household-only readings are 2-3x lower.",
      "Denominator is Census 2011 population projected forward. Values for the 2020s will be re-based once Census 2027 lands; expect a downward revision for high-migration states.",
      "This is electricity BILLED to end-users, not electricity DELIVERED to the state. Power lost to theft and unbilled use (the AT&C gap) is excluded from the numerator.",
    ],
  },

  // PR-G (2026-05-25) — close the 5 remaining /t/energy 404s discovered
  // during PR-F's §13 smoke. The legacy energy topics.json block lists
  // 5 shards with no allowlist route:
  //   1. state_electricity_sales_mu        → state-electricity-sales-mu (single)
  //   2. state_atc_losses_pct              → state-atc-losses-pct (single)
  //   3. state_installed_capacity_by_source_mw      → state-installed-capacity-geographical-mw (facet-multiplexed by fuel_type)
  //   4. state_electricity_generation_by_source_gwh → state-electricity-generation-gwh (facet-multiplexed by fuel_type)
  //   5. state_installed_capacity_total_mw → Pattern B duplicate of
  //      state_installed_capacity_with_alloc_mw (already routes to
  //      state-installed-capacity-allocated-mw via entry #7). PR #222
  //      spliced both legacy shards into one canonical FY05-FY25 series;
  //      having two topics.json cards for the same data is citizen-noise.
  //      This PR PRUNES (5) from topics.json rather than aliasing it,
  //      matching the PR-F precedent (state_peak_demand_mw prune).
  //
  // Adapter wiring confirmed:
  //   * distribution.py block 1 (line 87) emits state-atc-losses-pct
  //   * distribution.py block 2 (line 102) emits state-electricity-sales-mu
  //   * generation.py block 2 (line 77) emits state-electricity-generation-gwh-{fuel}
  //   * installed_capacity.py block 3 (line 144) emits state-installed-capacity-geographical-mw + -{fuel} children
  //
  // Meta blocks sourced verbatim from datasets/taxonomy/indicators.json
  // per the allowlist authoring doctrine (lines 47-75). Children for the
  // two facet-multiplexed parents enumerate the 5 canonical fuel buckets
  // (coal/gas/hydro/nuclear/renewable) that the backend adapter collapses
  // each ICED sub-fuel category into.

  // --- PR-G 1: Annual electricity sales (MU), ICED state-wise deep-dive ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_electricity_sales_mu",
    canonical_indicator_id: "state-electricity-sales-mu",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "state-electricity-sales-mu",
      title: "Annual electricity sales (by state, MU)",
      description:
        "Total electricity actually billed to end-consumers (domestic + commercial + industrial + agricultural + public-lighting) in the state, in million units (MU). The gap between Generation and Sales is the absolute AT&C loss.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MU",
      short_unit: "MU",
      icon: "receipt",
      attribution_geography: "where_billed",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED state-wise deep-dive; underlying figures from PFC State Distribution Utilities report. Includes intra-state imports — consumption can exceed in-state generation.",
      notes:
        "Read alongside generation (state-electricity-generation-gwh): generation MINUS sales = absolute AT&C loss. 1 MU (million unit) = 1 GWh; the unit relabel is dimensionally identical.",
    },
    // PR-I (Row 5 PR-1): Hans-curated caveats for the AT&C-decomposition cohort.
    // Sales-MU is the absolute-MU denominator; 3 distribution-efficiency cards
    // (billing / collection / T&D loss) decompose AT&C into commercial + technical halves.
    caveats: [
      "Sales is the absolute MU billed; Generation MINUS Sales = absolute AT&C loss. A state at 80,000 MU sales with 100,000 MU generation has 20% AT&C; pair with generation on this topic to read the gap, not the level.",
      "1 MU = 1 GWh; the unit relabel is dimensionally identical. State energy department dashboards quote MU; CEA quotes GWh; treat as the same number when reconciling Punjab or Tamil Nadu state-PR figures against CEA national tables.",
      "Sales includes intra-state imports, so consumption can exceed in-state generation; Delhi, Goa and Punjab buy heavily from the central pool. Don't read high sales as a proxy for high in-state generation capacity.",
    ],
  },

  // --- PR-G 2: Aggregate Technical & Commercial losses (%), ICED state-wise deep-dive ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_atc_losses_pct",
    canonical_indicator_id: "state-atc-losses-pct",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "state-atc-losses-pct",
      title: "Power lost to leaks and theft (%)",
      description:
        "How much of the power that entered your state's grid never reached a paying meter. 'Technical' losses = grid heat and ageing wires; 'Commercial' losses = theft and uncollected bills. The floor for any future tariff hike.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "%",
      icon: "activity",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED state-wise deep-dive API row 'AT&C Losses'. Calculation method: PFC. Vintage updated annually with PFC report release (typically Q3 FY+1).",
      notes:
        "UDAY (2015) targeted all-India AT&C below 15% by 2018-19; the actual all-India figure has hovered around 15% since then. State-level dispersion is wide — Gujarat / Andhra at ~6-10%, Bihar / J&K at ~25-40%. AT&C = T&D loss + commercial loss; the three sub-components (billing / collection / T&D) are surfaced separately under state-distribution-efficiency-pct.",
    },
    caveats: [
      "AT&C losses bundle technical losses (transmission heat, ageing lines) with commercial losses (theft, unbilled use). A 20% state may be losing mostly to old infrastructure or mostly to theft — the policy fixes differ.",
      "The UDAY reform target was 15% by FY19; the FY25 national average is still around 16%, and only a handful of states (Gujarat, Andhra, Kerala, Himachal) sit consistently below the target.",
      "Reported figures depend on discom metering and billing data. States with weak feeder metering can under-report losses by classifying unmetered agricultural supply as 'consumption' rather than as loss.",
      "Pre-FY18 numbers are UDAY-era self-reports; FY18+ are PFC integrated ratings with stricter denominators. Bihar's drop from 38% to 28% across FY17-FY19 is partly the methodology shift, not the turnaround.",
    ],
  },

  // --- PR-G 3: State installed capacity by fuel (geographical basis) — facet-multiplexed ---
  //   * Legacy shard `state_installed_capacity_by_source_mw.json` carries
  //     ~1815 rows (state × fuel × FY16-FY26). Backend adapter
  //     `installed_capacity.py` block 3 (line 151) collapses ICED's
  //     sub-fuel granularity into 5 canonical buckets keyed on
  //     `dimension_values.fuel_type ∈ {coal,gas,hydro,nuclear,renewable}`.
  //   * Parent `state-installed-capacity-geographical-mw` carries the sum
  //     (entry #6 above already routes the totals-only legacy slug
  //     `state_installed_capacity_geographical_mw` to the SAME parent —
  //     a single big-number card; this faceted entry adds the per-fuel
  //     breakdown view via the FacetPicker primitive shipped in PR-D #277).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_installed_capacity_by_source_mw",
    canonical_parent_indicator_id: "state-installed-capacity-geographical-mw",
    table_id: "energy.energy_installed_capacity",
    facet_axis_id: "fuel_type",
    facet_values: [
      {
        canonical_child_id: "state-installed-capacity-geographical-mw-coal",
        legacy_facet_label: "coal",
      },
      {
        canonical_child_id: "state-installed-capacity-geographical-mw-gas",
        legacy_facet_label: "gas",
      },
      {
        canonical_child_id: "state-installed-capacity-geographical-mw-hydro",
        legacy_facet_label: "hydro",
      },
      {
        canonical_child_id: "state-installed-capacity-geographical-mw-nuclear",
        legacy_facet_label: "nuclear",
      },
      {
        canonical_child_id: "state-installed-capacity-geographical-mw-renewable",
        legacy_facet_label: "renewable",
      },
    ],
    meta: {
      id: "state-installed-capacity-geographical-mw",
      title: "Power plants built, by fuel (MW)",
      description:
        "Total installed capacity physically located in the state, broken out by fuel type. 'Geographical' means every plant counts toward the state where it sits, regardless of who owns it or where the power is dispatched. Read this as 'where the steel-and-concrete sits' — NOT 'where the electricity flows to'.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      short_unit: "MW",
      icon: "factory",
      attribution_geography: "where_produced",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED capacity-metatable rollup of CEA-published station-level capacity; harmonised across fiscal years 2015-16 onwards. Sub-fuels collapsed into 5 canonical buckets (coal / gas / hydro / nuclear / renewable) per indicator-naming.md.",
      notes:
        "For the share-allocated counterpart (rights to output via central-sector PPAs), see state-installed-capacity-allocated-mw. The all-India total equals the allocated total (as it must) but the per-state breakdown diverges sharply for states that import or export power through central PPAs.",
    },
    caveats: [
      "MW = nameplate peak, not energy delivered. Pair with 'Where your state's power comes from' on this page — a 1GW solar plant delivers energy like 200MW of coal would. Compare RUN, not just BUILT.",
      "A plant in Madhya Pradesh may serve Maharashtra under PPAs — 'installed in state' is not 'available to state'. UP draws on Rihand (MP-located); Delhi pulls from Dadri (UP-located).",
      "CEA collapses lignite into 'coal'; solar+wind+biomass into 'renewable'. Tamil Nadu coal absorbs Neyveli lignite; Karnataka renewable bundles wind + solar + biomass. Disaggregated comparison hides the real mix.",
    ],
  },

  // --- PR-G 4: State electricity generation by fuel (GWh) — facet-multiplexed ---
  //   * Legacy shard `state_electricity_generation_by_source_gwh.json` carries
  //     ~1685 rows (state × fuel × FY16-FY26). Backend adapter `generation.py`
  //     block 2 (line 77) collapses ICED sub-fuels into 5 canonical buckets
  //     keyed on `dimension_values.fuel_type`.
  //   * Parent `state-electricity-generation-gwh` carries the sum (entry
  //     #8 from PR 7a already routes the totals-only legacy slug
  //     `state_electricity_generation_mu` to the SAME parent — single
  //     big-number card; this faceted entry adds the per-fuel breakdown
  //     view via the FacetPicker primitive).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_electricity_generation_by_source_gwh",
    canonical_parent_indicator_id: "state-electricity-generation-gwh",
    table_id: "energy.energy_generation",
    facet_axis_id: "fuel_type",
    facet_values: [
      {
        canonical_child_id: "state-electricity-generation-gwh-coal",
        legacy_facet_label: "coal",
      },
      {
        canonical_child_id: "state-electricity-generation-gwh-gas",
        legacy_facet_label: "gas",
      },
      {
        canonical_child_id: "state-electricity-generation-gwh-hydro",
        legacy_facet_label: "hydro",
      },
      {
        canonical_child_id: "state-electricity-generation-gwh-nuclear",
        legacy_facet_label: "nuclear",
      },
      {
        canonical_child_id: "state-electricity-generation-gwh-renewable",
        legacy_facet_label: "renewable",
      },
    ],
    meta: {
      id: "state-electricity-generation-gwh",
      title: "Where your state's power comes from (GWh)",
      description:
        "Per-state actual electricity generated, broken out by fuel type. The delivered counterpart to installed capacity — capacity is potential, generation is what plants actually produced. 1 MU (million unit) = 1 GWh; the unit relabel is dimensionally identical.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "GWh",
      short_unit: "GWh",
      icon: "zap",
      attribution_geography: "where_produced",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED /v1/gen-metatable-data (CEA-sourced upstream). Sub-fuels collapsed into 5 canonical buckets (coal / gas / hydro / nuclear / renewable) per indicator-naming.md.",
      notes:
        "Most-recent fiscal year is partial-year-actuals + forecast and may revise; treat the most-recent two FYs as preliminary. ICED's 'Others' bucket (interstate/central plants pre-allocation) is dropped because it cannot be mapped to a state choropleth honestly. Capacity-generation gap = PLF — coal capacity dominates but generation share is higher (~70%); gas is capacity-rich, generation-poor due to fuel-supply constraints.",
    },
    caveats: [
      "ICED collapses lignite into 'coal' and solar+wind+biomass into 'renewable'. Tamil Nadu's coal line absorbs Neyveli lignite; Karnataka's renewable bundles wind + solar. Disaggregated cross-year compares are unsafe.",
      "CEA and ICED use different cut-off conventions (CEA month-end snapshots vs ICED financial-year-end). A 2% Gujarat coal-share rise between FY19 and FY22 may be a cut-off shift, not new plants.",
      "GWh = energy delivered (capacity x hours run). Pair with 'Power plants built, by fuel' on this page — high coal generation may be many coal plants or few plants run hard. The policy fixes differ.",
    ],
  },

  // ---------------------------------------------------------------------------
  // PR 7a (P.1.A C5 additive reader-switch) — 8 energy descriptors.
  //
  // Reader-replaceable shards routed to their canonical equivalents per the
  // pre-design memo §2 (Fowler) and on-disk verification of legacy shard
  // shapes:
  //   * Shards #1-#5 (`installed_capacity_<fuel>_mw.json`) are per-state SNAPSHOTS
  //     (35 entities × single time `2026-03`), NOT national time-series. Mapped
  //     to `state-installed-capacity-snapshot-mw-<fuel>` (exact 35×1 match);
  //     mapping to `national-installed-capacity-mw-<fuel>` (1×1) would silently
  //     reduce visible data from 35 state rows to 1 national row and was rejected.
  //   * Shard #7 (`state_installed_capacity_with_alloc_mw.json`) carries FY15-FY25
  //     (396 rows); the canonical `state-installed-capacity-allocated-mw` now
  //     carries FY05-FY25 (770 rows) after PR #222 spliced the RBI Handbook
  //     long-arc onto the ICED post-FY15 segment. INTENTIONAL time-window
  //     extension — citizens see MORE data on the canonical path, not less.
  //   * Shard #8 (`state_electricity_generation_mu.json`) uses publisher unit
  //     `MU` (million units); canonical `state-electricity-generation-gwh` uses
  //     `GWh`. 1 MU == 1 GWh numerically — the unit relabel is dimensionally
  //     identical (no value transformation needed at read time).
  //
  // DESCOPED from PR 7a (deferred to 7b/7c per Fowler split): 5 shards
  // with no clean 1:1 canonical mapping — `installed_capacity_{thermal,
  // total, by_source}_mw.json`,
  // `state_installed_capacity_by_source_mw.json` (faceted),
  // `state_installed_capacity_total_mw.json` (Block 5 lift input).
  // (A 6th shard `installed_mw_by_state.json` was retired in PR-A 2026-05-25
  // — superseded by the per-fuel CEA family rather than canonicalised.)

  // --- 1: National capacity, Coal (CEA monthly snapshot, per-state) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/installed_capacity_coal_mw",
    canonical_indicator_id: "state-installed-capacity-snapshot-mw-coal",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-installed-capacity-snapshot-mw-coal",
      title: "State installed capacity — Coal (CEA monthly snapshot)",
      description:
        "Coal-fired thermal capacity allocated to each state, end-of-month snapshot from the CEA Monthly Executive Summary. India's largest fuel category nationally (~42%).",
      entity_kind: "state",
      time_grain: "month",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      icon: "flame",
      attribution_geography: "where_allocated",
      comparability: "comparable_across_states_snapshot_only",
      implementing_authority: "joint",
      methodology_vintage:
        "CEA Monthly Executive Summary — IC sheet snapshot 2026-03.",
    },
  },

  // --- 2: National capacity, Gas (CEA monthly snapshot, per-state) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/installed_capacity_gas_mw",
    canonical_indicator_id: "state-installed-capacity-snapshot-mw-gas",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-installed-capacity-snapshot-mw-gas",
      title: "State installed capacity — Gas (CEA monthly snapshot)",
      description:
        "Natural-gas and liquid-fuel thermal capacity allocated to each state, end-of-month snapshot from the CEA Monthly Executive Summary. Stranded-fuel risk; small share.",
      entity_kind: "state",
      time_grain: "month",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      icon: "flame",
      attribution_geography: "where_allocated",
      comparability: "comparable_across_states_snapshot_only",
      implementing_authority: "joint",
      methodology_vintage:
        "CEA Monthly Executive Summary — IC sheet snapshot 2026-03.",
    },
  },

  // --- 3: National capacity, Hydro (CEA monthly snapshot, per-state) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/installed_capacity_hydro_mw",
    canonical_indicator_id: "state-installed-capacity-snapshot-mw-hydro",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-installed-capacity-snapshot-mw-hydro",
      title: "State installed capacity — Hydro (CEA monthly snapshot)",
      description:
        "Conventional (>25 MW) plus small-hydro capacity allocated to each state, end-of-month snapshot from the CEA Monthly Executive Summary. Site-bound; multi-decade lifetime.",
      entity_kind: "state",
      time_grain: "month",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      icon: "droplets",
      attribution_geography: "where_allocated",
      comparability: "comparable_across_states_snapshot_only",
      implementing_authority: "joint",
      methodology_vintage:
        "CEA Monthly Executive Summary — IC sheet snapshot 2026-03.",
    },
  },

  // --- 4: National capacity, Nuclear (CEA monthly snapshot, per-state) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/installed_capacity_nuclear_mw",
    canonical_indicator_id: "state-installed-capacity-snapshot-mw-nuclear",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-installed-capacity-snapshot-mw-nuclear",
      title: "State installed capacity — Nuclear (CEA monthly snapshot)",
      description:
        "Nuclear capacity allocated to each state, end-of-month snapshot from the CEA Monthly Executive Summary. Central-sector only; allocated to states via PPAs.",
      entity_kind: "state",
      time_grain: "month",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      icon: "atom",
      attribution_geography: "where_allocated",
      comparability: "comparable_across_states_snapshot_only",
      implementing_authority: "joint",
      methodology_vintage:
        "CEA Monthly Executive Summary — IC sheet snapshot 2026-03.",
    },
  },

  // --- 5: National capacity, Renewable (CEA monthly snapshot, per-state) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/installed_capacity_renewable_mw",
    canonical_indicator_id: "state-installed-capacity-snapshot-mw-renewable",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-installed-capacity-snapshot-mw-renewable",
      title: "State installed capacity — Renewable (CEA monthly snapshot)",
      description:
        "Wind, solar, biomass and waste-to-energy capacity allocated to each state, end-of-month snapshot from the CEA Monthly Executive Summary. Rapid growth; ~30% national capacity by FY26.",
      entity_kind: "state",
      time_grain: "month",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      icon: "sun",
      attribution_geography: "where_allocated",
      comparability: "comparable_across_states_snapshot_only",
      implementing_authority: "joint",
      methodology_vintage:
        "CEA Monthly Executive Summary — IC sheet snapshot 2026-03.",
    },
  },

  // --- 6: State installed capacity, geographical-location basis (FY15-FY25) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_installed_capacity_geographical_mw",
    canonical_indicator_id: "state-installed-capacity-geographical-mw",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-installed-capacity-geographical-mw",
      title: "State installed electricity capacity, geographical-location basis (MW)",
      description:
        "Total installed capacity physically located in the state, summed across all fuels. 'Geographical' means every plant counts toward the state where it sits, regardless of who owns it or where the power is dispatched. Read this as 'where the steel-and-concrete sits' — NOT 'where the electricity flows to'.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      icon: "factory",
      attribution_geography: "where_produced",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED capacity-metatable rollup of CEA-published station-level capacity; harmonised across fiscal years 2015-16 onwards.",
      notes:
        "For the share-allocated counterpart (rights to output via central-sector PPAs), see state-installed-capacity-allocated-mw. The all-India total equals the allocated total (as it must) but the per-state breakdown diverges sharply for states that import or export power through central PPAs.",
    },
  },

  // --- 7: State installed capacity, allocated-shares basis (FY05-FY25 long-arc) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_installed_capacity_with_alloc_mw",
    canonical_indicator_id: "state-installed-capacity-allocated-mw",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-installed-capacity-allocated-mw",
      title: "State installed electricity capacity, allocated-shares basis (MW)",
      description:
        "Same as the geographical-location capacity, but each state credited its share of joint-sector and central-sector plants per regional allocation formulas. Use this when comparing 'rights to electricity' rather than 'physical assets sited here'. The all-India total equals the geographical total (as it must) but the per-state breakdown can diverge sharply: a state with little local capacity but large central-PPA shares has higher allocated capacity than geographical.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "raw",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "MW",
      icon: "factory",
      attribution_geography: "where_allocated",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED state-wise deep-dive API for FY15-FY25 (fiscal years 2015-16 onwards); RBI Handbook of Statistics on Indian States, Table 140 (silver tier; republishes CEA originals) for the pre-FY15 splice (fiscal years 2004-05 to 2013-14). Per plan-doc 20260522 §3 Q-c Option 1 SPLICE: methodology break at FY15 (basis change + RBI portion carries no per-fuel breakdown).",
      notes:
        "Time coverage on the canonical path is FY05-FY25 (770 rows). The legacy shard `state_installed_capacity_with_alloc_mw.json` carries only FY15-FY25 (396 rows); PR #222 spliced the RBI Handbook Table 140 pre-FY15 segment onto the ICED post-FY15 portion. Citizens reading via the canonical path see the full 21-year long arc; the legacy-shard path saw 11 years.",
      series_breaks: [
        {
          at_time: "2015-04",
          kind: "definition_change",
          note:
            "Pre-FY15 portion is RBI Handbook Table 140 (state totals only — no fuel breakdown); FY15+ portion is NITI ICED (full per-fuel decomposition available on the children). Treat the pre-FY15 segment as state-aggregate-only.",
        },
      ],
    },
  },

  // --- 8: State electricity generation, FY15-FY25 (MU == GWh unit alias) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_electricity_generation_mu",
    canonical_indicator_id: "state-electricity-generation-gwh",
    table_id: "energy.energy_generation",
    meta: {
      id: "state-electricity-generation-gwh",
      title: "State electricity generation, by fuel (GWh)",
      description:
        "Per-state actual electricity generated, summed across all fuels. The delivered counterpart to installed capacity — capacity is potential, generation is what plants actually produced.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "GWh",
      icon: "zap",
      attribution_geography: "where_produced",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED /v1/gen-metatable-data (CEA-sourced upstream).",
      notes:
        "Most-recent fiscal year is partial-year-actuals + forecast and may revise; treat the most-recent two FYs as preliminary. 1 MU (million unit) = 1 GWh — the legacy shard `state_electricity_generation_mu.json` reported the same numbers in MU units; only the label changes. ICED's 'Others' bucket (interstate/central plants pre-allocation) is dropped because it cannot be mapped to a state choropleth honestly.",
    },
  },

  // --- 9: State annual power requirement (MU == GWh), RBI Handbook T141 ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_power_requirement_mu",
    canonical_indicator_id: "state-electricity-requirement-mu",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "state-electricity-requirement-mu",
      title: "State annual power requirement (MU)",
      description:
        "Annual energy requirement assessed by the state (MU = million units = GWh), fiscal year — the demand-side counterpart to availability. Requirement minus availability gives the 'energy not supplied' deficit.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "raw",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MU",
      icon: "zap",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "centre",
      methodology_vintage:
        "RBI Handbook of Statistics on Indian States 2024-25, Table 141. Originating data: Central Electricity Authority, Ministry of Power.",
      notes:
        "Read alongside availability (Table 139): the percentage gap (deficit / requirement) is the operational power-deficit metric. The all-India deficit shrank from ~10% in FY05 to under 0.5% from FY18 onwards; persistent state-level deficits today flag distribution / scheduling issues, not generation shortage.",
    },
  },

  // --- 10: State annual power availability (MU == GWh), RBI Handbook T139 ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_power_availability_mu",
    canonical_indicator_id: "state-electricity-availability-mu",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "state-electricity-availability-mu",
      title: "State annual power availability (MU)",
      description:
        "Annual energy actually supplied to the state (MU = million units = GWh), fiscal year. The supply-side companion to Requirement (T141). Requirement − Availability = the energy-not-supplied deficit.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "raw",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "MU",
      icon: "zap",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "centre",
      methodology_vintage:
        "RBI Handbook of Statistics on Indian States 2024-25, Table 139. Originating data: Central Electricity Authority, Ministry of Power.",
      notes:
        "The all-India figure has converged on near-zero deficit since FY18, but state-level deficits persist for grid-island / load-shedding states.",
    },
  },

  // --- 11: State per-capita electricity availability (kWh/person/year), RBI Handbook T138 ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_per_capita_availability_kwh",
    canonical_indicator_id: "state-per-capita-electricity-availability-kwh",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "state-per-capita-electricity-availability-kwh",
      title: "State per-capita electricity availability (kWh/person/year)",
      description:
        "Annual per-capita electricity availability (kWh / person / year), by state and Union Territory, fiscal year. The most citizen-relevant single number for 'how much power do people in this state actually get to use' — captures both supply expansion and transmission losses.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "rate",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "kWh per person per year",
      icon: "zap",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "centre",
      methodology_vintage:
        "RBI Handbook of Statistics on Indian States 2024-25, Table 138. Originating data: Central Electricity Authority, Ministry of Power.",
      notes:
        "Computed by CEA as state energy availability (MU) ÷ state mid-year population. The all-India figure roughly tripled from ~600 kWh in FY05 to ~1300 kWh in FY24, but the inter-state spread is wide (Goa / Punjab / Gujarat above 2,000; Bihar / Manipur / Nagaland still below 400). Per-capita is on geographical-area population (resident), not consumption-weighted — large industrial-export states (e.g. Chhattisgarh, Sikkim) post inflated numbers because the power they generate is consumed elsewhere.",
    },
  },

  // --- PR-Q (Row 6 P.1.C first canonical fuel-consumption lift, 2026-05-25) ---
  // ICED `/energy/fuel-sources/coal/consumption-domestic-state` -> 450 obs rows
  // (states x fiscal-years FY06-FY25) into the long-reserved
  // `energy_fuel_consumption` parquet stem. Adapter:
  //   * fuel_consumption.py block 1 emits state-coal-consumption-mt
  // ICED publishes 5 grade rows per (state, FY): raw + washed + middlings +
  // lignite + TOTAL COAL. The adapter sums the 4 component grades and DROPS
  // the publisher's TOTAL COAL row to avoid double-counting. Hans + Max
  // signed off this aggregation as a documented `derivation="raw"` row
  // (we're reading 4 rows and writing 1 sum; not imputing).
  {
    kind: "single",
    legacy_artifact_id: "energy/state_coal_consumption_mt",
    canonical_indicator_id: "state-coal-consumption-mt",
    table_id: "energy.energy_fuel_consumption",
    meta: {
      id: "state-coal-consumption-mt",
      title: "State coal consumption (Mt, by fiscal year)",
      description:
        "Million tonnes of coal actually burned in the state per fiscal year — summed across raw, washed, middlings and lignite grades. High values typically indicate either large thermal generation fleets (Maharashtra, UP, MP, Chhattisgarh) or heavy industrial heat demand (steel, cement, sponge-iron clusters).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "Mt",
      short_unit: "Mt",
      icon: "flame",
      attribution_geography: "where_consumed",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED /energy/fuel-sources/coal/consumption-domestic-state (Coal Controller's Office / Ministry of Coal upstream). Aggregated by SUM of the 4 component grades (raw + washed + middlings + lignite); the precomputed TOTAL COAL rows are dropped to avoid double-counting.",
      notes:
        "Read with state-installed-capacity-allocated-mw (coal facet) and state-electricity-generation-gwh (coal facet) on the same /t/energy page: a state with high coal consumption but low coal generation is using coal for industrial heat (steel/cement/sponge-iron) rather than power. attribution_geography = where_consumed, NOT where_mined — coal mined in Jharkhand and Odisha but burned in deficit states.",
    },
    // PR-Q (Row 6 P.1.C commit 1): Hans-curated caveats for the first canonical
    // fuel-consumption indicator. The 4-grade SUM methodology, the thermal-vs-
    // industrial bifurcation, and the where_consumed attribution are the three
    // honesty cues a citizen needs before reading a state's level.
    caveats: [
      "ICED reports 4 coal grades (raw + washed + middlings + lignite); we sum them and drop the publisher's TOTAL COAL row to avoid double-counting. Read this as a derived total, not as a single published figure.",
      "Heavy-industry states dominate the level: Maharashtra, UP, MP and Chhattisgarh burn most coal in thermal fleets; Gujarat and Odisha add steel and sponge-iron kilns on top. A services-tilted state like Karnataka stays low despite a top-10 GSDP.",
      "Coal is mined in Jharkhand and Odisha but consumed wherever the thermal plant or kiln sits. A low-consumption state is not a low-coal-dependence state if its grid imports coal-fired power — pair with state-power-purchase-share-pct to see imported reliance.",
    ],
  },

  // --- PR-R (Row 6 P.1.C 2/9, rooftop solar capacity lift, 2026-05-25) ---
  // ICED `/energy/renewable/solar/rooftop/state` -> 321 obs rows (states x
  // fiscal-years FY18-FY25) joined into the existing `energy_installed_capacity`
  // parquet stem. Adapter:
  //   * installed_capacity.py block 6 emits state-rooftop-solar-capacity-mw
  // Rooftop is a sub-fuel measurement of installed MW; complements utility-scale
  // solar tracked under state-installed-capacity-snapshot-mw-renewable. The
  // total state solar fleet = utility-scale + rooftop. No facets; one row per
  // (state, fiscal_year). Hans + Max signed off non-faceted lift (the rooftop
  // category itself IS the facet — no further breakdown by residential /
  // commercial / industrial published per-state).
  {
    kind: "single",
    legacy_artifact_id: "energy/state_rooftop_solar_capacity_mw",
    canonical_indicator_id: "state-rooftop-solar-capacity-mw",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "state-rooftop-solar-capacity-mw",
      title: "State rooftop solar installed capacity (MW)",
      description:
        "Cumulative installed rooftop solar PV in megawatts — residential + commercial + industrial + public buildings. Owned by the building owner, NOT by a utility. Complements (does not replace) utility-scale solar, which lives under state-installed-capacity-snapshot-mw-renewable.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "MW",
      short_unit: "MW",
      icon: "sun",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED /energy/renewable/solar/rooftop/state. Originating data: MNRE / state nodal agencies via the National Rooftop Solar Programme. ICED is the federal aggregator; not the issuing authority.",
      notes:
        "A state's TOTAL solar fleet = utility-scale + rooftop. Gujarat dominates rooftop by absolute MW thanks to a decade of state co-funding plus the SURYA Gujarat residential push; Rajasthan and Karnataka lead utility-scale but lag rooftop because rooftop economics depend on retail tariff structure (favouring high commercial-tariff states like Maharashtra and Tamil Nadu) more than insolation.",
    },
    // PR-R (Row 6 P.1.C commit 1): Hans-curated caveats. The utility-vs-rooftop
    // mental model, the tariff-economics vs insolation distinction, and the
    // cumulative-vs-annual nuance are the three honesty cues citizens need.
    caveats: [
      "This is rooftop ONLY — building-mounted PV owned by the building owner. The state's TOTAL solar fleet = rooftop + utility-scale (utility-scale lives under the installed-capacity-renewable card on this page). A state can be a solar superstar by either path; Karnataka is utility-led, Gujarat is rooftop-strong.",
      "Tariff structure drives rooftop economics more than sunshine. Maharashtra and Tamil Nadu host commercial buildings paying high retail tariffs (₹8-12/kWh), so rooftop's payback is fast there even with merely good insolation. Rajasthan has the best insolation but its commercial tariffs are lower, so rooftop lags despite being a solar leader overall.",
      "These are CUMULATIVE MW installed to-date, not new MW added in the year. A flat line in a state means the rollout has slowed, not that capacity was lost. Compare consecutive fiscal years to see the actual annual deployment pace.",
    ],
  },

  // --- 12: ACS-ARR gap on electricity sales (₹/kWh), NITI ICED ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_acs_arr_gap_inr_per_kwh",
    canonical_indicator_id: "state-acs-arr-gap-inr-per-kwh",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "state-acs-arr-gap-inr-per-kwh",
      title: "ACS-ARR gap on electricity sales (₹/kWh, by state)",
      description:
        "Average Cost of Supply minus Average Revenue Realised, per unit of electricity sold. Positive = the utility loses money on every unit it sells (closed by tariff hike, loss reduction, or state subsidy). Zero is the UDAY/RDSS policy goal.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "rate",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "₹/kWh",
      icon: "indian-rupee",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED state-wise deep-dive row 'ACS-ARR (Electricity Sales) Gap'. Calculated by PFC from utility tariff orders + audited accounts.",
      notes:
        "Opposite sign convention from fiscal-deficit indicators — here a NEGATIVE number is the surplus side. Surfaced under both the energy and fiscal topics (Hans M:N tag) because the discom-funding question lives at the boundary of both.",
    },
  },

  // --- 13: Distribution billing efficiency (%), NITI ICED operational performance ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_distribution_billing_efficiency_pct",
    canonical_indicator_id: "state-distribution-efficiency-pct-billing",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "state-distribution-efficiency-pct-billing",
      title: "Distribution billing efficiency (%, by state)",
      description:
        "Share of energy actually billed to a consumer, out of total energy input to the distribution system. 100% = every kWh that enters the grid was billed.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "%",
      icon: "receipt",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED /energy/electricity/distribution/operationalPerformanceStates (category: billing-efficiency).",
      notes:
        "Complement of billing-side losses (theft, unmetered consumption, under-billing). Together with collection efficiency, decomposes the commercial half of AT&C losses: AT&C loss ≈ 1 − (billing × collection / 100).",
    },
    // PR-I (Row 5 PR-1): Hans-curated caveats. Billing efficiency is the first
    // commercial half of the AT&C decomposition; pair with collection efficiency
    // and T&D loss below to recover the full AT&C loss identity.
    caveats: [
      "This is the COMMERCIAL half of AT&C decomposition: AT&C loss approx 1 - (billing x collection / 100). A state at 85% billing and 95% collection still leaks ~19% AT&C; pair with collection efficiency and T&D loss on this topic to see the full leak.",
      "The gap below 100% bundles theft, unmetered consumption, unauthorised connections, and under-billing of subsidised categories. Punjab's agricultural pumping is largely unmetered and shown as 'assessed' load; treat Punjab's low billing as policy choice, not enforcement failure.",
      "Higher is better, but a state at 92% may have ring-fenced industrial feeders (high metering) while rural and agricultural feeders stay unmetered. Split by consumer category before ranking Gujarat against Bihar on the same scale.",
    ],
  },

  // --- 14: Distribution collection efficiency (%), NITI ICED operational performance ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_distribution_collection_efficiency_pct",
    canonical_indicator_id: "state-distribution-efficiency-pct-collection",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "state-distribution-efficiency-pct-collection",
      title: "Distribution collection efficiency (%, by state)",
      description:
        "Share of billed revenue actually collected from consumers, by state. 100% = every rupee billed was paid.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "%",
      icon: "wallet",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED /energy/electricity/distribution/operationalPerformanceStates (category: collection-efficiency).",
      notes:
        "Captures how much of the energy that WAS billed got paid for. Low collection often reflects high accounts-receivable days on government / agricultural / municipal consumer categories.",
    },
    // PR-I (Row 5 PR-1): Hans-curated caveats. Collection efficiency is the second
    // commercial half of the AT&C decomposition; reads as a weighted average and
    // often hides government-departmental arrears spikes.
    caveats: [
      "This is the second COMMERCIAL half of AT&C: of every rupee billed, what share got paid. A state at 95% headline collection can be effectively below 80% if government-departmental arrears (PWD, municipal corporations) are separated from retail.",
      "Bihar and Uttar Pradesh have a history of settling municipal and state-department overdues via state-government bond issuances; collection can JUMP in a single year on settlement, not behaviour. Annotate the methodology break before reading the trend.",
      "Low collection often concentrates in agricultural, government and municipal consumer categories rather than domestic/commercial; treat a state's collection as a weighted average and ask the discom for the per-category breakdown before drawing policy conclusions.",
    ],
  },

  // --- 15: Distribution T&D loss (%), NITI ICED operational performance ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_distribution_td_loss_pct",
    canonical_indicator_id: "state-distribution-efficiency-pct-td-loss",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "state-distribution-efficiency-pct-td-loss",
      title: "Transmission & Distribution loss (%, by state)",
      description:
        "Transmission and Distribution loss as % of energy input — the TECHNICAL half of AT&C losses (heat / ageing / unmetered consumption on the wires).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "%",
      icon: "cable",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED /energy/electricity/distribution/operationalPerformanceStates (category: td-loss).",
      notes:
        "T&D loss + commercial-loss = AT&C loss. Where AT&C is a comprehensive ledger of revenue leakage, T&D isolates the part attributable to physical infrastructure (line losses, transformer inefficiency). Older meters and longer rural feeders correlate with higher T&D loss; sub-station upgrades and HVDS rollout drive it down.",
    },
    // PR-I (Row 5 PR-1): Hans-curated caveats. T&D loss is the TECHNICAL half of AT&C;
    // can fall while AT&C stays high if commercial losses dominate (the Bihar mid-2010s case).
    caveats: [
      "This is the TECHNICAL half of AT&C: line heat, transformer inefficiency, ageing wires. AT&C loss = T&D loss + commercial loss; pair with billing efficiency and collection efficiency on this topic to isolate whether the problem is wires or revenue.",
      "Rural-feeder length is the dominant technical predictor; Rajasthan and Madhya Pradesh carry high T&D partly from long radial feeders to dispersed villages. Compare T&D loss with feeder length or rural electrification share, not just with peer-state level.",
      "T&D loss can FALL while AT&C stays high if commercial losses dominate; Bihar mid-2010s saw HVDS and feeder bifurcation cut T&D while billing/collection lagged. Treat a T&D improvement as necessary but not sufficient for AT&C turnaround.",
    ],
  },

  // --- 16: RPO compliance (3 facets: solar / non-solar / total) — FIRST FACET-MULTIPLEXED ENTRY ---
  //   * Legacy shard `state_rpo_compliance_pct.json` emits ONE artifact with
  //     `rows[].facet ∈ {"solar","non-solar","total"}` (hyphenated display form).
  //   * Canonical store materialises 3 child indicator_ids
  //     (state-rpo-compliance-pct-solar / -non-solar / -total) keyed on
  //     `dimension_values.rpo_segment ∈ {"solar","non_solar","total"}` (snake-case).
  //   * Parent `state-rpo-compliance-pct` is compute-on-read per
  //     indicator-naming.md D29 (parent has `source_id = null`).
  //   * Adapter fuses the 3 child rows into ONE IndicatorArtifact with
  //     `rows[].facet = legacy_facet_label` (hyphenated, preserves citizen-
  //     readable form). Sources aggregate from the children
  //     (parent has no source FK).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_rpo_compliance_pct",
    canonical_parent_indicator_id: "state-rpo-compliance-pct",
    table_id: "energy.energy_distribution_performance",
    facet_axis_id: "rpo_segment",
    facet_values: [
      {
        canonical_child_id: "state-rpo-compliance-pct-solar",
        legacy_facet_label: "solar",
      },
      {
        canonical_child_id: "state-rpo-compliance-pct-non-solar",
        legacy_facet_label: "non-solar",
      },
      {
        canonical_child_id: "state-rpo-compliance-pct-total",
        legacy_facet_label: "total",
      },
    ],
    meta: {
      id: "state-rpo-compliance-pct",
      title: "Clean-energy purchase targets met (%)",
      description:
        "Share of each clean-energy purchase obligation your state's discoms met. RPO = a legal % of power discoms must buy from renewables. Three facets — solar, non-solar, combined-target. 'Total' is NOT solar+non-solar; it's the combined-target ratio. >100% = over-compliance (often via REC trades).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "%",
      icon: "leaf",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_snapshot_only",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED /energy/electricity/distribution/rpo (MNRE / state-regulator data). Three facets: solar (solarCompliance), non-solar (nonSolarCompliance), total (totalCompliance).",
      notes:
        "Targets themselves vary by state and rise over time, so a 95% compliance in FY21 may represent more renewables than 105% in FY19. Compute-on-read parent: rows fuse from the 3 child indicator_ids materialised in the canonical store.",
    },
    caveats: [
      "The 'total' segment is NOT the sum of solar + non-solar — it measures compliance against a separate combined-target regulatory denominator. Values above 100% indicate over-compliance.",
      "RPO targets vary by state and rise over time. 95% compliance in one year may represent more renewables than 105% in an earlier year; cross-year and cross-state comparisons must consider the underlying target movement.",
      "RPO is the obligation MET, not the state's clean-energy share. Gujarat over-complies and sells RECs; Bihar under-complies and buys them. 60% means met 60% of an aspirational target — not 60% renewable.",
    ],
  },

  // ---------------------------------------------------------------------------
  // PR B.01 (2026-05-25) — livestock NDLM Pashu Aadhaar, state-grain.
  //
  // First citizen-facing /t/agriculture surface; first canonical-backed
  // indicator from a sub-state-grain adapter that auto-emits state-rollup
  // siblings per ADR-0043 (auto-rollup at canonical-write time).
  //
  // Pipeline shape:
  //   * District rows are the source-of-truth (~3383 rows, FY 2024-25 only),
  //     materialised by backend/yen_gov/canonical/adapters/livestock/pashu_aadhaar.py
  //     as `district-pashu-aadhaar-count-<species>` (10 species enum).
  //   * State-rollup rows (~211) are auto-emitted in the SAME envelope as
  //     `state-pashu-aadhaar-count-<species>` (derivation='sum', reusing
  //     src-7e5d4aac4995 per ADR-0032 sources-as-citation-ledger).
  //   * Both parents (district + state) carry source_id=null and zero
  //     observation rows (compute-on-read per Hans D33.8).
  //
  // This allowlist covers the 10 state-grain species children. District-
  // grain wiring waits for PR B.02 (entityKindToAdminLevel dispatch
  // helper) + PR B.03 (first district allowlist entry as smoke-proof).
  //
  // Hans-honest framing (mirrored in every meta block below): NDLM
  // Pashu Aadhaar is a TAGGED-ANIMAL COUNT, not a livestock census.
  // Coverage varies by state — places with active vet-camp programmes
  // (KA, AP, TN) lead; rollout in NE states is partial. Always read
  // alongside the Livestock Census denominator (next PR after the 5-PR
  // NDLM sprint completes).
  //
  // Per ADR-0030 §11.4 + ADR-0043: each species is a closed-vocabulary
  // facet child. comparability='directional_only' + renderer_rules=
  // ['no_rank_table'] suppress the ranked-table view (a "Bihar > Tamil
  // Nadu in cattle tags" rank order would be a citizen-misleading number
  // — Bihar tags more cattle because Bihar HAS more cattle).

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_cattle",
    canonical_indicator_id: "state-pashu-aadhaar-count-cattle",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-cattle",
      title: "Cattle tagged with Pashu Aadhaar (state)",
      description:
        "State total of cattle issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual cattle population — coverage varies by state programme rollout.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Tagged count is NOT a livestock census. NDLM rollout coverage varies by state — Karnataka, Andhra Pradesh, Tamil Nadu lead via active vet-camp programmes; North-East coverage is partial. Read alongside the 20th Livestock Census (next ingestion PR) for the denominator. State-grain values are auto-summed from district children at canonical-write time (derivation='sum'); the district-grain series is the source-of-truth.",
    },
    caveats: [
      "Pashu Aadhaar counts ANIMALS TAGGED, not cattle owned. A state with 8M tagged cattle may have 12M cattle - the gap is uncovered villages, not missing animals. Read alongside the 20th Livestock Census 2019 for the denominator (40-60% coverage typical).",
      "Karnataka and Andhra Pradesh lead via state-funded vet-camp programmes; Manipur and Mizoram trail on terrain and staffing. A 'KA tags more cattle than Bihar' ranking measures programme effort, not herd size - Bihar's cattle population is larger.",
      "Each tag is a 12-digit RFID; lost or damaged tags get re-issued. The cumulative count drifts above the live herd as replacement events accumulate. Officials reconcile via the Indus Database snapshot - take FY-end (Mar) values, not mid-year.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_buffalo",
    canonical_indicator_id: "state-pashu-aadhaar-count-buffalo",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-buffalo",
      title: "Buffaloes tagged with Pashu Aadhaar (state)",
      description:
        "State total of buffaloes issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual buffalo population — coverage varies by state programme rollout.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Tagged count is NOT a livestock census. Read alongside the 20th Livestock Census for the denominator. State-grain values are auto-summed from district children at canonical-write time (derivation='sum').",
    },
    caveats: [
      "Buffalo tagging tracks the milk-dairy workforce. UP, Punjab, Haryana hold ~50% of India's buffaloes (Murrah breed); 'Kerala has few tagged buffaloes' reflects breed economics, not programme failure. Cattle:buffalo ratio varies sharply by state.",
      "Same coverage gap as cattle: tagged COUNT, not buffalo population. 2019 Livestock Census put Indian buffalo at ~110M; mid-2025 tagged is ~half that. Read with the 'cattle tagged' card - gap structures match but state ranks differ.",
      "Gujarat (Amul) and Maharashtra route tagging through dairy cooperatives; non-coop states use vet camps. Coop coverage is faster on milkers but slower on draught animals. The metric is honest about animals; less honest about WHICH buffaloes get tagged first.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_goat",
    canonical_indicator_id: "state-pashu-aadhaar-count-goat",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-goat",
      title: "Goats tagged with Pashu Aadhaar (state)",
      description:
        "State total of goats issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual goat population.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Tagged count is NOT a livestock census. State-grain values auto-summed from district children at canonical-write time.",
    },
    caveats: [
      "Goats are pastoral - Rajasthan's Bhopa and MP's Banjara herders move with seasons. A 'tagged in Rajasthan' count under-represents migratory herds - the same goat may winter in Rajasthan, summer in Punjab. Tagging happens at vet camps.",
      "Same coverage gap as cattle and buffalo: tagged COUNT, not goat population. 2019 Livestock Census put Indian goats at ~149M (largest livestock category); goats sit lowest in vet-camp triage, so coverage trails cattle by a wide margin.",
      "Goat meat economy is largely INFORMAL - slaughter happens locally, not via abattoirs. Andhra and Telangana tag more via state mutton-trader registration; Bihar trails as goat-meat trade is informal. Metric measures formalisation, not herd.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_sheep",
    canonical_indicator_id: "state-pashu-aadhaar-count-sheep",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-sheep",
      title: "Sheep tagged with Pashu Aadhaar (state)",
      description:
        "State total of sheep issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual sheep population.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Tagged count is NOT a livestock census. State-grain values auto-summed from district children at canonical-write time.",
    },
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_pig",
    canonical_indicator_id: "state-pashu-aadhaar-count-pig",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-pig",
      title: "Pigs tagged with Pashu Aadhaar (state)",
      description:
        "State total of pigs issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual pig population.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Tagged count is NOT a livestock census. State-grain values auto-summed from district children at canonical-write time.",
    },
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_mithun",
    canonical_indicator_id: "state-pashu-aadhaar-count-mithun",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-mithun",
      title: "Mithun tagged with Pashu Aadhaar (state)",
      description:
        "State total of mithun (Bos frontalis, the semi-domesticated bovid of the North-East hills) issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Mithun is a North-East species (Arunachal Pradesh, Nagaland, Manipur, Mizoram); zero presence in most other states is honest, not missing. Tagged count is NOT a livestock census.",
    },
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_yak",
    canonical_indicator_id: "state-pashu-aadhaar-count-yak",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-yak",
      title: "Yaks tagged with Pashu Aadhaar (state)",
      description:
        "State total of yaks issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Yaks are Himalayan species (Ladakh, Sikkim, Arunachal, Himachal); zero counts elsewhere are honest.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Yak distribution is climatically constrained to high-altitude Himalayan states; zero in the plains is honest. Tagged count is NOT a livestock census.",
    },
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_horse",
    canonical_indicator_id: "state-pashu-aadhaar-count-horse",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-horse",
      title: "Horses tagged with Pashu Aadhaar (state)",
      description:
        "State total of horses issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual equine population.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Equine tagging is at the early-rollout stage; very low absolute counts. Tagged count is NOT a livestock census.",
    },
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_donkey",
    canonical_indicator_id: "state-pashu-aadhaar-count-donkey",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-donkey",
      title: "Donkeys tagged with Pashu Aadhaar (state)",
      description:
        "State total of donkeys issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual donkey population.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Equine tagging is at the early-rollout stage; very low absolute counts. Tagged count is NOT a livestock census.",
    },
  },

  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_mule",
    canonical_indicator_id: "state-pashu-aadhaar-count-mule",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-mule",
      title: "Mules tagged with Pashu Aadhaar (state)",
      description:
        "State total of mules issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan, summed from district rows. Tagged COUNT, not actual mule population.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (state aggregate of districts per ADR-0043).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Equine tagging is at the early-rollout stage; very low absolute counts. Tagged count is NOT a livestock census.",
    },
  },

  // PR B.03 (2026-05-25) — first district-grain allowlist entry. SMOKE
  // PROOF of the B.01 (ADR-0043 auto-rollup writer) + B.02
  // (entityKindToAdminLevel dispatch helper) pipeline. The district
  // canonical rows are the SOURCE-OF-TRUTH per ADR-0043; the state-grain
  // descriptor above is the SUM aggregate auto-emitted by the same
  // adapter run. With this descriptor, `loadIndicator()` returns an
  // IndicatorArtifact whose `coverage.admin_level === "district"` (via
  // the B.02 dispatch helper) and whose `rows[].entity_id` carries the
  // legacy `S<n>-D<lgd>` / `U<n>-D<lgd>` district-id form (via
  // `canonicalEntityToLegacy`'s `slice(3)`).
  //
  // NOT YET WIRED into `topics.json` — `IndicatorChoropleth.svelte` only
  // supports `entity_kind === "state"` today (the only national boundary
  // layer in production). A national district-grain choropleth (or a
  // district-grain extension to IndicatorChoropleth) is the next
  // architectural PR in the livestock B-series. Until that lands, this
  // descriptor proves the data plumbing end-to-end through unit tests
  // (see "buildIndicatorArtifact — district-grain (PR B.03 smoke
  // proof)" describe block in indicator-from-canonical.test.ts) without
  // introducing a broken citizen surface.
  //
  // Cattle is the first district species because it has the highest
  // district coverage at 758 districts (PR 3 / 281 lift summary), the
  // clearest choropleth signal, and matches the state-grain default
  // species on /t/agriculture — the same indicator at two grains.
  {
    kind: "single",
    legacy_artifact_id: "agriculture/district_pashu_aadhaar_count_cattle",
    canonical_indicator_id: "district-pashu-aadhaar-count-cattle",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "district-pashu-aadhaar-count-cattle",
      title: "Cattle tagged with Pashu Aadhaar (district)",
      description:
        "District total of cattle issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
      entity_kind: "district",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "animals",
      short_unit: "tagged",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 758 districts with non-zero counts).",
      renderer_rules: ["no_rank_table"],
      notes:
        "Tagged count is NOT a livestock census. Coverage varies by district within a state — even within Karnataka or Andhra Pradesh (national leaders), rollout reaches some districts before others. Read alongside the 20th Livestock Census for the denominator. This is the source-of-truth grain; state values are the SUM rollup.",
    },
  },
];

const BY_LEGACY_ID = new Map(
  CANONICAL_BACKED_INDICATORS.map((d) => [d.legacy_artifact_id, d] as const),
);

/** Whether the given catalogue artifact id reads from the canonical Parquet
 *  store (true) or the legacy per-shard JSON (false). */
export function isCanonicalBacked(legacy_artifact_id: string): boolean {
  return BY_LEGACY_ID.has(legacy_artifact_id);
}

/** Resolve the canonical descriptor for an artifact id, or null when the
 *  artifact has not yet been migrated to the canonical reader. */
export function getCanonicalDescriptor(
  legacy_artifact_id: string,
): CanonicalIndicatorDescriptor | null {
  return BY_LEGACY_ID.get(legacy_artifact_id) ?? null;
}
