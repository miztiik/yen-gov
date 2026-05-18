// Admin panels smoke spec.
//
// Strategy: intercept every `/api/...` request via `page.route()` and
// return fixture JSON shaped to match `admin/src/lib/api.ts`. This makes
// the e2e run hermetic (no FastAPI backend needed in CI) and turns the
// spec into a UI contract test against api.ts — the FastAPI side is
// already covered by backend/tests/test_admin_*.py.
//
// Per-panel asserts: heading renders + no pageerror. Click each nav
// button to confirm the App.svelte router switches the panel content.

import { test, expect, type Page } from "@playwright/test";

/** Minimal FastAPI fixture shapes — shaped to api.ts contracts. */
const FIXTURES = {
  health: { status: "ok", version: "0.1.0" },
  inventory: {
    generated_at: "2026-05-18T00:00:00Z",
    stores: [{
      family: "elections", kind: "observations",
      path: "datasets/elections/election_results.parquet",
      size_bytes: 14_772_201, mtime: "2026-05-18T00:00:00Z",
      row_count: 199_330,
      stats: { indicators: 30, entities: 39_568, periods: 27, min_year: 2016, max_year: 2026, sources: 84 },
    }],
    indicators: [{
      family: "elections", indicator_id: "ac-winner-party-id",
      obs_count: 4112, entity_count: 4112, period_count: 27,
      min_year: 2016, max_year: 2026,
    }],
  },
  schemas: {
    schemas: [{
      id: "https://example.org/schema.json", title: "Example",
      x_version: "1.0", last_changelog: null,
      meta_ok: true, meta_errors: [],
      data_files: 5, data_failing_files: 0, data_failures: [],
    }],
    orphan_failures: [],
    summary: { total_schemas: 1, meta_failing: 0, data_failing_files: 0, orphan_files: 0 },
  },
  pipelineRuns: {
    runs: [],
    total: 0,
    active: null,
    allowed_commands: { validate: "Validate datasets" },
  },
};

async function mockApi(page: Page) {
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let body: unknown;
    if (path === "/api/health") body = FIXTURES.health;
    else if (path === "/api/inventory") body = FIXTURES.inventory;
    else if (path === "/api/schemas") body = FIXTURES.schemas;
    else if (path === "/api/pipeline/runs") body = FIXTURES.pipelineRuns;
    else body = {};
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

let errors: string[];

test.beforeEach(async ({ page }) => {
  errors = [];
  page.on("pageerror", e => errors.push(`[pageerror] ${e.message}`));
  page.on("console", msg => {
    if (msg.type() === "error" && !msg.text().includes("Failed to load resource")) {
      errors.push(`[console.error] ${msg.text()}`);
    }
  });
  await mockApi(page);
});

test.afterEach(() => {
  expect(errors, `Admin emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("admin panels", () => {
  test("shell loads, health badge resolves, inventory is default panel", async ({ page }) => {
    await page.goto("/");
    // Sidebar branding
    await expect(page.getByText(/yen-gov/i).first()).toBeVisible();
    // Health badge shows the mocked version
    await expect(page.getByText(/API v0\.1\.0/)).toBeVisible({ timeout: 10_000 });
    // Default panel = Inventory
    await expect(page.getByRole("heading", { name: "Inventory", level: 2 })).toBeVisible();
  });

  test("clicking Schemas nav switches to Schemas panel", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Schemas/ }).click();
    await expect(page.getByRole("heading", { name: "Schemas", level: 1 })).toBeVisible();
  });

  test("clicking Pipeline nav switches to Pipeline panel", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Pipeline/ }).click();
    await expect(page.getByRole("heading", { name: "Pipeline", level: 1 })).toBeVisible();
  });
});
