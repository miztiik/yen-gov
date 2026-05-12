// Contract tests for the admin app's FastAPI client.
//
// `api.ts` is the only piece of admin code that crosses a process
// boundary. We mock `globalThis.fetch` (allowed under CLAUDE.md Holy
// Law #7 because the boundary IS the contract — testing it without the
// mock would just be testing FastAPI). The test fixtures mirror the
// shape FastAPI returns; if the real backend ever drifts, a thin
// integration test (admin/e2e/) will catch it. We intentionally do NOT
// re-test deep response semantics here — that's the FastAPI test
// suite's job (backend/tests/test_admin_*.py).

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { api, type Inventory } from "./api";

interface FetchCall { url: string; init?: RequestInit }

function installFetchMock(factory: (call: FetchCall) => { ok: boolean; status?: number; statusText?: string; json: () => Promise<unknown> }) {
  const calls: FetchCall[] = [];
  const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const call = { url, init };
    calls.push(call);
    return factory(call) as unknown as Response;
  });
  globalThis.fetch = fetchSpy as unknown as typeof fetch;
  return { calls };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api.health", () => {
  test("GETs /api/health and returns parsed body", async () => {
    const { calls } = installFetchMock(() => ({
      ok: true,
      json: async () => ({ status: "ok", version: "0.0.1" }),
    }));
    const out = await api.health();
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/health");
    expect(out).toEqual({ status: "ok", version: "0.0.1" });
  });

  test("throws on non-2xx response with status in message", async () => {
    installFetchMock(() => ({ ok: false, status: 500, statusText: "Internal Server Error", json: async () => ({}) }));
    await expect(api.health()).rejects.toThrow(/GET \/api\/health failed: 500/);
  });
});

describe("api.inventory", () => {
  test("returns the cells array as-is", async () => {
    const fixture: Inventory = {
      events: ["AcGenMay2026"],
      states: { S22: "Tamil Nadu" },
      cells: [{
        event: "AcGenMay2026", state: "S22",
        summary: { total_seats: 234, schema_version: "5.0", path: "datasets/elections/AcGenMay2026/S22/result.summary.json", mtime: "2026-05-01T00:00:00Z" },
        parties: "datasets/elections/AcGenMay2026/S22/parties.json",
        sqlite: "datasets/elections/AcGenMay2026/S22/results.sqlite",
        ac_results: { found: 234, expected: 234, missing: 0 },
      }],
    };
    installFetchMock(() => ({ ok: true, json: async () => fixture }));
    const out = await api.inventory();
    expect(out.events).toEqual(["AcGenMay2026"]);
    expect(out.cells[0].ac_results.missing).toBe(0);
  });
});

describe("api.triggerPipeline", () => {
  test("POSTs JSON body and parses run_id", async () => {
    const { calls } = installFetchMock(() => ({
      ok: true,
      json: async () => ({ run_id: "20260512-001", meta: {} }),
    }));
    const out = await api.triggerPipeline({ command: "validate", args: [], confirm: true });
    expect(calls[0].url).toBe("/api/pipeline/runs");
    expect(calls[0].init?.method).toBe("POST");
    expect(calls[0].init?.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({ command: "validate", args: [], confirm: true });
    expect(out.run_id).toBe("20260512-001");
  });

  test("propagates FastAPI detail string in error message", async () => {
    installFetchMock(() => ({
      ok: false, status: 422, statusText: "Unprocessable Entity",
      json: async () => ({ detail: "command 'rm -rf /' is not allowed" }),
    }));
    // The mock above would only match if api.triggerPipeline's command type
    // accepted arbitrary strings. We test the error-shaping path with a
    // legitimate command that the server happens to reject.
    await expect(api.triggerPipeline({ command: "validate", args: [], confirm: true }))
      .rejects.toThrow(/422.*command 'rm -rf \/' is not allowed/);
  });
});

describe("api.eciUpsertPin", () => {
  test("auto-injects confirm: true alongside pin entry", async () => {
    const { calls } = installFetchMock(() => ({
      ok: true,
      json: async () => ({ replaced: false, entry: { state: "S22", year: 2026, category_id: 1, cat_name: "AC", confirmed_at: "2026-05-12T00:00:00Z" }, total_pins: 1 }),
    }));
    await api.eciUpsertPin({ state: "S22", year: 2026, category_id: 1, cat_name: "AC" });
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.confirm).toBe(true);
    expect(body.state).toBe("S22");
  });
});
