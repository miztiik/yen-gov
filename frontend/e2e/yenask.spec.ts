// YENASK dev-route end-to-end smoke (PR-1).
//
// Drives /dev/yenask through the full pipeline:
//   1. Catalogue loads from canonical manifest + dim queries.
//   2. Click a canned intent button.
//   3. Compiler produces a DuckDBPlan; executor runs main + provenance SQL.
//   4. AnswerViewModel renders: table rows, SourceListV2 strip, "how
//      computed" disclosure.
//
// Per CLAUDE.md §15 + #13 this proves the lab actually exercises the
// canonical Parquet end-to-end inside the browser. The pageerror trap
// follows the duckdb-harness pattern: zero runtime errors permitted.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `yenask emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("yenask dev route", () => {
  test("loads catalogue and answers the TN party-totals canned intent", async ({
    page,
  }) => {
    await page.goto("/dev/yenask");

    await expect(
      page.getByRole("heading", { name: /YENASK/i }),
    ).toBeVisible();

    // The catalogue boots DuckDB-WASM, registers 4 dim/taxonomy tables,
    // and runs 4 small queries — allow generous time for the wasm cold
    // boot + small Parquet fetches.
    const partyButton = page.locator('[data-canned-id="tn-may-2026-party-totals"]');
    await expect(partyButton).toBeEnabled({ timeout: 60_000 });

    await partyButton.click();

    // Compiler + executor — the slice is Tamil Nadu only (in_s22).
    const table = page.getByTestId("yenask-answer-table");
    await expect(table).toBeVisible({ timeout: 60_000 });

    // At least one party row; TN AcGenMay2026 has 4+ parties on record.
    const rows = table.locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);

    // Provenance strip must render with a non-empty SourceListV2.
    const sourceStrip = page.getByTestId("yenask-source-strip");
    await expect(sourceStrip).toBeVisible();
    // SourceListV2 always renders at least one row; either real ECI or
    // synthesised "source unattested". Either way the strip is non-empty.
    await expect(
      sourceStrip.locator('[data-component="source-list-v2"]'),
    ).toBeVisible();

    // The "how computed" disclosure exists and contains the concept_id.
    const computation = page.getByTestId("yenask-computation");
    await expect(computation).toBeVisible();
    await computation.locator("summary").click();
    await expect(computation).toContainText("party_totals");
    await expect(computation).toContainText("election_results");
  });
});
