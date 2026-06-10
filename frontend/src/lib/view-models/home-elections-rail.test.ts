// home-elections-rail.test.ts (PR-W4d, 2026-06-10)
//
// Pure-model tests for buildHomeElectionsRail + its component pickers.
// Mocks `../election-events` (catalogue fetcher) and `./election-results`
// (national-PC loader) per CLAUDE.md section 15 explicit carve-out for
// fetch-driven loaders.

import { describe, expect, it, vi, beforeEach } from "vitest";

import type { ElectionEventsCatalogue, ElectionEventRow } from "../election-events";
import type { ElectionResultRow } from "./election-results";
import type { LoaderResult } from "../loader-result";

// Hoisted mocks. We swap implementations per-test via mockImplementation
// rather than re-mocking the module, so the SUT module sees a stable
// stub set across the whole file.
const mockFetchElectionEvents = vi.hoisted(() => vi.fn());
const mockLoadElectionResults = vi.hoisted(() => vi.fn());

vi.mock("../election-events", () => ({
  fetchElectionEvents: mockFetchElectionEvents,
}));
vi.mock("./election-results", () => ({
  loadElectionResults: mockLoadElectionResults,
}));

import {
  buildHomeElectionsRail,
  buildHomeElectionsRailFast,
  composeRail,
  pickAnchorEvent,
  pickClosestRace,
  refineHookCard,
} from "./home-elections-rail";

// ---------------- fixtures ----------------

function makeEvent(overrides: Partial<ElectionEventRow>): ElectionEventRow {
  return {
    event_id: overrides.event_id ?? "general-2024",
    kind: overrides.kind ?? "parliament",
    display: overrides.display ?? "Display",
    polled_on: overrides.polled_on ?? "2024-06-01",
    data_status: overrides.data_status,
    term_end_estimated: overrides.term_end_estimated ?? null,
    event_id_aliases: overrides.event_id_aliases,
    notes: overrides.notes,
  };
}

function makeCatalogue(
  per_state: Record<string, ElectionEventRow[]>,
): ElectionEventsCatalogue {
  return {
    $schema: "x",
    $schema_version: "1.3",
    sources: [],
    states: per_state,
  };
}

function makeRow(overrides: Partial<ElectionResultRow>): ElectionResultRow {
  return {
    entity_id: overrides.entity_id ?? "IN-PC-2008-maharashtra-388",
    entity_kind: "pc",
    entity_name: overrides.entity_name ?? "Mumbai South-Central",
    state_slug: overrides.state_slug ?? "maharashtra",
    state_code: overrides.state_code ?? "S13",
    eci_no: overrides.eci_no ?? 30,
    delim_year: 2008,
    period_label: "general-2024",
    candidate_name: null,
    position: 1,
    votes: null,
    vote_share_pct: null,
    is_winner: overrides.is_winner ?? true,
    party_id: null,
    party_eci_code: null,
    party_short: null,
    party_short_raw: null,
    brand_colour_hex: null,
    brand_colour_confidence: null,
    symbol_asset_path: null,
    margin_pct: overrides.margin_pct ?? null,
    turnout_pct: null,
    electors: null,
    votes_polled: null,
    winner_age: null,
    winner_candidate_name: null,
    reservation: "GEN",
  };
}

beforeEach(() => {
  mockFetchElectionEvents.mockReset();
  mockLoadElectionResults.mockReset();
});

// ---------------- pickAnchorEvent ----------------

describe("pickAnchorEvent", () => {
  it("returns the most-recent complete parliament event across states", () => {
    const cat = makeCatalogue({
      S01: [
        makeEvent({ event_id: "general-2019", polled_on: "2019-05-19", data_status: "complete" }),
        makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" }),
      ],
      S13: [
        makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" }),
        makeEvent({ event_id: "general-2014", polled_on: "2014-05-12", data_status: "complete" }),
      ],
    });
    const e = pickAnchorEvent(cat);
    expect(e?.event_id).toBe("general-2024");
  });

  it("skips assembly events even when newer than every parliament event", () => {
    const cat = makeCatalogue({
      S01: [
        makeEvent({ event_id: "assembly-2026", kind: "assembly", polled_on: "2026-05-10", data_status: "complete" }),
        makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" }),
      ],
    });
    const e = pickAnchorEvent(cat);
    expect(e?.event_id).toBe("general-2024");
  });

  it("skips parliament events with non-complete data_status", () => {
    const cat = makeCatalogue({
      S01: [
        makeEvent({ event_id: "general-2029", polled_on: "2029-05-01", data_status: "pending_upstream" }),
        makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" }),
      ],
    });
    const e = pickAnchorEvent(cat);
    expect(e?.event_id).toBe("general-2024");
  });

  it("returns null when no eligible parliament event exists", () => {
    const cat = makeCatalogue({
      S01: [
        makeEvent({ event_id: "assembly-2023", kind: "assembly", polled_on: "2023-05-10", data_status: "complete" }),
      ],
    });
    expect(pickAnchorEvent(cat)).toBeNull();
  });

  it("de-dupes the same event_id across multiple state slices", () => {
    const cat = makeCatalogue({
      S01: [makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" })],
      S13: [makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" })],
    });
    const e = pickAnchorEvent(cat);
    expect(e?.event_id).toBe("general-2024");
  });
});

// ---------------- pickClosestRace ----------------

describe("pickClosestRace", () => {
  it("returns the winner row with the smallest margin_pct", () => {
    const rows = [
      makeRow({ entity_id: "A", margin_pct: 12.5 }),
      makeRow({ entity_id: "B", margin_pct: 0.34 }),
      makeRow({ entity_id: "C", margin_pct: 8.1 }),
    ];
    expect(pickClosestRace(rows)?.entity_id).toBe("B");
  });

  it("ignores rows with null margin_pct", () => {
    const rows = [
      makeRow({ entity_id: "A", margin_pct: null }),
      makeRow({ entity_id: "B", margin_pct: 5.0 }),
    ];
    expect(pickClosestRace(rows)?.entity_id).toBe("B");
  });

  it("ignores non-winner rows even when their margin is smaller", () => {
    const rows = [
      makeRow({ entity_id: "A", margin_pct: 0.1, is_winner: false }),
      makeRow({ entity_id: "B", margin_pct: 7.0, is_winner: true }),
    ];
    expect(pickClosestRace(rows)?.entity_id).toBe("B");
  });

  it("returns null when no row has a numeric margin", () => {
    expect(pickClosestRace([])).toBeNull();
    expect(pickClosestRace([makeRow({ margin_pct: null })])).toBeNull();
  });
});

// ---------------- composeRail ----------------

describe("composeRail", () => {
  const anchor = makeEvent({
    event_id: "general-2024",
    polled_on: "2024-06-01",
    data_status: "complete",
  });
  const catalogue = makeCatalogue({ S13: [anchor] });

  it("anchor card titles Parliament <year> + routes to /t/elections/<event>", () => {
    const payload = composeRail(catalogue, anchor, []);
    expect(payload.anchor.title).toBe("Parliament 2024");
    expect(payload.anchor.subtitle).toBe("National results");
    expect(payload.anchor.href).toBe("/t/elections/general-2024");
  });

  it("hook card uses the closest race + routes to /<state>/elections/<event>", () => {
    const rows = [
      makeRow({
        entity_id: "IN-PC-2008-maharashtra-388",
        entity_name: "Mumbai South-Central",
        state_slug: "maharashtra",
        margin_pct: 0.45,
      }),
      makeRow({ entity_id: "B", state_slug: "karnataka", margin_pct: 12.5 }),
    ];
    const payload = composeRail(catalogue, anchor, rows);
    expect(payload.hook.title).toBe("2024's closest seat");
    expect(payload.hook.subtitle).toContain("Mumbai South-Central");
    expect(payload.hook.subtitle).toContain("0.45%");
    expect(payload.hook.href).toBe("/maharashtra/elections/general-2024");
  });

  it("hook card degrades to event link when no rows carry a margin", () => {
    const payload = composeRail(catalogue, anchor, []);
    expect(payload.hook.title).toBe("Parliament 2024");
    expect(payload.hook.subtitle).toBe("Latest event highlights");
    expect(payload.hook.href).toBe("/t/elections/general-2024");
  });

  it("hook subtitle floors sub-0.01% margins to '< 0.01%' so they don't look broken", () => {
    const rows = [
      makeRow({
        entity_name: "Mumbai North-West",
        state_slug: "maharashtra",
        margin_pct: 0.0093, // real 2024 PC margin: 48 votes / ~518k
      }),
    ];
    const payload = composeRail(catalogue, anchor, rows);
    expect(payload.hook.subtitle).toBe("Mumbai North-West - margin < 0.01%");
  });

  it("door card is a static link to /t/elections", () => {
    const payload = composeRail(catalogue, anchor, []);
    expect(payload.door.title).toBe("All elections");
    expect(payload.door.href).toBe("/t/elections");
  });
});

// ---------------- buildHomeElectionsRail ----------------

describe("buildHomeElectionsRail", () => {
  it("end-to-end: composes the 3-card payload from catalogue + loader", async () => {
    mockFetchElectionEvents.mockResolvedValue(
      makeCatalogue({
        S13: [makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" })],
      }),
    );
    const okResult: LoaderResult<ElectionResultRow[]> = {
      status: "ok",
      data: [
        makeRow({
          entity_name: "Mumbai South-Central",
          state_slug: "maharashtra",
          margin_pct: 0.45,
        }),
      ],
    };
    mockLoadElectionResults.mockResolvedValue(okResult);

    const payload = await buildHomeElectionsRail();
    expect(payload.anchor.href).toBe("/t/elections/general-2024");
    expect(payload.hook.subtitle).toContain("Mumbai South-Central");
    expect(payload.door.href).toBe("/t/elections");
  });

  it("degrades hook when loader returns failed status", async () => {
    mockFetchElectionEvents.mockResolvedValue(
      makeCatalogue({
        S13: [makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" })],
      }),
    );
    const failedResult: LoaderResult<ElectionResultRow[]> = {
      status: "failed",
      reason: "data_unavailable",
      retry: () => Promise.resolve(failedResult),
    };
    mockLoadElectionResults.mockResolvedValue(failedResult);

    const payload = await buildHomeElectionsRail();
    expect(payload.hook.subtitle).toBe("Latest event highlights");
  });

  it("throws when no eligible parliament event exists", async () => {
    mockFetchElectionEvents.mockResolvedValue(
      makeCatalogue({
        S13: [
          makeEvent({ event_id: "assembly-2023", kind: "assembly", polled_on: "2023-05-10", data_status: "complete" }),
        ],
      }),
    );
    await expect(buildHomeElectionsRail()).rejects.toThrow(
      /no parliament event with data_status='complete'/,
    );
  });
});

// ---------------- buildHomeElectionsRailFast ----------------

describe("buildHomeElectionsRailFast", () => {
  it("returns a degraded-hook payload without calling the loader", async () => {
    mockFetchElectionEvents.mockResolvedValue(
      makeCatalogue({
        S13: [makeEvent({ event_id: "general-2024", polled_on: "2024-06-01", data_status: "complete" })],
      }),
    );
    const payload = await buildHomeElectionsRailFast();
    expect(payload.anchor.href).toBe("/t/elections/general-2024");
    expect(payload.hook.subtitle).toBe("Latest event highlights");
    expect(payload.door.href).toBe("/t/elections");
    // Fast path MUST NOT touch the slow loader.
    expect(mockLoadElectionResults).not.toHaveBeenCalled();
  });

  it("throws on the same catalogue shapes as the full builder", async () => {
    mockFetchElectionEvents.mockResolvedValue(makeCatalogue({}));
    await expect(buildHomeElectionsRailFast()).rejects.toThrow(
      /no parliament event with data_status='complete'/,
    );
  });
});

// ---------------- refineHookCard ----------------

describe("refineHookCard", () => {
  const fast = composeRail(
    makeCatalogue({}),
    makeEvent({ event_id: "general-2024", polled_on: "2024-06-01" }),
    [],
  );

  it("upgrades the hook when the loader returns a margin-carrying row", async () => {
    const okResult: LoaderResult<ElectionResultRow[]> = {
      status: "ok",
      data: [
        makeRow({
          entity_name: "Mumbai South-Central",
          state_slug: "maharashtra",
          margin_pct: 0.45,
        }),
      ],
    };
    mockLoadElectionResults.mockResolvedValue(okResult);
    const refined = await refineHookCard(fast, "general-2024");
    expect(refined.hook.title).toBe("2024's closest seat");
    expect(refined.hook.subtitle).toContain("Mumbai South-Central");
    expect(refined.hook.href).toBe("/maharashtra/elections/general-2024");
    // Anchor + door cards are untouched by the refine pass.
    expect(refined.anchor).toEqual(fast.anchor);
    expect(refined.door).toEqual(fast.door);
  });

  it("returns the input payload unchanged when the loader fails", async () => {
    const failedResult: LoaderResult<ElectionResultRow[]> = {
      status: "failed",
      reason: "data_unavailable",
      retry: () => Promise.resolve(failedResult),
    };
    mockLoadElectionResults.mockResolvedValue(failedResult);
    const refined = await refineHookCard(fast, "general-2024");
    expect(refined).toEqual(fast);
  });

  it("returns the input payload unchanged when no row carries a margin", async () => {
    mockLoadElectionResults.mockResolvedValue({ status: "ok", data: [] });
    const refined = await refineHookCard(fast, "general-2024");
    expect(refined).toEqual(fast);
  });

  it("swallows loader exceptions silently", async () => {
    mockLoadElectionResults.mockRejectedValue(new Error("boom"));
    const refined = await refineHookCard(fast, "general-2024");
    expect(refined).toEqual(fast);
  });
});
