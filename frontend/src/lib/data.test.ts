import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchStates,
  fetchConstituencies,
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

  // fetchDistricts retired in Phase-0 closeout T.0c-ii-B.2 — the district
  // list now flows through `view-models/districts.ts` against the
  // canonical `taxonomy.entities` table via DuckDB-WASM. Coverage lives
  // in `view-models/districts.test.ts`. The hand-authored
  // `datasets/reference/in/states/<S>/districts.json` files remain on
  // disk as curator input feeding `entities.parquet`.
  it.skip("legacy fetcher replaced by view-model loader", () => {});
});

describe("fetchConstituencyResult — moved to view-model loader", () => {
  // PR-E (Phase 1.3a) retired the per-shard JSON loader. The Constituency
  // route now reads through `lib/view-models/constituency.ts` against the
  // canonical Parquet store via DuckDB-WASM. Unit coverage lives in
  // `view-models/constituency.test.ts`; the 404-as-null contract is now
  // a "zero candidate rows → partial / not_published" SQL-shape contract.
  it.skip("legacy contract replaced by view-model loader", () => {});
});

describe("fetchPartyRegistry — deleted in PR-R.3 (Phase 1.8e)", () => {
  // The central party registry overlay (reference/in/parties.json +
  // parties-discovered.json) was retired in PR-R.3. The canonical roster
  // now lives at datasets/taxonomy/parties.json and is consumed by the
  // backend party-lookup adapter; the frontend reads party metadata
  // through view-model loaders (dim_parties + dim_party_alliances) over
  // DuckDB-WASM, not via a separate JSON-fetch path.
  it.skip("legacy fetcher replaced by canonical taxonomy + view-model loaders", () => {});
});

describe("fetchPersonEntity / slugifyCandidate — deleted in PR-S.2 (Phase 1.8f)", () => {
  // Per-candidate JSON sidecars under datasets/people/<event>/<ac>/<slug>.json
  // (3,983 files) and the people.entity.schema.json contract were retired
  // in PR-S.2. Biographic fields (sex/age/education/profession/
  // constituency_type/party_type) are now columns on dim_candidates.parquet
  // (schema v1.2) and surface via `loadConstituencyResult` ->
  // `CandidateResult.bio`. The view-model unit suite
  // (view-models/constituency.test.ts) covers the SQL projection; the
  // Constituency route exercises the render path.
  it.skip("legacy fetcher + slug helper replaced by canonical dim_candidates bio columns", () => {});
});

