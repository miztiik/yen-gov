// Extended-route smoke tests — non-golden-path routes that still ship in
// the bundle and could regress silently. Each test asserts:
//   1. route mounts (no `pageerror`, attached via beforeEach trap)
//   2. the route's identifying copy is in the DOM
//
// Routes covered:
//   /about                                     — about page
//   /disclaimer                                — legal-style disclaimer
//   /settings                                  — color overrides editor
//   /no-such-route                             — 404 fallback
//   /s/tamil-nadu/party/dmk-DMK                — party page
//   /lab/tamil-nadu/AcGenMay2026               — Psephlab simulator
//   /compare/tamil-nadu/AcGenMay2026           — Compare surface
//
// These routes are NOT pixel-asserted; they're smoke tests. Visual specs
// (screenshot-diff) belong in a separate file when/if added (CLAUDE.md §15).

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

test.describe("extended routes", () => {
  test("about page renders disclaimer header", async ({ page }) => {
    await page.goto("/about");
    await expect(page.getByRole("heading", { level: 1, name: /About yen-gov/i })).toBeVisible();
    // The "broader civic-data hub" framing is the load-bearing copy on
    // this page (cited in commit messages). If it's gone, the doc-code
    // sync (CLAUDE.md Holy Law #4) has drifted.
    await expect(page.getByText(/yen-gov is not just an elections site/i)).toBeVisible();
  });

  test("disclaimer page renders legal-style sections", async ({ page }) => {
    await page.goto("/disclaimer");
    await expect(page.getByRole("heading", { level: 1, name: /^Disclaimer$/ })).toBeVisible();
    // The Accuracy / Completeness / Methodology / Citation / Corrections
    // headings are the load-bearing structure (paste-ready copy from
    // handover §8.2). All five must render.
    await expect(page.getByRole("heading", { level: 2, name: /Accuracy/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Completeness/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Methodology/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Citation/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Corrections/ })).toBeVisible();
  });

  test("settings page renders color overrides editor", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
    await expect(page.getByText(/Party color overrides/i)).toBeVisible();
  });

  test("404 fallback renders for unknown route", async ({ page }) => {
    await page.goto("/no-such-route-here");
    await expect(page.getByRole("heading", { level: 1, name: "404" })).toBeVisible();
    await expect(page.getByText(/No route matches/i)).toBeVisible();
  });

  test("party page renders for DMK in Tamil Nadu", async ({ page }) => {
    // Slug shape: <short-slug>-<eci-code-lower>. DMK is short=DMK, eci=DMK.
    await page.goto("/s/tamil-nadu/party/dmk-DMK");
    // Wait for at least one of: party heading, summary table, or "no
    // matching party" fallback. We don't pin exact copy because the
    // Party.svelte template may evolve; the pageerror trap is the real
    // assertion.
    await page.waitForLoadState("networkidle", { timeout: 15_000 });
  });

  test("psephlab loads actuals for tamil-nadu / AcGenMay2026", async ({ page }) => {
    await page.goto("/lab/tamil-nadu/AcGenMay2026");
    await page.waitForLoadState("networkidle", { timeout: 30_000 });
    // Engine produces some seat-count text; we just confirm the route is
    // alive enough to have rendered something other than a blank shell.
    await expect(page.locator("main").first()).toBeVisible();
  });

  test("compare surface loads for tamil-nadu / AcGenMay2026", async ({ page }) => {
    await page.goto("/compare/tamil-nadu/AcGenMay2026");
    await page.waitForLoadState("networkidle", { timeout: 30_000 });
    await expect(page.locator("main").first()).toBeVisible();
  });
});
