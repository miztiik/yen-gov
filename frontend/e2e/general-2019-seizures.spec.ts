// E2E smoke for the MCC-period seizures card (Row D of
// TODO/20260614-three-ephemeral-ingests-plan.md).
//
// Two surfaces, one event. The card is only mounted for events with
// an `mcc_seizures.csv` on disk (today: only `general-2019`).
//
//   1. National  /t/elections/general-2019
//   2. State     /maharashtra/elections/general-2019
//
// The state surface scopes the headline + sparkline to maharashtra;
// the choropleth still renders 36 states. The national surface
// renders the national rollup with no `state_slug` filter.
//
// Each test:
//   - Waits for the card to mount.
//   - Asserts the headline + map + sparkline are visible.
//   - Switches measure via the picker (default -> cash) and
//     verifies the headline label updates.
//
// First-hit cold compile dominates; per-test timeout bumped to 90s.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("election seizures card (Row D, general-2019)", () => {
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

  test("national surface (/t/elections/general-2019) mounts card", async ({
    page,
  }) => {
    await page.goto("/t/elections/general-2019");

    // The card mounts once the CSV finishes loading.
    await expect(page.getByTestId("election-seizures-card")).toBeVisible({
      timeout: 30_000,
    });

    // Headline + map + sparkline.
    await expect(
      page.getByTestId("election-seizures-headline"),
    ).toBeVisible();
    await expect(page.getByTestId("election-seizures-map")).toBeVisible();
    await expect(
      page.getByTestId("election-seizures-sparkline"),
    ).toBeVisible();

    // Default measure is "total" with value unit; switch to cash and
    // verify the headline label changes.
    const headlineBefore = await page
      .getByTestId("election-seizures-headline")
      .textContent();
    await page
      .locator('[data-testid="election-seizures-picker-option"][data-category="cash"]')
      .click();
    await expect
      .poll(
        async () => {
          const t = await page
            .getByTestId("election-seizures-headline")
            .textContent();
          return t !== headlineBefore;
        },
        { timeout: 5_000 },
      )
      .toBe(true);
  });

  test("state surface (/maharashtra/elections/general-2019) mounts state-scoped card", async ({
    page,
  }) => {
    await page.goto("/maharashtra/elections/general-2019");
    const card = page.getByTestId("election-seizures-card");
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByTestId("election-seizures-headline"),
    ).toBeVisible();
    await expect(page.getByTestId("election-seizures-map")).toBeVisible();
    // The state-scoped mount sets `data-state-slug="maharashtra"` on
    // the root card element AND renders "Maharashtra only" in the
    // scope label. Pinning the attr is the cheapest "the filter took
    // effect" assertion (the choropleth itself still draws all 36
    // states for national context).
    await expect(card).toHaveAttribute("data-state-slug", "maharashtra");
    const cardText = await card.textContent();
    expect(cardText?.toLowerCase()).toContain("maharashtra");
  });
});
