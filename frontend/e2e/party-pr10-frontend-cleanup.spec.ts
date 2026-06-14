// PR-10 of TODO/20260613-party-deferred-followups-plan.md section 12.
//
// Playwright e2e for the 3 PR-10 scope items:
//   1. The "Pre-1999 LS history not yet ingested" caption is GONE from
//      every /parties/<slug> page (the data exists post-PR-8 #1003; the
//      caption was lying). Verified by asserting the dropped data-testid
//      `party-ls-coverage` is no longer in the DOM on a representative
//      party with LS history.
//   2. The BJP 1980 founding strip (Hans 3b verdict) is visible on
//      /parties/bjp with the correct citizen-tested copy + a working
//      cross-link to /parties/bjs (resolves today; the /parties/jnp
//      link in the same strip is forward-looking and not click-tested
//      because parties.IN.JNP is minted by a future historical-parties
//      PR per umbrella plan section 11).
//   3. The 2 lspc-delim methodology-break markers (1967 + 1976) render
//      on the DMK LS chart - DMK's contested-cycle history spans
//      1962-2024 so BOTH breaks fall strictly inside the visible X
//      domain per the `computeMethodologyBreakMarkers` filter.
//
// Per-party oracle rationale:
//   - /parties/inc -> chosen for oracle 1 because INC has the longest
//     LS history of any party and previously rendered the caption.
//   - /parties/bjp -> the only party that triggers the lineage strip.
//   - /parties/dmk -> brief-specified party for the marker oracle; its
//     1962+ LS coverage exercises both delim seams.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

// PR-4 party-detail page cold-loads a ~177 MB candidate corpus into
// DuckDB-WASM via the strongholds + history marts; even with the marts
// being ~50 KB each, the duckdb-wasm boot + party-detail loader + JSON
// taxonomy fetches push first-paint past Playwright's 30s default on
// a cold vite. Raise per-test timeout to 60s so the goto + loader gate
// have headroom; the existing party-stronghold-choropleth.spec.ts
// works around the same constraint by running on already-warm vite.
test.setTimeout(60_000);

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

test.describe("PR-10 party page cleanup", () => {
  test("oracle 1: 'Pre-1999 LS history not yet ingested' caption is gone (/parties/inc)", async ({
    page,
  }) => {
    await page.goto("/parties/inc", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("party-loading")).toBeHidden({
      timeout: 30_000,
    });
    // INC has an LS chart - the chart section must mount (sanity check
    // that we're on the right surface).
    await expect(page.getByTestId("party-ls-chart")).toBeVisible();
    // The dropped caption's data-testid MUST NOT be in the DOM.
    await expect(page.getByTestId("party-ls-coverage")).toHaveCount(0);
    // And the literal copy MUST NOT appear anywhere on the page.
    await expect(
      page.locator("body", {
        hasText: "Pre-1999 LS history not yet ingested",
      }),
    ).toHaveCount(0);
  });

  test("oracle 2: BJP 1980 founding strip renders with cross-links per Hans 3b verdict", async ({
    page,
  }) => {
    await page.goto("/parties/bjp", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("party-loading")).toBeHidden({
      timeout: 30_000,
    });

    const strip = page.getByTestId("party-recognition-strip");
    await expect(strip).toBeVisible();
    // The new "lineage" kind is stamped on the data-kind attribute.
    await expect(strip).toHaveAttribute("data-kind", "lineage");
    // Verbatim copy fragments per Hans 3b (the byte-for-byte assertion
    // lives in the vitest pin; here we anchor on the 3 most-recognised
    // citizen tokens).
    await expect(strip).toContainText("1980");
    await expect(strip).toContainText("Bharatiya Jana Sangh");
    await expect(strip).toContainText("Janata Party");
    // The /parties/bjs link resolves today (parties.IN.BJS exists in
    // parties.csv) - clicking it must navigate.
    const bjsLink = strip.getByRole("link", {
      name: /Bharatiya Jana Sangh/i,
    });
    await expect(bjsLink).toBeVisible();
    await bjsLink.click();
    await expect(page).toHaveURL(/\/parties\/bjs(\/|$|\?)/);
  });

  test("oracle 3: 2 methodology-break markers (1967 + 1976) render on /parties/dmk LS chart", async ({
    page,
  }) => {
    await page.goto("/parties/dmk", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("party-loading")).toBeHidden({
      timeout: 30_000,
    });

    const lsChart = page.getByTestId("party-ls-chart");
    await expect(lsChart).toBeVisible();

    // Pre-1999 data is visible on the X axis (DMK's earliest LS
    // cycle 1962 sits at index 0 of the chronological domain). At
    // any chart width the first tick label is rendered.
    await expect(lsChart).toContainText("1962");

    // Exactly 2 vertical markers (1967 + 1976) rendered inside the
    // chart group. Stamped data-methodology-version attributes pin
    // the identity so a future broadening of the catalogue doesn't
    // silently change the count.
    const markers = lsChart.locator(
      '[data-testid="methodology-break-marker"]',
    );
    await expect(markers).toHaveCount(2);
    await expect(markers.first()).toHaveAttribute(
      "data-methodology-version",
      "lspc-delim-1967",
    );
    await expect(markers.last()).toHaveAttribute(
      "data-methodology-version",
      "lspc-delim-1976",
    );
    await expect(markers.first()).toHaveAttribute(
      "data-reference-number",
      "1",
    );
    await expect(markers.last()).toHaveAttribute(
      "data-reference-number",
      "2",
    );

    // The footnote caption below the chart references both breaks.
    const caption = page.getByTestId("party-ls-methodology-caption");
    await expect(caption).toBeVisible();
    await expect(caption).toContainText("1) delim 1967");
    await expect(caption).toContainText("2) delim 1976");
  });
});
