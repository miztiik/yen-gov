/**
 * `party-current-strength.test.ts` — vitest pin for the per-party
 * "Where this party sits today" strip view-model (PR-7 of
 * TODO/20260614-party-page-reimagination-plan.md).
 *
 * Covers:
 *   - Pure helpers: `chronologicalSortKey`,
 *     `parseMonthFromPeriodLabel`, `lsEventIdFromPeriodLabel`,
 *     `titleCaseStateSlug`, `pickLastContestedLabel`.
 *   - Pure SQL builders: `buildParliamentLatestSql`,
 *     `buildStateAssembliesLatestSql` - shape contract only (CAST
 *     AS BIGINT present, ROW_NUMBER pattern, no QUALIFY).
 *   - Pure projections: `projectParliamentLatest`,
 *     `projectStateAssembliesLatest`.
 *   - Outer loader `loadPartyCurrentStrength`: mocks DuckDB and
 *     drives 4 representative parties through:
 *       - BJP: full strip (Parliament + 31-state assemblies +
 *         latest = May 2026 state).
 *       - DMK: state-only party (LS + 2-state assemblies).
 *       - "LS-only" synthetic party: parliament_latest populated,
 *         state_assemblies_latest = null.
 *       - "Defunct/no-data" synthetic party: both null, returns
 *         null overall.
 *       - NOTA (sentinel): returns null before any DuckDB call.
 *
 * The test file mocks the DuckDB boundary (`../duckdb`) + the
 * canonical CSV columns helper (`../canonical/csv-columns`) so the
 * pin runs in-process with no network or DuckDB-WASM dependency.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerCsvFile: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(),
}));

import { csvColumnsClause } from "../canonical/csv-columns";
import { query, registerCsvFile } from "../duckdb";
import {
  __resetForTests,
  PARLIAMENT_TOTAL_SEATS,
  buildParliamentLatestSql,
  buildStateAssembliesLatestSql,
  chronologicalSortKey,
  loadPartyCurrentStrength,
  lsEventIdFromPeriodLabel,
  parseMonthFromPeriodLabel,
  pickLastContestedLabel,
  projectParliamentLatest,
  projectStateAssembliesLatest,
  titleCaseStateSlug,
  type ParliamentLatest,
  type StateAssembliesLatest,
} from "./party-current-strength";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);
const mockedCsvColumnsClause = vi.mocked(csvColumnsClause);

beforeEach(() => {
  __resetForTests();
  mockedQuery.mockReset();
  mockedRegisterCsvFile.mockReset();
  mockedCsvColumnsClause.mockReset();
  mockedRegisterCsvFile.mockResolvedValue(undefined);
  // The canonical csv-columns helper returns a `columns={...}` SQL
  // fragment; the loader splices it verbatim into the read_csv call.
  // The exact shape is irrelevant for the loader contract test - any
  // non-empty fragment exercises the splice path.
  mockedCsvColumnsClause.mockResolvedValue(
    "columns={'party_id': 'VARCHAR', 'body': 'VARCHAR'}",
  );
});

// --- pure helpers ---------------------------------------------------------

describe("chronologicalSortKey", () => {
  it("derives YYYY-MM key from a LsGen<Mon><Year> period_label", () => {
    expect(chronologicalSortKey("LsGenJun2024")).toBe("2024-06");
    expect(chronologicalSortKey("LsGenMay2019")).toBe("2019-05");
  });

  it("derives YYYY-MM key from a AcGen<Mon><Year> period_label", () => {
    expect(chronologicalSortKey("AcGenNov2024")).toBe("2024-11");
    expect(chronologicalSortKey("AcGenMay2026")).toBe("2026-05");
  });

  it("falls back deterministically when no <Mon><Year> suffix matches", () => {
    expect(chronologicalSortKey("garbage")).toBe("9999-99-garbage");
    expect(chronologicalSortKey("")).toBe("9999-99-");
  });
});

describe("parseMonthFromPeriodLabel", () => {
  it("extracts the citizen-facing Mon YYYY string", () => {
    expect(parseMonthFromPeriodLabel("LsGenJun2024")).toBe("Jun 2024");
    expect(parseMonthFromPeriodLabel("AcGenNov2024")).toBe("Nov 2024");
    expect(parseMonthFromPeriodLabel("AcGenMay2026")).toBe("May 2026");
  });

  it("returns null for malformed period_labels", () => {
    expect(parseMonthFromPeriodLabel("garbage")).toBeNull();
    expect(parseMonthFromPeriodLabel("")).toBeNull();
  });
});

describe("lsEventIdFromPeriodLabel", () => {
  it("derives the topic event_id slug from a LsGen<Mon><Year> label", () => {
    expect(lsEventIdFromPeriodLabel("LsGenJun2024")).toBe("general-2024");
    expect(lsEventIdFromPeriodLabel("LsGenMay2019")).toBe("general-2019");
    expect(lsEventIdFromPeriodLabel("LsGenFeb1962")).toBe("general-1962");
  });

  it("returns null for non-LS labels", () => {
    expect(lsEventIdFromPeriodLabel("AcGenNov2024")).toBeNull();
    expect(lsEventIdFromPeriodLabel("LsBye2018")).toBeNull();
    expect(lsEventIdFromPeriodLabel("")).toBeNull();
  });
});

describe("titleCaseStateSlug", () => {
  it("capitalises single-word state slugs verbatim", () => {
    expect(titleCaseStateSlug("maharashtra")).toBe("Maharashtra");
    expect(titleCaseStateSlug("gujarat")).toBe("Gujarat");
  });

  it("capitalises hyphenated state slugs word-by-word", () => {
    expect(titleCaseStateSlug("tamil-nadu")).toBe("Tamil Nadu");
    expect(titleCaseStateSlug("uttar-pradesh")).toBe("Uttar Pradesh");
  });

  it("returns empty string for empty input (defensive)", () => {
    expect(titleCaseStateSlug("")).toBe("");
  });
});

describe("pickLastContestedLabel", () => {
  const parliamentJun2024: ParliamentLatest = {
    year: 2024,
    event_id: "general-2024",
    month_label: "Jun 2024",
    seats_won: 211,
    seats_total: 543,
    vote_share_pct: 36.65,
    rank_label: null,
  };
  const assembliesMay2026: StateAssembliesLatest = {
    seats_won: 100,
    seats_total: 500,
    state_count: 5,
    latest_event_label: "West Bengal State Assembly, May 2026",
    latest_event_sort_key: "2026-05",
  };
  const assembliesOct2019: StateAssembliesLatest = {
    seats_won: 50,
    seats_total: 288,
    state_count: 1,
    latest_event_label: "Maharashtra State Assembly, Oct 2019",
    latest_event_sort_key: "2019-10",
  };

  it("picks the assembly latest when assemblies are more recent than parliament", () => {
    expect(pickLastContestedLabel(parliamentJun2024, assembliesMay2026)).toBe(
      "West Bengal State Assembly, May 2026",
    );
  });

  it("picks parliament when parliament is more recent than the assembly latest", () => {
    expect(pickLastContestedLabel(parliamentJun2024, assembliesOct2019)).toBe(
      "Parliament General Election, Jun 2024",
    );
  });

  it("picks the assembly latest when parliament is null", () => {
    expect(pickLastContestedLabel(null, assembliesMay2026)).toBe(
      "West Bengal State Assembly, May 2026",
    );
  });

  it("picks parliament when assemblies is null", () => {
    expect(pickLastContestedLabel(parliamentJun2024, null)).toBe(
      "Parliament General Election, Jun 2024",
    );
  });

  it("returns null when both inputs are null", () => {
    expect(pickLastContestedLabel(null, null)).toBeNull();
  });
});

// --- pure SQL builders ----------------------------------------------------

describe("buildParliamentLatestSql", () => {
  it("returns SQL that filters on party_id + body=parliament and CASTs SUMs", () => {
    const sql = buildParliamentLatestSql(
      "parties.IN.BJP",
      "columns={...}",
      "/data/marts/party_pages/history.csv",
    );
    expect(sql).toContain("party_id = 'parties.IN.BJP'");
    expect(sql).toContain("body = 'parliament'");
    expect(sql).toContain("CAST(SUM(seats) AS BIGINT)");
    expect(sql).toContain("CAST(SUM(party_votes) AS BIGINT)");
    expect(sql).toContain("CAST(SUM(total_votes) AS BIGINT)");
    expect(sql).toContain("GROUP BY period_label");
    expect(sql).toContain("/data/marts/party_pages/history.csv");
  });

  it("does NOT use QUALIFY (DuckDB-WASM portability)", () => {
    const sql = buildParliamentLatestSql(
      "parties.IN.BJP",
      "columns={...}",
      "/u.csv",
    );
    expect(sql).not.toMatch(/\bQUALIFY\b/);
  });
});

describe("buildStateAssembliesLatestSql", () => {
  it("returns SQL with ROW_NUMBER, full-corpus chamber JOIN, party-filtered seats", () => {
    const sql = buildStateAssembliesLatestSql(
      "parties.IN.BJP",
      "columns={...}",
      "/data/marts/party_pages/history.csv",
    );
    // The all_assembly CTE scans the full body='assembly' corpus,
    // NOT just THIS party's rows - chamber_seats requires it.
    expect(sql).toMatch(/all_assembly[\s\S]+body = 'assembly'/);
    // Per-state latest cycle uses ROW_NUMBER PARTITION BY state.
    expect(sql).toContain("ROW_NUMBER() OVER (PARTITION BY state");
    // The party_latest CTE narrows to the focal party.
    expect(sql).toContain("party_id = 'parties.IN.BJP'");
    // The chamber_seats CTE does NOT narrow to the focal party.
    expect(sql).toMatch(/chamber_latest[\s\S]+SUM\(a\.seats\)/);
    // BIGINT casts on both sums (HUGEINT trap).
    expect(sql).toContain("CAST(SUM(a.seats) AS BIGINT)");
    // Final SELECT JOINs the two halves on (state, period_label).
    expect(sql).toMatch(
      /JOIN chamber_latest c[\s\S]+ON p\.state = c\.state AND p\.period_label = c\.period_label/,
    );
  });

  it("does NOT use QUALIFY (DuckDB-WASM portability)", () => {
    const sql = buildStateAssembliesLatestSql(
      "parties.IN.BJP",
      "columns={...}",
      "/u.csv",
    );
    expect(sql).not.toMatch(/\bQUALIFY\b/);
  });
});

// --- pure projections -----------------------------------------------------

describe("projectParliamentLatest", () => {
  it("picks the chronologically latest row + computes vote_share_pct", () => {
    // 2 rows; the 2019 row has the same year as no other, the 2024
    // row should be picked. Note party_votes / total_votes returned
    // as bigint to mirror duckdb-wasm BIGINT-CAST serialisation.
    const out = projectParliamentLatest([
      {
        period_label: "LsGenMay2019",
        year: 2019,
        party_seats: 303n,
        party_votes: 229076879n,
        total_votes: 614686844n,
      },
      {
        period_label: "LsGenJun2024",
        year: 2024,
        party_seats: 211n,
        party_votes: 235974144n,
        total_votes: 643890022n,
      },
    ]);
    expect(out).not.toBeNull();
    expect(out!.year).toBe(2024);
    expect(out!.event_id).toBe("general-2024");
    expect(out!.month_label).toBe("Jun 2024");
    expect(out!.seats_won).toBe(211);
    expect(out!.seats_total).toBe(PARLIAMENT_TOTAL_SEATS);
    expect(out!.vote_share_pct).toBeCloseTo(36.65, 1);
    expect(out!.rank_label).toBeNull();
  });

  it("returns null for an empty row set (party with no LS history)", () => {
    expect(projectParliamentLatest([])).toBeNull();
  });

  it("returns null vote_share_pct when total_votes is zero", () => {
    const out = projectParliamentLatest([
      {
        period_label: "LsGenJun2024",
        year: 2024,
        party_seats: 5,
        party_votes: 0,
        total_votes: 0,
      },
    ]);
    expect(out!.vote_share_pct).toBeNull();
  });

  it("breaks ties between same-year period_labels chronologically (Jun vs Sep)", () => {
    // Synthetic shape - two LS generals in the same year (rare; the
    // current canonical corpus never has this) - the projection must
    // pick the later month chronologically, NOT alphabetically.
    const out = projectParliamentLatest([
      {
        period_label: "LsGenSep2024",
        year: 2024,
        party_seats: 10,
        party_votes: 100,
        total_votes: 1000,
      },
      {
        period_label: "LsGenJun2024",
        year: 2024,
        party_seats: 20,
        party_votes: 200,
        total_votes: 1000,
      },
    ]);
    expect(out!.month_label).toBe("Sep 2024");
    expect(out!.seats_won).toBe(10);
  });
});

describe("projectStateAssembliesLatest", () => {
  const resolver = (slug: string): string | null => {
    // Synthetic state-name resolver for the test; production callers
    // plumb the canonical `states` reactive store.
    const map: Record<string, string> = {
      "tamil-nadu": "Tamil Nadu",
      "puducherry": "Puducherry",
      "maharashtra": "Maharashtra",
      "west-bengal": "West Bengal",
    };
    return map[slug] ?? null;
  };

  it("sums seats across states + counts states + picks the chronologically latest event", () => {
    const out = projectStateAssembliesLatest(
      [
        {
          state: "maharashtra",
          period_label: "AcGenNov2024",
          year: 2024,
          party_seats: 132n,
          chamber_seats: 288n,
        },
        {
          state: "west-bengal",
          period_label: "AcGenMay2026",
          year: 2026,
          party_seats: 207n,
          chamber_seats: 294n,
        },
        {
          state: "tamil-nadu",
          period_label: "AcGenMay2026",
          year: 2026,
          party_seats: 1n,
          chamber_seats: 234n,
        },
      ],
      resolver,
    );
    expect(out).not.toBeNull();
    expect(out!.seats_won).toBe(340);
    expect(out!.seats_total).toBe(816);
    expect(out!.state_count).toBe(3);
    // 2026-05 > 2024-11, so latest is one of the 2026 states. Tie-
    // break is alphabetic state (tamil-nadu < west-bengal). Both are
    // valid; the test asserts the ordering rule the helper documents.
    expect(out!.latest_event_label).toBe("Tamil Nadu State Assembly, May 2026");
    expect(out!.latest_event_sort_key).toBe("2026-05");
  });

  it("falls back to Title Cased slug when the resolver returns null", () => {
    const out = projectStateAssembliesLatest(
      [
        {
          state: "jammu-and-kashmir",
          period_label: "AcGenOct2024",
          year: 2024,
          party_seats: 29n,
          chamber_seats: 90n,
        },
      ],
      () => null,
    );
    expect(out!.latest_event_label).toBe(
      "Jammu And Kashmir State Assembly, Oct 2024",
    );
  });

  it("returns null for an empty row set (party with no assembly history)", () => {
    expect(projectStateAssembliesLatest([], resolver)).toBeNull();
  });

  it("skips rows with null state or null period_label (defensive)", () => {
    const out = projectStateAssembliesLatest(
      [
        {
          state: null,
          period_label: "AcGenNov2024",
          year: 2024,
          party_seats: 10n,
          chamber_seats: 288n,
        },
        {
          state: "maharashtra",
          period_label: null,
          year: 2024,
          party_seats: 10n,
          chamber_seats: 288n,
        },
      ],
      resolver,
    );
    expect(out).toBeNull();
  });
});

// --- loadPartyCurrentStrength outer shape --------------------------------

describe("loadPartyCurrentStrength", () => {
  it("returns null for sentinel parties without touching DuckDB", async () => {
    const out = await loadPartyCurrentStrength("parties.IN.NOTA", {
      is_sentinel: true,
    });
    expect(out).toBeNull();
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegisterCsvFile).not.toHaveBeenCalled();
  });

  it("returns null for null / empty party_id without touching DuckDB", async () => {
    expect(await loadPartyCurrentStrength(null)).toBeNull();
    expect(await loadPartyCurrentStrength("")).toBeNull();
    expect(await loadPartyCurrentStrength(undefined)).toBeNull();
    expect(mockedQuery).not.toHaveBeenCalled();
  });

  it("returns same Promise on repeated calls for the same party_id (cache hit)", async () => {
    mockedQuery.mockResolvedValue([]);
    const p1 = loadPartyCurrentStrength("parties.IN.BJP");
    const p2 = loadPartyCurrentStrength("parties.IN.BJP");
    expect(p1).toBe(p2);
    await p1;
    // Loader still fires both queries (parliament + assemblies) once,
    // even though the rows are empty.
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });

  it("populates the full BJP-shape strip from realistic mart rows", async () => {
    // Loader fires 2 queries in parallel: parliament_latest, then
    // state_assemblies_latest. Order matches the buildParliamentLatestSql
    // + buildStateAssembliesLatestSql plumbing in fetchPartyCurrentStrength.
    mockedQuery
      .mockResolvedValueOnce([
        {
          period_label: "LsGenJun2024",
          year: 2024,
          party_seats: 211n,
          party_votes: 235974144n,
          total_votes: 643890022n,
        },
      ])
      .mockResolvedValueOnce([
        {
          state: "maharashtra",
          period_label: "AcGenNov2024",
          year: 2024,
          party_seats: 132n,
          chamber_seats: 288n,
        },
        {
          state: "west-bengal",
          period_label: "AcGenMay2026",
          year: 2026,
          party_seats: 207n,
          chamber_seats: 294n,
        },
      ]);
    const out = await loadPartyCurrentStrength("parties.IN.BJP");
    expect(out).not.toBeNull();
    expect(out!.parliament_latest).not.toBeNull();
    expect(out!.parliament_latest!.year).toBe(2024);
    expect(out!.parliament_latest!.event_id).toBe("general-2024");
    expect(out!.parliament_latest!.seats_won).toBe(211);
    expect(out!.parliament_latest!.vote_share_pct).toBeCloseTo(36.65, 1);
    expect(out!.state_assemblies_latest).not.toBeNull();
    expect(out!.state_assemblies_latest!.seats_won).toBe(339);
    expect(out!.state_assemblies_latest!.seats_total).toBe(582);
    expect(out!.state_assemblies_latest!.state_count).toBe(2);
    // 2026-05 > 2024-11 > 2024-06 - the cross-body latest is the WB
    // 2026 row (titleCaseStateSlug fallback because the loader was
    // called without an explicit stateNameFromSlug resolver).
    expect(out!.last_contested_label).toBe("West Bengal State Assembly, May 2026");
  });

  it("returns parliament-only shape for a synthetic LS-only party (state_assemblies null)", async () => {
    mockedQuery
      .mockResolvedValueOnce([
        {
          period_label: "LsGenJun2024",
          year: 2024,
          party_seats: 5n,
          party_votes: 1000n,
          total_votes: 100000n,
        },
      ])
      .mockResolvedValueOnce([]);
    const out = await loadPartyCurrentStrength("parties.IN.LS_ONLY");
    expect(out!.parliament_latest).not.toBeNull();
    expect(out!.state_assemblies_latest).toBeNull();
    expect(out!.last_contested_label).toBe(
      "Parliament General Election, Jun 2024",
    );
  });

  it("returns assemblies-only shape for a state-party (parliament null)", async () => {
    mockedQuery
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          state: "tamil-nadu",
          period_label: "AcGenMay2026",
          year: 2026,
          party_seats: 59n,
          chamber_seats: 234n,
        },
      ]);
    const out = await loadPartyCurrentStrength("parties.IN.DMK", {
      stateNameFromSlug: (slug) => (slug === "tamil-nadu" ? "Tamil Nadu" : null),
    });
    expect(out!.parliament_latest).toBeNull();
    expect(out!.state_assemblies_latest).not.toBeNull();
    expect(out!.state_assemblies_latest!.seats_won).toBe(59);
    expect(out!.state_assemblies_latest!.state_count).toBe(1);
    expect(out!.last_contested_label).toBe("Tamil Nadu State Assembly, May 2026");
  });

  it("returns null overall when both bodies have no data (defunct / unknown party)", async () => {
    mockedQuery.mockResolvedValue([]);
    const out = await loadPartyCurrentStrength("parties.IN.NONEXISTENT");
    expect(out).toBeNull();
  });

  it("clears the cache on fetch error so a retry re-issues the queries", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("network gone"));
    await expect(loadPartyCurrentStrength("parties.IN.BJP")).rejects.toThrow(
      "network gone",
    );
    // Cache entry cleared - retry should re-fire the queries.
    mockedQuery.mockResolvedValue([]);
    const second = await loadPartyCurrentStrength("parties.IN.BJP");
    expect(second).toBeNull();
  });
});
