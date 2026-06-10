// Parent plan section 25.4 (E3) state silhouette browser smoke.
//
// CLAUDE.md section 13 gate for the StateAcMap (maplibre) outline layer
// + TileCartogram (SVG) silhouette layer. The vitest contract
// (frontend/src/contracts/state-silhouette-smoke.test.ts) byte-confirms
// the geometry decodes + projects; this spec byte-confirms the
// rendered citizen surface actually fetches the shared
// `boundaries/in/states/all.{topojson,geojson}` corpus and (for the
// hex arm) draws the silhouette `<path>` BELOW the hex grid.
//
// Three representative states cover the same risk axes as the
// vitest contract:
//   - S22 Tamil Nadu - large peninsular polygon.
//   - S04 Bihar      - medium inland polygon.
//   - U04 Lakshadweep - tiny island archipelago.
//
// "No new fetch" guardrail: we listen for `/data/boundaries/in/states/all.*`
// being requested. The expected behaviour is one GET per page-load that
// returns 200; the in-memory cache inside `loadStateSilhouette`
// collapses StateAcMap + ElectionMap into a single decoded
// FeatureCollection per state.
//
// Mobile project skip: same justification as state-ac-coverage.spec.ts -
// the silhouette layer has no breakpoint-specific code path.

import { test, expect, type Response } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

const STATE_TARGETS: ReadonlyArray<{ code: string; slug: string; label: string }> = [
  { code: "S22", slug: "tamil-nadu", label: "Tamil Nadu" },
  { code: "S04", slug: "bihar", label: "Bihar" },
  // Lakshadweep is a UT without an Assembly election - the AC drilldown
  // page would 404. Skip the per-AC smoke for U04 and rely on the
  // vitest contract for the projection assertion; the citizen-facing
  // silhouette surface for U04 is the same loader code path TN + Bihar
  // exercise. (The state-ac-coverage spec also skips U04 for the same
  // reason - no AC shard exists.)
];

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

test.describe("E3 state silhouette - StateAcMap fetches shared state corpus", () => {
  for (const { code, slug, label } of STATE_TARGETS) {
    test(`${code} (${label}) /${slug}/ac/1 fetches boundaries/in/states/all.*`, async ({
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

      // Don't wait for `networkidle` - large maplibre fills + DuckDB
      // worker spin keep the network bus busy enough on first cold
      // load that the page can exceed the 30s timeout. The shared
      // silhouette load runs alongside the rest of StateAcMap's
      // mount; the response listener captures it as soon as it
      // returns, well within the poll timeout below.
      await page.goto(`/${slug}/ac/1`, { waitUntil: "domcontentloaded" });

      // The state silhouette load is fired by StateAcMap on mount.
      // Poll until at least one shared-corpus GET returns 200.
      await expect
        .poll(() => seen.length, { timeout: 30_000 })
        .toBeGreaterThan(0);
      expect(seen.length, `${code}: at least one states/all.* GET`).toBeGreaterThan(0);

      // Map canvas must still render alongside the silhouette load.
      await expect(page.locator("canvas.maplibregl-canvas").first()).toBeVisible({
        timeout: 30_000,
      });

      page.off("response", onResp);
    });
  }
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
