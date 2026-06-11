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

    // Default availability is "Has data" (PR 2026-06-11 firehose-honesty
    // fix), which hides the ~210 rows the catalogue declares
    // pending_upstream. Today the catalogue exposes 101 has-data rows
    // (4 collapsed Parliament events + 97 Assembly events); future
    // ingest PRs only grow this floor.
    const all_count = await rows.count();
    expect(
      all_count,
      "default (All body + Has-data availability) should expose every ingested event",
    ).toBeGreaterThanOrEqual(100);

    await filter.getByRole("button", { name: /^Assembly$/ }).click();
    const assembly_count = await rows.count();
    expect(assembly_count).toBeGreaterThanOrEqual(90);
    expect(assembly_count).toBeLessThan(all_count);

    await filter.getByRole("button", { name: /^All$/ }).click();
    const restored_count = await rows.count();
    expect(restored_count).toBe(all_count);
  });

  test("default hides pending_upstream events and the toggle reveals them with a Pending badge", async ({
    page,
  }) => {
    // PR 2026-06-11 (firehose-honesty fix): the catalogue carries
    // data_status="pending_upstream" for events whose per-event CSVs are
    // not on disk yet. The firehose:
    //   1. defaults to "Has data" availability filter -> those rows are
    //      hidden so the citizen does not read "error" badges as
    //      "yen-gov broken".
    //   2. exposes an "All including pending" toggle that brings them
    //      back, rendered with a slate "Pending" badge (never amber
    //      "error" text).
    //   3. fires zero network requests for the pending rows -- the
    //      catalogue's data_status is the pre-skip signal so no
    //      summary.csv 404 ever lands.

    const summary_requests: string[] = [];
    page.on("request", (req) => {
      const url = req.url();
      if (url.includes("/elections/") && url.endsWith("/summary.csv")) {
        summary_requests.push(url);
      }
    });

    await page.goto("/t/elections");
    await expect(page.getByTestId("elections-firehose-table")).toBeVisible({
      timeout: 30_000,
    });

    const rows = page.locator('[data-testid^="firehose-row-"]');
    const default_count = await rows.count();

    // Toggle to "All including pending" — row count must grow.
    const availability = page.getByTestId("firehose-availability-filter");
    await availability
      .getByRole("button", { name: /^All including pending$/ })
      .click();

    const expanded_count = await rows.count();
    expect(
      expanded_count,
      `expected pending-included view (${expanded_count}) to exceed has-data-only view (${default_count})`,
    ).toBeGreaterThan(default_count);

    // The new view should expose >= 1 Pending badge — the catalogue
    // currently declares ~210 pending events; today only the slate
    // "Pending" badge is visible (never amber "error" text for these).
    const pending_badges = page.getByTestId("firehose-pending-badge");
    await expect(pending_badges.first()).toBeVisible({ timeout: 15_000 });
    const pending_count = await pending_badges.count();
    expect(pending_count).toBeGreaterThan(0);

    // Restore default filter and assert NO summary.csv was fetched for
    // a known-pending event. The 1999/2004 Parliament cohort is the
    // simplest case: those years have no parliament/election=YYYY/
    // directory on disk; the pre-skip MUST keep them silent.
    await availability.getByRole("button", { name: /^Has data$/ }).click();
    await expect(rows).toHaveCount(default_count);

    // After a small settle window every catalogue-declared pending row
    // must have been pre-skipped — no summary.csv 404 may have landed
    // for parliament/election=1999/ or parliament/election=2004/.
    await page.waitForTimeout(500);
    const pending_year_404s = summary_requests.filter(
      (u) =>
        u.includes("parliament/election=1999/") ||
        u.includes("parliament/election=2004/"),
    );
    expect(
      pending_year_404s,
      `pre-skip leaked: catalogue-declared pending parliament events triggered summary.csv fetches:\n${pending_year_404s.join("\n")}`,
    ).toEqual([]);
  });
});
