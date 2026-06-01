// Unit tests for the PR-B6 election time-slider stop derivation.
//
// The Svelte component is a thin shell; all the orderable/snappable logic
// lives in these pure helpers, so this is where the "snaps to real events
// only" + "clamp stale permalink" guarantees are proven.

import { describe, expect, it } from "vitest";
import { buildSliderStops, stopIndexForEvent } from "./election-time-slider";
import type { ElectionEventRow } from "../election-events";

function ev(partial: Partial<ElectionEventRow> & { event_id: string; polled_on: string }): ElectionEventRow {
  return {
    kind: "assembly",
    display: `${partial.event_id} display`,
    ...partial,
  } as ElectionEventRow;
}

// Deliberately oldest-LAST to prove the helper sorts rather than trusting
// the catalogue's hand-authored order.
const EVENTS: ElectionEventRow[] = [
  ev({ event_id: "AcGenMay2026", polled_on: "2026-05-02", display: "May 2026" }),
  ev({ event_id: "AcGenApr2016", polled_on: "2016-04-04", display: "Apr 2016" }),
  ev({ event_id: "AcGenApr2021", polled_on: "2021-04-06", display: "Apr 2021" }),
];

describe("buildSliderStops", () => {
  it("sorts stops chronologically ascending (oldest first)", () => {
    const stops = buildSliderStops(EVENTS);
    expect(stops.map(s => s.event_id)).toEqual([
      "AcGenApr2016",
      "AcGenApr2021",
      "AcGenMay2026",
    ]);
  });

  it("derives a 4-digit year label from polled_on", () => {
    const stops = buildSliderStops(EVENTS);
    expect(stops.map(s => s.label)).toEqual(["2016", "2021", "2026"]);
  });

  it("carries the full display string for the active readout", () => {
    const stops = buildSliderStops(EVENTS);
    expect(stops[2].display).toBe("May 2026");
  });

  it("collapses duplicate event_ids to a single stop (snaps to real events)", () => {
    const withDupe = [...EVENTS, ev({ event_id: "AcGenApr2021", polled_on: "2021-04-06" })];
    const stops = buildSliderStops(withDupe);
    expect(stops).toHaveLength(3);
    expect(stops.filter(s => s.event_id === "AcGenApr2021")).toHaveLength(1);
  });

  it("returns an empty array for no events", () => {
    expect(buildSliderStops([])).toEqual([]);
  });

  it("does not mutate the input array order", () => {
    const before = EVENTS.map(e => e.event_id);
    buildSliderStops(EVENTS);
    expect(EVENTS.map(e => e.event_id)).toEqual(before);
  });
});

describe("stopIndexForEvent", () => {
  const stops = buildSliderStops(EVENTS);

  it("finds the index of a present event id", () => {
    expect(stopIndexForEvent(stops, "AcGenApr2016")).toBe(0);
    expect(stopIndexForEvent(stops, "AcGenApr2021")).toBe(1);
    expect(stopIndexForEvent(stops, "AcGenMay2026")).toBe(2);
  });

  it("clamps an unknown/extinct event id to the most-recent stop", () => {
    expect(stopIndexForEvent(stops, "AcGenJan1990")).toBe(2);
  });

  it("clamps a null selection to the most-recent stop", () => {
    expect(stopIndexForEvent(stops, null)).toBe(2);
  });
});
