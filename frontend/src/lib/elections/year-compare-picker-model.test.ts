import { describe, expect, it } from "vitest";

import {
  buildYearPickerOptions,
  buildTimeOrderedYearOptions,
  type YearPickerSourceEvent,
} from "./year-compare-picker-model";

const EVENTS: YearPickerSourceEvent[] = [
  { event_id: "assembly-2016", year_label: "2016", winner_color_hex: "#abc" },
  { event_id: "assembly-2021", year_label: "2021", winner_color_hex: null },
  { event_id: "assembly-2026", year_label: "2026", winner_color_hex: "#def" },
];

const DATED: YearPickerSourceEvent[] = [
  { event_id: "a-2011", year_label: "2011", winner_color_hex: null, polled_on: "2011-04-13" },
  { event_id: "a-2016", year_label: "2016", winner_color_hex: null, polled_on: "2016-05-16" },
  { event_id: "a-2021", year_label: "2021", winner_color_hex: null, polled_on: "2021-04-06" },
];

describe("buildYearPickerOptions", () => {
  it("preserves the caller's ordering verbatim", () => {
    const out = buildYearPickerOptions(EVENTS);
    expect(out.map((o) => o.event_id)).toEqual([
      "assembly-2016",
      "assembly-2021",
      "assembly-2026",
    ]);
  });

  it("carries year_label + winner_color_hex through unchanged", () => {
    const out = buildYearPickerOptions(EVENTS);
    expect(out[0]).toMatchObject({
      year_label: "2016",
      winner_color_hex: "#abc",
    });
    expect(out[1].winner_color_hex).toBeNull();
  });

  it("flags exactly the excludeEventId option as disabled", () => {
    const out = buildYearPickerOptions(EVENTS, {
      excludeEventId: "assembly-2021",
    });
    expect(out.map((o) => o.is_disabled)).toEqual([false, true, false]);
  });

  it("disables nothing when no excludeEventId is given", () => {
    const out = buildYearPickerOptions(EVENTS);
    expect(out.every((o) => !o.is_disabled)).toBe(true);
  });

  it("disables nothing when excludeEventId matches no event", () => {
    const out = buildYearPickerOptions(EVENTS, {
      excludeEventId: "assembly-1999",
    });
    expect(out.every((o) => !o.is_disabled)).toBe(true);
  });

  it("returns an empty array for empty input", () => {
    expect(buildYearPickerOptions([])).toEqual([]);
  });
});

describe("buildTimeOrderedYearOptions", () => {
  // Later selection = 2021; the EARLIER selector must disable 2021 and
  // anything after it (none here), keeping only strictly-earlier years.
  it("earlier role: disables years at/after the later selection", () => {
    const out = buildTimeOrderedYearOptions(DATED, {
      role: "earlier",
      otherPolledOn: "2021-04-06",
    });
    expect(out.map((o) => [o.event_id, o.is_disabled])).toEqual([
      ["a-2011", false],
      ["a-2016", false],
      ["a-2021", true],
    ]);
  });

  // Earlier selection = 2016; the LATER selector must disable 2016 and
  // anything before it, keeping only strictly-later years.
  it("later role: disables years at/before the earlier selection", () => {
    const out = buildTimeOrderedYearOptions(DATED, {
      role: "later",
      otherPolledOn: "2016-05-16",
    });
    expect(out.map((o) => [o.event_id, o.is_disabled])).toEqual([
      ["a-2011", true],
      ["a-2016", true],
      ["a-2021", false],
    ]);
  });

  it("bans the same year on both sides (the boundary is disabled)", () => {
    const earlier = buildTimeOrderedYearOptions(DATED, {
      role: "earlier",
      otherPolledOn: "2016-05-16",
    });
    // 2016 itself (== other) is disabled for the earlier selector.
    expect(earlier.find((o) => o.event_id === "a-2016")?.is_disabled).toBe(true);
  });

  it("allows any gap (N-5 vs N): 2011 stays selectable against 2021", () => {
    const out = buildTimeOrderedYearOptions(DATED, {
      role: "earlier",
      otherPolledOn: "2021-04-06",
    });
    expect(out.find((o) => o.event_id === "a-2011")?.is_disabled).toBe(false);
  });

  it("disables nothing when otherPolledOn is null", () => {
    const out = buildTimeOrderedYearOptions(DATED, {
      role: "earlier",
      otherPolledOn: null,
    });
    expect(out.every((o) => !o.is_disabled)).toBe(true);
  });
});
