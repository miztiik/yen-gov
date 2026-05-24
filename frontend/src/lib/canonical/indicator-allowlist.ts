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

export interface CanonicalIndicatorDescriptor {
  /** Legacy catalogue artifact id (e.g. `energy/state_peak_electricity_demand_mw`). */
  legacy_artifact_id: string;
  /** Canonical fact-table `indicator_id` (kebab-case per indicator-naming.md D30). */
  canonical_indicator_id: string;
  /** Manifest table id (e.g. `energy.energy_demand_supply`). */
  table_id: string;
  /** Static IndicatorMeta block — what the citizen sees as the card header.
   *  Source: `datasets/taxonomy/indicators.parquet` row for `canonical_indicator_id`. */
  meta: IndicatorMeta;
}

export const CANONICAL_BACKED_INDICATORS: ReadonlyArray<CanonicalIndicatorDescriptor> = [
  // C4.7 Phase B — peak electricity demand (RBI Handbook Table 142 FY13–FY24
  // + NITI ICED state-wise deep-dive FY25 extension; 430 rows, 35 entities).
  // See TODO/20260524-p1a-data-reacquisition-plan.md §3 C4.7 Phase A status.
  {
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
  // DESCOPED from PR 7a (deferred to 7b/7c per Fowler split): the 6 shards
  // with no clean 1:1 canonical mapping — `installed_capacity_{thermal,
  // total, by_source}_mw.json`, `installed_mw_by_state.json`,
  // `state_installed_capacity_by_source_mw.json` (faceted),
  // `state_installed_capacity_total_mw.json` (Block 5 lift input).

  // --- 1: National capacity, Coal (CEA monthly snapshot, per-state) ---
  {
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
