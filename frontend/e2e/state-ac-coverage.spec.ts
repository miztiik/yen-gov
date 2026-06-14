// state-ac-coverage e2e spec.
//
// Phase A.4 of docs/archive/plans/20260529-boundary-rip-and-replace-plan.md.
//
// Per-state Playwright coverage matrix that asserts every state's AC
// choropleth on the state-election page renders correctly. This is the citizen-facing
// counterpart to the unit-level `state-ac-registry-coverage.test.ts`
// contract: the unit test asserts the STATE_AC registry covers every
// on-disk shard; THIS spec asserts the end-to-end pathway (state event
// page + D3/SVG map mount + boundary fetch) works on the
// live frontend.
//
// Default invocation runs a 5-code canary subset (CANARY_CODES below)
// that protects each distinct AC-shard shape (ordinary LGD,
// LGD-with-rewrite, district-fallback, elected UT, non-LGD seat_id).
// The full 31-code matrix runs on demand via `AC_COVERAGE_FULL=1`,
// scheduled nightly and on path-filtered PRs in
// .github/workflows/e2e-ac-full.yml. Per
// docs/archive/plans/20260531-e2e-runtime-trim-plan.md PR-2 - keeping the per-PR
// gate cheap while preserving exhaustive coverage as a time-based
// safety net. States whose latest Assembly event is still
// `pending_upstream` fall back to their newest complete Assembly event;
// states with no complete Assembly event are skipped explicitly because
// the state-election page does not mount the AC map until result rows exist.
//
// State-code lists are INLINED here (not imported from sources.ts).
// The vitest contract `state-ac-registry-coverage.test.ts` enforces
// `STATE_AC keys === on-disk-shard set`; adding a new state to that
// set requires updating BOTH the registry AND `FULL_CODES` below.
// The duplication is intentional - it makes the e2e test independent
// of the production module graph and surfaces accidental drift as a
// missing test, not a silent skip.
//
// Per-state assertions (all must pass for the state to be "green"):
//   1. Page mounts without pageerror / requestfailed for /data/...
//   2. State-election H1 is non-empty and the map section mounts.
//   3. D3 SVG map mounts and renders at least one AC feature path.
//   4. The map's own GET request for the boundary shard returns 200.
//      We listen via `page.waitForResponse` (set up BEFORE goto) rather
//      than firing a manual fetch - manual `fetch(method:"HEAD")` from
//      page context triggers a `requestfailed` because Vite's
//      `serveDatasets()` middleware (vite.config.ts) only handles GET.
//      A HEAD probe would also fail in CI for the same reason. Hooking
//      the existing map-triggered GET avoids both problems and verifies
//      the EXACT same fetch the citizen-facing render makes. TopoJSON
//      siblings now exist for AC shards (ADR-0047), so the accepted
//      request is either `.topojson` or the GeoJSON fallback.
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

interface ElectionEventRow {
  event_id: string;
  kind: string;
  display: string;
  polled_on: string;
  data_status?: string;
}

interface ElectionEventsCatalogue {
  states: Record<string, ElectionEventRow[]>;
}

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const entitiesPath = resolve(repoRoot, "datasets", "taxonomy", "entities.json");
const electionEventsPath = resolve(repoRoot, "datasets", "taxonomy", "election_events.json");

const entities = (
  JSON.parse(readFileSync(entitiesPath, "utf-8")) as { entities: EntityRow[] }
).entities;
const electionEvents = JSON.parse(
  readFileSync(electionEventsPath, "utf-8"),
) as ElectionEventsCatalogue;

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

function defaultAssemblyEvent(code: string): ElectionEventRow | null {
  const rows = electionEvents.states[code] ?? [];
  const assemblyRows = rows.filter(
    (r) => r.kind === "assembly" && r.data_status !== "pending_upstream",
  );
  const candidates = assemblyRows.length > 0 ? assemblyRows : rows;
  if (candidates.length === 0) return null;
  return candidates.reduce((latest, row) =>
    row.polled_on > latest.polled_on ? row : latest,
  );
}

// State / UT codes for which `boundaries/electoral/delim=2008/ac/state=<lgd-slug>/all.geojson`
// exists on disk after A.2 (31 entries; the boundaries/in/ac/... -> boundaries/electoral/delim=2008/ac/...
// rename landed in G10 of TODO/20260603-data-and-charting-platform-reset-plan.md section 4 EL2).
// Sorted lexicographically.
const FULL_CODES: readonly string[] = [
  "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08",
  "S10", "S11", "S12", "S13", "S14", "S15", "S16", "S17",
  "S18", "S19", "S20", "S21", "S22", "S23", "S24", "S25",
  "S26", "S27", "S28", "S29",
  "U05", "U07", "U08",
];

// Canary subset (5 codes) covering the representative AC-shard shapes
// across the 31-state matrix. Each canary protects a distinct risk:
//   S24 - ordinary large LGD state (Uttar Pradesh; 403 ACs)
//   S01 - LGD-with-bifurcation-rewrite (Andhra Pradesh post-2014;
//         exercises the ac_no_rewrite path)
//   S03 - district-fallback geometry (Assam; T4 district overlay,
//         no per-AC polygons in the canonical source)
//   U05 - elected UT on the ordinary path (Delhi; smaller LGD)
//   U08 - non-LGD seat_id join (J&K; exercises the U08-specific
//         seat_id-keyed boundary registry path)
// Path-filter triggers in .github/workflows/e2e-ac-full.yml run the
// full matrix on any PR that touches the files the canary cannot
// protect (sources.ts, AC shards, taxonomy, contract test). Nightly
// schedule provides a time-based safety net.
const CANARY_CODES: readonly string[] = ["S24", "S01", "S03", "U05", "U08"];

const CODES_UNDER_TEST: readonly string[] = process.env.AC_COVERAGE_FULL
  ? FULL_CODES
  : CANARY_CODES;

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
  for (const code of CODES_UNDER_TEST) {
    const slug = codeToSlug[code];
    if (!slug) {
      test(`${code}: entity lookup missing for code in entities.json`, () => {
        throw new Error(`No active entity found for code ${code} in entities.json`);
      });
      continue;
    }
    const event = defaultAssemblyEvent(code);
    if (!event || event.kind !== "assembly" || event.data_status === "pending_upstream") {
      test.skip(
        `${code}: no complete assembly event available for AC map e2e`,
        () => {},
      );
      continue;
    }

    test(`${code} (${slug}) /${slug}/elections/${event.event_id} renders AC map cleanly`, async ({ page }) => {
      // The AC boundary shard partition is keyed by the canonical LGD
      // slug (ADR-0048 LGD-canonical rename, e.g. `state=delhi`,
      // `state=uttar-pradesh`), which is NOT always the same as the
      // URL slug used for navigation (e.g. `nct-of-delhi`,
      // `jammu-and-kashmir-ut`). Rather than re-derive the partition
      // slug here, match the map's own GET for ANY AC shard returning
      // 200 — the state-election page only loads this state's shard, so the
      // first 200 match IS this state's boundary, and we verify the
      // EXACT fetch the citizen-facing render makes. TopoJSON siblings
      // exist for AC shards (ADR-0047), so accept either extension.
      const acShardRe =
        /\/data\/boundaries\/electoral\/delim=2008\/ac\/state=[^/]+\/all\.(topojson|geojson)(\?|$)/;
      // Set up the shard-response listener BEFORE navigation so the
      // map's own GET is captured by the same Promise we await later.
      const shardResponsePromise = page
        .waitForResponse(
          (r) =>
            r.request().method() === "GET" &&
            r.status() === 200 &&
            acShardRe.test(r.url()),
          { timeout: 30_000 },
        )
        .catch(() => null);

      await page.goto(`/${slug}/elections/${encodeURIComponent(event.event_id)}`);
      await page.waitForLoadState("networkidle", { timeout: 30_000 });

      // State-election page must resolve to real event chrome.
      const h1 = page.locator("h1").first();
      await expect(h1).toBeVisible({ timeout: 15_000 });
      const heading = (await h1.textContent())?.trim() ?? "";
      expect(heading.length, `${code}: H1 should be non-empty`).toBeGreaterThan(0);
      await expect(page.getByTestId("state-event-map")).toBeVisible({
        timeout: 15_000,
      });

      // D3 SVG map must mount and render constituency features.
      const svg = page.getByTestId("state-event-map-geo").locator("svg").first();
      await expect(svg).toBeVisible({
        timeout: 15_000,
      });
      await expect
        .poll(
          async () => page.locator(".state-ac-map-d3__feature").count(),
          { timeout: 15_000 },
        )
        .toBeGreaterThan(0);

      // Boundary shard load (via the map's own GET, captured above).
      const shardResponse = await shardResponsePromise;
      expect(
        shardResponse,
        `${code}: map did not request /data/boundaries/electoral/delim=2008/ac/state=<lgd-slug>/all.{topojson,geojson}`,
      ).not.toBeNull();
      expect(shardResponse?.status(), `${code}: shard load failed`).toBe(200);
    });
  }
});
