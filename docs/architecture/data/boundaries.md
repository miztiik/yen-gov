# Boundaries — disk topology, identifier discipline, ledger

**Last Updated**: 2026-05-22
**Owner**: data layer (`backend/yen_gov/pipelines/boundaries_*` + `tools/lgd/` + `tools/boundaries/`)

This doc captures the rationale behind every design choice that touched the boundary stack as it evolved from "one `india.geojson` outline" through "LGD-coded states + districts" to TN-granular sub-district + village layers (TODO/TN-GRANULAR-GEO-PLAN.md), and through the T.0d consolidation (2026-05-22) that moved the tree to Hive partitioning and retired the per-shard sidecars. When the plan and this doc disagree, **this doc wins** (Holy Law #4 — docs are agent memory; the plan is a working artifact).

> **Canonical pivot stance (2026-05-22, T.0d amendment)**: under the canonical long-format pivot ([ADR-0030](../decisions/0030-canonical-store-duckdb-wasm.md)), the boundary tree remains a **sibling family** to the canonical Parquet store. Geometry stays in GeoJSON / PMTiles (per-layer cutover spec in [ADR-0031 + Amendment 2026-05-22](../decisions/0031-boundary-geometry-strategy.md)). `datasets/boundaries/` is **excluded from any `_old/` sweep and any deletion step** (R25 of ADR-0030 + ADR-0031). T.0d normalised on-disk layout to Hive partitioning and consolidated the three sidecar families (`*.sources.json` / `*.metadata.json` / `*.unkeyed.json`) plus the per-state `<eci>-villages-index.json` manifests into a single parquet ledger at `datasets/boundaries/boundary_layers.parquet` (FK to `taxonomy/sources.parquet` v2.0).

## Disk layout (post-T.0d, Hive-partitioned)

```
datasets/boundaries/
├── boundary_layers.parquet                          # 74 rows; one per shard; the ledger
└── in/
    ├── country/all.geojson                          # IN outline (was india-soi.geojson)
    ├── states/all.geojson                           # all 36 states/UTs; property `state_lgd`
    ├── districts/all.geojson                        # all districts; property `dist_lgd`
    ├── subdistricts/state=in_<lc>/all.geojson       # per-state (TN today); property `subdist_lgd`
    ├── villages/state=in_<lc>/district=<lgd>/all.geojson  # per-(state, district); property `village_lgd`
    ├── ac/state=in_<lc>/all.geojson                 # 37 states/UTs; property keyed to ECI ac code
    ├── pc/delim=<YYYY>/all.geojson                  # national; delim partition mandatory (ECI cycles)
    └── postal/IN-pincodes-<city>.geojson            # orthogonal; NOT LGD; keyed by pincode
```

Partition keys (`state=in_<lc>`, `district=<lgd>`) match the conventions in `datasets/elections/`, `datasets/energy/`, etc., so the same tooling that resolves observation Parquet paths resolves boundary paths.

### `boundary_layers.parquet` (the ledger)

One row per shard. Schema in `datasets/schemas/boundary-layers.schema.json`. The 10 required columns:

| Column | Meaning |
| --- | --- |
| `layer_id` (PK) | Dot-grammar matching the Hive path (e.g. `boundaries.in.villages.state=in_s22.district=603`) |
| `family` | always `"boundaries"` |
| `country` | always `"in"` |
| `kind` | `"country" \| "states" \| "districts" \| "subdistricts" \| "villages" \| "ac" \| "pc" \| "postal"` |
| `path` | repo-relative POSIX path to the geojson |
| `source_id` | FK to `datasets/taxonomy/sources.parquet` (ADR-0032 v2.0 triple shape) |
| `crs` | EPSG identifier (e.g. `"EPSG:4326"`) |
| `original_feature_count` | features in the source before any filtering / simplification |
| `retained_feature_count` | features in the emitted geojson |
| `unkeyed_count` | features dropped because they did not join to the LGD registry |

Denominator invariant: `original_feature_count == retained_feature_count + unkeyed_count` (enforced by `BoundaryLayerRow` Pydantic validator in `backend/yen_gov/canonical/boundary_layers_seed.py`).

7 optional nullable columns: `state_eci`, `state_lgd`, `district_lgd`, `simplification_tolerance`, `simplification_algorithm`, `bbox`, `notes`. As of schema v1.1 (2026-05-24), `delimitation_vintage` (nullable, `^[0-9]{4}$`) is added: required on PC rows (and on future AC rows once delimitation history backfills land), null elsewhere. See [ADR-0031 Amendment 2026-05-24](../decisions/0031-boundary-geometry-strategy.md#amendment-2026-05-24-pc-layer-ingest--delimyyyy-partition-key).

Frontend has zero direct readers of this parquet today (renderer never needed metadata at runtime). The ledger is the **operator + citizen-citation surface**; the geojsons remain the renderer's input.

### Why Hive partitioning (T.0d)

Pre-T.0d the tree was flat: `boundaries/in/geojson/india-states.geojson`, `boundaries/in/geojson/S22-ac.geojson`, `boundaries/in/geojson/S22-villages-603.geojson` mixed at the same depth, plus an ad-hoc `S22-villages-index.json` per state listing which districts had been ingested. That worked for the 8–10 layers that existed pre-pivot but did not scale: national villages would put ~700 files in one directory, and the index manifest was a second control plane next to the manifest.json one.

Hive partitioning solves both:

1. Per-state and per-district shards live at their own depth (`villages/state=in_s22/district=603/all.geojson`), so `ls boundaries/in/villages/state=in_s22/` lists "TN districts with village geometry on disk" without an index file.
2. Frontend resolves a layer to a path via `boundaryRelPath(level, parentDistrictLgd?, stateLgd?)` (`frontend/src/lib/boundaries.ts`). Village lookups fetch the partition path directly and let 404 = "not yet ingested" propagate as `null` (graceful degradation).
3. The convention matches every other family on disk — one fewer mental model for new contributors.

### Why postal stays segregated under `postal/`

Pincodes are **postal delivery zones**, not administrative units. They cross block / village / taluk lines. Mixing them under the LGD-keyed Hive tree would imply they participate in the same hierarchy and the same join — they don't, and pretending they do is a citizen-trust killer. The `postal/` subtree is intentional: a different visual layer in the UI, a different join key (`pincode` not `*_lgd`), and the rendering label "postal zone, not administrative". No `state=...` partition because the pincode IS the identifier (one or more cities per file).

## Identifier discipline

### LGD as registry vs LGD-keyed geometry

Two distinct things:

- **LGD = registry**: the Local Government Directory CSVs (`datasets/taxonomy/lgd/{states,districts,subdistricts,villages}-latest.csv` plus dated immutable snapshots `<role>-YYYY-MM-DD.csv` per plan TODO/20260517-canonical-long-format-pivot.md §0e.10.2-C; moved from `datasets/reference/in/lgd/` in T.0c-ii closeout, 2026-05-21). These are *codes + hierarchy + names*, no geometry. Maintained by `tools/lgd/snapshot.py` from `ramSeraph/opendata` release `lgd-latest-extra1`.
- **LGD-keyed geometry**: the Hive-partitioned GeoJSONs above. Each feature carries the **same LGD code** as the registry, so the join is one column (`state_lgd` / `dist_lgd` / `subdist_lgd` / `village_lgd`).

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

Per-file budget: **8 MB gzipped**. Enforced by `boundaries.budget.test.ts` (frontend vitest). Beyond this, mid-tier Android phones on 4G start to feel the chunk download.

For TN villages this means simplification at write time. The simplification metadata (tolerance, algorithm, original/retained feature counts) lives in the `boundary_layers.parquet` row (`simplification_tolerance`, `simplification_algorithm`, `original_feature_count`, `retained_feature_count`). Without that record, downstream area/length math from the simplified geometry would silently lie.

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

Disk layout sits OUTSIDE the LGD Hive tree to make the orthogonality visible at the path level: `datasets/boundaries/in/postal/IN-pincodes-<city>.geojson`. `boundaryRelPath("postal")` returns `postal/IN-pincodes-chennai.geojson` and the loader fetches it via the same `${DATA_BASE}/boundaries/in/${relpath}` URL builder — keeps the code one-arm.

**Status (Phase 4 §160 of TN-GRANULAR-GEO-PLAN, structural surface landed 2026-05-15)**: schema v1.0 + loader + tests are in place; the actual Chennai pincode geojson, the per-state registry data file, and the search-affordance UI consumer follow in subsequent commits gated on the Phase 3 search affordance landing first (Fowler YAGNI — structural surface ahead of the data and consumer). T.0d wired postal into `boundaryRelPath` so when the geojson lands it will be served via the same loader.

## Enforcement

A Tier-B forbidden-path gate (`tier_b_legacy_boundary_sidecars` in `backend/yen_gov/validate.py`) rejects any future `*.sources.json` / `*.metadata.json` / `*.unkeyed.json` / `*-index.json` under `datasets/boundaries/`. The companion allowlist at `datasets/_ops/legacy-boundary-sidecars.txt` ships empty by design; it exists only to support short-lived overrides during follow-up PRs (with PR-body justification required). Same pattern as `tier_b_legacy_folded_indicator_shards`.

Frontend has a paired contract test at `frontend/src/contracts/boundaries-conform.test.ts` that asserts every `**/*.geojson` under `datasets/boundaries/in/` matches one of the seven Hive-shape patterns AND that no legacy sidecar / index manifest survives.

## See also

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
