// URL prefix-drop post-P4 tombstone-behavior contract
// (TODO/20260609-url-prefix-drop-phase0-plan.md PR-P4 / ADR-0037 Phase 4b).
//
// PR-P4 (2026-06-10) deleted `RedirectLegacyUrl.svelte` + the `/s/*`
// route entry + the `redirect-legacy-url.ts` pure helper, completing
// the 4-phase URL-prefix-drop strangler-fig. The earlier P1 redirect
// behaviour (`/s/<state>/...` -> `/<state>/...` via `history.replaceState`)
// is GONE; legacy bookmarks now fall through to the NotFound page.
//
// This spec is the tombstone-behaviour contract: it pins the
// post-PR-P4 outcome so a future agent doesn't accidentally
// re-introduce the redirect without first updating this contract.
//
// Covers:
//   1. `/s/<state>` (1-of-many legacy shape) 404s with the NotFound
//      surface (no replaceState, no Grammar A render).
//   2. `/s/<state>/t/<topic>` (multi-segment legacy shape) also 404s.
//   3. Grammar A direct URLs (`/<state>`, `/<state>/t/<topic>`)
//      continue to render directly with no redirect.
//   4. The chrome literals stay un-poached by the Grammar A `/:state`
//      catch-all (regression guard).
//
// If this file goes red, the answer is one of:
//   * A redirect was re-introduced (read PR-P4 in the plan + undo
//     before merging).
//   * The NotFound surface copy changed (update the assertions OR
//     restore the original copy).
//   * A new chrome literal was added but not registered in the route
//     table BEFORE the Grammar A `/:state` catch-all.

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

test.describe("URL prefix drop - post-P4 tombstone behaviour", () => {
  test("/s/tamil-nadu (legacy 2-segment) falls through to NotFound (no redirect)", async ({
    page,
  }) => {
    await page.goto("/s/tamil-nadu");
    // URL bar must NOT flip (no redirect hop).
    await expect(page).toHaveURL(/\/s\/tamil-nadu$/);
    // NotFound surface must render.
    await expect(
      page.getByRole("heading", { level: 1, name: "404" }),
    ).toBeVisible();
    await expect(page.getByText(/No route matches/i)).toBeVisible();
    await expect(page.getByText(/This page has moved/i)).toBeVisible();
  });

  test("/s/karnataka/t/elections (legacy 4-segment) also falls through to NotFound", async ({
    page,
  }) => {
    await page.goto("/s/karnataka/t/elections");
    await expect(page).toHaveURL(/\/s\/karnataka\/t\/elections$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "404" }),
    ).toBeVisible();
  });

  test("/tamil-nadu (Grammar A direct) renders the state hub", async ({
    page,
  }) => {
    await page.goto("/tamil-nadu");
    await expect(page).toHaveURL(/\/tamil-nadu$/);
    await expect(
      page.getByRole("heading", { level: 1, name: /Tamil Nadu/i }),
    ).toBeVisible();
  });

  test("/tamil-nadu/t/elections (Grammar A direct) renders the state-topic page", async ({
    page,
  }) => {
    await page.goto("/tamil-nadu/t/elections");
    await expect(page).toHaveURL(/\/tamil-nadu\/t\/elections$/);
    await expect(
      page.getByRole("heading", { level: 1 }).first(),
    ).toBeVisible();
  });

  test("chrome routes are not poached by the /:state catch-all", async ({
    page,
  }) => {
    // The 1-segment Grammar A `/:state` catch-all comes AFTER every
    // chrome literal in the route table. Disjointness contract
    // guarantees no state slug equals a chrome token. Smoke this
    // end-to-end so a future route-ordering regression fails loud.
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

  test("/no-such-route falls through to NotFound (Grammar A /:state catch-all is 404-gated)", async ({
    page,
  }) => {
    // The Grammar A `/:state` route matches `/no-such-route` but
    // StateOverview.svelte's `is_unknown_state` derived gate (PR-P2
    // follow-up) re-renders the NotFound surface when `states.isLoaded
    // === true` AND `state_code === null`. This test pins that gate.
    await page.goto("/no-such-route-here");
    await expect(page).toHaveURL(/\/no-such-route-here$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "404" }),
    ).toBeVisible();
    await expect(page.getByText(/No route matches/i)).toBeVisible();
  });
});
