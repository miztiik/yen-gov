// PL3 Psephlab in-browser smoke per CLAUDE.md section 13.
//
// Parent plan section 5 row 41:
//   "PL3 Load /lab/:state/:event, swing-mutation, screenshot"
//
// PL2 (fix at commit 974eec6f) unblocked the loader; before PL2 the
// loader threw and the page rendered "Failed to load actuals" - no
// smoke was possible. PL3 pins that the PL2 fix continues to hold and
// surfaces the G1 schema-drift regression class (parties.csv 7->8 col)
// at runtime.
//
// What this spec asserts (positive evidence the loader is repaired):
//
//   1. /lab/tamil-nadu/AcGenApr2021 loads with ZERO console errors
//      (catches PL2-class regressions where the loader throws).
//   2. ParliamentArc (aria-label="Seat distribution arc") renders with
//      exactly 234 dots.
//   3. Legend total (sum of per-party tabular-nums seats) == 234
//      (E5 assertSeatTallyInvariant green from an independent load
//      context, so PL3 is its own gate independent of E5).
//   4. ZERO failed requests for /data/entities/parties.csv (the G1
//      schema-drift regression signature: 200 response that DuckDB
//      rejects due to column-count mismatch surfaces here as either
//      a console error caught by attachPageErrorTrap OR a downstream
//      "Loading actuals..." that never resolves).
//   5. Captures the rendered ParliamentArc as a screenshot for audit
//      trail (PL3 receipt).
//
// What this spec does NOT assert:
//   - Specific party totals (covered by e5-parliament-arc-seats.spec.ts).
//   - Alternate counting methods (E6 ships in the SAME PR via subagent
//     C + orchestrator wiring; their smoke is added as a follow-up
//     describe block here OR a sister spec - keep this spec focused on
//     PL3's "loader is repaired" gate).
//   - Mobile breakpoint (Psephlab has no breakpoint-specific code path;
//     skip mobile-pixel-5 per the e5 spec doctrine).

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

test.beforeEach(({ page }, testInfo) => {
  trap = null;
  test.skip(
    testInfo.project.name === "mobile-pixel-5",
    "Psephlab PL3 smoke is desktop-only (Psephlab has no breakpoint-specific code path).",
  );
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap?.getErrors() ?? [];
  trap = null;
  expect(
    errors,
    `Page emitted runtime errors:\n${errors.join("\n")}`,
  ).toEqual([]);
});

test.describe("PL3 Psephlab loader smoke post-PL2 fix (section 5 row 41)", () => {
  test("/lab/tamil-nadu/AcGenApr2021 renders 234-dot arc with clean console + parties.csv", async ({
    page,
  }) => {
    // Audit responses for parties.csv specifically - the G1 regression
    // signature is a 200-OK CSV response that DuckDB's sniffer rejects
    // due to column-count mismatch. The PL2 fix at duckdb.ts now reads
    // the columns dict from datasets/data/_schema/columns.json so a
    // future schema addition does NOT re-introduce the regression.
    const partiesCsvAudit: { url: string; status: number; ok: boolean }[] = [];
    page.on("response", (resp) => {
      const url = resp.url();
      if (url.includes("/data/entities/parties.csv")) {
        partiesCsvAudit.push({
          url,
          status: resp.status(),
          ok: resp.ok(),
        });
      }
    });

    await page.goto("/lab/tamil-nadu/AcGenApr2021", {
      waitUntil: "domcontentloaded",
    });

    // Wait for the ParliamentArc SVG to render. The loader must have
    // returned rows successfully (PL2 fix allows this; before PL2 the
    // loader threw and ParliamentArc never mounted).
    const arc = page.locator('svg[aria-label="Seat distribution arc"]');
    await expect(arc).toBeVisible({ timeout: 60_000 });

    // Invariant #1: dot count == 234 (the canonical pinned result).
    const dotCount = await arc.locator("circle").count();
    expect(
      dotCount,
      "ParliamentArc dot count != 234 for TN AcGenApr2021. " +
        "If this fails, the loader may have returned empty or the engine " +
        "did not reconcile tallies. See assertSeatTallyInvariant in " +
        "frontend/src/lib/charts/count-seats.ts.",
    ).toBe(234);

    // Invariant #2: legend total == 234. Cross-checks the per-party
    // chip sum independently of the dot count.
    const legendTotal = await arc
      .locator("xpath=following-sibling::ul[1]")
      .first()
      .evaluate((ul: HTMLElement) => {
        let sum = 0;
        for (const li of Array.from(ul.querySelectorAll("li"))) {
          const tabular = li.querySelector(".tabular-nums");
          if (!tabular) continue;
          const n = parseInt(tabular.textContent?.trim() ?? "", 10);
          if (!Number.isNaN(n)) sum += n;
        }
        return sum;
      });
    expect(
      legendTotal,
      "ParliamentArc legend total != 234 for TN AcGenApr2021. See " +
        "assertSeatTallyInvariant in frontend/src/lib/charts/count-seats.ts.",
    ).toBe(234);

    // Invariant #3: dot count == legend total (internal consistency).
    expect(
      dotCount,
      `Dot count != legend total for TN AcGenApr2021: dots=${dotCount} ` +
        `legend=${legendTotal}. The two are sourced from the same SeatTally; ` +
        "a mismatch means a rendering bug in ParliamentArc.svelte.",
    ).toBe(legendTotal);

    // Audit: at least one parties.csv response captured, AND every
    // captured response is a 200-OK. The PL2 regression signature would
    // be a 200 here PLUS the page would never have left "Loading
    // actuals..." (which the arc-visible expect above already would
    // have failed on); this audit is the explicit, named gate for the
    // regression class so a future agent reading the failure sees the
    // root cause spelled out.
    expect(
      partiesCsvAudit.length,
      "Expected at least one /data/entities/parties.csv request during " +
        "Psephlab load. If zero, the loader's dim_parties JOIN regressed.",
    ).toBeGreaterThan(0);
    const failed = partiesCsvAudit.filter((r) => !r.ok);
    expect(
      failed,
      "One or more /data/entities/parties.csv responses returned non-200. " +
        "See PL2 fix doctrine in frontend/src/lib/duckdb.ts " +
        "(csvColumnsClause / schema-as-single-source-of-truth).",
    ).toEqual([]);

    // Capture the PL3 receipt screenshot.
    await page.screenshot({
      path: "test-results/psephlab-pl3-receipt.png",
      fullPage: false,
    });
  });
});
