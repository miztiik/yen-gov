import { describe, expect, it } from "vitest";

import {
  buildYearPickerOptions,
  type YearPickerSourceEvent,
} from "./year-compare-picker-model";

const EVENTS: YearPickerSourceEvent[] = [
  { event_id: "assembly-2016", year_label: "2016", winner_color_hex: "#abc" },
  { event_id: "assembly-2021", year_label: "2021", winner_color_hex: null },
  { event_id: "assembly-2026", year_label: "2026", winner_color_hex: "#def" },
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
