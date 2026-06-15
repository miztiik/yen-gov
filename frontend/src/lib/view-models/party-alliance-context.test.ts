/**
 * `party-alliance-context.test.ts` - vitest pin for the Alliance
 * Context view-model (PR-8 of TODO/20260614-party-page-reimagination
 * -plan.md).
 *
 * Covers:
 *   - Pure helpers: `eventIdToYear`, `parliamentEventLabel`,
 *     `stateAssemblyEventLabel`, `stripAllianceYearSuffix`,
 *     `titleCaseStateSlug`, `pickRoleFromSeats`.
 *   - Pure SQL builders: `buildFocalAllianceSql`,
 *     `buildPartnerAllianceSql`, `buildSeatsSql` (shape contract:
 *     CAST AS BIGINT present, no QUALIFY, empty input -> safe no-op
 *     SQL that returns zero rows).
 *   - Pure projection: `projectAllianceContext` with synthetic
 *     inputs spanning the BJP-led-NDA case, INC-led-INDIA case, AAP
 *     no-Parliament case, state-only party, alone-state case, and
 *     null when both bodies empty.
 *   - Outer loader: cache behaviour, sentinel + IND short-circuits,
 *     null/empty party_id, error path resets the cache.
 *
 * Mocks the DuckDB boundary + canonical CSV-columns helper so the
 * pin runs in-process. Mirrors the PR-7 `party-current-strength.
 * test.ts` shape verbatim.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerCsvFile: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(),
}));

// `loadAllPartiesMeta` + `fetchStates` are the in-loader resolver
// sources for short-name + state-name lookups. Tests mock both to
// empty by default; the "BJP full roundtrip" / AAP tests still pass
// explicit `partyShortFromId` / `stateNameFromSlug` overrides which
// short-circuit the loader's resolver-fetch branch entirely.
vi.mock("./parties", () => ({
  loadAllPartiesMeta: vi.fn(() => Promise.resolve(new Map())),
}));

vi.mock("../data", () => ({
  fetchStates: vi.fn(() =>
    Promise.resolve({
      $schema: "",
      $schema_version: "1.0",
      sources: [],
      country: "IN",
      states: [],
    }),
  ),
}));

import { csvColumnsClause } from "../canonical/csv-columns";
import { query, registerCsvFile } from "../duckdb";
import {
  __resetForTests,
  buildFocalAllianceSql,
  buildPartnerAllianceSql,
  buildSeatsSql,
  eventIdToYear,
  loadPartyAllianceContext,
  parliamentEventLabel,
  pickRoleFromSeats,
  projectAllianceContext,
  stateAssemblyEventLabel,
  stripAllianceYearSuffix,
  titleCaseStateSlug,
} from "./party-alliance-context";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);
const mockedCsvColumnsClause = vi.mocked(csvColumnsClause);

beforeEach(() => {
  __resetForTests();
  mockedQuery.mockReset();
  mockedRegisterCsvFile.mockReset();
  mockedCsvColumnsClause.mockReset();
  mockedRegisterCsvFile.mockResolvedValue(undefined);
  mockedCsvColumnsClause.mockResolvedValue(
    "columns={'party_id': 'VARCHAR', 'event_id': 'VARCHAR'}",
  );
});

// --- pure helpers ---------------------------------------------------------

describe("eventIdToYear", () => {
  it("extracts 4-digit year suffix", () => {
    expect(eventIdToYear("general-2024")).toBe(2024);
    expect(eventIdToYear("general-2019")).toBe(2019);
    expect(eventIdToYear("assembly-2026")).toBe(2026);
  });

  it("returns null when no 4-digit suffix", () => {
    expect(eventIdToYear("general")).toBeNull();
    expect(eventIdToYear("")).toBeNull();
    expect(eventIdToYear("general-202")).toBeNull();
  });
});

describe("parliamentEventLabel", () => {
  it("formats as 'Parliament <year>'", () => {
    expect(parliamentEventLabel("general-2024")).toBe("Parliament 2024");
    expect(parliamentEventLabel("general-2019")).toBe("Parliament 2019");
    expect(parliamentEventLabel("general-2014")).toBe("Parliament 2014");
  });

  it("falls back to event_id verbatim when no year matches", () => {
    expect(parliamentEventLabel("garbage")).toBe("garbage");
  });
});

describe("stateAssemblyEventLabel", () => {
  it("formats as '<State> (<year>)'", () => {
    expect(stateAssemblyEventLabel("Maharashtra", "assembly-2024")).toBe(
      "Maharashtra (2024)",
    );
    expect(stateAssemblyEventLabel("Bihar", "assembly-2020")).toBe(
      "Bihar (2020)",
    );
  });

  it("falls back to '<State> (<event_id>)' when no year matches", () => {
    expect(stateAssemblyEventLabel("Kerala", "garbage")).toBe(
      "Kerala (garbage)",
    );
  });
});

describe("stripAllianceYearSuffix", () => {
  it("strips trailing -YYYY", () => {
    expect(stripAllianceYearSuffix("NDA-2024")).toBe("NDA");
    expect(stripAllianceYearSuffix("INDIA-2024")).toBe("INDIA");
    expect(stripAllianceYearSuffix("UPA-2014")).toBe("UPA");
  });

  it("leaves unsuffixed names untouched", () => {
    expect(stripAllianceYearSuffix("Mahayuti")).toBe("Mahayuti");
    expect(stripAllianceYearSuffix("MVA")).toBe("MVA");
    expect(stripAllianceYearSuffix("LDF")).toBe("LDF");
    expect(stripAllianceYearSuffix("UDF")).toBe("UDF");
  });

  it("only strips the final -YYYY (preserves internal dashes)", () => {
    expect(stripAllianceYearSuffix("Some-Alliance-2024")).toBe("Some-Alliance");
  });
});

describe("titleCaseStateSlug", () => {
  it("converts slug to Title Case", () => {
    expect(titleCaseStateSlug("maharashtra")).toBe("Maharashtra");
    expect(titleCaseStateSlug("tamil-nadu")).toBe("Tamil Nadu");
    expect(titleCaseStateSlug("uttar-pradesh")).toBe("Uttar Pradesh");
  });

  it("lowercases connector words (and, of, the) after the first word", () => {
    // J&K alliance ledger uses the old seed slug `jammu-and-kashmir`
    // (canonical display is "Jammu and Kashmir (UT)"); the fallback
    // path must render "and" lowercase to match conventional prose.
    expect(titleCaseStateSlug("jammu-and-kashmir")).toBe("Jammu and Kashmir");
    expect(titleCaseStateSlug("dadra-and-nagar-haveli")).toBe(
      "Dadra and Nagar Haveli",
    );
    // First word keeps its capital even when it would otherwise
    // match the connector list.
    expect(titleCaseStateSlug("and-test")).toBe("And Test");
  });

  it("handles empty slug", () => {
    expect(titleCaseStateSlug("")).toBe("");
  });
});

describe("pickRoleFromSeats", () => {
  it("returns 'alone' when partner_seats is empty", () => {
    expect(pickRoleFromSeats(100, [])).toBe("alone");
    expect(pickRoleFromSeats(0, [])).toBe("alone");
  });

  it("returns 'led' when focal has at least as many seats as max partner", () => {
    expect(pickRoleFromSeats(240, [16, 12, 8])).toBe("led");
    expect(pickRoleFromSeats(100, [100, 50])).toBe("led"); // tie favours focal
    expect(pickRoleFromSeats(50, [50])).toBe("led"); // tie favours focal
  });

  it("returns 'junior' when at least one partner has more seats", () => {
    expect(pickRoleFromSeats(16, [240, 12])).toBe("junior");
    expect(pickRoleFromSeats(0, [10])).toBe("junior");
  });
});

// --- pure SQL builders ----------------------------------------------------

describe("buildFocalAllianceSql", () => {
  it("filters by the focal party_id and orders by event_id DESC", () => {
    const sql = buildFocalAllianceSql(
      "parties.IN.BJP",
      "columns={'party_id': 'VARCHAR'}",
      "/data/data/entities/party_alliances.csv",
    );
    expect(sql).toContain("party_id = 'parties.IN.BJP'");
    expect(sql).toContain("ORDER BY event_id DESC, state");
    expect(sql).toContain("/data/data/entities/party_alliances.csv");
    expect(sql).not.toMatch(/\bQUALIFY\b/);
  });
});

describe("buildPartnerAllianceSql", () => {
  it("returns no-op SQL when focal_alliance_keys is empty", () => {
    const sql = buildPartnerAllianceSql(
      [],
      "columns={}",
      "/data/data/entities/party_alliances.csv",
    );
    expect(sql).toContain("WHERE 1 = 0");
  });

  it("builds a JOIN against a literal VALUES list", () => {
    const sql = buildPartnerAllianceSql(
      [
        { event_id: "general-2024", state: "IN", alliance: "NDA-2024" },
        {
          event_id: "assembly-2024",
          state: "maharashtra",
          alliance: "Mahayuti",
        },
      ],
      "columns={}",
      "/data/data/entities/party_alliances.csv",
    );
    expect(sql).toContain("VALUES");
    expect(sql).toContain("('general-2024', 'IN', 'NDA-2024')");
    expect(sql).toContain("('assembly-2024', 'maharashtra', 'Mahayuti')");
    expect(sql).toContain("JOIN focal_keys");
    expect(sql).not.toMatch(/\bQUALIFY\b/);
  });
});

describe("buildSeatsSql", () => {
  it("returns no-op SQL when seat_lookups is empty", () => {
    const sql = buildSeatsSql(
      [],
      "columns={}",
      "/data/data/marts/party_pages/history.csv",
    );
    expect(sql).toContain("WHERE 1 = 0");
  });

  it("builds a JOIN against a literal VALUES list and CASTs SUM AS BIGINT", () => {
    const sql = buildSeatsSql(
      [
        { party_id: "parties.IN.BJP", year: 2024, body: "parliament" },
        { party_id: "parties.IN.JDU", year: 2024, body: "parliament" },
      ],
      "columns={}",
      "/data/data/marts/party_pages/history.csv",
    );
    expect(sql).toContain("VALUES");
    expect(sql).toContain("('parties.IN.BJP', 2024, 'parliament')");
    expect(sql).toContain("CAST(SUM(h.seats) AS BIGINT)");
    expect(sql).toContain("GROUP BY h.party_id, h.body, h.year, h.state");
    expect(sql).not.toMatch(/\bQUALIFY\b/);
  });
});

// --- projectAllianceContext ----------------------------------------------

describe("projectAllianceContext", () => {
  const partyShort = (pid: string): string | null => {
    const map: Record<string, string> = {
      "parties.IN.BJP": "BJP",
      "parties.IN.JDU": "JD(U)",
      "parties.IN.TDP": "TDP",
      "parties.IN.INC": "INC",
      "parties.IN.DMK": "DMK",
      "parties.IN.SHSUBT": "SHS(UBT)",
      "parties.IN.NCPSP": "NCP(SP)",
    };
    return map[pid] ?? null;
  };
  const stateName = (slug: string): string | null => {
    const map: Record<string, string> = {
      maharashtra: "Maharashtra",
      bihar: "Bihar",
      "tamil-nadu": "Tamil Nadu",
    };
    return map[slug] ?? null;
  };

  it("returns null when both bodies are empty", () => {
    const result = projectAllianceContext(
      "parties.IN.BJP",
      [],
      [],
      new Map(),
      partyShort,
      stateName,
    );
    expect(result).toBeNull();
  });

  it("BJP general-2024: led NDA with JD(U) + TDP partners", () => {
    const focal_rows = [
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
    ];
    const partner_rows = [
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.JDU",
      },
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.TDP",
      },
    ];
    const seat_map = new Map<string, number>();
    // Parliament rows are per-state in the mart; seed two state-rows
    // per party so the prefix-sum helper exercises the cross-state
    // aggregation path.
    seat_map.set("parties.IN.BJP\u0001parliament\u00012024\u0001UP", 33);
    seat_map.set("parties.IN.BJP\u0001parliament\u00012024\u0001MH", 178);
    seat_map.set("parties.IN.JDU\u0001parliament\u00012024\u0001BR", 12);
    seat_map.set("parties.IN.TDP\u0001parliament\u00012024\u0001AP", 16);
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      partner_rows,
      seat_map,
      partyShort,
      stateName,
    );
    expect(result).not.toBeNull();
    expect(result!.parliament).not.toBeNull();
    expect(result!.parliament!.event_label).toBe("Parliament 2024");
    expect(result!.parliament!.alliance).toBe("NDA");
    expect(result!.parliament!.role).toBe("led");
    expect(result!.parliament!.partner_count).toBe(2);
    // TDP (16) sorts before JD(U) (12) by seats DESC.
    expect(result!.parliament!.partner_names_top).toEqual(["TDP", "JD(U)"]);
    // 211 (BJP) + 16 (TDP) + 12 (JD(U)) = 239.
    expect(result!.parliament!.total_alliance_seats).toBe(239);
    expect(result!.state_assemblies).toEqual([]);
  });

  it("focal Parliament with empty alliance string is dropped from the section", () => {
    const focal_rows = [
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "",
        party_id: "parties.IN.AAP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.AAP",
      focal_rows,
      [],
      new Map(),
      partyShort,
      stateName,
    );
    // AAP carries alliance="" rows only -> parliament=null +
    // state_assemblies=[] -> overall null.
    expect(result).toBeNull();
  });

  it("state-Assembly alliance: Mahayuti led by BJP in Maharashtra 2024", () => {
    const focal_rows = [
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "Mahayuti",
        party_id: "parties.IN.BJP",
      },
    ];
    const partner_rows = [
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "Mahayuti",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "Mahayuti",
        party_id: "parties.IN.SHSUBT",
      },
    ];
    const seat_map = new Map<string, number>();
    seat_map.set(
      "parties.IN.BJP\u0001assembly\u00012024\u0001maharashtra",
      132,
    );
    seat_map.set(
      "parties.IN.SHSUBT\u0001assembly\u00012024\u0001maharashtra",
      20,
    );
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      partner_rows,
      seat_map,
      partyShort,
      stateName,
    );
    expect(result).not.toBeNull();
    expect(result!.parliament).toBeNull();
    expect(result!.state_assemblies).toHaveLength(1);
    const row = result!.state_assemblies[0]!;
    expect(row.state).toBe("maharashtra");
    expect(row.state_name).toBe("Maharashtra");
    expect(row.event_label).toBe("Maharashtra (2024)");
    expect(row.alliance).toBe("Mahayuti");
    expect(row.role).toBe("led");
    expect(row.partner_count).toBe(1);
    expect(row.partner_names_top).toEqual(["SHS(UBT)"]);
    expect(row.total_alliance_seats).toBe(152);
  });

  it("state Assembly contested alone surfaces as role='alone' with alliance=null", () => {
    const focal_rows = [
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
    ];
    const seat_map = new Map<string, number>();
    seat_map.set(
      "parties.IN.BJP\u0001assembly\u00012024\u0001maharashtra",
      50,
    );
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      [],
      seat_map,
      partyShort,
      stateName,
    );
    expect(result).not.toBeNull();
    expect(result!.state_assemblies).toHaveLength(1);
    const row = result!.state_assemblies[0]!;
    expect(row.alliance).toBeNull();
    expect(row.role).toBe("alone");
    expect(row.partner_count).toBe(0);
    expect(row.partner_names_top).toEqual([]);
    expect(row.total_alliance_seats).toBe(50);
  });

  it("alliance row with no partner seats degrades to role='alone'", () => {
    // Per user-memory 2026-06-14: alliance rows can ship without
    // candidacies CSV. When the alliance is named but no partner
    // seats are in the mart, the role degrades to "alone" with
    // empty partners list.
    const focal_rows = [
      {
        event_id: "assembly-2024",
        state: "bihar",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
    ];
    const partner_rows = [
      {
        event_id: "assembly-2024",
        state: "bihar",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      partner_rows,
      new Map(),
      partyShort,
      stateName,
    );
    expect(result).not.toBeNull();
    expect(result!.state_assemblies).toHaveLength(1);
    const row = result!.state_assemblies[0]!;
    expect(row.role).toBe("alone");
    expect(row.partner_count).toBe(0);
  });

  it("picks MAX(event_id) per state when focal has multiple cycles", () => {
    const focal_rows = [
      {
        event_id: "assembly-2019",
        state: "maharashtra",
        alliance: "MVA-2019",
        party_id: "parties.IN.INC",
      },
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "MVA-2024",
        party_id: "parties.IN.INC",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.INC",
      focal_rows,
      [],
      new Map(),
      partyShort,
      stateName,
    );
    expect(result).not.toBeNull();
    expect(result!.state_assemblies).toHaveLength(1);
    // 2024 wins over 2019.
    expect(result!.state_assemblies[0]!.event_id).toBe("assembly-2024");
    expect(result!.state_assemblies[0]!.alliance).toBe("MVA");
  });

  it("state_assemblies are sorted alphabetically by state slug", () => {
    const focal_rows = [
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2020",
        state: "bihar",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      [],
      new Map(),
      partyShort,
      stateName,
    );
    expect(result!.state_assemblies.map((r) => r.state)).toEqual([
      "bihar",
      "maharashtra",
    ]);
  });

  it("falls back to titleCaseStateSlug when stateNameFromSlug returns null", () => {
    const focal_rows = [
      {
        event_id: "assembly-2024",
        state: "tripura",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      [],
      new Map(),
      partyShort,
      () => null,
    );
    expect(result!.state_assemblies[0]!.state_name).toBe("Tripura");
  });

  it("falls back to party_id when partyShortFromId returns null", () => {
    const focal_rows = [
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
    ];
    const partner_rows = [
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.UNKNOWN_PARTY",
      },
    ];
    const seat_map = new Map<string, number>();
    seat_map.set("parties.IN.BJP\u0001parliament\u00012024\u0001IN", 211);
    seat_map.set(
      "parties.IN.UNKNOWN_PARTY\u0001parliament\u00012024\u0001IN",
      5,
    );
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      partner_rows,
      seat_map,
      () => null,
      stateName,
    );
    expect(result!.parliament!.partner_names_top).toEqual([
      "parties.IN.UNKNOWN_PARTY",
    ]);
  });

  it("truncates partner_names_top at MAX_PARTNER_NAMES (5)", () => {
    const focal_rows = [
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "BIG-2024",
        party_id: "parties.IN.BJP",
      },
    ];
    const partner_rows = [
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "BIG-2024",
        party_id: "parties.IN.BJP",
      },
      ...Array.from({ length: 7 }, (_, i) => ({
        event_id: "general-2024",
        state: "IN",
        alliance: "BIG-2024",
        party_id: `parties.IN.P${i}`,
      })),
    ];
    const seat_map = new Map<string, number>();
    seat_map.set("parties.IN.BJP\u0001parliament\u00012024\u0001IN", 100);
    for (let i = 0; i < 7; i += 1) {
      seat_map.set(
        `parties.IN.P${i}\u0001parliament\u00012024\u0001IN`,
        10 + i, // P6=16, P5=15, ... P0=10
      );
    }
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      partner_rows,
      seat_map,
      (pid) => pid,
      stateName,
    );
    expect(result!.parliament!.partner_count).toBe(7);
    expect(result!.parliament!.partner_names_top).toHaveLength(5);
    // Top 5 by seats DESC: P6 (16), P5 (15), P4 (14), P3 (13), P2 (12).
    expect(result!.parliament!.partner_names_top).toEqual([
      "parties.IN.P6",
      "parties.IN.P5",
      "parties.IN.P4",
      "parties.IN.P3",
      "parties.IN.P2",
    ]);
  });

  // PR-11 of TODO/20260615-party-page-citizen-fixes-plan.md (Jony +
  // Citizen): the citizen-facing strip caps to events with year >=
  // cutoff_year. Older alliance ledger rows survive in the canonical
  // CSV (the cap is render-only); the projection just drops them
  // from BOTH the Parliament pick and the per-state list. These
  // tests pin the cap independently of the runtime year used in
  // production (which is `new Date().getFullYear() - 10`).

  it("PR-11 cap: drops Parliament pick whose year < cutoff_year", () => {
    const focal_rows = [
      {
        event_id: "general-2014",
        state: "IN",
        alliance: "NDA-2014",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      focal_rows, // partner_rows = focal_rows (BJP solo in NDA-2014)
      new Map(),
      partyShort,
      stateName,
      2020, // cutoff: only events with year >= 2020 survive
    );
    // Only Parliament row was 2014 < 2020 -> dropped -> entire
    // projection returns null (state_assemblies also empty).
    expect(result).toBeNull();
  });

  it("PR-11 cap: keeps Parliament pick whose year >= cutoff_year (boundary)", () => {
    const focal_rows = [
      {
        event_id: "general-2020",
        state: "IN",
        alliance: "NDA-2020",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      focal_rows,
      new Map(),
      partyShort,
      stateName,
      2020, // boundary: year == cutoff -> INCLUDED
    );
    expect(result).not.toBeNull();
    expect(result!.parliament).not.toBeNull();
    expect(result!.parliament!.event_id).toBe("general-2020");
  });

  it("PR-11 cap: drops per-state Assembly rows whose year < cutoff_year", () => {
    const focal_rows = [
      {
        event_id: "assembly-2009",
        state: "maharashtra",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2010",
        state: "bihar",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2025",
        state: "kerala",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      [],
      new Map(),
      partyShort,
      stateName,
      2020, // cutoff: maharashtra picks 2024 (>=2020 OK), bihar
      // picks 2010 (<2020 DROP), kerala 2025 (>=2020 OK).
    );
    expect(result).not.toBeNull();
    expect(
      result!.state_assemblies.map((r) => `${r.state}:${r.event_id}`),
    ).toEqual(["kerala:assembly-2025", "maharashtra:assembly-2024"]);
  });

  it("PR-11 cap: returns null when EVERY row is older than cutoff", () => {
    const focal_rows = [
      {
        event_id: "general-2009",
        state: "IN",
        alliance: "NDA-2009",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2010",
        state: "bihar",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      focal_rows,
      new Map(),
      partyShort,
      stateName,
      2020,
    );
    expect(result).toBeNull();
  });

  it("PR-11 cap: omitting cutoff_year disables the cap (no-cap default)", () => {
    const focal_rows = [
      {
        event_id: "assembly-2009",
        state: "bihar",
        alliance: "",
        party_id: "parties.IN.BJP",
      },
    ];
    const result = projectAllianceContext(
      "parties.IN.BJP",
      focal_rows,
      [],
      new Map(),
      partyShort,
      stateName,
      // cutoff_year omitted -> Number.NEGATIVE_INFINITY -> no cap.
    );
    expect(result).not.toBeNull();
    expect(result!.state_assemblies).toHaveLength(1);
    expect(result!.state_assemblies[0]!.event_id).toBe("assembly-2009");
  });
});

// --- loader contract ------------------------------------------------------

describe("loadPartyAllianceContext", () => {
  it("returns null for null/empty party_id without touching DuckDB", async () => {
    await expect(loadPartyAllianceContext(null)).resolves.toBeNull();
    await expect(loadPartyAllianceContext(undefined)).resolves.toBeNull();
    await expect(loadPartyAllianceContext("")).resolves.toBeNull();
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegisterCsvFile).not.toHaveBeenCalled();
  });

  it("returns null for is_sentinel parties without touching DuckDB", async () => {
    await expect(
      loadPartyAllianceContext("parties.IN.NOTA", { is_sentinel: true }),
    ).resolves.toBeNull();
    await expect(
      loadPartyAllianceContext("parties.IN.UNK", { is_sentinel: true }),
    ).resolves.toBeNull();
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegisterCsvFile).not.toHaveBeenCalled();
  });

  it("returns null for Independent (parties.IN.IND) without touching DuckDB", async () => {
    await expect(
      loadPartyAllianceContext("parties.IN.IND"),
    ).resolves.toBeNull();
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegisterCsvFile).not.toHaveBeenCalled();
  });

  it("caches the Promise per party_id", async () => {
    mockedQuery.mockResolvedValue([]);
    const p1 = loadPartyAllianceContext("parties.IN.BJP");
    const p2 = loadPartyAllianceContext("parties.IN.BJP");
    expect(p1).toBe(p2);
    await Promise.all([p1, p2]);
    // Only one round of focal-ledger fetch (Step 1) - partners +
    // seats both skipped because focal_rows is empty.
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("returns null when focal has no alliance rows", async () => {
    mockedQuery.mockResolvedValueOnce([]); // focal_rows empty
    const result = await loadPartyAllianceContext("parties.IN.NEW");
    expect(result).toBeNull();
  });

  it("BJP general-2024 full roundtrip yields NDA Parliament + state assemblies", async () => {
    // Step 1: focal alliance ledger.
    mockedQuery.mockResolvedValueOnce([
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "Mahayuti",
        party_id: "parties.IN.BJP",
      },
    ]);
    // Step 3: partner rows (full alliance roster).
    mockedQuery.mockResolvedValueOnce([
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "general-2024",
        state: "IN",
        alliance: "NDA-2024",
        party_id: "parties.IN.JDU",
      },
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "Mahayuti",
        party_id: "parties.IN.BJP",
      },
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "Mahayuti",
        party_id: "parties.IN.SHS",
      },
    ]);
    // Step 5: seat rows from the history mart.
    mockedQuery.mockResolvedValueOnce([
      {
        party_id: "parties.IN.BJP",
        body: "parliament",
        year: 2024,
        state: "uttar-pradesh",
        seats: 33,
      },
      {
        party_id: "parties.IN.BJP",
        body: "parliament",
        year: 2024,
        state: "madhya-pradesh",
        seats: 29,
      },
      {
        party_id: "parties.IN.JDU",
        body: "parliament",
        year: 2024,
        state: "bihar",
        seats: 12,
      },
      {
        party_id: "parties.IN.BJP",
        body: "assembly",
        year: 2024,
        state: "maharashtra",
        seats: 132,
      },
      {
        party_id: "parties.IN.SHS",
        body: "assembly",
        year: 2024,
        state: "maharashtra",
        seats: 57,
      },
    ]);
    const result = await loadPartyAllianceContext("parties.IN.BJP", {
      stateNameFromSlug: (slug) =>
        slug === "maharashtra" ? "Maharashtra" : null,
      partyShortFromId: (pid) => {
        if (pid === "parties.IN.JDU") return "JD(U)";
        if (pid === "parties.IN.SHS") return "SHS";
        if (pid === "parties.IN.BJP") return "BJP";
        return null;
      },
    });
    expect(result).not.toBeNull();
    expect(result!.parliament).not.toBeNull();
    expect(result!.parliament!.alliance).toBe("NDA");
    expect(result!.parliament!.role).toBe("led"); // 62 > 12
    expect(result!.parliament!.partner_names_top).toEqual(["JD(U)"]);
    expect(result!.state_assemblies).toHaveLength(1);
    expect(result!.state_assemblies[0]!.alliance).toBe("Mahayuti");
    expect(result!.state_assemblies[0]!.role).toBe("led"); // 132 > 57
    expect(result!.state_assemblies[0]!.partner_names_top).toEqual(["SHS"]);
  });

  it("skips partner-roster + seat-fetch queries when focal carries only alone rows", async () => {
    // Focal has 2 alliance="" rows; no partner-roster fetch needed.
    mockedQuery.mockResolvedValueOnce([
      {
        event_id: "assembly-2024",
        state: "maharashtra",
        alliance: "",
        party_id: "parties.IN.AAP",
      },
      {
        event_id: "assembly-2024",
        state: "delhi",
        alliance: "",
        party_id: "parties.IN.AAP",
      },
    ]);
    // Step 5: seats for focal alone (one row each).
    mockedQuery.mockResolvedValueOnce([
      {
        party_id: "parties.IN.AAP",
        body: "assembly",
        year: 2024,
        state: "maharashtra",
        seats: 0,
      },
      {
        party_id: "parties.IN.AAP",
        body: "assembly",
        year: 2024,
        state: "delhi",
        seats: 62,
      },
    ]);
    const result = await loadPartyAllianceContext("parties.IN.AAP", {
      stateNameFromSlug: (slug) => {
        if (slug === "maharashtra") return "Maharashtra";
        if (slug === "delhi") return "Delhi";
        return null;
      },
    });
    expect(result).not.toBeNull();
    expect(result!.parliament).toBeNull();
    expect(result!.state_assemblies).toHaveLength(2);
    expect(result!.state_assemblies.every((r) => r.role === "alone")).toBe(
      true,
    );
    // Only 2 DuckDB calls: focal + seats. Partner-roster fetch skipped.
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });

  it("clears the cache entry on error so retries re-issue", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("boom"));
    await expect(
      loadPartyAllianceContext("parties.IN.BJP"),
    ).rejects.toThrow("boom");
    // Retry: cache cleared, fresh round.
    mockedQuery.mockResolvedValueOnce([]);
    await expect(
      loadPartyAllianceContext("parties.IN.BJP"),
    ).resolves.toBeNull();
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });
});
