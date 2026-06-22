// PR-E3 vitest for `lib/view-models/general-elections-model.ts`.

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  loadGeneralElections,
  loadGeneralElectionsSources,
} from "./general-elections-model";
import type { EventSummaryRow } from "../elections/event-summary-loader";
import type { SourceRow } from "../sources";
import type { PartyMeta } from "./parties";

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
    event_id: "general-2024",
    state_code: null,
    scope: "national",
    kind: "parliament",
    polled_on: "2024-06-01",
    leading_party_id: "parties.IN.BJP",
    seats_won: 240,
    seats_contested: 543,
    turnout_pct: 66.1,
    runner_up_party_id: "parties.IN.INC",
    runner_up_seats: 99,
    source_id: "src-abc",
    ...over,
  };
}

const partiesMeta = new Map<string, PartyMeta>([
  ["parties.IN.BJP", emptyMeta("parties.IN.BJP", "BJP", "#ea580c")],
  ["parties.IN.INC", emptyMeta("parties.IN.INC", "INC", "#2563eb")],
]);

describe("loadGeneralElections", () => {
  it("returns rows in descending polled_on order with turnout deltas", async () => {
    const summary: EventSummaryRow[] = [
      row({ event_id: "general-2024", polled_on: "2024-06-01", turnout_pct: 66.1 }),
      row({
        event_id: "general-2019",
        polled_on: "2019-05-19",
        turnout_pct: 67.4,
        leading_party_id: "parties.IN.BJP",
        seats_won: 303,
      }),
      row({
        event_id: "general-2014",
        polled_on: "2014-05-12",
        turnout_pct: 66.4,
        leading_party_id: "parties.IN.BJP",
        seats_won: 282,
      }),
    ];
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => summary,
      loadPartiesMetaOverride: async () => partiesMeta,
    });
    expect(out.map((r) => r.year)).toEqual([2024, 2019, 2014]);
    // 2024 vs 2019 = -1.3pp
    expect(out[0].turnout_delta_pp).toBeCloseTo(-1.3, 1);
    // 2019 vs 2014 = +1.0pp
    expect(out[1].turnout_delta_pp).toBeCloseTo(1.0, 1);
    // 2014 is earliest in the sorted-asc-then-flipped list -> null delta
    expect(out[2].turnout_delta_pp).toBeNull();
  });

  it("resolves leading + runner-up party cells from the meta map", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [row({})],
      loadPartiesMetaOverride: async () => partiesMeta,
    });
    expect(out).toHaveLength(1);
    expect(out[0].leading.party_id).toBe("parties.IN.BJP");
    expect(out[0].leading.short).toBe("BJP");
    expect(out[0].leading.detail_href).toBe("/parties/bjp");
    expect(out[0].runner_up?.party_id).toBe("parties.IN.INC");
    expect(out[0].runner_up?.short).toBe("INC");
    expect(out[0].runner_up?.seats).toBe(99);
  });

  it("ignores state-scope rows", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [
        row({ event_id: "general-2024" }),
        row({
          event_id: "assembly-2026",
          state_code: "S22",
          scope: "state",
          kind: "assembly",
          polled_on: "2026-05-08",
        }),
      ],
      loadPartiesMetaOverride: async () => partiesMeta,
    });
    expect(out).toHaveLength(1);
    expect(out[0].event_id).toBe("general-2024");
  });

  it("populates fallback short + null detail_href when party_id absent from meta", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [
        row({ leading_party_id: "parties.IN.NEWPARTY" }),
      ],
      loadPartiesMetaOverride: async () => new Map(),
    });
    expect(out[0].leading.short).toBe("NEWPARTY");
    expect(out[0].leading.detail_href).toBe("/parties/newparty");
  });

  it("handles null leading party gracefully", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [
        row({ leading_party_id: null, runner_up_party_id: null, runner_up_seats: null }),
      ],
      loadPartiesMetaOverride: async () => new Map(),
    });
    expect(out[0].leading.party_id).toBeNull();
    expect(out[0].leading.short).toBe("");
    expect(out[0].leading.detail_href).toBeNull();
    expect(out[0].runner_up).toBeNull();
  });

  it("derives majority_mark, mandate, margin and others_seats per row", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [
        row({ seats_won: 240, seats_contested: 543, runner_up_seats: 99 }),
      ],
      loadPartiesMetaOverride: async () => partiesMeta,
    });
    const r = out[0];
    expect(r.majority_mark).toBe(272); // floor(543/2)+1
    expect(r.mandate.majority).toBe(false);
    expect(r.mandate.gap).toBe(240 - 272);
    expect(r.mandate.label).toBe("Short by 32");
    expect(r.margin).toBe(141); // 240 - 99
    expect(r.others_seats).toBe(204); // 543 - 240 - 99
    expect(r.source_id).toBe("src-abc");
  });

  it("labels a single-party majority", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [
        row({ seats_won: 303, seats_contested: 543 }),
      ],
      loadPartiesMetaOverride: async () => partiesMeta,
    });
    expect(out[0].mandate.majority).toBe(true);
    expect(out[0].mandate.gap).toBe(31); // 303 - 272
    expect(out[0].mandate.label).toBe("Majority");
  });

  it("computes seat_swing as the leading-slot delta vs the prior cycle", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [
        row({ event_id: "general-2024", polled_on: "2024-06-01", seats_won: 240 }),
        row({ event_id: "general-2019", polled_on: "2019-05-19", seats_won: 303 }),
        row({ event_id: "general-2014", polled_on: "2014-05-12", seats_won: 282 }),
      ],
      loadPartiesMetaOverride: async () => partiesMeta,
    });
    expect(out.map((r) => r.year)).toEqual([2024, 2019, 2014]);
    expect(out[0].seat_swing).toBe(240 - 303); // -63
    expect(out[1].seat_swing).toBe(303 - 282); // +21
    expect(out[2].seat_swing).toBeNull(); // earliest cycle
  });

  it("clamps others_seats to zero and falls back margin when no runner-up", async () => {
    const out = await loadGeneralElections({
      loadEventSummaryOverride: async () => [
        row({
          seats_won: 300,
          seats_contested: 543,
          runner_up_party_id: null,
          runner_up_seats: null,
        }),
      ],
      loadPartiesMetaOverride: async () => new Map(),
    });
    expect(out[0].runner_up).toBeNull();
    expect(out[0].margin).toBe(300); // 300 - 0
    expect(out[0].others_seats).toBe(243); // 543 - 300 - 0
  });
});

describe("loadGeneralElectionsSources", () => {
  const sourceRows: SourceRow[] = [
    {
      source_id: "src-eci",
      producer: "Election Commission of India",
      title: "General Election Statistical Report",
      vintage: "2024",
      url: "https://eci.gov.in",
    },
    {
      source_id: "src-unused",
      producer: "Somebody Else",
      title: "Unused",
      vintage: "2020",
      url: null,
    },
  ];

  it("resolves cited source_ids into deduped publisher pills", async () => {
    const pills = await loadGeneralElectionsSources(["src-eci", "src-eci"], {
      loadSourceRowsOverride: async () => sourceRows,
    });
    expect(pills).toHaveLength(1);
    expect(pills[0].url).toBe("https://eci.gov.in");
  });

  it("returns an empty array for an empty id set", async () => {
    const pills = await loadGeneralElectionsSources([], {
      loadSourceRowsOverride: async () => sourceRows,
    });
    expect(pills).toEqual([]);
  });

  it("throws on an FK violation (cited id absent from source.csv)", async () => {
    await expect(
      loadGeneralElectionsSources(["src-missing"], {
        loadSourceRowsOverride: async () => sourceRows,
      }),
    ).rejects.toThrow(/Holy Law #9/);
  });
});
