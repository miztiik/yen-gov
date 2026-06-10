// X1a in-browser smoke - per CLAUDE.md section 13.
//
// What this proves (POSITIVE evidence)
// ------------------------------------
// X1a flipped `dim_parties` + `taxonomy.sources` readers from parquet to
// CSV via the new `registerCsvAsTable` seam in `lib/duckdb.ts`. The 3
// citizen surfaces below all consume those flipped tables; this smoke
// asserts:
//
//   1. ZERO requests for `dim_parties.parquet` + `taxonomy/sources.parquet`
//      on any of the 3 routes (those two parquet URLs are dead bytes
//      post-X1a; X1b deletes them next).
//   2. >=1 request for `data/entities/parties.csv` on each route that
//      consumes the dim_parties view (StateOverview / Constituency /
//      Yenask).
//   3. >=1 request for `data/entities/source.csv` on each route that
//      consumes the sources view (StateOverview / Constituency / Yenask).
//   4. 0 console errors + 0 failed requests (via attachPageErrorTrap).
//
// Smoke routes mirror the F1.3a/b precedent:
//
//   /tamil-nadu                       - StateOverview (state-overview)
//   /tamil-nadu/ac/167                - Constituency (constituency)
//   /lab/yenask                         - Yenask (yenask/concepts via
//                                                 canned intent)
//
// What this does NOT assert
// -------------------------
// "Zero parquet requests of ANY kind" is intentionally NOT enforced.
// X1a-LEFTOVER consumers still on parquet are listed under
// SURVIVING_PARQUET_SUBSTRINGS below. X1b (this PR's preceding chunk)
// deleted the 12 SAFE-TO-DELETE parquets from disk; their substrings
// were moved into BANNED_PARQUET_SUBSTRINGS so the smoke fails loud if
// any caller still emits a fetch for them.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

// X1a + X1b deleted these parquets from disk; any request is a bug.
const BANNED_PARQUET_SUBSTRINGS = [
  // X1a-flipped
  "dim_parties.parquet",
  "taxonomy/sources.parquet",
  // X1a-followup #811
  "ac_crosswalk.parquet",
  // X1b orphan deletes (F1.3b dropped JOIN; no surviving reader)
  "dim_persons.parquet",
  "dim_pcs.parquet",
  "taxonomy/persons.parquet",
  // X1b small taxonomy orphans (CSV at datasets/data/<name>.csv)
  "election_events.parquet",
  "methodology_breaks.parquet",
  "topics.parquet",
  "state_tiers.parquet",
  "facet-axes.parquet",
  "indicator_topic_tags.parquet",
  // X1b post-YA-apply (semantic-catalogue.ts flipped to CSV in PR #813)
  "dim_acs.parquet",
  "elections_candidacies.parquet",
] as const;

interface RequestAudit {
  urls: string[];
  partiesCsv: string[];
  sourceCsv: string[];
  bannedParquet: string[];
  surviorParquet: string[];
}

// Still on parquet by scope; retire via B3 + a later partial-X1b pass.
const SURVIVING_PARQUET_SUBSTRINGS = [
  "election_results",
  "dim_party_alliances",
  "entities.parquet",
  "indicators.parquet",
] as const;

function attachRequestAudit(page: import("@playwright/test").Page): RequestAudit {
  const audit: RequestAudit = {
    urls: [],
    partiesCsv: [],
    sourceCsv: [],
    bannedParquet: [],
    surviorParquet: [],
  };
  page.on("response", (resp) => {
    const url = resp.url();
    audit.urls.push(url);
    if (/\/data\/entities\/parties\.csv$/.test(url)) {
      audit.partiesCsv.push(url);
    }
    if (/\/data\/entities\/source\.csv$/.test(url)) {
      audit.sourceCsv.push(url);
    }
    for (const banned of BANNED_PARQUET_SUBSTRINGS) {
      if (url.includes(banned)) {
        audit.bannedParquet.push(url);
        break;
      }
    }
    for (const survivor of SURVIVING_PARQUET_SUBSTRINGS) {
      if (url.includes(survivor)) {
        audit.surviorParquet.push(url);
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

test.describe("X1a - dim_parties + taxonomy.sources flipped to CSV", () => {
  test("StateOverview /tamil-nadu fetches parties.csv + source.csv (NO dim_parties.parquet + sources.parquet)", async ({
    page,
  }) => {
    const audit = attachRequestAudit(page);

    await page.goto("/tamil-nadu");

    // Wait for the state hub to render (DMK / AIADMK party chips
    // appear in the per-AC winners list once the loader resolves).
    await expect(
      page.getByText(/DMK|AIADMK/).first(),
    ).toBeVisible({ timeout: 60_000 });

    // BANNED: zero requests for dim_parties.parquet OR taxonomy/sources.parquet.
    expect(
      audit.bannedParquet,
      `Expected ZERO requests for dim_parties.parquet + taxonomy/sources.parquet on /tamil-nadu; got:\n${audit.bannedParquet.join("\n")}`,
    ).toEqual([]);

    // POSITIVE: at least one fetch of parties.csv (state-overview
    // queries party identity).
    expect(
      audit.partiesCsv,
      `Expected >=1 fetch of /data/entities/parties.csv on /tamil-nadu;\nAll URLs captured (last 30):\n${audit.urls.slice(-30).join("\n")}`,
    ).not.toHaveLength(0);

    // POSITIVE: at least one fetch of source.csv (state-overview
    // queries sources_v2 provenance ledger).
    expect(
      audit.sourceCsv,
      `Expected >=1 fetch of /data/entities/source.csv on /tamil-nadu`,
    ).not.toHaveLength(0);

    // Surviving parquet consumers - LOG only (X1b cleanup).
    if (audit.surviorParquet.length > 0) {
      const uniq = Array.from(new Set(audit.surviorParquet)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[X1a-smoke] StateOverview: ${uniq.length} surviving parquet URL(s) (X1b retires):\n${uniq.join("\n")}`,
      );
    }
  });

  test("Constituency /tamil-nadu/ac/167 fetches parties.csv + source.csv (NO dim_parties.parquet + sources.parquet)", async ({
    page,
  }) => {
    const audit = attachRequestAudit(page);

    // AC 167 (Mylapore) - any AC in TN works; pick a stable mid-numbered one.
    await page.goto("/tamil-nadu/ac/167");

    // Wait for the per-AC candidates panel to render.
    await expect(
      page.getByText(/winner|votes|turnout|margin/i).first(),
    ).toBeVisible({ timeout: 60_000 });

    expect(
      audit.bannedParquet,
      `Expected ZERO requests for dim_parties.parquet + taxonomy/sources.parquet on /tamil-nadu/ac/167; got:\n${audit.bannedParquet.join("\n")}`,
    ).toEqual([]);

    expect(
      audit.partiesCsv,
      `Expected >=1 fetch of /data/entities/parties.csv on /tamil-nadu/ac/167`,
    ).not.toHaveLength(0);

    expect(
      audit.sourceCsv,
      `Expected >=1 fetch of /data/entities/source.csv on /tamil-nadu/ac/167`,
    ).not.toHaveLength(0);

    if (audit.surviorParquet.length > 0) {
      const uniq = Array.from(new Set(audit.surviorParquet)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[X1a-smoke] Constituency: ${uniq.length} surviving parquet URL(s) (X1b retires):\n${uniq.join("\n")}`,
      );
    }
  });

  test("Yenask /lab/yenask runs party_totals concept against parties.csv + source.csv (NO dim_parties.parquet + sources.parquet from the concept SQL)", async ({
    page,
  }) => {
    const audit = attachRequestAudit(page);

    await page.goto("/lab/yenask");

    await expect(
      page.getByRole("heading", { name: /Yen-Ask/i }),
    ).toBeVisible({ timeout: 30_000 });

    // Run a canned intent. Yenask's execute-plan dispatches
    // elections.dim_parties + taxonomy.sources through
    // registerCsvAsTable (X1a) - other table_ids in the plan
    // (e.g. semantic-catalogue startup reads) STAY on parquet.
    const partyButton = page.locator(
      '[data-canned-id="tn-apr-2021-party-totals"]',
    );
    await expect(partyButton).toBeEnabled({ timeout: 60_000 });
    await partyButton.click();

    const table = page.getByTestId("yenask-answer-table");
    await expect(table).toBeVisible({ timeout: 60_000 });
    expect(await table.locator("tbody tr").count()).toBeGreaterThan(0);

    // After the concept ran, the X1a-flipped surfaces (dim_parties +
    // taxonomy.sources) MUST be served by their CSV equivalents.
    expect(
      audit.partiesCsv,
      `Expected >=1 fetch of /data/entities/parties.csv on /lab/yenask after running party_totals`,
    ).not.toHaveLength(0);

    expect(
      audit.sourceCsv,
      `Expected >=1 fetch of /data/entities/source.csv on /lab/yenask after running party_totals`,
    ).not.toHaveLength(0);

    expect(
      audit.bannedParquet,
      `Expected ZERO requests for dim_parties.parquet + taxonomy/sources.parquet on /lab/yenask; got:\n${audit.bannedParquet.join("\n")}`,
    ).toEqual([]);

    if (audit.surviorParquet.length > 0) {
      const uniq = Array.from(new Set(audit.surviorParquet)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[X1a-smoke] Yenask: ${uniq.length} surviving parquet URL(s) from semantic-catalogue + non-X1a consumers (X1b retires):\n${uniq.join("\n")}`,
      );
    }
  });
});
