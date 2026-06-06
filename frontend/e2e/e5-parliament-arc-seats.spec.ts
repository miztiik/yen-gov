// E5 ParliamentArc seats invariant regression spec.
//
// Parent plan section 25.6a + gate `seats-invariant-test` (section 22.6):
//
//   "pins a known result so the parliament arc renders exactly
//    `total_seats` dots with `sum(seats_won) == total_seats == COUNT(DISTINCT
//    constituency winner)`; the ~2x double-count regression cannot return."
//
// What this spec asserts (per CLAUDE.md section 13 in-browser smoke):
//
//   1. ZERO console errors on `/lab/<state>/<event>` for two representative
//      states (TN 234 seats; Bihar 243 seats).
//   2. The ParliamentArc SVG (aria-label "Seat distribution arc") renders
//      EXACTLY `total_seats` <circle> elements.
//   3. The legend total (sum of per-party tabular-nums chips) equals
//      `total_seats` exactly. No silent halving, no drift.
//
// Why two states: the parent plan's 234-seat TN is the orchestrator's
// canonical pinned result; the 243-seat Bihar event is the second-largest
// assembly in the corpus and exercises a different party set (RJD/JD(U)/BJP/INC
// vs DMK/AIADMK). Mobile project is skipped per the existing
// `state-ac-coverage.spec.ts` doctrine - Psephlab has no
// breakpoint-specific code path.
//
// What this spec does NOT assert:
//   - alternate counting methods (E6 sub-plan; gated on Citizen + Hans
//     second opinion + "hypothetical recount, not official result" banner)
//   - per-party seat-count exactness (parent plan section 22.6 only pins
//     the sum invariant)
//   - mutation-aware FPTP after a swing slider has been touched (Psephlab
//     mutation coverage is in the existing vitest suite at
//     `src/lib/psephlab/engine.test.ts`)

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

const SEATS_INVARIANT_TARGETS: ReadonlyArray<{
  slug: string;
  event: string;
  expected_total_seats: number;
  label: string;
}> = [
  {
    slug: "tamil-nadu",
    event: "AcGenApr2021",
    expected_total_seats: 234,
    label: "Tamil Nadu Assembly April 2021",
  },
  {
    slug: "bihar",
    event: "AcGenOct2020",
    expected_total_seats: 243,
    label: "Bihar Assembly October 2020",
  },
];

let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

test.beforeEach(({ page }, testInfo) => {
  trap = null;
  test.skip(
    testInfo.project.name === "mobile-pixel-5",
    "ParliamentArc seats invariant smoke is desktop-only (Psephlab has no breakpoint-specific code path).",
  );
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap?.getErrors() ?? [];
  trap = null;
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("E5 ParliamentArc seats invariant (25.6a)", () => {
  for (const target of SEATS_INVARIANT_TARGETS) {
    test(`/lab/${target.slug}/${target.event} renders exactly ${target.expected_total_seats} dots AND ${target.expected_total_seats} legend total (${target.label})`, async ({
      page,
    }) => {
      await page.goto(`/lab/${target.slug}/${target.event}`, {
        waitUntil: "domcontentloaded",
      });

      // Wait for the ParliamentArc SVG to render. The aria-label is
      // hand-authored in `frontend/src/lib/ParliamentArc.svelte`.
      const arc = page.locator('svg[aria-label="Seat distribution arc"]');
      await expect(arc).toBeVisible({ timeout: 60_000 });

      // Invariant #1: dot count == expected total_seats.
      // ParliamentArc reconciles per-row rounding so the slot count is
      // exactly `total_seats`; any deviation here is the input feed
      // double-counting upstream (the bug class 25.6a guards against).
      const dotCount = await arc.locator("circle").count();
      expect(
        dotCount,
        `ParliamentArc dot count != ${target.expected_total_seats} for ` +
          `${target.event}/${target.slug}; got ${dotCount}. ` +
          `If this fails, sum(seats_won) drifted from total_seats; see ` +
          `assertSeatTallyInvariant in frontend/src/lib/charts/count-seats.ts.`,
      ).toBe(target.expected_total_seats);

      // Invariant #2: legend total == expected total_seats.
      // The legend lists one chip per party with a tabular-nums seat count;
      // they MUST sum to total_seats (sentinel: the ~2x bug would show
      // legend=2N while dots=N or vice versa).
      const legendTotal = await arc
        .locator("xpath=following-sibling::ul[1]")
        .first()
        .evaluate((ul: HTMLElement) => {
          let sum = 0;
          for (const li of Array.from(ul.querySelectorAll("li"))) {
            const tabular = li.querySelector(".tabular-nums");
            if (!tabular) continue;
            const n = parseInt(tabular.textContent?.trim() ?? "", 10);
            if (!Number.isNaN(n)) sum += n;
          }
          return sum;
        });
      expect(
        legendTotal,
        `ParliamentArc legend total != ${target.expected_total_seats} for ` +
          `${target.event}/${target.slug}; got ${legendTotal}. ` +
          `If this fails, sum(seats_won across parties) != total_seats.`,
      ).toBe(target.expected_total_seats);

      // Invariant #3 (cross-check): dot count == legend total. Even if both
      // are wrong (a future regression that drifts BOTH by the same factor),
      // a mismatch between them is a separate failure mode the orchestrator
      // explicitly wants caught.
      expect(
        dotCount,
        `Dot count != legend total for ${target.event}/${target.slug}: ` +
          `dots=${dotCount} legend=${legendTotal}. The two are sourced from ` +
          `the same SeatTally; a mismatch means a rendering bug in ParliamentArc.`,
      ).toBe(legendTotal);
    });
  }
});
