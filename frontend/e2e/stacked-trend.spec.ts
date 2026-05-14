// Stacked-trend route smoke: /t/energy renders the new chart, the legend,
// the unit/mode chip, and the SourceList — without runtime errors.
//
// Per CLAUDE.md §15: a citizen-visible route MUST land with at least:
//   • route loads, no `pageerror`
//   • one DOM assertion that proves the new content is there
//   • a SourceList provenance assertion (data-bearing route)

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

test.describe("stacked-trend on /t/energy", () => {
  test("renders the composed installed-capacity stacked chart", async ({ page }) => {
    await page.goto("/t/energy");
    await expect(page.getByRole("heading", { name: "Energy", level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    // Mode chip is rendered by StackedTrend.svelte once the model resolves.
    // CSS uppercases it visually, but the DOM text remains lowercase.
    await expect(page.getByText(/^percent$|^absolute$/)).toBeVisible({ timeout: 15_000 });

    // Legend includes at least one of the known fuel labels.
    await expect(page.getByText("Coal").first()).toBeVisible();

    // Provenance: the chart is data-bearing, so SourceList must appear.
    await expect(page.getByText(SOURCE_LIST_TEXT).first()).toBeVisible();
  });
});
