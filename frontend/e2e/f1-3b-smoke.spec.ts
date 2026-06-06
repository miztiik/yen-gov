// F1.3b in-browser smoke - per CLAUDE.md section 13.
//
// What this proves (POSITIVE evidence)
// ------------------------------------
// The 3 view-models that F1.3b flipped to CSV
// (`view-models/national-elections.ts`, `yenask/concepts.ts`,
// `explore/duckdb-views.ts`) DO read per-(state, year) CSV under
// `datasets/elections/{assembly,parliament}/...` AND the citizen
// surfaces render without runtime errors.
//
// The smoke routes are the three F1.3b citizen surfaces:
//
//   /t/elections/LsGenApr2019           - NationalElectionsAtlas
//                                         (national-elections view-model)
//   /lab/yenask                         - Yenask
//                                         (yenask/concepts via canned intent)
//   /s/tamil-nadu/explore               - Explore
//                                         (explore/duckdb-views)
//
// What this CANNOT cleanly prove
// ------------------------------
// "ZERO requests for the 4 decommissioned Parquet shards on the smoke
// routes" is intentionally NOT a hard gate here. Reason: the same
// routes mount OTHER consumers that are still on Parquet by design at
// F1.3b:
//
//   - elections.dim_parties (kept; X1a flips it later)
//   - taxonomy.sources      (kept; X1a flips it later)
//   - yenask semantic-catalogue boots its own dim_acs + dim_parties +
//     elections_candidacies parquet reads to build the catalogue (NOT
//     the per-question concept SQL F1.3b flipped)
//   - NationalElectionsAtlas mounts a TileCartogram that fetches the
//     tile-layout JSON (no parquet); ChartShell etc.
//
// These survive F1.3b's scope. They'll get their own CSV flip in X1a.
// The unit-test surface (national-elections.test.ts +
// compile-intent.test.ts + duckdb-views.test.ts) already pins the SQL
// boundary for the 3 rewritten loaders to NOT issue read_parquet
// against the 4 dropped tables.
//
// Method
// ------
// Attach page.on("response", ...) BEFORE page.goto() so EVERY response
// is captured. After the citizen-visible loader-resolved signal,
// assert:
//
//   (a) >=1 expected per-(state, year) CSV responses for each surface
//   (b) 0 console errors / 0 failed requests (via attachPageErrorTrap)
//
// Also LOG (not assert) the surviving parquet substrings observed on
// the route so the PR body can carry a "surviving non-allowlisted
// consumers" line for X1a follow-up.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

const SURVIVING_PARQUET_SUBSTRINGS = [
  "elections_candidacies",
  "election_results",
  "dim_persons",
  "dim_acs",
  "dim_pcs",
] as const;

interface RequestAudit {
  urls: string[];
  parliamentCands: string[];
  parliamentSummary: string[];
  assemblyCands: string[];
  assemblySummary: string[];
  electoral: string[];
  parquetSurvivors: string[];
}

function attachRequestAudit(page: import("@playwright/test").Page): RequestAudit {
  const audit: RequestAudit = {
    urls: [],
    parliamentCands: [],
    parliamentSummary: [],
    assemblyCands: [],
    assemblySummary: [],
    electoral: [],
    parquetSurvivors: [],
  };
  page.on("response", (resp) => {
    const url = resp.url();
    audit.urls.push(url);
    if (/\/elections\/parliament\/election=\d+\/candidacies\.csv$/.test(url)) {
      audit.parliamentCands.push(url);
    }
    if (/\/elections\/parliament\/election=\d+\/summary\.csv$/.test(url)) {
      audit.parliamentSummary.push(url);
    }
    if (/\/elections\/assembly\/state=[^/]+\/election=\d+\/candidacies\.csv$/.test(url)) {
      audit.assemblyCands.push(url);
    }
    if (/\/elections\/assembly\/state=[^/]+\/election=\d+\/summary\.csv$/.test(url)) {
      audit.assemblySummary.push(url);
    }
    if (/\/data\/entities\/electoral\.csv$/.test(url)) {
      audit.electoral.push(url);
    }
    for (const banned of SURVIVING_PARQUET_SUBSTRINGS) {
      if (url.includes(banned)) {
        audit.parquetSurvivors.push(url);
        break;
      }
    }
  });
  return audit;
}

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("F1.3b - CSV reader cutover smoke", () => {
  test("NationalElectionsAtlas /t/elections/LsGenApr2019 fetches parliament/election=2019 summary.csv + electoral.csv", async ({
    page,
  }) => {
    const audit = attachRequestAudit(page);

    await page.goto("/t/elections/LsGenApr2019");

    // Wait for the atlas to render. The page mounts a maplibre
    // choropleth keyed by PC join_keys; once the winners load the page
    // becomes interactive. As a stable load-complete signal, wait for
    // any DMK / INC / BJP party-short chip that the per-PC winners
    // surface produces (LsGenApr2019 had 543 PCs with party winners
    // covering all 3 of those parties).
    await expect(
      page.getByText(/BJP|INC|DMK|YSRCP/).first(),
    ).toBeVisible({ timeout: 60_000 });

    // POSITIVE evidence: at least one parliament/election=2019
    // summary.csv response + electoral.csv response.
    expect(
      audit.parliamentSummary,
      `Expected >=1 parliament/election=2019/summary.csv response;\nAll URLs captured (last 30):\n${audit.urls.slice(-30).join("\n")}`,
    ).not.toHaveLength(0);
    expect(
      audit.electoral,
      "Expected >=1 electoral.csv response (canonical PC entity join)",
    ).not.toHaveLength(0);

    // Surviving parquet consumers (LOG for visibility; do NOT assert
    // empty - X1a cuts them over). national-elections.ts now uses 0
    // of the F1.3b-decommissioned parquets in its own SQL; any
    // survivor here is from sibling components on the page (chrome,
    // boundary loaders, dim_parties, taxonomy.sources).
    if (audit.parquetSurvivors.length > 0) {
      const uniq = Array.from(new Set(audit.parquetSurvivors)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[F1.3b-smoke] NationalElectionsAtlas: ${uniq.length} surviving parquet URL(s) from non-F1.3b consumers (dim_parties + sibling chrome). Carry to X1a:\n${uniq.join("\n")}`,
      );
    }
  });

  test("Yenask /lab/yenask runs the party_totals concept on per-(state, year) assembly CSV", async ({
    page,
  }) => {
    const audit = attachRequestAudit(page);

    await page.goto("/lab/yenask");

    await expect(
      page.getByRole("heading", { name: /Yen-Ask/i }),
    ).toBeVisible({ timeout: 30_000 });

    // The catalogue boots first (legacy dim_* parquet reads; tolerated).
    // Wait for the canned-intent button to enable then click party_totals.
    const partyButton = page.locator(
      '[data-canned-id="tn-apr-2021-party-totals"]',
    );
    await expect(partyButton).toBeEnabled({ timeout: 60_000 });
    await partyButton.click();

    // Wait for the answer table - the citizen-visible signal that
    // executePlan succeeded against the per-(state, year) CSV.
    const table = page.getByTestId("yenask-answer-table");
    await expect(table).toBeVisible({ timeout: 60_000 });
    expect(await table.locator("tbody tr").count()).toBeGreaterThan(0);

    // POSITIVE evidence: the post-click concept SQL fetched
    // candidacies.csv + electoral.csv. Per F1.3b yenask/concepts.ts
    // party_totals concept reads candidacies.csv (per-candidacy
    // votes/seats) JOIN electoral.csv (AC entity scope).
    expect(
      audit.assemblyCands,
      `Expected >=1 assembly candidacies.csv response on /lab/yenask after clicking party_totals;\nAll URLs captured (last 30):\n${audit.urls.slice(-30).join("\n")}`,
    ).not.toHaveLength(0);
    expect(
      audit.electoral,
      "Expected >=1 electoral.csv response (canonical AC entity join)",
    ).not.toHaveLength(0);

    // Surviving parquet consumers: ALL F1.3b survivors here come from
    // (a) the semantic catalogue's catalogue-time dim reads (NOT the
    // concept SQL F1.3b flipped) and (b) the dim_parties + sources
    // tables kept on Parquet until X1a. LOG only.
    if (audit.parquetSurvivors.length > 0) {
      const uniq = Array.from(new Set(audit.parquetSurvivors)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[F1.3b-smoke] Yenask: ${uniq.length} surviving parquet URL(s) from semantic-catalogue + dim_parties (NOT the flipped concept SQL). Carry to X1a:\n${uniq.join("\n")}`,
      );
    }
  });

  test("Explore /s/tamil-nadu/explore (AcGenApr2021) builds CSV-backed DuckDB views", async ({
    page,
  }) => {
    const audit = attachRequestAudit(page);

    await page.goto("/s/tamil-nadu/explore");

    // Switch to the 2021 cohort - TN AcGenMay2026 has NO on-disk CSV
    // (compilation vintage Feb-2023 cut at 2021).
    const picker = page.getByTestId("event-picker");
    await expect(picker).toBeVisible({ timeout: 30_000 });
    await picker.selectOption("AcGenApr2021");

    // Wait for the Explore presets surface to mount + populate. The
    // page builds the 4 views (parties, constituencies, candidates,
    // party_totals) via buildExploreViews on event change.
    // The Run-query button is the stable signal it is ready.
    const runButton = page.getByRole("button", { name: /Run/i }).first();
    await expect(runButton).toBeEnabled({ timeout: 60_000 });

    // Run a preset - any preset that touches candidates / constituencies
    // / party_totals will force the views to materialise their data
    // through DuckDB-WASM, which is the moment CSV fetch fires.
    await runButton.click();

    // Wait for some result row to render (presets-table has tbody rows
    // when a query succeeds).
    await expect(
      page.locator('[data-testid="explore-results"] tbody tr, [data-testid="explore-results"] table tbody tr').first(),
    ).toBeVisible({ timeout: 60_000 });

    // POSITIVE evidence: at least one assembly candidacies + summary
    // CSV response (party_totals / candidates / constituencies all
    // read from those CSVs).
    expect(
      [...audit.assemblyCands, ...audit.assemblySummary].length,
      `Expected >=1 assembly CSV response (candidacies or summary) on /s/tamil-nadu/explore (AcGenApr2021);\nAll URLs captured (last 30):\n${audit.urls.slice(-30).join("\n")}`,
    ).toBeGreaterThan(0);
    expect(
      audit.electoral,
      "Expected >=1 electoral.csv response (canonical AC entity join)",
    ).not.toHaveLength(0);

    // Surviving parquet consumers: dim_parties is the only one F1.3b
    // explicitly keeps on Parquet for explore's `parties` view.
    if (audit.parquetSurvivors.length > 0) {
      const uniq = Array.from(new Set(audit.parquetSurvivors)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[F1.3b-smoke] Explore: ${uniq.length} surviving parquet URL(s) from non-F1.3b consumers (dim_parties + sibling chrome). Carry to X1a:\n${uniq.join("\n")}`,
      );
    }
  });
});
