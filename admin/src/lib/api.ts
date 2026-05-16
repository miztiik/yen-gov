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

export interface InventoryCellSummary {
  schema_version?: string | null;
  sources?: ProvenanceSource[];
  total_seats?: number | null;
  path?: string;
  mtime?: string;
  error?: string;
}

export interface InventoryCell {
  event: string;
  state: string;
  summary: InventoryCellSummary | null;
  parties: string | null;
  sqlite: string | null;
  ac_results: {
    found: number;
    expected: number | null;
    missing: number | null;
  };
}

export interface Inventory {
  events: string[];
  /** ECI code → display name (e.g. S22 → "Tamil Nadu"). */
  states: Record<string, string>;
  cells: InventoryCell[];
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

// ---------- ECI Recon ----------

export interface EciHit {
  id: number;
  kind: "hit";
  cat_name: string;
  index_name: string;
  index_url: string;
  title_headline: string;
}
export interface EciMissOrError {
  id: number;
  kind: "miss" | "error";
  error?: string;
}
export type EciProbe = EciHit | EciMissOrError;

export interface EciSweepResult {
  available?: boolean;
  ts: string;
  range: [number, number];
  hits: EciHit[];
  misses: number[];
  errors: { id: number; error: string }[];
}

export interface EciPinEntry {
  state: string;
  year: number;
  category_id: number;
  cat_name: string;
  confirmed_at: string;
  notes?: string;
}

export interface EciPinsResponse {
  payload: {
    $schema: string;
    $schema_version: string;
    sources: ProvenanceSource[];
    pins: EciPinEntry[];
  };
  path: string;
  schema_id: string;
  loaded_in_process: { state: string; year: number; category_id: number }[];
  events: { state: string; year: number; event_id: string; has_partywise: boolean }[];
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
  last_collected_at: string | null;
  observed_count: number;
  pending_count: number;
  unavailable_count: number;
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

  // ECI Recon
  eciLastSweep: (): Promise<EciSweepResult & { available: boolean }> =>
    getJson("/api/eci/recon/last-sweep"),
  eciSweep: (start: number, end: number, sleep_ms = 300): Promise<EciSweepResult> =>
    postJson("/api/eci/recon/sweep", { start, end, sleep_ms }),
  eciProbe: (id: number): Promise<EciProbe> =>
    getJson(`/api/eci/recon/probe/${id}`),
  eciCompare: (a: number, b: number): Promise<{ a: EciProbe; b: EciProbe }> =>
    postJson("/api/eci/recon/compare", { a, b }),
  eciPins: (): Promise<EciPinsResponse> => getJson("/api/eci/pins"),
  eciUpsertPin: (entry: Omit<EciPinEntry, "confirmed_at"> & { confirmed_at?: string; notes?: string }): Promise<{ replaced: boolean; entry: EciPinEntry; total_pins: number }> =>
    postJson("/api/eci/pins", { ...entry, confirm: true }),
  eciDeletePin: (state: string, year: number): Promise<{ removed: boolean; total_pins: number }> =>
    postJson("/api/eci/pins/delete", { state, year, confirm: true }),

  // Indicators inventory
  indicators: (): Promise<IndicatorsInventoryResponse> =>
    getJson("/api/inventory/indicators"),
};
