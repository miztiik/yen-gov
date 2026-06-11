// YENASK dev-route end-to-end smoke (post-F1.3b cutover).
//
// Drives /lab/yenask through the full pipeline:
//   1. Catalogue loads from canonical manifest + dim queries (Parquet;
//      X1a flips this).
//   2. Click a canned intent button (4 canned intents now scope to
//      Tamil Nadu AC General April 2021 — the deepest TN partition
//      with on-disk CSV; TN-2026 CSV has not been emitted).
//   3. Compiler produces a DuckDBPlan; executor runs the main SQL
//      against per-(state, year) CSV via DuckDB-WASM `read_csv(...)`
//      and the provenance SQL against `taxonomy.sources` (Parquet).
//   4. AnswerViewModel renders: table rows, publisher-pill source strip,
//      "how computed" disclosure.
//
// Per CLAUDE.md §15 + #13 this proves the lab actually exercises the
// canonical long-format CSV end-to-end inside the browser. The
// pageerror trap is the standard zero-runtime-error guarantee.
//

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
    await page.goto("/lab/yenask");

    await expect(
      page.getByRole("heading", { name: /Yen-Ask/i }),
    ).toBeVisible();

    // The catalogue boots DuckDB-WASM, registers 4 dim/taxonomy tables,
    // and runs 4 small queries — allow generous time for the wasm cold
    // boot + small Parquet fetches.
    const partyButton = page.locator('[data-canned-id="tn-apr-2021-party-totals"]');
    await expect(partyButton).toBeEnabled({ timeout: 60_000 });

    await partyButton.click();

    // Compiler + executor — the slice is Tamil Nadu only (tamil-nadu).
    const table = page.getByTestId("yenask-answer-table");
    await expect(table).toBeVisible({ timeout: 60_000 });

    // At least one party row; TN AcGenApr2021 has DMK + AIADMK + BJP +
    // INC + several others on record.
    const rows = table.locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);

    // Provenance strip must render with a non-empty publisher-pill row.
    const sourceStrip = page.getByTestId("yenask-source-strip");
    await expect(sourceStrip).toBeVisible();
    // The new SourceList from $lib/sources renders "Source: <publisher>..."
    // even when the provenance ledger collapsed to the synthesised
    // "Source unattested" placeholder pill.
    await expect(sourceStrip.getByText(/^Source:/).first()).toBeVisible();

    // The "how computed" disclosure exists and contains the concept_id.
    // Post-F1.3b the main_sql contains `read_csv(...)` against per-
    // (state, year) candidacies.csv, NOT `election_results`.
    const computation = page.getByTestId("yenask-computation");
    await expect(computation).toBeVisible();
    await computation.locator("summary").click();
    await expect(computation).toContainText("party_totals");
    await expect(computation).toContainText("read_csv(");
    await expect(computation).toContainText("candidacies.csv");
  });
});
