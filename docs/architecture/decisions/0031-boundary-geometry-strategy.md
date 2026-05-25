# ADR-0031 — Boundary geometry as a sibling family (GeoJSON + PMTiles), not in the canonical Parquet store

**Status**: Amended (2026-05-25, D.6 — PC swap closes KEEP-CURRENT; core decisions unchanged)
**Last Updated**: 2026-05-25
**Deciders**: User; Jony (UX, owns map rendering surface); Gregor (contracts, sibling-family stance)
**Supersedes**: nothing — first ADR to formalise the boundary tree as canonical store sibling
**Related**: [ADR-0030](0030-canonical-store-duckdb-wasm.md) (canonical observation store); [ADR-0032](0032-sources-citation-ledger.md) (sources citation ledger v2.0 — the FK target tightened by T.0d); [boundaries.md](../data/boundaries.md) (operational spec); [canonical-store.md §17](../data/canonical-store.md)

## Context

The canonical pivot ([ADR-0030](0030-canonical-store-duckdb-wasm.md)) puts every yen-gov observation into Hive-partitioned Parquet read by DuckDB-WASM in the browser. That decision raised the question: where does boundary geometry live?

The pre-pivot tree already has working boundary infrastructure under `datasets/boundaries/in/` — country outline, india-states / india-districts / india-soi GeoJSONs, per-state `S<NN>-ac.geojson` for assembly constituencies (S01–S2x), TN-granular sub-districts and per-district village layers, and a postal/pincode orthogonal layer. Files ship with `.sources.json` provenance sidecars, `.metadata.json` (license + CRS + simplification block), and `.unkeyed.json` (denominator of features dropped because they did not join to the LGD registry). The full operational spec lives in [boundaries.md](../data/boundaries.md).

The decision to capture:

- Does boundary geometry move into the canonical Parquet store, or stay in its own sibling family?
- What format does each level use — GeoJSON, PMTiles, something else?
- How does the frontend discover boundary files? Via `datasets/manifest.json` (D21) or by guessing paths?
- How does an observation row resolve to a polygon?
- What is the deletion / migration policy as the canonical pivot lands?

This ADR exists because the answer is **cross-cutting** (data layer + frontend renderer + manifest contract) and the canonical-pivot rip-and-replace (D13) makes the "do nothing, leave it as it is" path risky: an execution agent reading "everything legacy moves to `_old/`" could plausibly sweep `datasets/boundaries/` into the same move and break every map in the app. Writing the rule down once, in one place, is cheaper than fielding the same agent question every round.

## Decision

### D25 (restated, authoritative)

**Boundary geometry lives outside the canonical Parquet store, in the sibling family `datasets/boundaries/in/`.** Observations reference geometry via `entity_id` FK that resolves through `taxonomy/entities.json` to `(entity_level, entity_code)` and then to a boundary file path enumerated in `datasets/manifest.json`.

### Format split by layer size

| Layer | Current format | Cutover trigger |
| --- | --- | --- |
| Country (`IN`) | GeoJSON | stays GeoJSON (single polygon, <100 KB) |
| State (national, all 36) | GeoJSON | stays GeoJSON |
| District (national, all) | GeoJSON now | → PMTiles when single file exceeds ~10 MB gzipped OR when zoom-level tiling becomes a perf win |
| AC per state (`S<NN>-ac.geojson`) | GeoJSON | stays GeoJSON per-state (one file per state stays under budget) |
| PC national (2024 delimitation) | GeoJSON (545 features, ~8.4 MB) | stays GeoJSON for now; promote to PMTiles when a second delimitation vintage lands and the combined per-delim files exceed the budget. See Amendment 2026-05-24. |
| Sub-district / taluk | GeoJSON now (TN only) | → PMTiles when national rollout, same trigger as districts |
| Village per state | GeoJSON now (TN partial) | → PMTiles per state when state coverage exceeds budget |
| Postal (pincode, orthogonal — not LGD) | GeoJSON per city | stays GeoJSON per city (segregated under `postal/` — see boundaries.md) |

**The 10 MB threshold answers Q11 of THE PLAN** ([TODO/20260517-canonical-long-format-pivot.md](../../../TODO/20260517-canonical-long-format-pivot.md)). It is an opening bid, not a hard wall: re-evaluate when the first layer trips it. The deciding factor is wall-clock cold-load on a mid-tier Android — when the GeoJSON download visibly stalls the map paint, switch.

### Why a sibling family, not Parquet

Vector geometry is not tabular. Forcing it into Parquet loses:

- **Tile pyramids** — PMTiles ships pre-built zoom levels; Parquet cannot pre-tile.
- **Simplification by zoom level** — natural to PMTiles, awkward to Parquet rows.
- **GPU-native rendering** — maplibre-gl reads PMTiles directly via HTTP Range and pushes to WebGL; Parquet would require a CPU-side conversion every query.
- **Geometry-aware operations** — turf.js / mapbox-gl-draw / spatial joins all expect GeoJSON/MVT, not row vectors.

Putting geometry in Parquet is a hammer-meets-screw decision. The canonical Parquet store stays focused on observations; geometry stays in the format the GIS world already solved (rejected as R24 in ADR-0030).

### Why GeoJSON + PMTiles, not a single format

GeoJSON wins on: human-readable diffs, hand-edit-ability for tiny layers (country outline), trivial inspection, no toolchain overhead. PMTiles wins on: file size at scale, pre-tiled zoom levels, single-file HTTP Range archive, native maplibre-gl protocol.

Using GeoJSON when it's small and PMTiles when it's large is the right two-format compromise. A single-format world either pays GeoJSON's size cost at scale (national village layer would be hundreds of MB) or pays PMTiles' tooling cost on a trivial country outline.

### Discovery via the manifest, not by guessing

`datasets/manifest.json` (D21) enumerates boundary files alongside observation Parquet so the frontend has **one** control-plane:

```json
{
  "tables": [
    {
      "table_id": "boundaries.in.states",
      "family": "boundaries",
      "files": [
        { "path": "boundaries/in/geojson/india-states.geojson",
          "format": "geojson", "size_bytes": 1234567 }
      ]
    },
    {
      "table_id": "boundaries.in.districts",
      "family": "boundaries",
      "files": [
        { "path": "boundaries/in/geojson/india-districts.geojson",
          "format": "geojson", "size_bytes": 8765432 }
      ]
    }
  ]
}
```

Frontend NEVER hardcodes geometry paths. The loader reads the manifest, finds the boundary entry matching `(entity_level, layer)`, and fetches via HTTP Range. This is the same rule as observation Parquet (rejected as R23 in ADR-0030) — one control plane, no guessing.

### Resolution path: observation → polygon

```
observations.entity_id          (e.g. "IN-S22-167-2866")
    │
    ▼
taxonomy/entities.json row
    │   { entity_id, entity_level: "ac" | "district" | "state" | "country",
    │     entity_code, parent_entity_id, valid_from, valid_to, ... }
    ▼
datasets/manifest.json — boundary table for that entity_level
    │
    ▼
boundaries/in/geojson/S22-ac.geojson  (or .pmtiles when migrated)
    │
    ▼
feature with matching property (e.g. ac_lgd === 167)
```

The entity row carries `entity_valid_from` / `entity_valid_to` (D23) so the choropleth can grey (not hide) regions outside their validity window — Telangana before 2014, J&K/Ladakh before 2019.

### Existing files preserved as-is

Every file currently under `datasets/boundaries/in/` stays exactly where it is. Specifically:

- `boundaries/in/country/IN.json`
- `boundaries/in/geojson/india-soi.geojson`
- `boundaries/in/geojson/india-states.geojson`
- `boundaries/in/geojson/india-districts.geojson`
- `boundaries/in/geojson/S01-ac.geojson` through `S2x-ac.geojson` (every existing per-state AC file)
- `boundaries/in/geojson/S<NN>-subdistricts.geojson` (TN today; other states as ingested)
- `boundaries/in/geojson/S<NN>-villages-<dist_lgd>.geojson` (TN today; other states as ingested)
- All `.sources.json`, `.metadata.json`, `.unkeyed.json` sidecars (preserved by convention)
- `boundaries/in/postal/IN-pincodes-<city>.geojson` (Chennai today)

Future additions (PCs, taluks national rollout, villages national rollout) follow the same `boundaries/in/{geojson|pmtiles}/` layout under the format-per-level table above.

### Migration / deletion exclusion (R25)

**`datasets/boundaries/` is NEVER moved into `_old/`.** Phase 0.13 (the legacy JSON sweep) and Phase 1.8 (the legacy deletion) EXCLUDE the boundary tree.

Any execution agent that finds itself about to run `git rm` or `git mv` against a file under `datasets/boundaries/` MUST stop and escalate to the user. This is repeated in §0c of THE PLAN, in the deletion manifest, in `canonical-store.md` §2, and now here — four places, on purpose, because the cost of a wrong sweep is every map in the app rendering blank.

### Lakshadweep and other rendering callouts

Operational rendering rules (Lakshadweep displayed at true geographic position with optional zoom-on-hover callout; no US-Alaska-style inset; no postal layer as a clickable choropleth; new districts only render their polyline forward from `created_after_2011.date`) live in [boundaries.md](../data/boundaries.md) and [frontend/maps.md](../frontend/maps.md). They are not ADR-grade decisions — they are operational style. This ADR points at them and stops.

## Rejected alternatives

| # | Rejected | Why |
| --- | --- | --- |
| B1 | Push geometry into Parquet alongside observations (one row per feature with a `geometry: BLOB` column) | See "Why a sibling family" above. Loses tile pyramids, zoom-level simplification, GPU-native rendering, geometry-aware ops. R24 of ADR-0030. |
| B2 | Single-format world — all GeoJSON or all PMTiles | GeoJSON-only pays size cost at scale (national villages > hundreds of MB); PMTiles-only pays tooling cost on trivial layers. Two-format split is the right compromise. |
| B3 | Frontend guesses geometry paths from convention (`boundaries/in/geojson/<level>.geojson`) | Brittle; partition policy and file-format choice become hidden contracts in the renderer. Use the manifest (D21). R23 of ADR-0030 (for observations) applies symmetrically here. |
| B4 | Sweep `datasets/boundaries/` into `_old/` with the rest of the pre-pivot tree during Phase 0.13 | Boundaries are NOT pre-pivot artifacts — they are canonical-store siblings (D25). R25 of ADR-0030. The cost of a wrong sweep is every map in the app rendering blank. |
| B5 | Move boundary geometry into the per-family Parquet (e.g. carry an AC polygon column on every elections row) | Massive duplication; geometry would repeat once per (election × AC) row instead of once per AC. Locks geometry to one family. Worse than B1. |
| B6 | Vector tile server (Tippecanoe + tile server in production) | Violates static-first (Holy Law #1) — needs a running server. PMTiles is the static-hostable equivalent and is what we adopt. |
| B7 | Reuse `taxonomy/entities.parquet` for geometry by adding a `geometry: BLOB` column | Same as B1; entities table becomes mixed-concern and grows by 1–2 orders of magnitude in size for no query win. |
| B8 | Embed PMTiles inside the Parquet manifest as base64 | Defeats HTTP Range — would force full-archive download. PMTiles' value is range-fetching tile slices. |
| B9 | Keep the per-shard `.sources.json` sidecars and just rewrite them into the v2.0 §12 citation triple shape (T.0d alternative) | Rejected during T.0d as a half-measure dressed as a contract fix. Two problems: (a) the same RBI Handbook cited by 200 shards reproduces the per-shard smear the v2.0 ledger exists to eliminate (§12 ledger is a TABLE keyed on the triple, not a per-shard array); (b) the boundary tree would diverge from the rest of `datasets/` where provenance is parquet-FK-only — frontend / backend / tooling now have to special-case boundary provenance reads. The right shape is one row per `(producer, title, vintage)` in `taxonomy/sources.parquet` joined to `boundary_layers.parquet` rows by `source_id` FK. |
| B10 | Fold ONLY `.sources.json` to the parquet ledger and keep `.metadata.json` + `.unkeyed.json` sidecars (half-measure) | Rejected during T.0d. The three sidecar files (provenance + simplification metadata + dropped-feature denominator) all describe one boundary layer. Splitting them across two homes (parquet for provenance, sidecar for the other two) creates a join the consumer has to do at runtime against a non-parquet format — worse ergonomics than today. The 10 columns of `BoundaryLayerRow` carry all three concerns in one parquet row; the parquet ledger is the natural single home. |
| B11 | Put `boundary_layers.parquet` under `datasets/taxonomy/` alongside `sources.parquet` and `entities.parquet` | Rejected during T.0d. The taxonomy tree carries reference vocabularies that span every family (sources, indicators, election events, state tiers, topic catalogue). Boundary layers are FAMILY-LEVEL inventory — same altitude as a hypothetical `elections/election_layers.parquet`, not the same altitude as `entities.parquet`. The right home is `datasets/boundaries/boundary_layers.parquet` (sibling to the geojson shards it inventories). Keeps the taxonomy tree generic and the boundary family self-contained. |

## Amendment 2026-05-22 (T.0d boundaries consolidation)

The core decisions of this ADR (sibling-family, GeoJSON+PMTiles split, manifest discovery, no-move rule) are unchanged. Two operational seams that were under-specified at original drafting got formalised during T.0d:

### 1. On-disk layout is Hive-partitioned

Pre-T.0d the boundary tree carried a flat `boundaries/in/geojson/` directory mixing every layer plus per-state AC files (`S22-ac.geojson`) and per-district village files (`S22-villages-603.geojson`) at the same depth, with an ad-hoc `<eci>-villages-index.json` per state that listed which districts had been ingested. That worked for the 8–10 layers that existed pre-pivot but did not scale to national rollout (national villages would put ~700 files in one directory).

T.0d migrates the tree to Hive partitioning, matching the convention already in use under `datasets/elections/`, `datasets/energy/`, etc.:

```
datasets/boundaries/in/
├── country/all.geojson
├── states/all.geojson
├── districts/all.geojson
├── subdistricts/state=in_<lc>/all.geojson           # one per state
├── villages/state=in_<lc>/district=<lgd>/all.geojson # one per (state, district)
├── ac/state=in_<lc>/all.geojson                     # one per state (37 today)
└── postal/IN-pincodes-<city>.geojson                # not LGD, segregated by city
```

The partition keys are the entity hierarchy keys already in `taxonomy/entities.parquet`: `state=in_<lower-case-iso>` and `district=<lgd>`. Frontend resolves a layer to a path via `boundaryRelPath(level, parentDistrictLgd?, stateLgd?)` (in `frontend/src/lib/boundaries.ts`); village lookups no longer probe a per-state index manifest — they fetch the partition path directly and let 404 = "not yet ingested" propagate as `null` (graceful degradation).

### 2. Provenance + simplification metadata + dropped-feature counts move to `boundary_layers.parquet`

The per-shard sidecars (`*.sources.json`, `*.metadata.json`, `*.unkeyed.json`) and the per-state `<eci>-villages-index.json` manifests retire. Their content folds into a single parquet ledger at `datasets/boundaries/boundary_layers.parquet`, one row per shard, schema in `datasets/schemas/boundary-layers.schema.json`:

- `layer_id` (PK) — dot-grammar matching the Hive path (`boundaries.in.ac.state=in_s22`, `boundaries.in.villages.state=in_s22.district=603`)
- `family` / `country` / `kind` / `state_eci` / `state_lgd` / `district_lgd` — partition keys
- `source_id` — FK to `taxonomy/sources.parquet` (ADR-0032 v2.0 citation triple shape)
- `original_feature_count` / `retained_feature_count` / `unkeyed_count` — denominator + dropped-feature accounting (was `*.unkeyed.json`)
- `simplification_tolerance` / `simplification_algorithm` / `crs` — was `*.metadata.json`
- `bbox` / `notes` — optional

Frontend has zero direct readers of this parquet today (the renderer never needed provenance metadata at runtime). The parquet is the operator + citizen-citation surface; the geojsons remain the renderer's input.

Three retired schemas (`boundary.sources.schema.json`, `boundary.unkeyed.schema.json`, `boundary.villages_index.schema.json`) are deleted in the T.0d Tier-A commit. `feature_collection.metadata.schema.json` stays — still consumed by `backend/yen_gov/sources/india_geodata/power_plants.py`.

### 3. Enforcement: Tier-B forbidden-path gate

A new `tier_b_legacy_boundary_sidecars(root)` check in `backend/yen_gov/validate.py` rejects any future `*.sources.json` / `*.metadata.json` / `*.unkeyed.json` / `*-index.json` under `datasets/boundaries/`. Companion allowlist at `datasets/_ops/legacy-boundary-sidecars.txt` ships empty by design; it exists only to support short-lived overrides during follow-up PRs (with PR-body justification required). Same enforcement pattern as `tier_b_meadow_shard_contract`.

### 4. Manifest format key tightening

`datasets/manifest.json` boundary entries keep their `format: "geojson" | "pmtiles"` discriminator (D21 unchanged). New entries follow the Hive path layout above.

## Amendment 2026-05-24 (PC layer ingest + `delim=YYYY/` partition key)

The first Parliamentary Constituency layer ships in this PR: 545 PCs covering the 2024 General Election delimitation, sourced from [`github.com/shijithpk/2024_maps_supplement`](https://github.com/shijithpk/2024_maps_supplement) (Unlicense, treated as public-domain dedication). The underlying boundary decisions are issued by the Election Commission of India via [Press Note No. 23](https://elections24.eci.gov.in/docs/press-note-no-23.pdf), reflecting the Delimitation Commission Orders of 1976 (baseline), 2008 (amendment), 2022 (J&K), and 2023 (Assam).

### 1. PC sits as a sibling kind, NOT as an `ac` partition

Per §0a authority assignment (Hans + Max), and per Citizen-user mental-model testing, AC (Assembly Constituency) and PC (Parliamentary Constituency) are **different electoral surfaces** — they elect different bodies (state legislative assemblies vs the national Lok Sabha), they aggregate at different scales (one PC typically contains 5–10 ACs), and they follow independent delimitation cycles. The boundaries tree treats them as sibling families under `boundaries/in/pc/` and `boundaries/in/ac/`, never as parent/child.

### 2. Mandatory `delim=YYYY/` partition key on PC (and on AC going forward)

Indian electoral boundaries change at delimitation cycles. The current PC ingest reflects the 2024 General Election delimitation (which itself layers 1976 + 2008 + 2022 J&K + 2023 Assam). Any pre-2009 Lok Sabha analysis (1952–2004 cycles) needs the pre-2008 boundaries; any future delimitation (next is expected ~2026 after the next Census) ships as a new partition.

The Hive partition key `delim=<YYYY>` makes the vintage explicit on disk and on the layer_id:

```
datasets/boundaries/in/pc/delim=2024/all.geojson
```

corresponds to `layer_id = boundaries.in.pc.delim=2024` and to a `BoundaryLayerRow.delimitation_vintage = "2024"` column added in v1.1 of the `boundary-layers.schema.json` (additive, nullable — pre-existing AC layers carry `null` until a follow-up PR backfills their delimitation vintage). Pattern is `^[0-9]{4}$` so accidental ISO dates or free-form text are rejected at the Pydantic boundary.

The AC layers already on disk (37 per-state shards under `boundaries/in/ac/state=in_*/all.geojson`) are NOT in scope for this PR — they keep their existing path. When the next AC delimitation lands or when pre-2008 AC layers are added, those PRs will move them under `boundaries/in/ac/delim=<YYYY>/state=in_*/all.geojson` and bump this ADR. `_paths.derive_hive` already accepts `delim` as an optional segment, so the migration is mechanical.

### 3. Citizen-rendering: 2 J&K-territory placeholders carry `ls_seat_code=999`

The 545 PC dataset contains 2 features with `ls_seat_code=999` covering Pakistan-administered Kashmir + China-administered Aksai Chin — territory claimed by India but not currently delimited as Lok Sabha seats. Renderers MUST treat these as "claimed but unrepresented" (e.g. diagonal hatch overlay, never tinted with election colours). This is a citizen-trust gate: a flat blue choropleth implying ECI conducted elections there would be wrong.

### 4. Citation surface

`taxonomy/sources.parquet` now carries 6 boundary citation rows (was 5). The shijithpk producer publishes two distinct publications cited by yen-gov:

- `("shijithpk", "J&K Assembly New Borders (georeferenced)", "2024")` → `src-68ad69e02476` — pre-existing
- `("shijithpk", "India Lok Sabha Parliamentary Constituency boundaries (georeferenced)", "2024")` → `src-2af556fe59e0` — new in this PR

These are distinct source_ids by design (ADR-0032 Rejected A: collapsing on producer alone loses per-document citation precision). Both rows mark `is_issuing_authority = false` because ECI is the upstream-upstream authority; both mark `confidence_tier = "bronze"` because shijithpk's own README warns the maps are "researcher-quality, not survey-grade — international borders will be off, use at your own risk". Suitable for choropleth visualisation; NOT for area/distance calculation.

When ECI publishes an authoritative shapefile (or when an LGD-keyed equivalent lands), a future PR will add a DIFFERENT source row with `is_issuing_authority = true` and the existing bronze row stays as-is for back-compat.

## Amendment 2026-05-25 (Phase D AC consolidation + state polygon swap outcomes)

Phase D of the [boundary coverage-expansion plan](../../../TODO/20260524-boundary-coverage-expansion-plan.md) ran D.0 (state polygons) and D.1 to D.4 (AC consolidation snapshot + promote + per-state mixed-verdict carve-outs) across PRs #263, #270, and #273 on 2026-05-25. This amendment records the concrete per-state outcomes so the next agent reading this ADR can see the authority-by-state table without re-reading the plan-doc.

### 1. State polygon swap (D.0) - DataMeet to ramSeraph `LGD_States`

PR #263 (`b2742582`) repointed `boundaries/in/states/all.geojson` from DataMeet `Admin2` to ramSeraph `LGD_States` (single national file, 36 polygons, 406 KB raw / 84.1 KB gzipped). All 36 features carry `State_LGD` (2-digit LGD code, integer) as the join key. The frontend's `boundary_join_name` override map collapsed from three overrides (A&N, Delhi, J&K) to one because the LGD-int join eliminates the legal-form vs idiomatic-form discrepancy that name-keyed joins suffered.

Ledger: `boundaries.in.states` row in `boundary_layers.parquet` carries `source_id = src-a1dd899f902d` (ramSeraph `Indian Admin Boundaries (LGD-keyed)`, `lgd-latest-extra1` vintage, CC-BY-4.0 attribution chain, silver confidence tier).

### 2. AC consolidation (D.1 to D.4) - per-state authority post-Phase-D

PR #273 (`fcd481cf`) bundled the D.2 promote (10 eligible states) + the D.3 Assam keep-current + D.4 J&K keep-current verdicts into a single ship. Authority-by-state today:

| State / UT | ECI code | Authority | Producer | `source_id` | Phase |
| --- | --- | --- | --- | --- | --- |
| Bihar | S04 | ramSeraph `LGD_Assembly_Constituencies` (243 ACs, 99% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Haryana | S07 | ramSeraph (90 ACs, 97% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Himachal Pradesh | S08 | ramSeraph (68 ACs, 99% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Nagaland | S17 | ramSeraph (60 ACs, 100% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Odisha | S18 | ramSeraph (147 ACs, 97% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Punjab | S19 | ramSeraph (117 ACs, 100% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Tripura | S23 | ramSeraph (60 ACs, 100% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Chhattisgarh | S26 | ramSeraph (90 ACs, 99% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Uttarakhand | S28 | ramSeraph (70 ACs, 100% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| NCT of Delhi | U05 | ramSeraph (70 ACs, 97% name parity) | ramSeraph | `src-a1dd899f902d` | D.2 promote |
| Assam | S03 | HTL `assam_AC.json` keep-current (LGD count 134 vs SoT 126; 1% name parity) | HTL | `src-4ad56b409556` | D.3 keep-current |
| Jammu and Kashmir (UT) | U08 | shijithpk `j_and_k_assembly_new_borders` keep-current (LGD count 101 vs SoT 90; 6% name parity) | shijithpk | `src-68ad69e02476` | D.4 keep-current |
| Other 19 states/UTs with assemblies (S01, S02, S05, S06, S10, S11, S12, S13, S14, S15, S16, S20, S21, S22, S24, S25, S27, S29, U07) | various | HTL per-state geojson (keep-current; outside D.2 promote set) | HTL | `src-4ad56b409556` | pre-Phase-D |

Total ledger rows at `level='ac'`: 31 (10 ramSeraph + 20 HTL + 1 shijithpk), one per elective state/UT.

### 3. S17 Nagaland Article 371A empirical correction

D.1 recon `notes/2026-05-25-d1-ac-consolidation-recon.md` section 4 originally hypothesised that any `status == 'Pre delimitation'` rows in the ramSeraph upstream should be filtered before promote. Empirical inspection during the D.2 snapshot proved this wrong for the current LGD release: 9 of the 10 D.2-eligible states carry zero `Pre delimitation` rows, and S17 Nagaland carries 100% (all 60 ACs tagged Pre-delim). Reason: Article 371A constitutionally exempts Nagaland from the 2008 Delimitation, so the 1976-vintage 60-AC layout IS the canonical layout used by ECI for current Nagaland elections. Filtering Pre-delim would have erased Nagaland entirely.

D.2 therefore shipped the additive `apply_exclude_filter` capability in `tools/boundaries/snapshot.py` (with 6 unit tests, general-purpose for future per-state slices) but did NOT invoke it from any of the 10 `pipeline.json` entries. Future D.x promotes that include S03 Assam, S22 Tamil Nadu, or U07 Puducherry should measure per-state Pre-delim distribution before deciding whether to filter. Recorded in the recon note's section 4 "Empirical correction" block and section 7 item 2 update.

### 4. Cross-links

- [Phase 0.0 status table](../../../TODO/20260524-boundary-coverage-expansion-plan.md#phase-00--status-ready-reckoner-update-after-every-pr) - rows D.0 / D.1 / D.2 / D.3 / D.4 / D.5
- [D.1 recon note](../../../notes/2026-05-25-d1-ac-consolidation-recon.md) - per-state property schema, parity invariants, Article 371A empirical correction
- [PR #263](https://github.com/miztiik/yen-gov/pull/263) (D.0 state polygons), [PR #270](https://github.com/miztiik/yen-gov/pull/270) (D.1 recon), [PR #273](https://github.com/miztiik/yen-gov/pull/273) (D.2/D.3/D.4 bundle)
- [boundary-data-sources.md](../../reference/boundary-data-sources.md) - full per-state inventory + producer/license catalogue
- [tools/boundaries/verify_ac_parity.py](../../../tools/boundaries/verify_ac_parity.py) - permanent post-snapshot parity re-assertion (kept for any future D.2-style promotion); the one-shot `recon_d1_ac.py` retires in the D.5 PR per CLAUDE.md section 10

### 5. What this amendment does NOT change

The "boundaries-are-a-sibling-family" decision (D25 / R24 / R25 in section 1) is unchanged. The `delim=YYYY/` partition key from the 2026-05-24 amendment is unchanged (AC layers still carry `delimitation_vintage = null` pending a separate follow-up that backfills 2008 / 1976 / etc. per state). The Tier-B forbidden-path gate is unchanged. The two-format policy (GeoJSON below ~10 MB; PMTiles above) is unchanged.

## Amendment 2026-05-25 (Phase D.6 PC swap - KEEP-CURRENT verdict)

Phase D.6 of the [boundary coverage-expansion plan](../../../TODO/20260524-boundary-coverage-expansion-plan.md) proposed swapping the PC layer source from `shijithpk` (Unlicense, QGIS-traced from the 2024 ECI delim PDF, 545 features) to ramSeraph `LGD_Parliament_Constituencies.geojsonl.7z` (CC0-1.0, BharatMaps-lineage survey-grade). Recon (`tools/boundaries/recon_d6_pc.py`, full audit in [notes/2026-05-25-d6-pc-recon.md](../../../notes/2026-05-25-d6-pc-recon.md)) produced four structural NO-GO findings; D.6 closes KEEP-CURRENT.

### 1. The four blockers

1. **Feature count = 543** (plan-doc gate required 545 +/- 1). 543 is the post-2019 constitutional Lok Sabha elected-seat count (the 104th Amendment abolished 2 nominated Anglo-Indian seats); shijithpk preserves the historical 545. The count alone is borderline.
2. **Six entire states have ZERO active features** in the ramSeraph release; 39 features carry `status="Pre delimitation"` and the rest of those states are absent: J&K (6/6 pre-delim), Arunachal Pradesh (2/2), Nagaland (1/1), Manipur (2/2), Assam (14/14), Jharkhand (14/14). Adopting would silently strip ~78 current-delim active PCs from the citizen-facing map.
3. **No `lgd_pc_code` property** present in the feature schema. The two PC-id candidates (`pc_id`, `pc_no`) are not LGD codes; CLAUDE.md section 3 identifier discipline requires LGD codes for non-elections identifiers.
4. **`pc_id` is an unstable legacy frozen key**. Telangana (17 PCs, st_code=36) uses Andhra Pradesh's pre-2014 `28xx` prefix instead of TS `36xx`; 44 of 543 features fail the obvious `st_code*100 + pc_no` derivation. A join on `pc_id` would silently mis-attribute Telangana data to Andhra Pradesh.

### 2. The decision

`tools/boundaries/pipeline.json` PC entry is unchanged; `datasets/ephemeral/india_ls_seats_545.geojson` remains the PC source-of-truth; `datasets/boundaries/in/pc/delim=2024/all.geojson` and the `src-2af556fe59e0` sources row (shijithpk PC, 2024) stay in place. No data, ledger, schema, frontend, or code changes ship in this PR.

### 3. What this amendment overrides

The 2026-05-24 amendment (section 4 "Citation surface") anticipated a future PR that would "add a DIFFERENT source row with `is_issuing_authority = true`" once an LGD-keyed equivalent landed. D.6 confirms the LGD-keyed equivalent (ramSeraph `LGD_Parliament_Constituencies`) is NOT yet a viable replacement; the upstream that exists today is structurally drifted (vintage mix + missing identifier + legacy state-code aliasing). The bronze shijithpk row remains the only citation surface for PC geometry; no new sources row is added.

### 4. Re-evaluation triggers

Re-run `tools/boundaries/recon_d6_pc.py` and re-open D.6 when ANY of:

- ramSeraph publishes a release where the six structural-gap states (J&K, Arunachal, Nagaland, Manipur, Assam, Jharkhand) all have `status=" "` (active) features.
- An `lgd_pc_code` property (or the documented LGD-portal PC code under any name) is added to the upstream schema.
- The Telangana `pc_id` block is rewritten to use a state-correct prefix (`36xx` for TS) so the synthetic key derivation holds across the whole national set.
- ECI directly publishes a survey-grade post-2019-Amendment GeoJSON of the 543 active PCs (would be `is_issuing_authority = true`, gold-tier).

Independent of upstream: re-evaluate when a frontend PC consumer is proposed (today `frontend/src/lib/boundaries.ts` `GeoLevel` union has no `"pc"` member and no view-model joins on PC). At that point the citizen-facing risk of the current bronze-tier shijithpk layer must be re-weighed against whatever ramSeraph drift remains; an interim "shard ramSeraph's 504 active features + retain shijithpk's pre-delim states" composite is on the table but out of scope until a real consumer exists.

### 5. Recon driver kept in-tree

Per the D.1 precedent (`tools/boundaries/recon_d1_ac.py` retired in the D.5 wrap-up PR after D.2 promoted), `tools/boundaries/recon_d6_pc.py` would normally retire in the D.6 promote PR. Because D.6 closes KEEP-CURRENT, there is no follow-up promote PR scheduled; the recon driver is kept in-tree as the explicit re-evaluation trigger. Cost: one ~250-line tool (pure stdlib + `py7zr`); benefit: a future agent reopening D.6 has the exact recon harness at hand, with the four-gate verdict logic, the per-state status breakdown, and the `pc_id` derivation check ready to re-run against a future upstream release.

## Consequences

### Positive

- Maps continue to work through the pivot with zero file movement — Phase 0 lands without touching `boundaries/`.
- Citizen rendering performance is preserved (maplibre-gl reads PMTiles natively when we migrate large layers).
- Hand-editable small layers (country outline) stay GeoJSON for trivial inspection / diff review.
- One control plane (`datasets/manifest.json`) for both observations and boundaries — frontend never special-cases geometry discovery.
- Boundary tree is explicitly out-of-scope for the legacy sweep — the four-place repetition (THE PLAN §0c, deletion manifest, canonical-store.md §2, this ADR) makes a wrong sweep require ignoring four signs.

### Negative

- Two formats to support (GeoJSON + PMTiles). Cutover policy (the 10 MB threshold) is a guess until we trip it.
- Boundary file discovery now requires the manifest to be regenerated whenever a layer is added — one more write-time step.
- Frontend loaders need a small `format` switch on the boundary entry (GeoJSON vs PMTiles read paths differ). Manifest carries `format` so the switch is data-driven, not hardcoded.

### Neutral

- The existing rich boundaries.md doc (operational rules, identifier discipline, methodology breaks, postal orthogonality, Lakshadweep, sidecar conventions) is unchanged and remains authoritative for operational detail. This ADR is a thin "where does it live and why" record above that operational layer.

## Implementation plan

Phase 0.14 of THE PLAN ships:

1. This ADR.
2. A short canonical-pivot note added to [boundaries.md](../data/boundaries.md) that points at this ADR and the canonical-store doc and reasserts the no-move rule. No restructuring of boundaries.md — it is already authoritative for operational detail.
3. No file movement, no code change. Geometry tree continues to work as-is.

Subsequent phases:

- Phase 0.6 (manifest contract): the writer adds boundary table entries to `datasets/manifest.json`.
- Phase 0.8 (DuckDB-WASM wired): frontend loader switches its boundary discovery to read from `manifest.json` instead of hardcoded paths (small refactor — fewer than 10 lines).
- Phase 1+ : as new boundary layers are added (PCs, national taluks, national villages), apply the format-per-level table above. First layer that trips the 10 MB threshold drives the GeoJSON → PMTiles tooling work; that work is itself a follow-up ADR if non-trivial.

## See also

- [ADR-0030 — canonical store on Parquet + DuckDB-WASM](0030-canonical-store-duckdb-wasm.md) — sibling-family rationale (D25, R24, R25)
- [boundaries.md](../data/boundaries.md) — operational spec (disk topology, sidecars, LGD discipline, methodology breaks, postal orthogonality)
- [canonical-store.md §17](../data/canonical-store.md) — pointer from the canonical store to this ADR
- [canonical-pivot deletion manifest](../canonical-pivot-deletion-manifest.md) — re-asserts the no-move rule
- [THE PLAN §0c + §6 step 0.14](../../../TODO/20260517-canonical-long-format-pivot.md) — boundaries-preservation reinforcement
- [frontend/maps.md](../frontend/maps.md) — operational rendering rules (Lakshadweep, choropleth greying)
