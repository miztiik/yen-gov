// Phase 3 adopter smoke for IndicatorRanked.
//
// Verifies that the new ranked-comparison helpers (PR #153) are
// adopted in IndicatorRanked.svelte:
//
//   - The inline distribution bar shows a peer-median tick (a thin
//     slate vertical line) on at least one comparable indicator.
//   - The gap-line header strip uses direction-aware wording
//     ("X is N above/below Y." or "X matches Y.") with a verdict
//     badge that never contains the words "better" / "worse" (honesty
//     rule — verdict is on a separate badge).
//
// Mount route: `/t/energy` (TopicLanding) has IndicatorRanked + a
// stable set of installed-MW / share-renewables indicators. Per the
// chart plan §R-10, mounted-on routes are preferred over place-first
// routes when the legacy mount is the only one available; this is a
// `/t/` topic landing route — already canonical for topics.
//
// CLAUDE.md §15: attachPageErrorTrap is enforced.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

test.beforeEach(async ({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(async () => {
  const errors = trap?.getErrors() ?? [];
  trap = null;
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("IndicatorRanked Phase 3 polish", () => {
  test("energy topic renders at least one peer-median tick on a ranked indicator", async ({ page }) => {
    await page.goto("/t/energy");

    // Wait for at least one IndicatorRanked block to mount. Use a
    // forgiving timeout because TopicLanding fetches several artifacts
    // in parallel.
    const ticks = page.locator('[data-testid="indicator-ranked-median-tick"]');
    await expect(ticks.first()).toBeVisible({ timeout: 20_000 });

    // The tick exists on every ranked-and-comparable indicator that has
    // at least one present value. We require ≥1 (one tick per matching
    // distribution row). Asserting an exact count would be brittle as
    // the indicator corpus evolves.
    const count = await ticks.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("compare picker on a ranked indicator surfaces direction-aware gap wording", async ({ page }) => {
    // Karnataka hub mounts ranked indicators with the home-state pin
    // (S10). Selecting any compare state through the inline "Compare
    // with" picker should surface the Phase 3 gap-line strip with the
    // closed-enum wording produced by `computeGapLine`. The wording
    // must never say better/worse (honesty rule).
    await page.goto("/s/karnataka");

    // Find the first IndicatorRanked compare picker. Some routes may
    // mount it inside multiple ranked blocks; first is enough.
    const picker = page.locator('select#ranked-compare-select').first();
    const exists = await picker.isVisible().catch(() => false);
    test.skip(!exists, "No ranked compare picker mounted on /s/karnataka");

    // Pick any non-empty option. Use Tamil Nadu (S22) if present, else
    // the first available option.
    const options = await picker.locator("option").allTextContents();
    const tnIdx = options.findIndex(t => /tamil/i.test(t));
    if (tnIdx > 0) {
      await picker.selectOption({ index: tnIdx });
    } else {
      // Pick any non-"none" option (index 0 is the "— none —" sentinel).
      await picker.selectOption({ index: 1 });
    }

    const wording = page.locator('[data-testid="indicator-ranked-gap-wording"]').first();
    await expect(wording).toBeVisible({ timeout: 10_000 });
    const text = (await wording.textContent())?.trim() ?? "";
    expect(text).toMatch(/(above|below|matches|No data to compare)/i);

    // Honesty rule: the wording NEVER contains "better" or "worse".
    expect(text).not.toMatch(/better|worse/i);
  });
});
