/**
 * Unit tests for sibling-events-rail-model.
 *
 * Asserts the J-elevated-4 verdict baked into R4 of
 * TODO/20260615-state-election-event-page-redesign-plan.md
 * (2026-06-15):
 *  - chips sorted ASC by polled_on (oldest-to-newest); citizen reads
 *    left-to-right in time.
 *  - is_current flag identifies the active chip.
 *  - prior_year / compare_href OMITTED when the current event has no
 *    prior same-body sibling (J-elevated-4 single-event rail pin).
 *  - winner_color_hex is the resolver's output verbatim (production
 *    closes over the event_summary mart; tests stub it).
 *  - deriveYearLabel: standard `<kind>-<YYYY>` shape, future v1.4
 *    `<kind>-<YYYY>-<month-slug>` shape, and the unknown fallback.
 *  - same-body filter: parliament events DO NOT appear on the
 *    assembly rail (and vice versa).
 */

import { describe, expect, it } from "vitest";

import {
  buildSiblingEventsRail,
  deriveYearLabel,
  deriveYearNumber,
  siblingKindFor,
} from "./sibling-events-rail-model";
import type {
  ElectionEventRow,
  ElectionEventsCatalogue,
} from "../election-events";

interface FixtureEvent extends ElectionEventRow {
  /** state_code is a fixture-only grouping key (the production
   *  ElectionEventRow has no state_code field; the catalogue carries
   *  it as the outer dict key). The fixture builder uses this to
   *  bucket rows into the right state, then drops it from the
   *  emitted catalogue shape. */
  __state_code: string;
}

function fixtureCatalogue(rows: FixtureEvent[]): ElectionEventsCatalogue {
  const states: Record<string, ElectionEventRow[]> = {};
  for (const r of rows) {
    const sc = r.__state_code;
    if (!states[sc]) states[sc] = [];
    // Drop the fixture-only marker so the catalogue rows match the
    // production ElectionEventRow shape verbatim.
    const { __state_code: _ignored, ...row } = r;
    void _ignored;
    states[sc].push(row);
  }
  return {
    $schema: "test",
    $schema_version: "test",
    sources: [],
    states,
  };
}

function fixtureEvent(
  partial: Partial<ElectionEventRow> & {
    event_id: string;
    state_code: string;
    polled_on: string;
  },
): FixtureEvent {
  return {
    event_id: partial.event_id,
    polled_on: partial.polled_on,
    kind: partial.kind ?? "assembly",
    display: partial.display ?? partial.event_id,
    data_status: partial.data_status ?? "complete",
    event_id_aliases: partial.event_id_aliases ?? [],
    __state_code: partial.state_code,
  };
}

describe("deriveYearLabel", () => {
  it("strips the kind prefix and returns the bare year for standard ids", () => {
    expect(deriveYearLabel("assembly-2024")).toBe("2024");
    expect(deriveYearLabel("parliament-2019")).toBe("2019");
    expect(deriveYearLabel("general-2024")).toBe("2024");
  });
  it("emits 'YYYY MMM' for future catalogue v1.4 collision ids", () => {
    expect(deriveYearLabel("assembly-2005-feb")).toBe("2005 FEB");
    expect(deriveYearLabel("assembly-2005-nov")).toBe("2005 NOV");
  });
  it("falls back to the event_id verbatim when neither shape matches", () => {
    expect(deriveYearLabel("assembly-bye-2024-channapatna")).toBe(
      "assembly-bye-2024-channapatna",
    );
    expect(deriveYearLabel("weird-id")).toBe("weird-id");
  });
});

describe("deriveYearNumber", () => {
  it("returns the year integer for standard ids", () => {
    expect(deriveYearNumber("assembly-2024")).toBe(2024);
    expect(deriveYearNumber("parliament-2019")).toBe(2019);
  });
  it("returns the year integer for collision ids", () => {
    expect(deriveYearNumber("assembly-2005-feb")).toBe(2005);
  });
  it("returns null for shapes lacking a 4-digit year", () => {
    expect(deriveYearNumber("weird-id")).toBeNull();
  });
});

describe("siblingKindFor", () => {
  it("maps 'ac' to 'assembly' and 'pc' to 'parliament'", () => {
    expect(siblingKindFor("ac")).toBe("assembly");
    expect(siblingKindFor("pc")).toBe("parliament");
  });
});

describe("buildSiblingEventsRail", () => {
  const STATE_CODE = "S13";
  const STATE_SLUG = "maharashtra";

  it("sorts chips ASC by polled_on and flags the current chip", () => {
    const catalogue = fixtureCatalogue([
      fixtureEvent({
        event_id: "assembly-2019",
        state_code: STATE_CODE,
        polled_on: "2019-10-21",
        kind: "assembly",
        display: "Maharashtra Assembly 2019",
      }),
      fixtureEvent({
        event_id: "assembly-2024",
        state_code: STATE_CODE,
        polled_on: "2024-11-20",
        kind: "assembly",
        display: "Maharashtra Assembly 2024",
      }),
      fixtureEvent({
        event_id: "assembly-2014",
        state_code: STATE_CODE,
        polled_on: "2014-10-15",
        kind: "assembly",
        display: "Maharashtra Assembly 2014",
      }),
    ]);
    const rail = buildSiblingEventsRail({
      catalogue,
      state_code: STATE_CODE,
      state_slug: STATE_SLUG,
      current_event_id: "assembly-2024",
      body: "ac",
      winner_color_for_event_id: () => null,
    });
    expect(rail.events.map((c) => c.event_id)).toEqual([
      "assembly-2014",
      "assembly-2019",
      "assembly-2024",
    ]);
    expect(rail.events.map((c) => c.is_current)).toEqual([false, false, true]);
  });

  it("computes prior_year + compare_href when a prior same-body event exists", () => {
    const catalogue = fixtureCatalogue([
      fixtureEvent({
        event_id: "assembly-2019",
        state_code: STATE_CODE,
        polled_on: "2019-10-21",
      }),
      fixtureEvent({
        event_id: "assembly-2024",
        state_code: STATE_CODE,
        polled_on: "2024-11-20",
      }),
    ]);
    const rail = buildSiblingEventsRail({
      catalogue,
      state_code: STATE_CODE,
      state_slug: STATE_SLUG,
      current_event_id: "assembly-2024",
      body: "ac",
      winner_color_for_event_id: () => null,
    });
    expect(rail.prior_year).toBe(2019);
    expect(rail.compare_href).toBe(
      "/compare/elections/maharashtra/assembly-2019/assembly-2024",
    );
    // PR1: the Compare picker offers the earlier same-body event(s) as
    // selectable "from" years; state_slug + current_event_id are echoed
    // so the picker can build compare URLs.
    expect(rail.state_slug).toBe(STATE_SLUG);
    expect(rail.current_event_id).toBe("assembly-2024");
    expect(rail.compare_options.map((o) => o.event_id)).toEqual([
      "assembly-2019",
    ]);
    expect(rail.compare_options.every((o) => !o.is_disabled)).toBe(true);
  });

  it("OMITS prior_year + compare_href when the current event is the FIRST chip (J-elevated-4 single-event pin)", () => {
    const catalogue = fixtureCatalogue([
      fixtureEvent({
        event_id: "assembly-2024",
        state_code: "U08",
        polled_on: "2024-09-25",
        display: "J&K Assembly 2024",
      }),
    ]);
    const rail = buildSiblingEventsRail({
      catalogue,
      state_code: "U08",
      state_slug: "jammu-and-kashmir-ut",
      current_event_id: "assembly-2024",
      body: "ac",
      winner_color_for_event_id: () => null,
    });
    expect(rail.events).toHaveLength(1);
    expect(rail.prior_year).toBeNull();
    expect(rail.compare_href).toBeNull();
    // PR1: no earlier event -> the Compare picker has no options and the
    // rail renders no Compare control.
    expect(rail.compare_options).toEqual([]);
  });

  it("excludes events of the OTHER body kind (assembly rail hides parliament rows)", () => {
    const catalogue = fixtureCatalogue([
      fixtureEvent({
        event_id: "assembly-2019",
        state_code: STATE_CODE,
        polled_on: "2019-10-21",
        kind: "assembly",
      }),
      fixtureEvent({
        event_id: "general-2024",
        state_code: STATE_CODE,
        polled_on: "2024-05-13",
        kind: "parliament",
        display: "Maharashtra Parliament 2024",
      }),
      fixtureEvent({
        event_id: "assembly-2024",
        state_code: STATE_CODE,
        polled_on: "2024-11-20",
        kind: "assembly",
      }),
    ]);
    const ac_rail = buildSiblingEventsRail({
      catalogue,
      state_code: STATE_CODE,
      state_slug: STATE_SLUG,
      current_event_id: "assembly-2024",
      body: "ac",
      winner_color_for_event_id: () => null,
    });
    expect(ac_rail.events.map((c) => c.event_id)).toEqual([
      "assembly-2019",
      "assembly-2024",
    ]);
    const pc_rail = buildSiblingEventsRail({
      catalogue,
      state_code: STATE_CODE,
      state_slug: STATE_SLUG,
      current_event_id: "general-2024",
      body: "pc",
      winner_color_for_event_id: () => null,
    });
    expect(pc_rail.events.map((c) => c.event_id)).toEqual(["general-2024"]);
  });

  it("threads winner_color_hex through from the resolver", () => {
    const catalogue = fixtureCatalogue([
      fixtureEvent({
        event_id: "assembly-2024",
        state_code: STATE_CODE,
        polled_on: "2024-11-20",
      }),
      fixtureEvent({
        event_id: "assembly-2019",
        state_code: STATE_CODE,
        polled_on: "2019-10-21",
      }),
    ]);
    const palette: Record<string, string> = {
      "assembly-2024": "#f97316",
      "assembly-2019": "#0ea5e9",
    };
    const rail = buildSiblingEventsRail({
      catalogue,
      state_code: STATE_CODE,
      state_slug: STATE_SLUG,
      current_event_id: "assembly-2024",
      body: "ac",
      winner_color_for_event_id: (id) => palette[id] ?? null,
    });
    const by_id = new Map(rail.events.map((c) => [c.event_id, c.winner_color_hex]));
    expect(by_id.get("assembly-2024")).toBe("#f97316");
    expect(by_id.get("assembly-2019")).toBe("#0ea5e9");
  });

  it("href encodes the event_id segment for safety", () => {
    const catalogue = fixtureCatalogue([
      fixtureEvent({
        event_id: "assembly-2005-feb",
        state_code: "S04",
        polled_on: "2005-02-23",
        display: "Bihar Assembly 2005 (Feb)",
      }),
    ]);
    const rail = buildSiblingEventsRail({
      catalogue,
      state_code: "S04",
      state_slug: "bihar",
      current_event_id: "assembly-2005-feb",
      body: "ac",
      winner_color_for_event_id: () => null,
    });
    expect(rail.events[0].href).toBe(
      "/bihar/elections/assembly-2005-feb",
    );
    expect(rail.events[0].year_label).toBe("2005 FEB");
  });
});
