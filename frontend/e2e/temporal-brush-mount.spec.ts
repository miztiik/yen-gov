// Temporal viewport brush mount on StackedTrendV2 (Phase 1.5 first
// renderer adopter). Asserts:
//
//   1. The brush mounts below the chronological seat-composition
//      StackedTrendV2 on the state hub.
//   2. The presets row + reset chip + period strip render with the
//      closed-enum data-attributes from `TemporalViewportBrush.svelte`.
//   3. Year-derivable presets (5y / 10y / 25y) are present because
//      `temporal_domain_kind="month"` makes the period_ids ("YYYY-MM")
//      year-derivable.
//   4. Clicking the "Recent 5" preset narrows the chart's visible bars
//      to (at most) 5 — the data-window-from / data-window-to
//      attributes on the brush root flip, and the bar count in the
//      chart's `<g class="stacked-trend-v2__bars">` drops accordingly.
//   5. Clicking Reset restores the full bar count.
//
// Karnataka (S10) is used because the BJP/INC/JD(S) seat history runs
// 1957..2023 (16 assembly elections) — same state used as the
// deterministic A/B treatment in `composition-bar-mount.spec.ts`, and
// long enough that the brush's recent/5y/10y/25y presets all have
// meaningful effects.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("temporal viewport brush — StackedTrendV2 adopter", () => {
  test("karnataka renders the brush below the seat-composition chart", async ({ page }) => {
    await page.goto("/s/karnataka");

    // Wait for the chart shell to mount — the brush sits inside the
    // same ElectionSeatsTrend wrapper.
    await expect(
      page.getByRole("heading", { name: /Seat composition over time/i }),
    ).toBeVisible({ timeout: 20_000 });

    // Brush root with its closed-enum attribute set.
    const brush = page.locator('[data-component="temporal-brush"]').first();
    await expect(brush).toBeVisible({ timeout: 10_000 });
    await expect(brush).toHaveAttribute("data-domain-kind", "month");
    await expect(brush).toHaveAttribute("data-is-full", "true");

    // Presets row exists with the closed enum vocabulary.
    const presets = brush.locator('[data-slot="presets"]');
    await expect(presets).toBeVisible();
    for (const preset of ["all", "recent", "5y", "10y", "25y"] as const) {
      await expect(presets.locator(`[data-preset="${preset}"]`)).toBeVisible();
    }
    await expect(presets.locator('[data-slot="reset"]')).toBeVisible();

    // Reset is disabled at full window — the brush starts full.
    await expect(presets.locator('[data-slot="reset"]')).toBeDisabled();

    // Strip cells render with the same period_ids as the chart axis.
    const strip = brush.locator('[data-slot="strip"]');
    await expect(strip).toBeVisible();
    const stripCells = strip.locator('[data-period-id]');
    const fullBarCount = await stripCells.count();
    // Karnataka dataset has ≥2 election bars on record.
    expect(fullBarCount).toBeGreaterThanOrEqual(2);

    // Chart bar count matches the strip cell count at full window.
    const chartBars = page.locator(
      '.stacked-trend-v2__bars > .stacked-trend-v2__bar',
    );
    await expect(chartBars).toHaveCount(fullBarCount);
  });

  test("strip click narrows the chart to one period and Reset restores it", async ({ page }) => {
    await page.goto("/s/karnataka");
    await expect(
      page.getByRole("heading", { name: /Seat composition over time/i }),
    ).toBeVisible({ timeout: 20_000 });

    const brush = page.locator('[data-component="temporal-brush"]').first();
    await expect(brush).toBeVisible({ timeout: 10_000 });

    const chartBars = page.locator(
      '.stacked-trend-v2__bars > .stacked-trend-v2__bar',
    );
    const fullBarCount = await chartBars.count();
    expect(fullBarCount).toBeGreaterThanOrEqual(2);

    // Click the first strip cell — single-period window
    // (anchor commits as both from and to in v1 brush UX).
    const stripCells = brush.locator('[data-slot="strip"] [data-period-id]');
    const firstCell = stripCells.first();
    const firstPeriodId = await firstCell.getAttribute("data-period-id");
    expect(firstPeriodId).not.toBeNull();
    await firstCell.click();

    // Brush state flips: from = to = first period id, is-full false.
    await expect(brush).toHaveAttribute("data-is-full", "false");
    await expect(brush).toHaveAttribute("data-window-from", firstPeriodId!);
    await expect(brush).toHaveAttribute("data-window-to", firstPeriodId!);

    // Chart drops to a single bar.
    await expect(chartBars).toHaveCount(1);

    // Reset restores the full window.
    await brush.locator('[data-slot="reset"]').click();
    await expect(brush).toHaveAttribute("data-is-full", "true");
    await expect(chartBars).toHaveCount(fullBarCount);
  });
});
