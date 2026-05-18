// Canonical manifest types. Mirrors datasets/schemas/manifest.schema.json
// item shape; bumps there must update these in the same commit per
// CLAUDE.md §11.

export type TableId = string; // <family>.<table>, e.g. "elections.observations"

export interface CanonicalFile {
  path: string;          // POSIX relative under datasets/
  size_bytes: number;
  row_count?: number | null;
  partition_values?: Record<string, string> | null;
}

export interface CanonicalTable {
  table_id: TableId;
  family: string;
  format: "parquet" | "geojson" | "pmtiles" | "json";
  schema_version: string;      // "<major>.<minor>"
  partition_columns: string[]; // empty when unpartitioned
  files: CanonicalFile[];
  row_count_total?: number | null;
}

export interface Manifest {
  $schema: string;
  $schema_version: string;
  manifest_version: string;
  generated_at: string; // RFC 3339 UTC
  tables: CanonicalTable[];
}

// Reader-side compatibility set. The reader fails loud on any
// schema_version not listed here (canonical-store.md §11.2).
//
// Bump rules: producer (writer) upgrades first; reader follows. To accept
// a new schema_version, add it here in the same commit that ships the
// reader's adaptation logic. NEVER coerce / silently best-effort.
export const SUPPORTED_SCHEMA_VERSIONS: Record<string, ReadonlyArray<string>> = {
  "observation.schema.json": ["1.0", "1.1"],
  "source.schema.json": ["1.0"],
  "entity.schema.json": ["1.0"],
  "indicator-catalogue.schema.json": ["1.0"],
  "operator-state.schema.json": ["1.0"],
  "caveat.schema.json": ["1.0"],
  "methodology-break.schema.json": ["1.0"],
  "facet-axes.schema.json": ["1.0"],
  "manifest.schema.json": ["1.0"],
  "taxonomy-parties.schema.json": ["1.0"],
  "delimitation-lineage.schema.json": ["1.0"],
};

export type ManifestErrorKind =
  | "not_found"
  | "network"
  | "malformed"
  | "schema_version_unsupported"
  | "table_not_found";

export interface ManifestError {
  kind: ManifestErrorKind;
  message: string;
  table_id?: TableId;
}
