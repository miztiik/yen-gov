// PR-12 of TODO/20260613-party-deferred-followups-plan.md section 14.
//
// Playwright e2e for the PartyStrongholdMap PC choropleth wired into
// the per-party page above the existing strongholds text list.
//
// Path-A oracle (orchestrator brief 2026-06-14): the plan-doc's
// original "22 DMK PCs from LS 2024" oracle was reframed because the
// existing strongholds mart at
// `datasets/data/marts/party_pages/strongholds.csv` is top-10 PER
// (party, body) by LIFETIME wins (backend untouched per brief). The
// per-party oracle is therefore the COUNT OF COLOURED PCs in the
// citizen-visible choropleth, verified via the per-polygon
// `data-bucket` attribute (NOT via SVG fill colour — colour-based
// counting includes the "absent" hatched polygons in some renderers;
// data-bucket is the deterministic signal per the lessons-2026-06-12
// `data-pending DOM attribute` doctrine).
//
// Per-party oracles (mart-verified 2026-06-14 against the head of
// origin/main):
//   - DMK: 10 PC strongholds in tamil-nadu (10/10 join to delim=2024)
//   - AAP: 6 PC strongholds in punjab (6/6 join)
//   - BJP: 10 PC strongholds across 4 states (10/10 join)
// One mobile-360 scenario verifies the map is hidden under the 640px
// breakpoint (Jony 2g + Citizen 3a) while the existing text list
// continues to render below.

import { test, expect, type Locator, type Page } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

async function gotoPartyAndWaitForMap(page: Page, slug: string): Promise<void> {
  // `waitUntil: 'domcontentloaded'` (not the default 'load') because
  // the delim=2024 PC topojson is ~2-3 MB on cold-load and the 'load'
  // event waits for every subresource. The party-loading sentinel +
  // strongholds section + svg waits below are the real gates.
  await page.goto(`/parties/${slug}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("party-loading")).toBeHidden({
    timeout: 30_000,
  });
  // The strongholds section must mount (precondition for our map to
  // render; the wrapper lives INSIDE it).
  await expect(page.getByTestId("party-strongholds")).toBeVisible();
  // Wait for the topojson to finish loading (the SVG only appears
  // after `collection` is set in onMount). The wrapper is `display:
  // none` under 640px so we read the SVG from the inner component.
  const svg = page.locator(
    '[data-testid="party-pc-stronghold-map"] svg',
  );
  await expect(svg).toBeVisible({ timeout: 30_000 });
}

async function countColouredPcs(page: Page): Promise<number> {
  // "Coloured" = NOT absent AND NOT zero. The component stamps
  // data-bucket="absent" for PCs not in the party's stronghold mart
  // (rendered as hatch) and data-bucket="zero" for the impossible-
  // in-practice case of contested-but-never-won (would render
  // slate-100). Both bucket values count as "no data shown to the
  // citizen", per Path-A oracle. Buckets "one" / "two" / "three-four" /
  // "five-plus" all count as coloured.
  const polys = await page
    .locator(
      '[data-testid="pc-stronghold"][data-bucket]:not([data-bucket="absent"]):not([data-bucket="zero"])',
    )
    .all();
  return polys.length;
}

test.describe("/parties/:slug PC stronghold choropleth (PR-12)", () => {
  test("DMK colours exactly 10 PCs (top-10 lifetime LS strongholds in TN)", async ({
    page,
  }) => {
    await gotoPartyAndWaitForMap(page, "dmk");

    // Path-A oracle: 10 PCs coloured. The mart's top-10 LS
    // strongholds for DMK all join to delim=2024 PC topojson
    // unique_ids (10/10 verified at dispatch time on
    // datasets/data/marts/party_pages/strongholds.csv head).
    expect(await countColouredPcs(page)).toBe(10);

    // The map wrapper must be the visible wrapper (i.e. the
    // `hidden sm:block` Tailwind doesn't apply at Desktop Chrome).
    await expect(
      page.getByTestId("party-pc-stronghold-map-wrap"),
    ).toBeVisible();

    // The citizen-honest caption is visible.
    await expect(
      page.getByTestId("party-stronghold-map-caption"),
    ).toContainText("top-10");

    // The existing strongholds text list still renders BELOW the map
    // (the PR did NOT replace it; only added above it).
    await expect(page.getByTestId("party-ls-strongholds")).toBeVisible();
  });

  test("AAP colours exactly 6 PCs (top-6 LS strongholds in Punjab)", async ({
    page,
  }) => {
    await gotoPartyAndWaitForMap(page, "aap");

    // Path-A oracle: 6 PCs coloured (AAP's mart row count is 6 for
    // body=parliament; per the dispatch probe). The mart cap is 10
    // top per body but AAP has only 6 PC wins on record because the
    // party is recent (2014 onwards) and concentrated in Punjab.
    expect(await countColouredPcs(page)).toBe(6);

    await expect(
      page.getByTestId("party-pc-stronghold-map-wrap"),
    ).toBeVisible();
    await expect(
      page.getByTestId("party-stronghold-map-caption"),
    ).toContainText("top-10");
  });

  test("BJP colours exactly 10 PCs across multiple home states", async ({
    page,
  }) => {
    await gotoPartyAndWaitForMap(page, "bjp");

    // BJP has 10 mart rows distributed across 4 states (assam,
    // bihar, goa, gujarat per dispatch probe). All 10 join to
    // delim=2024 topojson. The map is full-India crop because
    // BJP's parties.csv home_state_codes field is empty (national
    // party).
    expect(await countColouredPcs(page)).toBe(10);

    await expect(
      page.getByTestId("party-pc-stronghold-map-wrap"),
    ).toBeVisible();
    // For national parties the existing top-10 AC + LS lists stand
    // in as the per-state linkout (per orchestrator brief: deferred
    // AC choropleth + brief's "text-linkout list" framing).
    await expect(page.getByTestId("party-ls-strongholds")).toBeVisible();
    await expect(page.getByTestId("party-vs-strongholds")).toBeVisible();
  });

  test("mobile 360px viewport hides the stronghold map (Jony 2g)", async ({
    page,
  }) => {
    // Test runs against the chromium project by default; override
    // the viewport for this scenario only. The 360px width sits
    // below the Tailwind `sm:` breakpoint (640px) so the
    // `hidden sm:block` class on the wrapper resolves to
    // display: none.
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/parties/dmk", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("party-loading")).toBeHidden({
      timeout: 30_000,
    });
    await expect(page.getByTestId("party-strongholds")).toBeVisible();

    // Wrapper exists in the DOM but is display:none under 640px.
    // Use `toBeHidden` rather than asserting absence; the brief
    // calls for "Hidden at <640px viewport".
    const wrap: Locator = page.getByTestId("party-pc-stronghold-map-wrap");
    await expect(wrap).toBeHidden();

    // The existing text list still renders so the citizen sees the
    // strongholds in a list format on small viewports.
    await expect(page.getByTestId("party-ls-strongholds")).toBeVisible();
  });
});
