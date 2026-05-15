// Phase 3.1 vertical — prices topic e2e smoke.
//
// Asserts the catalogue → render → honesty-component pipeline end-to-end:
//   1. /t lists the new "Prices and inflation" topic card with the right
//      indicator count (drift detector covers presence; this covers the
//      citizen-visible label).
//   2. /t/prices route mounts without pageerror.
//   3. The Union-list framing banner (Hans's mis-framing guard) renders.
//   4. The Phase 2 RebaseBanner shows up on the WPI section (value_kind =
//      "index", series_breaks contains rebases) — this is the headline
//      proof that the renderer-primitive → honesty-component → catalogue
//      wiring is live, not just present in code.
//   5. Phase 2 DirectionLegendCue renders for at least one chart's
//      legend (all prices indicators are direction=neutral, so we assert
//      the "neither direction is good or bad" copy).
//   6. SourceList (provenance per CLAUDE.md §12) renders for at least one
//      artifact.
//
// The matching transport + health verticals share the same wiring path;
// they get smoke coverage via golden-path/extended-routes once they
// stabilise.

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

test.describe("topic: prices", () => {
  test("/t lists the prices topic card", async ({ page }) => {
    await page.goto("/t");
    await expect(
      page.getByRole("heading", { level: 3, name: /Prices and inflation/i }),
    ).toBeVisible();
    // Indicator count is part of the card copy. If this drifts, either
    // the catalogue lost an artifact or TopicIndex's count rendering
    // regressed.
    await expect(page.getByText(/7 indicators/i).first()).toBeVisible();
  });

  test("/t/prices renders title, list-badge, and Union-list framing", async ({ page }) => {
    await page.goto("/t/prices");
    await expect(
      page.getByRole("heading", { level: 1, name: /Prices and inflation/i }),
    ).toBeVisible();
    // Hans's mis-framing guard: monetary policy is centre/RBI, ranking
    // states by inflation misleads → topic.list = "union" surfaces this
    // banner. If list classification drifts to "state" or the banner
    // template changes, this catches it.
    await expect(page.getByText(/Union-list subject/i)).toBeVisible();
    await expect(
      page.getByText(/administered by the Government of India/i).first(),
    ).toBeVisible();
  });

  test("RebaseBanner renders on the WPI index series", async ({ page }) => {
    await page.goto("/t/prices");
    // WPI has series_breaks with kind="rebase" at four points; the
    // RebaseBanner should report the count and most-recent at_time.
    // We don't pin the exact at_time string (the artifact may add
    // future rebases) — only the "Rebased N times" stem.
    //
    // The WPI section sits 6th of 7 on a long page. We assert
    // toBeAttached (DOM presence) rather than toBeVisible because the
    // banner is far below the fold and may not be in the viewport on
    // mobile profiles — the contract is "renderer wired the component
    // for value_kind=index", which DOM presence proves.
    await expect(
      page.getByText(/Rebased \d+ times? — most recent at/i).first(),
    ).toBeAttached({ timeout: 30_000 });
  });

  test("DirectionLegendCue surfaces neutral framing on a prices chart", async ({ page }) => {
    await page.goto("/t/prices");
    // All prices indicators have direction=neutral (inflation isn't
    // unambiguously good or bad — disinflation can mean weak demand,
    // higher inflation can erode savings). DirectionLegendCue must say so.
    await expect(
      page.getByText(/neither direction is good or bad/i).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("provenance (sources) renders for at least one prices artifact", async ({ page }) => {
    await page.goto("/t/prices");
    // SourceList renders the upstream URL chip per Holy Law #9 / §12.
    // Any prices artifact should show its CMIE / RBI / NSO source link.
    await expect(
      page.getByText(/Source/i).first(),
    ).toBeVisible({ timeout: 15_000 });
  });
});
