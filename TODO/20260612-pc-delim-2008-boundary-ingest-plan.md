# PC delim=2008 boundary geometry ingest — 2026-06-12

**Status:** READY-TO-IMPLEMENT (with one pre-flight stop)
**Correction level:** Level-3 (data ingest + frontend boundary registration + downstream consumer wire-up)
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §0a (data shape = Hans + Max; engineering = Fowler) · §3 storage doctrine · §9 DoD · §12 provenance · §13 UI verification.
**Predecessor:** PR [#958](https://github.com/miztiik/yen-gov/pull/958) deferred PC choropleth on pre-2024 Parliament event pages because delim=2008 PC geometry was missing. This plan closes that gap (FU#3 from PR #958 closure).

## Problem (research-confirmed 2026-06-12)

Today the StateElection page renders a placeholder card on `/<state>/elections/general-2019`, `/general-2014`, `/general-2009` because:
- `datasets/boundaries/electoral/delim=2024/pc/all.{topojson,geojson}` EXISTS (543 features, 18th LS geography).
- `datasets/boundaries/electoral/delim=2008/pc/...` DOES NOT EXIST.

Using 2024 geometry retroactively for pre-2024 events is a citation-integrity breach (J&K reorg 2022 + Assam reorg 2023 redrew boundaries; rendering LS 2019 results against 2024 polygons silently mis-attributes seats). Per CLAUDE.md §12 + OWID comparability doctrine, geometry vintage MUST match the event's delim vintage.

LS 2009 + LS 2014 + LS 2019 were all conducted under the **2008 Delimitation Commission Order** (Justice Kuldip Singh). One geometry covers all three events.

## Verdicts (locked, no re-debate)

### V1 — Source: datameet/maps parliamentary-constituencies shapefile

**Chosen source:** `https://github.com/datameet/maps/tree/master/parliamentary-constituencies`

Rationale (per Explore subagent research 2026-06-12):
- Covers 2008 Delimitation (only known community archive of pre-2024 PC geometry).
- CC-BY 4.0 licence; permissive + citable.
- shijithpk (current 2024 PC publisher in this repo) IMPLICITLY recommends datameet for older geometry — README says "Datameet maps … still have pre-delimitation parliamentary seat borders".
- Existing project precedent: yen-gov already ingests datameet AC layers; shapefile handling is proven.

**Rejected alternatives:**
- **ramSeraph LGD_Parliament_Constituencies** — per [TODO/20260524-boundary-coverage-expansion-plan.md](./20260524-boundary-coverage-expansion-plan.md) Phase D.6 recon, has 4 critical NO-GO findings (39 features marked `status="Pre delimitation"` covering 6 entire states; missing 2 J&K admin territories; no `lgd_pc_code`; Telangana PCs carry pre-bifurcation AP prefixes). Not fit for delim=2008.
- **Susewind 2014** — researcher-grade, covers 2014 delim not 2008; CC-BY-SA-NC NC clause is problematic for static-site bundle.
- **ECI direct** — no machine-readable GIS publication. Only PDF gazettes.
- **OSM admin boundaries** — sparse + inconsistently keyed; fallback only.
- **GADM / Natural Earth** — don't carry Indian PC boundaries.

### V2 — Scope: delim=2008 ONLY this PR

Pre-2008 delimitation (LS 1998/2002/2004 events) is OUT OF SCOPE. No known credible public GIS source for 1997 Delimitation. Deferred to a future Phase 2 plan-doc if citizen interest warrants.

Per-event coverage after this PR ships:

| Event | delim_year | PC boundary status after ingest |
| --- | --- | --- |
| general-2024 | 2024 | YES (already shipped on `main`) |
| general-2019 | 2008 | **YES (this PR)** |
| general-2014 | 2008 | **YES (this PR)** |
| general-2009 | 2008 | **YES (this PR)** |
| general-2004 | pre-2008 | NO (out of scope; placeholder card persists) |
| general-1999 | pre-2008 | NO (out of scope; placeholder card persists) |

### V3 — Naming + storage layout

- On-disk paths:
  - `datasets/boundaries/electoral/delim=2008/pc/all.topojson`
  - `datasets/boundaries/electoral/delim=2008/pc/all.geojson`
- Boundary source ID in `frontend/src/lib/boundaries/sources.ts`: **`INDIA_PC_2008`** (mirrors existing `INDIA_PC` naming; new const, additive — does NOT modify the 2024 const).
- Update existing `INDIA_PC` jsdoc comment to clarify it's the 2024 delim (no behaviour change).

### V4 — Citation chain

Per CLAUDE.md §12: one new row in `datasets/data/entities/source.csv` via `derive_source_id`:

```python
from backend.yen_gov.canonical.citation import derive_source_id
sid = derive_source_id(
    producer="datameet",
    title="India Elections Parliamentary Constituencies (2008 Delimitation)",
    vintage="2008-delimitation",
)
# url = "https://github.com/datameet/maps/tree/master/parliamentary-constituencies"
```

The boundary_layers control table row (or its CSV equivalent post-X1a-fu2 retirement — verify on-disk format) carries this src_id FK.

### V5 — License attribution policy (resolves STOP-2)

Follow existing repo precedent: datameet CC-BY 4.0 attribution is preserved on the per-source row in `source.csv` + surfaced in the citizen-facing data attribution footer (wherever the existing AC datameet sources are surfaced). No CC0 re-licensing; per-source citation discipline already handles this.

### V6 — STOP-AND-SURFACE pre-flight (resolves STOP-1)

The subagent runs an empirical pre-flight BEFORE writing ingest code:

1. Download a sample datameet PC shapefile to a scratch dir.
2. Run `ogrinfo <shp>` to dump the attribute schema.
3. Cross-check 5-10 PC records against `datasets/data/entities/electoral.csv` rows where `delim_year=2008 AND entity_kind=pc`. Verify the `eci_no` per-state numbering matches.

If alignment fails (e.g. datameet uses a national 1-543 index rather than per-state 1-N), STOP and report. The fix is mechanical — write a small mapping table — but warrants user sign-off before authoring (the mapping is editorial).

## Scope (this PR — rows A through F)

| # | Change | Files | Level |
| - | --- | --- | :---: |
| A | Pre-flight V6 empirical check. Verify datameet shapefile attribute schema aligns with `electoral.csv` per-state `eci_no` keys. STOP if not. | (scratch / no commit) | 1 |
| B | Add datameet 2008 PC ingest entry to the boundary pipeline config (`tools/boundaries/pipeline.json` or equivalent). One new `kind: "pc"` entry with `delim_vintage: "2008"` + datameet shapefile URL + source_triple. | `tools/boundaries/pipeline.json` (or whichever file declares ingest entries) | 1 |
| C | Run snapshot tool: download → unzip shapefile → ogr2ogr to geojson → mapshaper simplify per `config/topojson.json` → write `datasets/boundaries/electoral/delim=2008/pc/all.{geojson,topojson}`. | `tools/boundaries/snapshot.py` (no code change expected; just running with new pipeline entry) | 1 |
| D | Add new source.csv row + boundary_layers control row via the snapshot tool's standard provenance emission. | `datasets/data/entities/source.csv` · `datasets/data/entities/boundary_layer.csv` (or wherever the boundary_layers control table lives post-X1a-fu2 retirement) | 1 |
| E | Register `INDIA_PC_2008` in `frontend/src/lib/boundaries/sources.ts`. Update `INDIA_PC` jsdoc to name 2024 delim explicitly. Update consumer wiring on `StateElection.svelte` + `NationalElection.svelte` to select the right PC source based on the event's delim_year (post-flip, the PC placeholder card retires for the LS 2019/2014/2009 surfaces; routes the right geometry to `StatePcMapD3` + `IndiaPcMapD3`). | `frontend/src/lib/boundaries/sources.ts` · `frontend/src/routes/StateElection.svelte` · `frontend/src/routes/NationalElection.svelte` | 2 |
| F | Tests + browser smoke updates. Existing `state-event-view.spec.ts` placeholder-card assertion for LS 2019 surfaces flips to PC-choropleth assertion. New smoke surfaces added: `/maharashtra/elections/general-2019`, `/karnataka/elections/general-2019`, `/maharashtra/elections/general-2014`. | `frontend/e2e/state-event-view.spec.ts` · `frontend/e2e/national-event-view.spec.ts` · contract tests if `STATE_PC` discovery shape changed | 1 |

**Out of scope (separate plan-docs):**
- Pre-2008 Delimitation (LS 2004 / 1999 / 1998 events) — no known credible GIS source. Phase 2.
- Per-state PC tile cartogram layout for 2008 delim — would let State Parliament pages get "Equal seats" view. Tile-layout authoring is its own discipline. Phase 2.
- Re-ingest of any AC layer (this PR is PC-only).
- Re-render / re-cache invalidation of the LS 2024 surface (no change to delim=2024 data).

## Acceptance gates

| Gate | Command |
| --- | --- |
| Pre-flight V6 attribute alignment | Subagent reports verbatim ogrinfo output + cross-check verdict. Must be GREEN before proceeding to Row B. |
| Tier-A schema validation | `python -m yen_gov validate --root .` passes on the new boundary_layers row + source.csv addition |
| Snapshot tool exit | Ingest completes cleanly; geojson + topojson files written with non-zero feature count (expect 543 ±2) |
| svelte-check | 0 NEW errors vs the 30 pre-existing baseline on main |
| vitest | `cd frontend; bun x vitest run --pool=forks --poolOptions.forks.singleFork=true` all pass; new contract tests for `INDIA_PC_2008` boundary entry pass |
| playwright | `cd frontend; bun x playwright test e2e/state-event-view.spec.ts e2e/national-event-view.spec.ts` all pass |
| browser smoke 1 | `/maharashtra/elections/general-2019`: PC choropleth visible (NOT placeholder card); winner shading + tooltip + Winner\|Margin toggle work |
| browser smoke 2 | `/maharashtra/elections/general-2014`: same as smoke 1 |
| browser smoke 3 | `/karnataka/elections/general-2019`: PC choropleth visible (state-agnostic verification) |
| browser smoke 4 | `/t/elections/general-2019` (national surface): switch the 3-way toggle to "Constituencies" → 543 PC polygons render |
| browser smoke 5 (regression check) | `/t/elections/general-2024`: still works — delim=2024 geometry uncorrupted |
| browser smoke 6 (placeholder still works for out-of-scope events) | `/maharashtra/elections/general-2004`: placeholder card persists (delim pre-2008 out of scope) |
| smoke console | zero `[error]` console events across all 6 smoke surfaces |

## Risk register

| # | Risk | Mitigation | Stop? |
| - | --- | --- | --- |
| 1 | **V6 pre-flight finds attribute misalignment** (datameet `PC_NUM` is national 1-543 not per-state 1-N). | Pre-flight catches it; subagent reports verbatim ogrinfo + cross-check; STOPS before authoring code. Resolution requires user sign-off on a mapping table. | YES |
| 2 | **datameet shapefile coverage <543** (e.g. only 540 PCs because community redraw skipped 3 disputed seats). | Pre-flight reports feature count; if <540, surface as Scope-change ledger row. If 540-543, proceed but document the missing seats in the closure ledger. | NO (proceed if 540+) |
| 3 | **Citation breach — datameet geometry is community redraw, not ECI-issued**. | Per V4 + V5: source.csv row names datameet as the producer + 2008-delimitation as the vintage; downstream citation chain honestly attributes the community-redraw provenance. Citizens see "Boundary source: datameet community redraw of 2008 Delimitation Commission Order" in the data attribution footer. Not a hide. | NO |
| 4 | **Frontend consumer route doesn't gracefully fall back when delim_year is pre-2008**. | Row E wiring: route logic must check `event_row.delim_year` and render placeholder for delim_year < 2008. Test this in the smoke 6 case. | NO |
| 5 | **Snapshot tool may not have a shapefile_zip URL handler** (research said it might need adding). | Row C: if snapshot.py needs a new format handler, add it (~10-20 LOC, mechanical). If it does NOT need one, no code change. | NO |
| 6 | **boundary_layers control table** — research said `boundary_layers.parquet` but post-X1a-fu2 retirement on 2026-06-07 this is `datasets/data/entities/boundary_layer.csv`. Snapshot tool may emit to the old parquet path that no longer exists. | Row C verifies tool output path; if tool emits parquet, fix tool to emit CSV per the X1a-fu2 doctrine. May require minor tool update. | NO |
| 7 | **Backend pytest baseline drift** — 30 pre-existing failures per FU#1 + FU#2 work; this PR's pytest must not introduce more. | Compare pre/post pytest run on the sub-worktree vs origin/main. | NO |

## Implementation discipline

- **Worktree:** subagent works in `..\yen-gov-pc-delim-2008` on branch `feat/boundaries-pc-delim-2008-ingest` (file-disjoint from active sibling worktrees per master-collision protection).
- **§13 UI verification:** subagent MUST hit all 6 browser smoke surfaces. Smoke 5 (regression) + Smoke 6 (placeholder still works for out-of-scope events) are critical.
- **§7 debug logs:** zero `[DEBUG]` markers at PR finish.
- **§8 git hygiene:** named branch, explicit-path `git add`, squash-merge, post-merge cleanup. NO `git add .` / `-A`.
- **§9 lockfile:** zero `package.json` changes expected.
- **CLAUDE.md §10 STOP-AND-SURFACE:** Risk #1 (V6 pre-flight) is the explicit stop. Do not proceed if attribute alignment fails.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | research | Explore subagent surveyed 7 candidate sources; datameet is the clear winner. CC-BY 4.0 license; covers 2008 delim; existing project precedent for shapefile ingest. STOP-1 (attribute alignment) requires empirical pre-flight. |
| 2026-06-12 | scope-lock | This PR ships delim=2008 PC only. Pre-2008 deferred. Per-state PC tile cartogram authoring deferred to Phase 2. |
