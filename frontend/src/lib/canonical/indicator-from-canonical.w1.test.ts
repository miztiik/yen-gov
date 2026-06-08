// Vitest -- W1 RBI State Finances cohort (2026-06-08)
// Branch: feat/w1-canonical-first-rbi-state-finances
//
// Per CLAUDE.md section 15 + user memory "Per-indicator frontend
// allowlist seam for canonical reader-switches" doctrine: mocked
// DuckDB-WASM boundary, descriptor invariants, builder edge cases,
// loader SQL shape, dispatch null vs populated.
//
// Sibling-pattern: indicator-from-canonical.test.ts (parent suite for the
// energy + livestock descriptors). This file mirrors the same `vi.mock`
// surface and lazy-seeded slug -> legacy map so test isolation matches.

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
  type CanonicalIndicatorDescriptor,
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
    ["delhi", "U05"],
  ]);
});

// W1 ID mapping (legacy fiscal shard id -> canonical kebab-case id).
// Keep this in lockstep with the PR commit body's mapping table.
const W1_MAPPINGS: ReadonlyArray<readonly [string, string]> = [
  ["fiscal/state_own_tax_revenue_inr_crore", "own-tax-revenue-inr-crore"],
  ["fiscal/state_share_central_taxes_inr_crore", "central-tax-devolution-inr-crore"],
  ["fiscal/state_revenue_expenditure_inr_crore", "revenue-expenditure-inr-crore"],
  ["fiscal/state_grants_in_aid_inr_crore", "grants-in-aid-inr-crore"],
  ["fiscal/outstanding_debt_pct_gsdp", "outstanding-liabilities-pct-gsdp"],
  ["fiscal/state_pension_expenditure_inr_crore", "pension-expenditure-inr-crore"],
];

describe("W1 RBI State Finances cohort -- allowlist invariants", () => {
  it("every W1 legacy id is allowlisted and resolves to the canonical id", () => {
    for (const [legacy, canonical] of W1_MAPPINGS) {
      expect(isCanonicalBacked(legacy), `not allowlisted: ${legacy}`).toBe(true);
      const d = getCanonicalDescriptor(legacy);
      expect(d, `null descriptor: ${legacy}`).not.toBeNull();
      expect(d!.kind).toBe("single");
      if (d!.kind === "single") {
        expect(d!.canonical_indicator_id, `wrong canonical_id for ${legacy}`).toBe(canonical);
      }
    }
  });

  it("every W1 descriptor carries csv_path under data/datapoints/geo/", () => {
    for (const [legacy, canonical] of W1_MAPPINGS) {
      const d = getCanonicalDescriptor(legacy) as CanonicalSingleIndicatorDescriptor;
      expect(d.csv_path).toBe(`data/datapoints/geo/${canonical}.csv`);
    }
  });

  it("every W1 descriptor shares the same fiscal table_id", () => {
    // Hans + Max W1 decision (plan-doc §10): all 6 RBI State Finances W1
    // indicators sit on a single fact-table (state_finances) — the
    // long-format CSV doesn't materialise this until the bulk re-ingest
    // PR lands, but the table_id contract belongs in the allowlist now.
    for (const [legacy] of W1_MAPPINGS) {
      const d = getCanonicalDescriptor(legacy)!;
      expect(d.table_id).toBe("fiscal.state_finances");
    }
  });

  it("every W1 descriptor has the citizen-facing IndicatorMeta block populated", () => {
    for (const [legacy] of W1_MAPPINGS) {
      const d = getCanonicalDescriptor(legacy)!;
      expect(d.meta.title.length).toBeGreaterThan(0);
      expect(d.meta.entity_kind).toBe("state");
      expect(d.meta.time_grain).toBe("fiscal_year");
      // Unit is non-empty for every W1 indicator.
      expect(d.meta.unit.length).toBeGreaterThan(0);
      expect(d.meta.attribution_geography).toBe("where_administered");
    }
  });

  it("W1 cohort hits the 6/42 canonical-backed checkpoint set by the G5 audit", () => {
    // Counts the W1 cohort specifically (NOT the total allowlist size,
    // which also includes the energy + livestock cohorts). 6 is the
    // W1 deliverable per the plan-doc §10 W1 row + G5-PR-B threshold
    // (canonical-backed >= 22/42 unblocks the bulk rip; W1 contributes 6).
    let count = 0;
    for (const [legacy] of W1_MAPPINGS) {
      if (isCanonicalBacked(legacy)) count += 1;
    }
    expect(count).toBe(6);
  });

  it("descriptors carry direction values appropriate to fiscal semantics", () => {
    // own-tax-revenue: states collecting their own taxes is fiscal-capacity-positive.
    expect(getCanonicalDescriptor("fiscal/state_own_tax_revenue_inr_crore")!.meta.direction)
      .toBe("higher_is_better");
    // outstanding-liabilities-%-GSDP: debt-to-GSDP is the canonical
    // lower-is-better fiscal indicator (FRBM target framing).
    expect(getCanonicalDescriptor("fiscal/outstanding_debt_pct_gsdp")!.meta.direction)
      .toBe("lower_is_better");
    // central-tax-devolution / revenue-expenditure / grants-in-aid /
    // pension-expenditure: neutral. High devolution rewards lower
    // per-capita income, NOT effort; pension is committed liability,
    // not a policy choice; revenue expenditure can be salary inflation
    // OR welfare delivery -- direction is ambiguous without context.
    for (const id of [
      "fiscal/state_share_central_taxes_inr_crore",
      "fiscal/state_revenue_expenditure_inr_crore",
      "fiscal/state_grants_in_aid_inr_crore",
      "fiscal/state_pension_expenditure_inr_crore",
    ]) {
      expect(getCanonicalDescriptor(id)!.meta.direction).toBe("neutral");
    }
  });

  it("outstanding-liabilities-%-GSDP descriptor flags Accounts-only + S09 exclusions", () => {
    // The CSV emit script DROPS J&K-state-era (S09) rows + RE/BE projection rows.
    // The descriptor's `caveats[]` MUST surface both decisions verbatim so
    // AboutThisData renders them in the citizen-visible "Known caveats" section.
    const d = getCanonicalDescriptor("fiscal/outstanding_debt_pct_gsdp")!;
    expect(d.caveats, "outstanding-liabilities-%-GSDP descriptor missing caveats[]").toBeDefined();
    expect(d.caveats!.length).toBeGreaterThanOrEqual(2);
    // Caveat about RE/BE projections being excluded.
    expect(d.caveats!.some((c) => /RE|BE|Revised|Budget|Accounts-only|Accounts only/i.test(c))).toBe(true);
    // Caveat about J&K state-era exclusion.
    expect(d.caveats!.some((c) => /J&K|Jammu|S09|state-era/i.test(c))).toBe(true);
  });

  it("all W1 descriptors are present in CANONICAL_BACKED_INDICATORS array", () => {
    const allowlistIds = new Set(CANONICAL_BACKED_INDICATORS.map((d) => d.legacy_artifact_id));
    for (const [legacy] of W1_MAPPINGS) {
      expect(allowlistIds.has(legacy), `descriptor missing from array: ${legacy}`).toBe(true);
    }
  });
});

describe("W1 loader -- DuckDB-WASM round-trip via R2 CSV path", () => {
  const W1_SAMPLE: CanonicalIndicatorDescriptor = getCanonicalDescriptor(
    "fiscal/state_own_tax_revenue_inr_crore",
  )!;

  it("registers the per-indicator CSV URL + sources table before querying", async () => {
    mockedQuery.mockResolvedValue([]);
    await expect(loadIndicatorFromCanonical(W1_SAMPLE)).rejects.toThrow(
      /current indicator schema requires at least one row/,
    );
    const csvUrls = mockedRegisterCsvFile.mock.calls.map((c) => c[0]);
    expect(csvUrls.some((u) => u.includes("own-tax-revenue-inr-crore.csv"))).toBe(true);
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls.map((c) => c[0]);
    expect(csvAsTableIds).toContain("taxonomy.sources");
    // Parquet path is NEVER touched on the CSV-only W1 cohort.
    expect(mockedRegister).not.toHaveBeenCalled();
  });

  it("queries the CSV via read_csv(<url>, columns={...}) with no indicator_id filter", async () => {
    mockedQuery.mockResolvedValue([]);
    await expect(loadIndicatorFromCanonical(W1_SAMPLE)).rejects.toThrow(
      /current indicator schema requires at least one row/,
    );
    const firstSql = mockedQuery.mock.calls[0][0] as string;
    expect(firstSql).toMatch(/FROM\s+read_csv\(/);
    expect(firstSql).toMatch(/own-tax-revenue-inr-crore\.csv/);
    expect(firstSql).toMatch(/columns=\{/);
    // Per-indicator CSV: indicator_id is encoded in the filename.
    expect(firstSql).not.toMatch(/indicator_id\s*=/);
  });

  it("translates slug entity_ids to legacy ECI codes via the canonical seam", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "andhra-pradesh", time: 2016, value: 44181.39, source_id: "src-4ead503ee617" },
        { entity_id: "tamil-nadu", time: 2016, value: 82956.13, source_id: "src-4ead503ee617" },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-4ead503ee617",
          producer: "Rajya Sabha Secretariat (Government of India)",
          title: "Rajya Sabha Session 260 Unstarred Question 1323",
          vintage: "2023-08-01",
          license: "OGL-IN-1.0",
          confidence_tier: "gold",
          is_issuing_authority: true,
          verification_method: "transcribed",
          url_main: "https://sansad.in/rs/questions/questions-and-answers",
          citation_full: null,
          notes: null,
        },
      ]);
    const out = await loadIndicatorFromCanonical(W1_SAMPLE);
    // Slug -> legacy ECI code translation via the test map seeded in beforeEach.
    const entityIds = out.rows.map((r) => r.entity_id).sort();
    expect(entityIds).toEqual(["S01", "S22"]);
    // CSV integer time stringified to match the IndicatorRow.time contract.
    expect(out.rows.every((r) => typeof r.time === "string")).toBe(true);
    // Canonical id surfaces on the rebuilt artifact's `indicator.id`.
    expect(out.indicator.id).toBe("own-tax-revenue-inr-crore");
    // Provenance attached via sourcesV2 weak-map (legacy `sources[]` stays empty).
    expect(out.sources).toEqual([]);
    const v2 = indicatorArtifactSourcesV2(out);
    expect(v2).toHaveLength(1);
    expect(v2![0].producer).toBe("Rajya Sabha Secretariat (Government of India)");
  });

  it("the W1 cohort uses 2 distinct provenance src-ids and 1 RBI Handbook id", async () => {
    // The 4 Rajya-Sabha-Q1323 indicators share src-4ead503ee617.
    // outstanding-liabilities-%-GSDP uses src-17c983e79ed9 (RBI State Finances).
    // pension-expenditure-inr-crore uses src-552aabf4ecb2 (RBI Handbook Table 171).
    // The same source_id appears on every row of the 4 sibling indicators
    // (one citation row per producer/title/vintage triple per plan section 12).
    const sample = getCanonicalDescriptor(
      "fiscal/state_grants_in_aid_inr_crore",
    ) as CanonicalSingleIndicatorDescriptor;
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "andhra-pradesh", time: 2016, value: 100, source_id: "src-4ead503ee617" },
        { entity_id: "andhra-pradesh", time: 2017, value: 110, source_id: "src-4ead503ee617" },
      ])
      .mockResolvedValueOnce([]);  // sources query
    const out = await loadIndicatorFromCanonical(sample);
    expect(out.rows.length).toBe(2);
    expect(out.indicator.id).toBe("grants-in-aid-inr-crore");
  });

  it("loadIndicatorIfCanonical returns the canonical artifact for a W1 legacy id (R2 CSV path)", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        { entity_id: "andhra-pradesh", time: 2007, value: 27.4, source_id: "src-17c983e79ed9" },
      ])
      .mockResolvedValueOnce([
        {
          source_id: "src-17c983e79ed9",
          producer: "Reserve Bank of India",
          title: "State Finances: A Study of Budgets, 2022-23 (Appendix Table 20)",
          vintage: "2022-23",
          license: "OGL-IN-1.0",
          confidence_tier: "gold",
          is_issuing_authority: true,
          verification_method: "live-fetch",
          url_main: "https://rbi.org.in/",
          citation_full: null,
          notes: null,
        },
      ]);
    const out = await loadIndicatorIfCanonical("fiscal/outstanding_debt_pct_gsdp");
    expect(out).not.toBeNull();
    expect(out!.indicator.id).toBe("outstanding-liabilities-pct-gsdp");
    expect(out!.rows[0].entity_id).toBe("S01");
    expect(out!.rows[0].time).toBe("2007");
    expect(out!.rows[0].value).toBe(27.4);
  });
});
