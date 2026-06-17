/**
 * Unit tests for compare-dot-summary (PR3 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md).
 *
 * Pins the To-winner party-dot tally contract:
 *  - distinct To-winner parties, ordered by seat frequency descending;
 *  - orphans (Boundary changed / New seat) and null party ids excluded;
 *  - capped at MAX_COMPARE_DOTS with the remainder surfaced as `overflow`;
 *  - colour resolver injected (the model never imports getPartyColor).
 *
 * Pure model -> no Svelte mount, runs in the node env.
 */

import { describe, it, expect } from "vitest";
import {
  buildCompareDotSummary,
  MAX_COMPARE_DOTS,
  type CompareDotRow,
} from "./compare-dot-summary";

// Deterministic stub resolver: party_id -> "#" + the id (so assertions read
// the party identity straight off the dot). The real route injects
// `(pid) => getPartyColor(pid, null).hex`.
const stubHex = (pid: string): string => `#${pid}`;

function dotRow(to_party_id: string | null, is_orphan = false): CompareDotRow {
  return { to_party_id, is_orphan };
}

describe("buildCompareDotSummary", () => {
  it("returns empty dots + zero overflow for no rows", () => {
    const out = buildCompareDotSummary([], stubHex);
    expect(out.dots).toEqual([]);
    expect(out.overflow).toBe(0);
  });

  it("orders distinct To-winner parties by frequency descending", () => {
    const rows = [
      dotRow("dmk"),
      dotRow("dmk"),
      dotRow("dmk"),
      dotRow("admk"),
      dotRow("admk"),
      dotRow("bjp"),
    ];
    const out = buildCompareDotSummary(rows, stubHex);
    // dmk (3) > admk (2) > bjp (1).
    expect(out.dots).toEqual(["#dmk", "#admk", "#bjp"]);
    expect(out.overflow).toBe(0);
  });

  it("excludes orphan rows from the tally", () => {
    const rows = [
      dotRow("dmk"),
      dotRow("xyz", true), // orphan (New seat) - no stable To-party
      dotRow("xyz", true), // orphan (Boundary changed)
    ];
    const out = buildCompareDotSummary(rows, stubHex);
    expect(out.dots).toEqual(["#dmk"]);
    expect(out.overflow).toBe(0);
  });

  it("excludes rows with a null To-party id", () => {
    const rows = [dotRow("dmk"), dotRow(null), dotRow(null)];
    const out = buildCompareDotSummary(rows, stubHex);
    expect(out.dots).toEqual(["#dmk"]);
  });

  it("tie-breaks equal frequencies by party_id ascending (deterministic)", () => {
    const rows = [dotRow("ccc"), dotRow("aaa"), dotRow("bbb")];
    const out = buildCompareDotSummary(rows, stubHex);
    expect(out.dots).toEqual(["#aaa", "#bbb", "#ccc"]);
  });

  it("caps the dots at MAX_COMPARE_DOTS and reports the overflow", () => {
    // 8 distinct parties, each one seat -> 6 dots + overflow 2.
    const ids = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"];
    const rows = ids.map((id) => dotRow(id));
    const out = buildCompareDotSummary(rows, stubHex);
    expect(out.dots).toHaveLength(MAX_COMPARE_DOTS);
    expect(out.overflow).toBe(ids.length - MAX_COMPARE_DOTS);
  });

  it("keeps the most-frequent parties when overflowing", () => {
    // p-top wins 5 seats so it must survive the cap even though its id
    // sorts last alphabetically; the 7 single-seat parties fill the rest.
    const rows = [
      dotRow("z-top"),
      dotRow("z-top"),
      dotRow("z-top"),
      dotRow("z-top"),
      dotRow("z-top"),
      dotRow("a1"),
      dotRow("a2"),
      dotRow("a3"),
      dotRow("a4"),
      dotRow("a5"),
      dotRow("a6"),
      dotRow("a7"),
    ];
    const out = buildCompareDotSummary(rows, stubHex);
    expect(out.dots[0]).toBe("#z-top");
    expect(out.dots).toHaveLength(MAX_COMPARE_DOTS);
    // 8 distinct parties total -> 2 overflow.
    expect(out.overflow).toBe(2);
  });

  it("uses the injected resolver verbatim (no hex mutation)", () => {
    const calls: string[] = [];
    const spy = (pid: string): string => {
      calls.push(pid);
      return pid === "dmk" ? "#ABCDEF" : "#123456";
    };
    // dmk wins 2 seats vs bjp's 1, so the frequency order is unambiguous.
    const out = buildCompareDotSummary(
      [dotRow("dmk"), dotRow("dmk"), dotRow("bjp")],
      spy,
    );
    expect(out.dots).toEqual(["#ABCDEF", "#123456"]);
    expect(calls).toEqual(["dmk", "bjp"]);
  });

  it("counts two distinct parties even if they share a hex", () => {
    // Distinctness is by party_id, not colour: a colliding hex still
    // occupies two dots.
    const collide = (): string => "#888888";
    const out = buildCompareDotSummary([dotRow("p1"), dotRow("p2")], collide);
    expect(out.dots).toEqual(["#888888", "#888888"]);
    expect(out.overflow).toBe(0);
  });
});
