# ADR-0031 — Boundary geometry as a sibling family (GeoJSON + PMTiles), not in the canonical Parquet store

**Status**: Accepted
**Last Updated**: 2026-05-18
**Deciders**: User; Jony (UX, owns map rendering surface); Gregor (contracts, sibling-family stance)
**Supersedes**: nothing — first ADR to formalise the boundary tree as canonical store sibling
**Related**: [ADR-0030](0030-canonical-store-duckdb-wasm.md) (canonical observation store); [boundaries.md](../data/boundaries.md) (operational spec); [canonical-store.md §17](../data/canonical-store.md)

## Context

The canonical pivot ([ADR-0030](0030-canonical-store-duckdb-wasm.md)) puts every yen-gov observation into Hive-partitioned Parquet read by DuckDB-WASM in the browser. That decision raised the question: where does boundary geometry live?

The pre-pivot tree already has working boundary infrastructure under `datasets/boundaries/in/` — country outline, india-states / india-districts / india-soi GeoJSONs, per-state `S<NN>-ac.geojson` for assembly constituencies (S01–S2x), TN-granular sub-districts and per-district village layers, and a postal/pincode orthogonal layer. Files ship with `.sources.json` provenance sidecars, `.metadata.json` (license + CRS + simplification block), and `.unkeyed.json` (denominator of features dropped because they did not join to the LGD registry). The full operational spec lives in [boundaries.md](../data/boundaries.md).

The decision to capture:

- Does boundary geometry move into the canonical Parquet store, or stay in its own sibling family?
- What format does each level use — GeoJSON, PMTiles, something else?
- How does the frontend discover boundary files? Via `datasets/manifest.json` (D21) or by guessing paths?
- How does an observation row resolve to a polygon?
- What is the deletion / migration policy as the canonical pivot lands?

This ADR exists because the answer is **cross-cutting** (data layer + frontend renderer + manifest contract) and the canonical-pivot rip-and-replace (D13) makes the "do nothing, leave it as it is" path risky: an execution agent reading "everything legacy moves to `_old/`" could plausibly sweep `datasets/boundaries/` into the same move and break every map in the app. Writing the rule down once, in one place, is cheaper than fielding the same agent question every round.

## Decision

### D25 (restated, authoritative)

**Boundary geometry lives outside the canonical Parquet store, in the sibling family `datasets/boundaries/in/`.** Observations reference geometry via `entity_id` FK that resolves through `taxonomy/entities.json` to `(entity_level, entity_code)` and then to a boundary file path enumerated in `datasets/manifest.json`.

### Format split by layer size

| Layer | Current format | Cutover trigger |
| --- | --- | --- |
| Country (`IN`) | GeoJSON | stays GeoJSON (single polygon, <100 KB) |
| State (national, all 36) | GeoJSON | stays GeoJSON |
| District (national, all) | GeoJSON now | → PMTiles when single file exceeds ~10 MB gzipped OR when zoom-level tiling becomes a perf win |
| AC per state (`S<NN>-ac.geojson`) | GeoJSON | stays GeoJSON per-state (one file per state stays under budget) |
| PC national | not yet ingested | PMTiles from day one (election cycles need zoom in; one national file > budget at full resolution) |
| Sub-district / taluk | GeoJSON now (TN only) | → PMTiles when national rollout, same trigger as districts |
| Village per state | GeoJSON now (TN partial) | → PMTiles per state when state coverage exceeds budget |
| Postal (pincode, orthogonal — not LGD) | GeoJSON per city | stays GeoJSON per city (segregated under `postal/` — see boundaries.md) |

**The 10 MB threshold answers Q11 of THE PLAN** ([TODO/20260517-canonical-long-format-pivot.md](../../../TODO/20260517-canonical-long-format-pivot.md)). It is an opening bid, not a hard wall: re-evaluate when the first layer trips it. The deciding factor is wall-clock cold-load on a mid-tier Android — when the GeoJSON download visibly stalls the map paint, switch.

### Why a sibling family, not Parquet

Vector geometry is not tabular. Forcing it into Parquet loses:

- **Tile pyramids** — PMTiles ships pre-built zoom levels; Parquet cannot pre-tile.
- **Simplification by zoom level** — natural to PMTiles, awkward to Parquet rows.
- **GPU-native rendering** — maplibre-gl reads PMTiles directly via HTTP Range and pushes to WebGL; Parquet would require a CPU-side conversion every query.
- **Geometry-aware operations** — turf.js / mapbox-gl-draw / spatial joins all expect GeoJSON/MVT, not row vectors.

Putting geometry in Parquet is a hammer-meets-screw decision. The canonical Parquet store stays focused on observations; geometry stays in the format the GIS world already solved (rejected as R24 in ADR-0030).

### Why GeoJSON + PMTiles, not a single format

GeoJSON wins on: human-readable diffs, hand-edit-ability for tiny layers (country outline), trivial inspection, no toolchain overhead. PMTiles wins on: file size at scale, pre-tiled zoom levels, single-file HTTP Range archive, native maplibre-gl protocol.

Using GeoJSON when it's small and PMTiles when it's large is the right two-format compromise. A single-format world either pays GeoJSON's size cost at scale (national village layer would be hundreds of MB) or pays PMTiles' tooling cost on a trivial country outline.

### Discovery via the manifest, not by guessing

`datasets/manifest.json` (D21) enumerates boundary files alongside observation Parquet so the frontend has **one** control-plane:

```json
{
  "tables": [
    {
      "table_id": "boundaries.in.states",
      "family": "boundaries",
      "files": [
        { "path": "boundaries/in/geojson/india-states.geojson",
          "format": "geojson", "size_bytes": 1234567 }
      ]
    },
    {
      "table_id": "boundaries.in.districts",
      "family": "boundaries",
      "files": [
        { "path": "boundaries/in/geojson/india-districts.geojson",
          "format": "geojson", "size_bytes": 8765432 }
      ]
    }
  ]
}
```

Frontend NEVER hardcodes geometry paths. The loader reads the manifest, finds the boundary entry matching `(entity_level, layer)`, and fetches via HTTP Range. This is the same rule as observation Parquet (rejected as R23 in ADR-0030) — one control plane, no guessing.

### Resolution path: observation → polygon

```
observations.entity_id          (e.g. "IN-S22-167-2866")
    │
    ▼
taxonomy/entities.json row
    │   { entity_id, entity_level: "ac" | "district" | "state" | "country",
    │     entity_code, parent_entity_id, valid_from, valid_to, ... }
    ▼
datasets/manifest.json — boundary table for that entity_level
    │
    ▼
boundaries/in/geojson/S22-ac.geojson  (or .pmtiles when migrated)
    │
    ▼
feature with matching property (e.g. ac_lgd === 167)
```

The entity row carries `entity_valid_from` / `entity_valid_to` (D23) so the choropleth can grey (not hide) regions outside their validity window — Telangana before 2014, J&K/Ladakh before 2019.

### Existing files preserved as-is

Every file currently under `datasets/boundaries/in/` stays exactly where it is. Specifically:

- `boundaries/in/country/IN.json`
- `boundaries/in/geojson/india-soi.geojson`
- `boundaries/in/geojson/india-states.geojson`
- `boundaries/in/geojson/india-districts.geojson`
- `boundaries/in/geojson/S01-ac.geojson` through `S2x-ac.geojson` (every existing per-state AC file)
- `boundaries/in/geojson/S<NN>-subdistricts.geojson` (TN today; other states as ingested)
- `boundaries/in/geojson/S<NN>-villages-<dist_lgd>.geojson` (TN today; other states as ingested)
- All `.sources.json`, `.metadata.json`, `.unkeyed.json` sidecars (preserved by convention)
- `boundaries/in/postal/IN-pincodes-<city>.geojson` (Chennai today)

Future additions (PCs, taluks national rollout, villages national rollout) follow the same `boundaries/in/{geojson|pmtiles}/` layout under the format-per-level table above.

### Migration / deletion exclusion (R25)

**`datasets/boundaries/` is NEVER moved into `_old/`.** Phase 0.13 (the legacy JSON sweep) and Phase 1.8 (the legacy deletion) EXCLUDE the boundary tree.

Any execution agent that finds itself about to run `git rm` or `git mv` against a file under `datasets/boundaries/` MUST stop and escalate to the user. This is repeated in §0c of THE PLAN, in the deletion manifest, in `canonical-store.md` §2, and now here — four places, on purpose, because the cost of a wrong sweep is every map in the app rendering blank.

### Lakshadweep and other rendering callouts

Operational rendering rules (Lakshadweep displayed at true geographic position with optional zoom-on-hover callout; no US-Alaska-style inset; no postal layer as a clickable choropleth; new districts only render their polyline forward from `created_after_2011.date`) live in [boundaries.md](../data/boundaries.md) and [frontend/maps.md](../frontend/maps.md). They are not ADR-grade decisions — they are operational style. This ADR points at them and stops.

## Rejected alternatives

| # | Rejected | Why |
| --- | --- | --- |
| B1 | Push geometry into Parquet alongside observations (one row per feature with a `geometry: BLOB` column) | See "Why a sibling family" above. Loses tile pyramids, zoom-level simplification, GPU-native rendering, geometry-aware ops. R24 of ADR-0030. |
| B2 | Single-format world — all GeoJSON or all PMTiles | GeoJSON-only pays size cost at scale (national villages > hundreds of MB); PMTiles-only pays tooling cost on trivial layers. Two-format split is the right compromise. |
| B3 | Frontend guesses geometry paths from convention (`boundaries/in/geojson/<level>.geojson`) | Brittle; partition policy and file-format choice become hidden contracts in the renderer. Use the manifest (D21). R23 of ADR-0030 (for observations) applies symmetrically here. |
| B4 | Sweep `datasets/boundaries/` into `_old/` with the rest of the pre-pivot tree during Phase 0.13 | Boundaries are NOT pre-pivot artifacts — they are canonical-store siblings (D25). R25 of ADR-0030. The cost of a wrong sweep is every map in the app rendering blank. |
| B5 | Move boundary geometry into the per-family Parquet (e.g. carry an AC polygon column on every elections row) | Massive duplication; geometry would repeat once per (election × AC) row instead of once per AC. Locks geometry to one family. Worse than B1. |
| B6 | Vector tile server (Tippecanoe + tile server in production) | Violates static-first (Holy Law #1) — needs a running server. PMTiles is the static-hostable equivalent and is what we adopt. |
| B7 | Reuse `taxonomy/entities.parquet` for geometry by adding a `geometry: BLOB` column | Same as B1; entities table becomes mixed-concern and grows by 1–2 orders of magnitude in size for no query win. |
| B8 | Embed PMTiles inside the Parquet manifest as base64 | Defeats HTTP Range — would force full-archive download. PMTiles' value is range-fetching tile slices. |

## Consequences

### Positive

- Maps continue to work through the pivot with zero file movement — Phase 0 lands without touching `boundaries/`.
- Citizen rendering performance is preserved (maplibre-gl reads PMTiles natively when we migrate large layers).
- Hand-editable small layers (country outline) stay GeoJSON for trivial inspection / diff review.
- One control plane (`datasets/manifest.json`) for both observations and boundaries — frontend never special-cases geometry discovery.
- Boundary tree is explicitly out-of-scope for the legacy sweep — the four-place repetition (THE PLAN §0c, deletion manifest, canonical-store.md §2, this ADR) makes a wrong sweep require ignoring four signs.

### Negative

- Two formats to support (GeoJSON + PMTiles). Cutover policy (the 10 MB threshold) is a guess until we trip it.
- Boundary file discovery now requires the manifest to be regenerated whenever a layer is added — one more write-time step.
- Frontend loaders need a small `format` switch on the boundary entry (GeoJSON vs PMTiles read paths differ). Manifest carries `format` so the switch is data-driven, not hardcoded.

### Neutral

- The existing rich boundaries.md doc (operational rules, identifier discipline, methodology breaks, postal orthogonality, Lakshadweep, sidecar conventions) is unchanged and remains authoritative for operational detail. This ADR is a thin "where does it live and why" record above that operational layer.

## Implementation plan

Phase 0.14 of THE PLAN ships:

1. This ADR.
2. A short canonical-pivot note added to [boundaries.md](../data/boundaries.md) that points at this ADR and the canonical-store doc and reasserts the no-move rule. No restructuring of boundaries.md — it is already authoritative for operational detail.
3. No file movement, no code change. Geometry tree continues to work as-is.

Subsequent phases:

- Phase 0.6 (manifest contract): the writer adds boundary table entries to `datasets/manifest.json`.
- Phase 0.8 (DuckDB-WASM wired): frontend loader switches its boundary discovery to read from `manifest.json` instead of hardcoded paths (small refactor — fewer than 10 lines).
- Phase 1+ : as new boundary layers are added (PCs, national taluks, national villages), apply the format-per-level table above. First layer that trips the 10 MB threshold drives the GeoJSON → PMTiles tooling work; that work is itself a follow-up ADR if non-trivial.

## See also

- [ADR-0030 — canonical store on Parquet + DuckDB-WASM](0030-canonical-store-duckdb-wasm.md) — sibling-family rationale (D25, R24, R25)
- [boundaries.md](../data/boundaries.md) — operational spec (disk topology, sidecars, LGD discipline, methodology breaks, postal orthogonality)
- [canonical-store.md §17](../data/canonical-store.md) — pointer from the canonical store to this ADR
- [canonical-pivot deletion manifest](../canonical-pivot-deletion-manifest.md) — re-asserts the no-move rule
- [THE PLAN §0c + §6 step 0.14](../../../TODO/20260517-canonical-long-format-pivot.md) — boundaries-preservation reinforcement
- [frontend/maps.md](../frontend/maps.md) — operational rendering rules (Lakshadweep, choropleth greying)
