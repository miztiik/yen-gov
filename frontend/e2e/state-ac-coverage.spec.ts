// state-ac-coverage e2e spec.
//
// Phase A.4 of TODO/20260529-boundary-rip-and-replace-plan.md.
//
// Per-state Playwright coverage matrix that asserts every state's AC
// drilldown page renders correctly. This is the citizen-facing
// counterpart to the unit-level `state-ac-registry-coverage.test.ts`
// contract: the unit test asserts the STATE_AC registry covers every
// on-disk shard; THIS spec asserts the end-to-end pathway (map mount
// + footer link + geojson fetch + SoT-name binding) works on the
// live frontend.
//
// State-code list is INLINED here (not imported from sources.ts).
// The vitest contract `state-ac-registry-coverage.test.ts` enforces
// `STATE_AC keys === on-disk-shard set`; adding a new state to that
// set requires updating BOTH the registry AND this constant. The
// duplication is intentional - it makes the e2e test independent of
// the production module graph and surfaces accidental drift as a
// missing test, not a silent skip.
//
// Per-state assertions (all must pass for the state to be "green"):
//   1. Page mounts without pageerror / requestfailed for /data/...
//   2. H1 is non-empty AND is NOT the literal "AC 1" placeholder -
//      it must be the resolved SoT name (e.g. "NIPPANI" for S10,
//      "BEHAT" for S24).
//   3. Map canvas (canvas.maplibregl-canvas) mounts.
//   4. Footer attribution link is the centralised A.3 link:
//      `<a href="/about?section=maps">Boundary sources & licensing</a>`.
//   5. The map's own GET request for the geojson shard returns 200.
//      We listen via `page.waitForResponse` (set up BEFORE goto) rather
//      than firing a manual fetch - manual `fetch(method:"HEAD")` from
//      page context triggers a `requestfailed` because Vite's
//      `serveDatasets()` middleware (vite.config.ts) only handles GET.
//      A HEAD probe would also fail in CI for the same reason. Hooking
//      the existing map-triggered GET avoids both problems and verifies
//      the EXACT same fetch the citizen-facing render makes.
//
// Mobile project skip: the AC drilldown's map behaviour is the same
// across viewports (no breakpoint-specific code path); running the
// 31-state matrix against `mobile-pixel-5` would double CI time
// without surfacing distinct regressions.

import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { attachPageErrorTrap } from "./_helpers";

interface EntityRow {
  entity_type: string;
  entity_code: string;
  display_name: string;
  entity_valid_to: number | null;
}

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const entitiesPath = resolve(repoRoot, "datasets", "taxonomy", "entities.json");

const entities = (
  JSON.parse(readFileSync(entitiesPath, "utf-8")) as { entities: EntityRow[] }
).entities;

const codeToSlug: Record<string, string> = {};
for (const e of entities) {
  if ((e.entity_type === "state" || e.entity_type === "ut") && e.entity_valid_to === null) {
    codeToSlug[e.entity_code] = e.display_name
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }
}

// State / UT codes for which `boundaries/in/ac/state=in_<lc>/all.geojson`
// exists on disk after A.2 (31 entries). Sorted lexicographically.
const STATE_CODES: readonly string[] = [
  "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08",
  "S10", "S11", "S12", "S13", "S14", "S15", "S16", "S17",
  "S18", "S19", "S20", "S21", "S22", "S23", "S24", "S25",
  "S26", "S27", "S28", "S29",
  "U05", "U07", "U08",
];

// `trap` is nullable + `afterEach` uses optional-chaining because
// `test.skip()` in `beforeEach` short-circuits BEFORE we assign `trap`,
// yet Playwright still runs `afterEach` for skipped tests. Without the
// guard, the mobile-pixel-5 project crashes with
// `TypeError: Cannot read properties of undefined (reading 'getErrors')`.
// Pattern mirrors `indicator-ranked-polish.spec.ts`.
let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

test.beforeEach(({ page }, testInfo) => {
  trap = null;
  test.skip(
    testInfo.project.name === "mobile-pixel-5",
    "AC coverage matrix is desktop-only (no mobile-specific map code path)",
  );
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap?.getErrors() ?? [];
  trap = null;
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("STATE_AC per-state coverage", () => {
  for (const code of STATE_CODES) {
    const slug = codeToSlug[code];
    if (!slug) {
      test(`${code}: entity lookup missing for code in entities.json`, () => {
        throw new Error(`No active entity found for code ${code} in entities.json`);
      });
      continue;
    }
    test(`${code} (${slug}) /s/${slug}/ac/1 renders cleanly`, async ({ page }) => {
      const lcCode = code.toLowerCase();
      const shardUrl = `/data/boundaries/in/ac/state=in_${lcCode}/all.geojson`;
      // Set up the shard-response listener BEFORE navigation so the
      // map's own GET is captured by the same Promise we await later.
      const shardResponsePromise = page
        .waitForResponse(
          (r) => r.url().includes(shardUrl) && r.request().method() === "GET",
          { timeout: 30_000 },
        )
        .catch(() => null);

      await page.goto(`/s/${slug}/ac/1`);
      await page.waitForLoadState("networkidle", { timeout: 30_000 });

      // H1 must resolve to a real SoT name (not the loading placeholder).
      const h1 = page.locator("h1").first();
      await expect(h1).toBeVisible({ timeout: 15_000 });
      await expect
        .poll(async () => (await h1.textContent())?.trim() ?? "", { timeout: 15_000 })
        .not.toBe("AC 1");
      const heading = (await h1.textContent())?.trim() ?? "";
      expect(heading.length, `${code}: H1 should be non-empty`).toBeGreaterThan(0);

      // Map canvas must mount.
      await expect(page.locator("canvas.maplibregl-canvas").first()).toBeVisible({
        timeout: 15_000,
      });

      // Footer attribution = centralised A.3 link.
      const attrLink = page
        .locator(`.maplibregl-ctrl-attrib-inner a[href$="/about?section=maps"]`)
        .first();
      await expect(attrLink).toHaveText(/Boundary sources & licensing/);

      // GeoJSON shard load (via the map's own GET, captured above).
      const shardResponse = await shardResponsePromise;
      expect(shardResponse, `${code}: map did not request ${shardUrl}`).not.toBeNull();
      expect(shardResponse?.status(), `${code}: shard load failed`).toBe(200);
    });
  }
});
