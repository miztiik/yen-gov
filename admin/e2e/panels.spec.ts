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
    events: ["AcGenMay2026"],
    states: { S22: "Tamil Nadu" },
    cells: [{
      event: "AcGenMay2026", state: "S22",
      summary: { total_seats: 234, schema_version: "5.0", path: "datasets/elections/AcGenMay2026/S22/result.summary.json", mtime: "2026-05-01T00:00:00Z", sources: [] },
      parties: "datasets/elections/AcGenMay2026/S22/parties.json",
      sqlite: "datasets/elections/AcGenMay2026/S22/results.sqlite",
      ac_results: { found: 234, expected: 234, missing: 0 },
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
  eciLastSweep: {
    available: false,
    ts: "1970-01-01T00:00:00Z",
    range: [0, 0],
    hits: [], misses: [], errors: [],
  },
  eciPins: {
    payload: { $schema: "x", $schema_version: "1.0", sources: [], pins: [] },
    path: "config/eci-pins.json", schema_id: "x",
    loaded_in_process: [], events: [],
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
    else if (path === "/api/eci/recon/last-sweep") body = FIXTURES.eciLastSweep;
    else if (path === "/api/eci/pins") body = FIXTURES.eciPins;
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

  test("clicking ECI Recon nav switches to EciRecon panel", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /ECI Recon/ }).click();
    await expect(page.getByRole("heading", { name: /ECI Recon/, level: 1 })).toBeVisible();
    // Sub-section heading proves the panel actually mounted (not just the title).
    await expect(page.getByRole("heading", { name: /1\. Enumerate/, level: 2 })).toBeVisible();
  });
});
