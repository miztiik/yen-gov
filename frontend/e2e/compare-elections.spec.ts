// E2E smoke for the path-form compare cascade (PR-W4b, 2026-06-10).
//
// Surface under test: `/compare/elections/<state>/<from>/<to>` -
// IndiaVotes-style winner-change table with KPIs + filter chips.
//
// Oracle: for `/compare/elections/tamil-nadu/general-2014/general-2019`,
// the on-disk parliament summaries carry 26 TN PCs in each year
// (verified against `datasets/elections/parliament/election=2014/summary.csv`
// + `=2019/summary.csv`; TN's full 39-PC slate only landed in the 2024
// vintage on disk). The 2014->2019 swing in TN is the textbook
// AIADMK -> DMK-led alliance flip: 25 of the 26 comparable PCs change
// hands. The spec floors at >= 20 rows + >= 15 flips to ride above the
// actual on-disk counts (26 / 25) with margin.
//
// Plus the project-wide page-error trap (`attachPageErrorTrap`) which
// surfaces uncaught exceptions + console.error + `/data/` requestfailed
// events while filtering the graceful-degradation 404-as-null pattern
// (ADR-0014) and maplibre's teardown AbortError.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("compare elections (PR-W4b path-form cascade)", () => {
  // First-hit cold compile (vite-plugin-svelte + DuckDB-WASM worker)
  // takes ~30s warm + >60s on Windows; two parallel loaders compound
  // that. Bump the describe timeout in line with `national-event-view`
  // (the other DuckDB-heavy spec).
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

  test("renders KPIs + winner-change table for TN general-2014 vs general-2019", async ({
    page,
  }) => {
    await page.goto(
      "/compare/elections/tamil-nadu/general-2014/general-2019",
    );

    // Page wrapper visible immediately.
    await expect(page.getByTestId("compare-elections")).toBeVisible();

    // Data-arrival oracle: the table mounts only after BOTH loaders
    // resolve and compare_rows populates. Use the table container as the
    // ready signal (30s for the parallel DuckDB-WASM cold path).
    await expect(page.getByTestId("compare-elections-table")).toBeVisible({
      timeout: 30_000,
    });

    // KPI strip visible (carries data after the table mounts).
    await expect(page.getByTestId("compare-elections-kpis")).toBeVisible();

    // The badges for from + to events are visible.
    await expect(
      page.getByTestId("compare-elections-from-badge"),
    ).toBeVisible();
    await expect(
      page.getByTestId("compare-elections-to-badge"),
    ).toBeVisible();

    // Row floor: >= 20 rows. TN carries 26 PCs in both 2014 + 2019
    // parliament data on disk; the floor at 20 absorbs any future
    // pruning while still proving the join populated.
    const rows = page.locator('[data-testid^="compare-row-"]');
    const row_count = await rows.count();
    expect(
      row_count,
      `Expected >= 20 compare rows for TN 2014->2019; got ${row_count}`,
    ).toBeGreaterThanOrEqual(20);

    // Flip floor: >= 15 flips. The 2014->2019 TN swing (AIADMK ->
    // DMK-led alliance) flipped 25 of 26 comparable PCs on disk. 15 is
    // a defensive floor; any future re-ingest that preserves the swing
    // direction will pass.
    const flips_text = await page
      .getByTestId("compare-elections-kpi-flips")
      .textContent();
    const flips = parseInt((flips_text ?? "0").replace(/[^0-9]/g, ""), 10);
    expect(
      flips,
      `Expected >= 15 flips for TN 2014->2019; got ${flips}`,
    ).toBeGreaterThanOrEqual(15);
  });

  test("filter chip narrows the table to flips only", async ({ page }) => {
    await page.goto(
      "/compare/elections/tamil-nadu/general-2014/general-2019",
    );
    await expect(page.getByTestId("compare-elections-table")).toBeVisible({
      timeout: 30_000,
    });

    const all_rows = await page
      .locator('[data-testid^="compare-row-"]')
      .count();
    expect(all_rows).toBeGreaterThanOrEqual(20);

    // Apply the Flips filter.
    await page.getByTestId("compare-elections-filter-flips").click();

    const flips_only = await page
      .locator('[data-testid^="compare-row-"]')
      .count();
    expect(flips_only).toBeGreaterThanOrEqual(15);
    expect(flips_only).toBeLessThanOrEqual(all_rows);
  });
});
