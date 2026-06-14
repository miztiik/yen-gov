import { describe, it, expect } from "vitest";

import type { ElectionEventRow } from "../election-events";
import type { ElectionResultRow } from "../view-models/election-results";
import { getPartyColor } from "../colors/resolver";
import {
  buildHistoryRows,
  winnerForEntity,
  type EventResultEntry,
  type HistoryRow,
} from "./constituency-history-model";

// Bastar PC fixture - the plan-doc's named oracle for PR-W4a's gate G3.
// Five general elections (2004-2024) where Bastar's seat changed hands
// across BJP / INC / IND across the cycles. The fixture is synthetic;
// the on-disk corpus for chhattisgarh today carries general-2009 ->
// general-2024 (4 rows), but the model is data-agnostic and the test
// asserts a 5-row case so we exercise the sort + the filter + the
// party-pill colour-lookup integration in one shot.
const BASTAR_ENTITY_ID = "IN-PC-2008-chhattisgarh-294";

function eventRow(
  event_id: string,
  polled_on: string,
): ElectionEventRow {
  return {
    event_id,
    kind: "parliament",
    display: event_id,
    polled_on,
  };
}

function resultRow(
  overrides: Partial<ElectionResultRow> & {
    entity_id: string;
    is_winner: boolean;
  },
): ElectionResultRow {
  const base: ElectionResultRow = {
    entity_id: overrides.entity_id,
    entity_kind: "pc",
    entity_name: "Bastar",
    state_slug: "chhattisgarh",
    state_code: "S26",
    eci_no: 9,
    delim_year: 2008,
    period_label: "general-2024",
    candidate_name: null,
    position: 1,
    votes: null,
    vote_share_pct: 47.23,
    is_winner: overrides.is_winner,
    party_id: "parties.IN.BJP",
    party_eci_code: "BJP",
    party_short: "BJP",
    party_short_raw: "BJP",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    symbol_asset_path: null,
    margin_pct: 5.7,
    turnout_pct: 68.46,
    electors: null,
    votes_polled: null,
    // TODO/20260612 Row B contract: ElectionResultRow now requires the
    // margin_votes field. The constituency-history model ignores it; we
    // pass null because the on-disk loader leaves it null on uncontested
    // seats (and the fixture is shape-only, not value-sensitive).
    margin_votes: null,
    winner_age: null,
    winner_candidate_name: null,
    reservation: "GEN",
  };
  return { ...base, ...overrides };
}

const BASTAR_HISTORY: EventResultEntry[] = [
  {
    event: eventRow("general-2024", "2024-06-01"),
    rows: [
      resultRow({
        entity_id: BASTAR_ENTITY_ID,
        is_winner: true,
        party_id: "parties.IN.BJP",
        party_short: "BJP",
        party_short_raw: "BJP",
        vote_share_pct: 47.23,
        margin_pct: 5.7,
        period_label: "general-2024",
      }),
    ],
  },
  {
    event: eventRow("general-2019", "2019-05-19"),
    rows: [
      resultRow({
        entity_id: BASTAR_ENTITY_ID,
        is_winner: true,
        party_id: "parties.IN.INC",
        party_short: "INC",
        party_short_raw: "INC",
        vote_share_pct: 44.61,
        margin_pct: 5.27,
        period_label: "general-2019",
      }),
    ],
  },
  {
    event: eventRow("general-2014", "2014-05-12"),
    rows: [
      resultRow({
        entity_id: BASTAR_ENTITY_ID,
        is_winner: true,
        party_id: "parties.IN.BJP",
        party_short: "BJP",
        party_short_raw: "BJP",
        vote_share_pct: 38.42,
        margin_pct: 12.51,
        period_label: "general-2014",
      }),
    ],
  },
  {
    event: eventRow("general-2009", "2009-05-13"),
    rows: [
      resultRow({
        entity_id: BASTAR_ENTITY_ID,
        is_winner: true,
        party_id: "parties.IN.BJP",
        party_short: "BJP",
        party_short_raw: "BJP",
        vote_share_pct: 41.20,
        margin_pct: 15.29,
        period_label: "general-2009",
      }),
    ],
  },
  {
    event: eventRow("general-2004", "2004-05-10"),
    rows: [
      // Old delim - different entity_id. The model MUST skip this row,
      // proving that the entity_id filter binds.
      resultRow({
        entity_id: "IN-PC-1976-S26-1",
        is_winner: true,
        party_id: "parties.IN.IND",
        party_short: "IND",
        party_short_raw: "IND",
        vote_share_pct: 33.7,
        margin_pct: 4.1,
        period_label: "general-2004",
      }),
    ],
  },
];

describe("winnerForEntity", () => {
  it("returns the winner row when the entity_id matches and is_winner=true", () => {
    const rows = [
      resultRow({
        entity_id: BASTAR_ENTITY_ID,
        is_winner: true,
        party_short: "BJP",
      }),
    ];
    expect(winnerForEntity(rows, BASTAR_ENTITY_ID)?.party_short).toBe("BJP");
  });

  it("returns null when no row matches the entity_id", () => {
    const rows = [
      resultRow({ entity_id: "IN-PC-2008-bihar-1", is_winner: true }),
    ];
    expect(winnerForEntity(rows, BASTAR_ENTITY_ID)).toBeNull();
  });

  it("ignores non-winner rows even if the entity_id matches", () => {
    const rows = [
      resultRow({ entity_id: BASTAR_ENTITY_ID, is_winner: false, position: 2 }),
    ];
    expect(winnerForEntity(rows, BASTAR_ENTITY_ID)).toBeNull();
  });

  it("returns the FIRST is_winner=true match (stable for winner-only scopes)", () => {
    const rows = [
      resultRow({
        entity_id: BASTAR_ENTITY_ID,
        is_winner: true,
        party_short: "BJP",
      }),
      // Pathological second winner row - the model takes the first
      // (real loaders never emit two winners per entity).
      resultRow({
        entity_id: BASTAR_ENTITY_ID,
        is_winner: true,
        party_short: "INC",
      }),
    ];
    expect(winnerForEntity(rows, BASTAR_ENTITY_ID)?.party_short).toBe("BJP");
  });
});

describe("buildHistoryRows", () => {
  it("the PR-W4a oracle: 5 entries -> 4 rows (one skipped on entity_id), sorted oldest-first", () => {
    const rows = buildHistoryRows(BASTAR_HISTORY, BASTAR_ENTITY_ID);
    expect(rows).toHaveLength(4);
    expect(rows.map((r) => r.event_id)).toEqual([
      "general-2009",
      "general-2014",
      "general-2019",
      "general-2024",
    ]);
    expect(rows.map((r) => r.year)).toEqual([2009, 2014, 2019, 2024]);
    expect(rows.map((r) => r.winner_party_id)).toEqual([
      "parties.IN.BJP",
      "parties.IN.BJP",
      "parties.IN.INC",
      "parties.IN.BJP",
    ]);
  });

  it("the citizen-readable winner_party_short follows the v1.1 fallback chain", () => {
    const long_tail_winner: EventResultEntry = {
      event: eventRow("general-2024", "2024-06-01"),
      rows: [
        resultRow({
          entity_id: BASTAR_ENTITY_ID,
          is_winner: true,
          // Long-tail party - not yet keyed in parties.json, so the
          // joined party_id is the UNK sentinel but the upstream
          // party_short_raw carries the citizen-visible label.
          party_id: "parties.IN.UNK",
          party_short: "UNK",
          party_short_raw: "RBSP",
        }),
      ],
    };
    const rows = buildHistoryRows([long_tail_winner], BASTAR_ENTITY_ID);
    expect(rows[0].winner_party_short).toBe("RBSP");
  });

  it("synthesises winner_party_id=parties.IN.UNK when the loader returned a null party_id", () => {
    const null_party: EventResultEntry = {
      event: eventRow("general-2024", "2024-06-01"),
      rows: [
        resultRow({
          entity_id: BASTAR_ENTITY_ID,
          is_winner: true,
          party_id: null,
          party_short_raw: "—",
        }),
      ],
    };
    const rows = buildHistoryRows([null_party], BASTAR_ENTITY_ID);
    expect(rows[0].winner_party_id).toBe("parties.IN.UNK");
  });

  it("skips events whose loader returned an empty rows[] (event not on disk)", () => {
    const empty: EventResultEntry = {
      event: eventRow("general-2024", "2024-06-01"),
      rows: [],
    };
    expect(buildHistoryRows([empty], BASTAR_ENTITY_ID)).toEqual([]);
  });

  it("skips events whose winner row has null vote_share_pct or null margin_pct", () => {
    const broken: EventResultEntry = {
      event: eventRow("general-2024", "2024-06-01"),
      rows: [
        resultRow({
          entity_id: BASTAR_ENTITY_ID,
          is_winner: true,
          vote_share_pct: null,
          margin_pct: 5.7,
        }),
      ],
    };
    expect(buildHistoryRows([broken], BASTAR_ENTITY_ID)).toEqual([]);
  });

  it("emits the empty array when the entity has no winning rows across any event", () => {
    const stranger = "IN-PC-2008-bihar-1";
    expect(buildHistoryRows(BASTAR_HISTORY, stranger)).toEqual([]);
  });
});

describe("party colour integration", () => {
  // The PR-W4a brief asks the test to "assert correct party-pill
  // colours via getPartyColor". The Svelte template calls
  // `getPartyColor(row.winner_party_id)` per row; here we verify the
  // model's winner_party_id values feed the resolver to STABLE hex
  // colours per the colour-system tiers
  // (yen-gov-architecture.md "Colour system" - anchor / brand /
  // algorithmic). The assertion is on the resolver source labels +
  // hex stability, not the bytes themselves (anchor hexes are a
  // user-facing artifact and may be retuned).

  it("BJP + INC resolve via the anchor tier (citizen-recall colours)", () => {
    const rows = buildHistoryRows(BASTAR_HISTORY, BASTAR_ENTITY_ID);
    const bjp = rows.find((r) => r.winner_party_id === "parties.IN.BJP");
    const inc = rows.find((r) => r.winner_party_id === "parties.IN.INC");
    expect(bjp).toBeDefined();
    expect(inc).toBeDefined();
    expect(getPartyColor(bjp!.winner_party_id).source).toBe("anchor");
    expect(getPartyColor(inc!.winner_party_id).source).toBe("anchor");
    expect(getPartyColor(bjp!.winner_party_id).hex).not.toBe(
      getPartyColor(inc!.winner_party_id).hex,
    );
  });

  it("repeated parties resolve to the same hex (palette stability across history rows)", () => {
    const rows: HistoryRow[] = buildHistoryRows(BASTAR_HISTORY, BASTAR_ENTITY_ID);
    const bjps = rows.filter((r) => r.winner_party_id === "parties.IN.BJP");
    expect(bjps.length).toBeGreaterThanOrEqual(2);
    const hexes = bjps.map((r) => getPartyColor(r.winner_party_id).hex);
    expect(new Set(hexes).size).toBe(1);
  });
});
