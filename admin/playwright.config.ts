// Playwright config for the admin app.
//
// Why a separate config (vs reusing frontend's): admin runs on a different
// port (5174), needs its own dev server, and ALL fetch traffic to
// `/api/...` is intercepted via `page.route()` in the specs themselves —
// no FastAPI backend is required for the e2e run. This keeps CI hermetic
// (no python + uvicorn boot step) and the spec assertions narrow (the UI
// contract against `admin/src/lib/api.ts`, not the FastAPI shape itself —
// that's covered by backend/tests/test_admin_*.py).
//
// Single chromium project — admin is desktop-only (operator console), no
// mobile responsiveness commitment.
//
// Accessibility scanning is a project-level non-goal (CLAUDE.md §0).

import { defineConfig, devices } from "@playwright/test";

const PORT = 5174;
const HOST = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
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
  ],
  webServer: {
    // bun is the canonical runner (mirrors frontend/playwright.config.ts).
    // Forwarded `--host 127.0.0.1 --port 5174 --strictPort` makes the
    // bound interface match the Playwright baseURL exactly: Vite 6's
    // default host is `localhost`, which on CI's dual-stack runners can
    // resolve in a way that lags Playwright's 127.0.0.1 readiness probe
    // past the 60s window. Pinning the host eliminates that race; pinning
    // the port (already strictPort in vite.config.ts) makes the contract
    // visible at the test boundary too.
    // Timeout bumped to 120s to match frontend — cold `bun install` plus
    // first vite optimize on a fresh CI runner has been observed >60s.
    // `stdout` switched from "ignore" to "pipe" so a webserver crash is
    // diagnosable in the action log instead of surfacing only as a
    // mysterious timeout.
    command: "bun run dev -- --host 127.0.0.1 --port 5174 --strictPort",
    url: HOST,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
