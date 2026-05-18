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
  fileUrls,
  loadManifest,
  tableFromManifest,
  type Manifest,
} from "./duckdb";

const SAMPLE_MANIFEST: Manifest = {
  manifest_version: "1.0",
  generated_at: "2026-05-18T12:00:00Z",
  tables: [
    {
      table_id: "elections.observations",
      family: "elections",
      table_name: "observations",
      kind: "observations",
      format: "parquet",
      schema_version: "1.1",
      partition_columns: [],
      files: [
        { path: "elections/observations.parquet", size_bytes: 13_472_657, row_count: 179_746 },
      ],
      row_count_total: 179_746,
    },
    {
      table_id: "taxonomy.sources",
      family: "taxonomy",
      table_name: "sources",
      kind: "taxonomy",
      format: "parquet",
      schema_version: "1.0",
      partition_columns: [],
      files: [{ path: "taxonomy/sources.parquet", size_bytes: 12_345, row_count: 84 }],
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
    expect(m.tables[0].table_id).toBe("elections.observations");
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

  it("tableFromManifest returns the matching table", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.observations");
    expect(t.row_count_total).toBe(179_746);
  });

  it("tableFromManifest throws on unknown table_id", () => {
    expect(() => tableFromManifest(SAMPLE_MANIFEST, "energy.observations")).toThrow(
      /table_id not found: energy.observations/,
    );
  });

  it("fileUrls prepends DATA_BASE to each manifest path", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.observations");
    const urls = fileUrls(t);
    expect(urls).toHaveLength(1);
    expect(urls[0].endsWith("/data/elections/observations.parquet")).toBe(true);
  });
});

describe("registerTable view name resolution", () => {
  // Pure-helper coverage of the manifest-driven defaulting rule introduced
  // with manifest.schema.json v1.1 (THE PLAN row 1.8a-bis). Boots no
  // DuckDB-WASM — same separation as `manifest helpers` above; the real
  // round-trip lives in Playwright (Phase 0.11).

  it("defaultViewName prefers manifest table_name when present", () => {
    const t = tableFromManifest(SAMPLE_MANIFEST, "elections.observations");
    expect(defaultViewName(t, "elections.observations")).toBe("observations");
  });

  it("defaultViewName falls back to last table_id segment when table_name missing", () => {
    // Simulate a pre-v1.1 manifest entry where the writer hasn't yet been
    // upgraded. The reader must still produce a sensible view name so old
    // bundles keep working after a writer-only revert.
    const legacy = tableFromManifest(SAMPLE_MANIFEST, "elections.observations");
    const { table_name: _omit, ...stripped } = legacy;
    expect(defaultViewName(stripped, "elections.observations")).toBe("observations");
    expect(defaultViewName(stripped, "energy.energy_capacity")).toBe("energy_capacity");
  });
});
