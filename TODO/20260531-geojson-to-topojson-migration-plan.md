# Plan — GeoJSON to TopoJSON migration (all 10 layers in 2 tracks)

**Last Updated**: 2026-05-31
**Status**: PLANNING — awaiting human approval before execution
**Mandate origin**: 2026-05-31 user request "switch to topojson — we are a data analytics app, not a political science cartography correctness app; losing precision of a few curves of a pixel is acceptable"
**Plan-doc level**: Level-5 (cross-cutting; touches canonical store, lift orchestrators, frontend loader, conformance tests, CI, docs, ADR)
**Worktree discipline**: this work runs on `worker` worktree. **Every PR branches FROM `main`** (NOT from any side branch / NOT from a prior plan-PR's branch). Confirmed by user 2026-05-31.
**Autonomous-execution mandate**: every execution row below specifies `Branch`, `Files`, `Acceptance criteria`, `DoD gates`, `Executing agent`. A fresh subagent reading any single row MUST be able to ship the PR with only `bootstrap.md` + this plan-doc + the row itself loaded into context.

## 0. Pre-amble cross-refs (REQUIRED reading before any execution turn)

- [CLAUDE.md](../CLAUDE.md) — Holy Laws #1 (static-first), #3 (contracts before logic), #6 (no hardcoding), #8 (mature OSS first), #9 (provenance mandatory), #11 (schema versioning)
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) — load before any execution turn
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) — 2-commit-then-squash + 5-gate DoD + post-merge cleanup
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) — boundary partition shape
- [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) — Vite middleware + GH Pages publish
- [docs/architecture/decisions/0031-boundary-geometry-strategy.md](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) — prior boundary-format decision
- [docs/architecture/decisions/0047-topojson-as-render-encoding.md](../docs/architecture/decisions/0047-topojson-as-render-encoding.md) — companion ADR (drafted as P0 R0.1)
- Pattern-to-mimic for orchestrator shape: [tools/boundaries/lift_villages_jk_bhuvan.py](../tools/boundaries/lift_villages_jk_bhuvan.py) (argparse CLI + subprocess + deterministic write)
- Subagent verdicts captured 2026-05-31: Fowler (Mapshaper CLI), Jony (noise-floor methodology), Max (no external sources adopted)

## 1. Scope reckoner — ALL 10 layers in-scope; split into 2 tracks by honest-perf framing

### Track A (TopoJSON wins big — encoding swap is the dominant perf factor)

| Layer | Hive partition | Approx feature count | Why Track A |
|---|---|---|---|
| country | `country/all.geojson` | 1 | Trivial; lowest-risk pilot |
| state | `states/all.geojson` | 36 | India home choropleth; **Phase 1 target** |
| district | `districts/all.geojson` | ~780 | National choropleth; high frequency view |
| subdistrict | `subdistricts/state=in_<lc>/all.geojson` | ~7,500 across ~36 shards | State page drill-down |
| AC (assembly) | `ac/state=in_<lc>/all.geojson` | ~4,100 across ~30 shards | Election surfaces |
| PC (parliament) | `pc/delim=YYYY/all.geojson` | ~543 per delim | Election surfaces |
| ULB-wards | `ulb_wards/...` | varies | Urban governance views |
| panchayats | `panchayats/...` | varies | Rural governance views |

### Track A2 (TopoJSON ships for consistency + honest disclaimer; real perf needs vector tiles)

| Layer | Hive partition | Approx feature count | Track A2 framing |
|---|---|---|---|
| villages | `villages/state=in_<lc>/district=<lgd>/all.geojson` | ~600,000 across hundreds of shards | Convert to TopoJSON for format-consistency + ~30% size win. Browser render-cost (drawing 600k polygons) remains dominant — felt-perf gain is partial. P5.3 commissions PMTiles successor for the real fix. |
| postal (pincodes) | `postal/state=in_<lc>/all.geojson` + `postal/scope=unkeyed/all.geojson` | ~19,000 | Same story at smaller scale. |

**Honest perf framing (locked 2026-05-31)**: Track A's wire-byte reduction (60-80% per Fowler's Mapshaper history) translates to felt-faster on India home + state + district. Track A2's same encoding gives ~30% size reduction but does NOT solve perceived slowness because browser polygon-rendering — not parse/decode — is the bottleneck. The plan does not pretend otherwise. Track A2 still ships so the loader contract is uniform and so the GeoJSON retirement (P5.4) is total.

## 2. Source-ladder reckoner (locked 2026-05-31 per Max's audit)

User's original ladder was `geoBoundaries → udit-001 → convert-existing`. Max's audit found BOTH external sources strip LGD codes from features (geoBoundaries normalises to `shapeName`/`shapeISO`/`shapeID`/`shapeGroup`/`shapeType`; udit-001 hobbyist mirror). Adopting either as canonical breaks every join in `boundary_layers.parquet`.

**Decision: all 10 in-scope layers convert IN-PLACE from existing LGD-keyed GeoJSON sources to TopoJSON. No external source is introduced.** Max's full verdict lands at `notes/2026-05-31-geoboundaries-udit001-source-audit.md` (P0 R0.2) so future agents do not re-litigate.

## 3. Tooling (locked 2026-05-31 per Fowler's verdict)

**Tool**: [Mapshaper CLI](https://github.com/mbloch/mapshaper). Node, single global install, subprocess-invoked from Python lift orchestrators (same pattern as `lift_shared.py` uses for `7z`).

**Invocation shape**:

```bash
mapshaper in.geojson -clean -simplify weighted 5% \
  -o format=topojson quantization=<QUANT> out.topo.json
```

**Quantization — CONFIG-DRIVEN with OWID default**. New file `config/topojson.json` (introduced P2.1) holds per-layer overrides; default is `1e5`:

```json
{
  "$schema_version": "1.0",
  "default_quantization": 100000,
  "simplification": "weighted 5%",
  "per_layer": {
    "states": { "quantization": 100000 },
    "districts": { "quantization": 100000 }
  }
}
```

Converter reads `config/topojson.json`; layers not in `per_layer` use `default_quantization`. Schema-validated per Holy Law #6. The file MUST carry `"$schema"` + `"$schema_version"` per Holy Law #11 (omitted from the snippet above for brevity). Any future per-layer override = 1-line JSON edit, no code change.

**Determinism (locked per Fowler + Gregor red-team 2026-05-31)**:
- Mapshaper version pinned in machine-readable `tools/topojson/.mapshaper-version` (CI reads it; README cites it). Avoids README-vs-CI drift.
- Mapshaper installed via `bunx mapshaper` from `frontend/package.json` devDependency, NOT global `npm i -g`. `bun.lock` is the version contract.
- Converter subprocess inherits `env={**os.environ, "LC_ALL": "C", "LC_NUMERIC": "C"}` to avoid locale-sensitive numeric formatting.
- **`-clean` flag is OPT-IN per layer** via `config/topojson.json` (default OFF). `-clean` mutates topology (gap-fill, sliver removal); silently breaks coordinate + feature-count contracts. Default invocation drops it.
- Idempotency key = `sha256(input) + mapshaper_version + quantization`, stored as sidecar `<output>.topojson.meta.json`. mtime is NOT a contract (git resets mtime on checkout; cross-worktree breaks it).
- If converter ever re-parses + re-emits JSON, use `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
- Version bump of mapshaper = schema-version-style migration.

## 4. Plan execution table (DAG)

Status flags: `[ ]` not-started · `[~]` in-progress · `[x]` done · `[!]` blocked · `[-]` collapsed

| Phase | Row | Title | Level | Depends-on | Executing agent | PR | Status |
|-------|-----|-------|-------|-----------|-----------------|----|--------|
| **P0**: Foundations | 0.1 | Author ADR-0047 (already drafted; ships with PR-0) | 2 | — | default | `#486` | `[x]` |
| P0 | 0.2 | Distill Max's source audit to `notes/2026-05-31-geoboundaries-udit001-source-audit.md` | 1 | — | default | `#486` | `[x]` |
| P0 | 0.3 | PR-0 (plan-doc + ADR + Max-distill) | 2 | 0.1, 0.2 | default | `#486` | `[x]` |
| **P1**: Benchmark scaffolding | 1.1 | Add Playwright bench spec | 3 | 0.3 | Jony | #487 | `[x]` |
| P1 | 1.2 | Add `VITE_BENCH=1` perf-mark instrumentation | 2 | 0.3 | Jony | #487 | `[x]` |
| P1 | 1.3 | Run baseline; publish `notes/2026-05-31-topojson-baseline-bench.md` | 1 | 1.1, 1.2 | Jony | #487 | `[x]` |
| P1 | 1.4 | Stamp plan-doc with derived STOP-CONDITION numbers | 0 | 1.3 | default | n/a | `[x]` |
| **P2**: Phase 1 — India home (state layer) | 2.1 | Add converter + `config/topojson.json` + schema + pytest | 3 | 0.1 | Fowler | #488 | `[x]` |
| P2 | 2.2 | Run converter on `states/all.geojson` | 1 | 2.1 | default | #488 | `[x]` |
| P2 | 2.3 | Extend frontend loader (topo-first, geo fallback) | 3 | 2.2 | Jony | #488 | `[x]` |
| P2 | 2.4 | Extend conformance test for `.topojson` siblings | 2 | 2.3 | Jony | #488 | `[x]` |
| P2 | 2.5 | Add `"topojson"` to format enum | 1 | 2.3 | Jony | n/a | `[-]` |
| P2 | 2.6 | Run candidate bench; verify STOP CONDITION | 1 | 2.2, 2.3, 1.4 | Jony | #488 | `[x]` |
| P2 | 2.7 | Phase-1 PR (P2.1-2.6 bundled) | 3 | 2.6 | Fowler+Jony | #488 | `[x]` |
| **P3**: Track A cascade | 3.1 | Convert `districts/all.geojson` | 2 | 2.7 | Fowler | #489 | `[x]` |
| P3 | 3.2 | Convert subdistrict shards (one PR, ~36 shards) | 2 | 2.7 | Fowler | #489 | `[x]` |
| P3 | 3.3 | Convert `country/all.geojson` (bundle into 3.1) | 1 | 2.7 | Fowler | bundled into #489 | `[x]` |
| **P4**: Electoral + governance + Track A2 | 4.1 | Convert AC shards | 2 | 2.7 | Fowler | #490 | `[x]` |
| P4 | 4.2 | Convert PC shards | 2 | 2.7 | Fowler | #491 | `[x]` |
| P4 | 4.3 | Convert ULB-wards | 2 | 2.7 | Fowler | #493 (partial 1369/3300), #500 (complete 1931/1931) | `[x]` |
| P4 | 4.4 | Convert panchayats | 2 | 2.7 | Fowler | #494 (partial 483/663), `_pending_` (complete 180/180) | `[x]` |
| P4 | 4.5 | Convert villages (Track A2; honest-perf disclaimer in PR body) | 3 | 2.7 | Fowler | #495 (partial 233/659; follow-up needed) | `[~]` |
| P4 | 4.6 | Convert postal/pincodes (Track A2) | 2 | 2.7 | Fowler | #492 | `[x]` |
| **P5**: Distill + cleanup | 5.1 | `docs/how-to/convert-geojson-to-topojson.md` runbook | 2 | all P4 | default | #498 | `[x]` |
| P5 | 5.2 | `docs/architecture/frontend/topojson-loader.md` | 2 | all P4 | default | #498 | `[x]` |
| P5 | 5.3 | Commission `TODO/2026-05-31-village-pincode-vector-tiles-plan.md` (PMTiles successor) | 2 | 2.7 | default | #497 | `[x]` |
| P5 | 5.4 | Commission cleanup PR for `.geojson` retirement | 2 | all P4 | default | #499 | `[x]` |
| P5 | 5.5 | Archive this plan-doc with "Plan complete" block | 1 | 5.1, 5.2, 5.3 | default | `_pending_` | `[ ]` |

## 4a. Per-row execution specs (zero-context subagent execution)

Every row below has everything a fresh subagent needs. The loop: read `bootstrap.md` → read this row → execute → ship PR per [ship-a-pr.md](../docs/how-to/ship-a-pr.md).

### P0.2 — Distill Max source audit
- **Branch**: `feat/topojson-p0r2-source-audit-distillation` (FROM main)
- **Files**: NEW `notes/2026-05-31-geoboundaries-udit001-source-audit.md` (~80 lines: Max's verbatim table + key finding + join-key risk + sample properties)
- **Acceptance**: file exists; cross-linked from this plan §2 + ADR-0047 §Rejected-A
- **DoD gates**: all n/a (notes-only)
- **Executing agent**: default

### P0.3 — PR-0 (plan-doc + ADR + Max-distill)
- **Branch**: `feat/topojson-p0-plan-and-adr` (FROM main)
- **Files**: this plan-doc + ADR-0047 + P0.2's note
- **Acceptance**: 3 files committed; plan-doc + ADR cross-link; ADR status = "proposed"
- **DoD gates**: all n/a (docs-only)
- **Executing agent**: default

### P1.1 — Playwright bench spec
- **Branch**: `feat/topojson-p1r1-bench-spec` (FROM main)
- **Files**: NEW `frontend/e2e/boundary-benchmark.spec.ts` (parametrised by env `BOUNDARY_FORMAT=geojson|topojson`); throttling: Slow-4G (1.6 Mbps down / 750 Kbps up / 150 ms RTT), CPU 4x throttle, viewport 390x844, deviceScaleFactor 2
- **Acceptance**: spec runs green against current main with `BOUNDARY_FORMAT=geojson`; captures Jony's 5 metrics (wire bytes, TTFP, parse cost, long-tasks, screenshot)
- **DoD gates**: Gate 3 svelte-check · Gate 4 vitest · others n/a
- **Executing agent**: Jony

### P1.2 — perf-mark instrumentation
- **Branch**: `feat/topojson-p1r2-perf-marks` (FROM main)
- **Files**: MODIFY `frontend/src/lib/IndicatorChoropleth.svelte` (wrap fetch+parse+addSource in `performance.mark` start/end behind `import.meta.env.VITE_BENCH === '1'` guard)
- **Acceptance**: marks fire only when `VITE_BENCH=1`; zero runtime cost in production build (Vite DCE)
- **DoD gates**: Gate 3 · Gate 4 · others n/a
- **Executing agent**: Jony

### P1.3 — baseline measurement
- **Branch**: `feat/topojson-p1r3-baseline-bench-notes` (FROM main)
- **Files**: NEW `notes/2026-05-31-topojson-baseline-bench.md` (median + p95 + computed noise-floor for each Jony metric across 10-cold + 10-warm runs)
- **Acceptance**: noise-floor computed as `p95 - median` per metric
- **DoD gates**: all n/a (notes-only)
- **Executing agent**: Jony

### P1.4 — STOP-CONDITION stamp
- **Branch**: bundle into P1.3 PR
- **Files**: MODIFY this plan-doc §7 with derived numbers (`>= 3 x noise_floor` substituted with absolute values)

### P2.1 — Converter orchestrator
- **Branch**: `feat/topojson-p2r1-converter` (FROM main)
- **Files**:
  - NEW `tools/topojson/__init__.py`
  - NEW `tools/topojson/convert_layer.py` (argparse CLI: `--input PATH --output PATH --layer NAME [--config config/topojson.json]`; subprocess to mapshaper; reads quantization from config; deterministic; idempotent — skip if output exists and input mtime older)
  - NEW `tools/topojson/README.md` (mapshaper version pin + install instructions)
  - NEW `config/topojson.json` (per §3 shape)
  - NEW `datasets/schemas/topojson-config.schema.json` (validates `config/topojson.json`)
  - NEW `backend/tests/test_topojson_convert_layer.py` (pytest fixtures: tiny 3-feature GeoJSON; assert mapshaper called with right args; output parses; 2x-run byte equality)
- **Acceptance**: `python -m tools.topojson.convert_layer --input datasets/boundaries/in/states/all.geojson --output /tmp/states.topojson --layer states` produces valid TopoJSON; 2x runs byte-identical
- **DoD gates**: Gate 1 validate (new schema) · Gate 2 pytest · others n/a
- **Executing agent**: Fowler
- **Edge cases**: mapshaper not installed → fail-fast with install hint; config missing → use default 1e5 + warn; invalid input → mapshaper's stderr surfaced verbatim

### P2.2 — States converter run
- **Branch**: `feat/topojson-p2r2-states-topojson` (FROM main)
- **Files**: NEW `datasets/boundaries/in/states/all.topojson`
- **Acceptance**: valid TopoJSON; `topojson.feature(t, t.objects.states).features.length === 36`; size delta vs `all.geojson` in PR body
- **DoD gates**: Gate 1 validate · others n/a (no frontend touched yet)
- **Executing agent**: default

### P2.3 — Frontend loader (ADDITIVE; non-breaking signature)
- **Branch**: `feat/topojson-p2r3-loader` (FROM main)
- **Files**:
  - MODIFY `frontend/src/lib/boundaries.ts` — **KEEP `boundaryRelPath()` returning `string` (geo path, unchanged)**. Add NEW sibling `boundaryRelPaths(level, ...args): { topo: string; geo: string }`. Add NEW `loadBoundaryData(level, opts)`: tries topo first, falls back to geo on 404/parse-error/decode-error, logs `[fallback]` warning with reason. The deprecated wrapper at `boundaries.ts` L132-L141 is left untouched.
  - MODIFY callers in `frontend/src/lib/IndicatorChoropleth.svelte` + `frontend/src/lib/maplibre/MapChoropleth.svelte` to use `loadBoundaryData()` (no signature change to existing call sites that use `boundaryRelPath()` — they keep working unchanged).
  - NEW `frontend/src/lib/boundaries.loader.test.ts` (vitest: mock fetch; topo-first; 404 fallback; parse-error fallback; warning fired)
  - ADD `topojson-client` AND `mapshaper` (as devDep) to `frontend/package.json` (regenerate `bun.lock` in SAME commit per CLAUDE.md §9 lockfile rule)
  - MODIFY `frontend/src/lib/canonical/types.ts` — add `"topojson"` to format enum (current: `"parquet" | "geojson" | "pmtiles" | "json"` per L17; verified 2026-05-31 via grep — does NOT currently include topojson, this IS a real additive edit)
  - CO-BUMP `datasets/schemas/manifest.schema.json` (or wherever the manifest `format` enum lives) to include `"topojson"` per CLAUDE.md §11 (minor `x-version` bump + `x-changelog` entry in same commit)
  - Grep sweep: `frontend/src/lib/boundaries.contract.test.ts` calls `boundaryRelPath()` in ~5 places — these CONTINUE working (signature unchanged); extend the test file with positive cases for new `boundaryRelPaths()` shape
- **Acceptance**: `bun run check` returns 0 TypeScript errors (tsc-pass-or-perish sub-gate); loader unit tests pass; existing `boundaries.path.test.ts` + `boundaries.integration.test.ts` + `boundaries.contract.test.ts` continue green (extended, NOT broken)
- **Structural commit split** (one PR, two commits before squash): (a) deps + enum + new sibling functions + tests (compiles, unused); (b) caller switch + conformance extension
- **DoD gates**: Gate 3 svelte-check 0e + `bun run check` 0e · Gate 4 vitest · Gate 5 browser-smoke `/` (loader picks topo when both present)
- **Executing agent**: Jony

### P2.4 — Conformance test extension
- **Branch**: bundle into P2.3 PR
- **Files**: MODIFY `frontend/src/contracts/boundaries-conform.test.ts` — glob `**/*.{geojson,topojson}`; assert every topojson has sibling geojson until P5.4; assert no orphan topojson at undeclared Hive paths; **assert feature-count parity per shard** (`topojson.feature(t, t.objects.X).features.length === geojson.features.length`); do NOT assert coordinate equality (quantization is by design lossy). Also grep + fix any test using `globSync("**/*.geojson")` or hardcoded boundary-file counts under `frontend/src/contracts/**` + `backend/tests/**` BEFORE P2.7 merges.

### P2.5 — types.ts enum (subsumed into P2.3)
- Row collapsed into P2.3 (the format enum widen + manifest schema co-bump are listed there). Kept as a row number for traceability; status flips to `[-]` collapsed when P2.3 ships.

### P2.6 — Candidate bench
- **Branch**: bundle into P2.7 PR
- **Files**: NEW `notes/2026-05-31-topojson-candidate-bench.md` (10-cold + 10-warm against `/` with topojson live). PR body MUST report BOTH raw bytes AND gzip-transfer bytes (GH Pages serves gzipped; raw deltas overstate the win).
- **Acceptance**: P1.4 STOP CONDITION numerically satisfied; if not, P2.7 BLOCKED with explicit diagnosis → trigger P2.6a (rollback row, see below)

### P2.6a — Rollback row (only fires if P2.6 fails)
- **Branch**: `feat/topojson-p2r6a-rollback` (FROM main)
- **Files**: `git rm datasets/boundaries/in/states/all.topojson` (revert P2.2 artefact). LEAVE the converter + config + loader landed (dormant; loader just always falls through to geojson since no topojson sibling exists). Open follow-up plan-doc diagnosing the failure.
- **Acceptance**: `/` still renders identically; conformance test green (no orphan topojson); loader `[fallback]` warning fires for `/states` confirming fallback path works
- **DoD gates**: Gate 1 · Gate 3 · Gate 4 · Gate 5
- **Executing agent**: Fowler
- **STOP**: do NOT proceed to P3 if P2.6a fires; surface to user for re-scope.

### P2.7 — Phase-1 bundle PR
- **Branch**: `feat/topojson-p2-phase1-india-home` (FROM main; NOT stacked on P2.1/P2.2/P2.3 branches — re-do work in one branch if prototyped separately)
- **Files**: union of P2.1-P2.6
- **Acceptance**: 5-gate DoD green; PR body cites candidate-vs-baseline deltas + STOP-CONDITION satisfaction line-by-line
- **DoD gates**: ALL 5 (Gate 5 = `/` shows state choropleth + console shows topojson loaded + NO fallback warning fired)
- **Executing agent**: Fowler (converter) + Jony (frontend) collaborate; default orchestrates

### P3 / P4 rows (template applies to each)
Each row is structurally identical: P2.2 + a slice of P2.6.
- **Branch**: `feat/topojson-p<N>r<M>-<layer>` (FROM main)
- **Files**: NEW `<partition>/all.topojson` for each shard the row covers + bench note IF row touches a citizen-visible route
- **Acceptance**: each topojson valid + sibling geojson untouched + conformance test green + (citizen-visible layers) bench shows no regression
- **Source hash pin (concurrency guard)**: PR body MUST cite `sha256(input.geojson)` measured at converter-run time; pre-merge re-verify hash hasn't drifted (master + schema-row-b worktrees share `datasets/`; parallel agent could mutate the source between P2.2 run and PR merge). Abort + re-run if drift detected.
- **DoD gates**: Gate 1 + Gate 2 + Gate 3 + Gate 4 + Gate 5 (smoke the affected route)
- **Executing agent**: Fowler (Jony review for citizen-facing routes)
- **Track A2 rows (P4.5 + P4.6) — additional kill-switch**: PR body MUST include honest-perf disclaimer AND an explicit STOP-CHECK — *if Jony's bench shows TopoJSON village delta < noise floor AND PMTiles successor (P5.3) is already in flight, DEFER P4.5; villages stay as `.geojson` until PMTiles lands; ADR-0047 amended to acknowledge*. Avoids the sunk-cost trap of shipping a format that's immediately superseded.

### P5.1 / P5.2 / P5.3 / P5.4 / P5.5 — distillation + cleanup
Standard docs PRs (Level-2). Branch FROM main. Follow [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md). Gates 3+4 only.

## 5. Fallback contract (locked 2026-05-31 per Q fallback-semantics)

Per user: "graceful failover — fetch + gap-fill topo; if still gaps then fallback to geo; wherever gap is identified, first thing to do is convert, then apply fallback logic; no user toggle".

Implementation:
1. Loader tries `<path>.topojson` first.
2. On HTTP 404 OR JSON parse error OR `topojson.feature()` decode failure: log `[fallback]` console warning with reason, fetch `<path>.geojson`, render.
3. Conformance test (P2.4) is the upstream gap-detector: every shipped boundary partition has both formats OR (post-P5.4) only topojson. CI fails on gaps.
4. No user-facing toggle.

## 6. Agent dispatch matrix

| Agent | Owns | Escalates to |
|---|---|---|
| **Fowler** | converter (P2.1) + every Track A/A2 converter run (P3.x, P4.x) + CI Mapshaper version pin | default (if blocked on cross-cutting decision) |
| **Jony** | bench spec (P1.1), perf-mark (P1.2), baseline + candidate bench notes (P1.3, P2.6), frontend loader (P2.3-P2.5) | default + Citizen (felt-perf interpretation) |
| **Gregor** | (review only) any row that changes partition shape OR loader contract OR conformance test semantics — vetos contract drift | default |
| **Max** | closed-out after P0.2 — no further dispatch | n/a |
| **Citizen** | bench interpretation ("does Slow-4G + 4x-CPU citizen feel it?") for P2.6 / P3.x / P4.x | Jony |
| **default** | plan-doc edits, ADR edits, distillations, PR orchestration, merge cleanup | user |

**Subagent invocation rule**: when a row says `Executing agent: Fowler`, the orchestrating default agent uses `runSubagent → Fowler (Engineering)` with the row's spec block verbatim as prompt. Subagent ships the PR autonomously; default agent only resumes for merge ceremony + next-row dispatch.

## 7. STOP CONDITION (this plan as a whole)

Plan terminates when:
- P5.5 archive landed.
- All 10 in-scope layers (8 Track A + 2 Track A2) exist as `.topojson` siblings.
- P5.3 successor plan-doc (PMTiles) AND P5.4 cleanup-PR commission BOTH exist (commissioned ≠ executed).
- Both distilled docs (P5.1 + P5.2) live.
- ADR-0047 status flipped to "accepted" (was "proposed" in P0.1).

Per-row Phase-2 STOP CONDITION numbers (derived 2026-05-31 from
`notes/2026-05-31-topojson-baseline-bench.md` § 3; rule = `delta >= 3 *
noise_floor` against the warm-steady-state baseline; route `/`):

| Metric | Warm median (geojson baseline) | Warm noise floor (p95 - median) | 3 x noise floor | Topojson candidate MUST show |
| --- | ---: | ---: | ---: | --- |
| wire_bytes (B) | 812,494 | 0 | 0 | Any measurable reduction; target 60-80% per OWID/Mapshaper precedent (>= 487 KB drop). Absolute floor: >= 5% reduction OR explicit per-PR diagnosis. |
| resource_fetch_ms | 4,087.4 | 175.0 | 525 | Reduction >= 525 ms (median over 5 warm runs). |
| ttfp_ms | 7,628 | 1,688 | 5,064 | Reduction >= 5,064 ms OR explicit acknowledgement that TTFP is dominated by app-shell hydration (in which case `resource_fetch_ms` is the gating metric). |
| parse_ms | null on `/` baseline | n/a | n/a | Becomes load-bearing post-P2.3 once `loadBoundary()` is the canonical topojson-first/geojson-fallback fetcher; add 3 x noise-floor rule then. |

Methodology deviations from the per-row spec (5 + 5 runs, single context,
screenshots dropped) recorded in the baseline note's section 1.

## 8. Open questions deferred to user

None. All ambiguities resolved 2026-05-31.

## 8a. Doctrine notes (added per Gregor 2026-05-31)

- **Provenance**: `.topojson` siblings carry NO new `source_id`. Encoding is a derivative of the existing `source_id`-bearing GeoJSON; `boundary_layers.parquet` row is unchanged across the conversion. (Holy Law #9 satisfied; encoding is not provenance per [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md).)
- **Canonical-store integrity**: doubled `.geojson` + `.topojson` siblings do NOT violate ADR-0030. `boundary_layers.parquet` PK keys ONE layer regardless of how many physical encodings the file system holds; the two siblings are two encodings of one logical layer.
- **ADR-0031 relationship**: ADR-0047 partially supersedes ADR-0031's format-split-by-layer-size table (GeoJSON cells become TopoJSON post-P5.4; PMTiles trigger column unchanged). P5.5 commissions an amendment row on ADR-0031 to update its format-split table.
- **CI time budget**: no CI step walks `datasets/boundaries/**` during the transition window. Tier-B validator is local-only per CLAUDE.md §11; doubling boundary file count does not affect CI wall-clock.

## 9. Out-of-scope explicit walls

- Vector tiles / PMTiles for villages + pincodes as FIRST perf strategy (commissioned P5.3; villages still ship as topojson in P4.5 with honest disclaimer).
- Retirement of `.geojson` siblings (commissioned P5.4; separate plan/PR).
- Adoption of geoBoundaries / udit-001 — REJECTED per Max; do not re-litigate.
- Per-layer quantization tuning beyond default 1e5 — only if Jony's smoke flags artifacts; config-driven shape exists so override is trivial.
- Server-side rendering / SSG — deployment stays static GH Pages.
- Concurrent multi-PR execution from THIS plan — user instruction: this plan's work is strictly serial; other agents may run parallel in disjoint subsystems.

