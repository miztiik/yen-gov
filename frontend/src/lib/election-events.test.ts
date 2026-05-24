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
    // Multi-event, default:true on the latest — the well-behaved historical shape.
    // Defaults are now ignored; max(polled_on) selects the same row.
    S22: [
      { event_id: "AcGenMay2026", kind: "assembly", display: "TN AC May 2026", polled_on: "2026-05-06", default: true },
      { event_id: "AcGenApr2021", kind: "assembly", display: "TN AC Apr 2021", polled_on: "2021-04-06" },
    ],
    // Single event — degenerate case.
    S25: [
      { event_id: "AcGenMar2021", kind: "assembly", display: "WB AC Mar 2021", polled_on: "2021-03-27" },
    ],
    // The Meghalaya/Tripura bug shape: multi-event, NO default flag anywhere,
    // oldest-first array order (how the AE-panel backfills landed). The old
    // function returned rows[0]=1978 (45-year regression); the new function
    // returns max(polled_on)=2023.
    S15: [
      { event_id: "AcGenFeb1978", kind: "assembly", display: "ML AC Feb 1978", polled_on: "1978-02-25" },
      { event_id: "AcGenFeb2023", kind: "assembly", display: "ML AC Feb 2023", polled_on: "2023-02-27" },
    ],
    // Stale-flag shape: default:true on the OLDER event. max(polled_on) must
    // still win — flag drift cannot override the canonical date fact.
    S08: [
      { event_id: "AcGenNov2017", kind: "assembly", display: "HP AC Nov 2017", polled_on: "2017-11-09", default: true },
      { event_id: "AcGenNov2022", kind: "assembly", display: "HP AC Nov 2022", polled_on: "2022-11-12" },
    ],
    S04: [], // empty array — explicit "no data" signal
  },
};

describe("defaultEventForState", () => {
  it("returns the event with the most recent polled_on", () => {
    expect(defaultEventForState(CATALOGUE, "S22")?.event_id).toBe("AcGenMay2026");
  });

  it("returns the only row when the state has a single event", () => {
    expect(defaultEventForState(CATALOGUE, "S25")?.event_id).toBe("AcGenMar2021");
  });

  it("regression: returns max(polled_on) when no row carries default:true and the array is oldest-first (Meghalaya/Tripura bug)", () => {
    expect(defaultEventForState(CATALOGUE, "S15")?.event_id).toBe("AcGenFeb2023");
  });

  it("regression: ignores a stale default:true flag pointed at an older event", () => {
    expect(defaultEventForState(CATALOGUE, "S08")?.event_id).toBe("AcGenNov2022");
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

  it("sorts events most-recent-first by polled_on regardless of on-disk order", () => {
    // S15 is oldest-first on disk (1978, 2023). After sorting, latest leads.
    const out = listEventsForState(CATALOGUE, "S15");
    expect(out.map(e => e.event_id)).toEqual(["AcGenFeb2023", "AcGenFeb1978"]);
  });

  it("does not mutate the input catalogue array", () => {
    const before = CATALOGUE.states.S15.map(e => e.event_id);
    listEventsForState(CATALOGUE, "S15");
    expect(CATALOGUE.states.S15.map(e => e.event_id)).toEqual(before);
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
