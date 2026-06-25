// Contract: ONE source of truth for the constituency-map hover card.
//
// The standard-map-hover-card plan
// (TODO/20260625-standard-map-hover-card-plan.md) collapsed every
// per-surface bespoke tooltip-HTML builder into a single typed renderer
// (`renderTooltipCard`, lib/boundaries/tooltip-card.ts) wrapped by one
// presentational chrome component (`HoverCardShell.svelte`). Before that,
// each AC/PC map hand-rolled its own markup + its own `escapeHtml`, which
// drifted - the exact failure the "schema is the design system" rule
// forbids.
//
// This guard (plan Row 7) goes red the moment a surface re-rolls bespoke
// card markup or stops delegating to the shared renderer:
//
//   A. `renderTooltipCard` is DEFINED once (tooltip-card.ts) and IMPORTED
//      only by the four surfaces that own card CONTENT.
//   B. `HoverCardShell` is MOUNTED only by the four surfaces that own card
//      CHROME.
//   C. the migrated hex builder (election-tile-layout.ts) carries no
//      private `escapeHtml` - escaping is delegated to renderTooltipCard.
//   D. the retired bespoke "Winner:" / "Margin:" labels are gone from that
//      hex builder. Scoped to that ONE file: both strings live legitimately
//      elsewhere (chart legends, a dev sandbox's `.includes` check), so
//      this is NOT a global ban.
//   E. the card's distinctive structural literals appear in NO production
//      file but the shared renderer (a copy-pasted bespoke card trips this).
//
// Node-env source scan, matching the house pattern of
// contracts/party-colour-import-allowlist.test.ts. No DOM.

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

const SRC_ROOT = resolve(__dirname, "..");
const SELF = "contracts/tooltip-card-single-source.contract.test.ts";

// --- the single home of the shared card ---------------------------------
const RENDERER_MODULE = "lib/boundaries/tooltip-card.ts";
const HEX_BUILDER = "lib/view-models/election-tile-layout.ts";

// Surfaces that own card CONTENT (import the shared `renderTooltipCard`).
const RENDER_IMPORTERS = [
  "lib/charts/IndiaPcMapD3.svelte",
  "lib/charts/StateAcMapD3.svelte",
  "lib/charts/StatePcMapD3.svelte",
  "lib/view-models/election-tile-layout.ts",
].sort();

// Surfaces that own card CHROME (mount the shared `HoverCardShell`).
const SHELL_MOUNTERS = [
  "lib/charts/IndiaPcMapD3.svelte",
  "lib/charts/StateAcMapD3.svelte",
  "lib/charts/StatePcMapD3.svelte",
  "lib/charts/TileCartogram.svelte",
].sort();

// Distinctive markup that must live ONLY in the shared renderer: the card
// wrapper class and the affordance copy. A bespoke re-roll reproducing the
// card would carry one of these.
const CARD_LITERALS = ['class="yen-tip"', "Click to view"] as const;

function* walkSource(dir: string): IterableIterator<string> {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (name === "node_modules" || name.startsWith(".")) continue;
      yield* walkSource(full);
    } else if (
      name.endsWith(".ts") ||
      name.endsWith(".svelte") ||
      name.endsWith(".svelte.ts")
    ) {
      yield full;
    }
  }
}

function toPosix(abs: string): string {
  return relative(SRC_ROOT, abs).split(sep).join("/");
}

function isTestFile(rel: string): boolean {
  return (
    rel.includes("/__tests__/") ||
    rel.endsWith(".test.ts") ||
    rel.endsWith(".spec.ts")
  );
}

interface SourceFile {
  rel: string;
  src: string;
}

// Production (non-test, non-self) source files, read once. Tests are
// excluded: they legitimately reference the card symbols + literals to
// assert behaviour, so the single-source invariant is about production.
const PRODUCTION: SourceFile[] = [];
for (const abs of walkSource(SRC_ROOT)) {
  const rel = toPosix(abs);
  if (rel === SELF || isTestFile(rel)) continue;
  PRODUCTION.push({ rel, src: readFileSync(abs, "utf8") });
}

// A brace-import of one or more named bindings from a `tooltip-card`
// module. `[^}]*` spans newlines, so multi-line import blocks are caught
// (a continuation-line binding would slip a naive line-by-line scan).
const TOOLTIP_IMPORT_RE =
  /import\s*(?:type\s+)?\{([^}]*)\}\s*from\s*["'][^"']*\/tooltip-card["']/g;

// An import statement whose module specifier is the HoverCardShell
// component (default or renamed local binding still counts as a mount).
const SHELL_IMPORT_RE = /from\s*["'][^"']*\/HoverCardShell\.svelte["']/;

// A local definition of `renderTooltipCard` (function or arrow const).
const RENDERER_DEF_RE =
  /(?:export\s+)?(?:function\s+renderTooltipCard\s*\(|const\s+renderTooltipCard\s*=)/;

function importsRenderTooltipCard(src: string): boolean {
  for (const m of src.matchAll(TOOLTIP_IMPORT_RE)) {
    if (/\brenderTooltipCard\b/.test(m[1])) return true;
  }
  return false;
}

function hexBuilder(): SourceFile {
  const hex = PRODUCTION.find((f) => f.rel === HEX_BUILDER);
  expect(hex, `${HEX_BUILDER} not found under ${SRC_ROOT}`).toBeDefined();
  return hex as SourceFile;
}

describe("hover card: single source of truth (plan Row 7)", () => {
  it("A. renderTooltipCard is DEFINED only in the shared module", () => {
    const definers = PRODUCTION.filter((f) => RENDERER_DEF_RE.test(f.src))
      .map((f) => f.rel)
      .sort();
    expect(definers).toEqual([RENDERER_MODULE]);
  });

  it("A. renderTooltipCard is IMPORTED by EXACTLY the four content surfaces", () => {
    const importers = PRODUCTION.filter(
      (f) => f.rel !== RENDERER_MODULE && importsRenderTooltipCard(f.src),
    )
      .map((f) => f.rel)
      .sort();
    expect(importers).toEqual(RENDER_IMPORTERS);
  });

  it("B. HoverCardShell is MOUNTED by EXACTLY the four chrome surfaces", () => {
    const mounters = PRODUCTION.filter((f) => SHELL_IMPORT_RE.test(f.src))
      .map((f) => f.rel)
      .sort();
    expect(mounters).toEqual(SHELL_MOUNTERS);
  });

  it("C. the migrated hex builder declares no private escapeHtml", () => {
    // Escaping is delegated to renderTooltipCard; no bespoke escaper of any
    // form (`function escapeHtml` or `const escapeHtml =`) may return.
    expect(/\bescapeHtml\b/.test(hexBuilder().src)).toBe(false);
  });

  it("D. the retired 'Winner:' / 'Margin:' labels are gone from the hex builder", () => {
    const src = hexBuilder().src;
    // Scoped to this ONE file only - do NOT globally ban these strings.
    expect(src.includes("Winner:")).toBe(false);
    expect(src.includes("Margin:")).toBe(false);
  });

  it.each(CARD_LITERALS)(
    "E. card literal %j lives only in the shared renderer",
    (literal) => {
      const holders = PRODUCTION.filter((f) => f.src.includes(literal))
        .map((f) => f.rel)
        .sort();
      expect(
        holders,
        `bespoke card markup leaked: ${JSON.stringify(
          literal,
        )} found outside ${RENDERER_MODULE}`,
      ).toEqual([RENDERER_MODULE]);
    },
  );
});
