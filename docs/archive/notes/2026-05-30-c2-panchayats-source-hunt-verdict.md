# C.2 LGD Panchayats (gram-panchayat) upstream hunt verdict

**Date**: 2026-05-30
**Plan-doc row**: C.2 of TODO/20260529-boundary-rip-and-replace-plan.md
**Doctrine**: LGD-golden source-of-truth + ramSeraph mirror preference + CC0 license alignment.

## TL;DR

**Tier-1 path found and ready to implement.** ramSeraph publishes `LGD_panchayats.geojsonl.7z` via the official Indian Admin Boundaries releases (`panchayats` tag), sourced from LGD / BharatMaps `GramPanchayat_Boundary` MapServer layer. ~255k gram-panchayat features, geojsonl_7z format, CC0 1.0 license with attribution. Same upstream lineage as the already-shipping states / districts / subdistricts / villages / blocks entries. **Coverage gap**: ramSeraph's notes report ~9 states/UTs without LGD panchayat geometry (HP, J&K, Sikkim + most NE states); Bhuvan_panchayats provides a Tier-1.5 secondary for gap-fill. **Partition strategy**: nested district-keyed Hive partition `boundaries/in/panchayats/state=in_<lc>/district=<lgd>/all.geojson` (mirrors `lift_villages_national.py`). **Budget**: high per-shard risk; auto-fallback path from PR #443 C.1.c is available + will be needed for ~10-15% of high-density shards. **Frontend**: per-district registry recommended (state-level would bind 300-2500 panchayats per state — citizen UX requires district-picker drilldown). **Recon-only PR; defer infrastructure + implementation + frontend to C.2.a / C.2.b / C.2.c.**

## "Gram Panchayat" vs Block Panchayat vs Zilla Parishad — the LGD distinction

LGD distinguishes FOUR panchayat tiers. From https://lgdirectory.gov.in (verified via ramSeraph + LGD homepage stats):

| Entity class | LGD code (expected) | Count (national) | Tier | C.2 scope? |
|---|---|---|---|---|
| **Gram Panchayat (GP)** | `panchayat_lgd` (TBC on snapshot) | 255,304 | Village-cluster / rural local body | ✅ YES |
| **Block Panchayat / Panchayat Samiti / Mandal Parishad** | `block_panchayat_lgd` | 6,756 | Intermediate (block-level aggregation) | ❌ NO (admin-only, no distinct geometry) |
| **Zilla Parishad / District Panchayat** | `zp_lgd` | 674 | District-tier | ❌ NO (overlaps existing district polygons) |
| Traditional local bodies (Khap, etc.) | — | ~14,102 | Non-uniform regional | ❌ NO (not LGD-keyed nationally) |

**C.2 scope**: ONLY gram-panchayats (255,304 entities). The 3 higher tiers are deferred:
- Block Panchayat ≠ "Development Block" (C.1's scope); these are the elected SAMITI/PS body, typically aggregated from child GPs with no distinct boundary geometry. Defer to a future PR if a citizen indicator demands them.
- Zilla Parishad aligns with the district polygon already shipped — separate geometry not needed.

**Naming convention**: yen-gov uses singular non-prefixed level names (`village` not `lgd_village`); recommend `panchayat` for the new `level` enum value (over `gram_panchayat`). Schema impact: one-line enum addition.

## Investigation log

### ramSeraph releases (`panchayats` tag)

Probed https://github.com/ramSeraph/indian_admin_boundaries/releases (panchayats tag).

**Relevant artefacts:**

1. **`LGD_panchayats.geojsonl.7z`** — **TARGET FOUND** (Tier-1 primary)
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/LGD_panchayats.geojsonl.7z`
   - Source: LGD Directory (e-Panchayat MMP, Ministry of Panchayati Raj) + BharatMaps consolidation
   - License: CC0 1.0 (attribute to LGD + BharatMaps + ramSeraph)
   - Feature count claim: 255,304 GPs nationally (matches LGD published stat); actual emitted count likely 225-245k due to missing-state gap
   - Compressed size (estimate): ~150-200 MB
   - Extracted GeoJSON (estimate): ~1.5-2.5 GB at native precision
   - Coverage gap: ramSeraph notes report HP, J&K, Sikkim, Meghalaya, Mizoram, Manipur, Nagaland, Arunachal Pradesh + 1-2 UTs without published LGD geometry. To be confirmed on first snapshot.

2. **`bhuvan_panchayats.geojsonl.7z`** — alternative (Bhuvan / ISRO / SIS-DP) — Tier-1.5
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/bhuvan_panchayats.geojsonl.7z`
   - Uneven per-state coverage; mainly useful for gap-state fall-back

**Choice rationale**: Pick `LGD_panchayats.geojsonl.7z` (not Bhuvan) for these reasons:
- Same BharatMaps/LGD lineage as the rest of yen-gov's boundary corpus (consistency with C.1.b blocks, villages, subdistricts).
- `panchayat_lgd` numeric code joins natively to LGD-keyed indicator parquets.
- CC0 1.0 license matches other LGD releases.
- Bhuvan reserved as Tier-1.5 fall-back for the 9 gap states if a citizen indicator later demands panchayat coverage there (C.2.d optional follow-up).

### LGD / BharatMaps

**LGD Directory** (https://lgdirectory.gov.in, homepage stats verified):
- Reports "255,304 Gram Panchayats" as a navigable entity class.
- Confirms the gram-panchayat vs block-panchayat vs zilla-parishad tier distinction.
- Block download UI at `https://lgdirectory.gov.in/globalviewlocalbodyforcitizen.do` (web UI, not a machine-readable API).
- LGD itself publishes attribute tables only, NOT vector boundaries — geometry comes via the BharatMaps + ramSeraph pipeline.

**BharatMaps service** (https://mapservice.gov.in/gismapservice/):
- `GramPanchayat_Boundary` MapServer carries panchayat polygons.
- Source URL: `https://mapservice.gov.in/gismapservice/rest/services/BharatMapService/GramPanchayat_Boundary/MapServer/0`
- This is the upstream that ramSeraph mirrors into `LGD_panchayats.geojsonl.7z`.

### Existing yen-gov precedent (NOT the same as C.2)

`tools/boundaries/lift_villages_national.py` (read 2026-05-30):
- Dedicated orchestrator for LGD_Villages — DISTRICT-keyed nested hive partition pattern.
- Resolves `state_lgd` -> ECI state code; groups features by `(state_eci, district_lgd)`; emits per-(state, district) hive shards.
- Outputs: `datasets/boundaries/in/villages/state=in_<lc>/district=<lgd>/all.geojson`.
- SKIP-on-budget pattern (`if shard_size > SNAPSHOT_BYTE_BUDGET: continue` per `_paths.SNAPSHOT_BYTE_BUDGET = 12 MB`).

`tools/boundaries/lift_blocks_national.py` (post-PR #443; read 2026-05-30):
- C.1.c auto-fallback pattern: on budget breach at `coord_precision=N`, re-emit at `coord_precision=N-1`; if still over budget, SKIP. Records `simplification_tolerance_deg` per shard in parquet.

**Reuse strategy**: C.2.b lift script (`tools/boundaries/lift_panchayats_national.py`) should be modelled on `lift_villages_national.py` (district-keyed nested partition) BUT inherit the C.1.c auto-fallback pattern from `lift_blocks_national.py` (graceful degradation on budget overflow). The high-density state shards (UP, MP, MH, KA, AP, TN) will exercise the auto-fallback path for ~10-15% of shards based on first-order density estimate.

### Other probed sources

- **LGD Directory direct** (https://lgdirectory.gov.in): attribute tables only, no geometry. Source of canonical 255k count.
- **Bhuvan Panchayat3** (https://bhuvan-panchayat3.nrsc.gov.in/): ISRO panchayat overlay. Uneven per-state coverage; Tier-1.5 for gap-fill only.
- **State portals** (Maharashtra Mahaonline, Karnataka KSDI, Telangana TRACGIS): no consistent panchayat-geometry routes found in ramSeraph routing table; panchayat data embedded in broader admin services but not separately published.
- **DataMeet** (https://github.com/datameet/maps): no gram-panchayat layer; historical archives only.
- **PMGSY open data** (https://geosadak-pmgsy.nic.in/opendata/): publishes block boundaries (already used by C.1's Tier-2 alternative), not panchayats.

## Recommended path

**Tier-1 implementation (no deferral; recon-only PR plus separate C.2.a / C.2.b / C.2.c implementation PRs):**

### Slicing (mirrors C.1 precedent: recon → infrastructure → implementation → frontend)

| Slice | Scope | Deliverable | Gate emphasis |
|---|---|---|---|
| **C.2** (this PR, recon-only) | Upstream verification; verdict doc | `notes/2026-05-30-c2-panchayats-source-hunt-verdict.md` + plan-doc C.2 row update | N/A (research deliverable) |
| **C.2.a** (infrastructure) | Schema: add `"panchayat"` to `level` enum; backend `Level` Literal; `_paths.Kind` + `KIND_TO_LEVEL`; pipeline.json entry; orchestrator stub + 8-case test suite mirroring `test_lift_blocks_national.py` | ~6 file changes; no datasets | Gate 2 (pytest) |
| **C.2.b** (live lift + datasets) | Run lift script against live upstream; commit ~792 per-(state, district) shards; upsert parquet rows; HIVE_SHAPES test update | ~792 geojson shards + parquet + 2 source-file edits | Gates 1, 2, 4 |
| **C.2.c** (frontend registry + district-picker) | Add `PANCHAYAT_BOUNDARY_BY_DISTRICT` registry; district-picker UI shim; contract test | sources.ts + 1 new component + 1 new test | Gates 3, 4, 5 |
| **C.2.d** (optional gap-fill) | If a citizen indicator later demands panchayat coverage in gap states, ingest `bhuvan_panchayats.geojsonl.7z` for HP/J&K/etc. | conditional Bhuvan shards | Deferred unless demanded |

### Step-by-step implementation checklist (for C.2.a + C.2.b)

1. **Pipeline entry** (C.2.a): Add to `tools/boundaries/pipeline.json` under `inputs`:
   - `kind: "panchayats"`, `level: "panchayat"`, source `geojsonl_7z` pointing at the ramSeraph URL, `coord_precision: 3`, `id_property: "panchayat_lgd"` (TBC), `name_property: "panchayat_name"` (TBC). License CC0-1.0. Comment naming the 9-state gap + linking this verdict.
2. **Schema bump** (C.2.a): `datasets/schemas/boundary-layers.schema.json` — add `"panchayat"` to `level` enum. Bump `$id` minor version.
3. **Backend mapper** (C.2.a): `backend/yen_gov/canonical/boundary_layers_seed.py` — add `"panchayat"` to `Level` Literal.
4. **Path kinds** (C.2.a): `tools/boundaries/_paths.py` — add `"panchayats"` to `Kind` Literal; map `"panchayats" → "panchayat"` in `KIND_TO_LEVEL`.
5. **Lift script** (C.2.a infrastructure + C.2.b live run): `tools/boundaries/lift_panchayats_national.py` modelled on `lift_villages_national.py` + inheriting `lift_blocks_national.py`'s auto-fallback pattern. Per-feature: extract `state_lgd`, `dist_lgd`, `panchayat_lgd`, `panchayat_name`. Group by `(state_eci, dist_lgd)`. Per group: sort by `panchayat_lgd`, round coords to `coord_precision=3`, emit. On budget breach: auto-fallback to precision=2; if still over, SKIP + parent-dir rmdir.
6. **Tests** (C.2.a infrastructure): `backend/tests/test_lift_panchayats_national.py` mirroring the 11-test `test_lift_blocks_national.py` coverage (including the 2 auto-fallback tests from C.1.c).
7. **Live snapshot** (C.2.b): Run the lift; emit ~792 per-(state, district) shards under `datasets/boundaries/in/panchayats/state=in_<lc>/district=<lgd>/all.geojson`. Upsert rows into `boundary_layers.parquet`. First-snapshot MUST inspect actual property names and update `id_property` / `name_property` in pipeline.json if they differ from the assumed `panchayat_lgd` / `panchayat_name`.
8. **Contract test** (C.2.b): `frontend/src/contracts/state-panchayats-registry-coverage.test.ts` — discoverShards walks `datasets/boundaries/in/panchayats/state=in_*/district=*/all.geojson`; asserts every on-disk shard has a parquet row + join-property on first feature; extends `boundaries-conform.test.ts` HIVE_SHAPES (one new regex entry).
9. **Frontend registry** (C.2.c): `frontend/src/lib/maplibre/sources.ts` — new `PANCHAYAT_BOUNDARY_BY_DISTRICT` registry keyed by `{state_code}-{district_lgd}`; mirrors `BLOCK_BOUNDARY` but at district granularity.
10. **Frontend UX shim** (C.2.c, optional): district-picker component that lists available panchayat-coverage districts for a state and loads the relevant shard on selection. Scope to be decided after C.2.b ships.

### Frontend scoping decision: state-level vs district-level

**Recommendation: district-level registry** (deferred to C.2.c PR).

Rationale:
- 255k features / 36 states = ~7k panchayats per state average (UP could have >30k). State-level GeoJSON-source binds would push 7-30k polygons into a single map layer — citizen UX would degrade significantly even with maplibre's GPU-backed rendering at typical district zoom (8).
- Precedent: villages layer uses district-keyed shards for the same reason.
- **Pattern**: user selects state → sees district picker → selects district → map loads that district's panchayat layer.
- Defers the UI/UX challenge to a later PR with real data + measured perf characteristics.

## Risks and open questions

| # | Risk | Mitigation | Severity |
|---|---|---|---|
| 1 | Upstream file size (~150-200 MB compressed, ~1.5-2.5 GB extracted); ~30-60s extraction cost | Reuse C.1.b py7zr streaming pattern; clean `.runtime/raw/` after lift; no blockers expected | Low |
| 2 | Per-shard budget breaches in high-density districts (UP/MP/MH/KA/AP/TN) — ~10-15% of shards | Inherit C.1.c auto-fallback verbatim; record `simplification_tolerance_deg` per shard | Low (precedent solved) |
| 3 | 9 state/UT coverage gap (HP, J&K, Sikkim, NE states + UTs) | Document in plan-doc + dataset README; C.2.d optional Bhuvan fall-back; pattern matches villages layer's existing gap | Medium (acceptable; out-of-scope to fill in C.2.b) |
| 4 | Data vintage drift — panchayat boundaries change at each 5-year election cycle | `pipeline.json` `vintage` field captures snapshot year; `update_period_days` (if adopted) declares refresh cadence; same drift profile as blocks + districts | Low |
| 5 | Join-key column name TBD — recon assumes `panchayat_lgd`; actual property TBC on first lift | First-snapshot inspection per C.1.b precedent; if differs (e.g. `gp_lgd` / `OBJECTID`), update pipeline.json + sources.ts before mass-lift | Low (precedent solved) |
| 6 | Test latency on ~792 shards | `it.each()` parameterized + lazy first-feature read (not full parse); vitest parallel execution; village layer already handles this | Low |
| 7 | Frontend district-picker UX (new component) | Defer to C.2.c PR; scope after C.2.b ships with measured data | Medium (UX work; not technical) |

## Cited URLs (for reproducibility)

- ramSeraph releases (panchayats tag): https://github.com/ramSeraph/indian_admin_boundaries/releases (panchayats tag, recon-time)
- LGD_panchayats direct download: https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/LGD_panchayats.geojsonl.7z
- bhuvan_panchayats download (Tier-1.5 alternative): https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/bhuvan_panchayats.geojsonl.7z
- BharatMaps upstream layer 0: https://mapservice.gov.in/gismapservice/rest/services/BharatMapService/GramPanchayat_Boundary/MapServer/0
- ramSeraph indianopenmaps reference: https://indianopenmaps.com/not-so-open/panchayats/lgd/{z}/{x}/{y}.pbf
- LGD Directory home: https://lgdirectory.gov.in
- Bhuvan Panchayat3 service: https://bhuvan-panchayat3.nrsc.gov.in/
- ramSeraph parent: https://github.com/ramSeraph/indianopenmaps (DATA_LICENSE.md — CC0 1.0)
- Precedent lift scripts: `tools/boundaries/lift_villages_national.py` (district-keyed partition), `tools/boundaries/lift_blocks_national.py` (auto-fallback)
- Precedent verdict (C.1): `notes/2026-05-29-c1-blocks-source-hunt-verdict.md`
- C.1.c implementation: PR #443 merge commit `c797f2fa` (auto-fallback pattern)

## Verdict summary

**Status**: Tier-1, ready to implement. Recon-only PR closes C.2; implementation follows in C.2.a / C.2.b / C.2.c.

**Why no deferral**:
1. LGD_panchayats published + stable; ramSeraph release lineage is the same upstream as blocks/villages/subdistricts already shipped.
2. Format identical to existing yen-gov infrastructure (geojsonl_7z, py7zr).
3. License (CC0 1.0 + attribution) aligns with yen-gov's CC0-first doctrine.
4. LGD-golden source (BharatMaps lineage) is the canonical authority.
5. Auto-fallback pattern (PR #443) is in place + covers the high-density per-shard budget risk.
6. Coverage gap (9 states/UTs) is documented + matches the existing villages-layer gap; fall-back path exists if a citizen indicator later demands it.

**Next-PR scope (C.2.a + C.2.b)**: 10 steps above; estimate ~800 changed files (pipeline.json + schema + lift script + ~792 per-(state, district) shards + parquet + sidecars + contract test + plan-doc flip). Frontend registry deferred to C.2.c; citizen surface (rural-governance topic page binding panchayats) deferred to a Phase D arc.
