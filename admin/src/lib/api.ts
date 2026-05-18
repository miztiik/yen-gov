// Thin fetch wrapper for the local FastAPI surface. Same-origin in
// dev (vite proxies /api → 127.0.0.1:8000); same-origin in any future
// bundled-with-uvicorn deployment.
//
// Types are hand-written for now. When the surface grows beyond a
// handful of endpoints, swap in `openapi-typescript` codegen against
// http://127.0.0.1:8000/openapi.json (FastAPI emits it for free).

export interface ProvenanceSource {
  url: string;
  fetched_at: string;
}

/**
 * Family-agnostic inventory of the canonical Parquet store.
 *
 * Backend walks every `datasets/*.parquet` and `datasets/<family>/*.parquet`,
 * surfaces one `InventoryStore` per file, and rolls every fact-table
 * parquet up into `InventoryIndicator[]`. Election-specific (event ×
 * state) drill-downs are NOT in this surface — those belong to a future
 * family-specific panel; the generic inventory stays generic so the day
 * energy / demography / fiscal / health ship their own fact-table
 * parquet (per-family stem, e.g. `elections/election_results.parquet`),
 * they appear here automatically.
 */
export interface InventoryStoreStats {
  indicators: number;
  entities: number;
  periods: number;
  min_year: number | null;
  max_year: number | null;
  sources: number;
}

export interface InventoryStore {
  /** Top-level directory under `datasets/` (e.g. `elections`, `taxonomy`). */
  family: string;
  /** `observations` | `dim` | `taxonomy` | `other`. */
  kind: "observations" | "dim" | "taxonomy" | "other";
  /** Repo-relative POSIX path. */
  path: string;
  size_bytes: number;
  mtime: string;
  row_count: number | null;
  /** Populated only for `kind === "observations"`. */
  stats: InventoryStoreStats | null;
  /** Set when DuckDB rejects the file (corrupt / unreadable). */
  error?: string;
}

export interface InventoryIndicator {
  family: string;
  indicator_id: string;
  obs_count: number;
  entity_count: number;
  period_count: number;
  min_year: number | null;
  max_year: number | null;
}

export interface Inventory {
  generated_at: string;
  stores: InventoryStore[];
  indicators: InventoryIndicator[];
}

export interface SchemaIssue {
  file: string;
  message: string;
}

export interface SchemaChangelogEntry {
  version: string;
  date: string;
  description: string;
}

export interface SchemaInfo {
  id: string;
  title: string | null;
  x_version: string | null;
  last_changelog: SchemaChangelogEntry | null;
  meta_ok: boolean;
  meta_errors: SchemaIssue[];
  data_files: number;
  data_failing_files: number;
  data_failures: SchemaIssue[];
}

export interface SchemasReport {
  schemas: SchemaInfo[];
  orphan_failures: SchemaIssue[];
  summary: {
    total_schemas: number;
    meta_failing: number;
    data_failing_files: number;
    orphan_files: number;
  };
}

export interface PipelineRunSummary {
  run_id: string;
  started_at: string;
  has_console_log: boolean;
  has_structured_log: boolean;
  command: string | null;
  exit_code: number | null;
  status: "ok" | "failed" | "running" | "unknown";
}

export interface PipelineRunsResponse {
  runs: PipelineRunSummary[];
  total: number;
  active: Record<string, unknown> | null;
  allowed_commands: Record<string, string>;
}

export interface PipelineRunDetail {
  run_id: string;
  status: "ok" | "failed" | "running" | "unknown";
  meta: Record<string, unknown>;
  console_tail: string[];
  structured_tail: Record<string, unknown>[];
}

export interface TriggerRequest {
  command:
    | "validate"
    | "run"
    | "reference"
    | "ingest-energy-power-plants"
    | "ingest-fiscal-rbi"
    | "eci-statreport"
    | "eci-statreport-emit";
  args: string[];
  confirm: true;
}

// ---------- Indicators inventory ----------

export interface IndicatorIndexRow {
  id: string;
  topic: string;
  path: string;
  title: string;
  documentation_status: "stub" | "partial" | "authored";
  inventory_status: "empty" | "partial" | "complete";
  frozen: boolean;
  last_polled_at: string | null;
  observed_count: number;
  pending_count: number;
  unavailable_count: number;
  // Structured temporal range (schema v2.0, all optional).
  min_time?: string;
  max_time?: string;
  min_period_label?: string;
  max_period_label?: string;
  observed_periods_within_range?: number;
  gap_count_within_range?: number;
  time_grain?: string;
  cadence?:
    | "annual_cy"
    | "annual_fy"
    | "quarterly_cy"
    | "quarterly_fy"
    | "monthly"
    | "weekly"
    | "daily"
    | "decennial"
    | "ad_hoc";
}

export interface IndicatorsInventoryResponse {
  $schema: string | null;
  $schema_version: string | null;
  generated_at: string | null;
  index_mtime: string;
  count: number;
  indicators: IndicatorIndexRow[];
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail ?? ""; } catch { /* */ }
    throw new Error(`POST ${path} → ${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: (): Promise<{ status: string; version: string }> =>
    getJson("/api/health"),
  inventory: (): Promise<Inventory> => getJson("/api/inventory"),
  schemas: (): Promise<SchemasReport> => getJson("/api/schemas"),
  pipelineRuns: (): Promise<PipelineRunsResponse> => getJson("/api/pipeline/runs"),
  pipelineRun: (run_id: string): Promise<PipelineRunDetail> =>
    getJson(`/api/pipeline/runs/${encodeURIComponent(run_id)}`),
  triggerPipeline: (req: TriggerRequest): Promise<{ run_id: string; meta: Record<string, unknown> }> =>
    postJson("/api/pipeline/runs", req),

  // Indicators inventory
  indicators: (): Promise<IndicatorsInventoryResponse> =>
    getJson("/api/inventory/indicators"),
};
