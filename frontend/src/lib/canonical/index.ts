// Canonical store — frontend reader (Phase 0.8).
//
// Per ADR-0030 + docs/architecture/data/canonical-store.md §15. This module
// is the SOLE entry point the frontend uses to read Parquet observations
// through DuckDB-WASM. The legacy JSON loaders in `src/lib/data.ts` stay
// independent during the Phase 0/Phase 1 migration; the two paths never
// cross (D13: rip-and-replace, no strangler-fig in production code).
//
// What lives here:
//   manifest.ts  — fetch + validate datasets/manifest.json (schema-version guard)
//   duckdb.ts    — lazy DuckDB-WASM init + query helper
//   types.ts     — TS shape of Manifest / Table / File entries
//   index.ts     — public re-exports
//
// What does NOT live here (intentionally):
//   view-model loaders (D19) — Phase 1+ once a real chart binds against
//   the canonical store. Keeping this module narrow until then keeps the
//   skeleton honest.

export { fetchManifest, isCompatibleSchemaVersion, lookupTable } from "./manifest";
export type {
  CanonicalFile,
  CanonicalTable,
  Manifest,
  ManifestError,
  TableId,
} from "./types";
export { SUPPORTED_SCHEMA_VERSIONS } from "./types";
