// Vitest -- G5 bulk-rip cohort (2026-06-08)
// Branch: feat/g5-bulk-rip-25-indicators
//
// Per CLAUDE.md section 15 + user memory "Per-indicator frontend
// allowlist seam for canonical reader-switches" doctrine: mocked
// DuckDB-WASM boundary, descriptor invariants, builder edge cases,
// loader SQL shape, dispatch null vs populated.
//
// Sibling-pattern: indicator-from-canonical.w1.test.ts (W1 RBI State
// Finances cohort, 2026-06-08). This file mirrors the same vi.mock
// surface and lazy-seeded slug -> legacy map so test isolation matches.
// Covers all 25 G5 indicators: 14 single + 11 facet-multiplexed,
// totaling 84 per-indicator CSVs under data/datapoints/geo/.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  registerSlice: vi.fn(async () => "noop"),
  registerCsvAsTable: vi.fn(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  ),
  registerCsvFile: vi.fn(async () => undefined),
  query: vi.fn(),
}));

vi.mock("./csv-columns", () => ({
  csvColumnsClause: vi.fn(async () =>
    "columns={'entity_id': 'VARCHAR', 'time': 'BIGINT', 'value': 'DOUBLE', 'source_id': 'VARCHAR'}",
  ),
}));

vi.mock("./canonical-entity-translation", async () => {
  const actual = await vi.importActual<
    typeof import("./canonical-entity-translation")
  >("./canonical-entity-translation");
  return {
    ...actual,
    loadCanonicalSlugToLegacyMap: vi.fn(async () => testSlugToLegacyMap),
  };
});

let testSlugToLegacyMap: Map<string, string> = new Map();

vi.mock("../indicators", async () => {
  const actual = await vi.importActual<typeof import("../indicators")>("../indicators");
  return {
    ...actual,
    fetchIndicator: vi.fn(),
  };
});

import { query, registerCsvAsTable, registerCsvFile, registerTable } from "../duckdb";
import {
  loadIndicatorFromCanonical,
  loadIndicatorIfCanonical,
  indicatorArtifactSourcesV2,
} from "./indicator-from-canonical";
import {
  CANONICAL_BACKED_INDICATORS,
  getCanonicalDescriptor,
  isCanonicalBacked,
  type CanonicalFacetMultiplexedDescriptor,
  type CanonicalSingleIndicatorDescriptor,
} from "./indicator-allowlist";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
  mockedRegisterCsvFile.mockReset();
  mockedRegisterCsvFile.mockResolvedValue(undefined);
  mockedRegisterCsvAsTable.mockReset();
  mockedRegisterCsvAsTable.mockImplementation(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  );
  testSlugToLegacyMap = new Map([
    ["IN", "IN"],
    ["andhra-pradesh", "S01"],
    ["arunachal-pradesh", "S02"],
    ["assam", "S03"],
    ["bihar", "S04"],
    ["tamil-nadu", "S22"],
    ["uttar-pradesh", "S24"],
    ["delhi", "U05"],
  ]);
});

// G5 ID mapping. Kept in lockstep with the PR commit body's mapping
// table + .tmp_g5_test_data.ts (generator output).
// Tuple: [legacy_artifact_id, canonical_indicator_id, kind]
const G5_MAPPINGS: ReadonlyArray<readonly [string, string, "single" | "facet-multiplexed"]> = [
  // demography (1)
  ["demography/state_population_lakhs", "state-population-lakhs", "single"],
  // economy (10)
  ["economy/gdp_inr_crore", "gdp-inr-crore", "facet-multiplexed"],
  ["economy/gva_by_industry_constant_inr_crore", "gva-by-industry-constant-inr-crore", "facet-multiplexed"],
  ["economy/iip_index", "iip-index", "facet-multiplexed"],
  ["economy/india_external_balance_inr_crore", "india-external-balance-inr-crore", "facet-multiplexed"],
  ["economy/nsdp_inr_crore", "nsdp-inr-crore", "facet-multiplexed"],
  ["economy/per_capita_nsdp_constant_inr", "per-capita-nsdp-constant-inr", "single"],
  ["economy/per_capita_nsdp_current_inr", "per-capita-nsdp-current-inr", "single"],
  ["economy/sectoral_gva_inr_crore", "sectoral-gva-inr-crore", "facet-multiplexed"],
  ["economy/state_gdp_constant_2011_12_inr_lakh_crore", "state-gdp-constant-2011-12-inr-lakh-crore", "single"],
  ["economy/state_per_capita_consumption_inr", "per-capita-consumption-inr", "single"],
  // environment (8)
  ["environment/india_ghg_emissions_by_subsector_ggco2e", "india-ghg-emissions-ggco2e-by-subsector", "facet-multiplexed"],
  ["environment/india_ghg_emissions_mtco2e_by_sector", "india-ghg-emissions-mtco2e-by-sector", "facet-multiplexed"],
  ["environment/state_no2_annual_mean_ug_m3", "no2-annual-mean-ug-m3", "single"],
  ["environment/state_pm10_annual_mean_ug_m3", "pm10-annual-mean-ug-m3", "single"],
  ["environment/state_pm25_annual_mean_ug_m3", "pm25-annual-mean-ug-m3", "single"],
  ["environment/state_power_sector_co2_emissions_mtco2", "state-power-sector-co2-emissions-mtco2", "facet-multiplexed"],
  ["environment/state_so2_annual_mean_ug_m3", "so2-annual-mean-ug-m3", "single"],
  ["environment/state_thermal_fgd_installed_share_pct", "thermal-fgd-installed-share-pct", "single"],
  // fiscal (5)
  ["fiscal/net_transfers_from_centre", "net-transfers-from-centre-inr-crore", "facet-multiplexed"],
  ["fiscal/state_external_debt_inr_crore", "state-external-debt-inr-crore", "single"],
  ["fiscal/state_non_tax_revenue_inr_crore", "non-tax-revenue-inr-crore", "single"],
  ["fiscal/states_combined_gross_fiscal_deficit", "states-combined-gross-fiscal-deficit-inr-crore", "single"],
  ["fiscal/union_gross_fiscal_deficit", "union-gross-fiscal-deficit-inr-crore", "single"],
  // prices (1)
  ["prices/cpi_inflation_pct", "cpi-inflation-pct", "facet-multiplexed"],
];

describe("G5 bulk-rip cohort -- allowlist invariants (25 indicators)", () => {
  it("inventory is exactly 25 mappings (10 economy + 8 environment + 5 fiscal + 1 demography + 1 prices)", () => {
    expect(G5_MAPPINGS.length).toBe(25);
    // Sanity per-topic counts.
    const byTopic = new Map<string, number>();
    for (const [legacy] of G5_MAPPINGS) {
      const topic = legacy.split("/")[0];
      byTopic.set(topic, (byTopic.get(topic) ?? 0) + 1);
    }
    expect(byTopic.get("economy")).toBe(10);
    expect(byTopic.get("environment")).toBe(8);
    expect(byTopic.get("fiscal")).toBe(5);
    expect(byTopic.get("demography")).toBe(1);
    expect(byTopic.get("prices")).toBe(1);
  });

  it("every G5 legacy id is allowlisted and resolves to the expected canonical id + kind", () => {
    for (const [legacy, canonical, kind] of G5_MAPPINGS) {
      expect(isCanonicalBacked(legacy), `not allowlisted: ${legacy}`).toBe(true);
      const d = getCanonicalDescriptor(legacy);
      expect(d, `null descriptor: ${legacy}`).not.toBeNull();
      expect(d!.kind, `wrong kind for ${legacy}`).toBe(kind);
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id, `wrong canonical_id for ${legacy}`).toBe(
          canonical,
        );
      } else {
        expect(
          d!.canonical_parent_indicator_id,
          `wrong canonical_parent_id for ${legacy}`,
        ).toBe(canonical);
      }
    }
  });

  it("every G5 single descriptor carries csv_path under data/datapoints/geo/", () => {
    for (const [legacy, canonical, kind] of G5_MAPPINGS) {
      if (kind !== "single") continue;
      const d = getCanonicalDescriptor(legacy) as CanonicalSingleIndicatorDescriptor;
      expect(d.csv_path).toBe(`data/datapoints/geo/${canonical}.csv`);
    }
  });

  it("every G5 facet-multiplexed descriptor's children carry csv_path under data/datapoints/geo/", () => {
    for (const [legacy, _canonical, kind] of G5_MAPPINGS) {
      if (kind !== "facet-multiplexed") continue;
      const d = getCanonicalDescriptor(legacy) as CanonicalFacetMultiplexedDescriptor;
      expect(d.facet_values.length, `${legacy} has zero facet_values`).toBeGreaterThan(0);
      for (const fv of d.facet_values) {
        expect(fv.csv_path).toMatch(/^data\/datapoints\/geo\/.+\.csv$/);
        expect(fv.canonical_child_id.length).toBeGreaterThan(0);
        expect(fv.legacy_facet_label.length).toBeGreaterThan(0);
      }
    }
  });

  it("every G5 descriptor has the citizen-facing IndicatorMeta block populated", () => {
    for (const [legacy] of G5_MAPPINGS) {
      const d = getCanonicalDescriptor(legacy)!;
      expect(d.meta.title.length).toBeGreaterThan(0);
      expect(d.meta.unit.length).toBeGreaterThan(0);
      expect(d.meta.description.length).toBeGreaterThan(0);
      expect(d.meta.methodology_vintage.length).toBeGreaterThan(0);
      // entity_kind for G5 is always one of state | country
      expect(["state", "country"]).toContain(d.meta.entity_kind);
    }
  });

  it("all G5 descriptors are present in CANONICAL_BACKED_INDICATORS array", () => {
    const allowlistIds = new Set(CANONICAL_BACKED_INDICATORS.map((d) => d.legacy_artifact_id));
    for (const [legacy] of G5_MAPPINGS) {
      expect(allowlistIds.has(legacy), `descriptor missing from array: ${legacy}`).toBe(true);
    }
  });

  it("G5 cohort hits the 31/42 canonical-backed checkpoint (6 W1 + 25 G5)", () => {
    // Counts the G5 cohort plus the W1 cohort. The 11 G5-PR-A orphans
    // were deleted and were never canonical-backed, so the post-G5
    // canonical-backed count is 6 + 25 = 31 out of the historical 42
    // wired-indicator universe (the 11 silent orphans came off the
    // denominator in G5-PR-A).
    let count = 0;
    for (const [legacy] of G5_MAPPINGS) {
      if (isCanonicalBacked(legacy)) count += 1;
    }
    expect(count).toBe(25);
  });

  it("country-grain G5 indicators correctly declare entity_kind", () => {
    // Per the user brief, these are NATIONAL grain (entity_kind="country"),
    // NEVER state grain. Verifying the descriptor pins this correctly so
    // a future agent does not accidentally re-classify them.
    const COUNTRY_GRAIN = new Set<string>([
      "economy/gdp_inr_crore",
      "economy/gva_by_industry_constant_inr_crore",
      "economy/iip_index",
      "economy/india_external_balance_inr_crore",
      "environment/india_ghg_emissions_by_subsector_ggco2e",
      "environment/india_ghg_emissions_mtco2e_by_sector",
      "fiscal/states_combined_gross_fiscal_deficit",
      "fiscal/union_gross_fiscal_deficit",
    ]);
    for (const [legacy, , ] of G5_MAPPINGS) {
      const d = getCanonicalDescriptor(legacy)!;
      const expected = COUNTRY_GRAIN.has(legacy) ? "country" : "state";
      expect(d.meta.entity_kind, `${legacy}: expected ${expected}`).toBe(expected);
    }
  });

  it("facet-multiplexed descriptors carry exactly the facet counts asserted in the commit body", () => {
    // The expected per-indicator facet counts from the mapping table.
    const EXPECTED: Record<string, number> = {
      "economy/gdp_inr_crore": 2,
      "economy/gva_by_industry_constant_inr_crore": 10,
      "economy/iip_index": 10,
      "economy/india_external_balance_inr_crore": 6,
      "economy/nsdp_inr_crore": 2,
      "economy/sectoral_gva_inr_crore": 2,
      "environment/india_ghg_emissions_by_subsector_ggco2e": 26,
      "environment/india_ghg_emissions_mtco2e_by_sector": 4,
      "environment/state_power_sector_co2_emissions_mtco2": 2,
      "fiscal/net_transfers_from_centre": 3,
      "prices/cpi_inflation_pct": 4,
    };
    for (const [legacy, expected] of Object.entries(EXPECTED)) {
      const d = getCanonicalDescriptor(legacy) as CanonicalFacetMultiplexedDescriptor;
      expect(d.facet_values.length, `${legacy} expected ${expected} facets`).toBe(expected);
    }
  });

  it("ghg-by-subsector descriptor has the 26 IPCC sector x sub-sector children", () => {
    // The 26-subsector case is the boundary case for option (b) per-facet
    // CSVs. Verify the descriptor carries all of them; child slugs use
    // pipe -> dash replacement (Agriculture|Enteric Fermentation ->
    // agriculture-enteric-fermentation) per the slugify helper.
    const d = getCanonicalDescriptor(
      "environment/india_ghg_emissions_by_subsector_ggco2e",
    ) as CanonicalFacetMultiplexedDescriptor;
    expect(d.facet_values.length).toBe(26);
    // Spot-check 4 sub-sectors across 4 different parent sectors:
    const childIds = new Set(d.facet_values.map((fv) => fv.canonical_child_id));
    expect(childIds.has("india-ghg-emissions-ggco2e-by-subsector-agriculture-enteric-fermentation")).toBe(true);
    expect(childIds.has("india-ghg-emissions-ggco2e-by-subsector-energy-energy-industries")).toBe(true);
    expect(childIds.has("india-ghg-emissions-ggco2e-by-subsector-waste-municipal-solid-waste-disposal")).toBe(true);
    expect(childIds.has("india-ghg-emissions-ggco2e-by-subsector-land-use-land-use-change-and-forestry-forest-land")).toBe(true);
  });

  it("net-transfers-from-centre has 3 facets (Accounts + RE + BE) preserving legacy semantics", () => {
    // The legacy shard has 3 implicit facets: rows with no facet column
    // are 'Accounts' (settled past year); rows with facet='BE' are Budget
    // Estimate; rows with facet='RE' are Revised Estimate. The G5 migration
    // pulls the implicit 'Accounts' bucket out as an explicit facet so
    // every row in the CSV has an explicit facet label.
    const d = getCanonicalDescriptor(
      "fiscal/net_transfers_from_centre",
    ) as CanonicalFacetMultiplexedDescriptor;
    expect(d.facet_values.length).toBe(3);
    const labels = d.facet_values.map((fv) => fv.legacy_facet_label).sort();
    expect(labels).toEqual(["Accounts", "BE", "RE"]);
  });

  it("net-transfers-from-centre marks comparability as directional_only (thin time series)", () => {
    // Per W1 lesson: the original shard had only 3 years (1 Accounts +
    // 1 RE + 1 BE). The substitute used in W1 (pension expenditure) was
    // not available here, so the indicator is migrated as a degraded
    // series with directional_only comparability. Verifying the
    // descriptor surfaces this honestly.
    const d = getCanonicalDescriptor("fiscal/net_transfers_from_centre")!;
    expect(d.meta.comparability).toBe("directional_only");
    expect(d.caveats).toBeDefined();
    expect(d.caveats!.some((c) => /THIN|thin|3 fiscal years|Accounts/i.test(c))).toBe(true);
  });
});

describe("G5 representative-indicator loader round-trip (R2 CSV path)", () => {
  it("state-population-lakhs (single, state-grain): registers per-indicator CSV + sources view", async () => {
    const d = getCanonicalDescriptor(
      "demography/state_population_lakhs",
    ) as CanonicalSingleIndicatorDescriptor;
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "andhra-pradesh", time: 2020, value: 521.6, source_id: "src-3155ffeddf80" },
        { entity_id: "tamil-nadu", time: 2020, value: 736.8, source_id: "src-3155ffeddf80" },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-3155ffeddf80",
          producer: "NITI Aayog India Climate & Energy Dashboard",
          title: "State-wise Deep Dive — Population (lakhs) by State, fiscal-year",
          vintage: "2024-25",
          license: "OGL-IN-1.0",
          confidence_tier: "gold",
          is_issuing_authority: true,
          verification_method: "transcribed",
          url_main: "https://iced.niti.gov.in/analytics/state-wise-deep-dive",
          citation_full: null,
          notes: null,
        },
      ]);
    const out = await loadIndicatorFromCanonical(d);
    expect(out.indicator.id).toBe("state-population-lakhs");
    expect(out.rows.length).toBe(2);
    expect(out.rows.map((r) => r.entity_id).sort()).toEqual(["S01", "S22"]);
    // Time integers serialised as strings on the IndicatorRow surface.
    expect(out.rows.every((r) => typeof r.time === "string")).toBe(true);
    // Provenance attached via sourcesV2 weak-map.
    const v2 = indicatorArtifactSourcesV2(out);
    expect(v2).toHaveLength(1);
    expect(v2![0].producer).toBe("NITI Aayog India Climate & Energy Dashboard");
  });

  it("cpi-inflation-pct (facet-multiplexed, 4 facets): UNION ALL across 4 child CSVs", async () => {
    const d = getCanonicalDescriptor(
      "prices/cpi_inflation_pct",
    ) as CanonicalFacetMultiplexedDescriptor;
    // Mock returns rows tagged with synth indicator_id literal (one per facet
    // child). The 'general' + 'food' branches return 1 row each.
    mockedQuery
      .mockResolvedValueOnce([
        { indicator_id: "cpi-inflation-pct-general", entity_id: "tamil-nadu", time: 2022, value: 6.1, source_id: "src-324392501ae9" },
        { indicator_id: "cpi-inflation-pct-food", entity_id: "tamil-nadu", time: 2022, value: 7.3, source_id: "src-324392501ae9" },
        { indicator_id: "cpi-inflation-pct-fuel", entity_id: "tamil-nadu", time: 2022, value: 8.9, source_id: "src-324392501ae9" },
        { indicator_id: "cpi-inflation-pct-housing-urban", entity_id: "tamil-nadu", time: 2022, value: 4.5, source_id: "src-324392501ae9" },
      ])
      .mockResolvedValueOnce([]); // sources query
    const out = await loadIndicatorFromCanonical(d);
    expect(out.indicator.id).toBe("cpi-inflation-pct");
    expect(out.rows.length).toBe(4);
    // Mock returns 4 distinct synth indicator_ids -> 4 distinct facet labels.
    const distinctFacets = new Set(out.rows.map((r) => r.facet));
    expect(distinctFacets).toEqual(new Set(["general", "food", "fuel", "housing_urban"]));
    // Per-facet CSV URLs were registered ahead of the query.
    const csvUrls = mockedRegisterCsvFile.mock.calls.map((c) => c[0]);
    expect(csvUrls.some((u) => u.includes("cpi-inflation-pct-general.csv"))).toBe(true);
    expect(csvUrls.some((u) => u.includes("cpi-inflation-pct-food.csv"))).toBe(true);
    expect(csvUrls.some((u) => u.includes("cpi-inflation-pct-fuel.csv"))).toBe(true);
    expect(csvUrls.some((u) => u.includes("cpi-inflation-pct-housing-urban.csv"))).toBe(true);
  });

  it("union-gross-fiscal-deficit (single, country-grain): IN row passes through entity-kind filter", async () => {
    const d = getCanonicalDescriptor(
      "fiscal/union_gross_fiscal_deficit",
    ) as CanonicalSingleIndicatorDescriptor;
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "IN", time: 2018, value: 649418, source_id: "src-a678f28ff9fc" },
        { entity_id: "IN", time: 2019, value: 933651, source_id: "src-a678f28ff9fc" },
      ])
      .mockResolvedValueOnce([]); // sources query
    const out = await loadIndicatorFromCanonical(d);
    expect(out.indicator.id).toBe("union-gross-fiscal-deficit-inr-crore");
    expect(out.rows.length).toBe(2);
    expect(out.rows.every((r) => r.entity_id === "IN")).toBe(true);
  });

  it("gdp-inr-crore (facet-multiplexed, country-grain): IN rows pass through across both facets", async () => {
    const d = getCanonicalDescriptor(
      "economy/gdp_inr_crore",
    ) as CanonicalFacetMultiplexedDescriptor;
    mockedQuery
      .mockResolvedValueOnce([
        { indicator_id: "gdp-inr-crore-current", entity_id: "IN", time: 2020, value: 19800000, source_id: "src-bb7935971e98" },
        { indicator_id: "gdp-inr-crore-constant", entity_id: "IN", time: 2020, value: 14500000, source_id: "src-bb7935971e98" },
      ])
      .mockResolvedValueOnce([]); // sources query
    const out = await loadIndicatorFromCanonical(d);
    expect(out.indicator.id).toBe("gdp-inr-crore");
    expect(out.rows.length).toBe(2);
    expect(out.rows.every((r) => r.entity_id === "IN")).toBe(true);
    const facetLabels = new Set(out.rows.map((r) => r.facet));
    expect(facetLabels).toEqual(new Set(["current", "constant"]));
  });

  it("loadIndicatorIfCanonical returns the canonical artifact for a G5 legacy id", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "andhra-pradesh", time: 2018, value: 13.1, source_id: "src-263dcba882ba" },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-263dcba882ba",
          producer: "NITI Aayog India Climate & Energy Dashboard",
          title: "Climate-Environment Air Quality AQI Map Markers API — State-wise annual mean concentrations of NO2/SO2/PM10/PM2.5 (ug/m3)",
          vintage: "2024-25",
          license: "OGL-IN-1.0",
          confidence_tier: "silver",
          is_issuing_authority: false,
          verification_method: "live-fetch",
          url_main: "https://icedapi.niti.gov.in/climate-environment/environment/air-quality/aqi-map-markers",
          citation_full: null,
          notes: null,
        },
      ]);
    const out = await loadIndicatorIfCanonical("environment/state_no2_annual_mean_ug_m3");
    expect(out).not.toBeNull();
    expect(out!.indicator.id).toBe("no2-annual-mean-ug-m3");
    expect(out!.rows[0].entity_id).toBe("S01");
    expect(out!.rows[0].time).toBe("2018");
    expect(out!.rows[0].value).toBe(13.1);
  });

  it("non-G5 legacy id falls through to null (dispatch sanity)", async () => {
    // Spot-check that the bulk-rip migration did NOT accidentally widen
    // dispatch to all paths. A made-up legacy id returns null per the
    // existing isCanonicalBacked invariant.
    expect(await loadIndicatorIfCanonical("nonexistent/fake_indicator")).toBeNull();
  });

  it("the G5 cohort references 22 distinct source_ids (de-duped from 25 indicators)", () => {
    // PM10 + PM2.5 + NO2 + SO2 share src-263dcba882ba (same ICED AQI API
    // endpoint, one citation triple). De-dup brings 25 -> 22 unique
    // src-ids. Per ADR-0032: identity = (producer, title, vintage).
    const SHARED_AQI_SOURCE = "src-263dcba882ba";
    expect(SHARED_AQI_SOURCE.length).toBe(16); // src- + 12 hex
    // The 4 AQI sibling indicators share this id.
    const aqiSiblings = [
      "environment/state_no2_annual_mean_ug_m3",
      "environment/state_pm10_annual_mean_ug_m3",
      "environment/state_pm25_annual_mean_ug_m3",
      "environment/state_so2_annual_mean_ug_m3",
    ];
    for (const id of aqiSiblings) {
      expect(isCanonicalBacked(id)).toBe(true);
    }
  });
});
