# Boundary data philosophy

**Last Updated**: 2026-05-26

The "why" behind yen-gov's boundary-data choices. The "what" (current
inventory, per-level coverage, license rows, identifier discipline) lives
in [docs/reference/boundary-data-sources.md](../reference/boundary-data-sources.md);
the operational pipeline lives in
[tools/boundaries/README.md](../../tools/boundaries/README.md); the
architectural decisions are recorded in
[ADR-0031](../architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy).
This doc explains the recurring reasoning -- the questions an agent
keeps asking ("can we use GADM?", "what about the topo maps?", "is
DIGIPIN on the roadmap?", "why are 20 states still on HTL?") -- once,
in one place, so the reference docs and plan-docs can link here instead
of re-litigating.

## Why polygons, not topographic raster

yen-gov renders administrative-boundary **choropleths**: polygons
coloured by an indicator value (`/t/fiscal`, `/s/<state>/t/elections`,
the per-state AC map). The renderer is
[`frontend/src/lib/IndicatorChoropleth.svelte`](../../frontend/src/lib/IndicatorChoropleth.svelte);
it joins observation rows to polygon `properties` by an LGD or ECI key.
A choropleth is a polygon-fill operation, not a terrain render.

We do **not** render terrain. There is no hillshade, no contour layer,
no elevation tint, no satellite basemap. That capability adds nothing to
the citizen question yen-gov answers ("how is my state doing on
indicator X?") and would balloon the static bundle by an order of
magnitude.

`ramSeraph/india_topo_maps` packages the Survey of India 1:50k (Open
Series Maps), 1:25k (NHP), and 1:5k (CMPDI) topographic sheets as
georeferenced raster PMTiles. They are valuable for hiking-app builders,
terrain analysts, and survey workflows -- but the bytes they ship are
raster pixel data, not the vector polygons our renderer joins to
indicator rows. Adopting them would be a strict regression on the
static-bundle weight (Holy Law #1) for zero citizen-visible win.

Recorded so the next "should we pull india_topo_maps?" question has a
written no.

## TopoJSON adoption status

TopoJSON is a **different thing** from topographic raster, despite both
names starting with "topo". TopoJSON is a vector format -- the same
polygon geometry as GeoJSON, but with three byte-level optimisations:

- **Shared arcs.** A border that two adjacent polygons share (e.g. the
  Maharashtra-Gujarat state line) is stored once and referenced twice.
  GeoJSON duplicates it once per polygon ring.
- **Coordinate quantisation.** Lat/lng floats are converted to small
  integers plus a `{scale, translate}` header. 6-decimal floats become
  4-5 digit integers.
- **Single properties block.** Feature `properties` is declared at the
  top level once instead of per-ring.

Net: 3-5x smaller wire bytes for the same polygons. Lossless when
decoded by `topojson-client.feature()` -- the consumer gets a standard
GeoJSON `FeatureCollection` back.

**Status**: planned, not shipped. Plan-doc:
[TODO/20260525-topojson-frontend-perf-plan.md](../../TODO/20260525-topojson-frontend-perf-plan.md).
Phases: P0 prove -> P1 write `quantize.py` alongside GeoJSON -> P2 read
branch in `boundaries.ts` -> P3 swap states + districts shards + retire
the matching GeoJSON via `git rm` -> P4 measure 4G-slow paint on
`/t/fiscal` before merge -> P5 hold (per-state subdistrict and
per-(state, district) village shards stay on GeoJSON; PMTiles is still
the long-term wire). Frontend renderers (MapLibre) and join keys
(`State_LGD`, `dist_lgd`) are unchanged by this swap -- the conversion
happens upstream of `addSource()`.

When a future agent asks "why are we shipping multi-MB GeoJSON when
NDLM ships 926 KB TopoJSON for the same district set?", the answer is:
we know; the swap is queued at the plan-doc above.

## GADM rejection rationale

[GADM](https://gadm.org/) (Global Administrative Areas) is a widely
catalogued international boundary dataset. yen-gov does **not** use
GADM as a source, today or planned. Four reasons, in order of weight:

1. **Disputed-territory polygons.** GADM's India dataset includes
   features that carry China/Pakistan-claimed slices in their `_1.json`
   state-level geometry (5 of 41 features). For an Indian-government-
   citizen site, shipping a boundary file that encodes contested
   geography in the polygon shape is a non-starter regardless of the
   other concerns.
2. **License blocks static-bundle redistribution.** GADM's terms
   reserve commercial / redistribution rights; the static-site bundle
   yen-gov publishes to GitHub Pages does not meet the "non-commercial
   academic use" qualifier cleanly. Per Holy Law #1 (static-first
   production) and CLAUDE.md "open source first", we adopt only
   sources that allow unencumbered redistribution as part of a
   compiled static bundle. Datameet (CC-BY-4.0), ramSeraph (CC0-1.0
   with attribution requested), and shijithpk (Unlicense) all clear
   this bar; GADM does not.
3. **Identifier mismatch.** GADM uses HASC codes (`IN.TN`, `IN.AP`).
   yen-gov keys every administrative join on LGD codes (for
   districts, sub-districts, blocks, villages, ACs, PCs) per
   [identifiers.md](../reference/identifiers.md). Adopting GADM would
   force a name-normalisation translator the rest of the pipeline does
   not need.
4. **Stale.** GADM v4.1 (the current release) has not been refreshed
   for the post-2019 Ladakh split, the post-2014 Telangana split, or
   the merged DNH-DD UT. The currently-shipped datameet `Admin2`
   layer carries all three.

What we use instead, by level:

- **Country outline**: yashveeeeeeer/india-geodata (SoI-derived,
  CC-BY-4.0).
- **States and UTs**: ramSeraph `LGD_States` (CC0-1.0, attribution
  requested).
- **Districts**: ramSeraph `LGD_Districts` (CC-BY-4.0).
- **Sub-districts and villages**: ramSeraph `LGD_Subdistricts` +
  `LGD_Villages` (CC-BY-4.0).
- **Assembly Constituencies**: 10 ramSeraph `LGD_Assembly_Constituencies`
  states (post-Phase-D.2) + 20 HTL states + 1 shijithpk J&K.
- **Parliamentary Constituencies**: shijithpk 2024 delimitation (1 file,
  545 features).
- **Pincodes**: Department of Posts via data.gov.in OGD All-India
  Pincode Boundary (GODL-IN).

When a future agent re-asks "can we just pull GADM for the missing
states?", the answer is no -- the reasons above are structural, not
preferences, and re-litigating them is descoped per
[TODO/20260524-boundary-coverage-expansion-plan.md](../../TODO/20260524-boundary-coverage-expansion-plan.md)
section "Not in this plan (descoped)".

## DIGIPIN deferral

[DIGIPIN](https://www.indiapost.gov.in/VAS/Pages/digipin.aspx) is the
Department of Posts' geocoding system: a 10-character alphanumeric code
that encodes a 4 m x 4 m grid cell anywhere in India. It is a
**point/grid system at postal-address precision**, not a polygon
family.

DIGIPIN is **not on the boundary-coverage roadmap**. Two reasons:

1. **It is not a polygon family.** yen-gov's renderer joins observation
   rows to polygon shapes via LGD or ECI keys. A 4 m x 4 m grid cell
   has no LGD code, no polygon spine, and no entity in
   `datasets/taxonomy/entities.parquet`. Adopting DIGIPIN would need a
   separate point/grid handler -- a different code path than the
   choropleth pipeline.
2. **No citizen need at present.** Today no yen-gov route asks
   "tell me about this 4 m square". Every indicator family
   (elections, fiscal, energy, health, agriculture, livestock) is
   keyed at state, district, sub-district, or village granularity.
   The DIGIPIN handler stays unbuilt until the citizen need exists.

**Re-evaluation trigger**: when a delivery-address-precision feature
becomes a citizen need -- for example a `/p/<digipin>` route that
returns the LGD district, the ECI AC, and the nearest pincode for a
DIGIPIN code -- this section flips to "queued" and a new plan-doc
opens. Until then, DIGIPIN is acknowledged out-of-scope.

## HTL not done versus HTL deliberately kept

A common misread of [docs/reference/boundary-data-sources.md](../reference/boundary-data-sources.md)
section "Per-level gaps" row "AC" is that the 20 states/UTs still on
HTL (HindustanTimesLabs/shapefiles) are pending TODO work that has not
yet shipped. They are not. The 20 HTL states are **deliberately kept
on HTL** per the Phase D.1 recon verdict.

Phase D of the
[boundary-coverage-expansion plan](../../TODO/20260524-boundary-coverage-expansion-plan.md)
runs as follows. The ramSeraph `LGD_Assembly_Constituencies` release
is the consolidation candidate for AC layers; D.1 (recon, per state)
parity-checks ramSeraph against the existing HTL polygons on two
gates:

- **Name-match parity.** At least 95% of HTL `AC_NAME` entries must
  resolve cleanly against the ramSeraph `AC_NAME` for the same state.
- **Feature-count drift tolerance.** The feature count delta must
  not exceed the documented per-state tolerance.

A state that passes both gates is **promoted** to ramSeraph in Phase
D.2 (the swap PR per the gap-fill-not-bulk-swap policy). A state that
fails either gate **stays on HTL until upstream publishes a refreshed
delim that matches the post-current-delimitation layout**. Phase D.1
authorised 10 promotions and pinned 20 to HTL with documented reasons.
HTL is therefore the current best-fit source for those 20 states, not
a placeholder.

Same pattern, two carve-outs:

- **S03 Assam**: D.3 carve-out. LGD-parity score was 1% (catastrophic
  name-match miss); ramSeraph's S03 layout does not cleanly reflect
  the post-2023 delim. S03 stays on HTL with the `delimitation_warning`
  on `pipeline.json` flagging the post-2008 mismatch; HTL is the
  best-fit source available today.
- **U08 Jammu and Kashmir**: D.4 carve-out. The ramSeraph snapshot
  carries the pre-2019 layout (87 ACs); the citizen-facing rendering
  needs the post-2022 90-AC layout from the Delimitation Commission.
  U08 stays on shijithpk's `j_and_k_assembly_new_borders` (Unlicense,
  90 features, 2022 delim).

Final per-state AC layer ledger: **10 ramSeraph + 20 HTL + 1 shijithpk
= 31 elective state/UT AC layers**. The same five states/UTs without an
elective assembly (Chandigarh, DNH-DD, Lakshadweep, Andaman, Ladakh)
have no per-state AC layer because they have no assembly to depict.

**Re-evaluation trigger** for the 20 HTL states + Assam carve-out: when
ramSeraph upstream publishes a refreshed AC delim that passes the D.1
parity gates, the affected state(s) flip to "promotion candidate" and
go through Phase D.2 / D.5. Until that upstream refresh lands, the
status is "kept on HTL on purpose", not "pending TODO".

## See also

- [docs/reference/boundary-data-sources.md](../reference/boundary-data-sources.md)
  -- the live coverage ledger + identifier catalogue + per-level
  source rows.
- [docs/architecture/data/boundaries.md](../architecture/data/boundaries.md)
  -- subsystem doc (disk topology, identifier discipline, methodology
  breaks).
- [docs/architecture/frontend/map.md](../architecture/frontend/map.md)
  -- how the frontend consumes the boundary layers via MapLibre.
- [docs/architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy](../architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy)
  -- the ADR establishing boundary geometry as a sibling family
  (GeoJSON + PMTiles) outside the canonical Parquet store, plus the
  T.0d amendment introducing `boundary_layers.parquet`.
- [tools/boundaries/README.md](../../tools/boundaries/README.md) --
  the operational pipeline + source format dispatch.
- [TODO/20260524-boundary-coverage-expansion-plan.md](../../TODO/20260524-boundary-coverage-expansion-plan.md)
  -- the phased coverage-gap closure plan (Phase A pincode through
  Phase E Census 2011 polygons).
- [TODO/20260525-topojson-frontend-perf-plan.md](../../TODO/20260525-topojson-frontend-perf-plan.md)
  -- the queued TopoJSON adoption plan referenced in the
  "TopoJSON adoption status" section above.
- [docs/concepts/disclaimer.md](disclaimer.md) -- the user-facing
  wording for boundary attribution and the doctrine on what we will
  and will not say about contested geographies.
