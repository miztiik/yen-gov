// Canonical manifest types. Mirrors datasets/schemas/manifest.schema.json
// item shape; bumps there must update these in the same commit per
// CLAUDE.md §11.

export type TableId = string; // <family>.<table>, e.g. "elections.election_results"

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

/**
 * Informational record of a renamed/relocated artifact so external tooling
 * and archived embeds can find the canonical successor. Hand-curated by
 * the writer when an emit drops a known prior path; the loader/reader
 * never consult this field (it is informational only).
 *
 * Surfaces in manifest v1.2+; absent on v1.0/v1.1 snapshots.
 */
export interface ManifestDeprecation {
  old_path: string;             // POSIX relative under datasets/
  new_path: string;             // MUST match an entry in tables[].files[].path
  deprecated_at: string;        // ISO 8601 date (YYYY-MM-DD)
  removed_at?: string | null;   // ISO 8601 date or null while the legacy file remains
}

export interface Manifest {
  $schema: string;
  $schema_version: string;
  manifest_version: string;
  generated_at: string; // RFC 3339 UTC
  tables: CanonicalTable[];
  deprecations?: ManifestDeprecation[];
}

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
