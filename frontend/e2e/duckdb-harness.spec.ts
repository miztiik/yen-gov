// Phase 0.11 — failure-state UX harness assertions.
//
// Drives /dev/duckdb-harness through three paths:
//   1. Real query — boots DuckDB-WASM, registers the Tamil Nadu
//      elections.election_results slice, runs COUNT(*) against the canonical
//      Parquet, and asserts no other election partition was requested.
//   2. Forced manifest 404 — overrides fetch to return 404 for the
//      manifest URL, asserts plain-language copy renders + retry visible.
//   3. Forced unknown table — asks for a table_id not in the manifest,
//      asserts the dataset-not-available copy.
//
// Per D17: the citizen never sees a stack trace. The spec asserts the
// failure-reason text does NOT contain stacky markers ("at ", ".js:", etc).
//
// pageerror trap is attached per CLAUDE.md §15. The intentional manifest
// 404 lives inside the page's fetch override, not as a real request, so
// the trap's requestfailed listener does not fire.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `harness emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("duckdb harness", () => {
  test("real query — wasm round-trip returns the Tamil Nadu slice", async ({ page }) => {
    const electionShardRequests: string[] = [];
    page.on("request", (request) => {
      const url = request.url();
      if (url.includes("/data/elections/") && url.includes("/election_results.parquet")) {
        electionShardRequests.push(url);
      }
    });

    await page.goto("/dev/duckdb-harness");
    await expect(page.getByRole("heading", { name: /DuckDB-WASM failure-state harness/i }))
      .toBeVisible();

    // The page auto-runs the real query on mount; allow time for the wasm
    // boot + ~13 MB Parquet fetch + Arrow round-trip.
    await expect(page.getByTestId("state-ok")).toBeVisible({ timeout: 60_000 });

    await expect(page.getByTestId("state-partition")).toHaveText("tamil-nadu");

    // The harness registers only the Tamil Nadu shard. If the TN corpus grows,
    // this lower bound remains stable while still proving we did not fall back
    // to the full national election table.
    const rowText = await page.getByTestId("row-count").innerText();
    expect(Number(rowText)).toBeGreaterThanOrEqual(20_040);

    const eventText = await page.getByTestId("event-count").innerText();
    expect(Number(eventText)).toBeGreaterThanOrEqual(1);

    expect(electionShardRequests.length).toBeGreaterThan(0);
    expect(electionShardRequests.every((url) => url.includes("/state=tamil-nadu/"))).toBe(true);
  });

  test("forced manifest 404 — plain-language copy + retry, no stack", async ({ page }) => {
    await page.goto("/dev/duckdb-harness");
    await expect(page.getByTestId("state-ok")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("btn-force-404").click();
    await expect(page.getByTestId("state-failed")).toBeVisible({ timeout: 15_000 });

    const reason = await page.getByTestId("failure-reason").innerText();
    expect(reason).toMatch(/data catalogue|could not be fetched/i);
    // D17: no raw stack trace ever reaches the citizen.
    expect(reason).not.toMatch(/\bat \w+/);
    expect(reason).not.toMatch(/\.js:\d+/);
    expect(reason).not.toMatch(/file:\/\//);
    expect(reason).not.toMatch(/Error:/);

    await expect(page.getByTestId("btn-retry")).toBeVisible();
  });

  test("forced unknown table — dataset-not-available copy", async ({ page }) => {
    await page.goto("/dev/duckdb-harness");
    await expect(page.getByTestId("state-ok")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("btn-force-unknown").click();
    await expect(page.getByTestId("state-failed")).toBeVisible({ timeout: 15_000 });

    const reason = await page.getByTestId("failure-reason").innerText();
    expect(reason).toMatch(/not available/i);
    await expect(page.getByTestId("btn-retry")).toBeVisible();
  });
});
