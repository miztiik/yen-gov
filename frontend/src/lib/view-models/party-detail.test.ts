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

import { query, registerCsvFile } from "../duckdb";
import { loadPartyMeta, type PartyMeta } from "./parties";
import {
  __resetForTests,
  bodyForPeriodLabel,
  computeTotals,
  foldHistoryRows,
  foldStrongholdRows,
  loadPartyDetail,
  partyIdTail,
  type PartyHistoryPoint,
  type PartyStronghold,
} from "./party-detail";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);
const mockedLoadPartyMeta = vi.mocked(loadPartyMeta);

beforeEach(() => {
  __resetForTests();
  mockedQuery.mockReset();
  mockedRegisterCsvFile.mockReset();
  mockedRegisterCsvFile.mockResolvedValue(undefined);
  mockedLoadPartyMeta.mockReset();
});

/** Build a minimal PartyMeta for the loader mock. */
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
    is_sentinel: false,
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
      { year: 1989, period_label: "AcGenJan1989", seats: 0, vote_share_pct: 14.4, contested: null },
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
      results: ["W", "W", "L"],
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
      { year: 1984, period_label: "LsGenDec1984", seats: 415, vote_share_pct: 49.1, contested: 517 },
      { year: 2024, period_label: "LsGenMay2024", seats: 99, vote_share_pct: 21.2, contested: 328 },
    ];
    const vs: PartyHistoryPoint[] = [
      { year: 2021, period_label: "AcGenApr2021", seats: 133, vote_share_pct: 37.7, contested: 188 },
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
      { year: 2019, period_label: "LsGenApr2019", seats: 0, vote_share_pct: 0.5, contested: 5 },
    ];
    expect(computeTotals(ls, []).elections_contested).toBe(1);
  });

  it("only counts cycles with seats>0 OR contested>0 (defensive vs zero-everything rows)", () => {
    const ls: PartyHistoryPoint[] = [
      { year: 2019, period_label: "LsGenApr2019", seats: 0, vote_share_pct: 0, contested: 0 },
    ];
    expect(computeTotals(ls, []).elections_contested).toBe(0);
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
    // Loader fires 4 queries in order:
    //   1. vsHistorySql  (VS party-aggregate rows)
    //   2. lsHistorySql  (LS per-PC winner counts grouped by event)
    //   3. strongholdSql (per-AC/PC winner rows where this party won)
    //   4. entitySql     (electoral.csv name JOIN; skipped when 0 strongholds)
    mockedQuery
      .mockResolvedValueOnce([
        // VS 2021 party-aggregate
        { year: 2021, period_label: "AcGenApr2021", indicator_id: "party-seats-won", value_numeric: 133 },
        { year: 2021, period_label: "AcGenApr2021", indicator_id: "party-vote-share-pct", value_numeric: 37.7 },
        { year: 2021, period_label: "AcGenApr2021", indicator_id: "party-contested-acs", value_numeric: 188 },
      ])
      .mockResolvedValueOnce([
        // LS synthesised: 22 PC wins in 2024 (from per-PC winner rows).
        { year: 2024, period_label: "LsGenMay2024", seats_count: 22 },
      ])
      .mockResolvedValueOnce([
        {
          entity_id: "IN-S22-AC-2008-167",
          period_label: "AcGenApr2021",
          winner_party_id: "parties.IN.DMK",
        },
      ])
      .mockResolvedValueOnce([
        // electoral.csv row uses the LGD-slug shape with an LGD-
        // sequential suffix (4025), but carries the natural-key
        // fields (`entity_kind`, `delim_year`, `state`, `eci_no`)
        // that JOIN back to the per-state CSV peer entity_id
        // `IN-S22-AC-2008-167` via the 4-tuple translator.
        {
          entity_id: "IN-AC-2008-tamil-nadu-4025",
          name: "Mylapore",
          entity_kind: "ac",
          delim_year: 2008,
          state: "tamil-nadu",
          eci_no: 167,
        },
      ]);

    const out = await loadPartyDetail("parties.IN.DMK");
    expect(out).not.toBeNull();
    expect(out!.metadata.short).toBe("DMK");
    expect(out!.ls_history).toHaveLength(1);
    expect(out!.ls_history[0]!.period_label).toBe("LsGenMay2024");
    expect(out!.ls_history[0]!.seats).toBe(22);
    // Synthesised LS rows carry null vote_share_pct + contested by design.
    expect(out!.ls_history[0]!.vote_share_pct).toBeNull();
    expect(out!.vs_history).toHaveLength(1);
    expect(out!.vs_history[0]!.period_label).toBe("AcGenApr2021");
    expect(out!.vs_strongholds).toHaveLength(1);
    expect(out!.vs_strongholds[0]!.constituency_name).toBe("Mylapore");
    expect(out!.totals.ls_seats).toBe(22);
    expect(out!.totals.vs_seats).toBe(133);
    expect(out!.totals.peak_vs_year).toBe(2021);
  });

  it("returns empty bodies when one of LS / VS has no data (national-only / state-only parties)", async () => {
    mockedLoadPartyMeta.mockResolvedValue(metaFixture({
      party_id: "parties.IN.LS_ONLY",
      short: "LSONLY",
    }));
    // 4 queries: vsAggregate (empty); lsSynthesis (one cycle);
    // stronghold (empty -> entity JOIN skipped, so only 3 mocks needed).
    mockedQuery
      .mockResolvedValueOnce([]) // vs aggregate
      .mockResolvedValueOnce([
        { year: 2024, period_label: "LsGenMay2024", seats_count: 5 },
      ])
      .mockResolvedValueOnce([]); // stronghold rows empty
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

  it("falls back to empty constituency_name when the peer entity_id parses to an unknown state code", async () => {
    // A stronghold row whose peer entity_id uses an unknown ECI st_code
    // (e.g. `S99`) won't parse via `parsePeerEntityId` -> excluded from
    // the JOIN tuple list -> no electoral.csv row matches -> the
    // lookup miss falls back to empty constituency_name + state. The
    // page surface renders the empty fallback instead of the citizen-
    // readable name. This locks in the defensive behaviour declared in
    // the translator module.
    mockedLoadPartyMeta.mockResolvedValue(metaFixture());
    mockedQuery
      .mockResolvedValueOnce([]) // vs aggregate
      .mockResolvedValueOnce([]) // ls synthesis
      .mockResolvedValueOnce([
        {
          entity_id: "IN-S99-AC-2008-1",
          period_label: "AcGenApr2021",
          winner_party_id: "parties.IN.DMK",
        },
      ]);
    // No 4th mock: the entity JOIN is skipped because peerKeys is
    // empty (the only stronghold row failed to parse).
    const out = await loadPartyDetail("parties.IN.DMK");
    expect(out!.vs_strongholds).toHaveLength(1);
    expect(out!.vs_strongholds[0]!.entity_id).toBe("IN-S99-AC-2008-1");
    expect(out!.vs_strongholds[0]!.constituency_name).toBe("");
    expect(out!.vs_strongholds[0]!.state).toBe("");
  });
});
