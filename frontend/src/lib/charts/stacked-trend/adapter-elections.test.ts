import { describe, it, expect } from "vitest";
import {
  electionsToStackedTrend,
  parseElectionEventId,
  type ResultSummaryDoc,
} from "./adapter-elections";

// ---------------------------------------------------------------------------
// Inline ``ResultSummaryDoc`` fixtures.
//
// Pre-PR-O.2-minimal (2026-05-18) these tests loaded
// ``datasets/elections/AcGen.../S03/result.summary.json`` via ``readFileSync``.
// Under the canonical pivot (TODO row 1.8b) the legacy per-state summary
// JSON shards are deprecated and will be retired in PR-O-ii; the adapter's
// contract is the in-memory ``ResultSummaryDoc`` shape (produced going
// forward by a canonical-Parquet -> adapter helper), so the test pins that
// shape directly with inline literals. Numbers for Assam Apr 2016 mirror
// the real ECI totals so the BJP=60 / INC=26 assertion stays semantically
// faithful; later events use simplified placeholder rows since the tests
// only assert ordering / shape for them.
// ---------------------------------------------------------------------------

const ASSAM_APR_2016: ResultSummaryDoc = {
  sources: [],
  election: "AcGenApr2016",
  state: "S03",
  body: "AC",
  total_seats: 126,
  totals: { electors: 19990755, votes_polled: 16919364, turnout_pct: 84.64 },
  party_totals: [
    { party_short: "BJP",   seats_contested:  89, seats_won: 60, votes: 4992185, vote_share_pct: 29.51 },
    { party_short: "INC",   seats_contested: 122, seats_won: 26, votes: 5238655, vote_share_pct: 30.96 },
    { party_short: "AGP",   seats_contested:  30, seats_won: 14, votes: 1377482, vote_share_pct:  8.14 },
    { party_short: "AIUDF", seats_contested:  74, seats_won: 13, votes: 2207945, vote_share_pct: 13.05 },
    { party_short: "BOPF",  seats_contested:  13, seats_won: 12, votes:  666057, vote_share_pct:  3.94 },
    { party_short: "IND",   seats_contested: 121, seats_won:  1, votes: 1867531, vote_share_pct: 11.04 },
  ],
};

const ASSAM_APR_2021: ResultSummaryDoc = {
  sources: [],
  election: "AcGenApr2021",
  state: "S03",
  body: "AC",
  total_seats: 126,
  party_totals: [
    { party_short: "BJP", seats_contested:  92, seats_won: 60, votes: 5000000, vote_share_pct: 33.0 },
    { party_short: "INC", seats_contested: 100, seats_won: 29, votes: 4500000, vote_share_pct: 29.0 },
    { party_short: "AGP", seats_contested:  26, seats_won:  9, votes: 1200000, vote_share_pct:  7.0 },
  ],
};

const ASSAM_MAY_2026: ResultSummaryDoc = {
  sources: [],
  election: "AcGenMay2026",
  state: "S03",
  body: "AC",
  total_seats: 126,
  party_totals: [
    { party_short: "BJP", seats_contested:  92, seats_won: 65, votes: 5200000, vote_share_pct: 34.0 },
    { party_short: "INC", seats_contested: 100, seats_won: 30, votes: 4600000, vote_share_pct: 29.5 },
  ],
};

const GOA_MAY_2026: ResultSummaryDoc = {
  sources: [],
  election: "AcGenMay2026",
  state: "S11",
  body: "AC",
  total_seats: 40,
  party_totals: [
    { party_short: "BJP", seats_contested: 40, seats_won: 20, votes: 200000, vote_share_pct: 35.0 },
  ],
};

describe("parseElectionEventId", () => {
  it("parses ECI AcGen event ids into sortable period_id + human label", () => {
    expect(parseElectionEventId("AcGenApr2021")).toEqual({
      period_id: "2021-04",
      period_label: "Apr 2021",
    });
    expect(parseElectionEventId("AcGenMay2026")).toEqual({
      period_id: "2026-05",
      period_label: "May 2026",
    });
  });

  it("falls back to the raw id when the pattern doesn't match", () => {
    expect(parseElectionEventId("WeirdId")).toEqual({
      period_id: "WeirdId",
      period_label: "WeirdId",
    });
  });
});

describe("electionsToStackedTrend — Assam (S03) seats_won timeline", () => {
  const summaries: ResultSummaryDoc[] = [
    ASSAM_APR_2016,
    ASSAM_APR_2021,
    ASSAM_MAY_2026,
  ];

  it("produces three bars in chronological order", () => {
    const model = electionsToStackedTrend(summaries, {
      value: "seats_won",
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
    });
    expect(model.bars.length).toBe(3);
    expect(model.bars.map(b => b.period_id)).toEqual([
      "2016-04",
      "2021-04",
      "2026-05",
    ]);
    expect(model.bars.map(b => b.period_label)).toEqual([
      "Apr 2016",
      "Apr 2021",
      "May 2026",
    ]);
  });

  it("dimension is 'party' so partyColour resolves the segments", () => {
    const model = electionsToStackedTrend(summaries, {
      value: "seats_won",
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
    });
    expect(model.dimension).toBe("party");
  });

  it("unit is seats with value_kind=count when value=seats_won", () => {
    const model = electionsToStackedTrend(summaries, {
      value: "seats_won",
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
    });
    expect(model.unit.label).toBe("seats");
    expect(model.unit.value_kind).toBe("count");
  });

  it("unit is share when value=vote_share_pct", () => {
    const model = electionsToStackedTrend(summaries, {
      value: "vote_share_pct",
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
    });
    expect(model.unit.value_kind).toBe("share");
  });

  it("BJP+INC seat totals match the underlying summaries (sanity check)", () => {
    const model = electionsToStackedTrend(summaries, {
      value: "seats_won",
      config: { coverage_ceiling: 0.99, max_named_categories: 12 },
    });
    const apr16 = model.bars.find(b => b.period_id === "2016-04")!;
    const segs = new Map(apr16.segments.map(s => [s.category_id, s.value ?? 0]));
    expect(segs.get("BJP")).toBe(60);
    expect(segs.get("INC")).toBe(26);
  });

  it("unions and dedupes sources across summaries", () => {
    const model = electionsToStackedTrend(summaries, {
      value: "seats_won",
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
    });
    expect(Array.isArray(model.sources)).toBe(true);
  });

  it("rejects mixed-state input", () => {
    expect(() =>
      electionsToStackedTrend([ASSAM_MAY_2026, GOA_MAY_2026], {
        value: "seats_won",
        config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      }),
    ).toThrow(/one state/);
  });

  it("rejects empty input", () => {
    expect(() =>
      electionsToStackedTrend([], {
        value: "seats_won",
        config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      }),
    ).toThrow(/empty/);
  });
});

describe("electionsToStackedTrend — designated headline override", () => {
  it("honours headline_text when supplied", () => {
    const summaries: ResultSummaryDoc[] = [ASSAM_MAY_2026];
    const model = electionsToStackedTrend(summaries, {
      value: "seats_won",
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      headline_text: "Custom headline",
    });
    expect(model.headline?.rule).toBe("designated");
    expect(model.headline?.text).toBe("Custom headline");
  });
});
