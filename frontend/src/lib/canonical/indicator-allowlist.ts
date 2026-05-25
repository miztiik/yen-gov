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
      title: "Renewable Purchase Obligation compliance (%, by state)",
      description:
        "Three citizen-readable segments of state RPO compliance — solar, non-solar, and combined-target. Each measures share of the regulatory RPO target met. The 'total' segment is NOT the sum of solar + non-solar; it's the combined-target compliance ratio (its own regulatory denominator). Values above 100% indicate over-compliance.",
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
    ],
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
