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
    // We do NOT wait for `networkidle` here: the state-overview surface
    // mounts maplibre-gl, which sustains a steady tail of WebGL/tile
    // traffic (alongside Vite HMR and the boundaries-manifest probe)
    // such that "no network for 500ms" can take >>15s on CI and times
    // out before the page is interactively done. The visibility
    // assertion below is the real gating signal — SourceList renders
    // only after the result.summary fetch resolves, which is the load
    // contract this test cares about. Mirror this pattern in any new
    // non-TN spec.
    await expect(page.getByText(SOURCE_LIST_TEXT).first()).toBeVisible({ timeout: 30_000 });
  });

  test("bihar (S04) degrades gracefully for pending_upstream state", async ({ page }) => {
    // No election artifact ships for Bihar yet. The route must mount
    // without throwing; the `attachPageErrorTrap` afterEach asserts that.
    // We do NOT assert specific copy because the empty-state surface is
    // expected to evolve as we wire up the per-topic graceful-empty UI.
    // `networkidle` is intentionally avoided — see the kerala test
    // above for the rationale; `main` becoming visible is sufficient
    // proof of mount.
    await page.goto("/s/bihar");
    await expect(page.locator("main").first()).toBeVisible({ timeout: 15_000 });
  });
});
