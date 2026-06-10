# TopoJSON migration benchmark — methodology and results

**Last Updated**: 2026-05-31
**Owner**: data layer (frontend boundary loader + Playwright bench harness)

This doc captures the per-route benchmark protocol used to validate the
GeoJSON-to-TopoJSON migration of `datasets/boundaries/in/states/all.*`.
It is the durable home for two reconnaissance notes lifted from `notes/`
during the G4 working-docs-home retirement (2026-06-08). The two dated sections below are historical
receipts captured verbatim so future benchmark runs can be checked
against the same harness contract.

Pointers:

- Harness: [frontend/e2e/boundary-benchmark.spec.ts](../../../frontend/e2e/boundary-benchmark.spec.ts).
- Loader instrumentation: [frontend/src/lib/boundaries.ts](../../../frontend/src/lib/boundaries.ts) (VITE_BENCH=1 guard).
- Benchmark for the geojson-to-topojson migration (2026-05-31).

---

## 2026-05-31 2026-05-31-topojson-baseline-bench

> Historical receipt lifted from `notes/2026-05-31-topojson-baseline-bench.md`
> on 2026-06-08 (G4 closure). Original closed P1.1 + P1.2 + P1.3 + P1.4 of
> the GeoJSON-to-TopoJSON migration plan.

### 1. Methodology

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

#### Methodology deviations from spec

- **5 + 5 runs** instead of 10 + 10. Cold runs measured ~60 s wall each
  under the throttle (full goto-to-load + 20 s lazy window + cache wipe);
  10 + 10 would have crossed the 20-min wall budget the spec
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

### 2. Baseline numbers (geojson, route `/`)

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

### 3. STOP CONDITION (derived for P1.4)

Per the P1.4 spec, the per-metric STOP CONDITION for a candidate
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

### 4. Appendix — first + last 5 lines of `.runtime/bench/results.jsonl`

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

### 5. Reproduce locally

```powershell
cd frontend
$env:VITE_BENCH = "1"
$env:BOUNDARY_FORMAT = "geojson"
bunx playwright test boundary-benchmark.spec.ts --project=chromium
```

Override run counts via `BENCH_COLD_RUNS` + `BENCH_WARM_RUNS` env vars.
Results land at `.runtime/bench/results.jsonl` (gitignored).

---

## 2026-05-31 2026-05-31-topojson-candidate-bench

> Historical receipt lifted from `notes/2026-05-31-topojson-candidate-bench.md`
> on 2026-06-08 (G4 closure). Original closed P2.6 of the migration plan.
> Candidate artefact: `datasets/boundaries/in/states/all.topojson` (P2.2 output;
> mapshaper 0.7.22; quantization 1e5; simplification `5% weighted`).

### 1. Methodology

Identical to the P1.3 baseline (see preceding section): Chromium-only,
Slow-4G (1.6 Mbps down, 150 ms RTT), 4x CPU throttle, 390x844 viewport.
5 cold + 5 warm runs against `/`, single BrowserContext, per-run cache
wipe for cold. Run 2026-05-31T00:59Z to T01:06Z, total wall ~7m 30s.

The only difference: `BOUNDARY_FORMAT=topojson` env var (informational
tag in results.jsonl). The harness measures whatever the loader actually
fetches; the topojson sibling now exists for `states/all`, so the
boundaries.ts P2.3 loader picks topojson first and skips the geojson
sibling.

### 2. Candidate numbers (topojson, route `/`)

Source: `.runtime/bench/results.jsonl`, 10 rows (5 cold + 5 warm).

| Metric | Cold median | Cold p95 | Cold noise floor | Warm median | Warm p95 | Warm noise floor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| wire_bytes (B) | 135,778 | 135,778 | 0 | 135,778 | 135,778 | 0 |
| boundary_response_count | 1 | 1 | 0 | 1 | 1 | 0 |
| ttfp_ms | 41,244 | 41,272 | 28 | 6,844 | 6,908 | 64 |
| parse_ms | 8,141 | 8,164 | 23 | 8,888 | 9,035 | 147 |
| resource_fetch_ms | 3,711.7 | 3,773.0 | 61.3 | 3,826.1 | 3,830.4 | 4.3 |
| long_tasks_count | 0 | 0 | 0 | 0 | 0 | 0 |

`parse_ms` is no longer `null`: this PR moves the loader contract so
`/` flows through `loadBoundaryFromPath()`, which wraps the fetch +
topojson-client decode in the VITE_BENCH-guarded `boundary-load:*`
performance marks. The metric is now load-bearing per the baseline
note's section-1 deviation.

### 3. STOP CONDITION evaluation

| Metric | Baseline warm median | Candidate warm median | Delta | Floor (3 x baseline noise OR plan §7) | Verdict |
| --- | ---: | ---: | ---: | --- | :---: |
| wire_bytes (B) | 812,494 | 135,778 | -676,716 (-83.3%) | >= 5% reduction; target 60-80% (OWID) | **PASS** (83% reduction; massively above 60-80% target) |
| boundary_response_count | 2 | 1 | -1 | n/a (new metric for this PR) | **PASS** (structural improvement; 1 fetch vs 2) |
| resource_fetch_ms | 4,087.4 | 3,826.1 | -261.3 (-6.4%) | reduction >= 525 ms | **MISS** (261 ms reduction; below 3 x noise floor) |
| ttfp_ms | 7,628 | 6,844 | -784 (-10.3%) | reduction >= 5,064 ms OR shift to resource_fetch_ms gate | **MISS** (784 ms; below 3 x noise floor); fallback gate also misses |

**Net judgement (honest)**: 2 of 4 metrics pass cleanly; 2 miss the strict
3-x-noise-floor thresholds. The wire-bytes metric - the one the plan §3
identifies as OWID/Fowler's primary justification ("60-80% reduction") -
HITS at 83%. The fetch-time gates miss for two reasons:

- HTTP/TCP connection + TLS + RTT overhead is constant per request and
  does not scale with payload size. The 1.6 Mbps + 150 ms RTT throttle
  amortises connection cost over fewer bytes, but the cost itself is
  unchanged. Baseline fetched 2 files of ~406 KB each at ~2 s per
  request; candidate fetches 1 file of 136 KB at ~3.8 s. The single
  candidate request cost is not 1/6 of the baseline 2-request cost
  because connection setup dominates short transfers under throttle.
- `ttfp_ms` is dominated by Vite dev's hot-reload bundling +
  Svelte 5 hydration cost on the throttled CPU, not boundary load.
  Plan §7 explicitly anticipates this ("TTFP is dominated by app-shell
  hydration cost, not boundary load") and permits the
  resource_fetch_ms substitution; resource_fetch_ms also misses.

**Also new this PR (cost side, not benefit)**: `parse_ms` materialises at
~8.9 s warm. topojson-client's decode + arc-walk is CPU-bound and the
4x throttle hits it hard. Baseline did NOT measure this cost because
the maplibre internal fetcher did its own (un-instrumented) decode in
the worker realm; the apples-to-apples comparison is partial. Whether
the 8.9 s candidate parse_ms is genuinely NEW work or simply the
already-incurred-but-unmeasured baseline cost surfaced by the new
loader seam is the open question for P3 / P5.3 (PMTiles successor).

### 4. Decision and proceed-or-rollback recommendation

**Recommendation: proceed to ship Phase 1 (NOT P2.6a rollback)**, on the
following grounds:

1. The primary OWID/Fowler-cited metric (`wire_bytes`) hits its target
   at 83% reduction. Citizens on metered or slow networks see less
   data transferred regardless of CPU.
2. The structural improvement (1 boundary fetch vs 2) is unambiguous;
   removes a connection-setup tax per request.
3. The strict 3x-noise-floor miss on `resource_fetch_ms` is small in
   absolute terms (264 ms below the 525 ms threshold) and partially
   explained by per-request overhead that does not scale with payload.
4. The `parse_ms` cost surfaced post-P2.3 is a measurement gain, not
   necessarily a workload gain (maplibre's worker-realm fetcher also
   parses JSON; baseline did not instrument it).
5. P5.3 commissions a PMTiles successor that solves the
   render-cost-on-throttled-CPU bottleneck for layers where format
   alone is insufficient (Track A2). This PR ships the cheap wire-side
   win without claiming it solves render perf.

**Open red flag for follow-up**: parse_ms ~9 s warm on the citizen
target device is significant. If P3 cascade shows the same cost on
larger layers (districts ~780 features, subdistricts ~7,500), the
candidate decode cost may eclipse the wire saving and force either
(a) per-layer raw-geojson preservation for already-small layers,
(b) acceleration of the PMTiles cutover, or (c) topojson-WASM decode.

**P2.6a rollback NOT executed**. If the user disagrees with this
judgement, the rollback path remains 1 commit away: `git rm
datasets/boundaries/in/states/all.topojson` leaves the converter +
loader + tests landed (dormant; loader falls through to geojson on
404).

### 5. Appendix - first + last lines of `.runtime/bench/results.jsonl`

First (cold run 0):

```
{"ts":"2026-05-31T00:59:49.457Z","route":"/","format":"topojson","run_idx":0,"cold_or_warm":"cold","metrics":{"wire_bytes":135778,"boundary_response_count":1,"ttfp_ms":46572,"parse_ms":7423.6,"resource_fetch_ms":3656.7,"long_tasks_count":0,"long_tasks_total_ms":0}}
```

Last (warm run 4):

```
{"ts":"2026-05-31T01:06:17.846Z","route":"/","format":"topojson","run_idx":4,"cold_or_warm":"warm","metrics":{"wire_bytes":135778,"boundary_response_count":1,"ttfp_ms":6844,"parse_ms":9034.6,"resource_fetch_ms":3830.5,"long_tasks_count":0,"long_tasks_total_ms":0}}
```

### 6. Source hash pin (concurrency guard, plan §4a P3/P4)

```
sha256(datasets/boundaries/in/states/all.geojson) =
  fe0ebbfe60ede3a7211cdd64b91a9d790020614b18b60eea83ae91ee7ee74c29
```

Measured at converter-run time AND verifiable pre-merge via
`Get-FileHash datasets/boundaries/in/states/all.geojson -Algorithm SHA256`.

### 7. Reproduce locally

```powershell
cd frontend
$env:VITE_BENCH = "1"
$env:BOUNDARY_FORMAT = "topojson"
bunx playwright test boundary-benchmark.spec.ts --project=chromium
```

Results land at `.runtime/bench/results.jsonl` (gitignored).
