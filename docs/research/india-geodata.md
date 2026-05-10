# Research: india-geodata aggregator

**Last Updated**: 2026-05-10
**Status**: active — primary upstream for several non-electoral layers

## Question

Is [`yashveeeeeeer/india-geodata`](https://github.com/yashveeeeeeer/india-geodata) a stable, attributable upstream we can lean on for socio-economic and infrastructure layers, or do we go directly to the original government portals each time?

## Candidates

### A. india-geodata (chosen for first ingest)

- Repo: <https://github.com/yashveeeeeeer/india-geodata>
- License (overall): CC BY 4.0; per-dataset licenses live in each `metadata.json`.
- Coverage: 14 categories across ~1,800 files. Small files in-repo, large in GitHub Releases (one tag per dataset).
- Format mix: GeoJSON, Parquet, PMTiles, GeoJSONL, Shapefile, CSV, GeoTIFF, KML.
- Per-dataset metadata schema is exemplary — `name`, `title`, `description`, `category`, `level`, `coverage{spatial, temporal, admin_level}`, `sources[]{name, url, authority}`, `license{id, name, url}`, `formats[]`, `coordinate_system`, `storage{repo_files, release_tag}`, `last_updated`. We adopted this vocabulary additively into our own schemas (D3 in the umbrella plan).
- Maintained by an individual (Yashveer Singh, +2 contributors). 50 stars, 6 forks at the time of evaluation. Small but organised.
- Attribution: required by CC BY. We carry it via the `sources[].authority` field on emitted artifacts and a "Data sources" section on the relevant frontend pages.

### B. Original government portals (secondary, layered in over time)

- e.g. CEA for power, NIC HealthGIS for hospitals, MoSPI for census, RBI for state finances, Survey of India for boundaries.
- Pros: authoritative, no intermediary, license usually clearer (India OGL or public domain).
- Cons: heterogeneous formats, frequent re-organisation of URLs, often only PDF/Excel — non-trivial scrape per source.
- We **layer these in** when (i) the upstream we used reports "Unspecified" license, (ii) the data freshness lags significantly, or (iii) we need a field india-geodata didn't extract.

### C. Other aggregators (DataMeet, ramSeraph, planemad)

- These are upstream of india-geodata for specific subtrees. We can swap to them directly if india-geodata becomes stale or if we need their original release cadence.
- Tracked dataset-by-dataset, not adopted wholesale.

## Decision

Use india-geodata as the **first-pass upstream** for a new non-electoral layer when it covers it. Always:

1. Carry `india-geodata` URL **and** the underlying authority in `sources[]` (two entries, both with `fetched_at`).
2. Cite the per-dataset license in `metadata.license`. Never coerce "Unspecified" to a stronger claim.
3. Plan a "go to original" follow-up the moment the layer is in production. The follow-up is captured in the per-dataset research note, not promised in code comments.

## Open follow-ups

- Pin to a specific commit SHA when we ingest, so re-runs are reproducible. (Their large files are in releases; small files in-repo — both have stable refs.)
- Evaluate whether `electoral/` (AC + PC GeoJSONs) replaces what `tools/boundaries/` currently builds. Tracked in the umbrella plan as D7.
- Watch for license clarification in upstream metadata — request via PR if dataset is `Unspecified` but license is plainly present in source materials.

## References

- Repo README: <https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main/README.md> (visited 2026-05-10)
- Power-plants metadata example: <https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main/data/energy/power-plants/metadata.json> (visited 2026-05-10)
- License: <https://creativecommons.org/licenses/by/4.0/>
