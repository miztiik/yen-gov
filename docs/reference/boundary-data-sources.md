# Boundary Data Sources

**Last Updated**: 2026-05-13

This is the catalogue and decision record for **geographic boundary data** — state outlines, assembly constituency (AC) polygons, parliamentary constituency (PC) polygons, district polygons — that the frontend renders as choropleth maps. It is the boundary-data counterpart to [`data-sources.md`](data-sources.md) (which covers election *results* sources).

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

## Source-selection policy: gap-fill, not bulk-swap

The yen-gov rule for any third-party boundary catalogue we evaluate (ramSeraph, yashveeeeeeer/india-geodata, etc.) is the same:

1. **Keep what already works.** State outlines (datameet) and the 28 HTL AC layers we ship today are correct for the gazetted geometry they cover. We do not wholesale-replace them just because a newer aggregator exists — every swap is a regression risk and an attribution churn for zero functional gain.
2. **Adopt only to fill a real gap.** A "gap" is one of: (a) a layer we don't have at all (e.g. district polygons), (b) a state where the layer we have is known stale against current delimitation (e.g. Assam post-2023), or (c) an identifier registry we need but haven't ingested (e.g. LGD codes for districts).
3. **Track the rest as catalogue.** Layers a third-party publishes that overlap our existing coverage are recorded below for the record, with explicit "why we don't switch" notes — so the next person asking "shouldn't we use X?" finds the answer.

The two `pipeline.json` arrays codify this: `inputs` is what actually builds today; `staged_inputs` (added 2026-05-13) holds gap-fill entries that are ready to drop into `inputs` when the corresponding feature ships and any required format handler exists.

## Sources evaluated, not adopted (yet)

We track these alternatives so the next "is there a better source?" question has a reusable answer.

### [ramSeraph/indian_admin_boundaries](https://github.com/ramSeraph/indian_admin_boundaries)

A single, actively-maintained catalogue of Indian administrative boundary data, organised as one GitHub Release per layer. Every release ships `.geojsonl.7z` (newline-delimited GeoJSON inside a 7z archive); the LGD-derived ones carry stable LGD codes as feature properties. License across all releases: **CC0 1.0 with attribution requested for datameet and the original government publisher** ([`indianopenmaps/DATA_LICENSE.md`](https://github.com/ramSeraph/indianopenmaps/blob/main/DATA_LICENSE.md)).

Decision per release tag, applying the gap-fill policy above:

| Release | Lineage / source URL | yen-gov use today | Decision |
| --- | --- | --- | --- |
| `states` (`LGD_States`, `bhuvan_states`, `SOI_States`) | LGD/Bharatmaps, Bhuvan, Survey of India | datameet `Admin2` already in use | **Catalogue only.** Equivalent geometry; switching would churn `STATE_NAME_TO_ECI` joins for no functional gain. Worth a future audit if datameet ever stops reflecting a reorganisation. |
| `districts` (`LGD_Districts`, `bhuvan_districts`, `SOI_Districts`) | same three lineages | **none — no district polygon layer in `pipeline.json`** | **Adopt to fill the gap.** `LGD_Districts` is the natural pick (carries LGD codes — joins directly to our `district.lgd_code` field per [ADR-0015](../architecture/decisions/0015-constituency-hierarchy-fields.md)). Staged entry in `pipeline.json#staged_inputs`; activate when the first district choropleth ships. |
| `constituencies` (`LGD_Assembly_Constituencies`, `LGD_Parliament_Constituencies`, Susewind 2014 AC/PC) | BharatMaps `mapservice.gov.in/.../AC_PC` for LGD; Susewind 2014 academic dataset | 28 states already from HTL per-state files | **Catalogue + tiebreaker.** For TN/KL/WB/etc. the HTL files we ship match the same gazetted geometry. Use `LGD_Assembly_Constituencies` only as the **Assam tiebreaker** (see [Assam delimitation note](#assam-delimitation-note)) and as the candidate when any other state is redelimited. PC polygons are not yet a yen-gov surface; revisit when a Lok Sabha cycle is in scope. |
| `subdistricts` / `blocks` / `panchayats` / `villages` / `habitations` | LGD/Bharatmaps | none | **Catalogue only.** No yen-gov consumer today. Reconsider if a PRI / scheme-delivery panel ships. |
| `urban` | LGD ULBs / wards | none | **Catalogue only.** Becomes interesting when ULB-level governance data ships. |
| `forests` / `coastal` / `goa_crz` | Forest Survey of India, MoEFCC CRZ, Goa CRZ georef | none | **Out of scope** for the governance-indicators surface. |
| `postal` / `police` | India Post pincodes, state police jurisdictions | none | **Out of scope.** |
| `census-2011` | Census 2011 admin units | none today; relevant when census indicators ship | **Catalogue.** Will become a gap-fill candidate when we wire census-2011 indicators that need polygon joins. |
| `historical` | Historical district boundaries (multi-vintage) | none | **Catalogue.** Unique offering — nobody else publishes this cleanly. Adopt only when a historical-comparison feature is on the roadmap. |

What we are explicitly **not** doing: bulk-importing every release "because it's there." Each adoption is a separate `pipeline.json` change in the same PR as the consuming feature, with its own provenance sidecar.

#### Format gap: `geojsonl.7z`

ramSeraph ships `.geojsonl.7z`, which `tools/boundaries/snapshot.py` does not yet handle (it knows `geojson` and `shp_bundle`). Activating any entry from `pipeline.json#staged_inputs` requires a one-time addition to `materialize_input()`: 7z-extract → NDJSON → wrap features into a `FeatureCollection`. Tracked here rather than as a separate ticket so it's discovered when someone tries to activate a staged entry.

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

When Assam falls inside an election cycle yen-gov is publishing, the LGD AC release is the first candidate to evaluate for replacement — available from either [`ramSeraph/indian_admin_boundaries#constituencies`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/constituencies) (`LGD_Assembly_Constituencies.geojsonl.7z`) or yashveeeeeeer/india-geodata. Both repackage the same BharatMaps lineage; pick whichever has the more recent `fetched_at` at decision time. Until then, the warning stays and the file ships as-is.

## Adding a new boundary source — the bar

Before any new source is added to [`pipeline.json`](../../tools/boundaries/pipeline.json):

1. **License compatibility.** MIT, CC-BY 4.0, CC0, GODL-India, India OGL — all fine. Check the upstream `LICENSE` file directly, not a third-party summary.
2. **Property schema.** Document which property carries the join key (`AC_NO`, `ST_NM`, etc.) and confirm `frontend/src/lib/maplibre/sources.ts` already handles it (or add a mapping). Boundary files with no stable join key are not usable.
3. **Delimitation alignment.** State which delimitation order's geometry the file represents. If unknown, treat as unverified.
4. **Provenance.** The `manifest.json` carries one `{ url, fetched_at }` per packed file (CLAUDE.md §12). Permanent URLs only — no signed/time-limited links.
5. **Size sanity.** A simplified per-state AC PMTiles file should land in the low hundreds of kB. If it balloons, revisit `coord_precision` and the tippecanoe simplification settings before committing.

## Related ecosystem sources (not boundary-pipeline)

The two siblings of `ramSeraph/indian_admin_boundaries` are tracked here so the next "can we use this?" question has a recorded answer.

### LGD identifier registry — [`ramseraph.github.io/opendata/lgd/`](https://ramseraph.github.io/opendata/lgd/)

Daily 7z archives of every Local Government Directory entity table (37 components — states, districts, sub-districts, blocks, ACs, PCs, PRI/ULB bodies and wards, villages, pincode mappings, etc.). The mirror's tables side, sibling to the geometry-side `ramSeraph/indian_admin_boundaries` catalogued above. **Not a boundary source — no geometry — but the canonical issuer of `lgd_code`** which our [`district.schema.json`](../../datasets/schemas/district.schema.json) and [ADR-0015](../architecture/decisions/0015-constituency-hierarchy-fields.md) treat as the preferred district id.

Full component catalogue, URL pattern, archive lifecycle, and per-component adoption verdict: **[lgd-opendata.md](lgd-opendata.md)**. Ingestion will live under `tools/lgd/`, not `tools/boundaries/`; out of scope for `pipeline.json`. Listed here because the user-facing question ("what about ramSeraph?") spans both.

### Topographic raster basemaps — [`ramSeraph/india_topo_maps`](https://github.com/ramSeraph/india_topo_maps)

Survey of India 1:50k (Open Series Maps), 1:25k (NHP), 1:5k (CMPDI) topographic sheets, georeferenced and packed as raster PMTiles + tile-server URLs. **Out of scope for yen-gov.** We render administrative-boundary choropleths, not terrain — these PMTiles are raster basemap tiles (hillshade / contours), not the vector polygons our renderer joins to indicator data. Pulling them would balloon the static bundle for zero citizen-visible value. Recorded here so the question is answered.

## See also

- [`tools/boundaries/README.md`](../../tools/boundaries/README.md) — operational reference (how to run the pipeline, source format dispatch)
- [`docs/architecture/frontend/map.md`](../architecture/frontend/map.md) — how the frontend consumes the PMTiles
- [`docs/concepts/disclaimer.md`](../concepts/disclaimer.md) — user-facing wording for boundary attribution
- [`docs/reference/data-sources.md`](data-sources.md) — election-results sources (sister catalogue)
- [`docs/reference/lgd-opendata.md`](lgd-opendata.md) — LGD tables (identifier registry) catalogue
- CLAUDE.md §11 (schema versioning), §12 (provenance)
