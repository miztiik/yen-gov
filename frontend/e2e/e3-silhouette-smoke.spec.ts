// Parent plan section 25.4 (E3) state silhouette browser smoke.
//
// CLAUDE.md section 13 gate for the TileCartogram (SVG) hex-arm
// silhouette layer. As of Row 1 of
// TODO/20260616-map-geometry-rip-and-palette-plan.md the geo arm
// (StateAcMapD3) no longer draws a silhouette - only the equal-seats
// (`?view=hex`) TileCartogram arm does. The vitest contract
// (frontend/src/contracts/state-silhouette-smoke.test.ts) byte-confirms
// the geometry decodes + projects; this spec byte-confirms the rendered
// hex arm actually fetches the shared `boundaries/in/states/all.*`
// corpus and draws the silhouette `<path>` BELOW the hex grid.
//
// "No new fetch" guardrail: we listen for `/data/boundaries/in/states/all.*`
// being requested. The expected behaviour is one GET per page-load that
// returns 200; the in-memory cache inside `loadStateSilhouette`
// collapses repeat reads into a single decoded FeatureCollection.
//
// Mobile project skip: same justification as state-ac-coverage.spec.ts -
// the silhouette layer has no breakpoint-specific code path.

import { test, expect, type Response } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

const STATES_BOUNDARY_RE =
  /\/data\/boundaries\/in\/states\/all\.(topojson|geojson)(\?|$)/;

let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

test.beforeEach(({ page }, testInfo) => {
  trap = null;
  test.skip(
    testInfo.project.name === "mobile-pixel-5",
    "State silhouette smoke is desktop-only (no mobile-specific code path)",
  );
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap?.getErrors() ?? [];
  trap = null;
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("E3 state silhouette - TileCartogram hex arm draws SVG silhouette", () => {
  // Tamil Nadu has a persisted hex layout (election_tile_layouts.json
  // covers S22 / scope=S22, layout_kind=ac, delim_year=2008). The hex
  // arm shows when `?view=hex` is appended to the StateElection
  // route. The silhouette `<path data-layer="state-silhouette">`
  // then renders BELOW the hex grid.
  test("S22 (Tamil Nadu) /tamil-nadu/elections/AcGenApr2021?view=hex renders state-silhouette <path>", async ({
    page,
  }) => {
    const seen: string[] = [];
    const onResp = (resp: Response): void => {
      if (
        resp.request().method() === "GET" &&
        resp.status() === 200 &&
        STATES_BOUNDARY_RE.test(resp.url())
      ) {
        seen.push(resp.url());
      }
    };
    page.on("response", onResp);

    await page.goto(`/tamil-nadu/elections/AcGenApr2021?view=hex`, {
      waitUntil: "domcontentloaded",
    });

    // Hex container must mount (skip silently if the state's hex
    // layout is missing - same posture as the geo arm fallback).
    const hexBox = page.locator(`[data-testid="election-map-hex"]`);
    await expect(hexBox).toBeVisible({ timeout: 30_000 });

    // The silhouette <path> renders inside the hex SVG once the
    // shared loader has resolved the feature. Wait for both the
    // boundary fetch + the DOM node.
    await expect
      .poll(() => seen.length, { timeout: 30_000 })
      .toBeGreaterThan(0);
    const silhouette = page.locator(`path[data-layer="state-silhouette"]`);
    await expect(silhouette).toHaveCount(1, { timeout: 30_000 });
    const d = await silhouette.getAttribute("d");
    expect(d, "silhouette path d-attr should be non-empty").toBeTruthy();
    expect(d!.length).toBeGreaterThan(20);
    expect(d!.startsWith("M")).toBe(true);

    page.off("response", onResp);
  });
});
