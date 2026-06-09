import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  IMAGINING_HEADLINE,
  shouldRenderAssumptions,
  officialResultLine,
} from "./ImaginingCard.svelte";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SVELTE_SRC = readFileSync(
  join(__dirname, "ImaginingCard.svelte"),
  "utf-8",
);

describe("IMAGINING_HEADLINE constant", () => {
  it("is the exact 9-word encouraging-tone phrase (Hans convergence)", () => {
    expect(IMAGINING_HEADLINE).toBe(
      "Imagine the seats under a different counting rule.",
    );
  });
  it("is ASCII-only (no curly quotes, em-dash, emoji)", () => {
    expect(Array.from(IMAGINING_HEADLINE).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
  it("does NOT contain the retired hazard vocabulary (HYPOTHETICAL / WARNING / etc.)", () => {
    const banned = ["HYPOTHETICAL", "WARNING", "CAUTION", "DISCLAIMER", "FABRICATED", "NOT THE OFFICIAL"];
    for (const word of banned) {
      expect(IMAGINING_HEADLINE.toUpperCase()).not.toContain(word);
    }
  });
});

describe("shouldRenderAssumptions", () => {
  it("returns false for undefined", () => {
    expect(shouldRenderAssumptions(undefined)).toBe(false);
  });
  it("returns false for empty array", () => {
    expect(shouldRenderAssumptions([])).toBe(false);
  });
  it("returns true for non-empty array", () => {
    expect(shouldRenderAssumptions(["one"])).toBe(true);
    expect(shouldRenderAssumptions(["a", "b", "c"])).toBe(true);
  });
});

describe("officialResultLine", () => {
  it("returns null for undefined", () => {
    expect(officialResultLine(undefined)).toBeNull();
  });
  it("returns null for empty string", () => {
    expect(officialResultLine("")).toBeNull();
  });
  it("returns null for whitespace-only string", () => {
    expect(officialResultLine("   ")).toBeNull();
    expect(officialResultLine("\t\n  ")).toBeNull();
  });
  it("uses 'Official:' prefix (not 'Official result:' which was the old hazard wording)", () => {
    const out = officialResultLine("DMK won 133 of 234 seats (FPTP)");
    expect(out).toBe("Official: DMK won 133 of 234 seats (FPTP)");
    expect(out).not.toMatch(/Official result:/);
  });
});

describe("ImaginingCard.svelte source structure", () => {
  it('declares role="alert" on the root element (live-region carve-out preserved)', () => {
    expect(SVELTE_SRC).toMatch(/role="alert"/);
  });
  it('declares aria-live="polite"', () => {
    expect(SVELTE_SRC).toMatch(/aria-live="polite"/);
  });
  it("renders IMAGINING_HEADLINE in the template", () => {
    expect(SVELTE_SRC).toContain("{IMAGINING_HEADLINE}");
  });
  it("uses the calm civic-indigo accent rail (--accent token), NOT rose hazard chrome", () => {
    expect(SVELTE_SRC).toMatch(/--accent/);
    expect(SVELTE_SRC).toMatch(/bg-surface/);
    expect(SVELTE_SRC).not.toMatch(/bg-rose-/);
    expect(SVELTE_SRC).not.toMatch(/border-rose-/);
    expect(SVELTE_SRC).not.toMatch(/text-rose-/);
  });
  it("is sticky-top so the citizen never scrolls past the announcement", () => {
    expect(SVELTE_SRC).toMatch(/\bsticky\b/);
    expect(SVELTE_SRC).toMatch(/\btop-0\b/);
  });
  it("uses calm slate body via --ink tokens, NOT uppercase scream", () => {
    expect(SVELTE_SRC).toMatch(/--ink/);
    // The Tailwind 'uppercase' utility (a `class=` token) is forbidden;
    // a docstring mention of the word in prose is fine.
    expect(SVELTE_SRC).not.toMatch(/class="[^"]*\buppercase\b/);
    expect(SVELTE_SRC).not.toMatch(/class="[^"]*\btracking-wider\b/);
  });
  it("guards assumptions <ul> with shouldRenderAssumptions", () => {
    expect(SVELTE_SRC).toMatch(/shouldRenderAssumptions\(/);
  });
  it("guards official-result line with officialResultLine", () => {
    expect(SVELTE_SRC).toMatch(/officialResultLine\(/);
  });
  it("references docs_href via 'Read how this counting works ->' link copy", () => {
    expect(SVELTE_SRC).toMatch(/docs_href/);
    expect(SVELTE_SRC).toMatch(/Read how this counting works/);
  });
  it("ASCII-only in source (no emojis or curly quotes)", () => {
    const cleaned = SVELTE_SRC.replace(/[\r\n]/g, "");
    expect(Array.from(cleaned).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
