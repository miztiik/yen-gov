// Playwright smoke for the /parties index page (PR-3 of
// TODO/20260612-party-rendering-and-party-pages-plan.md).
//
// Asserts the citizen-facing surface mounts, fetches parties.csv, and
// the three input axes (search box, recognition chip, letter rail)
// each measurably narrow the visible row count. Clicking an INC pill
// must navigate to `/parties/inc`. UNK must NEVER appear (filtered
// out at the loader boundary).
//
// Test isolation: each test starts on /parties; the test runner
// guarantees a fresh browser context so the module-level cache in
// `loadAllParties()` is reset between tests.

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

test.describe("/parties index", () => {
  test("renders the H1 + at least one party row + INC pill", async ({ page }) => {
    await page.goto("/parties");
    await expect(page.getByRole("heading", { level: 1, name: "Parties" })).toBeVisible();

    // The index must load and render rows; wait for the loading sentinel
    // to disappear so the loader has resolved.
    await expect(page.getByTestId("parties-loading")).toBeHidden({ timeout: 15_000 });

    // INC row links to /parties/inc and carries the INC pill text.
    const incLink = page.locator('a[data-party-id="parties.IN.INC"]');
    await expect(incLink).toBeVisible();
    await expect(incLink).toHaveAttribute("href", /\/parties\/inc$/);
  });

  test("UNK is filtered out (no /parties/unk citizen page)", async ({ page }) => {
    await page.goto("/parties");
    await expect(page.getByTestId("parties-loading")).toBeHidden({ timeout: 15_000 });
    // The UNK sentinel must NEVER appear as a citizen entity.
    const unk = page.locator('a[data-party-id="parties.IN.UNK"]');
    await expect(unk).toHaveCount(0);
  });

  test("search box narrows the visible rows", async ({ page }) => {
    await page.goto("/parties");
    await expect(page.getByTestId("parties-loading")).toBeHidden({ timeout: 15_000 });
    const totalBefore = await page.locator('a[data-party-id]').count();
    expect(totalBefore).toBeGreaterThan(100); // baseline canonical store has 2000+ parties

    await page.getByTestId("parties-search").fill("DMK");
    // Give the reactive pipeline a tick to settle; the assertion implicitly waits.
    await expect.poll(async () => page.locator('a[data-party-id]').count())
      .toBeLessThan(totalBefore);
    const totalAfter = await page.locator('a[data-party-id]').count();
    expect(totalAfter).toBeGreaterThan(0);
    expect(totalAfter).toBeLessThan(totalBefore);
    // DMK row remains visible.
    await expect(page.locator('a[data-party-id="parties.IN.DMK"]')).toBeVisible();
  });

  test('recognition chip "State" narrows the count', async ({ page }) => {
    await page.goto("/parties");
    await expect(page.getByTestId("parties-loading")).toBeHidden({ timeout: 15_000 });
    const allCount = await page.locator('a[data-party-id]').count();

    await page.locator('button[data-chip-key="state"]').click();
    // After the chip click the count drops AND the State chip becomes active.
    await expect(page.locator('button[data-chip-key="state"]'))
      .toHaveAttribute("data-chip-active", "true");
    await expect.poll(async () => page.locator('a[data-party-id]').count())
      .toBeLessThan(allCount);
  });

  test('letter rail jump anchor "D" reaches the D section', async ({ page }) => {
    await page.goto("/parties");
    await expect(page.getByTestId("parties-loading")).toBeHidden({ timeout: 15_000 });
    const dAnchor = page.locator('a[data-letter-anchor="letter-d"]');
    await expect(dAnchor).toBeVisible();
    await dAnchor.click();
    // The H2 with id="letter-d" must exist and (via scroll-mt-4) be on screen.
    await expect(page.locator('h2#letter-d')).toBeInViewport();
  });

  test("clicking an INC pill navigates to /parties/inc", async ({ page }) => {
    await page.goto("/parties");
    await expect(page.getByTestId("parties-loading")).toBeHidden({ timeout: 15_000 });
    await page.locator('a[data-party-id="parties.IN.INC"]').click();
    await expect(page).toHaveURL(/\/parties\/inc$/);
  });
});
