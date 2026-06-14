// Functional smoke for the GitHub Pages SPA fallback.
//
// GitHub Pages serves frontend/public/404.html for unknown deep links under
// the deployed base. The shim bounces to the app shell and the boot script
// restores the original route before the router starts. In Playwright we run
// against Vite dev (see playwright.config.ts) so /data is available; the
// observable contract is still the same: fallback input -> clean URL -> page.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("GitHub Pages SPA fallback", () => {
  test.describe.configure({ timeout: 90_000 });

  test("restores a fallback deep link to the elections firehose", async ({ page }) => {
    const trap = attachPageErrorTrap(page);

    await page.goto("/?yg-redirect=%2Ft%2Felections");

    await expect(page).toHaveURL(/\/t\/elections$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "Elections firehose" }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("elections-firehose-table")).toBeVisible({
      timeout: 30_000,
    });

    expect(
      trap.getErrors(),
      `Page emitted runtime errors:\n${trap.getErrors().join("\n")}`,
    ).toEqual([]);
  });
});