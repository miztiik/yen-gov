// E2E smoke for the new elections firehose (PR-W3d, 2026-06-10).
//
// Surface: `/t/elections` (firehose route registered in main.ts BEFORE
// the parameterised `/t/elections/:event`, so first-match-wins resolves
// the bare path to ElectionsFirehose.svelte).
//
// Three behaviours pinned here:
//   1. The firehose table renders with >= 6 Parliament rows after the
//      body-filter chip is clicked. The catalogue currently carries
//      6 unique general-* event_ids (1999/2004/2009/2014/2019/2024);
//      the spec's original `>= 18` floor was authored before the data
//      shape was inspected and would have failed every run. >= 6 is the
//      truth-on-disk floor; future LS backfills will only grow the
//      count.
//   2. Click-through on a Parliament row navigates to the rebuilt
//      NationalElection view at `/t/elections/<event-slug>` (W3c
//      output). Assembly rows go to `/<state>/elections/<event-slug>`
//      (StateElection; W3b not yet rebuilt but the route exists).
//   3. The page-error trap surfaces uncaught exceptions / console.error
//      / `/data/` requestfailed events. Cold compile of DuckDB-WASM
//      worker takes ~30s on Windows; the 90s describe timeout covers
//      it (matches national-event-view.spec.ts precedent).

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("elections firehose (PR-W3d)", () => {
  // Same cold-compile budget as the W3c spec (vite + duckdb-wasm worker
  // bootstrap dominate the first hit).
  test.describe.configure({ timeout: 90_000 });

  let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

  test.beforeEach(({ page }) => {
    trap = attachPageErrorTrap(page);
  });

  test.afterEach(() => {
    const errors = trap?.getErrors() ?? [];
    expect(
      errors,
      `Page emitted runtime errors:\n${errors.join("\n")}`,
    ).toEqual([]);
  });

  test("/t/elections firehose renders >= 6 Parliament events after filter", async ({
    page,
  }) => {
    await page.goto("/t/elections");

    // Table mounts as soon as the catalogue (~3 KB JSON) resolves; the
    // 30s window covers the cold vite compile.
    await expect(page.getByTestId("elections-firehose-table")).toBeVisible({
      timeout: 30_000,
    });

    // Filter to Parliament only. The catalogue carries 6 unique
    // general-* event_ids; the firehose collapses each event_id to ONE
    // "All India" row, so the filtered count is exactly 6 today (it
    // can only grow as future PRs backfill earlier LS elections).
    const filter = page.getByTestId("firehose-body-filter");
    await filter.getByRole("button", { name: /^Parliament$/ }).click();

    const rows = page.locator('[data-testid^="firehose-row-"]');
    const count = await rows.count();
    expect(
      count,
      `expected >= 6 Parliament rows after collapse, got ${count}`,
    ).toBeGreaterThanOrEqual(6);

    // Spot-check that a known event row is rendered with its expected
    // testid suffix (Parliament rows collapse to `firehose-row-<event_id>`).
    await expect(page.getByTestId("firehose-row-general-2024")).toBeVisible();
  });

  test("click-through routes a Parliament row to /t/elections/<event>", async ({
    page,
  }) => {
    await page.goto("/t/elections");
    await expect(page.getByTestId("elections-firehose-table")).toBeVisible({
      timeout: 30_000,
    });

    // Filter so the row link is unambiguous, then click the open-arrow
    // anchor on the general-2024 row (the whole-row anchor is the last
    // cell). The row itself uses `aria-label="Open <display>"` so we
    // target it via that name.
    const filter = page.getByTestId("firehose-body-filter");
    await filter.getByRole("button", { name: /^Parliament$/ }).click();

    const row = page.getByTestId("firehose-row-general-2024");
    await expect(row).toBeVisible();
    await row.getByRole("link", { name: /^Open .+ Election 2024$/i }).click();

    await expect(page).toHaveURL(/\/t\/elections\/general-2024$/);

    // Wait for the rebuilt national event view to render (its KPIs strip
    // is the load-complete oracle from PR-W3c).
    await expect(page.getByTestId("national-event-kpis")).toBeVisible({
      timeout: 30_000,
    });
  });

  test("body filter chips narrow the row count and All restores", async ({
    page,
  }) => {
    await page.goto("/t/elections");
    await expect(page.getByTestId("elections-firehose-table")).toBeVisible({
      timeout: 30_000,
    });

    const filter = page.getByTestId("firehose-body-filter");
    const rows = page.locator('[data-testid^="firehose-row-"]');

    const all_count = await rows.count();
    expect(
      all_count,
      "default (All filter) should expose every catalogue event",
    ).toBeGreaterThanOrEqual(200);

    await filter.getByRole("button", { name: /^Assembly$/ }).click();
    const assembly_count = await rows.count();
    expect(assembly_count).toBeGreaterThanOrEqual(200);
    expect(assembly_count).toBeLessThan(all_count);

    await filter.getByRole("button", { name: /^All$/ }).click();
    const restored_count = await rows.count();
    expect(restored_count).toBe(all_count);
  });
});
