// PR-9 of TODO/20260614-party-page-reimagination-plan.md - section 11.
//
// Unit tests for the `buildPartyProvenance` PURE projector.
// The async `loadSourceLookup` accessor is exercised by the
// contract test in `frontend/src/contracts/party-page-provenance.test.ts`.

import { describe, expect, it } from "vitest";

import {
  buildPartyProvenance,
  compressProducers,
  mergeLabelDuplicates,
  splitSourceIds,
  type PartyPageSource,
} from "./party-sources";
import type {
  PartyDetailViewModel,
  PartyHistoryPoint,
  PartyStronghold,
} from "./party-detail";
import type { PartyMeta } from "./parties";

function metaFixture(overrides: Partial<PartyMeta> = {}): PartyMeta {
  return {
    party_id: "parties.IN.BJP",
    short: "BJP",
    full: "Bharatiya Janata Party",
    founded_year: 1980,
    dissolved_year: null,
    recognition_scope: "national",
    home_state_codes: [],
    symbol_asset: null,
    brand_colour: "#FF9933",
    wikipedia: null,
    name_native_script: null,
    aliases: [],
    predecessor_party_ids: [],
    successor_party_ids: [],
    is_sentinel: false,
    leader: null,
    ...overrides,
  };
}

function historyPoint(
  year: number,
  label: string,
  seats: number,
  source_ids: string[],
): PartyHistoryPoint {
  return {
    year,
    period_label: label,
    seats,
    vote_share_pct: null,
    contested: null,
    source_ids,
  };
}

function stronghold(
  entity_id: string,
  source_ids: string[],
): PartyStronghold {
  return {
    entity_id,
    constituency_name: "Some PC",
    state: "tamil-nadu",
    wins: 3,
    contested: 4,
    // PR-7: `last_won_year` widening - fixture pins null since
    // this test covers the source-provenance envelope (recency is
    // not in scope).
    last_won_year: null,
    results: ["W", "W", "L", "W"],
    source_ids,
    // PR-8b D8a: `pc_slug` + `href` widening - fixture pins null
    // since this test covers source-provenance (clickability is
    // not in scope).
    pc_slug: null,
    href: null,
  };
}

function vmFixture(
  overrides: Partial<PartyDetailViewModel> = {},
): PartyDetailViewModel {
  return {
    metadata: metaFixture(),
    ls_history: [],
    vs_history: [],
    ls_strongholds: [],
    vs_strongholds: [],
    totals: {
      ls_seats: 0,
      vs_seats: 0,
      elections_contested: 0,
      first_year: 0,
      last_year: 0,
      peak_ls_seats: 0,
      peak_ls_year: 0,
      peak_vs_seats: 0,
      peak_vs_year: 0,
    },
    ls_methodology_breaks: [],
    current_strength: null,
    alliance_context: null,
    alliance_source_ids: [],
    current_strength_source_ids: [],
    provenance: {
      pills_per_card: {
        parliament: [],
        state_assembly: [],
        strongholds: [],
        current_strength: [],
        alliance_context: [],
      },
    },
    ...overrides,
  };
}

function srcRow(
  source_id: string,
  producer: string,
  title: string,
  vintage: string,
  url = "",
): PartyPageSource {
  return { source_id, producer, title, vintage, url };
}

// --- splitSourceIds -------------------------------------------------------

describe("splitSourceIds", () => {
  it("returns [] for null / undefined / empty", () => {
    expect(splitSourceIds(null)).toEqual([]);
    expect(splitSourceIds(undefined)).toEqual([]);
    expect(splitSourceIds("")).toEqual([]);
  });

  it("splits on pipe and dedupes preserving first-seen order", () => {
    expect(splitSourceIds("src-aaa|src-bbb|src-aaa|src-ccc")).toEqual([
      "src-aaa",
      "src-bbb",
      "src-ccc",
    ]);
  });

  it("trims whitespace and drops empty fragments", () => {
    expect(splitSourceIds("src-aaa| src-bbb || src-ccc ")).toEqual([
      "src-aaa",
      "src-bbb",
      "src-ccc",
    ]);
  });
});

// --- compressProducers ----------------------------------------------------

describe("compressProducers", () => {
  it("returns empty string for empty input", () => {
    expect(compressProducers([])).toBe("");
  });

  it("joins 1-3 producers verbatim, deduped", () => {
    expect(compressProducers(["ECI", "TCPD"])).toBe("ECI, TCPD");
    expect(compressProducers(["ECI", "ECI", "TCPD"])).toBe("ECI, TCPD");
  });

  it("caps at 3 then appends '+ N more' for 4+ distinct producers", () => {
    expect(
      compressProducers(["ECI", "TCPD", "RBI", "NITI", "MoSPI"]),
    ).toBe("ECI, TCPD, RBI + 2 more");
  });

  it("trims whitespace and drops empty entries before counting", () => {
    expect(compressProducers([" ECI ", "", " TCPD ", "RBI"])).toBe(
      "ECI, TCPD, RBI",
    );
  });
});

// --- mergeLabelDuplicates -------------------------------------------------

describe("mergeLabelDuplicates", () => {
  it("returns input unchanged when length <= 1", () => {
    expect(mergeLabelDuplicates([])).toEqual([]);
    const single = [
      { label: "RBI", vintage_summary: "2024", url: null, count: 1 },
    ];
    expect(mergeLabelDuplicates(single)).toEqual(single);
  });

  it("preserves pills that already have distinct labels", () => {
    const out = mergeLabelDuplicates([
      { label: "RBI State Finances", vintage_summary: "2025-26", url: null, count: 3 },
      { label: "ECI", vintage_summary: "2024", url: "https://eci.gov.in/x", count: 2 },
    ]);
    expect(out).toHaveLength(2);
    // Sorted: RBI (count 3) before ECI (count 2).
    expect(out.map((p) => p.label)).toEqual(["RBI State Finances", "ECI"]);
  });

  it("collapses two pills with same label + same vintage_summary into one with summed count", () => {
    const out = mergeLabelDuplicates([
      { label: "ECI", vintage_summary: "2024", url: null, count: 2 },
      { label: "ECI", vintage_summary: "2024", url: "https://eci.gov.in/x", count: 3 },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0]!.label).toBe("ECI");
    expect(out[0]!.vintage_summary).toBe("2024");
    expect(out[0]!.count).toBe(5);
    // First non-empty url wins.
    expect(out[0]!.url).toBe("https://eci.gov.in/x");
  });

  it("collapses same-label pills with different vintages via summarize rule", () => {
    // Two distinct vintage_summary strings -> "<a> to <b>".
    const out2 = mergeLabelDuplicates([
      { label: "ECI", vintage_summary: "2019", url: null, count: 1 },
      { label: "ECI", vintage_summary: "2024", url: null, count: 1 },
    ]);
    expect(out2).toHaveLength(1);
    expect(out2[0]!.vintage_summary).toBe("2019 to 2024");
    // Three+ distinct -> "various".
    const out3 = mergeLabelDuplicates([
      { label: "ECI", vintage_summary: "2019", url: null, count: 1 },
      { label: "ECI", vintage_summary: "2024", url: null, count: 1 },
      { label: "ECI", vintage_summary: "1984", url: null, count: 1 },
    ]);
    expect(out3).toHaveLength(1);
    expect(out3[0]!.vintage_summary).toBe("various");
  });

  it("collapses same-label pills whose vintage_summary strings are all empty", () => {
    const out = mergeLabelDuplicates([
      { label: "ECI", vintage_summary: "", url: null, count: 1 },
      { label: "ECI", vintage_summary: "", url: null, count: 1 },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0]!.vintage_summary).toBe("");
  });

  it("guarantees unique (label + vintage_summary) Svelte keys post-merge", () => {
    // Regression guard for the SourceList.svelte each-key collision
    // that originally caused this helper to exist. Input simulates a
    // page where many ECI titles all overflow the 30-char label budget
    // and dedupeToPills produces multiple "ECI" pills.
    const out = mergeLabelDuplicates([
      { label: "ECI", vintage_summary: "2024", url: null, count: 1 },
      { label: "ECI", vintage_summary: "2024", url: null, count: 1 },
      { label: "ECI", vintage_summary: "2019", url: null, count: 1 },
      { label: "TCPD", vintage_summary: "2024", url: null, count: 1 },
      { label: "TCPD", vintage_summary: "2024", url: null, count: 1 },
    ]);
    const keys = out.map((p) => `${p.label}::${p.vintage_summary}`);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("sorts merged output by count desc, then label asc", () => {
    const out = mergeLabelDuplicates([
      { label: "TCPD", vintage_summary: "2024", url: null, count: 1 },
      { label: "ECI", vintage_summary: "2024", url: null, count: 2 },
      { label: "ECI", vintage_summary: "2019", url: null, count: 3 },
    ]);
    // After merge: ECI (count 5), TCPD (count 1).
    expect(out.map((p) => p.label)).toEqual(["ECI", "TCPD"]);
    expect(out[0]!.count).toBe(5);
  });
});

// --- buildPartyProvenance (happy path) ------------------------------------

describe("buildPartyProvenance happy path", () => {
  it("emits non-empty pills_per_card entries when every card has data + sources", () => {
    const lookup = new Map<string, PartyPageSource>([
      ["src-eci-ls-2024", srcRow("src-eci-ls-2024", "Election Commission of India", "General Election to Lok Sabha 2024 - Statistical Report", "2024", "https://eci.gov.in/ls2024")],
      ["src-eci-ae-2021", srcRow("src-eci-ae-2021", "Election Commission of India", "State Assembly Election 2021 - Statistical Report", "2021", "https://eci.gov.in/ae2021")],
      ["src-tcpd-ae-2021", srcRow("src-tcpd-ae-2021", "TCPD", "AE Candidates 2021", "2021-06")],
      ["src-tcpd-ls-2024", srcRow("src-tcpd-ls-2024", "TCPD", "LS Candidates 2024", "2024-06")],
      ["src-aece-2025", srcRow("src-aece-2025", "Adam Carr Election Centre", "Alliance Tracker", "2025-01")],
    ]);
    const vm = vmFixture({
      ls_history: [
        historyPoint(1984, "LsGenDec1984", 2, ["src-eci-ls-2024", "src-tcpd-ls-2024"]),
        historyPoint(2024, "LsGenMay2024", 240, ["src-eci-ls-2024"]),
      ],
      vs_history: [
        historyPoint(2021, "AcGenApr2021", 77, ["src-eci-ae-2021", "src-tcpd-ae-2021"]),
      ],
      ls_strongholds: [stronghold("IN-PC-2008-S22-10", ["src-eci-ls-2024"])],
      vs_strongholds: [stronghold("IN-AC-2008-S22-167", ["src-tcpd-ae-2021"])],
      current_strength: {
        parliament_latest: {
          year: 2024,
          event_id: "general-2024",
          month_label: "May 2024",
          seats_won: 240,
          seats_total: 543,
          vote_share_pct: 36.5,
          rank_label: null,
        },
        state_assemblies_latest: {
          seats_won: 77,
          seats_total: 234,
          state_count: 1,
          latest_event_label: "Tamil Nadu State Assembly, Apr 2021",
          latest_event_sort_key: "2021-04",
        },
        last_contested_label: "Parliament, May 2024",
      },
      alliance_context: {
        parliament: {
          event_label: "Parliament 2024",
          event_id: "general-2024",
          alliance: "NDA",
          role: "led",
          partner_count: 0,
          partner_names_top: [],
          total_alliance_seats: 240,
        },
        state_assemblies: [],
      },
      alliance_source_ids: ["src-aece-2025"],
      current_strength_source_ids: ["src-eci-ls-2024", "src-eci-ae-2021"],
    });
    const out = buildPartyProvenance(vm, lookup);
    // Every card with data emits at least one pill; pill labels reflect
    // the publisher abbreviation (ECI, TCPD) plus the series_family
    // sliced from the title's leading clause.
    expect(out.pills_per_card.parliament.length).toBeGreaterThan(0);
    expect(out.pills_per_card.state_assembly.length).toBeGreaterThan(0);
    expect(out.pills_per_card.strongholds.length).toBeGreaterThan(0);
    expect(out.pills_per_card.current_strength.length).toBeGreaterThan(0);
    expect(out.pills_per_card.alliance_context.length).toBeGreaterThan(0);
    // Spot-check one pill: parliament should carry an ECI pill that
    // names both 2024 and 1984 cycle vintages.
    const parl_eci = out.pills_per_card.parliament.find((p) =>
      p.label.startsWith("ECI"),
    );
    expect(parl_eci).toBeDefined();
    expect(parl_eci!.vintage_summary).toBe("2024");
    // The alliance card cites the single Adam Carr Election Centre pill.
    expect(out.pills_per_card.alliance_context).toHaveLength(1);
    expect(out.pills_per_card.alliance_context[0]!.label).toBe(
      "Adam Carr Election Centre",
    );
    expect(out.pills_per_card.alliance_context[0]!.vintage_summary).toBe(
      "2025-01",
    );
  });

  it("emits an empty pills array per card for a sentinel party with zero data", () => {
    const lookup = new Map<string, PartyPageSource>();
    const out = buildPartyProvenance(
      vmFixture({
        metadata: metaFixture({
          party_id: "parties.IN.NOTA",
          short: "NOTA",
          is_sentinel: true,
        }),
      }),
      lookup,
    );
    expect(out.pills_per_card.parliament).toEqual([]);
    expect(out.pills_per_card.state_assembly).toEqual([]);
    expect(out.pills_per_card.strongholds).toEqual([]);
    expect(out.pills_per_card.current_strength).toEqual([]);
    expect(out.pills_per_card.alliance_context).toEqual([]);
  });
});

// --- buildPartyProvenance (STOP-AND-SURFACE) ------------------------------

describe("buildPartyProvenance STOP-AND-SURFACE (Holy Law #9)", () => {
  it("throws when a card has data but resolves zero source_ids", () => {
    const lookup = new Map<string, PartyPageSource>();
    const vm = vmFixture({
      ls_history: [historyPoint(2024, "LsGenMay2024", 99, [])],
    });
    expect(() => buildPartyProvenance(vm, lookup)).toThrowError(
      /card "parliament".*has data but resolves zero source_ids.*Holy Law #9/,
    );
  });

  it("throws when a cited source_id is missing from source_lookup (FK violation)", () => {
    const lookup = new Map<string, PartyPageSource>();
    const vm = vmFixture({
      ls_history: [
        historyPoint(2024, "LsGenMay2024", 99, ["src-not-in-source-csv"]),
      ],
    });
    expect(() => buildPartyProvenance(vm, lookup)).toThrowError(
      /source_id "src-not-in-source-csv".*not present.*source\.csv/,
    );
  });

  it("includes the party_id in the FK-violation message", () => {
    const lookup = new Map<string, PartyPageSource>();
    const vm = vmFixture({
      metadata: metaFixture({ party_id: "parties.IN.DMK" }),
      ls_history: [historyPoint(2024, "LsGenMay2024", 22, ["src-missing"])],
    });
    expect(() => buildPartyProvenance(vm, lookup)).toThrowError(
      /\/parties\/parties\.IN\.DMK/,
    );
  });

  it("includes the party_id in the data-without-source message", () => {
    const lookup = new Map<string, PartyPageSource>();
    const vm = vmFixture({
      metadata: metaFixture({ party_id: "parties.IN.AAP" }),
      vs_history: [historyPoint(2020, "AcGenFeb2020", 62, [])],
    });
    expect(() => buildPartyProvenance(vm, lookup)).toThrowError(
      /\/parties\/parties\.IN\.AAP/,
    );
  });
});
