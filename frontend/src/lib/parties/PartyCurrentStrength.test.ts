/**
 * `PartyCurrentStrength.test.ts` — vitest pin for the pure formatters
 * exported from `PartyCurrentStrength.svelte` (PR-7 of TODO/20260614-
 * party-page-reimagination-plan.md).
 *
 * Per project doctrine, vitest does not mount Svelte. The pin covers
 * the pure helpers that live in the component's `<script module>`
 * block (`formatSeats` + `formatVoteShare`); the rendered-DOM smoke
 * is in `Party.test.ts` (which mounts the route) and the manual
 * §13 browser smoke recorded in the PR body.
 */
import { describe, expect, it } from "vitest";

import { formatSeats, formatVoteShare } from "./PartyCurrentStrength.svelte";

describe("formatSeats", () => {
  it("formats integer seat counts with Indian-style comma grouping", () => {
    expect(formatSeats(0)).toBe("0");
    expect(formatSeats(5)).toBe("5");
    expect(formatSeats(543)).toBe("543");
    expect(formatSeats(1776)).toBe("1,776");
    expect(formatSeats(4035)).toBe("4,035");
  });

  it("truncates non-integer inputs (defensive against unexpected DuckDB shape)", () => {
    expect(formatSeats(132.7)).toBe("132");
    expect(formatSeats(211.0)).toBe("211");
  });
});

describe("formatVoteShare", () => {
  it("formats percentages with one decimal place and a trailing %", () => {
    // Note: 36.65 is *not* exactly representable in IEEE-754 - the
    // closest double is 36.6499...9, which `.toFixed(1)` correctly
    // rounds to "36.6". The honest 1dp value of 235,974,144 /
    // 643,890,022 * 100 (BJP LS-2024 vote-share) is "36.6%", not
    // the "36.7%" that two-step rounding would suggest.
    expect(formatVoteShare(36.65)).toBe("36.6%");
    expect(formatVoteShare(0)).toBe("0.0%");
    expect(formatVoteShare(100)).toBe("100.0%");
    expect(formatVoteShare(2.345)).toBe("2.3%");
  });
});
