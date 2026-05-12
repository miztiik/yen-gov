import { describe, it, expect } from "vitest";
import { currentTerm, termAt, type GovernmentTimeline } from "./governments";

const TIMELINE: GovernmentTimeline = {
  $schema: "https://example.invalid/schemas/state_government.schema.json",
  $schema_version: "1.0",
  sources: [{ url: "https://example.invalid/source", fetched_at: "2026-05-01T00:00:00Z" }],
  state: "S22",
  terms: [
    {
      start: "2011-05-16",
      end: "2016-05-22",
      regime: "elected",
      party_code: "AIADMK",
      alliance: null,
      cm_name: "J. Jayalalithaa",
    },
    {
      start: "2016-05-23",
      end: "2021-05-06",
      regime: "elected",
      party_code: "AIADMK",
      alliance: null,
      cm_name: "Edappadi K. Palaniswami",
    },
    {
      start: "2021-05-07",
      end: null,
      regime: "elected",
      party_code: "DMK",
      alliance: null,
      cm_name: "M. K. Stalin",
    },
  ],
};

describe("currentTerm", () => {
  it("returns the term whose end is null", () => {
    const t = currentTerm(TIMELINE);
    expect(t).not.toBeNull();
    expect(t?.cm_name).toBe("M. K. Stalin");
  });

  it("falls back to the chronologically last term if none is open", () => {
    const closed = {
      ...TIMELINE,
      terms: TIMELINE.terms.map(t => ({ ...t, end: t.end ?? "2026-05-01" })),
    };
    const t = currentTerm(closed);
    expect(t?.cm_name).toBe("M. K. Stalin");
  });

  it("returns null on empty timeline or null input", () => {
    expect(currentTerm(null)).toBeNull();
    expect(currentTerm({ ...TIMELINE, terms: [] })).toBeNull();
  });
});

describe("termAt", () => {
  it("finds the term covering a given date", () => {
    expect(termAt(TIMELINE, "2014-01-01")?.cm_name).toBe("J. Jayalalithaa");
    expect(termAt(TIMELINE, "2018-06-15")?.cm_name).toBe("Edappadi K. Palaniswami");
    expect(termAt(TIMELINE, "2024-01-01")?.cm_name).toBe("M. K. Stalin");
  });

  it("includes the start date and end date inclusively", () => {
    expect(termAt(TIMELINE, "2011-05-16")?.cm_name).toBe("J. Jayalalithaa");
    expect(termAt(TIMELINE, "2016-05-22")?.cm_name).toBe("J. Jayalalithaa");
    expect(termAt(TIMELINE, "2016-05-23")?.cm_name).toBe("Edappadi K. Palaniswami");
  });

  it("treats end:null as covering all dates after start", () => {
    expect(termAt(TIMELINE, "2199-12-31")?.cm_name).toBe("M. K. Stalin");
  });

  it("returns null for dates before the first term", () => {
    expect(termAt(TIMELINE, "1900-01-01")).toBeNull();
  });

  it("returns null on null timeline", () => {
    expect(termAt(null, "2024-01-01")).toBeNull();
  });
});
