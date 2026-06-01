// Elections atlas smoke (UK-style elections plan, PR-B3+). Tagged
// @elections so it can be run/skipped as a cohort separate from the
// golden path. Drives the state assembly results map+toggle.
//
// Pinned surface: Maharashtra (S13) AcGenOct2019 — S13 is the pilot hex
// layout (288 ACs) AND has 288 AC winners on disk, so BOTH the geographic
// arm and the equal-seats cartogram render real data.

import { test, expect } from "@playwright/test";

const ROUTE = "/s/maharashtra/elections/AcGenOct2019";

test("@elections state election map toggles geo <-> equal-seats and persists to URL", async ({
  page,
}) => {
  await page.goto(ROUTE);

  // The map section + segmented toggle are present; default arm is geo.
  await expect(page.getByRole("heading", { name: "Results map" })).toBeVisible();
  const toggle = page.locator('[data-testid="election-map-toggle"]');
  await expect(toggle).toBeVisible();
  await expect(page.locator('[data-testid="election-map-geo"]')).toBeVisible();

  // Switch to the equal-seats cartogram.
  await toggle.locator('[data-view="hex"]').click();
  await expect(page).toHaveURL(/[?&]view=hex/);

  // The cartogram paints one <polygon> per Maharashtra AC (288).
  const hex = page.locator('[data-testid="election-map-hex"]');
  await expect(hex.locator("svg polygon")).toHaveCount(288);

  // Switch back to the geographic map — the ?view=hex param is dropped.
  await toggle.locator('[data-view="geo"]').click();
  await expect(page).not.toHaveURL(/[?&]view=hex/);
  await expect(page.locator('[data-testid="election-map-geo"]')).toBeVisible();
});

test("@elections selecting a seat on the cartogram navigates to that constituency", async ({
  page,
}) => {
  await page.goto(`${ROUTE}?view=hex`);

  const hex = page.locator('[data-testid="election-map-hex"]');
  await expect(hex.locator("svg polygon").first()).toBeVisible();

  await hex.locator("svg polygon").first().click();

  // Clicking a tile drills into the AC detail route for this state.
  await expect(page).toHaveURL(/\/s\/maharashtra\/ac\/\d+/);
});
