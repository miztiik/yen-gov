// F1.3a Path A in-browser smoke - per CLAUDE.md section 13.
//
// What this proves (POSITIVE evidence)
// ------------------------------------
// The 3 view-models that F1.3a flipped to CSV
// (`view-models/constituency.ts`, `view-models/state-overview.ts`,
// `psephlab/canonical-loaders.ts`) DO read per-(state, year) CSV under
// `datasets/elections/assembly/state=*/election=*/` AND the citizen
// surfaces render without runtime errors.
//
// The smoke routes are the two assembly-side citizen surfaces:
//
//   /tamil-nadu                        - StateOverview view-model
//   /tamil-nadu/.../ac/<some-AC-slug>  - Constituency view-model
//
// What this CANNOT cleanly prove
// ------------------------------
// "ZERO requests for the 4 decommissioned Parquet shards on the smoke
// routes" is intentionally NOT a hard gate here. Reason: the same
// routes mount OTHER consumers that are still on Parquet by design at
// F1.3a:
//
//   - `view-models/election-seats-trend.ts` (StateOverview)
//   - `view-models/india-leading-parties.ts` (Home, indirectly)
//   - `view-models/parties-palette.ts`
//   - `charts/composition-bar/adapter-elections-seats.ts` (StateOverview)
//
// These survive F1.3a's scope (per the F1 sub-plan F1.3a/F1.3b/F1.4
// split). They'll get their own CSV flip in F1.3b + X1a. The
// "non-renderer consumers stay on legacy fetch until the cutover phase
// covers them" doctrine is recorded in
// `TODO/20260606-handover-prompt-data-charting-reset.md` section 7
// lesson 7. The unit-test surface (state-overview.test.ts +
// constituency.test.ts + canonical-loaders.test.ts) already pins the
// SQL boundary for the 3 rewritten loaders to NOT issue read_parquet
// against the 4 dropped tables.
//
// Method
// ------
// Attach page.on("response", ...) BEFORE page.goto() so EVERY response
// is captured. After the citizen-visible loader-resolved signal (a DMK
// chip rendered on TN-2021 - the page DOESN'T render that chip unless
// loadStateOverview returned ok with party_totals[]), assert:
//
//   (a) >=1 candidacies.csv + summary.csv + electoral.csv responses
//   (b) 0 console errors / 0 failed requests on /data/* (via
//       attachPageErrorTrap)
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
] as const;

interface RequestAudit {
  urls: string[];
  cands: string[];
  summary: string[];
  electoral: string[];
  parquetSurvivors: string[];
}

function attachRequestAudit(page: import("@playwright/test").Page): RequestAudit {
  const audit: RequestAudit = {
    urls: [],
    cands: [],
    summary: [],
    electoral: [],
    parquetSurvivors: [],
  };
  page.on("response", (resp) => {
    const url = resp.url();
    audit.urls.push(url);
    if (/\/elections\/assembly\/state=tamil-nadu\/election=\d+\/candidacies\.csv$/.test(url)) {
      audit.cands.push(url);
    }
    if (/\/elections\/assembly\/state=tamil-nadu\/election=\d+\/summary\.csv$/.test(url)) {
      audit.summary.push(url);
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

test.describe("F1.3a Path A - CSV reader cutover smoke", () => {
  test("StateOverview /tamil-nadu (AcGenApr2021) fetches per-(state, year) CSV from the rewritten loaders", async ({
    page,
  }) => {
    const audit = attachRequestAudit(page);

    await page.goto("/tamil-nadu");

    // Switch to the 2021 cohort - the latest TN assembly TCPD has data
    // for. AcGenMay2026 (the default) has NO on-disk TCPD CSV yet
    // (compilation vintage Feb-2023 cut at 2021); a separate ingest
    // gap, not an F1.3a concern.
    const picker = page.getByTestId("event-picker");
    await expect(picker).toBeVisible({ timeout: 15_000 });
    await picker.selectOption("AcGenApr2021");

    // Wait for the loader's OK arm. The DMK chip on at least one AC
    // winner badge is the strongest citizen-visible signal that
    // loadStateOverview returned ok with party_totals[] AND
    // ac_winners[] from the CSV pipeline. Regex because the chip text
    // is "DMK . 1.4 pt margin" inside a generic, not "DMK" alone.
    await expect(page.getByText(/DMK/).first()).toBeVisible({ timeout: 30_000 });

    // POSITIVE evidence: at least one CSV response for each of the 3
    // surfaces my rewritten loader expects.
    expect(
      audit.cands,
      `Expected >=1 candidacies.csv response on /tamil-nadu (AcGenApr2021);\nAll URLs captured (last 30):\n${audit.urls.slice(-30).join("\n")}`,
    ).not.toHaveLength(0);
    expect(audit.summary, "Expected >=1 summary.csv response").not.toHaveLength(0);
    expect(
      audit.electoral,
      "Expected >=1 electoral.csv response (canonical AC entity join)",
    ).not.toHaveLength(0);

    // Surviving parquet consumers (LOG for visibility; do NOT assert
    // empty - F1.3b / X1a cuts them over).
    if (audit.parquetSurvivors.length > 0) {
      const uniq = Array.from(new Set(audit.parquetSurvivors)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[F1.3a-smoke] StateOverview: ${uniq.length} surviving parquet URL(s) from non-F1.3a consumers (election-seats-trend / parties-palette / composition-bar / india-leading-parties). Carry to F1.3b + X1a:\n${uniq.join("\n")}`,
      );
    }
  });

  test("Constituency /tamil-nadu/.../ac/<slug> (AcGenApr2021) fetches per-(state, year) CSV from the rewritten loader", async ({
    page,
  }) => {
    // Land on StateOverview, switch to AcGenApr2021 so the AC links
    // carry the event in the URL (the AC URL builder nests the event
    // per ADR-0052: /<slug>/elections/<event>/ac/<slug>).
    await page.goto("/tamil-nadu");
    const picker = page.getByTestId("event-picker");
    await expect(picker).toBeVisible({ timeout: 15_000 });
    await picker.selectOption("AcGenApr2021");
    await expect(page.getByText(/DMK/).first()).toBeVisible({ timeout: 30_000 });

    const firstAcHref = await page
      .locator('a[href*="/tamil-nadu/elections/AcGenApr2021/ac/"]')
      .first()
      .getAttribute("href");
    expect(
      firstAcHref,
      "Expected at least one AC link under AcGenApr2021 on StateOverview",
    ).toBeTruthy();

    // Attach the audit AFTER selection so it captures only the AC
    // route's loader behaviour.
    const audit = attachRequestAudit(page);
    await page.goto(firstAcHref!);

    // Wait for the candidate-biographics testid (per golden-path
    // contract: rendered for at least the first row whether bio data
    // is present or not). Stable load-complete marker.
    await expect(
      page.locator('[data-testid="candidate-biographics"]').first(),
    ).toBeVisible({ timeout: 30_000 });

    expect(
      audit.cands,
      `Expected >=1 candidacies.csv response on Constituency route;\nAll URLs captured (last 30):\n${audit.urls.slice(-30).join("\n")}`,
    ).not.toHaveLength(0);
    expect(audit.summary, "Expected >=1 summary.csv response").not.toHaveLength(0);
    expect(audit.electoral, "Expected >=1 electoral.csv response").not.toHaveLength(0);

    if (audit.parquetSurvivors.length > 0) {
      const uniq = Array.from(new Set(audit.parquetSurvivors)).sort();
      // eslint-disable-next-line no-console
      console.log(
        `[F1.3a-smoke] Constituency: ${uniq.length} surviving parquet URL(s) from non-F1.3a consumers. Carry to F1.3b + X1a:\n${uniq.join("\n")}`,
      );
    }
  });
});
