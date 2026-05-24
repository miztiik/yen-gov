# T.0d — Boundaries consolidation execution spec

**Last Updated**: 2026-05-24
**Status**: MERGED 2026-05-22 (`9e2ee3db`). All six chunks landed as one fused atomic commit per CLAUDE.md §15. Frontend repoint + ADR-0031 amendment + Tier-B `tier_b_boundary_layer_invariants` validator all in scope.
**Authors**: Gregor (Architect — contract design), voicing Hans (Governance) on hierarchy + Max (OWID-style coverage strategist) on global precedent, per CLAUDE.md §0a authority routing.
**Scope**: replace the flat `boundaries/in/geojson/*` topology + per-file `.sources.json` / `.metadata.json` / `.unkeyed.json` sidecars with a Hive-partitioned tree plus one canonical `boundary_layers.parquet` control table FK-bound to `taxonomy/sources.parquet`.
**Amends**: [ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) (Status: Accepted → Amended 2026-05-22 in T.0d commit `9e2ee3db`). Conforms to [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) §12 v2.0.
**Doc-class routing**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md); rationale lives in ADR-0031 amendment (in the same commit as execution); current shape lives in `docs/architecture/data/boundaries.md` (rewritten same commit).

---

## §1 — Directory layout verdict at 1000+ file scale

### What changes vs ADR-0031's flat tree

ADR-0031's "flat tree" argument (boundaries.md §"Why a flat tree") was calibrated to ~25 files, all `S22-` prefixed. At national rollout the same tree carries **~3,400 files in one directory**: 1 country + 1 national states + ~36 per-state outlines + 1 national districts + ~700 per-district shards + 36 AC sets + 36 PC sets + 36 subdistrict sets + ~3,000 village shards + per-city postal + per-city ULB (future) + autonomous-council overlays. `ls`, `import.meta.glob`, IDE file pickers, and human discoverability all collapse at that count. The flat justification is local-optimum logic that doesn't survive 10× growth (master plan §0b is explicit on this).

User precedent is the canonical Hive grammar already in `datasets/elections/state=in_s22/election_results.parquet`. Apply the same grammar to boundaries.

### Proposed tree (verdict)

```
datasets/boundaries/
├── boundary_layers.parquet          # NEW canonical control table (see §2)
└── in/
    ├── country/
    │   └── IN.geojson                                              # 1
    ├── states/
    │   ├── all.geojson                                             # 1   (national 36-feature outline)
    │   └── state=<S>/state.geojson                                 # ~36 (per-state hover-zoom outlines, future)
    ├── districts/
    │   ├── all.geojson                                             # 1   (national ~700 features)
    │   └── state=<S>/all.geojson                                   # ~36 (per-state carve-outs, loads faster)
    ├── ac/
    │   └── state=<S>/all.geojson                                   # ~36
    ├── pc/
    │   ├── all.geojson                                             # 1   (543 features; → PMTiles when budget trips)
    │   └── state=<S>/all.geojson                                   # ~36 (future)
    ├── subdistricts/
    │   └── state=<S>/all.geojson                                   # ~36
    ├── villages/
    │   └── state=<S>/
    │       └── district=<dist_lgd>/all.geojson                     # ~3,000 across India
    └── postal/                                                      # orthogonal — NOT LGD admin hierarchy
        └── city=<city>/pincodes.geojson                            # per-city; segregated as ADR-0031 already mandates
```

PMTiles siblings (when a layer trips the 10 MB cutover from ADR-0031 §"Format split by layer size") land at the **same partition path** with `.pmtiles` extension. The loader switches read paths off the `format` column on `boundary_layers.parquet` — no separate `pmtiles/` subtree, format is data-driven.

### Decisions resolved inline

| Question | Verdict | Why |
| --- | --- | --- |
| Per-level subdirs? | **Yes** (`country/`, `states/`, `districts/`, `ac/`, `pc/`, `subdistricts/`, `villages/`, `postal/`) | Reflects the admin-spine vocabulary citizens + IAS officers already use; one `ls` per level instead of one `ls` across all 8 levels. |
| Per-state Hive partition? | **Yes** (`state=<S>/all.geojson`) | Symmetric to `elections/state=in_s22/`. DuckDB-WASM `HIVE_PARTITIONING_AUTO` understands it. Loader needs zero special-case code. |
| Postal location? | **`postal/city=<city>/pincodes.geojson`** | Already segregated under `postal/` (ADR-0031); add Hive partition for city for symmetry. Orthogonality preserved by the peer-dir position, not by a deeper namespace. |
| Future PMTiles? | **Same partition, `.pmtiles` extension** | Format is a column on `boundary_layers.parquet`, not a directory split. ADR-0031's GeoJSON+PMTiles two-format world is preserved verbatim — only the discovery path changes. |
| `S22-villages-index.json`? | **DELETE** | Subsumed twice over by `boundary_layers.parquet` (queryable rows) AND `manifest.json` (file inventory). Two manifests is one too many; the per-state JSON loses. |
| Filename grammar | **Hive `state=<S>` over flat `S22-` prefix or nested `s22/`** | Hive is the one grammar already in use elsewhere in `datasets/`. Two grammars in one repo is what kills consistency. |

### Hans + Max sign-off lens

**Hans (governance)**: The admin spine `country → state → district → ac/pc/subdistrict → village` matches the Indian Constitution Part IX/IXA + Local Government Directory hierarchy verbatim. Citizens reason this way; IAS officers reason this way; LGD is keyed this way. Edge cases (ULBs, panchayats, autonomous councils, cantonments, Fifth-Schedule scheduled areas) are **overlays not hierarchy** — they belong in peer top-level dirs (`urban/`, `panchayats/`, `overlays/`, `cantonments/`) when ingested. The proposed tree does not block them; it makes the orthogonality structurally explicit.

**Max (OWID precedent)**: GADM uses level-keyed split (`gadm41_IND_0.json` country, `_1.json` states, `_2.json` districts, `_3.json` subdistricts) — same level-spine. Natural Earth uses scale-keyed split (`ne_10m_admin_1_states`). OWID grapher fetches per-country shapefile at `countries.geojson` (single file with all features). None of those scale to per-village granularity; **GADM stops at level 3 (subdistrict)** because the next level explodes — vindicating both the Hive partition decision and the per-state shard for villages.

### Rejected alternatives

| # | Rejected | Reason |
| - | --- | --- |
| L1 | Keep flat tree, just rename files to `<level>-state=<S>-<dist>-all.geojson` | Encodes hierarchy in filename instead of directory; doesn't help `ls`, doesn't help `import.meta.glob`, loses Hive-grammar interop with DuckDB. |
| L2 | Nested lowercase (`s22/villages/603.geojson`) without Hive | Two grammars in one repo (`state=in_s22` for elections, `s22/` for boundaries). Cognitive overhead with no structural payoff. |
| L3 | Per-state Parquet sibling carrying inline geometry (`state=S22/villages.parquet`) | Re-violates ADR-0031 R24 (geometry-in-Parquet loses tile pyramids + GPU-native rendering). The control table goes in Parquet; the geometry stays GeoJSON/PMTiles. |

---

## §2 — Sidecar consolidation scope

### `.sources.json` (73 files) — **DELETE**

Replaced by `source_id` FK column on `boundary_layers.parquet` → `taxonomy/sources.parquet` (citation triple). This is the v2.0 contract from ADR-0032 applied verbatim to the boundary family. **4 sources to seed** (one per upstream actually present on disk today; postal subtree under §1 is forward-looking only — no India Post row until a postal layer actually lands):

| # | producer | title | vintage | license | tier | issuing_authority | verification_method |
| - | --- | --- | --- | --- | --- | :-: | --- |
| 1 | DataMeet India Maps Project | datameet/maps Admin2 boundary bundle | _empty (rolling)_ | `CC-BY-4.0` | silver | false (republishes Census/SoI) | `archived-snapshot` |
| 2 | Hindustan Times Labs | HTL state-AC shapefile bundle | 2008 Delimitation | `unknown-public` (MIT applied to data; see notes) | silver | false | `archived-snapshot` |
| 3 | shijithpk | J&K Assembly New Borders (georeferenced) | 2024 | `public-domain` (Unlicense) | bronze | false | `archived-snapshot` |
| 4 | ramSeraph | Indian Admin Boundaries (LGD-keyed) | lgd-latest-extra1 | `CC-BY-4.0` | silver | false (republishes LGD/SoI) | `archived-snapshot` |

**License-enum gap surfaced**: MIT-on-data is unusual (HTL); the safe call per ADR-0032 §12 enum is `unknown-public` with the per-row `notes` carrying `"upstream MIT (software license applied to data; treated as attribution-only)"`. No schema bump required.

**India Post / postal sources**: deliberately NOT seeded by this PR. `tools/boundaries/pipeline.json` has zero postal entries and `datasets/boundaries/in/geojson/` contains zero `*pincode*` / `*postal*` files today. The `postal/city=<city>/pincodes.geojson` subtree under §1 is forward-looking only — when the first postal layer ingests, that PR adds the 5th source row with the actual license discovered at ingest time. Per user 2026-05-22: do not seed `unknown-public` rows on speculation.

`source_id` derivation: `derive_source_id(producer, title, vintage)` per `backend/yen_gov/canonical/citation.py`. Stdlib-only triple-hash; no change to the citation module required.

### `.metadata.json` (39 files) — **FOLD ALL INTO `boundary_layers.parquet`**

CRS + license + coverage + simplification block all become columns on the new control table. The renderer no longer needs to fetch a per-file sidecar to know simplification tolerance — one `SELECT * FROM boundary_layers WHERE partition_path = ?` returns everything.

**Carve-out preserved**: `feature_collection.metadata.schema.json` v1.2 stays untouched — `backend/yen_gov/sources/india_geodata/power_plants.py:242` still emits `datasets/features/in/energy/power-plants.geojson.metadata.json` for the (non-boundary) power-plants feature collection. The schema's only remaining consumer becomes that one writer; existing test `backend/tests/test_boundary_snapshot_unkeyed_metadata.py:167` gets rewritten to assert the new boundary table shape but leaves the feature-collection schema alone.

### `.unkeyed.json` (2 files) — **FOLD into `boundary_layers.parquet`** as `{unkeyed_count, unkeyed_keys_json}`

The count is citizen-trust (Hans's denominator-transparency argument from boundaries.md); the names list is operator detail. Both as columns. JSON-encoded names string stays small (handful of names per file). Rejected: demoting to `.runtime/` — loses the count from the citizen surface.

### `S22-villages-index.json` (1 file) — **DELETE**

Subsumed by `manifest.json` (path inventory) + `boundary_layers.parquet` (queryable rows). Two indices for the same thing is the classic shadow-source-of-truth defect.

### Proposed `boundary_layers.parquet` columns

```
layer_id            string  PK   "boundaries.in.villages.state=in_s22.district=603"
level               enum         country|state|district|ac|pc|subdistrict|village|postal
entity_state        string  null S22 / U07 / null for national
entity_district     string  null dist_lgd / null
entity_city         string  null city slug / null (postal only)
partition_path      string       "boundaries/in/villages/state=in_s22/district=603/all.geojson"
format              enum         geojson|pmtiles
crs                 string       default "EPSG:4326"
simplification_algorithm     enum null   douglas-peucker|visvalingam|shapely-preserve-topology|coord-precision-round|none
simplification_tolerance_deg float null
original_feature_count       int
retained_feature_count       int
unkeyed_count                int
unkeyed_keys_json   string  null small JSON array, name-only
size_bytes          int
source_id           string  FK   → taxonomy/sources.parquet
notes               string  null
```

Total: **15 columns; 12 required + 3 optional**. Adopts OWID `origin.*` precedent for the metadata fields exactly as ADR-0032 did for sources.

---

## §3 — T.0d execution checklist (one fused commit)

Per CLAUDE.md §15 paired-test discipline. P.1.A Energy plan §6 precedent (everything in one commit).

| # | File / artifact | Action | Why | Test tier |
| - | --- | --- | --- | --- |
| 1 | `datasets/schemas/boundary-layers.schema.json` v1.0 | **NEW** | Control-table contract (15 columns) | unit (Tier-A meta-schema + tmp_path round-trip) |
| 2 | `datasets/schemas/boundary.sources.schema.json` | **DELETE** | Replaced by FK on `boundary_layers.parquet` | contract (no `.sources.json` under `boundaries/` after migration) |
| 3 | `datasets/schemas/boundary.unkeyed.schema.json` | **DELETE** | Folded into Parquet columns | contract (none on disk) |
| 4 | `datasets/schemas/boundary.villages_index.schema.json` | **DELETE** | Subsumed by manifest + Parquet | contract (none on disk) |
| 5 | `datasets/schemas/feature_collection.metadata.schema.json` | **No change** | Still used by `power_plants.py`; description-only edit doesn't trigger version bump per the 2026-05-19 lesson | — |
| 6 | `backend/yen_gov/canonical/boundary_layers_seed.py` | **NEW** | Pydantic `BoundaryLayerRow(ConfigDict(extra="forbid", frozen=True))` + `emit_to_parquet(root, rows)` + parity assertions (FK closure, denominator invariant `retained = original − unkeyed`) | unit (tmp_path fixture; 6 cases — happy path, FK miss, denom mismatch, additive-bump tolerance, empty rows, byte-stable re-emit) |
| 7 | `backend/yen_gov/canonical/citation.py` | **No code change** | Stdlib triple-hash already covers all 5 boundary producers | unit (test asserts 5 deterministic `source_id`s) |
| 8 | `backend/yen_gov/canonical/sources_seed.py` (or equivalent existing sources-seeding seam) | **MODIFY** | Add 5 boundary-source rows alongside Energy / elections rows | unit (Tier-A asserts 5 expected source_ids materialise) |
| 9 | `tools/boundaries/snapshot.py` | **REWRITE** the four sidecar writers (`_write_sources_sidecar` line 487, `_write_unkeyed_sidecar` line 540, `_write_simplification_metadata_sidecar` line 580, `emit_index_manifest` line 466). Replace with single `_collect_boundary_layer_row(...) → BoundaryLayerRow`. At end of run, call `boundary_layers_seed.emit_to_parquet(...)`. Repoint output paths per §1. | Sidecar emit retired; one Parquet write per run | integration (Tier-A pytest with mocked HTTP, fixture pipeline.json, asserts new Hive paths + parquet row presence) |
| 10 | `tools/boundaries/pipeline.json` | **MODIFY** | Add per-entry `source_triple: {producer, title, vintage}` block; remove `license` + `license_url` (now sourced from `taxonomy/sources.parquet`); update `out` to Hive paths | contract (Tier-A asserts every pipeline entry yields a valid triple resolvable to a seeded source row) |
| 11 | `tools/boundaries/build.py` | **MODIFY** | Same path repoint as snapshot.py; no structural rewrite | unit (existing tests pass) |
| 12 | `tools/boundaries/migrate_to_hive_layout.py` | **NEW** (one-shot, like `tools/migrate_sources_v1_to_v2.py`) | `git mv` 73 geometry files → Hive paths; `git rm` 115 sidecar files; emit initial `boundary_layers.parquet` from on-disk inspection | one-shot tool; no test (deletes self-evidence) |
| 13 | `datasets/manifest.json` | **REGENERATED** by writer | New boundary `table_id`s following partition pattern (`boundaries.in.villages.state=in_s22`); `format` populated per row from `boundary_layers.parquet` | contract (existing manifest contract test + new `boundaries-conform.test.ts`) |
| 14 | `frontend/src/lib/maplibre/sources.ts` | **MODIFY** | Repoint every `geojson_local_path` string from flat to Hive layout (`boundaries/in/states/all.geojson`, `boundaries/in/ac/state=S22/all.geojson`, …) | unit (existing unit tests pass on new paths) |
| 15 | `frontend/src/contracts/boundaries-conform.test.ts` | **NEW** vitest | Scan `datasets/boundaries/boundary_layers.parquet`; assert each `partition_path` exists on disk; assert each `source_id` resolves in `taxonomy/sources.parquet`; assert no `.sources.json` / `.metadata.json` / `.unkeyed.json` under `boundaries/` | contract (new — parallels `datasets-conform.test.ts`) |
| 16 | `backend/yen_gov/canonical/writer.py` line 918 | **No change to skip-list** (already excludes `boundaries`) but ADD a small `emit_boundary_layers_if_present()` hook so the writer regenerates `boundary_layers.parquet` when snapshot.py has appended rows | Writer owns the control table | unit (test asserts hook is idempotent) |
| 17 | `backend/yen_gov/validate.py` (Tier-B) | **MODIFY** | Add `tier_b_legacy_boundary_sidecars(root)` chained into `run()` — fails on any `*.sources.json` / `*.metadata.json` / `*.unkeyed.json` / `*-index.json` under `boundaries/`. Allowlist file `datasets/_ops/legacy-boundary-sidecars.txt` (empty post-migration) | Anti-pattern enforcement per PR1 2026-05-22 lesson | unit (6 cases mirroring PR1's pattern) |
| 18 | `datasets/_ops/legacy-boundary-sidecars.txt` | **NEW** (empty + header comment) | Future agent who re-adds a sidecar adds an allowlist line, signalling intent | — |
| 19 | `docs/architecture/decisions/0031-boundary-geometry-strategy.md` | **AMEND** Status: Accepted → **Amended 2026-05-22**. Add §"Amendment 2026-05-22 (T.0d)" + 3 new rejected alternatives (B9 per-file sidecar, B10 keep-and-rewrite, B11 partial-fold) | ADR rationale per CLAUDE.md §5 doc-routing | — |
| 20 | `docs/architecture/data/boundaries.md` | **REWRITE** "Disk layout" + "sidecars" sections; everything else unchanged | Subsystem doc per ADR-0034 routing rule | — |
| 21 | `docs/architecture/data/canonical-store.md` §17 | **MODIFY** pointer to mention `boundary_layers.parquet` ledger | Subsystem doc cross-link | — |
| 22 | `TODO/20260517-canonical-long-format-pivot.md` §0e.7 + §0e.8 | **MODIFY** | T.0d ledger row marked DONE (commit SHA appended); retirement-ledger entry for 115 sidecars marked DONE | Plan-doc per ADR-0034 | — |
| 23 | `/memories/repo/yen-gov-architecture.md` line 117 | **MODIFY** | Replace "DEFERRED to T.0d" entry with "DONE T.0d" + SHA | Memory derived from docs | — |
| 24 | `datasets/migration-ledger.csv` | **APPEND** row | Hive-tree + sidecar consolidation logged | — |

### Estimated diff size

- **~25 source-code files** modified / created
- **115 sidecar files deleted** (73 `.sources.json` + 39 `.metadata.json` + 2 `.unkeyed.json` + 1 `-index.json`)
- **73 geometry files moved via `git mv`** (path rename only — zero byte change)
- **Net diff**: ≈ -2,000 lines (sidecar deletions) + ≈ +700 lines (Pydantic + writer hooks + tests + boundary_layers schema + ADR amendment) ≈ **-1,300 net**
- **Total files in commit**: ≈ 215

Correction Level: **4** (cross-cutting structural + behavioural; touches schemas + backend + tools + frontend + docs). Fused atomic per §15 because any intermediate commit breaks the frontend reader (paths change) or the validator (sidecars present but writer no longer emits them).

---

## §4 — Risks + rejected alternatives

### Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| **Directory-layout wrong** (we move 73 files, then realise the verdict is wrong) | HIGH | Get §1 user-approved BEFORE staging. Reversal is another rename PR + frontend rewrite + parquet rewrite — not catastrophic but expensive. The user's "Hive like elections" mandate plus GADM precedent give high confidence. |
| **Future agent re-adds a per-file `.sources.json` under `boundaries/`** because §12 says every artifact needs provenance | MEDIUM | Four-fence defence: (a) Tier-B validator fails closed per item #17; (b) snapshot.py docstring carries a NEVER comment; (c) ADR-0031 amendment lists it as Rejected B9; (d) CLAUDE.md §10 gets one new anti-pattern bullet citing the amendment. PR1 (2026-05-22) precedent shows this pattern works. |
| **Migration corrupts on-disk geometry** | LOW | `git mv` preserves bytes verbatim; SHA256-equality dance per the G.1.b lesson (2026-05-22) — snapshot all 73 geometry files SHA before migration, re-verify after. |
| **§13 browser-smoke gap** — repointed paths might 404 if any reference is missed | MEDIUM | Greppable contract: search frontend for the literal string `boundaries/in/geojson/` (currently 16+ matches) and migrate every one. Verify with §13 browser smoke on all 5 representative map routes (TN AC, Kerala AC, India states, TN villages, TN subdistricts). |

### Rejected alternatives

| # | Rejected | One-line reason |
| - | --- | --- |
| R1 | Keep `.sources.json` sidecars, rewrite contents to §12 v2.0 shape (`source_id` + remove `fetched_at`) | Smallest change, but still leaves 73+ sidecars to maintain, doesn't address cardinality explosion, doesn't give renderer queryable columns. FK-to-Parquet pattern is strictly better at 1000+ scale. |
| R2 | Fold `.sources.json` only; keep `.metadata.json` per-file | Half-measure; two storage shapes for the same per-file metadata; complicates the seed module. Single table cleaner per Canonical Data Model (EIP). |
| R3 | Put `boundary_layers.parquet` under `datasets/taxonomy/` | Conflates the boundary sibling-family with citizen-trusted taxonomy (ADR-0031 D25). The ledger belongs WITH the geometry it describes. |
| R4 | Per-state subdirectory WITHOUT Hive grammar (`s22/` not `state=s22/`) | Breaks consistency with `elections/state=in_s22/...`. Two grammars in one repo. DuckDB-WASM HIVE_PARTITIONING_AUTO loses the hint. |
| R5 | Emit one PMTiles-only artifact and skip GeoJSON entirely | Re-litigates ADR-0031 B2; out of scope for T.0d (this PR is path/sidecar consolidation, not the GeoJSON→PMTiles cutover). |

### Hans edge-case scan (Indian admin scenarios where the proposed layout might break)

| Scenario | Does the tree cope? |
| --- | --- |
| **Urban Local Bodies** (Municipal Corp / Municipality / Nagar Panchayat) | YES — peer dir `urban/state=<S>/city=<city>/<type>/` when first ULB layer ships. Tree allows the addition; no retrofit needed today. |
| **Panchayati Raj** (Gram / Block / Zilla) | YES — gram-panchayat layer fits under `villages/` (LGD-coded at village level); block + zilla as peer `panchayats/` dir when ingested. |
| **Sixth Schedule autonomous councils** (KHADC, JHADC, GHADC, BTC, Chakma / Lai / Mara, TTAADC) | YES — overlay tier under `overlays/state=<S>/sixth_schedule/<council>.geojson`. Not a hierarchy replacement; explicit peer position makes the orthogonality visible. |
| **Fifth Schedule scheduled areas** (10 states) | YES — same `overlays/` peer pattern as Sixth Schedule. |
| **Cantonment Boards** (62 across India) | YES — orthogonal small enclaves; `cantonments/state=<S>/<city>.geojson` peer dir, same shape as `postal/`. |
| **PESA (Panchayats Extension to Scheduled Areas) blocks** | YES — overlay tier. |
| **Notified Industrial Areas** | YES — overlay tier. |

The proposed admin spine (`country/states/districts/ac/pc/subdistricts/villages/postal`) is the **stable LGD hierarchy**; everything Hans-flagged is **overlay** and lives in peer top-level dirs when ingested. The tree composes — it doesn't have to be revisited to add an overlay.

### OPEN items — RESOLVED 2026-05-22 by user

- ~~**OPEN-1 (Hans + Max)**: India Post pincode license~~ — **MOOT**. No pincode/postal geojson exists in `datasets/boundaries/in/geojson/` today and `tools/boundaries/pipeline.json` has no postal entry. The `postal/` subtree under §1 is forward-looking only. T.0d seeds 4 sources (DataMeet / HTL / shijithpk / ramSeraph), not 5. When postal ingestion actually lands in a future PR, that PR adds the 5th source row with the real license. Per user: "don't ship unknown-public; find the real source" — doing so by NOT seeding speculatively.
- ~~**OPEN-2 (Hans)**: methodology_break_ref column on `boundary_layers.parquet`~~ — **MOOT**. Methodology breaks are ALREADY canonicalised on `taxonomy/entities.parquet` district rows via `entity_valid_from` + `notes` columns. Example: `IN-S22-D735 Mayiladuthurai entity_valid_from: 2020, notes: "Carved from: NAG."`; `IN-S22-D733 Tenkasi entity_valid_from: 2019, notes: "Carved from: TIN."`; `IN-S22-D730 Chengalpattu entity_valid_from: 2019, notes: "split_from predecessors not in current district list: Kanchipuram"`. Per `datasets/migration-ledger.csv:227` the break-marker fields (`census_2011_code`, `lgd_code_history`, `created_after_2011`) all live on `entity.schema.json`. Adding `methodology_break_ref` to `boundary_layers.parquet` would be misplaced — the break is a property of the ENTITY (district row), not the BOUNDARY (geometry shard). T.0d does not change anything for methodology breaks; the existing canonical surface is correct. Per user: "if there is a methodology break, just go and update it" — done; nothing to update.
- **OPEN-3 (Jony)**: `STATE_NAME_TO_ECI` map retirement — **DEFERRED to new `T.0e`** (not folded into T.0d). User correction 2026-05-22: "ECI has a different number for the states and government of India has a different number for the states." The constant is broken because it projects only one of THREE coexisting code systems (ECI: `S22`; LGD/MoHA: `33`; ISO 3166-2: `IN-TN`). `taxonomy/entities.parquet` already carries all three as separate columns (`legacy_id` = ECI, `lgd_code` = LGD, `iso_3166_2` = ISO). Retiring `STATE_NAME_TO_ECI` means porting **9 frontend files** (Home, CompareIndicator, IndicatorChoropleth, IndicatorRanked, IndicatorSmallMultiples, IndiaMap, drilldown.ts, plus the 2 `routes/` consumers) from synchronous `Object.entries(STATE_NAME_TO_ECI)` to DuckDB-WASM `loadStates()` view-model queries against `taxonomy.entities WHERE entity_type IN ('state','ut')`. That is a 9-file frontend refactor with §13 browser smoke MANDATORY on every indicator route + Home + Compare — too much to bundle into T.0d's path-consolidation scope without losing reviewability. Tracked as separate `T.0e` in master plan §0e.7.

---

## §5 — Sequencing in the master plan

Slot per master plan §0e.7: **after Energy P.1.A merges** (so the P.1 fused-atomic pattern is proven and T.0d follows it) and **before T.2 + T.3** (so the topic-catalogue rollout doesn't compete with the boundary work). Independent of S.1 (persons fork) — can land in parallel with the T.x sequence.

```
PR #92 merge (doc-refactor) → Energy P.1.A → T.0d (boundaries consolidation)
   → T.2 (lift topics) → T.3 (catalogue topic-tags) → S.1 (persons fork)
   → Energy P.1.B → Energy P.1.C → Energy P.1.D → P.2 (next family) → …
```

## §6 — Handoff (for the agent that executes T.0d)

Read these, in order, before touching code:

1. **This file** — §1 layout + §2 scope + §3 checklist + §4 risks.
2. **[ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md)** — current architecture; this T.0d commit amends it.
3. **[ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md)** — §12 v2.0 sources contract; the FK target.
4. **[boundaries.md](../docs/architecture/data/boundaries.md)** — current operational spec; this T.0d commit rewrites "Disk layout" + "sidecars" sections.
5. **[`tools/boundaries/snapshot.py`](../tools/boundaries/snapshot.py)** — current sidecar-emit code; this T.0d commit rewrites the 4 writer methods.
6. **[`frontend/src/lib/maplibre/sources.ts`](../frontend/src/lib/maplibre/sources.ts)** — current frontend consumer; this T.0d commit repoints `geojson_local_path` strings.

Pre-flight checks (run BEFORE staging):

- Verify §1 user-approved (NO file moves before this confirmation).
- SHA-snapshot all 73 `.geojson` files; re-verify post-`git mv`.
- Run `python -m yen_gov validate --root .` clean BEFORE making any change (baseline).
- Run `pytest -q` + `bun run test --run` (frontend vitest) — both green BEFORE.

Verification gates (must pass before commit):

- Tier-A pytest green (`pytest -q` in `backend/`).
- Vitest green (`bun run test --run` in `frontend/`).
- New `boundaries-conform.test.ts` passes.
- Tier-B validator clean: `python -m yen_gov validate --root .`.
- §13 browser smoke: 5 routes — TN AC, Kerala AC, India states, TN villages, TN subdistricts.
- `git status --porcelain | grep '\.sources\.json\|\.metadata\.json\|\.unkeyed\.json'` returns ZERO matches under `boundaries/`.
- `find datasets/boundaries -name '*.geojson' | wc -l` = 73 (no geometry lost).

Commit shape: single `--no-ff` merge of one fused-atomic commit per CLAUDE.md §15.
