# Tamil Nadu Granular Geography — Plan

**Created**: 2026-05-15
**Authors**: Hans (Governance), Fowler (Engineering), Jony (UI/UX)
**Sign-off target**: ≥95% confidence from each on their segment before code lands.
**Authority to execute**: granted by user 2026-05-15 — plan does not pause for further approval; proceed phase-by-phase once sign-offs land. Escalate only per §Escalation.

## Plan version log

- **v1** (initial draft) — generic plan.
- **v2** — Hans signed off at 96 % after LGD-as-registry / Census-as-geometry split, pincode segregation, sidecar denominator, simplification metadata, methodology break markers.
- **v3** — Fowler 78→96 (per-district village split, Tidy First Phase 1a/1b, missing test tiers, YAGNI deferral); Jony 78→96 (lazy fetch + skeleton, breadcrumb glyph, dropped Lakshadweep connector, pincode→district fallback, `scale_hint` bucketing, missing states, methodology demotion).
- **v3.1** — final non-blocker nits (chunk-count pinned to 80, LGD-license merge-gate, greyed-crumb names lowest valid grain, "no data" labelled with unit).
- **v4 — ADAPTED TO EXISTING TOPOLOGY 2026-05-15**. Mid-execution discovery: yen-gov already has substantial LGD + boundary infra (`tools/lgd/snapshot.py` fetching ramSeraph mirror, `datasets/boundaries/in/geojson/india-districts.geojson` with `dist_lgd` features, `datasets/boundaries/in/geojson/S<NN>-ac.geojson` per-state assembly-constituency boundaries, `datasets/reference/in/lgd/` CSVs, `district.schema.json` v3.2 with `lgd_code`+`created_on`+`split_from`, `boundary.sources.schema.json` + `feature_collection.metadata.schema.json` sidecar pattern, ADR-0019 already names `subdistrict_lgd_code`/`village_lgd_code` as future canonical columns). v4 reshapes the plan to **extend** these contracts, not invent parallel ones. Hans + Jony scope unaffected (sources are the same ramSeraph upstream Hans already approved; UX layer unaffected). Fowler scope re-scored after v4 below.
- **v5 — PIPELINE TOPOLOGY ALSO ALIGNED 2026-05-15** (Phase 0 complete; pause before Phase 1b). Second mid-execution discovery: `tools/boundaries/snapshot.py` + `tools/boundaries/pipeline.json` is the **existing canonical boundary pipeline**, with format dispatch (`geojson`, `shp_bundle`, `geojsonl_7z`), an already-wired `LGD_Districts.geojsonl.7z` entry pulling from `ramSeraph/indian_admin_boundaries`, `coord_precision`-based budget control, and license/name/id-property metadata structured per-entry. Building `backend/yen_gov/pipelines/boundaries_tn/{fetch,normalize,emit}.py` would duplicate ~80% of `tools/boundaries/snapshot.py` and fork the boundary-pipeline topology into a TN-specific island. v5 retires the proposed `backend/yen_gov/pipelines/boundaries_tn/` and instead **extends `tools/boundaries/pipeline.json` + `tools/boundaries/snapshot.py`** as a Strangler Fig: append `LGD_Subdistricts.geojsonl.7z` + per-district-sliced `LGD_Villages.geojsonl.7z` entries to `pipeline.json`; teach `snapshot.py` (a) a `state_filter` block for sub-national slicing, (b) a `split_by` block for the per-district village emission pattern, and (c) `boundary.unkeyed.json` sidecar emission when LGD-join drops features. Phase 0 (schemas + ADR + boundaries doc) is unaffected — schemas + identifier discipline are universal. Phase 2/3/4 unaffected. Fowler re-poll required on Phase 1b only before resuming execution.

## Problem in one paragraph

yen-gov today renders India as country + 36 states/UTs. Tamil Nadu is the May-2026 launch state and the citizen mental model goes deeper: **State → District → Sub-district (taluk) → Block → Village**, plus pincode for postal lookup. We have no taluk/village polygons on disk, no LGD code registry, no drill-in interaction, and the country outline we ship is a generic GADM-style polyline rather than the **Survey of India** outline (which is the politically-correct boundary for an Indian-government-facing app and the one ECI/MoSPI use). Lakshadweep is also currently absent or sub-pixel at national zoom. This plan acquires the data, stores it under the existing `datasets/` contract surface with stable LGD identifiers, and surfaces a drill-down on the TN map without inventing any per-layer bespoke UI.

## Sources (locked from 2026-05-15 research; refined v4 to existing topology)

**Two distinct things to acquire**: (a) **LGD = registry** — codes + hierarchy, no geometry; (b) **LGD-keyed geometry** — polygons each feature carries the same LGD code as the registry, so the join is one column. yen-gov already standardised on **ramSeraph's mirrors** (CC-BY-4.0) for both — `tools/lgd/snapshot.py` pulls the LGD CSVs from `ramSeraph/opendata` and the existing `india-districts.geojson` was pulled from `ramSeraph/indian_admin_boundaries`. v4 extends this pattern to subdistricts and villages — same upstream owner, same release cadence, same `dist_lgd` / future `subdist_lgd` / `village_lgd` property convention. yashveeeeeeer/india-geodata stays as cross-check + the SoI silhouette, but is no longer the primary spine.

| Layer | Primary source (geometry) | Identifier source | Existing on disk? | Verdict |
| --- | --- | --- | --- | --- |
| India outline (silhouette) | [yashveeeeeeer/india-geodata `india-soi.geojson`](https://github.com/yashveeeeeeer/india-geodata/blob/main/data/administrative/country/india-soi.geojson) | n/a | NO — to add as `datasets/boundaries/in/geojson/india-soi.geojson` | USE — silhouette only. **License note (Fowler v4 nit 3)**: yashveeeeeeer SoI is a separate upstream from ramSeraph; Phase 1b fetcher MUST confirm its license (repo states CC-BY-4.0 derivative of SoI under National Geospatial Policy 2022) and write a dedicated `india-soi.geojson.sources.json` sidecar — does NOT inherit the ramSeraph license blanket. |
| States | existing `datasets/boundaries/in/geojson/india-states.geojson` (LGD-keyed) | `state_lgd` property | YES | keep |
| Districts | existing `datasets/boundaries/in/geojson/india-districts.geojson` from `ramSeraph/indian_admin_boundaries/releases/download/districts/LGD_Districts.geojsonl.7z` | `dist_lgd` property | YES | keep; refresh via `tools/lgd/snapshot.py` extension |
| TN sub-districts (taluks) | `ramSeraph/indian_admin_boundaries` `subdistricts` release (LGD-keyed) — confirm asset name during Phase 1b probe | `subdist_lgd` property | NO — to add as `datasets/boundaries/in/geojson/S22-subdistricts.geojson` | USE; sliced to TN at write time |
| TN villages | `ramSeraph/indian_admin_boundaries` `villages` release (LGD-keyed) — confirm asset name during Phase 1b probe | `village_lgd` property | NO — to add as per-district files `datasets/boundaries/in/geojson/S22-villages-<district_lgd>.geojson` (~38 files) | USE; per-district split (Fowler v3 §a) |
| LGD registry CSVs | `ramSeraph/opendata` `lgd-latest-extra1` release (already used for States, Districts) | — | YES for States+Districts; NO for Subdistricts+Villages | extend `tools/lgd/snapshot.py` to fetch Subdistricts (and Villages if available) |
| Chennai pincode polygons | [datameet/PincodeBoundary](https://github.com/datameet/PincodeBoundary) | `pincode` property | NO | MAYBE — see segregation below; deferred to Phase 4 (Fowler v3 YAGNI) |

**Pincode segregation rule (Hans-flagged)**: pincodes are **postal delivery zones**, NOT administrative units. They cross block/village/taluk lines. They MUST live under a separate tree `datasets/boundaries/in/postal/` (NOT in `geojson/` with the LGD-keyed administrative layers), MUST NOT carry an LGD-coded property, and the UI MUST render them on a different visual layer with explicit "postal zone, not administrative" labelling. Mixing them with administrative layers is a citizen-trust killer.

**Non-sources**: lgdirectory.gov.in NAPIX API (registration friction not justified for a static pipeline; ramSeraph mirror already covers it); raw Census 2011 shapefiles direct from ORGI (legally grey to redistribute — ramSeraph's already-published derivatives provide upstream-cited lineage).

## Lakshadweep / A&N convention (decision)

Render at **true geographic position** — matches ECI, MoSPI, datameet convention; Indian readers expect geographic truth. No US-Alaska-style displaced inset. Add an **optional zoom-on-hover callout for Lakshadweep** at national scale where it goes sub-pixel (<~600px wide). Andaman & Nicobar already large enough at national zoom. Decision rationale lands in `docs/architecture/frontend/maps.md` in the same commit as the code.

## Naming nit (resolved)

`datasets/indicators/in/` uses `in` = ISO 3166-1 alpha-2 for India, lowercased per project convention. **No rename.** Documented in this plan; no action.

---

## Sequencing (Tidy First / Beck)

Each phase is one or more commits, structural-OR-behavioural per commit, tests in the same commit (CLAUDE.md §15). Phases 0–2 are data-layer (Hans + Fowler own); Phase 3 is GUI (Jony owns); Phase 4 is polish.

---

## Phase 0 — Boundaries contract surface (Correction Level 3, Hans + Fowler + Gregor)

**Goal**: define WHERE TN granular boundaries live on disk, under what schema, before any bytes are downloaded. Contracts before logic (Holy Law #3).

- [ ] **Disk layout — extends existing `datasets/boundaries/in/geojson/` tree** (NOT a new `tn/` subtree — preserves symmetry with existing `india-states.geojson` / `india-districts.geojson` / `S<NN>-ac.geojson`):
  - `datasets/boundaries/in/geojson/india-soi.geojson` (NEW; SoI silhouette).
  - `datasets/boundaries/in/geojson/S22-subdistricts.geojson` (TN taluks; LGD-keyed via `subdist_lgd` property).
  - `datasets/boundaries/in/geojson/S22-villages-<district_lgd>.geojson` — **per-district split** (~38 files for TN; one per district; Fowler v3 §a — kills the `import.meta.glob` bundle bomb).
  - `datasets/boundaries/in/postal/IN-pincodes-chennai.geojson` — **separate `postal/` subtree**, postal not administrative (Hans rule). Deferred to Phase 4 with consumer (Fowler v3 YAGNI).
  - Each `.geojson` ships with the existing `<file>.geojson.sources.json` sidecar (`boundary.sources.schema.json` v1.0).
- [ ] **`datasets/schemas/subdistrict.schema.json`** v1.0 — NEW per-state subdistrict registry, analogous to existing `district.schema.json` v3.2. Per-state file path: `datasets/reference/in/states/<S>/subdistricts.json`. Per-item: `id`, `id_source` enum `lgd|wikipedia`, `lgd_code` (LGD numeric subdistrict code), `name`, `name_alt?` (Hans v2 — Thoothukudi/Tuticorin), `name_source` enum `lgd|census_2011`, `district_id` (parent district id), `created_on?`, `split_from?`, `notes?`. Top-level: `$schema`, `$schema_version`, `sources`, `state` (`^[SU]\d{2}$`), `subdistricts`. Conditional rule: `lgd_code` required when `id_source=lgd`.
- [ ] **`datasets/schemas/district.schema.json` v3.3** (additive minor bump from v3.2) — adds optional `name_alt`, `name_source` enum `lgd|census_2011`, `census_2011_code?`, `lgd_code_history?: [{old, retired_on}]`, `created_after_2011?: {date, parent_lgd_codes: [strings], notes}` (Hans v2 — multiple parents possible, e.g. Chengalpattu carved from Kancheepuram + others). Existing TN data files re-validate (purely additive). Required `x-changelog` entry added in same commit.
- [ ] **Reuse `feature_collection.metadata.schema.json` v1.1** (additive bump from existing v1.0) — for the new boundary GeoJSONs that need richer metadata than the bare `boundary.sources.schema.json` sidecar carries (license + coverage + CRS + simplification). v1.1 adds optional file-level `simplification` object: `{tolerance_deg, algorithm, original_feature_count, retained_feature_count}` (Hans v2 — without this, downstream area/length math silently lies). v1.1 changelog entry in same commit.
- [ ] **`datasets/schemas/boundary.unkeyed.schema.json`** v1.0 (NEW; Hans v2 sidecar) — defines `<file>.geojson.unkeyed.json` shape: `{$schema, $schema_version, for, dropped: [{source_feature_name, reason, dropped_at}], totals: {original, retained, dropped}}`. Surfaces a denominator (Hans v2 — defuses Negativity instinct: "47 of 12,524 villages (0.4%) lack an LGD join").
- [ ] **ADR-0019 amendment** — promote `subdistrict_lgd_code` (`INTEGER`) and `village_lgd_code` (`INTEGER`) from "future additions" (already pre-listed in ADR-0019 §3 last sentence) to first-class canonical column rows on first emitter need.
- [ ] **`docs/architecture/data/boundaries.md`** — NEW doc, ships in same commit as the new schemas. Documents: tree layout (extension of existing `geojson/` tree, NOT a parallel `tn/` tree), postal-vs-administrative segregation rationale, LGD-as-registry vs LGD-keyed-geometry split, why ramSeraph is the chosen upstream (CC-BY-4.0, LGD-coded, already wired via `tools/lgd/snapshot.py`), why we do NOT use names as IDs, file-size budget (≤8 MB gzipped per file), simplification metadata rationale, post-2011 district-split methodology break treatment via `created_after_2011`, sidecar-pattern rationale, Lakshadweep callout decision link to `frontend/maps.md`.
- [ ] **LGD redistribution license — RESOLVED in v4**: `tools/lgd/snapshot.py` already redistributes `states-latest.csv` + `districts-latest.csv` from the ramSeraph mirror under CC-BY-4.0; the same release covers Subdistricts (and likely Villages). License is permissive, redistribution is fine, attribution sidecar already lands via `csv.sources.schema.json`. No merge-gate needed (Fowler v3 nit retired).
- [ ] **Tier-A + Tier-B contract tests**: schemas validate against meta-schema; existing data files re-validate under v3.3 of district schema (purely additive). No new data files in Phase 0; those land in Phase 1b.

**Gregor consult required** before this phase if boundary contract shape is contested.

---

## Phase 1a — Validator wires the schemas (Correction Level 2, structural-only, Fowler)

Tidy First split. Pure structural commits (one per schema): register `subdistrict.schema.json` v1.0, bump `district.schema.json` to v3.3, bump `feature_collection.metadata.schema.json` to v1.1, register `boundary.unkeyed.schema.json` v1.0 in the validator. ADR-0019 amendment commit promoting `subdistrict_lgd_code` and `village_lgd_code` to first-class canonical-column rows. No emitters, no data files. Tier-A passes (schemas validate against meta-schema); Tier-B re-validates existing data (purely additive — existing `districts.json` files re-validate under v3.3 unchanged).

## Phase 1b — Boundary ingestion pipeline (Correction Level 3, behavioural, Fowler)

**Goal (v5)**: extend the **existing canonical boundary pipeline** at `tools/boundaries/{pipeline.json,snapshot.py,build.py}` to fetch + emit TN subdistrict and village layers from `ramSeraph/indian_admin_boundaries`. Strangler Fig over the existing `LGD_Districts.geojsonl.7z` entry (same upstream, same `geojsonl_7z` format, same `coord_precision`-based budget control). Also extend `tools/lgd/snapshot.py` (LGD CSV fetcher) to pull the matching Subdistricts (and Villages if present) registries from `ramSeraph/opendata`. NO new `backend/yen_gov/pipelines/boundaries_tn/` — that proposal in v3/v4 forked the boundary-pipeline topology and is retired. NO frontend touched.

- [x] **Extend `tools/lgd/snapshot.py`** — DONE in v4 (REQUIRED_COMPONENTS = States/Districts/Subdistricts; OPTIONAL_COMPONENTS = Villages, probed per-token, skipped on 404). Emits `subdistricts-latest.csv` + sidecar (and `villages-latest.csv` + sidecar when present) under `datasets/reference/in/lgd/`.
- [ ] **Extend `tools/boundaries/pipeline.json`** — append two new `inputs` entries, additive (existing entries untouched):
  - `kind: "subdistricts"`, `country: "IN"`, `state: "S22"`, `out: "geojson/S22-subdistricts.geojson"`. `source.format: "geojsonl_7z"` (existing handler), `source.urls: ["https://github.com/ramSeraph/indian_admin_boundaries/releases/download/subdistricts/LGD_Subdistricts.geojsonl.7z"]`, `source.coord_precision: 3`, `source.state_filter: {property: "state_lgd", equals: 33}` (NEW block — see snapshot.py extension below). `id_property: "subdist_lgd"`, `name_property: "sdtname"` (confirm via first snapshot). License = CC0-1.0 (same blanket as `LGD_Districts`). No `tippecanoe` block — this layer ships as static GeoJSON consumed by `import.meta.glob` (Phase 2 loader); PMTiles conversion can be added later if a vector-tile consumer materialises (YAGNI).
  - `kind: "villages"`, `country: "IN"`, `state: "S22"`, `out: "geojson/S22-villages-{dist_lgd}.geojson"` (NEW templated `out` — see `split_by` block). `source.format: "geojsonl_7z"`, `source.urls: ["https://github.com/ramSeraph/indian_admin_boundaries/releases/download/villages/LGD_Villages.geojsonl.7z"]`, `source.coord_precision: 4` (villages are smaller; precision=3 ~110 m would over-simplify), `source.state_filter: {property: "state_lgd", equals: 33}`, `source.split_by: {property: "dist_lgd", emit_index: "geojson/S22-villages-index.json", index_schema: "boundary.villages_index.schema.json"}` (NEW block — emits one file per district + an index manifest). `id_property: "village_lgd"`, `name_property: "vlgname"` (confirm). License = CC0-1.0.
- [ ] **Extend `tools/boundaries/snapshot.py`** — three additive capabilities, each behind its own opt-in source block (existing entries unaffected):
  - **`source.state_filter`**: after format dispatch produces the FeatureCollection, drop any feature whose `properties[<property>] != <equals>` (or `not in <one_of>`). Counts both sides for the unkeyed-sidecar denominator.
  - **`source.split_by`**: when present, instead of writing a single `out` file, group features by `properties[<property>]` (skip features missing the property — they go to the unkeyed sidecar with `reason: "no_lgd_code_in_source"`), and write one file per group at the templated `out` path (`{dist_lgd}` token substitution). Also write the `emit_index` manifest (`{state_lgd, district_lgd_codes: [unique sorted ints], generated_at}`) validated against the schema named in `index_schema`.
  - **`boundary.unkeyed.json` sidecar**: any time the snapshotter drops features (state_filter exclusion, missing split-by property, missing `id_property`, geometry invalid), emit `<out>.unkeyed.json` per `boundary.unkeyed.schema.json` v1.0 with `totals` + per-feature `dropped` entries. Empty `dropped: []` with `totals.dropped: 0` is the canonical "perfect snapshot" signal — write it explicitly, never omit (denominator visibility per Hans v2).
  - **`feature_collection.metadata.schema.json` v1.1 sidecar `simplification` block**: when `coord_precision` is applied, record `{tolerance_deg: 10**-precision, algorithm: "shapely-preserve-topology"... or document existing rounding as algorithm "coord-precision-round" — confirm during implementation}`, original/retained feature + vertex counts. Lands as `<out>.metadata.json` alongside the existing `<out>.sources.json`.
- [ ] **`backend/tests/test_boundary_snapshot_extensions.py`** — pytest against a small real fixture (3 TN districts × 5 taluks × ~20 villages, cropped from a one-time ramSeraph snapshot committed under `backend/tests/fixtures/boundaries/`). No mocks (Holy Law #7). Asserts: `state_filter` keeps only TN features and records the dropped count; `split_by` writes one file per `dist_lgd` group + the index manifest validating against `boundary.villages_index.schema.json`; `unkeyed.json` denominator math (`original == retained + dropped`); `metadata.json` `simplification` block consistent with actual feature counts; gzipped per-district village file ≤ 8 MB budget at the configured `coord_precision`. Existing snapshot tests stay green (additive change).
- [ ] **`tools/boundaries/README.md` update** — extend the existing README with the three new `source.*` blocks (`state_filter`, `split_by`, unkeyed-sidecar emission) and the rationale for templated `out` + index manifest. Same commit. NO new `docs/architecture/data/boundaries-pipeline.md` doc — `tools/boundaries/README.md` is the established home for this pipeline's rationale per CLAUDE.md §3 (`tools/` are self-contained; their README owns the design).
- [ ] **SoI silhouette acquisition (separate, low-risk)** — fetch `india-soi.geojson` from `yashveeeeeeer/india-geodata` via a one-off `tools/boundaries/pipeline.json` entry (`kind: "country"`, `out: "geojson/india-soi.geojson"`, `source.format: "geojson"`, single URL). License field set to the yashveeeeeeer-stated CC-BY-4.0 with attribution sidecar (Fowler v4 nit 3 — separate license blanket from ramSeraph). No new mechanism needed; uses the existing `geojson` format handler.

**Commit sequence (Fowler v5 nit — explicit, two-hat-clean, ~5 commits)**:
1. **(structural, optional)** — *Extract Function* in `snapshot.py` carving `process_entry()` into `_load_source()` / `_filter()` / `_split()` / `_emit()` IFF the existing function lacks those seams. Empty/skipped if seams already exist; the plan does not invent tidies for their own sake.
2. **(behavioural)** — add `source.state_filter` block + pytest. Empty-match fails loud (assert, not silent empty FC). `coord_precision` re-asserted explicitly per new pipeline entry (no silent inheritance).
3. **(behavioural)** — add `source.split_by` block + index manifest emission (atomic: shards + manifest written via temp-then-rename so partial output on crash is impossible) + pytest validating the index against `boundary.villages_index.schema.json`.
4. **(behavioural)** — add `boundary.unkeyed.json` sidecar + `feature_collection.metadata.schema.json` v1.1 `simplification` block emission + pytest on denominator math.
5. **(behavioural)** — append the two TN `inputs` entries (subdistricts + villages) and the SoI one-off `country` entry to `pipeline.json`; run `snapshot.py` against them; commit the resulting `datasets/boundaries/in/geojson/{S22-subdistricts,S22-villages-<dist_lgd>×38,S22-villages-index,india-soi}.geojson` artifacts + sidecars.

**Fixture provenance (Fowler v5 nit)**: the cropped fixture under `backend/tests/fixtures/boundaries/` carries its own `<file>.geojsonl.sources.json` pointing at the upstream ramSeraph release URL + `fetched_at`, plus a `notes` line in the test file describing the crop procedure (state_lgd=33 ∩ first 3 dist_lgd values ∩ first 5 subdist_lgd per district ∩ first ~20 village_lgd per subdistrict). Empty `sources` is NOT appropriate — the data is upstream-derived, not hand-authored.

**`tools/boundaries/README.md` invariant clause (Fowler v5 nit)**: the README extension explicitly states "entries without `state_filter` / `split_by` keys behave identically to pre-v5 snapshot.py — the new blocks are additive opt-in. Existing `inputs` entries are untouched; existing tests stay green."

---

## Phase 2 — Frontend boundary loader (Correction Level 2, Fowler + Jony)

**Goal**: a single typed loader that the existing `IndicatorChoropleth.svelte` and any future map can call. Removes the per-component `fetch('/state-outline.json')` pattern. Uses the **existing flat `datasets/boundaries/in/geojson/` tree** (v4) — no new `tn/` subtree.

- [x] **`frontend/src/lib/boundaries.ts`** — `loadBoundary(level, parentLgdCode?, stateLgdCode?)` returning a typed `BoundaryFeatureCollection`. Path composition (v4, matches existing on-disk filenames):
  - `("country") → "india-soi.geojson"` (Phase 4 — falls back to existing `india.geojson` until then)
  - `("state") → "india-states.geojson"` (existing)
  - `("district") → "india-districts.geojson"` (existing)
  - `("subdistrict", _, "33") → "S22-subdistricts.geojson"` (TN; one file per state)
  - `("village", "<dist_lgd>", "33") → "S22-villages-<dist_lgd>.geojson"` (per-district)
  Loader reads `S22-villages-index.json` at startup so it knows which `<dist_lgd>` files actually exist (Fowler v4 nit 1 — no 404-probe on hover). Uses Vite `import.meta.glob` over per-district village files (so a village-level click for district `603` resolves to `S22-villages-603.geojson` only — never loads all of TN at once). Static-first (CLAUDE.md §1), lazy chunk-per-district. 404-as-null for unknown parents (graceful degradation contract). Loader exposes the join-key property name per level (`state_lgd` / `dist_lgd` / `subdist_lgd` / `village_lgd`) so the choropleth doesn't hardcode it.
- [x] **Vitest unit test** — `boundaries.path.test.ts`: pure path resolver — `("village", "603", "33") → "S22-villages-603.geojson"`, `("subdistrict", undefined, "33") → "S22-subdistricts.geojson"`, `("district") → "india-districts.geojson"`, `("state") → "india-states.geojson"`. Plus join-key resolver: `joinKeyFor("village") === "vil_lgd"` (upstream uses `vil_*`/`subdt_*` not `village_*`/`subdist_*`).
- [x] **Vitest contract test** — `boundaries.contract.test.ts`: schema-validation of sidecars covered by existing `frontend/src/contracts/datasets-conform.test.ts`; this file adds the loader-specific invariants — every shipped `*.geojson` has a sibling `<file>.geojson.sources.json`, every feature on each LGD-keyed file carries the level's join-key property, every entry in `S22-villages-index.json` has its shard on disk, and no orphan boundary file exists outside the loader's path table.
- [x] **Vitest integration test** — `boundaries.integration.test.ts`: loader composes correct path for `("subdistrict", undefined, "33")`; `fetch` mock returns fixture; loader returns typed collection. 404 → `null`, not throw. Index-cache + missing-index branches included.
- [x] **Bundle-budget test** (Tier-Contract, Fowler edit) — `boundaries.budget.test.ts`: per-village-shard ≤ 4 MB, per-subdistrict ≤ 8 MB, per-national ≤ 16 MB; total chunk count `*.geojson` ≤ 80; index registers exactly the shards on disk.
- [x] **Catalogue drift detector** — orphan-boundary detection moved into `boundaries.contract.test.ts` (the `loader's path table reaches every non-AC boundary file` block) rather than extending `catalogue-coverage.test.ts`. Reason: the catalogue test gates **indicator** artifacts against `topic-catalogue.json`; boundary files are not indicators and the catalogue has no concept of them. The loader's path table IS the boundary equivalent of the catalogue, so the orphan check belongs next to the loader. Schema drift on the catalogue test would otherwise be triggered by a non-indicator concern.

---

## Phase 3 — Citizen drill-down UX (Correction Level 3, Jony + Citizen User)

**Goal**: on a TN-scoped indicator, the citizen can click a district → see taluks → click a taluk → see villages, with the same legend/slider/headline machinery, no per-level bespoke components. Schema-driven, not bespoke (Jony's standing rule).

- [ ] **`frontend/src/lib/IndicatorChoropleth.svelte`** — accepts a `geoLevel` prop (`country|state|district|subdistrict|village`). Default unchanged (`state`). When the citizen clicks a feature on a TN-scoped indicator and a deeper level exists, the map zooms-and-replaces (not stacks). Click reads the join-key property (`dist_lgd` / `subdist_lgd` / `village_lgd`) the loader exposes per level — never hardcoded. Breadcrumb at top: `India › Tamil Nadu › Coimbatore › Pollachi`. Each crumb is a back-affordance. **Three-commit Tidy First split (Fowler v4 nit 2)**: (i) structural — accept `geoLevel` prop, no behaviour change; (ii) structural — consume loader-exposed `joinKey` per level, replacing any hardcoded property reads; (iii) behavioural — wire drill-click to `loadBoundary(level, parentLgdCode, stateLgdCode)` and the zoom-and-replace transition. Three commits, three reviews.
- [ ] **Lazy fetch + skeleton** (Jony edit §a) — village GeoJSON fetched on **district-click**, not pre-loaded with the taluk view. While fetching: taluk polygons remain at full opacity, a small spinner overlays only the clicked district (NOT full-screen). Failure → taluk view stays put, inline toast "village boundaries unavailable", breadcrumb does NOT advance.
- [ ] **Breadcrumb glyph** (Jony edit §b) — each breadcrumb crumb shows the parent polygon's centroid as a 12px monochrome SVG glyph beside the name. Reuses the existing SVG path renderer; no new component. Solves "where am I in TN at village zoom" without a mini-map.
- [ ] **Time-aware breadcrumb names** (Hans edit) — at village level on a pre-2020 time slice, the breadcrumb's parent-taluk crumb shows the **2011 name**, not today's name (and the methodology marker explains why on hover).
- [ ] **Drill-grain gating** (Hans non-blocker, promoted to bullet) — the drill is greyed out below an indicator's valid grain. PLFS / NFHS sample doesn't support village-level inference; the indicator's `min_grain` field (`state|district|subdistrict|village`) gates which click depths are enabled. Greyed crumbs surface a tooltip naming the **lowest valid grain** in the same line: "this indicator is measured at district level, not village" (Jony v3 nit — citizen knows the floor without a second tap).
- [ ] **No new components.** Legend, time slider, headline, source-list all reuse existing primitives. Legend bucketing reads `scale_hint` from indicator metadata (Jony edit §e), NOT from `geoLevel` — village-grain indicators have different value ranges from state-grain.
- [ ] **Empty state** (Jony edit §f) — district/taluk/village with null value renders as diagonal-hatch fill + a legend entry "no data" with both swatch AND a count of polygons in that bucket, **labelled with unit** (e.g. "12 districts, no data") so it doesn't read ambiguously next to value buckets (Jony v3 nit).
- [ ] **Drill transition** — 250ms ease-out zoom; respects `prefers-reduced-motion` → instant. (Jony edit §f)
- [ ] **Gesture map** — tap = drill, drag = pan, no long-press. Pinch reserved for Phase 4. (Jony edit §f)
- [ ] **Lakshadweep callout** — at national zoom only, small inset rectangle bottom-left, Lakshadweep zoomed ~10×, with a labelled border ("Lakshadweep, shown 10×"). **No connecting line** (Jony edit §c — the labelled border carries the meaning; the line implied geographic continuity that isn't there). Disappears below state zoom.
- [ ] **Pincode** — postal-search affordance ONLY. Typed pincode → if Chennai: zoom to pincode polygon. Otherwise: zoom to **district** (Jony edit §d — taluk centroid is a guess dressed as precision; district is honest) + banner "Pincode-level boundaries available for Chennai metro only. Showing your district." Pincode is never a clickable choropleth layer.
- [ ] **Methodology break tooltip demoted** (Jony edit §g) — small "i" glyph in the legend (NOT on every polygon). Polygon hover shows number first, methodology note as a smaller second line, only on affected districts in affected years.
- [ ] **Playwright e2e** `frontend/e2e/tn-drilldown.spec.ts`: load TN page, click district, assert taluk-level features rendered, click taluk, assert village-level features rendered, breadcrumb back to state, no console errors. Per CLAUDE.md §13 + §15.
- [ ] **Vitest integration test** (Fowler edit) `IndicatorChoropleth.boundaries.test.ts` — drill click triggers the correct `loadBoundary(level, parentLgdCode, stateLgdCode)` call (e.g. district `603` click on a TN indicator → `("village", "603", "33")`); 404-as-null degrades to inline toast without throw.
- [ ] **Citizen-User review** before merge: "can a non-technical TN voter find their village in <30s starting from the home page?"
- [ ] **`docs/architecture/frontend/maps.md`** — same commit. Decision log: zoom-and-replace vs stacked, breadcrumb pattern + glyph, lazy village fetch + skeleton, Lakshadweep callout (no connector), pincode-as-search-only with district fallback, drill-grain gating, methodology-break tooltip demotion.

---

## Phase 4 — Polish (Correction Level 1, Jony)

- [x] Replace generic India outline with SoI outline everywhere (visual diff review). — verified 2026-05-15: `boundaries.ts` `country` branch already returns `india-soi.geojson`; `india-soi.geojson` + `.sources.json` are on disk; no remaining code reference to plain `india.geojson`. Phase 1b/2 landed the structural swap; this checkbox closes the audit.
- [x] **Schema bump `boundaries.schema.json` v1.0 → v1.1** to add `name_ta` (Fowler YAGNI — field lands in the same arc as its consumer, the Tamil tooltip). — done 2026-05-15: realised on the registry side as `state.schema.json` v3.3→v3.4, `district.schema.json` v3.3→v3.4, `subdistrict.schema.json` v1.0→v1.1 (no `boundaries.schema.json` exists; the Tamil name belongs on the registry, not the geojson sidecar — feature properties come from upstream ramSeraph and aren't ours to constrain). All 7 affected data files re-bumped to the new `$schema_version`; backend + frontend test suites green.
- [x] Tamil names (`name_ta`) in tooltips when present. — done 2026-05-15: `IndicatorChoropleth.svelte` `deeper_tooltips` now reads `f.properties?.name_ta` and renders it on a secondary line (`lang="ta"`) below the English label. No-op until a producer joins the registry's `name_ta` into geojson features; consumer is forward-compatible.
- [ ] Mobile gesture tuning (pinch-to-drill enabled — was reserved in Phase 3).
- [ ] **Pincode polygons + `datasets/schemas/postal.schema.json` v1.0** — schema + Chennai pincode file land here under `datasets/boundaries/in/postal/IN-pincodes-chennai.geojson` with `<file>.geojson.sources.json` sidecar (Fowler YAGNI — deferred from Phase 0 since the consumer is the search affordance built in Phase 3; if Phase 3 search ships before Phase 4, promote this bullet to Phase 3). Loader path table extends with `("postal", "<pincode>", "33") → "../postal/IN-pincodes-chennai.geojson"`; bundle-budget chunk count remains 80.

---

## Escalation (questions during execution)

User authority: **proceed without further approval** once 95% sign-off lands. During execution, route questions as below; only escalate to user if NONE of these resolve:

| Question type | First consult |
| --- | --- |
| UI/UX, gestures, legends, drill interaction | **Jony** |
| Will a citizen actually understand this? | **Citizen User** (with Jony) |
| What indicator should we surface at taluk/village level? Is the data trustworthy? | **Max** |
| Software engineering — refactor, test, commit hygiene, schema migration mechanics | **Fowler** |
| Cross-boundary contract shape, integration pattern, data-model design | **Gregor** |
| Governance framing, fiscal-federalism context for any indicator surfaced | **Hans** |

Document each consult inline in the relevant commit message: `Consulted: Jony — ...` so the chain is auditable.

## Definition of Done (per CLAUDE.md §9, applied here)

- All **schemas extended/added in v4** — `district.schema.json` v3.3 (bumped), `subdistrict.schema.json` v1.0 (new), `feature_collection.metadata.schema.json` v1.1 (bumped), `boundary.unkeyed.schema.json` v1.0 (new), `boundary.sources.schema.json` (existing, reused), `postal.schema.json` v1.0 (Phase 4) — pass Tier-A + Tier-B validation in CI.
- Every boundary file has `sources` (≥1 URL, `fetched_at` UTC).
- `npm test` + `npm run test:e2e` + `pytest -q` green.
- TN drill-down smoke-tested via agent browser tools (§13) on `http://localhost:5173/`: home → TN page → district click → taluk click → village click, no console errors.
- All decision rationales captured in `docs/architecture/data/boundaries.md`, `tools/boundaries/README.md` (Phase 1b extensions), `docs/architecture/frontend/maps.md` — same commits.
- Lockfiles in sync (§9 last bullet).
- No `[DEBUG]` markers, no hardcoded values, no mocks.

## Confidence scores (to be filled before execution)

- Hans (governance / sources / fiscal-federalism framing of TN): **96%** ✅ (signed off 2026-05-15 v2; v4 unchanged — same ramSeraph upstream, same segregation rules)
- Fowler (engineering / pipeline / schema / tests): **96%** ✅ (signed off 2026-05-15 v5 — Strangler Fig over `tools/boundaries/snapshot.py`; folded nits: 5-commit explicit sequence, fixture provenance, atomic split_by emission, coord_precision per-entry, fail-loud on empty state_filter, README invariant clause)
- Jony (UI/UX / drill interaction / Lakshadweep): **96%** ✅ (signed off 2026-05-15 v3; v4 unchanged — UX layer is upstream of disk topology)

**Status: GREEN. All three sign-offs ≥95 on v5. Execution authorized. Phase 0 complete; Phase 1b begins.**

Threshold: each ≥95%. If any below, iterate the relevant section and re-poll **only** that agent.
