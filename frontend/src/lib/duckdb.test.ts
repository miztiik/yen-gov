// Contract tests for the DuckDB-WASM loader's pure helpers.
//
// We test the manifest-shape helpers (loadManifest, tableFromManifest, fileUrls)
// because they are pure and have a clear contract. We do NOT boot DuckDB-WASM
// in vitest — wasm + worker + Arrow round-trip is exactly the kind of thing
// Playwright was made for. The round-trip smoke against a real Parquet shard
// lands in Phase 0.11 (failure-state harness) via Playwright.
//
// Mocks: `fetch` is mocked because the loader's contract IS the fetch boundary
// (CLAUDE.md §15 explicit carve-out). Nothing else is mocked.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  __resetForTests,
  defaultViewName,
  filesForSlice,
  fileUrls,
  loadManifest,
  rowSchemaFileForTable,
  tableFromManifest,
  type Manifest,
} from "./duckdb";

const SAMPLE_MANIFEST: Manifest = {
  $schema: "./schemas/manifest.schema.json",
  $schema_version: "1.4",
  manifest_version: "1.0",
  generated_at: "2026-05-18T12:00:00Z",
  tables: [
    {
      table_id: "elections.election_results",
      family: "elections",
      table_name: "election_results",
      kind: "observations",
      format: "parquet",
      schema_version: "1.1",
      partition_columns: ["state"],
      files: [
        {
          path: "elections/state=kerala/election_results.parquet",
          size_bytes: 508_781,
          row_count: 11_860,
          partition_values: { state: "kerala" },
        },
        {
          path: "elections/state=tamil-nadu/election_results.parquet",
          size_bytes: 1_456_891,
          row_count: 20_040,
          partition_values: { state: "tamil-nadu" },
        },
      ],
      row_count_total: 31_900,
    },
    {
      table_id: "elections.dim_party_alliances",
      family: "elections",
      table_name: "dim_party_alliances",
      kind: "dim",
      format: "parquet",
      schema_version: "1.0",
      partition_columns: [],
      files: [{ path: "elections/dim_party_alliances.parquet", size_bytes: 12_345, row_count: 84 }],
      row_count_total: 84,
    },
  ],
};

describe("manifest helpers", () => {
  beforeEach(() => {
    __resetForTests();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loadManifest fetches /data/manifest.json and parses it", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(SAMPLE_MANIFEST), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const m = await loadManifest();
    expect(m.tables).toHaveLength(2);
    expect(m.tables[0].table_id).toBe("elections.election_results");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect((fetchSpy.mock.calls[0][0] as string).endsWith("/data/manifest.json")).toBe(true);
  });

  it("loadManifest caches the promise across calls", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(SAMPLE_MANIFEST), { status: 200 }),
    );
    await loadManifest();
    await loadManifest();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("loadManifest does not poison cache on failure", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("nope", { status: 500, statusText: "Server Error" }))
      .mockResolvedValueOnce(new Response(JSON.stringify(SAMPLE_MANIFEST), { status: 200 }));
    await expect(loadManifest()).rejects.toThrow(/manifest fetch failed: 500/);
    const m = await loadManifest();
    expect(m.tables).toHaveLength(2);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("loadManifest rejects unsupported manifest schema versions and does not poison cache", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...SAMPLE_MANIFEST, $schema_version: "9.9" }), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(SAMPLE_MANIFEST), { status: 200 }));

    await expect(loadManifest()).rejects.toThrow(/schema_version_unsupported: manifest schema_version 9\.9/);
    const manifest = await loadManifest();

    expect(manifest.$schema_version).toBe("1.4");
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("tableFromManifest returns the matching table", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    expect(t.row_count_total).toBe(31_900);
  });

  it("tableFromManifest accepts current non-observation table versions", () => {
    const table = tableFromManifest(SAMPLE_MANIFEST, "elections.dim_party_alliances");

    expect(table.schema_version).toBe("1.0");
    expect(rowSchemaFileForTable(table)).toBe("dim-party-alliances.schema.json");
  });

  it("tableFromManifest rejects unsupported table versions", () => {
    const manifest: Manifest = {
      ...SAMPLE_MANIFEST,
      tables: [{ ...SAMPLE_MANIFEST.tables[0], schema_version: "9.9" }],
    };

    expect(() => tableFromManifest(manifest, "elections.election_results")).toThrow(
      /schema_version_unsupported: table 'elections\.election_results' schema_version 9\.9/,
    );
  });

  it("tableFromManifest rejects current tables without an explicit row-schema mapping", () => {
    const manifest: Manifest = {
      ...SAMPLE_MANIFEST,
      tables: [{ ...SAMPLE_MANIFEST.tables[1], table_id: "taxonomy.unknown" }],
    };

    expect(() => tableFromManifest(manifest, "taxonomy.unknown")).toThrow(
      /no row schema mapping for taxonomy\.unknown/,
    );
  });

  it("tableFromManifest throws on unknown table_id", () => {
    expect(() => tableFromManifest(SAMPLE_MANIFEST, "energy.observations")).toThrow(
      /table_id not found: energy.observations/,
    );
  });

  it("fileUrls prepends DATA_BASE to each manifest path", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    const urls = fileUrls(t);
    expect(urls).toHaveLength(2);
    expect(urls[0].endsWith("/data/elections/state=kerala/election_results.parquet")).toBe(true);
    expect(urls[1].endsWith("/data/elections/state=tamil-nadu/election_results.parquet")).toBe(true);
  });

  it("filesForSlice returns only files whose partition values match", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    const files = filesForSlice(t, { state: "tamil-nadu" });
    expect(files).toHaveLength(1);
    expect(files[0].path).toBe("elections/state=tamil-nadu/election_results.parquet");
  });

  it("filesForSlice throws on an unknown partition key", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    expect(() => filesForSlice(t, { state_code: "S22" })).toThrow(
      /unknown partition key "state_code".*partition_columns: state/,
    );
  });

  it("filesForSlice throws when no files match the requested slice", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    expect(() => filesForSlice(t, { state: "nonexistent-fake" })).toThrow(
      /no files match elections\.election_results partition state=nonexistent-fake/,
    );
  });

  it("filesForSlice throws for unpartitioned tables unless fallback is explicit", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.dim_party_alliances");
    expect(() => filesForSlice(t, { state: "tamil-nadu" })).toThrow(
      /table elections\.dim_party_alliances is unpartitioned/,
    );
    expect(filesForSlice(t, { state: "tamil-nadu" }, { allowFullTableFallback: true })).toEqual(
      t.files,
    );
  });

  it("filesForSlice throws on an empty partition filter", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    expect(() => filesForSlice(t, {})).toThrow(/slice filter.*is empty/);
  });
});

describe("registerTable view name resolution", () => {
  // Pure-helper coverage of the manifest-driven defaulting rule introduced
  // with manifest.schema.json v1.1 (THE PLAN row 1.8a-bis). Boots no
  // DuckDB-WASM — same separation as `manifest helpers` above; the real
  // round-trip lives in Playwright (Phase 0.11).

  it("defaultViewName prefers manifest table_name when present", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    expect(defaultViewName(t, "elections.election_results")).toBe("election_results");
  });

  it("defaultViewName falls back to last table_id segment when table_name missing", () => {
    // Simulate a pre-v1.1 manifest entry where the writer hasn't yet been
    // upgraded. The reader must still produce a sensible view name so old
    // bundles keep working after a writer-only revert.
    const legacy = tableFromManifest(SAMPLE_MANIFEST, "elections.election_results");
    const { table_name: _omit, ...stripped } = legacy;
    expect(defaultViewName(stripped, "elections.election_results")).toBe("election_results");
    expect(defaultViewName(stripped, "energy.energy_capacity")).toBe("energy_capacity");
  });
});

