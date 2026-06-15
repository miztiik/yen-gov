// PR-4 vitest for `view-models/party-detail.ts`.
//
// Per CLAUDE.md section 15: the loader's contract IS the DuckDB-WASM
// boundary - mocking `query` / `registerCsvFile` / `csvColumnsClause`
// is the explicit carve-out from Holy Law #7 (no mocks). The pure
// folders (`foldHistoryRows`, `foldStrongholdRows`, `computeTotals`,
// `bodyForPeriodLabel`, `partyIdTail`) carry the bulk of the contract;
// the loader's outer shape (cache hit, null on missing metadata, body
// split) is the remainder.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerCsvFile: vi.fn(async () => undefined),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={'entity_id': 'VARCHAR'}"),
}));

vi.mock("./parties", () => ({
  loadPartyMeta: vi.fn(),
}));

vi.mock("./party-current-strength", () => ({
  loadPartyCurrentStrength: vi.fn(),
}));

vi.mock("./party-alliance-context", () => ({
  loadPartyAllianceContext: vi.fn(),
}));

// PR-9: neutralise the provenance envelope in party-detail's outer-shape
// tests. The STOP-AND-SURFACE check inside `buildPartyProvenance` would
// otherwise throw on every fixture here (the raw mart rows below don't
// stub `source_ids` on each row). The provenance contract itself is
// gated by `frontend/src/contracts/party-page-provenance.test.ts`; here
// we only need the loader to assemble a VM end-to-end.
vi.mock("./party-sources", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./party-sources")>();
  return {
    ...actual,
    loadSourceLookup: vi.fn(async () => new Map()),
    buildPartyProvenance: vi.fn(() => ({
      badges: {
        parliament: "",
        state_assembly: "",
        strongholds: "",
        current_strength: "",
        alliance_context: "",
      },
      strip: { total_count: 0, all: [], producer_summary: "" },
    })),
  };
});

import { query, registerCsvFile } from "../duckdb";
import { loadPartyMeta, type PartyMeta } from "./parties";
import { loadPartyCurrentStrength } from "./party-current-strength";
import { loadPartyAllianceContext } from "./party-alliance-context";
import {
  __resetForTests,
  bodyForPeriodLabel,
  computeTotals,
  foldHistoryRows,
  foldStrongholdRows,
  loadPartyDetail,
  partyIdTail,
  pickLsMethodologyBreaks,
  visibleLsMethodologyBreaks,
  type MethodologyBreakRow,
  type PartyHistoryPoint,
  type PartyStronghold,
} from "./party-detail";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);
const mockedLoadPartyMeta = vi.mocked(loadPartyMeta);
const mockedLoadPartyCurrentStrength = vi.mocked(loadPartyCurrentStrength);
const mockedLoadPartyAllianceContext = vi.mocked(loadPartyAllianceContext);

/** Stub the global `fetch` used by `fetchLsMethodologyBreaks` so the
 *  view-model loader doesn't hit the network during tests. Each test
 *  installs its own response shape; `beforeEach` resets the stub. */
// Use a plain `any` here: `vi.spyOn(global, 'fetch')` returns a
// `MockInstance` whose generic shape conflicts with the loose
// `MockInstance<(this: unknown, ...args: unknown[]) => unknown>`
// default — vitest accepts both at runtime but TS rejects the
// implicit unification. The cast keeps the test code small without
// dragging the full lib.dom `fetch` type signature into scope.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let fetchSpy: any = null;
function stubMethodologyBreaksFetch(
  rows: MethodologyBreakRow[] = [
    {
      methodology_version: "lspc-delim-1967",
      at_year: 1967,
      at_period_seq: 2,
      kind: "frame_change",
      note: "Parliament constituency boundaries shifted from the 1951-Order delimitation to the 1962 Delimitation Commission output.",
      publisher_url: null,
      supersedes_methodology_version: null,
    },
    {
      methodology_version: "lspc-delim-1976",
      at_year: 1977,
      at_period_seq: 3,
      kind: "frame_change",
      note: "Parliament constituency boundaries shifted to the 1971-72 Delimitation Commission output, frozen by 42nd Amendment until 2008.",
      publisher_url: null,
      supersedes_methodology_version: "lspc-delim-1967",
    },
  ],
): void {
  fetchSpy?.mockRestore();
  fetchSpy = vi.spyOn(global, "fetch").mockImplementation(async (url) => {
    if (String(url).includes("methodology_breaks.json")) {
      return new Response(
        JSON.stringify({
          $schema: "../schemas/methodology-break.schema.json",
          $schema_version: "1.0",
          methodology_breaks: rows,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    throw new Error(`unexpected fetch in test: ${String(url)}`);
  });
}

beforeEach(() => {
  __resetForTests();
  mockedQuery.mockReset();
  mockedRegisterCsvFile.mockReset();
  mockedRegisterCsvFile.mockResolvedValue(undefined);
  mockedLoadPartyMeta.mockReset();
  mockedLoadPartyCurrentStrength.mockReset();
  // Default: the strip loader returns null so existing tests that
  // only stub the 2 detail-loader queries (history + strongholds)
  // don't have to absorb the strip loader's 2 extra parallel queries.
  mockedLoadPartyCurrentStrength.mockResolvedValue(null);
  mockedLoadPartyAllianceContext.mockReset();
  // PR-8: same null-by-default discipline as the strength strip -
  // the Alliance Context loader reads party_alliances.csv +
  // history.csv via its own DuckDB boundary, so tests that don't
  // explicitly opt in get the suppressed-strip surface.
  mockedLoadPartyAllianceContext.mockResolvedValue(null);
  stubMethodologyBreaksFetch();
});

/** Build a minimal PartyMeta for the loader mock. PR-11: includes
 *  `leader: null` since the PartyMeta type now carries a leader field
 *  populated by `loadPartyMeta` from parties_leadership.csv (default
 *  null = no current leader on disk; the common case today). */
function metaFixture(overrides: Partial<PartyMeta> = {}): PartyMeta {
  return {
    party_id: "parties.IN.DMK",
    short: "DMK",
    full: "Dravida Munnetra Kazhagam",
    founded_year: 1949,
    dissolved_year: null,
    recognition_scope: "state",
    home_state_codes: ["IN-TN"],
    symbol_asset: null,
    brand_colour: "#dc2626",
    wikipedia: "https://en.wikipedia.org/wiki/Dravida_Munnetra_Kazhagam",
    name_native_script: null,
    aliases: [],
    predecessor_party_ids: [],
    successor_party_ids: [],
    is_sentinel: false,
    leader: null,
    ...overrides,
  };
}

// --- pure helpers ---------------------------------------------------------

describe("bodyForPeriodLabel", () => {
  it("classifies Ls* labels as Lok Sabha", () => {
    expect(bodyForPeriodLabel("LsGenMay2024")).toBe("ls");
    expect(bodyForPeriodLabel("LsByeJun2018")).toBe("ls");
  });
  it("classifies Ac* labels as Vidhan Sabha", () => {
    expect(bodyForPeriodLabel("AcGenApr2021")).toBe("vs");
    expect(bodyForPeriodLabel("AcByeOct1971")).toBe("vs");
  });
  it("returns null for unrecognised prefixes", () => {
    expect(bodyForPeriodLabel("PanchayatJan2020")).toBeNull();
    expect(bodyForPeriodLabel("")).toBeNull();
  });
});

describe("partyIdTail", () => {
  it("extracts the last dot-separated token from a canonical party_id", () => {
    expect(partyIdTail("parties.IN.DMK")).toBe("DMK");
    expect(partyIdTail("parties.IN.AIADMK")).toBe("AIADMK");
  });
  it("returns the input itself when no dot is present (defensive)", () => {
    expect(partyIdTail("DMK")).toBe("DMK");
  });
});

// --- foldHistoryRows ------------------------------------------------------

describe("foldHistoryRows", () => {
  it("folds 3-per-cycle rows into one PartyHistoryPoint per period_label", () => {
    const out = foldHistoryRows([
      {
        year: 2021,
        period_label: "AcGenApr2021",
        indicator_id: "party-seats-won",
        value_numeric: 133,
      },
      {
        year: 2021,
        period_label: "AcGenApr2021",
        indicator_id: "party-vote-share-pct",
        value_numeric: 37.7,
      },
      {
        year: 2021,
        period_label: "AcGenApr2021",
        indicator_id: "party-contested-acs",
        value_numeric: 188,
      },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({
      year: 2021,
      period_label: "AcGenApr2021",
      seats: 133,
      vote_share_pct: 37.7,
      contested: 188,
      source_ids: [],
    });
  });

  it("sorts the output chronologically by year then period_label", () => {
    const out = foldHistoryRows([
      { year: 2021, period_label: "AcGenApr2021", indicator_id: "party-seats-won", value_numeric: 133 },
      { year: 1989, period_label: "AcGenJan1989", indicator_id: "party-seats-won", value_numeric: 150 },
      { year: 1991, period_label: "AcGenFeb1991", indicator_id: "party-seats-won", value_numeric: 2 },
    ]);
    expect(out.map((p) => p.year)).toEqual([1989, 1991, 2021]);
  });

  it("ignores rows with null period_label / null year / unrecognised indicator", () => {
    const out = foldHistoryRows([
      { year: 2021, period_label: null, indicator_id: "party-seats-won", value_numeric: 100 },
      { year: null, period_label: "AcGenApr2021", indicator_id: "party-seats-won", value_numeric: 100 },
      { year: 2021, period_label: "AcGenApr2021", indicator_id: "irrelevant", value_numeric: 999 },
    ]);
    expect(out).toEqual([]);
  });

  it("defaults seats to 0 and contested+vote_share to null when their rows are missing", () => {
    // Only the vote-share row appears; seats column SHOULD be 0, not null
    const out = foldHistoryRows([
      {
        year: 1989,
        period_label: "AcGenJan1989",
        indicator_id: "party-vote-share-pct",
        value_numeric: 14.4,
      },
    ]);
    expect(out).toEqual([
      { year: 1989, period_label: "AcGenJan1989", seats: 0, vote_share_pct: 14.4, contested: null, source_ids: [] },
    ]);
  });

  it("coerces bigint year (DuckDB BIGINT) to number", () => {
    const out = foldHistoryRows([
      {
        year: 2021n as unknown as bigint,
        period_label: "AcGenApr2021",
        indicator_id: "party-seats-won",
        value_numeric: 133,
      },
    ]);
    expect(out[0]!.year).toBe(2021);
    expect(typeof out[0]!.year).toBe("number");
  });
});

// --- foldStrongholdRows ---------------------------------------------------

describe("foldStrongholdRows", () => {
  const target = "parties.IN.DMK";
  const nameLookup = new Map<string, string>([
    ["IN-AC-2008-S22-167", "Mylapore"],
    ["IN-AC-2008-S22-1", "Gummidipoondi"],
  ]);
  const stateLookup = new Map<string, string>([
    ["IN-AC-2008-S22-167", "tamil-nadu"],
    ["IN-AC-2008-S22-1", "tamil-nadu"],
  ]);

  it("counts wins per entity_id and emits W/L sparkline chronologically", () => {
    const out = foldStrongholdRows(
      [
        {
          entity_id: "IN-AC-2008-S22-167",
          period_label: "AcGenJan1989",
          winner_party_id: "parties.IN.DMK",
        },
        {
          entity_id: "IN-AC-2008-S22-167",
          period_label: "AcGenFeb1996",
          winner_party_id: "parties.IN.DMK",
        },
        {
          entity_id: "IN-AC-2008-S22-167",
          period_label: "AcGenApr2021",
          winner_party_id: "parties.IN.AIADMK",
        },
      ],
      target,
      nameLookup,
      stateLookup,
    );
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({
      entity_id: "IN-AC-2008-S22-167",
      constituency_name: "Mylapore",
      state: "tamil-nadu",
      wins: 2,
      contested: 3,
      // PR-7: the legacy fold path (test-only; production loader
      // reads `last_won_year` from the mart) emits null because
      // `RawStrongholdRow` does not carry per-event year.
      last_won_year: null,
      results: ["W", "W", "L"],
      source_ids: [],
    });
  });

  it("excludes 0-win entries from the output (only true strongholds)", () => {
    const out = foldStrongholdRows(
      [
        {
          entity_id: "IN-AC-2008-S22-1",
          period_label: "AcGenApr2021",
          winner_party_id: "parties.IN.AIADMK",
        },
      ],
      target,
      nameLookup,
      stateLookup,
    );
    expect(out).toEqual([]);
  });

  it("sorts by wins desc, then win-rate desc, then entity_id asc", () => {
    // Build 3 entities, all with the same number of wins (2) but
    // different denominators - win-rate desc should pick the sweeper.
    const out = foldStrongholdRows(
      [
        // ENT-A: 2-of-3
        { entity_id: "ENT-A", period_label: "1", winner_party_id: target },
        { entity_id: "ENT-A", period_label: "2", winner_party_id: target },
        { entity_id: "ENT-A", period_label: "3", winner_party_id: "other" },
        // ENT-B: 2-of-2 (sweeper)
        { entity_id: "ENT-B", period_label: "1", winner_party_id: target },
        { entity_id: "ENT-B", period_label: "2", winner_party_id: target },
        // ENT-C: 2-of-2 (sweeper; ties win-rate, lower entity_id wins)
        { entity_id: "ENT-C", period_label: "1", winner_party_id: target },
        { entity_id: "ENT-C", period_label: "2", winner_party_id: target },
      ],
      target,
      new Map(),
      new Map(),
    );
    expect(out.map((s) => s.entity_id)).toEqual(["ENT-B", "ENT-C", "ENT-A"]);
  });

  it("clips the output to the top-10 strongholds", () => {
    const rows: { entity_id: string; period_label: string; winner_party_id: string }[] = [];
    for (let i = 0; i < 15; i += 1) {
      rows.push({
        entity_id: `ENT-${String(i).padStart(2, "0")}`,
        period_label: "1",
        winner_party_id: target,
      });
    }
    const out = foldStrongholdRows(rows, target, new Map(), new Map());
    expect(out).toHaveLength(10);
  });

  it("falls back to empty constituency_name / state when the lookup misses", () => {
    const out = foldStrongholdRows(
      [
        {
          entity_id: "IN-AC-2008-S22-999",
          period_label: "AcGenApr2021",
          winner_party_id: target,
        },
      ],
      target,
      new Map(),
      new Map(),
    );
    expect(out[0]!.constituency_name).toBe("");
    expect(out[0]!.state).toBe("");
  });
});

// --- computeTotals --------------------------------------------------------

describe("computeTotals", () => {
  it("sums seats per body and picks the peak year by max seats", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 1984, period_label: "LsGenDec1984", seats: 415, vote_share_pct: 49.1, contested: 517, source_ids: [] },
      { year: 2024, period_label: "LsGenMay2024", seats: 99, vote_share_pct: 21.2, contested: 328, source_ids: [] },
    ];
    const vs: PartyHistoryPoint[] = [
      { year: 2021, period_label: "AcGenApr2021", seats: 133, vote_share_pct: 37.7, contested: 188, source_ids: [] },
    ];
    const t = computeTotals(ls, vs);
    expect(t.ls_seats).toBe(514);
    expect(t.vs_seats).toBe(133);
    expect(t.peak_ls_seats).toBe(415);
    expect(t.peak_ls_year).toBe(1984);
    expect(t.peak_vs_seats).toBe(133);
    expect(t.peak_vs_year).toBe(2021);
    expect(t.first_year).toBe(1984);
    expect(t.last_year).toBe(2024);
    expect(t.elections_contested).toBe(3);
  });

  it("returns zeroed totals on empty input (sentinel-safe)", () => {
    const t = computeTotals([], []);
    expect(t).toEqual({
      ls_seats: 0,
      vs_seats: 0,
      elections_contested: 0,
      first_year: 0,
      last_year: 0,
      peak_ls_seats: 0,
      peak_ls_year: 0,
      peak_vs_seats: 0,
      peak_vs_year: 0,
    });
  });

  it("counts cycles where contested > 0 even when seats are zero (no-win contesting)", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2019, period_label: "LsGenApr2019", seats: 0, vote_share_pct: 0.5, contested: 5, source_ids: [] },
    ];
    expect(computeTotals(ls, []).elections_contested).toBe(1);
  });

  it("only counts cycles with seats>0 OR contested>0 (defensive vs zero-everything rows)", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2019, period_label: "LsGenApr2019", seats: 0, vote_share_pct: 0, contested: 0, source_ids: [] },
    ];
    expect(computeTotals(ls, []).elections_contested).toBe(0);
  });
});

// --- pickLsMethodologyBreaks (PR-10) --------------------------------------

describe("pickLsMethodologyBreaks", () => {
  it("returns only the 2 lspc-delim methodology_versions that PR-10 surfaces", () => {
    const rows: MethodologyBreakRow[] = [
      {
        methodology_version: "lspc-delim-1967",
        at_year: 1967,
        at_period_seq: 2,
        kind: "frame_change",
        note: "irrelevant text for the unit test",
      },
      {
        methodology_version: "lspc-delim-1976",
        at_year: 1977,
        at_period_seq: 3,
        kind: "frame_change",
        note: "irrelevant text for the unit test",
      },
      {
        methodology_version: "lspc-delim-2008",
        at_year: 2009,
        at_period_seq: 5,
        kind: "frame_change",
        note: "post-1998 delim break - NOT surfaced on the LS chart per PR-10",
      },
      {
        methodology_version: "cpi-rebase-2012",
        at_year: 2012,
        at_period_seq: 1,
        kind: "rebase",
        note: "unrelated indicator family - filtered out",
      },
    ];
    const got = pickLsMethodologyBreaks(rows);
    expect(got).toHaveLength(2);
    expect(got.map((r) => r.methodology_version)).toEqual([
      "lspc-delim-1967",
      "lspc-delim-1976",
    ]);
  });

  it("returns rows in at_year ascending order regardless of input order", () => {
    const rows: MethodologyBreakRow[] = [
      {
        methodology_version: "lspc-delim-1976",
        at_year: 1977,
        at_period_seq: 3,
        kind: "frame_change",
        note: "second break",
      },
      {
        methodology_version: "lspc-delim-1967",
        at_year: 1967,
        at_period_seq: 2,
        kind: "frame_change",
        note: "first break",
      },
    ];
    const got = pickLsMethodologyBreaks(rows);
    expect(got.map((r) => r.at_year)).toEqual([1967, 1977]);
  });

  it("returns empty for an empty catalogue (defensive)", () => {
    expect(pickLsMethodologyBreaks([])).toEqual([]);
  });
});

// --- visibleLsMethodologyBreaks (PR-10 chart/caption co-gate) -------------

describe("visibleLsMethodologyBreaks", () => {
  const delim1967: MethodologyBreakRow = {
    methodology_version: "lspc-delim-1967",
    at_year: 1967,
    at_period_seq: 2,
    kind: "frame_change",
    note: "first break",
  };
  const delim1976: MethodologyBreakRow = {
    methodology_version: "lspc-delim-1976",
    at_year: 1977,
    at_period_seq: 3,
    kind: "frame_change",
    note: "second break",
  };
  function p(year: number, label: string): PartyHistoryPoint {
    return {
      year,
      period_label: label,
      seats: 0,
      vote_share_pct: null,
      contested: null,
      source_ids: [],
    };
  }

  it("DMK case: ls_history 1962-2024 makes BOTH delim breaks visible (chart + caption agree)", () => {
    const out = visibleLsMethodologyBreaks(
      [delim1967, delim1976],
      [p(1962, "LsGenFeb1962"), p(2024, "LsGenJun2024")],
    );
    expect(out).toHaveLength(2);
  });

  it("BJP case: ls_history 1984-2024 (first contested 1984) hides BOTH delim breaks (chart + caption agree)", () => {
    const out = visibleLsMethodologyBreaks(
      [delim1967, delim1976],
      [p(1984, "LsGenDec1984"), p(2024, "LsGenJun2024")],
    );
    expect(out).toEqual([]);
  });

  it("INC pre-1999 cohort: ls_history 1989-2024 hides BOTH delim breaks (first cycle > both at_years)", () => {
    const out = visibleLsMethodologyBreaks(
      [delim1967, delim1976],
      [p(1989, "LsGenNov1989"), p(2024, "LsGenJun2024")],
    );
    expect(out).toEqual([]);
  });

  it("narrow domain 1962-1971 keeps only 1967 break (at_year <= last) and hides 1976 (at_year > last)", () => {
    const out = visibleLsMethodologyBreaks(
      [delim1967, delim1976],
      [p(1962, "LsGenFeb1962"), p(1971, "LsGenMar1971")],
    );
    expect(out).toHaveLength(1);
    expect(out[0]!.methodology_version).toBe("lspc-delim-1967");
  });

  it("empty ls_history returns empty (defensive; the consumer gates on chart presence)", () => {
    expect(visibleLsMethodologyBreaks([delim1967, delim1976], [])).toEqual([]);
  });
});

// --- loadPartyDetail outer shape ------------------------------------------

describe("loadPartyDetail", () => {
  it("returns null when metadata is missing (unknown party_id)", async () => {
    mockedLoadPartyMeta.mockResolvedValue(null);
    const out = await loadPartyDetail("parties.IN.NONEXISTENT");
    expect(out).toBeNull();
    // The query path must NOT fire when metadata is missing - the loader
    // short-circuits before touching DuckDB.
    expect(mockedQuery).not.toHaveBeenCalled();
  });

  it("returns null for null / empty party_id (defensive)", async () => {
    expect(await loadPartyDetail(null)).toBeNull();
    expect(await loadPartyDetail("")).toBeNull();
    expect(await loadPartyDetail(undefined)).toBeNull();
    expect(mockedLoadPartyMeta).not.toHaveBeenCalled();
  });

  it("returns the SAME Promise on repeated calls for the same party_id (cache hit)", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture());
    mockedQuery.mockResolvedValue([]);
    const p1 = loadPartyDetail("parties.IN.DMK");
    const p2 = loadPartyDetail("parties.IN.DMK");
    expect(p1).toBe(p2);
    await p1;
    expect(mockedLoadPartyMeta).toHaveBeenCalledTimes(1);
  });

  it("assembles ls_history + vs_history + totals from the DuckDB rows", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture());
    // Loader fires 2 queries in order: party-page history mart, then
    // party-page strongholds mart. The full electoral corpus is scanned
    // only by the backend derive-party-pages command.
    mockedQuery
      .mockResolvedValueOnce([
        {
          body: "assembly",
          year: 2021,
          period_label: "AcGenApr2021",
          seats: 133,
          vote_share_pct: 37.7,
          contested: 188,
        },
        {
          body: "parliament",
          year: 1962,
          period_label: "LsGenFeb1962",
          seats: 7,
          vote_share_pct: 11.4,
          contested: 18,
        },
        {
          body: "parliament",
          year: 2024,
          period_label: "LsGenJun2024",
          seats: 22,
          vote_share_pct: 26.7,
          contested: 22,
        },
      ])
      .mockResolvedValueOnce([
        {
          body: "assembly",
          rank: 1,
          entity_id: "IN-S22-AC-2008-167",
          constituency_name: "Mylapore",
          state: "tamil-nadu",
          wins: 1,
          contested: 1,
          results: "W",
        },
      ]);

    const out = await loadPartyDetail("parties.IN.DMK");
    expect(out).not.toBeNull();
    expect(out!.metadata.short).toBe("DMK");
    // 2 LS cycles after the fold: 1962 + 2024 (chronologically sorted).
    expect(out!.ls_history).toHaveLength(2);
    expect(out!.ls_history[0]!.period_label).toBe("LsGenFeb1962");
    expect(out!.ls_history[1]!.period_label).toBe("LsGenJun2024");
    expect(out!.ls_history[1]!.seats).toBe(22);
    // LS rows NOW carry vote_share_pct + contested (PR-4 closure-ledger
    // known-degradation #1 closed by the LS-aggregate-ingest PR, 2026-06-13).
    expect(out!.ls_history[1]!.vote_share_pct).toBe(26.7);
    expect(out!.ls_history[1]!.contested).toBe(22);
    expect(out!.vs_history).toHaveLength(1);
    expect(out!.vs_history[0]!.period_label).toBe("AcGenApr2021");
    expect(out!.vs_strongholds).toHaveLength(1);
    expect(out!.vs_strongholds[0]!.constituency_name).toBe("Mylapore");
    expect(out!.totals.ls_seats).toBe(29);
    expect(out!.totals.vs_seats).toBe(133);
    expect(out!.totals.peak_vs_year).toBe(2021);

    // PR-10: ls_methodology_breaks populates from the stubbed
    // catalogue (2 lspc-delim rows, chronologically sorted) AND
    // survives the visibleLsMethodologyBreaks filter because the
    // mocked DMK history spans 1962-2024 (both at_year=1967 + 1977
    // fall strictly inside).
    expect(out!.ls_methodology_breaks).toHaveLength(2);
    expect(
      out!.ls_methodology_breaks.map((r) => r.methodology_version),
    ).toEqual(["lspc-delim-1967", "lspc-delim-1976"]);
    expect(out!.ls_methodology_breaks[0]!.kind).toBe("frame_change");

    const registered = mockedRegisterCsvFile.mock.calls.map(([url]) => String(url));
    expect(registered.some((url) => url.includes("/data/marts/party_pages/history.csv"))).toBe(true);
    expect(registered.some((url) => url.includes("/data/marts/party_pages/strongholds.csv"))).toBe(true);
    expect(registered.some((url) => url.includes("/data/datapoints/electoral/"))).toBe(false);
    const sql = mockedQuery.mock.calls.map(([q]) => String(q)).join("\n");
    expect(sql).not.toContain("data/datapoints/electoral");
  });

  it("returns empty bodies when one of LS / VS has no data (national-only / state-only parties)", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture({
      party_id: "parties.IN.LS_ONLY",
      short: "LSONLY",
    }));
    // 2 queries: history mart, strongholds mart.
    mockedQuery
      .mockResolvedValueOnce([
        {
          body: "parliament",
          year: 2024,
          period_label: "LsGenJun2024",
          seats: 5,
          vote_share_pct: 1.2,
          contested: 12,
        },
      ])
      .mockResolvedValueOnce([]);
    const out = await loadPartyDetail("parties.IN.LS_ONLY");
    expect(out!.vs_history).toEqual([]);
    expect(out!.ls_history).toHaveLength(1);
    expect(out!.ls_strongholds).toEqual([]);
    expect(out!.vs_strongholds).toEqual([]);
  });

  it("handles sentinel parties (NOTA) without crashing", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture({
      party_id: "parties.IN.NOTA",
      short: "NOTA",
      full: "None of the Above",
      is_sentinel: true,
      recognition_scope: "sentinel",
      founded_year: 2013,
    }));
    mockedQuery.mockResolvedValue([]);
    const out = await loadPartyDetail("parties.IN.NOTA");
    expect(out).not.toBeNull();
    expect(out!.metadata.is_sentinel).toBe(true);
    expect(out!.ls_history).toEqual([]);
    expect(out!.vs_history).toEqual([]);
  });

  it("clears the cache on fetch error so a retry re-issues the queries", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture());
    mockedQuery.mockRejectedValueOnce(new Error("network gone"));
    await expect(loadPartyDetail("parties.IN.DMK")).rejects.toThrow(
      "network gone",
    );
    // The cache entry should be cleared; a second call retries.
    mockedQuery.mockResolvedValue([]);
    const out = await loadPartyDetail("parties.IN.DMK");
    expect(out).not.toBeNull();
  });

  it("passes through empty constituency_name/state from the mart", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture());
    mockedQuery
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          body: "assembly",
          rank: 1,
          entity_id: "IN-S99-AC-2008-1",
          constituency_name: "",
          state: "",
          wins: 1,
          contested: 1,
          results: "W",
        },
      ]);
    const out = await loadPartyDetail("parties.IN.DMK");
    expect(out!.vs_strongholds).toHaveLength(1);
    expect(out!.vs_strongholds[0]!.entity_id).toBe("IN-S99-AC-2008-1");
    expect(out!.vs_strongholds[0]!.constituency_name).toBe("");
    expect(out!.vs_strongholds[0]!.state).toBe("");
  });

  // PR-7b: the Current Strength strip view-model is plumbed in
  // parallel with the existing history / strongholds reads. The
  // detail loader surfaces whatever the strip loader returns -
  // typically a populated `PartyCurrentStrength` for live parties
  // and `null` for sentinels (NOTA / UNK). This test pins both
  // the populated path and the suppression path.
  it("surfaces current_strength from the strip loader on the view-model", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture());
    mockedQuery.mockResolvedValue([]);
    mockedLoadPartyCurrentStrength.mockResolvedValue({
      parliament_latest: {
        year: 2024,
        event_id: "general-2024",
        month_label: "Jun 2024",
        seats_won: 22,
        seats_total: 543,
        vote_share_pct: 26.7,
        rank_label: null,
      },
      state_assemblies_latest: {
        seats_won: 133,
        seats_total: 234,
        state_count: 1,
        latest_event_label: "Tamil Nadu State Assembly, Apr 2021",
        latest_event_sort_key: "2021-04",
      },
      last_contested_label: "Parliament General Election, Jun 2024",
    });
    const out = await loadPartyDetail("parties.IN.DMK");
    expect(out).not.toBeNull();
    expect(out!.current_strength).not.toBeNull();
    expect(out!.current_strength!.parliament_latest!.seats_won).toBe(22);
    expect(out!.current_strength!.state_assemblies_latest!.state_count).toBe(1);
    expect(out!.current_strength!.last_contested_label).toBe(
      "Parliament General Election, Jun 2024",
    );
    expect(mockedLoadPartyCurrentStrength).toHaveBeenCalledWith(
      "parties.IN.DMK",
      expect.objectContaining({ is_sentinel: false }),
    );
  });

  it("surfaces current_strength=null for sentinel parties (NOTA / UNK)", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture({
      party_id: "parties.IN.NOTA",
      short: "NOTA",
      full: "None of the Above",
      is_sentinel: true,
      recognition_scope: "sentinel",
      founded_year: 2013,
    }));
    mockedQuery.mockResolvedValue([]);
    mockedLoadPartyCurrentStrength.mockResolvedValue(null);
    const out = await loadPartyDetail("parties.IN.NOTA");
    expect(out!.current_strength).toBeNull();
    expect(mockedLoadPartyCurrentStrength).toHaveBeenCalledWith(
      "parties.IN.NOTA",
      expect.objectContaining({ is_sentinel: true }),
    );
  });

  // PR-8: the Alliance Context strip is plumbed in parallel with the
  // existing detail reads + the PR-7b strength strip. Same suppression
  // discipline: surface whatever the loader returns; null hides the
  // strip without breaking the page.
  it("surfaces alliance_context from the strip loader on the view-model", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture());
    mockedQuery.mockResolvedValue([]);
    mockedLoadPartyAllianceContext.mockResolvedValue({
      parliament: {
        event_label: "Parliament 2024",
        event_id: "general-2024",
        alliance: "NDA",
        role: "led",
        partner_count: 2,
        partner_names_top: ["JD(U)", "TDP"],
        total_alliance_seats: 290,
      },
      state_assemblies: [
        {
          state: "maharashtra",
          state_name: "Maharashtra",
          event_label: "Maharashtra (2024)",
          event_id: "general-2024",
          alliance: "Mahayuti",
          role: "led",
          partner_count: 1,
          partner_names_top: ["SHS"],
          total_alliance_seats: 230,
        },
      ],
    });
    const out = await loadPartyDetail("parties.IN.DMK");
    expect(out).not.toBeNull();
    expect(out!.alliance_context).not.toBeNull();
    expect(out!.alliance_context!.parliament!.alliance).toBe("NDA");
    expect(out!.alliance_context!.state_assemblies).toHaveLength(1);
    expect(out!.alliance_context!.state_assemblies[0]!.alliance).toBe(
      "Mahayuti",
    );
    expect(mockedLoadPartyAllianceContext).toHaveBeenCalledWith(
      "parties.IN.DMK",
      expect.objectContaining({ is_sentinel: false }),
    );
  });

  it("surfaces alliance_context=null for sentinel parties (NOTA / UNK)", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture({
      party_id: "parties.IN.NOTA",
      short: "NOTA",
      full: "None of the Above",
      is_sentinel: true,
      recognition_scope: "sentinel",
      founded_year: 2013,
    }));
    mockedQuery.mockResolvedValue([]);
    mockedLoadPartyAllianceContext.mockResolvedValue(null);
    const out = await loadPartyDetail("parties.IN.NOTA");
    expect(out!.alliance_context).toBeNull();
    expect(mockedLoadPartyAllianceContext).toHaveBeenCalledWith(
      "parties.IN.NOTA",
      expect.objectContaining({ is_sentinel: true }),
    );
  });
});
