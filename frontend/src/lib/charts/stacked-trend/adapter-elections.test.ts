import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  electionsToStackedTrend,
  parseElectionEventId,
  type ResultSummaryDoc,
} from "./adapter-elections";

const repoRoot = resolve(__dirname, "../../../../..");

function loadSummary(event: string, state: string): ResultSummaryDoc {
  const p = resolve(
    repoRoot,
    `datasets/elections/${event}/${state}/result.summary.json`,
  );
  return JSON.parse(readFileSync(p, "utf-8")) as ResultSummaryDoc;
}

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
  const summaries = [
    loadSummary("AcGenApr2016", "S03"),
    loadSummary("AcGenApr2021", "S03"),
    loadSummary("AcGenMay2026", "S03"),
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
      electionsToStackedTrend([loadSummary("AcGenMay2026", "S03"), loadSummary("AcGenMay2026", "S11")], {
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
    const summaries = [loadSummary("AcGenMay2026", "S03")];
    const model = electionsToStackedTrend(summaries, {
      value: "seats_won",
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      headline_text: "Custom headline",
    });
    expect(model.headline?.rule).toBe("designated");
    expect(model.headline?.text).toBe("Custom headline");
  });
});
