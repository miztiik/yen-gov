# Electoral boundary geometry

Last Updated: 2026-06-09

Geometry shards for ECI Assembly Constituencies (AC) and Parliamentary
Constituencies (PC), keyed by the Delimitation Commission Order vintage they
reflect.

## Layout

```
datasets/boundaries/electoral/
  delim=<year>/
    ac/
      state=<slug>/
        all.geojson
        all.topojson
    pc/
      all.geojson
      all.topojson
```

The grammar is asymmetric on purpose:

- **AC** uses `delim=<year>/ac/state=<slug>/all.{geojson,topojson}` -- a
  per-state shard tree because Assembly Constituencies are defined within
  state legislatures and the per-state shards keep the citizen-facing page
  load bounded.
- **PC** uses `delim=<year>/pc/all.{geojson,topojson}` -- a single
  country-wide file because Parliamentary Constituencies span the whole
  Union and are not state-partitioned in the canonical store.

## Current contents on disk

| Vintage | AC | PC | Notes |
| --- | --- | --- | --- |
| `delim=2008` | 31 state subtrees (62 files) | -- | The 2008 Delimitation Commission Order. PC for this vintage is the symmetric inverse upstream gap; not in scope for the G10 introduction. |
| `delim=2024` | -- | 1 country file (2 files) | The 2024 LS map (incorporating the J&K 2022 + Assam 2023 reorganisations). AC for this vintage is the symmetric inverse upstream gap. |
| `delim=2026` | `.gitkeep` only | `.gitkeep` only | Reserved for the next ECI Delimitation Commission Order. |

The two `delim=<year>` rows above are the FIRST two electoral vintages on
disk. As new ECI Delimitation Commission Orders are gazetted, each gets
its own `delim=<year>/` peer at this level; no overwrite of any prior
vintage.

## Map-engine contract

The map engine picks the boundary set from the active election event's
`delim_year` (per `TODO/20260603-data-and-charting-platform-reset-plan.md`
section 4 EL2). Old + new delimitation coexist as distinct rows; the
engine MUST NOT overlay mismatched polygons (a pre-2008 result joined
against a 2008-Delim AC layer is a citizen-trust bug).

## Cross-references

- Plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md)
  section 4 EL2 (the layout grammar) and the G10 ledger row (the rip).
- Schema: [../../schemas/boundary-layers.schema.json](../../schemas/boundary-layers.schema.json)
  v1.5 (partition_path + layer_id patterns widened to accept the
  `boundaries/electoral/` subtree).
- Frontend reader: [`frontend/src/lib/maplibre/sources.ts`](../../../frontend/src/lib/maplibre/sources.ts)
  (`STATE_AC` + `INDIA_PC` registries).
- Backend gate: [`backend/tests/test_electoral_boundaries_layout.py`](../../../backend/tests/test_electoral_boundaries_layout.py)
  asserts the on-disk layout matches this grammar.
- Companion admin spine: [`../in/README` (implicit)](../in/) keeps the
  non-electoral admin boundaries (country / states / districts /
  subdistricts / blocks / panchayats / villages / wards / postal). The
  admin spine and the electoral spine sit as peers under
  `datasets/boundaries/`.
