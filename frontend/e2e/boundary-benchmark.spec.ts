// Boundary loader benchmark harness for the TopoJSON migration
// (TODO/20260531-geojson-to-topojson-migration-plan.md P1.1/P1.3).
//
// Captures the citizen-felt metrics for the boundary load surface under
// the citizen target (Slow-4G + 4x CPU throttle + 390x844 viewport):
//   1. wire_bytes              from PerformanceResourceTiming.encodedBodySize
//                              (falls back to transferSize when 0)
//   2. ttfp_ms                 first-paint from performance.getEntriesByType
//   3. parse_ms                gap between boundary-fetch-start +
//                              boundary-source-added marks emitted by
//                              loadBoundary() under VITE_BENCH=1. Null when
//                              the active route fetches via the maplibre
//                              internal path (which lives outside the
//                              loadBoundary seam); resource_fetch_ms is
//                              the always-available proxy in that case.
//   4. resource_fetch_ms       sum of (responseEnd - requestStart) over
//                              every .geojson/.topojson resource entry.
//   5. long_tasks_*            count + total duration of long tasks.
//
// Results appended one JSON line per run to .runtime/bench/results.jsonl.
// Format toggle via BOUNDARY_FORMAT env (default "geojson"); the topojson
// run is exercised by P2.6 once converter + loader ship.
//
// Chromium-only: CDP-dependent (Network.emulateNetworkConditions +
// Emulation.setCPUThrottlingRate). Other Playwright projects skip the body.
//
// Single-context design (revised from the plan-doc's per-cold-run-context
// pattern): per-iteration BrowserContext teardown under an active CDP
// throttle hangs ~indefinitely on Windows, so we use ONE context. "Cold"
// simulates fresh-arrival by clearing cookies + storage + caches before
// each navigation; "warm" reuses everything. The trade-off is recorded in
// notes/2026-05-31-topojson-baseline-bench.md "Methodology" section.

import { test, expect, type CDPSession, type Page } from "@playwright/test";
import { appendFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

test.describe.configure({ mode: "serial" });

const BOUNDARY_FORMAT = (process.env.BOUNDARY_FORMAT ?? "geojson").toLowerCase();
const ROUTE = "/";
// Defaults to 5+5 (reduced from the plan-doc's 10+10 after dry-runs
// measured ~80s wall per cold iteration under Slow-4G + 4x-CPU throttle;
// 10+10 exceeded the 20-min budget cited in the plan-doc). 5+5 still
// yields stable median + p95 + noise-floor (=p95-median) per Jony's
// methodology. Deviation documented in PR body + baseline note.
const COLD_RUNS = Number(process.env.BENCH_COLD_RUNS ?? "5");
const WARM_RUNS = Number(process.env.BENCH_WARM_RUNS ?? "5");
const RUNTIME_DIR = resolve(__dirname, "../..", ".runtime/bench");
const RESULTS_PATH = `${RUNTIME_DIR}/results.jsonl`;

interface RunRecord {
  ts: string;
  route: string;
  format: string;
  run_idx: number;
  cold_or_warm: "cold" | "warm";
  metrics: {
    wire_bytes: number;
    boundary_response_count: number;
    ttfp_ms: number | null;
    parse_ms: number | null;
    resource_fetch_ms: number;
    long_tasks_count: number;
    long_tasks_total_ms: number;
  };
}

async function runOne(
  page: Page,
  client: CDPSession,
  runIdx: number,
  coldOrWarm: "cold" | "warm",
): Promise<RunRecord> {
  if (coldOrWarm === "cold") {
    await client.send("Network.clearBrowserCache");
    await page.context().clearCookies();
    try {
      await page.evaluate(async () => {
        try {
          const keys = await caches.keys();
          await Promise.all(keys.map(k => caches.delete(k)));
        } catch {
          /* no caches API on this origin */
        }
        try {
          localStorage.clear();
          sessionStorage.clear();
        } catch {
          /* origin not yet established */
        }
      });
    } catch {
      /* about:blank evaluate may reject on first cold; ignore */
    }
  }

  // Capture wire bytes via the page response stream rather than
  // PerformanceResourceTiming: maplibre fetches its source geojson from a
  // worker realm whose resource entries are NOT visible to the main
  // thread's performance buffer. page.on("response") sees ALL requests
  // including worker-originated ones, so it's the only reliable wire
  // counter for the boundary surface.
  let wireBytes = 0;
  let respCount = 0;
  const listener = async (resp: import("@playwright/test").Response) => {
    try {
      const pathname = new URL(resp.url()).pathname;
      if (!pathname.endsWith(".geojson") && !pathname.endsWith(".topojson")) return;
      // sizes() returns the byte counts from the network response,
      // independent of whether the body was decoded by JS.
      const sizes = await resp.request().sizes();
      wireBytes += sizes.responseBodySize;
      respCount += 1;
    } catch {
      /* response already closed or sizes unavailable; skip */
    }
  };
  page.on("response", listener);

  await page.goto(ROUTE, { waitUntil: "load", timeout: 90_000 });
  // Boundary fetch is lazy on $effect; give it a fixed wall window. 20s
  // covers state-page boundary loads at 1.6 Mbps with 4x CPU.
  await page.waitForTimeout(20_000);

  page.off("response", listener);

  const metrics = await page.evaluate(() => {
    const paints = performance.getEntriesByType("paint") as PerformanceEntry[];
    const firstPaint = paints.find(p => p.name === "first-paint");

    const measures = performance.getEntriesByType("measure") as PerformanceEntry[];
    const boundaryMeasures = measures.filter(m => m.name.startsWith("boundary-load:"));
    const parseMs = boundaryMeasures.length
      ? boundaryMeasures.reduce((acc, m) => acc + m.duration, 0)
      : null;

    const resources = performance.getEntriesByType(
      "resource",
    ) as PerformanceResourceTiming[];
    const boundaryResources = resources.filter(r => {
      const pathname = new URL(r.name).pathname;
      return pathname.endsWith(".geojson") || pathname.endsWith(".topojson");
    });
    const fetchTotalMs = boundaryResources.reduce(
      (acc, r) => acc + (r.responseEnd - r.requestStart),
      0,
    );
    const wireBytes = boundaryResources.reduce(
      (acc, r) => acc + (r.encodedBodySize || r.transferSize || 0),
      0,
    );

    let longTasks: PerformanceEntry[] = [];
    try {
      longTasks = performance.getEntriesByType("longtask") as PerformanceEntry[];
    } catch {
      /* longtask not exposed without a PerformanceObserver registration */
    }

    return {
      ttfp_ms: firstPaint ? firstPaint.startTime : null,
      parse_ms: parseMs,
      resource_fetch_ms: fetchTotalMs,
      wire_bytes: wireBytes,
      boundary_response_count: boundaryResources.length,
      long_tasks_count: longTasks.length,
      long_tasks_total_ms: longTasks.reduce((acc, t) => acc + t.duration, 0),
    };
  });

  return {
    ts: new Date().toISOString(),
    route: ROUTE,
    format: BOUNDARY_FORMAT,
    run_idx: runIdx,
    cold_or_warm: coldOrWarm,
    metrics: {
      wire_bytes: wireBytes,
      boundary_response_count: respCount,
      ttfp_ms: metrics.ttfp_ms,
      parse_ms: metrics.parse_ms,
      resource_fetch_ms: metrics.resource_fetch_ms,
      long_tasks_count: metrics.long_tasks_count,
      long_tasks_total_ms: metrics.long_tasks_total_ms,
    },
  };
}

test("boundary loader benchmark (cold + warm)", async ({ browser }, testInfo) => {
  test.skip(
    testInfo.project.name !== "chromium",
    "CDP throttling is Chromium-only",
  );
  test.setTimeout(20 * 60 * 1000);

  mkdirSync(RUNTIME_DIR, { recursive: true });
  writeFileSync(RESULTS_PATH, "");

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  const client = await context.newCDPSession(page);
  await client.send("Network.enable");
  await client.send("Network.emulateNetworkConditions", {
    offline: false,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
    latency: 150,
  });
  await client.send("Emulation.setCPUThrottlingRate", { rate: 4 });

  for (let i = 0; i < COLD_RUNS; i++) {
    const record = await runOne(page, client, i, "cold");
    appendFileSync(RESULTS_PATH, JSON.stringify(record) + "\n");
  }
  for (let i = 0; i < WARM_RUNS; i++) {
    const record = await runOne(page, client, i, "warm");
    appendFileSync(RESULTS_PATH, JSON.stringify(record) + "\n");
  }

  await context.close();

  expect(COLD_RUNS + WARM_RUNS).toBeGreaterThan(0);
});
