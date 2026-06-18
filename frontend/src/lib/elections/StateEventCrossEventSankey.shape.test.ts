/**
 * Static-source contract test for StateEventCrossEventSankey.svelte
 * (state-event polish Row 1, 2026-06-18). Jony + Citizen verdict, already
 * ratified: the seat-flow Sankey is (a) single-line per band, (b) a
 * landscape (wide + short) shape, and (c) always-on (no Hide/Show toggle).
 *
 * This reads the component source off disk (like
 * StateElection.section-order.test.ts) and freezes all three at the vitest
 * gate so a future worktree-staleness merge cannot silently revert any of
 * them. Negative-control: reintroduce the toggle, the portrait W/H, or the
 * old `+ 12` seat-count offset locally and this goes RED with a concrete
 * failure message; revert and it goes GREEN.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const SOURCE = readFileSync(
  resolve(__dirname, "StateEventCrossEventSankey.svelte"),
  "utf8",
);

describe("StateEventCrossEventSankey.svelte - Row 1 polish contract", () => {
  it("is always-on: no Hide/Show toggle remains in the source", () => {
    expect(
      SOURCE.includes("state-event-seat-flow-toggle"),
      "StateEventCrossEventSankey.svelte still contains the " +
        "`state-event-seat-flow-toggle` testid. The seat-flow diagram is " +
        "always-on per the Row 1 Jony + Citizen verdict (2026-06-18); the " +
        "Hide/Show pill is deleted. If you are restoring it, the verdict " +
        "has changed - update the Row 1 plan + this test.",
    ).toBe(false);
    expect(
      SOURCE.includes("Hide seat flow"),
      "StateEventCrossEventSankey.svelte still contains the `Hide seat " +
        "flow` copy from the deleted toggle pill. Remove it (diagram is " +
        "always-on).",
    ).toBe(false);
    expect(
      SOURCE.includes("Show seat flow"),
      "StateEventCrossEventSankey.svelte still contains the `Show seat " +
        "flow` copy from the deleted toggle pill. Remove it (diagram is " +
        "always-on).",
    ).toBe(false);
  });

  it("uses a landscape chart shape (W / H >= 2.2)", () => {
    const wMatch = SOURCE.match(/const\s+W\s*=\s*(\d+)/);
    const hMatch = SOURCE.match(/const\s+H\s*=\s*(\d+)/);
    expect(
      wMatch,
      "Could not parse `const W = <number>` from " +
        "StateEventCrossEventSankey.svelte - the layout-constant shape " +
        "changed; update this test.",
    ).not.toBeNull();
    expect(
      hMatch,
      "Could not parse `const H = <number>` from " +
        "StateEventCrossEventSankey.svelte - the layout-constant shape " +
        "changed; update this test.",
    ).not.toBeNull();
    const w = Number(wMatch![1]);
    const h = Number(hMatch![1]);
    expect(h, "H must be > 0").toBeGreaterThan(0);
    expect(
      w / h,
      `Seat-flow chart must be landscape (W / H >= 2.2) per the Row 1 ` +
        `Jony verdict (2026-06-18). Found W=${w}, H=${h}, ratio=${(
          w / h
        ).toFixed(2)}.`,
    ).toBeGreaterThanOrEqual(2.2);
  });

  it("has no two-line band-count `+ 12` vertical offset", () => {
    expect(
      /\+\s*12\b/.test(SOURCE),
      "StateEventCrossEventSankey.svelte still contains a `+ 12` offset. " +
        "The seat count is now a single-baseline <tspan> suffix on the " +
        "band label (no second <text> at `y + h/2 + 12`).",
    ).toBe(false);
    expect(
      SOURCE.includes("b.h / 2 + 12"),
      "StateEventCrossEventSankey.svelte still contains the old " +
        "`b.h / 2 + 12` two-line seat-count baseline. Collapse it to a " +
        "single <text> with a muted <tspan> seat-count suffix.",
    ).toBe(false);
  });
});
