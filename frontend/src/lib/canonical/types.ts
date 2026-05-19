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
  // facet-axes.schema.json + delimitation-lineage.schema.json retired in
  // PR-Q.2 (TODO row 1.8d-ii). facet-axes now ships as a parquet emitted
  // from the Python literal in backend/yen_gov/canonical/facet_axes_seed.py;
  // delimitation-lineage placeholder removed pending real authoring.
  "manifest.schema.json": ["1.0", "1.1", "1.2"],
  "taxonomy-parties.schema.json": ["1.0"],
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
