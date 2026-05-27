// Vitest — Phase B canonical→legacy IndicatorArtifact adapter
// (P.1.A C4.7, plan TODO/20260524-p1a-data-reacquisition-plan.md §3).
//
// Per CLAUDE.md §15: the loader's contract IS the DuckDB-WASM boundary —
// mocking `query` / `registerTable` is the explicit carve-out from Holy
// Law #7 (no mocks). The round-trip against the real Parquet shard is
// asserted by the §13 browser-smoke (state hub /s/tamil-nadu shows the
// peak demand card with the FY13–FY25 sparkline + 245.4k MW national).

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  registerSlice: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

vi.mock("../indicators", async () => {
  // Pull in the real module so we re-export every helper the production
  // code path expects (uniqueTimes, seriesByEntity, ...). Only the
  // network-touching `fetchIndicator` gets a vi.fn() stub so the
  // Phase B-extension `loadIndicator(path)` legacy fall-through can be
  // asserted without hitting fetch().
  const actual = await vi.importActual<typeof import("../indicators")>("../indicators");
  return {
    ...actual,
    fetchIndicator: vi.fn(),
  };
});

import { query, registerTable } from "../duckdb";
import { fetchIndicator } from "../indicators";
import {
  buildIndicatorArtifact,
  canonicalEntityToLegacy,
  entityKindToAdminLevel,
  legacyArtifactIdFromPath,
  loadIndicator,
  loadIndicatorFromCanonical,
  loadIndicatorIfCanonical,
} from "./indicator-from-canonical";
import {
  CANONICAL_BACKED_INDICATORS,
  getCanonicalDescriptor,
  isCanonicalBacked,
  type CanonicalIndicatorDescriptor,
} from "./indicator-allowlist";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);
const mockedFetch = vi.mocked(fetchIndicator);

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
  mockedFetch.mockReset();
});

// Test fixture mirrors the on-disk shape of the C4.7 Phase A canonical row.
// Pre-loaded into the descriptor lookup; one real entry today (peak demand).
const PEAK_DEMAND_DESCRIPTOR: CanonicalIndicatorDescriptor = getCanonicalDescriptor(
  "energy/state_peak_electricity_demand_mw",
)!;

// PR-H (2026-05-25) — after Hans-curated caveats landed on PEAK_DEMAND_DESCRIPTOR
// + per-capita-consumption + atc-losses, we need a real allowlist descriptor
// that DOES NOT carry `caveats[]` for the "default behavior" test below.
// peak-electricity-supplied-mw (the PR-F sibling) is the cleanest
// analog: same family, same shape, no Hans caveats authored yet.
const NO_CAVEATS_DESCRIPTOR: CanonicalIndicatorDescriptor = getCanonicalDescriptor(
  "energy/state_peak_met_mw",
)!;

describe("indicator-allowlist (Phase B registry invariants)", () => {
  it("exports at least one descriptor (the C4.7 Phase B seed)", () => {
    expect(CANONICAL_BACKED_INDICATORS.length).toBeGreaterThan(0);
  });

  it("treats the seed peak-demand artifact as canonical-backed", () => {
    expect(isCanonicalBacked("energy/state_peak_electricity_demand_mw")).toBe(true);
  });

  it("treats unrelated artifacts as legacy-backed (false)", () => {
    // PR-F (2026-05-25): `energy/state_per_capita_electricity_consumption_kwh`
    // moved into the allowlist this PR (closes 1 of 4 /t/energy 404s);
    // replaced here with a synthetic id that has no real shard surface.
    expect(isCanonicalBacked("energy/this_id_does_not_exist_in_allowlist")).toBe(false);
    expect(isCanonicalBacked("does/not/exist")).toBe(false);
    expect(isCanonicalBacked("")).toBe(false);
  });

  it("resolves the descriptor for the seed artifact and null otherwise", () => {
    const d = getCanonicalDescriptor("energy/state_peak_electricity_demand_mw");
    expect(d).not.toBeNull();
    // Seed descriptor is the kind:"single" shape — narrow before accessing
    // the single-variant canonical_indicator_id field.
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("peak-electricity-demand-mw");
    }
    expect(d!.table_id).toBe("energy.energy_demand_supply");
    expect(getCanonicalDescriptor("nope")).toBeNull();
  });

  it("seed descriptor carries the citizen-visible IndicatorMeta block", () => {
    expect(PEAK_DEMAND_DESCRIPTOR.meta.title).toMatch(/peak/i);
    expect(PEAK_DEMAND_DESCRIPTOR.meta.unit).toBe("MW");
    expect(PEAK_DEMAND_DESCRIPTOR.meta.entity_kind).toBe("state");
    expect(PEAK_DEMAND_DESCRIPTOR.meta.time_grain).toBe("fiscal_year");
  });

  // PR-E (AboutThisData RPO caveat surfacing) extended by Row 4 IA pass
  // (2026-05-25, this PR): the RPO descriptor now carries THREE citizen-
  // honesty bullets — PR-E's original two plus the Row-4 obligation-MET
  // vs share clarification authored by Hans. Surfaced verbatim in the
  // AboutThisData "Known caveats" section under Card 5 ("Clean-energy
  // purchase targets met (%)") on /s/<state>/t/energy.
  it("RPO descriptor carries the three citizen-honesty caveats (PR-E + Row 4)", () => {
    const rpo = getCanonicalDescriptor("energy/state_rpo_compliance_pct");
    expect(rpo).not.toBeNull();
    expect(rpo!.kind).toBe("facet-multiplexed");
    expect(rpo!.caveats).toBeDefined();
    expect(rpo!.caveats!.length).toBe(3);
    // Caveat 1: the "total" semantics warning (primary citizen-honesty
    // cue; complements the FacetPicker primitive shipped in PR-D #277).
    expect(rpo!.caveats![0]).toMatch(/NOT the sum of solar/);
    expect(rpo!.caveats![0]).toMatch(/combined-target/);
    // Caveat 2: the temporal-comparability warning (RPO targets rise
    // over time + vary by state).
    expect(rpo!.caveats![1]).toMatch(/targets vary by state and rise over time/i);
    // Caveat 3 (Row 4 / Hans): obligation MET vs state's clean-energy share
    // — over-compliance via REC trades is real (Gujarat 130%); under-
    // compliance is buying RECs (Bihar). Defuses the "60% means 60%
    // renewable" misread the heading rewrite amplifies.
    expect(rpo!.caveats![2]).toMatch(/obligation MET/);
    expect(rpo!.caveats![2]).toMatch(/Gujarat/);
    expect(rpo!.caveats![2]).toMatch(/Bihar/);
    expect(rpo!.caveats![2]).toMatch(/RECs?/);
  });

  // PR-H (2026-05-25): Hans-curated caveats land on 3 additional canonical
  // descriptors (peak-demand + per-capita-consumption + atc-losses).
  // Each test asserts: (a) caveats[] is populated, (b) the count matches
  // the authored bullet count, (c) a key phrase from each bullet survives
  // a regex match so a future content edit that breaks the citizen-honesty
  // intent (e.g. silently dropping a bullet) trips the suite.
  //
  // These tests pin the AUTHORED INTENT, not the verbatim text — so cosmetic
  // copy-editing (punctuation, em-dash polishing) does NOT break them, but
  // a wholesale rewrite or deletion does.
  it("PR-H peak-demand descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_peak_electricity_demand_mw");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: instantaneous-vs-average misread (Rosling 'Size' instinct guard).
    expect(d!.caveats![0]).toMatch(/highest single-instant load/i);
    // 2: supplied-gap framing (load-shedding signal).
    expect(d!.caveats![1]).toMatch(/peak-electricity-supplied-mw/);
    expect(d!.caveats![1]).toMatch(/unmet demand/i);
    // 3: FY20 RBI rename-not-methodology-break clarification.
    expect(d!.caveats![2]).toMatch(/Demand Not Met/);
    expect(d!.caveats![2]).toMatch(/FY 2019-20/);
  });

  it("PR-H per-capita-consumption descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor(
      "energy/state_per_capita_electricity_consumption_kwh",
    );
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Gujarat-industrial + Punjab-pumping "per person includes more
    // than households" anchor. Row 4 IA pass (2026-05-25) replaced PR-H's
    // Kerala/Chhattisgarh framing with this version after the heading
    // rewrite to "Electricity used per person (kWh/year)" amplified the
    // household-only misreading risk (Hans verdict).
    expect(d!.caveats![0]).toMatch(/'Per person'/);
    expect(d!.caveats![0]).toMatch(/Gujarat/);
    expect(d!.caveats![0]).toMatch(/Punjab/);
    expect(d!.caveats![0]).toMatch(/2-3x lower/);
    // 2: Census 2011 + projection denominator staleness flag.
    expect(d!.caveats![1]).toMatch(/Census 2011/);
    expect(d!.caveats![1]).toMatch(/Census 2027/);
    // 3: billed-vs-delivered (AT&C gap excluded from numerator).
    expect(d!.caveats![2]).toMatch(/BILLED/);
    expect(d!.caveats![2]).toMatch(/DELIVERED/);
  });

  it("PR-H atc-losses descriptor carries the 4 Hans-curated caveats (PR-H + Row 4 break-marker)", () => {
    const d = getCanonicalDescriptor("energy/state_atc_losses_pct");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    // Row 4 IA pass (2026-05-25): 4th caveat APPENDED to PR-H's 3 bullets
    // to surface the UDAY → PFC FY18 methodology break (Hans non-negotiable
    // #7 interim disclosure until methodology-breaks sparkline primitive
    // lands as a Level-4 follow-up).
    expect(d!.caveats!.length).toBe(4);
    // 1: technical-vs-commercial bundling (Pramit's 'one number, two
    // phenomena' editorial flag).
    expect(d!.caveats![0]).toMatch(/technical losses/i);
    expect(d!.caveats![0]).toMatch(/commercial losses/i);
    expect(d!.caveats![0]).toMatch(/policy fixes differ/i);
    // 2: UDAY target + league-table exemplars (Hans Rosling
    // "name the best entity" framing).
    expect(d!.caveats![1]).toMatch(/UDAY/);
    expect(d!.caveats![1]).toMatch(/15%/);
    expect(d!.caveats![1]).toMatch(/Gujarat|Andhra|Kerala|Himachal/);
    // 3: reporting-integrity caveat (feeder-metering under-reporting).
    expect(d!.caveats![2]).toMatch(/feeder metering/i);
    expect(d!.caveats![2]).toMatch(/agricultural/i);
    // 4 (Row 4 / Hans): UDAY → PFC FY18 hard methodology break. Bihar
    // 38→28% across FY17-FY19 is partly the denominator shift, not the
    // turnaround. Defuses the smooth-line misreading that the post-FY18
    // PFC integrated rating denominators tighten the reported number.
    expect(d!.caveats![3]).toMatch(/UDAY/);
    expect(d!.caveats![3]).toMatch(/PFC/);
    expect(d!.caveats![3]).toMatch(/FY18/);
    expect(d!.caveats![3]).toMatch(/Bihar/);
  });

  // Row 4 IA pass (2026-05-25): NEW caveats arrays land on the two
  // facet-multiplexed survivors of the /t/energy chapter prune (cards 2
  // and 3 in Jony's scroll order). Each carries 3 Hans-curated bullets
  // sourced from the methodology-break + cross-card audit. The pair is
  // coordinated: card-2 bullet 3 explicitly points to card 3 and vice
  // versa, so the cognitive trap (GWh delivered vs MW nameplate) is
  // surfaced symmetrically from both ends.
  it("Row 4: generation-by-source descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor(
      "energy/state_electricity_generation_by_source_gwh",
    );
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: ICED SUB_FUEL_TO_CANONICAL collapse (lignite-into-coal,
    // solar+wind+biomass-into-renewable). Tamil Nadu coal absorbs
    // Neyveli lignite; Karnataka renewable bundles wind + solar.
    expect(d!.caveats![0]).toMatch(/ICED/);
    expect(d!.caveats![0]).toMatch(/lignite/i);
    expect(d!.caveats![0]).toMatch(/Tamil Nadu|Karnataka/);
    // 2: CEA vs ICED cut-off convention drift (month-end snapshots vs
    // financial-year-end). Gujarat coal-share micro-shifts may be
    // cut-off artifacts, not new plants.
    expect(d!.caveats![1]).toMatch(/CEA/);
    expect(d!.caveats![1]).toMatch(/ICED/);
    expect(d!.caveats![1]).toMatch(/cut-off/i);
    expect(d!.caveats![1]).toMatch(/Gujarat/);
    // 3: coordinated cross-card pointer to card 3 (GWh delivered vs
    // MW built). High coal generation may be many coal plants or few
    // plants run hard — the policy fixes differ.
    expect(d!.caveats![2]).toMatch(/GWh/);
    expect(d!.caveats![2]).toMatch(/Power plants built/i);
    expect(d!.caveats![2]).toMatch(/policy fixes differ/i);
  });

  it("Row 4: installed-capacity-by-source descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor(
      "energy/state_installed_capacity_by_source_mw",
    );
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: coordinated cross-card pointer to card 2 (MW nameplate vs GWh
    // delivered). 1GW solar delivers like 200MW of coal would — RUN vs
    // BUILT distinction.
    expect(d!.caveats![0]).toMatch(/MW.*nameplate/i);
    expect(d!.caveats![0]).toMatch(/Where your state's power comes from/i);
    expect(d!.caveats![0]).toMatch(/RUN/);
    expect(d!.caveats![0]).toMatch(/BUILT/);
    // 2: inter-state PPA trap ("installed in state" not "available to
    // state"). Rihand (MP) serves UP; Dadri (UP) serves Delhi.
    expect(d!.caveats![1]).toMatch(/Madhya Pradesh|MP/);
    expect(d!.caveats![1]).toMatch(/Maharashtra/);
    expect(d!.caveats![1]).toMatch(/PPAs?/);
    expect(d!.caveats![1]).toMatch(/Rihand/);
    expect(d!.caveats![1]).toMatch(/Dadri/);
    // 3: CEA SUB_FUEL_TO_CANONICAL collapse mirror of card 2 bullet 1.
    expect(d!.caveats![2]).toMatch(/CEA/);
    expect(d!.caveats![2]).toMatch(/lignite/i);
    expect(d!.caveats![2]).toMatch(/Tamil Nadu|Karnataka/);
  });

  // PR-F (2026-05-25): 2 new allowlist entries close /t/energy 404s flagged
  // by user smoke. Both entries map legacy short-name shards to existing
  // canonical indicators in `energy.energy_demand_supply`; meta blocks
  // sourced from datasets/taxonomy/indicators.json per the allowlist
  // authoring doctrine (lines 47-75).
  it("PR-F peak_met descriptor routes to peak-electricity-supplied-mw", () => {
    const d = getCanonicalDescriptor("energy/state_peak_met_mw");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("peak-electricity-supplied-mw");
    }
    expect(d!.table_id).toBe("energy.energy_demand_supply");
    expect(d!.meta.title).toMatch(/peak power supplied/i);
    expect(d!.meta.unit).toBe("MW");
    expect(d!.meta.direction).toBe("higher_is_better");
  });

  it("PR-F per_capita_consumption descriptor routes to per-capita-electricity-consumption-kwh", () => {
    const d = getCanonicalDescriptor("energy/state_per_capita_electricity_consumption_kwh");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("per-capita-electricity-consumption-kwh");
    }
    expect(d!.table_id).toBe("energy.energy_demand_supply");
    // Row 4 IA pass (2026-05-25): heading rewritten from "State per-capita
    // electricity consumption (kWh/year)" to citizen-anchored "Electricity
    // used per person (kWh/year)" per Citizen subagent verdict.
    expect(d!.meta.title).toMatch(/electricity used per person/i);
    expect(d!.meta.unit).toBe("kWh per person per year");
    // Distinct from per-capita AVAILABILITY (RBI T138) — consumption is
    // billed end-use, availability is delivered-to-state (incl. T&D losses).
    expect(d!.meta.attribution_geography).toBe("where_consumed");
  });

  // PR-G (2026-05-25): 4 new allowlist entries close the 5 remaining
  // /t/energy 404s discovered during PR-F's §13 smoke. Two singles route
  // to ICED-sourced distribution-performance canonicals; two faceted
  // entries route to fuel_type-multiplexed parents already wired by
  // PR 7a for their totals-only sibling slugs. The 5th 404
  // (state_installed_capacity_total_mw) is resolved by a topics.json
  // prune (Pattern B duplicate of state_installed_capacity_with_alloc_mw),
  // not an allowlist add.
  it("PR-G state_electricity_sales_mu descriptor routes to electricity-sales-mu", () => {
    const d = getCanonicalDescriptor("energy/state_electricity_sales_mu");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("electricity-sales-mu");
    }
    expect(d!.table_id).toBe("energy.energy_distribution_performance");
    expect(d!.meta.title).toMatch(/electricity sales/i);
    expect(d!.meta.unit).toBe("MU");
    // ICED end-consumer billing attribution (distinct from where-administered).
    expect(d!.meta.attribution_geography).toBe("where_billed");
  });

  it("PR-G state_atc_losses_pct descriptor routes to atc-losses-pct", () => {
    const d = getCanonicalDescriptor("energy/state_atc_losses_pct");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("atc-losses-pct");
    }
    expect(d!.table_id).toBe("energy.energy_distribution_performance");
    // Row 4 IA pass (2026-05-25): heading rewritten from "Aggregate Technical
    // & Commercial losses (%, by state)" to citizen-anchored "Power lost to
    // leaks and theft (%)" per Citizen + Hans verdicts.
    expect(d!.meta.title).toMatch(/power lost.*leaks.*theft/i);
    expect(d!.meta.unit).toBe("%");
    // Discom-health metric: lower is better (UDAY target was <15%).
    expect(d!.meta.direction).toBe("lower_is_better");
  });

  // PR-I (Row 5 PR-1, 2026-05-25): Hans-curated caveats land on the 4
  // indicators that decompose the AT&C ledger. Sales-MU is the absolute-MU
  // denominator; billing + collection + T&D loss decompose AT&C into
  // commercial + technical halves per the identity
  //   AT&C loss approx 1 - (billing x collection / 100) + T&D loss.
  // Each card carries 3 Hans bullets with named-state anchors + cross-card
  // pointers (by indicator title, not canonical id, so the cross-reference
  // survives heading rewrites). Authored-intent regex assertions over
  // verbatim text per the PR-H test-resilience pattern.
  it("PR-I sales-mu descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_electricity_sales_mu");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Generation MINUS Sales = absolute AT&C loss; pair with generation.
    expect(d!.caveats![0]).toMatch(/Generation MINUS Sales/);
    expect(d!.caveats![0]).toMatch(/AT&C/);
    // 2: 1 MU = 1 GWh unit equivalence; state-PR vs CEA reconciliation.
    expect(d!.caveats![1]).toMatch(/1 MU = 1 GWh/);
    expect(d!.caveats![1]).toMatch(/Punjab|Tamil Nadu/);
    expect(d!.caveats![1]).toMatch(/CEA/);
    // 3: Intra-state imports; Delhi/Goa/Punjab buy from central pool.
    expect(d!.caveats![2]).toMatch(/intra-state imports/i);
    expect(d!.caveats![2]).toMatch(/Delhi/);
    expect(d!.caveats![2]).toMatch(/Goa|Punjab/);
  });

  it("PR-I billing-efficiency descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_distribution_billing_efficiency_pct");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Decomposition-identity anchor (commercial half of AT&C).
    expect(d!.caveats![0]).toMatch(/COMMERCIAL half of AT&C/);
    expect(d!.caveats![0]).toMatch(/billing x collection/);
    expect(d!.caveats![0]).toMatch(/collection efficiency/i);
    expect(d!.caveats![0]).toMatch(/T&D loss/);
    // 2: Punjab agricultural pumping unmetered ("assessed" load).
    expect(d!.caveats![1]).toMatch(/Punjab/);
    expect(d!.caveats![1]).toMatch(/unmetered/i);
    expect(d!.caveats![1]).toMatch(/assessed/i);
    // 3: Industrial-feeder ring-fencing vs rural; Gujarat vs Bihar.
    expect(d!.caveats![2]).toMatch(/Gujarat/);
    expect(d!.caveats![2]).toMatch(/Bihar/);
    expect(d!.caveats![2]).toMatch(/consumer category/i);
  });

  it("PR-I collection-efficiency descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_distribution_collection_efficiency_pct");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Government-departmental arrears hidden in headline collection.
    expect(d!.caveats![0]).toMatch(/COMMERCIAL half of AT&C/);
    expect(d!.caveats![0]).toMatch(/government-departmental arrears|government.*arrears/i);
    expect(d!.caveats![0]).toMatch(/PWD|municipal corporation/i);
    // 2: Bihar/UP bond-settlement methodology-break warning.
    expect(d!.caveats![1]).toMatch(/Bihar/);
    expect(d!.caveats![1]).toMatch(/Uttar Pradesh|UP/);
    expect(d!.caveats![1]).toMatch(/bond/i);
    expect(d!.caveats![1]).toMatch(/methodology break/i);
    // 3: Per-category breakdown / weighted-average framing.
    expect(d!.caveats![2]).toMatch(/agricultural/i);
    expect(d!.caveats![2]).toMatch(/weighted average/i);
  });

  it("PR-I td-loss descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_distribution_td_loss_pct");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Decomposition-identity anchor (technical half of AT&C).
    expect(d!.caveats![0]).toMatch(/TECHNICAL half of AT&C/);
    expect(d!.caveats![0]).toMatch(/AT&C loss = T&D loss \+ commercial loss/);
    expect(d!.caveats![0]).toMatch(/billing efficiency/i);
    expect(d!.caveats![0]).toMatch(/collection efficiency/i);
    // 2: Rural-feeder length predictor; Rajasthan + MP.
    expect(d!.caveats![1]).toMatch(/Rajasthan/);
    expect(d!.caveats![1]).toMatch(/Madhya Pradesh|MP/);
    expect(d!.caveats![1]).toMatch(/feeder/i);
    // 3: Bihar mid-2010s: T&D fell while AT&C stayed high.
    expect(d!.caveats![2]).toMatch(/Bihar/);
    expect(d!.caveats![2]).toMatch(/HVDS/);
    expect(d!.caveats![2]).toMatch(/necessary but not sufficient/i);
  });

  it("PR-G state_installed_capacity_by_source_mw descriptor routes to installed-capacity-geographical-mw with 5 fuel children", () => {
    const d = getCanonicalDescriptor("energy/state_installed_capacity_by_source_mw");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("installed-capacity-geographical-mw");
      expect(d!.facet_axis_id).toBe("fuel_type");
      expect(d!.facet_values).toHaveLength(5);
      const fuels = d!.facet_values.map((fv) => fv.legacy_facet_label);
      expect(fuels).toEqual(["coal", "gas", "hydro", "nuclear", "renewable"]);
      // Spot-check one child mapping (coal): canonical_child_id encodes
      // the parent + fuel suffix per indicator-naming.md D30.
      const coal = d!.facet_values.find((fv) => fv.legacy_facet_label === "coal");
      expect(coal?.canonical_child_id).toBe("installed-capacity-geographical-mw-coal");
    }
    expect(d!.table_id).toBe("energy.energy_installed_capacity");
    expect(d!.meta.title).toMatch(/by fuel/i);
    expect(d!.meta.unit).toBe("MW");
  });

  it("PR-G state_electricity_generation_by_source_gwh descriptor routes to electricity-generation-gwh with 5 fuel children", () => {
    const d = getCanonicalDescriptor("energy/state_electricity_generation_by_source_gwh");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("electricity-generation-gwh");
      expect(d!.facet_axis_id).toBe("fuel_type");
      expect(d!.facet_values).toHaveLength(5);
      const fuels = d!.facet_values.map((fv) => fv.legacy_facet_label);
      expect(fuels).toEqual(["coal", "gas", "hydro", "nuclear", "renewable"]);
      const renewable = d!.facet_values.find((fv) => fv.legacy_facet_label === "renewable");
      expect(renewable?.canonical_child_id).toBe("electricity-generation-gwh-renewable");
    }
    expect(d!.table_id).toBe("energy.energy_generation");
    // Row 4 IA pass (2026-05-25): heading rewritten from "State electricity
    // generation, by fuel (GWh)" to citizen-anchored "Where your state's
    // power comes from (GWh)" per Citizen subagent verdict.
    expect(d!.meta.title).toMatch(/where your state.*power comes from/i);
    expect(d!.meta.unit).toBe("GWh");
  });

  // PR-P (Row 5 PR-4, 2026-05-25): Hans-curated caveats land on the 3
  // livestock Pashu Aadhaar species canonical descriptors (cattle +
  // buffalo + goat). Closes Row 5 Tier-1 4/4 of the §1 long-format
  // pivot. Each card carries 3 Hans bullets with named-state anchors
  // and the tagged-COUNT-vs-population framing Hans non-negotiably
  // demands for the Pashu Aadhaar surface (per PR B.01 comment block,
  // a state's tagging rank does not equal its livestock-population rank).
  // Authored-intent regex assertions over verbatim text per the PR-H /
  // PR-I test-resilience pattern.
  // Cattle cohort PR (Row 5 PR-P cohort 2/3, 2026-05-27): cattle state-grain +
  // district-grain descriptors shipped; re-enabling the cattle caveat
  // assertion. Buffalo sibling follows in cohort 3 of 3.
  it("PR-P cattle Pashu Aadhaar descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("agriculture/state_pashu_aadhaar_count_cattle");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Tagged-vs-owned framing; Livestock Census 2019 as denominator.
    expect(d!.caveats![0]).toMatch(/ANIMALS TAGGED/);
    expect(d!.caveats![0]).toMatch(/not cattle owned/i);
    expect(d!.caveats![0]).toMatch(/20th Livestock Census/);
    expect(d!.caveats![0]).toMatch(/40-60% coverage/);
    // 2: Programme-effort-vs-herd-size confound; KA + AP lead, NE trail.
    expect(d!.caveats![1]).toMatch(/Karnataka/);
    expect(d!.caveats![1]).toMatch(/Andhra Pradesh/);
    expect(d!.caveats![1]).toMatch(/Manipur|Mizoram/);
    expect(d!.caveats![1]).toMatch(/Bihar/);
    expect(d!.caveats![1]).toMatch(/programme effort/i);
    // 3: RFID replacement-tag inflation; FY-end snapshot convention.
    expect(d!.caveats![2]).toMatch(/12-digit RFID/);
    expect(d!.caveats![2]).toMatch(/Indus Database/);
    expect(d!.caveats![2]).toMatch(/FY-end/);
  });

  // Buffalo cohort PR (Row 5 PR-P cohort 3/3, 2026-05-27): buffalo state-grain
  // + district-grain descriptors shipped; re-enabling the buffalo caveat
  // assertion. Completes the PR-P trio (cattle + buffalo + goat).
  it("PR-P buffalo Pashu Aadhaar descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("agriculture/state_pashu_aadhaar_count_buffalo");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Milk-belt concentration; UP/Punjab/Haryana hold ~50% of buffaloes.
    expect(d!.caveats![0]).toMatch(/milk-dairy/i);
    expect(d!.caveats![0]).toMatch(/UP, Punjab, Haryana/);
    expect(d!.caveats![0]).toMatch(/Murrah/);
    expect(d!.caveats![0]).toMatch(/Kerala/);
    expect(d!.caveats![0]).toMatch(/breed economics/i);
    // 2: Coverage-gap pointer to cattle card; Livestock Census 110M denom.
    expect(d!.caveats![1]).toMatch(/Same coverage gap as cattle/);
    expect(d!.caveats![1]).toMatch(/~110M/);
    expect(d!.caveats![1]).toMatch(/cattle tagged/);
    // 3: Dairy-coop confounder (Gujarat Amul vs vet-camp states).
    expect(d!.caveats![2]).toMatch(/Gujarat/);
    expect(d!.caveats![2]).toMatch(/Amul/);
    expect(d!.caveats![2]).toMatch(/Maharashtra/);
    expect(d!.caveats![2]).toMatch(/dairy cooperatives/i);
    expect(d!.caveats![2]).toMatch(/draught/i);
  });

  // Goat cohort PR (Row 5 PR-P, 2026-05-27): goat descriptors shipped;
  // re-enabling the goat caveat assertion. Cattle and buffalo siblings
  // follow in cohort PRs 2 and 3 of 3.
  it("PR-P goat Pashu Aadhaar descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("agriculture/state_pashu_aadhaar_count_goat");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: Pastoral-nomadic herding; cross-state migration confound.
    expect(d!.caveats![0]).toMatch(/pastoral/i);
    expect(d!.caveats![0]).toMatch(/Rajasthan/);
    expect(d!.caveats![0]).toMatch(/Bhopa/);
    expect(d!.caveats![0]).toMatch(/Banjara/);
    expect(d!.caveats![0]).toMatch(/migratory/i);
    // 2: Coverage-gap pointer to cattle+buffalo; vet-camp triage priority.
    expect(d!.caveats![1]).toMatch(/Same coverage gap as cattle and buffalo/);
    expect(d!.caveats![1]).toMatch(/~149M/);
    expect(d!.caveats![1]).toMatch(/largest livestock category/);
    expect(d!.caveats![1]).toMatch(/vet-camp triage/);
    // 3: Informal-meat-economy confounder (AP + TS lead, Bihar trails).
    expect(d!.caveats![2]).toMatch(/INFORMAL/);
    expect(d!.caveats![2]).toMatch(/Andhra/);
    expect(d!.caveats![2]).toMatch(/Telangana/);
    expect(d!.caveats![2]).toMatch(/mutton-trader/);
    expect(d!.caveats![2]).toMatch(/Bihar/);
    expect(d!.caveats![2]).toMatch(/formalisation/i);
  });

  // PR-Q (Row 6 P.1.C, 2026-05-25): first canonical fuel-consumption lift.
  // Establishes the long-reserved `energy_fuel_consumption` parquet stem
  // and ships coal-consumption-mt with 3 Hans-curated caveats. The
  // adapter sums ICED's 4 grade rows (raw + washed + middlings + lignite)
  // and drops the publisher's TOTAL COAL row to avoid double-counting.
  it("PR-Q state_coal_consumption_mt descriptor routes to coal-consumption-mt", () => {
    const d = getCanonicalDescriptor("energy/state_coal_consumption_mt");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("coal-consumption-mt");
    }
    expect(d!.table_id).toBe("energy.energy_fuel_consumption");
    expect(d!.meta.title).toMatch(/coal consumption/i);
    expect(d!.meta.unit).toBe("Mt");
    // where_consumed -- coal is burned in the attributed state, not mined there.
    expect(d!.meta.attribution_geography).toBe("where_consumed");
    // Joint-implementation cue: ICED (NITI) federally aggregates; Coal
    // Controller's Office / Ministry of Coal upstream; states host the
    // generating + industrial demand.
    expect(d!.meta.implementing_authority).toBe("joint");
    expect(d!.meta.icon).toBe("flame");
    expect(d!.meta.entity_kind).toBe("state");
    expect(d!.meta.time_grain).toBe("fiscal_year");
  });

  it("PR-Q coal-consumption descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_coal_consumption_mt");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: 4-grade SUM methodology + TOTAL COAL dropped to avoid double-counting.
    expect(d!.caveats![0]).toMatch(/4 coal grades|four coal grades|4-grade/i);
    expect(d!.caveats![0]).toMatch(/raw.*washed.*middlings.*lignite/i);
    expect(d!.caveats![0]).toMatch(/TOTAL COAL/);
    expect(d!.caveats![0]).toMatch(/double-counting/i);
    // 2: Heavy-industry-state anchors (Maharashtra, UP, MP, Chhattisgarh).
    expect(d!.caveats![1]).toMatch(/Maharashtra/);
    expect(d!.caveats![1]).toMatch(/UP|Uttar Pradesh/);
    expect(d!.caveats![1]).toMatch(/Chhattisgarh|MP|Madhya Pradesh/);
    expect(d!.caveats![1]).toMatch(/thermal|industrial|kiln/i);
    // 3: where_consumed clarification + companion-card pointer.
    expect(d!.caveats![2]).toMatch(/Jharkhand/);
    expect(d!.caveats![2]).toMatch(/Odisha/);
    expect(d!.caveats![2]).toMatch(/where_consumed|burned|consumed/i);
  });

  // PR-R (Row 6 P.1.C 2/9, 2026-05-25): rooftop solar capacity lift. Joins
  // the existing `energy_installed_capacity` parquet stem (rooftop is a
  // sub-fuel measurement of installed MW; the total solar fleet = rooftop
  // + utility-scale tracked under installed-capacity-snapshot-mw-
  // renewable). 321 obs rows, FY18-FY25, non-faceted.
  it("PR-R state_rooftop_solar_capacity_mw descriptor routes to rooftop-solar-capacity-mw", () => {
    const d = getCanonicalDescriptor("energy/state_rooftop_solar_capacity_mw");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("rooftop-solar-capacity-mw");
    }
    // Rooftop joins the existing installed-capacity parquet stem -- NOT a
    // new stem. The rooftop measurement is logically a sub-fuel of installed MW.
    expect(d!.table_id).toBe("energy.energy_installed_capacity");
    expect(d!.meta.title).toMatch(/rooftop solar/i);
    expect(d!.meta.unit).toBe("MW");
    // where_administered -- the state's nodal agency administers rooftop
    // programmes; building owners install (not the centre, not the utility).
    expect(d!.meta.attribution_geography).toBe("where_administered");
    expect(d!.meta.implementing_authority).toBe("state");
    expect(d!.meta.icon).toBe("sun");
    expect(d!.meta.direction).toBe("higher_is_better");
    expect(d!.meta.entity_kind).toBe("state");
    expect(d!.meta.time_grain).toBe("fiscal_year");
  });

  it("PR-R rooftop-solar descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_rooftop_solar_capacity_mw");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: rooftop-vs-utility-scale mental model + companion-card pointer.
    expect(d!.caveats![0]).toMatch(/rooftop only|rooftop ONLY|rooftop\b.*only/i);
    expect(d!.caveats![0]).toMatch(/utility-scale|utility scale/i);
    expect(d!.caveats![0]).toMatch(/Karnataka|Gujarat/);
    // 2: tariff-economics-not-just-insolation; named-state anchors.
    expect(d!.caveats![1]).toMatch(/tariff/i);
    expect(d!.caveats![1]).toMatch(/Maharashtra|Tamil Nadu/);
    expect(d!.caveats![1]).toMatch(/Rajasthan/);
    expect(d!.caveats![1]).toMatch(/insolation|sunshine/i);
    // 3: cumulative-vs-annual semantics.
    expect(d!.caveats![2]).toMatch(/cumulative/i);
    expect(d!.caveats![2]).toMatch(/annual|year/i);
  });

  // PR-S (Row 6 P.1.C 3/9, 2026-05-25): thermal capacity retired lift. First
  // Pattern A-facet in the P.1.C cohort. National-only (entity_kind="country"),
  // 2 facets after SUB_FUEL_TO_CANONICAL collapse ("oil-gas" -> "gas" per
  // Hans D33.8). Joins the existing `energy_installed_capacity` parquet stem.
  it("PR-S india_thermal_capacity_retired_mw descriptor routes to facet-multiplexed parent", () => {
    const d = getCanonicalDescriptor("energy/india_thermal_capacity_retired_mw");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("india-thermal-capacity-retired-mw");
      expect(d!.facet_axis_id).toBe("fuel_type");
      // Exactly 2 children: coal + gas (oil-gas collapsed). No "oil-gas",
      // no "diesel", no "oil" -- the canonical fuel_type axis only has 5
      // buckets and only coal + gas appear for retired thermal.
      expect(d!.facet_values.length).toBe(2);
      const childIds = d!.facet_values.map((fv) => fv.canonical_child_id).sort();
      expect(childIds).toEqual([
        "india-thermal-capacity-retired-mw-coal",
        "india-thermal-capacity-retired-mw-gas",
      ]);
      const labels = d!.facet_values.map((fv) => fv.legacy_facet_label).sort();
      expect(labels).toEqual(["coal", "gas"]);
      // CRITICAL: legacy_facet_label is the CANONICAL bucket name, NOT the
      // raw publisher label "oil-gas". The collapse must surface to the
      // citizen-facing axis.
      expect(labels).not.toContain("oil-gas");
      expect(labels).not.toContain("oil_gas");
    }
    expect(d!.table_id).toBe("energy.energy_installed_capacity");
    expect(d!.meta.title).toMatch(/thermal capacity retired/i);
    expect(d!.meta.unit).toBe("MW");
    expect(d!.meta.entity_kind).toBe("country");
    expect(d!.meta.time_grain).toBe("fiscal_year");
    expect(d!.meta.direction).toBe("neutral");
    expect(d!.meta.attribution_geography).toBe("where_produced");
    expect(d!.meta.implementing_authority).toBe("joint");
    expect(d!.meta.icon).toBe("trash-2");
  });

  it("PR-S thermal-retired descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/india_thermal_capacity_retired_mw");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: national-only grain; cannot rank a state on this card.
    expect(d!.caveats![0]).toMatch(/national/i);
    expect(d!.caveats![0]).toMatch(/state-level|state level|cannot be ranked/i);
    expect(d!.caveats![0]).toMatch(/CEA|Central Electricity Authority/);
    // 2: gas bucket bundles oil + diesel + gas; not pure natural-gas exit.
    expect(d!.caveats![1]).toMatch(/gas/i);
    expect(d!.caveats![1]).toMatch(/oil-fired|oil fired|diesel/i);
    expect(d!.caveats![1]).toMatch(/oil-gas|publisher label/i);
    // 3: retirements != exit; pair with additions to read net.
    expect(d!.caveats![2]).toMatch(/coal retirements|≠|not.*exit|exit\b/i);
    expect(d!.caveats![2]).toMatch(/installed-capacity|additions|net/i);
  });

  // PR-T (Row 6 P.1.C 4/9, 2026-05-25): state oil-product consumption lift.
  // Second Pattern A-facet in the P.1.C cohort, on the NEW `oil_product`
  // axis (no SUB_FUEL_TO_CANONICAL collapse -- 1:1 publisher-to-canonical
  // for the 7 product children). Joins the `energy_fuel_consumption`
  // parquet stem (also used by PR-Q coal-consumption).
  it("PR-T state_oil_product_consumption_kt descriptor routes to facet-multiplexed parent", () => {
    const d = getCanonicalDescriptor("energy/state_oil_product_consumption_kt");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("oil-product-consumption-kt");
      expect(d!.facet_axis_id).toBe("oil_product");
      // Exactly 7 children: diesel-hsd, petrol, lpg, kerosene, naphtha,
      // petroleum-coke, others. Publisher labels are 1:1 with canonical
      // value_ids (no SUB_FUEL_TO_CANONICAL collapse).
      expect(d!.facet_values.length).toBe(7);
      const childIds = d!.facet_values.map((fv) => fv.canonical_child_id).sort();
      expect(childIds).toEqual([
        "oil-product-consumption-kt-diesel-hsd",
        "oil-product-consumption-kt-kerosene",
        "oil-product-consumption-kt-lpg",
        "oil-product-consumption-kt-naphtha",
        "oil-product-consumption-kt-others",
        "oil-product-consumption-kt-petrol",
        "oil-product-consumption-kt-petroleum-coke",
      ]);
      const labels = d!.facet_values.map((fv) => fv.legacy_facet_label).sort();
      expect(labels).toEqual([
        "diesel-hsd",
        "kerosene",
        "lpg",
        "naphtha",
        "others",
        "petrol",
        "petroleum-coke",
      ]);
    }
    expect(d!.table_id).toBe("energy.energy_fuel_consumption");
    expect(d!.meta.title).toMatch(/oil-product consumption/i);
    expect(d!.meta.unit).toBe("kt");
    expect(d!.meta.entity_kind).toBe("state");
    expect(d!.meta.time_grain).toBe("fiscal_year");
    expect(d!.meta.direction).toBe("neutral");
    expect(d!.meta.attribution_geography).toBe("where_consumed");
    expect(d!.meta.implementing_authority).toBe("centre");
    expect(d!.meta.icon).toBe("fuel");
  });

  it("PR-T oil-product-consumption descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_oil_product_consumption_kt");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: where-consumed not where-refined; Gujarat/Jamnagar refinery anchor.
    expect(d!.caveats![0]).toMatch(/where-?CONSUMED|consumed.*not.*refined/i);
    expect(d!.caveats![0]).toMatch(/Gujarat|Jamnagar/);
    expect(d!.caveats![0]).toMatch(/Punjab|Haryana|agricultural/i);
    // 2: LPG tracks PMUY rollout, not wealth; Bihar/UP/MP anchor.
    expect(d!.caveats![1]).toMatch(/LPG/);
    expect(d!.caveats![1]).toMatch(/PMUY|Ujjwala/);
    expect(d!.caveats![1]).toMatch(/Bihar|UP|MP|Rajasthan/);
    // 3: petroleum-coke air-quality regulation; NCR/Supreme Court anchor.
    expect(d!.caveats![2]).toMatch(/pet[ -]?coke|petroleum-?coke/i);
    expect(d!.caveats![2]).toMatch(/NCR|Supreme Court|air[ -]?quality|emissions/i);
    expect(d!.caveats![2]).toMatch(/cement|glass|industrial/i);
  });

  // PR-U (Row 6 P.1.C 5/9, 2026-05-26): national primary energy supply (TPES)
  // lift. Third Pattern A-facet in the P.1.C cohort, on the EXISTING
  // `fuel_type` axis (extended with `oil` + `renewable` value_ids in this PR).
  // National-only (entity_kind="country") -- ICED does NOT publish state-level
  // TPES. Joins the `energy_fuel_consumption` parquet stem.
  it("PR-U national_primary_energy_supply_mtoe descriptor routes to facet-multiplexed parent", () => {
    const d = getCanonicalDescriptor("energy/national_primary_energy_supply_mtoe");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("india-primary-energy-supply-mtoe");
      expect(d!.facet_axis_id).toBe("fuel_type");
      // Exactly 6 children on the canonical fuel_type axis (publisher's
      // 7th facet 'total' is FILTERED at canonical lift as compute-on-read
      // parent semantics).
      expect(d!.facet_values.length).toBe(6);
      const childIds = d!.facet_values.map((fv) => fv.canonical_child_id).sort();
      expect(childIds).toEqual([
        "india-primary-energy-supply-mtoe-coal",
        "india-primary-energy-supply-mtoe-gas",
        "india-primary-energy-supply-mtoe-hydro",
        "india-primary-energy-supply-mtoe-nuclear",
        "india-primary-energy-supply-mtoe-oil",
        "india-primary-energy-supply-mtoe-renewable",
      ]);
      // Publisher `renewables` plural collapses to canonical `renewable`
      // singular; the legacy_facet_label is the CANONICAL bucket name
      // (not the raw publisher label).
      const labels = d!.facet_values.map((fv) => fv.legacy_facet_label).sort();
      expect(labels).toEqual(["coal", "gas", "hydro", "nuclear", "oil", "renewable"]);
      expect(labels).not.toContain("renewables");
    }
    expect(d!.table_id).toBe("energy.energy_fuel_consumption");
    expect(d!.meta.title).toMatch(/primary energy supply|TPES/i);
    expect(d!.meta.unit).toBe("mtoe");
    expect(d!.meta.entity_kind).toBe("country");
    expect(d!.meta.time_grain).toBe("fiscal_year");
    expect(d!.meta.direction).toBe("neutral");
    expect(d!.meta.attribution_geography).toBe("where_consumed");
    expect(d!.meta.implementing_authority).toBe("centre");
  });

  it("PR-U primary-energy-supply descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/national_primary_energy_supply_mtoe");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: national-only grain; ICED does not publish state-level TPES.
    expect(d!.caveats![0]).toMatch(/national/i);
    expect(d!.caveats![0]).toMatch(/state-level|state level|cannot be ranked/i);
    expect(d!.caveats![0]).toMatch(/MU|GWh|electricity|kt|coal/i);
    // 2: TPES is not what you USE; conversion losses anchor.
    expect(d!.caveats![1]).toMatch(/TPES|primary/i);
    expect(d!.caveats![1]).toMatch(/conversion|losses|transform/i);
    expect(d!.caveats![1]).toMatch(/coal plant|FINAL|end-use|electricity/i);
    // 3: mtoe is an analyst unit; kWh/MWh anchor.
    expect(d!.caveats![2]).toMatch(/mtoe/i);
    expect(d!.caveats![2]).toMatch(/analyst|citizen/i);
    expect(d!.caveats![2]).toMatch(/kWh|MWh|billion/i);
  });

  // PR-V (Row 6 P.1.C 6/9, 2026-05-26): state plant load factor by fuel
  // lift. Third Pattern A-facet in the P.1.C cohort, on the EXISTING
  // `fuel_type` axis. UNLIKE every other facet-multiplexed indicator,
  // PR-V does NOT use SUB_FUEL_TO_CANONICAL collapse -- PLF is a
  // percentage that cannot be summed across fuels. 8 publisher labels
  // map 1:1 to existing fuel_type axis values via a dedicated mapping
  // dict. Joins the `energy_generation` parquet stem.
  it("PR-V state_plant_load_factor_pct descriptor routes to facet-multiplexed parent", () => {
    const d = getCanonicalDescriptor("energy/state_plant_load_factor_pct");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("plant-load-factor-pct");
      expect(d!.facet_axis_id).toBe("fuel_type");
      // Exactly 8 children on the canonical fuel_type axis (NO sub-fuel
      // collapse; publisher's 8 labels map 1:1 to 8 distinct axis values).
      expect(d!.facet_values.length).toBe(8);
      const childIds = d!.facet_values.map((fv) => fv.canonical_child_id).sort();
      expect(childIds).toEqual([
        "plant-load-factor-pct-biomass",
        "plant-load-factor-pct-coal",
        "plant-load-factor-pct-gas",
        "plant-load-factor-pct-hydro",
        "plant-load-factor-pct-nuclear",
        "plant-load-factor-pct-small-hydro",
        "plant-load-factor-pct-solar",
        "plant-load-factor-pct-wind",
      ]);
      // Publisher `bio-power` collapses to canonical `biomass`;
      // `oil-gas` collapses to canonical `gas`; `small-hydro` retains
      // its kebab form for the indicator-id suffix but uses the
      // `small_hydro` axis value_id in dimension_values.
      const labels = d!.facet_values.map((fv) => fv.legacy_facet_label).sort();
      expect(labels).not.toContain("bio-power");
      expect(labels).not.toContain("oil-gas");
      expect(labels).toContain("biomass");
      expect(labels).toContain("gas");
      expect(labels).toContain("small_hydro");
    }
    expect(d!.table_id).toBe("energy.energy_generation");
    expect(d!.meta.title).toMatch(/plant load factor|PLF/i);
    expect(d!.meta.unit).toBe("percent");
    expect(d!.meta.short_unit).toBe("%");
    expect(d!.meta.entity_kind).toBe("state");
    expect(d!.meta.time_grain).toBe("fiscal_year");
    expect(d!.meta.direction).toBe("neutral");
    expect(d!.meta.attribution_geography).toBe("where_produced");
    expect(d!.meta.implementing_authority).toBe("joint");
  });

  it("PR-V plant-load-factor descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_plant_load_factor_pct");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: not-comparable-across-fuels; solar Rajasthan vs coal WB anchor.
    expect(d!.caveats![0]).toMatch(/not comparable across fuels|within a fuel/i);
    expect(d!.caveats![0]).toMatch(/solar|Rajasthan|coal|stranded/i);
    expect(d!.caveats![0]).toMatch(/FacetPicker|do NOT|total/i);
    // 2: resource-bounded, not performance-bounded; wind sites anchor.
    expect(d!.caveats![1]).toMatch(/resource[- ]bounded|RESOURCE-bounded/i);
    expect(d!.caveats![1]).toMatch(/sunlight|wind|Tamil Nadu|Gujarat|Karnataka/i);
    expect(d!.caveats![1]).toMatch(/hydro|drought|monsoon|inter-year/i);
    // 3: empty cells + outliers are real; nuclear states + gas allocation anchor.
    expect(d!.caveats![2]).toMatch(/empty|extreme|outlier/i);
    expect(d!.caveats![2]).toMatch(/Nuclear|reactor|TN|KA|RJ|GJ/i);
    expect(d!.caveats![2]).toMatch(/gas[- ]allocation|100%|anomaly|upstream/i);
  });

  // PR-W (Row 6 P.1.C 7/9, 2026-05-26): state power-purchase share by source.
  // Fourth Pattern A-facet; 12 children on EXISTING fuel_type axis extended
  // with hybrid_bundled + trading_other. NO sub-fuel collapse (percentage
  // values cannot be summed across sources without double-counting).
  it("PR-W state_power_purchase_share_pct descriptor routes to facet-multiplexed parent", () => {
    const d = getCanonicalDescriptor("energy/state_power_purchase_share_pct");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("power-purchase-share-pct");
      expect(d!.facet_axis_id).toBe("fuel_type");
      expect(d!.facet_values.length).toBe(12);
      const childIds = d!.facet_values.map((fv) => fv.canonical_child_id).sort();
      expect(childIds).toEqual([
        "power-purchase-share-pct-biomass",
        "power-purchase-share-pct-coal",
        "power-purchase-share-pct-diesel",
        "power-purchase-share-pct-gas",
        "power-purchase-share-pct-hybrid-bundled",
        "power-purchase-share-pct-hydro",
        "power-purchase-share-pct-nuclear",
        "power-purchase-share-pct-renewable-other",
        "power-purchase-share-pct-small-hydro",
        "power-purchase-share-pct-solar",
        "power-purchase-share-pct-trading-other",
        "power-purchase-share-pct-wind",
      ]);
      const labels = d!.facet_values.map((fv) => fv.legacy_facet_label);
      // Raw publisher labels must NOT appear.
      expect(labels).not.toContain("bio-power");
      expect(labels).not.toContain("oil-gas");
      expect(labels).not.toContain("other-res");
      expect(labels).not.toContain("trading-and-others");
      // Canonical labels MUST appear.
      expect(labels).toContain("biomass");
      expect(labels).toContain("gas");
      expect(labels).toContain("renewable_other");
      expect(labels).toContain("hybrid_bundled");
      expect(labels).toContain("trading_other");
    }
    expect(d!.table_id).toBe("energy.energy_demand_supply");
    expect(d!.meta.title).toMatch(/power.?purchase|procurement/i);
    expect(d!.meta.unit).toBe("percent");
    expect(d!.meta.entity_kind).toBe("state");
    expect(d!.meta.time_grain).toBe("fiscal_year");
    expect(d!.meta.attribution_geography).toBe("where_consumed");
    expect(d!.meta.implementing_authority).toBe("state");
  });

  it("PR-W power-purchase-share descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_power_purchase_share_pct");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: procurement vs generation; Karnataka / Bihar anchor.
    expect(d!.caveats![0]).toMatch(/procurement.*generation|generation.*procurement/i);
    expect(d!.caveats![0]).toMatch(/DISCOM|BUY|buy/i);
    expect(d!.caveats![0]).toMatch(/Karnataka|Bihar|import|export/i);
    // 2: hybrid is a contract category, not a fuel.
    expect(d!.caveats![1]).toMatch(/hybrid/i);
    expect(d!.caveats![1]).toMatch(/contract|CONTRACT|MNRE|PPA/i);
    expect(d!.caveats![1]).toMatch(/re-?categor|same electrons|installed-capacity/i);
    // 3: trading share is not a stress signal.
    expect(d!.caveats![2]).toMatch(/trading/i);
    expect(d!.caveats![2]).toMatch(/IEX|PXIL|exchange|UI/i);
    expect(d!.caveats![2]).toMatch(/Punjab|Haryana|Delhi|peaky|competence|crisis/i);
  });

  // PR-X (Row 6 P.1.C 8/9, 2026-05-26): national final-energy consumption
  // by sector x fuel composite. Fifth Pattern A-facet; 18 sparse children
  // on NEW sector_fuel_pair axis. Publisher 'agriculture | oil' ->
  // canonical 'agriculture-oil'. National-only (entity_kind=country).
  it("PR-X national_final_energy_consumption_by_sector_mtoe descriptor routes to facet-multiplexed parent", () => {
    const d = getCanonicalDescriptor("energy/national_final_energy_consumption_by_sector_mtoe");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("facet-multiplexed");
    if (d!.kind === "facet-multiplexed") {
      expect(d!.canonical_parent_indicator_id).toBe("india-final-energy-consumption-mtoe");
      expect(d!.facet_axis_id).toBe("sector_fuel_pair");
      expect(d!.facet_values.length).toBe(18);
      const childIds = d!.facet_values.map((fv) => fv.canonical_child_id);
      // Spot-check the 4 most volume-significant pairs.
      expect(childIds).toContain("india-final-energy-consumption-mtoe-industry-coal");
      expect(childIds).toContain("india-final-energy-consumption-mtoe-industry-oil");
      expect(childIds).toContain("india-final-energy-consumption-mtoe-transport-oil");
      expect(childIds).toContain("india-final-energy-consumption-mtoe-residential-electricity");
      // Absent pairs MUST NOT appear (publisher does not emit them).
      expect(childIds).not.toContain("india-final-energy-consumption-mtoe-residential-coal");
      expect(childIds).not.toContain("india-final-energy-consumption-mtoe-transport-gas");
      // Raw publisher labels (pipe-separated) must NOT appear in legacy_facet_label.
      const labels = d!.facet_values.map((fv) => fv.legacy_facet_label);
      for (const l of labels) {
        expect(l).not.toContain(" | ");
        expect(l).not.toContain(" ");
      }
    }
    expect(d!.table_id).toBe("energy.energy_demand_supply");
    expect(d!.meta.title).toMatch(/final energy consumption/i);
    expect(d!.meta.unit).toBe("mtoe");
    expect(d!.meta.entity_kind).toBe("country");
    expect(d!.meta.time_grain).toBe("fiscal_year");
    expect(d!.meta.attribution_geography).toBe("where_consumed");
  });

  it("PR-X final-energy-consumption descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/national_final_energy_consumption_by_sector_mtoe");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: FINAL vs PRIMARY distinction; conversion losses anchor.
    expect(d!.caveats![0]).toMatch(/FINAL|PRIMARY|primary|final/i);
    expect(d!.caveats![0]).toMatch(/TPES|primary supply|consumption/i);
    expect(d!.caveats![0]).toMatch(/conversion|losses|transformation/i);
    // 2: sparse pairs are not zero.
    expect(d!.caveats![1]).toMatch(/sparse|absent|missing|NOT zero|not.*zero/i);
    expect(d!.caveats![1]).toMatch(/18|residential|transport|publisher/i);
    expect(d!.caveats![1]).toMatch(/impute|fake|honest|gap/i);
    // 3: sector names are MoSPI taxonomy.
    expect(d!.caveats![2]).toMatch(/MoSPI|taxonomy|publisher|naming/i);
    expect(d!.caveats![2]).toMatch(/non-?energy|CGD|feedstock|fertiliser/i);
    expect(d!.caveats![2]).toMatch(/citizen|renderer|re-?label/i);
  });

  // PR-Y (Row 6 P.1.C 9/9 -- FINAL, state renewable grid capacity, 2026-05-26):
  // RBI Handbook Table 143 single-source 18-year longitudinal series.
  // Pattern A-SINGLE (scalar; no facet axis).
  it("PR-Y state_renewable_grid_capacity_mw descriptor routes to single canonical indicator", () => {
    const d = getCanonicalDescriptor("energy/state_renewable_grid_capacity_mw");
    expect(d).not.toBeNull();
    expect(d!.kind).toBe("single");
    if (d!.kind === "single") {
      expect(d!.canonical_indicator_id).toBe("renewable-grid-capacity-mw");
    }
    expect(d!.table_id).toBe("energy.energy_installed_capacity");
    expect(d!.meta.title).toMatch(/renewable.*capacity|grid-connected renewable/i);
    expect(d!.meta.unit).toBe("MW");
    expect(d!.meta.entity_kind).toBe("state");
    expect(d!.meta.direction).toBe("higher_is_better");
    expect(d!.meta.attribution_geography).toBe("where_administered");
    expect(d!.meta.icon).toBe("sun");
  });

  it("PR-Y renewable-grid-capacity descriptor carries the 3 Hans-curated caveats", () => {
    const d = getCanonicalDescriptor("energy/state_renewable_grid_capacity_mw");
    expect(d).not.toBeNull();
    expect(d!.caveats).toBeDefined();
    expect(d!.caveats!.length).toBe(3);
    // 1: combined RE -- no per-source split.
    expect(d!.caveats![0]).toMatch(/combined|no per-source|lumps/i);
    expect(d!.caveats![0]).toMatch(/wind|solar|small-?hydro|biomass/i);
    expect(d!.caveats![0]).toMatch(/PR-Q|PR-R|cross-reference|deep history|2007/i);
    // 2: installed capacity is not energy delivered.
    expect(d!.caveats![1]).toMatch(/installed|capacity/i);
    expect(d!.caveats![1]).toMatch(/NOT.*energy|not.*delivered|plant load factor|PLF/i);
    expect(d!.caveats![1]).toMatch(/coal plant|generation|MW|flowing/i);
    // 3: end-March snapshot vs FY flow.
    expect(d!.caveats![2]).toMatch(/end-?March|snapshot|STOCK|stock/i);
    expect(d!.caveats![2]).toMatch(/cumulative|annual|flow|difference/i);
    expect(d!.caveats![2]).toMatch(/MoSPI|RBI|restate|revision/i);
  });
});

describe("PR 7a — additive reader-switch for 8 energy descriptors", () => {
  // Registry-shape invariants for every PR 7a descriptor. Per CLAUDE.md §15
  // these are CONTRACT tests: they assert the allowlist's published surface
  // (legacy slug → canonical indicator id + table_id + meta) matches the
  // expected wiring for each of the 8 shards reader-switched in this PR.
  // Catches accidental future edits to the wrong row or a typo'd table_id
  // (which would silently fall through to legacy fetch and 404 once Phase D
  // git-rm's the underlying shard).

  const PR_7A: ReadonlyArray<{
    legacy_id: string;
    canonical_id: string;
    table_id: string;
  }> = [
    {
      legacy_id: "energy/installed_capacity_coal_mw",
      canonical_id: "installed-capacity-snapshot-mw-coal",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_gas_mw",
      canonical_id: "installed-capacity-snapshot-mw-gas",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_hydro_mw",
      canonical_id: "installed-capacity-snapshot-mw-hydro",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_nuclear_mw",
      canonical_id: "installed-capacity-snapshot-mw-nuclear",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/installed_capacity_renewable_mw",
      canonical_id: "installed-capacity-snapshot-mw-renewable",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/state_installed_capacity_geographical_mw",
      canonical_id: "installed-capacity-geographical-mw",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/state_installed_capacity_with_alloc_mw",
      canonical_id: "installed-capacity-allocated-mw",
      table_id: "energy.energy_installed_capacity",
    },
    {
      legacy_id: "energy/state_electricity_generation_mu",
      canonical_id: "electricity-generation-gwh",
      table_id: "energy.energy_generation",
    },
  ];

  it("registers all 8 PR 7a descriptors as canonical-backed", () => {
    for (const row of PR_7A) {
      expect(isCanonicalBacked(row.legacy_id)).toBe(true);
    }
  });

  it("wires every PR 7a legacy slug to the expected canonical id + table", () => {
    for (const row of PR_7A) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d, `descriptor missing for ${row.legacy_id}`).not.toBeNull();
      // PR 7a entries are all kind:"single" — narrow before accessing the
      // single-variant canonical_indicator_id field.
      expect(d!.kind, `descriptor for ${row.legacy_id} must be kind:single`).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id).toBe(row.canonical_id);
      }
      expect(d!.table_id).toBe(row.table_id);
    }
  });

  it("every PR 7a meta block declares entity_kind=state + unit=MW|GWh", () => {
    for (const row of PR_7A) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.id).toBe(row.canonical_id);
      expect(d.meta.entity_kind).toBe("state");
      expect(["MW", "GWh"]).toContain(d.meta.unit);
      // Title must be non-empty (rail-budget compliance is asserted by
      // topic-titles-rail-fit elsewhere; here we only require presence).
      expect(d.meta.title.length).toBeGreaterThan(0);
    }
  });

  it("snapshot-fuel descriptors (#1-#5) carry time_grain=month + comparability=snapshot_only", () => {
    const snapshot_ids = PR_7A.filter((r) =>
      r.canonical_id.startsWith("installed-capacity-snapshot-mw-"),
    );
    expect(snapshot_ids).toHaveLength(5);
    for (const row of snapshot_ids) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.time_grain).toBe("month");
      expect(d.meta.comparability).toBe("comparable_across_states_snapshot_only");
      expect(d.meta.attribution_geography).toBe("where_allocated");
    }
  });

  it("time-series descriptors (#6-#8) carry time_grain=fiscal_year + comparability=across_states_and_time", () => {
    const fy_ids = PR_7A.filter((r) =>
      [
        "installed-capacity-geographical-mw",
        "installed-capacity-allocated-mw",
        "electricity-generation-gwh",
      ].includes(r.canonical_id),
    );
    expect(fy_ids).toHaveLength(3);
    for (const row of fy_ids) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.comparability).toBe("comparable_across_states_and_time");
    }
  });

  it("allocated-shares descriptor (#7) declares FY15 series_break for the RBI splice", () => {
    const d = getCanonicalDescriptor("energy/state_installed_capacity_with_alloc_mw")!;
    expect(d.meta.series_breaks).toBeDefined();
    expect(d.meta.series_breaks!.length).toBeGreaterThanOrEqual(1);
    const fy15 = d.meta.series_breaks!.find((b) => b.at_time === "2015-04");
    expect(fy15, "FY15 series_break missing").toBeDefined();
    expect(fy15!.kind).toBe("definition_change");
    expect(fy15!.note).toMatch(/RBI/i);
  });

  it("generation descriptor (#8) keeps GWh unit (NOT MU) per ADR-0030 unit normalisation", () => {
    const d = getCanonicalDescriptor("energy/state_electricity_generation_mu")!;
    expect(d.meta.unit).toBe("GWh");
    expect(d.meta.notes).toMatch(/MU/);
  });

  it("every PR 7a legacy_id is a distinct entry in CANONICAL_BACKED_INDICATORS (no duplicates)", () => {
    const slugs = CANONICAL_BACKED_INDICATORS.map((d) => d.legacy_artifact_id);
    const uniq = new Set(slugs);
    expect(uniq.size).toBe(slugs.length);
    // And: every PR 7a slug is present at least once.
    for (const row of PR_7A) {
      expect(slugs).toContain(row.legacy_id);
    }
  });
});

describe("canonicalEntityToLegacy — entity-id translation", () => {
  it("strips IN- prefix from state ids", () => {
    expect(canonicalEntityToLegacy("IN-S22")).toBe("S22");
    expect(canonicalEntityToLegacy("IN-U08")).toBe("U08");
    expect(canonicalEntityToLegacy("IN-S01")).toBe("S01");
  });

  it("passes bare IN national aggregate through unchanged", () => {
    expect(canonicalEntityToLegacy("IN")).toBe("IN");
  });

  it("passes already-bare ECI codes through unchanged", () => {
    // Defensive — should never happen on canonical input, but the helper
    // must be idempotent so a double-call is harmless.
    expect(canonicalEntityToLegacy("S22")).toBe("S22");
  });

  it("passes unrecognised shapes through (no throw)", () => {
    expect(canonicalEntityToLegacy("foo")).toBe("foo");
    expect(canonicalEntityToLegacy("")).toBe("");
  });

  // PR B.02 — district-grain entity_id translation. The legacy district
  // code form is `S<n>-D<lgd>` / `U<n>-D<lgd>`; the canonical form
  // prepends `IN-`. `slice(3)` handles the longer shape natively (no
  // code change vs PR B.01); these contract tests lock the behaviour so
  // PR B.03's first district allowlist entry can rely on it.
  it("strips IN- prefix from district ids (state-parent)", () => {
    expect(canonicalEntityToLegacy("IN-S03-D280")).toBe("S03-D280");
    expect(canonicalEntityToLegacy("IN-S22-D640")).toBe("S22-D640");
  });

  it("strips IN- prefix from district ids (UT-parent)", () => {
    expect(canonicalEntityToLegacy("IN-U05-D640")).toBe("U05-D640");
    expect(canonicalEntityToLegacy("IN-U07-D003")).toBe("U07-D003");
  });
});

describe("entityKindToAdminLevel — PR B.02 dispatch helper", () => {
  // The single seam mapping canonical `IndicatorMeta.entity_kind`
  // (typed union: country | state | district | subdistrict |
  // constituency | city | ward) onto the legacy
  // `IndicatorCoverage.admin_level` string consumed by AboutThisData
  // and the choropleth boundary picker. Per ADR-0043 sub-state-grain
  // adapters now emit BOTH grains (district SoT + state SUM rollup);
  // each grain reaches the renderer through its own allowlist
  // descriptor whose `meta.entity_kind` decides `admin_level` via this
  // helper.

  it("maps state -> 'state' (preserves legacy state-grain behaviour)", () => {
    expect(entityKindToAdminLevel("state")).toBe("state");
  });

  it("maps district -> 'district' (B.03 first district descriptor lands here)", () => {
    expect(entityKindToAdminLevel("district")).toBe("district");
  });

  it("maps country -> 'country' (matches legacy national_*.json admin_level)", () => {
    expect(entityKindToAdminLevel("country")).toBe("country");
  });

  it("maps subdistrict -> 'subdistrict' (future grain, no surface yet)", () => {
    expect(entityKindToAdminLevel("subdistrict")).toBe("subdistrict");
  });

  it("returns null for constituency / city / ward (no boundary surface yet)", () => {
    expect(entityKindToAdminLevel("constituency")).toBeNull();
    expect(entityKindToAdminLevel("city")).toBeNull();
    expect(entityKindToAdminLevel("ward")).toBeNull();
  });

  it("returns null for undefined input (defensive — descriptor missing meta)", () => {
    expect(entityKindToAdminLevel(undefined)).toBeNull();
  });

  // Load-bearing contract test: every CANONICAL_BACKED_INDICATORS
  // descriptor MUST round-trip through the dispatch helper consistently
  // with the artifact built by buildIndicatorArtifact. Catches the
  // regression class where a new descriptor ships with
  // `entity_kind: "district"` while buildIndicatorArtifact hard-codes
  // `"state"` (the exact PR B.01-shaped trap this helper retires).
  it("every CANONICAL_BACKED_INDICATORS descriptor passes through the dispatch consistently", () => {
    for (const d of CANONICAL_BACKED_INDICATORS) {
      const built = buildIndicatorArtifact(d, [], []);
      expect(built.coverage.admin_level).toBe(entityKindToAdminLevel(d.meta.entity_kind));
    }
  });
});

// Cattle cohort PR (Row 5 PR-P cohort 2/3, 2026-05-27): district-grain cattle
// descriptor shipped alongside its state-grain sibling; re-enabling the B.03
// district smoke describe which targets the cattle district descriptor.
describe("buildIndicatorArtifact — district-grain (PR B.03 smoke proof)", () => {
  // PR B.03 (2026-05-25) — end-to-end smoke proof of the B.01
  // (ADR-0043 auto-rollup writer) + B.02 (entityKindToAdminLevel
  // dispatch helper) pipeline against the first district-grain
  // allowlist entry. Verifies:
  //  - The dispatch helper translates `entity_kind: "district"` to
  //    `admin_level: "district"` for a REAL allowlist descriptor
  //    (not a synthesised one in a unit test).
  //  - `canonicalEntityToLegacy` strips `IN-` from real district id
  //    shapes (state-parent `IN-S03-D280` -> `S03-D280` and UT-parent
  //    `IN-U05-D640` -> `U05-D640`).
  //  - The legacy `IndicatorArtifact` carries one row per
  //    (district, period) with `value_numeric` mapped to `value` and
  //    `period_label` mapped to `time`.
  //  - The descriptor is NOT a state-grain duplicate of the existing
  //    `state-pashu-aadhaar-count-cattle` — same canonical fact-table
  //    but different `indicator_id` and different `entity_kind`.
  const DISTRICT_CATTLE_DESCRIPTOR: CanonicalIndicatorDescriptor =
    getCanonicalDescriptor("agriculture/district_pashu_aadhaar_count_cattle")!;

  // Real-shape district obs rows from livestock_pashu_aadhaar.parquet
  // (Karnataka district 280 + UT district 640 + state-parent district
  // 7 for shape coverage). Values are illustrative; the lift contract
  // is tested separately in backend/tests/test_livestock_pashu_aadhaar_lift.py.
  const DISTRICT_OBS_ROWS = [
    {
      entity_id: "IN-S03-D280",
      period_label: "2024-04",
      value_numeric: 12345,
      source_id: "src-7e5d4aac4995",
    },
    {
      entity_id: "IN-S03-D281",
      period_label: "2024-04",
      value_numeric: 9876,
      source_id: "src-7e5d4aac4995",
    },
    {
      entity_id: "IN-U05-D640",
      period_label: "2024-04",
      value_numeric: 543,
      source_id: "src-7e5d4aac4995",
    },
  ];
  const NDLM_SRC_ROW = [
    {
      source_id: "src-7e5d4aac4995",
      producer: "Department of Animal Husbandry & Dairying",
      title: "NDLM Bharat Pashudhan — animal registration",
      vintage: "FY 2024-25",
      url_main: "https://bpa.dahd.gov.in/",
    },
  ];

  it("descriptor exists in the allowlist with district entity_kind", () => {
    expect(DISTRICT_CATTLE_DESCRIPTOR).toBeDefined();
    expect(DISTRICT_CATTLE_DESCRIPTOR.kind).toBe("single");
    if (DISTRICT_CATTLE_DESCRIPTOR.kind === "single") {
      expect(DISTRICT_CATTLE_DESCRIPTOR.canonical_indicator_id).toBe(
        "district-pashu-aadhaar-count-cattle",
      );
    }
    expect(DISTRICT_CATTLE_DESCRIPTOR.table_id).toBe("livestock.livestock_pashu_aadhaar");
    expect(DISTRICT_CATTLE_DESCRIPTOR.meta.entity_kind).toBe("district");
  });

  it("buildIndicatorArtifact emits admin_level='district' (B.02 dispatch end-to-end)", () => {
    const a = buildIndicatorArtifact(DISTRICT_CATTLE_DESCRIPTOR, DISTRICT_OBS_ROWS, NDLM_SRC_ROW);
    expect(a.coverage.admin_level).toBe("district");
    // Helper output MUST equal the artifact's admin_level for this
    // real district descriptor — that's the B.02 contract surface.
    expect(a.coverage.admin_level).toBe(
      entityKindToAdminLevel(DISTRICT_CATTLE_DESCRIPTOR.meta.entity_kind),
    );
  });

  it("strips IN- from district entity_ids (state-parent and UT-parent shapes)", () => {
    const a = buildIndicatorArtifact(DISTRICT_CATTLE_DESCRIPTOR, DISTRICT_OBS_ROWS, NDLM_SRC_ROW);
    const entities = new Set(a.rows.map((r) => r.entity_id));
    expect(entities.has("S03-D280")).toBe(true);
    expect(entities.has("S03-D281")).toBe(true);
    expect(entities.has("U05-D640")).toBe(true);
    // Originals MUST be gone (no IN- prefix leak).
    expect(entities.has("IN-S03-D280")).toBe(false);
    expect(entities.has("IN-U05-D640")).toBe(false);
  });

  it("maps period_label -> time and value_numeric -> value for district rows", () => {
    const a = buildIndicatorArtifact(DISTRICT_CATTLE_DESCRIPTOR, DISTRICT_OBS_ROWS, NDLM_SRC_ROW);
    const district_280 = a.rows.find((r) => r.entity_id === "S03-D280" && r.time === "2024-04");
    expect(district_280?.value).toBe(12345);
    const ut_district = a.rows.find((r) => r.entity_id === "U05-D640" && r.time === "2024-04");
    expect(ut_district?.value).toBe(543);
  });

  it("does NOT duplicate the state-grain sibling descriptor (distinct indicator_id, same table)", () => {
    const state_d = getCanonicalDescriptor("agriculture/state_pashu_aadhaar_count_cattle")!;
    expect(state_d.kind).toBe("single");
    if (state_d.kind === "single" && DISTRICT_CATTLE_DESCRIPTOR.kind === "single") {
      // Same fact-table — the auto-rollup writer (ADR-0043) ships
      // both grains in a single parquet via different indicator_ids.
      expect(state_d.table_id).toBe(DISTRICT_CATTLE_DESCRIPTOR.table_id);
      // Distinct indicator_id (the grain prefix differs).
      expect(state_d.canonical_indicator_id).not.toBe(
        DISTRICT_CATTLE_DESCRIPTOR.canonical_indicator_id,
      );
      // Distinct entity_kind (the dispatch contract).
      expect(state_d.meta.entity_kind).toBe("state");
      expect(DISTRICT_CATTLE_DESCRIPTOR.meta.entity_kind).toBe("district");
    }
  });
});

describe("buildIndicatorArtifact — canonical rows → legacy IndicatorArtifact", () => {
  const OBS_ROWS = [
    { entity_id: "IN", period_label: "2013-04", value_numeric: 135453, source_id: "src-rbi" },
    { entity_id: "IN", period_label: "2024-04", value_numeric: 250070, source_id: "src-rbi" },
    { entity_id: "IN", period_label: "2025-04", value_numeric: 245416, source_id: "src-iced" },
    { entity_id: "IN-S22", period_label: "2013-04", value_numeric: 13522, source_id: "src-rbi" },
    { entity_id: "IN-S22", period_label: "2024-04", value_numeric: 20211, source_id: "src-rbi" },
    { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
  ];
  const SRC_ROWS = [
    {
      source_id: "src-iced",
      producer: "NITI Aayog",
      title: "India Climate & Energy Dashboard",
      vintage: "FY 2024-25",
      url_main: "https://iced.niti.gov.in/",
    },
    {
      source_id: "src-rbi",
      producer: "Reserve Bank of India",
      title: "Handbook of Statistics on Indian States",
      vintage: "2024-25",
      url_main: "https://rbi.org.in/handbook",
    },
  ];

  it("maps canonical entity_ids to legacy form (strips IN-)", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    const entities = new Set(a.rows.map((r) => r.entity_id));
    expect(entities.has("IN")).toBe(true);
    expect(entities.has("S22")).toBe(true);
    expect(entities.has("IN-S22")).toBe(false);
  });

  it("maps period_label → time and value_numeric → value", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    const tn_2025 = a.rows.find((r) => r.entity_id === "S22" && r.time === "2025-04");
    expect(tn_2025?.value).toBe(20211);
  });

  it("derives coverage.temporal from min/max time across rows", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.coverage.temporal).toBe("2013-04 to 2025-04");
    expect(a.coverage.admin_level).toBe("state");
  });

  it("collapses to a single period when all rows share the same time", () => {
    const single = OBS_ROWS.filter((r) => r.period_label === "2025-04");
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, single, SRC_ROWS);
    expect(a.coverage.temporal).toBe("2025-04");
  });

  it("emits one IndicatorSource per joined source row, with empty fetched_at", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.sources).toHaveLength(2);
    const titles = a.sources.map((s) => s.name);
    expect(titles).toContain("India Climate & Energy Dashboard (FY 2024-25)");
    expect(titles).toContain("Handbook of Statistics on Indian States (2024-25)");
    for (const s of a.sources) {
      expect(s.fetched_at).toBe("");
      expect(typeof s.url).toBe("string");
    }
  });

  it("passes the descriptor's IndicatorMeta block through verbatim", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.indicator).toBe(PEAK_DEMAND_DESCRIPTOR.meta);
  });

  it("synthesises a stub methodology block compatible with AboutThisData", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.methodology).toBeDefined();
    expect(a.methodology!.documentation_status).toBe("stub");
    expect(a.methodology!.definition.length).toBeGreaterThan(0);
    expect(a.methodology!.publisher_methodology_url).toBeNull();
    expect(a.methodology!.methodology_breaks).toEqual([]);
  });

  // PR-E (AboutThisData RPO caveat surfacing): `descriptor.caveats` is the
  // allowlist-authored bullet list lifted into `methodology.known_caveats[]`
  // so AboutThisData.svelte's "Known caveats" section can render it.
  // Descriptors without `caveats` populated keep the legacy empty-array
  // behaviour (no surface change for the ~30 non-caveat-carrying entries).
  it("emits an empty known_caveats array when the descriptor declares no caveats", () => {
    // PR-H (2026-05-25): swapped from PEAK_DEMAND_DESCRIPTOR to
    // NO_CAVEATS_DESCRIPTOR (= peak-electricity-supplied-mw)
    // because PEAK_DEMAND now carries Hans-curated caveats[]. The
    // "no-caveats default → empty array" invariant is unchanged; only
    // the canary descriptor moved.
    expect(NO_CAVEATS_DESCRIPTOR.caveats).toBeUndefined();
    const a = buildIndicatorArtifact(NO_CAVEATS_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.methodology!.known_caveats).toEqual([]);
  });

  it("copies descriptor.caveats verbatim into methodology.known_caveats", () => {
    const with_caveats: CanonicalIndicatorDescriptor = {
      ...PEAK_DEMAND_DESCRIPTOR,
      caveats: [
        "First caveat — top of the bullet list.",
        "Second caveat — preserves declaration order.",
      ],
    } as CanonicalIndicatorDescriptor;
    const a = buildIndicatorArtifact(with_caveats, OBS_ROWS, SRC_ROWS);
    expect(a.methodology!.known_caveats).toEqual([
      "First caveat — top of the bullet list.",
      "Second caveat — preserves declaration order.",
    ]);
  });

  it("treats descriptor.caveats as defensive-copy (mutating the artifact does not back-mutate the descriptor)", () => {
    const original_caveats = ["caveat A", "caveat B"];
    const with_caveats: CanonicalIndicatorDescriptor = {
      ...PEAK_DEMAND_DESCRIPTOR,
      caveats: original_caveats,
    } as CanonicalIndicatorDescriptor;
    const a = buildIndicatorArtifact(with_caveats, OBS_ROWS, SRC_ROWS);
    a.methodology!.known_caveats.push("post-build mutation");
    expect(original_caveats).toEqual(["caveat A", "caveat B"]);
  });

  it("declares schema v4.4 + OGL-IN-1.0 license", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, OBS_ROWS, SRC_ROWS);
    expect(a.$schema_version).toBe("4.4");
    expect(a.license.id).toBe("OGL-IN-1.0");
    expect(a.license.redistributable).toBe(true);
  });

  it("handles an empty result set without throwing", () => {
    const a = buildIndicatorArtifact(PEAK_DEMAND_DESCRIPTOR, [], []);
    expect(a.rows).toEqual([]);
    expect(a.sources).toEqual([]);
    expect(a.coverage.temporal).toBe("");
  });
});

describe("loadIndicatorFromCanonical — DuckDB-WASM round-trip (loader)", () => {
  it("registers the fact-table and sources table before querying", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    const registered = mockedRegister.mock.calls.map((c) => c[0]);
    expect(registered).toContain("energy.energy_demand_supply");
    expect(registered).toContain("taxonomy.sources");
  });

  it("queries the fact-table view (last segment of table_id) filtered by indicator_id", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    const firstSql = mockedQuery.mock.calls[0][0] as string;
    expect(firstSql).toMatch(/FROM\s+energy_demand_supply/);
    expect(firstSql).toMatch(/indicator_id\s*=\s*'peak-electricity-demand-mw'/);
  });

  it("returns an empty artifact when the fact-table has no rows for this indicator", async () => {
    mockedQuery.mockResolvedValueOnce([]); // observation query
    const out = await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    expect(out.rows).toEqual([]);
    expect(out.sources).toEqual([]);
    // Second (sources) query is SKIPPED when there are no source_ids to look up.
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("issues the sources query when observation rows reference at least one source_id", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
      ])
      .mockResolvedValueOnce([
        { source_id: "src-iced", producer: "NITI", title: "ICED", vintage: "FY25", url_main: "https://example/" },
      ]);
    const out = await loadIndicatorFromCanonical(PEAK_DEMAND_DESCRIPTOR);
    expect(mockedQuery).toHaveBeenCalledTimes(2);
    const secondSql = mockedQuery.mock.calls[1][0] as string;
    expect(secondSql).toMatch(/FROM\s+sources/);
    expect(secondSql).toMatch(/'src-iced'/);
    expect(out.sources).toHaveLength(1);
    expect(out.rows[0].entity_id).toBe("S22");
  });
});

describe("loadIndicatorIfCanonical — single dispatch entry-point", () => {
  it("returns null for legacy-backed artifacts (caller falls back to fetch)", async () => {
    const out = await loadIndicatorIfCanonical("energy/some_legacy_shard");
    expect(out).toBeNull();
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegister).not.toHaveBeenCalled();
  });

  it("returns the canonical artifact for an allowlisted id", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
      ])
      .mockResolvedValueOnce([
        { source_id: "src-iced", producer: "NITI", title: "ICED", vintage: "FY25", url_main: "https://example/" },
      ]);
    const out = await loadIndicatorIfCanonical("energy/state_peak_electricity_demand_mw");
    expect(out).not.toBeNull();
    expect(out!.indicator.id).toBe("peak-electricity-demand-mw");
    expect(out!.rows[0].entity_id).toBe("S22");
  });
});

describe("legacyArtifactIdFromPath — DATA_BASE path → catalogue artifact id", () => {
  it("extracts <topic>/<id> from a well-formed legacy path", () => {
    expect(legacyArtifactIdFromPath("/indicators/in/energy/state_peak_electricity_demand_mw.json"))
      .toBe("energy/state_peak_electricity_demand_mw");
    expect(legacyArtifactIdFromPath("/indicators/in/demography/state_population_lakhs.json"))
      .toBe("demography/state_population_lakhs");
  });

  it("returns the empty string for paths outside the indicators tree", () => {
    expect(legacyArtifactIdFromPath("/data/indicators/in/energy/foo.json")).toBe("");
    expect(legacyArtifactIdFromPath("/indicators/us/energy/foo.json")).toBe("");
    expect(legacyArtifactIdFromPath("/indicators/in/energy/foo.csv")).toBe("");
    expect(legacyArtifactIdFromPath("")).toBe("");
    expect(legacyArtifactIdFromPath("nonsense")).toBe("");
  });
});

describe("loadIndicator — universal entry-point (Phase B-extension)", () => {
  it("returns the canonical artifact for an allowlisted path (no fetchIndicator call)", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "IN-S22", period_label: "2025-04", value_numeric: 20211, source_id: "src-iced" },
      ])
      .mockResolvedValueOnce([
        { source_id: "src-iced", producer: "NITI", title: "ICED", vintage: "FY25", url_main: "https://example/" },
      ]);
    const out = await loadIndicator("/indicators/in/energy/state_peak_electricity_demand_mw.json");
    expect(out.indicator.id).toBe("peak-electricity-demand-mw");
    expect(out.rows[0].entity_id).toBe("S22");
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("falls through to fetchIndicator for a non-allowlisted legacy path", async () => {
    const legacy: import("../indicators").IndicatorArtifact = {
      $schema_version: "4.4",
      indicator: {
        id: "state-population-lakhs",
        title: "Population (lakhs)",
        unit: "lakhs",
        entity_kind: "state",
        time_grain: "annual",
      } as any,
      coverage: { temporal: "2011" } as any,
      license: { id: "OGL-IN-1.0", redistributable: true } as any,
      methodology: {} as any,
      sources: [],
      rows: [],
    } as any;
    mockedFetch.mockResolvedValueOnce(legacy);
    const out = await loadIndicator("/indicators/in/demography/state_population_lakhs.json");
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(mockedFetch).toHaveBeenCalledWith("/indicators/in/demography/state_population_lakhs.json");
    expect(out).toBe(legacy);
    expect(mockedQuery).not.toHaveBeenCalled();
  });

  it("falls through to fetchIndicator for a path that doesn't match the indicators shape", async () => {
    const legacy: import("../indicators").IndicatorArtifact = { rows: [] } as any;
    mockedFetch.mockResolvedValueOnce(legacy);
    const out = await loadIndicator("/data/elections/in/le/maharashtra/2024-11/results.json");
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(out).toBe(legacy);
  });
});

describe("PR 7c.5 — additive reader-switch for 7 P.1.B simple energy descriptors", () => {
  // Contract tests for the 7 simple `kind: "single"` descriptors wired in
  // PR 7c.5. Same shape as PR 7a invariants — catches accidental future
  // edits to the wrong row or a typo'd table_id.

  const PR_7C5_SIMPLE: ReadonlyArray<{
    legacy_id: string;
    canonical_id: string;
    table_id: string;
  }> = [
    {
      legacy_id: "energy/state_power_requirement_mu",
      canonical_id: "electricity-requirement-mu",
      table_id: "energy.energy_demand_supply",
    },
    {
      legacy_id: "energy/state_power_availability_mu",
      canonical_id: "electricity-availability-mu",
      table_id: "energy.energy_demand_supply",
    },
    {
      legacy_id: "energy/state_per_capita_availability_kwh",
      canonical_id: "per-capita-electricity-availability-kwh",
      table_id: "energy.energy_demand_supply",
    },
    {
      legacy_id: "energy/state_acs_arr_gap_inr_per_kwh",
      canonical_id: "acs-arr-gap-inr-per-kwh",
      table_id: "energy.energy_distribution_performance",
    },
    {
      legacy_id: "energy/state_distribution_billing_efficiency_pct",
      canonical_id: "distribution-efficiency-pct-billing",
      table_id: "energy.energy_distribution_performance",
    },
    {
      legacy_id: "energy/state_distribution_collection_efficiency_pct",
      canonical_id: "distribution-efficiency-pct-collection",
      table_id: "energy.energy_distribution_performance",
    },
    {
      legacy_id: "energy/state_distribution_td_loss_pct",
      canonical_id: "distribution-efficiency-pct-td-loss",
      table_id: "energy.energy_distribution_performance",
    },
  ];

  it("registers all 7 PR 7c.5 simple descriptors as canonical-backed", () => {
    for (const row of PR_7C5_SIMPLE) {
      expect(isCanonicalBacked(row.legacy_id), `not allowlisted: ${row.legacy_id}`).toBe(true);
    }
  });

  it("wires every PR 7c.5 simple slug to the expected canonical id + table (kind:single)", () => {
    for (const row of PR_7C5_SIMPLE) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d, `descriptor missing for ${row.legacy_id}`).not.toBeNull();
      expect(d!.kind, `descriptor for ${row.legacy_id} must be kind:single`).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id).toBe(row.canonical_id);
      }
      expect(d!.table_id).toBe(row.table_id);
    }
  });

  it("every PR 7c.5 simple meta block declares entity_kind=state + a citizen-readable unit", () => {
    for (const row of PR_7C5_SIMPLE) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.id).toBe(row.canonical_id);
      expect(d.meta.entity_kind).toBe("state");
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.attribution_geography).toBe("where_administered");
      expect(d.meta.unit.length).toBeGreaterThan(0);
      expect(d.meta.title.length).toBeGreaterThan(0);
    }
  });

  it("ACS-ARR descriptor flags both sign convention and policy goal in description (Jony)", () => {
    const d = getCanonicalDescriptor("energy/state_acs_arr_gap_inr_per_kwh")!;
    // The brief calls out the sign-convention copy fix: positive = loses
    // money + closed by tariff hike / loss reduction / state subsidy.
    expect(d.meta.description).toMatch(/positive/i);
    expect(d.meta.description).toMatch(/tariff|subsidy|loss reduction/i);
  });
});

describe("PR 7c.5 — RPO compliance facet-multiplexed descriptor", () => {
  // The first kind:"facet-multiplexed" descriptor. Verifies the
  // discriminated-union dispatch, hyphenated legacy facet labels,
  // single-SQL fan-in, and child-sourced provenance.

  const RPO_DESCRIPTOR = getCanonicalDescriptor("energy/state_rpo_compliance_pct")!;

  it("registers the RPO legacy slug as canonical-backed", () => {
    expect(isCanonicalBacked("energy/state_rpo_compliance_pct")).toBe(true);
  });

  it("descriptor is kind:facet-multiplexed with parent + 3 children", () => {
    expect(RPO_DESCRIPTOR.kind).toBe("facet-multiplexed");
    if (RPO_DESCRIPTOR.kind === "facet-multiplexed") {
      expect(RPO_DESCRIPTOR.canonical_parent_indicator_id).toBe("rpo-compliance-pct");
      expect(RPO_DESCRIPTOR.table_id).toBe("energy.energy_distribution_performance");
      expect(RPO_DESCRIPTOR.facet_axis_id).toBe("rpo_segment");
      expect(RPO_DESCRIPTOR.facet_values).toHaveLength(3);
      const child_ids = RPO_DESCRIPTOR.facet_values.map((fv) => fv.canonical_child_id);
      expect(child_ids).toEqual([
        "rpo-compliance-pct-solar",
        "rpo-compliance-pct-non-solar",
        "rpo-compliance-pct-total",
      ]);
    }
  });

  it("uses HYPHENATED legacy facet labels (citizen-readable, NOT snake_case canonical value_id)", () => {
    if (RPO_DESCRIPTOR.kind !== "facet-multiplexed") {
      throw new Error("RPO descriptor must be facet-multiplexed");
    }
    const labels = RPO_DESCRIPTOR.facet_values.map((fv) => fv.legacy_facet_label);
    expect(labels).toEqual(["solar", "non-solar", "total"]);
    // Defensive: explicitly assert non-solar is hyphenated, NOT underscored
    // (the canonical dimension_values.rpo_segment uses "non_solar"; the
    // legacy shard + frontend renderer use "non-solar"). Easy regression
    // to introduce by copy-paste from the catalogue row.
    expect(labels).toContain("non-solar");
    expect(labels).not.toContain("non_solar");
  });

  it("[mandatory] adapter fuses 3 child rows into one artifact with hyphenated facet labels", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        // 3 children × 1 state × 1 FY
        {
          indicator_id: "rpo-compliance-pct-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 95.5,
          source_id: "src-rpo",
        },
        {
          indicator_id: "rpo-compliance-pct-non-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 88.2,
          source_id: "src-rpo",
        },
        {
          indicator_id: "rpo-compliance-pct-total",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 92.1,
          source_id: "src-rpo",
        },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-rpo",
          producer: "NITI Aayog",
          title: "India Climate & Energy Dashboard — RPO",
          vintage: "FY 2024-25",
          url_main: "https://iced.niti.gov.in/",
        },
      ]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    // (1) hyphenated facet label survives end-to-end:
    expect(result.rows.some((r) => r.facet === "non-solar"), "row.facet must be hyphenated 'non-solar'").toBe(true);
    expect(result.rows.some((r) => r.facet === "solar")).toBe(true);
    expect(result.rows.some((r) => r.facet === "total")).toBe(true);
    // No row should accidentally carry the snake-case canonical value_id:
    expect(result.rows.some((r) => r.facet === "non_solar")).toBe(false);
  });

  it("[mandatory] issues ONE SQL with `indicator_id IN (` covering all 3 children", async () => {
    mockedQuery.mockResolvedValueOnce([]); // no observations, sources query is skipped
    await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    // Exactly one query (sources skipped because no source_ids harvested):
    expect(mockedQuery).toHaveBeenCalledTimes(1);
    const sql = mockedQuery.mock.calls[0][0] as string;
    expect(sql).toMatch(/indicator_id\s+IN\s*\(/);
    expect(sql).toMatch(/'rpo-compliance-pct-solar'/);
    expect(sql).toMatch(/'rpo-compliance-pct-non-solar'/);
    expect(sql).toMatch(/'rpo-compliance-pct-total'/);
    expect(sql).toMatch(/FROM\s+energy_distribution_performance/);
  });

  it("[mandatory] aggregates sources from CHILD rows (parent has source_id=null per D29)", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        {
          indicator_id: "rpo-compliance-pct-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 95.5,
          source_id: "src-rpo",
        },
        {
          indicator_id: "rpo-compliance-pct-non-solar",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 88.2,
          source_id: "src-rpo",
        },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-rpo",
          producer: "NITI Aayog",
          title: "ICED RPO",
          vintage: "FY 2024-25",
          url_main: "https://iced.niti.gov.in/",
        },
      ]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    expect(result.sources).toHaveLength(1);
    expect(result.sources[0].name).toBe("ICED RPO (FY 2024-25)");
    // Sources SQL was the second call and queried by harvested child
    // source_ids — not by parent (which has source_id=null and would
    // produce zero rows).
    const sourcesSql = mockedQuery.mock.calls[1][0] as string;
    expect(sourcesSql).toMatch(/'src-rpo'/);
  });

  it("[mandatory] derives coverage.temporal from min/max across ALL fused child rows", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        // Different children cover different FYs — the parent's coverage
        // must be the UNION (min across children → max across children).
        {
          indicator_id: "rpo-compliance-pct-solar",
          entity_id: "IN-S22",
          period_label: "2018-04",
          value_numeric: 70.0,
          source_id: "src-rpo",
        },
        {
          indicator_id: "rpo-compliance-pct-non-solar",
          entity_id: "IN-S22",
          period_label: "2020-04",
          value_numeric: 80.0,
          source_id: "src-rpo",
        },
        {
          indicator_id: "rpo-compliance-pct-total",
          entity_id: "IN-S22",
          period_label: "2024-04",
          value_numeric: 92.0,
          source_id: "src-rpo",
        },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-rpo",
          producer: "NITI",
          title: "ICED",
          vintage: "FY25",
          url_main: "https://example/",
        },
      ]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    expect(result.coverage.temporal).toBe("2018-04 to 2024-04");
  });

  it("artifact's indicator.id is the parent (NOT any child); meta block carries parent fields", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    const result = await loadIndicatorFromCanonical(RPO_DESCRIPTOR);
    expect(result.indicator.id).toBe("rpo-compliance-pct");
    expect(result.indicator.unit).toBe("%");
    expect(result.indicator.entity_kind).toBe("state");
  });

  it("loadIndicatorIfCanonical dispatches the facet-multiplexed slug to the canonical path", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    const out = await loadIndicatorIfCanonical("energy/state_rpo_compliance_pct");
    expect(out).not.toBeNull();
    expect(out!.indicator.id).toBe("rpo-compliance-pct");
  });
});

// TODO(deploy-unblock PR #424): re-enable when state-grain + district-grain
// Pashu Aadhaar descriptors (and Hans-curated caveats) land in the paired follow-up
// PR. Tracked under the Phase D livestock cohort in the grain-rip plan.
describe.skip("PR B.01 — livestock NDLM Pashu Aadhaar state-grain (10 species)", () => {
  // Registry-shape invariants for the 10 state-grain species descriptors
  // shipped by PR B.01. Per ADR-0043 the canonical writer auto-emits
  // `state-pashu-aadhaar-count-<species>` SUM-rollup rows alongside the
  // source-of-truth district rows; this PR wires those state rows through
  // the existing state-pipeline frontend (entity_kind: "state",
  // canonical_entity → "S<n>" / "U<n>" via the same canonicalEntityToLegacy
  // helper as every other state-grain canonical indicator).
  //
  // District-grain wiring follows in PR B.02 (entityKindToAdminLevel
  // dispatch helper, district code support in canonicalEntityToLegacy) +
  // PR B.03 (first district allowlist entry).

  const PR_B01: ReadonlyArray<{
    legacy_id: string;
    canonical_id: string;
    species: string;
  }> = [
    { legacy_id: "agriculture/state_pashu_aadhaar_count_cattle",  canonical_id: "state-pashu-aadhaar-count-cattle",  species: "cattle"  },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_buffalo", canonical_id: "state-pashu-aadhaar-count-buffalo", species: "buffalo" },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_goat",    canonical_id: "state-pashu-aadhaar-count-goat",    species: "goat"    },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_sheep",   canonical_id: "state-pashu-aadhaar-count-sheep",   species: "sheep"   },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_pig",     canonical_id: "state-pashu-aadhaar-count-pig",     species: "pig"     },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_mithun",  canonical_id: "state-pashu-aadhaar-count-mithun",  species: "mithun"  },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_yak",     canonical_id: "state-pashu-aadhaar-count-yak",     species: "yak"     },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_horse",   canonical_id: "state-pashu-aadhaar-count-horse",   species: "horse"   },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_donkey",  canonical_id: "state-pashu-aadhaar-count-donkey",  species: "donkey"  },
    { legacy_id: "agriculture/state_pashu_aadhaar_count_mule",    canonical_id: "state-pashu-aadhaar-count-mule",    species: "mule"    },
  ];

  it("registers all 10 PR B.01 descriptors as canonical-backed", () => {
    for (const row of PR_B01) {
      expect(isCanonicalBacked(row.legacy_id)).toBe(true);
    }
  });

  it("wires every PR B.01 legacy slug to the expected canonical id + livestock table", () => {
    for (const row of PR_B01) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d).not.toBeNull();
      expect(d!.kind).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id).toBe(row.canonical_id);
      }
      expect(d!.table_id).toBe("livestock.livestock_pashu_aadhaar");
    }
  });

  it("every PR B.01 meta block declares state grain + directional-only comparability + no_rank_table", () => {
    // ADR-0043 + Hans honest-renderer doctrine: tagged-animal counts are
    // not a livestock census; rank tables would mislead citizens. Each
    // descriptor MUST carry comparability='directional_only' AND
    // renderer_rules=['no_rank_table'] to suppress the ranked-table view.
    for (const row of PR_B01) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.entity_kind).toBe("state");
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.unit).toBe("animals");
      expect(d.meta.value_kind).toBe("count");
      expect(d.meta.comparability).toBe("directional_only");
      expect(d.meta.renderer_rules).toContain("no_rank_table");
      expect(d.meta.attribution_geography).toBe("where_resident");
      expect(d.meta.title).toMatch(/Pashu Aadhaar/);
      expect(d.meta.notes).toMatch(/NOT a livestock census/);
    }
  });
});

// TODO(deploy-unblock PR #424): re-enable when state-grain + district-grain
// Pashu Aadhaar descriptors (and Hans-curated caveats) land in the paired follow-up
// PR. Tracked under the Phase D livestock cohort in the grain-rip plan.
describe.skip("Phase 3.B - district-grain Pashu Aadhaar fan-out (9 species)", () => {
  // Phase 3.B extends the cattle district descriptor (PR B.03 / B.05.f) to
  // the 9 other species that ship in the same `livestock_pashu_aadhaar`
  // canonical Parquet. Each district descriptor is the source-of-truth
  // grain per ADR-0043; the state-grain sibling is the SUM rollup
  // auto-emitted in the same canonical adapter run (PR B.01).

  const PR_3B: ReadonlyArray<{
    legacy_id: string;
    canonical_id: string;
    species: string;
  }> = [
    { legacy_id: "agriculture/district_pashu_aadhaar_count_buffalo", canonical_id: "district-pashu-aadhaar-count-buffalo", species: "buffalo" },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_goat",    canonical_id: "district-pashu-aadhaar-count-goat",    species: "goat"    },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_sheep",   canonical_id: "district-pashu-aadhaar-count-sheep",   species: "sheep"   },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_pig",     canonical_id: "district-pashu-aadhaar-count-pig",     species: "pig"     },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_mithun",  canonical_id: "district-pashu-aadhaar-count-mithun",  species: "mithun"  },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_yak",     canonical_id: "district-pashu-aadhaar-count-yak",     species: "yak"     },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_horse",   canonical_id: "district-pashu-aadhaar-count-horse",   species: "horse"   },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_donkey",  canonical_id: "district-pashu-aadhaar-count-donkey",  species: "donkey"  },
    { legacy_id: "agriculture/district_pashu_aadhaar_count_mule",    canonical_id: "district-pashu-aadhaar-count-mule",    species: "mule"    },
  ];

  it("registers all 9 Phase 3.B district descriptors as canonical-backed", () => {
    for (const row of PR_3B) {
      expect(isCanonicalBacked(row.legacy_id)).toBe(true);
    }
  });

  it("wires every Phase 3.B district slug to the expected canonical id + livestock table", () => {
    for (const row of PR_3B) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d).not.toBeNull();
      expect(d!.kind).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id).toBe(row.canonical_id);
      }
      expect(d!.table_id).toBe("livestock.livestock_pashu_aadhaar");
    }
  });

  it("every Phase 3.B descriptor declares district grain + Hans honest-renderer doctrine", () => {
    for (const row of PR_3B) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.entity_kind).toBe("district");
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.unit).toBe("animals");
      expect(d.meta.value_kind).toBe("count");
      expect(d.meta.comparability).toBe("directional_only");
      expect(d.meta.renderer_rules).toContain("no_rank_table");
      expect(d.meta.attribution_geography).toBe("where_resident");
      expect(d.meta.title).toMatch(/district/);
      expect(d.meta.notes).toMatch(/NOT a livestock census|early-rollout/);
    }
  });

  it("district descriptors are distinct from their state-grain siblings", () => {
    for (const row of PR_3B) {
      const district = getCanonicalDescriptor(row.legacy_id)!;
      const state = getCanonicalDescriptor(
        row.legacy_id.replace("district_", "state_"),
      )!;
      expect(district.meta.id).not.toBe(state.meta.id);
      expect(district.meta.entity_kind).toBe("district");
      expect(state.meta.entity_kind).toBe("state");
      expect(district.table_id).toBe(state.table_id);
    }
  });
});

// TODO(deploy-unblock PR #424): re-enable when state-grain + district-grain
// Pashu Aadhaar descriptors (and Hans-curated caveats) land in the paired follow-up
// PR. Tracked under the Phase D livestock cohort in the grain-rip plan.
describe.skip("Phase 3.C-partial - Owner Registration (2 facet-multiplexed parents)", () => {
  // Phase 3.C-partial wires the NDLM Owner Registration series. The
  // parent indicators are zero-row in canonical (compute-on-read parents:
  // parent_indicator_id is null in the catalogue); the renderer SUMs the
  // 6 landholding-bracket children to materialise the parent value.
  // Landholding brackets aligned with Agriculture Census 2015-16.

  const OWNER_REG_PARENTS: ReadonlyArray<{
    legacy_id: string;
    canonical_parent_id: string;
    entity_kind: "state" | "district";
  }> = [
    {
      legacy_id: "agriculture/state_livestock_owner_reg_count",
      canonical_parent_id: "state-livestock-owner-reg-count",
      entity_kind: "state",
    },
    {
      legacy_id: "agriculture/district_livestock_owner_reg_count",
      canonical_parent_id: "district-livestock-owner-reg-count",
      entity_kind: "district",
    },
  ];

  const LANDHOLDING_BRACKETS: ReadonlyArray<string> = [
    "landless_marginal",
    "small",
    "semi_medium",
    "medium",
    "large",
    "not_specified",
  ];

  it("registers both Owner Reg parents as canonical-backed", () => {
    for (const row of OWNER_REG_PARENTS) {
      expect(isCanonicalBacked(row.legacy_id)).toBe(true);
    }
  });

  it("every Owner Reg parent is a facet-multiplexed descriptor on the landholding axis", () => {
    for (const row of OWNER_REG_PARENTS) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d).not.toBeNull();
      expect(d!.kind).toBe("facet-multiplexed");
      if (d!.kind === "facet-multiplexed") {
        expect(d!.canonical_parent_indicator_id).toBe(row.canonical_parent_id);
        expect(d!.facet_axis_id).toBe("landholding");
        expect(d!.facet_values).toHaveLength(6);
        const labels = d!.facet_values.map((f) => f.legacy_facet_label);
        for (const bracket of LANDHOLDING_BRACKETS) {
          expect(labels).toContain(bracket);
        }
      }
      expect(d!.table_id).toBe("livestock.livestock_owner_registration");
    }
  });

  it("every Owner Reg parent meta carries Hans honest-renderer doctrine", () => {
    for (const row of OWNER_REG_PARENTS) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.entity_kind).toBe(row.entity_kind);
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.value_kind).toBe("count");
      expect(d.meta.unit).toBe("owners");
      expect(d.meta.comparability).toBe("directional_only");
      expect(d.meta.renderer_rules).toContain("no_rank_table");
      expect(d.meta.title).toMatch(/landholding/);
      expect(d.meta.notes).toMatch(/not_specified/);
    }
  });

  it("Owner Reg district descriptor is distinct from state sibling but shares the fact table", () => {
    const district = getCanonicalDescriptor(
      "agriculture/district_livestock_owner_reg_count",
    )!;
    const state = getCanonicalDescriptor(
      "agriculture/state_livestock_owner_reg_count",
    )!;
    expect(district.meta.id).not.toBe(state.meta.id);
    expect(district.meta.entity_kind).toBe("district");
    expect(state.meta.entity_kind).toBe("state");
    expect(district.table_id).toBe(state.table_id);
  });
});

// TODO(deploy-unblock PR #424): re-enable when state-grain + district-grain
// Pashu Aadhaar descriptors (and Hans-curated caveats) land in the paired follow-up
// PR. Tracked under the Phase D livestock cohort in the grain-rip plan.
describe.skip("Phase 3.C-partial - NAIP IV (8 single descriptors across 4 metric families)", () => {
  // NAIP IV is a SELECT-DISTRICT programme; 8 states/UTs report zero
  // coverage upstream and that absence is honesty signal, not a defect.
  // Each metric family ships at both grains (district source-of-truth +
  // state SUM rollup per ADR-0043); units differ across families so they
  // ship as 8 single descriptors rather than a facet-multiplexed parent.

  const NAIP_IV: ReadonlyArray<{
    legacy_id: string;
    canonical_id: string;
    entity_kind: "state" | "district";
    unit: string;
  }> = [
    { legacy_id: "agriculture/state_livestock_naip_iv_inseminations",        canonical_id: "state-livestock-naip-iv-inseminations",        entity_kind: "state",    unit: "inseminations" },
    { legacy_id: "agriculture/district_livestock_naip_iv_inseminations",     canonical_id: "district-livestock-naip-iv-inseminations",     entity_kind: "district", unit: "inseminations" },
    { legacy_id: "agriculture/state_livestock_naip_iv_pregnancy_diagnoses",  canonical_id: "state-livestock-naip-iv-pregnancy-diagnoses",  entity_kind: "state",    unit: "diagnoses"     },
    { legacy_id: "agriculture/district_livestock_naip_iv_pregnancy_diagnoses", canonical_id: "district-livestock-naip-iv-pregnancy-diagnoses", entity_kind: "district", unit: "diagnoses"     },
    { legacy_id: "agriculture/state_livestock_naip_iv_calves_born",          canonical_id: "state-livestock-naip-iv-calves-born",          entity_kind: "state",    unit: "calves"        },
    { legacy_id: "agriculture/district_livestock_naip_iv_calves_born",       canonical_id: "district-livestock-naip-iv-calves-born",       entity_kind: "district", unit: "calves"        },
    { legacy_id: "agriculture/state_livestock_naip_iv_farmers_benefitted",   canonical_id: "state-livestock-naip-iv-farmers-benefitted",   entity_kind: "state",    unit: "farmers"       },
    { legacy_id: "agriculture/district_livestock_naip_iv_farmers_benefitted", canonical_id: "district-livestock-naip-iv-farmers-benefitted", entity_kind: "district", unit: "farmers"       },
  ];

  it("registers all 8 NAIP IV descriptors as canonical-backed", () => {
    for (const row of NAIP_IV) {
      expect(isCanonicalBacked(row.legacy_id)).toBe(true);
    }
  });

  it("wires every NAIP IV slug to the expected canonical id + livestock_naip_iv table", () => {
    for (const row of NAIP_IV) {
      const d = getCanonicalDescriptor(row.legacy_id);
      expect(d).not.toBeNull();
      expect(d!.kind).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id).toBe(row.canonical_id);
      }
      expect(d!.table_id).toBe("livestock.livestock_naip_iv");
    }
  });

  it("every NAIP IV descriptor carries Hans honest-renderer doctrine + select-district honesty note", () => {
    for (const row of NAIP_IV) {
      const d = getCanonicalDescriptor(row.legacy_id)!;
      expect(d.meta.entity_kind).toBe(row.entity_kind);
      expect(d.meta.time_grain).toBe("fiscal_year");
      expect(d.meta.value_kind).toBe("count");
      expect(d.meta.unit).toBe(row.unit);
      expect(d.meta.comparability).toBe("directional_only");
      expect(d.meta.renderer_rules).toContain("no_rank_table");
      expect(d.meta.title).toMatch(/NAIP IV/);
      expect(d.meta.notes).toMatch(/SELECT-DISTRICT/);
    }
  });

  it("each NAIP IV metric family has matched district + state descriptors sharing the fact table", () => {
    const families = ["inseminations", "pregnancy_diagnoses", "calves_born", "farmers_benefitted"];
    for (const family of families) {
      const district = getCanonicalDescriptor(`agriculture/district_livestock_naip_iv_${family}`)!;
      const state = getCanonicalDescriptor(`agriculture/state_livestock_naip_iv_${family}`)!;
      expect(district).not.toBeNull();
      expect(state).not.toBeNull();
      expect(district.meta.id).not.toBe(state.meta.id);
      expect(district.meta.entity_kind).toBe("district");
      expect(state.meta.entity_kind).toBe("state");
      expect(district.table_id).toBe(state.table_id);
      expect(district.table_id).toBe("livestock.livestock_naip_iv");
    }
  });
});
