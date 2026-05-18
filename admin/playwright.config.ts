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
    // Explicit --host 127.0.0.1 --strictPort matches HOST exactly so the
    // URL probe doesn't race IPv6 (::1) vs IPv4 (127.0.0.1) binding on
    // fresh CI runners — without this vite's default "localhost" binding
    // can resolve to ::1 while the probe hits 127.0.0.1 and times out.
    // Timeout matches frontend (120s) — bun + vite cold-start on a CI
    // runner regularly takes 30-90s before the dev server is reachable.
    // stdout: "pipe" surfaces vite startup logs so a real failure is
    // diagnosable from CI output rather than appearing as a silent
    // timeout.
    command: "bun run dev -- --host 127.0.0.1 --port 5174 --strictPort",
    url: HOST,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
