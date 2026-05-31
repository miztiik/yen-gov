# ADR-0047 — TopoJSON as render encoding for boundary layers

**Status**: accepted (flipped from proposed at plan-doc P5.5 via PR-Z4 archive; see Acceptance evidence below). Amendment commissioned at [TODO/2026-05-31-geojson-sibling-retirement-plan.md](../../../TODO/2026-05-31-geojson-sibling-retirement-plan.md) (Track A `.geojson` sibling retirement) and [TODO/2026-05-31-village-pincode-vector-tiles-plan.md](../../../TODO/2026-05-31-village-pincode-vector-tiles-plan.md) (Track A2 PMTiles successor).
**Date**: 2026-05-31
**Authors**: yen-gov agent (default), red-teamed by Fowler + Jony + Max subagents
**Plan-doc**: [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../../../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md)
**Supersedes**: **partially supersedes** [ADR-0031 boundary geometry strategy](0031-boundary-geometry-strategy.md) — specifically ADR-0031's format-split-by-layer-size table (GeoJSON cells become TopoJSON post-P5.4 of the migration plan; PMTiles trigger column unchanged). Rest of ADR-0031 unchanged. Plan-doc P5.5 commissions an amendment row on ADR-0031 to update its table.

## Context

yen-gov ships boundary polygons as GeoJSON under `datasets/boundaries/in/<layer>/<partition>/all.geojson`. These files are fetched by the static frontend on every relevant page (India home, state, district pages). For mid-to-large feature counts (state ~36, district ~780, AC ~4,100), GeoJSON's verbosity and lack of topology-sharing make payloads 60-80% larger than necessary, hurting wire bytes and cold-cache time-to-first-paint on slow mobile networks.

TopoJSON (Bostock 2012) is a GeoJSON-extension format that shares arc geometry across adjacent polygons and quantizes coordinates to an integer grid. For shared-edge admin polygons (which all yen-gov boundary layers are), this produces dramatic size reductions with no semantic loss at typical choropleth zoom levels.

## Decision

1. **TopoJSON becomes the preferred shipping encoding** for the 8 in-scope boundary layers (country, state, district, subdistrict, AC, PC, ULB-wards, panchayats). Villages and pincodes are out-of-scope because their bottleneck is browser render cost, not file format — they get a separate plan-doc for vector tiles.

2. **In-place conversion only — no external source adoption.** Both candidate external mirrors (geoBoundaries `wmgeolab`, udit-001) strip LGD codes from their published features (Max audit 2026-05-31). Adopting them as canonical breaks every join in the canonical Parquet store. yen-gov's existing LGD-keyed GeoJSONs are converted to TopoJSON in place; the canonical identity surface is unchanged. **`.topojson` siblings carry no new `source_id`** — the encoding is a derivative of the existing `source_id`-bearing GeoJSON, and `boundary_layers.parquet` rows are unchanged across the conversion (Holy Law #9 satisfied; encoding is not provenance per [docs/concepts/data-provenance.md](../../concepts/data-provenance.md)).

3. **Tooling: Mapshaper CLI** (Fowler verdict 2026-05-31). Subprocess-invoked from Python lift orchestrators (same pattern as the existing `7z` shell-out in `tools/boundaries/lift_shared.py`). Pinned version, deterministic output, byte-identical re-runs.

4. **Quantization: OWID default 1e5** (~1m precision). Hardcoded; revisited per-layer only if visual-diff smoke flags artifacts at home-page zoom.

5. **Loader contract**: frontend prefers `.topojson`; on 404 or parse-error falls back to `.geojson` sibling. No user toggle. The conformance test is the upstream gap-detector — CI fails if a declared partition lacks both formats.

6. **Phasing**: Phase 1 (India home, state layer) ships behind a measured STOP CONDITION (Jony's noise-floor methodology — no fixed % target). Phases 2-3 cascade once Phase 1 proves the encoding swap clears the noise floor on real throttled hardware.

## Rejected alternatives

### A. Adopt geoBoundaries as canonical for ADM0-ADM2
geoBoundaries normalizes every feature to its universal schema (`shapeName`, `shapeISO`, `shapeID`, `shapeGroup`, `shapeType`). The LGD code that yen-gov uses as canonical join identity is stripped, even though geoBoundaries' own metadata cites `lgdirectory.gov.in` as upstream for ADM2/3/4. Adopting would force either a fragile 780-row name-crosswalk (Anantnag vs Anantnāg vs Anant Nag, plus bifurcation drift) or upstream PR to wmgeolab (no SLA). Both costlier than in-place conversion. See `notes/2026-05-31-geoboundaries-udit001-source-audit.md`.

### B. Adopt udit-001
Same LGD-strip problem at smaller coverage (country + state + per-state district only). Hobbyist provenance. No benefit over (A).

### C. Hybrid — geoBoundaries as render-only tier with canonical-Parquet lookup by indexed feature ID
Possible but adds a load-bearing runtime join in the frontend that does not exist today. High engineering cost. Defers all the LGD-strip risk to a brittle indexed lookup. Rejected — encoding swap delivers the perf win without introducing new identity surface.

### D. Python `topojson` package
Less battle-tested than Mapshaper on Indian coastline multipolygons (Sundarbans, Kutch, Konkan). Pure-Python wins on integration aesthetics but loses on production-grade output. Fowler verdict 2026-05-31.

### E. Vector tiles (PMTiles / MVT) as Phase 1
Right answer for villages + pincodes; wrong answer for state + district where feature counts are small enough that the tile overhead exceeds the gain. Commissioned as a separate plan-doc at P5.3 of the migration plan.

### F. Replace `.geojson` in place (no sibling kept)
Rejected per user 2026-05-31: "retain geojson until full swap; we will delete in separate plan". The retirement is commissioned at plan P5.4 as a follow-up PR — not bundled into the encoding swap.

### G. User-facing toggle for format
Rejected per user 2026-05-31: "no user toggle". Loader behaviour is deterministic — topojson-first with mechanical fallback on parse failure.

## Consequences

### Positive
- 60-80% wire-byte reduction on state/district/AC/PC/wards/panchayats (Fowler estimate based on mapshaper production-pipeline history).
- Faster cold-cache TTFP on Slow-4G + 4x-CPU-throttled mobile (Jony noise-floor-multiple verification gate at plan P2.6).
- Lower egress cost on GH Pages.
- No new upstream dependency in canonical store (Max).
- Loader fallback contract means a broken topojson file degrades gracefully instead of breaking the page (user instruction).

### Negative
- Adds Node toolchain (Mapshaper CLI) to dev + CI install requirements. Single global package; pinned version. Smaller surface than a per-repo `node_modules`.
- `topojson.feature()` decode step adds ~main-thread cost per page load (Jony metric 3 — verified at P2.6 must not regress beyond noise floor).
- Doubles boundary file count during the transition (sibling `.geojson` + `.topojson`). Reverted by plan P5.4 cleanup PR.
- Mapshaper version becomes a contract surface — version bump = schema-version-style migration (regenerate all topojson under new version, validate diff, swap, drop old).

### Migration path
Per plan-doc phases P2-P4. Phase 1 (state layer) gates on measured perf clearing noise floor. Phases 2-3 follow once Phase 1 proves the encoding swap delivers.

## References

- Plan-doc: [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../../../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md)
- Mike Bostock, "How To Infer Topology" (2012, the TopoJSON paper)
- Mapshaper CLI: https://github.com/mbloch/mapshaper
- Subagent verdicts captured 2026-05-31 in plan-doc §0 cross-refs.

## Acceptance evidence (2026-05-31)

Plan-doc shipped all 5 phases. ADR flips from `proposed` to `accepted`.

| Phase | PRs |
|---|---|
| P0 (plan + ADR + Max audit) | #486 |
| P1 (bench harness + baseline) | #487 |
| P2 (Phase 1 state layer + loader + bench) | #488 |
| P3 (Track A cascade: districts + country + subdistricts) | #489 |
| P4.1 (AC) | #490 |
| P4.2 (PC) | #491 |
| P4.3 (ULB-wards) | #493 partial + #500 complete |
| P4.4 (panchayats) | #494 partial + #502 complete |
| P4.5 (villages, Track A2) | #495 partial + #504 complete |
| P4.6 (postal/pincodes, Track A2) | #492 |
| Batched converter (perf rescue for cascade) | #496 |
| P5.1 + P5.2 (distill docs) | #498 |
| P5.3 (PMTiles successor plan commissioned) | #497 |
| P5.4 (`.geojson` retirement plan commissioned) | #499 |
| P5.5 (this archive + ADR flip) | #505 |

All 8 Track A boundary layers (country, state, district, subdistrict, AC, PC, ULB-wards, panchayats) AND both Track A2 layers (villages, postal) ship `.topojson` siblings 100% coverage. Loader topojson-first / geojson-fallback contract live in production via `frontend/src/lib/boundaries.ts`. Conformance test asserts feature-count parity per shard via `frontend/src/contracts/boundaries-conform.test.ts` (4137 assertions green per PR #500 gate).

