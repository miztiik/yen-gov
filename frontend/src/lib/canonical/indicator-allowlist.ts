// Canonical-backed indicator allowlist (Phase B of P.1.A C4.7).
//
// This module is the single-source-of-truth for which catalogue artifacts
// have already been migrated from the legacy per-shard JSON loader
// (`/data/indicators/in/<topic>/<id>.json`) to a DuckDB-WASM query against
// the canonical long-format CSV store under `/data/datapoints/<class>/`
// (MIGRATING from Hive-partitioned Parquet at `/data/<family>/<table>.parquet`
// per the platform-reset plan chunks F1 / X1a).
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
//    `rpo-compliance-pct-solar` etc., parented by
//    `rpo-compliance-pct` which carries `source_id = null` per
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
//    differ both in shape (kebab `rpo-compliance-pct`) and
//    sometimes in unit-suffix or basis-suffix (e.g.
//    `state_electricity_generation_mu` -> `electricity-generation-gwh`,
//    `state_distribution_billing_efficiency_pct` ->
//    `distribution-efficiency-pct-billing` flips the modifier
//    order). The allowlist is the single source of truth for these
//    renames; until the catalogue regenerates topics.json against the
//    canonical taxonomy (a Level-5 chore deferred behind the canonical
//    reader ADR), this file is the rename ledger.
//
// Adding a new entry
// ------------------
// 1. Verify the canonical fact-table carries the indicator: query
//    `read_csv('datasets/data/datapoints/<class>/<variable_id>.csv', columns={...})`
//    with the `indicator_id` filter; assert non-zero rows. (MIGRATING
//    from `read_parquet('datasets/<family>/<table>.parquet')` per plan
//    chunks F1 / X1a; both shapes coexist during the cutover.)
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
  /** Manifest table id (e.g. `energy.energy_demand_supply`). The field
   *  stays named `table_id` rather than flipping to `csv_path` because it
   *  is a key into `manifest.json` (format-agnostic) - the manifest
   *  resolves the key to a concrete file list at read time, and the file
   *  list itself flips from Parquet to long-format CSV at chunk X1a per
   *  the platform-reset plan. Renaming the field here would cascade
   *  through every descriptor + the adapter + tests for zero behaviour
   *  change. */
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
  /** R2 reader-flip (sub-plan 20260607): repo-relative path under
   *  `datasets/` that the adapter `read_csv(...)`s instead of resolving
   *  `table_id` through the parquet manifest. Set on a per-descriptor
   *  basis as each family migrates; when present, the CSV reader fires
   *  and the parquet path is bypassed. When absent, the legacy parquet
   *  path via `registerTable(table_id)` runs (back-compat for any
   *  descriptor not yet flipped). The path shape is the canonical
   *  long-format `data/datapoints/geo/<canonical_indicator_id>.csv`
   *  per the csv-column-contract.md section 3.3 file class. For
   *  facet-multiplexed descriptors this field stays absent on the
   *  parent and is set per child in `facet_values[].csv_path`. */
  csv_path?: string;
  /** G29 pilot opt-in flag (parent plan section 14.5 / 15 / 16):
   *  swaps the legacy maplibre-based `<IndicatorChoropleth>` for the
   *  d3-geo SVG `<GeoChoropleth>` (F2b.3) at this descriptor's
   *  render seam. Reversible by removing the field. The pilot is
   *  scoped to ONE descriptor per PR; the next indicator gets its
   *  own follow-on entry. Today the only value is the literal
   *  `"geo-choropleth-f2b"`; future renderer flips can widen the
   *  union. State-grain only at the pilot; the dispatch falls
   *  through to the legacy maplibre body for any non-state grain
   *  even when the flag is set, so the worst-case behaviour for a
   *  misapplied flag is the legacy render. */
  renderer_override?: "geo-choropleth-f2b";
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
  /** R2 reader-flip (sub-plan 20260607): per-child CSV path under
   *  `datasets/` for the canonical long-format file that backs THIS
   *  facet child. When every child of a facet-multiplexed descriptor
   *  has a `csv_path`, the adapter fans out via N `read_csv(...)`
   *  reads UNION-ed under a synth `indicator_id` literal column so
   *  the existing per-row facet dispatch keeps working unchanged. */
  csv_path?: string;
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
    canonical_indicator_id: "peak-electricity-demand-mw",
    csv_path: "data/datapoints/geo/peak-electricity-demand-mw.csv",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "peak-electricity-demand-mw",
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
        "Read alongside Peak Supplied (peak-electricity-supplied-mw) — the gap is the unmet peak demand, more operationally critical than the energy-deficit % because shortages force load-shedding. RBI Handbook relabelled 'Surplus / Deficit' to 'Demand Not Met' from FY 2019-20 onwards; underlying definition is unchanged.",
    },
    caveats: [
      "Peak demand is the highest single-instant load observed — a one-hour summer evening spike, not an average. A state can have a high peak yet a moderate annual energy requirement.",
      "Read against peak-electricity-supplied-mw: the gap is unmet demand that forced load-shedding. A rising peak with a rising gap is a worse signal than a rising peak alone.",
      "RBI Handbook relabelled 'Surplus/Deficit' to 'Demand Not Met' from FY 2019-20; the column name changes but the underlying definition does not — do not read the rename as a methodology break.",
    ],
  },

  // PR-F (2026-05-25) — close 4 /t/energy 404s flagged by user smoke.
  // The legacy topics.json energy block references THREE short-name shards
  // that have no allowlist route + ONE meadow-only orphan; this PR adds 2
  // allowlist entries (peak_met → peak-electricity-supplied-mw,
  // per_capita_consumption_kwh → per-capita-electricity-consumption-kwh)
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
    canonical_indicator_id: "peak-electricity-supplied-mw",
    csv_path: "data/datapoints/geo/peak-electricity-supplied-mw.csv",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "peak-electricity-supplied-mw",
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
    canonical_indicator_id: "per-capita-electricity-consumption-kwh",
    csv_path: "data/datapoints/geo/per-capita-electricity-consumption-kwh.csv",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "per-capita-electricity-consumption-kwh",
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
  //   1. state_electricity_sales_mu        → electricity-sales-mu (single)
  //   2. state_atc_losses_pct              → atc-losses-pct (single)
  //   3. state_installed_capacity_by_source_mw      → installed-capacity-geographical-mw (facet-multiplexed by fuel_type)
  //   4. state_electricity_generation_by_source_gwh → electricity-generation-gwh (facet-multiplexed by fuel_type)
  //   5. state_installed_capacity_total_mw → Pattern B duplicate of
  //      state_installed_capacity_with_alloc_mw (already routes to
  //      installed-capacity-allocated-mw via entry #7). PR #222
  //      spliced both legacy shards into one canonical FY05-FY25 series;
  //      having two topics.json cards for the same data is citizen-noise.
  //      This PR PRUNES (5) from topics.json rather than aliasing it,
  //      matching the PR-F precedent (state_peak_demand_mw prune).
  //
  // Adapter wiring confirmed:
  //   * distribution.py block 1 (line 87) emits atc-losses-pct
  //   * distribution.py block 2 (line 102) emits electricity-sales-mu
  //   * generation.py block 2 (line 77) emits electricity-generation-gwh-{fuel}
  //   * installed_capacity.py block 3 (line 144) emits installed-capacity-geographical-mw + -{fuel} children
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
    canonical_indicator_id: "electricity-sales-mu",
    csv_path: "data/datapoints/geo/electricity-sales-mu.csv",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "electricity-sales-mu",
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
        "Read alongside generation (electricity-generation-gwh): generation MINUS sales = absolute AT&C loss. 1 MU (million unit) = 1 GWh; the unit relabel is dimensionally identical.",
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
    canonical_indicator_id: "atc-losses-pct",
    csv_path: "data/datapoints/geo/atc-losses-pct.csv",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "atc-losses-pct",
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
        "UDAY (2015) targeted all-India AT&C below 15% by 2018-19; the actual all-India figure has hovered around 15% since then. State-level dispersion is wide — Gujarat / Andhra at ~6-10%, Bihar / J&K at ~25-40%. AT&C = T&D loss + commercial loss; the three sub-components (billing / collection / T&D) are surfaced separately under distribution-efficiency-pct.",
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
  //   * Parent `installed-capacity-geographical-mw` carries the sum
  //     (entry #6 above already routes the totals-only legacy slug
  //     `state_installed_capacity_geographical_mw` to the SAME parent —
  //     a single big-number card; this faceted entry adds the per-fuel
  //     breakdown view via the FacetPicker primitive shipped in PR-D #277).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_installed_capacity_by_source_mw",
    canonical_parent_indicator_id: "installed-capacity-geographical-mw",
    table_id: "energy.energy_installed_capacity",
    facet_axis_id: "fuel_type",
    facet_values: [
      {
        canonical_child_id: "installed-capacity-geographical-mw-coal",
        csv_path: "data/datapoints/geo/installed-capacity-geographical-mw-coal.csv",
        legacy_facet_label: "coal",
      },
      {
        canonical_child_id: "installed-capacity-geographical-mw-gas",
        csv_path: "data/datapoints/geo/installed-capacity-geographical-mw-gas.csv",
        legacy_facet_label: "gas",
      },
      {
        canonical_child_id: "installed-capacity-geographical-mw-hydro",
        csv_path: "data/datapoints/geo/installed-capacity-geographical-mw-hydro.csv",
        legacy_facet_label: "hydro",
      },
      {
        canonical_child_id: "installed-capacity-geographical-mw-nuclear",
        csv_path: "data/datapoints/geo/installed-capacity-geographical-mw-nuclear.csv",
        legacy_facet_label: "nuclear",
      },
      {
        canonical_child_id: "installed-capacity-geographical-mw-renewable",
        csv_path: "data/datapoints/geo/installed-capacity-geographical-mw-renewable.csv",
        legacy_facet_label: "renewable",
      },
    ],
    meta: {
      id: "installed-capacity-geographical-mw",
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
        "For the share-allocated counterpart (rights to output via central-sector PPAs), see installed-capacity-allocated-mw. The all-India total equals the allocated total (as it must) but the per-state breakdown diverges sharply for states that import or export power through central PPAs.",
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
  //   * Parent `electricity-generation-gwh` carries the sum (entry
  //     #8 from PR 7a already routes the totals-only legacy slug
  //     `state_electricity_generation_mu` to the SAME parent — single
  //     big-number card; this faceted entry adds the per-fuel breakdown
  //     view via the FacetPicker primitive).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_electricity_generation_by_source_gwh",
    canonical_parent_indicator_id: "electricity-generation-gwh",
    table_id: "energy.energy_generation",
    facet_axis_id: "fuel_type",
    facet_values: [
      {
        canonical_child_id: "electricity-generation-gwh-coal",
        csv_path: "data/datapoints/geo/electricity-generation-gwh-coal.csv",
        legacy_facet_label: "coal",
      },
      {
        canonical_child_id: "electricity-generation-gwh-gas",
        csv_path: "data/datapoints/geo/electricity-generation-gwh-gas.csv",
        legacy_facet_label: "gas",
      },
      {
        canonical_child_id: "electricity-generation-gwh-hydro",
        csv_path: "data/datapoints/geo/electricity-generation-gwh-hydro.csv",
        legacy_facet_label: "hydro",
      },
      {
        canonical_child_id: "electricity-generation-gwh-nuclear",
        csv_path: "data/datapoints/geo/electricity-generation-gwh-nuclear.csv",
        legacy_facet_label: "nuclear",
      },
      {
        canonical_child_id: "electricity-generation-gwh-renewable",
        csv_path: "data/datapoints/geo/electricity-generation-gwh-renewable.csv",
        legacy_facet_label: "renewable",
      },
    ],
    meta: {
      id: "electricity-generation-gwh",
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
  //     to `installed-capacity-snapshot-mw-<fuel>` (exact 35×1 match);
  //     mapping to `installed-capacity-mw-<fuel>` (1×1) would silently
  //     reduce visible data from 35 state rows to 1 national row and was rejected.
  //   * Shard #7 (`state_installed_capacity_with_alloc_mw.json`) carries FY15-FY25
  //     (396 rows); the canonical `installed-capacity-allocated-mw` now
  //     carries FY05-FY25 (770 rows) after PR #222 spliced the RBI Handbook
  //     long-arc onto the ICED post-FY15 segment. INTENTIONAL time-window
  //     extension — citizens see MORE data on the canonical path, not less.
  //   * Shard #8 (`state_electricity_generation_mu.json`) uses publisher unit
  //     `MU` (million units); canonical `electricity-generation-gwh` uses
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
    canonical_indicator_id: "installed-capacity-snapshot-mw-coal",
    csv_path: "data/datapoints/geo/installed-capacity-snapshot-mw-coal.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "installed-capacity-snapshot-mw-coal",
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
    canonical_indicator_id: "installed-capacity-snapshot-mw-gas",
    csv_path: "data/datapoints/geo/installed-capacity-snapshot-mw-gas.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "installed-capacity-snapshot-mw-gas",
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
    canonical_indicator_id: "installed-capacity-snapshot-mw-hydro",
    csv_path: "data/datapoints/geo/installed-capacity-snapshot-mw-hydro.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "installed-capacity-snapshot-mw-hydro",
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
    canonical_indicator_id: "installed-capacity-snapshot-mw-nuclear",
    csv_path: "data/datapoints/geo/installed-capacity-snapshot-mw-nuclear.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "installed-capacity-snapshot-mw-nuclear",
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
    canonical_indicator_id: "installed-capacity-snapshot-mw-renewable",
    csv_path: "data/datapoints/geo/installed-capacity-snapshot-mw-renewable.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "installed-capacity-snapshot-mw-renewable",
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
    canonical_indicator_id: "installed-capacity-geographical-mw",
    csv_path: "data/datapoints/geo/installed-capacity-geographical-mw.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "installed-capacity-geographical-mw",
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
        "For the share-allocated counterpart (rights to output via central-sector PPAs), see installed-capacity-allocated-mw. The all-India total equals the allocated total (as it must) but the per-state breakdown diverges sharply for states that import or export power through central PPAs.",
    },
  },

  // --- 7: State installed capacity, allocated-shares basis (FY05-FY25 long-arc) ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_installed_capacity_with_alloc_mw",
    canonical_indicator_id: "installed-capacity-allocated-mw",
    csv_path: "data/datapoints/geo/installed-capacity-allocated-mw.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "installed-capacity-allocated-mw",
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
    canonical_indicator_id: "electricity-generation-gwh",
    csv_path: "data/datapoints/geo/electricity-generation-gwh.csv",
    table_id: "energy.energy_generation",
    meta: {
      id: "electricity-generation-gwh",
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
    canonical_indicator_id: "electricity-requirement-mu",
    csv_path: "data/datapoints/geo/electricity-requirement-mu.csv",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "electricity-requirement-mu",
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
    canonical_indicator_id: "electricity-availability-mu",
    csv_path: "data/datapoints/geo/electricity-availability-mu.csv",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "electricity-availability-mu",
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
    canonical_indicator_id: "per-capita-electricity-availability-kwh",
    csv_path: "data/datapoints/geo/per-capita-electricity-availability-kwh.csv",
    table_id: "energy.energy_demand_supply",
    meta: {
      id: "per-capita-electricity-availability-kwh",
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
  //   * fuel_consumption.py block 1 emits coal-consumption-mt
  // ICED publishes 5 grade rows per (state, FY): raw + washed + middlings +
  // lignite + TOTAL COAL. The adapter sums the 4 component grades and DROPS
  // the publisher's TOTAL COAL row to avoid double-counting. Hans + Max
  // signed off this aggregation as a documented `derivation="raw"` row
  // (we're reading 4 rows and writing 1 sum; not imputing).
  {
    kind: "single",
    legacy_artifact_id: "energy/state_coal_consumption_mt",
    canonical_indicator_id: "coal-consumption-mt",
    csv_path: "data/datapoints/geo/coal-consumption-mt.csv",
    table_id: "energy.energy_fuel_consumption",
    meta: {
      id: "coal-consumption-mt",
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
        "Read with installed-capacity-allocated-mw (coal facet) and electricity-generation-gwh (coal facet) on the same /t/energy page: a state with high coal consumption but low coal generation is using coal for industrial heat (steel/cement/sponge-iron) rather than power. attribution_geography = where_consumed, NOT where_mined — coal mined in Jharkhand and Odisha but burned in deficit states.",
    },
    // PR-Q (Row 6 P.1.C commit 1): Hans-curated caveats for the first canonical
    // fuel-consumption indicator. The 4-grade SUM methodology, the thermal-vs-
    // industrial bifurcation, and the where_consumed attribution are the three
    // honesty cues a citizen needs before reading a state's level.
    caveats: [
      "ICED reports 4 coal grades (raw + washed + middlings + lignite); we sum them and drop the publisher's TOTAL COAL row to avoid double-counting. Read this as a derived total, not as a single published figure.",
      "Heavy-industry states dominate the level: Maharashtra, UP, MP and Chhattisgarh burn most coal in thermal fleets; Gujarat and Odisha add steel and sponge-iron kilns on top. A services-tilted state like Karnataka stays low despite a top-10 GSDP.",
      "Coal is mined in Jharkhand and Odisha but consumed wherever the thermal plant or kiln sits. A low-consumption state is not a low-coal-dependence state if its grid imports coal-fired power — pair with power-purchase-share-pct to see imported reliance.",
    ],
  },

  // --- PR-R (Row 6 P.1.C 2/9, rooftop solar capacity lift, 2026-05-25) ---
  // ICED `/energy/renewable/solar/rooftop/state` -> 321 obs rows (states x
  // fiscal-years FY18-FY25) joined into the existing `energy_installed_capacity`
  // parquet stem. Adapter:
  //   * installed_capacity.py block 6 emits rooftop-solar-capacity-mw
  // Rooftop is a sub-fuel measurement of installed MW; complements utility-scale
  // solar tracked under installed-capacity-snapshot-mw-renewable. The
  // total state solar fleet = utility-scale + rooftop. No facets; one row per
  // (state, fiscal_year). Hans + Max signed off non-faceted lift (the rooftop
  // category itself IS the facet — no further breakdown by residential /
  // commercial / industrial published per-state).
  {
    kind: "single",
    legacy_artifact_id: "energy/state_rooftop_solar_capacity_mw",
    canonical_indicator_id: "rooftop-solar-capacity-mw",
    csv_path: "data/datapoints/geo/rooftop-solar-capacity-mw.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "rooftop-solar-capacity-mw",
      title: "State rooftop solar installed capacity (MW)",
      description:
        "Cumulative installed rooftop solar PV in megawatts — residential + commercial + industrial + public buildings. Owned by the building owner, NOT by a utility. Complements (does not replace) utility-scale solar, which lives under installed-capacity-snapshot-mw-renewable.",
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

  // --- PR-S (Row 6 P.1.C 3/9, thermal capacity retired lift, 2026-05-25) ---
  // ICED `/v1/retired-capacity-plants` -> 29 obs rows (national-only, FY05-FY25)
  // joined into the existing `energy_installed_capacity` parquet stem. Adapter:
  //   * installed_capacity.py block 7 emits india-thermal-capacity-retired-mw-{fuel}
  // First Pattern A-facet indicator in P.1.C cohort. National-only --
  // ICED does NOT publish state-level retired capacity. The publisher emits
  // 2 facets: "coal" and "oil-gas"; SUB_FUEL_TO_CANONICAL collapses "oil-gas"
  // -> canonical "gas" per Hans D33.8 (the 5-bucket fuel_type axis).
  // legacy_facet_label is the CANONICAL bucket name ("gas"), NOT the raw
  // publisher label ("oil-gas") -- citizens see the collapsed view.
  // Compute-on-read parent: the parent indicator-id india-thermal-capacity-
  // retired-mw carries no observation rows; the renderer sums the 2 fuel
  // children at read time (Hans D33.8 convention; same as state-installed-
  // capacity-geographical-mw and electricity-generation-gwh).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/india_thermal_capacity_retired_mw",
    canonical_parent_indicator_id: "india-thermal-capacity-retired-mw",
    table_id: "energy.energy_installed_capacity",
    facet_axis_id: "fuel_type",
    facet_values: [
      {
        canonical_child_id: "india-thermal-capacity-retired-mw-coal",
        csv_path: "data/datapoints/geo/india-thermal-capacity-retired-mw-coal.csv",
        legacy_facet_label: "coal",
      },
      {
        canonical_child_id: "india-thermal-capacity-retired-mw-gas",
        csv_path: "data/datapoints/geo/india-thermal-capacity-retired-mw-gas.csv",
        legacy_facet_label: "gas",
      },
    ],
    meta: {
      id: "india-thermal-capacity-retired-mw",
      title: "India thermal capacity retired, by fuel (MW per year)",
      description:
        "National total of thermal generating capacity retired each fiscal year, broken down by fuel (coal vs gas). A key signal in the energy-transition story: rising coal retirements mean the fleet is being REPLACED rather than just EXPANDED. Pair with installed-capacity additions to read the NET change.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "MW",
      short_unit: "MW",
      icon: "trash-2",
      attribution_geography: "where_produced",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED /v1/retired-capacity-plants. Originating data: Central Electricity Authority station-level retirement records. ICED is the federal aggregator; not the issuing authority.",
      notes:
        "National-only — ICED does NOT publish state-level retired capacity. Captures only utility-scale thermal retirements; captive plants and renewables decommissioning are out of scope. The 'gas' facet bundles oil-fired + diesel + gas-fired plants (ICED's publisher label is 'oil-gas'; the canonical 5-bucket fuel_type axis collapses to 'gas' per Hans D33.8).",
    },
    // PR-S (Row 6 P.1.C commit 1): Hans-curated caveats. Three honesty cues
    // citizens need: national-only-grain, oil-gas-collapse, and net-change-pairing.
    caveats: [
      "National figures only — this is the ALL-INDIA annual retirement; ICED does not publish state-level retired capacity. A state cannot be ranked here. To attribute a coal retirement to (say) West Bengal or Maharashtra, cross-reference CEA station-level decommissioning notices directly.",
      "'Gas' here bundles oil-fired + diesel + gas-fired plants. ICED's raw publisher label is 'oil-gas' (because legacy oil and diesel thermal plants share grid characteristics with gas); the canonical 5-bucket fuel axis collapses to 'gas'. A spike in 'gas' retirements is often diesel-station decommissioning, not natural-gas exit.",
      "Coal retirements ≠ coal exit. Pair with installed-capacity additions on this page to read NET change: India retires ~1-2 GW coal annually since FY16 but ADDS 5-8 GW of new coal in the same window. Fleet is being modernised (sub-critical → super-critical), not phased out.",
    ],
  },

  // --- PR-T (Row 6 P.1.C 4/9, oil-product consumption lift, 2026-05-26) ---
  // ICED `/energy/fuel-sources/oil/consumptionStateProductTrend` -> 2901 obs
  // rows (state-level, FY11-FY25) joined into the existing
  // `energy_fuel_consumption` parquet stem reserved by PR-Q. Adapter:
  //   * fuel_consumption.py block 2 emits oil-product-consumption-kt-{product}
  // 7-facet Pattern A-facet on the NEW `oil_product` axis (per Hans).
  // Unlike fuel_type's SUB_FUEL_TO_CANONICAL collapse, the 7 publisher
  // labels (diesel-hsd, petrol, lpg, kerosene, naphtha, petroleum-coke,
  // others) map 1:1 onto canonical value_ids -- no sub-bucket roll-up.
  // legacy_facet_label is the canonical bucket name = the raw publisher
  // label (already in lowercase-hyphen citizen-display form).
  // Compute-on-read parent: the parent indicator-id state-oil-product-
  // consumption-kt carries no observation rows; the renderer sums the 7
  // product children at read time (Hans D33.8; same as the `species`
  // axis pattern used by pashu-aadhaar-count).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_oil_product_consumption_kt",
    canonical_parent_indicator_id: "oil-product-consumption-kt",
    table_id: "energy.energy_fuel_consumption",
    facet_axis_id: "oil_product",
    facet_values: [
      {
        canonical_child_id: "oil-product-consumption-kt-diesel-hsd",
        csv_path: "data/datapoints/geo/oil-product-consumption-kt-diesel-hsd.csv",
        legacy_facet_label: "diesel-hsd",
      },
      {
        canonical_child_id: "oil-product-consumption-kt-petrol",
        csv_path: "data/datapoints/geo/oil-product-consumption-kt-petrol.csv",
        legacy_facet_label: "petrol",
      },
      {
        canonical_child_id: "oil-product-consumption-kt-lpg",
        csv_path: "data/datapoints/geo/oil-product-consumption-kt-lpg.csv",
        legacy_facet_label: "lpg",
      },
      {
        canonical_child_id: "oil-product-consumption-kt-kerosene",
        csv_path: "data/datapoints/geo/oil-product-consumption-kt-kerosene.csv",
        legacy_facet_label: "kerosene",
      },
      {
        canonical_child_id: "oil-product-consumption-kt-naphtha",
        csv_path: "data/datapoints/geo/oil-product-consumption-kt-naphtha.csv",
        legacy_facet_label: "naphtha",
      },
      {
        canonical_child_id: "oil-product-consumption-kt-petroleum-coke",
        csv_path: "data/datapoints/geo/oil-product-consumption-kt-petroleum-coke.csv",
        legacy_facet_label: "petroleum-coke",
      },
      {
        canonical_child_id: "oil-product-consumption-kt-others",
        csv_path: "data/datapoints/geo/oil-product-consumption-kt-others.csv",
        legacy_facet_label: "others",
      },
    ],
    meta: {
      id: "oil-product-consumption-kt",
      title: "State oil-product consumption, by product (kt per fiscal year)",
      description:
        "Per-state annual consumption of refined petroleum products in kilotonnes, broken down by 7 products. Diesel dominates everywhere (transport + agriculture); LPG tracks PMUY (Ujjwala) household-coverage policy; petroleum-coke tracks heavy-industry heat use. Where-CONSUMED attribution (not where-refined): the figure tells you where the product was sold and burned, not where it came out of a refinery.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "kt",
      short_unit: "kt",
      icon: "fuel",
      attribution_geography: "where_consumed",
      comparability: "comparable_with_normalisation",
      implementing_authority: "centre",
      methodology_vintage:
        "NITI Aayog ICED /energy/fuel-sources/oil/consumptionStateProductTrend (PPAC / Ministry of Petroleum & Natural Gas upstream). Per-state per-product per-FY, FY11-FY25. The OTHERS state bucket and the IN national row are dropped at meadow ingest.",
      notes:
        "Like coal, oil is a *consumption* statistic — where the product is burned, not where the refinery sits. Diesel + petrol track economic activity; LPG tracks household-policy coverage more than wealth (a poor rural state with successful PMUY rollout will show high per-capita LPG). The 'others' bucket is the publisher's catch-all (fuel oil, ATF, lubricants, bitumen) — preserved verbatim, never imputed.",
    },
    // PR-T (Row 6 P.1.C commit 1): Hans-curated caveats. Three honesty cues
    // citizens need: where-consumed-not-refined, LPG-is-policy-not-wealth,
    // petroleum-coke-is-air-quality-debt.
    caveats: [
      "Where-CONSUMED, not where-refined. Gujarat is a refinery hub (Jamnagar) but a state's number here only reflects what was SOLD and BURNED within its borders — not what was produced. A landlocked diesel-heavy state (Punjab, Haryana) ranks high because of agricultural pump-set use, not because it has refineries.",
      "LPG tracks the PMUY rollout, NOT wealth. The Ujjwala scheme distributed ~9 crore connections since FY17, concentrated in rural Bihar / UP / MP / Rajasthan. A rising LPG line in a poor state is a policy-success signal (cooking-fuel transition) — not a wealth signal. Falling rural firewood use is the upside; rural-household subsidy load is the downside.",
      "Petroleum-coke is heavily air-quality-regulated. The 'pet coke' bucket bundles refinery by-products burned in cement and glass plants — pollution-intensive use. NCR banned its industrial use in 2017 (Supreme Court); other states allow it conditionally. A rising pet-coke line in your state is an emissions-debt signal that policy may eventually close.",
    ],
  },

  // --- PR-U (Row 6 P.1.C 5/9, national primary energy supply lift, 2026-05-26) ---
  // ICED `/analytics/state-wise-deep-dive` (primary-energy-supply national
  // series) -> 140 obs rows (national-only, FY05-FY25) joined into the
  // existing `energy_fuel_consumption` parquet stem reserved by PR-Q for
  // "national primary/final energy supply" indicators. Adapter:
  //   * fuel_consumption.py block 3 emits india-primary-energy-supply-mtoe-{fuel}
  // 6-facet Pattern A-facet on the EXISTING `fuel_type` axis (extended
  // with `oil` + `renewable` value_ids in this PR). National-only --
  // ICED does NOT publish state-level TPES.
  // Publisher facets: coal, oil, gas, hydro, nuclear, renewables (+ total
  // which is FILTERED at adapter time as compute-on-read parent). Publisher
  // "renewables" (plural aggregate) collapses to canonical "renewable"
  // singular per indicator-naming.md. legacy_facet_label = canonical
  // bucket name in each entry.
  // Compute-on-read parent: india-primary-energy-supply-mtoe carries no
  // observation rows; renderer sums the 6 fuel children at read time
  // (Hans D33.8; allow_compute_on_read_total=True on the fuel_type axis).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/national_primary_energy_supply_mtoe",
    canonical_parent_indicator_id: "india-primary-energy-supply-mtoe",
    table_id: "energy.energy_fuel_consumption",
    facet_axis_id: "fuel_type",
    facet_values: [
      {
        canonical_child_id: "india-primary-energy-supply-mtoe-coal",
        csv_path: "data/datapoints/geo/india-primary-energy-supply-mtoe-coal.csv",
        legacy_facet_label: "coal",
      },
      {
        canonical_child_id: "india-primary-energy-supply-mtoe-oil",
        csv_path: "data/datapoints/geo/india-primary-energy-supply-mtoe-oil.csv",
        legacy_facet_label: "oil",
      },
      {
        canonical_child_id: "india-primary-energy-supply-mtoe-gas",
        csv_path: "data/datapoints/geo/india-primary-energy-supply-mtoe-gas.csv",
        legacy_facet_label: "gas",
      },
      {
        canonical_child_id: "india-primary-energy-supply-mtoe-hydro",
        csv_path: "data/datapoints/geo/india-primary-energy-supply-mtoe-hydro.csv",
        legacy_facet_label: "hydro",
      },
      {
        canonical_child_id: "india-primary-energy-supply-mtoe-nuclear",
        csv_path: "data/datapoints/geo/india-primary-energy-supply-mtoe-nuclear.csv",
        legacy_facet_label: "nuclear",
      },
      {
        canonical_child_id: "india-primary-energy-supply-mtoe-renewable",
        csv_path: "data/datapoints/geo/india-primary-energy-supply-mtoe-renewable.csv",
        legacy_facet_label: "renewable",
      },
    ],
    meta: {
      id: "india-primary-energy-supply-mtoe",
      title: "India total primary energy supply (TPES), by source (mtoe per fiscal year)",
      description:
        "Annual total primary energy supply for India, broken down by 6 sources (coal + oil + gas + hydro + nuclear + renewables) in million tonnes of oil equivalent (mtoe). The TPES denominator behind every per-capita / per-GDP energy intensity calculation. Coal dominates (~55%); renewables is the fastest-growing bucket; nuclear is structurally small.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "mtoe",
      short_unit: "mtoe",
      icon: "flame",
      attribution_geography: "where_consumed",
      comparability: "comparable_with_normalisation",
      implementing_authority: "centre",
      methodology_vintage:
        "NITI Aayog ICED /analytics/state-wise-deep-dive (primary-energy-supply national series). Originating data: MoSPI Energy Statistics India (annual edition). ICED is the federal aggregator; not the issuing authority. National-only.",
      notes:
        "TPES = indigenous production + net imports of energy commodities, in mtoe (million tonnes of oil equivalent). The 'renewables' bucket is the publisher's aggregate (solar + wind + biomass + small-hydro + waste-to-energy combined; not broken into sub-fuels at this grain). Publisher 'total' row is dropped at canonical lift — total is computed at read time as SUM(coal + oil + gas + hydro + nuclear + renewable) per the compute-on-read parent pattern.",
    },
    // PR-U (Row 6 P.1.C commit 1): Hans-curated caveats. Three honesty cues
    // citizens need: national-only-grain, mtoe-not-citizen-unit, TPES-not-end-use.
    caveats: [
      "National figures only — this is the ALL-INDIA TPES; ICED does not publish state-level primary energy supply. A state cannot be ranked here. State-level energy is published separately as ELECTRICITY (MU/GWh) and CONSUMPTION of specific fuels (coal MT, oil products kt) — those are end-use, not primary supply.",
      "TPES is not what you USE — it is what enters the energy system. The mtoe number bundles indigenous production + net imports BEFORE conversion losses. A coal plant burns 100 mtoe of coal to deliver ~35 mtoe of electricity to homes and factories. To read household / industry consumption, use the FINAL energy consumption indicators (when published), not TPES.",
      "mtoe (million tonnes of oil equivalent) is an analyst unit, not a citizen one. 1 mtoe ≈ 11.6 billion kWh. India's ~900 mtoe in recent years works out to ~8 MWh per person per year of PRIMARY energy — but after conversion losses, only ~1.2 MWh per person per year reaches the meter as electricity. The gap is the transformation tax.",
    ],
  },

  // --- PR-V (Row 6 P.1.C 6/9, state plant load factor by fuel, 2026-05-26) ---
  // ICED `/v1/plf-metatable-data` (state-wise PLF percentage by fuel) ->
  // 1652 obs rows (36 states/UTs x 11 FYs x 8 fuels) joined into the
  // existing `energy_generation` parquet stem. Adapter:
  //   * generation.py block 3 emits plant-load-factor-pct-{fuel}
  // 8-facet Pattern A-facet on the EXISTING `fuel_type` axis. UNLIKE
  // every other facet-multiplexed energy indicator, PR-V does NOT use
  // SUB_FUEL_TO_CANONICAL collapse — PLF is a PERCENTAGE that cannot
  // be summed across fuels. Each publisher label maps 1:1 to a
  // distinct existing fuel_type value_id (bio-power -> biomass,
  // small-hydro -> small_hydro, oil-gas -> gas, others 1:1).
  // Compute-on-read parent: plant-load-factor-pct carries no
  // observation rows; the FacetPicker primitive surfaces the 8
  // children as individual series. NOTE: the axis's compute-on-read
  // total flag (allow_compute_on_read_total=True on fuel_type) is
  // semantically a footgun here -- a "Total" PLF view would be
  // SUM-of-percentages-across-fuels (nonsense). This is disclosed in
  // the citizen-facing Hans caveats below.
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_plant_load_factor_pct",
    canonical_parent_indicator_id: "plant-load-factor-pct",
    table_id: "energy.energy_generation",
    facet_axis_id: "fuel_type",
    facet_values: [
      {
        canonical_child_id: "plant-load-factor-pct-coal",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-coal.csv",
        legacy_facet_label: "coal",
      },
      {
        canonical_child_id: "plant-load-factor-pct-gas",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-gas.csv",
        legacy_facet_label: "gas",
      },
      {
        canonical_child_id: "plant-load-factor-pct-hydro",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-hydro.csv",
        legacy_facet_label: "hydro",
      },
      {
        canonical_child_id: "plant-load-factor-pct-nuclear",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-nuclear.csv",
        legacy_facet_label: "nuclear",
      },
      {
        canonical_child_id: "plant-load-factor-pct-small-hydro",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-small-hydro.csv",
        legacy_facet_label: "small_hydro",
      },
      {
        canonical_child_id: "plant-load-factor-pct-solar",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-solar.csv",
        legacy_facet_label: "solar",
      },
      {
        canonical_child_id: "plant-load-factor-pct-wind",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-wind.csv",
        legacy_facet_label: "wind",
      },
      {
        canonical_child_id: "plant-load-factor-pct-biomass",
        csv_path: "data/datapoints/geo/plant-load-factor-pct-biomass.csv",
        legacy_facet_label: "biomass",
      },
    ],
    meta: {
      id: "plant-load-factor-pct",
      title: "State plant load factor (PLF), by fuel source (% per fiscal year)",
      description:
        "Plant Load Factor — the share of nameplate capacity actually delivered as energy over a fiscal year. Per state, per fuel source (8 buckets: coal, gas, hydro, nuclear, small-hydro, solar, wind, biomass). Coal PLFs near 60% indicate healthy merit-order despatch; near 40% indicates structural underuse (stranded assets). Renewable PLFs are RESOURCE-bounded and inherently lower (solar ~20%, wind ~25%) — these are not failures.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "neutral",
      scale_hint: "linear",
      unit: "percent",
      short_unit: "%",
      icon: "activity",
      attribution_geography: "where_produced",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage:
        "NITI Aayog ICED /v1/plf-metatable-data (CEA-sourced upstream). PLF is the standard CEA metric: energy generated / (capacity × hours-in-period) × 100. Republished by ICED; not the issuing authority (plan-doc §3 Q-d).",
      notes:
        "PLF is dimensionless (%) and directly comparable across states WITHIN a fuel. NOT comparable across fuels — a 25% solar PLF is excellent, a 25% coal PLF is a stranded asset. The publisher emits 8 sub-fuels (bio-power, coal, hydro, nuclear, oil-gas, small-hydro, solar, wind); the canonical lift maps them 1:1 to existing fuel_type axis values (bio-power -> biomass, oil-gas -> gas, small-hydro -> small_hydro) with NO sub-fuel collapse step (PLF is a percentage — collapsing would compute meaningless sums).",
    },
    // PR-V (Row 6 P.1.C commit 1): Hans-curated caveats. Three honesty cues
    // citizens need: not-comparable-across-fuels, resource-vs-performance,
    // outliers-and-zero-rows-are-real.
    caveats: [
      "PLF is NOT comparable across fuels — only within a fuel. A 20% solar PLF in Rajasthan is excellent (the resource ceiling is ~22%); a 20% coal PLF in West Bengal is a stranded-asset signal. The FacetPicker keeps fuels visually separate for exactly this reason; do NOT mentally sum the 8 sub-series into a 'total' number.",
      "Renewable PLFs are RESOURCE-bounded, not performance-bounded. Solar PLF is capped by sunlight hours (~20-22% even with perfect kit). Wind PLF is capped by site quality — Tamil Nadu / Gujarat / Karnataka coastal zones reach ~25-28%; inland low-wind states cannot. Hydro and small-hydro swing 20 percentage points across drought vs monsoon years — read inter-year change, not a single year.",
      "Many state-fuel cells will be empty or show extreme values. Nuclear PLF only exists in states hosting reactors (TN, KA, RJ, GJ, MH, UP). Gas PLFs persistently below 25% across many states reflect ALL-INDIA gas-allocation shortages, not state-level despatch failures. A handful of publisher cells exceed 100% (data anomaly preserved verbatim; treat as upstream-quality flag, not a record-breaking achievement).",
    ],
  },

  // --- PR-W (Row 6 P.1.C 7/9, state power-purchase share by source, 2026-05-26) ---
  // ICED `/statelevel-power-purchase-quantum-and-cost` (state-wise
  // procurement-mix share by source) -> 2658 obs rows (36 states/UTs x
  // 10 FYs x ~7-12 sources-per-state) joined into the EXISTING
  // `energy_demand_supply` parquet stem (procurement is a demand-side
  // metric). Adapter:
  //   * demand_supply.py block 7 emits power-purchase-share-pct-{source}
  // 12-facet Pattern A-facet on the EXISTING `fuel_type` axis (now
  // extended with `hybrid_bundled` + `trading_other` value_ids).
  // PR-W is a procurement-mix indicator (where DISCOMs BUY from),
  // NOT a generation-mix (what state plants produce). Values are
  // percentages summing to ~100 per (state, FY); CANNOT collapse
  // renewable sub-fuels (same PLF-style exemption as PR-V).
  // Compute-on-read parent: power-purchase-share-pct carries no
  // observation rows; the FacetPicker primitive surfaces the 12
  // children. The "Total" view would sum percentages across sources
  // and arrive close to 100% by construction, so it's not informative
  // -- the per-source pills are where the story lives.
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_power_purchase_share_pct",
    canonical_parent_indicator_id: "power-purchase-share-pct",
    table_id: "energy.energy_demand_supply",
    facet_axis_id: "fuel_type",
    facet_values: [
      { canonical_child_id: "power-purchase-share-pct-coal", legacy_facet_label: "coal" , csv_path: "data/datapoints/geo/power-purchase-share-pct-coal.csv" },
      { canonical_child_id: "power-purchase-share-pct-gas", legacy_facet_label: "gas" , csv_path: "data/datapoints/geo/power-purchase-share-pct-gas.csv" },
      { canonical_child_id: "power-purchase-share-pct-diesel", legacy_facet_label: "diesel" , csv_path: "data/datapoints/geo/power-purchase-share-pct-diesel.csv" },
      { canonical_child_id: "power-purchase-share-pct-hydro", legacy_facet_label: "hydro" , csv_path: "data/datapoints/geo/power-purchase-share-pct-hydro.csv" },
      { canonical_child_id: "power-purchase-share-pct-nuclear", legacy_facet_label: "nuclear" , csv_path: "data/datapoints/geo/power-purchase-share-pct-nuclear.csv" },
      { canonical_child_id: "power-purchase-share-pct-small-hydro", legacy_facet_label: "small_hydro" , csv_path: "data/datapoints/geo/power-purchase-share-pct-small-hydro.csv" },
      { canonical_child_id: "power-purchase-share-pct-solar", legacy_facet_label: "solar" , csv_path: "data/datapoints/geo/power-purchase-share-pct-solar.csv" },
      { canonical_child_id: "power-purchase-share-pct-wind", legacy_facet_label: "wind" , csv_path: "data/datapoints/geo/power-purchase-share-pct-wind.csv" },
      { canonical_child_id: "power-purchase-share-pct-biomass", legacy_facet_label: "biomass" , csv_path: "data/datapoints/geo/power-purchase-share-pct-biomass.csv" },
      { canonical_child_id: "power-purchase-share-pct-renewable-other", legacy_facet_label: "renewable_other" , csv_path: "data/datapoints/geo/power-purchase-share-pct-renewable-other.csv" },
      { canonical_child_id: "power-purchase-share-pct-hybrid-bundled", legacy_facet_label: "hybrid_bundled" , csv_path: "data/datapoints/geo/power-purchase-share-pct-hybrid-bundled.csv" },
      { canonical_child_id: "power-purchase-share-pct-trading-other", legacy_facet_label: "trading_other" , csv_path: "data/datapoints/geo/power-purchase-share-pct-trading-other.csv" },
    ],
    meta: {
      id: "power-purchase-share-pct",
      title: "State power-purchase share by source (% per fiscal year)",
      description:
        "Share of total electricity purchased by a state's distribution utilities, broken down by generation source (12 buckets: coal, gas, diesel, hydro, nuclear, small-hydro, solar, wind, biomass, other-renewables, hybrid-bundled, trading-and-others). The PROCUREMENT mix (where DISCOMs buy from), not the GENERATION mix (what state plants produce). Values sum to ~100% per (state, FY). Compare against electricity-generation-gwh-{fuel} to read the trade pattern: RE-exporters vs thermal-importers.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "neutral",
      scale_hint: "linear",
      unit: "percent",
      short_unit: "%",
      icon: "shopping-cart",
      attribution_geography: "where_consumed",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "NITI Aayog ICED /statelevel-power-purchase-quantum-and-cost (PFC / Ministry of Power upstream). Per-state per-source per-FY, FY16-FY25. The publisher's totalCost field is not emitted (many nulls in early years and unit ambiguous).",
      notes:
        "12 publisher buckets map to canonical fuel_type axis values via a dedicated 1:1 dict (bio-power -> biomass; oil-gas -> gas; other-res -> renewable_other; hybrid-bundled + trading-and-others -> new value_ids hybrid_bundled + trading_other added in this PR). NO sub-fuel collapse because procurement share is a percentage that cannot be summed across sources without double-counting the same megawatt-hour.",
    },
    // PR-W: Hans-curated caveats. Three honesty cues:
    // procurement-vs-generation, hybrid-bundled-is-not-a-fuel,
    // trading-share-is-not-a-stress-signal.
    caveats: [
      "Procurement is NOT generation. A state's power-purchase mix shows what its DISCOMs BUY from -- not what its plants produce. Karnataka generates a lot of wind and solar but imports significant coal via inter-state PPAs; Bihar produces almost nothing locally and procures most of its power from central thermal plants. Compare with electricity-generation-gwh-{fuel} to see the export-import pattern.",
      "Hybrid-bundled is a CONTRACT category, not a fuel. The hybrid PPA bucket (wind + solar + storage sold as one bundle) emerged post-2022 under MNRE policy; it grows in some states while solar and wind shares stay flat -- because the SAME electrons are just being re-categorised under a different contract structure. Don't read hybrid growth as new RE; cross-reference with installed-capacity series.",
      "Trading-and-others share is NOT a stress signal. Buying ~10-20% on power exchanges (IEX / PXIL) is normal procurement strategy -- it lets DISCOMs meet demand fluctuations cheaper than via long-term PPAs. Punjab, Haryana, Delhi run high trading shares (15-25%) because their demand is peaky; this is competence, not crisis. Only when trading + UI dominates the year-on-year delta should you read a procurement-planning failure.",
    ],
  },

  // --- PR-X (Row 6 P.1.C 8/9, national final-energy consumption by sector x fuel, 2026-05-26) ---
  // ICED `/analytics/state-wise-deep-dive` (final-energy-consumption
  // national series) -> 360 obs rows (national-only, FY05-FY24, 18
  // sparse sector x fuel pairs out of the 6 x 5 = 30 Cartesian product)
  // joined into the EXISTING energy_demand_supply parquet stem (final
  // consumption is the consumer-side counterpart of TPES primary supply).
  // 18-facet Pattern A-facet on the NEW `sector_fuel_pair` axis (added
  // this PR). Publisher emits each row as a compound facet
  // "agriculture | oil"; canonical lift sanitises to "agriculture-oil".
  // National-only -- ICED does NOT publish state-level final-energy
  // consumption (per-state would require state-level MoSPI energy
  // statistics that aren't published).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/national_final_energy_consumption_by_sector_mtoe",
    canonical_parent_indicator_id: "india-final-energy-consumption-mtoe",
    table_id: "energy.energy_demand_supply",
    facet_axis_id: "sector_fuel_pair",
    facet_values: [
      { canonical_child_id: "india-final-energy-consumption-mtoe-agriculture-electricity", legacy_facet_label: "agriculture-electricity" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-agriculture-electricity.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-agriculture-gas", legacy_facet_label: "agriculture-gas" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-agriculture-gas.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-agriculture-oil", legacy_facet_label: "agriculture-oil" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-agriculture-oil.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-cgd-and-others-gas", legacy_facet_label: "cgd-and-others-gas" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-cgd-and-others-gas.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-commercial-electricity", legacy_facet_label: "commercial-electricity" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-commercial-electricity.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-commercial-oil", legacy_facet_label: "commercial-oil" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-commercial-oil.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-industry-coal", legacy_facet_label: "industry-coal" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-industry-coal.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-industry-electricity", legacy_facet_label: "industry-electricity" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-industry-electricity.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-industry-gas", legacy_facet_label: "industry-gas" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-industry-gas.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-industry-oil", legacy_facet_label: "industry-oil" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-industry-oil.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-non-energy-gas", legacy_facet_label: "non-energy-gas" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-non-energy-gas.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-non-energy-oil", legacy_facet_label: "non-energy-oil" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-non-energy-oil.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-other-electricity", legacy_facet_label: "other-electricity" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-other-electricity.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-other-oil", legacy_facet_label: "other-oil" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-other-oil.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-residential-electricity", legacy_facet_label: "residential-electricity" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-residential-electricity.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-residential-oil", legacy_facet_label: "residential-oil" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-residential-oil.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-transport-electricity", legacy_facet_label: "transport-electricity" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-transport-electricity.csv" },
      { canonical_child_id: "india-final-energy-consumption-mtoe-transport-oil", legacy_facet_label: "transport-oil" , csv_path: "data/datapoints/geo/india-final-energy-consumption-mtoe-transport-oil.csv" },
    ],
    meta: {
      id: "india-final-energy-consumption-mtoe",
      title: "India final energy consumption, by sector and source (mtoe per fiscal year)",
      description:
        "Final energy consumed in India broken down by end-use sector x fuel (18 sparse pairs out of 6 sectors x 5 fuels). 'Final' = what households, industry, transport actually USE -- AFTER conversion losses from primary energy (TPES). Industry-coal + transport-oil typically dominate; residential-electricity + agriculture-electricity track grid extension and pump-set use. Compare with india-primary-energy-supply-mtoe to see the conversion-loss gap.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "mtoe",
      short_unit: "mtoe",
      icon: "flame",
      attribution_geography: "where_consumed",
      comparability: "comparable_with_normalisation",
      implementing_authority: "centre",
      methodology_vintage:
        "NITI Aayog ICED /analytics/state-wise-deep-dive (final-energy-consumption national series). Originating data: MoSPI Energy Statistics India (annual edition). ICED is the federal aggregator; not the issuing authority. National-only.",
      notes:
        "18 sparse (sector x fuel) pairs out of the 6 x 5 Cartesian product. Many cells are structurally zero or near-zero (e.g. residential coal is rare; non-energy electricity is undefined) and the publisher does NOT emit them at all -- treat absent pairs as 'not measured', not 'zero'. The canonical lift sanitises publisher 'sector | fuel' strings into kebab pair-ids on the NEW sector_fuel_pair axis. Compute-on-read parent total = SUM(all 18 children) = total final-energy consumption.",
    },
    // PR-X (Row 6 P.1.C commit 1): Hans-curated caveats. Three honesty cues:
    // final-vs-primary distinction, sparse-pairs-vs-zero, sector-naming-stretch.
    caveats: [
      "FINAL energy is what you USE; PRIMARY energy is what enters the system. India's ~600 mtoe of final consumption is what households, industry, transport actually consume -- well below the ~900 mtoe of TPES (primary supply) because power plants, refineries and transmission lose ~30% as conversion + line losses. To compare 'how much do we consume vs produce' meaningfully, use FINAL on the consumer side and PRIMARY on the production / import side; mixing them double-counts the transformation tax.",
      "Many publisher cells are absent, NOT zero. The dataset emits only 18 of the 30 possible (sector x fuel) pairs -- residential coal, transport gas, agriculture coal etc. are missing because either they don't exist meaningfully in India (transport gas was negligible pre-CGD rollout) or the publisher does not measure them at this grain. Absent cells should NOT be imputed as zero in any visualisation -- a sparse stacked bar with white-space gaps is more honest than a fake-flat zero series.",
      "Sector names are MoSPI taxonomy, not citizen-intuitive labels. 'Non-energy' = oil + gas used as petrochemical / fertiliser FEEDSTOCK, not for combustion (the carbon ends up embedded in plastic / urea, not the atmosphere). 'CGD and others' = city-gas-distribution networks (piped natural gas to households + CNG for vehicles); the 'others' is a catch-all for small gas-distribution slivers. 'Other' (no qualifier) covers fishing, mining and a long tail of un-classified end-uses. These names should ideally be re-labelled at the renderer for the /t/energy citizen surface; we preserve publisher names verbatim in the canonical layer.",
    ],
  },

  // --- PR-Y (Row 6 P.1.C 9/9, state-wise renewable grid capacity MW, 2026-05-26) ---
  // RBI Handbook 2024-25 edition, Table 143 -> 585 obs (36 states/UTs x 18
  // calendar years 2007-2024). Pattern A-SINGLE -- the publisher emits no
  // per-source split (combined wind + solar + small-hydro + biomass +
  // waste-to-energy as one MW number) so this is a scalar indicator, not
  // a facet-multiplexed one. Lifts onto the EXISTING
  // energy_installed_capacity parquet stem. Adapter: installed_capacity.py
  // final block emits renewable-grid-capacity-mw passthrough.
  {
    kind: "single",
    legacy_artifact_id: "energy/state_renewable_grid_capacity_mw",
    canonical_indicator_id: "renewable-grid-capacity-mw",
    csv_path: "data/datapoints/geo/renewable-grid-capacity-mw.csv",
    table_id: "energy.energy_installed_capacity",
    meta: {
      id: "renewable-grid-capacity-mw",
      title: "State installed grid-connected renewable capacity (MW, end-March snapshot)",
      description:
        "Cumulative grid-connected renewable-power generation capacity installed in the state (MW), as at end-March of the calendar year. Combined wind + solar + small-hydro + biomass + waste-to-energy -- RBI's Table 143 does NOT publish a per-source split. The closest proxy for a state-level renewable-capacity time series with deep history (18 years). National total grew from ~10 GW in 2007 to ~144 GW in 2024 (14x). Rajasthan, Gujarat, Tamil Nadu, Karnataka, Maharashtra dominate; Bihar, Odisha, NE states remain in single-digit GW territory.",
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
      implementing_authority: "centre",
      methodology_vintage:
        "RBI Handbook of Statistics on Indian States 2024-25 edition, Table 143. Originating data: MoSPI Energy Statistics, Government of India. End-March cumulative installed-capacity snapshots, calendar-year-labelled (catalogue period uses YYYY-04 sentinel).",
      notes:
        "Telangana data from 2015 (state created June 2014); Ladakh from 2023 (UT created October 2019). 'Total' / 'Others' rows in the source workbook are skipped at parse time. Compare with PR-R `rooftop-solar-capacity-mw` to see what fraction of the renewable total is rooftop (typically <10% of total RE capacity).",
    },
    // PR-Y: Hans-curated caveats. Three honesty cues: combined-RE-no-split,
    // cumulative-installed-not-generation, RBI-snapshot-cadence.
    caveats: [
      "Combined RE total -- no per-source split. RBI Table 143 lumps wind + solar + small-hydro + biomass + waste-to-energy into ONE megawatt number per state per year. To see the source mix WITHIN a state's renewable fleet, cross-reference with PR-Q's installed-capacity-by-source series + PR-R's rooftop-solar capacity. The trade-off: this series goes back to 2007 (deep history); the per-source ICED series only starts from FY17.",
      "Installed capacity is NOT energy delivered. A state with 25 GW of RE capacity that runs at 20% plant load factor delivers 5 GW-average -- less than a single 4 GW coal plant. Use PR-V's plant-load-factor by fuel + PR-Q's electricity-generation-gwh to convert capacity into ACTUAL energy. Cumulative MW alone is the 'how much steel is on the ground' metric, not the 'how much electricity is flowing' metric.",
      "End-March snapshot vs financial-year accumulation. This series is an end-March STOCK reading (cumulative MW as at March 31 of the labelled year). Capacity ADDED during a fiscal year is the difference between two consecutive years; the series itself does NOT show annual flow. RBI re-publishes the same numbers as MoSPI Energy Statistics -- expect minor revisions (~1-2%) when MoSPI restates back-years; the latest RBI edition supersedes older ones for each year-cell.",
    ],
  },

  // --- 12: ACS-ARR gap on electricity sales (₹/kWh), NITI ICED ---
  {
    kind: "single",
    legacy_artifact_id: "energy/state_acs_arr_gap_inr_per_kwh",
    canonical_indicator_id: "acs-arr-gap-inr-per-kwh",
    csv_path: "data/datapoints/geo/acs-arr-gap-inr-per-kwh.csv",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "acs-arr-gap-inr-per-kwh",
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
    canonical_indicator_id: "distribution-efficiency-pct-billing",
    csv_path: "data/datapoints/geo/distribution-efficiency-pct-billing.csv",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "distribution-efficiency-pct-billing",
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
    canonical_indicator_id: "distribution-efficiency-pct-collection",
    csv_path: "data/datapoints/geo/distribution-efficiency-pct-collection.csv",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "distribution-efficiency-pct-collection",
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
    canonical_indicator_id: "distribution-efficiency-pct-td-loss",
    csv_path: "data/datapoints/geo/distribution-efficiency-pct-td-loss.csv",
    table_id: "energy.energy_distribution_performance",
    meta: {
      id: "distribution-efficiency-pct-td-loss",
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
  //     (rpo-compliance-pct-solar / -non-solar / -total) keyed on
  //     `dimension_values.rpo_segment ∈ {"solar","non_solar","total"}` (snake-case).
  //   * Parent `rpo-compliance-pct` is compute-on-read per
  //     indicator-naming.md D29 (parent has `source_id = null`).
  //   * Adapter fuses the 3 child rows into ONE IndicatorArtifact with
  //     `rows[].facet = legacy_facet_label` (hyphenated, preserves citizen-
  //     readable form). Sources aggregate from the children
  //     (parent has no source FK).
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "energy/state_rpo_compliance_pct",
    canonical_parent_indicator_id: "rpo-compliance-pct",
    table_id: "energy.energy_distribution_performance",
    facet_axis_id: "rpo_segment",
    facet_values: [
      {
        canonical_child_id: "rpo-compliance-pct-solar",
        csv_path: "data/datapoints/geo/rpo-compliance-pct-solar.csv",
        legacy_facet_label: "solar",
      },
      {
        canonical_child_id: "rpo-compliance-pct-non-solar",
        csv_path: "data/datapoints/geo/rpo-compliance-pct-non-solar.csv",
        legacy_facet_label: "non-solar",
      },
      {
        canonical_child_id: "rpo-compliance-pct-total",
        csv_path: "data/datapoints/geo/rpo-compliance-pct-total.csv",
        legacy_facet_label: "total",
      },
    ],
    meta: {
      id: "rpo-compliance-pct",
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
  //     as `pashu-aadhaar-count-<species>` (10 species enum).
  //   * State-rollup rows (~211) are auto-emitted in the SAME envelope as
  //     `pashu-aadhaar-count-<species>` (state-grain rollup) (derivation='sum', reusing
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
  // facet child. comparability='directional_only' suppresses rank in the
  // canonical semantics; grapher/indicator_render.json owns the matching
  // `no_rank_table` renderer hint (a "Bihar > Tamil Nadu in cattle tags"
  // rank order would be a citizen-misleading number — Bihar tags more
  // cattle because Bihar HAS more cattle).











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
  // PR B.05 (#294, 2026-05-25) extended `IndicatorChoropleth.svelte` to
  // dispatch on `artifact.coverage.admin_level`: "district" routes to the
  // national LGD-keyed district polygon layer (INDIA_DISTRICTS, 784 rows);
  // anything else falls through to the state layer (INDIA_STATES, 36 rows).
  // PR B.05.f (#295) mounted the cattle district-grain card on
  // `/t/agriculture` as the hero choropleth. Phase 3.B (this PR) extends
  // the same pattern to the 9 other species that ship in the same
  // `livestock_pashu_aadhaar` canonical Parquet: buffalo / goat / sheep /
  // pig / mithun / yak / horse / donkey / mule. Each district descriptor
  // is the source-of-truth grain (per ADR-0043); the state-grain sibling
  // above is the SUM rollup auto-emitted in the same adapter run.
  //
  // Cattle remains the hero (default + featured on `/t/agriculture`)
  // because it has the highest district coverage at 758 districts and
  // the clearest choropleth signal. The other 9 species ship at district
  // grain on the same chapter without `default: true` / `featured: true`;
  // a citizen drills in by clicking the species card. Sparse-coverage
  // species (horse 6, donkey 1, mule 1) carry an explicit honesty note:
  // the choropleth is mostly grey because the tagging programme has
  // barely begun for these animals, not because the animals are absent.
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_cattle",
    canonical_indicator_id: "pashu-aadhaar-count-cattle",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-cattle.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-cattle",
      title: "Cattle tagged with Pashu Aadhaar",
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
      notes:
        "Tagged count is NOT a livestock census. Coverage varies by district within a state -- even within Karnataka or Andhra Pradesh (national leaders), rollout reaches some districts before others. Read alongside the 20th Livestock Census for the denominator. This is the source-of-truth grain; state values are the SUM rollup.",
    },
  },

  // --- Phase 3.B (2026-05-25) --- district-grain fan-out to 9 more species
  // on the same `livestock_pashu_aadhaar` canonical Parquet. Each entry
  // is the source-of-truth grain (ADR-0043); the state-grain sibling
  // above is the SUM rollup auto-emitted in the same adapter run.
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_buffalo",
    canonical_indicator_id: "pashu-aadhaar-count-buffalo",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-buffalo.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-buffalo",
      title: "Buffaloes tagged with Pashu Aadhaar",
      description:
        "District total of buffaloes issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 698 districts with non-zero counts).",
      notes:
        "Tagged count is NOT a livestock census. Buffalo tagging concentrates in the dairy belt (UP, Punjab, Haryana, Andhra Pradesh, Gujarat); North-East and tribal districts may show zero because the programme has not reached them yet, not because buffaloes are absent. Read alongside the 20th Livestock Census for the denominator. State values are the SUM rollup.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_goat",
    canonical_indicator_id: "pashu-aadhaar-count-goat",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-goat.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-goat",
      title: "Goats tagged with Pashu Aadhaar",
      description:
        "District total of goats issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 598 districts with non-zero counts).",
      notes:
        "Tagged count is NOT a livestock census. Goats are a smallholder species; tagging coverage follows extension-worker presence, not goat presence. Rajasthan, West Bengal, UP lead by absolute count; districts in arid Maharashtra and Karnataka may under-report despite large goat populations. Read alongside the 20th Livestock Census for the denominator.",
    },
  },
  // Goat cohort PR (Row 5 PR-P, 2026-05-27): state-grain + district-grain
  // siblings on the same livestock_pashu_aadhaar canonical table. Both
  // carry Hans-curated caveats[] honouring the 3-bullet rhythm pinned by
  // the PR-P regex assertions in indicator-from-canonical.test.ts (L550).
  // canonical_indicator_id is grain-less per ADR-0044 (id = measure-unit-facet;
  // grain is dispatched from entity_kind at read time).
  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_goat",
    canonical_indicator_id: "pashu-aadhaar-count-goat",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-goat.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-goat",
      title: "Goats tagged with Pashu Aadhaar (state)",
      description:
        "State SUM rollup of goats issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Auto-emitted by the canonical adapter from district source-of-truth rows per ADR-0043.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationStateWise SUM rollup of district source-of-truth, snapshot 2026-05-25; FY 2024-25.",
      notes:
        "Tagged count is NOT a livestock census. State values are the SUM rollup of districts that have reached programme rollout; pastoral migration across district and state lines confounds attribution. Read alongside the 20th Livestock Census for the denominator.",
    },
    caveats: [
      "Rajasthan's Bhopa and Banjara pastoral communities herd migratory goat flocks cross-district and cross-state; tags follow the registering office, not the grazing geography, so headline counts attribute roaming herds to one state.",
      "Same coverage gap as cattle and buffalo: the 20th Livestock Census 2019 reports ~149M goats nationwide (the largest livestock category), but vet-camp triage runs cattle-first then buffalo, so goat coverage lags 6-12 months.",
      "INFORMAL meat-economy bias inflates Andhra Pradesh and Telangana counts via Hyderabad mutton-trader vet camps; Bihar and eastern UP under-report not because herds are smaller but because programme formalisation lags.",
    ],
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/district_pashu_aadhaar_count_goat",
    canonical_indicator_id: "pashu-aadhaar-count-goat",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-goat.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "district-pashu-aadhaar-count-goat",
      title: "Goats tagged with Pashu Aadhaar (district)",
      description:
        "District source-of-truth count of goats issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. The state-grain sibling is the SUM rollup auto-emitted in the same canonical adapter run per ADR-0043.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043).",
      notes:
        "Tagged count is NOT a livestock census. District aggregation hides intra-district pastoral migration; Rajasthan's Jaisalmer and Barmer districts in particular may double-count herds that move between them in a single tagging season. Read alongside the 20th Livestock Census for the denominator.",
    },
    caveats: [
      "District aggregation hides intra-district pastoral migration; Rajasthan's Jaisalmer and Barmer or Gujarat's Kutch may double-count herds that move between adjacent districts within a single tagging season.",
      "Same coverage gap as cattle and buffalo: the 20th Livestock Census 2019 reports ~149M goats nationwide (the largest livestock category), but vet-camp triage runs cattle-first then buffalo, so goat coverage lags 6-12 months at district grain.",
      "INFORMAL meat-economy bias inflates Hyderabad and surrounding Andhra Pradesh and Telangana districts via mutton-trader vet camps; Bihar and eastern UP districts under-report because programme formalisation lags, not because herds are smaller.",
    ],
  },
  // Cattle cohort PR (Row 5 PR-P cohort 2/3, 2026-05-27): state-grain +
  // district-grain siblings on the same livestock_pashu_aadhaar canonical
  // table. Mirrors the goat cohort (PR #428) field shape; Hans-curated
  // caveats[] pinned by the PR-P cattle regex assertions in
  // indicator-from-canonical.test.ts (L499) and the B.03 district smoke
  // describe (L1320). canonical_indicator_id is grain-less per ADR-0044.
  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_cattle",
    canonical_indicator_id: "state-pashu-aadhaar-count-cattle",
    // CSV is single-file per ADR-0043 (sub-state grain source-of-truth +
    // auto-emitted state SUM rollup share the same file); the descriptor
    // grain is dispatched at read time via the entity_kind row filter.
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-cattle.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-cattle",
      title: "Cattle tagged with Pashu Aadhaar (state)",
      description:
        "State SUM rollup of cattle issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Auto-emitted by the canonical adapter from district source-of-truth rows per ADR-0043.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationStateWise SUM rollup of district source-of-truth, snapshot 2026-05-25; FY 2024-25.",
      notes:
        "Tagged count is NOT a livestock census. State values are the SUM rollup of districts that have reached programme rollout; the 20th Livestock Census 2019 reports ~193M cattle nationwide, so 40-60% coverage is typical at state grain.",
    },
    caveats: [
      "ANIMALS TAGGED, not cattle owned: the 20th Livestock Census 2019 counts ~193M cattle nationwide, while NDLM Pashu Aadhaar coverage runs at 40-60% coverage by state. Tag growth tracks vet-camp effort and Indus Database enrolment, not herd growth.",
      "Karnataka (KMF) and Andhra Pradesh (dairy-coop vet camps) lead by tag count; Manipur, Mizoram and Bihar trail not because herds are smaller but because dairy-coop networks and programme effort are weaker there. Headline ranks reflect rollout, not population.",
      "Each animal carries a unique 12-digit RFID tag persisted in the Indus Database; cattle lifespans of 12-15 years mean FY-end snapshot counts include retired and deceased animals whose tags have not yet been retired, inflating live-herd estimates.",
    ],
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/district_pashu_aadhaar_count_cattle",
    canonical_indicator_id: "district-pashu-aadhaar-count-cattle",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-cattle.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "district-pashu-aadhaar-count-cattle",
      title: "Cattle tagged with Pashu Aadhaar (district)",
      description:
        "District source-of-truth count of cattle issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. The state-grain sibling is the SUM rollup auto-emitted in the same canonical adapter run per ADR-0043.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043).",
      notes:
        "Tagged count is NOT a livestock census. District aggregation hides transhumant herds in Himachal Pradesh, Uttarakhand, and Jammu and Kashmir that move seasonally between bagh districts. Read alongside the 20th Livestock Census for the denominator.",
    },
    caveats: [
      "ANIMALS TAGGED, not cattle owned: the 20th Livestock Census 2019 counts ~193M cattle nationwide, while NDLM Pashu Aadhaar coverage runs at 40-60% coverage by district. District tag totals reflect Indus Database enrolment, not herd size.",
      "Karnataka and Andhra Pradesh districts lead by tag count via strong dairy-coop vet camps; Manipur, Mizoram and Bihar districts trail because programme effort and dairy-coop reach are weaker, not because cattle herds are smaller there.",
      "Each animal carries a unique 12-digit RFID tag persisted in the Indus Database; transhumant cattle in Himachal Pradesh, Uttarakhand and Jammu and Kashmir cross district lines seasonally, so FY-end snapshot counts attribute roaming herds to whichever district registered the tag.",
    ],
  },
  // Buffalo cohort PR (Row 5 PR-P cohort 3/3, 2026-05-27): buffalo state-grain
  // + district-grain siblings on the same livestock_pashu_aadhaar canonical
  // table. Mirrors cattle cohort (PR #429) field shape; Hans-curated caveats[]
  // pinned by the PR-P buffalo regex assertions in
  // indicator-from-canonical.test.ts (L524). canonical_indicator_id is
  // grain-prefixed per ADR-0044 + cattle precedent so the table-driven
  // describes at L1999/L2063 can distinguish state vs district rows.
  {
    kind: "single",
    legacy_artifact_id: "agriculture/state_pashu_aadhaar_count_buffalo",
    canonical_indicator_id: "state-pashu-aadhaar-count-buffalo",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-buffalo.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "state-pashu-aadhaar-count-buffalo",
      title: "Buffaloes tagged with Pashu Aadhaar (state)",
      description:
        "State SUM rollup of buffaloes issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Auto-emitted by the canonical adapter from district source-of-truth rows per ADR-0043.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationStateWise SUM rollup of district source-of-truth, snapshot 2026-05-25; FY 2024-25.",
      notes:
        "Tagged count is NOT a livestock census. The 20th Livestock Census 2019 reports ~110M buffaloes nationwide, ~55% concentrated in UP, Punjab, Haryana and Rajasthan (Murrah breed milk-dairy belt). State tag totals reflect cooperative reach (Verka, Vita, Amul, NDDB) more than natural distribution.",
    },
    caveats: [
      "Buffaloes cluster in the milk-dairy belt: UP, Punjab, Haryana and Rajasthan hold ~55% of Indian buffaloes via the Murrah breed economics, while Kerala and the NE have negligible herds. Tag-count ranks reproduce the milk-dairy belt geography, not a uniform national programme.",
      "Same coverage gap as cattle: the 20th Livestock Census 2019 counts ~110M buffaloes nationwide vs ~193M cattle tagged at 40-60% coverage; buffalo coverage trails cattle by 3-6 months because vet-camp triage runs cattle-first in Gujarat NDDB and Karnataka KMF rollouts.",
      "Gujarat tag totals are inflated by the Amul dairy-cooperative network which runs vet camps across district lines; Maharashtra trails despite a large buffalo herd because dairy cooperatives are weaker outside the Mumbai-Pune corridor, and male draught buffaloes are mostly sold for meat before tagging which skews counts heavily female.",
    ],
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/district_pashu_aadhaar_count_buffalo",
    canonical_indicator_id: "district-pashu-aadhaar-count-buffalo",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-buffalo.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "district-pashu-aadhaar-count-buffalo",
      title: "Buffaloes tagged with Pashu Aadhaar (district)",
      description:
        "District source-of-truth count of buffaloes issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. The state-grain sibling is the SUM rollup auto-emitted in the same canonical adapter run per ADR-0043.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043).",
      notes:
        "Tagged count is NOT a livestock census. District aggregation in Gujarat (Anand, Kheda) is inflated by Amul chilling-centre vet camps that cross district lines; swamp-buffalo districts in Assam and coastal AP are structurally under-counted because vet camps prioritise dryland Murrah-cluster herds.",
    },
    caveats: [
      "Buffaloes cluster in the milk-dairy belt: UP, Punjab, Haryana districts dominate via the Murrah breed economics, while Kerala and NE districts hold negligible herds. District tag-count ranks reproduce the milk-dairy belt geography, not programme reach across districts.",
      "Same coverage gap as cattle: the 20th Livestock Census 2019 counts ~110M buffaloes nationwide vs ~193M cattle tagged at 40-60% coverage; buffalo district coverage trails cattle tagged by 3-6 months because vet-camp triage runs cattle-first in district rollouts.",
      "Gujarat district totals (Anand, Kheda) are inflated by Amul-owned chilling-centre vet camps that cross district lines; Maharashtra districts trail despite large buffalo herds because dairy cooperatives are weaker outside the Mumbai-Pune corridor, and male draught buffalo calves are sold for meat before tagging which skews FY-end counts heavily female.",
    ],
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_sheep",
    canonical_indicator_id: "pashu-aadhaar-count-sheep",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-sheep.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-sheep",
      title: "Sheep tagged with Pashu Aadhaar",
      description:
        "District total of sheep issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 426 districts with non-zero counts).",
      notes:
        "Tagged count is NOT a livestock census. Sheep concentrate in Rajasthan, Karnataka, Andhra Pradesh, Tamil Nadu, and Jammu and Kashmir; districts outside these belts may show zero because the species is genuinely scarce there, not because tagging is missing. Read alongside the 20th Livestock Census for the denominator.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_pig",
    canonical_indicator_id: "pashu-aadhaar-count-pig",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-pig.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-pig",
      title: "Pigs tagged with Pashu Aadhaar",
      description:
        "District total of pigs issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 428 districts with non-zero counts).",
      notes:
        "Tagged count is NOT a livestock census. Pig tagging concentrates in the North-East (Assam, Nagaland, Meghalaya) and Kerala; mainland districts often show zero because pig farming is genuinely small-scale there. Read alongside the 20th Livestock Census for the denominator.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_mithun",
    canonical_indicator_id: "pashu-aadhaar-count-mithun",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-mithun.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-mithun",
      title: "Mithun tagged with Pashu Aadhaar",
      description:
        "District total of mithun issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 232 districts with non-zero counts).",
      notes:
        "Tagged count is NOT a livestock census. Mithun (Bos frontalis) is a North-East-only species; near-total district coverage shows only in Arunachal Pradesh, Nagaland, Manipur, Mizoram. Mainland districts show zero because the species is absent, not because tagging failed. Read alongside the 20th Livestock Census for the denominator.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_yak",
    canonical_indicator_id: "pashu-aadhaar-count-yak",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-yak.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-yak",
      title: "Yak tagged with Pashu Aadhaar",
      description:
        "District total of yak issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 235 districts with non-zero counts).",
      notes:
        "Tagged count is NOT a livestock census. Yak is a high-Himalayan species; coverage is concentrated in Ladakh, Himachal Pradesh, Sikkim, Arunachal Pradesh. Lower-altitude districts show zero because the species is absent, not because tagging failed. Read alongside the 20th Livestock Census for the denominator.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_horse",
    canonical_indicator_id: "pashu-aadhaar-count-horse",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-horse.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-horse",
      title: "Horses tagged with Pashu Aadhaar",
      description:
        "District total of horses (including ponies) issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 6 districts with non-zero counts).",
      notes:
        "Equine tagging is at the early-rollout stage; only 6 districts nationwide report any horses tagged. The choropleth is mostly grey because the programme has barely begun for equines, not because horses are absent. Tagged count is NOT a livestock census.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_donkey",
    canonical_indicator_id: "pashu-aadhaar-count-donkey",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-donkey.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-donkey",
      title: "Donkeys tagged with Pashu Aadhaar",
      description:
        "District total of donkeys issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 1 district with non-zero count).",
      notes:
        "Equine tagging is at the early-rollout stage; only 1 district nationwide reports any donkeys tagged. The choropleth is almost entirely grey because the programme has barely begun for equines, not because donkeys are absent. Tagged count is NOT a livestock census.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/pashu_aadhaar_count_mule",
    canonical_indicator_id: "pashu-aadhaar-count-mule",
    csv_path: "data/datapoints/geo/pashu-aadhaar-count-mule.csv",
    table_id: "livestock.livestock_pashu_aadhaar",
    meta: {
      id: "pashu-aadhaar-count-mule",
      title: "Mules tagged with Pashu Aadhaar",
      description:
        "District total of mules issued a 12-digit Pashu Aadhaar tag under NDLM Bharat Pashudhan. Source-of-truth for the Pashu Aadhaar series per ADR-0043; the state-grain sibling indicator is the SUM rollup auto-emitted in the same canonical adapter run.",
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
        "NDLM Bharat Pashudhan getAnimalRegistrationDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 (district source-of-truth per ADR-0043; 1 district with non-zero count).",
      notes:
        "Equine tagging is at the early-rollout stage; only 1 district nationwide reports any mules tagged. The choropleth is almost entirely grey because the programme has barely begun for equines, not because mules are absent. Tagged count is NOT a livestock census.",
    },
  },

  // --- Phase 3.C-partial Owner Reg (2026-05-25) --- 2 facet-multiplexed
  // parent fanning out to 6 landholding-bracket children. Catalogue
  // parent is compute-on-read (parent_indicator_id=null, zero canonical
  // rows); the renderer SUMs children to materialise the parent value.
  // Landholding brackets aligned with Agriculture Census 2015-16.
  // `not_specified` aggregates rows where the owner did not self-declare
  // a holding size. The composite gender axis was collapsed at adapter
  // time (Phase 2.A) per Hans honest-renderer rule. Per ADR-0044, grain
  // lives on entity_kinds[] not in the id; state-grain rows share the
  // same indicator_id (entity_id alone distinguishes), SUM-rolled from
  // district children per ADR-0043.
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "agriculture/livestock_owner_reg_count",
    canonical_parent_indicator_id: "livestock-owner-reg-count",
    table_id: "livestock.livestock_owner_registration",
    facet_axis_id: "landholding",
    facet_values: [
      {
        canonical_child_id: "livestock-owner-reg-count-landless-marginal",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-landless-marginal.csv",
        legacy_facet_label: "landless_marginal",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-small",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-small.csv",
        legacy_facet_label: "small",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-semi-medium",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-semi-medium.csv",
        legacy_facet_label: "semi_medium",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-medium",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-medium.csv",
        legacy_facet_label: "medium",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-large",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-large.csv",
        legacy_facet_label: "large",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-not-specified",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-not-specified.csv",
        legacy_facet_label: "not_specified",
      },
    ],
    meta: {
      id: "livestock-owner-reg-count",
      title: "Registered livestock owners, by landholding",
      description:
        "Number of livestock owners registered under NDLM Bharat Pashudhan, broken out by landholding bracket. District is the source-of-truth grain per ADR-0043; the state-grain sibling shares the same indicator_id (entity_id alone distinguishes) and is the SUM rollup auto-emitted in the same canonical adapter run. Landholding bracket is the citizen-meaningful axis: landless / marginal smallholders are the dominant register; large landholders the smallest cohort.",
      entity_kind: "district",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "owners",
      short_unit: "owners",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getOwnerRegLandHoldingDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 only (CY 2024 deferred). Landholding brackets aligned with Agriculture Census 2015-16. `not_specified` aggregates rows where the owner did not self-declare a holding size. 741 districts with non-zero counts.",
      notes:
        "Registered owners is NOT total owners. The bulk of the register is `not_specified` because the registration form does not require a holding declaration; do not read the 5 named brackets as the only owners. Composite gender axis collapsed at Phase 2.A adapter time. State-grain auto-summed from district children per ADR-0043.",
    },
  },

  // --- Grain-prefix legacy id aliases (2026-05-27) --- topics.json still
  // references the pre-grain-rip ids `state_livestock_owner_reg_count` and
  // `district_livestock_owner_reg_count`. Per ADR-0044 the canonical id is
  // grain-free (`livestock-owner-reg-count`); these 2 aliases route both
  // legacy lookups to the SAME facet-multiplexed descriptor above. Only
  // legacy_artifact_id and meta.entity_kind differ; everything else is
  // verbatim. Mirrors precedent of post-grain-rip 404 closures in
  // PRs #280/#282/#293. See docs/concepts/indicator-naming.md.
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "agriculture/state_livestock_owner_reg_count",
    canonical_parent_indicator_id: "livestock-owner-reg-count",
    table_id: "livestock.livestock_owner_registration",
    facet_axis_id: "landholding",
    facet_values: [
      {
        canonical_child_id: "livestock-owner-reg-count-landless-marginal",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-landless-marginal.csv",
        legacy_facet_label: "landless_marginal",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-small",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-small.csv",
        legacy_facet_label: "small",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-semi-medium",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-semi-medium.csv",
        legacy_facet_label: "semi_medium",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-medium",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-medium.csv",
        legacy_facet_label: "medium",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-large",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-large.csv",
        legacy_facet_label: "large",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-not-specified",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-not-specified.csv",
        legacy_facet_label: "not_specified",
      },
    ],
    meta: {
      id: "livestock-owner-reg-count",
      title: "Registered livestock owners, by landholding",
      description:
        "Number of livestock owners registered under NDLM Bharat Pashudhan, broken out by landholding bracket. District is the source-of-truth grain per ADR-0043; the state-grain sibling shares the same indicator_id (entity_id alone distinguishes) and is the SUM rollup auto-emitted in the same canonical adapter run. Landholding bracket is the citizen-meaningful axis: landless / marginal smallholders are the dominant register; large landholders the smallest cohort.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "owners",
      short_unit: "owners",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getOwnerRegLandHoldingDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 only (CY 2024 deferred). Landholding brackets aligned with Agriculture Census 2015-16. `not_specified` aggregates rows where the owner did not self-declare a holding size. 741 districts with non-zero counts.",
      notes:
        "Registered owners is NOT total owners. The bulk of the register is `not_specified` because the registration form does not require a holding declaration; do not read the 5 named brackets as the only owners. Composite gender axis collapsed at Phase 2.A adapter time. State-grain auto-summed from district children per ADR-0043.",
    },
  },
  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "agriculture/district_livestock_owner_reg_count",
    canonical_parent_indicator_id: "livestock-owner-reg-count",
    table_id: "livestock.livestock_owner_registration",
    facet_axis_id: "landholding",
    facet_values: [
      {
        canonical_child_id: "livestock-owner-reg-count-landless-marginal",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-landless-marginal.csv",
        legacy_facet_label: "landless_marginal",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-small",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-small.csv",
        legacy_facet_label: "small",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-semi-medium",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-semi-medium.csv",
        legacy_facet_label: "semi_medium",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-medium",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-medium.csv",
        legacy_facet_label: "medium",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-large",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-large.csv",
        legacy_facet_label: "large",
      },
      {
        canonical_child_id: "livestock-owner-reg-count-not-specified",
        csv_path: "data/datapoints/geo/livestock-owner-reg-count-not-specified.csv",
        legacy_facet_label: "not_specified",
      },
    ],
    meta: {
      id: "livestock-owner-reg-count",
      title: "Registered livestock owners, by landholding",
      description:
        "Number of livestock owners registered under NDLM Bharat Pashudhan, broken out by landholding bracket. District is the source-of-truth grain per ADR-0043; the state-grain sibling shares the same indicator_id (entity_id alone distinguishes) and is the SUM rollup auto-emitted in the same canonical adapter run. Landholding bracket is the citizen-meaningful axis: landless / marginal smallholders are the dominant register; large landholders the smallest cohort.",
      entity_kind: "district",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "owners",
      short_unit: "owners",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan getOwnerRegLandHoldingDistrictWise endpoint snapshot 2026-05-25; FY 2024-25 only (CY 2024 deferred). Landholding brackets aligned with Agriculture Census 2015-16. `not_specified` aggregates rows where the owner did not self-declare a holding size. 741 districts with non-zero counts.",
      notes:
        "Registered owners is NOT total owners. The bulk of the register is `not_specified` because the registration form does not require a holding declaration; do not read the 5 named brackets as the only owners. Composite gender axis collapsed at Phase 2.A adapter time. State-grain auto-summed from district children per ADR-0043.",
    },
  },

  // --- Phase 3.C-partial NAIP IV (2026-05-25) --- 8 single descriptors,
  // one per metric family per grain. No parent indicator (units differ
  // across families: events vs calves vs farmers). NAIP IV is a SELECT-
  // DISTRICT programme: 8 states/UTs report zero coverage upstream
  // (Kerala, Punjab, Puducherry, Chandigarh, Delhi, Lakshadweep, A&N,
  // D&NH+D&D); this is NOT a defect. For `calves_born`, the sex axis was
  // collapsed via SUM at Phase 2.C adapter time. State-grain auto-summed
  // from district children per ADR-0043.
  {
    kind: "single",
    legacy_artifact_id: "agriculture/livestock_naip_iv_inseminations",
    canonical_indicator_id: "livestock-naip-iv-inseminations",
    csv_path: "data/datapoints/geo/livestock-naip-iv-inseminations.csv",
    table_id: "livestock.livestock_naip_iv",
    meta: {
      id: "livestock-naip-iv-inseminations",
      title: "NAIP IV: artificial inseminations done",
      description:
        "District total of artificial inseminations delivered under the National Artificial Insemination Programme IV. Source-of-truth grain per ADR-0043; the state-grain sibling is the SUM rollup auto-emitted in the same canonical adapter run.",
      entity_kind: "district",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "inseminations",
      short_unit: "AIs",
      icon: "activity",
      attribution_geography: "where_administered",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan NAIP IV endpoint snapshot 2026-05-25; FY 2024-25 only (CY 2024 deferred). 588 districts with non-zero counts.",
      notes:
        "NAIP IV is a SELECT-DISTRICT programme; 8 states/UTs report zero coverage upstream (Kerala, Punjab, Puducherry, Chandigarh, Delhi, Lakshadweep, A&N, D&NH+D&D). The choropleth is grey across those states because the programme is absent there, not because districts failed to report. Counts events, not animals.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/livestock_naip_iv_pregnancy_diagnoses",
    canonical_indicator_id: "livestock-naip-iv-pregnancy-diagnoses",
    csv_path: "data/datapoints/geo/livestock-naip-iv-pregnancy-diagnoses.csv",
    table_id: "livestock.livestock_naip_iv",
    meta: {
      id: "livestock-naip-iv-pregnancy-diagnoses",
      title: "NAIP IV: pregnancy diagnoses",
      description:
        "District total of pregnancy diagnoses performed on inseminated animals under the National Artificial Insemination Programme IV. Source-of-truth grain per ADR-0043; the state-grain sibling is the SUM rollup auto-emitted in the same canonical adapter run.",
      entity_kind: "district",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "diagnoses",
      short_unit: "PDs",
      icon: "activity",
      attribution_geography: "where_administered",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan NAIP IV endpoint snapshot 2026-05-25; FY 2024-25 only (CY 2024 deferred). 588 districts with non-zero counts.",
      notes:
        "NAIP IV is a SELECT-DISTRICT programme; 8 states/UTs report zero coverage upstream. The diagnosis-to-insemination ratio is usually ~10%; cross-district ratios reflect both biology and field-staff diligence. This is the source-of-truth grain.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/livestock_naip_iv_calves_born",
    canonical_indicator_id: "livestock-naip-iv-calves-born",
    csv_path: "data/datapoints/geo/livestock-naip-iv-calves-born.csv",
    table_id: "livestock.livestock_naip_iv",
    meta: {
      id: "livestock-naip-iv-calves-born",
      title: "NAIP IV: calves born",
      description:
        "District total of calves born from NAIP IV inseminations. Source-of-truth grain per ADR-0043; the state-grain sibling is the SUM rollup auto-emitted in the same canonical adapter run.",
      entity_kind: "district",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "calves",
      short_unit: "calves",
      icon: "users",
      attribution_geography: "where_administered",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan NAIP IV endpoint snapshot 2026-05-25; FY 2024-25 only (CY 2024 deferred). Sex axis (male/female) collapsed via SUM at Phase 2.C adapter time. 588 districts with non-zero counts.",
      notes:
        "NAIP IV is a SELECT-DISTRICT programme; 8 states/UTs report zero coverage upstream. Calf count reports both sexes; sex-disaggregated lift deferred. This is the source-of-truth grain.",
    },
  },
  {
    kind: "single",
    legacy_artifact_id: "agriculture/livestock_naip_iv_farmers_benefitted",
    canonical_indicator_id: "livestock-naip-iv-farmers-benefitted",
    csv_path: "data/datapoints/geo/livestock-naip-iv-farmers-benefitted.csv",
    table_id: "livestock.livestock_naip_iv",
    meta: {
      id: "livestock-naip-iv-farmers-benefitted",
      title: "NAIP IV: farmers benefitted",
      description:
        "District total of distinct farmers who availed at least one NAIP IV insemination service. Source-of-truth grain per ADR-0043; the state-grain sibling is the SUM rollup auto-emitted in the same canonical adapter run.",
      entity_kind: "district",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "farmers",
      short_unit: "farmers",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage:
        "NDLM Bharat Pashudhan NAIP IV endpoint snapshot 2026-05-25; FY 2024-25 only (CY 2024 deferred). 588 districts with non-zero counts.",
      notes:
        "NAIP IV is a SELECT-DISTRICT programme; 8 states/UTs report zero coverage upstream. Counts distinct farmers per district per FY. This is the source-of-truth grain.",
    },
  },

  // ---------------------------------------------------------------------------
  // W1 RBI State Finances cohort (2026-06-08, feat/w1-canonical-first-rbi-state-finances).
  //
  // Migrates 6 fiscal indicators from legacy datasets/indicators/in/fiscal/<id>.json
  // shards onto the canonical long-format CSV seam per plan-doc §10 W1 + §3.
  // Closes the 0/42 canonical-backed count to 6/42; unblocks the G5-PR-B
  // bulk rip once W1 + W2 + W3 cross the 22/42 threshold the G5 audit set.
  //
  // Substitution noted: `fiscal/net_transfers_from_centre` was REPLACED by
  // `fiscal/state_pension_expenditure_inr_crore` because the former's legacy
  // shard carries only 3 years (1 Accounts + 1 RE + 1 BE) and 1 Accounts
  // year x 31 entities is too thin for a citizen-grade time series.
  // `state_pension_expenditure_inr_crore` is RBI Handbook Table 171, 21 years
  // x 30 entities = 619 Accounts rows (longest series of any candidate).
  //
  // S09 (J&K state-era 2008-2019) and RE/BE projection rows are excluded
  // from the `outstanding-liabilities-pct-gsdp` CSV: silently merging the
  // pre-2019 state with the post-2019 UT would obscure the constitutional
  // reorganisation, and RE/BE rows are upstream projections not settled
  // Accounts. Documented as caveats on the descriptor.
  //
  // Time encoding: the canonical `time` column is the fiscal-year-start year
  // (integer) per datasets/data/_schema/columns.json. Legacy `"YYYY-04"`
  // (April-anchored = FY start) maps to integer `YYYY`. Legacy `"YYYY-03"`
  // (March-anchored = FY end) maps to integer `YYYY - 1`. The
  // `outstanding-liabilities-pct-gsdp` series uses the March-anchored form
  // and is rewound by one year; the other 5 are April-anchored and pass
  // through verbatim.

  {
    kind: "single",
    legacy_artifact_id: "fiscal/state_own_tax_revenue_inr_crore",
    canonical_indicator_id: "own-tax-revenue-inr-crore",
    csv_path: "data/datapoints/geo/own-tax-revenue-inr-crore.csv",
    table_id: "fiscal.state_finances",
    meta: {
      id: "own-tax-revenue-inr-crore",
      title: "Own tax revenue (state)",
      description:
        "Tax revenue raised by the State Government from sources within its constitutional jurisdiction (state GST share, state excise, stamp duties, motor vehicle tax, etc.). A direct measure of a state's revenue effort. Excludes the state's share of central taxes devolved by the Finance Commission.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "INR (crore)",
      short_unit: "INRcr",
      icon: "landmark",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "state",
      methodology_vintage:
        "Rajya Sabha Session 260 Unstarred Question 1323, answered 1 August 2023.",
      notes:
        "Read alongside `share-central-taxes-inr-crore` (central tax devolution) and `grants-in-aid-inr-crore` (centre-to-state grants) to see the full revenue picture. Raw INR-crore values are not directly comparable across states of very different size; per-capita and %-of-GSDP normalisations are the next-cut readings.",
    },
    caveats: [
      "Excludes the state's share of central taxes (Finance Commission devolution); add `central-tax-devolution-inr-crore` for total tax receipts.",
      "Raw INR-crore is not directly comparable across states of very different size. Karnataka at INR 1.3 lakh-crore and Sikkim at INR 1,000 crore reflect tax bases proportional to GSDP, not policy difference.",
      "Covers fiscal years 2016-17 to 2022-23 (the window the parliamentary question covered). Earlier and later years require separate sources (CAG, RBI State Finances).",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/state_share_central_taxes_inr_crore",
    canonical_indicator_id: "central-tax-devolution-inr-crore",
    csv_path: "data/datapoints/geo/central-tax-devolution-inr-crore.csv",
    table_id: "fiscal.state_finances",
    meta: {
      id: "central-tax-devolution-inr-crore",
      title: "Central tax devolution (state share)",
      description:
        "Amount transferred to each state as its share in central taxes under the Finance Commission's award formula. Income tax, CGST, and Union excise are divided among states using a weighted formula (population, income gap, area, demographic performance, forest cover, tax effort).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR (crore)",
      short_unit: "INRcr",
      icon: "landmark",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "centre",
      methodology_vintage:
        "Rajya Sabha Session 260 Unstarred Question 1323, answered 1 August 2023.",
      notes:
        "The formula is fixed for each Finance Commission cycle (5 years). Year-on-year changes within a cycle track central gross tax collections; cross-cycle jumps (14th FC -> 15th FC, FY 2020-21 onwards) reflect formula changes. Direction is `neutral`: a high devolution rewards lower per-capita income and weaker tax base; the citizen-readable measure of state fiscal effort is `own-tax-revenue-inr-crore`, not this column.",
    },
    caveats: [
      "Devolution depends on national tax buoyancy, not state effort. A poor year for central GST collections shrinks every state's share proportionally.",
      "15th Finance Commission (FY 2020-21 onwards) changed weights and introduced a separate 1% share for the J&K/Ladakh UTs that previously formed J&K state. Cross-cycle comparisons need a footnote.",
      "Covers fiscal years 2016-17 to 2022-23.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/state_revenue_expenditure_inr_crore",
    canonical_indicator_id: "revenue-expenditure-inr-crore",
    csv_path: "data/datapoints/geo/revenue-expenditure-inr-crore.csv",
    table_id: "fiscal.state_finances",
    meta: {
      id: "revenue-expenditure-inr-crore",
      title: "Revenue expenditure (state)",
      description:
        "Total revenue-account expenditure by the State Government in the fiscal year: salaries, pensions, interest payments, subsidies, grants to local bodies, and operating costs of departments. Excludes capital expenditure (assets, infrastructure) which appears in the capital account.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR (crore)",
      short_unit: "INRcr",
      icon: "landmark",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "state",
      methodology_vintage:
        "Rajya Sabha Session 260 Unstarred Question 1323, answered 1 August 2023.",
      notes:
        "Direction is `neutral`: spending more is not necessarily better (could be salary inflation) and spending less is not necessarily better (could be under-delivery on welfare). The honest reading is the composition (salary vs subsidy vs interest) and the revenue-deficit (revenue expenditure minus revenue receipts), both surfaced as separate indicators.",
    },
    caveats: [
      "Excludes capital expenditure (infrastructure, land, buildings). A state with a large capex push will look like it spends less per-capita on the revenue account.",
      "Interest payments and pensions are non-discretionary committed liabilities; the share of revenue expenditure that goes to these (vs developmental departments) is the citizen-meaningful split.",
      "Covers fiscal years 2016-17 to 2022-23.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/state_grants_in_aid_inr_crore",
    canonical_indicator_id: "grants-in-aid-inr-crore",
    csv_path: "data/datapoints/geo/grants-in-aid-inr-crore.csv",
    table_id: "fiscal.state_finances",
    meta: {
      id: "grants-in-aid-inr-crore",
      title: "Grants-in-aid from the Centre (state)",
      description:
        "Total grants received by each state from the Central Government in the fiscal year: Finance Commission grants (revenue-deficit, local bodies, post-devolution), centrally-sponsored scheme transfers (PMAY, MGNREGA, PMGSY, etc.), and special-purpose grants. Distinct from central tax devolution (the formula-based share of taxes); grants are conditional or scheme-tied.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR (crore)",
      short_unit: "INRcr",
      icon: "landmark",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "centre",
      methodology_vintage:
        "Rajya Sabha Session 260 Unstarred Question 1323, answered 1 August 2023.",
      notes:
        "Read alongside `central-tax-devolution-inr-crore` for the full picture of centre-to-state transfers. NEH (north-east + hill) special-category states draw a disproportionate share of grants; per-capita is the comparison frame.",
    },
    caveats: [
      "Tied to centrally-sponsored schemes (CSS) in most cases - the state cannot redirect the funds. A high grant figure can mean the state is implementing many CSS, not that it is fiscally healthy.",
      "Finance-Commission revenue-deficit grants taper across the FC cycle; expect step-downs at FC boundaries (FY 2015-16 / FY 2020-21).",
      "Covers fiscal years 2016-17 to 2022-23.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/outstanding_debt_pct_gsdp",
    canonical_indicator_id: "outstanding-liabilities-pct-gsdp",
    csv_path: "data/datapoints/geo/outstanding-liabilities-pct-gsdp.csv",
    table_id: "fiscal.state_finances",
    meta: {
      id: "outstanding-liabilities-pct-gsdp",
      title: "Outstanding liabilities (% of GSDP)",
      description:
        "Total outstanding state government debt as a share of Gross State Domestic Product, end-of-FY. Includes internal debt (market borrowings, NSSF, special securities), loans from the Centre, and provident-fund liabilities. The single most-watched indicator of state fiscal sustainability.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "%",
      short_unit: "%",
      icon: "trending-down",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "state",
      methodology_vintage:
        "RBI State Finances: A Study of Budgets, 2022-23 edition, Appendix Table 20 (Outstanding Liabilities of State Governments as Percentage of GSDP).",
      notes:
        "FRBM target: under 20% for the Centre, under 25% (most states) to 35% (special-category states) per state-FRBM acts. The 14th Finance Commission tightened the discipline; FY 2020-21 COVID stimulus expanded debt across the board with an explicit relaxation. NEH special-category states (Mizoram, Arunachal Pradesh, Manipur, Nagaland) routinely exceed 50% because GSDP base is small.",
    },
    caveats: [
      "Accounts-only canonical series. The legacy shard's 2024-25 RE (Revised Estimate) and 2025-26 BE (Budget Estimate) rows are EXCLUDED from this CSV because they are upstream projections, not settled. Add them back in a later release once Accounts land.",
      "J&K state-era values (2007-08 to 2018-19, ECI code S09) are EXCLUDED. The constitutional reorganisation in August 2019 split J&K into two UTs (J&K-UT and Ladakh); the canonical `jammu-and-kashmir` slug represents the post-2019 UT only. Silently merging the two would obscure the reorganisation.",
      "GSDP denominator is published with a 2-year lag (FY 2024-25 debt uses provisional FY 2022-23 GSDP); year-on-year movements can be denominator-driven, not numerator-driven.",
      "FRBM targets vary by state-tier; do not compare against a single threshold across NEH special-category and general-category states.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/state_pension_expenditure_inr_crore",
    canonical_indicator_id: "pension-expenditure-inr-crore",
    csv_path: "data/datapoints/geo/pension-expenditure-inr-crore.csv",
    table_id: "fiscal.state_finances",
    meta: {
      id: "pension-expenditure-inr-crore",
      title: "Pension expenditure (state revenue account)",
      description:
        "State government pension liabilities paid in the fiscal year: old-pension-scheme (OPS) payments to pre-2004 recruits, family pensions, and commuted-pension settlements. The single largest fixed liability for most states. Read alongside salary expenditure to see the committed-spending squeeze.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR (crore)",
      short_unit: "INRcr",
      icon: "landmark",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "state",
      methodology_vintage:
        "RBI Handbook of Statistics on Indian States, 2024-25 edition, Table 171 (State-wise Pension).",
      notes:
        "Pre-2004 recruits remain on OPS (defined-benefit, employer-funded); post-2004 NPS (defined-contribution) shifts the liability off the state budget but accrues a separate matching-contribution flow. Several states (Rajasthan, Chhattisgarh, Punjab, Himachal, Jharkhand) have legislated NPS-to-OPS reversal post-2022; the lagged actuarial impact will appear over the next two decades, not in this column today.",
    },
    caveats: [
      "OPS-to-NPS-to-OPS-reversal: the FY24 number does not yet show the actuarial liability the post-2022 reversal states have committed to. The fiscal squeeze will materialise over 2030-2050 as the post-2004 cohort retires.",
      "Includes commuted-pension settlements which are lumpy; a single-year spike often reflects a wave of retirements, not a permanent step-up.",
      "Does not include central employees stationed in the state (Railways, paramilitary, central PSUs); those liabilities sit on the Union account.",
      "Covers fiscal years 2004-05 to 2024-25.",
    ],
  },

  // ---------------------------------------------------------------------------
  // G5 bulk-rip cohort (2026-06-08, feat/g5-bulk-rip-25-indicators).
  //
  // Migrates the 25 remaining wired legacy JSON indicator shards under
  // datasets/indicators/in/{economy,environment,fiscal,demography,prices}/
  // onto the canonical long-format CSV seam per plan-doc §8 D1 + §10 W1-W3.
  // Closes the gap from 6/42 (post-W1) to 31/42 canonical-backed.
  //
  // Facet handling: option (b) per-facet CSVs for every facet-multiplexed
  // indicator (matches existing energy convention). Per-facet child CSVs at
  // data/datapoints/geo/<parent_id>-<facet_slug>.csv with the same 4-column
  // (entity_id, time, value, source_id) shape; facet labels project via the
  // facet-multiplexed UNION-ALL reader (indicator-from-canonical.ts).
  //
  // Multi-vintage collapse: legacy shards (NSDP, sectoral GVA, external
  // balance) carrying multiple base-year vintages collapsed to ONE row per
  // (entity, year, facet) preferring the latest available vintage. Per
  // Rosling-rule (CLAUDE.md anti-pattern #14): base-year rebases are
  // methodology breaks on the SAME id, not separate indicators.
  //
  // Time encoding: integer year (extract YYYY from any legacy time shape).
  // Fiscal-year YYYY-04 -> YYYY; March-anchored YYYY-03 -> YYYY-1;
  // calendar YYYY -> YYYY; snapshot YYYY-MM-DD -> YYYY.

  {
    kind: "single",
    legacy_artifact_id: "demography/state_population_lakhs",
    canonical_indicator_id: "state-population-lakhs",
    csv_path: "data/datapoints/geo/state-population-lakhs.csv",
    table_id: "demography.demography_canonical",
    meta: {
      id: "state-population-lakhs",
      title: "State population (lakhs)",
      description: "Total population of each state/UT (lakhs = 100,000). Census 2011 baseline projected forward by NITI ICED methodology; awaits Census 2027 re-base. Includes national-aggregate IN row.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "count",
      direction: "neutral",
      scale_hint: "linear",
      unit: "Lakhs",
      short_unit: "lakh",
      icon: "users",
      attribution_geography: "where_resident",
      comparability: "comparable_with_normalisation",
      implementing_authority: "joint",
      methodology_vintage: "Census 2011 + NITI ICED state-wise linear projection. Awaits Census 2027 re-base.",
      notes: "Per-capita denominators for most welfare indicators trace back to this projection. Population deltas at the bifurcation events (Telangana 2014, J&K UT split 2019) are reflected from the year of formation.",
    },
    caveats: [
      "Census 2011 baseline projected forward; values for 2020s subject to mid-decade re-base once Census 2027 lands.",
      "Includes the national-aggregate IN row alongside the 36 state/UT slugs.",
      "Bifurcation effects: Andhra Pradesh excludes Telangana from 2014-04; J&K excludes Ladakh from 2019-04.",
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "economy/gdp_inr_crore",
    canonical_parent_indicator_id: "gdp-inr-crore",
    table_id: "economy.economy_canonical",
    facet_axis_id: "price_basis",
    meta: {
      id: "gdp-inr-crore",
      title: "Gross Domestic Product (INR crore)",
      description: "India national GDP in INR crore. Facets: 'current' (nominal, contemporaneous prices) and 'constant' (real, base 2011-12). Use the constant series for growth analysis; current for nominal-share comparisons.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "trending-up",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "centre",
      methodology_vintage: "MoSPI National Accounts Statistics, base 2011-12 (constant series). NITI ICED Key Economic Indicators API snapshot 2024-25.",
      notes: "Constant-price series is the inflation-adjusted real measure; current-price is the nominal measure used for share-of-GDP ratios. Pre-2011-12 base-year rebases are absorbed by the publisher (CSO/MoSPI) into the constant 2011-12 series.",
    },
    caveats: [
      "Base year is 2011-12; an upstream re-base to 2017-18 was announced but not published. Cross-base comparisons require a back-cast splice (not done in this canonical series).",
      "State-level GDP (GSDP) is a separate canonical id (state_gdp_constant_2011_12_inr_lakh_crore -> state-gdp-constant-2011-12-inr-lakh-crore); this id is the national aggregate only.",
    ],
    facet_values: [
      {
        canonical_child_id: "gdp-inr-crore-current",
        legacy_facet_label: "current",
        csv_path: "data/datapoints/geo/gdp-inr-crore-current.csv",
      },
      {
        canonical_child_id: "gdp-inr-crore-constant",
        legacy_facet_label: "constant",
        csv_path: "data/datapoints/geo/gdp-inr-crore-constant.csv",
      },
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "economy/gva_by_industry_constant_inr_crore",
    canonical_parent_indicator_id: "gva-by-industry-constant-inr-crore",
    table_id: "economy.economy_canonical",
    facet_axis_id: "industry",
    meta: {
      id: "gva-by-industry-constant-inr-crore",
      title: "Gross Value Added by industry (constant prices, INR crore)",
      description: "India national GVA at constant 2011-12 prices, by industry of origin. 10 industry rollups: Agriculture/forestry/fishing, Construction, Electricity/gas/water utilities, Financial/real-estate/professional services, GVA at basic prices (total), Manufacturing, Mining and quarrying, NVA at basic prices, Public Administration/defence/other services, Trade/hotels/transport/communication.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "bar-chart-3",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "centre",
      methodology_vintage: "MoSPI National Accounts Statistics, base 2011-12. NITI ICED Key Economic Indicators API snapshot 2024-25.",
      notes: "Each industry's row is its standalone GVA contribution; the 'GVA at basic prices' facet is the all-industry total and the 'NVA at basic prices' facet is GVA minus consumption of fixed capital. Sum of leaf industries equals total GVA modulo statistical discrepancy.",
    },
    caveats: [
      "Industry classification is the NIC-2008-based 10-section rollup; finer sub-section detail requires the underlying CSO release.",
      "Constant prices are referenced to 2011-12; nominal current-prices series is a separate indicator (not yet migrated).",
    ],
    facet_values: [
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-agriculture-forestry-and-fishing",
        legacy_facet_label: "Agriculture, forestry and fishing",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-agriculture-forestry-and-fishing.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-construction",
        legacy_facet_label: "Construction",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-construction.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-electricity-gas-water-supply-and-other-utility-services",
        legacy_facet_label: "Electricity, gas, water supply and other utility services",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-electricity-gas-water-supply-and-other-utility-services.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-financial-real-estate-and-professional-services",
        legacy_facet_label: "Financial, real estate and professional services",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-financial-real-estate-and-professional-services.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-gva-at-basic-prices",
        legacy_facet_label: "GVA at basic prices",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-gva-at-basic-prices.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-manufacturing",
        legacy_facet_label: "Manufacturing",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-manufacturing.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-mining-and-quarrying",
        legacy_facet_label: "Mining and quarrying",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-mining-and-quarrying.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-nva-at-basic-prices",
        legacy_facet_label: "NVA at basic prices",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-nva-at-basic-prices.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-public-administration-defence-and-other-services",
        legacy_facet_label: "Public Administration, defence and other services",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-public-administration-defence-and-other-services.csv",
      },
      {
        canonical_child_id: "gva-by-industry-constant-inr-crore-trade-hotels-transport-communication-and-broadcasting-services",
        legacy_facet_label: "Trade, hotels, transport, communication and Broadcasting services",
        csv_path: "data/datapoints/geo/gva-by-industry-constant-inr-crore-trade-hotels-transport-communication-and-broadcasting-services.csv",
      },
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "economy/iip_index",
    canonical_parent_indicator_id: "iip-index",
    table_id: "economy.economy_canonical",
    facet_axis_id: "use_based_or_sectoral",
    meta: {
      id: "iip-index",
      title: "Index of Industrial Production (2011-12=100)",
      description: "India national IIP by use-based + sectoral classification. 10 facets: Capital goods, Consumer durables, Consumer non-durables, Electricity, General (all-IIP), Infrastructure/construction goods, Intermediate goods, Manufacturing, Mining & Quarrying, Primary goods.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "index",
      direction: "neutral",
      scale_hint: "linear",
      unit: "index (2011-12=100)",
      short_unit: "idx",
      icon: "activity",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "centre",
      methodology_vintage: "Central Statistics Office (MoSPI) IIP release, base 2011-12. NITI ICED Key Economic Indicators API snapshot 2024-25.",
      notes: "The 'General' facet is the headline all-IIP index. Use-based facets (Primary/Capital/Intermediate/Infrastructure-construction/Consumer-durables/Consumer-non-durables) decompose by stage of production; sectoral facets (Mining-Quarrying/Manufacturing/Electricity) decompose by ISIC sector.",
    },
    caveats: [
      "Base year is 2011-12; an upstream rebase to 2017-18 was announced by MoSPI but the rebased series is not yet on the canonical path.",
      "Annual numbers shown here are fiscal-year averages of the monthly IIP release.",
    ],
    facet_values: [
      {
        canonical_child_id: "iip-index-capital-goods",
        legacy_facet_label: "Capital goods",
        csv_path: "data/datapoints/geo/iip-index-capital-goods.csv",
      },
      {
        canonical_child_id: "iip-index-consumer-durables",
        legacy_facet_label: "Consumer durables",
        csv_path: "data/datapoints/geo/iip-index-consumer-durables.csv",
      },
      {
        canonical_child_id: "iip-index-consumer-non-durables",
        legacy_facet_label: "Consumer non-durables",
        csv_path: "data/datapoints/geo/iip-index-consumer-non-durables.csv",
      },
      {
        canonical_child_id: "iip-index-electricity",
        legacy_facet_label: "Electricity",
        csv_path: "data/datapoints/geo/iip-index-electricity.csv",
      },
      {
        canonical_child_id: "iip-index-general",
        legacy_facet_label: "General",
        csv_path: "data/datapoints/geo/iip-index-general.csv",
      },
      {
        canonical_child_id: "iip-index-infrastructure-construction-goods",
        legacy_facet_label: "Infrastructure/ construction goods",
        csv_path: "data/datapoints/geo/iip-index-infrastructure-construction-goods.csv",
      },
      {
        canonical_child_id: "iip-index-intermediate-goods",
        legacy_facet_label: "Intermediate goods",
        csv_path: "data/datapoints/geo/iip-index-intermediate-goods.csv",
      },
      {
        canonical_child_id: "iip-index-manufacturing",
        legacy_facet_label: "Manufacturing",
        csv_path: "data/datapoints/geo/iip-index-manufacturing.csv",
      },
      {
        canonical_child_id: "iip-index-mining-quarrying",
        legacy_facet_label: "Mining & Quarrying",
        csv_path: "data/datapoints/geo/iip-index-mining-quarrying.csv",
      },
      {
        canonical_child_id: "iip-index-primary-goods",
        legacy_facet_label: "Primary goods",
        csv_path: "data/datapoints/geo/iip-index-primary-goods.csv",
      },
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "economy/india_external_balance_inr_crore",
    canonical_parent_indicator_id: "india-external-balance-inr-crore",
    table_id: "economy.economy_canonical",
    facet_axis_id: "balance_component",
    meta: {
      id: "india-external-balance-inr-crore",
      title: "India external balance components (INR crore)",
      description: "India Balance-of-Payments components in INR crore. 6 facets: Trade Balance, Invisibles (Net), Current Account Balance, Total Foreign Investment, Loans (Net), Overall Balance.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "line-chart",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "centre",
      methodology_vintage: "Reserve Bank of India BoP release. NITI ICED Key Economic Indicators API snapshot 2024-25.",
      notes: "Current Account Balance = Trade Balance + Invisibles (Net). Capital Account = Total Foreign Investment + Loans (Net) + others. Overall Balance reflects reserve-asset movements.",
    },
    caveats: [
      "Composite of multi-publisher data (RBI BoP + MoCI trade releases) compiled by NITI ICED; check the RBI BoP release directly for the most up-to-date current-account numbers.",
      "Some rows carry a 'vintage' qualifier in the legacy shard (e.g. provisional vs revised); canonical CSV emits the latest available value per (entity, year) tuple.",
    ],
    facet_values: [
      {
        canonical_child_id: "india-external-balance-inr-crore-current-account-balance",
        legacy_facet_label: "Current Account Balance",
        csv_path: "data/datapoints/geo/india-external-balance-inr-crore-current-account-balance.csv",
      },
      {
        canonical_child_id: "india-external-balance-inr-crore-invisibles-net",
        legacy_facet_label: "Invisibles (Net)",
        csv_path: "data/datapoints/geo/india-external-balance-inr-crore-invisibles-net.csv",
      },
      {
        canonical_child_id: "india-external-balance-inr-crore-loans-net",
        legacy_facet_label: "Loans (Net)",
        csv_path: "data/datapoints/geo/india-external-balance-inr-crore-loans-net.csv",
      },
      {
        canonical_child_id: "india-external-balance-inr-crore-overall-balance",
        legacy_facet_label: "Overall Balance",
        csv_path: "data/datapoints/geo/india-external-balance-inr-crore-overall-balance.csv",
      },
      {
        canonical_child_id: "india-external-balance-inr-crore-total-foreign-investment",
        legacy_facet_label: "Total Foreign Investment",
        csv_path: "data/datapoints/geo/india-external-balance-inr-crore-total-foreign-investment.csv",
      },
      {
        canonical_child_id: "india-external-balance-inr-crore-trade-balance",
        legacy_facet_label: "Trade Balance",
        csv_path: "data/datapoints/geo/india-external-balance-inr-crore-trade-balance.csv",
      },
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "economy/nsdp_inr_crore",
    canonical_parent_indicator_id: "nsdp-inr-crore",
    table_id: "economy.economy_canonical",
    facet_axis_id: "price_basis",
    meta: {
      id: "nsdp-inr-crore",
      title: "Net State Domestic Product (INR crore)",
      description: "Per-state NSDP in INR crore. 2 facets: 'current' (nominal prices) and 'constant' (real prices, latest available base year). Multiple base-year vintages (1993-94 / 1999-2000 / 2004-05 / 2011-12) collapsed into ONE series per (entity, year, facet) by preferring the latest vintage.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "trending-up",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "joint",
      methodology_vintage: "RBI Handbook of Statistics on Indian Economy 2024-25, Tables 5 (current) + 6 (constant). Multi-vintage base-year rebases: 1993-94 (pre-2003), 1999-2000 (2003-2010), 2004-05 (2010-2015), 2011-12 (2015-).",
      notes: "Per Rosling-rule (CLAUDE.md anti-pattern #14): base-year rebases are methodology breaks on the SAME id, not new ids. Constant-price series stitches across rebase boundaries; consult original RBI publication for cross-base back-cast methodology.",
    },
    caveats: [
      "Multi-vintage data: 4 base years (1993-94 / 1999-2000 / 2004-05 / 2011-12). Canonical CSV keeps the latest available vintage per (entity, year, facet); other vintages discarded.",
      "Raw INR-crore is not comparable across states of very different size; per-capita NSDP (per-capita-nsdp-current-inr / per-capita-nsdp-constant-inr) is the cross-state-comparable framing.",
    ],
    facet_values: [
      {
        canonical_child_id: "nsdp-inr-crore-current",
        legacy_facet_label: "current",
        csv_path: "data/datapoints/geo/nsdp-inr-crore-current.csv",
      },
      {
        canonical_child_id: "nsdp-inr-crore-constant",
        legacy_facet_label: "constant",
        csv_path: "data/datapoints/geo/nsdp-inr-crore-constant.csv",
      },
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "economy/per_capita_nsdp_constant_inr",
    canonical_indicator_id: "per-capita-nsdp-constant-inr",
    csv_path: "data/datapoints/geo/per-capita-nsdp-constant-inr.csv",
    table_id: "economy.economy_canonical",
    // G29 PILOT (2026-06-09): first descriptor to flip from the
    // legacy 923-LOC maplibre wrapper `<IndicatorChoropleth>` to the
    // d3-geo SVG F2b.3 `<GeoChoropleth>` primitive. Pilot scope per
    // parent plan section 14.5 / 15 / 16 + the per-indicator
    // allowlist seam doctrine; reversible by removing this field.
    // Subsequent indicators get their own PRs.
    renderer_override: "geo-choropleth-f2b",
    meta: {
      id: "per-capita-nsdp-constant-inr",
      title: "Per-capita NSDP (constant prices, INR)",
      description: "Per-capita Net State Domestic Product at constant prices, INR. Includes national-aggregate IN row. Multiple base-year vintages absorbed via latest-vintage rule (see methodology).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "INR",
      short_unit: "INR",
      icon: "user-check",
      attribution_geography: "where_resident",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage: "RBI Handbook of Statistics on Indian Economy 2024-25, Table 10 (Per Capita Net State Domestic Product - State-wise, At Constant Prices).",
      notes: "Cross-state-comparable real-income measure. Direction: higher is better (more output per resident). Multi-vintage base-year rebases stitched (latest-vintage wins per row).",
    },
    caveats: [
      "Per Rosling-rule: base-year rebases are methodology breaks on SAME id; not separate indicators. Pre-2011-12 vintages exist for legacy series.",
      "Population denominator is Census 2011 + projection; will be re-based once Census 2027 is published.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "economy/per_capita_nsdp_current_inr",
    canonical_indicator_id: "per-capita-nsdp-current-inr",
    csv_path: "data/datapoints/geo/per-capita-nsdp-current-inr.csv",
    table_id: "economy.economy_canonical",
    meta: {
      id: "per-capita-nsdp-current-inr",
      title: "Per-capita NSDP (current prices, INR)",
      description: "Per-capita Net State Domestic Product at current (nominal) prices, INR. Includes national-aggregate IN row. Multiple base-year vintages absorbed via latest-vintage rule.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "INR",
      short_unit: "INR",
      icon: "user-check",
      attribution_geography: "where_resident",
      comparability: "comparable_with_normalisation",
      implementing_authority: "joint",
      methodology_vintage: "RBI Handbook of Statistics on Indian Economy 2024-25, Table 9 (Per Capita Net State Domestic Product - State-wise, At Current Prices).",
      notes: "Nominal-rupee per-capita output measure. For real-income comparisons across years, use per-capita-nsdp-constant-inr instead. Population denominator is Census 2011 + projection.",
    },
    caveats: [
      "Current-price means inflation NOT removed; values rise with both growth and inflation. Cross-year comparisons should use the constant-price sibling indicator.",
      "Multi-vintage base-year rebases stitched (latest-vintage wins per row).",
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "economy/sectoral_gva_inr_crore",
    canonical_parent_indicator_id: "sectoral-gva-inr-crore",
    table_id: "economy.economy_canonical",
    facet_axis_id: "price_basis",
    meta: {
      id: "sectoral-gva-inr-crore",
      title: "Sectoral GVA (state, INR crore)",
      description: "Gross Value Added by state, faceted by price basis (current + constant). 2 facets: 'current' (nominal prices), 'constant' (real prices, base 2011-12). Includes national-aggregate IN row.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "bar-chart-3",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "joint",
      methodology_vintage: "MoSPI National Accounts Statistics, base 2011-12 (constant). NITI ICED State-wise Deep Dive API snapshot 2024-25.",
      notes: "Raw INR-crore not cross-state-comparable; per-capita normalisations are sibling indicators. Constant-price series at base 2011-12.",
    },
    caveats: [
      "Aggregated all-sector GVA at state grain; sector-level decomposition (agriculture/industry/services) lives in the legacy GVA-by-industry shard (currently national-grain only).",
      "Base year is 2011-12.",
    ],
    facet_values: [
      {
        canonical_child_id: "sectoral-gva-inr-crore-current",
        legacy_facet_label: "current",
        csv_path: "data/datapoints/geo/sectoral-gva-inr-crore-current.csv",
      },
      {
        canonical_child_id: "sectoral-gva-inr-crore-constant",
        legacy_facet_label: "constant",
        csv_path: "data/datapoints/geo/sectoral-gva-inr-crore-constant.csv",
      },
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "economy/state_gdp_constant_2011_12_inr_lakh_crore",
    canonical_indicator_id: "state-gdp-constant-2011-12-inr-lakh-crore",
    csv_path: "data/datapoints/geo/state-gdp-constant-2011-12-inr-lakh-crore.csv",
    table_id: "economy.economy_canonical",
    meta: {
      id: "state-gdp-constant-2011-12-inr-lakh-crore",
      title: "State GDP at constant 2011-12 prices (INR lakh crore)",
      description: "Gross State Domestic Product at constant 2011-12 prices, INR lakh crore (1 lakh crore = 1 trillion = 10^12). Includes national-aggregate IN row.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "INR (lakh crore)",
      short_unit: "INRlc",
      icon: "trending-up",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "joint",
      methodology_vintage: "MoSPI National Accounts Statistics, base 2011-12. NITI ICED State-wise Deep Dive API snapshot 2024-25.",
      notes: "Real GDP measure (inflation removed); use this for growth-rate analysis. Cross-state comparison without per-capita normalisation conflates growth with population size.",
    },
    caveats: [
      "Base year is 2011-12; an upstream rebase to 2017-18 was announced but not published.",
      "Raw lakh-crore values not directly cross-state comparable; per-capita GSDP would be the framed measure (not yet a canonical indicator).",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "economy/state_per_capita_consumption_inr",
    canonical_indicator_id: "per-capita-consumption-inr",
    csv_path: "data/datapoints/geo/per-capita-consumption-inr.csv",
    table_id: "economy.economy_canonical",
    meta: {
      id: "per-capita-consumption-inr",
      title: "State per-capita private consumption (INR per person per year)",
      description: "Per-capita Private Final Consumption Expenditure (PFCE) at state level, INR per person per year. National-aggregate IN row included. Welfare proxy that does not require an NSS round.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "INR",
      short_unit: "INR",
      icon: "shopping-bag",
      attribution_geography: "where_resident",
      comparability: "comparable_across_states",
      implementing_authority: "joint",
      methodology_vintage: "MoSPI National Accounts PFCE (CSO modelled to state level). NITI ICED Key Economic Indicators API snapshot 2024-25.",
      notes: "National-Accounts PFCE per capita is CSO-modelled from national totals down to state level. Different from (typically higher than) NSS Household Consumption Expenditure surveys; both are valid for different questions.",
    },
    caveats: [
      "Andhra Pradesh pre-2014 includes Telangana; J&K pre-2019 includes Ladakh.",
      "Modelled from national PFCE by CSO; not a direct state-level survey measurement.",
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "environment/india_ghg_emissions_by_subsector_ggco2e",
    canonical_parent_indicator_id: "india-ghg-emissions-ggco2e-by-subsector",
    table_id: "environment.environment_canonical",
    facet_axis_id: "subsector",
    meta: {
      id: "india-ghg-emissions-ggco2e-by-subsector",
      title: "India GHG emissions by sub-sector (Gg CO2e)",
      description: "India national GHG emissions in Gg CO2e (1 Gg = 1 kt = 1000 tonnes). 26 facets representing IPCC sector + sub-sector hierarchy: 5 Agriculture sub-sectors, 5 Energy sub-sectors, 5 IPPU sub-sectors, 6 LULUCF sub-sectors, 5 Waste sub-sectors.",
      entity_kind: "country",
      time_grain: "year",
      value_kind: "raw",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "Gg CO2e",
      short_unit: "Gg",
      icon: "cloud",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "centre",
      methodology_vintage: "BUR4 (Fourth Biennial Update Report to UNFCCC, 2024). NITI ICED Climate-Environment GHG Emissions API snapshot 2024-25.",
      notes: "Hierarchical facet labels use '|' separator (e.g. 'Agriculture|Enteric Fermentation'). LULUCF sector can have NEGATIVE values (carbon sequestration). Sum across sub-sectors within a sector equals the parent sector total in india-ghg-emissions-ggco2e-by-sector.",
    },
    caveats: [
      "BUR4 covers years 2016-2020 in the published submission; later years require BUR5 (not yet submitted). Multi-year facet coverage varies.",
      "LULUCF sub-sectors include carbon-sink rows that can be negative; aggregation must respect signs.",
      "Sub-sector aggregation to sector-level should match india-ghg-emissions-ggco2e-by-sector but unit there is MtCO2e (1 Mt = 1000 Gg).",
    ],
    facet_values: [
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-agriculture-agricultural-soils",
        legacy_facet_label: "Agriculture|Agricultural soils",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-agriculture-agricultural-soils.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-agriculture-enteric-fermentation",
        legacy_facet_label: "Agriculture|Enteric Fermentation",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-agriculture-enteric-fermentation.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-agriculture-field-burning-of-agricultural-residues",
        legacy_facet_label: "Agriculture|Field Burning of Agricultural Residues",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-agriculture-field-burning-of-agricultural-residues.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-agriculture-manure-management",
        legacy_facet_label: "Agriculture|Manure Management",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-agriculture-manure-management.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-agriculture-rice-cultivation",
        legacy_facet_label: "Agriculture|Rice Cultivation",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-agriculture-rice-cultivation.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-energy-energy-industries",
        legacy_facet_label: "Energy|Energy Industries",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-energy-energy-industries.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-energy-fugitive-emissions",
        legacy_facet_label: "Energy|Fugitive emissions",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-energy-fugitive-emissions.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-energy-manufacturing-industries-and-construction",
        legacy_facet_label: "Energy|Manufacturing Industries and Construction",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-energy-manufacturing-industries-and-construction.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-energy-other-sectors",
        legacy_facet_label: "Energy|Other Sectors",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-energy-other-sectors.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-energy-transport",
        legacy_facet_label: "Energy|Transport",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-energy-transport.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-chemicals",
        legacy_facet_label: "Industrial processes and product use|Chemicals",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-chemicals.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-metal-production",
        legacy_facet_label: "Industrial processes and product use|Metal production",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-metal-production.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-minerals",
        legacy_facet_label: "Industrial processes and product use|Minerals",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-minerals.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-other",
        legacy_facet_label: "Industrial processes and product use|Other",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-other.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-production-of-halocarbons-and-sulphur-hexafluoride",
        legacy_facet_label: "Industrial processes and product use|Production of halocarbons and sulphur hexafluoride",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-industrial-processes-and-product-use-production-of-halocarbons-and-sulphur-hexafluoride.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-cropland",
        legacy_facet_label: "Land use, Land-use change and Forestry|Cropland",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-cropland.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-forest-land",
        legacy_facet_label: "Land use, Land-use change and Forestry|Forest land",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-forest-land.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-fuelwood-use",
        legacy_facet_label: "Land use, Land-use change and Forestry|Fuelwood use",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-fuelwood-use.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-grassland",
        legacy_facet_label: "Land use, Land-use change and Forestry|Grassland",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-grassland.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-harvested-wood-products",
        legacy_facet_label: "Land use, Land-use change and Forestry|Harvested Wood Products",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-harvested-wood-products.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-settlement",
        legacy_facet_label: "Land use, Land-use change and Forestry|Settlement",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-settlement.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-waste-biological-treatment-of-solid-waste",
        legacy_facet_label: "Waste|Biological Treatment of Solid Waste",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-waste-biological-treatment-of-solid-waste.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-waste-human-sewage",
        legacy_facet_label: "Waste|Human Sewage",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-waste-human-sewage.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-waste-incineration-and-open-burning-of-waste",
        legacy_facet_label: "Waste|Incineration and Open Burning of Waste",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-waste-incineration-and-open-burning-of-waste.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-waste-municipal-solid-waste-disposal",
        legacy_facet_label: "Waste|Municipal Solid Waste Disposal",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-waste-municipal-solid-waste-disposal.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-ggco2e-by-subsector-waste-waste-water-handling",
        legacy_facet_label: "Waste|Waste-water handling",
        csv_path: "data/datapoints/geo/india-ghg-emissions-ggco2e-by-subsector-waste-waste-water-handling.csv",
      },
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "environment/india_ghg_emissions_mtco2e_by_sector",
    canonical_parent_indicator_id: "india-ghg-emissions-mtco2e-by-sector",
    table_id: "environment.environment_canonical",
    facet_axis_id: "sector",
    meta: {
      id: "india-ghg-emissions-mtco2e-by-sector",
      title: "India GHG emissions by sector (Mt CO2e)",
      description: "India national GHG emissions in MtCO2e (1 Mt = 1,000,000 tonnes). 4 facets: Energy Sector, Industrial processes and product use, Agriculture, Waste. (LULUCF carbon-sink is a separate balance, not in this sector total.)",
      entity_kind: "country",
      time_grain: "year",
      value_kind: "raw",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "Mt CO2e",
      short_unit: "Mt",
      icon: "cloud",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "centre",
      methodology_vintage: "BUR4 (Fourth Biennial Update Report to UNFCCC, 2024). NITI ICED Climate-Environment GHG Emissions API snapshot 2024-25.",
      notes: "Sector-level rollup of the sub-sector breakdown in india-ghg-emissions-ggco2e-by-subsector (note: different unit Mt vs Gg, factor of 1000). Energy is the dominant sector (~70% of India's gross emissions).",
    },
    caveats: [
      "BUR4 published submission; multi-year aggregation reported separately by sector (Energy/IPPU/Agriculture/Waste). LULUCF is a separate balance excluded from sector totals.",
      "Unit is MtCO2e (megatonnes) - the sub-sector sibling uses GgCO2e (gigagrams = kilotonnes); 1 Mt = 1000 Gg.",
    ],
    facet_values: [
      {
        canonical_child_id: "india-ghg-emissions-mtco2e-by-sector-agriculture",
        legacy_facet_label: "Agriculture",
        csv_path: "data/datapoints/geo/india-ghg-emissions-mtco2e-by-sector-agriculture.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-mtco2e-by-sector-energy-sector",
        legacy_facet_label: "Energy Sector",
        csv_path: "data/datapoints/geo/india-ghg-emissions-mtco2e-by-sector-energy-sector.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-mtco2e-by-sector-industrial-processes-and-product-use",
        legacy_facet_label: "Industrial processes and product use",
        csv_path: "data/datapoints/geo/india-ghg-emissions-mtco2e-by-sector-industrial-processes-and-product-use.csv",
      },
      {
        canonical_child_id: "india-ghg-emissions-mtco2e-by-sector-waste",
        legacy_facet_label: "Waste",
        csv_path: "data/datapoints/geo/india-ghg-emissions-mtco2e-by-sector-waste.csv",
      },
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "environment/state_no2_annual_mean_ug_m3",
    canonical_indicator_id: "no2-annual-mean-ug-m3",
    csv_path: "data/datapoints/geo/no2-annual-mean-ug-m3.csv",
    table_id: "environment.environment_canonical",
    meta: {
      id: "no2-annual-mean-ug-m3",
      title: "State annual mean NO2 (ug/m3)",
      description: "State-wise annual mean concentration of Nitrogen Dioxide (NO2), micrograms per cubic metre. Compiled from CPCB National Air Quality Monitoring Programme via NITI ICED AQI Map Markers API.",
      entity_kind: "state",
      time_grain: "year",
      value_kind: "rate",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "ug/m3",
      short_unit: "ug/m3",
      icon: "wind",
      attribution_geography: "where_measured",
      comparability: "directional_only",
      implementing_authority: "joint",
      methodology_vintage: "Central Pollution Control Board (CPCB) National Air Quality Monitoring Programme. NITI ICED AQI Map Markers snapshot 2024-25. WHO 2021 air quality guideline: annual mean NO2 <= 10 ug/m3.",
      notes: "State-mean aggregation across CPCB monitoring stations; monitoring-station coverage skews to urban/industrial areas (rural-mean would be lower). WHO 2021 guideline annual NO2 = 10 ug/m3; most Indian state-means exceed this.",
    },
    caveats: [
      "State-mean aggregation across CPCB monitoring stations; skewed to urban areas where stations are concentrated. Rural-only means would be substantially lower.",
      "Station counts vary year-over-year as new stations are commissioned; multi-year trends partially reflect monitoring-network expansion rather than air-quality change.",
      "Comparability marked directional-only because station-count and method changes confound cross-state and cross-year comparisons.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "environment/state_pm10_annual_mean_ug_m3",
    canonical_indicator_id: "pm10-annual-mean-ug-m3",
    csv_path: "data/datapoints/geo/pm10-annual-mean-ug-m3.csv",
    table_id: "environment.environment_canonical",
    meta: {
      id: "pm10-annual-mean-ug-m3",
      title: "State annual mean PM10 (ug/m3)",
      description: "State-wise annual mean concentration of Particulate Matter <= 10 micrometres (PM10), micrograms per cubic metre. Compiled from CPCB National Air Quality Monitoring Programme via NITI ICED AQI Map Markers API.",
      entity_kind: "state",
      time_grain: "year",
      value_kind: "rate",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "ug/m3",
      short_unit: "ug/m3",
      icon: "wind",
      attribution_geography: "where_measured",
      comparability: "directional_only",
      implementing_authority: "joint",
      methodology_vintage: "Central Pollution Control Board (CPCB) National Air Quality Monitoring Programme. NITI ICED AQI Map Markers snapshot 2024-25. India NAAQS: annual mean PM10 <= 60 ug/m3; WHO 2021: <= 15 ug/m3.",
      notes: "PM10 includes coarser particles than PM2.5 (e.g. wind-blown dust). India National Ambient Air Quality Standard (NAAQS) annual mean = 60 ug/m3; WHO 2021 guideline = 15 ug/m3 (much stricter). Most state-means exceed both.",
    },
    caveats: [
      "Station-mean aggregation; skewed to urban areas. Station counts vary year-over-year.",
      "PM10 includes PM2.5 + coarse particulates; PM2.5 sibling indicator captures the finer-particulate sub-fraction.",
      "Comparability marked directional-only due to station-count + method changes.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "environment/state_pm25_annual_mean_ug_m3",
    canonical_indicator_id: "pm25-annual-mean-ug-m3",
    csv_path: "data/datapoints/geo/pm25-annual-mean-ug-m3.csv",
    table_id: "environment.environment_canonical",
    meta: {
      id: "pm25-annual-mean-ug-m3",
      title: "State annual mean PM2.5 (ug/m3)",
      description: "State-wise annual mean concentration of fine Particulate Matter <= 2.5 micrometres (PM2.5), micrograms per cubic metre. The most-watched air-pollution metric for health impact. Compiled from CPCB monitoring via NITI ICED AQI Map Markers API.",
      entity_kind: "state",
      time_grain: "year",
      value_kind: "rate",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "ug/m3",
      short_unit: "ug/m3",
      icon: "wind",
      attribution_geography: "where_measured",
      comparability: "directional_only",
      implementing_authority: "joint",
      methodology_vintage: "Central Pollution Control Board (CPCB) National Air Quality Monitoring Programme. NITI ICED AQI Map Markers snapshot 2024-25. India NAAQS: annual mean PM2.5 <= 40 ug/m3; WHO 2021: <= 5 ug/m3.",
      notes: "PM2.5 penetrates deep into lungs; primary driver of respiratory / cardiovascular health impact from air pollution. India NAAQS = 40 ug/m3; WHO 2021 guideline = 5 ug/m3 (most strict WHO update). Almost all Indian states exceed both.",
    },
    caveats: [
      "Station-mean aggregation; PM2.5 monitoring network is sparser than PM10. Network coverage expanding year-over-year.",
      "Annual mean masks seasonal Delhi-NCR / IGP winter spikes (November-February >300 ug/m3) and post-Diwali peaks.",
      "Comparability marked directional-only due to station-count + method changes.",
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "environment/state_power_sector_co2_emissions_mtco2",
    canonical_parent_indicator_id: "state-power-sector-co2-emissions-mtco2",
    table_id: "environment.environment_canonical",
    facet_axis_id: "fuel_type",
    meta: {
      id: "state-power-sector-co2-emissions-mtco2",
      title: "State power-sector CO2 emissions by fuel (Mt CO2)",
      description: "State-wise CO2 emissions from electricity generation, in MtCO2. 2 facets: 'coal' and 'oil-gas'. Hydro / nuclear / renewable assumed zero direct-CO2 (life-cycle emissions excluded).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "raw",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "Mt CO2",
      short_unit: "Mt",
      icon: "factory",
      attribution_geography: "where_administered",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "joint",
      methodology_vintage: "Central Electricity Authority (CEA) plant-level emission factors aggregated by state. NITI ICED CO Emission Metatable API snapshot 2024-25.",
      notes: "Only direct combustion CO2 from coal + oil/gas plants; hydro / nuclear / renewable count as zero (life-cycle emissions excluded). Coal-dominant states (Chhattisgarh, Jharkhand, Odisha, MP) show much larger values.",
    },
    caveats: [
      "Excludes life-cycle emissions from hydro/nuclear/renewable; head-line zero for those fuels reflects direct combustion only.",
      "Per-MWh emission factor varies by plant vintage + efficiency; state averages mask plant-level heterogeneity.",
    ],
    facet_values: [
      {
        canonical_child_id: "state-power-sector-co2-emissions-mtco2-coal",
        legacy_facet_label: "coal",
        csv_path: "data/datapoints/geo/state-power-sector-co2-emissions-mtco2-coal.csv",
      },
      {
        canonical_child_id: "state-power-sector-co2-emissions-mtco2-oil-gas",
        legacy_facet_label: "oil-gas",
        csv_path: "data/datapoints/geo/state-power-sector-co2-emissions-mtco2-oil-gas.csv",
      },
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "environment/state_so2_annual_mean_ug_m3",
    canonical_indicator_id: "so2-annual-mean-ug-m3",
    csv_path: "data/datapoints/geo/so2-annual-mean-ug-m3.csv",
    table_id: "environment.environment_canonical",
    meta: {
      id: "so2-annual-mean-ug-m3",
      title: "State annual mean SO2 (ug/m3)",
      description: "State-wise annual mean concentration of Sulphur Dioxide (SO2), micrograms per cubic metre. Compiled from CPCB monitoring via NITI ICED AQI Map Markers API.",
      entity_kind: "state",
      time_grain: "year",
      value_kind: "rate",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "ug/m3",
      short_unit: "ug/m3",
      icon: "wind",
      attribution_geography: "where_measured",
      comparability: "directional_only",
      implementing_authority: "joint",
      methodology_vintage: "Central Pollution Control Board (CPCB) National Air Quality Monitoring Programme. NITI ICED AQI Map Markers snapshot 2024-25. India NAAQS: annual mean SO2 <= 50 ug/m3; WHO 2021: <= 40 ug/m3 (24-hr).",
      notes: "SO2 primarily from coal-fired power + diesel + smelters. India NAAQS = 50 ug/m3 annual; most state-means well within limit. SO2 FGD scrubber-mandates (CPCB 2015 notification) drive observed declines.",
    },
    caveats: [
      "Station-mean aggregation; skewed to urban + industrial monitoring sites.",
      "FGD compliance (state-thermal-fgd-installed-share-pct sibling indicator) is the policy-relevant proxy for future SO2 trends.",
      "Comparability marked directional-only due to station-count + method changes.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "environment/state_thermal_fgd_installed_share_pct",
    canonical_indicator_id: "thermal-fgd-installed-share-pct",
    csv_path: "data/datapoints/geo/thermal-fgd-installed-share-pct.csv",
    table_id: "environment.environment_canonical",
    meta: {
      id: "thermal-fgd-installed-share-pct",
      title: "State thermal FGD installed share (%)",
      description: "Share of state's coal-fired thermal capacity with installed Flue-Gas Desulphurisation (FGD), percent. Compliance metric for CPCB 7-December-2015 SO2 emission norms. Single snapshot (2026 reading).",
      entity_kind: "state",
      time_grain: "year",
      value_kind: "share",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "%",
      short_unit: "%",
      icon: "filter",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "joint",
      methodology_vintage: "MoEFCC Notification 7-December-2015 (Environment Protection Act SO2 norms for thermal plants). CPCB plant-level compliance tracking. NITI ICED FGD API snapshot 2026-05.",
      notes: "FGD scrubbers remove SO2 from flue-gas before chimney release. The 2015 notification mandated FGD on all coal-fired thermal plants by phased deadlines (multiple extensions). State-share reflects installed-base ratio, not commissioned + operational.",
    },
    caveats: [
      "Single-snapshot data (2026 reading). Time-series version requires periodic CPCB compliance audit re-snapshot.",
      "States with zero coal-thermal capacity show NaN (excluded from this CSV). Hydro/renewable-heavy states naturally absent.",
      "'Installed' includes commissioned-but-not-yet-operational units; effective operational share may be lower.",
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "fiscal/net_transfers_from_centre",
    canonical_parent_indicator_id: "net-transfers-from-centre-inr-crore",
    table_id: "fiscal.fiscal_canonical",
    facet_axis_id: "budget_phase",
    meta: {
      id: "net-transfers-from-centre-inr-crore",
      title: "Net transfers from Centre (INR crore)",
      description: "Total devolution + grants from Central Government to each state in a fiscal year, net of returns and adjustments. 3 facets: 'Accounts' (settled past years), 'RE' (Revised Estimate for current year), 'BE' (Budget Estimate for forthcoming year).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "neutral",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "landmark",
      attribution_geography: "where_administered",
      comparability: "directional_only",
      implementing_authority: "centre",
      methodology_vintage: "RBI State Finances: A Study of Budgets, Statement 17 (Devolution and Transfer of Resources from the Centre - Net column), 2025-26 edition. Earlier years require scraping prior editions.",
      notes: "Devolution = state's share in central taxes (Finance Commission formula). Grants = Finance Commission grants + centrally-sponsored scheme grants + special-purpose transfers. This is the federal-transfer side of state fiscal capacity. Coverage is THIN (3 fiscal years 2023-24 Accounts + 2024-25 RE + 2025-26 BE).",
    },
    caveats: [
      "Coverage is THIN: only 3 fiscal years (1 Accounts + 1 RE + 1 BE) in the upstream snapshot. Earlier years require scraping prior RBI State Finances editions.",
      "BE (Budget Estimate) and RE (Revised Estimate) facets are upstream projections, NOT settled Accounts; treat as forward-looking guidance.",
      "Raw INR-crore not directly cross-state comparable; per-capita and %-of-state-revenue normalisations are sibling indicators that need ingestion.",
      "Comparability marked directional-only due to thin time series and mixed Accounts/RE/BE rows.",
    ],
    facet_values: [
      {
        canonical_child_id: "net-transfers-from-centre-inr-crore-accounts",
        legacy_facet_label: "Accounts",
        csv_path: "data/datapoints/geo/net-transfers-from-centre-inr-crore-accounts.csv",
      },
      {
        canonical_child_id: "net-transfers-from-centre-inr-crore-re",
        legacy_facet_label: "RE",
        csv_path: "data/datapoints/geo/net-transfers-from-centre-inr-crore-re.csv",
      },
      {
        canonical_child_id: "net-transfers-from-centre-inr-crore-be",
        legacy_facet_label: "BE",
        csv_path: "data/datapoints/geo/net-transfers-from-centre-inr-crore-be.csv",
      },
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/state_external_debt_inr_crore",
    canonical_indicator_id: "state-external-debt-inr-crore",
    csv_path: "data/datapoints/geo/state-external-debt-inr-crore.csv",
    table_id: "fiscal.fiscal_canonical",
    meta: {
      id: "state-external-debt-inr-crore",
      title: "State external debt (INR crore)",
      description: "Outstanding external debt at state level, INR crore. Single snapshot from Rajya Sabha parliamentary answer; sub-set of states reporting.",
      entity_kind: "state",
      time_grain: "year",
      value_kind: "currency",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "trending-down",
      attribution_geography: "where_administered",
      comparability: "directional_only",
      implementing_authority: "state",
      methodology_vintage: "Rajya Sabha Session 259 Unstarred Question 1480 (response date Feb-2023). Single-snapshot answer; sub-set of states.",
      notes: "External debt = debt denominated in foreign currency, typically multilateral lender (World Bank, ADB, JICA, etc.) loans. Single-snapshot from parliamentary answer; not a time-series.",
    },
    caveats: [
      "Single snapshot from a parliamentary answer; not a time-series.",
      "Sub-set of states reporting; absent states either had no external debt or did not report.",
      "Time grain coarsened to year (2026) for the canonical CSV; original publication date was 2023 but the answer covered cumulative outstanding through that date.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/state_non_tax_revenue_inr_crore",
    canonical_indicator_id: "non-tax-revenue-inr-crore",
    csv_path: "data/datapoints/geo/non-tax-revenue-inr-crore.csv",
    table_id: "fiscal.fiscal_canonical",
    meta: {
      id: "non-tax-revenue-inr-crore",
      title: "State non-tax revenue (INR crore)",
      description: "State Government revenue from non-tax sources (royalties, dividends, fees, fines, interest, share of PSU profits, etc.), INR crore. Excludes own-tax revenue and central transfers.",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "higher_is_better",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "landmark",
      attribution_geography: "where_administered",
      comparability: "comparable_with_normalisation",
      implementing_authority: "state",
      methodology_vintage: "Rajya Sabha Session 260 Unstarred Question 1323 (response date 1-Aug-2023). Covers fiscal years 2016-17 to 2022-23.",
      notes: "Mining royalties dominate for mineral-rich states (Odisha, Jharkhand, Chhattisgarh); dividend income from state PSUs significant for some states. Read alongside own-tax-revenue-inr-crore for the full picture of state revenue effort.",
    },
    caveats: [
      "Covers fiscal years 2016-17 to 2022-23 only (the window of the parliamentary question).",
      "Raw INR-crore not directly cross-state comparable; per-capita and %-of-GSDP normalisations needed.",
      "Mining-royalty windfalls (e.g. Odisha iron ore) can drive year-to-year spikes; not a steady-state measure.",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/states_combined_gross_fiscal_deficit",
    canonical_indicator_id: "states-combined-gross-fiscal-deficit-inr-crore",
    csv_path: "data/datapoints/geo/states-combined-gross-fiscal-deficit-inr-crore.csv",
    table_id: "fiscal.fiscal_canonical",
    meta: {
      id: "states-combined-gross-fiscal-deficit-inr-crore",
      title: "States combined Gross Fiscal Deficit (INR crore)",
      description: "Aggregate Gross Fiscal Deficit of all 28 states + Delhi + Puducherry combined, INR crore. The macro picture of state-level fiscal positioning.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "trending-down",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "joint",
      methodology_vintage: "RBI State Finances: A Study of Budgets - all-states aggregate, multiple editions covering FY 2006-07 through FY 2025-26 BE.",
      notes: "FRBM target for combined state deficit: 3% of GSDP (combined); COVID-19 stimulus relaxed to 5%+ for FY 2020-21. Cross-cycle Finance Commission boundaries (FY 2015-16, FY 2020-21) frame the policy regime.",
    },
    caveats: [
      "Includes RE (Revised Estimate) and BE (Budget Estimate) tail years where Accounts not yet settled; treat tail values as projections.",
      "Country-grain aggregate; per-state breakdown lives in sibling indicators (e.g. outstanding-liabilities-pct-gsdp).",
    ],
  },

  {
    kind: "single",
    legacy_artifact_id: "fiscal/union_gross_fiscal_deficit",
    canonical_indicator_id: "union-gross-fiscal-deficit-inr-crore",
    csv_path: "data/datapoints/geo/union-gross-fiscal-deficit-inr-crore.csv",
    table_id: "fiscal.fiscal_canonical",
    meta: {
      id: "union-gross-fiscal-deficit-inr-crore",
      title: "Union Gross Fiscal Deficit (INR crore)",
      description: "Central (Union) Government Gross Fiscal Deficit in INR crore. The macro headline of central-government borrowing requirement.",
      entity_kind: "country",
      time_grain: "fiscal_year",
      value_kind: "currency",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "INR crore",
      short_unit: "INRcr",
      icon: "trending-down",
      attribution_geography: "where_administered",
      comparability: "comparable_across_time",
      implementing_authority: "centre",
      methodology_vintage: "RBI Handbook of Statistics on Indian Economy - Union Government Finances tables, multiple editions covering FY 1980-81 through latest BE.",
      notes: "FRBM target for Centre: 3% of GDP; relaxed during COVID-19 to 9.2% (FY 2020-21). Path back to FRBM-target is the framing for fiscal-glide-path budget speeches.",
    },
    caveats: [
      "Includes RE and BE tail years; treat as projections.",
      "FRBM target framing as %-of-GDP is a separate sibling indicator (not yet a canonical id); raw INR-crore here.",
    ],
  },

  {
    kind: "facet-multiplexed",
    legacy_artifact_id: "prices/cpi_inflation_pct",
    canonical_parent_indicator_id: "cpi-inflation-pct",
    table_id: "prices.prices_canonical",
    facet_axis_id: "cpi_subindex",
    meta: {
      id: "cpi-inflation-pct",
      title: "State CPI inflation (% YoY)",
      description: "State-wise annual CPI inflation, % year-over-year. 4 facets: 'general' (headline all-items index), 'food' (Food and Beverages sub-index), 'fuel' (Fuel and Light sub-index), 'housing_urban' (Housing sub-index, urban areas only).",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "rate",
      direction: "lower_is_better",
      scale_hint: "linear",
      unit: "% YoY",
      short_unit: "%",
      icon: "trending-up",
      attribution_geography: "where_consumed",
      comparability: "comparable_across_states_and_time",
      implementing_authority: "centre",
      methodology_vintage: "RBI Handbook of Statistics on Indian States 2024-25, Tables 108-111 (State-wise Average Inflation - CPI, General + Food and Beverages + Fuel and Light + Housing-Urban). Compiled by MoCI Office of the Economic Adviser / Labour Bureau MoLE.",
      notes: "RBI inflation target (medium-term): 4% +/- 2% (Monetary Policy Committee, since 2016). Food + Fuel facets are the volatile components; General is the headline index. Housing-Urban only collected for urban areas (no rural sub-index).",
    },
    caveats: [
      "Base year is CPI 2012=100 (rural+urban combined); Labour Bureau CPI-IW for industrial workers is a separate series.",
      "Headline 'general' facet is the all-items index; food + fuel + housing facets are sub-indices and do not sum to general.",
      "Housing-Urban facet is urban-area-only; rural housing inflation not separately published.",
    ],
    facet_values: [
      {
        canonical_child_id: "cpi-inflation-pct-general",
        legacy_facet_label: "general",
        csv_path: "data/datapoints/geo/cpi-inflation-pct-general.csv",
      },
      {
        canonical_child_id: "cpi-inflation-pct-food",
        legacy_facet_label: "food",
        csv_path: "data/datapoints/geo/cpi-inflation-pct-food.csv",
      },
      {
        canonical_child_id: "cpi-inflation-pct-fuel",
        legacy_facet_label: "fuel",
        csv_path: "data/datapoints/geo/cpi-inflation-pct-fuel.csv",
      },
      {
        canonical_child_id: "cpi-inflation-pct-housing-urban",
        legacy_facet_label: "housing_urban",
        csv_path: "data/datapoints/geo/cpi-inflation-pct-housing-urban.csv",
      },
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
