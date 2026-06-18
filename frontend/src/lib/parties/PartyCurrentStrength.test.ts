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

describe("PartyCurrentStrength.svelte heading contract", () => {
  // Source-level pin (Row F): the strip heading + aria-label name the
  // party via the new `party_label` prop, so for party_label="CPI" the
  // section reads "CPI latest scorecard". Doctrine forbids mounting
  // Svelte in vitest, so we read the .svelte source and assert the
  // template shape + the removal of the pre-Row-F literal
  // "Where this party sits today".
  const here = dirname(fileURLToPath(import.meta.url));
  const source = readFileSync(
    join(here, "PartyCurrentStrength.svelte"),
    "utf-8",
  );

  it("declares the party_label prop and destructures it from $props()", () => {
    expect(source).toMatch(/party_label:\s*string/);
    expect(source).toMatch(
      /const\s*\{[^}]*\bparty_label\b[^}]*\}\s*:\s*Props\s*=\s*\$props\(\)/,
    );
  });

  it("renders the <h2> heading template as `{party_label} latest scorecard`", () => {
    expect(source).toMatch(/<h2[\s\S]*?\{party_label\} latest scorecard/);
  });

  it("yields 'CPI latest scorecard' when party_label is 'CPI'", () => {
    // The source-wired template is `{party_label} latest scorecard`;
    // substituting the short code reproduces the rendered heading.
    const headingTemplate = "{party_label} latest scorecard";
    expect(source).toContain(headingTemplate);
    expect(headingTemplate.replace("{party_label}", "CPI")).toBe(
      "CPI latest scorecard",
    );
  });

  it("sets the section aria-label to match the visible heading", () => {
    expect(source).toContain(
      "aria-label={`${party_label} latest scorecard`}",
    );
  });

  it("drops the pre-Row-F literal heading + aria-label", () => {
    expect(source).not.toMatch(/<h2[\s\S]*?Where this party sits today/);
    expect(source).not.toContain('aria-label="Where this party sits today"');
  });
});

describe("PartyCurrentStrength.svelte parliament-date link contract", () => {
  // Source-level pin (Row G): the Parliament line's date
  // `{parliament.month_label}` is wrapped in an in-app anchor pointing
  // at the national parliament election page via the base-aware
  // `link.nationalElection(parliament.event_id)` builder. The State-
  // Assembly line is intentionally NOT linked (out of Row-G scope).
  // Doctrine forbids mounting Svelte in vitest, so we read the .svelte
  // source and assert the template shape.
  const here = dirname(fileURLToPath(import.meta.url));
  const source = readFileSync(
    join(here, "PartyCurrentStrength.svelte"),
    "utf-8",
  );

  // Scope the link assertions to each body line by slicing the source
  // between the per-line data-testid anchors.
  const parliamentBlock = source.slice(
    source.indexOf('data-testid="party-current-strength-parliament"'),
    source.indexOf('data-testid="party-current-strength-assemblies"'),
  );
  const assembliesBlock = source.slice(
    source.indexOf('data-testid="party-current-strength-assemblies"'),
    source.indexOf('data-testid="party-current-strength-last"'),
  );

  it("imports the base-aware link builder", () => {
    expect(source).toContain('import { link } from "../links"');
  });

  it("wraps the parliament month_label in an anchor built via link.nationalElection(parliament.event_id)", () => {
    // The href MUST go through the base-aware builder (not a hardcoded
    // `/t/elections/...`) so the `in-app-hrefs-use-base` contract holds.
    expect(parliamentBlock).toContain(
      "href={link.nationalElection(parliament.event_id)}",
    );
    // The anchor wraps the month_label text node.
    expect(parliamentBlock).toMatch(
      /<a[\s\S]*?href=\{link\.nationalElection\(parliament\.event_id\)\}[\s\S]*?>\{parliament\.month_label\}<\/a>/,
    );
    // Standard in-app link styling (matches the wiki link + other
    // in-app links across /parties/<slug>).
    expect(parliamentBlock).toContain('class="text-sky-700 hover:underline"');
  });

  it("guards the anchor behind a truthy event_id so a missing id never yields a base-only href", () => {
    expect(parliamentBlock).toMatch(/\{#if parliament\.event_id\}/);
    expect(parliamentBlock).toMatch(
      /\{:else\}\{parliament\.month_label\}\{\/if\}/,
    );
  });

  it("does NOT link the State-Assembly date", () => {
    expect(assembliesBlock).not.toContain("link.nationalElection");
    expect(assembliesBlock).not.toMatch(/<a\s/);
  });
});
