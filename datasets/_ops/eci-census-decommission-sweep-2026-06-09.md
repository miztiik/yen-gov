# ECI + census decommission sweep - re-run receipt (2026-06-09)

Parent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) chunk G32 / Round-8b (parent-plan B2b.5 PR-stage 0e).

Precedent: [datasets/_ops/eci-census-decommission-sweep-2026-06-05.md](eci-census-decommission-sweep-2026-06-05.md) (the original audit, classified A-E, marked NOT YET ZERO / re-scoped). This re-run closes the gate per the Round-8b "audit IS the deliverable" contract: any live consumer outside elections is owned by its named chunk, not by this sweep.

## Outcome (TL;DR)

The four-grep sweep was re-run on `main` at HEAD `5b1c90d8`. **ZERO NEW violations** surfaced (no hit absent from the June 5 audit and not already forward-pointed to an owning chunk). **5 of the 9 June-5 §B forward-pointers RESOLVED via file-deletion** in the X1b-pt2 / 0d-del arc since June 5; **the remaining 4 backend forward-pointers + 1 frontend dead-code retire + 1 boundary-pipeline carry-over remain live but are owned by named chunks** (B2b.3 governments office.csv re-key, boundary slug-partition migration, F1/X1a dead-code retire, ADR-0050 inventory adapter). The taxonomy backing files (`datasets/taxonomy/lgd_states.json` + its schema) survive as the upstream map all bridges still read; per June 5 §E they retire with X1b-final when every §B consumer pivots. Elections spine remains compliant: `state_codes.csv` has no `eci_st_code` column; census codes are LABEL-only (never join keys); `eci_no` retained on `electoral.csv` as the candidacies bind. Round-8b gate `eci-census-decommission-sweep` is therefore CLOSED.

## Invariants verified compliant

- **`eci_no` RETAINED.** `datasets/data/entities/electoral.csv` still carries `eci_no` (the per-constituency ballot serial, NOT the state code). Sweep that strips `eci_no` would be a regression; it is intact.
- **Census codes are LABEL-only, never join keys.** Grep 4 (`census_20(01|11)_code`) returned 19 hits, all in (a) `seed/geo_csv.py` + `seed/state_codes_csv.py` writers that emit the columns from the parsed LGD snapshot, and (b) `frontend/src/lib/canonical/canonical-entity-translation.test.ts` test fixtures asserting the column header shape. Zero JOIN / WHERE / `==` / `.get(` lookups keyed on census codes anywhere.
- **State spine has no `eci_st_code` column.** `datasets/data/entities/state_codes.csv` header carries `lgd_state_id, lgd_name, iso_3166_2, census_2001_code, census_2011_code, kind, slug, aliases` per round-8 / 8c; `columns.json` notes "eci_st_code is NOT carried (round-8 decommission)" / "DROPPED".

## Classified hits (re-run 2026-06-09)

Disposition legend (unchanged from June 5): **DROPPED** | **RETAINED-BRIDGE** | **FORWARD** | **FALSE-POS** | **RETAINED-eci_no** | **NEW-VIOLATION**. NEW classes added this re-run: **RESOLVED-DELETE** (file/loader deleted since June 5) | **DOC-STALE-CARRIED** (description text in a schema or migration ledger references a since-retired path; non-load-bearing).

### A. Elections-owned spine - still compliant (unchanged from June 5)

| Hit | Token | Disposition |
| --- | --- | --- |
| `backend/yen_gov/canonical/seed/state_codes_csv.py:26` | `eci_st_code` (docstring "DROPPED") | DROPPED - spine has no such column |
| `datasets/data/_schema/columns.json:41,53` | `eci_st_code` (notes "NOT carried" / "DROPPED") | FALSE-POS - notes only |
| `backend/yen_gov/canonical/seed/geo_csv.py:20,80,90,124` | `eci_st_code` -> `geo.csv` `aliases` token | RETAINED-BRIDGE - geo.csv keeps the `S<NN>` alias so the cross-surface resolvers in §B keep working until they pivot |
| `datasets/data/entities/electoral.csv` (header) | `eci_no` | RETAINED-eci_no |
| `datasets/data/entities/state_codes.csv` | - | DROPPED - no `eci_st_code` column |

### B. Cross-subsystem live consumers - diff vs June 5

`eci_st_code` is still the relational join key inside the legacy source parquets that surviving loaders translate to LGD slugs at the write boundary. Five June-5 forward-pointers RESOLVED via file-deletion in the X1b-pt2 + 0d-del arc; the rest still live and forward-pointed.

| June-5 row | Current status |
| --- | --- |
| `backend/yen_gov/canonical/reingest/energy_datapoints.py` (B2b.1 energy) | **RESOLVED-DELETE** - file deleted in X1b-pt2 (energy family retired 2026-06-07, local commit `8ea74f24`); the FE per-indicator CSV seam replaced it |
| `backend/yen_gov/canonical/reingest/livestock_datapoints.py` (B2b.2 livestock) | **RESOLVED-DELETE** - file deleted in X1b-pt2 (livestock family retired same commit); per-indicator CSV seam in place |
| `backend/yen_gov/canonical/reingest/governments_term_shape.py:115-183` (B2b.3 governments) | **FORWARD** - `load_eci_state_to_geo_entity` still live; `_run_governments_term_shape.py` is the driver. office.csv + office_holdings.csv still keyed on `IN-S##` / `IN-U##` prefixes (28 + 3 = 31 CM offices in office.csv; 390 holding rows in office_holdings.csv). Forward-pointed to **B2b.3 governments** (office.csv re-key to slugs; precondition for geo.csv alias drop) |
| `backend/yen_gov/canonical/reingest/state_tiers.py` (state-tiers owner) | **RESOLVED-DELETE** - file deleted in X1b (taxonomy seed retired) |
| `backend/yen_gov/canonical/reingest/election_events.py` (election-events owner) | **RESOLVED-DELETE** - file deleted in X1b (taxonomy seed retired) |
| `backend/yen_gov/canonical/reingest/ac_crosswalk.py` (0d-del) | **RESOLVED-DELETE** - file deleted (ac_crosswalk retired per B2b.5.0d-del) |
| `backend/yen_gov/canonical/adapters/eci/state_slug.py:1-39` | **FORWARD** - `eci_to_lgd_slug()` bridge still live; retires once every §B caller above pivots |
| `backend/yen_gov/canonical/adapters/eci_ae_panel.py:746-747`, `eci_ls.py:498-499` | **FORWARD** - ADR-0050 inventory adapter still translates at the write boundary; owned by inventory/adapters chunk |
| `backend/yen_gov/canonical/writer.py:184-215` | **FORWARD** - `_eci_to_lgd_slug_case_sql()` Hive-partition CASE still live and called from line 215; owned by **boundary/partition chunk**. `FAMILY_FACT_PARTITION_BY` registry is non-empty |
| `backend/yen_gov/sources/datagovin_ogd/ingest_pincode_polygons.py:265-283` | **FORWARD** - `_ECI_TO_LGD_SLUG_CACHE` partition bucket still live; owned by **pincode/boundary owner** |

### C. Hive partition grammar `state=in_[su]##` - diff vs June 5

| Hit | Count | Disposition |
| --- | --- | --- |
| `datasets/data/entities/boundary_layer.csv` | 4014 data rows | **RETAINED-BRIDGE** - legitimate admin-spine partition values under `boundaries/in/villages/state=in_s##/district=###/...`. Admin spine did NOT migrate to slug partitions; only the electoral subtree did (G10 moved electoral to `boundaries/electoral/delim=<year>/<grain>/state=<slug>/...`). Not a violation |
| `datasets/schemas/boundary-layers.schema.json:36,67,89` | 3 description blocks | **RETAINED-BRIDGE** - schema descriptions explicitly contrast the legacy admin form `state=in_s01` with the new electoral form `state=andhra-pradesh`. Both are valid per the widened regex. Not a violation |
| `datasets/schemas/manifest.schema.json:26,96` | 2 description examples | **DOC-STALE-CARRIED** - example paths reference `elections/state=in_s22/election_results.parquet`, a parquet retired in X1a-fu2 sub-row D (2026-06-07). Non-load-bearing; the schema's `path` regex still accepts the Hive `=` separator for other consumers. Cleanup-with-next-schema-bump candidate; not a sweep target |
| `backend/yen_gov/canonical/boundary_layers_seed.py:164` | 1 comment | **FALSE-POS-COMMENT** - comment mentions "alongside the legacy `state=in_s01` form" while describing the widened regex |
| `datasets/migration-ledger.csv:203` | 1 historical example | **FALSE-POS-HISTORICAL** |
| `datasets/_ops/eci-census-decommission-sweep-2026-06-05.md` | 3 mentions | **FALSE-POS** - prior receipt itself |
| `tools/boundaries/pipeline.json` | 31 `"out"` field entries | **FORWARD** - 31 electoral AC pmtile output paths under `electoral/delim=2008/ac/state=in_[su]##/all.pmtiles`. PR #847 ("out repoint") repointed a different field-set in G10-followon work; the `"out"` field for these 31 AC entries was NOT in scope for #847. Owned by the **boundary slug-partition chunk** to complete the electoral migration. (NB this hit was not enumerated by file:line in June 5 §C; it was implicit in "boundary/partition chunk in flight". Recording it explicitly here.) |

### D. Frontend - diff vs June 5

| Hit | June-5 location | Current status |
| --- | --- | --- |
| `canonicalEntityToLegacy('IN-S22')->'S22'` | `frontend/src/lib/canonical/indicator-from-canonical.ts:73-84` | **FORWARD** - function lifted to its own module `frontend/src/lib/canonical/canonical-entity-translation.ts` (structural refinement; not a fix). 4 consumers still live: `indicator-allowlist.ts:1726` (comment), `indicator-from-canonical.ts:1` (import + dispatch), `indicator-from-canonical.test.ts:69-1309`, `districts.ts:2-3`, `districts.test.ts` 16 fixtures, `tile-cartogram.test.ts` 12 fixtures, `choropleth-entity-context.{ts,test.ts}` 5 hits, `DevChartsSandbox.svelte:1`. Owned by **F1 / X1a** dead-code retire once canonical allowlist covers all renderers |
| `frontend/src/lib/canonical/election-csv-paths.ts:16` | (not in June 5) | **FALSE-POS-COMMENT** - comment cites the F1.3 sub-plan's "drop the ECI st_code map" directive; the module itself is the legitimate per-(state, year) CSV path builder, no `eci_st_code` value usage |

### E. Taxonomy source + schema - unchanged from June 5

| Hit | Disposition |
| --- | --- |
| `datasets/taxonomy/lgd_states.json:20-405` (`eci_st_code` on 36 rows) | **RETAINED-BRIDGE** - upstream map every §B loader still reads. Retires with X1b-final when every §B consumer pivots to geo.csv aliases |
| `datasets/schemas/lgd-states.schema.json:11,36,67` (`eci_st_code` field) | retires with `lgd_states.json` |

### F. Extra-grep entity-ID prefix scan (`IN-S\d{2}-` + `IN-U\d{2}-`) - new in this re-run

Not in June 5; added per G32 brief. 55 + 9 = 64 code/test hits across 14 files. All trace to two sources:

- **Backend office.csv + office_holdings.csv emit** (`canonical/office_holdings_seed.py`, `canonical/entities_seed.py`, `canonical/reingest/governments_term_shape.py`, `canonical/adapters/eci/identity.py`, `canonical/writer.py`): the `IN-S##-CM` / `IN-U##-CM` office_id grammar - **carried-forward FORWARD to B2b.3 governments** (per §B above; the `office_id` keys on `IN-S##` because the underlying state entity_id still does)
- **Frontend canonicalEntityToLegacy consumers**: tests + view-models exercising the dead-code retire path - **carried-forward FORWARD to F1 / X1a** (per §D above)

Zero NEW-VIOLATION. Every hit traces to a row already classified in §B / §D.

## Diff vs June 5 audit

| Section | June 5 status | 2026-06-09 status |
| --- | --- | --- |
| A elections spine | compliant | compliant (unchanged) |
| B cross-subsystem loaders (9 live entries) | 9 live (FORWARD) | **5 RESOLVED-DELETE** (energy_datapoints, livestock_datapoints, state_tiers, election_events, ac_crosswalk); **4 still live** (governments_term_shape, eci/state_slug bridge, eci_ae_panel + eci_ls inventory, writer Hive-CASE, ingest_pincode_polygons) |
| C Hive partition grammar | mid-migration (boundary chunk in flight) | electoral subtree migrated via G10 / G10-followon (#847); admin spine retained (legitimate); 31 pipeline.json `"out"` entries newly enumerated and forward-pointed to boundary slug-partition chunk |
| D frontend `canonicalEntityToLegacy` | one location | function lifted to its own module; same dead-code retire still owed; consumer set widened (now 14 files across renderers + tests) |
| E taxonomy `lgd_states.json` + schema | RETAINED-BRIDGE | RETAINED-BRIDGE (unchanged; retires with X1b-final) |
| F entity-id prefix scan | (not run) | run; zero NEW-VIOLATION; all trace to §B + §D |

What was cleaned by named chunks since June 5: X1b-pt2 deleted the energy + livestock canonical reingest modules (2026-06-07); B2b.5.0d-del / X1b retired `ac_crosswalk` + `state_tiers` + `election_events` reingest modules; G10 + G10-followon #847 / #849 migrated the electoral boundary subtree to slug partitions and stamped pipeline.json `sot_ref` + `delimitation_warning` repoints. The remaining work is sequenced into named chunks (B2b.3 governments, boundary slug-partition, F1/X1a, inventory/adapters, X1b-final taxonomy retire).

## Sweep commands (reproducible)

```
git grep -niE 'eci_st_code'                       -- backend/yen_gov frontend/src datasets ':!datasets/ephemeral'
git grep -niE '\bst_code\b'                       -- backend/yen_gov frontend/src
git grep -niE 'state=in_[su][0-9]{2}'             -- backend/yen_gov frontend/src datasets ':!datasets/ephemeral'
git grep -niE 'census_20(01|11)_code'             -- backend/yen_gov frontend/src
git grep -niE 'IN-S[0-9]{2}-'                     -- backend/yen_gov frontend/src
git grep -niE 'IN-U[0-9]{2}-'                     -- backend/yen_gov frontend/src
```

Counts: grep 1 = 71 (10 unique files); grep 2 = 14; grep 3 = 4024 (4014 of which are legitimate admin-spine data rows in `boundary_layer.csv`); grep 4 = 19 (all LABEL or test-fixture); grep 5 = 55 across 14 files; grep 6 = 9 across 3 files.

## Verdict

Gate `eci-census-decommission-sweep` status: **CLOSED**. Round-8b drops to DONE. The remaining forward-pointers (governments office.csv + office_holdings.csv re-key, eci/state_slug + writer Hive-CASE + ingest_pincode_polygons cross-surface translations, frontend `canonicalEntityToLegacy` dead-code retire, `tools/boundaries/pipeline.json` 31 `"out"` entries, X1b-final retire of `lgd_states.json` + its schema) are owned by their named chunks; this gate stops watching them per the Round-8b "audit IS the deliverable" contract. Per CLAUDE.md section 10 STOP-AND-SURFACE: zero NEW-VIOLATION found; no escalation needed.
