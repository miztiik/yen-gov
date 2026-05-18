import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchStates,
  fetchConstituencies,
  fetchDistricts,
  fetchPartyRegistry,
  fetchPersonEntity,
  slugifyCandidate,
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

describe("fetchParties — deleted in PR-H (Phase 1.3d)", () => {
  // Party.svelte now derives party_meta (recognition + alliance) from
  // loadStateOverview's PartyTotals, which JOINs dim_parties +
  // dim_party_alliances. The per-event parties.json shard is no longer
  // consumed by any frontend surface.
  it.skip("legacy fetcher replaced by canonical view-model", () => {});
});

describe("fetchResultSummary — moved to view-model loader", () => {
  // PR-G (Phase 1.3c) retired the per-shard JSON loader. StateOverview,
  // Party, ElectionSeatsTrend, IndiaMap all read through view-model loaders
  // in `lib/view-models/` against the canonical Parquet store via
  // DuckDB-WASM. The `result.summary.json` shards under datasets/_old/ are
  // read-only legacy projections, slated for deletion in Phase 1.8.
  it.skip("legacy contract replaced by view-model loaders", () => {});
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

describe("fetchConstituencyResult — moved to view-model loader", () => {
  // PR-E (Phase 1.3a) retired the per-shard JSON loader. The Constituency
  // route now reads through `lib/view-models/constituency.ts` against the
  // canonical Parquet store via DuckDB-WASM. Unit coverage lives in
  // `view-models/constituency.test.ts`; the 404-as-null contract is now
  // a "zero candidate rows → partial / not_published" SQL-shape contract.
  it.skip("legacy contract replaced by view-model loader", () => {});
});

describe("fetchPartyRegistry — master + discovered merge", () => {
  function masterFile(parties: unknown[]): unknown {
    return {
      $schema: "https://yen-gov.github.io/schemas/parties-master.schema.json",
      $schema_version: "1.0",
      sources: [],
      parties,
    };
  }
  function discoveredFile(parties: unknown[]): unknown {
    return {
      $schema: "https://yen-gov.github.io/schemas/parties-discovered.schema.json",
      $schema_version: "1.0",
      sources: [],
      parties,
    };
  }

  it("hits both reference paths in parallel", async () => {
    fetchSpy.mockImplementation(() => Promise.resolve(jsonResponse(masterFile([]))));
    await fetchPartyRegistry();
    const calls = fetchSpy.mock.calls.map(c => c[0]);
    expect(calls).toContain(`${BASE}/reference/in/parties.json`);
    expect(calls).toContain(`${BASE}/reference/in/parties-discovered.json`);
  });

  it("master wins over discovered for the same short_name", async () => {
    fetchSpy
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(masterFile([
        { short_name: "INC", full_name: "Indian National Congress", eci_code: "742", recognition: "national" },
      ]))))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(discoveredFile([
        { short_name: "INC", full_name: "INDIAN NATIONAL CONGRESS", eci_code: null,
          recognition: "unknown",
          first_seen: { election_id: "AcGenMay2026", state_code: "S22" },
          sources: [{ url: "https://x/y", fetched_at: "2026-05-12T10:00:00Z" }] },
      ]))));
    const reg = await fetchPartyRegistry();
    expect(reg.byShort.INC.source).toBe("master");
    expect(reg.byShort.INC.full_name).toBe("Indian National Congress");
    expect(reg.byShort.INC.recognition).toBe("national");
    expect(reg.byEciCode["742"].short_name).toBe("INC");
  });

  it("master aliases resolve to the canonical entry", async () => {
    fetchSpy
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(masterFile([
        { short_name: "AIADMK", full_name: "All India Anna Dravida Munnetra Kazhagam",
          eci_code: "201", recognition: "state", recognized_in_states: ["S22"],
          aliases: ["ADMK"] },
      ]))))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(discoveredFile([]))));
    const reg = await fetchPartyRegistry();
    expect(reg.byShort.AIADMK).toBe(reg.byShort.ADMK);
    expect(reg.byShort.ADMK.eci_code).toBe("201");
  });

  it("discovered-only entries surface with recognition='unknown' and source='discovered'", async () => {
    fetchSpy
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(masterFile([]))))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(discoveredFile([
        { short_name: "ZPM", full_name: "Zoram People's Movement", eci_code: null,
          recognition: "unknown",
          first_seen: { election_id: "AcGenNov2023", state_code: "S17" },
          sources: [{ url: "https://x/s3.xlsx", fetched_at: "2026-05-12T10:00:00Z" }] },
      ]))));
    const reg = await fetchPartyRegistry();
    expect(reg.byShort.ZPM.source).toBe("discovered");
    expect(reg.byShort.ZPM.recognition).toBe("unknown");
    expect(reg.byShort.ZPM.eci_code).toBeNull();
  });

  it("404 on either file degrades gracefully", async () => {
    fetchSpy
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(masterFile([
        { short_name: "INC", full_name: "Indian National Congress", eci_code: "742", recognition: "national" },
      ]))))
      .mockImplementationOnce(() => Promise.resolve(new Response("nope", { status: 404 })));
    const reg = await fetchPartyRegistry();
    expect(reg.byShort.INC.short_name).toBe("INC");
  });

  it("alias does not overwrite an existing real short_name", async () => {
    // If two master entries collide via an alias, the real short_name wins.
    fetchSpy
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(masterFile([
        { short_name: "DMK", full_name: "Dravida Munnetra Kazhagam", eci_code: "582",
          recognition: "state", recognized_in_states: ["S22"] },
        { short_name: "AIADMK", full_name: "AIADMK Full",
          eci_code: "201", recognition: "state", recognized_in_states: ["S22"],
          aliases: ["DMK"] }, // pathological but possible
      ]))))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(discoveredFile([]))));
    const reg = await fetchPartyRegistry();
    expect(reg.byShort.DMK.eci_code).toBe("582"); // canonical, not the alias hijack
  });
});

describe("slugifyCandidate — mirrors backend people_panel.slugify", () => {
  it("ASCII-folds, lowercases, collapses non-alphanumerics to hyphens", () => {
    expect(slugifyCandidate("GOVINDARAJAN T.J")).toBe("govindarajan-t-j");
    expect(slugifyCandidate("Dr. A. P. J. Abdul Kalam")).toBe("dr-a-p-j-abdul-kalam");
    expect(slugifyCandidate("José Ñoño")).toBe("jose-nono");
    expect(slugifyCandidate("USHA")).toBe("usha");
  });
});

describe("fetchPersonEntity — the 404-as-null contract", () => {
  it("composes election + ac_code + slug into the people sidecar path", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ candidate_slug: "govindarajan-t-j" }));
    const out = await fetchPersonEntity("AcGenApr2021", 1, "govindarajan-t-j");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/people/AcGenApr2021/1/govindarajan-t-j.json`,
    );
    expect(out).toMatchObject({ candidate_slug: "govindarajan-t-j" });
  });

  it("returns null on 404 (candidate has no biographic sidecar yet)", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("not found", { status: 404 }));
    const out = await fetchPersonEntity("AcGenApr2021", 1, "nobody");
    expect(out).toBeNull();
  });

  it("throws on other non-OK responses", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("err", { status: 500, statusText: "Internal" }));
    await expect(
      fetchPersonEntity("AcGenApr2021", 1, "x"),
    ).rejects.toThrow(/failed: 500/);
  });
});

