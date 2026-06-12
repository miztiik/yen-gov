// Playwright e2e for the Scatter chart (PR-W4c, 2026-06-10).
//
// Smokes the brief's G2 + G4 gates: scatter mounts on both the national
// event view and the state event view, filter narrowing works on the
// `body` chip (>=1 dot disappears), and clicking a dot navigates to
// the constituency leaf route.
//
// Why `body` and `margin-band` narrowing (not `reservation`): the
// W2b loader projects `reservation` from `datasets/data/entities/
// electoral.csv`, but that column is empty for every row today; the
// reservation chip therefore narrows to zero rows. The body chip
// (parliament/assembly) and margin-band chips DO narrow against real
// per-row data, so the assertions never depend on the placeholder
// reservation enum.
//
// Why `force: true` on the dot click: the scatter packs many overlapping
// large circles (the largest PCs by electors sit on top of each other in
// the high-turnout / wide-margin corner). Playwright's actionability
// check legitimately reports "X intercepts pointer events" because the
// nominally-first dot in document order may be visually beneath a larger
// dot. The bypass is fine for the routing assertion: we are testing that
// clicking ANY dot navigates correctly, not which specific dot.

import { expect, test } from "@playwright/test";

test("scatter renders on national event view + margin filter narrows + dot click drills in", async ({
  page,
}) => {
  await page.goto("/t/elections/general-2024", {
    waitUntil: "domcontentloaded",
  });

  // Scatter mounts: SVG + at least one dot.
  await expect(page.getByTestId("scatter-chart")).toBeVisible({
    timeout: 15_000,
  });
  const dots = page.locator('[data-testid^="scatter-dot-"]');
  await expect(dots.first()).toBeVisible({ timeout: 15_000 });

  // National general-2024 = 543 PCs; allow for the loader's null-arm
  // guard to drop a handful with missing margin_pct / turnout_pct.
  const all_count = await dots.count();
  expect(all_count).toBeGreaterThanOrEqual(540);

  // Narrow to margin band <2% — a real subset, never the full 543.
  await page.getByTestId("scatter-filter-margin-band-lt2").click();
  await page.waitForTimeout(150);
  const lt2_count = await dots.count();
  expect(lt2_count).toBeLessThan(all_count);
  expect(lt2_count).toBeGreaterThan(0);

  // TODO/20260612 Row A.5 + E: the Body chip is HIDDEN on the
  // national-event surface (lock_body=true) - the body is already
  // fixed by the route (parliament-only via the W2b loader's
  // NATIONAL-PC dispatch). Confirm the chip is absent so a future
  // refactor cannot silently re-leak it.
  await expect(
    page.getByTestId("scatter-filter-body-all"),
  ).toHaveCount(0);
  await expect(
    page.getByTestId("scatter-filter-body-parliament"),
  ).toHaveCount(0);
  await expect(
    page.getByTestId("scatter-filter-body-assembly"),
  ).toHaveCount(0);

  // Reset margin filter, then click a dot — verify navigation to the
  // constituency leaf. force:true bypasses the overlapping-circles
  // actionability check.
  await page.getByTestId("scatter-filter-margin-band-all").click();
  await page.waitForTimeout(150);
  await dots.first().click({ force: true });
  await expect(page).toHaveURL(/\/elections\/general-2024\/[a-z0-9-]+/, {
    timeout: 10_000,
  });
});

test("scatter renders on state event view with state filter pre-applied + lock_body hides Body chip + responsive width", async ({
  page,
}) => {
  // TODO/20260612 set the viewport to the max-w-6xl class width so we
  // can assert the SVG fills the container responsively (Row A.4).
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/karnataka/elections/assembly-2023", {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("scatter-chart")).toBeVisible({
    timeout: 15_000,
  });
  const dots = page.locator('[data-testid^="scatter-dot-"]');
  await expect(dots.first()).toBeVisible({ timeout: 15_000 });

  // Karnataka has 224 ACs in the 2008-delim corpus; the W2b loader
  // emits one per row, then the scatter drops any with null
  // turnout_pct / margin_pct. Allow some slack.
  const count = await dots.count();
  expect(count).toBeGreaterThanOrEqual(200);

  // TODO/20260612 Row A.5: the Body chip is HIDDEN on state-event
  // surfaces (lock_body=true) - the body is already fixed by the URL,
  // so the chip would only let citizens toggle to an inactive body
  // that empties the chart. Both body chips must not be visible.
  await expect(
    page.getByTestId("scatter-filter-body-assembly"),
  ).toHaveCount(0);
  await expect(
    page.getByTestId("scatter-filter-body-all"),
  ).toHaveCount(0);

  // TODO/20260612 Row A.4: the SVG width binds to the wrapper's
  // clientWidth. On a 1280px viewport with the page's max-w-6xl
  // container (1152px) + padding, the SVG should occupy at least 900px.
  const svg_width = await page
    .getByTestId("scatter-chart")
    .evaluate((el) => Number((el as SVGSVGElement).getAttribute("width")));
  expect(svg_width).toBeGreaterThan(900);

  // TODO/20260612 Row A.3: Y-axis ticks adapt to the data range. For
  // Karnataka AE 2023 the max winning margin sits around 60-70%, so
  // computeYMax should cap the Y-axis well below 100. Assert the
  // top-most Y tick label is below 100% so the chart isn't wasting
  // canvas on empty upper range.
  const y_tick_labels = page.locator(
    '[data-testid="scatter-chart"] text[text-anchor="end"]',
  );
  const labels = await y_tick_labels.allTextContents();
  const nums = labels
    .map((l) => Number.parseInt(l.replace("%", "").trim(), 10))
    .filter((n) => Number.isFinite(n));
  expect(nums.length).toBeGreaterThan(0);
  const max_y = Math.max(...nums);
  expect(max_y).toBeLessThan(100);
});
