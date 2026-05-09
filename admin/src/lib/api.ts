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

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: (): Promise<{ status: string; version: string }> =>
    getJson("/api/health"),
  inventory: (): Promise<Inventory> => getJson("/api/inventory"),
};
