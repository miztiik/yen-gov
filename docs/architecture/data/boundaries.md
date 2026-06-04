# Boundaries — disk topology, identifier discipline, ledger

**Last Updated**: 2026-05-25
**Owner**: data layer (`backend/yen_gov/pipelines/boundaries_*` + `tools/lgd/` + `tools/boundaries/`)

This doc captures the rationale behind every design choice that touched the boundary stack as it evolved from "one `india.geojson` outline" through "LGD-coded states + districts" to TN-granular sub-district + village layers (TODO/TN-GRANULAR-GEO-PLAN.md), and through the T.0d consolidation (2026-05-22) that moved the tree to Hive partitioning and retired the per-shard sidecars. When the plan and this doc disagree, **this doc wins** (Holy Law #4 — docs are agent memory; the plan is a working artifact).

> **Canonical pivot stance (2026-05-22, T.0d amendment)**: under the canonical long-format pivot ([ADR-0030](../decisions/0030-canonical-store-duckdb-wasm.md)), the boundary tree remains a **sibling family** to the canonical Parquet store. Geometry stays in GeoJSON / PMTiles (per-layer cutover spec in [ADR-0031 + Amendment 2026-05-22](../decisions/0031-boundary-geometry-strategy.md)). `datasets/boundaries/` is **excluded from any `_old/` sweep and any deletion step** (R25 of ADR-0030 + ADR-0031). T.0d normalised on-disk layout to Hive partitioning and consolidated the three sidecar families (`*.sources.json` / `*.metadata.json` / `*.unkeyed.json`) plus the per-state `<eci>-villages-index.json` manifests into a single parquet ledger at `datasets/boundaries/boundary_layers.parquet` (FK to `taxonomy/sources.parquet` v2.0).

## Disk layout (post-T.0d, Hive-partitioned)

```
datasets/boundaries/
├── boundary_layers.parquet                          # 753 rows; one per shard; the ledger
└── in/
    ├── country/all.geojson                          # IN outline (was india-soi.geojson)
    ├── states/all.geojson                           # all 36 states/UTs; property `State_LGD`
    ├── districts/all.geojson                        # all districts; property `dist_lgd`
    ├── subdistricts/state=in_<lc>/all.geojson       # 36 states/UTs; property `subdist_lgd`
    ├── villages/state=in_<lc>/district=<lgd>/all.geojson  # 27 states/UTs; per-(state, district); property `village_lgd`
    ├── ac/state=in_<lc>/all.geojson                 # 31 elective states/UTs; property keyed to ECI ac code
    ├── pc/delim=<YYYY>/all.geojson                  # national; delim partition mandatory (ECI cycles)
    └── postal/state=in_<lc>/all.geojson             # 36 state shards; orthogonal; keyed by pincode
        postal/scope=unkeyed/all.geojson             # unresolved pincode polygons
```

Partition keys (`state=in_<lc>`, `district=<lgd>`, and the postal-only `scope=unkeyed`) match the conventions in `datasets/elections/`, `datasets/energy/`, etc., so the same tooling that resolves observation Parquet paths resolves boundary paths.

### `boundary_layers.parquet` (the ledger)

One row per shard. Schema in `datasets/schemas/boundary-layers.schema.json`. The 10 required columns:

| Column | Meaning |
| --- | --- |
| `layer_id` (PK) | Dot-grammar matching the Hive path (e.g. `boundaries.in.villages.state=tamil-nadu.district=603`) |
| `level` | `"country" \| "state" \| "district" \| "subdistrict" \| "village" \| "ac" \| "pc" \| "postal"` |
| `partition_path` | repo-relative POSIX path under `datasets/` to the geometry file |
| `format` | `"geojson" \| "pmtiles"` |
| `crs` | EPSG identifier (e.g. `"EPSG:4326"`) |
| `original_feature_count` | features in the source before any filtering / simplification |
| `retained_feature_count` | features in the emitted geojson |
| `unkeyed_count` | features dropped because they did not join to the relevant registry |
| `size_bytes` | byte size of the published geometry file |
| `source_id` | FK to `datasets/taxonomy/sources.parquet` (ADR-0032 v2.0 triple shape) |

Denominator invariant: `original_feature_count == retained_feature_count + unkeyed_count` (enforced by `BoundaryLayerRow` Pydantic validator in `backend/yen_gov/canonical/boundary_layers_seed.py`).

8 optional nullable columns: `entity_state`, `entity_district`, `entity_city`, `simplification_algorithm`, `simplification_tolerance_deg`, `unkeyed_keys_json`, `notes`, and `delimitation_vintage`. As of schema v1.1 (2026-05-24), `delimitation_vintage` (nullable, `^[0-9]{4}$`) is added: required on PC rows (and on future AC rows once delimitation history backfills land), null elsewhere. See [ADR-0031 Amendment 2026-05-24](../decisions/0031-boundary-geometry-strategy.md#amendment-2026-05-24-pc-layer-ingest--delimyyyy-partition-key).

Frontend has zero direct readers of this parquet today (renderer never needed metadata at runtime). The ledger is the **operator + citizen-citation surface**; the geojsons remain the renderer's input.

### Why Hive partitioning (T.0d)

Pre-T.0d the tree was flat: `boundaries/in/geojson/india-states.geojson`, `boundaries/in/geojson/S22-ac.geojson`, `boundaries/in/geojson/S22-villages-603.geojson` mixed at the same depth, plus an ad-hoc `S22-villages-index.json` per state listing which districts had been ingested. That worked for the 8–10 layers that existed pre-pivot but did not scale: national villages would put ~700 files in one directory, and the index manifest was a second control plane next to the manifest.json one.

Hive partitioning solves both:

1. Per-state and per-district shards live at their own depth (`villages/state=tamil-nadu/district=603/all.geojson`), so `ls boundaries/in/villages/state=tamil-nadu/` lists "TN districts with village geometry on disk" without an index file.
2. Frontend resolves a layer to a path via `boundaryRelPath(level, parentDistrictLgd?, stateLgd?)` (`frontend/src/lib/boundaries.ts`). Village lookups fetch the partition path directly and let 404 = "not yet ingested" propagate as `null` (graceful degradation).
3. The convention matches every other family on disk — one fewer mental model for new contributors.

### Why postal stays segregated under `postal/`

Pincodes are **postal delivery zones**, not administrative units. They cross block / village / taluk lines. Mixing them under the LGD-keyed Hive tree would imply they participate in the same hierarchy and the same join - they don't, and pretending they do is a citizen-trust killer. The `postal/` subtree is intentional: a different visual layer in the UI, a different join key (`pincode` not `*_lgd`), and the rendering label "postal zone, not administrative". The current `postal/state=in_<lc>/all.geojson` partition is a storage/cache boundary for pincode polygons whose state can be resolved; it does NOT make pincode an administrative child of the state. Unresolved pincode polygons live under `postal/scope=unkeyed/all.geojson`.

## Identifier discipline

### LGD as registry vs LGD-keyed geometry

Two distinct things:

- **LGD = registry**: the Local Government Directory CSVs (`datasets/taxonomy/lgd/{states,districts,subdistricts,villages}-latest.csv` plus dated immutable snapshots `<role>-YYYY-MM-DD.csv` per plan docs/archive/plans/20260517-canonical-long-format-pivot.md §0e.10.2-C; moved from `datasets/reference/in/lgd/` in T.0c-ii closeout, 2026-05-21). These are *codes + hierarchy + names*, no geometry. Maintained by `tools/lgd/snapshot.py` from `ramSeraph/opendata` release `lgd-latest-extra1`.
- **LGD-keyed geometry**: the Hive-partitioned GeoJSONs above. Each feature carries the **same LGD code** as the registry, so the join is one column (`State_LGD` / `dist_lgd` / `subdist_lgd` / `village_lgd`).

This split lets us (a) refresh the registry independently of geometry, (b) detect drift (any feature whose LGD code is not in the current registry → increments `unkeyed_count` on the ledger row), and (c) carry name changes without re-emitting geometry (the registry has the new name; the polygon is unchanged).

### Why ramSeraph

[`ramSeraph/opendata`](https://github.com/ramSeraph/opendata) and [`ramSeraph/indian_admin_boundaries`](https://github.com/ramSeraph/indian_admin_boundaries) are CC-BY-4.0 mirrors of the official LGD + admin-boundary datasets, refreshed every ~3 months. We chose this upstream over scraping `lgdirectory.gov.in` directly because:

- Permissive license, attribution-only (vs. unclear redistribution terms on the original portal).
- LGD-coded features (the official portal exports name-only).
- Stable release-tag pattern (`lgd-latest-extra1`) that `tools/lgd/snapshot.py` already walks date-tokens against.
- One owner, two repos, both active — single point of failure but a known and monitored one.

The `india.gov.in` NAPIX API was rejected as a primary upstream: it requires registration, has rate limits incompatible with our static-pipeline ethos, and the ramSeraph mirror covers the same ground with no auth.

### Why we never use names as IDs

Names drift (Thoothukudi/Tuticorin, Kanyakumari/Kanniyakumari, Chennai/Madras) and merge (Chengalpattu was carved from Kancheepuram, Villupuram, and Tiruvannamalai). The LGD numeric code is the only stable handle. Where a name is needed for citizen display, it lives as a `name` field; where an alternate or historical name is useful, `name_alt`; where the name's authority matters, `name_source` (`lgd|census_2011|wikipedia`). None of these are identifiers.

## File-size budget

Per-fetch budget: the active target is the per-layer gzip ceiling in `tools/boundaries/simplify.py:LAYER_TUNING` (100-500 KB depending on layer). The full corpus check is `python tools/boundaries/simplify.py --dry-run --skip-parquet`; it belongs at the boundary-pipeline seam, not in everyday frontend vitest. Beyond this, mid-tier Android phones on 4G start to feel the chunk download.

For village and subdistrict rollouts this means simplification at write time. The simplification metadata (tolerance, algorithm, original/retained feature counts) lives in the `boundary_layers.parquet` row (`simplification_tolerance_deg`, `simplification_algorithm`, `original_feature_count`, `retained_feature_count`). Without that record, downstream area/length math from the simplified geometry would silently lie.

## Coverage gaps (live)

The live, per-level coverage status — what we have, what we don't have, and what closes each gap — lives in [`docs/reference/boundary-data-sources.md` §"Coverage status — what we have, what we don't have"](../../reference/boundary-data-sources.md#coverage-status--what-we-have-what-we-dont-have). One canonical home, edited in the same PR as the ingest that moves a number. Per the doc-routing contract (CLAUDE.md §5 / [ADR-0034](../decisions/0034-documentation-routing-contract.md)): this subsystem doc describes the **disk + identifier shape**; the reference doc describes the **catalogue + coverage**.

Three gap categories matter today and are tracked there:

1. **District entity backfill** — 145/784 districts curated in `entities.json`; 639 missing. Closed by [Plan Phase 0.2](../../../TODO/20260524-boundary-coverage-expansion-plan.md) via LGD master + Census-2011 cross-enrichment.
2. **Village upstream gap** — 9 of 36 states/UTs (S02 / S08 / S14 / S15 / S16 / S17 / S21 / U08 / U09) have no village polygons from `LGD_Villages`. Closed per-state via the bhuvan fall-back ONLY when a village-keyed citizen indicator demands it; not in the active sprint.
3. **Survey-grade swaps** — state polygon (DataMeet → ramSeraph `LGD_States`), PC polygon (shijithpk → ramSeraph `LGD_Parliament_Constituencies`), and AC consolidation (HTL+shijithpk → ramSeraph `LGD_Assembly_Constituencies`) are upgrade tracks, not coverage gaps. Plan Phases D.0 / D.6 / D.1→D.5.

## Methodology breaks

Indian administrative geography is not stable. Post-2011 districts (Mayiladuthurai 2020, Tenkasi/Tirupathur/Chengalpattu/Kallakurichi/Ranipet 2019) did not exist in Census 2011, so any indicator computed from Census 2011 inputs has no value at the new district's geometry — and any time-series visualisation that draws a polyline through that boundary is lying.

`entity.schema.json` district rows on `datasets/taxonomy/entities.json` surface three break markers (originally on `district.schema.json` v3.3, retired in T.0c-iii Phase D.3 — see [ADR-0033](../decisions/0033-retire-wikipedia-districts-adapter.md)):

- `census_2011_code` — the 2011 code, or `null` for post-2011 districts. Lets a renderer say "this district did not exist in 2011".
- `lgd_code_history` — for the rare case where an LGD code itself was retired and reissued.
- `created_after_2011` — `{date, parent_lgd_codes:[...], notes}`. The `parent_lgd_codes` is **plural** because some new districts have multiple ancestors (Chengalpattu carved from three).

Trend visualisations MUST consult these fields and either (a) render the new district's polyline only from its `created_after_2011.date` forward, or (b) render the parents' aggregate up to that date. Silent continuous polylines are a bug.

## Lakshadweep callout

See [`docs/architecture/frontend/map.md`](../frontend/map.md). Summary: render at true geographic position (Indian-reader expectation, MoSPI/ECI convention), with an optional zoom-on-hover callout when sub-pixel at national zoom. **No US-Alaska-style displaced inset.** No connecting line on the callout — the labelled border carries the meaning.

## Postal (pincode) — search-only orthogonal layer

Pincode polygons are an India Post artifact, not LGD. Two design consequences:

- **The pincode IS the identifier.** No agency-specific code to invent (CLAUDE.md §3). `postal.schema.json` v1.0 (per-state pincode registry, modelled on `subdistrict.schema.json`) carries `id` = 6-digit pincode and `id_source` = `"indiapost"` as the only enum value.
- **Pincodes don't nest cleanly under revenue districts.** Some span district borders. The schema makes `district_id` and `subdistrict_id` OPTIONAL (predominant district when set, absent when ambiguous), so the registry doesn't lie about a hierarchy that isn't there.

The frontend treats `postal` as a search-only orthogonal layer (Jony edit §d of TN-GRANULAR-GEO-PLAN): typed pincode → zoom to its polygon when present, otherwise fall back to district. Pincode is **never a clickable choropleth layer** and **never a drill rung** — the drill state machine (`frontend/src/lib/drilldown.ts`) carries `postal` as a sentinel rank `-1` so `nextLevel("postal") === null` and the function table stays total without forcing every caller to narrow first.

Disk layout sits OUTSIDE the LGD administrative tree to make the orthogonality visible at the path level: `datasets/boundaries/in/postal/state=in_<lc>/all.geojson` for state-resolved pincode polygons and `datasets/boundaries/in/postal/scope=unkeyed/all.geojson` for unresolved polygons. The same `${DATA_BASE}/boundaries/in/${relpath}` URL builder can fetch the shard once a postal search consumer is wired.

**Status (Phase A.2, 2026-05-25)**: pincode polygons now ship as 36 per-state shards plus one `scope=unkeyed` shard. The search-affordance UI consumer remains future work; until then, postal stays a data-ready search layer rather than a clickable choropleth rung.

## Enforcement

A Tier-B forbidden-path gate (`tier_b_legacy_boundary_sidecars` in `backend/yen_gov/validate.py`) rejects any future `*.sources.json` / `*.metadata.json` / `*.unkeyed.json` / `*-index.json` under `datasets/boundaries/`. The companion allowlist at `datasets/_ops/legacy-boundary-sidecars.txt` ships empty by design; it exists only to support short-lived overrides during follow-up PRs (with PR-body justification required). Same pattern as `tier_b_meadow_shard_contract`.

Frontend has a paired contract test at `frontend/src/contracts/boundaries-conform.test.ts` that asserts every `**/*.geojson` under `datasets/boundaries/in/` matches a known Hive-shape pattern AND that no legacy sidecar / index manifest survives.

## Design rationale

This section folds in receipts from the legacy `docs/architecture/decisions/` ADRs that pinned design choices for this subsystem, per parent plan section 9 (keep-receipts ADR retirement) and [decision-index.md](../../reference/decision-index.md). Each receipt below is condensed Context + Decision + Consequences from the originating ADR; the verbatim rejected alternatives live under [Rejected alternatives](#rejected-alternatives).

### ADR-0031: boundary-geometry-strategy

**Context.** The canonical pivot ([ADR-0030](../decisions/0030-canonical-store-duckdb-wasm.md)) puts every yen-gov observation into the canonical store. That raised the question of where boundary geometry lives, what format each level uses, how the frontend discovers boundary files, how an observation row resolves to a polygon, and what the deletion/migration policy is. The answer is cross-cutting (data layer + frontend renderer + manifest contract) and the canonical-pivot rip-and-replace makes the "do nothing" path risky: an execution agent reading "everything legacy moves to `_old/`" could plausibly sweep `datasets/boundaries/` into the same move and break every map in the app. Writing the rule down once, in one place, is cheaper than fielding the same question every round.

**Decision (D25, authoritative).** Boundary geometry lives **outside** the canonical Parquet store, in the sibling family `datasets/boundaries/in/`. Observations reference geometry via `entity_id` FK that resolves through `taxonomy/entities.json` to `(entity_level, entity_code)` and then to a boundary file path enumerated in `datasets/manifest.json`. The format split is by layer size: GeoJSON wins on human-readable diffs, hand-edit-ability for tiny layers, trivial inspection, no toolchain overhead; PMTiles wins on file size at scale, pre-tiled zoom levels, native maplibre-gl protocol. Country / state / per-state AC / current-vintage PC stay GeoJSON; districts / sub-districts / villages cut over to PMTiles when a single file exceeds ~10 MB gzipped OR when zoom-level tiling becomes a perf win. Frontend NEVER hardcodes geometry paths - the loader reads the manifest, finds the boundary entry matching `(entity_level, layer)`, and fetches via HTTP Range (one control plane, no guessing, same rule as observation Parquet per R23 of ADR-0030).

**Migration / deletion exclusion (R25).** `datasets/boundaries/` is **never** moved into `_old/`. Phase 0.13 (legacy JSON sweep) and Phase 1.8 (legacy deletion) EXCLUDE the boundary tree. Any execution agent that finds itself about to run `git rm` or `git mv` against a file under `datasets/boundaries/` MUST stop and escalate. This is repeated in four places on purpose (this doc, ADR-0030, the deletion manifest, and originally the ADR file itself) - the cost of a wrong sweep is every map in the app rendering blank.

**Amendment 2026-05-22 (T.0d consolidation).** On-disk layout is Hive-partitioned (matches `datasets/elections/`, `datasets/energy/`, etc.) and the per-shard sidecars (`*.sources.json` / `*.metadata.json` / `*.unkeyed.json`) + per-state `<eci>-villages-index.json` manifests retire in favour of a single ledger at `datasets/boundaries/boundary_layers.parquet` (FK to `taxonomy/sources.parquet` v2.0). A new Tier-B forbidden-path gate (`tier_b_legacy_boundary_sidecars`) rejects any future sidecar / index re-emission.

**Amendment 2026-05-25 (D.6 PC swap).** Closes the `KEEP-CURRENT` clause on the per-layer table for PCs; the current-vintage 545-feature file stays GeoJSON for now and promotes to PMTiles when a second delimitation vintage lands and combined per-`delim=YYYY` files exceed the budget. Core decisions (sibling-family, format-split, manifest discovery, no-move rule) unchanged.

**Consequences.** Geometry stays in the format the GIS world already solved (rejected as R24 of ADR-0030); the canonical Parquet store stays focused on observations; the frontend has one control plane (the manifest); the boundary tree is structurally safe from the canonical-pivot's deletion machinery; the entity row's `entity_valid_from` / `entity_valid_to` columns let the choropleth grey (not hide) regions outside their validity window (Telangana pre-2014, J&K / Ladakh pre-2019).

### ADR-0036: state-identity-and-slice-registration

Primary fold lives at [canonical-store.md#adr-0036-state-identity-and-slice-registration](canonical-store.md#adr-0036-state-identity-and-slice-registration) - the state-identity rule and the `registerSlice` contract are foundational to the canonical store. This doc cross-references because `boundaries.ts` is one of the consumers of `registerSlice`-style manifest-directed discovery for the boundary family (the loader resolves `boundaryRelPath(level, ...)` against `datasets/manifest.json` entries rather than constructing paths from any state-code convention, matching the ADR-0030 R23 / ADR-0036 manifest-native rule). See [Rejected alternatives](#rejected-alternatives) for the trace of options A-F that the ADR weighed.

### ADR-0047: topojson-as-render-encoding

The 2026-05-31 topojson migration **partially supersedes** ADR-0031's format-split-by-layer-size table for the 8 in-scope Track-A boundary layers (country, state, district, subdistrict, AC, PC, ULB-wards, panchayats). The GeoJSON cells in ADR-0031's table become TopoJSON post-PR-Z4; the PMTiles trigger column is unchanged. ADR-0031's other decisions (sibling-family, manifest discovery, no-move rule, deletion exclusion) remain in force. The TopoJSON fold itself lives at [topojson-loader.md#adr-0047-topojson-as-render-encoding](../frontend/topojson-loader.md#adr-0047-topojson-as-render-encoding). Villages and pincodes are out-of-scope (their bottleneck is render cost, not file format - they get the Track A2 PMTiles successor at [TODO/2026-05-31-village-pincode-vector-tiles-plan.md](../../../TODO/2026-05-31-village-pincode-vector-tiles-plan.md)).

## Rejected alternatives

### ADR-0031 rejected alternatives

Verbatim from the originating ADR (B1-B11). Append-only per parent plan section 9 (keep-receipts).

| # | Rejected | Why |
| --- | --- | --- |
| B1 | Push geometry into Parquet alongside observations (one row per feature with a `geometry: BLOB` column) | See "Why a sibling family" above. Loses tile pyramids, zoom-level simplification, GPU-native rendering, geometry-aware ops. R24 of ADR-0030. |
| B2 | Single-format world - all GeoJSON or all PMTiles | GeoJSON-only pays size cost at scale (national villages > hundreds of MB); PMTiles-only pays tooling cost on trivial layers. Two-format split is the right compromise. |
| B3 | Frontend guesses geometry paths from convention (`boundaries/in/geojson/<level>.geojson`) | Brittle; partition policy and file-format choice become hidden contracts in the renderer. Use the manifest (D21). R23 of ADR-0030 (for observations) applies symmetrically here. |
| B4 | Sweep `datasets/boundaries/` into `_old/` with the rest of the pre-pivot tree during Phase 0.13 | Boundaries are NOT pre-pivot artifacts - they are canonical-store siblings (D25). R25 of ADR-0030. The cost of a wrong sweep is every map in the app rendering blank. |
| B5 | Move boundary geometry into the per-family Parquet (e.g. carry an AC polygon column on every elections row) | Massive duplication; geometry would repeat once per (election x AC) row instead of once per AC. Locks geometry to one family. Worse than B1. |
| B6 | Vector tile server (Tippecanoe + tile server in production) | Violates static-first (Holy Law #1) - needs a running server. PMTiles is the static-hostable equivalent and is what we adopt. |
| B7 | Reuse `taxonomy/entities.parquet` for geometry by adding a `geometry: BLOB` column | Same as B1; entities table becomes mixed-concern and grows by 1-2 orders of magnitude in size for no query win. |
| B8 | Embed PMTiles inside the Parquet manifest as base64 | Defeats HTTP Range - would force full-archive download. PMTiles' value is range-fetching tile slices. |
| B9 | Keep the per-shard `.sources.json` sidecars and just rewrite them into the v2.0 section 12 citation triple shape (T.0d alternative) | Rejected during T.0d as a half-measure dressed as a contract fix. Two problems: (a) the same RBI Handbook cited by 200 shards reproduces the per-shard smear the v2.0 ledger exists to eliminate (section 12 ledger is a TABLE keyed on the triple, not a per-shard array); (b) the boundary tree would diverge from the rest of `datasets/` where provenance is parquet-FK-only - frontend / backend / tooling now have to special-case boundary provenance reads. The right shape is one row per `(producer, title, vintage)` in `taxonomy/sources.parquet` joined to `boundary_layers.parquet` rows by `source_id` FK. |
| B10 | Fold ONLY `.sources.json` to the parquet ledger and keep `.metadata.json` + `.unkeyed.json` sidecars (half-measure) | Rejected during T.0d. The three sidecar files (provenance + simplification metadata + dropped-feature denominator) all describe one boundary layer. Splitting them across two homes (parquet for provenance, sidecar for the other two) creates a join the consumer has to do at runtime against a non-parquet format - worse ergonomics than today. The 10 columns of `BoundaryLayerRow` carry all three concerns in one parquet row; the parquet ledger is the natural single home. |
| B11 | Put `boundary_layers.parquet` under `datasets/taxonomy/` alongside `sources.parquet` and `entities.parquet` | Rejected during T.0d. The taxonomy tree carries reference vocabularies that span every family (sources, indicators, election events, state tiers, topic catalogue). Boundary layers are FAMILY-LEVEL inventory - same altitude as a hypothetical `elections/election_layers.parquet`, not the same altitude as `entities.parquet`. The right home is `datasets/boundaries/boundary_layers.parquet` (sibling to the geojson shards it inventories). Keeps the taxonomy tree generic and the boundary family self-contained. |

## See also

- [docs/concepts/boundary-data-philosophy.md](../../concepts/boundary-data-philosophy.md) -- the "why" behind every boundary-data choice (polygons vs topographic raster, GADM rejection, TopoJSON adoption status, DIGIPIN deferral, HTL kept on purpose).
- [TODO/TN-GRANULAR-GEO-PLAN.md](../../../TODO/TN-GRANULAR-GEO-PLAN.md) — implementation plan that drove the original tree.
- [ADR-0030 — canonical store on Parquet + DuckDB-WASM](../decisions/0030-canonical-store-duckdb-wasm.md) — sibling-family rationale (D25).
- [ADR-0031 — boundary geometry strategy + Amendment 2026-05-22](../decisions/0031-boundary-geometry-strategy.md) — format-per-layer, GeoJSON→PMTiles cutover, no-move rule, Hive layout + parquet ledger.
- [ADR-0032 — sources citation ledger v2.0](../decisions/0032-sources-citation-ledger.md) — the FK target for `boundary_layers.source_id`.
- [canonical-store.md §17](canonical-store.md) — resolution path from observation row to boundary file.
- [ADR-0019: dataset topology + canonical column names](../decisions/0019-dataset-topology-and-column-discipline.md) — `subdistrict_lgd_code` and `village_lgd_code` first-class promotion.
- [ADR-0015: constituency hierarchy fields](../decisions/0015-constituency-hierarchy-fields.md) — `district_id` lifecycle.
- [`ADR-0003: ephemeral raw under `.runtime/`](../decisions/0003-ephemeral-raw-under-runtime.md) — why fetch caches are not committed.
- [`datasets/schemas/boundary-layers.schema.json`](../../../datasets/schemas/boundary-layers.schema.json) — v1.0 (T.0d).
- [`datasets/schemas/feature_collection.metadata.schema.json`](../../../datasets/schemas/feature_collection.metadata.schema.json) — v1.1 (retained — still used by `india_geodata.power_plants`).
- [`datasets/schemas/postal.schema.json`](../../../datasets/schemas/postal.schema.json) — v1.0 (Phase 4 §160).
- [`tools/lgd/snapshot.py`](../../../tools/lgd/snapshot.py) — LGD CSV fetcher.
- [`tools/boundaries/`](../../../tools/boundaries/) — boundary snapshot + Hive migration tooling.
