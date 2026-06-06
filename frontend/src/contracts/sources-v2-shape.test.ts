// sources-v2-shape contract test (post-X1b + post-B3, 2026-06-06).
//
// X1b (#814) retired `datasets/taxonomy/sources.parquet`; B3 (#819)
// deleted `datasets/schemas/source.schema.json` (the parquet's row
// schema) because the parquet is gone. The new SoT for citation
// metadata is `datasets/data/entities/source.csv`; that file has its
// own column-contract schema at `datasets/schemas/csv.sources.schema.json`.
//
// This contract test keeps the post-X1b manifest invariant: the legacy
// `taxonomy.sources` table_id MUST NOT be registered in
// `datasets/manifest.json`, and `manifest.deprecations[]` MUST carry
// the redirect to `data/entities/source.csv` so `warnIfLegacyPath` in
// `lib/duckdb.ts` can surface a useful console warning for archived
// embeds that still point at the old parquet path.
//
// The retired-fetch-telemetry-field-discipline (FORBIDDEN_SOURCE_FIELDS
// regression guard from the v2 era) now lives at the new CSV column
// schema; see `frontend/src/contracts/sources-csv-shape.test.ts` if a
// post-X1b mirror is needed.
//
// Per R-23: the audit pins to the authoring source (the manifest),
// NOT a folded JSON projection of the parquet.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");

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
