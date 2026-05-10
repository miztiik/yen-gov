# Research: Healthcare facilities

**Last Updated**: 2026-05-10
**Status**: planned — Phase E

## Question

Where does the canonical list of public health facilities (PHCs, CHCs, district hospitals, sub-centres) in India live? We need point locations + per-state rollups for the Infrastructure pillar.

## Candidates

### A. NIC HealthGIS via `planemad/india_health_facilities`

- Repo: <https://github.com/planemad/india_health_facilities>
- License: India OGL (declared by the maintainer).
- Coverage: PHCs, CHCs, district hospitals; ~47 MB GeoJSON.
- Re-published through india-geodata (`data/healthcare/facilities/`).
- Why this is likely v1: clean GeoJSON, attributable, OGL.

### B. NIC HealthGIS portal directly

- Portal (when available): hosted by Ministry of Health & Family Welfare via NIC.
- Authoritative; refresh cadence unclear from upstream documentation. Worth a focused investigation when v1 lands.

### C. data.gov.in

- Some health-facility datasets republished there; coverage usually a subset.

### D. OpenStreetMap (Humanitarian OpenStreetMap exports)

- Pros: globally comparable; volunteer-validated where active.
- Cons: India coverage uneven; tag conventions vary by region.
- Use as a cross-reference, not primary.

## Decision (provisional)

**v1**: ingest `planemad/india_health_facilities` via india-geodata as the GeoJSON, emit:

- `datasets/features/in/healthcare/facilities.geojson` (+ metadata sidecar).
- `datasets/indicators/in/healthcare/facilities_per_100k_by_state.json` — needs population (Phase D dependency, see [`state-gdp-rbi.md`](state-gdp-rbi.md) and a still-to-be-written `population.md`).

**v2**: directly poll NIC HealthGIS for refreshed coordinates; OSM as a cross-validation pass.

## Open follow-ups

- Facility taxonomy: PHC / CHC / DH / sub-centre / specialty hospital — confirm the `kind` enum from upstream properties, do not invent.
- Public vs private: this dataset is *public* facilities only. A private-hospital dataset is a separate concern; flag if needed.
- Bundle size: 47 MB is the boundary of what we'd lazy-load. Plan: split per state at emit time so the frontend pulls only the active state's facilities.

## References

- planemad upstream: <https://github.com/planemad/india_health_facilities>
- india-geodata mirror: <https://github.com/yashveeeeeeer/india-geodata/tree/main/data/healthcare/facilities>
