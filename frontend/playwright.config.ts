// Playwright golden-path harness for the static frontend.
//
// Why dev (not preview): the data tier (`/data/...`) is served by the
// `serveDatasets()` middleware in vite.config.ts, which only runs in
// `vite dev`. `vite preview` would 404 every data fetch. CI mirrors the
// dev wiring so the test exercises the same code path the local
// developer hits.
//
// Why two projects (chromium desktop + Pixel 5 mobile): the citizen-target
// (CLAUDE.md "mid-tier Android, patchy 4G") makes the LeftRail's `lg:`
// breakpoint switch (drawer ↔ static rail) the most layout-fragile code in
// the app — running the same specs at 393×851 catches regressions that
// Desktop Chrome doesn't. Firefox/webkit are still descoped: not enough
// browser-specific bugs to justify the CI-minute multiplier.
//
// Accessibility (axe-core, contrast assertions, screen-reader hints) is a
// project-level non-goal per CLAUDE.md §0 — do NOT add @axe-core/playwright
// or aria-* assertions here.
//
// docs/architecture/frontend/overview.md lists the routes under test.

import { defineConfig, devices } from "@playwright/test";

const PORT = 5173;
const HOST = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // serial — single dev server, deterministic order
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: HOST,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-pixel-5", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "bun run dev -- --host 127.0.0.1 --port 5173 --strictPort",
    url: HOST,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
