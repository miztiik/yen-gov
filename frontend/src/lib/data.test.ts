import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchStates,
  fetchResultSummary,
  fetchParties,
  fetchConstituencies,
  fetchDistricts,
  fetchConstituencyResult,
} from "./data";

// All loaders go through `${DATA_BASE}<path>` where DATA_BASE = `${BASE_URL}data`.
// In vitest the default BASE_URL is "/", so DATA_BASE === "/data".
const BASE = "/data";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

let fetchSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchSpy = vi.fn();
  globalThis.fetch = fetchSpy as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchStates", () => {
  it("requests the canonical states reference path and returns parsed JSON", async () => {
    const payload = { country: "IN", states: [] };
    fetchSpy.mockResolvedValueOnce(jsonResponse(payload));
    const out = await fetchStates();
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/reference/in/states.json`);
    expect(out).toEqual(payload);
  });

  it("throws on non-OK response", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("nope", { status: 500, statusText: "Internal" }));
    await expect(fetchStates()).rejects.toThrow(/states\.json failed: 500/);
  });
});

describe("fetchResultSummary / fetchParties", () => {
  it("composes event + state into the per-election path", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));
    await fetchResultSummary("AcGenMay2026", "S22");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/elections/AcGenMay2026/S22/result.summary.json`,
    );
  });

  it("composes event + state for parties.json", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));
    await fetchParties("AcGenMay2026", "S22");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/elections/AcGenMay2026/S22/parties.json`,
    );
  });
});

describe("fetchConstituencies / fetchDistricts", () => {
  it("uses the per-state reference path for constituencies", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));
    await fetchConstituencies("S22");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/reference/in/states/S22/constituencies.json`,
    );
  });

  it("uses the per-state reference path for districts", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));
    await fetchDistricts("S22");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/reference/in/states/S22/districts.json`,
    );
  });
});

describe("fetchConstituencyResult — the 404-as-null contract", () => {
  it("composes event + state + eci_no into the per-AC result path", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ eci_no: 167 }));
    const out = await fetchConstituencyResult("AcGenMay2026", "S22", 167);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/elections/AcGenMay2026/S22/results/167.json`,
    );
    expect(out).toMatchObject({ eci_no: 167 });
  });

  it("returns null on 404 (countermanded / postponed AC — not an error)", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("not found", { status: 404 }));
    const out = await fetchConstituencyResult("AcGenMay2026", "S22", 999);
    expect(out).toBeNull();
  });

  it("throws on other non-OK responses (500, etc.)", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("err", { status: 500, statusText: "Internal" }));
    await expect(fetchConstituencyResult("AcGenMay2026", "S22", 1)).rejects.toThrow(/failed: 500/);
  });
});
