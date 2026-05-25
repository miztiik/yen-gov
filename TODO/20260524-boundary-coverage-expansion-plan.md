# Boundary coverage expansion — phased plan (pincode → subdistricts → villages → AC consolidation → census-2011)

**Date opened**: 2026-05-24
**Status snapshot**: Phase A (pincode) complete (A.1.a + A.1.b + A.2 merged); Phase B (subdistrict national lift) merged as #257 at `011a9764`; Phase C (village national lift) merged as #259 at `7308121a` — 27 states/UTs / 645 per-(state, district) village shards; 9 states/UTs documented as upstream gaps in [`docs/reference/boundary-data-sources.md` §"Coverage status — Village gap"](../docs/reference/boundary-data-sources.md#village-gap--the-9-statesuts-missing-from-upstream-lgd_villages) (promoted from `notes/` to canonical reference 2026-05-25).
**Authority**: Hans + Max (data shape) for layer choices; Fowler (engineering craft) for migration mechanics; Jony + Citizen for any UI surface that exposes the new layers.
**Rationale anchors** (do NOT re-state here):
- Source catalogue + cross-walk to the LGD ⇔ Census ⇔ Constituency ⇔ PIN code alignment matrix: [`docs/reference/boundary-data-sources.md`](../docs/reference/boundary-data-sources.md)
- LGD tables side: [`docs/reference/lgd-opendata.md`](../docs/reference/lgd-opendata.md)
- Disk layout + identifier discipline + methodology-break rules: [`docs/architecture/data/boundaries.md`](../docs/architecture/data/boundaries.md)
- Decision history: [ADR-0031 Boundary geometry strategy](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) (+ 2026-05-24 amendment for PC layer + delim partition)
- "Gap-fill, not bulk-swap" policy: [`boundary-data-sources.md` §"Source-selection policy"](../docs/reference/boundary-data-sources.md#why-these-choices)

## Phase 0.0 — Status ready reckoner (UPDATE AFTER EVERY PR)

**This table is the live status ledger for the boundary-coverage expansion.** Update it in the SAME PR as the phase's code/data changes, so a session interruption at any point leaves an accurate map of where work stopped. An agent picking up the work mid-flight should be able to read ONLY this table + the affected phase section to know what to do next.

| Phase | PR | Status | Merged SHA | Notes / blockers |
| --- | :---: | --- | :---: | --- |
| **0.1** Subdistrict CSV ingest (re-run `tools/lgd/snapshot.py`) | #235 | Merged | 18b8a69c | Snapshot run 2026-05-24 token landed 7,090 subdistricts (36 states); incidental states/districts refresh to 24May token included. |
| **0.2** District backfill (639 rows → `entities.json`) | #267 | In progress | — | New `tools/lgd/backfill_entities_districts.py` (pure stdlib json+csv, ~280 lines incl. docstring; replicates `state_lgd_resolver` logic inline per CLAUDE.md §4 "tools MUST NOT import backend"). Reads `datasets/taxonomy/lgd/districts-latest.csv` (784 rows), builds the `{state_lgd_int: ECI_code}` map from currently-valid state/UT rows (filters out historic composite J&K S09 via `entity_valid_to is None`), dedups against the existing 145 district rows, emits 639 new district rows sorted by `(parent_entity_id, int(lgd_code))` for byte-determinism. New row shape: `entity_id=IN-<state_eci>-D<lgd>`, `entity_valid_from=1947` (default per plan; operator may amend post-2011 carve-outs in follow-up PRs), `legacy_id=null` (no Wikipedia 3-letter predecessor for the LGD-only slice), `notes="LGD district. Census 2011 code: <N>."` when CSV `Census 2011 Code != 0` else `"LGD district."` (carries the LGD ↔ Census-2011 cross-ref as structured-comment to avoid an additive schema bump to v1.3). entities.json grows 218 → 857 rows; districts 145 → 784; `entities.parquet` regen via `emit-taxonomy` is byte-stable across re-runs (SHA-256 identical). 9 Tier-A tests in NEW `backend/tests/test_backfill_entities_districts.py` (dedup, J&K routing to U08, unknown-state loud-fail, sort order, idempotent re-run, deterministic two-cold-runs, Census-zero short-notes). Coverage rationale: [`docs/reference/boundary-data-sources.md` §"Coverage status"](../docs/reference/boundary-data-sources.md#coverage-status--what-we-have-what-we-dont-have). Gates: validate OK, pytest 1013 passed / 44 skipped / 3 deselected (the standing DuckDB-Windows-segfault deselects). |
| **0.3** Subdistrict entity seed | — | Deferred → Phase B.1 | — | Folded into Phase B ingest |
| **0.4** Simplify existing national boundary files (D-P) | #244 | Merged | a0f34911 | **Blocks D.0 and D.6** — `tools/boundaries/simplify.py` (NEW) wraps mapshaper; 74 shards re-simplified in-place; 71% gz byte reduction (26.8 MB → 7.6 MB); contract test `boundaries-conform.test.ts` extended with per-layer ceiling. |
| **A.1.a** Pincode directory — structural surface (no real data) | #247 | Merged | f46b02ca | Pure parser (`pincode_directory.py`) + `ResourceMeta` entry (UUID `5c2f62fe-5afa-4119-a499-fec9d604d5bd`) + Tier-A test against inline 5-col fixtures. Sufficient to unblock A.1.b; parser amended in A.1.b to handle the real 11-col upstream shape. |
| **A.1.b** Pincode directory — ingest + emit | _pending_ | In progress | — | Operator captcha-fetched the 11-col CSV (165627 rows) into `datasets/ephemeral/all_india_pincode_directory_2025.csv`. Parser amended (5 → 11 cols; 6 new fields optional, back-compat preserved). Ingest module (`ingest_pincode.py`) parses + sorts by (pincode, officename) + writes deterministic CSV intermediate + DuckDB `read_csv` multi-thread COPY → Parquet (3.75 MB, 165627 rows, 92.6% with WGS84 lat/long, 261 invalid coord cells skipped). UPSERTs `src-8d139f840009` (Department of Posts, "All India Pincode Directory", 2025; OGL-IN-1.0; gold; issuing-authority; transcribed). Wall-time 12s on 165k rows; byte-identical across re-runs (verified SHA-256). 14 parser tests + 10 ingest tests; backend pytest 943 passed / 44 skipped / 0 failed. |
| **A.2** Pincode polygons (national) | #254 | Merged | 39932f09 | Operator-supplied KMZ at `datasets/ephemeral/dd7bfd69-143e-462b-bfa3-2ac35d931342.kmz` (data.gov.in OGD All-India Pincode Boundary, Department of Posts, 2025). Pure stdlib KML 2.2 parser (`pincode_polygons.py`) + ingest (`ingest_pincode_polygons.py`) emit 36 per-state shards (`boundaries/in/postal/state=in_<sNN>/all.geojson`) + 1 synthetic `scope=unkeyed` shard for 17 pincodes whose state cannot be resolved via `MIN(statename) GROUP BY pincode` against the A.1.b directory parquet. 19,312 placemarks parsed; 19,295 keyed (99.91%); 17 unkeyed; largest shard TN at 5.2 MB uncompressed (well under 8 MB-gzipped PMTiles cutover). Byte-determinism verified across re-runs (SHA-256 identical for all 37 shards + boundary_layers.parquet + sources.parquet). 7th boundary source seeded (`datagovin_post_pincode_polygons_2025`, OGL-IN-1.0, gold, **issuing-authority** — first non-republisher boundary source) via `BOUNDARY_SOURCES` extension; `boundary_layers_seed.py` count assertions bumped 6→7 in lockstep. 16 parser tests + 14 ingest tests; backend pytest 973 passed / 44 skipped / 0 failed. No UI consumer yet — §13 smoke deferred per A.2 acceptance gate. |
| **B** Subdistrict national lift (TN → 36 states/UTs) | #257 | Merged | 011a9764 | 0.1 (#235) already supplied the subdistricts CSV. New `tools/boundaries/lift_subdistricts_national.py` (one-shot orchestrator, ~330 lines, pure stdlib + DuckDB writer) reads cached `LGD_Subdistricts.geojsonl` (6,471 features), groups by `state_lgd` property, maps to ECI state code via new `backend.yen_gov.canonical.state_lgd_resolver` (entities.json → `{state_lgd_int: ECI_code}` map; pure logic; 10 unit tests), and emits 36 per-state shards under `boundaries/in/subdistricts/state=in_<sNN>/all.geojson`. Largest shard S12 (Maharashtra) at 9,974 KB, well under 12 MB SNAPSHOT_BYTE_BUDGET. 0 unkeyed features (every `state_lgd` resolves to a current state/UT). TN partition_path identical to legacy entry (same layer_id) — merge_with_existing semantics replace the row; ledger goes from 110 → 146 rows (+36 subdistrict). Legacy TN-only pipeline.json entry (`kind=subdistricts, state=S22, state_filter=state_lgd=33`) **deleted** — the orchestrator supersedes it; running snapshot.py never re-creates the obsolete TN slice. 0.3 (subdistrict entity seed) intentionally deferred from this PR — needs district backfill (0.2, 639 missing district entities) as prerequisite; not yet started. 19/19 unit tests pass; `python -m yen_gov validate --root .` OK. |
| **C** Village national lift (TN → 27 states/UTs; 9-state upstream gap) | #259 | Merged | 7308121a | New `tools/boundaries/lift_villages_national.py` (one-shot orchestrator, ~370 lines, pure stdlib + DuckDB writer) reads cached `LGD_Villages.geojsonl` (1.8 GB / 584,615 features), groups by `(state_lgd, dist_lgd)` tuple, maps state_lgd → ECI via the shared `state_lgd_resolver` from Phase B, and emits per-(state, district) Hive shards under `boundaries/in/villages/state=in_<sNN>/district=<lgd>/all.geojson` (two-level partition). 9/9 unit tests green (grouping + sort determinism + end-to-end emit + byte-determinism + unknown-state warning + stale-shard cleanup). Result: 645 village shards across 27 states/UTs; 0 unkeyed features; 0 oversize-skip; ledger goes from 108 → 753 rows (+645 village). Pre-existing 38 TN shards REPLACED in place (same partition_path keys → merge_with_existing semantics retire the legacy rows); NET new = 607. Legacy TN-only pipeline.json entry (`kind=villages, state=S22, state_filter=state_lgd=33`) **deleted** — the orchestrator supersedes it. **9 states missing villages from upstream**: S02 Arunachal Pradesh, S08 Himachal Pradesh, S14 Manipur, S15 Meghalaya, S16 Mizoram, S17 Nagaland, S21 Sikkim, U08 J&K, U09 Ladakh (one more than the plan's 8-state estimate — Ladakh U09 had been counted within "J&K" in the plan; both are now confirmed separately gone). Coverage recon documented in [`docs/reference/boundary-data-sources.md` §"Coverage status"](../docs/reference/boundary-data-sources.md#coverage-status--what-we-have-what-we-dont-have); bhuvan fall-back remains OUT OF SCOPE per the plan. Memory peak ~11 GB during the JSON-parse phase (acceptable on dev machines; documented in module docstring); wall-clock ~10 min end-to-end on the cached extract. `python -m yen_gov validate --root .` OK. |
| **D.0** State polygon swap (DataMeet → ramSeraph `LGD_States`) | #263 | Merged | b2742582 | Survey-grade upgrade landed. `tools/boundaries/pipeline.json` swapped to single ramSeraph URL with `id_property=State_LGD` (int), `name_property=STNAME`, `coord_precision=2`. `datasets/boundaries/in/states/all.geojson` = 36 polygons, 406 KB raw / 84.1 KB gz (well under 16 MB national ceiling). All 36 LGDs FK-resolve to `taxonomy/sources.parquet` row `src-a1dd899f902d` (CC0 1.0, issuing-authority). Frontend consumers re-wired: `view-models/states.ts` adds `boundary_join_key` string-keyed projection + `lgdCodeToEci()` helper + widened `eciFromStateName`; `IndicatorChoropleth.svelte` + `maplibre/IndiaMap.svelte` switch fills/tooltips to `boundary_join_key`; `maplibre/sources.ts` + `boundaries.ts` `JOIN_KEYS.state` = `"State_LGD"` with MapChoropleth `keys_are_numeric` + `to-number` int-bridge. Tests: NEW Phase D.0 invariants block in `boundaries-conform.test.ts` (4 invariants); overhauled `view-models/states.test.ts` (22 tests); updated `boundaries.path.test.ts`. Gates: validate OK, pytest 1001 passed / 44 skipped / 3 deselected, svelte-check 0 errors, D.0-scope vitest 44/44, §13 browser smoke 7 routes incl. choropleth-join verified on `/t/fiscal` (Punjab dark red, regional differentiation). Pre-existing 487 vitest failures on `boundaries.budget.test.ts` + `boundaries-conform.test.ts` Phase 0.4 (PR #257 / #259 budget-ceiling debt) NOT caused by D.0; follow-up ceiling-bump PR queued separately. |
| **D.1** AC consolidation snapshot recon (one-shot, gating) | — | Not started | — | Independent of 0.4 |
| **D.2** AC consolidation promote 28 states | — | Not started | — | After **D.1** |
| **D.3** AC consolidation — Assam carve-out | — | Not started | — | After **D.1** |
| **D.4** AC consolidation — J&K carve-out | — | Not started | — | After **D.1** |
| **D.5** AC consolidation wrap-up (docs + ledger + ADR amend) | — | Not started | — | After **D.2/D.3/D.4** |
| **D.6** PC polygon swap (shijithpk → ramSeraph `LGD_Parliament_Constituencies`) | — | Not started | — | After **0.4**; survey-grade upgrade per user override 2026-05-24 |
| **E** Census-2011 polygon layer | — | Deferred | — | Out of scope until first Census-driven citizen surface ships |

**Update protocol** (mandatory for every PR landing in this plan):
1. Set `Status` to `In progress` when the worker worktree is created.
2. Set `PR` to `#<number>` once `gh pr create` returns.
3. Set `Status` to `In review` if waiting on CI / human review.
4. Set `Status` to `Merged` + `Merged SHA` to the 7-char short merge SHA once `gh pr merge` confirms `state: MERGED`.
5. If blocked, set `Status` to `Blocked: <reason>` + add detail in `Notes`. Never silently skip.
6. The status update lives in the SAME commit as the phase's code/data work \u2014 NOT a separate docs PR (per CLAUDE.md §5 "docs-only PRs are a code smell").

**Status enum** (case-sensitive): `Not started` | `In progress` | `In review` | `Merged` | `Blocked: <reason>` | `Deferred`

---

## Boundary file-size policy (Jony + Fowler joint, 2026-05-24)

**Two levers in strict order** to keep per-shard size citizen-friendly on patchy 4G:

1. **Simplify geometry** at zoom-appropriate Douglas-Peucker tolerance (lever applied first, every time).
2. **Shard at the citizen's current viewport, no finer** (lever applied only if simplification can't bring a shard under the per-fetch ceiling).

**Per-fetch ceiling**: ≤ 500 KB gzipped per file. **Per-fetch floor**: ≥ ~50 KB gzipped (below this the per-fetch TLS + HTTP/2 header overhead dominates wall-clock; many tiny fetches are wasteful, not faster). Aim for **100–300 KB gzipped per shard** as the sweet spot.

**On-disk reality today (audited 2026-05-24)** — every "national" file currently violates the ceiling by 3–5×:

| File | Raw KB | Est gzip KB | Verdict |
| --- | ---: | ---: | --- |
| `country/all.geojson` | 12,042 | ~2,168 | Way over |
| `states/all.geojson` | 11,330 | ~2,040 | Way over |
| `pc/delim=2024/all.geojson` | 8,564 | ~1,542 | Over |
| `districts/all.geojson` | 6,696 | ~1,205 | Over |
| `ac/state=in_u08/all.geojson` | 5,519 | ~993 | Outlier, over |
| `subdistricts/state=in_s22/all.geojson` | 5,084 | ~915 | Over (TN only ingested today) |
| Largest village per-district shard (`district=593`) | 2,727 | ~491 | At ceiling |
| Most AC per-state shards | 100–1,000 | 20–300 | Sweet spot |
| Most village per-district shards | 100–2,000 | 20–400 | Sweet spot |

**Per-layer simplification targets** (Phase 0.4 implements these; Phase D.0 + D.6 swap targets must clear them):

| Layer | Citizen viewport zoom | Douglas-Peucker tolerance | Target gzipped per shard | Shard rule |
| --- | --- | --- | ---: | --- |
| `country` | India-fits-on-phone | ~0.005° (~500 m) | < 100 KB | 1 national file |
| `states` | India zoom | ~0.002° (~200 m) | < 200 KB | 1 national file (36 features) |
| `districts` | India zoom | ~0.001° (~100 m) | < 500 KB | 1 national file (784 features); shard by state ONLY if still > 500 KB after D-P |
| `pc` | India zoom | ~0.001° | < 500 KB | 1 national file (545 features); shard by state ONLY if > 500 KB after D-P (likely after survey-grade swap) |
| `ac` | state-hub zoom | ~0.001° | < 500 KB per state | per-state shard already; ONLY tighten D-P for the 3–4 outlier states (UP/MP/BR/RJ) |
| `subdistricts` | state-hub zoom | ~0.0005° (~50 m) | < 300 KB per state | per-state shard (Phase B) |
| `villages` | district-drill zoom | ~0.0002° (~20 m) | < 500 KB per district | per-district shard already (Phase C) |

**Why simplification first, sharding second** (Fowler's HTTP economics + Jony's URL grammar):
- TLS+TCP setup on patchy 4G is ~200–500 ms latency per fresh connection; HTTP/2 multiplexes BUT per-request header overhead is still ~50–100 ms.
- Going from 1 file → N files multiplies header overhead linearly; the savings appear only when each shard is genuinely smaller than the per-fetch ceiling AND the viewport actually needs only one shard at a time.
- Citizens looking at India don't see 1 m coastline precision; they see Bharat-shaped blob. Survey-grade vectors are wasted bytes at that zoom.
- Each fetch is also a failure mode + a loading-state flicker. Many small fetches = many retry banners; fewer fetches = cleaner UX.

**The URL grammar stays one-fetch-per-viewport**:
- Home / national choropleth → 1 file `<layer>/all.geojson`
- State hub → 1 file `<layer>/state=<s>/all.geojson`
- District drill (today only meaningful for villages) → 1 file `<layer>/state=<s>/district=<d>/all.geojson`

**This policy applies as a hard gate** on Phase D.0 (state geometry swap) and Phase D.6 (PC swap). Survey-grade BharatMaps polygons will balloon raw size 2–3× vs current sources; Phase D.0 + D.6 PRs MUST simplify down to the targets above before merging.

---

## Phase summary

| Phase | Scope | Status | Active PRs | Blocking |
| --- | --- | --- | --- | --- |
| **0** | LGD coverage prereq: fetch missing `Subdistricts.csv` via `tools/lgd/snapshot.py`; backfill remaining 639 districts into `entities.json`; seed first `entities.json` subdistrict rows | Not started | — | None (gates B + C readiness) |
| **A** | Pincode lookup CSV (Phase A.1) + national pincode polygons (Phase A.2) | Not started | — | None (independent of B/C/D/E) |
| **B** | Sub-district national lift (TN-only → 36 states/UTs) using ramSeraph `LGD_Subdistricts` | Not started | — | Phase 0 subdistrict CSV ingest |
| **C** | Village national lift (TN-only → national, minus 8 states upstream) using ramSeraph `LGD_Villages` | Not started | — | After B (proves the LGD ingest pattern at smaller cardinality) |
| **D** | Survey-grade swap to ramSeraph BharatMaps lineage: state polygons (D.0), AC consolidation (D.1–D.5), PC swap (D.6) | Not started | — | D.1 snapshot recon must happen before any AC promotes; D.0 + D.6 are independent of AC work |
| **E** | Census-2011 polygon layer (`Districts_2011`, `SubDistricts_2011`) — adopt when first census-driven citizen surface ships | Deferred | — | First Census-2011 indicator consumer; out of scope until then |

---

## Phase 0 — LGD code coverage prerequisites

**Why this phase exists**: Phases B and C lift sub-district and village geometry. The geometry is keyed by `lgd_code`; without the matching LGD CSV on disk, the ingest has no name/parent reference to validate against. We have states (100%) and the LGD districts mirror (784 rows), but subdistricts haven't been snapshotted and only 145 of 784 districts are folded into `entities.json` today (the 145 with ECI mappings). Phase 0 closes both gaps.

**Coverage status on disk (audited 2026-05-24)**:

| Layer | LGD CSV mirror (`datasets/taxonomy/lgd/`) | `entities.json` rows | Notes |
| --- | :---: | :---: | --- |
| State | ✅ `states-latest.csv` (36 rows, dated 2026-05-20) | 29 states + 10 UTs = **39 / 39 (100%)**, all carry `lgd_code` + `iso_3166_2` + `legacy_id` (ECI) | No work needed |
| District | ✅ `districts-latest.csv` (784 rows, dated 2026-05-20) | **145 / 784 (18%)**, all 145 carry `lgd_code` | The 145 are the districts with ECI-linked constituencies; 639 non-electoral districts await fold-in. Per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md) new districts land via hand-curated PR against `entities.json`, not re-scrape — backfill is a one-shot. |
| Subdistrict | ❌ None on disk | **0** | Snapshot tool wired ([`tools/lgd/snapshot.py`](../tools/lgd/snapshot.py) line 50 has `Subdistricts` in `REQUIRED_COMPONENTS`) but no `subdistricts-latest.csv` yet — either the last `tools/lgd/snapshot.py` run pre-dated the Subdistricts wiring, or the upstream release token's Subdistricts asset isn't published yet. Re-run + verify. |
| Village | ❌ None on disk | **0** | Optional component on the snapshot tool. Defer until Phase C. |

### 0.1 — Subdistrict CSV ingest

- **What ships**: `datasets/taxonomy/lgd/subdistricts-<YYYY-MM-DD>.csv` + `subdistricts-latest.csv` + `subdistricts-latest.csv.sources.json` provenance sidecar. Same dated+latest+sources triple shape as states/districts.
- **Tooling**: re-run `python tools/lgd/snapshot.py` from repo root. The tool already lists `Subdistricts` as a required component (added 2026-05-15) but the disk shows only states + districts — so either (a) the upstream release token doesn't have `Subdistricts.<token>.csv.7z`, or (b) the tool hasn't been re-run since the wiring change. Both are operator-runnable in seconds.
- **Recovery if upstream is missing the asset**: file an issue at [`ramSeraph/opendata`](https://github.com/ramSeraph/opendata/issues) requesting the Subdistricts asset on the next release; in the meantime the LGD portal export ([screenshot the user provided](https://lgdirectory.gov.in/globalviewsubdistrict.do)) is a manual fall-back — click "Spreadsheet" per state, drop the 36 CSVs under `.runtime/raw/lgd/subdistricts-portal/`, then a small `tools/lgd/portal_subdistrict_concat.py` (NEW, ~30 lines) concatenates them with a unified header. **Do NOT build a captcha-solving headless-browser scraper** — the portal export is faster manually than a robust scraper, and ramSeraph's automated mirror is the long-term plan.
- **Acceptance gates**:
  - File row count: expect ~6,500 subdistricts nationally (per LGD documentation). Loud-fail < 5,000 or > 8,000.
  - Sidecar `sources.json` carries a `source_id` rooted at the LGD Authority + date token.
  - Tier-A schema-sanity test asserts header shape: `S.No., State Code, District Code, Sub-District Code, Sub-District Name (In English), Sub-District Name (In Local), Census 2011 Code, ...`.
  - **No frontend consumer in this sub-phase** — the CSV is read by Phase B + 0.3 only.

### 0.2 — District backfill (639 rows → `entities.json`)

- **Why this phase exists (citizen-need rationale)**: District-level choropleths are a real, near-term citizen need across multiple Phase-2 and Phase-3 indicator families. **Financial inclusion** ingests bank branches at pincode level and rolls up to district to show banking density ("how many branches per 100k population in my district"). **Topography / rainfall / water** indicators (groundwater levels, monsoon precipitation, soil moisture) are published district-keyed by IMD / CGWB / NABARD and need district polygons to render meaningfully. **Social-sector trackers** (PMAY housing coverage, JJM tap-water coverage) are district-keyed by design. Today's 145-district entity subset (the ECI-mapped slice across S03/S06/S11/S22/S25/U07) is **insufficient** for any of these surfaces — the choropleth polygon paints, but no entity row means no label, no tooltip, no hub-link, no provenance lookup. The 639-district gap blocks every district-keyed citizen surface outside the 6 ECI states. **Hand-curation is the right answer here, not a workaround.** Per user direction 2026-05-25: "let us not shy away from" the hand-curation work; per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md), `entities.json` is the hand-curated authoritative roster by design.
- **Cross-enrichment guidance (multi-source)**: Three sources already carry the raw inputs; the generator script cross-joins them at suggest-time so the operator-review pass is small:
  1. **LGD master CSV** (`datasets/taxonomy/lgd/districts-latest.csv`) is the primary source-of-truth for the modern roster (784 active LGD codes). The CSV itself carries `Census 2001 Code` + `Census 2011 Code` columns — it is **already a pre-joined LGD ⇔ Census-2011 cross-reference**. No second-source ingest needed for the basic mapping.
  2. **Census-2011 polygons** (`Districts_2011` from ramSeraph, CC0-1.0) supply an independent name + geometry cross-check for districts that existed in 2011. Where the LGD-CSV `Census 2011 Code` is populated, the row inherits a 2011-vintage ancestor entity (the generator outputs this as a suggestion for the operator to confirm).
  3. **`entities.json` conventions** (per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md)) define the row shape (`entity_id` = `IN-S{nn}-D{lgd_code}`, `parent_entity_id` = parent state row, `entity_valid_from` = gazette date for post-2011 carve-outs OR 1947 for pre-existing, `legacy_id` = wikipedia 3-letter ECI cross-reference where applicable).
- **What ships**: hand-curated extension of `datasets/taxonomy/entities.json` to cover the remaining 639 districts in `districts-latest.csv`. Each new row carries `entity_id` = `IN-S{nn}-D{lgd_code}` (the existing convention, e.g. `IN-S22-D568` for Chennai), `entity_type="district"`, `lgd_code` from the CSV, `display_name` from the CSV (operator-normalised for casing / hyphenation quirks), `parent_entity_id` = parent state. `legacy_id` (the wikipedia 3-letter code) stays NULL for non-ECI-mapped districts — it's an optional ECI-cross-reference column, not a primary identifier.
- **Tooling**: small generator script (~50 lines) `tools/lgd/backfill_entities_districts.py` (NEW) that reads `districts-latest.csv`, diffs against `entities.json#/entities`, emits a JSON patch the operator hand-reviews + commits. The output is deterministic so the patch is small (only the 639 net-new rows). The generator's suggested rows include the LGD-CSV `Census 2011 Code` as a structured-comment field on each patch entry so the operator can spot any LGD ↔ Census-2011 mismatches that flag a real entity event (split / merger / rename) vs a transliteration drift; mismatches go to a `notes/` recon file before the patch is merged.
- **Why hand-review (not full automation)**: per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md), `entities.json` is hand-curated. The generator suggests rows; the operator confirms (a) display-name casing / hyphenation, (b) `entity_valid_from` (default 1947 for pre-2011 districts, gazette date for post-2011 carve-outs such as Mayiladuthurai 2020, Tenkasi/Tirupathur/Chengalpattu/Kallakurichi/Ranipet 2019, the Telangana split 2014, Ladakh 2019), (c) LGD ↔ Census-2011 name-drift flags. Multi-source enrichment continues across future LGD snapshots: when a fresher LGD CSV lands, re-run the generator; its diff highlights deltas (new districts, renames, code retirements); operator confirms each delta before commit.
- **Acceptance gates**:
  - All 639 new rows carry `lgd_code` (the existing `test_compile_skips_districts_without_lgd_code` enforces no-row-without-code at compile time).
  - `entities.json` row count goes from 185 to 824 (185 + 639).
  - `entities.parquet` compile is deterministic and byte-stable on re-run.
  - `python -m yen_gov validate --root .` is OK.
  - Per-state district counts on `entities.parquet` reconcile within ±1 against `datasets/boundaries/in/districts/all.geojson` `dist_lgd` cardinality per state.
  - No frontend consumer changes (state-hub pages today don't list districts; adding them is a separate Jony PR).
- **Sequencing**: Phase 0.2 is **independent of all D.* work** — can ship in parallel with Phase D.0 (state polygon swap) or any AC consolidation phase. Recommended sequence: D.0 first (small surgical, unblocks survey-grade state map), then 0.2 (larger hand-curation work). But the two are sequenceable in either order without blocking each other.

### 0.3 — Subdistrict seed into `entities.json` (DEFERRED to Phase B)

- The first user-visible reason to add `entity_type="subdistrict"` rows to `entities.json` is when Phase B emits per-state subdistrict geojsons that need an entity FK target. **Defer**: ship Phase 0.1 + 0.2 first; Phase B adds subdistrict entity rows as part of its own ingest PR (likely a separate sub-phase B.1).

### 0.4 — Simplify existing national boundary files (Jony + Fowler joint, blocks D.0)

- **Why this sub-phase exists**: every "national" file on disk today exceeds the 500 KB gzipped per-fetch ceiling by 3–5× (see "Boundary file-size policy" above). This makes patchy-4G page-load wall-clock unnecessarily painful TODAY, and it will get worse once the Phase D.0 + D.6 survey-grade swaps inflate raw vertex counts.
- **What ships**: a new `tools/boundaries/simplify.py` (~80 lines) that wraps Shapely's [`simplify(tolerance, preserve_topology=True)`](https://shapely.readthedocs.io/en/stable/reference/shapely.simplify.html) (or [`mapshaper`](https://github.com/mbloch/mapshaper) CLI if Shapely's tolerance behavior at very low values is unstable for our coastlines). Runs per-layer at the tolerance specified in the per-layer table above. Emits in place. Deterministic on re-run.
- **Acceptance gates**:
  - Run on existing `country`, `states`, `districts`, `pc/delim=2024`, `subdistricts/state=in_s22`, all AC per-state, all village per-district files.
  - Every resulting file ≤ 500 KB gzipped (measure with `gzip -c | wc -c`).
  - Vitest contract: extend [`frontend/src/contracts/boundaries-conform.test.ts`](../frontend/src/contracts/boundaries-conform.test.ts) to fail the build if any boundary file exceeds the per-layer gzipped ceiling.
  - **§13 browser smoke**: home choropleth + 3 state hubs (TN/KL/BR) + 1 district drill (TN district 568) all render visually indistinguishable at India / state / district zoom levels. Pixel-level diffs at coastlines are expected and acceptable at the simplification tolerance; missing polygons or visible jagged edges at viewport zoom are not.
  - Tier-A + Tier-B + svelte-check pass.
- **Independent of 0.1 + 0.2**: can ship as its own PR before or after the LGD CSV ingest.

---

## Phase A — Pincode (lookup table → then polygons)

**Why this phase exists**: pincode is the only common spatial vocabulary an Indian citizen volunteers ("my pincode is 600028"); it is an orthogonal *search-only* layer per [`boundaries.md` §"Postal"](../docs/architecture/data/boundaries.md#postal-pincode--search-only-orthogonal-layer). The structural surface (schema, loader, `boundaryRelPath("postal")`) already landed; only ingest remains.

**Use the existing adapter, don't build a new one.** [`backend/yen_gov/sources/datagovin_ogd/`](../backend/yen_gov/sources/datagovin_ogd/) already ships the **operator-CSV-cache** pattern for data.gov.in resources — pin a `ResourceMeta` in [`urls.py`](../backend/yen_gov/sources/datagovin_ogd/urls.py), operator runs the one-time captcha-solve and drops the CSV under `.runtime/raw/datagovin/<leaf>.csv`, ingest reads from the cache thereafter. Proven on `fiscal/centre_transfers_gross`. **Do NOT build a new HTTP client**; do NOT use the OGD JSON API ([`urls.py` docstring](../backend/yen_gov/sources/datagovin_ogd/urls.py) explains why: demo key caps at 10 rows/request, 429s after a few pages, real keys gated on SMS-OTP we cannot script).

### A.1 — Pincode directory CSV (citizen lookup table, ~165k rows)

- **Primary source — `pincode-directory` (NEW)**: Department of Posts (issuing authority, **gold** tier), via data.gov.in [`all-india-pincode-directory-till-last-month`](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month). Monthly cadence, GODL-IN, CSV. Columns: `circlename, regionname, divisionname, officename, pincode`. This is **the** authoritative directory — every Post Office row keyed by pincode. Use it as the canonical pincode lookup.
- **Resource UUID discovery**: run [`tools/datagovin_recon.py all-india-pincode-directory-till-last-month`](../tools/datagovin_recon.py) — emits the resource UUID + download URLs by scraping the portal page (data.gov.in builds pages client-side; UUIDs live in the inline JS). Pin the result in [`backend/yen_gov/sources/datagovin_ogd/urls.py`](../backend/yen_gov/sources/datagovin_ogd/urls.py) as a new `ResourceMeta`.
- **What ships**:
  - One operator-captcha-fetched CSV cached at `.runtime/raw/datagovin/pincode_directory.csv` (ephemeral per [`CLAUDE.md §2`](../CLAUDE.md), not committed).
  - Emitted reference table at `datasets/reference/in/pincodes/pincode-directory.csv` (+ companion `pincode-directory-YYYY-MM.csv` immutable snapshot following the LGD dated+latest shape from [PR #73](../docs/reference/lgd-opendata.md)). **NOT** under `datasets/indicators/` — pincode is reference data, not an indicator.
  - New schema `datasets/schemas/pincode-directory.schema.json` v1.0 validating columns + `source_id` FK.
  - One row added to `datasets/taxonomy/sources.parquet` via `backend.yen_gov.canonical.citation.derive_source_id` (producer="Department of Posts (Ministry of Communications)", title="All India Pincode Directory", vintage="<YYYY-MM>", license=`OGL-IN-1.0` if our enum permits OR `unknown-public` until clarified — verify against [§12 enum](../CLAUDE.md), GODL-IN may need adding).
- **Supplementary — LGD pincode tables (DEFER, lower priority)**: [`ramseraph.github.io/opendata/lgd/`](https://ramseraph.github.io/opendata/lgd/) `pincode_urban.<DDMmmYYYY>.csv.7z` + `pincode_villages.<DDMmmYYYY>.csv.7z` map pincode → ULB/village `lgd_code`. **Only adopt if Phase D / Phase B exposes a need for the LGD-code join**; the Dept of Posts directory above is sufficient for the citizen-volunteers-their-pincode use case. When/if adopted, output to `datasets/taxonomy/lgd/pincode-urban.csv` + `pincode-villages.csv` via `tools/lgd/snapshot.py` (existing tool, NOT a new one).
- **Acceptance gates**:
  - Tier-A schema sanity (`pytest -q`): new `pincode-directory.schema.json` validates against JSON Schema 2020-12 meta; new `backend/tests/test_sources_datagovin_ogd_pincode.py` exercises the parser against a 5-row fixture.
  - Tier-B corpus conformance (`python -m yen_gov validate --root .`): the emitted CSV round-trips through the schema.
  - Row-count sanity: ~165k rows expected (every Post Office in India). Loud-fail if <100k or >300k.
  - Provenance: emitted CSV row count = sum across `circlename` partitions = same as upstream CSV row count modulo deduplication on `(officename, pincode)`.
  - **No frontend consumer in this sub-phase** — A.1 is a backend-only data drop. §13 browser smoke not required.

### A.2 — National pincode polygons

- **What ships**: `datasets/boundaries/in/postal/IN-pincodes-<region>.geojson` shards conforming to the existing `postal` schema; ledger row(s) in `boundary_layers.parquet`.
- **Source candidates** (pick one per first-snapshot recon):
  1. ramSeraph [`indian_cadastrals#postal`](https://github.com/ramSeraph/indian_cadastrals/releases/tag/postal) — `PincodeBoundaries.geojsonl.7z` (PostalGIS lineage, CC0-1.0). **Coverage gap**: missing HP, J&K, Sikkim, ML, MZ, MN, NL, AR (8 states/UTs).
  2. Same release — `Datagov_Pincode_Boundaries.geojsonl.7z` (data.gov.in lineage, GODL-IN). **All-India coverage**, but lower granularity in some urban areas.
  3. Same release — `GSDL_Pincodes.geojsonl.7z` (Geospatial Delhi Limited, CC0-1.0). **Delhi only**, but per-sub-locality granularity. Pair with #1 or #2 for the rest of India.
- **Recommended split**: adopt #1 (PostalGIS) as the primary national source + #3 (GSDL) for Delhi; fall back to district polygons for the 8 missing states. Avoids GODL-vs-CC0 license mixing and keeps the granularity story consistent.
- **Tooling**: extend `tools/boundaries/snapshot.py` — `geojsonl_7z` dispatch path already exists. Add the source to `tools/boundaries/pipeline.json#inputs[]` with `kind=postal`, `state_filter` not used (national).
- **Acceptance gates**:
  - Tier-A schema sanity: pincode `postal` geometry validates against the existing schema.
  - Tier-B corpus conformance: ledger row(s) carry `level=postal`, valid `source_id` FK.
  - File-size budget: per-shard ≤ 8 MB gzipped (boundaries.budget.test.ts). If the national pincode file exceeds, split by state-prefix (pincode 6 → first digit gives region) into 9 shards.
  - Frontend boundaries contract test (`frontend/src/contracts/boundaries-conform.test.ts`) passes.
  - §13 browser smoke: ONLY if a consumer surface exists. A.2 alone has no UI consumer — defer §13 smoke until the search affordance lands as a separate PR.

### A.3 — (Future, NOT this plan) Search affordance UI

- Out of scope here. Pincode → "this is your district / AC / PC" surface is a separate Jony + Citizen PR after A.1 + A.2 land.

---

## Phase B — Sub-district national lift

**What ships (as actually executed, 2026-05-25)**: extends the existing sub-district adoption (TN-only today, 300 features) to all 36 states/UTs via a one-shot orchestrator script rather than the planned `state_filter` removal on the snapshot.py entry.

- **Source**: ramSeraph [`indian_admin_boundaries#subdistricts`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/subdistricts) — `LGD_Subdistricts.geojsonl.7z` (60 MB compressed, 263 MB extracted, 6,471 features).
- **Mechanics (actual)**: rather than removing `state_filter` from the `tools/boundaries/snapshot.py` pipeline entry, a new one-shot orchestrator [`tools/boundaries/lift_subdistricts_national.py`](../tools/boundaries/lift_subdistricts_national.py) reads the cached extracted geojsonl, groups features by the `state_lgd` integer property, maps each LGD code to an ECI state code via [`backend/yen_gov/canonical/state_lgd_resolver.py`](../backend/yen_gov/canonical/state_lgd_resolver.py) (NEW; pure-logic projection of `entities.json` state/UT rows to `{state_lgd_int: ECI_code}`), and emits one per-state shard under `boundaries/in/subdistricts/state=in_<sNN>/all.geojson`. The orchestrator reuses `snapshot.py`'s public primitives (`fetch_geojsonl_7z`, `emit_feature_collection`, `_round_coords_geom`, `SNAPSHOT_BYTE_BUDGET`) so per-shard byte format is byte-for-byte identical to what snapshot.py would have produced; only the orchestration moved.
- **Why a separate orchestrator rather than extending snapshot.py**: snapshot.py's existing `split_by` machinery emits shards keyed by the raw group key (e.g. `district=603`), not by a value derived from a per-row lookup against another canonical table (here: LGD `state_lgd` int → ECI state code via `entities.json`). Adding that resolver path into snapshot.py would either teach `derive_hive` about state-code resolution (cross-cutting concern) or layer new pipeline.json field semantics (`lift_by_state`-style). Both are larger changes than the one-shot lift, and Phase C (village lift) can independently choose to invoke this script with parameters or reuse a generalised snapshot.py extension after Phase B's pattern stabilises. The legacy TN-only pipeline.json entry is **deleted** in this PR; the orchestrator is the canonical source for the subdistricts tree.
- **Acceptance gates (results)**:
  - Ledger row count: 36 `level=subdistrict` shards (one per state/UT partition), not 1. ✓
  - Per-state retained-feature counts non-zero: every state of the 36 emitted ≥ 1 feature; 0 unkeyed (every `state_lgd` resolves to a current state/UT). ✓
  - File-size budget: per-shard ≤ 12 MB raw (`SNAPSHOT_BYTE_BUDGET`). Largest is S12 Maharashtra at 9,974 KB; S13 MP at 9,305 KB; S24 RJ at 8,237 KB. All well under the budget; no `split_by=district` partition needed for subdistricts. The Jony per-fetch gzip ceiling (≤ 500 KB gzipped per shard, ~< 300 KB target per the per-layer policy table above) will be enforced by a follow-up Phase 0.4-class simplification PR if/when subdistrict shards land in a consumer surface; this PR is coverage extension, not size optimisation. ✓
  - Tier-A schema sanity: 19/19 unit tests pass (10 resolver + 9 lift). Tier-B corpus conformance: `python -m yen_gov validate --root .` OK (0 issues). Full backend pytest: 992 passed / 44 skipped / 0 failed (973 pre-existing + 19 new). ✓
  - §13 browser smoke: skipped per the original acceptance gate — no consumer surface yet uses the subdistrict layer beyond TN. The 9 SoI state-page consumers that load the TN shard (`state=in_s22`) keep working since the partition_path is identical pre/post lift (same layer_id; merge_with_existing semantics replace the row in boundary_layers.parquet). ✓
- **0.3 (subdistrict entity seed) status**: intentionally **deferred** from this PR. The plan-doc folds 0.3 into Phase B (per the 0.1→0.4→A.1→A.2→B→C→D dependency order), but seeding ~6,471 subdistrict rows into `entities.json` requires the 639 missing district entities (0.2) as parents — and 0.2 has not yet shipped. Per the per-row entity_id convention `IN-S<nn>-D<lgd>-SD<lgd>`, every subdistrict row needs an `parent_entity_id` that resolves to a current district row; today only 145 of 784 districts live in `entities.json`. Sequencing rule: ship 0.2 → ship 0.3 as a follow-up (single dedicated PR, ~6.5k row additions, deterministic generator from the subdistricts CSV). This PR ships the geometry alone; consumers that need to drill from district to subdistrict via the FK will get the additional rows in a follow-up.

---

## Phase C — Village national lift

**What ships**: extend village adoption (TN-only today, 38 districts) to all states for which ramSeraph publishes village geometry.

- **Source**: ramSeraph [`indian_admin_boundaries#villages`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/villages) — `LGD_Villages.geojsonl.7z`. **Upstream coverage gap**: HP, J&K, Sikkim, ML, MZ, MN, NL, AR are missing. Fall-back files in the same release: `bhuvan_villages.geojsonl.7z` (broad coverage) + `Bhuvan_JK_Villages.geojsonl.7z` (J&K-specific). License chain identical to other LGD files.
- **Mechanics**: same pattern as Phase B but with `split_by=district` enforced from the start (village geometry is the largest layer).
- **Pre-flight**: snapshot once into `.runtime/raw/ramseraph/villages/`, run `du -sh` per state, confirm largest state shard ≤ 8 MB gzipped after default simplification. If not, tighten `simplification_tolerance_deg` for villages above other layers' default.
- **Acceptance gates**:
  - Ledger row count: ~28 states' worth of `level=village` partitions (3 dozen states minus the 8 missing). Each state-partition further sliced by district per the existing TN pattern (~600 districts nationally → ~600 shards).
  - Per-state coverage report: file a recon note in `notes/` for the 8 missing states (do they need bhuvan fall-back, or is "no village layer for state X" acceptable for now?).
  - Tier-B corpus conformance passes.
  - File-size budget: every shard ≤ 8 MB gzipped (the binding constraint here).
  - No frontend smoke required unless a village-aware consumer ships in the same PR.

### Delivered (2026-05-25, merged as #259 at `7308121a`)

- **Orchestrator**: [`tools/boundaries/lift_villages_national.py`](../tools/boundaries/lift_villages_national.py) — one-shot, ~370 lines. Pure-logic helpers (`group_features_by_state_and_district`, `sort_features_deterministically`) covered by 9/9 unit tests in [`backend/tests/test_lift_villages_national.py`](../backend/tests/test_lift_villages_national.py). Reuses the snapshot.py primitives (`fetch_geojsonl_7z`, `emit_feature_collection`, `_round_coords_geom`, `SNAPSHOT_BYTE_BUDGET`) so output byte format stays identical to the legacy TN entry. Reuses the `state_lgd_resolver` shipped in Phase B (no new state-mapping code).
- **Run output (cached `--skip-fetch`)**: 584,615 features parsed → 645 (state, district) buckets → 645 shards emitted across 27 states/UTs. 0 unkeyed features (every feature carries both `state_lgd` and `dist_lgd`); 0 unknown-state warnings; 0 oversize-skip (largest shard well below the 12 MB byte budget). Wall-clock ~10 min on the cached 1.8 GB extract; peak RSS ~11 GB during JSON parse (documented as acceptable on dev machines; if it becomes a constraint a two-pass streaming refactor is straightforward).
- **Per-state coverage** (27 emitted, sorted by ECI code):

  | ECI | State / UT | Districts | Villages |
  | --- | --- | ---: | ---: |
  | S01 | Andhra Pradesh | 26 | 15,443 |
  | S03 | Assam | 35 | 20,998 |
  | S04 | Bihar | 38 | 43,332 |
  | S05 | Goa | 2 | 385 |
  | S06 | Gujarat | 33 | 18,763 |
  | S07 | Haryana | 22 | 6,838 |
  | S10 | Karnataka | 31 | 30,416 |
  | S11 | Kerala | 14 | 1,623 |
  | S12 | Madhya Pradesh | 52 | 47,571 |
  | S13 | Maharashtra | 36 | 48,610 |
  | S18 | Odisha | 30 | 52,663 |
  | S19 | Punjab | 23 | 12,832 |
  | S20 | Rajasthan | 33 | 40,102 |
  | S22 | Tamil Nadu | 38 | 18,159 |
  | S23 | Tripura | 8 | 880 |
  | S24 | Uttar Pradesh | 75 | 101,729 |
  | S25 | West Bengal | 23 | 40,890 |
  | S26 | Chhattisgarh | 33 | 20,761 |
  | S27 | Jharkhand | 24 | 32,931 |
  | S28 | Uttarakhand | 13 | 17,501 |
  | S29 | Telangana | 33 | 10,738 |
  | U01 | Andaman and Nicobar Islands | 3 | 799 |
  | U02 | Chandigarh | 1 | 22 |
  | U03 | Dadra and Nagar Haveli and Daman and Diu | 3 | 90 |
  | U04 | Lakshadweep | 1 | 27 |
  | U05 | NCT of Delhi | 11 | 382 |
  | U07 | Puducherry | 4 | 130 |

- **Upstream coverage gap (9 states/UTs)**: S02 Arunachal Pradesh, S08 Himachal Pradesh, S14 Manipur, S15 Meghalaya, S16 Mizoram, S17 Nagaland, S21 Sikkim, U08 J&K, U09 Ladakh. One more than the plan's 8-state estimate — Ladakh (U09) had been counted within "J&K" in the plan; both are now confirmed separately gone (J&K became 3 entities post-2019: state J&K → UT J&K (U08) + UT Ladakh (U09), and the upstream ramSeraph LGD_Villages extract has neither). Documented in [`docs/reference/boundary-data-sources.md` §"Village gap"](../docs/reference/boundary-data-sources.md#village-gap--the-9-statesuts-missing-from-upstream-lgd_villages) (canonical home; promoted from `notes/` 2026-05-25). Bhuvan fall-back deferred until a citizen surface actually consumes village geometry for one of those states; the canonical reference records the pivot decision logic.
- **pipeline.json**: the legacy TN-only `kind=villages` entry (state-filtered to `state_lgd=33`, split-by `dist_lgd`, `emit_index=S22-villages-index.json`) is deleted in the same commit as the orchestrator + lift output. snapshot.py running for any other purpose will not regenerate the obsolete TN slice.
- **Pre-flight policy on shard sizes**: every emitted shard is well below the 12 MB SNAPSHOT_BYTE_BUDGET (largest is the TN district 593 file at ~2.7 MB raw / ~0.5 MB gzipped — same value carried forward from the legacy TN run). The `simplification_algorithm="coord-precision-round"` + `simplification_tolerance_deg=1e-4` (=4dp coord rounding, ~11 m) is identical to the legacy TN entry. No frontend consumer migration required (single per-district file pattern stays unchanged).

---

## Phase D — Survey-grade swap to ramSeraph BharatMaps lineage (states + AC + PC)

**Direction approved by user (2026-05-24)**: where ramSeraph publishes a survey-grade BharatMaps polygon for a layer we currently source from a non-survey-grade lineage (DataMeet, HTL, shijithpk), swap to ramSeraph. The gap-fill-not-bulk-swap policy ([`boundary-data-sources.md`](../docs/reference/boundary-data-sources.md#why-these-choices)) is **overridden** for this phase specifically because the upgrade is a citizen-visible quality lift (sub-meter survey vector vs hand-traced QGIS approximation) plus a code-system alignment (everything keyed by `lgd_code` post-swap). Pre-existing override of "no functional gain" framing logged here as the rationale anchor.

ramSeraph BharatMaps lineage applies to three layers we use today:
- `LGD_States` (Phase D.0) — replaces DataMeet `Admin2`.
- `LGD_Assembly_Constituencies` (Phase D.1–D.5) — replaces HTL per-state + shijithpk J&K.
- `LGD_Parliament_Constituencies` (Phase D.6) — replaces shijithpk 2024_maps_supplement.

Districts + sub-districts + villages are ALREADY on the ramSeraph LGD lineage (Phases B + C ingest them); no swap needed there.

### D.0 — State polygon swap (DataMeet → ramSeraph `LGD_States`)

- **What ships**: `INDIA_STATES.geojson_url` in [`frontend/src/lib/maps/sources.ts`](../frontend/src/lib/maps/sources.ts) repointed from the DataMeet `Admin2` file to a ramSeraph-derived `LGD_States.geojsonl.7z` shard converted to per-feature GeoJSON. `INDIA_STATES.join_property` changes from `ST_NM` to whatever the ramSeraph file carries (likely `state_lgd_code` or `STATE`; D.0 recon resolves it). New `lgdCodeToEci(lgdCode)` view-model helper in [`frontend/src/lib/view-models/states.ts`](../frontend/src/lib/view-models/states.ts) wraps the existing `taxonomy.entities` DuckDB-WASM query (the same Parquet that already powers `eciFromStateName`). The 3-entry `boundary_join_name` override map (Andaman & Nicobar, Delhi, J&K) re-validates against the new source's name strings — expect to drop most/all overrides because the LGD source uses canonical names.
- **Why this is technically trivial**: T.0e already retired the old `STATE_NAME_TO_ECI` constant in favour of a DuckDB-WASM lookup against `datasets/taxonomy/entities.parquet`, and that Parquet carries all three code systems (`legacy_id`=`S22`, `lgd_code`=`33`, `iso_3166_2`=`IN-TN`) on every state row. The swap is a property repoint + a new view-model helper, not a data migration.
- **Tooling**: add a `kind=state` entry to [`tools/boundaries/pipeline.json`](../tools/boundaries/pipeline.json) pointing at ramSeraph `LGD_States.geojsonl.7z` (released alongside `LGD_Districts`); run `tools/boundaries/snapshot.py --kind state` to emit `datasets/boundaries/in/state/IN-states.geojson` (single national file, ~120 KB gzipped).
- **Acceptance gates**:
  - File row count: 36 (28 states + 8 UTs) features in the emitted GeoJSON. Loud-fail any other number.
  - Every feature carries `lgd_code` resolvable to a row in `taxonomy.entities` via `lgdCodeToEci`. Vitest contract: `boundaries-conform.test.ts` extension asserts FK resolution for all 36.
  - **Per-shard size ceiling (HARD GATE)**: `states/all.geojson` ≤ 200 KB gzipped after Douglas-Peucker simplification at ~0.002° tolerance (per ["Boundary file-size policy"](#boundary-file-size-policy-jony--fowler-joint-2026-05-24) above). Survey-grade raw will likely be 5–10 MB pre-simplification — D-P is non-negotiable, not optional. Use `tools/boundaries/simplify.py` (Phase 0.4).
  - Existing `frontend/src/contracts/boundaries-conform.test.ts` still passes (schema unchanged; just data source change).
  - **§13 browser smoke (mandatory)**: open the national choropleth (e.g. `/`, `/t/elections`) on a state-keyed indicator, verify all 36 states/UTs render coloured, no console warnings about "unknown state", no white-tile gaps. Compare visually against pre-swap screenshot — expect pixel-level changes at coastlines + disputed borders (survey-grade vs DataMeet trace), but no missing or mis-coloured states.
  - Tier-B corpus conformance OK.
- **Independent of D.1–D.5**: state geometry has no dependency on AC consolidation; can ship as a standalone PR before or after the AC recon. **Depends on Phase 0.4** if the simplifier tool isn't already in tree.

### D.1 — First-snapshot recon (one-shot, gating)

- **What ships**: a recon note in `notes/` (NOT a code PR) recording:
  - The exact property schema of `LGD_Assembly_Constituencies.geojsonl.7z` features (does it carry `lgd_ac_code`? `AC_NO`? `state_code`? `ac_name`?). The catalogue page does not enumerate these; we need to look at the file.
  - The vintage anchor: does the file reflect Assam 2023 re-delim (still 126 ACs but new boundaries) and J&K 2022 re-delim (90 ACs)? Compare counts per state against `datasets/reference/in/states/S{nn}/constituencies.json`.
  - Per-state retained-feature count + total (should be ~4,123 ACs nationally pre-2026).
- **Tooling**: `tools/boundaries/snapshot.py --source constituencies --kind ac` lands the file into `.runtime/raw/ramseraph/constituencies/`; recon is then a manual jq/python inspection per [§2 path rule](../CLAUDE.md#2-path-rules-mandatory) (`.runtime/` is ephemeral; do not reference its paths from anything committed). The recon note may quote findings; it must not link to the raw file path.
- **Acceptance gate (the gating decision for D.2+)**: a yes/no per state. The note must answer: "For state S{nn}, does ramSeraph LGD AC count + names match the source-of-truth `constituencies.json`?" If yes → eligible for promotion in D.2+. If no → flag for individual investigation, keep current source (HTL or shijithpk).

### D.2 — Promote the obvious matches (28 states under 2008 delim)

- **Scope**: every state currently sourced from HTL where D.1 confirms LGD parity.
- **What ships**: replace the per-state HTL entry in [`pipeline.json`](../tools/boundaries/pipeline.json) with a ramSeraph entry sliced by state from the national LGD file; re-run snapshot; verify ledger row count is identical to today (still 1 file per state); citizen-visible map unchanged.
- **Mechanics**: ramSeraph publishes a single national file, but our ledger keeps the per-state-file granularity (cleaner for cache invalidation + per-state map loads). Use a `split_by=state` directive in `pipeline.json` (already supported per `tools/boundaries/snapshot.py`).
- **Acceptance gates per state**:
  - Per-state `AC_NO` (or `lgd_ac_code`) coverage 100% vs the SoT `constituencies.json` — `tools/boundaries/verify_ac_parity.py` (write this script) emits a coverage report.
  - Name-match coverage ≥ 95% (allow 5% Latin/diacritic noise); manual review of mismatches.
  - File-size budget passes.
  - §13 browser smoke on the affected state's election page: choropleth renders, no console errors, no 404s.

### D.3 — Assam (S03) — special case

- **Gate**: D.1 must answer whether LGD reflects 2023 Assam re-delim. Three outcomes:
  1. **LGD has 2023 delim** → swap S03 to ramSeraph (resolves the long-standing delimitation warning in `pipeline.json`).
  2. **LGD has pre-2023 delim** (same as HTL) → no swap value; keep HTL; the delimitation warning stays open.
  3. **Mixed / unclear** → file an open question for Hans + Max + Fowler; do not swap.

### D.4 — J&K (U08) — special case

- **Gate**: D.1 must answer whether LGD has the 90-AC 2022 re-delim layout (current shijithpk source has it). Three outcomes mirror D.3.
  - If LGD = 90 ACs with names matching `datasets/reference/in/states/U08/constituencies.json` → swap U08 from shijithpk to ramSeraph (cleaner license, stable LGD codes).
  - If LGD still has 87 (pre-statehood) ACs → keep shijithpk.

### D.5 — Wrap-up (AC consolidation)

- Update [`boundary-data-sources.md`](../docs/reference/boundary-data-sources.md) inventory table to reflect each promoted state's new producer.
- Update [`docs/architecture/decisions/0031-boundary-geometry-strategy.md`](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) with a 2026-Q3 (or whenever Phase D lands) amendment recording the consolidation outcome per state.
- Refresh `boundary_layers.parquet` ledger; `source_id` on every promoted row points at the ramSeraph `LGD_Assembly_Constituencies` row in `datasets/taxonomy/sources.parquet`.

### D.6 — PC polygon swap (shijithpk → ramSeraph `LGD_Parliament_Constituencies`)

- **What ships**: `pc` layer in [`pipeline.json`](../tools/boundaries/pipeline.json) repointed from `shijithpk/2024_maps_supplement` (Unlicense, GIS-traced in QGIS over the 2024 delim PDF) to ramSeraph `LGD_Parliament_Constituencies.geojsonl.7z` (CC0-1.0, BharatMaps survey-grade). Single national file, ~545 features expected (the 2024 delim count).
- **Recon gate (D.6 prerequisite)**: snapshot once; verify ramSeraph file reflects the 2024 General Election delimitation (post-Jammu UT + post-Telangana). If the LGD file is pre-2024 delim (still 543 PCs with pre-delim boundaries), DO NOT swap — keep shijithpk until LGD catches up.
- **Acceptance gates**:
  - PC feature count = 545 (±1 for J&K / Ladakh boundary edge cases — manually inspect).
  - Every feature carries `lgd_pc_code`; vitest FK-resolution test against `taxonomy.entities` (once PC entities seed lands as a separate dependency — this may push D.6 behind a Phase 0 sub-task).
  - **Per-shard size ceiling (HARD GATE)**: `pc/delim=2024/all.geojson` ≤ 500 KB gzipped after Douglas-Peucker simplification at ~0.001° tolerance (per ["Boundary file-size policy"](#boundary-file-size-policy-jony--fowler-joint-2026-05-24) above). Survey-grade raw will likely be 10–20 MB pre-simplification (vs today's 8.5 MB raw / 1.5 MB gzipped shijithpk file). If still > 500 KB after D-P, shard by state (`pc/delim=2024/state=<s>/all.geojson`) — that's a renderer change in [`frontend/src/lib/maps/sources.ts`](../frontend/src/lib/maps/sources.ts) + view-models, scope it in the same PR.
  - §13 browser smoke on any PC-keyed indicator surface (today: limited; revisit when a Lok Sabha cycle's tracker ships).
- **Independent of D.0–D.5**: can ship as a standalone PR; no AC consolidation dependency. **Depends on Phase 0.4** if the simplifier tool isn't already in tree.

---

## Phase E — Census-2011 polygon layer (DESCOPED, narrowed to district+subdistrict cross-check)

**Decision (user, 2026-05-24)**: descope Census-2011 villages. The `Census_Villages` release is **points, not polygons** — we are a choropleth-first site and points don't render as administrative shapes. Don't adopt.

**What remains useful**: `Districts_2011` + `SubDistricts_2011` polygons exist as a **cross-check oracle** for Phase B (sub-district national lift). They are CC0-1.0 and frozen at Census-2011 vintage — useful to catch any major boundary drift between LGD/BharatMaps (Phase B source) and the canonical Census reference.

- **If/when first Census-2011 indicator ships** (deferred trigger): adopt `Districts_2011.geojsonl.7z` + `SubDistricts_2011.geojsonl.7z` ONLY (the two polygon files, CC0-1.0). Store under `datasets/boundaries/in/<level>/vintage=2011/` (Hive partition extension) — vintage is a property, not a sibling kind. **No `Census_Villages` ingest.**
- **PC11_TV_DIR.csv.7z** (Census-2011 town + village name directory): catalogue only; useful for entity-name cross-referencing if/when a 2011-vintage indicator wants to disambiguate village names against modern LGD names.
- **SHRUG variants** (`shrug-district-pc11`, `shrug-subdistrict-pc11`, `shrug-village-pc11`) are **CC-BY-NC-SA 4.0 — NON-COMMERCIAL**, NOT safe for redistribution from our static bundle. **Do not adopt under any conditions.**
- **No tooling work until trigger fires.** The cross-check use in Phase B (verifying LGD subdistrict counts against Census-2011) happens at-need with a one-off recon script, not as a permanent shard on disk.

---

## Cross-cutting validation (every phase)

Every phase PR must pass:

1. **Tier-A schema sanity** (`pytest -q` in `backend/`): all schema invariants hold.
2. **Tier-B corpus conformance** (`python -m yen_gov validate --root .`): no Tier-B regressions.
3. **`backend/tests/`** loader tests for new data shapes (real fixtures per Holy Law #7 — no mocks except fetch boundary).
4. **`frontend/src/contracts/boundaries-conform.test.ts`** passes — the runtime ajv gate for what the frontend will fetch.
5. **`bun run test`** in `frontend/` is green at commit time (no "I'll add tests later").
6. **§13 browser smoke** when a UI surface changes; skip when phase is pure backend/data.
7. **No new mocks** unless user-requested.
8. **Lockfile sync** (Holy Law #9 + DoD): not applicable here since no `package.json` edits are anticipated. If a phase adds a new frontend dependency (unlikely), include the bun.lock regen.
9. **Provenance**: every new ledger row in `boundary_layers.parquet` carries a `source_id` FK to `datasets/taxonomy/sources.parquet`. Every new sources row uses the v2.0 citation-ledger shape ([ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md)).

---

## Open questions (TBD; promote into the relevant doc on resolution)

- **Phase A.1 output path**: `datasets/reference/in/pincodes/pincode-directory.csv` (proposed default — "reference data, not an indicator") vs `datasets/taxonomy/pincodes/...` (sibling to `taxonomy/entities.parquet`, treats pincode as a first-class taxonomy alongside states/districts/ACs) vs `datasets/postal/pincode_directory.parquet` (treats `postal` as its own family alongside `elections/`, `energy/`, `demography/`). Gregor + Max decision required — affects loader path, validator scope, and how Phase A.2 polygons cross-reference the directory. Recommend `datasets/reference/in/pincodes/` as the lowest-coupling default until Phase A.2 ships and a polygon×directory join is needed.
- **Phase A.1 license enum**: GODL-IN / `OGL-IN-1.0` is not in the current `sources.parquet` license enum (§12 lists `OGL-IN-1.0` — verify these are the same string). If not, either rename or extend the enum in the same PR.
- **Phase A.2 source choice**: PostalGIS (gap-having, CC0) vs data.gov.in (gap-free, GODL). Decision lands after first-snapshot recon comparing actual citizen-visible quality.
- **Phase C upstream gap**: HP / J&K / Sikkim / ML / MZ / MN / NL / AR are not in `LGD_Villages`. Acceptable as "no village layer for state X today", or pull `bhuvan_villages` as fall-back? Defer to first concrete consumer.
- **Phase D first-snapshot recon outcome**: whether `LGD_Assembly_Constituencies` carries 2023 Assam delim + 2022 J&K delim. Cannot answer without running the snapshot.
- **Phase D parity threshold**: name-match coverage ≥ 95% is a placeholder; the actual threshold lands after the first state's recon report shows what diacritic noise the LGD file carries.
- **Phase E trigger**: which Census-2011 indicator ships first? Out of scope of this plan to predict; the trigger is "first Census-derived choropleth consumer surface".

---

## Handover prompt for next coding agent (copy-paste-ready)

**Last updated**: 2026-05-25 (after Phase D.0 — state polygon swap DataMeet → ramSeraph `LGD_States`).

This is a multi-agent codebase. The block below is the literal prompt to drop into the next coding agent's first message so it can pick up the sprint without human input. Keep it in sync with the Phase 0.0 status table above (single source of truth for what is merged).

> # yen-gov boundary expansion sprint — agent handover
>
> ## What this sprint is (one paragraph)
>
> yen-gov is a static GitHub Pages site for Indian socio-economic + election data. There is no production backend. This sprint adds administrative-boundary geometry (polygons) at every level — country → state → district → subdistrict → AC → PC → village → pincode — so citizen-facing choropleths can render correctly. The full plan lives at [`TODO/20260524-boundary-coverage-expansion-plan.md`](../TODO/20260524-boundary-coverage-expansion-plan.md). **Read its Phase 0.0 status table first** — it is the source of truth for what is merged and what is next.
>
> ## What is DONE (do NOT re-do)
>
> | Phase | What shipped | PR | SHA |
> |---|---|---|---|
> | 0.1 | LGD state-code seed | #235 | `18b8a69c` |
> | 0.4 | Boundary file simplifier (`tools/boundaries/simplify.py`) | #244 | `a0f34911` |
> | A.1.a | Pincode CSV parser + ResourceMeta plumbing | #247 | `f46b02ca` |
> | A.1.b | Pincode CSV emit + sources row | _earlier_ | _see plan-doc_ |
> | A.2 | Pincode polygons (national) | #254 | `39932f09` |
> | B | Subdistrict national lift (TN-only → 36 states/UTs) | #257 | `011a9764` |
> | C | Village national lift (TN-only → 27 states/UTs, 645 per-district shards) | #259 | `7308121a` |
> | C-doc | Plan-doc reconcile (close Phase C row) | #260 | `f2da01ef` |
> | D.0 | State polygon swap (DataMeet → ramSeraph `LGD_States`, LGD-int join) | #263 | `b2742582` |
>
> ## What is NEXT (in dependency order — one PR at a time)
>
> Two independent tracks can run in parallel — a single agent picks one; a second agent may pick the other without contention.
>
> **Track 1 — Phase D (boundary geometry upgrades + AC consolidation)**:
>
> 1. **Phase D.1** — AC consolidation snapshot recon (one-shot recon note in `notes/`, NOT a code PR). Gates D.2–D.5.
> 2. **Phase D.2** — Promote ~28 states from HTL to ramSeraph LGD (after D.1 confirms parity per state).
> 3. **Phase D.3** — Assam special-case (after D.1 confirms 2023 re-delim status).
> 4. **Phase D.4** — J&K special-case (after D.1 confirms 90-AC layout).
> 5. **Phase D.5** — AC consolidation wrap-up (docs + ledger + ADR amend).
> 6. **Phase D.6** — PC polygon swap (shijithpk → ramSeraph). Independent of D.0–D.5; can ship before or after.
>
> **Follow-up debt (separate small PR, NOT part of Track 1 or 2)**:
>
> - **Village/national budget-ceiling bump** — `frontend/src/lib/boundaries.budget.test.ts` + `frontend/src/contracts/boundaries-conform.test.ts` Phase 0.4 carry 487 PRE-EXISTING failures since PR #257 (subdistrict national lift, chunks 110 → 462) and PR #259 (village national lift, chunks 462 → 753 + village shard sizes exceeding `VILLAGE_SHARD_MAX_BYTES=4MB` and `LAYER_GZIP_CEILING_KB=500`). Bump ceilings to match current corpus reality (or split largest shards). Single-file scope; full-suite vitest goes green; CI on `main` recovers.
>
> **Track 2 — Phase 0.2 (district entity backfill, parallel to Track 1)**:
>
> - **Phase 0.2** — District backfill (639 rows → `entities.json`). Hand-curated extension; LGD master CSV + Census-2011 columns already on the CSV + entities.json conventions. Tooling: `tools/lgd/backfill_entities_districts.py` (NEW, ~50 lines generator). Unblocks every district-keyed citizen choropleth outside the 6 ECI-mapped states (financial-inclusion density, rainfall/water, topography, JJM/PMAY coverage). User direction 2026-05-25: hand-curation is acceptable; do not shy away from it. Per-phase rationale + acceptance gates in [§0.2 above](#02--district-backfill-639-rows--entitiesjson). Coverage status (live, what we have / don't have): [`docs/reference/boundary-data-sources.md` §"Coverage status"](../docs/reference/boundary-data-sources.md#coverage-status--what-we-have-what-we-dont-have).
>
> ## What is DEFERRED (do NOT start)
>
> - **Phase E** — Census-2011 polygons. User-mandated descope on 2026-05-24 because `Census_Villages` is points-not-polygons (we are a choropleth-first site). The Phase B cross-check use is at-need, not a permanent shard. **Do not start any Phase E work without an explicit unblock.**
>
> ## Known runtime issue (do NOT try to fix)
>
> **DuckDB on Python 3.14 + Windows segfaults inside three specific tests.** This is a runtime fragility, not a test-code bug. ALWAYS run backend pytest with the standing deselect line. **Full doctrine + reversal triggers + escalation path live in [`docs/architecture/testing.md` §"Runtime fragility"](../docs/architecture/testing.md#runtime-fragility--known-issues-do-not-fix-the-tests)** — read that section once and stop re-litigating. Standing deselect line:
>
> ```powershell
> pytest -q --deselect=backend/tests/test_canonical_writer.py::test_empty_dim_lists_do_not_touch_existing_dim_files --deselect=backend/tests/test_topics_seed.py::test_compile_accepts_topic_without_artifacts --deselect=backend/tests/test_canonical_writer_partition.py::test_pre_existing_monolith_swept_after_partitioned_emit
> ```
>
> Expected: **998 passed / 44 skipped / 3 deselected** (baseline as of 2026-05-25). Do NOT edit any of the three tests. Do NOT block a PR on them. Track upstream DuckDB / Python 3.14 fixes for the runtime, not the tests.
>
> ## Discipline (mandatory; multi-agent codebase)
>
> 1. **Read [`CLAUDE.md`](../CLAUDE.md) front-to-back** before any code change. Holy laws #1–#10 and §15 test policy are non-negotiable.
> 2. **Use a worker worktree** for substantive code work — never edit on master worktree while another agent is using it. Create with: `git worktree add ../yen-gov-d0-state-swap origin/main -b feat/state-polygon-swap-ramseraph`.
> 3. **Every PowerShell command in worker MUST be wrapped**: `Push-Location <worker-abs>; $env:PYTHONPATH=(Resolve-Path backend).Path; <cmd>; Pop-Location`. This pins which checkout's code runs (`python -m yen_gov` otherwise imports from the master editable install).
> 4. **Never touch parallel-agent worktrees**. `git worktree list` shows who's where. Stay in your own worker. Master worktree may have dirty parallel-agent files — leave them alone; stage only YOUR files when committing.
> 5. **Use sub-agents for task execution** — when you need codebase exploration, hand it to the `Explore` sub-agent (read-only, safe to call in parallel). When you need a persona viewpoint, hand it to that persona (`Fowler` for engineering craft, `Jony` for UI/UX, `Hans` for governance framing, `Max` for indicator-scout decisions, `Gregor` for architecture/contracts, `Citizen` for citizen-experience sanity check, `Andre` for any LLM/AI/SLM topic).
> 6. **Work autonomously** — the user is not available to respond. Do NOT wait for human input. Make good decisions per the plan-doc; document deviations in the commit body or a `notes/` file.
> 7. **Update the Phase 0.0 status table IN THE SAME COMMIT** as the code work — never a separate docs-only PR. The one carve-out: a self-PR-number race forces a one-line follow-up PR (the #260 pattern). Keep it to one file, one row.
> 8. **§13 browser smoke** is MANDATORY for any change touching `frontend/` or `admin/` runtime behaviour. Phase D.0 touches `frontend/src/lib/maps/sources.ts` — §13 applies. Phase D.1 is pure recon (no UI) — §13 not applicable.
> 9. **`gh pr merge --squash --delete-branch --auto`** from a worker is clean when master is on a feature branch; may print a cosmetic local-cleanup error when master is on `main`. Either way the server-side merge succeeds — verify with `gh pr view <#> --json state,mergedAt,mergeCommit`.
> 10. **Never use** `git stash`, `git reset --hard`, `git clean -fd`, `git checkout .`, `git add .`, `git push --force`, or amend pushed commits. See CLAUDE.md §8.
>
> ## Where to look up anything
>
> - **Project contract**: [`CLAUDE.md`](../CLAUDE.md) — Holy laws, schema versioning, provenance, test tiers, anti-patterns.
> - **Boundary subsystem doc**: [`docs/architecture/data/boundaries.md`](../docs/architecture/data/boundaries.md) — disk layout, identifier discipline, methodology-break rules, **coverage gaps pointer**.
> - **Boundary source catalogue + live coverage ledger**: [`docs/reference/boundary-data-sources.md`](../docs/reference/boundary-data-sources.md) — every upstream provider + license + selection policy + **what-we-have-what-we-dont-have ledger** (canonical home; supersedes any `notes/` files on the same subject).
> - **Decision history**: [`docs/architecture/decisions/0031-boundary-geometry-strategy.md`](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) (amended 2026-05-24 for PC layer + delim partition).
> - **§12 provenance contract**: [`docs/architecture/decisions/0032-sources-citation-ledger.md`](../docs/architecture/decisions/0032-sources-citation-ledger.md) — every new sources row uses v2.0 shape.
> - **Test policy + runtime fragility**: [`docs/architecture/testing.md`](../docs/architecture/testing.md) — four-tier matrix + canonical DuckDB-flake doctrine + reversal triggers.
> - **Repo memory**: `/memories/repo/yen-gov-architecture.md` — derived cheat-sheet (canonical docs win when they disagree).
> - **Session memory**: `/memories/session/boundary-coverage-sprint-resume.md` — sprint-scoped status (Phase D.0 kickoff kit superseded; D.0 merged via PR #263).
>
> ## Your first three commands (literally)
>
> ```powershell
> # 1. Read the plan-doc status table + the next-phase spec (pick a track first)
> Get-Content TODO\20260524-boundary-coverage-expansion-plan.md -TotalCount 60
> # Track 1: Phase D.1 (AC consolidation recon, gating)
> Select-String -Path TODO\20260524-boundary-coverage-expansion-plan.md -Pattern "^### D\.1" -Context 0, 40
> # Track 2: Phase 0.2 (district entity backfill, parallel to Track 1)
> Select-String -Path TODO\20260524-boundary-coverage-expansion-plan.md -Pattern "^### 0\.2" -Context 0, 40
>
> # 2. Read the session memory sprint resume
> # (use the memory tool: command=view, path=/memories/session/boundary-coverage-sprint-resume.md)
>
> # 3. Create your worker worktree (name = phase you're picking)
> git worktree add ..\yen-gov-d1-ac-recon origin/main -b feat/ac-consolidation-recon  # Track 1 example
> # OR
> git worktree add ..\yen-gov-0-2-districts origin/main -b feat/district-entity-backfill  # Track 2 example
> ```
>
> Then proceed per the phase spec. Work autonomously. Ship the PR. Update the Phase 0.0 status table in the same commit. Open the next agent's handover trail by editing this section's "Last updated" date + table when your phase lands.

---

## Not in this plan (descoped)

- **GADM as a source**: hard NO. Disputed-territory polygons (5 of 41 features carry China/Pakistan-claimed slice IDs), non-commercial license blocking static-bundle redistribution, uses HASC codes not LGD/ECI, and is stale (no Ladakh split). Documented in [`boundary-data-sources.md` §"Why not GADM"](../docs/reference/boundary-data-sources.md) — do not re-litigate.
- **Bulk swap of all 28 HTL states onto ramSeraph in one PR**: violates the gap-fill-not-bulk-swap policy. Phase D.2 promotes only those states where the parity-check authorises it; the rest stay on HTL until they need refresh.
- **DIGIPIN (4 m × 4 m grid)**: not a polygon family; needs a separate point/grid handler. Not on the boundary-coverage roadmap.
- **Topographic raster basemaps** (`ramSeraph/india_topo_maps`): out of scope for the choropleth-rendering frontend per [`boundary-data-sources.md`](../docs/reference/boundary-data-sources.md).
- **Historical district decadal series** (`ramSeraph/indian_admin_boundaries#historical`): high-value catalogue (1941 → 2001 polygons + `District_Timeseries_1951-2024.csv` change-log + name-change / split / carve-out CSVs). Adopt when a methodology-break-aware trend visualisation ships per [`boundaries.md` §"Methodology breaks"](../docs/architecture/data/boundaries.md#methodology-breaks). Out of scope for this plan.
