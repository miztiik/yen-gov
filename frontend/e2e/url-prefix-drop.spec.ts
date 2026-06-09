// URL prefix-drop Phase-0 redirect smoke test (PR-P1 of
// TODO/20260609-url-prefix-drop-phase0-plan.md / ADR-0037 Phase 2-4).
//
// Covers the citizen-facing acceptance for PR-P1:
//   1. Visiting a legacy Grammar B URL (`/s/<state>/...`) flips the
//      URL bar to the Grammar A equivalent (`/<state>/...`) via the
//      `RedirectLegacyUrl.svelte` `history.replaceState` hop.
//   2. The same Grammar A URL visited directly renders the same page
//      with no redirect (URL bar stays put).
//   3. Both grammars route to the same component - tested by smoke-
//      asserting that the resulting page contains the expected
//      identifying copy (state name in <h1>) regardless of entry URL.
//   4. No `pageerror` is thrown during the redirect hop.
//
// Out of scope (PR-P2 / PR-P3 cover these):
//   - AC slug shape change (`167-mylapore` -> `mylapore`).
//   - Internal `<a href>` migration from `url.*` (Grammar B) to
//     `link.*` (Grammar A). Existing anchors still emit Grammar B URLs
//     after PR-P1; clicking one triggers the redirect (intentional
//     one-hop overhead until PR-P2 sweeps the callers).

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual(
    [],
  );
});

test.describe("URL prefix drop - Phase 0 (PR-P1)", () => {
  test("/s/tamil-nadu redirects to /tamil-nadu (URL bar flips)", async ({
    page,
  }) => {
    await page.goto("/s/tamil-nadu");
    // The on-mount replaceState fires synchronously after Svelte
    // mounts the component, so by the time we get back to here the URL
    // should already be Grammar A.
    await expect(page).toHaveURL(/\/tamil-nadu$/);
    // The page should render StateOverview (Tamil Nadu is the state).
    await expect(
      page.getByRole("heading", { level: 1, name: /Tamil Nadu/i }),
    ).toBeVisible();
  });

  test("/tamil-nadu renders directly (no redirect, URL bar stays)", async ({
    page,
  }) => {
    await page.goto("/tamil-nadu");
    await expect(page).toHaveURL(/\/tamil-nadu$/);
    await expect(
      page.getByRole("heading", { level: 1, name: /Tamil Nadu/i }),
    ).toBeVisible();
  });

  test("/s/tamil-nadu/t/elections redirects to /tamil-nadu/t/elections", async ({
    page,
  }) => {
    await page.goto("/s/tamil-nadu/t/elections");
    await expect(page).toHaveURL(/\/tamil-nadu\/t\/elections$/);
    // StateTopic for elections should render the topic title or its
    // identifying copy.
    await expect(
      page.getByRole("heading", { level: 1 }).first(),
    ).toBeVisible();
  });

  test("/tamil-nadu/t/elections renders directly (no redirect)", async ({
    page,
  }) => {
    await page.goto("/tamil-nadu/t/elections");
    await expect(page).toHaveURL(/\/tamil-nadu\/t\/elections$/);
    await expect(
      page.getByRole("heading", { level: 1 }).first(),
    ).toBeVisible();
  });

  test("/s/karnataka/elections/AcGenMay2023 redirects to /karnataka/elections/AcGenMay2023", async ({
    page,
  }) => {
    await page.goto("/s/karnataka/elections/AcGenMay2023");
    await expect(page).toHaveURL(/\/karnataka\/elections\/AcGenMay2023$/);
  });

  test("/s/tamil-nadu/party/dmk-DMK redirects to /tamil-nadu/party/dmk-DMK", async ({
    page,
  }) => {
    await page.goto("/s/tamil-nadu/party/dmk-DMK");
    await expect(page).toHaveURL(/\/tamil-nadu\/party\/dmk-DMK$/);
  });

  test("/s/tamil-nadu/explore redirects to /tamil-nadu/explore", async ({
    page,
  }) => {
    await page.goto("/s/tamil-nadu/explore");
    await expect(page).toHaveURL(/\/tamil-nadu\/explore$/);
  });

  test("/s/tamil-nadu/d/chennai redirects to /tamil-nadu/d/chennai", async ({
    page,
  }) => {
    await page.goto("/s/tamil-nadu/d/chennai");
    await expect(page).toHaveURL(/\/tamil-nadu\/d\/chennai$/);
  });

  test("/s/tamil-nadu/ac/167-mylapore redirects preserving the AC slug shape", async ({
    page,
  }) => {
    // PR-P1 does NOT collapse `167-mylapore` -> `mylapore`; PR-P2 ships
    // that. This test pins the byte-for-byte path preservation through
    // PR-P1's `/s/*` redirect. After that hop the bare-AC convenience
    // entry then chains via ADR-0052 to the canonical event-nested URL
    // (`/<state>/elections/<default-event>/ac/<ac>`); that second hop is
    // pre-existing behaviour and out of PR-P1 scope. We assert only
    // that the final URL preserves the prefixed `167-mylapore` slug.
    await page.goto("/s/tamil-nadu/ac/167-mylapore");
    await expect(page).toHaveURL(/\/ac\/167-mylapore$/);
    // Confirm the leading `/s/` is gone (the PR-P1 redirect fired).
    await expect(page).not.toHaveURL(/\/s\//);
  });

  test("query string is preserved across the redirect", async ({ page }) => {
    await page.goto("/s/karnataka?yg_variant=treatment");
    await expect(page).toHaveURL(/\/karnataka\?yg_variant=treatment$/);
  });

  test("chrome routes are not poached by the /:state catch-all", async ({
    page,
  }) => {
    // The 1-segment Grammar A `/:state` catch-all comes AFTER every
    // chrome literal in the route table. Disjointness contract
    // guarantees no state slug equals a chrome token. Smoke this end-to-
    // end so a future route-ordering regression fails loud.
    await page.goto("/about");
    await expect(page).toHaveURL(/\/about$/);
    await expect(
      page.getByRole("heading", { level: 1, name: /About yen-gov/i }),
    ).toBeVisible();

    await page.goto("/disclaimer");
    await expect(page).toHaveURL(/\/disclaimer$/);
    await expect(
      page.getByRole("heading", { level: 1, name: /^Disclaimer$/ }),
    ).toBeVisible();

    await page.goto("/t");
    await expect(page).toHaveURL(/\/t$/);

    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings$/);
  });
});
