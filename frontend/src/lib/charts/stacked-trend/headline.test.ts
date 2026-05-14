import { describe, it, expect } from "vitest";
import { computeHeadline, designated, none, type HeadlineContext } from "./headline";
import type { StackedTrendBar } from "./types";

const ctx: HeadlineContext = {
  entity_label: "Chennai Central",
  category_labels: { DMK: "DMK", AIADMK: "AIADMK", BJP: "BJP" },
  value_kind: "share",
  unit_label: "%",
};

const bar = (period_id: string, order: number, segs: Record<string, number>): StackedTrendBar => ({
  period_id,
  period_label: period_id,
  order,
  segments: Object.entries(segs).map(([category_id, value]) => ({
    category_id,
    value,
    availability: "present" as const,
  })),
});

describe("max_latest_with_streak", () => {
  it("triggers on 4-of-5", () => {
    const bars = [
      bar("2001", 0, { DMK: 50, AIADMK: 40 }),
      bar("2006", 1, { DMK: 50, AIADMK: 40 }),
      bar("2011", 2, { AIADMK: 50, DMK: 40 }),
      bar("2016", 3, { DMK: 50, AIADMK: 40 }),
      bar("2021", 4, { DMK: 50, AIADMK: 40 }),
    ];
    const h = computeHeadline("max_latest_with_streak", bars, ctx);
    expect(h?.rule).toBe("max_latest_with_streak");
    expect(h?.text).toContain("DMK");
    expect(h?.text).toContain("4");
    expect(h?.highlight_category_id).toBe("DMK");
  });

  it("triggers on 3-period streak even when total wins < 4", () => {
    const bars = [
      bar("2001", 0, { AIADMK: 50, DMK: 40 }),
      bar("2006", 1, { AIADMK: 50, DMK: 40 }),
      bar("2011", 2, { DMK: 50, AIADMK: 40 }),
      bar("2016", 3, { DMK: 50, AIADMK: 40 }),
      bar("2021", 4, { DMK: 50, AIADMK: 40 }),
    ];
    const h = computeHeadline("max_latest_with_streak", bars, ctx);
    expect(h?.text).toContain("in a row");
    expect(h?.highlight_category_id).toBe("DMK");
  });

  it("returns none when no clean story", () => {
    const bars = [
      bar("2001", 0, { DMK: 50, AIADMK: 40 }),
      bar("2006", 1, { AIADMK: 50, DMK: 40 }),
      bar("2011", 2, { DMK: 50, AIADMK: 40 }),
      bar("2016", 3, { AIADMK: 50, DMK: 40 }),
    ];
    const h = computeHeadline("max_latest_with_streak", bars, ctx);
    expect(h?.rule).toBe("none");
    expect(h?.text).toBe("");
  });

  it("returns none with < 3 bars", () => {
    const bars = [bar("2001", 0, { DMK: 50, AIADMK: 40 }), bar("2006", 1, { DMK: 50, AIADMK: 40 })];
    expect(computeHeadline("max_latest_with_streak", bars, ctx)?.rule).toBe("none");
  });

  it("so_what for share value_kind shows pp delta", () => {
    const bars = [
      bar("A", 0, { DMK: 50, AIADMK: 50 }),
      bar("B", 1, { DMK: 55, AIADMK: 45 }),
      bar("C", 2, { DMK: 60, AIADMK: 40 }),
    ];
    const h = computeHeadline("max_latest_with_streak", bars, ctx);
    expect(h?.rule).toBe("max_latest_with_streak");
    expect(h?.so_what).toContain("pp");
    expect(h?.so_what).toContain("DMK");
  });
});

describe("max_lifetime", () => {
  it("triggers when one category dominates ≥ threshold", () => {
    const bars = [bar("X", 0, { coal: 80, gas: 20 }), bar("Y", 1, { coal: 70, gas: 30 })];
    const h = computeHeadline("max_lifetime", bars, {
      ...ctx,
      entity_label: "TN",
      category_labels: { coal: "Coal", gas: "Gas" },
      value_kind: "raw",
      unit_label: "MW",
    });
    expect(h?.rule).toBe("max_lifetime");
    expect(h?.text).toContain("Coal");
    expect(h?.highlight_category_id).toBe("coal");
  });

  it("returns none when no category passes threshold", () => {
    const bars = [bar("X", 0, { coal: 50, gas: 50 })];
    expect(computeHeadline("max_lifetime", bars, ctx)?.rule).toBe("none");
  });
});

describe("designated and none", () => {
  it("designated headline carries supplied text", () => {
    const h = designated("Custom story here", "DMK");
    expect(h?.rule).toBe("designated");
    expect(h?.text).toBe("Custom story here");
    expect(h?.highlight_category_id).toBe("DMK");
  });
  it("none returns empty", () => {
    expect(none()?.rule).toBe("none");
    expect(none()?.text).toBe("");
  });
});
