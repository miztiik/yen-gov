# Boundary Data Sources

**Last Updated**: 2026-05-10

This is the catalogue and decision record for **geographic boundary data** — state outlines, assembly constituency (AC) polygons, parliamentary constituency (PC) polygons — that the frontend renders as choropleth maps. It is the boundary-data counterpart to [`data-sources.md`](data-sources.md) (which covers election *results* sources).

The pipeline that consumes these sources lives in [`tools/boundaries/`](../../tools/boundaries/README.md); the file-by-file selection is encoded in [`tools/boundaries/pipeline.json`](../../tools/boundaries/pipeline.json).

## In use today

| Layer | Upstream | License | Notes |
| --- | --- | --- | --- |
| India state outlines (z 0–6) | [datameet/maps](https://github.com/datameet/maps) `States/Admin2.{shp,dbf,shx,prj,cpg}` | CC-BY 4.0 | 36 features. Reflects the Telangana split (2014), Ladakh split (2019), and merged Dadra-and-Nagar-Haveli-and-Daman-and-Diu UT. Frontend joins on `ST_NM` via `STATE_NAME_TO_ECI`. |
| AC polygons — TN (S22) | [HindustanTimesLabs/shapefiles](https://github.com/HindustanTimesLabs/shapefiles) `state_ut/tamilnadu/assembly/tamilnadu_AC.json` | MIT | `AC_NO` 1–234. Matches the 2008 Delimitation Order numbering used by ECI for the 2026 cycle. |
| AC polygons — KL (S11) | same repo, `kerala_AC.json` | MIT | `AC_NO` 1–140 |
| AC polygons — WB (S25) | same repo, `westbengal_AC.json` | MIT | `AC_NO` 1–294 |
| AC polygons — AS (S03) | same repo, `assam_AC.json` | MIT | `AC_NO` 1–126. Open question — see [Assam delimitation note](#assam-delimitation-note). |

## Why these choices

### Boundaries are delimitation-bound, not vintage-bound

State and AC polygons change **only when a delimitation order is gazetted**. They do not need refreshing on a calendar cadence. The relevant change events for our scope:

- **Assembly constituencies** for Tamil Nadu, Kerala, and West Bengal were last redrawn by the **2008 Delimitation Order** and have not changed since. Any source publishing those boundaries — whether published in 2017 or 2024 — represents the same gazetted geometry.
- **State boundaries** for India have changed three times since 2010: Telangana (2014), Jammu & Kashmir / Ladakh (2019), and DNH-DD merger (2020). The datameet `States/Admin2` layer reflects all three.
- **Assam ACs** were redrawn by the **2023 Delimitation Commission**; this is the one open boundary question in our scope (see below).

Because of this, "is the upstream still being committed to?" is not the right selection criterion. The right criterion is: "does this file represent the currently-gazetted delimitation, with the property names (`AC_NO`, `ST_NM`) we join on?"

### The Election Commission of India does not publish shapefiles

ECI's interactive results map renders constituency boundaries server-side; it does not expose downloadable shapefiles or GeoJSON. Every open AC dataset on GitHub — including the ones we use and the ones we evaluated — ultimately traces back to scrapes of ECI's polling-station-locator pages, the Local Government Directory (LGD), or academic releases (Susewind 2014). There is no first-party ECI vector boundary feed to switch to.

### Per-state files beat single-India files

HTL ships one file per state, ~1 MB each. A single all-India AC file is ~10 MB and forces every state page to download every state's geometry. Per-state PMTiles also let CI rebuild only the changed state when one needs replacing.

## Sources evaluated, not adopted (yet)

We track these alternatives so the next "is there a better source?" question has a reusable answer.

### [yashveeeeeeer/india-geodata](https://github.com/yashveeeeeeer/india-geodata)

A unified, actively-maintained catalogue of openly-licensed Indian geospatial data — administrative boundaries, electoral boundaries, census, environment, water, infrastructure, healthcare, education, urban data. Ships in modern formats (Parquet, PMTiles, GeoJSONL, Shapefile) via GitHub Releases. Browsable at <https://yashveeeeeeer.github.io/india-geodata/>.

For our **boundary** use case it is a candidate, not a switch. The reasons we have not adopted it for ACs **today** are operational, not qualitative:

1. **The upstream chain ends at the same places we already use.** Their AC release aggregates DataMeet's national `India_AC.shp` (national/) and a per-state ECI scrape (eci-statewise/`S{nn}_AC.{shp,dbf,shx}`) plus an LGD-derived release. The eci-statewise files are the same family as the HTL per-state files we already consume, repackaged. There is no third-party redraw happening; only re-aggregation.
2. **Their per-state AC files do not document a property schema.** We join the frontend choropleth on `AC_NO` (HTL) and `ST_NM` (datameet states). Switching requires confirming the property names and the AC numbering convention in each `S{nn}_AC.dbf` match what `frontend/src/lib/maplibre/sources.ts` and `pipeline.json` expect. Until that audit happens, swapping is a regression risk for zero functional gain on TN/KL/WB.
3. **The Assam decision can move first.** The one place a switch is *worth* doing is Assam (S03), where HTL likely predates the 2023 Delimitation Commission redraw. Their LGD release (see next section) is the candidate worth checking.

When we adopt it, the natural integration is per-layer (e.g. only Assam ACs) by adding a new entry to [`pipeline.json`](../../tools/boundaries/pipeline.json) — not a wholesale swap.

#### What "LGD release" means

LGD = **Local Government Directory**, the public registry of administrative units maintained by the Ministry of Panchayati Raj (<https://lgdirectory.gov.in/>). It assigns stable numeric codes to every state, district, sub-district, block, panchayat, village, and assembly constituency in India. Where LGD publishes geometry for an AC, that geometry is *the* government-of-India administrative reference for that constituency.

The yashveeeeeeer/india-geodata electoral release packages an `LGD_Assembly_Constituencies.{parquet,pmtiles,geojsonl.7z}` artifact under CC0. This is a different lineage from the HTL files we use today (which trace to ECI scrapes). For a state where the two disagree — like post-redraw Assam — LGD is the authoritative tiebreaker.

This **does not** mean LGD is silently better for states whose boundaries have not changed. For TN/KL/WB the two lineages should produce geometrically identical polygons modulo simplification.

### Other repositories evaluated

| Repo | What it offers | Why not adopted now |
| --- | --- | --- |
| [datameet/maps](https://github.com/datameet/maps) `assembly-constituencies/India_AC.shp` | Single all-India AC shapefile | Per-state HTL files give better request granularity and frontend joins. We already use datameet for state outlines. |
| [datta07/INDIAN-SHAPEFILES](https://github.com/datta07/INDIAN-SHAPEFILES) | Pan-India admin and constituency GeoJSON; actively maintained | Repo's own README states "Data Vintage: Primarily 2019". For TN/KL/WB this is the same gazetted geometry as our current source; for Assam it predates the 2023 redraw. No advantage at present. |
| [GaneshKathar/india-geojson](https://github.com/GaneshKathar/india-geojson) | Listed in GitHub search | Repository is empty. |
| OpenStreetMap relations | Live, community-edited | AC coverage uneven across states; would require validation per state per delimitation cycle. Worth keeping as a cross-check, not a primary source. |
| Survey of India digital products | Authoritative national mapping | Not openly licensed for redistribution in our context. |

## Other yashveeeeeeer/india-geodata datasets worth tracking

The same project catalogues many non-boundary datasets that are out of scope for the *boundary* pipeline but may be relevant to future yen-gov features (constituency-level enrichment, contextual layers, etc.). Recording them here so we don't re-research:

| Category | Datasets of likely interest |
| --- | --- |
| Healthcare | NIC HealthGIS public health facility locations (PHCs, CHCs, hospitals) |
| Education | Schools, colleges, universities, kindergartens (OSM-derived, ODbL) |
| Census | 2011 admin units; historical district series 1951–2024 |
| Remote sensing | District-level VIIRS nighttime lights (2012–2024); WorldPop 2020 1 km population density |
| Infrastructure | National highways, railways, PMGSY rural roads, ML-detected roads (Microsoft + Facebook) |
| Urban | Municipal ward boundaries for 28 cities; AMRUT slum boundaries |
| External link | SHRUG — socioeconomic data for 500K+ villages |

These are listed for awareness, not as decisions. Any future use of them goes through the same path as boundary sources: schema, license, identifier-join story, then a `pipeline.json`-equivalent entry under the appropriate tool.

## Assam delimitation note

The Assam Legislative Assembly was redelimited by the Delimitation Commission's order of 2023 (effective for elections after that date). Our current Assam AC source predates that order; it carries the older `AC_NO` 1..126 numbering and may have boundary differences against the 2023 layout.

The mitigation in [`pipeline.json`](../../tools/boundaries/pipeline.json) is the `delimitation_warning` field on the `S03` entry, plus the cross-check requirement in [`tools/boundaries/README.md`](../../tools/boundaries/README.md#assam-delimitation-caveat) — every `AC_NO` 1..126 in the simplified GeoJSON must match the corresponding constituency name in [`datasets/reference/in/states/S03/constituencies.json`](../../datasets/reference/in/states/S03/constituencies.json) before the boundaries PR can merge.

When Assam falls inside an election cycle yen-gov is publishing, the yashveeeeeeer/india-geodata `LGD_Assembly_Constituencies` release is the first candidate to evaluate for replacement, on the lineage rationale described above. Until then, the warning stays and the file ships as-is.

## Adding a new boundary source — the bar

Before any new source is added to [`pipeline.json`](../../tools/boundaries/pipeline.json):

1. **License compatibility.** MIT, CC-BY 4.0, CC0, GODL-India, India OGL — all fine. Check the upstream `LICENSE` file directly, not a third-party summary.
2. **Property schema.** Document which property carries the join key (`AC_NO`, `ST_NM`, etc.) and confirm `frontend/src/lib/maplibre/sources.ts` already handles it (or add a mapping). Boundary files with no stable join key are not usable.
3. **Delimitation alignment.** State which delimitation order's geometry the file represents. If unknown, treat as unverified.
4. **Provenance.** The `manifest.json` carries one `{ url, fetched_at }` per packed file (CLAUDE.md §12). Permanent URLs only — no signed/time-limited links.
5. **Size sanity.** A simplified per-state AC PMTiles file should land in the low hundreds of kB. If it balloons, revisit `coord_precision` and the tippecanoe simplification settings before committing.

## See also

- [`tools/boundaries/README.md`](../../tools/boundaries/README.md) — operational reference (how to run the pipeline, source format dispatch)
- [`docs/architecture/frontend/map.md`](../architecture/frontend/map.md) — how the frontend consumes the PMTiles
- [`docs/concepts/disclaimer.md`](../concepts/disclaimer.md) — user-facing wording for boundary attribution
- [`docs/reference/data-sources.md`](data-sources.md) — election-results sources (sister catalogue)
- CLAUDE.md §11 (schema versioning), §12 (provenance)
