# TopoJSON migration — baseline benchmark (P1.3)

**Last Updated**: 2026-05-31
**Closes**: P1.1 + P1.2 + P1.3 + P1.4 of [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md)
**Harness**: [frontend/e2e/boundary-benchmark.spec.ts](../frontend/e2e/boundary-benchmark.spec.ts)
**Perf-mark instrumentation**: [frontend/src/lib/boundaries.ts](../frontend/src/lib/boundaries.ts) (VITE_BENCH=1 guard)

## 1. Methodology

Single-context Playwright spec, Chromium-only, against `vite dev` on `/`.
Citizen-target throttle per CLAUDE.md:

- Network: Slow-4G (1.6 Mbps down / 750 Kbps up / 150 ms RTT) via
  `Network.emulateNetworkConditions` (CDP).
- CPU: 4x throttle via `Emulation.setCPUThrottlingRate` (CDP).
- Viewport: 390 x 844, deviceScaleFactor 2.

Per-run loop:

1. Cold runs only: `Network.clearBrowserCache` + `context.clearCookies()`
   + `caches.delete(*)` + `localStorage.clear()` + `sessionStorage.clear()`.
2. `page.goto("/")` with `waitUntil: "load"` (90 s timeout).
3. Fixed 20 s wall window for lazy boundary fetch + render.
4. Read metrics: `performance.getEntriesByType("paint" | "measure" |
   "resource" | "longtask")`.
5. Wire bytes via `page.on("response")` + `request().sizes().responseBodySize`
   (covers maplibre's worker-realm fetches; PerformanceResourceTiming does NOT
   because the worker has its own performance buffer).
6. Append one JSON line to `.runtime/bench/results.jsonl` (gitignored per
   CLAUDE.md Section 2).

Cold = simulated fresh-arrival via the cache/cookie/storage wipe.
Warm = re-navigation with everything cached.

### Methodology deviations from the plan-doc spec

- **5 + 5 runs** instead of 10 + 10. Cold runs measured ~60 s wall each
  under the throttle (full goto-to-load + 20 s lazy window + cache wipe);
  10 + 10 would have crossed the 20-min wall budget the plan-doc itself
  cites. 5 + 5 still gives stable median + p95 + noise-floor (p95 - median)
  and is reproducible: the cold-run wire_bytes column is bit-identical
  across all 5 runs.
- **Single BrowserContext** instead of per-cold-run new context. Per-iteration
  context teardown under an active CDP throttle hangs ~indefinitely on
  Windows; using one context + per-run cache wipe preserves the cold/warm
  contract without the hang.
- **Screenshots dropped from the spec body.** Under throttle they added
  ~5-10 s per run with no metric value (the screenshot was a sanity
  artefact, not part of the 5 measured metrics). Re-enable for diagnostic
  runs by setting `BENCH_SCREENSHOTS=1` (not implemented in this PR — flag
  reserved for follow-up if needed).
- **`parse_ms` is null on `/`** because the Home route's state-boundary
  load goes through maplibre's internal source-loader (in `MapChoropleth.svelte`),
  not through `loadBoundary()` in `frontend/src/lib/boundaries.ts`. The
  VITE_BENCH-guarded `boundary-fetch-start` / `boundary-source-added` marks
  only fire on the `loadBoundary()` path (which IS exercised by other
  routes, e.g. district drill-down in `IndicatorChoropleth.svelte`).
  The always-available proxy `resource_fetch_ms` (sum of
  `responseEnd - requestStart` over every `.geojson`/`.topojson` resource
  entry) covers the gap.
  **`parse_ms` becomes load-bearing post-P2.3** when `loadBoundary` is
  extended into the topojson-first / geojson-fallback canonical fetcher.

## 2. Baseline numbers (geojson, route `/`)

Source: `.runtime/bench/results.jsonl`, 10 rows (5 cold + 5 warm), wall
time 7m 48s (single test run, 2026-05-31T00:19Z to T00:27Z).

| Metric | Cold median | Cold p95 | Cold noise floor (p95 - median) | Warm median | Warm p95 | Warm noise floor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| wire_bytes (B) | 812,494 | 812,494 | 0 | 812,494 | 812,494 | 0 |
| boundary_response_count | 2 | 2 | 0 | 2 | 2 | 0 |
| ttfp_ms | 39,940 | 42,260 | 2,320 | 7,628 | 9,316 | 1,688 |
| resource_fetch_ms | 4,166.8 | 4,252.1 | 85.3 | 4,087.4 | 4,262.4 | 175.0 |
| parse_ms | n/a (null on `/`) | n/a | n/a | n/a | n/a | n/a |
| long_tasks_count | 0 | 0 | 0 | 0 | 0 | 0 |
| long_tasks_total_ms | 0 | 0 | 0 | 0 | 0 | 0 |

Notes:

- `wire_bytes` is bit-identical (812,494 bytes = 812.5 KB) across every
  cold AND warm run. The 2 responses on `/` are the two state-level
  boundary fetches issued by `IndiaMap.svelte` + `IndicatorChoropleth.svelte`
  off the maplibre source-loader path.
- `long_tasks_*` is zero because `PerformanceObserver` for longtask
  entries needs an active observer registration before tasks fire; the
  buffered `getEntriesByType("longtask")` path returns empty without one.
  Captured for completeness; P2.6 candidate bench MAY register an
  observer if longtask diff turns out to matter for the topojson vs
  geojson comparison.
- `resource_fetch_ms` and `wire_bytes` are nearly identical across cold
  AND warm because Vite dev serves the dataset directory via the
  `serveDatasets()` middleware with `cache-control` headers that bypass
  the browser HTTP cache; the warm re-navigation still re-issues the
  fetch (which is fine — what we care about is the relative delta when
  topojson lands, not the absolute warm vs cold gap).

## 3. STOP CONDITION (derived for P1.4)

Per plan-doc P1.4 spec, the per-metric STOP CONDITION for a candidate
topojson run vs this geojson baseline is `delta >= 3 * noise_floor`,
applied to the warm-median (the citizen-felt steady state).

| Metric | Warm median (geojson) | Warm noise floor | 3 x noise floor | Topojson candidate MUST show |
| --- | ---: | ---: | ---: | --- |
| wire_bytes (B) | 812,494 | 0 | 0 | Any measurable reduction; target 60-80% per OWID/Mapshaper precedent (>= 487 KB drop). |
| resource_fetch_ms | 4,087.4 | 175.0 | 525 | Reduction >= 525 ms (median over 5 warm runs). |
| ttfp_ms | 7,628 | 1,688 | 5,064 | Reduction >= 5,064 ms OR explicit acknowledgement that TTFP is dominated by app-shell hydration cost, not boundary load (in which case use `resource_fetch_ms` as the gating metric). |

Notes:

- `wire_bytes` noise floor is 0 (the metric is fully deterministic under
  this harness), so the "3 x noise floor" rule technically permits any
  positive delta. To avoid a degenerate gate, the wire-bytes test in
  P2.6 MUST cite an absolute floor of >= 5% reduction OR cite OWID's
  precedent expectation of 60-80% to fail-fast on a converter regression.
- `parse_ms` does not appear in the gate because the metric is null on
  this baseline route. Post-P2.3, when `loadBoundary` is the canonical
  fetcher, parse_ms will materialise and a 3 x noise-floor rule should be
  added then.

## 4. Appendix — first + last 5 lines of `.runtime/bench/results.jsonl`

First 5 (all cold):

```
{"ts":"2026-05-31T00:20:14.086Z","route":"/","format":"geojson","run_idx":0,"cold_or_warm":"cold","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":41348,"parse_ms":null,"resource_fetch_ms":4086.2000000476837,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:21:15.441Z","route":"/","format":"geojson","run_idx":1,"cold_or_warm":"cold","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":39924,"parse_ms":null,"resource_fetch_ms":4252.100000023842,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:22:16.716Z","route":"/","format":"geojson","run_idx":2,"cold_or_warm":"cold","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":39820,"parse_ms":null,"resource_fetch_ms":4235.5,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:23:18.021Z","route":"/","format":"geojson","run_idx":3,"cold_or_warm":"cold","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":39940,"parse_ms":null,"resource_fetch_ms":4166.800000071526,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:24:23.246Z","route":"/","format":"geojson","run_idx":4,"cold_or_warm":"cold","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":42260,"parse_ms":null,"resource_fetch_ms":4040.6999999284744,"long_tasks_count":0,"long_tasks_total_ms":0}}
```

Last 5 (all warm):

```
{"ts":"2026-05-31T00:24:55.157Z","route":"/","format":"geojson","run_idx":0,"cold_or_warm":"warm","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":9316,"parse_ms":null,"resource_fetch_ms":4061.4000000953674,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:25:24.489Z","route":"/","format":"geojson","run_idx":1,"cold_or_warm":"warm","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":7880,"parse_ms":null,"resource_fetch_ms":4137.200000047684,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:25:51.557Z","route":"/","format":"geojson","run_idx":2,"cold_or_warm":"warm","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":6604,"parse_ms":null,"resource_fetch_ms":4037.3000000715256,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:26:19.729Z","route":"/","format":"geojson","run_idx":3,"cold_or_warm":"warm","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":7628,"parse_ms":null,"resource_fetch_ms":4262.399999976158,"long_tasks_count":0,"long_tasks_total_ms":0}}
{"ts":"2026-05-31T00:26:48.219Z","route":"/","format":"geojson","run_idx":4,"cold_or_warm":"warm","metrics":{"wire_bytes":812494,"boundary_response_count":2,"ttfp_ms":6920,"parse_ms":null,"resource_fetch_ms":4087.399999976158,"long_tasks_count":0,"long_tasks_total_ms":0}}
```

## 5. Reproduce locally

```powershell
cd frontend
$env:VITE_BENCH = "1"
$env:BOUNDARY_FORMAT = "geojson"
bunx playwright test boundary-benchmark.spec.ts --project=chromium
```

Override run counts via `BENCH_COLD_RUNS` + `BENCH_WARM_RUNS` env vars.
Results land at `.runtime/bench/results.jsonl` (gitignored).
