// Unit tests for the canonical Psephlab loader (PR-R.1 / 1.8e MIGRATE).
//
// CLAUDE.md §15 carve-out: the loader's contract IS the duckdb.ts query
// boundary. `vi.mock("../duckdb", ...)` substitutes the IO layer; tests
// pin the SQL composition + result-row assembly into the legacy `Tallies`
// shape. The real DuckDB-WASM round-trip is asserted by Playwright in
// PR-R.2 against a real Parquet shard.
//
// Pattern mirrors `frontend/src/lib/view-models/constituency.test.ts`.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import { __resetForTests, loadActuals } from "./canonical-loaders";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

// Fixture: 2 ACs, 5 candidate rows total, 1 NOTA row per AC.
const constituencyRows = [
  { ac_eci_no: 1, name: "GUMMIDIPOONDI", votes_polled: 222_069 },
  { ac_eci_no: 2, name: "PONNERI (SC)", votes_polled: 198_500 },
];

const candidateRows = [
  // AC 1 — 2 real candidates + 1 NOTA
  {
    ac_eci_no: 1,
    rank: 1,
    name: "GOVINDARAJAN T.J",
    party_eci_code: "1234",
    party_short: "DMK",
    votes: 126_452,
    is_nota: 0,
  },
  {
    ac_eci_no: 1,
    rank: 2,
    name: "PRAKASH M",
    party_eci_code: "742",
    party_short: "PMK",
    votes: 75_514,
    is_nota: 0,
  },
  {
    ac_eci_no: 1,
    rank: null,
    name: "NOTA",
    party_eci_code: null,
    party_short: "NOTA",
    votes: 1_783,
    is_nota: 1,
  },
  // AC 2 — 1 real + 1 NOTA
  {
    ac_eci_no: 2,
    rank: 1,
    name: "INDEPENDENT_CANDIDATE",
    party_eci_code: null, // null party_eci_code → loader should fall back to "IND"
    party_short: "",      // empty short → loader should fall back to "IND"
    votes: 100_000,
    is_nota: 0,
  },
  {
    ac_eci_no: 2,
    rank: null,
    name: "NOTA",
    party_eci_code: null,
    party_short: "NOTA",
    votes: 900,
    is_nota: 1,
  },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
  __resetForTests();
});

describe("loadActuals — happy path", () => {
  it("assembles Tallies in legacy actuals.ts shape", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const t = await loadActuals("AcGenApr2021", "S22");

    expect(t.scope).toEqual({
      country: "IN",
      state: "S22",
      election: "AcGenApr2021",
    });
    expect(t.acs).toHaveLength(2);

    const ac1 = t.acs[0];
    expect(ac1.eci_no).toBe(1);
    expect(ac1.name).toBe("GUMMIDIPOONDI");
    expect(ac1.electorate).toBe(222_069); // votes_polled proxy, matches legacy contract
    expect(ac1.candidates).toHaveLength(3);

    expect(ac1.candidates[0]).toEqual({
      party_eci_code: "1234",
      party_short: "DMK",
      name: "GOVINDARAJAN T.J",
      votes: 126_452,
    });
    expect(ac1.candidates[1]).toEqual({
      party_eci_code: "742",
      party_short: "PMK",
      name: "PRAKASH M",
      votes: 75_514,
    });
    // NOTA candidate: party_eci_code MUST be "NOTA", party_short MUST be "NOTA".
    expect(ac1.candidates[2]).toEqual({
      party_eci_code: "NOTA",
      party_short: "NOTA",
      name: "NOTA",
      votes: 1_783,
    });
  });

  it("falls back to IND when party_eci_code + party_short are missing on a real candidate", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const t = await loadActuals("AcGenApr2021", "S22");
    const ac2 = t.acs[1];
    expect(ac2.candidates[0]).toEqual({
      party_eci_code: "IND",
      party_short: "IND",
      name: "INDEPENDENT_CANDIDATE",
      votes: 100_000,
    });
  });

  it("freezes Tallies + acs to prevent downstream mutation", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const t = await loadActuals("AcGenApr2021", "S22");
    expect(Object.isFrozen(t)).toBe(true);
    expect(Object.isFrozen(t.acs)).toBe(true);
  });

  it("registers all four canonical tables before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    await loadActuals("AcGenApr2021", "S22");

    const registered = mockedRegister.mock.calls.map(c => c[0]).sort();
    expect(registered).toEqual([
      "elections.dim_acs",
      "elections.dim_candidates",
      "elections.dim_parties",
      "elections.election_results",
    ]);
  });
});

describe("loadActuals — caching", () => {
  it("returns the same Promise for repeat (event, state) calls without re-querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const a = loadActuals("AcGenApr2021", "S22");
    const b = loadActuals("AcGenApr2021", "S22");
    expect(a).toBe(b);

    await a;
    // Total query() invocations: 2 (one constituencies, one candidates).
    // The second loadActuals call MUST NOT trigger a third query.
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });

  it("evicts the cache entry when the underlying query rejects", async () => {
    const boom = new Error("duckdb: boom");
    mockedQuery.mockRejectedValueOnce(boom);

    const first = loadActuals("AcGenApr2021", "S22");
    await expect(first).rejects.toThrow("duckdb: boom");

    // Second call must NOT re-use the rejected cached promise — it has
    // to re-issue the query so the caller can retry after fixing the
    // underlying issue. Mirrors the legacy actuals.ts cache.delete on
    // catch.
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const second = await loadActuals("AcGenApr2021", "S22");
    expect(second.acs).toHaveLength(2);
  });
});

describe("loadActuals — SQL composition", () => {
  it("issues separate queries scoped to the requested (event, state)", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    await loadActuals("AcGenMay2026", "S22");

    expect(mockedQuery).toHaveBeenCalledTimes(2);
    const [acSql] = mockedQuery.mock.calls[0];
    const [candSql] = mockedQuery.mock.calls[1];

    // Both queries are scoped — the period_label literal + state_code literal
    // appear in both, escaped exactly once each.
    expect(acSql).toContain("'AcGenMay2026'");
    expect(acSql).toContain("'S22'");
    expect(candSql).toContain("'AcGenMay2026'");
    expect(candSql).toContain("'S22'");

    // AC query selects from dim_acs LEFT JOIN election_results filtering
    // on ac-votes-polled. Candidate query has both the dim_candidates JOIN
    // and the NOTA UNION ALL.
    expect(acSql).toContain("ac-votes-polled");
    expect(candSql).toContain("ac-nota-votes");
    expect(candSql).toContain("UNION ALL");
  });

  it("escapes single quotes inside event / state values to prevent SQL injection at the seam", async () => {
    mockedQuery
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);

    await loadActuals("AcGen'OR'1=1", "S22");

    const [acSql] = mockedQuery.mock.calls[0];
    // Literal must appear with doubled single quote, NOT as a broken-out
    // string.
    expect(acSql).toContain("'AcGen''OR''1=1'");
  });

  it("emits the no-UNK-regression CASE fallback in the candidate SELECT", async () => {
    // PR-R.2 structural fix: when dim_candidates.party_id resolves to the
    // sentinel parties.IN.UNK (long-tail party not yet in canonical
    // taxonomy), the loader must surface the verbatim ECI short from
    // dim_candidates.party_short_raw — never the literal "UNK" — so
    // citizen-visible chips stay honest. Pin the CASE expression so a
    // future refactor that re-introduces a bare `dp.short_name` would
    // fail this test.
    mockedQuery
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);

    await loadActuals("AcGenMay2026", "S22");

    const [, [candSql]] = mockedQuery.mock.calls;
    expect(candSql).toContain("parties.IN.UNK");
    expect(candSql).toContain("dc.party_short_raw");
    expect(candSql).toContain("COALESCE(dc.party_short_raw");
  });
});

describe("loadActuals — empty result", () => {
  it("returns an empty acs[] when canonical store has no rows for (event, state)", async () => {
    mockedQuery
      .mockResolvedValueOnce([]) // no constituencies
      .mockResolvedValueOnce([]); // no candidates

    const t = await loadActuals("AcGenNeverHeld2099", "Z99");
    expect(t.scope).toEqual({
      country: "IN",
      state: "Z99",
      election: "AcGenNeverHeld2099",
    });
    expect(t.acs).toEqual([]);
    // Still frozen — the contract is the Tallies shape, not whether it has rows.
    expect(Object.isFrozen(t)).toBe(true);
  });
});
