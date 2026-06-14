# Admin-level sourcing: how each boundary layer enters yen-gov

**Last Updated**: 2026-05-30

The "what is the canonical upstream for level X" question recurs every time
a new boundary layer is added (panchayats in C.2, ULB wards in C.3,
J&K villages in C.4, blocks before that). This doc distills the answer
into one place so the next agent does not re-litigate the LGD vs
BharatMaps vs Bhuvan choice from first principles. For the WHY of
polygon choropleths over topo rasters and the LGD-golden discipline
itself, see [`boundary-data-philosophy.md`](boundary-data-philosophy.md).
For the architectural decision (one-source-per-level + parallel
orchestrators), see [ADR-0031](../architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy).

## The lineage chain (one diagram fits all levels)

```
LGD Directory (lgdirectory.gov.in)
    -> attribute tables (entity name + parent FK + LGD code), no geometry
        |
        v
BharatMaps (mapservice.gov.in)
    -> live MapServer carrying the geometry per level, joined on LGD codes
        |
        v
ramSeraph/indian_admin_boundaries (GitHub release tags)
    -> static .geojsonl.7z snapshots mirrored periodically, CC0 1.0
        |
        v
yen-gov tools/boundaries/lift_<level>_national.py
    -> per-state hive shards under datasets/boundaries/in/<level>/state=in_<lc>/
```

Three exceptions to the chain matter:

1. **LGD is missing entire states for some levels.** Villages: 8 states
   absent (HP, J&K, Sikkim + 5 NE). Panchayats: ~9 absent (same set).
   Wards (SBM): 4 absent (WB, Tripura, Mizoram, Manipur). Bhuvan
   (ISRO/NRSC, `bhuvan.nrsc.gov.in`) is the Tier-1.5 gap-filler --
   per-state layers sourced from State Revenue Departments under NSDI
   MoUs. C.4 (J&K villages) is the worked example.
2. **Some levels have NO national LGD geometry source.** ULB wards
   come from Swachh Bharat Mission Urban (`sbmurban.org`), not LGD.
   The lineage chain becomes `MoHUA SBM -> ramSeraph -> yen-gov`.
3. **Some levels have multiple parallel sources.** Wards has 4
   candidates (SBM, LivingAtlas, WB-AMRUT, Shillong-CMD). The pick
   rule below resolves which one yen-gov adopts.

## How to pick the canonical source for a new level

The pick is ALWAYS the same shape (verified across C.1 blocks, C.2
panchayats, C.3 wards, C.4 J&K villages):

1. **Prefer the source with direct government lineage** (LGD > BharatMaps
   > MoHUA-direct > Bhuvan/NRSC > LivingAtlas / commercial). This
   minimises the join risk to LGD-keyed indicator parquets.
2. **Prefer the source whose identifier is LGD-keyed** (numeric LGD
   codes joining natively to indicator parquets). LivingAtlas and
   similar commercial harmonisations may re-key features and break
   joins.
3. **Prefer the source matching the publisher of the dominant indicator
   family.** Wards: SBM publishes Swachh Survekshan rankings, so SBM
   ward polygons avoid cross-publisher join risk for the largest
   ward-grain indicator. Same heuristic ruled C.2 (LGD panchayats over
   Bhuvan).
4. **Prefer CC0 1.0 over more restrictive licences.** All current
   adopted sources are CC0 1.0; tighter licences would force per-route
   attribution surfaces that violate the icon-only footer chip
   contract.
5. **Reserve the runner-up as a documented gap-fill or cross-verify
   source.** Adoption of a 2nd parallel source for an existing level
   is a Level-3+ change and must be scoped as its own follow-up PR
   (e.g. C.3.d for SBM's 4 missing states would graduate LivingAtlas
   to Tier-1.5).

## The 3-convention rule (property-name surprise is mandatory)

Every new ramSeraph admin-level layer ships with a DIFFERENT property
naming convention. This is not a quirk -- it is a structural artefact
of the upstream chain (each State Revenue Department or central
publisher chose its own column names before LGD harmonisation existed).
The convention surfaced once per level so far:

| Level | C.x | Property convention | First-snapshot probe required? |
| --- | --- | --- | --- |
| State | n/a | `state_lgd` / `st_name` (long-form LGD) | already locked |
| District | n/a | `dist_lgd` / `dt_name` | already locked |
| Subdistrict | n/a | `subdist_lgd` / `sd_name` | already locked |
| Block | C.1 | `block_lgd` / `bl_name` | locked at C.1.b |
| Panchayat | C.2 | `st_lgd` / `dt_lgd` / `gp_code` / `gp_name` (SHORT-form) | locked at C.2.b |
| Ward | C.3 | `statecode` / `ulbcode` / `wardcode` / `wardname` (concatenated lowercase) | locked at C.3.b |
| Village (LGD) | pre-C | `state_lgd` / `dist_lgd` / `village_lgd` | already locked |
| Village (Bhuvan-JK) | C.4 | TBC at first probe (hypothesis: short-form like Bhuvan portal) | C.4.a |

**The rule**: every new orchestrator (`tools/boundaries/lift_<level>_national.py`
or `lift_<level>_<source>_<state>.py`) MUST start with a first-snapshot
property-name probe before assuming any naming. The probe pattern:

```python
# 1. fetch_geojsonl_7z(url) returns first 5 features
# 2. print(features[0]["properties"].keys()) to see actual names
# 3. lock the names into module-level constants
STATE_PROPERTY = "st_lgd"      # observed, not assumed
DISTRICT_PROPERTY = "dt_lgd"
ID_PROPERTY = "gp_code"
NAME_PROPERTY = "gp_name"
```

Hardcoding the long-form assumption (`state_lgd`/`district_lgd`/...) has
broken three orchestrators in a row (C.1.b, C.2.b, C.3.b). The
constants pattern + first-snapshot probe makes future levels safe.

## Partition shapes by level (what the disk layout looks like)

The partition shape is dictated by the JOIN PARENT, not by file size:

| Level | Partition shape | Why |
| --- | --- | --- |
| State / UT | `state=in_<lc>/all.geojson` | self-keyed |
| District | `state=in_<lc>/all.geojson` | child-array under state |
| Subdistrict | `state=in_<lc>/district=<lgd>/all.geojson` | join parent = district |
| Block | `state=in_<lc>/district=<lgd>/all.geojson` | join parent = district |
| Panchayat | `state=in_<lc>/district=<lgd>/all.geojson` | join parent = district |
| Village | `state=in_<lc>/district=<lgd>/all.geojson` | join parent = district |
| Ward | `state=in_<lc>/ulb=<lgd>/all.geojson` | join parent = ULB (NOT district) |

**Wards are the only level partitioned by ULB, not district.** This is
because the ward's parent in LGD's hierarchy is the urban local body
(`ulb_lgd`), not the district. A district can contain many ULBs; a
ward only ever belongs to one ULB. Citizen drill-down on
`/s/<state>/u/<ulb>/w/<n>` follows the partition.

## Byte-budget + auto-fallback per shard

Every shard is enforced under `SNAPSHOT_BYTE_BUDGET` (currently 16 MB,
declared in `tools/boundaries/snapshot.py`; raised from 12 MB on
2026-06-12 when the per-state AC coord_precision bump from 2 → 4 pushed
UP's 404-AC shard from 1.4 MB to 12.9 MB). High-density shards (UP,
MP, MH panchayats; metro ULB wards) breach the budget at native
precision. The C.1.c pattern from PR #443 (and inherited by C.2.b /
C.3.b / C.4.a) handles this:

1. Emit at `coord_precision=5` (native ~1 metre).
2. If shard > budget, re-emit at `coord_precision=4` (~10 metres).
3. If still over budget, re-emit at `coord_precision=3` (~100 metres).
4. If still over budget, SKIP and record in the parquet ledger.

The `simplification_tolerance_deg` column in the boundaries parquet
records the precision used so consumers can detect simplified shards.
SKIPPED shards surface as missing tiles in the frontend; the citizen
sees a "boundary unavailable" footer. ~10-15% of high-density shards
exercise the fallback path; <1% are SKIPPED in current vintages.

## When to adopt a new admin level (decision filter)

Adoption of a new level is a Level-3+ change requiring schema enum
addition, infrastructure code, lift orchestrator, frontend registry,
and contract tests. The trigger MUST be a citizen indicator that
genuinely needs that grain. Filters in priority order:

1. **Indicator demand**: is there a published indicator family that
   reports at this grain? (panchayats: MGNREGA + PRR; wards: Swachh
   Survekshan; villages: PMGSY + watershed)
2. **Source readiness**: is there a Tier-1 (or Tier-1.5 gap-fill)
   source that ships ALL relevant states or a documented majority?
3. **Citizen UX viability**: can a citizen reasonably navigate the
   density? (panchayats need a district-picker; wards need a
   ULB-picker; villages currently have no surface)
4. **Maintenance budget**: who refreshes when upstream republishes?
   The orchestrator must be re-runnable end-to-end without manual
   stitching.

If any of 1-4 fails, the level stays out of scope until the failing
condition resolves. The C.4 (J&K villages) decision was YES on 1 + 2 +
4 but DEFERRED on 3 (villages have no citizen surface yet); shipping
the disk layer ahead of the surface is OK because villages WILL get a
surface once an indicator demand materialises.

## Known coverage gaps (deferred)

These layers have NO viable upstream polygon source today. Each entry
names the gap, the candidate sources surveyed, the reason none qualify,
and the unblock trigger. Re-evaluate when an upstream release or a
citizen indicator changes the calculus.

- **U09 Ladakh villages** (deferred 2026-05-30 per
  [docs/archive/notes/2026-05-30-u09-ladakh-villages-source-probe-verdict.md](../../docs/archive/notes/2026-05-30-u09-ladakh-villages-source-probe-verdict.md)).
  `Bhuvan_JK_Villages` (used in C.4.a for U08) explicitly excludes
  Ladakh. `LGD_Villages` excludes Ladakh per release notes (alongside
  HP / Sikkim / Meghalaya / Mizoram / Manipur / Nagaland / Arunachal).
  `bhuvan_villages` national release predates the 2019 UT split.
  Census/SOI village-point sources are wrong geometry type. SHRUG
  Census 2011 polygons carry CC-BY-NC-SA (downstream-licensing
  concern) plus pre-2019 vintage requiring hand-curated reassignment.
  MoRD SVAMITVA is property-centroid data, not polygons. Until BOTH
  (a) an upstream-quality polygon source emerges (Bhuvan-Ladakh
  release; LGD coverage expansion; or independent civic source) AND
  (b) a citizen indicator demands village-grain rendering for Ladakh,
  `/s/ladakh` stays at district / UT grain.

- **S03 Assam post-2023 AC polygons** (deferred 2026-05-30 per
  [docs/archive/notes/2026-05-30-s03-furfur-svg-structure-probe-verdict.md](../../docs/archive/notes/2026-05-30-s03-furfur-svg-structure-probe-verdict.md)).
  ECI Delimitation Order 2023 ships as PDF only; no Tier-1 vector
  release exists. The Furfur Wikimedia SVG was probed and found to
  carry only 20 `<path>` elements / 25 subpath-starts (district-shape
  groups, NOT 126 per-AC polygons) plus 132 numeric label-only
  `<text>` nodes. Voronoi tessellation around the labels would
  approximate boundaries at L-XL effort but produce misleading
  geometry without a prominent caveat. S03 currently renders the
  T4 district-polygon fallback with a "boundaries pending post-2023
  delimitation; showing district outlines as interim" tooltip --
  honest about the gap. Election results still bind correctly to
  post-2023 SoT `eci_no` (no join breakage). Unblock when EITHER a
  Tier-1 vector source ships OR Furfur (via Wikimedia talk page)
  shares the AI native file.

## See also

- [`boundary-data-philosophy.md`](boundary-data-philosophy.md) -- the WHY
- [ADR-0031 boundary geometry strategy](../architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy) -- the architectural decision
- [`docs/how-to/add-new-boundary-layer.md`](../how-to/add-new-boundary-layer.md) -- the orchestrator authoring pattern
- [`docs/reference/boundary-data-sources.md`](../reference/boundary-data-sources.md) -- the per-level coverage + licence table
- [`tools/boundaries/README.md`](../../tools/boundaries/README.md) -- pipeline operations
