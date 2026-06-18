/**
 * `PartyAllianceContext.test.ts` - vitest pin for the pure formatters
 * exported from `PartyAllianceContext.svelte` (PR-8 of TODO/20260614-
 * party-page-reimagination-plan.md).
 *
 * Per project doctrine, vitest does not mount Svelte. The pin covers
 * the pure helpers that live in the component's `<script module>`
 * block (`formatPartnerList` + `formatAllianceLine`); the rendered-
 * DOM smoke is in `Party.test.ts` (which mounts the route) and the
 * manual section 13 browser smoke recorded in the PR body.
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

import {
  formatAllianceLine,
  formatPartnerList,
} from "./PartyAllianceContext.svelte";

describe("formatPartnerList", () => {
  it("returns empty string for empty partner list", () => {
    expect(formatPartnerList([], 0)).toBe("");
  });

  it("returns comma-joined list when not truncated", () => {
    expect(formatPartnerList(["JD(U)"], 1)).toBe("JD(U)");
    expect(formatPartnerList(["JD(U)", "TDP"], 2)).toBe("JD(U), TDP");
    expect(formatPartnerList(["A", "B", "C"], 3)).toBe("A, B, C");
  });

  it("appends (+N others) when partner_count exceeds list length", () => {
    expect(formatPartnerList(["JD(U)"], 3)).toBe("JD(U) (+2 others)");
    expect(formatPartnerList(["A", "B", "C", "D", "E"], 10)).toBe(
      "A, B, C, D, E (+5 others)",
    );
  });

  it("uses singular 'other' for a single truncated partner", () => {
    expect(formatPartnerList(["A", "B"], 3)).toBe("A, B (+1 other)");
  });
});

describe("formatAllianceLine", () => {
  it("renders 'contested alone' when alliance is null", () => {
    expect(formatAllianceLine("alone", null, [], 0)).toBe("contested alone");
    // Role override: even if a buggy caller passes 'led' with null
    // alliance, the null-alliance branch wins.
    expect(formatAllianceLine("led", null, [], 0)).toBe("contested alone");
  });

  it("renders 'led <alliance> with <partners>' for role='led'", () => {
    expect(formatAllianceLine("led", "NDA", ["JD(U)", "TDP"], 2)).toBe(
      "led NDA with JD(U), TDP",
    );
  });

  it("renders 'junior in <alliance> with <partners>' for role='junior'", () => {
    expect(formatAllianceLine("junior", "NDA", ["BJP"], 1)).toBe(
      "junior in NDA with BJP",
    );
  });

  it("renders honest 'partner data pending' for role='alone' with non-null alliance", () => {
    expect(formatAllianceLine("alone", "Mahayuti", [], 0)).toBe(
      "Mahayuti alliance, partner data pending",
    );
  });

  it("omits the 'with <partners>' tail when partner list is empty for led/junior", () => {
    expect(formatAllianceLine("led", "NDA", [], 0)).toBe("led NDA");
    expect(formatAllianceLine("junior", "INDIA", [], 0)).toBe("junior in INDIA");
  });

  it("appends (+N others) tail when partners are truncated", () => {
    expect(
      formatAllianceLine("led", "NDA", ["JD(U)", "TDP"], 7),
    ).toBe("led NDA with JD(U), TDP (+5 others)");
  });
});

describe("PartyAllianceContext.svelte D3 icon contract", () => {
  // Source-level pin: doctrine forbids mounting Svelte, so we read
  // the component file as text and assert the structural shape.
  // Defends the PR-2 swap of `<img src="/icons/...">` to inline
  // `<TopicIcon>` from regressing back to broken-image boxes.
  const here = dirname(fileURLToPath(import.meta.url));
  const source = readFileSync(
    join(here, "PartyAllianceContext.svelte"),
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

describe("PartyAllianceContext.svelte heading contract", () => {
  // Source-level pin (Row F): the strip heading + aria-label name the
  // party via the new `party_label` prop, so for party_label="CPI" the
  // section reads "Who CPI team up with". Doctrine forbids mounting
  // Svelte in vitest, so we read the .svelte source and assert the
  // template shape + the removal of the pre-Row-F literal
  // "Who they ride with".
  const here = dirname(fileURLToPath(import.meta.url));
  const source = readFileSync(
    join(here, "PartyAllianceContext.svelte"),
    "utf-8",
  );

  it("declares the party_label prop and destructures it from $props()", () => {
    expect(source).toMatch(/party_label:\s*string/);
    expect(source).toMatch(
      /const\s*\{[^}]*\bparty_label\b[^}]*\}\s*:\s*Props\s*=\s*\$props\(\)/,
    );
  });

  it("renders the <h2> heading template as `Who {party_label} team up with`", () => {
    expect(source).toMatch(/<h2[\s\S]*?Who \{party_label\} team up with/);
  });

  it("yields 'Who CPI team up with' when party_label is 'CPI'", () => {
    // The source-wired template is `Who {party_label} team up with`;
    // substituting the short code reproduces the rendered heading.
    const headingTemplate = "Who {party_label} team up with";
    expect(source).toContain(headingTemplate);
    expect(headingTemplate.replace("{party_label}", "CPI")).toBe(
      "Who CPI team up with",
    );
  });

  it("sets the section aria-label to match the visible heading", () => {
    expect(source).toContain(
      "aria-label={`Who ${party_label} team up with`}",
    );
  });

  it("drops the pre-Row-F literal heading + aria-label", () => {
    expect(source).not.toMatch(/<h2[\s\S]*?Who they ride with/);
    expect(source).not.toContain('aria-label="Who this party rides with"');
  });
});
