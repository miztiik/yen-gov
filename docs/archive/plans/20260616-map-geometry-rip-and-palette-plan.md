# Plan - Map geometry rip-and-replace (2024-only) + island visibility + configurable palette

**Last Updated**: 2026-06-16
**Level**: Level-4 (structural; boundary-geometry contract change + electoral single-vintage consolidation + renderer-config change). User-ratified direction (2026-06-16): rip-and-replace, no strangler-fig, keep the LATEST delimitation (2024) only, delete the oldest (2008).
**Status**: COMPLETE (2026-06-16) - ALL rows merged: Row 1 (#1085), Row 2 (#1089), Row 4 (#1086), Row 3 (#1094), Row 5 (#1095), Row 5b (#1096). See [Plan complete](#plan-complete) at the foot of this doc for the row -> destination distillation map.
**Strategy**: RIP-AND-REPLACE, NO STRANGLER-FIG. Each PR is a complete vertical slice (data + readers + tests change together) so no intermediate state ships a broken map, and there is NO old/new coexistence phase. GitHub history is the backup.

## 0. Operating contract

### 0.1 The five visible defects + the root causes (measured)

| Defect | Root cause (verified) |
| --- | --- |
| Chunky coastlines on every map | `config/topojson.json` `"simplification": "5% weighted keep-shapes"` deletes coastline vertices for ALL layers via `tools/topojson/convert_layer.py`. |
| Lakshadweep invisible at national zoom | The 4 d3 maps fit into a FIXED-height card (520px / 420px) with `geoMercator().fitSize([640,480], ...)`. India in Mercator is height-binding, so widening the container only letterboxes - the island stays ~2px. Removing the 640x480 constants ALONE is insufficient (Jony). |
| "Ugly outline" on every state | The state-silhouette overlay is loaded from a separately-simplified file whose border vertices do not match the fill layer. |
| Circle-marker clutter | The sub-threshold `<circle>` overlay (`india-party-map-helpers.ts`) drawn over tiny/dense areas. |
| Stale / mismatched electoral vintages | Two delimitation trees on disk (`delim=2008`, `delim=2024`) + 36 per-state AC shards; AC for J&K/AP/TG/Delhi missing from the 2024 tree. |

### 0.2 Hard-coded decisions (user-ratified 2026-06-16 - do NOT re-litigate)

| # | Decision |
| --- | --- |
| D1 | TopoJSON for the COUNTRY file only. Every other layer ships raw `.geojson` (ramSeraph upstream, byte-faithful). |
| D2 | Rebuild the country topojson from OUR on-disk `.geojson` masters in ONE mapshaper run: `quantization=19000`, arc-shared, NO shape simplification, lean property set that PRESERVES the live join keys `State_LGD` (states object) + `dist_lgd` (districts object) verbatim. Measured ~727 KB raw / ~193 KB gz, all 36 states incl Lakshadweep + Ladakh + 785 districts. We do NOT ingest bharatpashudhan's file (ours beats it on coverage + size once mapshaper is configured right). |
| D3 | NO geometry simplification anywhere. Quantization on the country topojson is allowed (lossless integer rounding, not vertex deletion). |
| D4 | Strip ALL non-country `.topojson` siblings + their `.meta.json` caches. |
| D5 | Keep ONLY the LATEST delimitation: `delim=2024`. Delete `delim=2008` + `delim=2026`. Historical elections are supported on 2024 geometry via the dual-key join (section 0.3). |
| D6 | AC + PC each consolidate to ONE national `delim=2024` file (no per-state AC shards). |
| D7 | NO tests on geometry data files. Delete every test that parses/walks an on-disk geometry file. Update the live consumers in the SAME slice (no-prisoners; rip-and-replace, not keep-for-green). One carve-out: KEEP `no-frontend-corpus-explosion.test.ts` - it is the guardrail that ENFORCES "no test may walk the geometry corpus" (the user's own rule mechanized); edit its canary list, do not delete. |
| D8 | Lakshadweep fix = widen the canvas (drop the fixed card height + `fitWidth`). NO circle markers. NO inset boxes. Citizen zooms-then-clicks on mobile (user, 2026-06-16). |
| D9 | Strip circle-marker overlay everywhere. Strip state-silhouette overlay from sub-state maps; KEEP `state-silhouette.ts` (the TileCartogram "Equal seats" hex arm still imports it). |
| D10 | Palette system is configurable + detached: a named token registry re-themeable via CSS/Tailwind, components reference palettes by NAME. Topic-family palettes apply to CATEGORICAL / chrome / neutral only; `hueForDirection` stays the single source for directional choropleth ramps (Jony + Hans - section 0.4). |

### 0.3 THE FIX that makes 2024-only honest - dual-key the PC + AC geometry (verified)

The mis-binding risk a naive "delete 2008" would create comes from the UNRELIABLE numeric `eci_no` in `electoral.csv` for pre-2024 PCs (22 of 544 are zero). The fix sidesteps it entirely by joining on NAME, which is reliable:

**Measured fact (probe, 2026-06-16):** both `delim=2008/pc` and `delim=2024/pc` carry `ls_seat_name`. **507 of 539 (94%) of 2008 PC name-slugs match a 2024 PC name-slug exactly.** Of the 32 misses, ~27 are spelling/transliteration variants (anantapuramu/anantapur, haasan/hassan, thoothukudi/tuticorin, belagavi/belgaum, cooch-behar/coochbehar) recoverable with a small alias table, and ~5 are genuine boundary changes (J&K Anantnag post-2022; Assam Kaliabor/Mangaldoi/Nowgong/Tezpur post-2023).

This is decisive because the 2008 Delimitation Order governs PC boundaries for LS 2009 THROUGH 2024 - they are the SAME polygons. So a 2019 result rendered on the 2024 polygon of the same-named seat is CORRECT, not approximate.

**The mechanism (one geometry, two indexed keys):**
- Stamp `pc_name_slug` (derived from `ls_seat_name`) onto the single `delim=2024/pc` file, which already carries the numeric `unique_id`. Same for the AC file (`ac_name_slug` alongside `lgd_ac_id`).
- Rewrite the frontend so ALL events (2009-2024) join by name-slug against the 2024 geometry; LS 2024 may keep numeric. Delete the `pc_delim_year === 2008 ? INDIA_PC_2008 : INDIA_PC` branch - there is one geometry now.
- The ~94% that match render correctly. The alias table (PR-5) recovers the ~27 spelling variants -> ~99%. The ~5 genuine-change seats (J&K pre-2022, Assam pre-2023) fall to a TABLE / grey-with-footnote, never a wrong-seat colour. This is the honest tail Hans required.
- Pre-2009 LS (1962-2004) keep their current placeholder cards (no geometry on disk; out of scope).

This RESOLVES the Hans/Gregor governance block WITHOUT keeping `delim=2008`: one geometry set, historical capability preserved via dual-key, honest table-fallback for the bounded genuine-change tail.

### 0.4 Palette doctrine (Jony + Hans, binding)

`frontend/src/lib/indicators.ts` `hueForDirection` is the existing good/bad cue: `higher_is_better=160` (teal), `lower_is_better=25` (red), `neutral=250` (blue); "dark always means high value." A topic-family hue (health=red) applied to the choropleth ramp would destroy that valence (infant-mortality and vaccination both rendered red). Therefore:
- **Directional choropleth ramps**: `hueForDirection` stays the single source. Tokenize its 3 hues via CSS vars so they are themeable, but direction - not topic - picks the ramp hue.
- **Topic-family palettes**: apply ONLY to categorical breakdowns (the `dimensionAnchors` registry in `anchors-domain.ts`, today only `power_source`), page chrome / wayfinding, and `neutral`-direction fills.

### 0.5 ESCALATE triggers (stop ONLY here)

1. A canonical CSV JSON-Schema MAJOR bump (1.x -> 2.x) becomes necessary (none expected - this touches geometry + render code).
2. Deleting `delim=2008` would remove an ELECTION-RESULT row. It must not - D5 deletes GEOMETRY only; `datasets/elections/**` + `datasets/data/datapoints/electoral/**` are untouched. If a result CSV is found to FK a `delim=2008` GEOMETRY path, STOP-AND-SURFACE.
3. After the 2024 AC ingest, if the AC name-slug overlap against the historical AC corpus is materially worse than the PC 94% (e.g. AP/TG bifurcation or J&K make it < 80%), STOP and surface the AC tail size before deleting `delim=2008/ac`.
4. A persona debate fails to converge.

### 0.6 Persona red-team verdicts folded in

Gregor (BLOCK -> resolved by 0.3 dual-key + key-preservation), Fowler (test-ledger correction + atomic slicing), Jony (Lakshadweep fitWidth recipe + palette scoping), Hans (2024-only honest via dual-key + table tail). All must-fix edits are baked into the rows below.

## 1. Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| **1** | Frontend component sweep: Lakshadweep fitWidth fix + strip circles + strip silhouettes (render-only, old geometry, ships first) | [x] DONE - shipped a Lakshadweep SQUARE marker (user-ratified reversal of D8/D9; the resting island was ~2px even after fitWidth) | #1085 | ~half-day |
| **2** | Admin geometry slice: rebuild country topojson + loader object-by-name + strip non-country topojson + tests | [x] DONE - + receipt re-architected to full boundary inventory (a coupling the spec missed; user-approved) | #1089 | ~1 day |
| **3** | Electoral slice: ingest 2024 AC + dual-key PC/AC + delete delim=2008/2026 + repoint routes + table-fallback tail + tests | [ ] READY - handed off: [20260616-row3-electoral-handover.md](20260616-row3-electoral-handover.md) | _pending_ | ~1 day |
| **4** | Configurable + detached palette token system | [x] DONE | #1086 | ~half-day |
| **5** | Docs reconciliation (map.md + electoral README + canonical-store note) | [ ] PENDING (after Row 3) | _pending_ | ~1h |
| **5b** | OPTIONAL join polish: PC + AC spelling-variant alias table; 94% -> ~99% | [ ] PENDING (after Row 3) | _pending_ | ~half-day |

Rows 1, 2, 4 are independent and parallelizable. Row 3 depends on Row 2 (the new geometry + loader). Row 5 depends on 1-3. Row 5b depends on 3.

## 2. Per-row specs

### Row 1 - Frontend component sweep (render-only; OLD geometry; the visible win first)

**Owner**: Jony. **Why first**: it changes how the SAME data renders (no data-path change), so it cannot break production, and it fixes the user's #1 pain (Lakshadweep) immediately.

**Lakshadweep fix (Jony's exact recipe)** - applied to all 4 components (`IndiaPartyMap.svelte`, `IndiaPcMapD3.svelte`, `StateAcMapD3.svelte`, `StatePcMapD3.svelte`):
- DELETE `const WIDTH = 640; const HEIGHT = 480;` AND the fixed wrapper `style="height: 520px"` / `"420px"`.
- Measure container width via `bind:clientWidth`. Project with `geoMercator().fitWidth(container_w, collection)`; derive height from `geoPath(projection).bounds(collection)`; re-translate so the extent starts at 0,0.
- SVG: `viewBox="0 0 {w} {h}"`, `width="100%"`, `style="height:auto; aspect-ratio:{w}/{h};"`. No fixed height -> the binding dimension scales with the viewport -> islands keep true relative size and grow with width. Optional `MAX_MAP_W ~= 900` clamp so a 4K monitor does not yield a giant hero.
- Reset the d3-zoom transform on width change: `select(svg_el).call(zoom_behavior.transform, zoomIdentity)` (prevents a stale-transform jump on resize).

**Strip circles (D9)**: delete the marker section of `india-party-map-helpers.ts` (`SUB_THRESHOLD_PX`, `MarkerOverlay`, `pathSpan`, `isSubThreshold`, `projectedCentroid`, `computeSubThresholdMarkers`; KEEP `resolveStateClickAction`). Strip the marker import + `$derived` + template `<circle>` from all 4 components. Rewrite the module-top JSDoc.

**Strip silhouettes (D9)**: delete the silhouette import + `SILHOUETTE_STROKE` + `silhouette_feature` state + loader `$effect` + template silhouette `<path>` from `StateAcMapD3.svelte` + `StatePcMapD3.svelte`. Narrow `ElectionMap.svelte` so any silhouette load fires only when `view === "hex"`. KEEP `state-silhouette.ts` (hex arm).

**Tests (this slice)**: delete/trim the marker + silhouette describes in `IndiaPartyMap.test.ts` + `StateAcMapD3.test.ts` (keep `resolveStateClickAction` / pure paint blocks). Update `frontend/e2e/e3-silhouette-smoke.spec.ts` to assert the hex-arm silhouette only.

**Acceptance**: vitest + svelte-check green; browser smoke at 1280px (Lakshadweep visibly painted - screenshot receipt), at 375px (map fits, zoom-then-tap works), and `?view=hex` (silhouette intact). **Oracle**: no `WIDTH = 640` literal + no `<circle>` overlay + no sub-state silhouette path remain; Lakshadweep cluster >= 4px at 1280px.

### Row 2 - Admin geometry slice (country topojson rebuild + loader + strip + tests)

**Owner**: Fowler + Gregor.

- **Rebuild** `boundaries/in/country/all.topojson` via new `tools/topojson/build_country.py`: one mapshaper run combining `in/states/all.geojson` + `in/districts/all.geojson` into `objects.states` + `objects.districts`, `quantization=19000`, arc-shared, NO `-simplify`. **PRESERVE `State_LGD` on states + `dist_lgd` on districts verbatim** (Gregor G1: renaming to `st_lgd`/`dt_lgd` would blank every map - `boundaries.ts` JOIN_KEYS, `IndiaPartyMap` JOIN_PROPERTY, `sources.ts` INDIA_STATES, `choropleth-entity-context` INDIA_DISTRICTS all read the current names). Edit `config/topojson.json` to drop the `5% weighted` simplification.
- **Loader object-by-name** (Gregor G3): extend `boundaries.ts` so `loadBoundary("country", { object })` addresses the topology object by NAME, not `objectKeys[0]` (the country file now has 2-3 objects). Re-point `IndiaPartyMap` (today fetches `states/all.topojson` directly) at the country file's `states` object. Make the loader format-aware: only `country` attempts topojson; all other levels read `.geojson` directly (no wasted 404 probe - Gregor G4).
- **Strip** all non-country `.topojson` + `.meta.json` (D4). After this, exactly one topojson remains.
- **Tests (this slice, per the verified ledger section 3)**: delete the geometry-reading admin tests; ADD compensating code-tests C1 (build_country output shape, tmp_path) + **C2 (NON-NEGOTIABLE: a Lakshadweep island feature survives into the output `states` + `districts` objects by name)** - C2 is the standing guard for the exact regression this plan exists to fix.

**Acceptance**: vitest + svelte-check + `pytest` green; `python -m yen_gov validate --root .` exits 0; browser smoke on `/` (national states choropleth paints - not blank) + `/tamil-nadu` (district drill). **Oracle**: `git ls-files "datasets/boundaries/**/*.topojson"` returns exactly `in/country/all.topojson`; its states object's first feature carries `State_LGD`; the home map paints with no console error.

### Row 3 - Electoral slice (ingest 2024 AC + dual-key + delete 2008 + repoint + tail)

**Owner**: Gregor + Hans (data shape) + Fowler (delete discipline).

- **Ingest** ramSeraph `LGD_Assembly_Constituencies.geojsonl.7z` -> ONE `electoral/delim=2024/ac/all.geojson` (D6). Replay the `lgd_ac_id` derivation (`tools/boundaries/lift_boundary_lgd_ac_id.py` - it is stamped post-hoc, not upstream; Gregor G6) + the AP/TG `ac_no` rewrite (`snapshot.py by_name_to_sot_eci_no`) + J&K `seat_id`. Carry `st_lgd` for state filtering.
- **Dual-key** (section 0.3): stamp `pc_name_slug` onto `delim=2024/pc/all.geojson` (from `ls_seat_name`) and `ac_name_slug` onto the new AC file (from the AC name). One file each, two indexed keys.
- **Rewrite the frontend join**: in `StateElection.svelte` + `NationalElection.svelte`, collapse `pcDelimYearForLsEvent` so ALL events (2009-2024) join by name-slug against the single 2024 geometry; delete `INDIA_PC_2008`; the `pc_winners` builder uses `slugify(entity_name)` for every event (it already does this for 2008). Repoint the 31 `STATE_AC` registry entries to the one national AC file + add a per-`st_lgd` filter inside `StateAcMapD3.svelte` (the national file is not pre-filtered per state - this is a code change, Gregor G2).
- **Table-fallback tail**: for events whose seats genuinely changed shape (J&K pre-2022, Assam pre-2023; enumerate at execution), render the results TABLE, not a choropleth (Hans - never a wrong-seat colour). The alias table for spelling variants is Row 5b.
- **Delete** `delim=2008` + `delim=2026`. Update `datasets/data/entities/boundary_layer.csv` (re-run the seed/compile, do not hand-edit - drop 31 AC + 1 PC `delim=2008` rows, add the `delim=2024` AC national row). Dispose of the `election_tile_layouts.json` `source_id` provenance that FKs `delim=2008` (Gregor G5 / Holy Law #9): re-derive off `delim=2024/ac` via `tools/gen_election_tile_layouts.py` OR record an explicit receipt.
- **Tests (this slice)**: delete the delim=2008 geometry tests; REWRITE `test_electoral_boundaries_layout.py` to the single-vintage grammar; update the e2e asserted URLs (`state-ac-coverage.spec.ts`, `e2e-ac-full.yml` path filter).

**Acceptance**: vitest + svelte-check + pytest + validate green; browser smoke on `/t/elections/general-2024` (PC atlas, numeric join), `/t/elections/general-2019` (PC atlas, name-slug join, >= 90% seats painted), one state AC route, and one J&K/Assam historical event (table-fallback, no broken map). **Oracle**: `electoral/` lists only `delim=2024` + README; an LS-2019 PC render binds >= 90% of seats to the correct same-named polygon; zero `INDIA_PC_2008` references remain.

### Row 4 - Configurable + detached palette token system

**Owner**: Jony + Hans. **Shape** (section 0.4):
- `frontend/src/lib/colors/palettes.ts` (NEW): `RAMP_HUES = { positive:160, negative:25, neutral:250 }` (read from CSS `--ramp-*` with JS fallback, mirroring the existing `--party-neutral` pattern) + `CATEGORICAL_PALETTES` (named OkLCh arrays: set2, paired, etc.).
- `frontend/src/lib/colors/topic-palette.ts` (NEW): `TOPIC_CATEGORICAL` map (agriculture->set2, energy->paired, ...) for categorical breakdowns ONLY.
- EDIT `indicators.ts hueForDirection` to source from `RAMP_HUES` (stays the single choropleth-ramp source). EDIT `anchors-domain.ts dimensionAnchors` to consume `CATEGORICAL_PALETTES` by name.

**Acceptance**: vitest + svelte-check green; browser smoke on 2-3 indicator pages across families. **Oracle**: a contract test asserts (1) every live topic family resolves to a registered categorical palette; (2) each `Direction` resolves to a registered ramp-hue token; (3) there is NO topic->choropleth-hue map (the anti-pattern).

### Row 5 - Docs reconciliation

**Owner**: default. Rewrite `docs/architecture/frontend/map.md` (still describes MapLibre + PMTiles + tippecanoe - now: d3-geo sole renderer, country=topojson, all-else=geojson, single 2024 vintage, dual-key historical join, no simplification). Rewrite `datasets/boundaries/electoral/README.md` (single-vintage + dual-key grammar). Note the boundary section of `docs/architecture/data/canonical-store.md` if it references per-state AC shards. **Oracle**: `git grep -nE "tippecanoe|PMTiles|5% weighted|delim=2008" docs/` returns only archive/historical mentions.

### Row 5b - OPTIONAL join polish (alias table)

**Owner**: Hans + Max. Build a small `(old_name_slug -> 2024_name_slug)` alias table for the ~27 PC spelling variants (anantapuramu->anantapur, haasan->hassan, ...) + the AC equivalents (size known after Row 3 ingest). Recovers 94% -> ~99%. The genuine-change tail stays on table-fallback. **Oracle**: post-alias, an LS-2019 PC render binds >= 98% of seats.

## 3. Verified test ledger (Explore opened each candidate file 2026-06-16)

The earlier "delete 20" was wrong. Truth:

- **DELETE whole-file (read on-disk geometry)**: `election-tile-layout-coverage.test.ts`, `topojson-island-render.test.ts`, `state-silhouette-smoke.test.ts`, `census-code-2011-coverage.test.ts`, `boundaries-conform.test.ts`, `boundaries.contract.test.ts`, `backend/tests/test_ac_parity_per_state.py`.
- **TRIM (mixed)**: `IndiaPartyMap.test.ts` + `StateAcMapD3.test.ts` - remove the geometry-read + marker describes; keep pure blocks (`resolveStateClickAction` / paint-formula) or whole-delete if none remain.
- **REWRITE**: `backend/tests/test_electoral_boundaries_layout.py` -> single-vintage grammar.
- **UPDATE asserted URL (e2e)**: `frontend/e2e/state-ac-coverage.spec.ts`, `frontend/e2e/e3-silhouette-smoke.spec.ts`, `.github/workflows/e2e-ac-full.yml` path filter.
- **KEEP UNCONDITIONALLY (guardrail)**: `frontend/src/contracts/no-frontend-corpus-explosion.test.ts` - it enforces the user's own "no corpus-walking tests" rule; edit its canary list only.
- **KEEP (pure / mocked / surviving-layer code-tests)**: `boundaries.integration.test.ts`, `boundaries.path.test.ts`, `boundaries.loader.test.ts` (update if the topo-fallback contract changes), `state-silhouette.test.ts`, `india-pc-map-helpers.test.ts`, `choropleth-entity-context.test.ts`, the panchayat/ward/block registry + shards coverage tests (untouched layers), `datasets-conform.test.ts`, the backend snapshot/lift code-tests (tmp_path fixtures, surviving code), `test_boundary_layers_seed.py`, `test_derive_hive_signature.py`.
- **ADD (compensating, code-level, fixtures only)**: C1 build_country output shape; **C2 island-survival-by-name (NON-NEGOTIABLE)**; C3 ingest_ac_2024 feature-count + dual-key presence; C4 loader country-object-by-name; C5 the rewritten single-vintage layout gate.

The executing agent opens each file before acting and applies the rule "reads on-disk geometry OR asserts deleted-world behaviour -> delete/rewrite; tests surviving CODE via fixtures -> keep".

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger (section 0.5).

1. **Orchestrator + subagent-PR topology.** Main agent owns the Reckoner; each row is a self-contained `runSubagent` brief (scope, files, gates, oracle).
2. **One row = one PR = one branch = one complete vertical slice** (data + readers + tests change together so no intermediate ships a broken map). Park master on `scratch-master-parking`. Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, 5-gate DoD, browser-verify any frontend runtime change. Row 3 is one PR with a visible commit ladder (ingest -> dual-key -> repoint -> delete -> tests).
3. **Ship loop, non-stop.** Rows 1, 2, 4 in parallel; Row 3 after Row 2; Row 5 after 1-3. Merge on green, pull main, advance.
4. **Tests ship with the row.** Never add a test that parses an on-disk geometry file (D7). Add the compensating code-tests (section 3).
5. **Persona debate converges to ONE ruling** when a row hits a contested call (CLAUDE.md 0a).
6. **Offload breadth to subagents**; keep the orchestrator window lean.
7. **Post-merge hygiene every time** (delete remote branch, prune `: gone`, remove `.tmp_*`, distill lessons).
8. **Stop only at a real boundary** (section 0.5 ESCALATE, STOP-AND-SURFACE per CLAUDE.md 10, or an audit chain > depth 3).
9. **Closure**: every row DONE or COLLAPSED-with-receipt; archive with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

## 4. Cross-references

- [CLAUDE.md](../../../CLAUDE.md) - Holy Laws #1/#3/#5/#8/#9/#10; sections 6, 0a, 10.
- [docs/architecture/frontend/map.md](../../../docs/architecture/frontend/map.md) - rewritten by Row 5.
- [datasets/boundaries/electoral/README.md](../../../datasets/boundaries/electoral/README.md) - rewritten by Row 3 / Row 5.
- [TODO/20260612-pc-delim-2008-boundary-ingest-plan.md](../../../TODO/20260612-pc-delim-2008-boundary-ingest-plan.md) - the prior PC ingest; its name-slug machinery is reused, its delim=2008 geometry retired by Row 3.
- [tools/topojson/convert_layer.py](../../../tools/topojson/convert_layer.py) + [config/topojson.json](../../../config/topojson.json) - the converter + the `5% weighted` knob Row 2 supersedes.
- [docs/how-to/ship-a-pr.md](../../../docs/how-to/ship-a-pr.md) + [docs/how-to/distill-a-plan.md](../../../docs/how-to/distill-a-plan.md).

## Plan complete

Closed 2026-06-16. All rows merged. Distillation complete (durable knowledge lives in the destinations below; this plan-doc remains as the audit ledger - do not edit further; new work starts a new plan-doc):

| Row | PR | Merge SHA | Durable knowledge distilled to |
| --- | --- | --- | --- |
| Row 1 - responsive fit + Lakshadweep square marker + strip circles/silhouettes | #1085 | `c258bd2dc` | [docs/architecture/frontend/map.md](../../../docs/architecture/frontend/map.md) (d3-geo renderer + `fitWidth`); `computeIslandMarker` JSDoc. |
| Row 2 - country TopoJSON (objects states+districts) + object-by-name loader + receipt | #1089 | (squash) | [map.md](../../../docs/architecture/frontend/map.md) (encoding rule) + [docs/architecture/data/boundaries.md](../../../docs/architecture/data/boundaries.md) + the `boundary_encoding.csv` receipt contract in `tools/topojson/emit_receipt.py` + `backend/yen_gov/validate.py`. |
| Row 4 - configurable palette token registry | #1086 | (squash) | `frontend/src/lib/colors/palettes.ts` + `colors/topic-palette.ts` + `app-tokens.css` (`--ramp-*`); contract in `palette-contract.test.ts`. |
| Row 3 - electoral rip to single 2024 vintage (national AC TopoJSON + dual-key PC) | #1094 | `54b33898c` | [datasets/boundaries/electoral/README.md](../../../datasets/boundaries/electoral/README.md) (single-vintage + dual-key grammar) + [map.md](../../../docs/architecture/frontend/map.md); the `boundary-layers.schema.json` v1.6 `format` enum (topojson) is self-documenting; tools `consolidate_ac_2024.py` + `dual_key_pc_2024.py` + `reseed_electoral_2024.py`. |
| Row 5 - docs reconciliation | #1095 | `4fcd7ca6f` | [map.md](../../../docs/architecture/frontend/map.md) + [boundaries.md](../../../docs/architecture/data/boundaries.md) + [boundary-coverage-matrix.md](../../../docs/architecture/data/boundary-coverage-matrix.md) + [canonical-store.md](../../../docs/architecture/data/canonical-store.md) + [boundary-data-philosophy.md](../../../docs/concepts/boundary-data-philosophy.md) + [convert-geojson-to-topojson.md](../../../docs/how-to/convert-geojson-to-topojson.md) (this row WAS the distillation of Rows 1-3 into the architecture docs). |
| Row 5b - PC name-slug alias table (96.0% -> 99.1%) | #1096 | (squash) | `frontend/src/lib/elections/pc-slug-alias.ts` (self-documenting curated table + per-entry rationale) + its contract test; the genuine-change-stays-grey doctrine is captured in the module header + the test's `does NOT alias any genuine-change seat` case. |

Agent-only execution lessons (orchestration topology, the worktree/CI/merge gotchas, the `delim_year`-vs-`delim=2008` distinction, the receipt-scoping finding) are in `/memories/` per CLAUDE.md §5, not in `docs/`.
