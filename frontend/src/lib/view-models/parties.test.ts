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
  csvColumnsClause: vi.fn(
    async () =>
      "columns={'party_id': 'VARCHAR', 'short': 'VARCHAR', 'full': 'VARCHAR', 'founded_year': 'BIGINT', 'dissolved_year': 'BIGINT', 'recognition_scope': 'VARCHAR', 'home_state_codes': 'VARCHAR', 'symbol_asset': 'VARCHAR', 'brand_colour': 'VARCHAR', 'wikipedia': 'VARCHAR', 'name_native_script': 'VARCHAR', 'is_sentinel': 'BOOLEAN'}",
  ),
}));

import { query, registerCsvFile } from "../duckdb";
import {
  __resetForTests,
  loadAllParties,
  loadAllPartiesMeta,
  loadPartyMeta,
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



