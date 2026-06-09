// Vitest - pure-helper + raw-source-text tests for HypotheticalRecountBanner.svelte
// (E6 Hans "fabricated-input" honesty primitive).
//
// Component-render assertions are deferred to Playwright per repo
// vitest doctrine (node-env, no jsdom, no @testing-library/svelte; see
// Skeleton.test.ts + MapHighlightLegend.test.ts +
// GallagherDisproportionality.test.ts for the 8-test precedent
// matched verbatim by sister E7 commit b6fce94d). Two testable
// surfaces here:
//
//  1) The 3 module-script exports:
//     - BANNER_HEADLINE  - the exact uppercase copy
//     - shouldRenderAssumptions(assumptions) - declarative <ul> guard
//     - officialResultLine(label)            - "Official result: ..." builder
//
//  2) Structural pins on the .svelte file SOURCE (the file-content
//     equivalent of DOM-render assertions; same intent, no jsdom
//     needed). These guard the load-bearing render contract:
//     role="alert", aria-live="polite", BANNER_HEADLINE usage in the
//     template, Tailwind rose hazard palette, sticky-top sentinel,
//     helper invocations, <strong> headline emphasis, ASCII-only source.

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  BANNER_HEADLINE,
  shouldRenderAssumptions,
  officialResultLine,
} from "./HypotheticalRecountBanner.svelte";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SVELTE_SRC = readFileSync(
  join(__dirname, "HypotheticalRecountBanner.svelte"),
  "utf-8",
);

// ---------- BANNER_HEADLINE constant ---------------------------------------

describe("BANNER_HEADLINE constant", () => {
  it("is the exact uppercase phrase", () => {
    expect(BANNER_HEADLINE).toBe(
      "HYPOTHETICAL RECOUNT - NOT THE OFFICIAL RESULT",
    );
  });

  it("is ASCII-only (no curly quotes, em-dash, emoji)", () => {
    expect(
      Array.from(BANNER_HEADLINE).every((c) => c.charCodeAt(0) < 128),
    ).toBe(true);
  });
});

// ---------- shouldRenderAssumptions ----------------------------------------

describe("shouldRenderAssumptions", () => {
  it("returns false for undefined", () => {
    expect(shouldRenderAssumptions(undefined)).toBe(false);
  });

  it("returns false for empty array", () => {
    expect(shouldRenderAssumptions([])).toBe(false);
  });

  it("returns true for non-empty array", () => {
    expect(shouldRenderAssumptions(["assumes uniform turnout"])).toBe(true);
    expect(
      shouldRenderAssumptions([
        "state-wide pool",
        "no threshold",
        "Sainte-Lague divisors",
      ]),
    ).toBe(true);
  });
});

// ---------- officialResultLine ---------------------------------------------

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

  it("formats the label with 'Official result:' prefix", () => {
    expect(officialResultLine("DMK won 133 of 234 seats (FPTP)")).toBe(
      "Official result: DMK won 133 of 234 seats (FPTP)",
    );
  });
});

// ---------- Source-structure pins (file-content equivalent of DOM render) --

describe("HypotheticalRecountBanner.svelte source structure", () => {
  it('declares role="alert" on the root element', () => {
    expect(SVELTE_SRC).toMatch(/role="alert"/);
  });

  it('declares aria-live="polite"', () => {
    expect(SVELTE_SRC).toMatch(/aria-live="polite"/);
  });

  it("renders the BANNER_HEADLINE constant in the template", () => {
    expect(SVELTE_SRC).toContain("{BANNER_HEADLINE}");
  });

  it("uses the Tailwind rose hazard palette", () => {
    expect(SVELTE_SRC).toMatch(/bg-rose-50/);
    expect(SVELTE_SRC).toMatch(/border-rose-300/);
    expect(SVELTE_SRC).toMatch(/text-rose-900/);
  });

  it("is sticky-top inside its parent", () => {
    expect(SVELTE_SRC).toMatch(/\bsticky\b/);
    expect(SVELTE_SRC).toMatch(/\btop-0\b/);
  });

  it("guards the assumptions <ul> with shouldRenderAssumptions", () => {
    expect(SVELTE_SRC).toMatch(/shouldRenderAssumptions\(/);
  });

  it("references officialResultLine in the template", () => {
    expect(SVELTE_SRC).toMatch(/officialResultLine\(/);
  });

  it("uses <strong> for the headline emphasis", () => {
    expect(SVELTE_SRC).toMatch(/<strong[^>]*>\{BANNER_HEADLINE\}<\/strong>/);
  });

  it("ASCII-only in source (no emojis or curly quotes)", () => {
    // Strip CRLF line endings and check every code point.
    const cleaned = SVELTE_SRC.replace(/[\r\n]/g, "");
    expect(Array.from(cleaned).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
