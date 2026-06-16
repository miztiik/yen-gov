// E2E smoke for the redesigned General-elections + Assembly-elections
// routes (PR-E4 of TODO/20260615-elections-redesign-plan.md).
//
// Replaces the deleted `elections-firehose.spec.ts`. The 315-row
// lazy-hydration firehose at `/t/elections` has been ripped + replaced
// by two routes per the user-mandated rip-and-replace doctrine:
//
//   /t/elections             -> GeneralElections.svelte (11 cycles)
//   /t/elections/assemblies  -> AssemblyElections.svelte (36+ cards)
//
// Both routes mount the shared ElectionsRouteTabs nav strip per Jony
// Section 0.1 D2 verdict.
//
// Pinned behaviours:
//   1. /t/elections renders the General-elections table with >= 6
//      Parliament cycles and the tab strip shows General as active.
//   2. /t/elections/assemblies renders >= 30 state cards + 5 no-leg
//      cards; tab strip shows Assembly as active.
//   3. Tab navigation flips between the two routes.
//   4. No `firehose` text leaks in the rendered DOM of either route.
//
// Cold-compile budget matches the W3c precedent (vite + duckdb-wasm
// worker; ~30s on Windows).

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("elections routes (PR-E4: General + Assembly)", () => {
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

  test("/t/elections renders the General-elections table + tab strip", async ({
    page,
  }) => {
    await page.goto("/t/elections");

    // Tab strip mounted above the H1
    await expect(page.getByTestId("elections-route-tabs")).toBeVisible({
      timeout: 30_000,
    });
    const generalTab = page.getByTestId("elections-route-tab-general");
    const assemblyTab = page.getByTestId("elections-route-tab-assembly");
    await expect(generalTab).toHaveAttribute("aria-current", "page");
    await expect(assemblyTab).not.toHaveAttribute("aria-current", "page");

    // Table populates from the event_summary mart shipped by PR-E2
    await expect(page.getByTestId("general-elections-table")).toBeVisible({
      timeout: 30_000,
    });
    const rows = page.locator('[data-testid^="general-elections-row-"]');
    const count = await rows.count();
    expect(
      count,
      `expected >= 6 Parliament rows, got ${count}`,
    ).toBeGreaterThanOrEqual(6);

    // The general-2024 row carries a year-link to /t/elections/general-2024
    await expect(
      page.getByTestId("general-elections-row-general-2024"),
    ).toBeVisible();
    await expect(
      page.getByTestId("general-elections-year-link-general-2024"),
    ).toHaveAttribute("href", "/t/elections/general-2024");

    // No firehose-era text leaks
    const bodyText = await page.locator("body").innerText();
    expect(bodyText.toLowerCase()).not.toContain("firehose");
  });

  test("/t/elections/assemblies renders the state-card grid + tab strip", async ({
    page,
  }) => {
    await page.goto("/t/elections/assemblies");

    // Tab strip with Assembly as the active pill
    await expect(page.getByTestId("elections-route-tabs")).toBeVisible({
      timeout: 30_000,
    });
    const assemblyTab = page.getByTestId("elections-route-tab-assembly");
    const generalTab = page.getByTestId("elections-route-tab-general");
    await expect(assemblyTab).toHaveAttribute("aria-current", "page");
    await expect(generalTab).not.toHaveAttribute("aria-current", "page");

    // Grid populates with at least 30 state cards (PR-E2 covers 30
    // states today; 5 no-leg cards always render).
    await expect(page.getByTestId("assembly-elections-grid")).toBeVisible({
      timeout: 30_000,
    });
    const cards = page.locator('[data-testid^="assembly-elections-card-"]');
    const cardCount = await cards.count();
    expect(
      cardCount,
      `expected >= 35 cards (30 with-leg + 5 no-leg), got ${cardCount}`,
    ).toBeGreaterThanOrEqual(35);

    // 5 no-legislature cards are flagged via data-no-legislature
    const noLeg = page.locator('[data-no-legislature="true"]');
    await expect(noLeg).toHaveCount(5);

    // No firehose text leaks
    const bodyText = await page.locator("body").innerText();
    expect(bodyText.toLowerCase()).not.toContain("firehose");
  });

  test("tab navigation flips between General and Assembly routes", async ({
    page,
  }) => {
    await page.goto("/t/elections");
    await expect(page.getByTestId("general-elections-table")).toBeVisible({
      timeout: 30_000,
    });

    // Click the Assembly tab; URL changes; table is replaced by grid.
    await page.getByTestId("elections-route-tab-assembly").click();
    await expect(page).toHaveURL(/\/t\/elections\/assemblies$/);
    await expect(page.getByTestId("assembly-elections-grid")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("elections-route-tab-assembly"),
    ).toHaveAttribute("aria-current", "page");

    // Click General to flip back.
    await page.getByTestId("elections-route-tab-general").click();
    await expect(page).toHaveURL(/\/t\/elections$/);
    await expect(page.getByTestId("general-elections-table")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("elections-route-tab-general"),
    ).toHaveAttribute("aria-current", "page");
  });
});
