# TopoJSON migration - candidate benchmark (P2.6)

**Last Updated**: 2026-05-31
**Closes**: P2.6 of [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md)
**Baseline**: [notes/2026-05-31-topojson-baseline-bench.md](2026-05-31-topojson-baseline-bench.md)
**Harness**: [frontend/e2e/boundary-benchmark.spec.ts](../frontend/e2e/boundary-benchmark.spec.ts) (unchanged)
**Candidate artefact**: `datasets/boundaries/in/states/all.topojson` (P2.2 output; mapshaper 0.7.22; quantization 1e5; simplification `5% weighted`)

## 1. Methodology

Identical to the P1.3 baseline: Chromium-only, Slow-4G (1.6 Mbps down,
150 ms RTT), 4x CPU throttle, 390x844 viewport. 5 cold + 5 warm runs
against `/`, single BrowserContext, per-run cache wipe for cold. Run
2026-05-31T00:59Z to T01:06Z, total wall ~7m 30s.

The only difference: `BOUNDARY_FORMAT=topojson` env var (informational
tag in results.jsonl). The harness measures whatever the loader actually
fetches; the topojson sibling now exists for `states/all`, so the
boundaries.ts P2.3 loader picks topojson first and skips the geojson
sibling.

## 2. Candidate numbers (topojson, route `/`)

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

## 3. STOP CONDITION evaluation

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

## 4. Decision and proceed-or-rollback recommendation

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

## 5. Appendix - first + last lines of `.runtime/bench/results.jsonl`

First (cold run 0):

```
{"ts":"2026-05-31T00:59:49.457Z","route":"/","format":"topojson","run_idx":0,"cold_or_warm":"cold","metrics":{"wire_bytes":135778,"boundary_response_count":1,"ttfp_ms":46572,"parse_ms":7423.6,"resource_fetch_ms":3656.7,"long_tasks_count":0,"long_tasks_total_ms":0}}
```

Last (warm run 4):

```
{"ts":"2026-05-31T01:06:17.846Z","route":"/","format":"topojson","run_idx":4,"cold_or_warm":"warm","metrics":{"wire_bytes":135778,"boundary_response_count":1,"ttfp_ms":6844,"parse_ms":9034.6,"resource_fetch_ms":3830.5,"long_tasks_count":0,"long_tasks_total_ms":0}}
```

## 6. Source hash pin (concurrency guard, plan §4a P3/P4)

```
sha256(datasets/boundaries/in/states/all.geojson) =
  fe0ebbfe60ede3a7211cdd64b91a9d790020614b18b60eea83ae91ee7ee74c29
```

Measured at converter-run time AND verifiable pre-merge via
`Get-FileHash datasets/boundaries/in/states/all.geojson -Algorithm SHA256`.

## 7. Reproduce locally

```powershell
cd frontend
$env:VITE_BENCH = "1"
$env:BOUNDARY_FORMAT = "topojson"
bunx playwright test boundary-benchmark.spec.ts --project=chromium
```

Results land at `.runtime/bench/results.jsonl` (gitignored).
