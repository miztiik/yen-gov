// Phase 6 (charting modernisation plan) — dev sandbox smoke.
//
// Drives /dev/charts-sandbox and asserts each renderer's <section>
// landed. The sandbox exists so reviewers can sanity-check that the
// generic renderers (HorizontalGroupedBar, OrderedCategoryBar,
// DumbbellRange, TimeSeriesLine, FacetPanelGrid) work against
// realistic-shaped fixture data at runtime, independent of any
// citizen route adopting them.
//
// This spec is intentionally minimal: it proves the route mounts
// without console errors AND the five sandbox sections exist.
// Detailed renderer behaviour is covered by per-renderer vitest
// suites + per-route e2e specs.
//
// pageerror trap per CLAUDE.md §15.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `sandbox emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test("dev charts sandbox renders every generic renderer section", async ({ page }) => {
  await page.goto("/dev/charts-sandbox");

  await expect(page.getByRole("heading", { name: "Charts sandbox", level: 1 })).toBeVisible();

  // Each renderer is wrapped in a <section data-sandbox-section="…">.
  for (const id of ["hgb", "ocb", "dr", "tsl", "fpg"]) {
    await expect(page.locator(`[data-sandbox-section="${id}"]`)).toBeVisible();
  }

  // Spot-check that one chart actually painted by asserting a synthetic
  // datum reaches the DOM. Scope to the HGB section so we don't collide
  // with the LeftRail state-picker which also contains "Tamil Nadu".
  const hgb = page.locator('[data-sandbox-section="hgb"]');
  await expect(hgb.getByText("Tamil Nadu", { exact: false }).first()).toBeVisible();
  await expect(hgb.getByText("12.7 GW").first()).toBeVisible();
});
