# Boundaries — disk topology, identifier discipline, sidecars

**Last Updated**: 2026-05-15
**Owner**: data layer (`backend/yen_gov/pipelines/boundaries_*` + `tools/lgd/`)

This doc captures the rationale behind every design choice that touched the boundary stack as it evolved from "one `india.geojson` outline" through "LGD-coded states + districts" to TN-granular sub-district + village layers (TODO/TN-GRANULAR-GEO-PLAN.md). When the plan and this doc disagree, **this doc wins** (Holy Law #4 — docs are agent memory; the plan is a working artifact).

## Disk layout

All boundary GeoJSONs live in a flat tree under `datasets/boundaries/in/`:

```
datasets/boundaries/in/
├── geojson/                                       # LGD-keyed administrative boundaries
│   ├── india.geojson                              # generic country outline (legacy; superseded by india-soi.geojson in Phase 4)
│   ├── india-soi.geojson                          # Survey-of-India silhouette (Phase 4)
│   ├── india-states.geojson                       # all 36 states/UTs; feature property `state_lgd`
│   ├── india-districts.geojson                    # all districts; feature property `dist_lgd`
│   ├── S<NN>-ac.geojson                           # per-state assembly-constituency boundaries (existing)
│   ├── S<NN>-subdistricts.geojson                 # per-state subdistrict (taluk/tehsil/mandal); feature property `subdist_lgd`
│   ├── S<NN>-villages-<dist_lgd>.geojson          # per-district village layer; feature property `village_lgd`
│   └── S<NN>-villages-index.json                  # manifest of which <dist_lgd> village files exist
└── postal/                                        # postal-delivery zones (NOT administrative)
    └── IN-pincodes-<city>.geojson                 # e.g. IN-pincodes-chennai.geojson (Phase 4)
```

Each `.geojson` ships with sidecars:

- **Always**: `<file>.geojson.sources.json` — `boundary.sources.schema.json` (provenance per CLAUDE.md §12).
- **When applicable**: `<file>.geojson.metadata.json` — `feature_collection.metadata.schema.json` v1.1 (license + coverage + CRS + simplification block).
- **When applicable**: `<file>.geojson.unkeyed.json` — `boundary.unkeyed.schema.json` v1.0 (denominator of features dropped because they could not be joined to the LGD registry).

### Why a flat tree (no `tn/` subtree)

An earlier draft proposed `datasets/boundaries/in/tn/{districts,subdistricts,villages/}/...`. Rejected because:

1. The existing on-disk convention is already flat (`india-states.geojson`, `india-districts.geojson`, `S<NN>-ac.geojson`). Inventing a parallel per-state subtree forks the topology for no semantic gain.
2. Filename prefixes already encode the state (`S22-...`), so "all TN files" is `ls S22-*` — symmetric with how AC files are addressed.
3. Per-district village split is achieved by the suffix (`-villages-603.geojson`), not by directory nesting. A loader's `import.meta.glob('S22-villages-*.geojson')` is the natural read pattern.

### Why postal is segregated under `postal/`

Pincodes are **postal delivery zones**, not administrative units. They cross block / village / taluk lines. Mixing them under `geojson/` with the LGD-keyed administrative layers would imply they participate in the same hierarchy and the same join — they don't, and pretending they do is a citizen-trust killer. The `postal/` subtree is intentional: a different visual layer in the UI, a different join key (`pincode` not `*_lgd`), and the rendering label "postal zone, not administrative".

## Identifier discipline

### LGD as registry vs LGD-keyed geometry

Two distinct things:

- **LGD = registry**: the Local Government Directory CSVs (`datasets/reference/in/lgd/{states,districts,subdistricts,villages}-latest.csv`). These are *codes + hierarchy + names*, no geometry. Maintained by `tools/lgd/snapshot.py` from `ramSeraph/opendata` release `lgd-latest-extra1`.
- **LGD-keyed geometry**: the boundary GeoJSONs above. Each feature carries the **same LGD code** as the registry, so the join is one column (`state_lgd` / `dist_lgd` / `subdist_lgd` / `village_lgd`).

This split lets us (a) refresh the registry independently of geometry, (b) detect drift (any feature whose LGD code is not in the current registry → goes into the `<file>.geojson.unkeyed.json` sidecar), and (c) carry name changes without re-emitting geometry (the registry has the new name; the polygon is unchanged).

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

Per-file budget: **8 MB gzipped**. Enforced by `boundaries.budget.test.ts` (Phase 2). Beyond this, mid-tier Android phones on 4G start to feel the chunk download.

For TN villages this means simplification at write time. The simplification metadata (tolerance, algorithm, original/retained feature counts) lands in the `<file>.geojson.metadata.json` `simplification` block (`feature_collection.metadata.schema.json` v1.1). Without that record, downstream area/length math from the simplified geometry would silently lie.

## Methodology breaks

Indian administrative geography is not stable. Post-2011 districts (Mayiladuthurai 2020, Tenkasi/Tirupathur/Chengalpattu/Kallakurichi/Ranipet 2019) did not exist in Census 2011, so any indicator computed from Census 2011 inputs has no value at the new district's geometry — and any time-series visualisation that draws a polyline through that boundary is lying.

`district.schema.json` v3.3 surfaces three break markers:

- `census_2011_code` — the 2011 code, or `null` for post-2011 districts. Lets a renderer say "this district did not exist in 2011".
- `lgd_code_history` — for the rare case where an LGD code itself was retired and reissued.
- `created_after_2011` — `{date, parent_lgd_codes:[...], notes}`. The `parent_lgd_codes` is **plural** because some new districts have multiple ancestors (Chengalpattu carved from three).

Trend visualisations MUST consult these fields and either (a) render the new district's polyline only from its `created_after_2011.date` forward, or (b) render the parents' aggregate up to that date. Silent continuous polylines are a bug.

## Lakshadweep callout

See [`docs/architecture/frontend/maps.md`](../frontend/maps.md). Summary: render at true geographic position (Indian-reader expectation, MoSPI/ECI convention), with an optional zoom-on-hover callout when sub-pixel at national zoom. **No US-Alaska-style displaced inset.** No connecting line on the callout — the labelled border carries the meaning.

## Postal (pincode) — search-only orthogonal layer

Pincode polygons are an India Post artifact, not LGD. Two design consequences:

- **The pincode IS the identifier.** No agency-specific code to invent (CLAUDE.md §3). `postal.schema.json` v1.0 (per-state pincode registry, modelled on `subdistrict.schema.json`) carries `id` = 6-digit pincode and `id_source` = `"indiapost"` as the only enum value.
- **Pincodes don't nest cleanly under revenue districts.** Some span district borders. The schema makes `district_id` and `subdistrict_id` OPTIONAL (predominant district when set, absent when ambiguous), so the registry doesn't lie about a hierarchy that isn't there.

The frontend treats `postal` as a search-only orthogonal layer (Jony edit §d of TN-GRANULAR-GEO-PLAN): typed pincode → zoom to its polygon when present, otherwise fall back to district. Pincode is **never a clickable choropleth layer** and **never a drill rung** — the drill state machine (`frontend/src/lib/drilldown.ts`) carries `postal` as a sentinel rank `-1` so `nextLevel("postal") === null` and the function table stays total without forcing every caller to narrow first.

Disk layout sits OUTSIDE the LGD `geojson/` tree to make the orthogonality visible at the path level: `datasets/boundaries/in/postal/IN-pincodes-<city>.geojson`. The loader's basename for postal climbs out of `geojson/` with a `..` segment (`"../postal/IN-pincodes-chennai.geojson"`); the URL builder resolves the segment naturally without needing a separate URL branch — keeps the code one-arm.

**Status (Phase 4 §160 of TN-GRANULAR-GEO-PLAN, landed 2026-05-15)**: schema v1.0 + loader + tests are in place; the actual Chennai pincode geojson, the per-state registry data file, and the search-affordance UI consumer follow in subsequent commits gated on the Phase 3 search affordance landing first (Fowler YAGNI — structural surface ahead of the data and consumer).

## See also

- [TODO/TN-GRANULAR-GEO-PLAN.md](../../../TODO/TN-GRANULAR-GEO-PLAN.md) — implementation plan that drove this doc.
- [ADR-0019: dataset topology + canonical column names](../decisions/0019-dataset-topology-and-column-discipline.md) — `subdistrict_lgd_code` and `village_lgd_code` first-class promotion.
- [ADR-0015: constituency hierarchy fields](../decisions/0015-constituency-hierarchy-fields.md) — `district_id` lifecycle.
- [ADR-0003: ephemeral raw under `.runtime/`](../decisions/0003-ephemeral-raw-under-runtime.md) — why fetch caches are not committed.
- [`datasets/schemas/district.schema.json`](../../../datasets/schemas/district.schema.json) — v3.3.
- [`datasets/schemas/subdistrict.schema.json`](../../../datasets/schemas/subdistrict.schema.json) — v1.0.
- [`datasets/schemas/feature_collection.metadata.schema.json`](../../../datasets/schemas/feature_collection.metadata.schema.json) — v1.1.
- [`datasets/schemas/boundary.unkeyed.schema.json`](../../../datasets/schemas/boundary.unkeyed.schema.json) — v1.0.
- [`datasets/schemas/boundary.villages_index.schema.json`](../../../datasets/schemas/boundary.villages_index.schema.json) — v1.0.
- [`datasets/schemas/postal.schema.json`](../../../datasets/schemas/postal.schema.json) — v1.0 (Phase 4 §160 — pincode registry; structural-only landing).
- [`tools/lgd/snapshot.py`](../../../tools/lgd/snapshot.py) — LGD CSV fetcher.
- [`tools/lgd/backfill_lgd_codes.py`](../../../tools/lgd/backfill_lgd_codes.py) — district name → LGD code bridge.
