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

// National Lok Sabha PC atlas (PR-B4). LsGenJun2024 PC results were ingested
// in PR-A4, so the choropleth lights up with winners + a seat-total bar.
const NATIONAL_ROUTE = "/t/elections/LsGenJun2024";

test("@elections national PC atlas renders results + toggles to the equal-seats cartogram", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    // The generic "Failed to load resource … 404" console line carries no URL;
    // 404s are vetted precisely by the response handler below, so skip it here
    // to avoid double-counting the expected optional-manifest 404.
    if (msg.type() === "error" && !/Failed to load resource.*404/.test(msg.text())) {
      errors.push(msg.text());
    }
  });
  page.on("response", (r) => {
    // The optional PMTiles boundary manifest is absent until vector tiles
    // ship; sources.ts resolves its 404 to null and falls back to GeoJSON,
    // so this specific 404 is an expected part of the contract, not a fault.
    if (r.status() === 404 && !r.url().endsWith("/boundaries/in/manifest.json")) {
      errors.push(`404 ${r.url()}`);
    }
  });

  await page.goto(NATIONAL_ROUTE);

  await expect(
    page.getByRole("heading", {
      name: "National results — Parliamentary Constituencies",
    }),
  ).toBeVisible();

  // PC winners light up the seat-total bar (PR-A4 ingested LsGenJun2024).
  // The national scan spans every state shard of election_results (~1.6M
  // rows) plus a DuckDB-WASM cold start, so allow a generous first paint.
  await expect(
    page.locator('[data-testid="national-seat-total-bar"]'),
  ).toBeVisible({ timeout: 30000 });

  // Geographic arm is the default.
  await expect(
    page.locator('[data-testid="national-election-map-geo"]'),
  ).toBeVisible();

  // Switch to the equal-seats cartogram → 545 national PC tiles.
  const toggle = page.locator('[data-testid="election-map-toggle"]');
  await toggle.locator('[data-view="hex"]').click();
  await expect(page).toHaveURL(/[?&]view=hex/);
  const hex = page.locator('[data-testid="national-election-map-hex"]');
  await expect(hex.locator("svg polygon")).toHaveCount(545);

  expect(errors).toEqual([]);
});

// Election time-slider (PR-B6). Maharashtra (S13) has 14 assembly events on
// record, so the snapping slider renders and scrubbing it to a different
// stop re-points the route's :event segment (URL = single source of truth).
test("@elections election time-slider snaps the map to another election year", async ({
  page,
}) => {
  await page.goto(ROUTE);

  const slider = page.locator('[data-testid="election-time-slider"]');
  await expect(slider).toBeVisible();

  const input = page.locator('[data-testid="election-time-slider-input"]');
  // AcGenOct2019 is stop index 12 of 14 (0-based); the most-recent stop
  // (index 13) is AcGenNov2024.
  await expect(input).toHaveValue("12");

  // Scrub to the most-recent election — the slider SNAPS to a real event and
  // the route's :event segment changes; no interpolation between years.
  await input.fill("13");
  await expect(page).toHaveURL(/\/s\/maharashtra\/elections\/AcGenNov2024/);

  // The slider re-derives its index from the new URL event.
  await expect(input).toHaveValue("13");
  await expect(
    page.locator('[data-testid="election-time-slider-active"]'),
  ).toContainText("2024");
});

// Filter rail (PR-B8). Changing the colour-by mode and the margin band
// writes the choice to the URL query, and reloading that shared URL
// reproduces the same screen (URL = single source of truth).
test("@elections filter rail reflects colour-by + margin band in the URL and a shared URL reproduces it", async ({
  page,
}) => {
  await page.goto(ROUTE);

  const rail = page.locator('[data-testid="election-filter-rail"]');
  await expect(rail).toBeVisible();

  // F3 — recolour by margin (always available).
  await page
    .locator('[data-testid="election-colour-mode"]')
    .selectOption("margin");
  await expect(page).toHaveURL(/[?&]mode=margin/);

  // F2 — margin band "Close" dims the landslide seats.
  await page.locator('[data-testid="election-margin-band"] [data-band="lt2"]').click();
  await expect(page).toHaveURL(/[?&]margin=lt2/);

  // Reset chip appears with the active-filter count and clears everything.
  const reset = page.locator('[data-testid="election-filter-reset"]');
  await expect(reset).toContainText("2");

  // A fresh load of the shared URL reproduces the same controls.
  const shared = new URL(page.url());
  await page.goto(shared.pathname + shared.search);
  await expect(page.locator('[data-testid="election-colour-mode"]')).toHaveValue(
    "margin",
  );
  await expect(
    page.locator('[data-testid="election-margin-band"] [data-band="lt2"]'),
  ).toHaveAttribute("aria-pressed", "true");
});

