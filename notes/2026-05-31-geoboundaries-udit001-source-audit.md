# geoBoundaries + udit-001 source audit — NO-GO as canonical boundary source

**Date**: 2026-05-31
**Auditor**: Max (data-shape authority per CLAUDE.md section 0a)
**Verdict**: NO-GO for both candidates as canonical or as render-only layer
**Plan-doc row**: P0.2 of [TODO/20260531-geojson-to-topojson-migration-plan.md](../TODO/20260531-geojson-to-topojson-migration-plan.md)
**ADR**: cross-linked from [docs/architecture/decisions/0047-topojson-as-render-encoding.md](../docs/architecture/decisions/0047-topojson-as-render-encoding.md) Rejected-A + Rejected-B

## 1. Context

User's original source ladder for the GeoJSON-to-TopoJSON migration was:

1. geoBoundaries (`wmgeolab/geoBoundaries`)
2. udit-001 mirror
3. convert existing yen-gov GeoJSON in place

Max was dispatched to audit (1) and (2) before any conversion work began, because adopting an external source as the canonical boundary truth would re-shape every join in `datasets/boundaries/boundary_layers.parquet`. The finding below locked the ladder at option (3): in-place conversion, no external source.

## 2. Canonical-identity contract (what the audit must protect)

Every boundary row in `boundary_layers.parquet` joins to indicator observations via a LGD-issued code (`state_lgd`, `district_lgd`, `subdistrict_lgd`, `village_lgd`, `ulb_lgd`, `panchayat_lgd`) plus the election-side codes (`ac_no`, `pc_no` keyed to delim vintage). Any external source that does NOT carry these codes as feature properties forces either (a) a brittle name-crosswalk join, or (b) an upstream PR with no SLA. Both break Holy Law section 9 (provenance is mandatory; encoding swap MUST NOT change identity surface).

## 3. geoBoundaries audit

**Repository**: `wmgeolab/geoBoundaries` (Williamsburg Geolab, College of William and Mary)
**Coverage**: ADM0-ADM4 for India + global
**Citation by upstream**: ADM2/3/4 cite `lgdirectory.gov.in` as upstream source

**Property set on emitted features** (sampled from `geoBoundariesCGAZ_ADM2.geojson` — district level):

| Property | Type | Example value |
|---|---|---|
| `shapeName` | string | "Anantnag" |
| `shapeISO` | string | "IN-JK" |
| `shapeID` | string | "33954820B72648895593538" |
| `shapeGroup` | string | "IND" |
| `shapeType` | string | "ADM2" |

**Critical finding**: `lgd_district_code` (or any LGD numeric code) is **absent from every feature**. geoBoundaries normalises ALL countries to its universal 5-property schema and drops issuing-authority codes during ingest, EVEN WHEN it cites the LGD as upstream. The `shapeID` is a SHA-derived geoBoundaries-internal ID, not stable across releases.

**Join-key risk**: matching geoBoundaries features to `boundary_layers.parquet` requires either:
- (a) a 780-row name crosswalk (district level) handling Anantnag vs Anantnāg vs Anant Nag, plus post-2007 J&K bifurcation drift (Kulgam from Anantnag, Bandipore from Baramula, etc.), plus Telangana post-2014 churn (creating ~10 new districts), plus annual LGD additions; OR
- (b) an upstream PR to wmgeolab to add `lgd_*_code` to ADM2/3/4. No SLA, no response-time commitment.

**Verdict**: NO-GO as canonical. NO-GO as render-only with frontend lookup (option (b) defers the LGD-strip risk to a brittle runtime join — high engineering cost, no perf upside vs in-place conversion).

## 4. udit-001 audit

**Repository**: `udit-001/india-maps` (hobbyist mirror)
**Coverage**: country + state + per-state district only
**Citation by upstream**: none explicit; appears to be a manual re-publication

**Property set on emitted features** (sampled from `india_district.geojson`):

| Property | Type | Example value |
|---|---|---|
| `district` | string | "Anantnag" |
| `state` | string | "Jammu and Kashmir" |
| `pc` | string | "Anantnag-Rajouri" |

**Critical finding**: same LGD-strip problem at smaller coverage. The `pc` association is hand-curated and out-of-date for post-2021 delim changes. No vintage metadata, no upstream SLA, no provenance ledger.

**Join-key risk**: same as geoBoundaries plus the coverage gap below ADM2.

**Verdict**: NO-GO. Strictly dominated by geoBoundaries (same identity problem, smaller coverage, weaker provenance).

## 5. Decision (locked by user 2026-05-31)

All 10 in-scope boundary layers in the TopoJSON migration plan-doc convert IN-PLACE from existing LGD-keyed GeoJSON. No external source is adopted. The encoding swap (GeoJSON to TopoJSON) is a derivative transform; the canonical `source_id` of each layer is unchanged. `boundary_layers.parquet` rows are byte-identical across the conversion. Holy Law section 9 satisfied: encoding is not provenance (see [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md) and ADR-0047 section Decision item 2).

## 6. Future agents — do not re-litigate

If a future agent proposes adopting geoBoundaries or udit-001 as canonical boundary source, this note is the standing refutation. The refutation holds until either (a) wmgeolab publishes `lgd_*_code` as a first-class feature property AND backfills history, OR (b) udit-001 acquires provenance metadata + LGD codes + an SLA. Neither is on any roadmap as of 2026-05-31.
