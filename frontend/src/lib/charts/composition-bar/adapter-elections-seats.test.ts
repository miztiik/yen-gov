// Vitest — Phase 3.6 (b) elections adapter (pure + loader).
//
// Per CLAUDE.md §15: the loader's contract IS the SQL boundary —
// mocking `query`/`registerSlice`/`registerTable` is the explicit carve-out from Holy
// Law #7. We don't boot DuckDB-WASM here; the round-trip is asserted
// in Playwright against a real Parquet shard in Phase 3.6 (c).

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../duckdb", () => ({
  registerSlice: vi.fn(async () => "noop"),
  registerTable: vi.fn(async () => "noop"),
  registerCsvAsTable: vi.fn(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  ),
  query: vi.fn(),
}));

import { query, registerCsvAsTable, registerSlice, registerTable } from "../../duckdb";
import {
  CAPTION_FPTP,
  DEFAULT_TOP_N,
  assembleCompositionBar,
  loadCompositionBarElectionSeats,
  projectSourcesV2,
  reduceToTopNWithTail,
  resolvePartyFill,
  sortPartiesBySeats,
  type CompositionBarLoadedRows,
  type CompositionBarPartyRow,
  type CompositionBarSourceJoinRow,
} from "./adapter-elections-seats";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);
const mockedRegisterSlice = vi.mocked(registerSlice);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegisterSlice.mockReset();
  mockedRegisterCsvAsTable.mockReset();
  mockedRegister.mockResolvedValue("noop");
  mockedRegisterSlice.mockResolvedValue("noop");
  mockedRegisterCsvAsTable.mockImplementation(async (id) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  );
});

function party(
  party_short: string,
  seats_won: number,
  eci_code: string | null = null,
  party_full: string | null = null,
): CompositionBarPartyRow {
  return {
    party_eci_code: eci_code ?? party_short,
    party_short,
    party_full: party_full ?? party_short,
    seats_won,
    party_id: `parties.IN.${party_short.toUpperCase()}`,
    brand_colour_hex: null,
    brand_colour_confidence: null,
  };
}

const GJ_2022_PARTIES: CompositionBarPartyRow[] = [
  party("BJP", 156, "BJP", "Bharatiya Janata Party"),
  party("INC", 17, "INC", "Indian National Congress"),
  party("AAP", 5, "AAP", "Aam Aadmi Party"),
  party("IND", 3, "IND", "Independent"),
  party("SP", 1, "SP", "Samajwadi Party"),
];

const GJ_2022_SOURCES: CompositionBarSourceJoinRow[] = [
  {
    source_id: "src-eci-form21-gj-2022",
    producer: "Election Commission of India",
    title: "Form 21 — Gujarat Legislative Assembly 2022",
    vintage: "2022-12-12",
    license: "ECI-Public",
    confidence_tier: "tier-1-issuing-authority",
    is_issuing_authority: true,
    verification_method: "matches-issuing-authority",
    url_main: "https://eci.gov.in/files/form21-gj-2022.pdf",
    citation_full: "ECI Form 21, Gujarat 2022.",
    notes: null,
  },
];

const GJ_2022_LOADED: CompositionBarLoadedRows = {
  parties: GJ_2022_PARTIES,
  sources: GJ_2022_SOURCES,
  total_seats: 182,
};

describe("sortPartiesBySeats", () => {
  it("sorts by seats desc", () => {
    const out = sortPartiesBySeats(GJ_2022_PARTIES);
    expect(out.map(p => p.party_short)).toEqual([
      "BJP",
      "INC",
      "AAP",
      "IND",
      "SP",
    ]);
  });

  it("breaks ties by party_short asc", () => {
    const out = sortPartiesBySeats([
      party("ZZZ", 5),
      party("AAA", 5),
      party("MMM", 5),
    ]);
    expect(out.map(p => p.party_short)).toEqual(["AAA", "MMM", "ZZZ"]);
  });

  it("does not mutate the input array", () => {
    const input = [...GJ_2022_PARTIES];
    const before = [...input];
    sortPartiesBySeats(input);
    expect(input).toEqual(before);
  });
});

describe("reduceToTopNWithTail — top-N edge cases (plan line 1338)", () => {
  it("returns [] for empty input", () => {
    expect(reduceToTopNWithTail([])).toEqual([]);
  });

  it("returns the single row when N=2 and only one party present", () => {
    const out = reduceToTopNWithTail([party("BJP", 99)], 2);
    expect(out.map(p => p.party_short)).toEqual(["BJP"]);
  });

  it("returns top 2 + Others when N=2 and more than 3 parties present", () => {
    const out = reduceToTopNWithTail(GJ_2022_PARTIES, 2);
    expect(out.map(p => p.party_short)).toEqual(["BJP", "INC", "OTHERS"]);
    expect(out.find(p => p.party_short === "OTHERS")?.seats_won).toBe(
      5 + 3 + 1,
    );
  });

  it("returns all rows when count <= N+1 (no single-item Others)", () => {
    // 5 rows, N=5 → returns 5 rows.
    const out = reduceToTopNWithTail(GJ_2022_PARTIES, 5);
    expect(out).toHaveLength(5);
    expect(out.every(p => p.party_short !== "OTHERS")).toBe(true);
  });

  it("returns all rows when count === N+1 (avoid degenerate Others)", () => {
    // 5 rows, N=4 → returns 5 rows (don't roll a single row into Others).
    const out = reduceToTopNWithTail(GJ_2022_PARTIES, 4);
    expect(out).toHaveLength(5);
    expect(out.every(p => p.party_short !== "OTHERS")).toBe(true);
  });

  it("returns top N + Others when count > N+1", () => {
    // Pad to 10 rows; N=5 → top 5 + Others.
    const padded = [
      ...GJ_2022_PARTIES,
      party("X1", 1),
      party("X2", 1),
      party("X3", 1),
      party("X4", 1),
      party("X5", 1),
    ];
    const out = reduceToTopNWithTail(padded, 5);
    expect(out).toHaveLength(6);
    expect(out[5].party_short).toBe("OTHERS");
    expect(out[5].seats_won).toBe(5); // 5 × 1
  });

  it("uses default top_n = 8 when not specified", () => {
    expect(DEFAULT_TOP_N).toBe(8);
    // 10 rows → top 8 + Others.
    const rows: CompositionBarPartyRow[] = [];
    for (let i = 0; i < 10; i++) rows.push(party(`P${i}`, 10 - i));
    const out = reduceToTopNWithTail(rows);
    expect(out).toHaveLength(9);
    expect(out[8].party_short).toBe("OTHERS");
  });

  it("handles the single-party degenerate case (99 of 182)", () => {
    // Plan line 1338: "single-party degenerate case (e.g. one party
    // holds 99 of 182, others split the rest)".
    const rows: CompositionBarPartyRow[] = [
      party("BJP", 99),
      party("INC", 70),
      party("AAP", 8),
      party("IND", 4),
      party("SP", 1),
    ];
    const out = reduceToTopNWithTail(rows, 8);
    // 5 rows, N=8 → all 5 (no tail).
    expect(out).toHaveLength(5);
    expect(out[0].party_short).toBe("BJP");
  });

  it("omits Others when the tail aggregate sums to zero", () => {
    // Tail rows all-zero → no Others row emitted.
    const rows: CompositionBarPartyRow[] = [
      party("BJP", 100),
      party("INC", 80),
      party("AAP", 2),
      party("X1", 0),
      party("X2", 0),
    ];
    const out = reduceToTopNWithTail(rows, 3);
    expect(out).toHaveLength(3);
    expect(out.every(p => p.party_short !== "OTHERS")).toBe(true);
  });
});

describe("resolvePartyFill", () => {
  it("returns OTHERS_FILL for the OTHERS tail row", () => {
    expect(
      resolvePartyFill(party("OTHERS", 5), ["BJP", "INC"]),
    ).toBe("#cbd5e1");
  });

  it("returns IND_FILL for IND", () => {
    expect(
      resolvePartyFill(party("IND", 3), ["BJP", "INC", "IND"]),
    ).toBe("#94a3b8");
  });

  it("returns IND_FILL for INDEPENDENT (alternate spelling)", () => {
    expect(
      resolvePartyFill(
        party("INDEPENDENT", 3),
        ["BJP", "INC", "INDEPENDENT"],
      ),
    ).toBe("#94a3b8");
  });

  it("returns the NOTA anchor swatch for NOTA", () => {
    // Plan line 1318: "render NOTA as its own swatch with the
    // existing NOTA colour anchor."
    expect(
      resolvePartyFill(party("NOTA", 0), ["BJP", "INC", "NOTA"]),
    ).toBe("#64748b"); // slate-500 from anchors.ts
  });

  it("delegates to partyColour for a regular party", () => {
    // The result is hex /^#[0-9a-f]{6}$/i — we don't pin the exact
    // colour because the OkLCh algorithm output is allowed to drift
    // when ANCHORS / palette config changes. We only pin that we get
    // SOME valid hex back.
    const fill = resolvePartyFill(party("XYZ", 1), ["XYZ"]);
    expect(fill).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

describe("assembleCompositionBar — happy path", () => {
  it("produces a CompositionBarModel from Gujarat-2022 rows", () => {
    const model = assembleCompositionBar(GJ_2022_LOADED, {
      state_label: "Gujarat",
      event_label: "2022",
    });
    expect(model.schema_version).toBe("1.0");
    expect(model.dimension).toBe("party");
    expect(model.total_value).toBe(182);
    expect(model.total_unit).toBe("seats");
    expect(model.label).toBe("Gujarat — 2022 Assembly");
    expect(model.subtitle).toBe("All 182 seats; FPTP winners only");
    expect(model.segments).toHaveLength(5);
  });

  it("sorts segments by seats desc (BJP first)", () => {
    const model = assembleCompositionBar(GJ_2022_LOADED, {
      state_label: "Gujarat",
      event_label: "2022",
    });
    expect(model.segments[0].id).toBe("BJP");
    expect(model.segments[0].value).toBe(156);
  });

  it("emits the FPTP caption verbatim (plan line 1320)", () => {
    const model = assembleCompositionBar(GJ_2022_LOADED, {
      state_label: "Gujarat",
      event_label: "2022",
    });
    expect(model.caption_fptp).toBe(CAPTION_FPTP);
    expect(CAPTION_FPTP).toContain("first-past-the-post");
    expect(CAPTION_FPTP).toContain("seat-share movements");
  });

  it("rolls a long tail into a visible Others segment", () => {
    const padded: CompositionBarLoadedRows = {
      ...GJ_2022_LOADED,
      parties: [
        ...GJ_2022_PARTIES,
        party("X1", 1),
        party("X2", 1),
        party("X3", 1),
        party("X4", 1),
        party("X5", 1),
      ],
      total_seats: 187,
    };
    const model = assembleCompositionBar(padded, {
      state_label: "Gujarat",
      event_label: "2022",
      top_n: 5,
    });
    const others = model.segments.find(s => s.is_tail);
    expect(others).toBeDefined();
    expect(others?.label).toBe("Others");
    expect(others?.swatch_role).toBe("others");
    expect(others?.value).toBe(5); // 5 × 1
  });

  it("emits NO tail segment when count <= N+1", () => {
    const model = assembleCompositionBar(GJ_2022_LOADED, {
      state_label: "Gujarat",
      event_label: "2022",
    });
    const tails = model.segments.filter(s => s.is_tail);
    expect(tails).toHaveLength(0);
  });

  it("renders NOTA as its own swatch when present (plan line 1318)", () => {
    const withNota: CompositionBarLoadedRows = {
      parties: [...GJ_2022_PARTIES, party("NOTA", 0, "NOTA", "None Of The Above")],
      sources: GJ_2022_SOURCES,
      total_seats: 182, // NOTA contributes 0 seats by definition
    };
    const model = assembleCompositionBar(withNota, {
      state_label: "Gujarat",
      event_label: "2022",
    });
    const nota = model.segments.find(s => s.id === "NOTA");
    expect(nota).toBeDefined();
    expect(nota?.swatch_role).toBe("nota");
    expect(nota?.fill).toBe("#64748b"); // slate-500 anchor
  });

  it("respects total_seats_override", () => {
    const model = assembleCompositionBar(
      { ...GJ_2022_LOADED, total_seats: 100 },
      {
        state_label: "Gujarat",
        event_label: "2022",
        total_seats_override: 182,
      },
    );
    expect(model.total_value).toBe(182);
    expect(model.subtitle).toBe("All 182 seats; FPTP winners only");
  });

  it("throws on zero party rows (loader must guard before calling)", () => {
    expect(() =>
      assembleCompositionBar(
        { parties: [], sources: [], total_seats: 0 },
        { state_label: "Gujarat", event_label: "2022" },
      ),
    ).toThrow();
  });

  it("propagates honesty_extra banners to the model", () => {
    const model = assembleCompositionBar(GJ_2022_LOADED, {
      state_label: "Gujarat",
      event_label: "2022",
      honesty_extra: [{ kind: "comparability", text: "Test banner." }],
    });
    expect(model.honesty_banners).toHaveLength(1);
    expect(model.honesty_banners[0].text).toBe("Test banner.");
  });
});

describe("projectSourcesV2", () => {
  it("projects DuckDB source rows to the v2.0 ledger shape", () => {
    const out = projectSourcesV2(GJ_2022_SOURCES);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({
      source_id: "src-eci-form21-gj-2022",
      producer: "Election Commission of India",
      is_issuing_authority: true,
      verification_method: "matches-issuing-authority",
    });
  });

  it("coerces is_issuing_authority to a boolean", () => {
    const row: CompositionBarSourceJoinRow = {
      ...GJ_2022_SOURCES[0],
      // DuckDB-WASM occasionally returns BOOLEAN as 0/1; coerce.
      is_issuing_authority: 0 as unknown as boolean,
    };
    const out = projectSourcesV2([row]);
    expect(out[0].is_issuing_authority).toBe(false);
  });
});

describe("loadCompositionBarElectionSeats — async loader (R-28 manifest registration)", () => {
  it("registers the state fact slice and supporting tables before querying", async () => {
    // Stub both queries with empty arrays - we only care about the
    // registerTable / registerCsvAsTable calls here.
    mockedQuery.mockResolvedValue([]);
    await loadCompositionBarElectionSeats("S05", "Dec 2022", {
      state_label: "Gujarat",
      event_label: "2022",
    });
    expect(mockedRegisterSlice).toHaveBeenCalledWith(
      "elections.election_results",
      { state: "goa" },
    );
    // dim_parties + taxonomy.sources flipped to CSV via X1a (PR #809).
    // E5 (plan section 25.6a) corrects the stale assertion that expected
    // `registerTable(...)` calls left behind by the X1a PR.
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls.map((c) => c[0]);
    expect(csvAsTableIds).toContain("elections.dim_parties");
    expect(csvAsTableIds).toContain("taxonomy.sources");
    // The legacy parquet `registerTable` path is no longer used here.
    const parquetTables = mockedRegister.mock.calls.map((c) => c[0]);
    expect(parquetTables).not.toContain("elections.dim_parties");
    expect(parquetTables).not.toContain("taxonomy.sources");
  });

  it("returns partial / not_published on zero party rows", async () => {
    mockedQuery.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    const res = await loadCompositionBarElectionSeats("S05", "Dec 2022", {
      state_label: "Gujarat",
      event_label: "2022",
    });
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
  });

  it("returns ok with model + sources_v2 on a happy round-trip", async () => {
    mockedQuery
      .mockResolvedValueOnce(
        GJ_2022_PARTIES.map(p => ({
          party_short: p.party_short,
          party_full: p.party_full,
          eci_code: p.party_eci_code,
          seats_won: p.seats_won,
          party_id: p.party_id,
          brand_colour_hex: p.brand_colour_hex,
          brand_colour_confidence: p.brand_colour_confidence,
        })),
      )
      .mockResolvedValueOnce(GJ_2022_SOURCES);

    const res = await loadCompositionBarElectionSeats("S05", "Dec 2022", {
      state_label: "Gujarat",
      event_label: "2022",
    });
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;
    expect(res.data.model.total_value).toBe(182);
    expect(res.data.model.segments[0].id).toBe("BJP");
    expect(res.data.sources_v2).toHaveLength(1);
    expect(res.data.sources_v2[0].source_id).toBe("src-eci-form21-gj-2022");
  });

  it("returns failed + retry on a thrown query error", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("boom"));
    const res = await loadCompositionBarElectionSeats("S05", "Dec 2022", {
      state_label: "Gujarat",
      event_label: "2022",
    });
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(typeof res.retry).toBe("function");
  });
});
