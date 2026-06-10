import { describe, it, expect } from "vitest";

import type { ElectionEventRow } from "../election-events";
import {
  deriveStrip,
  pillStateFor,
  sortEventsByPolledOn,
  type PillState,
} from "./year-pill-strip-model";

// 18 fictional events spanning 1957..2024 so the plan-doc's "18 pills"
// oracle exercises the sort + year extraction without dragging in
// real-world entity_ids. The natural order is intentionally scrambled
// so the sort assertion has something to bite on.
const EIGHTEEN_EVENTS: ElectionEventRow[] = [
  { event_id: "general-2009", kind: "parliament", display: "GE 2009", polled_on: "2009-05-13" },
  { event_id: "general-1957", kind: "parliament", display: "GE 1957", polled_on: "1957-03-12" },
  { event_id: "general-2024", kind: "parliament", display: "GE 2024", polled_on: "2024-06-01" },
  { event_id: "general-1971", kind: "parliament", display: "GE 1971", polled_on: "1971-03-10" },
  { event_id: "general-1962", kind: "parliament", display: "GE 1962", polled_on: "1962-02-19" },
  { event_id: "general-1967", kind: "parliament", display: "GE 1967", polled_on: "1967-02-21" },
  { event_id: "general-1977", kind: "parliament", display: "GE 1977", polled_on: "1977-03-20" },
  { event_id: "general-1980", kind: "parliament", display: "GE 1980", polled_on: "1980-01-06" },
  { event_id: "general-1984", kind: "parliament", display: "GE 1984", polled_on: "1984-12-27" },
  { event_id: "general-1989", kind: "parliament", display: "GE 1989", polled_on: "1989-11-26" },
  { event_id: "general-1991", kind: "parliament", display: "GE 1991", polled_on: "1991-06-15" },
  { event_id: "general-1996", kind: "parliament", display: "GE 1996", polled_on: "1996-05-07" },
  { event_id: "general-1998", kind: "parliament", display: "GE 1998", polled_on: "1998-03-07" },
  { event_id: "general-1999", kind: "parliament", display: "GE 1999", polled_on: "1999-10-13" },
  { event_id: "general-2004", kind: "parliament", display: "GE 2004", polled_on: "2004-05-10" },
  { event_id: "general-2014", kind: "parliament", display: "GE 2014", polled_on: "2014-05-12" },
  { event_id: "general-2019", kind: "parliament", display: "GE 2019", polled_on: "2019-05-19" },
  { event_id: "general-1952", kind: "parliament", display: "GE 1952", polled_on: "1952-04-17" },
];

describe("sortEventsByPolledOn", () => {
  it("sorts oldest-first by ISO polled_on, never mutates the input", () => {
    const before = EIGHTEEN_EVENTS.map((e) => e.event_id);
    const sorted = sortEventsByPolledOn(EIGHTEEN_EVENTS);
    expect(sorted.map((e) => e.polled_on)).toEqual([
      "1952-04-17",
      "1957-03-12",
      "1962-02-19",
      "1967-02-21",
      "1971-03-10",
      "1977-03-20",
      "1980-01-06",
      "1984-12-27",
      "1989-11-26",
      "1991-06-15",
      "1996-05-07",
      "1998-03-07",
      "1999-10-13",
      "2004-05-10",
      "2009-05-13",
      "2014-05-12",
      "2019-05-19",
      "2024-06-01",
    ]);
    expect(EIGHTEEN_EVENTS.map((e) => e.event_id)).toEqual(before);
  });

  it("handles the single-event and empty cases", () => {
    expect(sortEventsByPolledOn([])).toEqual([]);
    expect(
      sortEventsByPolledOn([
        { event_id: "general-2024", kind: "parliament", display: "x", polled_on: "2024-06-01" },
      ]).map((e) => e.event_id),
    ).toEqual(["general-2024"]);
  });
});

describe("pillStateFor", () => {
  const row: ElectionEventRow = {
    event_id: "general-2024",
    kind: "parliament",
    display: "GE 2024",
    polled_on: "2024-06-01",
  };

  it("extracts the year from the ISO polled_on head", () => {
    expect(pillStateFor(row, "general-2019").year).toBe(2024);
  });

  it("marks the active pill when the event_id matches", () => {
    const active = pillStateFor(row, "general-2024");
    const inactive = pillStateFor(row, "general-2019");
    expect(active.is_active).toBe(true);
    expect(inactive.is_active).toBe(false);
  });

  it("emits 0 for a malformed polled_on head (schema-break safety)", () => {
    expect(
      pillStateFor(
        { ...row, polled_on: "not-an-iso" },
        "general-2024",
      ).year,
    ).toBe(0);
  });
});

describe("deriveStrip (sort + project in one pass)", () => {
  it("the plan-doc oracle: 18 pills for 18 events, sorted oldest-first, exactly one active", () => {
    const strip: PillState[] = deriveStrip(EIGHTEEN_EVENTS, "general-2024");
    expect(strip).toHaveLength(18);
    expect(strip.map((p) => p.year)).toEqual([
      1952, 1957, 1962, 1967, 1971, 1977, 1980, 1984, 1989, 1991, 1996, 1998,
      1999, 2004, 2009, 2014, 2019, 2024,
    ]);
    const active = strip.filter((p) => p.is_active);
    expect(active).toHaveLength(1);
    expect(active[0].event_id).toBe("general-2024");
  });

  it("no pill is active when the active_event_id does not match any row", () => {
    const strip = deriveStrip(EIGHTEEN_EVENTS, "general-9999");
    expect(strip.every((p) => !p.is_active)).toBe(true);
  });

  it("supports onSelect contract: the active pill's event_id is the one onSelect would fire", () => {
    // The Svelte component fires `onSelect(event_id)` on click. The pure
    // model guarantees every row carries an event_id verbatim from the
    // input - the click handler at the template layer can pass it
    // through with no transformation.
    const strip = deriveStrip(EIGHTEEN_EVENTS, "general-2024");
    for (const pill of strip) {
      expect(typeof pill.event_id).toBe("string");
      expect(pill.event_id.startsWith("general-")).toBe(true);
    }
  });
});
