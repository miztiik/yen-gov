// Manifest fetch + validate. Frontend's first network operation in any
// canonical-store-backed session is `GET manifest.json`. If it 404s,
// times out, or fails schema-version check, every downstream view-model
// emits LoaderResult.failed (R23 — no path-guessing fallback).

import type { Manifest, ManifestError, TableId, CanonicalTable } from "./types";
import { SUPPORTED_SCHEMA_VERSIONS } from "./types";

const DEFAULT_MANIFEST_URL = "datasets/manifest.json";

export async function fetchManifest(
  url: string = DEFAULT_MANIFEST_URL,
  fetchImpl: typeof fetch = fetch,
): Promise<Manifest | ManifestError> {
  let response: Response;
  try {
    response = await fetchImpl(url);
  } catch (e) {
    return { kind: "network", message: `network error fetching ${url}: ${(e as Error).message}` };
  }
  if (response.status === 404) {
    return { kind: "not_found", message: `manifest not found at ${url}` };
  }
  if (!response.ok) {
    return { kind: "network", message: `HTTP ${response.status} on ${url}` };
  }
  let doc: unknown;
  try {
    doc = await response.json();
  } catch (e) {
    return { kind: "malformed", message: `manifest is not valid JSON: ${(e as Error).message}` };
  }
  return parseManifest(doc);
}

export function parseManifest(doc: unknown): Manifest | ManifestError {
  if (!doc || typeof doc !== "object") {
    return { kind: "malformed", message: "manifest is not an object" };
  }
  const m = doc as Partial<Manifest>;
  if (typeof m.$schema !== "string" || typeof m.$schema_version !== "string") {
    return { kind: "malformed", message: "manifest missing $schema or $schema_version" };
  }
  if (typeof m.manifest_version !== "string" || typeof m.generated_at !== "string") {
    return { kind: "malformed", message: "manifest missing manifest_version or generated_at" };
  }
  if (!Array.isArray(m.tables)) {
    return { kind: "malformed", message: "manifest.tables is not an array" };
  }
  // Cross-check the manifest's own $schema_version against the reader's
  // compatibility set. A mismatch here means the control plane itself is
  // unreadable; no individual table check would help.
  if (!isCompatibleSchemaVersion("manifest.schema.json", m.$schema_version)) {
    return {
      kind: "schema_version_unsupported",
      message: `manifest schema_version ${m.$schema_version} not in reader's supported set ${
        SUPPORTED_SCHEMA_VERSIONS["manifest.schema.json"].join(", ")
      }`,
    };
  }
  return m as Manifest;
}

export function isCompatibleSchemaVersion(schemaFile: string, version: string): boolean {
  const supported = SUPPORTED_SCHEMA_VERSIONS[schemaFile];
  if (!supported) return false;
  return supported.includes(version);
}

// Resolve a table by id. Returns ManifestError if absent (R23 — no
// fallback path-guessing) OR if the table's schema_version is outside
// the reader's compatible set (canonical-store.md §11.2 — fail loud).
export function lookupTable(
  manifest: Manifest,
  tableId: TableId,
  rowSchemaFile: string,
): CanonicalTable | ManifestError {
  const table = manifest.tables.find((t) => t.table_id === tableId);
  if (!table) {
    return { kind: "table_not_found", message: `no table '${tableId}' in manifest`, table_id: tableId };
  }
  if (!isCompatibleSchemaVersion(rowSchemaFile, table.schema_version)) {
    return {
      kind: "schema_version_unsupported",
      message: `table '${tableId}' schema_version ${table.schema_version} not in reader's supported set`,
      table_id: tableId,
    };
  }
  return table;
}
