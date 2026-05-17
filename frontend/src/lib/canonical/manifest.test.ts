// Manifest reader contract tests. Pure TS — no DuckDB-WASM, no real
// network. Tests assert the schema-version guard, error mapping, and
// table lookup semantics from canonical-store.md §11.2 + §12.4.
//
// The DuckDB-WASM round-trip lives in Playwright (Phase 1+) since vitest
// can't run real Web Workers.

import { describe, expect, it } from "vitest";

import { fetchManifest, isCompatibleSchemaVersion, lookupTable } from "./manifest";
import { SUPPORTED_SCHEMA_VERSIONS } from "./types";
import type { Manifest } from "./types";

const goodManifest: Manifest = {
  $schema: "./schemas/manifest.schema.json",
  $schema_version: "1.0",
  manifest_version: "1.0",
  generated_at: "2026-05-18T00:00:00Z",
  tables: [
    {
      table_id: "elections.observations",
      family: "elections",
      format: "parquet",
      schema_version: "1.0",
      partition_columns: [],
      files: [{ path: "elections/observations.parquet", size_bytes: 1024, row_count: 10 }],
      row_count_total: 10,
    },
    {
      table_id: "taxonomy.sources",
      family: "taxonomy",
      format: "parquet",
      schema_version: "1.0",
      partition_columns: [],
      files: [{ path: "taxonomy/sources.parquet", size_bytes: 512, row_count: 3 }],
      row_count_total: 3,
    },
  ],
};

function mockFetch(response: { status?: number; body: unknown; ok?: boolean }): typeof fetch {
  return async () =>
    ({
      status: response.status ?? 200,
      ok: response.ok ?? (response.status ?? 200) < 400,
      json: async () => response.body,
    }) as unknown as Response;
}

describe("isCompatibleSchemaVersion", () => {
  it("accepts a version listed in SUPPORTED_SCHEMA_VERSIONS", () => {
    expect(isCompatibleSchemaVersion("manifest.schema.json", "1.0")).toBe(true);
  });

  it("rejects a version not yet supported", () => {
    expect(isCompatibleSchemaVersion("manifest.schema.json", "2.0")).toBe(false);
  });

  it("rejects an unknown schema file entirely", () => {
    expect(isCompatibleSchemaVersion("not-a-real.schema.json", "1.0")).toBe(false);
  });

  it("covers every canonical schema in SUPPORTED_SCHEMA_VERSIONS at 1.0", () => {
    for (const file of Object.keys(SUPPORTED_SCHEMA_VERSIONS)) {
      expect(isCompatibleSchemaVersion(file, "1.0")).toBe(true);
    }
  });
});

describe("fetchManifest", () => {
  it("returns the manifest on 200 + valid JSON", async () => {
    const out = await fetchManifest("ignored", mockFetch({ body: goodManifest }));
    expect(out).toEqual(goodManifest);
  });

  it("returns not_found on 404", async () => {
    const out = await fetchManifest("ignored", mockFetch({ status: 404, body: {} }));
    expect(out).toEqual({ kind: "not_found", message: expect.stringContaining("manifest not found") });
  });

  it("returns network error on 5xx", async () => {
    const out = await fetchManifest("ignored", mockFetch({ status: 503, body: {} }));
    expect(out).toMatchObject({ kind: "network" });
  });

  it("returns network error when fetch throws", async () => {
    const out = await fetchManifest("ignored", async () => {
      throw new Error("dns boom");
    });
    expect(out).toMatchObject({ kind: "network", message: expect.stringContaining("dns boom") });
  });

  it("returns malformed when the body is not an object", async () => {
    const out = await fetchManifest("ignored", mockFetch({ body: "not-an-object" }));
    expect(out).toMatchObject({ kind: "malformed" });
  });

  it("returns malformed when required fields are missing", async () => {
    const out = await fetchManifest(
      "ignored",
      mockFetch({ body: { $schema: "x", tables: [] } }),
    );
    expect(out).toMatchObject({ kind: "malformed" });
  });

  it("returns schema_version_unsupported when manifest $schema_version is unknown", async () => {
    const bad = { ...goodManifest, $schema_version: "9.9" };
    const out = await fetchManifest("ignored", mockFetch({ body: bad }));
    expect(out).toMatchObject({ kind: "schema_version_unsupported" });
  });
});

describe("lookupTable", () => {
  it("returns the table when id matches and version is compatible", () => {
    const out = lookupTable(goodManifest, "elections.observations", "observation.schema.json");
    expect(out).toMatchObject({ table_id: "elections.observations", format: "parquet" });
  });

  it("returns table_not_found when id is absent (R23 — no fallback)", () => {
    const out = lookupTable(goodManifest, "nope.observations", "observation.schema.json");
    expect(out).toMatchObject({ kind: "table_not_found", table_id: "nope.observations" });
  });

  it("returns schema_version_unsupported when table version is outside compat set", () => {
    const m: Manifest = {
      ...goodManifest,
      tables: [{ ...goodManifest.tables[0], schema_version: "9.9" }],
    };
    const out = lookupTable(m, "elections.observations", "observation.schema.json");
    expect(out).toMatchObject({ kind: "schema_version_unsupported" });
  });

  it("rejects when the row schema file is unknown", () => {
    const out = lookupTable(goodManifest, "elections.observations", "made-up.schema.json");
    expect(out).toMatchObject({ kind: "schema_version_unsupported" });
  });
});
