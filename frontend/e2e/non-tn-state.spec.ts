// Multi-state coverage — the citizen perceives yen-gov as an *Indian*
// civic site, not a Tamil-Nadu site. These tests prove the same routes
// work for at least one other state with full data (Kerala / S11) and
// degrade gracefully for a state with no upstream artifact yet
// (Bihar / S04, `data_status: pending_upstream` in election-events.json).
//
// The graceful-degradation contract: a pending_upstream state must NOT
// throw a pageerror — it must render an empty/coming-soon shell. If the
// route crashes the test fails; if it shows a "data not available" panel
// the test passes (because the pageerror trap stays silent).

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap, SOURCE_LIST_TEXT } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("non-TN states", () => {
  test("kerala (S11) renders state overview with provenance", async ({ page }) => {
    await page.goto("/s/kerala");
    await page.waitForLoadState("networkidle", { timeout: 15_000 });
    // SourceList now sits inside the AboutThisData <details> accordion
    // (default collapsed), so it is attached to the DOM but not visible
    // until the citizen opens the disclosure. CLAUDE.md §15 only requires
    // the surface exists. Mirrors golden-path.spec.ts:108.
    await expect(page.getByText(SOURCE_LIST_TEXT).first()).toBeAttached({ timeout: 15_000 });
  });

  test("bihar (S04) degrades gracefully for pending_upstream state", async ({ page }) => {
    // No election artifact ships for Bihar yet. The route must mount
    // without throwing; the `attachPageErrorTrap` afterEach asserts that.
    // We do NOT assert specific copy because the empty-state surface is
    // expected to evolve as we wire up the per-topic graceful-empty UI.
    await page.goto("/s/bihar");
    await page.waitForLoadState("networkidle", { timeout: 15_000 });
    await expect(page.locator("main").first()).toBeVisible();
  });
});
