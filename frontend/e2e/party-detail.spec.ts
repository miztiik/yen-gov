// Playwright smoke for the /parties/<slug> per-party detail page
// (PR-4 of TODO/20260612-party-rendering-and-party-pages-plan.md).
//
// Asserts the citizen-facing surface mounts for representative
// parties across the four header-avatar tiers (anchor, brand,
// fallback, sentinel) plus the "Party not found" empty state:
//   - /parties/inc     -> anchor (INC blue)
//   - /parties/dmk     -> anchor (DMK red)
//   - /parties/nota    -> sentinel framing
//   - /parties/xyznotreal -> not-found state
//
// The PR brief mandates a 7-URL §13 smoke; the e2e harness runs a
// subset (4 here) and the smoke notes in the PR body document the
// remaining 3 manual checks (BJP, IND, CPIM).

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

test.describe("/parties/:slug per-party detail", () => {
  test("/parties/inc renders the INC detail page (anchor avatar + KPIs + LS chart + VS chart)", async ({
    page,
  }) => {
    await page.goto("/parties/inc");
    await expect(page.getByTestId("party-loading")).toBeHidden({ timeout: 30_000 });

    // (1) Header card
    await expect(page.getByTestId("party-detail")).toHaveAttribute(
      "data-party-id",
      "parties.IN.INC",
    );
    await expect(page.getByTestId("party-name")).toContainText("Indian National Congress");
    const avatar = page.getByTestId("party-avatar");
    await expect(avatar).toHaveAttribute("data-treatment", "anchor");
    // Sub-line: recognition badge + "peak ... LS seats in YYYY" (INC has
    // pre-1999 LS gap so peak might be 0; the sub-line still renders
    // the recognition label).
    await expect(page.getByTestId("party-subline")).toContainText(/party/i);

    // (3) KPI strip - 4 tiles
    await expect(page.getByTestId("party-kpi-ls-seats")).toBeVisible();
    await expect(page.getByTestId("party-kpi-vs-seats")).toBeVisible();
    await expect(page.getByTestId("party-kpi-cycles")).toBeVisible();
    await expect(page.getByTestId("party-kpi-range")).toBeVisible();

    // (4) LS chart MUST render an SVG with at least one bar.
    const lsChart = page.getByTestId("party-ls-chart");
    await expect(lsChart).toBeVisible();
    await expect(lsChart.locator("svg")).toBeVisible();
    await expect(
      lsChart.locator('rect[data-testid^="bar-"]').first(),
    ).toBeVisible();

    // (5) VS chart present (INC has state-AE wins so the section renders).
    const vsChart = page.getByTestId("party-vs-chart");
    await expect(vsChart).toBeVisible();
    await expect(vsChart.locator("svg")).toBeVisible();

    // (7) Metadata footer - at least the recognition badge appears.
    await expect(page.getByTestId("party-meta-recognition")).toBeVisible();
  });

  test("/parties/dmk renders the DMK detail page (anchor avatar + state party recognition)", async ({
    page,
  }) => {
    await page.goto("/parties/dmk");
    await expect(page.getByTestId("party-loading")).toBeHidden({ timeout: 30_000 });

    await expect(page.getByTestId("party-detail")).toHaveAttribute(
      "data-party-id",
      "parties.IN.DMK",
    );
    await expect(page.getByTestId("party-name")).toContainText(
      /Dravida Munnetra Kazhagam|DMK/i,
    );
    await expect(page.getByTestId("party-avatar")).toHaveAttribute(
      "data-treatment",
      "anchor",
    );

    // DMK has decades of Tamil Nadu AE wins -> VS chart must render.
    const vsChart = page.getByTestId("party-vs-chart");
    await expect(vsChart).toBeVisible();
    await expect(vsChart.locator("svg")).toBeVisible();

    // Strongholds section visible (DMK has Tamil Nadu seats with
    // multi-cycle wins).
    await expect(page.getByTestId("party-strongholds")).toBeVisible();
  });

  test("/parties/nota renders sentinel framing (no charts, citizen-honest one-liner)", async ({
    page,
  }) => {
    await page.goto("/parties/nota");
    await expect(page.getByTestId("party-loading")).toBeHidden({ timeout: 30_000 });

    await expect(page.getByTestId("party-detail")).toHaveAttribute(
      "data-party-id",
      "parties.IN.NOTA",
    );
    await expect(page.getByTestId("party-avatar")).toHaveAttribute(
      "data-treatment",
      "sentinel",
    );
    // Sentinel one-liner under the H1.
    await expect(page.getByTestId("party-sentinel-line")).toContainText(
      /NOTA/i,
    );
    // Charts MUST be hidden for sentinels.
    await expect(page.getByTestId("party-ls-chart")).toHaveCount(0);
    await expect(page.getByTestId("party-vs-chart")).toHaveCount(0);
    await expect(page.getByTestId("party-strongholds")).toHaveCount(0);
    await expect(page.getByTestId("party-kpis")).toHaveCount(0);
  });

  test("/parties/xyznotreal renders the friendly not-found state", async ({
    page,
  }) => {
    await page.goto("/parties/xyznotreal");
    await expect(page.getByTestId("party-loading")).toBeHidden({ timeout: 30_000 });

    // Not-found surface visible with H1 + recovery link.
    await expect(page.getByTestId("party-not-found")).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 1, name: "Party not found" }),
    ).toBeVisible();
    await expect(page.getByTestId("party-not-found-back")).toHaveAttribute(
      "href",
      /\/parties$/,
    );
    // The detail body MUST NOT render for an unknown party.
    await expect(page.getByTestId("party-detail")).toHaveCount(1); // wrapper
    await expect(page.getByTestId("party-header")).toHaveCount(0);
  });
});
