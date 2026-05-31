# Plan - GeoJSON sibling retirement (post-TopoJSON migration cleanup)

**Last Updated**: 2026-05-31
**Status**: PLANNING - awaiting human approval before execution
**Plan-doc level**: Level-5 (cross-cutting; loader simplification, canonical-store retirement, conformance inversion, ADR-0031 amendment, CLAUDE.md anti-pattern)
**Parent plan**: [20260531-geojson-to-topojson-migration-plan.md](20260531-geojson-to-topojson-migration-plan.md) - row P5.4 commissions this
**Mandate origin**: parent plan row P5.4 + user 2026-05-31 "retain geojson until full swap; we will delete in separate plan"
**Worktree discipline**: every PR branches FROM `main`. Confirmed by user 2026-05-31.

## 0. Pre-amble cross-refs (REQUIRED reading before any execution turn)

- [CLAUDE.md](../CLAUDE.md) - Holy Laws #1 (static-first), #3 (contracts before logic), #5 (structural fixes only), #10 (tests ship with feature)
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md)
- [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](20260531-geojson-to-topojson-migration-plan.md) - parent plan
- [docs/architecture/decisions/0031-boundary-geometry-strategy.md](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) - format-split table this plan amends
- [docs/architecture/decisions/0047-topojson-as-render-encoding.md](../docs/architecture/decisions/0047-topojson-as-render-encoding.md) - parent ADR
- [docs/architecture/frontend/topojson-loader.md](../docs/architecture/frontend/topojson-loader.md) - loader doc this plan simplifies
- [docs/how-to/convert-geojson-to-topojson.md](../docs/how-to/convert-geojson-to-topojson.md) - producer runbook
- PRs the parent plan shipped: #486-#496

## 1. Problem statement

Parent plan landed `.topojson` siblings alongside every `.geojson` partition under `datasets/boundaries/in/<layer>/`. The frontend loader prefers topojson, falls back to geojson. That sibling-pair was deliberate: keep geojson around so any encode bug, mapshaper version regression, or missed shard during the cascade has a safety net.

Three Track A2 layers (villages, postal/pincodes via PR #492 #495) shipped TopoJSON but the parent plan commissions a PMTiles successor for those at [TODO/2026-05-31-village-pincode-vector-tiles-plan.md](2026-05-31-village-pincode-vector-tiles-plan.md). When the PMTiles plan lands, those two layers drop their TopoJSON AND geojson siblings together. **This plan focuses on the 8 Track A layers** (country, state, district, subdistrict, AC, PC, ULB-wards, panchayats) where TopoJSON is the durable encoding.

Once every Track A partition has been TopoJSON-served on the live site without fallback warnings for a meaningful window, the `.geojson` siblings are dead weight: ~50MB of redundant bytes on every clone, every CI checkout, every gh-pages deploy. The cleanup removes them, simplifies the loader, inverts the conformance contract, amends ADR-0031, and pins the anti-pattern in CLAUDE.md.

## 2. Phase plan (DAG)

Status flags: `[ ]` not-started, `[~]` in-progress, `[x]` done, `[!]` blocked, `[-]` collapsed

| Phase | Row | Title | Level | Depends-on | Executing agent | PR | Status |
|-------|-----|-------|-------|-----------|-----------------|----|--------|
| **R0**: audit | 0.1 | Walk every Track A partition; assert (a) sibling `.topojson` exists, (b) sidecar matches, (c) feature-count parity. Emit `notes/<date>-track-a-prod-readiness-audit.md` with per-partition green/red status. | 2 | parent plan P4 closed | Fowler | `_pending_` | `[ ]` |
| R0 | 0.2 | Production fallback-warning telemetry: parse 7 days of GH Pages access logs (or browser-side console-warn capture if no server logs) for `[fallback] topojson:*` warnings. Any non-zero count = a partition the loader is silently falling through on; block R3 retirement until those partitions are re-encoded. | 3 | 0.1 | Jony | `_pending_` | `[ ]` |
| R0 | 0.3 | R0 bundle PR (audit + telemetry note + go/no-go verdict) | 2 | 0.1, 0.2 | default | `_pending_` | `[ ]` |
| **R1**: loader simplification | 1.1 | Drop `loadBoundaryFromPath` geojson-fallback branch; remove `loadBoundary` shim; keep `loadBoundaryData` as the sole entry point with topojson-only resolution. | 3 | 0.3 (green) | Jony | `_pending_` | `[ ]` |
| R1 | 1.2 | Update loader unit tests: remove fallback-path cases; add "topojson 404 -> null (caller renders no-data state)" case. | 2 | 1.1 | Jony | `_pending_` | `[ ]` |
| R1 | 1.3 | Remove `boundaryRelPaths()` (used only by the conformance test); inline the topojson path resolution into the conformance test directly. | 2 | 1.1 | Jony | `_pending_` | `[ ]` |
| **R2**: conformance inversion | 2.1 | Invert `frontend/src/contracts/boundaries-conform.test.ts`: from "every topojson has a sibling geojson" to "every Track A partition has a `.topojson` AND no `.geojson` sibling". Track A2 layers (villages, postal) retain their pre-PMTiles state. | 3 | R1 | Jony | `_pending_` | `[ ]` |
| R2 | 2.2 | Update `backend/yen_gov/canonical/boundary_layers_seed.py` to emit `.topojson` as the only physical encoding for Track A in `boundary_layers.parquet` rows. | 2 | 2.1 | Fowler | `_pending_` | `[ ]` |
| **R3**: retire `.geojson` siblings (Track A only) | 3.1 | `git rm` every Track A `*.geojson` under `datasets/boundaries/in/`. Excludes villages (`villages/**`) and postal (`postal/**`). | 2 | R2 | Fowler | `_pending_` | `[ ]` |
| R3 | 3.2 | Verify gh-pages deploy size delta in PR body (target: ~50MB reduction). Verify Vite middleware `serveDatasets()` no longer 404s on legitimate requests. | 1 | 3.1 | Jony | `_pending_` | `[ ]` |
| **R4**: doctrine updates | 4.1 | Amend ADR-0031 format-split table: Track A GeoJSON cells flip to TopoJSON; supporting paragraph mentions ADR-0047 + this plan. | 2 | R3 | default | `_pending_` | `[ ]` |
| R4 | 4.2 | Amend ADR-0047: status from "accepted" (post-parent-plan P5.5) to "accepted, retirement complete for Track A"; cross-link this plan. | 1 | R3 | default | `_pending_` | `[ ]` |
| R4 | 4.3 | Add CLAUDE.md anti-pattern: "Do NOT add `.geojson` siblings to Track A boundary partitions. Track A is topojson-only post-[this plan]." | 1 | R3 | default | `_pending_` | `[ ]` |
| R4 | 4.4 | Update `docs/architecture/frontend/topojson-loader.md` "Conformance invariants" section: invert the sibling-pair rule for Track A; document the Track A2 carve-out. | 1 | R3 | default | `_pending_` | `[ ]` |
| R4 | 4.5 | Update `docs/how-to/convert-geojson-to-topojson.md` "Conformance gates" section: drop the sibling-pair assertion mention. | 1 | R3 | default | `_pending_` | `[ ]` |
| **R5**: distill + archive | 5.1 | Archive this plan-doc with "Plan complete" block per [docs/how-to/distill.md](../docs/how-to/distill.md) | 1 | R4 | default | `_pending_` | `[ ]` |

## 3. STOP CONDITION

Plan terminates when:
- R0.2 telemetry confirms zero `[fallback]` warnings on Track A over the agreed observation window.
- Every Track A partition is `.topojson`-only on disk and on GH Pages.
- Loader has no geojson-fallback branch for Track A; tests cover the topojson-only path.
- Conformance test asserts topojson-only for Track A.
- ADR-0031 amended; ADR-0047 amended; CLAUDE.md anti-pattern added; both runbook docs updated.
- This plan-doc archived.

**Hard gate**: R0.2 telemetry MUST be green. If even one partition silently falls back, that partition is dropped from R3 scope and re-encoded first. No bulk-rm without a clean telemetry window. R3 BLOCKED on R0.2 negative until re-encode.

## 4. Agent dispatch matrix

| Agent | Owns | Escalates to |
|---|---|---|
| **Fowler** | R0.1 audit, R2.2 seed update, R3.1 mass rm + R3.2 size-delta verify | default |
| **Jony** | R0.2 telemetry, R1 loader simplification + tests, R2.1 conformance inversion, R3.2 dev-server smoke | Citizen (citizen-impact verdict if any fallback partition exists) |
| **Gregor** | R2.1 conformance contract review (inversion is a contract break for any external consumer of `datasets/boundaries/in/`; gate-keep) | default |
| **default** | this plan-doc, R0.3 bundle PR, R4 doctrine updates, R5 archive | user |

## 5. Out-of-scope explicit walls

- Track A2 (villages + postal) retirement. Owned by [TODO/2026-05-31-village-pincode-vector-tiles-plan.md](2026-05-31-village-pincode-vector-tiles-plan.md). Those layers retire their geojson + topojson together when PMTiles ships.
- Removing the topojson-client npm dependency. Loader still uses it for Track A.
- Removing the mapshaper devDependency. Producer side still needs it for re-encodes (version bumps, new layers).
- Loader API rename. `loadBoundaryData()` stays as the sole entry point post-R1; no further name churn.
- Retiring `.geojson` from any non-boundary subsystem (livestock, elections, fiscal). Unrelated.
- Server-side rendering. Static GH Pages only.

## 6. Open questions deferred to user

- R0.2 telemetry source: GH Pages does NOT expose access logs. Options: (a) instrument the loader to POST `[fallback]` events to a temporary collector before deciding; (b) declare R0.2 unverifiable + ship R3 on the strength of R0.1 audit + the conformance test alone. Recommend (a) for one observation week, then retire the collector at R5.
- Observation window for R0.2: 7 days proposed. Adjustable.
- Whether R3 is one PR per layer (8 PRs) or one bundle PR (1 PR with ~ several thousand file deletes). Recommend one bundle PR because the per-layer split offers no rollback benefit (the conformance inversion at R2.1 is the load-bearing safety net, not the rm-PR shape).
