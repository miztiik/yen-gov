// sources-v2-shape contract test.
//
// Two invariants enforced here that schemas can't enforce on themselves:
//
//   1. **Manifest registration**: `taxonomy.sources` is registered at
//      schema_version "2.0" in `datasets/manifest.json`. Consumers
//      (SourceList v2, ChartFooter, any future view-model) resolve the
//      parquet location via this `table_id` — NEVER a hardcoded
//      `/data/taxonomy/sources.parquet` (R-28).
//
//   2. **v2.0 ledger field discipline**: the on-disk JSON schema at
//      `datasets/schemas/source.schema.json` exposes exactly the v2.0
//      citizen-facing fields and ZERO retired fetch-telemetry fields.
//      `FORBIDDEN_SOURCE_FIELDS` (exported from
//      `frontend/src/lib/source-list-v2/types.ts`) lists everything
//      ADR-0032 P.0e retired — if any of these reappear under any
//      `sources[*].properties.*` path, this test fails loud.
//
// This is the front-end-side mirror of the v2.0 pivot constraint.
// Backend Tier-A pytest covers per-row validation
// (`backend/yen_gov/canonical/citation.py` + its tests); this conform
// test is the consumer-side drift detector that makes sure a future PR
// can't silently regrow `fetched_at` chrome.
//
// Per R-23: the audit pins to the authoring source (the JSON schema +
// the manifest), NOT to a folded JSON projection of the parquet.
// Per R-27: no JSON projections are introduced by this test.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { FORBIDDEN_SOURCE_FIELDS } from "../lib/source-list-v2";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");

// ---------- manifest registration ----------

interface ManifestTable {
  table_id: string;
  family?: string;
  table_name?: string;
  kind?: string;
  format?: string;
  schema_version?: string;
  files?: Array<{ path: string }>;
}

interface Manifest {
  tables: ManifestTable[];
}

const manifest = JSON.parse(
  readFileSync(resolve(repoRoot, "datasets", "manifest.json"), "utf8"),
) as Manifest;

const sourcesEntry: ManifestTable | undefined = manifest.tables.find(
  (t) => t.table_id === "taxonomy.sources",
);

describe("sources-v2 — manifest registration (R-28)", () => {
  it("taxonomy.sources is registered as a manifest table", () => {
    expect(
      sourcesEntry,
      "taxonomy.sources must appear in datasets/manifest.json so consumers can resolve the parquet via table_id (R-28). NEVER hardcode /data/taxonomy/sources.parquet at any call site.",
    ).toBeDefined();
  });

  it("registered at schema_version 2.0 (ADR-0032 P.0e citation ledger)", () => {
    expect(sourcesEntry?.schema_version).toBe("2.0");
  });

  it("registered as parquet format", () => {
    expect(sourcesEntry?.format).toBe("parquet");
  });

  it("registered as kind=taxonomy under family=taxonomy", () => {
    expect(sourcesEntry?.kind).toBe("taxonomy");
    expect(sourcesEntry?.family).toBe("taxonomy");
  });

  it("on-disk parquet path is taxonomy/sources.parquet", () => {
    // The path is for the manifest resolver; consumers must still go
    // through the table_id, not hardcode this path.
    expect(sourcesEntry?.files?.[0]?.path).toBe("taxonomy/sources.parquet");
  });
});

// ---------- schema field discipline ----------

interface JsonSchemaProperty {
  type?: string | string[];
  enum?: string[];
  description?: string;
}

interface SourcesItemSchema {
  type: "object";
  additionalProperties: boolean;
  required: string[];
  properties: Record<string, JsonSchemaProperty>;
}

interface SourcesSchema {
  "x-version": string;
  properties: {
    sources: {
      items: SourcesItemSchema;
    };
  };
}

const sourcesSchema = JSON.parse(
  readFileSync(resolve(repoRoot, "datasets", "schemas", "source.schema.json"), "utf8"),
) as SourcesSchema;

const itemSchema = sourcesSchema.properties.sources.items;

describe("sources-v2 — JSON schema is at x-version 2.0", () => {
  it("schema document is tagged x-version 2.0", () => {
    expect(sourcesSchema["x-version"]).toBe("2.0");
  });

  it("schema rejects unknown properties (additionalProperties: false)", () => {
    expect(itemSchema.additionalProperties).toBe(false);
  });
});

describe("sources-v2 — required field set matches ADR-0032 ledger", () => {
  // Exactly these 8 are required by the v2.0 citation ledger:
  // source_id, producer, title, vintage, license, confidence_tier,
  // is_issuing_authority, verification_method.
  const REQUIRED_V2 = [
    "source_id",
    "producer",
    "title",
    "vintage",
    "license",
    "confidence_tier",
    "is_issuing_authority",
    "verification_method",
  ];

  it("required set equals the v2.0 ledger 8-tuple", () => {
    // Strict equality on the set ensures neither additions nor removals
    // slip in without an ADR amendment + schema bump.
    expect([...itemSchema.required].sort()).toEqual([...REQUIRED_V2].sort());
  });
});

describe("sources-v2 — full property set is the 11-column v2 contract", () => {
  // The full v2 property set: 8 required + 3 optional/nullable.
  const ALLOWED_V2_PROPERTIES = [
    "source_id",
    "producer",
    "title",
    "vintage",
    "license",
    "confidence_tier",
    "is_issuing_authority",
    "verification_method",
    "url_main",
    "citation_full",
    "notes",
  ];

  it("property set equals the v2.0 11-column contract", () => {
    const declared = Object.keys(itemSchema.properties).sort();
    expect(declared).toEqual([...ALLOWED_V2_PROPERTIES].sort());
  });
});

describe("sources-v2 — retired fetch-telemetry fields are gone (R-24)", () => {
  // FORBIDDEN_SOURCE_FIELDS lists every v1.0 fetch-telemetry field that
  // ADR-0032 P.0e moved to .runtime/<adapter>/<source_id>.json sidecars.
  // Any of these reappearing under sources[*].properties.* is a regression
  // that re-introduces the fetched_at-smear anti-pattern (CLAUDE.md §10).
  for (const forbidden of FORBIDDEN_SOURCE_FIELDS) {
    it(`'${forbidden}' is NOT a property of sources[*]`, () => {
      expect(
        itemSchema.properties[forbidden],
        `'${forbidden}' reappeared in datasets/schemas/source.schema.json — ADR-0032 P.0e retired it from the canonical sources contract. It belongs in .runtime/<adapter>/<source_id>.json sidecars only.`,
      ).toBeUndefined();
    });
  }
});

describe("sources-v2 — locked enums match the SourceList v2 types", () => {
  // The frontend types union (`SourceLicense`, `ConfidenceTier`,
  // `VerificationMethod`) must match the schema enums one-to-one — any
  // schema-side enum addition without a frontend type bump is a contract
  // break.

  it("license enum is the locked 6-tuple", () => {
    expect([...(itemSchema.properties.license.enum ?? [])].sort()).toEqual(
      ["OGL-IN-1.0", "CC-BY-4.0", "CC0-1.0", "public-domain", "unknown-public", "internal"].sort(),
    );
  });

  it("confidence_tier enum is gold/silver/bronze", () => {
    expect([...(itemSchema.properties.confidence_tier.enum ?? [])].sort()).toEqual(
      ["gold", "silver", "bronze"].sort(),
    );
  });

  it("verification_method enum is the locked 4-tuple", () => {
    expect([...(itemSchema.properties.verification_method.enum ?? [])].sort()).toEqual(
      ["live-fetch", "archived-snapshot", "transcribed", "editorial"].sort(),
    );
  });
});
