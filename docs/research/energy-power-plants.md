# Research: Energy — power plants

**Last Updated**: 2026-05-10
**Status**: active — first non-electoral dataset to be ingested (forcing function for D5)

## Question

We need point locations and per-state installed-capacity rollups for power plants in India (coal, gas, hydro, nuclear, renewable). This is the first socio-economic dataset in yen-gov, and shapes every schema decision around indicators + features.

## Candidates

### A. india-geodata `data/energy/power-plants/INDIA_ENERGY_PLANTS.geojson` (chosen for v1)

- URL: <https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main/data/energy/power-plants/INDIA_ENERGY_PLANTS.geojson>
- Metadata: <https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main/data/energy/power-plants/metadata.json>
- Per-feature attributes (per the metadata): plant name, district, state, installed capacity (MW), fuel type.
- Coverage: India national; temporal: **2019**; admin_level: not declared (point data).
- Size: ~128 KB.
- License: **Unspecified** (label kept verbatim per D9).
- Sources declared upstream: Central Electricity Authority (CEA, <https://cea.nic.in/>) — authority "Ministry of Power" — plus secondary aggregator `datta07/INDIAN-SHAPEFILES` (<https://github.com/datta07/INDIAN-SHAPEFILES>).
- Why chosen: smallest viable footprint, demonstrates point + rollup duality, lets us prove the schema and rendering pipeline before chasing fresher data.

### B. Central Electricity Authority direct (planned follow-up)

- Portal: <https://cea.nic.in/> (visited 2026-05-10)
- The CEA publishes a monthly "Installed Capacity Report" (state-wise) and a separate plant register.
- Format: PDF + Excel — no public GeoJSON. Geocoding plant addresses is required.
- Freshness: monthly (vs 2019 in the india-geodata snapshot).
- License: government publication, generally India OGL when explicitly tagged. Confirm at scrape time.
- **Plan**: once v1 ships, build a CEA scraper as `backend/yen_gov/sources/cea/` that produces both an updated indicator (`installed_mw_by_state_by_fuel`) and an enriched feature collection. Lat/long enrichment can lean on the india-geodata coordinates as a starting cross-reference.

### C. `datta07/INDIAN-SHAPEFILES`

- Repo: <https://github.com/datta07/INDIAN-SHAPEFILES>
- The actual upstream of india-geodata's energy GeoJSON. Same license question (unspecified at time of evaluation).
- No advantage over india-geodata for our purposes; do not ingest separately.

### D. Global Power Plant Database (WRI)

- URL: <https://datasets.wri.org/dataset/globalpowerplantdatabase>
- License: CC BY 4.0.
- Pros: globally comparable, well-attributed, includes commissioning dates and ownership.
- Cons: India coverage may be less complete than CEA-derived sources for smaller plants.
- **Tracked**: evaluate in v2 alongside CEA. If WRI is more complete on small renewables, use it as the renewables source; CEA for thermal.

## Decision

**v1 (Phase B)**: ingest india-geodata GeoJSON. Emit two artifacts:

- `datasets/features/in/energy/power-plants.geojson` (+ metadata sidecar with `sources` listing both india-geodata and the upstream CEA URL).
- `datasets/indicators/in/energy/installed_mw_by_state.json` (rolled up by `state` ECI code, optionally faceted by fuel type).

**v2 (post-Phase B)**: CEA scraper as primary; india-geodata becomes a cross-reference for geocoding.

**v3 (later)**: cross-validate against WRI Global Power Plant DB; pick best-of source per fuel category.

## Open follow-ups

- Confirm fuel-type taxonomy (`coal`, `diesel`, `hydro`, `gas`, `nuclear`, `solar`, `wind`, `biomass`) before emitting v1 — derive from the actual GeoJSON properties, do not guess.
- District matching: india-geodata records district names as strings, not LGD codes. Backfill LGD codes through our existing district reference (`datasets/reference/in/states/<S>/districts.json`).
- "Installed MW per capita" choropleth needs a population indicator — flag for the People pillar (Phase D dependency).

## References

- india-geodata raw GeoJSON: <https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main/data/energy/power-plants/INDIA_ENERGY_PLANTS.geojson> (verified accessible 2026-05-10)
- india-geodata metadata: <https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main/data/energy/power-plants/metadata.json> (visited 2026-05-10; full content embedded in [`india-geodata.md`](india-geodata.md))
- CEA portal: <https://cea.nic.in/> (visited 2026-05-10)
- WRI Global Power Plant Database: <https://datasets.wri.org/dataset/globalpowerplantdatabase>
