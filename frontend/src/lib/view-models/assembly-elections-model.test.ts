// PR-E3 vitest for `lib/view-models/assembly-elections-model.ts`.

import { describe, expect, it } from "vitest";

import {
  NO_ASSEMBLY_UT_SLUGS,
  loadAssemblyElections,
} from "./assembly-elections-model";
import type { EventSummaryRow } from "../elections/event-summary-loader";
import type { PartyMeta } from "./parties";
import type { StateEntry } from "../data";

function emptyMeta(id: string, short: string, hex: string | null): PartyMeta {
  return {
    party_id: id,
    short,
    full: short,
    founded_year: null,
    dissolved_year: null,
    recognition_scope: null,
    home_state_codes: [],
    symbol_asset: null,
    brand_colour: hex,
    wikipedia: null,
    name_native_script: null,
    is_sentinel: false,
    aliases: [],
    predecessor_party_ids: [],
    successor_party_ids: [],
    leader: null,
  };
}

function row(over: Partial<EventSummaryRow>): EventSummaryRow {
  return {
    event_id: "assembly-2026",
    state_code: "S22",
    scope: "state",
    kind: "assembly",
    polled_on: "2026-05-08",
    leading_party_id: "parties.IN.DMK",
    seats_won: 159,
    seats_contested: 234,
    turnout_pct: 71.0,
    runner_up_party_id: "parties.IN.AIADMK",
    runner_up_seats: 66,
    source_id: "src-abc",
    ...over,
  };
}

const partiesMeta = new Map<string, PartyMeta>([
  ["parties.IN.DMK", emptyMeta("parties.IN.DMK", "DMK", "#ef4444")],
  ["parties.IN.AIADMK", emptyMeta("parties.IN.AIADMK", "AIADMK", "#22c55e")],
  ["parties.IN.JDU", emptyMeta("parties.IN.JDU", "JDU", null)],
]);

const stateCatalogue: StateEntry[] = [
  { eci_code: "S04", iso_3166_2: "IN-BR", name: "Bihar", kind: "state" },
  { eci_code: "S22", iso_3166_2: "IN-TN", name: "Tamil Nadu", kind: "state" },
  // No-leg UT: catalogue carries the entry but the loader skips with-leg projection.
  {
    eci_code: "U02",
    iso_3166_2: "IN-CH",
    name: "Chandigarh",
    kind: "union_territory",
  },
];

describe("loadAssemblyElections", () => {
  it("emits latest-event card per state from the catalogue order", async () => {
    const summary: EventSummaryRow[] = [
      // TN: two events, latest is 2026
      row({ event_id: "assembly-2021", polled_on: "2021-05-08", leading_party_id: "parties.IN.AIADMK", seats_won: 75 }),
      row({ event_id: "assembly-2026", polled_on: "2026-05-08" }),
      // Bihar: one event
      row({
        event_id: "assembly-2020",
        state_code: "S04",
        polled_on: "2020-11-10",
        leading_party_id: "parties.IN.JDU",
        seats_won: 43,
        seats_contested: 243,
        runner_up_party_id: null,
        runner_up_seats: null,
      }),
    ];
    const out = await loadAssemblyElections({
      loadEventSummaryOverride: async () => summary,
      loadPartiesMetaOverride: async () => partiesMeta,
      fetchStatesOverride: async () => ({ states: stateCatalogue }),
    });

    const stateCards = out.filter((c) => c.has_legislature);
    const noLegCards = out.filter((c) => !c.has_legislature);

    // Catalogue order: Bihar then Tamil Nadu (S04 / S22). Chandigarh skipped here
    // because it's in the no-leg set + appears in the no-leg block instead.
    expect(stateCards.map((c) => c.state_slug)).toEqual(["bihar", "tamil-nadu"]);

    // Bihar card: 1 event, latest is 2020 JDU
    const bihar = stateCards[0];
    expect(bihar.total_events_on_record).toBe(1);
    expect(bihar.latest_event?.event_id).toBe("assembly-2020");
    expect(bihar.latest_event?.leading_short).toBe("JDU");
    expect(bihar.latest_event?.detail_href).toBe("/bihar/elections/assembly-2020");

    // Tamil Nadu card: 2 events, latest is 2026 DMK
    const tn = stateCards[1];
    expect(tn.total_events_on_record).toBe(2);
    expect(tn.latest_event?.event_id).toBe("assembly-2026");
    expect(tn.latest_event?.year).toBe(2026);
    expect(tn.latest_event?.leading_party_id).toBe("parties.IN.DMK");
    expect(tn.latest_event?.leading_party_href).toBe("/parties/dmk");
    expect(tn.latest_event?.detail_href).toBe("/tamil-nadu/elections/assembly-2026");

    // No-leg cards = exactly 5 (the set), regardless of catalogue
    expect(noLegCards).toHaveLength(NO_ASSEMBLY_UT_SLUGS.size);
    for (const c of noLegCards) {
      expect(c.latest_event).toBeNull();
      expect(c.total_events_on_record).toBe(0);
      expect(NO_ASSEMBLY_UT_SLUGS.has(c.state_slug)).toBe(true);
    }
  });

  it("renders an empty card for a state in the catalogue with no mart rows", async () => {
    const out = await loadAssemblyElections({
      loadEventSummaryOverride: async () => [],
      loadPartiesMetaOverride: async () => partiesMeta,
      fetchStatesOverride: async () => ({ states: stateCatalogue }),
    });
    const tn = out.find((c) => c.state_slug === "tamil-nadu");
    expect(tn).toBeDefined();
    expect(tn?.has_legislature).toBe(true);
    expect(tn?.latest_event).toBeNull();
    expect(tn?.total_events_on_record).toBe(0);
  });

  it("uses the catalogue display name for no-leg cards when present", async () => {
    const out = await loadAssemblyElections({
      loadEventSummaryOverride: async () => [],
      loadPartiesMetaOverride: async () => partiesMeta,
      fetchStatesOverride: async () => ({ states: stateCatalogue }),
    });
    const chandigarh = out.find((c) => c.state_slug === "chandigarh");
    expect(chandigarh?.state_name).toBe("Chandigarh");
    expect(chandigarh?.state_code).toBe("U02");
    expect(chandigarh?.has_legislature).toBe(false);
  });

  it("falls back to title-cased slug for no-leg cards absent from catalogue", async () => {
    const out = await loadAssemblyElections({
      loadEventSummaryOverride: async () => [],
      loadPartiesMetaOverride: async () => partiesMeta,
      fetchStatesOverride: async () => ({ states: [] }),
    });
    const lakshadweep = out.find((c) => c.state_slug === "lakshadweep");
    expect(lakshadweep?.state_name).toBe("Lakshadweep");
    const dnh = out.find(
      (c) => c.state_slug === "dadra-and-nagar-haveli-and-daman-and-diu",
    );
    expect(dnh?.state_name).toBe("Dadra and Nagar Haveli and Daman and Diu");
  });

  it("falls back to short=tail when leading_party_id absent from meta", async () => {
    const out = await loadAssemblyElections({
      loadEventSummaryOverride: async () => [
        row({ leading_party_id: "parties.IN.NEWPARTY" }),
      ],
      loadPartiesMetaOverride: async () => new Map(),
      fetchStatesOverride: async () => ({ states: stateCatalogue }),
    });
    const tn = out.find((c) => c.state_slug === "tamil-nadu");
    expect(tn?.latest_event?.leading_short).toBe("NEWPARTY");
  });
});
