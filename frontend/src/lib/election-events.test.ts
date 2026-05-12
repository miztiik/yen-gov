import { describe, it, expect } from "vitest";
import {
  defaultEventForState,
  listEventsForState,
  findEvent,
  daysSincePolled,
  type ElectionEventsCatalogue,
} from "./election-events";

const CATALOGUE: ElectionEventsCatalogue = {
  $schema: "https://example.invalid/schemas/election-events.schema.json",
  $schema_version: "1.0",
  sources: [{ url: "https://example.invalid/source", fetched_at: "2026-05-01T00:00:00Z" }],
  states: {
    S22: [
      { event_id: "AcGenMay2026", kind: "assembly", display: "TN AC May 2026", polled_on: "2026-05-06", default: true },
      { event_id: "AcGenApr2021", kind: "assembly", display: "TN AC Apr 2021", polled_on: "2021-04-06" },
    ],
    S25: [
      { event_id: "AcGenMar2021", kind: "assembly", display: "WB AC Mar 2021", polled_on: "2021-03-27" },
    ],
    S04: [], // empty array — explicit "no data" signal
  },
};

describe("defaultEventForState", () => {
  it("returns the row marked default:true", () => {
    expect(defaultEventForState(CATALOGUE, "S22")?.event_id).toBe("AcGenMay2026");
  });

  it("falls back to the first row when no default flag is set", () => {
    expect(defaultEventForState(CATALOGUE, "S25")?.event_id).toBe("AcGenMar2021");
  });

  it("returns null for unknown state, empty state, or null inputs", () => {
    expect(defaultEventForState(CATALOGUE, "S99")).toBeNull();
    expect(defaultEventForState(CATALOGUE, "S04")).toBeNull();
    expect(defaultEventForState(null, "S22")).toBeNull();
    expect(defaultEventForState(CATALOGUE, null)).toBeNull();
  });
});

describe("listEventsForState", () => {
  it("returns the full per-state list", () => {
    expect(listEventsForState(CATALOGUE, "S22")).toHaveLength(2);
  });

  it("returns an empty array for unknown / null inputs", () => {
    expect(listEventsForState(CATALOGUE, "S99")).toEqual([]);
    expect(listEventsForState(null, "S22")).toEqual([]);
    expect(listEventsForState(CATALOGUE, null)).toEqual([]);
  });
});

describe("findEvent", () => {
  it("looks up an event by id within a state", () => {
    expect(findEvent(CATALOGUE, "S22", "AcGenApr2021")?.display).toBe("TN AC Apr 2021");
  });

  it("returns null when the event id is unknown for that state", () => {
    expect(findEvent(CATALOGUE, "S22", "AcGenJan1990")).toBeNull();
  });
});

describe("daysSincePolled", () => {
  it("returns the integer day count from polled_on to now", () => {
    const row = { event_id: "x", kind: "assembly", display: "x", polled_on: "2026-05-01" } as const;
    const now = new Date("2026-05-11T12:00:00Z");
    expect(daysSincePolled(row, now)).toBe(10);
  });

  it("returns negative for future polling dates", () => {
    const row = { event_id: "x", kind: "assembly", display: "x", polled_on: "2026-12-31" } as const;
    const now = new Date("2026-05-01T00:00:00Z");
    expect(daysSincePolled(row, now)).toBeLessThan(0);
  });
});
