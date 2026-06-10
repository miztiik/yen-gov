// home-elections-rail.spec.ts (PR-W4d, 2026-06-10)
//
// Playwright smoke for the 3-card elections rail mounted on Home (`/`).
// Two-phase load contract:
//   - Fast phase (catalogue only, ~200ms): anchor + door cards render
//     with a degraded "Latest event highlights" hook.
//   - Refine phase (NATIONAL-PC DuckDB-WASM, 10-30s cold): hook silently
//     upgrades to "<year>'s closest seat: <constituency> - margin X%".
// This spec asserts the fast-phase contract (the rail mounts + cards
// route correctly); refine-phase content is exercised by the view-model
// unit tests, not here.

import { expect, test } from "@playwright/test";

test.describe("Home elections rail (PR-W4d)", () => {
  // The IndiaMap on Home is slow to hydrate (maplibre + topojson decode)
  // even though the rail itself paints at catalogue speed. The default
  // 30s per-test timeout is enough for catalogue + DOM mount; bumping
  // to 60s gives headroom for the IndiaMap chrome around the rail.
  test.describe.configure({ timeout: 60_000 });

  test("renders 3 cards with non-empty content and correct hrefs", async ({ page }) => {
    await page.goto("/");

    // Fast-phase contract: rail mounts within 30s of catalogue resolving.
    const rail = page.getByTestId("home-elections-rail");
    await rail.waitFor({ state: "visible", timeout: 30_000 });

    const anchor = page.getByTestId("rail-anchor");
    const hook = page.getByTestId("rail-hook");
    const door = page.getByTestId("rail-door");

    await expect(anchor).toBeVisible();
    await expect(hook).toBeVisible();
    await expect(door).toBeVisible();

    // Anchor: title shape "Parliament <year>" + subtitle "National results".
    const anchorText = (await anchor.innerText()).trim();
    expect(anchorText).toMatch(/Parliament \d{4}/);
    expect(anchorText).toContain("National results");
    const anchorHref = await anchor.getAttribute("href");
    expect(anchorHref).toMatch(/^\/t\/elections\/[a-z0-9-]+$/);

    // Hook: title contains "closest seat" once refined OR "Parliament <year>"
    // while degraded. Subtitle non-empty in both arms.
    const hookText = (await hook.innerText()).trim();
    expect(hookText.length).toBeGreaterThan(20);
    const hookHref = await hook.getAttribute("href");
    // Either /<state>/elections/<event> (closest race) OR /t/elections/<event> (degraded).
    expect(hookHref).toMatch(/^\/([a-z0-9-]+\/elections\/[a-z0-9-]+|t\/elections\/[a-z0-9-]+)$/);

    // Door: routes to firehose.
    await expect(door).toContainText(/All elections/);
    expect(await door.getAttribute("href")).toBe("/t/elections");
  });

  test("anchor card navigates to the national event view", async ({ page }) => {
    await page.goto("/");
    const anchor = page.getByTestId("rail-anchor");
    await anchor.waitFor({ state: "visible", timeout: 30_000 });

    await Promise.all([
      page.waitForURL(/\/t\/elections\/[a-z0-9-]+$/, { timeout: 30_000 }),
      anchor.click(),
    ]);
    expect(page.url()).toMatch(/\/t\/elections\/[a-z0-9-]+$/);
  });

  test("door card navigates to /t/elections firehose", async ({ page }) => {
    await page.goto("/");
    const door = page.getByTestId("rail-door");
    await door.waitFor({ state: "visible", timeout: 30_000 });

    await Promise.all([
      page.waitForURL(/\/t\/elections$/, { timeout: 30_000 }),
      door.click(),
    ]);
    expect(page.url()).toMatch(/\/t\/elections$/);
  });
});
