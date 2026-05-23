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

import { query, registerTable } from "../duckdb";
import {
  buildIndicatorArtifact,
  canonicalEntityToLegacy,
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

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
});

// Test fixture mirrors the on-disk shape of the C4.7 Phase A canonical row.
// Pre-loaded into the descriptor lookup; one real entry today (peak demand).
const PEAK_DEMAND_DESCRIPTOR: CanonicalIndicatorDescriptor = getCanonicalDescriptor(
  "energy/state_peak_electricity_demand_mw",
)!;

describe("indicator-allowlist (Phase B registry invariants)", () => {
  it("exports at least one descriptor (the C4.7 Phase B seed)", () => {
    expect(CANONICAL_BACKED_INDICATORS.length).toBeGreaterThan(0);
  });

  it("treats the seed peak-demand artifact as canonical-backed", () => {
    expect(isCanonicalBacked("energy/state_peak_electricity_demand_mw")).toBe(true);
  });

  it("treats unrelated artifacts as legacy-backed (false)", () => {
    expect(isCanonicalBacked("energy/state_per_capita_electricity_consumption_kwh")).toBe(false);
    expect(isCanonicalBacked("does/not/exist")).toBe(false);
    expect(isCanonicalBacked("")).toBe(false);
  });

  it("resolves the descriptor for the seed artifact and null otherwise", () => {
    const d = getCanonicalDescriptor("energy/state_peak_electricity_demand_mw");
    expect(d).not.toBeNull();
    expect(d!.canonical_indicator_id).toBe("state-peak-electricity-demand-mw");
    expect(d!.table_id).toBe("energy.energy_demand_supply");
    expect(getCanonicalDescriptor("nope")).toBeNull();
  });

  it("seed descriptor carries the citizen-visible IndicatorMeta block", () => {
    expect(PEAK_DEMAND_DESCRIPTOR.meta.title).toMatch(/peak/i);
    expect(PEAK_DEMAND_DESCRIPTOR.meta.unit).toBe("MW");
    expect(PEAK_DEMAND_DESCRIPTOR.meta.entity_kind).toBe("state");
    expect(PEAK_DEMAND_DESCRIPTOR.meta.time_grain).toBe("fiscal_year");
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
    expect(firstSql).toMatch(/indicator_id\s*=\s*'state-peak-electricity-demand-mw'/);
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
    expect(out!.indicator.id).toBe("state-peak-electricity-demand-mw");
    expect(out!.rows[0].entity_id).toBe("S22");
  });
});
