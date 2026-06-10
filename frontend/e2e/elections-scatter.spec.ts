// Playwright e2e for the Scatter chart (PR-W4c, 2026-06-10).
//
// Smokes the brief's G2 + G4 gates: scatter mounts on both the national
// event view and the state event view, filter narrowing works on the
// `body` chip (>=1 dot disappears), and clicking a dot navigates to
// the constituency leaf route.
//
// Why `body` and `margin-band` narrowing (not `reservation`): the
// W2b loader projects `reservation` from `datasets/data/entities/
// electoral.csv`, but that column is empty for every row today; the
// reservation chip therefore narrows to zero rows. The body chip
// (>parliament/assembly) and margin-band chips DO narrow against real
// per-row data, so the assertions never depend on the placeholder
// reservation enum.

import { expect, test } from "@playwright/test";

test("scatter renders on national event view + body filter narrows", async ({
  page,
}) => {
  await page.goto("/t/elections/general-2024", {
    waitUntil: "domcontentloaded",
  });

  // Scatter mounts: SVG + at least one dot.
  await expect(page.getByTestId("scatter-chart")).toBeVisible({
    timeout: 15_000,
  });
  const dots = page.locator('[data-testid^="scatter-dot-"]');
  await expect(dots.first()).toBeVisible({ timeout: 15_000 });

  // National general-2024 = 543 PCs; allow for the loader's null-arm
  // guard to drop a handful with missing margin_pct / turnout_pct.
  const all_count = await dots.count();
  expect(all_count).toBeGreaterThanOrEqual(540);

  // Narrow to margin band <2% — a real subset, never the full 543.
  await page.getByTestId("scatter-filter-margin-band-lt2").click();
  await page.waitForTimeout(150);
  const lt2_count = await dots.count();
  expect(lt2_count).toBeLessThan(all_count);
  expect(lt2_count).toBeGreaterThan(0);

  // Reset margin filter, then change body to assembly: should narrow to
  // zero (this national view loads parliament-only via the W2b loader's
  // NATIONAL-PC dispatch; every projected datum has body=parliament).
  await page.getByTestId("scatter-filter-margin-band-all").click();
  await page.waitForTimeout(150);
  await page.getByTestId("scatter-filter-body-assembly").click();
  await page.waitForTimeout(150);
  await expect(page.getByTestId("scatter-empty")).toBeVisible();

  // Back to parliament and click one dot — verify navigation to the
  // constituency leaf.
  await page.getByTestId("scatter-filter-body-parliament").click();
  await page.waitForTimeout(150);
  const dot = dots.first();
  await dot.click();
  await expect(page).toHaveURL(/\/elections\/general-2024\/[a-z0-9-]+/, {
    timeout: 10_000,
  });
});

test("scatter renders on state event view with state filter pre-applied", async ({
  page,
}) => {
  await page.goto("/karnataka/elections/assembly-2023", {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("scatter-chart")).toBeVisible({
    timeout: 15_000,
  });
  const dots = page.locator('[data-testid^="scatter-dot-"]');
  await expect(dots.first()).toBeVisible({ timeout: 15_000 });

  // Karnataka has 224 ACs in the 2008-delim corpus; the W2b loader
  // emits one per row, then the scatter drops any with null
  // turnout_pct / margin_pct. Allow some slack.
  const count = await dots.count();
  expect(count).toBeGreaterThanOrEqual(200);

  // Body chip should be pre-set to "assembly" by the route (StateElection
  // syncs it via `$effect`). Switching to parliament should empty the
  // chart (loader is assembly-scoped).
  await page.getByTestId("scatter-filter-body-parliament").click();
  await page.waitForTimeout(150);
  await expect(page.getByTestId("scatter-empty")).toBeVisible();
});
