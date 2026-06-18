/**
 * Load-bearing oracle for state-event section-heading HARMONY (Row 4 of
 * the frontend polish plan, 2026-06-18).
 *
 * Verdict (Jony + Citizen, RATIFIED): the state-event page
 * (`/<state>/elections/<event>`) previously mixed TWO section-heading
 * treatments - a PLAIN `text-sm font-medium text-slate-700` on most
 * sections and an UPPERCASE CARD-LABEL
 * `text-sm font-semibold uppercase tracking-wide text-slate-500` on only
 * "Races by competitiveness" + "All parties - directory". That split
 * read inconsistent AND left the "Seat flow" heading under-weighted.
 * Citizen found the all-caps label too heavy to apply to EVERY section,
 * so the resolution is ONE slightly-stronger PLAIN canonical heading
 * applied uniformly:
 *
 *   text-sm font-semibold text-slate-800
 *
 * This test reads each of the 7 source files that own a top-level
 * state-event section <h2> off disk and asserts every <h2> uses the
 * canonical class and NEITHER legacy treatment survives. Reverting any
 * one section to a legacy style flips this RED with a message naming the
 * offending file.
 *
 * Pattern precedent: StateElection.section-order.test.ts (same dir) - a
 * pure node-env readFileSync contract test, no Svelte mount.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// The ONE canonical section-heading class every state-event <h2> must
// carry. Matched as a substring so a leading non-style utility such as
// `mb-3` may legitimately precede it.
const CANONICAL = "text-sm font-semibold text-slate-800";

// The two RETIRED treatments. No <h2> in these files may carry either.
const LEGACY_PLAIN = "font-medium text-slate-700";
const LEGACY_CARD_LABEL = "uppercase tracking-wide";

// Each source file that owns >= 1 top-level state-event section <h2>.
// Paths are relative to this file (frontend/src/lib/elections/). The
// 7 files carry 10 <h2> sites in total.
const FILES: ReadonlyArray<readonly [string, string]> = [
  ["StateElection.svelte", "../../routes/StateElection.svelte"],
  ["StateEventScatter.svelte", "./StateEventScatter.svelte"],
  ["StateEventMap.svelte", "./StateEventMap.svelte"],
  ["StateEventPartyComposite.svelte", "./StateEventPartyComposite.svelte"],
  ["StateEventCrossEventSankey.svelte", "./StateEventCrossEventSankey.svelte"],
  ["StateEventConstituencyList.svelte", "./StateEventConstituencyList.svelte"],
  ["StateEventAllParties.svelte", "./StateEventAllParties.svelte"],
];

// Global so matchAll captures EVERY <h2 class="..."> in the file.
const H2_CLASS = /<h2\s+class="([^"]+)"/g;

function h2Classes(relPath: string): string[] {
  const src = readFileSync(resolve(__dirname, relPath), "utf8");
  return Array.from(src.matchAll(H2_CLASS), (m) => m[1]);
}

describe("state-event section-heading harmony (Row 4)", () => {
  for (const [name, relPath] of FILES) {
    describe(name, () => {
      const classes = h2Classes(relPath);

      it("has at least one <h2>", () => {
        expect(
          classes.length,
          `${name}: expected >= 1 <h2 class="..."> but found none - a ` +
            `section heading was moved, renamed, or lost its class ` +
            `attribute. Update this oracle if the heading legitimately ` +
            `relocated.`,
        ).toBeGreaterThanOrEqual(1);
      });

      it("every <h2> uses the canonical class", () => {
        for (const cls of classes) {
          expect(
            cls.includes(CANONICAL),
            `${name}: <h2 class="${cls}"> is missing the canonical ` +
              `"${CANONICAL}". Every state-event section heading must use ` +
              `the single canonical treatment (Row 4 Jony + Citizen verdict).`,
          ).toBe(true);
        }
      });

      it("no <h2> carries a retired (legacy) treatment", () => {
        for (const cls of classes) {
          expect(
            cls.includes(LEGACY_PLAIN),
            `${name}: <h2 class="${cls}"> still carries the retired plain ` +
              `treatment "${LEGACY_PLAIN}". Harmonise to "${CANONICAL}".`,
          ).toBe(false);
          expect(
            cls.includes(LEGACY_CARD_LABEL),
            `${name}: <h2 class="${cls}"> still carries the retired ` +
              `card-label treatment "${LEGACY_CARD_LABEL}". Harmonise to ` +
              `"${CANONICAL}".`,
          ).toBe(false);
        }
      });
    });
  }
});

// ---------------------------------------------------------------------------
// AllianceTotals is a SHARED section component (mounted on BOTH the
// state-event page AND NationalElection.svelte). NationalElection uses the
// legacy plain heading on all its sections, so AllianceTotals must NOT be
// harmonised globally (that would make it a singleton there). Instead its
// heading is driven by an optional `headingClass` prop whose DEFAULT keeps
// the national surface byte-identical; the state-event route passes the
// canonical class. This block freezes that seam.
// ---------------------------------------------------------------------------
describe("AllianceTotals heading seam (Row 4)", () => {
  const route = readFileSync(
    resolve(__dirname, "../../routes/StateElection.svelte"),
    "utf8",
  );
  const alliance = readFileSync(
    resolve(__dirname, "./AllianceTotals.svelte"),
    "utf8",
  );

  it("StateElection passes the canonical headingClass to the AllianceTotals mount", () => {
    expect(
      route.includes(`headingClass="${CANONICAL}"`),
      `StateElection.svelte must pass headingClass="${CANONICAL}" to the ` +
        `AllianceTotals mount so the Alliance-totals section heading matches ` +
        `the other harmonised state-event sections.`,
    ).toBe(true);
  });

  it("AllianceTotals renders its heading from the prop (no hardcoded legacy <h2>)", () => {
    expect(
      alliance.includes("<h2 class={headingClass}>"),
      "AllianceTotals.svelte must render its section heading via " +
        "class={headingClass} (it is shared, so the class is prop-driven).",
    ).toBe(true);
    expect(
      /<h2 class="[^"]*font-medium text-slate-700[^"]*">/.test(alliance),
      "AllianceTotals.svelte must not hardcode the legacy heading class on " +
        "an <h2>; the heading is now prop-driven.",
    ).toBe(false);
  });

  it("AllianceTotals headingClass DEFAULTS to the legacy plain heading (national surface unchanged)", () => {
    expect(
      alliance.includes('headingClass = "text-sm font-medium text-slate-700"'),
      "AllianceTotals.svelte headingClass prop must DEFAULT to " +
        '"text-sm font-medium text-slate-700" so the NationalElection ' +
        "surface (which uses the legacy plain heading on every section) is " +
        "byte-identical.",
    ).toBe(true);
  });
});
