/**
 * Unit tests for the per-row card-plan projection (R7).
 *
 * The pure projection is the load-bearing seam between the on-disk
 * mart and the SVG bytes. Tests cover:
 *  - state-scope rows resolve to /share/{state-slug}/{event_id}.png
 *  - national-scope rows resolve to /share/national/{event_id}.png
 *  - missing party_id falls back to the no-winner headline shape
 *  - missing state lookup returns null (build skips the row, does
 *    not write garbage)
 *  - body-label mapping covers every catalogue kind
 *  - year-label extraction prefers event_id over polled_on
 */

import { describe, expect, it } from "vitest";

import {
  buildCardPlan,
  type EventSummaryRowForCard,
  type PartyRowForCard,
  type SourceRowForCard,
  type StateRowForCard,
} from "./plan";

const PARTIES = new Map<string, PartyRowForCard>([
  ["parties.IN.BJP", { party_id: "parties.IN.BJP", short: "BJP", brand_colour: "#FF9933" }],
  ["parties.IN.INC", { party_id: "parties.IN.INC", short: "INC", brand_colour: "#138808" }],
]);

const STATES = new Map<string, StateRowForCard>([
  ["S13", { state_code: "S13", state_name: "Maharashtra", state_slug: "maharashtra" }],
  ["U08", { state_code: "U08", state_name: "Jammu & Kashmir (UT)", state_slug: "jammu-and-kashmir-ut" }],
]);

const SOURCES = new Map<string, SourceRowForCard>([
  ["src-eci-ae", { source_id: "src-eci-ae", producer: "Election Commission of India" }],
]);

function row(partial: Partial<EventSummaryRowForCard>): EventSummaryRowForCard {
  // `??` short-circuits on undefined OR null; tests that need null
  // for leading_party_id / state_code pass null explicitly and the
  // fallback would override it. Use the `in` check so null partials
  // are respected verbatim.
  const has = (k: keyof EventSummaryRowForCard): boolean => k in partial;
  return {
    event_id: has("event_id") ? (partial.event_id as string) : "assembly-2024",
    state_code: has("state_code") ? partial.state_code! : "S13",
    scope: has("scope") ? (partial.scope as EventSummaryRowForCard["scope"]) : "state",
    kind: has("kind") ? (partial.kind as EventSummaryRowForCard["kind"]) : "assembly",
    polled_on: has("polled_on") ? (partial.polled_on as string) : "2024-11-20",
    leading_party_id: has("leading_party_id")
      ? partial.leading_party_id!
      : "parties.IN.BJP",
    seats_won: has("seats_won") ? (partial.seats_won as number) : 132,
    seats_contested: has("seats_contested") ? (partial.seats_contested as number) : 288,
    source_id: has("source_id") ? (partial.source_id as string) : "src-eci-ae",
  };
}

describe("buildCardPlan", () => {
  it("resolves a state-scope row to share/{state-slug}/{event_id}.png", () => {
    const plan = buildCardPlan({
      row: row({}),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.output_rel_path).toBe("share/maharashtra/assembly-2024.png");
  });

  it("resolves a national-scope row to share/national/{event_id}.png", () => {
    const plan = buildCardPlan({
      row: row({
        event_id: "general-2024",
        state_code: null,
        scope: "national",
        kind: "parliament",
        seats_contested: 543,
        seats_won: 240,
      }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.output_rel_path).toBe("share/national/general-2024.png");
    expect(plan?.card.scope_label).toBe("India");
  });

  it("populates winner_label + colour from the party lookup", () => {
    const plan = buildCardPlan({
      row: row({}),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.card.winner_label).toBe("BJP");
    expect(plan?.card.winner_colour_hex).toBe("#FF9933");
  });

  it("falls back to no-winner when leading_party_id is null", () => {
    const plan = buildCardPlan({
      row: row({ leading_party_id: null }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.card.winner_label).toBeNull();
    expect(plan?.card.winner_colour_hex).toBeNull();
  });

  it("falls back to no-winner when leading_party_id is unknown to the registry", () => {
    const plan = buildCardPlan({
      row: row({ leading_party_id: "parties.IN.UNKNOWN" }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.card.winner_label).toBeNull();
  });

  it("returns null when a state-scope row's state_code does not resolve", () => {
    const plan = buildCardPlan({
      row: row({ state_code: "S99" }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan).toBeNull();
  });

  it("returns null when a state-scope row has no state_code (mart violation)", () => {
    const plan = buildCardPlan({
      row: row({ scope: "state", state_code: null }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan).toBeNull();
  });

  it("maps every catalogue kind to a citizen-readable body label", () => {
    const kinds: EventSummaryRowForCard["kind"][] = [
      "parliament",
      "assembly",
      "general_bye",
      "assembly_bye",
      "by_election",
    ];
    const expected = [
      "Parliament",
      "Assembly",
      "Parliament By-election",
      "Assembly By-election",
      "By-election",
    ];
    kinds.forEach((kind, idx) => {
      const plan = buildCardPlan({
        row: row({ kind }),
        parties_by_id: PARTIES,
        states_by_code: STATES,
        sources_by_id: SOURCES,
      });
      expect(plan?.card.body_label).toBe(expected[idx]);
    });
  });

  it("derives year_label from event_id when present", () => {
    const plan = buildCardPlan({
      row: row({ event_id: "assembly-2024", polled_on: "2024-11-20" }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.card.year_label).toBe("2024");
  });

  it("falls back to polled_on year when event_id has no 4-digit year", () => {
    const plan = buildCardPlan({
      row: row({ event_id: "weird-id", polled_on: "2019-04-15" }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.card.year_label).toBe("2019");
  });

  it("composes the seats summary as 'N of M'", () => {
    const plan = buildCardPlan({
      row: row({ seats_won: 230, seats_contested: 288 }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.card.seats_summary).toBe("230 of 288");
  });

  it("uses the source.producer for the citation line", () => {
    const plan = buildCardPlan({
      row: row({}),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    expect(plan?.card.source_line).toBe(
      "Source: Election Commission of India",
    );
  });

  it("falls back to a default source line when source_id is unknown", () => {
    const plan = buildCardPlan({
      row: row({ source_id: "src-missing" }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: SOURCES,
    });
    // Still emits a non-empty source line; never an empty footer.
    expect(plan?.card.source_line).toMatch(/^Source:/);
  });

  it("normalises 'yen-gov' producer to upstream ECI attribution", () => {
    // The event_summary mart's own source row attributes the producer
    // as 'yen-gov' (we wrote the mart) - but for citizen-facing cards
    // the upstream IS ECI. Honest provenance per Holy Law #9.
    const yen_gov_sources = new Map<string, SourceRowForCard>([
      ["src-mart", { source_id: "src-mart", producer: "yen-gov" }],
    ]);
    const plan = buildCardPlan({
      row: row({ source_id: "src-mart" }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: yen_gov_sources,
    });
    expect(plan?.card.source_line).toBe(
      "Source: Election Commission of India",
    );
  });

  it("honours a verbatim non-yen-gov producer attribution", () => {
    const eci_sources = new Map<string, SourceRowForCard>([
      [
        "src-other",
        {
          source_id: "src-other",
          producer: "Trivedi Centre for Political Data (TCPD)",
        },
      ],
    ]);
    const plan = buildCardPlan({
      row: row({ source_id: "src-other" }),
      parties_by_id: PARTIES,
      states_by_code: STATES,
      sources_by_id: eci_sources,
    });
    expect(plan?.card.source_line).toBe(
      "Source: Trivedi Centre for Political Data (TCPD)",
    );
  });
});
