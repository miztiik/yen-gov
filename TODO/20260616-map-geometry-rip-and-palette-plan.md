# Plan - Map geometry rip-and-replace + island visibility + configurable palette

**Last Updated**: 2026-06-16
**Plan-doc level**: Level-4 (structural; boundary-geometry contract change + renderer-config change + electoral-vintage consolidation). One sub-decision (single delimitation vintage) touches Level-5 doctrine; it is user-ratified in the 2026-06-16 design conversation AND the seat-mis-binding objection is resolved structurally (section 4), so the executing agent does NOT re-pause on it.
**Status**: PLANNING - revised after a 4-persona red-team (Gregor / Fowler / Jony / Hans). Pending user "implement it".
**Strategy**: RIP-AND-REPLACE, no strangler-fig, no prisoners. Each PR is a COMPLETE vertical slice (geometry + the readers that consume it + the tests) so `main` always renders on the new world after each merge. No expand-migrate-contract coexistence phase.
**Worktree discipline**: every PR branches FROM `origin/main`. Park master on `scratch-master-parking` so no worktree owns `main` (clean gh-merge).

## 0. Operating contract

### 0.1 Why this plan exists

The citizen-facing India maps have visible defects, all traceable to one config knob plus two band-aids:

- **Root cause - chunky coasts + crude corpus**: `config/topojson.json` carries `"simplification": "5% weighted keep-shapes"`. `tools/topojson/convert_layer.py` applies that percentage-of-vertices budget to every layer; it deletes coastline detail.
- **Lakshadweep invisibility (independent cause)**: the four d3 map components hard-code `const WIDTH = 640; const HEIGHT = 480;` as the SVG viewBox AND sit in a fixed-height card (`520px` / `420px`). India in Mercator is height-binding, so widening the page only letterboxes the map - the islands stay ~2 px. The reference sites the user cited (data-analytics.github.io, shailendra.me, bharatpashudhan.ndlm.co.in) render wider and taller, and Lakshadweep is visible on the same laptop. Fix: drop the fixed height AND the 640x480, fit the projection to the real container width, let height follow the geography.
- **Band-aid 1 - circle-marker overlay**: `india-party-map-helpers.ts` + 4 components draw `<circle>` dots over sub-threshold areas. Delete entirely (user: "the circles is stupid").
- **Band-aid 2 - state silhouette overlay**: a separately-simplified state outline drawn over sub-state maps; its vertices do not match the fill layer, producing the "ugly outline" on every state. Delete from sub-state maps; keep `state-silhouette.ts` for the TileCartogram "Equal seats" hex arm.

User mandate (2026-06-16): rip-and-replace, stay true to ramSeraph upstream, no geometry simplification, do NOT test the geometry data files, no circles, no insets (zoom-then-click on mobile), keep ONLY the latest delimitation vintage, make the per-topic palette a configurable/detached token system, no prisoners (update live readers in the same rip; do not keep dead paths alive for compatibility).

### 0.2 Hard-coded scope (pre-ratified - do NOT re-litigate)

| # | Decision | Ratifier |
| --- | --- | --- |
| D1 | TopoJSON is used for the country file ONLY (`boundaries/in/country/all.topojson`). Every other layer ships as raw `.geojson`. | User |
| D2 | The country topojson is rebuilt from OUR existing on-disk `.geojson` masters (`in/country`, `in/states`, `in/districts`) via one mapshaper run: `quantization=19000`, arc-shared, NO shape simplification. PRESERVE the live join-key property names verbatim (`State_LGD`, `dist_lgd`). Measured output ~727 KB raw / ~193 KB gz, all 36 states incl Lakshadweep + Ladakh + post-2019 J&K + 785 districts. We do NOT ingest bharatpashudhan's file - our upstream beats it. | User + measurement |
| D3 | NO geometry simplification anywhere. Quantization (integer coordinate rounding) on the country topojson is allowed - lossless, not vertex deletion. | User |
| D4 | Strip ALL non-country `.topojson` siblings + their `.meta.json` idempotency caches across the 9 admin layers + both electoral grains. The country topojson is the only surviving `.topojson`. | User |
| D5 | NO tests on the geometry DATA files. Tests on the CODE that generates / splits / loads geometry stay (they use `tmp_path` / mocks). Exact per-file ledger in section 3. | User |
| D6 | Electoral AC + PC each become ONE country-wide file (no per-state AC shards). | User |
| D7 | Keep ONLY the latest delimitation vintage. Delete `delim=2008` + `delim=2026`. The seat-mis-binding risk is resolved structurally by the dual-key PC mechanism (section 4) + the reorganised-state table-fallback, NOT by keeping `delim=2008`. | User (2026-06-16, round 2) |
| D8 | Source current AC geometry from ramSeraph `LGD_Assembly_Constituencies.geojsonl.7z` - the single national file we already trust. No HTML scraping. | User + Explore |
| D9 | Remove `WIDTH=640; HEIGHT=480` AND the fixed card height from all 4 d3 map components. Container width drives the canvas; height follows the projected geography. This is the Lakshadweep fix. | User + measurement + Jony recipe |
| D10 | Strip circle-marker overlay everywhere (unconditional - no mobile subset). Strip state silhouette overlay from sub-state maps; keep `state-silhouette.ts` for the hex arm. | User |
| D11 | NO Lakshadweep inset, no A&N inset. Mobile citizens zoom-then-click. (The earlier optional-inset row is DELETED.) | User (2026-06-16, round 2) |
| D12 | Per-topic palette = a configurable + detached named-token registry, re-themeable via CSS/Tailwind tokens, components reference palettes by NAME. Topic palettes apply to CATEGORICAL + chrome ONLY; the directional choropleth ramp stays owned by `hueForDirection` (Jony + Hans: direction must win, or the good/bad cue is lost). | User + Jony + Hans |

### 0.3 Measurement receipts (facts the rows depend on)

- Country `in/country/all.geojson`: 1 MultiPolygon, 618 sub-polygons, 281,810 vertices, 12.0 MB. Current 5%-simplified `all.topojson` kept 228 polygons but DID retain 14 Lakshadweep + 63 A&N polygons - islands were never the simplifier's victim; the viewBox + fixed height were.
- OUR upstream rebuilt with mapshaper `quantization=19000` arc-shared, no simplification: combined states+districts = 727 KB raw / 193 KB gz, all 36 states incl Lakshadweep + Ladakh + 785 districts.
- Lakshadweep largest island vs canvas width: 640px -> 2px; 1280px -> 4px; 1600px -> 5px; 1920px -> 6px.
- ramSeraph `LGD_Assembly_Constituencies.geojsonl.7z` carries Delhi 70 + J&K 90 (post-2022) + AP 175 + TG 119 in one national file.
- Election catalogue (`datasets/taxonomy/election_events.json`, 652 events all `complete`): PC events at 2009/2014/2019/2024 = 36 state-slices each; pre-2024 PC = 108 slices. The 2008 Delimitation Order governs PC boundaries for 2009 THROUGH 2024 - they are the SAME polygons; `delim=2008/pc` vs `delim=2024/pc` differ only in JOIN KEY (slug vs numeric), not geometry. Genuine geometry-mismatch tail = J&K assembly pre-2022 (87 vs 90 seats) + Assam assembly pre-2023 (redrawn). AP S01 (2014/2019) + TG S29 (2014/2018/2023) are all post-bifurcation shapes = match current geometry.

### 0.4 ESCALATE triggers (stop ONLY here)

Run AUTO (per `docs/agents/bootstrap.md` autonomy stanza). Stop ONLY when:

1. A JSON-Schema MAJOR bump (1.x -> 2.x) becomes necessary (none expected).
2. Deleting `delim=2008` would remove ELECTION RESULT rows. It must not - D7 deletes GEOMETRY only; `datasets/elections/**` + `datasets/data/datapoints/electoral/**` result CSVs are untouched. No result CSV FKs a geometry path (verified: results FK `entity_id`). If that turns out false, STOP-AND-SURFACE.
3. The dual-key PC reconciliation (section 4) cannot produce a clean slug+numeric join for a pre-2024 PC event whose geometry IS unchanged (i.e. the fix fails on a same-polygon case). Then escalate with the specific failing event.
4. A persona debate fails to converge.
5. The ramSeraph asset is unreachable or its schema differs from the Explore-reported shape (then PR-3 blocks; PR-1/2/4/5 proceed).

### 0.5 Parallelization lanes

```
Lane A (independent):  [ PR-1 component sweep ]      [ PR-4 palette tokens ]
Lane B (sequential):   [ PR-2 admin geometry ] -> [ PR-3 electoral geometry ]
Lane C (last):                                                  -> [ PR-5 docs ]
```

- PR-1 (render-only, no geometry files) and PR-4 (colors lib) are independent of everything and of each other - fully parallel from t=0.
- PR-2 then PR-3 are sequential: PR-3's electoral repoint assumes PR-2's loader switch + country topojson have landed.
- PR-1 touches the 4 map components; PR-2 also edits `IndiaPartyMap.svelte` (its geometry fetch path). To avoid a collision, PR-1 lands FIRST on the components, PR-2 rebases onto it. If both are in flight, PR-1 has merge priority on the shared components.
- PR-5 (docs) lands after PR-2 + PR-3 so it documents the final shape.

### 0.6 Strategy ruling + persona-review receipt

Rip-and-replace (Fowler + user): GitHub is the backup; the geometry corpus regenerates from upstream in under two hours; no consumer needs old+new shapes to coexist. NO expand-migrate-contract - each PR is a complete slice, readers repointed in the same PR as the geometry change, so no broken intermediate ships to production.

This plan was red-teamed by four personas on 2026-06-15/16. Their binding edits are folded in:

- **Gregor (BLOCK -> resolved)**: (G1) preserve `State_LGD`/`dist_lgd` join keys verbatim - do NOT rename to `st_lgd`/`dt_lgd` (would blank every map). (G2) delim deletion orphans `INDIA_PC_2008` + 31 `STATE_AC` registry entries + `boundary_layer.csv` rows + `election_tile_layouts.json` provenance - all repointed in PR-3, not silently deleted. (G3) the country topojson carries 3 objects; the loader must address objects BY NAME, not `objectKeys[0]`. (G6) the national AC join key `lgd_ac_id` is DERIVED post-hoc by `lift_boundary_lgd_ac_id.py`, not shipped by ramSeraph - PR-3 replays it + the AP/TG `ac_no` rewrite + the J&K `seat_id` path.
- **Fowler (SHIP-WITH-EDITS)**: live readers fetch deleted paths -> repoint in the same slice. ~10 of the originally-listed "delete" tests are mocked/pure and STAY (section 3). `no-frontend-corpus-explosion.test.ts` is the guardrail that enforces "no test walks the geometry corpus" - KEEP unconditionally. Add compensating code-level tests C1-C6 (C2 non-negotiable: island survives the country build).
- **Jony (SHIP-WITH-EDITS)**: the Lakshadweep fix needs the fixed card HEIGHT dropped too (not just the 640x480) + `geoMercator().fitWidth(container_w)` + dynamic height via `aspect-ratio` + reset the d3-zoom transform on resize. Palette must NOT override `hueForDirection` on choropleths.
- **Hans (BLOCK D7 -> resolved structurally)**: forcing pre-2024 results onto 2024 geometry mis-binds seats ONLY where (a) the join key differs or (b) the polygons genuinely changed. (a) is fixed by the dual-key PC mechanism (section 4 - same polygons, both keys indexed). (b) is fixed by table-fallback for the bounded reorganised-state tail (J&K pre-2022, Assam pre-2023) - show the results table, draw no choropleth. Net: a fill is drawn ONLY where it is correct. Topic-palette hue is subordinate to indicator direction on every directional choropleth.

## 1. Status Reckoner

| Row | Lane | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- | --- |
| **PR-1** | A | Component sweep: strip circles + strip sub-state silhouettes + Lakshadweep fit-fix (drop fixed height, fitWidth, zoom-reset) + trim the marker/geometry component tests | [ ] PENDING | _pending_ | ~1 day |
| **PR-2** | B | Admin geometry: rebuild country topojson (q19000, arc-shared, no-simplify, keep `State_LGD`/`dist_lgd`, states+districts objects) + loader topojson-by-named-object + repoint `IndiaPartyMap` + strip all non-country `.topojson` + delete 6 geometry tests + add compensating tests C1/C2/C4 | [ ] PENDING | _pending_ | ~1 day |
| **PR-3** | B | Electoral geometry: ingest ramSeraph current AC -> one `delim=2024/ac/all.geojson` (replay `lgd_ac_id` + AP/TG `ac_no` rewrite + J&K `seat_id`) + dual-key `delim=2024/pc` + delete `delim=2008`/`delim=2026` + repoint 31 `STATE_AC` + collapse `INDIA_PC_2008` + reorganised-state table-fallback + update ledger + tile-layout provenance + rewrite layout test + update 2 e2e URLs | [ ] PENDING | _pending_ | ~1.5 days |
| **PR-4** | A | Configurable + detached palette token system (`palettes.ts` + `topic-palette.ts`, tokenize `hueForDirection`'s 3 hues; topic palettes categorical/chrome only) | [ ] PENDING | _pending_ | ~1 day |
| **PR-5** | C | Docs reconciliation: rewrite `map.md` boundary section + `electoral/README.md` + canonical-store boundary note to the new doctrine | [ ] PENDING | _pending_ | ~0.5 day |

## 2. Per-PR specifications

### PR-1 - Component sweep (Lane A, render-only)

**Owner**: Jony + Fowler. **No geometry data files touched** - maps keep rendering on the existing geometry; the visible win is islands appear + clutter gone.

**Scope**:
1. **Strip circles (D10)**: delete the marker section of `frontend/src/lib/charts/india-party-map-helpers.ts` (`SUB_THRESHOLD_PX`, `MarkerOverlay`, `pathSpan`, `isSubThreshold`, `projectedCentroid`, `computeSubThresholdMarkers`); KEEP `resolveStateClickAction`. Strip the marker import + `$derived<MarkerOverlay[]>` + template `<circle>` from `IndiaPartyMap.svelte`, `IndiaPcMapD3.svelte`, `StateAcMapD3.svelte`, `StatePcMapD3.svelte`. Rewrite the module-top JSDoc that cites the 14px marker.
2. **Strip sub-state silhouettes (D10)**: in `StateAcMapD3.svelte` + `StatePcMapD3.svelte` delete `loadStateSilhouette` import, `SILHOUETTE_STROKE`, the `silhouette_feature = $state` + loader `$effect`, the template silhouette `<path>`. Narrow `frontend/src/lib/elections/ElectionMap.svelte` so any silhouette load fires only when `view === "hex"`. KEEP `frontend/src/lib/state-silhouette.ts` (hex arm).
3. **Lakshadweep fit-fix (D9, Jony recipe)**: in all 4 components remove `const WIDTH = 640; const HEIGHT = 480;` AND the fixed wrapper height (`520px`/`420px`). Replace `geoMercator().fitSize([640,480], fc)` with fit-to-width:
   ```ts
   let container_w = $state(960);            // bind:clientWidth on the wrapper
   const layout = $derived.by(() => {
     if (!collection || container_w <= 0) return null;
     const w = Math.min(container_w, MAX_MAP_W);          // national clamp ~900
     const projection = geoMercator().fitWidth(w, collection);
     const [[x0, y0], [x1, y1]] = geoPath(projection).bounds(collection);
     const t = projection.translate();
     projection.translate([t[0] - x0, t[1] - y0]);        // re-origin to 0,0
     return { projection, path: geoPath(projection), w, h: Math.ceil(y1 - y0) };
   });
   ```
   SVG: `viewBox="0 0 {layout.w} {layout.h}"` + `width="100%" style="height:auto; aspect-ratio:{layout.w}/{layout.h};"`. On a `container_w` change, reset the zoom transform: `select(svg_el).call(zoom_behavior.transform, zoomIdentity)` (else the `<g>` keeps a stale transform and the map jumps).
4. **Tests**: trim the geometry-parse + marker describes from `IndiaPartyMap.test.ts` + `StateAcMapD3.test.ts` (keep any pure block; if none remains, whole-delete). Any kept block that reconstructs projected coordinates against `fitSize([640,480])` is geometry-coupled - delete it.

**Gates**: vitest + svelte-check green; browser smoke at >=1280px on `/` (screenshot: Lakshadweep visibly painted) AND `/tamil-nadu/elections/<event>` (no ghost outline, no circles) AND `/tamil-nadu/elections/<event>?view=hex` (hex silhouette intact).
**Oracle PR-1**: no `WIDTH = 640` / `SUB_THRESHOLD_PX` / sub-state silhouette `<path>` remains in the 4 components; the 1280px home screenshot shows the Lakshadweep cluster >= 4px; the hex arm still draws its silhouette.

### PR-2 - Admin geometry (Lane B)

**Owner**: Fowler + Gregor. Data-shape: Hans + Max fold into the property-set choice.

**Scope**:
1. **Rebuild country topojson (D2/D3)**: add `tools/topojson/build_country.py` - one mapshaper run combining `in/states/all.geojson` + `in/districts/all.geojson` (+ country outline) into `in/country/all.topojson` with `quantization=19000`, arc-shared, NO `-simplify`. **PRESERVE join keys verbatim**: the `states` object's features keep `State_LGD`; the `districts` object's features keep `dist_lgd` (Gregor G1 - do NOT rename). Edit `config/topojson.json` to remove the `5% weighted` simplification knob; bump `topojson-config.schema.json` MINOR if the knob shape changes.
2. **Loader topojson-by-named-object (D1, Gregor G3)**: extend `frontend/src/lib/boundaries.ts` so `loadBoundary` decodes a multi-object topology by an explicit object name (e.g. `loadBoundary("country", { object: "states" })`), NOT `objectKeys[0]`. Country level reads `all.topojson`; every other level reads `.geojson` directly (no topo-first probe -> no guaranteed 404, Gregor G4).
3. **Repoint `IndiaPartyMap.svelte`**: it fetches `/boundaries/in/states/all.topojson` today; point it at the new combined `country/all.topojson` requesting the `states` object.
4. **Strip non-country topojson (D4)**: `git rm` every `*.topojson` + `*.topojson.meta.json` under `in/{states,districts,subdistricts,blocks,panchayats,villages,wards,postal}`. `in/country/all.topojson` is the only survivor.
5. **Tests**: delete the 6 geometry-parse tests (section 3 DELETE rows that are admin-scoped). Add compensating tests: **C1** (`build_country.py` output object-shape, tmp_path), **C2 NON-NEGOTIABLE** (island survives: fixture incl LGD-31 Lakshadweep; assert it lands in both `states` and `districts` objects by name), **C4** (loader country-object-selection, mocked fetch).

**Gates**: vitest + svelte-check + `python -m yen_gov validate --root .` green; browser smoke on `/` (national states choropleth paints with real fills, NOT all-grey - proves join keys preserved) + `/tamil-nadu` (district drill).
**Oracle PR-2**: `git ls-files "datasets/boundaries/**/*.topojson"` returns exactly `datasets/boundaries/in/country/all.topojson`; its `states` object first feature carries `State_LGD`, its `districts` first feature carries `dist_lgd`; the home map paints non-default fills.

### PR-3 - Electoral geometry (Lane B, after PR-2)

**Owner**: Gregor + Fowler + Hans (table-fallback copy).

**Scope**:
1. **Ingest current AC (D6/D8, Gregor G6)**: add `tools/boundaries/ingest_ac_2024.py` - download `LGD_Assembly_Constituencies.geojsonl.7z`, decompress, write ONE national `datasets/boundaries/electoral/delim=2024/ac/all.geojson`. Replay the existing derivations so the join keys match what consumers read: `lgd_ac_id` via the `lift_boundary_lgd_ac_id` logic, the AP/TG `ac_no` rewrite (`snapshot.py` `by_name_to_sot_eci_no`), and carry `seat_id` for J&K post-2022. Carry `st_lgd` for per-state filtering.
2. **Dual-key PC (section 4)**: ensure `delim=2024/pc/all.geojson` carries BOTH `eci_no` (numeric) and `name_slug` per feature, so 2009/2014/2019 slug-keyed results AND 2024 numeric-keyed results both join to the identical 2008-Order polygons.
3. **Delete old vintages (D7)**: `git rm -r delim=2008 delim=2026`.
4. **Repoint readers (Gregor G2, no prisoners)**: collapse `INDIA_PC_2008` -> `INDIA_PC` in `frontend/src/lib/boundaries/sources.ts` and both routes (`NationalElection.svelte`, `StateElection.svelte`) now select `INDIA_PC` for all PC events, joining via whichever key the result carries (dual-key handles both). Repoint all 31 `STATE_AC` entries to the one national `delim=2024/ac/all.geojson` + add an `st_lgd` filter inside `StateAcMapD3.svelte` (the national file is not pre-filtered per state - this is a code change, not just a path swap).
5. **Reorganised-state table-fallback (Hans)**: for events whose geometry genuinely changed (J&K assembly pre-2022; Assam assembly pre-2023), the route renders the results TABLE and skips the choropleth (no fill drawn where it would be wrong). Gate this on a small explicit event-set, not a heuristic.
6. **Ledger + provenance**: re-run the boundary-layer seed so `datasets/data/entities/boundary_layer.csv` reflects post-rip disk truth (drop 31 `delim=2008` AC rows + the `delim=2008.pc` row; add the `delim=2024.ac` national row). Repoint or accept-with-receipt the `delim=2008` `source_id` strings in `datasets/grapher/election_tile_layouts.json` + the `tools/gen_election_tile_layouts.py` `AC_DIR`.
7. **Tests**: delete `test_ac_parity_per_state.py`; REWRITE `test_electoral_boundaries_layout.py` to the single-vintage grammar; update the asserted boundary URLs in `frontend/e2e/state-ac-coverage.spec.ts` + `frontend/e2e/e3-silhouette-smoke.spec.ts`; update the `delim=2008` path filter in `.github/workflows/e2e-ac-full.yml`. Add **C3** (`ingest_ac_2024.py` feature-count + 4-set presence + key-derivation, tmp_path) + **C5** (rewritten layout gate) + **C6** (join-key extraction from an in-memory FC).

**Gates**: vitest + svelte-check + pytest + validate green; browser smoke on `/t/elections/general-2024` (PC atlas, numeric join) + `/t/elections/general-2019` (PC atlas, slug join onto same polygons - paints correctly) + `/tamil-nadu/elections/<AC event>` (state AC from national file + filter) + one reorganised-state event (e.g. J&K pre-2022 assembly: table renders, no broken choropleth).
**Oracle PR-3**: `datasets/boundaries/electoral/` lists only `delim=2024` + `README.md`; `delim=2024` has `ac/all.geojson` + `pc/all.geojson`; `git grep -n "delim=2008" frontend/src datasets/data/entities/boundary_layer.csv` returns nothing live; the 2019 PC atlas paints correct per-seat fills (dual-key proven); the J&K-pre-2022 event shows a table with no map error.

### PR-4 - Configurable + detached palette token system (Lane A, independent)

**Owner**: Jony (named set) + Hans (topic semantics).

**Design (D12, Jony module shape - one source of truth)**:
- `frontend/src/lib/colors/palettes.ts` (NEW): `RAMP_HUES = { positive: 160, negative: 25, neutral: 250 }` (the 3 direction hues, tokenized) + `CATEGORICAL_PALETTES: Record<string, string[]>` (ColorBrewer-style named enums: `set2`, `paired`, etc., as OkLCh). A `rampHue(k)` + palette accessor that reads a CSS custom property (`--ramp-positive`, `--palette-*`) when present and falls back to the JS value (mirrors the existing `--party-neutral` token + `getComputedStyle` guard so SSR/vitest still resolve a colour). This is the "detached / re-themeable via CSS" requirement.
- `frontend/src/lib/colors/topic-palette.ts` (NEW): `TOPIC_CATEGORICAL: Record<string, keyof typeof CATEGORICAL_PALETTES>` mapping topic family -> a categorical palette name. One assignment per family, in one place.
- EDIT `frontend/src/lib/indicators.ts` `hueForDirection` to read `rampHue("positive"|"negative"|"neutral")` instead of the hard-coded 160/25/250. It STAYS the single source for the directional choropleth ramp.
- EDIT `frontend/src/lib/colors/anchors-domain.ts` `dimensionAnchors` (today only `power_source`) to consume `CATEGORICAL_PALETTES` by name.
- **Hard rule (Hans + Jony)**: topic palettes feed CATEGORICAL fills + page chrome + neutral-direction indicators ONLY. A `lower_is_better` / `higher_is_better` choropleth ALWAYS resolves its ramp through `hueForDirection`. There is NO topic->choropleth-hue map.

**Gates**: vitest + svelte-check green; browser smoke on one indicator page per 2-3 topic families (distinct categorical palettes) + one `lower_is_better` map (still red ramp, not topic hue).
**Oracle PR-4**: a contract test asserts (1) every live topic family resolves to a registered categorical palette; (2) each `Direction` resolves to a registered ramp-hue token; (3) there is NO topic->choropleth-hue mapping.

### PR-5 - Docs reconciliation (Lane C)

**Owner**: default.
**Scope**: rewrite `docs/architecture/frontend/map.md` boundary-pipeline section (it still describes MapLibre + PMTiles + tippecanoe + per-state AC shards - replace with: d3-geo sole renderer, country=topojson, all-else=geojson, single delim vintage, dual-key PC, no simplification, fit-to-width projection). Confirm `datasets/boundaries/electoral/README.md` single-vintage grammar (PR-3 may have done it; PR-5 verifies). Add a boundary note to `docs/architecture/data/canonical-store.md` if it references old shards.
**Gates**: markdown only; ASCII-only; cross-links resolve.
**Oracle PR-5**: `git grep -nE "tippecanoe|PMTiles|5% weighted|delim=2008|per-state AC shard" docs/` returns only archive/historical references, none as current doctrine.

## 3. Test ledger (verified file-by-file 2026-06-16)

**DELETE whole file (7)** - they `readFileSync` / walk on-disk `datasets/boundaries/**`:
`frontend/src/contracts/election-tile-layout-coverage.test.ts`, `frontend/src/contracts/topojson-island-render.test.ts`, `frontend/src/contracts/state-silhouette-smoke.test.ts`, `frontend/src/contracts/census-code-2011-coverage.test.ts`, `frontend/src/contracts/boundaries-conform.test.ts`, `frontend/src/lib/boundaries.contract.test.ts`, `backend/tests/test_ac_parity_per_state.py`.

**PARTIAL - trim geometry/marker describes, keep pure blocks (2)**:
`frontend/src/lib/charts/IndiaPartyMap.test.ts` (keep `resolveStateClickAction`), `frontend/src/lib/charts/StateAcMapD3.test.ts` (keep paint-formula if pure). If no pure block remains after trimming, whole-delete.

**REWRITE to new grammar (1)**:
`backend/tests/test_electoral_boundaries_layout.py` (path-existence gate -> single `delim=2024` vintage).

**KEEP but update the asserted boundary URL (2 e2e)**:
`frontend/e2e/state-ac-coverage.spec.ts`, `frontend/e2e/e3-silhouette-smoke.spec.ts` (they `waitForResponse` on `delim=2008` / `states/all.topojson` URLs; update the strings).

**KEEP THE GUARDRAIL (1) - unconditional**:
`frontend/src/contracts/no-frontend-corpus-explosion.test.ts`. It is the test that REJECTS any future test doing `broad-dataset-glob` or `generated-tests-from-corpus-list` over the geometry corpus - it mechanises the user's "don't test the data files" rule. Never delete it.

**KEEP untouched - mocked / pure / fixtures / registry-constants (16)**:
`boundaries.integration.test.ts`, `boundaries.path.test.ts`, `boundaries.loader.test.ts`, `state-silhouette.test.ts`, `india-pc-map-helpers.test.ts`, `choropleth-entity-context.test.ts`, `state-panchayats-registry-coverage.test.ts`, `state-blocks-registry-coverage.test.ts`, `state-wards-registry-coverage.test.ts`, `state-ac-registry-coverage.test.ts`, `state-panchayats-shards-coverage.test.ts`, `state-wards-shards-coverage.test.ts`, `datasets-conform.test.ts`, `boundary-benchmark.spec.ts`, `backend/tests/test_boundary_layers_seed.py`, `backend/tests/test_derive_hive_signature.py`, `backend/tests/test_boundary_snapshot_ac_no_rewrite.py`.

**Compensating CODE tests to ADD (use tmp_path / mocks, never walk the corpus)**:
- **C1** - `build_country.py` output object-shape (states+districts objects, counts, join keys present).
- **C2 (NON-NEGOTIABLE)** - island survival: fixture incl LGD-31 Lakshadweep; assert it lands in both objects by name. Replaces the deleted island-render guard.
- **C3** - `ingest_ac_2024.py` feature-count + Delhi/J&K/AP/TG presence + key derivation.
- **C4** - loader country-object-selection (mocked fetch).
- **C5** - rewritten electoral layout gate (path-existence, single vintage).
- **C6** - join-key extraction (`State_LGD`/`dist_lgd`/`lgd_ac_id`) from an in-memory FeatureCollection.

Headline: **7 whole-delete + 2 trim + 1 rewrite + 2 e2e-URL-update + 6 added**. Everything else (17 incl. the guardrail) is untouched. The earlier "~19-20 deletes" estimate was wrong by ~2x.

## 4. The dual-key PC mechanism (how single-vintage stays honest)

The objection (Hans, verified): deleting `delim=2008` and rendering pre-2024 PC results on `delim=2024` geometry can mis-bind seats. Root cause is NOT the polygons (the 2008 Delimitation Order governs PC shapes for 2009-2024 - identical geometry) but the JOIN KEY: `INDIA_PC` joins numeric `<state>_<eci_no>`; old results were slug-keyed because canonical `eci_no` is unreliable for 2008-vintage PCs.

Fix: `delim=2024/pc/all.geojson` carries BOTH keys per feature - `eci_no` (numeric, for 2024 results) AND `name_slug` (for 2009/2014/2019 results). The renderer joins on whichever key the result row provides. Same polygon, two indexes, zero results-data backfill, one geometry file. This is strictly better than keeping `delim=2008`: one vintage on disk, full historical capability preserved.

The residual - events where the polygons GENUINELY changed (J&K assembly pre-2022: 87 vs 90 seats; Assam assembly pre-2023: redrawn) - get the **table-fallback**: render the results table, draw no choropleth. You cannot honestly draw a 90-seat map for an 87-seat election; a table is the truthful surface. AP/TG post-2014 events already match current geometry, so they need nothing special.

Net: a choropleth fill is drawn ONLY where it is provably correct. Everywhere else, a table. No wrong-seat colour anywhere. This satisfies the citizen-honesty bar WITHOUT a second geometry vintage.

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change. Each PR is a COMPLETE slice (geometry + readers + tests) - no broken intermediate ships.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Run Lane A (PR-1, PR-4) in parallel with Lane B (PR-2 -> PR-3). Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked. NEVER add a test that parses an on-disk geometry file (D5) - the `no-frontend-corpus-explosion` guardrail will reject it anyway.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (section 0.4), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

## 5. Cross-references

- [CLAUDE.md](../CLAUDE.md) - Holy Laws #1 (static-first), #3 (contracts before logic), #5 (structural fixes only), #8 (OSS first), #9 (provenance), #10 (tests ship with feature); section 6 (levels); section 0a (authority table); section 10 (STOP-AND-SURFACE).
- [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) - renderer doctrine (rewritten by PR-5).
- [datasets/boundaries/electoral/README.md](../datasets/boundaries/electoral/README.md) - electoral grammar (rewritten by PR-3/PR-5).
- [TODO/20260612-pc-delim-2008-boundary-ingest-plan.md](20260612-pc-delim-2008-boundary-ingest-plan.md) - the plan that ingested `delim=2008/pc`; its mis-binding concern is resolved here by the dual-key mechanism (section 4), so its artifact is superseded, not contradicted.
- [tools/topojson/convert_layer.py](../tools/topojson/convert_layer.py) + [config/topojson.json](../config/topojson.json) - the converter + the `5% weighted` knob PR-2 supersedes.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - closure + archive ritual.
