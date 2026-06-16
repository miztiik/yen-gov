# Electoral boundary geometry

Last Updated: 2026-06-16

Geometry for ECI Assembly Constituencies (AC) and Parliamentary
Constituencies (PC). After the 2026-06-16 map-geometry rip (Row 3 of
`TODO/20260616-map-geometry-rip-and-palette-plan.md`) there is exactly
ONE delimitation vintage on disk -- `delim=2024` -- and it carries every
delimitation era via a dual-key join (see "Map-engine contract" below).

## Layout

```
datasets/boundaries/electoral/
  delim=2024/
    ac/
      all.topojson      # ONE national TopoJSON, object "ac"
    pc/
      all.geojson       # ONE national GeoJSON
```

- **AC** ships as ONE national TopoJSON `delim=2024/ac/all.topojson`
  (object `ac`; each feature stamped `state_ut_code`). The 31 per-state
  `delim=2008/ac/state=<slug>/all.geojson` shards that pre-dated the rip
  were consolidated into this one file and deleted. TopoJSON (not GeoJSON)
  because a national AC GeoJSON costs ~24 MB gzip vs the ~3.7 MB gzip the
  quantized + arc-shared TopoJSON costs -- D6 of the plan (correctness +
  static-first both satisfied; the geometry is lossless, only the encoding
  is denser). The frontend decodes it via `topojson-client` and filters per
  state by `state_ut_code`.
- **PC** ships as ONE national GeoJSON `delim=2024/pc/all.geojson`. It
  carries both a numeric `unique_id` (e.g. `S07_5`, for LS 2024) and a
  dual-key `pc_slug_uid` (e.g. `S07_karnal`, the name-slug join used by
  LS 2009-2019 events).

## Current contents on disk

| Vintage | AC | PC | Notes |
| --- | --- | --- | --- |
| `delim=2024` | 1 national TopoJSON (`ac/all.topojson`, ~4149 ACs) | 1 national GeoJSON (`pc/all.geojson`, 545 PCs) | The single map-geometry snapshot. AC is the consolidated national TopoJSON; PC carries the dual-key (numeric + name-slug) join. |

The pre-rip `delim=2008` (per-state AC shards + a PC file) and the reserved
`delim=2026/` placeholders were DELETED in Row 3. A future ECI Delimitation
Commission Order would re-introduce a new `delim=<year>/` peer at this level;
until then the single 2024 snapshot is authoritative for every era.

## Map-engine contract

The map engine joins every Lok Sabha / Assembly event against this single
2024 geometry:

- **LS 2024**: numeric join on the PC `unique_id` (`<state_ut_code>_<eci_no>`).
- **LS 2009 / 2014 / 2019**: name-slug join on the PC `pc_slug_uid`
  (`<state_ut_code>_<pc_name_slug>`) -- canonical `electoral.csv` carries
  unreliable `eci_no` values for the older delimitation, so the kebab-case
  PC name slug is the stable key. An unmatched seat renders grey (never a
  wrong-seat colour -- safe-by-construction).
- **AC events**: the national AC TopoJSON is filtered per state by
  `state_ut_code`, then painted via the per-state `join_property` crosswalk
  (lgd_ac_id / ac_no / seat_id) unchanged.

The `delim_year` baked into each tile-cartogram `unit_id`
(`IN-<code>-AC-2008-<n>`, `IN-PC-2008-<sc>-<ls>`) records the delimitation
ERA independently of the single geometry vintage on disk.

## Cross-references

- Plan: [TODO/20260616-map-geometry-rip-and-palette-plan.md](../../../TODO/20260616-map-geometry-rip-and-palette-plan.md)
  Row 3 (the rip) and [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md)
  section 4 EL2 (the original `boundaries/electoral/` introduction).
- Schema: [../../schemas/boundary-layers.schema.json](../../schemas/boundary-layers.schema.json)
  v1.6 (format enum widened to accept `topojson` for the national AC layer).
- Consolidation tool: `tools/boundaries/consolidate_ac_2024.py` (AC) +
  `tools/boundaries/dual_key_pc_2024.py` (PC dual-key stamp).
- Frontend reader: [`frontend/src/lib/maplibre/sources.ts`](../../../frontend/src/lib/maplibre/sources.ts)
  (`STATE_AC` + `INDIA_PC` registries).
- Backend gate: [`backend/tests/test_electoral_boundaries_layout.py`](../../../backend/tests/test_electoral_boundaries_layout.py)
  asserts the on-disk layout matches this grammar.
- Companion admin spine: [`../in/README` (implicit)](../in/) keeps the
  non-electoral admin boundaries (country / states / districts /
  subdistricts / blocks / panchayats / villages / wards / postal). The
  admin spine and the electoral spine sit as peers under
  `datasets/boundaries/`.
