# Plan - PMTiles vector tiles for villages + pincodes (Track A2 perf successor)

**Last Updated**: 2026-05-31
**Status**: PLANNING - awaiting human approval before execution
**Plan-doc level**: Level-5 (cross-cutting; new tooling chain, new frontend tile-source path, retires `.topojson` for two layers, amends ADR-0047)
**Parent plan**: [20260531-geojson-to-topojson-migration-plan.md](20260531-geojson-to-topojson-migration-plan.md) - row P5.3 commissions this
**Mandate origin**: parent plan section 1 Track A2 "honest perf framing" - TopoJSON is the wrong tool for villages (~600k features) + pincodes (~19k features). Browser polygon-render is the bottleneck, not file format. PMTiles fixes that.
**Worktree discipline**: every PR branches FROM `main`. Confirmed by user 2026-05-31.

## 0. Pre-amble cross-refs (REQUIRED reading before any execution turn)

- [CLAUDE.md](../CLAUDE.md) - Holy Laws #1 (static-first), #3 (contracts before logic), #4 (docs = agent memory), #8 (mature OSS first)
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md)
- [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](20260531-geojson-to-topojson-migration-plan.md) - parent plan; honest-perf framing in section 1; commissions this at P5.3
- [docs/architecture/decisions/0031-boundary-geometry-strategy.md](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) - PMTiles trigger column is the relevant prior decision
- [docs/architecture/decisions/0047-topojson-as-render-encoding.md](../docs/architecture/decisions/0047-topojson-as-render-encoding.md) - parent ADR; section "Rejected E" explicitly defers PMTiles for small layers, names PMTiles as the right answer for villages + pincodes
- PRs the parent plan shipped:
  - #486 (P0 plan + ADR) | #487 (P1 bench) | #488 (P2 state) | #489 (P3 cascade) | #490 (P4.1 AC) | #491 (P4.2 PC) | #492 (P4.6 postal) | #493 (P4.3 ULB partial) | #494 (P4.4 panchayat partial) | #495 (P4.5 villages partial) | #496 (batched converter)

## 1. Problem statement

TopoJSON conversion (parent plan P4.5 + P4.6) gave villages and pincodes a ~30% wire-byte reduction. **It did not move felt-perceived perf.** Browser polygon-rendering of 600,000 village polygons is the dominant cost on every state + district drill-down page that draws villages. Same story at smaller scale for ~19,000 pincode polygons.

The right answer for high-feature-count polygon layers in a static-bundle app is **vector tiles**, specifically PMTiles + Mapbox/MapLibre vector-tile rendering. Vector tiles ship the data to the browser already partitioned by zoom + viewport, so the browser draws only what is visible at the current zoom level. This is the well-trodden path used by every major geospatial frontend (OWID's PMTiles deployment, Felt, Protomaps' own demos).

Encoding villages + pincodes as PMTiles, served as static files from the same `datasets/` Hive tree the rest of yen-gov uses, replaces the TopoJSON encoding for those two layers and finally fixes the perceived slowness.

## 2. Tooling decision (proposed, locked at P0 of this plan)

**Tile builder**: [tippecanoe](https://github.com/felt/tippecanoe) (Felt fork of the Mapbox original). Single-binary, deterministic, Node-free, accepts GeoJSON in. Pinned version per the parent plan's mapshaper-version pattern.

**Tile container**: [PMTiles v3](https://github.com/protomaps/PMTiles). Single file per layer per partition. HTTP range-request friendly, no server required, GH Pages compatible.

**Frontend**: MapLibre GL JS already in `frontend/package.json` per parent plan section 0. PMTiles loader via `pmtiles` npm package (or `protomaps-leaflet` if MapLibre coupling is too tight). The frontend already renders raster + GeoJSON tiles on the home + state maps - adding a vector-tile source is additive.

**Source ladder**: same as parent plan section 2 - in-place from existing LGD-keyed GeoJSON / TopoJSON inputs under `datasets/boundaries/in/`. No external source. Tippecanoe consumes GeoJSON not TopoJSON, so input is the already-shipped `all.geojson` per shard.

## 3. Phase plan (DAG)

Status flags: `[ ]` not-started, `[~]` in-progress, `[x]` done, `[!]` blocked, `[-]` collapsed

| Phase | Row | Title | Level | Depends-on | Executing agent | PR | Status |
|-------|-----|-------|-------|-----------|-----------------|----|--------|
| **R0**: ADR + recon | 0.1 | Author ADR-00XX (next free number at draft time) - PMTiles as polygon-rich-layer render encoding | 3 | - | default | `_pending_` | `[ ]` |
| R0 | 0.2 | Recon: tippecanoe install matrix (Windows / WSL / Linux CI), version pin, run on one tiny shard, capture wall-clock + output PMTiles size | 2 | 0.1 | Fowler | `_pending_` | `[ ]` |
| R0 | 0.3 | R0 bundle PR (plan + ADR + recon note) | 2 | 0.1, 0.2 | default | `_pending_` | `[ ]` |
| **R1**: pilot state (villages) | 1.1 | Convert ONE state's village shards (suggest U17 Kerala - small geom; ~1,500 villages) to PMTiles | 3 | 0.3 | Fowler | `_pending_` | `[ ]` |
| R1 | 1.2 | Bench PMTiles vs `.topojson` vs `.geojson` for that state's village drill-down route. Same Playwright harness as parent plan P1. | 2 | 1.1 | Jony | `_pending_` | `[ ]` |
| R1 | 1.3 | Iff bench shows STOP-CONDITION clearance: ship pilot bundle PR | 2 | 1.2 | Fowler+Jony | `_pending_` | `[ ]` |
| **R2**: frontend loader extension | 2.1 | Extend `loadBoundaryData()` (or sibling `loadVectorTiles()`) to prefer `.pmtiles` when sibling exists; fall back to `.topojson` then `.geojson` | 3 | 1.3 | Jony | `_pending_` | `[ ]` |
| R2 | 2.2 | Conformance test: every village shard has EITHER `.pmtiles` OR `.topojson` (not both required post-cascade) | 2 | 2.1 | Jony | `_pending_` | `[ ]` |
| **R3**: cascade (villages) | 3.1 | Convert all remaining village shards (one PR per ~5 states, or one bulk PR if tippecanoe wall-clock is reasonable) | 2 | 2.2 | Fowler | `_pending_` | `[ ]` |
| **R4**: pincodes | 4.1 | Convert all pincode shards to PMTiles (smaller scope, single PR) | 2 | 2.2 | Fowler | `_pending_` | `[ ]` |
| **R5**: retirement + distill | 5.1 | Remove `.topojson` sibling for villages + pincodes (encoded as derivative; retiring the dead branch) | 2 | 3.1, 4.1 | default | `_pending_` | `[ ]` |
| R5 | 5.2 | Amend ADR-0047: mark villages + pincodes as PMTiles-served; cross-link this plan's ADR | 1 | 5.1 | default | `_pending_` | `[ ]` |
| R5 | 5.3 | `docs/how-to/build-pmtiles-layer.md` runbook | 2 | 5.1 | default | `_pending_` | `[ ]` |
| R5 | 5.4 | Archive this plan-doc with "Plan complete" block | 1 | 5.1, 5.2, 5.3 | default | `_pending_` | `[ ]` |

## 4. STOP CONDITION

This plan terminates when:
- All village partitions ship as `.pmtiles` (no `.topojson` sibling); pincode partitions same.
- Frontend loader picks `.pmtiles` first, conformance enforces.
- Jony's bench on one citizen-visible village drill-down route shows render-cost reduction clearing the noise floor (same methodology as parent plan P1).
- ADR amendment landed; runbook landed; plan archived.

R1.3 is a hard gate: if PMTiles bench does NOT clear noise floor on the pilot state, the plan ROLLS BACK at R1 (remove pilot artefact + open follow-up plan-doc diagnosing failure). Do not cascade to R3 / R4 on faith.

## 5. Agent dispatch matrix

| Agent | Owns | Escalates to |
|---|---|---|
| **Fowler** | tippecanoe install + recon (R0.2), every PMTiles build run (R1.1, R3.1, R4.1), CI version pin | default |
| **Jony** | bench (R1.2), loader extension (R2.1), conformance test (R2.2), citizen-perf interpretation | Citizen |
| **Citizen** | "does Slow-4G + 4x-CPU citizen feel the village page is faster?" verdict at R1.2 | Jony |
| **default** | plan-doc + ADR + runbook + archive | user |

## 6. Out-of-scope explicit walls

- PMTiles for state / district / AC / PC / wards / panchayats. Those layers ship as TopoJSON per parent plan and stay there (feature count too small to justify tile overhead).
- Custom tile server. Static files only. PMTiles is the choice precisely because it works over GH Pages range requests.
- Moving to a non-MapLibre renderer. MapLibre GL JS is the established choice.
- Re-litigating geoBoundaries / udit-001 as canonical source. Parent plan section 2 closed that.
- Building a sprite/style system for vector tiles. Inherit the existing choropleth color ramp.
- Real-time tile generation. Tiles are built offline in the lift step, committed (or generated in CI) like every other `datasets/` artefact.

## 7. Open questions deferred to user

- Tippecanoe install in CI: Windows runners have no apt; do we pin a WSL-only build step or commit pre-built tiles? (Recon R0.2 captures wall-clock per shard which informs the answer.)
- Per-zoom feature filtering: tippecanoe lets you drop features at low zoom (zoom 8 villages can be coalesced). Set policy here once recon lands.
- PMTiles file size budget: GH Pages soft limit per file is 100MB. If any partition exceeds that, split into sub-partitions (district / sub-district groupings).
