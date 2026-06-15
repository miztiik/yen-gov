import { describe, expect, test } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Contract: every top-level <main> / <section> wrapper inside a route
 * file may NOT hand-roll a Tailwind `max-w-*` cap. Routes must use
 * <PageContainer width="narrow|wide|full"> instead. The cap policy
 * lives in [frontend/src/lib/layout/PageContainer.svelte](../lib/layout/PageContainer.svelte).
 *
 * Motivation: 6 distinct caps (max-w-3xl / 4xl / 5xl / 6xl / 7xl /
 * screen-2xl) drifted across ~27 routes before
 * [TODO/20260615-party-page-citizen-fixes-plan.md](../../../TODO/20260615-party-page-citizen-fixes-plan.md)
 * PR-6 D7 baked one wide cap (max-w-screen-2xl) + one narrow opt-in
 * (max-w-3xl) + one no-cap escape hatch (full).
 *
 * Scope: this contract guards top-level <main> / <section> wrappers
 * only (those that open at column 0). Nested elements - chart cards,
 * card decks, prose blocks - may still scope their own widths inside
 * the page container.
 *
 * Allowlist: documented exceptions live in ALLOWLIST below. Add a new
 * entry only when the inline cap is structurally necessary AND the
 * choice is documented in
 * [frontend/src/lib/layout/README.md](../lib/layout/README.md).
 */

const here = dirname(fileURLToPath(import.meta.url));
const ROUTES_DIR = join(here, "..", "routes");

interface AllowlistEntry {
  /** Filename inside frontend/src/routes/ */
  file: string;
  /** Substring (verbatim) that uniquely identifies the allowed opening tag. */
  identifier: string;
  /** Why this exception exists. */
  reason: string;
}

const ALLOWLIST: ReadonlyArray<AllowlistEntry> = [
  {
    file: "StateOverview.svelte",
    identifier: 'class="max-w-md mx-auto p-12 text-center space-y-4"',
    reason:
      "Inline 404 recovery surface; mirrors NotFound.svelte copy. The wider page above uses <PageContainer width=\"wide\">.",
  },
];

// Match opening <main> or <section> tags that start at column 0 (i.e.
// top-level wrappers, not nested cards). The `s` flag lets [^>]* span
// newlines so multi-line opening tags (e.g. Party.svelte's <main\n
// class="..."\n  data-testid="...">) are captured as ONE match.
const TOP_LEVEL_OPEN_RE = /^<(main|section)\b([^>]*)>/gms;

// Tailwind cap classes we want to ban at the top level.
const CAP_RE = /\bmax-w-[A-Za-z0-9-]+/;

describe("no-route-bare-width-cap (PR-6 D7)", () => {
  const files = readdirSync(ROUTES_DIR).filter((n) => n.endsWith(".svelte"));

  expect(
    files.length,
    "expected at least one route file under frontend/src/routes/",
  ).toBeGreaterThan(0);

  for (const file of files) {
    test(`routes/${file}: top-level <main>/<section> may not carry max-w-*`, () => {
      const src = readFileSync(join(ROUTES_DIR, file), "utf-8");

      const violations: string[] = [];
      for (const match of src.matchAll(TOP_LEVEL_OPEN_RE)) {
        const fullTag = match[0];
        const attrs = match[2];
        if (!CAP_RE.test(attrs)) continue;
        const isAllowlisted = ALLOWLIST.some(
          (a) => a.file === file && fullTag.includes(a.identifier),
        );
        if (isAllowlisted) continue;
        violations.push(fullTag.replace(/\s+/g, " ").trim());
      }

      expect(
        violations,
        `Top-level <main>/<section> in routes/${file} declares its own max-w-*. ` +
          `Use <PageContainer width="narrow|wide|full"> from frontend/src/lib/layout/ ` +
          `instead. See frontend/src/lib/layout/README.md. ` +
          `Offenders: ${violations.join(" | ")}`,
      ).toEqual([]);
    });
  }
});
