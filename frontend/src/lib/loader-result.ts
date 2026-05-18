// D17 — citizen-facing failure-state contract for any async data loader.
//
// Per TODO/20260517-canonical-long-format-pivot.md D17:
//
//   "When DuckDB-WASM init / metadata fetch / partition Range fetch / query
//    execution fails or times out, the page renders plain-language copy
//    ('This data could not load right now') with retry, source/provenance
//    visible where possible, and never a raw stack trace."
//
// Every loader that fronts a citizen surface returns this discriminated
// union. The renderer MUST handle all four arms. `reason` is plain-language
// copy citizens can read — NOT the raw Error message or stack.

export type LoaderStatus = "loading" | "ok" | "partial" | "failed";

export type LoaderResult<T> =
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "partial"; data: T; reason: string }
  | { status: "failed"; reason: string; retry?: () => void };

/**
 * Map a thrown Error from a loader to citizen-readable failure copy.
 *
 * The four classes Phase 0.11 needs to discriminate are documented in D17:
 *   - DuckDB-WASM init  (wasm fetch / instantiate failure)
 *   - metadata fetch    (manifest.json 404/5xx, malformed JSON)
 *   - partition fetch   (parquet file 404/5xx, HTTP Range refusal)
 *   - query execution   (SQL error, schema mismatch, timeout)
 *
 * The copy is intentionally generic and reassuring. The technical reason
 * lands in `console.warn` for the developer; the citizen never sees a stack.
 */
export function describeFailure(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  // Log the raw reason so devs can debug without leaking it to the citizen.
  console.warn("[duckdb-loader] failure:", msg);

  if (/manifest fetch failed/i.test(msg)) {
    return "We could not load the data catalogue right now. Please try again in a moment.";
  }
  if (/table_id not found/i.test(msg)) {
    return "This dataset is not available yet. We are working on it.";
  }
  if (/HTTP\s*(4\d\d|5\d\d)|fetch.*failed|network/i.test(msg)) {
    return "The data file could not be fetched. Check your connection and try again.";
  }
  if (/duckdb|wasm|worker/i.test(msg)) {
    return "We could not start the in-browser database. Please refresh the page.";
  }
  return "This data could not load right now. Please try again.";
}
