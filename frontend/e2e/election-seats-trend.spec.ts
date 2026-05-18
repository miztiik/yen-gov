// Election seat-composition trend — the chronological StackedTrend wired
// into the state hub. Assam (S03) has three result.summary.json files on
// record (Apr 2016, Apr 2021, May 2026), so it's the canonical state for
// proving the chart mounts with multiple bars and surfaces provenance.

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

test.describe("election seats trend", () => {
  test("assam (S03) renders the chronological seat-composition section", async ({ page }) => {
    await page.goto("/s/assam");
    await expect(
      page.getByRole("heading", { name: /Seat composition over time/i }),
    ).toBeVisible({ timeout: 20_000 });
    // Provenance row is rendered by StackedTrend. SourceList now sits
    // inside the AboutThisData <details> accordion (default collapsed),
    // so it is attached to the DOM but not visible until the citizen
    // opens the disclosure. CLAUDE.md §15 only requires the surface
    // exists. Mirrors golden-path.spec.ts:108.
    await expect(page.getByText(SOURCE_LIST_TEXT).first()).toBeAttached({ timeout: 15_000 });
  });
});
