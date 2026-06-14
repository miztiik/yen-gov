// PR-1 vitest for `view-models/parties.ts`.
//
// Per CLAUDE.md section 15: the loader's contract IS the DuckDB-WASM
// boundary - mocking `query` / `registerCsvFile` / `csvColumnsClause`
// is the explicit carve-out from Holy Law #7 (no mocks). The §13
// in-browser smoke verifies the real-CSV round-trip on a route that
// renders a PartyPill (today: /dev/charts; from PR-2 onward: every
// citizen-facing party reference).

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerCsvFile: vi.fn(async () => undefined),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async (path: string) => {
    if (path.includes("parties_leadership")) {
      // PR-11: leadership shape mirrors
      // datasets/data/_schema/columns.json entry for
      // datasets/data/entities/parties_leadership.csv (all 7 columns
      // are VARCHAR). The exact string is opaque to the test because
      // `query` is mocked - the loader only feeds this string into a
      // SQL template that the mock never executes.
      return "columns={'party_id': 'VARCHAR', 'role': 'VARCHAR', 'person_name': 'VARCHAR', 'person_wikidata_qid': 'VARCHAR', 'valid_from': 'VARCHAR', 'valid_to': 'VARCHAR', 'source_id': 'VARCHAR'}";
    }
    return "columns={'party_id': 'VARCHAR', 'short': 'VARCHAR', 'full': 'VARCHAR', 'founded_year': 'BIGINT', 'dissolved_year': 'BIGINT', 'recognition_scope': 'VARCHAR', 'home_state_codes': 'VARCHAR', 'symbol_asset': 'VARCHAR', 'brand_colour': 'VARCHAR', 'wikipedia': 'VARCHAR', 'name_native_script': 'VARCHAR', 'is_sentinel': 'BOOLEAN'}";
  }),
}));

import { query, registerCsvFile } from "../duckdb";
import {
  __resetForTests,
  formatLeaderSince,
  loadAllParties,
  loadAllPartiesMeta,
  loadCurrentLeaders,
  loadPartyLeader,
  loadPartyMeta,
  toCurrentLeader,
  toPartyMeta,
  toPartySummary,
} from "./parties";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);

beforeEach(() => {
  __resetForTests();
  mockedQuery.mockReset();
  mockedRegisterCsvFile.mockReset();
  mockedRegisterCsvFile.mockResolvedValue(undefined);
});

// --- pure projection -------------------------------------------------------

describe("toPartyMeta", () => {
  it("normalises empty strings on optional columns to null", () => {
    const meta = toPartyMeta({
      party_id: "parties.IN.BJP",
      short: "BJP",
      full: "Bharatiya Janata Party",
      founded_year: 1980,
      dissolved_year: null,
      recognition_scope: "national",
      home_state_codes: "",
      symbol_asset: "",
      brand_colour: "#ea580c",
      wikipedia: "",
      name_native_script: "",
      is_sentinel: false,
    });
    expect(meta).not.toBeNull();
    expect(meta!.party_id).toBe("parties.IN.BJP");
    expect(meta!.short).toBe("BJP");
    expect(meta!.full).toBe("Bharatiya Janata Party");
    expect(meta!.founded_year).toBe(1980);
    expect(meta!.dissolved_year).toBeNull();
    expect(meta!.recognition_scope).toBe("national");
    expect(meta!.home_state_codes).toEqual([]);
    expect(meta!.symbol_asset).toBeNull();
    expect(meta!.brand_colour).toBe("#ea580c");
    expect(meta!.wikipedia).toBeNull();
    expect(meta!.name_native_script).toBeNull();
    expect(meta!.is_sentinel).toBe(false);
  });

  it("splits pipe-delimited home_state_codes", () => {
    const meta = toPartyMeta({
      party_id: "parties.IN.AAAP",
      short: "AAAP",
      full: "Aapki Apni Adhikar Party",
      founded_year: null,
      dissolved_year: null,
      recognition_scope: null,
      home_state_codes: "IN-BR|IN-HR",
      symbol_asset: null,
      brand_colour: null,
      wikipedia: null,
      name_native_script: null,
      is_sentinel: null,
    });
    expect(meta!.home_state_codes).toEqual(["IN-BR", "IN-HR"]);
  });

  it("coerces bigint founded_year (DuckDB BIGINT round-trip) to number", () => {
    const meta = toPartyMeta({
      party_id: "parties.IN.AAP",
      short: "AAP",
      full: "Aam Aadmi Party",
      founded_year: 2012n as unknown as bigint,
      dissolved_year: null,
      recognition_scope: "national",
      home_state_codes: null,
      symbol_asset: "party-symbols/broom.png",
      brand_colour: "#0072B0",
      wikipedia: "https://en.wikipedia.org/wiki/Aam_Aadmi_Party",
      name_native_script: "आम आदमी पार्टी",
      is_sentinel: null,
    });
    expect(meta!.founded_year).toBe(2012);
    expect(typeof meta!.founded_year).toBe("number");
    expect(meta!.symbol_asset).toBe("party-symbols/broom.png");
    expect(meta!.name_native_script).toBe("आम आदमी पार्टी");
  });

  it("flags sentinel rows (NOTA) via is_sentinel=true", () => {
    const meta = toPartyMeta({
      party_id: "parties.IN.NOTA",
      short: "NOTA",
      full: "None of the Above",
      founded_year: 2013,
      dissolved_year: null,
      recognition_scope: "sentinel",
      home_state_codes: null,
      symbol_asset: null,
      brand_colour: null,
      wikipedia: null,
      name_native_script: null,
      is_sentinel: true,
    });
    expect(meta!.is_sentinel).toBe(true);
    expect(meta!.recognition_scope).toBe("sentinel");
  });

  it("returns null when party_id is empty (defensive guard)", () => {
    const meta = toPartyMeta({
      party_id: "",
      short: "anything",
      full: null,
      founded_year: null,
      dissolved_year: null,
      recognition_scope: null,
      home_state_codes: null,
      symbol_asset: null,
      brand_colour: null,
      wikipedia: null,
      name_native_script: null,
      is_sentinel: null,
    });
    expect(meta).toBeNull();
  });

  it("falls back to party_id when short is blank (defensive vs schema bump)", () => {
    const meta = toPartyMeta({
      party_id: "parties.IN.MISSING_SHORT",
      short: "",
      full: null,
      founded_year: null,
      dissolved_year: null,
      recognition_scope: null,
      home_state_codes: null,
      symbol_asset: null,
      brand_colour: null,
      wikipedia: null,
      name_native_script: null,
      is_sentinel: null,
    });
    expect(meta!.short).toBe("parties.IN.MISSING_SHORT");
  });
});

// --- loader cache ---------------------------------------------------------

describe("loadAllPartiesMeta", () => {
  it("returns the SAME Promise on repeated calls (module-level cache hit)", async () => {
    mockedQuery.mockResolvedValue([
      {
        party_id: "parties.IN.BJP",
        short: "BJP",
        full: "Bharatiya Janata Party",
        founded_year: 1980,
        dissolved_year: null,
        recognition_scope: "national",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: "#ea580c",
        wikipedia: null,
        name_native_script: null,
        is_sentinel: false,
      },
    ]);

    const p1 = loadAllPartiesMeta();
    const p2 = loadAllPartiesMeta();
    expect(p1).toBe(p2);

    const map = await p1;
    expect(map.size).toBe(1);
    expect(map.get("parties.IN.BJP")?.short).toBe("BJP");

    // Cache hit: query fired exactly once even across two awaits.
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("populates the Map with every non-empty party_id", async () => {
    mockedQuery.mockResolvedValue([
      {
        party_id: "parties.IN.INC",
        short: "INC",
        full: "Indian National Congress",
        founded_year: 1885,
        dissolved_year: null,
        recognition_scope: "national",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: null,
        wikipedia: null,
        name_native_script: null,
        is_sentinel: false,
      },
      {
        party_id: "parties.IN.IND",
        short: "IND",
        full: "Independent",
        founded_year: null,
        dissolved_year: null,
        recognition_scope: "sentinel",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: null,
        wikipedia: null,
        name_native_script: null,
        is_sentinel: true,
      },
      {
        party_id: "parties.IN.UNK",
        short: "UNK",
        full: "Unknown party (resolver fallback)",
        founded_year: null,
        dissolved_year: null,
        recognition_scope: "sentinel",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: null,
        wikipedia: null,
        name_native_script: null,
        is_sentinel: true,
      },
      // Defensive: row with empty party_id is silently skipped.
      {
        party_id: "",
        short: "drop me",
        full: null,
        founded_year: null,
        dissolved_year: null,
        recognition_scope: null,
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: null,
        wikipedia: null,
        name_native_script: null,
        is_sentinel: null,
      },
    ]);

    const map = await loadAllPartiesMeta();
    expect(map.size).toBe(3);
    expect(map.get("parties.IN.INC")?.short).toBe("INC");
    expect(map.get("parties.IN.IND")?.is_sentinel).toBe(true);
    expect(map.get("parties.IN.NOTA")).toBeUndefined();
    expect(map.get("parties.IN.UNK")?.is_sentinel).toBe(true);
  });

  it("registers parties.csv exactly once via registerCsvFile", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadAllPartiesMeta();
    await loadAllPartiesMeta();
    expect(mockedRegisterCsvFile).toHaveBeenCalledTimes(1);
    // The argument must point at the canonical parties.csv URL.
    expect(mockedRegisterCsvFile.mock.calls[0]![0]).toContain(
      "data/entities/parties.csv",
    );
  });

  it("clears the cache on fetch error so a retry re-issues the fetch", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("network gone"));
    await expect(loadAllPartiesMeta()).rejects.toThrow("network gone");
    // Retry path: a second call must trigger a fresh query call.
    mockedQuery.mockResolvedValueOnce([
      {
        party_id: "parties.IN.BJP",
        short: "BJP",
        full: "Bharatiya Janata Party",
        founded_year: 1980,
        dissolved_year: null,
        recognition_scope: "national",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: null,
        wikipedia: null,
        name_native_script: null,
        is_sentinel: false,
      },
    ]);
    const map = await loadAllPartiesMeta();
    expect(map.size).toBe(1);
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });
});

// --- per-key accessor -----------------------------------------------------

describe("loadPartyMeta", () => {
  beforeEach(() => {
    mockedQuery.mockResolvedValue([
      {
        party_id: "parties.IN.BJP",
        short: "BJP",
        full: "Bharatiya Janata Party",
        founded_year: 1980,
        dissolved_year: null,
        recognition_scope: "national",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: "#ea580c",
        wikipedia: "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party",
        name_native_script: null,
        is_sentinel: false,
      },
      {
        party_id: "parties.IN.NOTA",
        short: "NOTA",
        full: "None of the Above",
        founded_year: 2013,
        dissolved_year: null,
        recognition_scope: "sentinel",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: null,
        wikipedia: null,
        name_native_script: null,
        is_sentinel: true,
      },
    ]);
  });

  it("returns the meta for a known party_id", async () => {
    const meta = await loadPartyMeta("parties.IN.BJP");
    expect(meta?.short).toBe("BJP");
    expect(meta?.founded_year).toBe(1980);
    expect(meta?.wikipedia).toContain("Bharatiya_Janata_Party");
  });

  it("returns null for an unknown party_id (no fabrication)", async () => {
    const meta = await loadPartyMeta("parties.IN.NEVER_HEARD_OF_IT");
    expect(meta).toBeNull();
  });

  it("returns null for null / undefined / empty input without hitting DuckDB", async () => {
    await loadPartyMeta(null);
    await loadPartyMeta(undefined);
    await loadPartyMeta("");
    expect(mockedQuery).not.toHaveBeenCalled();
  });

  it("sentinel rows (NOTA) load with is_sentinel=true", async () => {
    const meta = await loadPartyMeta("parties.IN.NOTA");
    expect(meta?.is_sentinel).toBe(true);
    expect(meta?.recognition_scope).toBe("sentinel");
    expect(meta?.wikipedia).toBeNull();
  });
});

// --- PR-3: parties index summary ------------------------------------------

describe("toPartySummary", () => {
  it("derives the URL slug from party_id and surfaces it on the row", () => {
    const summary = toPartySummary({
      party_id: "parties.IN.INC",
      short: "INC",
      full: "Indian National Congress",
      recognition_scope: "national",
      home_state_codes: null,
      founded_year: 1885,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: false,
    });
    expect(summary).not.toBeNull();
    expect(summary!.slug).toBe("inc");
    expect(summary!.party_id).toBe("parties.IN.INC");
  });

  it("returns null for the UNK row (partyIdToSlug yields null)", () => {
    // UNK is the resolver fallback; it has no /parties/<unk> page.
    const summary = toPartySummary({
      party_id: "parties.IN.UNK",
      short: "UNK",
      full: "Unknown",
      recognition_scope: "sentinel",
      home_state_codes: null,
      founded_year: null,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: true,
    });
    expect(summary).toBeNull();
  });

  it("collapses null recognition_scope / full / aliases / home_state_codes to ''", () => {
    const summary = toPartySummary({
      party_id: "parties.IN.AAAP",
      short: "AAAP",
      full: null,
      recognition_scope: null,
      home_state_codes: null,
      founded_year: null,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: null,
    });
    expect(summary!.full).toBe("");
    expect(summary!.recognition_scope).toBe("");
    expect(summary!.home_state_codes).toBe("");
    expect(summary!.aliases).toBe("");
    expect(summary!.is_sentinel).toBe(false);
  });

  it("preserves the raw pipe-delimited aliases string (no split at the loader)", () => {
    const summary = toPartySummary({
      party_id: "parties.IN.AAAP",
      short: "AAAP",
      full: "Aapki Apni Adhikar Party",
      recognition_scope: null,
      home_state_codes: "IN-BR|IN-HR",
      founded_year: null,
      symbol_asset: null,
      brand_colour: null,
      aliases: "AAAAP|AAAP",
      is_sentinel: null,
    });
    expect(summary!.aliases).toBe("AAAAP|AAAP");
    expect(summary!.home_state_codes).toBe("IN-BR|IN-HR");
  });

  it("falls back to party_id when short is blank (defensive)", () => {
    const summary = toPartySummary({
      party_id: "parties.IN.FALLBACK",
      short: "",
      full: null,
      recognition_scope: null,
      home_state_codes: null,
      founded_year: null,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: null,
    });
    expect(summary!.short).toBe("parties.IN.FALLBACK");
  });

  it("coerces bigint founded_year (DuckDB BIGINT round-trip) to number", () => {
    const summary = toPartySummary({
      party_id: "parties.IN.AAP",
      short: "AAP",
      full: "Aam Aadmi Party",
      recognition_scope: "national",
      home_state_codes: null,
      founded_year: 2012n as unknown as bigint,
      symbol_asset: "party-symbols/broom.png",
      brand_colour: "#0072B0",
      aliases: null,
      is_sentinel: false,
    });
    expect(summary!.founded_year).toBe(2012);
    expect(typeof summary!.founded_year).toBe("number");
  });
});

describe("loadAllParties", () => {
  /** Common fixture - 5 rows ordered by lower(short) as DuckDB would.
   *  Includes IND + NOTA sentinels + the UNK row that the loader MUST
   *  filter out (partyIdToSlug(UNK) === null). */
  const sortedRowsWithUnk = [
    {
      party_id: "parties.IN.AAP",
      short: "AAP",
      full: "Aam Aadmi Party",
      recognition_scope: "national",
      home_state_codes: null,
      founded_year: 2012,
      symbol_asset: null,
      brand_colour: "#0072B0",
      aliases: null,
      is_sentinel: false,
    },
    {
      party_id: "parties.IN.BJP",
      short: "BJP",
      full: "Bharatiya Janata Party",
      recognition_scope: "national",
      home_state_codes: null,
      founded_year: 1980,
      symbol_asset: null,
      brand_colour: "#ea580c",
      aliases: null,
      is_sentinel: false,
    },
    {
      party_id: "parties.IN.DMK",
      short: "DMK",
      full: "Dravida Munnetra Kazhagam",
      recognition_scope: "state",
      home_state_codes: "IN-TN",
      founded_year: 1949,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: false,
    },
    {
      party_id: "parties.IN.IND",
      short: "IND",
      full: "Independent",
      recognition_scope: "sentinel",
      home_state_codes: null,
      founded_year: null,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: true,
    },
    {
      party_id: "parties.IN.NOTA",
      short: "NOTA",
      full: "None of the Above",
      recognition_scope: "sentinel",
      home_state_codes: null,
      founded_year: null,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: true,
    },
    {
      party_id: "parties.IN.UNK",
      short: "UNK",
      full: "Unknown party",
      recognition_scope: "sentinel",
      home_state_codes: null,
      founded_year: null,
      symbol_asset: null,
      brand_colour: null,
      aliases: null,
      is_sentinel: true,
    },
  ];

  it("(a) returns rows in lower(short) ascending order (SQL-sorted)", async () => {
    mockedQuery.mockResolvedValue(sortedRowsWithUnk);
    const out = await loadAllParties();
    const shorts = out.map((r) => r.short);
    // Must be sorted ascending; UNK is dropped so the tail is NOTA.
    expect(shorts).toEqual(["AAP", "BJP", "DMK", "IND", "NOTA"]);
  });

  it("(b) excludes the UNK sentinel (slug is null at projection)", async () => {
    mockedQuery.mockResolvedValue(sortedRowsWithUnk);
    const out = await loadAllParties();
    expect(out.find((r) => r.party_id === "parties.IN.UNK")).toBeUndefined();
    // The other 5 rows survive.
    expect(out).toHaveLength(5);
  });

  it("(c) includes IND + NOTA sentinels carrying is_sentinel=true", async () => {
    mockedQuery.mockResolvedValue(sortedRowsWithUnk);
    const out = await loadAllParties();
    const ind = out.find((r) => r.party_id === "parties.IN.IND");
    const nota = out.find((r) => r.party_id === "parties.IN.NOTA");
    expect(ind?.is_sentinel).toBe(true);
    expect(ind?.slug).toBe("independent"); // sentinel override
    expect(nota?.is_sentinel).toBe(true);
    expect(nota?.slug).toBe("nota");
  });

  it("(d) returns the SAME Promise on repeated calls (module-level cache hit)", async () => {
    mockedQuery.mockResolvedValue([]);
    const p1 = loadAllParties();
    const p2 = loadAllParties();
    expect(p1).toBe(p2);
    await p1;
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("(e) preserves pipe-delimited aliases verbatim from CSV (no split at loader)", async () => {
    mockedQuery.mockResolvedValue([
      {
        party_id: "parties.IN.AAAP",
        short: "AAAP",
        full: "Aapki Apni Adhikar Party",
        recognition_scope: null,
        home_state_codes: "IN-BR|IN-HR",
        founded_year: null,
        symbol_asset: null,
        brand_colour: null,
        // DuckDB returns a CSV cell containing a pipe-delimited list as
        // a plain string - the loader keeps that shape so the index page
        // does substring matching against it without re-joining.
        aliases: "AAAAP|AAAP",
        is_sentinel: null,
      },
    ]);
    const out = await loadAllParties();
    expect(out).toHaveLength(1);
    expect(out[0]!.aliases).toBe("AAAAP|AAAP");
    expect(out[0]!.home_state_codes).toBe("IN-BR|IN-HR");
  });

  it("issues the read_csv query against parties.csv (URL contract)", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadAllParties();
    expect(mockedRegisterCsvFile).toHaveBeenCalledTimes(1);
    expect(mockedRegisterCsvFile.mock.calls[0]![0]).toContain(
      "data/entities/parties.csv",
    );
    const sql = mockedQuery.mock.calls[0]![0] as string;
    expect(sql).toContain("read_csv");
    expect(sql).toContain("data/entities/parties.csv");
    // Sort happens server-side so the consumer doesn't pay JS sort cost.
    expect(sql).toMatch(/ORDER\s+BY\s+lower\("short"\)/i);
    // Aliases column is projected (the index search depends on it).
    expect(sql).toContain("aliases");
  });

  it("clears the summary cache on fetch error so a retry re-issues the fetch", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("network gone"));
    await expect(loadAllParties()).rejects.toThrow("network gone");
    mockedQuery.mockResolvedValueOnce([
      {
        party_id: "parties.IN.BJP",
        short: "BJP",
        full: "Bharatiya Janata Party",
        recognition_scope: "national",
        home_state_codes: null,
        founded_year: 1980,
        symbol_asset: null,
        brand_colour: null,
        aliases: null,
        is_sentinel: false,
      },
    ]);
    const out = await loadAllParties();
    expect(out).toHaveLength(1);
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });
});

// --- PR-11: parties_leadership.csv loader --------------------------------
//
// The leadership loader is a parallel `read_csv` against
// datasets/data/entities/parties_leadership.csv; `loadPartyMeta` calls
// `loadCurrentLeaders` in `Promise.all` so the tooltip + per-party
// header pay one cold-load round-trip rather than two. The bulk-Map
// returned by `loadAllPartiesMeta` keeps `leader: null` so the
// /parties index page does NOT trigger the leader fetch.

const BJP_BJD_INC_LEADERSHIP_ROWS = [
  // BJP: historic row first, current row second (multi-term party).
  {
    party_id: "parties.IN.BJP",
    role: "President",
    person_name: "Amit Shah",
    person_wikidata_qid: "Q4746875",
    valid_from: "2014-01-01",
    valid_to: "2020-01-01",
    source_id: "src-631faac30c7d",
  },
  {
    party_id: "parties.IN.BJP",
    role: "President",
    person_name: "Jagat Prakash Nadda",
    person_wikidata_qid: "Q16193764",
    valid_from: "2020-01-20",
    valid_to: null,
    source_id: "src-631faac30c7d",
  },
  // BJD: single current row.
  {
    party_id: "parties.IN.BJD",
    role: "President",
    person_name: "Naveen Patnaik",
    person_wikidata_qid: "Q1190856",
    valid_from: "1997-12-26",
    valid_to: null,
    source_id: "src-631faac30c7d",
  },
  // INC: historic + current rows (the brief's load-bearing case).
  {
    party_id: "parties.IN.INC",
    role: "President",
    person_name: "Sonia Gandhi",
    person_wikidata_qid: "Q163225",
    valid_from: "2019-08-10",
    valid_to: "2022-10-26",
    source_id: "src-631faac30c7d",
  },
  {
    party_id: "parties.IN.INC",
    role: "President",
    person_name: "Mallikarjun Kharge",
    person_wikidata_qid: "Q6744197",
    valid_from: "2022-10-26",
    valid_to: "",
    source_id: "src-631faac30c7d",
  },
];

describe("toCurrentLeader", () => {
  it("returns null for HISTORIC rows (valid_to populated)", () => {
    const leader = toCurrentLeader({
      party_id: "parties.IN.BJP",
      role: "President",
      person_name: "Amit Shah",
      person_wikidata_qid: "Q4746875",
      valid_from: "2014-01-01",
      valid_to: "2020-01-01",
      source_id: "src-631faac30c7d",
    });
    expect(leader).toBeNull();
  });

  it("surfaces CURRENT rows (valid_to null) with all fields populated", () => {
    const leader = toCurrentLeader({
      party_id: "parties.IN.BJP",
      role: "President",
      person_name: "Jagat Prakash Nadda",
      person_wikidata_qid: "Q16193764",
      valid_from: "2020-01-20",
      valid_to: null,
      source_id: "src-631faac30c7d",
    });
    expect(leader).not.toBeNull();
    expect(leader!.name).toBe("Jagat Prakash Nadda");
    expect(leader!.role).toBe("President");
    expect(leader!.since).toBe("2020-01-20");
    expect(leader!.person_wikidata_qid).toBe("Q16193764");
  });

  it("treats empty-string valid_to as current (writer may emit '' instead of NULL)", () => {
    const leader = toCurrentLeader({
      party_id: "parties.IN.INC",
      role: "President",
      person_name: "Mallikarjun Kharge",
      person_wikidata_qid: "Q6744197",
      valid_from: "2022-10-26",
      valid_to: "",
      source_id: "src-631faac30c7d",
    });
    expect(leader).not.toBeNull();
    expect(leader!.name).toBe("Mallikarjun Kharge");
  });

  it("returns null when person_name is blank (defensive vs CSV gap)", () => {
    const leader = toCurrentLeader({
      party_id: "parties.IN.BJP",
      role: "President",
      person_name: "",
      person_wikidata_qid: null,
      valid_from: "2020-01-20",
      valid_to: null,
      source_id: null,
    });
    expect(leader).toBeNull();
  });

  it("returns null when role is blank", () => {
    const leader = toCurrentLeader({
      party_id: "parties.IN.BJP",
      role: "",
      person_name: "Jagat Prakash Nadda",
      person_wikidata_qid: null,
      valid_from: "2020-01-20",
      valid_to: null,
      source_id: null,
    });
    expect(leader).toBeNull();
  });

  it("returns null when valid_from is blank (PK violation upstream)", () => {
    const leader = toCurrentLeader({
      party_id: "parties.IN.BJP",
      role: "President",
      person_name: "Jagat Prakash Nadda",
      person_wikidata_qid: null,
      valid_from: "",
      valid_to: null,
      source_id: null,
    });
    expect(leader).toBeNull();
  });

  it("allows person_wikidata_qid to be null (hand-curated rows)", () => {
    const leader = toCurrentLeader({
      party_id: "parties.IN.CUSTOM",
      role: "Convenor",
      person_name: "Hand-curated Person",
      person_wikidata_qid: null,
      valid_from: "2025-01-01",
      valid_to: null,
      source_id: null,
    });
    expect(leader).not.toBeNull();
    expect(leader!.person_wikidata_qid).toBeNull();
  });
});

describe("loadCurrentLeaders", () => {
  it("returns CURRENT leaders only - historic rows are dropped", async () => {
    mockedQuery.mockResolvedValue(BJP_BJD_INC_LEADERSHIP_ROWS);
    const map = await loadCurrentLeaders();
    // BJP: Nadda only (Amit Shah is historic).
    expect(map.get("parties.IN.BJP")?.name).toBe("Jagat Prakash Nadda");
    // BJD: Naveen Patnaik.
    expect(map.get("parties.IN.BJD")?.name).toBe("Naveen Patnaik");
    // INC: Kharge only (Sonia is historic; matches brief's oracle 3).
    expect(map.get("parties.IN.INC")?.name).toBe("Mallikarjun Kharge");
    expect(map.size).toBe(3);
  });

  it("returns the SAME Promise on repeated calls (module-level cache hit)", async () => {
    mockedQuery.mockResolvedValue([]);
    const p1 = loadCurrentLeaders();
    const p2 = loadCurrentLeaders();
    expect(p1).toBe(p2);
    await p1;
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("registers parties_leadership.csv via registerCsvFile (URL contract)", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadCurrentLeaders();
    const calls = mockedRegisterCsvFile.mock.calls.map((c) => c[0]);
    expect(calls.some((u) => u.includes("parties_leadership.csv"))).toBe(true);
  });

  it("emits a SQL WHERE clause that filters to current rows (defence in depth)", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadCurrentLeaders();
    const sql = mockedQuery.mock.calls[0]![0] as string;
    expect(sql).toContain("parties_leadership.csv");
    expect(sql).toMatch(/WHERE\s+valid_to\s+IS\s+NULL/i);
  });

  it("clears the cache on fetch error so a retry re-issues the fetch", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("network gone"));
    await expect(loadCurrentLeaders()).rejects.toThrow("network gone");
    mockedQuery.mockResolvedValueOnce([
      {
        party_id: "parties.IN.BJD",
        role: "President",
        person_name: "Naveen Patnaik",
        person_wikidata_qid: "Q1190856",
        valid_from: "1997-12-26",
        valid_to: null,
        source_id: "src-631faac30c7d",
      },
    ]);
    const map = await loadCurrentLeaders();
    expect(map.size).toBe(1);
    expect(map.get("parties.IN.BJD")?.name).toBe("Naveen Patnaik");
  });
});

describe("loadPartyLeader", () => {
  beforeEach(() => {
    mockedQuery.mockResolvedValue(BJP_BJD_INC_LEADERSHIP_ROWS);
  });

  it("returns the current leader for a party with a current row", async () => {
    const leader = await loadPartyLeader("parties.IN.INC");
    expect(leader?.name).toBe("Mallikarjun Kharge");
    expect(leader?.role).toBe("President");
    expect(leader?.since).toBe("2022-10-26");
  });

  it("returns null for a party with NO leadership row (the common case today)", async () => {
    const leader = await loadPartyLeader("parties.IN.AAP");
    expect(leader).toBeNull();
  });

  it("returns null for null / undefined / empty input without hitting DuckDB", async () => {
    await loadPartyLeader(null);
    await loadPartyLeader(undefined);
    await loadPartyLeader("");
    expect(mockedQuery).not.toHaveBeenCalled();
  });
});

describe("loadPartyMeta - PR-11 leader composition", () => {
  /** Two-shot mock: parties.csv rows for the FIRST call, leadership
   *  rows for the SECOND. Promise.all dispatches in argument order so
   *  `loadAllPartiesMeta` (parties) wins call slot 0, `loadCurrentLeaders`
   *  (leadership) wins slot 1. */
  function setupTwoShot(): void {
    mockedQuery
      .mockResolvedValueOnce([
        {
          party_id: "parties.IN.BJP",
          short: "BJP",
          full: "Bharatiya Janata Party",
          founded_year: 1980,
          dissolved_year: null,
          recognition_scope: "national",
          home_state_codes: null,
          symbol_asset: null,
          brand_colour: "#ea580c",
          wikipedia: null,
          name_native_script: null,
          is_sentinel: false,
        },
        {
          party_id: "parties.IN.INC",
          short: "INC",
          full: "Indian National Congress",
          founded_year: 1885,
          dissolved_year: null,
          recognition_scope: "national",
          home_state_codes: null,
          symbol_asset: null,
          brand_colour: null,
          wikipedia: null,
          name_native_script: null,
          is_sentinel: false,
        },
        {
          party_id: "parties.IN.IND",
          short: "IND",
          full: "Independent",
          founded_year: null,
          dissolved_year: null,
          recognition_scope: "sentinel",
          home_state_codes: null,
          symbol_asset: null,
          brand_colour: null,
          wikipedia: null,
          name_native_script: null,
          is_sentinel: true,
        },
        {
          party_id: "parties.IN.AAP",
          short: "AAP",
          full: "Aam Aadmi Party",
          founded_year: 2012,
          dissolved_year: null,
          recognition_scope: "national",
          home_state_codes: null,
          symbol_asset: null,
          brand_colour: null,
          wikipedia: null,
          name_native_script: null,
          is_sentinel: false,
        },
      ])
      .mockResolvedValueOnce(BJP_BJD_INC_LEADERSHIP_ROWS);
  }

  it("merges the current leader onto the returned meta (BJP -> Nadda)", async () => {
    setupTwoShot();
    const meta = await loadPartyMeta("parties.IN.BJP");
    expect(meta).not.toBeNull();
    expect(meta!.short).toBe("BJP");
    expect(meta!.leader).not.toBeNull();
    expect(meta!.leader!.name).toBe("Jagat Prakash Nadda");
    expect(meta!.leader!.role).toBe("President");
    expect(meta!.leader!.since).toBe("2020-01-20");
  });

  it("surfaces ONLY the current leader for multi-term parties (INC -> Kharge, not Sonia)", async () => {
    setupTwoShot();
    const meta = await loadPartyMeta("parties.IN.INC");
    expect(meta).not.toBeNull();
    expect(meta!.leader).not.toBeNull();
    expect(meta!.leader!.name).toBe("Mallikarjun Kharge");
    // Historic Sonia row must NOT be surfaced.
    expect(meta!.leader!.name).not.toBe("Sonia Gandhi");
  });

  it("returns leader=null for a party with no leadership row (AAP - the common case)", async () => {
    setupTwoShot();
    const meta = await loadPartyMeta("parties.IN.AAP");
    expect(meta).not.toBeNull();
    expect(meta!.leader).toBeNull();
  });

  it("returns leader=null for sentinels with no leadership row (IND)", async () => {
    setupTwoShot();
    const meta = await loadPartyMeta("parties.IN.IND");
    expect(meta).not.toBeNull();
    expect(meta!.is_sentinel).toBe(true);
    expect(meta!.leader).toBeNull();
  });

  it("the bulk-Map `loadAllPartiesMeta` keeps leader=null (no per-row leader cost)", async () => {
    // Only the parties.csv fetch happens via loadAllPartiesMeta;
    // leadership stays uncalled. mockResolvedValue (not Once) so we
    // do not care which mocked rows surface.
    mockedQuery.mockResolvedValue([
      {
        party_id: "parties.IN.BJP",
        short: "BJP",
        full: "Bharatiya Janata Party",
        founded_year: 1980,
        dissolved_year: null,
        recognition_scope: "national",
        home_state_codes: null,
        symbol_asset: null,
        brand_colour: null,
        wikipedia: null,
        name_native_script: null,
        is_sentinel: false,
      },
    ]);
    const map = await loadAllPartiesMeta();
    // Bulk-Map placeholder: leader=null on every entry regardless of
    // what parties_leadership.csv contains.
    expect(map.get("parties.IN.BJP")?.leader).toBeNull();
  });
});

describe("formatLeaderSince", () => {
  it("renders a well-formed YYYY-MM-DD as '<D> <Mon> <YYYY>'", () => {
    expect(formatLeaderSince("2022-10-26")).toBe("26 Oct 2022");
    expect(formatLeaderSince("2020-01-20")).toBe("20 Jan 2020");
    expect(formatLeaderSince("1997-12-26")).toBe("26 Dec 1997");
  });

  it("renders single-digit day without leading zero in citizen form", () => {
    expect(formatLeaderSince("2018-01-01")).toBe("1 Jan 2018");
    expect(formatLeaderSince("2025-04-06")).toBe("6 Apr 2025");
  });

  it("falls back to the raw input string on malformed input (citizen-honest)", () => {
    expect(formatLeaderSince("2022")).toBe("2022");
    expect(formatLeaderSince("not-a-date")).toBe("not-a-date");
    expect(formatLeaderSince("")).toBe("");
    // Out-of-range month / day: surface the raw string rather than
    // fabricate "month 13" or "day 32".
    expect(formatLeaderSince("2022-13-01")).toBe("2022-13-01");
    expect(formatLeaderSince("2022-01-32")).toBe("2022-01-32");
    expect(formatLeaderSince("2022-00-15")).toBe("2022-00-15");
  });
});



