# Handover - Row 3 (electoral slice) of the map-geometry rip-and-replace plan

**Created**: 2026-06-16
**Parent plan**: [20260616-map-geometry-rip-and-palette-plan.md](20260616-map-geometry-rip-and-palette-plan.md)
**Status**: READY TO EXECUTE. Rows 1, 2, 4 are MERGED; Row 3 is the last implementation row (Rows 5 + 5b are docs/polish that depend on Row 3).
**Why handed off**: Row 3 is a full-day, single destructive PR that rewrites the electoral join contract AND permanently deletes two delimitation trees. The data path is fully de-risked (below); it deserves a fresh, focused context for an irreversible electoral-data change.

## What is already shipped (do NOT redo)

| Row | PR | What landed |
| --- | --- | --- |
| 1 | #1085 | Responsive map fit (fitWidth, `MAX_MAP_W=1200`) on all 4 d3 maps + **Lakshadweep square marker** (`computeIslandMarker`, national maps only) + stripped circle markers + stripped sub-state silhouettes. |
| 2 | #1089 | Single combined `boundaries/in/country/all.topojson` (2 objects: `states` 36 + `districts` 785, join keys `State_LGD`/`dist_lgd` preserved, NO simplification). Format-aware + object-by-name loader. Stripped all 4730 non-country topojson. `boundary_encoding.csv` is now the full boundary inventory (per-object country provenance + geojson-only rows); `emit_receipt.py` + `validate.py` extended. `build_country.py` + `backend/tests/test_build_country.py` (C1/C2 island-survival). |
| 4 | #1086 | Configurable palette token registry (`colors/palettes.ts` RAMP_HUES + CATEGORICAL_PALETTES, `colors/topic-palette.ts`, `--ramp-*` CSS vars). `hueForDirection` stays the single choropleth-ramp source. |

`origin/main` HEAD after Row 2: `4f95c6e2d`.

## De-risking already done for Row 3 (reuse this)

1. **Data source proven**: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z` (33.5 MB). Downloads cleanly via `Invoke-WebRequest` (or `snapshot.py`'s `_download`).
2. **Extraction proven**: `py7zr` 1.1.0 is in the venv. API: `py7zr.SevenZipFile(path, 'r').extractall(path=dest)`. The single member is `LGD_Assembly_Constituencies.geojsonl` = **4177 AC features across 30 states**. (NOT `.read()` / `.readall()` - those raise AttributeError.)
3. **ESCALATE 0.5.3 CLEARED**: AC name-slug overlap between the archive and the historical `delim=2008/ac` corpus is **100%** (3878/3878 across 29 shared states) - because the historical shards were built from THIS SAME archive. So the consolidation is mechanical and safe; no STOP-and-surface is needed on the AC tail.
4. **`snapshot.py` already processes this exact archive** (the existing `delim=2008/ac` shards came from it via the Phase D.7 universal LGD swap; see `tools/boundaries/pipeline.json`). Reuse its `lgd_ac_id` derivation, AP/TG `ac_no` rewrite (`by_name_to_sot_eci_no`), J&K `seat_id` handling.

### KEY INTERPRETATION (surfaced 2026-06-16 - confirm framing)
There is **no separate "2024 AC delimitation"** in the source. It is ONE AC delimitation. Row 3's "ingest 2024 AC" means: **consolidate** the 31 per-state `delim=2008/ac` shards (+ the states missing from the 2024 tree: J&K, AP, TG, Delhi per plan section 0.1) into ONE national `delim=2024/ac/all.geojson`, then relabel/retire the 2008 tree. `delim=2024/` currently holds only `pc/`.

Archive caveat: `State_LGD` is census-style (J&K=1, not the LGD code) with a few border-sliver contamination features (e.g. a "GUJARAT" feature under `State_LGD=8`). The `snapshot.py` normalisation already handles this; do not hand-clean.

## Row 3 execution (one PR, visible commit ladder)

Follow the parent plan's Row 3 spec (section 2, Row 3) verbatim. The ladder:

1. **ingest** -> emit one national `boundaries/electoral/delim=2024/ac/all.geojson` from the archive; replay `lift_boundary_lgd_ac_id.py` + AP/TG `ac_no` rewrite + J&K `seat_id`; carry `st_lgd` for per-state filtering.
2. **dual-key** -> stamp `pc_name_slug` (from `ls_seat_name`) onto `delim=2024/pc/all.geojson` and `ac_name_slug` onto the new AC file. (Section 0.3: 507/539 = 94% of 2008 PC name-slugs already match a 2024 PC name-slug exactly; the alias table for the ~27 spelling variants is Row 5b, separate.)
3. **repoint frontend join** -> in `StateElection.svelte` + `NationalElection.svelte`, collapse `pcDelimYearForLsEvent` so ALL events (2009-2024) join by name-slug against the single 2024 geometry; **delete `INDIA_PC_2008`**; repoint the 31 `STATE_AC` registry entries to the one national AC file + add a per-`st_lgd` filter inside `StateAcMapD3.svelte` (the national file is not pre-filtered per state - this is a code change, Gregor G2).
4. **delete** `delim=2008` + `delim=2026` geometry; re-run the seed/compile for `datasets/data/entities/boundary_layer.csv` (drop 31 AC + 1 PC `delim=2008` rows, add the `delim=2024` AC national row - do NOT hand-edit); dispose the `election_tile_layouts.json` `source_id` provenance that FKs `delim=2008` (re-derive off `delim=2024/ac` via `tools/gen_election_tile_layouts.py` OR record an explicit receipt - Gregor G5 / Holy Law #9). After the strip, **re-run `tools/topojson/emit_receipt.py`** so `boundary_encoding.csv` drops the deleted `delim=2008/2026` rows, then `validate` must stay green.
5. **table-fallback tail** -> for events whose seats genuinely changed shape (J&K pre-2022, Assam pre-2023; enumerate at execution) render the results TABLE, not a choropleth (Hans - never a wrong-seat colour).
6. **tests** -> delete the `delim=2008` geometry tests; rewrite `backend/tests/test_electoral_boundaries_layout.py` to the single-vintage grammar; update e2e asserted URLs (`state-ac-coverage.spec.ts`, `e2e-ac-full.yml` path filter). NO new on-disk-geometry tests (D7).

### ESCALATE / STOP triggers for Row 3 (plan section 0.5)
- A `delim=2008` GEOMETRY deletion must NOT remove any ELECTION-RESULT row. `datasets/elections/**` + `datasets/data/datapoints/electoral/**` are GEOMETRY-independent and stay. If a result CSV is found to FK a `delim=2008` GEOMETRY path, STOP-AND-SURFACE.
- The AC overlap checkpoint is already CLEARED (100%), so no STOP there.

## Gates (Row 3 DoD)
`pytest` + `validate --root .` (exit 0; the receipt must be regenerated post-delete) + `bun run check` + `bun run test` + browser smoke: `/t/elections/general-2024` (PC atlas, numeric join), `/<state>/elections/general-2019` (PC atlas, name-slug join, >= 90% seats painted), one state AC route, and one J&K/Assam historical event (table-fallback, no broken map). Oracle: `electoral/` lists only `delim=2024` + README; zero `INDIA_PC_2008` references remain.

## Worktree / cache notes
- A worktree `yen-gov-row3` was created on `feat/map-row3-electoral` off `4f95c6e2d` with the AC archive cached at `.tmp_row3/ac.7z` + extracted at `.tmp_row3/extracted/`. Worktrees can disappear between sessions (see `/memories/lessons*`); if absent, recreate via `git worktree add <abs> -b feat/map-row3-electoral origin/main` and re-download the archive (cheap, 33.5 MB). The `.tmp_row3/` scratch must NOT be committed.

## After Row 3
- **Row 5** (docs): rewrite `docs/architecture/frontend/map.md` (d3-geo sole renderer, country=topojson, all-else=geojson, single 2024 vintage, dual-key historical join, no simplification) + `datasets/boundaries/electoral/README.md` (single-vintage + dual-key grammar). Oracle: `git grep -nE "tippecanoe|PMTiles|5% weighted|delim=2008" docs/` returns only archive mentions. NOTE: Rows 1+2 already changed the renderer reality, so map.md is partly stale already - Row 5 can fold in those facts too.
- **Row 5b** (optional): PC + AC spelling-variant alias table (94% -> ~99%).
- **Closure**: distill the parent plan-doc per `docs/how-to/distill-a-plan.md`.
