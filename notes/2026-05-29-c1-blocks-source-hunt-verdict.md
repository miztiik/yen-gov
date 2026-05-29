# C.1 LGD Blocks upstream hunt verdict

**Date**: 2026-05-29
**Plan-doc row**: C.1 of TODO/20260529-boundary-rip-and-replace-plan.md
**Doctrine**: LGD-golden source-of-truth + ramSeraph mirror preference + CC0 license alignment.

## TL;DR

**Tier-1 path found and ready to implement.** ramSeraph publishes `LGD_Blocks.geojsonl.7z` via the official Indian Admin Boundaries releases (Dec 11, 2023), sourced from LGD/BharatMaps `Admin_Boundary_GramPanchayat` MapServer layer 2. 7323 block features, geojsonl_7z format, CC0 1.0 license with attribution. Same upstream lineage as the already-shipping states / districts / subdistricts / villages / panchayats entries. No deferral needed; implementation can proceed.

## "Block" vs "Subdistrict" — the LGD distinction

LGD treats them as DIFFERENT entities. From https://lgdirectory.gov.in (verified 2026-05-29):

- **7323 Development Blocks** ("Blocks" colloquially; Tehsil / Taluka / Mandal / Block in regional languages).
- **7090 Sub-Districts** (a separate tier between Districts and Blocks / Villages).

yen-gov already ships LGD_Subdistricts via `tools/boundaries/lift_subdistricts_national.py`. **C.1 targets Development Blocks, a separate level** — not a rename of subdistricts. The hierarchical nesting is:

```
State -> District -> Sub-District -> Block -> Village -> Gram Panchayat
```

Both are equally important for rural-development indicators (PMGSY + MGNREGA bind at Block granularity; some Census data structures at Subdistrict level). The naming/terminology varies by state: Blocks are called Tehsil (north / west), Taluka (south / west), Mandal (south / east), or Block (generic). The LGD code (`block_lgd`) is the canonical key regardless of state-specific terminology.

## Investigation log

### ramSeraph releases (comprehensive scan)

Probed https://github.com/ramSeraph/indian_admin_boundaries/releases (and page 2).

**Relevant release tags:**

1. **`blocks` tag** (Dec 11, 2023) — **TARGET FOUND**
   - [`LGD_Blocks.geojsonl.7z`](https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z) — Tier-1 primary (LGD-keyed, BharatMaps lineage)
   - [`PMGSY_Blocks.geojsonl.7z`](https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/PMGSY_Blocks.geojsonl.7z) — alternative (PMGSY-MIS source via geosadak)
   - [`bhuvan_blocks.geojsonl.7z`](https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/bhuvan_blocks.geojsonl.7z) — alternative (Bhuvan / NRSC source)

2. **`subdistricts` tag** (same release date) — separate; existing yen-gov infra. NOT the same as Blocks.

3. Other tags surveyed (out-of-scope for C.1 but noted for Phase C.2-C.6 + future arcs): `states`, `districts`, `constituencies`, `villages`, `panchayats`, `urban` (ULBs), `police`, `forests`, `pincodes`, `historical_districts`, `coastal_regulation_zones`, `census_2011`, `habitations`.

**Choice rationale:** Pick `LGD_Blocks.geojsonl.7z` (not PMGSY or Bhuvan) for these reasons:

- Same BharatMaps/LGD lineage as the rest of yen-gov's boundary corpus (consistency).
- `block_lgd` numeric code joins natively to LGD-keyed indicator parquets (no name-string joining).
- CC0 1.0 license matches the other LGD releases.
- PMGSY_Blocks may have a slightly different vintage / boundary edit window (PMGSY-MIS-specific edits); reserve as a Tier-2 fallback if LGD_Blocks turns up gaps for any state.

### LGD / BharatMaps

**LGD Directory** (https://lgdirectory.gov.in, verified 2026-05-29):

- Home page enumerates "7323 Development Blocks" as a navigable entity class.
- Confirms distinction from "7090 Sub-Districts".
- Block download UI at https://lgdirectory.gov.in/globalviewBlockforcitizen.do (web UI, not a machine-readable API).

**BharatMaps service** (https://mapservice.gov.in/gismapservice/, verified 2026-05-29):

- `Admin_Boundary_GramPanchayat` MapServer carries Block polygons on layer 2.
- Source URL: https://mapservice.gov.in/gismapservice/rest/services/BharatMapService/Admin_Boundary_GramPanchayat/MapServer/2
- This is the upstream that ramSeraph mirrors into `LGD_Blocks.geojsonl.7z`.

### Existing yen-gov subdistrict shipping (NOT the same as Blocks)

`tools/boundaries/lift_subdistricts_national.py` (read 2026-05-29):

- Dedicated orchestrator for LGD_Subdistricts (separate from generic `snapshot.py`).
- Resolves `state_lgd` -> ECI state code to emit per-state hive shards.
- Outputs: `datasets/boundaries/in/subdistricts/state=in_<sNN>/all.geojson`.
- Uses `py7zr` extraction on geojsonl_7z format — SAME infrastructure C.1 will require.

**Reuse strategy**: C.1 should add `tools/boundaries/lift_blocks_national.py` (or extend `snapshot.py`) modelled on `lift_subdistricts_national.py`. The format-handling, py7zr extraction, NDJSON -> FeatureCollection wrap, and per-state hive-partition logic are all reusable verbatim.

### Other probed sources

- **DataMeet** (https://github.com/datameet/maps): no Blocks layer found; historical archives only.
- **Survey of India** (https://onlinemaps.surveyofindia.gov.in): no public Block boundaries; admin boundaries route through BharatMaps.
- **PMGSY open data** (https://geosadak-pmgsy.nic.in/opendata/): publishes PMGSY-flavoured Block boundaries; mirrored by ramSeraph as the `PMGSY_Blocks` alternative noted above.

## Recommended path

**Tier-1 implementation (no deferral):**

### Step 1 — pipeline.json entry

Add under `inputs` (NOT staged) in `tools/boundaries/pipeline.json`:

```json
{
  "$comment": "GAP-FILL (active): India Development Block polygons keyed by LGD code. Sourced from ramSeraph's LGD_Blocks release (BharatMaps/LGD lineage); same upstream as the districts/subdistricts/villages/panchayats entries above. 7323 block features. snapshot.py handles source.format='geojsonl_7z' (py7zr extraction, NDJSON->FeatureCollection wrap). Per-state hive partitions emitted at datasets/boundaries/in/blocks/state=in_<lc>/all.geojson. See notes/2026-05-29-c1-blocks-source-hunt-verdict.md for the upstream verification + naming-vs-subdistricts distinction.",
  "kind": "blocks",
  "source_triple": {
    "producer": "ramSeraph",
    "title": "Indian Admin Boundaries (LGD-keyed)",
    "vintage": "lgd-latest-extra1"
  },
  "country": "IN",
  "out": "blocks/india-blocks.pmtiles",
  "source": {
    "format": "geojsonl_7z",
    "urls": [
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z"
    ],
    "coord_precision": 2
  },
  "license": "CC0-1.0",
  "license_url": "https://github.com/ramSeraph/indianopenmaps/blob/main/DATA_LICENSE.md",
  "license_note": "CC0 1.0 with requested attribution to datameet and the original government publisher (LGD/BharatMaps). Underlying upstream service: https://mapservice.gov.in/gismapservice/rest/services/BharatMapService/Admin_Boundary_GramPanchayat/MapServer/2",
  "id_property": "block_lgd",
  "name_property": "block_name",
  "id_property_note": "TO BE CONFIRMED on first snapshot. Property names follow LGD convention; expected schema is block_lgd / block_name / sd_lgd / dist_lgd / state_lgd. First-snapshot inspection MUST run before treating these names as canonical (analogous to D.0 first-snapshot confirmation for State_LGD / STNAME).",
  "tippecanoe": {
    "minzoom": 6,
    "maxzoom": 12,
    "layer": "blocks",
    "drop_densest_as_needed": true
  },
  "coord_precision_note": "coord_precision=2 (~1.1 km). Matches the districts entry; provides clean choropleth rendering at zoom 6-12 while keeping per-state shards under the simplification budget."
}
```

### Step 2 — schema bump

`datasets/schemas/boundary-layers.schema.json`: add `"block"` to the `level` enum (and to any allowed-values lists in adjacent schemas). Bump schema `$id` minor version.

### Step 3 — snapshot

Run `python -m yen_gov.tools.boundaries.snapshot --layer blocks` (or the equivalent orchestrator). Expected outputs:
- `datasets/boundaries/in/blocks/state=in_<lc>/all.geojson` x 36 (one per state / UT that has Blocks at all — Lakshadweep + some small UTs may legitimately not).
- Sidecar `.parquet` ledger row + `.json` metadata per shard.
- Per-shard simplification budget enforced by `tools/boundaries/simplify.py`.

First-snapshot MUST inspect the actual property names on a sample feature and update `id_property` / `name_property` in pipeline.json + the recommended `BLOCK_BOUNDARY` registry if they differ from the assumed `block_lgd` / `block_name`.

### Step 4 — frontend BLOCK registry

Add `frontend/src/lib/maplibre/sources.ts:BLOCK_BOUNDARY` mirroring the STATE_AC pattern:

```typescript
export const BLOCK_BOUNDARY: Record<StateCode, BoundaryEntry> = {
  S01: { id: 'S01', label: 'Andhra Pradesh', geojson_local_path: 'datasets/boundaries/in/blocks/state=in_s01/all.geojson', geojson_url: '/data/boundaries/in/blocks/state=in_s01/all.geojson', join_property: 'block_lgd' },
  // ... per state
};
```

### Step 5 — contract test

`frontend/src/contracts/state-blocks-registry-coverage.test.ts` analogous to A.2's `state-ac-registry-coverage.test.ts`:
- `discoverShards()` walks `datasets/boundaries/in/blocks/state=in_*/all.geojson`.
- `it.each(Object.entries(BLOCK_BOUNDARY))` asserts per-entry shape + file existence + property presence.
- Corpus-level: every on-disk shard has a registry entry; no orphan registry entries; counts match.

### Step 6 — citizen surface

C.1 itself does NOT require a topic page to ship (analogous to how A.2 shipped the STATE_AC registry without simultaneously authoring a new topic page — A.4 then exercised it). Defer block-level topic-page authoring to a Phase C+1 PR where rural-development indicators (PMGSY km / MGNREGA person-days) are mounted on a `/t/rural-development` chapter. The C.1 PR's Gate 5 is the contract test + browser smoke of a SINGLE state's block shard rendering at the existing `/about?section=maps` source-attribution surface.

## Cited URLs (for reproducibility)

- ramSeraph releases (blocks tag): https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/blocks (verified 2026-05-29; tag date Dec 11, 2023)
- LGD_Blocks direct download: https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z
- BharatMaps upstream layer 2: https://mapservice.gov.in/gismapservice/rest/services/BharatMapService/Admin_Boundary_GramPanchayat/MapServer/2
- ramSeraph indianopenmaps reference: https://indianopenmaps.com/not-so-open/blocks/lgd/{z}/{x}/{y}.pbf (the path the plan-doc row originally referenced; verified accessible)
- LGD Directory home (blocks statistics): https://lgdirectory.gov.in (7323 Blocks shown 2026-05-29)
- LGD blocks download UI: https://lgdirectory.gov.in/globalviewBlockforcitizen.do
- Alternative PMGSY source: https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/PMGSY_Blocks.geojsonl.7z (geosadak provenance)
- ramSeraph parent: https://github.com/ramSeraph/indianopenmaps (DATA_LICENSE.md verified CC0)
- Existing yen-gov subdistrict lift tool: `tools/boundaries/lift_subdistricts_national.py`
- DataMeet historical archive: https://github.com/datameet/maps (verified 2026-05-29; no Blocks layer)

## Verdict summary

**Status**: Tier-1, ready to implement. No blockers.

**Why no deferral**:
1. LGD_Blocks published + stable (19 months old; no new commits to blocks tag since Dec 11, 2023).
2. Format identical to existing yen-gov infrastructure (geojsonl_7z, py7zr + snapshot.py).
3. License (CC0 1.0 + attribution) aligns with yen-gov's CC0-first doctrine.
4. LGD-golden source (BharatMaps lineage) is the canonical authority.
5. No manual georef, no community consensus delay.

**Next-PR scope (C.1 implementation)**: 6 steps above. Estimate ~30-40 changed files (pipeline.json + schema + snapshot orchestrator + ~33 per-state shards + sidecars + frontend registry + contract test + plan-doc flip). Citizen surface deferred to Phase C+1.
