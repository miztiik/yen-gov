// Unit + golden-row tests for the generic `loadElectionResults(scope)`
// view-model (PR-W2b, 2026-06-10).
//
// Per CLAUDE.md section 15 + parent plan section 22.4 #4: the loader's
// contract IS the SQL boundary. We mock `query` / `registerCsvFile` /
// `registerCsvAsTable` (the explicit carve-out from Holy Law #7) and
// pin:
//
//   - body dispatch         - event prefix infers `pc` vs `ac` body;
//                             invalid scope combinations throw.
//   - scope dispatch        - NATIONAL-PC vs STATE-AC vs CONSTITUENCY
//                             runs the right query count + paths.
//   - projection helpers    - `projectAsWinnersByEntity` filters,
//                             `projectAsConstituencyRanks` sorts.
//   - GOLDEN-ROW ORACLE     - for the same underlying mock row-set, the
//                             generic loader (after projection +
//                             shape-mapping) produces byte-equal output
//                             to the surviving bespoke loader:
//                               loadConstituencyResult({event, state, eci_no})
//                                 (kept under view-models/legacy/ per
//                                  PR-W5a; sole non-trivial bespoke that
//                                  the W2b generic does not yet cover
//                                  end-to-end — bio + symbol +
//                                  margin_votes + NOTA-split + top-N).
//
// PR-W5a (2026-06-10): the `{event}` and `{event, state}` golden-row
// blocks retired with their bespoke counterparts (`loadNationalPcWinners`
// + `loadStateAcWinners`); the W3/W4 call-sites all flipped to
// `loadElectionResults` so the bespoke loaders had no remaining live
// consumers.
//
// The bespoke `loadIndiaLeadingParties` is INTENTIONALLY OUT OF SCOPE
// for this PR per the plan-doc (different underlying table, multi-event
// map input shape, party-aggregate question). It now lives under
// view-models/legacy/ as well; see the module-doc on
// `election-results.ts`.

import { beforeEach, describe, expect, it, vi } from "vitest";

// Shared mock seam (the CLAUDE.md section 15 carve-out for canonical-store
// loaders). Both the generic and bespoke loaders import from
// `../duckdb`; the same mocked module backs both.
vi.mock("../duckdb", () => ({
  registerCsvFile: vi.fn(async () => undefined),
  registerCsvAsTable: vi.fn(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "noop",
  ),
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

import {
  query,
  registerCsvAsTable,
  registerCsvFile,
} from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  bodyFromEvent,
  loadElectionResults,
  projectAsConstituencyRanks,
  projectAsWinnersByEntity,
  type ElectionResultRow,
} from "./election-results";
import { loadConstituencyResult } from "./legacy/constituency";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsv = vi.mocked(registerCsvFile);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedClause = vi.mocked(csvColumnsClause);

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegisterCsv.mockReset();
  mockedRegisterCsvAsTable.mockReset();
  mockedClause.mockReset();
  mockedRegisterCsv.mockResolvedValue(undefined);
  mockedRegisterCsvAsTable.mockImplementation(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "noop",
  );
  mockedClause.mockResolvedValue("columns={MOCKED}");
});

// --------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------

// PR-W5a (2026-06-10): PC_FIXTURE / AC_FIXTURE retired with the two
// matching golden-row oracle blocks (`{event}` + `{event, state}`).
// The CONSTITUENCY-scope oracle below uses its own fixture pair.

// Constituency-scope fixture carries BOTH generic and bespoke aliases:
//   generic: entity_id, entity_name, party_id, party_short, symbol_asset_path
//   bespoke: ac_id, constituency_name, party_id_raw, dp_short_name, election_symbol_asset_path
// Each loader reads the subset its SQL projects; the other keys are ignored.
const CONSTITUENCY_CANDIDATES_FIXTURE = [
  {
    // generic aliases
    entity_id: "IN-AC-2008-tamil-nadu-4062",
    entity_name: "GUMMIDIPOONDI",
    party_id: "parties.IN.DMK",
    party_short: "DMK",
    symbol_asset_path: "party-symbols/rising-sun.svg",
    // bespoke aliases (constituency.ts CandidateRow keys)
    ac_id: "IN-AC-2008-tamil-nadu-4062",
    constituency_name: "GUMMIDIPOONDI",
    party_id_raw: "parties.IN.DMK",
    dp_short_name: "DMK",
    election_symbol_asset_path: "party-symbols/rising-sun.svg",
    party_full: "Dravida Munnetra Kazhagam",
    result: "won",
    sex: "M",
    education: "10th Pass",
    profession: null,
    candidate_type: "challenger",
    source_id: null,
    // shared
    state_slug: "tamil-nadu",
    eci_no: 167,
    delim_year: 2008,
    candidate_name: "GOVINDARAJAN T.J",
    party_eci_code: "1234",
    party_short_raw: "DMK",
    brand_colour_hex: "#ff0000",
    brand_colour_confidence: "high",
    position: 1,
    votes: 126_452,
    vote_share_pct: 56.94,
    age: 60,
  },
  {
    entity_id: "IN-AC-2008-tamil-nadu-4062",
    entity_name: "GUMMIDIPOONDI",
    party_id: "parties.IN.PMK",
    party_short: "PMK",
    symbol_asset_path: null,
    ac_id: "IN-AC-2008-tamil-nadu-4062",
    constituency_name: "GUMMIDIPOONDI",
    party_id_raw: "parties.IN.PMK",
    dp_short_name: "PMK",
    election_symbol_asset_path: null,
    party_full: "Pattali Makkal Katchi",
    result: "lost",
    sex: "M",
    education: "10th Pass",
    profession: "Qualified Professional",
    candidate_type: "challenger",
    source_id: null,
    state_slug: "tamil-nadu",
    eci_no: 167,
    delim_year: 2008,
    candidate_name: "PRAKASH M",
    party_eci_code: "742",
    party_short_raw: "PMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    position: 2,
    votes: 75_514,
    vote_share_pct: 34.0,
    age: 50,
  },
  {
    entity_id: "IN-AC-2008-tamil-nadu-4062",
    entity_name: "GUMMIDIPOONDI",
    party_id: null,
    party_short: null,
    symbol_asset_path: null,
    ac_id: "IN-AC-2008-tamil-nadu-4062",
    constituency_name: "GUMMIDIPOONDI",
    party_id_raw: null,
    dp_short_name: null,
    election_symbol_asset_path: null,
    party_full: null,
    result: "lost",
    sex: null,
    education: null,
    profession: null,
    candidate_type: null,
    source_id: null,
    state_slug: "tamil-nadu",
    eci_no: 167,
    delim_year: 2008,
    candidate_name: "NOTA",
    party_eci_code: null,
    party_short_raw: null,
    brand_colour_hex: null,
    brand_colour_confidence: null,
    position: 9,
    votes: 1_783,
    vote_share_pct: 0.8,
    age: null,
  },
];

const CONSTITUENCY_SUMMARY_FIXTURE = [
  {
    margin_pct: 22.94,
    turnout_pct: 65.0,
    winner_candidate: "GOVINDARAJAN T.J",
    winner_age: 60,
  },
];

// --------------------------------------------------------------------
// Body dispatch + scope guards
// --------------------------------------------------------------------

describe("bodyFromEvent", () => {
  it("recognises slug forms", () => {
    expect(bodyFromEvent("general-2024")).toBe("pc");
    expect(bodyFromEvent("assembly-2026")).toBe("ac");
  });
  it("recognises legacy ECI forms (W2a alias strangler)", () => {
    expect(bodyFromEvent("LsGenJun2024")).toBe("pc");
    expect(bodyFromEvent("AcGenMay2026")).toBe("ac");
  });
  it("throws on unknown prefix", () => {
    expect(() => bodyFromEvent("zoo-2026")).toThrow(/cannot infer body/);
  });
});

describe("loadElectionResults - scope guards", () => {
  // `describeFailure` wraps the raw Error.message with citizen-friendly copy
  // and logs the raw message via console.warn (see lib/loader-result.ts).
  // Tests spy on console.warn to assert the right developer-visible reason
  // landed, while res.reason carries the (generic) citizen-facing string.
  it("rejects eci_no without state", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const res = await loadElectionResults({
      event: "assembly-2026",
      eci_no: 167,
    });
    expect(res.status).toBe("failed");
    expect(warnSpy).toHaveBeenCalledWith(
      "[duckdb-loader] failure:",
      expect.stringMatching(/eci_no scope requires `state`/),
    );
    warnSpy.mockRestore();
  });
  it("rejects state-scope on parliament events (no national-AC today)", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const res = await loadElectionResults({
      event: "general-2024",
      state: "S22",
    });
    expect(res.status).toBe("failed");
    expect(warnSpy).toHaveBeenCalledWith(
      "[duckdb-loader] failure:",
      expect.stringMatching(/state-scope is only supported for assembly/),
    );
    warnSpy.mockRestore();
  });
  it("rejects constituency-scope on parliament events today", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const res = await loadElectionResults({
      event: "general-2024",
      state: "S22",
      eci_no: 1,
    });
    expect(res.status).toBe("failed");
    expect(warnSpy).toHaveBeenCalledWith(
      "[duckdb-loader] failure:",
      expect.stringMatching(/constituency-scope drill-down is only supported for assembly/),
    );
    warnSpy.mockRestore();
  });
});

// --------------------------------------------------------------------
// Projection helpers
// --------------------------------------------------------------------

describe("projection helpers", () => {
  const sample: ElectionResultRow[] = [
    {
      entity_id: "B",
      entity_kind: "ac",
      entity_name: "B",
      state_slug: "x",
      state_code: "X",
      eci_no: 2,
      delim_year: 2008,
      period_label: "assembly-2026",
      candidate_name: "loser",
      position: 2,
      votes: 100,
      vote_share_pct: 30,
      is_winner: false,
      party_id: null,
      party_eci_code: null,
      party_short: null,
      party_short_raw: null,
      brand_colour_hex: null,
      brand_colour_confidence: null,
      symbol_asset_path: null,
      margin_pct: null,
      turnout_pct: null,
      electors: null,
      votes_polled: null,
      margin_votes: null,
      winner_age: null,
      winner_candidate_name: null,
      reservation: "GEN",
    },
    {
      entity_id: "A",
      entity_kind: "ac",
      entity_name: "A",
      state_slug: "x",
      state_code: "X",
      eci_no: 1,
      delim_year: 2008,
      period_label: "assembly-2026",
      candidate_name: "winner",
      position: 1,
      votes: 200,
      vote_share_pct: 60,
      is_winner: true,
      party_id: null,
      party_eci_code: null,
      party_short: null,
      party_short_raw: null,
      brand_colour_hex: null,
      brand_colour_confidence: null,
      symbol_asset_path: null,
      margin_pct: null,
      turnout_pct: null,
      electors: null,
      votes_polled: null,
      margin_votes: null,
      winner_age: null,
      winner_candidate_name: null,
      reservation: "GEN",
    },
  ];

  it("projectAsWinnersByEntity filters non-winners", () => {
    const out = projectAsWinnersByEntity(sample);
    expect(out).toHaveLength(1);
    expect(out[0].entity_id).toBe("A");
  });

  it("projectAsConstituencyRanks sorts by (entity_id, position)", () => {
    const out = projectAsConstituencyRanks(sample);
    expect(out.map((r) => r.entity_id)).toEqual(["A", "B"]);
  });
});

// --------------------------------------------------------------------
// GOLDEN-ROW ORACLE - scope {event, state, eci_no}
// --------------------------------------------------------------------
//
// PR-W5a (2026-06-10): the `{event}` and `{event, state}` oracles
// retired with their bespoke counterparts `loadNationalPcWinners` and
// `loadStateAcWinners`. The W3/W4 call-sites all flipped to
// `loadElectionResults`, so the bespoke loaders had no live consumers
// left. The CONSTITUENCY-scope oracle below survives because its
// bespoke counterpart `loadConstituencyResult` is kept under
// view-models/legacy/ (it projects a richer ConstituencyResult shape
// than the W2b generic does today; see legacy/constituency.ts header).

describe("GOLDEN-ROW oracle - {event, state, eci_no} matches loadConstituencyResult", () => {
  it("byte-equal candidate list (post NOTA-split + top-N cut)", async () => {
    // Both loaders make TWO queries (candidates + summary). Bespoke also
    // makes a sources lookup conditional on source_id present - the
    // fixture leaves source_id undefined so the sources query is
    // skipped on the bespoke side.
    mockedQuery
      // generic: candidates, summary
      .mockResolvedValueOnce(CONSTITUENCY_CANDIDATES_FIXTURE)
      .mockResolvedValueOnce(CONSTITUENCY_SUMMARY_FIXTURE)
      // bespoke: candidates, summary, (sources skipped: no source_id in fixture)
      .mockResolvedValueOnce(CONSTITUENCY_CANDIDATES_FIXTURE)
      .mockResolvedValueOnce(CONSTITUENCY_SUMMARY_FIXTURE);

    const event = "AcGenMay2026";
    const state = "S22";
    const eci_no = 167;
    const generic = await loadElectionResults({ event, state, eci_no });
    const bespoke = await loadConstituencyResult(event, state, eci_no);

    expect(generic.status).toBe("ok");
    expect(bespoke.status).toBe("ok");
    if (generic.status !== "ok" || bespoke.status !== "ok") return;

    // Reconstruct the bespoke `candidates` shape from generic rows: drop
    // NOTA (it splits into a separate nota bucket on the bespoke side);
    // cut at TOP_N=7; map to the CandidateResult-comparable shape.
    const fromGeneric = projectAsConstituencyRanks(generic.data)
      .filter((r) => (r.candidate_name ?? "").toUpperCase() !== "NOTA")
      .slice(0, 7)
      .map((r) => ({
        rank: r.position ?? 0,
        name: r.candidate_name ?? "",
        party_id: r.party_id ?? "parties.IN.UNK",
        party_short: r.party_short ?? r.party_id ?? "IND",
        votes: r.votes ?? 0,
        vote_share_pct: r.vote_share_pct ?? 0,
        is_winner: r.is_winner,
        party_eci_code: r.party_eci_code,
        brand_colour_hex: r.brand_colour_hex,
        brand_colour_confidence: r.brand_colour_confidence,
        election_symbol_asset_path: r.symbol_asset_path,
      }));

    const fromBespoke = bespoke.data.candidates.map((c) => ({
      rank: c.rank,
      name: c.name,
      party_id: c.party_id,
      party_short: c.party_short,
      votes: c.votes,
      vote_share_pct: c.vote_share_pct,
      is_winner: c.is_winner,
      party_eci_code: c.party_eci_code,
      brand_colour_hex: c.brand_colour_hex,
      brand_colour_confidence: c.brand_colour_confidence,
      election_symbol_asset_path: c.election_symbol_asset_path,
    }));

    expect(fromGeneric).toEqual(fromBespoke);

    // Also pin: NOTA flag isolated on the bespoke side; the generic row
    // for NOTA carries the same data (party_id=null, position=9).
    const genericNota = generic.data.find(
      (r) => (r.candidate_name ?? "").toUpperCase() === "NOTA",
    );
    expect(genericNota?.votes).toBe(bespoke.data.nota.votes);
    expect(genericNota?.vote_share_pct).toBe(
      bespoke.data.nota.vote_share_pct,
    );

    // And: generic carries the AC's margin + turnout on every candidate
    // row; bespoke surfaces them on totals + winner.
    expect(generic.data[0].turnout_pct).toBe(
      bespoke.data.totals.turnout_pct,
    );
    expect(generic.data[0].margin_pct).toBe(
      bespoke.data.winner.margin_pct,
    );
  });
});

// --------------------------------------------------------------------
// partial / failed arms
// --------------------------------------------------------------------

describe("LoaderResult arms", () => {
  it("returns partial / not_published when zero rows", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    const res = await loadElectionResults({ event: "general-2024" });
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data).toEqual([]);
  });

  it("returns failed with describeFailure + retry callable on query throw", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    mockedQuery.mockRejectedValueOnce(new Error("boom"));
    const res = await loadElectionResults({ event: "general-2024" });
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    // Raw "boom" lands in console.warn (developer-visible). The citizen
    // reason is the generic copy from describeFailure() since "boom"
    // doesn't match any of the known error classes.
    expect(warnSpy).toHaveBeenCalledWith(
      "[duckdb-loader] failure:",
      expect.stringContaining("boom"),
    );
    expect(typeof res.retry).toBe("function");
    warnSpy.mockRestore();
  });
});

// PR-W5a (2026-06-10): the `byUnitId` + `byAcEciNo` sort-key helpers
// retired with the matching `{event}` + `{event, state}` golden-row
// oracle blocks.

// --------------------------------------------------------------------
// REGRESSION: LEFT JOIN dim_parties present on all 3 scopes
// --------------------------------------------------------------------
//
// PR-W2b's golden-row oracle caught a pre-existing latent bug in the
// (now-deleted) bespoke `loadNationalPcWinners`: the SQL referenced
// `dp.eci_code` / `dp.short_name` / `dp.brand_colour_hex` but MISSED the
// `LEFT JOIN dim_parties dp ON dp.party_id = s.winner_party_id` line.
// The bug was invisible in unit tests (mocks returned dp.* columns
// directly) but would have crashed at runtime against a real DuckDB.
//
// PR-W5a deleted the bespoke loader; the new generic loader at
// `frontend/src/lib/view-models/election-results.ts` correctly includes
// the JOIN at NATIONAL-PC, STATE-AC, and CONSTITUENCY scopes. This block
// pins the JOIN strings so a future refactor cannot silently drop them
// again. We assert against the SQL strings the loader passes to `query()`,
// captured via the mock's `mock.calls` array.
//
// Reverting the LEFT JOIN line in any of the 3 dispatch functions makes
// the matching test RED.

describe("regression: LEFT JOIN dim_parties present on all 3 scopes (W2b oracle)", () => {
  it("NATIONAL-PC scope SQL contains LEFT JOIN dim_parties on s.winner_party_id", async () => {
    // Empty result -> loader returns "partial"; we only need the SQL
    // string to have been emitted to query() to inspect its shape.
    mockedQuery.mockResolvedValueOnce([]);
    await loadElectionResults({ event: "general-2024" });
    expect(mockedQuery).toHaveBeenCalledTimes(1);
    const sql = String(mockedQuery.mock.calls[0][0]);
    expect(sql).toMatch(
      /LEFT JOIN dim_parties dp ON dp\.party_id = s\.winner_party_id/,
    );
    // TODO/20260612 Row B pin: margin_votes is projected at NATIONAL-PC
    // scope so the scatter chart's radius encoding can read it from the
    // loader. Reverting the SELECT line makes this test RED.
    expect(sql).toMatch(/s\.margin_votes\s+AS margin_votes/);
  });

  it("STATE-AC scope SQL contains LEFT JOIN dim_parties on s.winner_party_id", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadElectionResults({ event: "assembly-2026", state: "S22" });
    expect(mockedQuery).toHaveBeenCalledTimes(1);
    const sql = String(mockedQuery.mock.calls[0][0]);
    expect(sql).toMatch(
      /LEFT JOIN dim_parties dp ON dp\.party_id = s\.winner_party_id/,
    );
    // TODO/20260612 Row B pin: margin_votes is also projected at
    // STATE-AC scope so the state-event surface's scatter chart picks
    // up the same radius encoding.
    expect(sql).toMatch(/s\.margin_votes\s+AS margin_votes/);
  });

  it("CONSTITUENCY scope candidates SQL contains LEFT JOIN dim_parties on ec.party_id", async () => {
    // CONSTITUENCY dispatch runs TWO queries: candidates first, summary
    // second. The candidates query holds the dim_parties JOIN. Mock 1+
    // candidate row so the dispatch doesn't bail at the empty-check.
    mockedQuery
      .mockResolvedValueOnce([
        {
          entity_id: "IN-AC-2008-tamil-nadu-4062",
          state_slug: "tamil-nadu",
          eci_no: 167,
          delim_year: 2008,
          entity_name: "GUMMIDIPOONDI",
          reservation: "GEN",
          candidate_name: "GOVINDARAJAN T.J",
          party_id: "parties.IN.DMK",
          party_eci_code: null,
          party_short: null,
          party_short_raw: "DMK",
          brand_colour_hex: null,
          brand_colour_confidence: null,
          symbol_asset_path: null,
          position: 1,
          votes: 100,
          vote_share_pct: 50,
          age: 60,
        },
      ])
      .mockResolvedValueOnce([]); // summary -- empty is fine, candidates set the shape
    await loadElectionResults({
      event: "assembly-2026",
      state: "S22",
      eci_no: 167,
    });
    expect(mockedQuery).toHaveBeenCalledTimes(2);
    const candidatesSql = String(mockedQuery.mock.calls[0][0]);
    expect(candidatesSql).toMatch(
      /LEFT JOIN dim_parties dp ON dp\.party_id = ec\.party_id/,
    );
  });
});
