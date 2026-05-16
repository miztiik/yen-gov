// /data-completeness smoke test (folded-indicator PR, commit 10).
//
// Asserts the citizen-facing transparency surface mounts, fetches the
// completeness index (`/data/reference/in/indicators-completeness.json`),
// and renders at least one row with a `stub` documentation badge — the
// load-bearing reality today (110/110 indicators are documentation_status
// `stub` after the v1.5→v2.0 auto-fold). When editors start authoring
// methodology, those counts will shift; this test only requires the
// PAGE to render rows and the BADGE vocabulary to remain ("stub"
// appears somewhere on the page).

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

test("data-completeness page renders index", async ({ page }) => {
  await page.goto("/data-completeness");
  await expect(page.getByRole("heading", { level: 1, name: /Data completeness/i })).toBeVisible();
  const table = page.getByTestId("indicators-table");
  await expect(table).toBeVisible();
  // At least one row carries a `stub` documentation_status badge today.
  await expect(table.getByText("stub", { exact: true }).first()).toBeVisible();
});
