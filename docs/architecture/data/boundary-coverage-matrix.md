# Boundary coverage matrix

**Last Updated:** 2026-06-01
**Tracked by:** [`docs/archive/plans/20260601-lgd-execution-handover.md`](../../../docs/archive/plans/20260601-lgd-execution-handover.md) (updated whenever a layer/state ships)

This document answers: **at every administrative granularity, which states and union territories have geometry and which are gaps.** It is the canonical inventory.

## Administrative hierarchy (LGD-canonical)

```
country (1)
  states / UTs (37 - 28 states + 8 UTs + 1 Ladakh aggregate; LGD lists 37)
    districts (~780)
      sub-districts / talukas / tehsils (~6000)
        blocks (rural admin units)
          panchayats (gram panchayats; rural)
            villages (~600k+)
        wards (urban; under ULBs - municipalities, corporations, town panchayats)
        postal pincodes (cross-cutting; not a true admin layer, indexed by India Post)
  parliamentary constituencies (PC; 543 elected + 2 nominated = 545; cross-cuts districts)
    assembly constituencies (AC; ~4123; sub-cuts a district or spans a few)
```

**Two parallel electoral hierarchies** sit alongside the LGD admin tree:

- **PC (Lok Sabha)** — 545 features in `datasets/boundaries/electoral/delim=2024/pc/all.geojson` (national file, post-2024 delim).
- **AC (Vidhan Sabha)** — 4149 features across 30 state partitions; per-state files in `datasets/boundaries/electoral/delim=2008/ac/state=<id>/all.geojson`.

PCs and ACs are NOT children of districts — they are independently delimited by ECI on population basis. A PC typically contains 5-10 ACs but is NOT bound to district borders.

## Layer totals (current state, 2026-06-01)

| Layer | Total features | Storage | Notes |
| --- | ---: | --- | --- |
| `country` | 1 | national `all.geojson` | India outline |
| `states` | 36 | national `all.geojson` | 36/37 (Ladakh aggregation TBC) |
| `districts` | **785** | national `all.geojson` (keyed by `state_lgd` 1-38) | LGD district directory |
| `subdistricts` | 36 partitions | per-state | one file per state present; feature counts vary |
| `blocks` | 36 partitions | per-state | rural admin |
| `panchayats` | 663 files | per-state nested by district | 28/36 partitions populated |
| `villages` | 659 files | per-state nested by district | sparse coverage |
| `wards` | 3300 files | per-state nested by ULB | urban |
| `postal` | 19,295 | per-state | pincode polygons |
| `ac` | **4149** | per-state | 32/36 state partitions have ACs (4 UTs have no legislative assembly) |
| `pc` | **545** | national `pc/delim=2024/all.geojson` | post-2024 ECI delim |

> File-count vs feature-count: rows marked "N files" indicate `villages`/`panchayats`/`wards`/`blocks`/`subdistricts` where each district inside the state is a separate `all.geojson` shard; we count shards, not features, to keep this doc cheap to regenerate.

## Per-state coverage matrix

`-` = layer absent. Numbers are feature counts (small layers) or file counts (large layers; villages/panchayats/wards/blocks/subdistricts). LGD-canonical state names sourced from the LGD portal; current yen-gov folder labels (`andhra-pradesh` etc.) retire in plan row L3 - L4 (see [LGD execution handover](../../../docs/archive/plans/20260601-lgd-execution-handover.md)).

| State folder | LGD name (expected) | districts* | sub-dist | blocks | panchayats | villages | wards | postal | AC | PC |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `andhra-pradesh` | Andhra Pradesh (partial, pre-bifurcation) | nat | 1 | 1 | 26 | 26 | 104 | 1249 | 175 | nat |
| `arunachal-pradesh` | Arunachal Pradesh | nat | 1 | 1 | - | - | - | 49 | 61 | nat |
| `assam` | Assam | nat | 1 | 1 | 35 | 35 | 58 | 575 | 126 | nat |
| `bihar` | Bihar | nat | 1 | 1 | 38 | 38 | 58 | 875 | 243 | nat |
| `goa` | Chhattisgarh | nat | 1 | 1 | 2 | 2 | 7 | 88 | 41 | nat |
| `gujarat` | Goa | nat | 1 | 1 | 33 | 33 | 164 | 996 | 164 | nat |
| `haryana` | Gujarat | nat | 1 | 1 | 22 | 22 | 81 | 315 | 90 | nat |
| `himachal-pradesh` | Haryana | nat | 1 | 1 | - | - | 58 | 437 | 68 | nat |
| `karnataka` | Himachal Pradesh | nat | 1 | 1 | 31 | 31 | 231 | 1354 | 225 | nat |
| `kerala` | Jammu & Kashmir (pre-2019) | nat | 1 | 1 | 14 | 14 | 75 | 1418 | 141 | nat |
| `madhya-pradesh` | Karnataka | nat | 1 | 1 | 53 | 52 | 335 | 770 | 225 | nat |
| `maharashtra` | Kerala | nat | 1 | 1 | 36 | 36 | 410 | 1589 | 303 | nat |
| `manipur` | Madhya Pradesh | nat | 1 | 1 | - | - | - | 53 | 68 | nat |
| `meghalaya` | Maharashtra | nat | 1 | 1 | 1 | - | - | 67 | 59 | nat |
| `mizoram` | Manipur | nat | 1 | 1 | - | - | - | 40 | 40 | nat |
| `nagaland` | Meghalaya | nat | 1 | 1 | - | - | 7 | 44 | 60 | nat |
| `odisha` | Mizoram | nat | 1 | 1 | 30 | 30 | 99 | 937 | 147 | nat |
| `punjab` | Nagaland | nat | 1 | 1 | 23 | 23 | 164 | 507 | 117 | nat |
| `rajasthan` | Odisha | nat | 1 | 1 | 49 | 33 | 202 | 1008 | 202 | nat |
| `sikkim` | **Sikkim (STALE - 38 AC expected 32; pre-2021 4-district)** | nat | 1 | 1 | - | - | 6 | 19 | 38 | nat |
| `tamil-nadu` | Tamil Nadu | nat | 1 | 1 | 38 | 38 | 128 | 2030 | 235 | nat |
| `tripura` | Tripura | nat | 1 | 1 | 8 | 8 | - | 79 | 60 | nat |
| `uttar-pradesh` | Uttar Pradesh | nat | 1 | 1 | 75 | 75 | 638 | 1655 | 404 | nat |
| `west-bengal` | Uttarakhand | nat | 1 | 1 | 23 | 23 | 7 | 1128 | 293 | nat |
| `chhattisgarh` | West Bengal | nat | 1 | 1 | 33 | 33 | 169 | 277 | 90 | nat |
| `jharkhand` | Jharkhand | nat | 1 | 1 | 24 | 24 | 39 | 378 | 96 | nat |
| `uttarakhand` | Punjab | nat | 1 | 1 | 13 | 13 | 74 | 300 | 70 | nat |
| `telangana` | Telangana | nat | 1 | 1 | 33 | 33 | 114 | 663 | 118 | nat |
| `andaman-and-nicobar` | Andaman & Nicobar | nat | 1 | 1 | 3 | 3 | 1 | 22 | **0 (no assembly)** | nat |
| `chandigarh` | Chandigarh | nat | 1 | 1 | 1 | 1 | 1 | 22 | **0 (no assembly)** | nat |
| `dadra-and-nagar-haveli-and-daman-and-diu` | Dadra & NH + Daman & Diu | nat | 1 | 1 | 3 | 3 | 1 | 5 | **0 (no assembly)** | nat |
| `lakshadweep` | Lakshadweep | nat | 1 | 1 | 1 | 1 | - | 9 | **0 (no assembly)** | nat |
| `delhi` | Delhi (NCT) | nat | 1 | 1 | 11 | 11 | 3 | 95 | 70 | nat |
| `puducherry` | Puducherry | nat | 1 | 1 | 4 | 4 | 2 | 32 | 29 | nat |
| `jammu-and-kashmir` | Jammu & Kashmir (post-2019 UT) | nat | 1 | 1 | - | 12 | 64 | 197 | 91 | nat |
| `ladakh` | Ladakh (post-2019 UT) | nat | 1 | 1 | - | 2 | - | 13 | **0 (no assembly)** | nat |

"nat" in **districts*** column = the 785 district polygons live in ONE national file `districts/all.geojson` keyed by `state_lgd`; no per-state district shards exist (and none are planned - one national file is the canonical shape for this layer).

"nat" in **PC** column = the state's PCs are inside the national `pc/delim=2024/all.geojson` (545 features total); no per-state PC file is needed.

District breakdown by `state_lgd` code (from `districts/all.geojson`, 785 total): 1=22, 2=12, 3=23, 4=1, 5=13, 6=22, 7=11, 8=50, 9=75, 10=38, 11=6, 12=26, 13=16, 14=16, 15=11, 16=8, 17=12, 18=35, 19=23, 20=24, 21=30, 22=33, 23=52, 24=33, 27=36, 28=26, 29=31, 30=2, 31=1, 32=14, 33=38, 34=4, 35=3, 36=33, 37=2, 38=3.

## Read-out of gaps

### Critical gaps (block citizen-facing pages)

1. **`districts` column = `nat` everywhere because districts ship as ONE national file** (`districts/all.geojson`, 785 features keyed by `state_lgd`). This is the canonical shape for this layer; no per-state shards exist or are planned. The asterisk on the column header points to the footnote explaining this.
2. **U08 Jammu & Kashmir post-2019 has NO panchayats partition**, only 12 village shards. ACs land 91 (90 elected + 1 POK reference per shijithpk source) - awaiting LGD AC code stamp (plan row LGD-STAMP).
3. **U09 Ladakh has no AC** (UT without legislative assembly) - correct.
4. **`sikkim` Sikkim is STALE on every layer**: 38 AC features (expected 32), 4-district vintage references (Sikkim was reorganised to 6 districts late 2021), no panchayats/villages, only 6 ward shards. Sikkim is the canary state for AC1a in the execution plan.

### Sparse layers needing follow-up

| Layer | States with `-` | Action |
| --- | --- | --- |
| `panchayats` | s02, s08, s14, s16, s17, s21, u08 | Bhuvan / state-portal panchayat lift cohort |
| `villages` | s02, s08, s14, s15, s16, s17, s21 | Bhuvan / NRSC village cadastre cohort |
| `wards` | s02, s14, s16, s21 (partial), s23, s27 (partial) | MoHUA SBM / state ULB-portal lift cohort |
| `AC` | u01, u02, u03, u04, u09 only | All 5 are UTs without legislative assembly - **correct**, not a gap |

### UTs without legislative assembly (AC count is correctly 0)

`andaman-and-nicobar` (Andaman), `chandigarh` (Chandigarh), `dadra-and-nagar-haveli-and-daman-and-diu` (DNH+DD), `lakshadweep` (Lakshadweep), `ladakh` (Ladakh). Five UTs total. Do NOT plan AC ingest for these.

## Source consolidation contract (GoI-only)

Per [LGD execution handover](../../../docs/archive/plans/20260601-lgd-execution-handover.md) source-of-truth doctrine:

| Layer | Canonical GoI source |
| --- | --- |
| country, states, districts, sub-districts, blocks | LGD portal directory + Survey of India outline |
| panchayats | LGD portal + Bhuvan panchayat layer |
| villages | Census of India 2011 village cadastre + Bhuvan |
| wards | LGD portal + MoHUA SBM / AMRUT publications |
| postal | India Post pincode polygon publications |
| AC | LGD AC directory (`globalviewstateforcitizen.do`) + ECI delim notification annex |
| PC | ECI delim notification annex + LGD PC directory |

Non-GoI sources (shijithpk, Garuda, ramSeraph mirrors, OSM, Wikimedia) survive ONLY as Tier-3 verification overlays in source-hunt notes; never written into `datasets/taxonomy/sources.parquet`.

## How to refresh this matrix

```powershell
.venv\Scripts\python.exe .tmp_matrix.py
```

(Script to be hardened into `tools/boundaries/coverage_matrix.py` under plan row L1d. For now it lives as a temp probe in worktree root.)

## See also

- [`docs/architecture/data/boundaries.md`](boundaries.md) — boundary layer architecture overview
- [`docs/concepts/lgd-authority.md`](../../concepts/lgd-authority.md) — (pending; plan row A2)
- [LGD execution handover plan](../../../docs/archive/plans/20260601-lgd-execution-handover.md)
- [LGD-canonical parent plan](../../../docs/archive/plans/20260601-lgd-canonical-plan.md)
- [ADR-0049: lgd_ac_id as internal join key](../decisions/0049-lgd-ac-id-internal-key.md)

