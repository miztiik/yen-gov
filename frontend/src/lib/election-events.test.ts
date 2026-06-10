import { describe, it, expect } from "vitest";
import {
  defaultEventForState,
  listEventsForState,
  findEvent,
  daysSincePolled,
  type ElectionEventsCatalogue,
} from "./election-events";

const CATALOGUE: ElectionEventsCatalogue = {
  $schema: "https://example.invalid/schemas/election-events.schema.json",
  $schema_version: "1.1",
  sources: [{ url: "https://example.invalid/source", fetched_at: "2026-05-01T00:00:00Z" }],
  states: {
    // Multi-event — max(polled_on) selects the latest.
    S22: [
      { event_id: "AcGenMay2026", kind: "assembly", display: "TN AC May 2026", polled_on: "2026-05-06" },
      { event_id: "AcGenApr2021", kind: "assembly", display: "TN AC Apr 2021", polled_on: "2021-04-06" },
    ],
    // Single event — degenerate case.
    S25: [
      { event_id: "AcGenMar2021", kind: "assembly", display: "WB AC Mar 2021", polled_on: "2021-03-27" },
    ],
    // The Meghalaya/Tripura bug shape: multi-event in oldest-first array order
    // (how the AE-panel backfills landed). The original (`rows[0]`) selector
    // returned 1978 (a 45-year regression); the current `max(polled_on)`
    // selector returns 2023. v1.1 of the schema removed the `default` field
    // entirely so the array order is the only thing left to mis-rely on —
    // this test guards against any future re-introduction of order-coupling.
    S15: [
      { event_id: "AcGenFeb1978", kind: "assembly", display: "ML AC Feb 1978", polled_on: "1978-02-25" },
      { event_id: "AcGenFeb2023", kind: "assembly", display: "ML AC Feb 2023", polled_on: "2023-02-27" },
    ],
    // Historical case: pre-v1.1 some on-disk rows carried a hand-authored
    // `default: true` flag pointed at an older event (stale-flag drift).
    // The flag is now gone from the type system and the on-disk schema;
    // this regression case is preserved with the flag REMOVED so the
    // "max(polled_on) wins regardless of array order" invariant remains
    // explicitly tested for the Himachal-Pradesh-style ordering.
    S08: [
      { event_id: "AcGenNov2017", kind: "assembly", display: "HP AC Nov 2017", polled_on: "2017-11-09" },
      { event_id: "AcGenNov2022", kind: "assembly", display: "HP AC Nov 2022", polled_on: "2022-11-12" },
    ],
    S04: [], // empty array — explicit "no data" signal
    // PR #525 shape: the Parliament LsGenJun2024 event (2024-06-01) is the
    // most-recent event by polled_on, but it sits ABOVE the latest assembly
    // election (AcGenMay2023). Every consumer of defaultEventForState is an
    // assembly-house view, so the default must stay on the latest assembly —
    // otherwise the assembly query finds no IN-<state>-LsGenJun2024-PARTY-*
    // rows and the state hub falls into its "not yet ingested" arm.
    S10: [
      { event_id: "AcGenMay2018", kind: "assembly", display: "KA AC May 2018", polled_on: "2018-05-12" },
      { event_id: "AcGenMay2023", kind: "assembly", display: "KA AC May 2023", polled_on: "2023-05-10" },
      { event_id: "LsGenJun2024", kind: "parliament", display: "Parliament Jun 2024", polled_on: "2024-06-01" },
    ],
    // Degenerate fallback: a state with ONLY a parliament event must still
    // resolve (most-recent-of-any-kind) rather than 404.
    U99: [
      { event_id: "LsGenJun2024", kind: "parliament", display: "Parliament Jun 2024", polled_on: "2024-06-01" },
    ],
    // PR-W2a (2026-06-10): bye-event fixture. The new `assembly_bye` kind
    // (added to EventKind in the same PR) exercises the bye-slug grammar
    // locked in PR-0 (`assembly-bye-<YYYY>-<seat-slug>`). The on-disk
    // catalogue ships one real-world bye fixture under S29 Karnataka
    // (Channapatna 2024); this inline fixture uses S29 too to mirror the
    // production shape. event_id_aliases is empty for new rows -- the
    // strangler array only carries prior cohort codes for renamed rows.
    S29: [
      {
        event_id: "assembly-bye-2024-channapatna",
        event_id_aliases: [],
        kind: "assembly_bye",
        display: "Karnataka Assembly - Channapatna by-election - November 2024",
        polled_on: "2024-11-13",
        data_status: "pending_upstream",
      },
      {
        event_id: "assembly-2023",
        event_id_aliases: ["AcGenMay2023"],
        kind: "assembly",
        display: "Karnataka Assembly - May 2023",
        polled_on: "2023-05-10",
      },
    ],
  },
};

describe("defaultEventForState", () => {
  it("returns the event with the most recent polled_on", () => {
    expect(defaultEventForState(CATALOGUE, "S22")?.event_id).toBe("AcGenMay2026");
  });

  it("returns the only row when the state has a single event", () => {
    expect(defaultEventForState(CATALOGUE, "S25")?.event_id).toBe("AcGenMar2021");
  });

  it("regression: returns max(polled_on) when the array is oldest-first (Meghalaya/Tripura bug)", () => {
    expect(defaultEventForState(CATALOGUE, "S15")?.event_id).toBe("AcGenFeb2023");
  });

  it("regression: returns max(polled_on) regardless of array order (Himachal Pradesh shape)", () => {
    expect(defaultEventForState(CATALOGUE, "S08")?.event_id).toBe("AcGenNov2022");
  });

  it("returns null for unknown state, empty state, or null inputs", () => {
    expect(defaultEventForState(CATALOGUE, "S99")).toBeNull();
    expect(defaultEventForState(CATALOGUE, "S04")).toBeNull();
    expect(defaultEventForState(null, "S22")).toBeNull();
    expect(defaultEventForState(CATALOGUE, null)).toBeNull();
  });

  it("PR #525: skips a newer parliament event and defaults to the latest assembly", () => {
    // LsGenJun2024 (2024-06-01) is the most-recent event by polled_on, but
    // the assembly-house default must stay on AcGenMay2023.
    expect(defaultEventForState(CATALOGUE, "S10")?.event_id).toBe("AcGenMay2023");
  });

  it("falls back to most-recent-of-any-kind when no assembly event exists", () => {
    expect(defaultEventForState(CATALOGUE, "U99")?.event_id).toBe("LsGenJun2024");
  });
});

describe("listEventsForState", () => {
  it("returns the full per-state list", () => {
    expect(listEventsForState(CATALOGUE, "S22")).toHaveLength(2);
  });

  it("sorts events most-recent-first by polled_on regardless of on-disk order", () => {
    // S15 is oldest-first on disk (1978, 2023). After sorting, latest leads.
    const out = listEventsForState(CATALOGUE, "S15");
    expect(out.map(e => e.event_id)).toEqual(["AcGenFeb2023", "AcGenFeb1978"]);
  });

  it("does not mutate the input catalogue array", () => {
    const before = CATALOGUE.states.S15.map(e => e.event_id);
    listEventsForState(CATALOGUE, "S15");
    expect(CATALOGUE.states.S15.map(e => e.event_id)).toEqual(before);
  });

  it("returns an empty array for unknown / null inputs", () => {
    expect(listEventsForState(CATALOGUE, "S99")).toEqual([]);
    expect(listEventsForState(null, "S22")).toEqual([]);
    expect(listEventsForState(CATALOGUE, null)).toEqual([]);
  });

  it("filters by kind when the optional kind arg is supplied (2026-06-09 Compare kind-constraint)", () => {
    // S10 has 2 assembly + 1 parliament; filter must keep only the
    // matching kind and stay sorted most-recent-first.
    expect(
      listEventsForState(CATALOGUE, "S10", "assembly").map((e) => e.event_id),
    ).toEqual(["AcGenMay2023", "AcGenMay2018"]);
    expect(
      listEventsForState(CATALOGUE, "S10", "parliament").map((e) => e.event_id),
    ).toEqual(["LsGenJun2024"]);
    // by_election kind has no rows -> empty.
    expect(
      listEventsForState(CATALOGUE, "S10", "by_election"),
    ).toEqual([]);
  });
});

describe("findEvent", () => {
  it("looks up an event by id within a state", () => {
    expect(findEvent(CATALOGUE, "S22", "AcGenApr2021")?.display).toBe("TN AC Apr 2021");
  });

  it("returns null when the event id is unknown for that state", () => {
    expect(findEvent(CATALOGUE, "S22", "AcGenJan1990")).toBeNull();
  });
});

describe("daysSincePolled", () => {
  it("returns the integer day count from polled_on to now", () => {
    const row = { event_id: "x", kind: "assembly", display: "x", polled_on: "2026-05-01" } as const;
    const now = new Date("2026-05-11T12:00:00Z");
    expect(daysSincePolled(row, now)).toBe(10);
  });

  it("returns negative for future polling dates", () => {
    const row = { event_id: "x", kind: "assembly", display: "x", polled_on: "2026-12-31" } as const;
    const now = new Date("2026-05-01T00:00:00Z");
    expect(daysSincePolled(row, now)).toBeLessThan(0);
  });
});

describe("PR-W2a bye-kind fixture (G5)", () => {
  it("S29 has at least one assembly_bye event", () => {
    // G5 oracle from TODO/20260609-election-experience-overhaul-plan.md
    // PR-W2a row: the new bye kind exists in the catalogue.
    const events = listEventsForState(CATALOGUE, "S29");
    expect(events.filter((e) => e.kind === "assembly_bye").length).toBeGreaterThanOrEqual(1);
  });

  it("the bye row carries the new event-slug shape `assembly-bye-<YYYY>-<seat-slug>`", () => {
    const bye = listEventsForState(CATALOGUE, "S29").find((e) => e.kind === "assembly_bye");
    expect(bye).toBeDefined();
    expect(bye?.event_id).toMatch(/^assembly-bye-\d{4}-[a-z0-9-]+$/);
  });

  it("ElectionEventRow accepts the optional event_id_aliases[] strangler field", () => {
    // S29's assembly-2023 row carries the legacy AcGenMay2023 cohort id in
    // event_id_aliases (one-release strangler per PR-W2a). The renamed
    // event_id resolves, and the alias preserves the legacy cohort id for
    // any consumer still typed against it.
    const ev = findEvent(CATALOGUE, "S29", "assembly-2023");
    expect(ev).toBeDefined();
    expect(ev?.event_id_aliases).toContain("AcGenMay2023");
  });
});
