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
 *
 * The bottom `D3 icon contract` block is a source-level pin (the
 * doctrine forbids mounting Svelte, so we read the .svelte file
 * from disk and grep for the regression shape). PR-2 of TODO/
 * 20260615-party-page-citizen-fixes-plan.md swapped two
 * `<img src="/icons/landmark.svg">` + `<img src="/icons/flag.svg">`
 * sites to `<TopicIcon name="...">` because stroke-less /
 * fill-less Lucide-style SVGs cannot inherit `currentColor` when
 * loaded as an `<img>`, producing empty-square broken-image boxes.
 * The pin asserts the structural swap survives future edits.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
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

describe("PartyCurrentStrength.svelte D3 icon contract", () => {
  // Source-level pin: doctrine forbids mounting Svelte, so we read
  // the component file as text and assert the structural shape.
  // Defends the PR-2 swap of `<img src="/icons/...">` to inline
  // `<TopicIcon>` from regressing back to broken-image boxes.
  const here = dirname(fileURLToPath(import.meta.url));
  const source = readFileSync(
    join(here, "PartyCurrentStrength.svelte"),
    "utf-8",
  );

  it("does not load icon glyphs via <img src=\"/icons/...\">", () => {
    // Lucide-style SVGs require inline injection to inherit
    // `currentColor`; loading them via <img> produces empty 16x16
    // squares (D3 defect from TODO/20260615-party-page-citizen-
    // fixes-plan.md).
    expect(source).not.toMatch(/<img\s[^>]*src=["']\/icons\//);
  });

  it("renders the landmark + flag glyphs via <TopicIcon>", () => {
    expect(source).toContain('import TopicIcon from "../TopicIcon.svelte"');
    expect(source).toMatch(/<TopicIcon[\s\S]*?name="landmark"/);
    expect(source).toMatch(/<TopicIcon[\s\S]*?name="flag"/);
  });
});
