// sources-v2-shape contract test.
//
// Two invariants enforced here that schemas can't enforce on themselves:
//
//   1. **Manifest registration**: `taxonomy.sources` is registered at
//      the current source schema version in `datasets/manifest.json`
//      (ADR-0042 bumped v2.0 -> v3.0 to add the `vintage: minLength: 1`
//      constraint).
//      Consumers (SourceList v2, ChartFooter, any future view-model)
//      resolve the parquet location via this `table_id` — NEVER a
//      hardcoded `/data/taxonomy/sources.parquet` (R-28).
//
//   2. **v2.0 ledger field discipline** (carried forward to v3.0): the
//      on-disk JSON schema at `datasets/schemas/source.schema.json`
//      exposes exactly the v2.0 citizen-facing fields and ZERO retired
//      fetch-telemetry fields. `FORBIDDEN_SOURCE_FIELDS` (exported from
//      `frontend/src/lib/source-list-v2/types.ts`) lists everything
//      ADR-0032 P.0e retired — if any of these reappear under any
//      `sources[*].properties.*` path, this test fails loud. v3.0 only
//      tightens vintage; it does not introduce or retire any fields.
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

const sourcesDeprecation: { old_path: string; new_path: string; deprecated_at: string } | undefined =
  (manifest as unknown as { deprecations?: Array<{ old_path: string; new_path: string; deprecated_at: string }> })
    .deprecations
    ?.find((d) => d.old_path === "taxonomy/sources.parquet");

describe("sources-v2 - manifest registration (R-28; X1b PARTIAL retired)", () => {
  // X1b (PR #814, 2026-06-06) retired taxonomy/sources.parquet from disk
  // and pruned its manifest entry. The current contract is:
  //   - taxonomy.sources MUST NOT be a manifest table (sourcesEntry =
  //     undefined; assertable here so a future agent that re-emits the
  //     parquet fails loud).
  //   - The deprecations[] array MUST carry a row pointing
  //     `taxonomy/sources.parquet` at the CSV replacement
  //     `data/entities/source.csv` so archived embeds get a useful
  //     console warning (warnIfLegacyPath in lib/duckdb.ts).
  //   - Frontend consumption is via the `registerCsvAsTable('taxonomy.sources')`
  //     seam in lib/duckdb.ts (X1a #809) which projects the parquet
  //     column shape from the new CSV file.
  it("taxonomy.sources is NOT a manifest table post-X1b", () => {
    expect(
      sourcesEntry,
      "taxonomy.sources was retired in X1b on 2026-06-06; re-registering it would re-introduce a deleted parquet. Consumers must use registerCsvAsTable('taxonomy.sources') (lib/duckdb.ts) which projects the parquet column shape from data/entities/source.csv.",
    ).toBeUndefined();
  });

  it("manifest deprecations[] carries the taxonomy/sources.parquet -> CSV redirect", () => {
    expect(
      sourcesDeprecation,
      "manifest.json deprecations[] MUST carry a row mapping taxonomy/sources.parquet -> data/entities/source.csv so warnIfLegacyPath in lib/duckdb.ts can surface a useful console warning for archived embeds.",
    ).toBeDefined();
    expect(sourcesDeprecation?.new_path).toBe("data/entities/source.csv");
    expect(sourcesDeprecation?.deprecated_at).toBe("2026-06-06");
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

describe("sources-v2 — JSON schema is at x-version 3.0", () => {
  it("schema document is tagged x-version 3.0 (ADR-0042 vintage-as-period-anchor)", () => {
    // ADR-0042 bumped the source schema from v2.0 to v3.0; the only
    // semantic change is `vintage: minLength: 1`. Field set is identical
    // to v2.0, so the rest of this contract continues to hold under v3.
    expect(sourcesSchema["x-version"]).toBe("3.0");
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
