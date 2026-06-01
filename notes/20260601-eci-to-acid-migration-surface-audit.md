# `eci_no` -> LGD `AC_ID` migration-surface audit (Row R1)

**Last Updated**: 2026-06-01

Read-only audit commissioned by [TODO/20260530-eci-to-lgd-acid-migration-plan.md](../TODO/20260530-eci-to-lgd-acid-migration-plan.md) Row R1. No data, schema, frontend, or backend code was modified to produce this note. It exhaustively inventories every site that reads, writes, joins on, or asserts on `eci_no` so the user can pick a migration strategy.

This note does NOT recommend a strategy. Rows R2+ (strategy choice + per-surface migration) ESCALATE per CLAUDE.md section 6 Level-5 and require explicit user design sign-off + this plan-doc amended in the same commit.

## section 0. Headline numbers

- ~95 files touch the identifier; ~260 references catalogued across 8 surfaces.
- Two spines coexist: ECI spine (`eci_no` / `ac_eci_no`, state-scoped 1-based) is 100% of election surfaces; LGD spine (`lgd_ac_id`, globally unique) is present in boundary-feature provenance on ~30/31 states/UTs that carry an `AC_ID` property - only U08/J&K lacks it. The SoT `constituencies.json` files carry 0% `lgd_ac_id` today, which is true-but-misleading: the join key already lives in the boundary features and only needs harvesting into the canonical store.
- 0 AC-grain indicator-family tables exist today, so section 6 is empty (no indicator migration needed now).
- The entity_id pattern `IN-<state>-AC-<delim>-<eci_no>` (ADR-0044) embeds `eci_no` and is a deliberate FACT-grain key; treat any entity_id change as a separate decision.

## section 1. READ sites in `frontend/` (11 files, ~84 refs)

TypeScript / SQL:
- [frontend/src/main.ts](../frontend/src/main.ts) L59 - `parseAcSlug` extracts `eci_no` from route.
- [frontend/src/lib/data.ts](../frontend/src/lib/data.ts) L67, L84 - row interface `eci_no: number`.
- [frontend/src/lib/elections/election-map-coloring.ts](../frontend/src/lib/elections/election-map-coloring.ts) L9, L123-176 - color/opacity map keyed by `ac_eci_no`.
- [frontend/src/lib/explore/duckdb-views.ts](../frontend/src/lib/explore/duckdb-views.ts) L61-136 - `SELECT da.eci_no AS ac_eci_no`, GROUP BY.
- [frontend/src/lib/explore/presets.ts](../frontend/src/lib/explore/presets.ts) L11-292 - preset SQL JOINs on `ac_eci_no`.
- [frontend/src/lib/slug.ts](../frontend/src/lib/slug.ts) L35-41 - `acSlug(eci_no, name)` builds URL slug; `parseAcSlug` reverses it.
- [frontend/src/lib/router.svelte.ts](../frontend/src/lib/router.svelte.ts) L25-27 - route `/s/:state/ac/:eci_no`.
- [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) L90-375 - ~30 state entries carry `join_property: "ac_no"`.
- [frontend/src/lib/view-models/constituency.ts](../frontend/src/lib/view-models/constituency.ts) L104-352 - `loadConstituencyResult(event, state_code, eci_no)` WHERE filter.
- [frontend/src/lib/RacesBoard.svelte](../frontend/src/lib/RacesBoard.svelte) L36-226 - `eci_no` field + `ac_eci_no` alias.
- [frontend/src/lib/MarginHistogram.svelte](../frontend/src/lib/MarginHistogram.svelte) L23-250 - `eci_no` field + tooltip.

Svelte routes / display:
- [frontend/src/routes/Constituency.svelte](../frontend/src/routes/Constituency.svelte) L22-161 - route param `eci_no`, hydration, `AC #{eci_no}` title.
- [frontend/src/routes/StateOverview.svelte](../frontend/src/routes/StateOverview.svelte) L186-952 - `winners.get(ac.eci_no)`, search/sort by eci_no, drilldown URL build.
- [frontend/src/routes/Psephlab.svelte](../frontend/src/routes/Psephlab.svelte) L289-298 - find AC by eci_no; dropdown label.
- [frontend/src/routes/Explore.svelte](../frontend/src/routes/Explore.svelte) L249-250 - schema docstring `constituencies(ac_eci_no, ...)`.
- [frontend/src/lib/maplibre/StateAcMap.svelte](../frontend/src/lib/maplibre/StateAcMap.svelte) L7-162 - prop `highlight_eci_no`, map key, popup, click-nav.
- [frontend/src/routes/DevChartsSandbox.svelte](../frontend/src/routes/DevChartsSandbox.svelte) L210 - fixture.
- [frontend/src/routes/About.svelte](../frontend/src/routes/About.svelte) L99-134 - citizen docs on `ac_no` + AP + J&K `seat_id`.

Test fixtures (also section 8): tile-cartogram.test.ts, constituency.test.ts, election-map-coloring.test.ts, election-tile-layout-coverage.test.ts.

## section 2. READ sites in `backend/` (15 files, ~110 refs)

Adapters / sources:
- [backend/yen_gov/canonical/adapters/eci/identity.py](../backend/yen_gov/canonical/adapters/eci/identity.py) L56-69 - `ac_entity_id(state_code, delim_year, eci_no)`.
- [backend/yen_gov/canonical/adapters/eci/observations.py](../backend/yen_gov/canonical/adapters/eci/observations.py) L50-323 - reads eci_no, emits observation rows.
- [backend/yen_gov/canonical/adapters/eci_ae_panel.py](../backend/yen_gov/canonical/adapters/eci_ae_panel.py) L89-366 - parses `ac_no` from CSV, emits `eci_no`.
- [backend/yen_gov/canonical/adapters/eci_ls.py](../backend/yen_gov/canonical/adapters/eci_ls.py) L10 - PC uses `pc_eci_no` (distinct dimension, separate migration).
- [backend/yen_gov/sources/eci/constituencywise.py](../backend/yen_gov/sources/eci/constituencywise.py) L13-268 - `to_constituency_result`, validates against page header.
- [backend/yen_gov/sources/eci/urls.py](../backend/yen_gov/sources/eci/urls.py) L55-61 - `constituencywise_url` builds ECI page URL from eci_no (ECI-semantic; cannot blindly swap to LGD).
- [backend/yen_gov/sources/eci/statistical_report_detailed.py](../backend/yen_gov/sources/eci/statistical_report_detailed.py) L250-657 - Excel `ac_no` -> internal `eci_no`.
- [backend/yen_gov/sources/wikipedia/constituencies.py](../backend/yen_gov/sources/wikipedia/constituencies.py) L16-209 - parses + emits SoT eci_no.
- [backend/yen_gov/pipeline/run.py](../backend/yen_gov/pipeline/run.py) L113-225 - `fetch_ac_results` eci_no param.
- [backend/yen_gov/pipeline/canonical_eci_backfill.py](../backend/yen_gov/pipeline/canonical_eci_backfill.py) L569 - emits dim_acs `eci_no`.
- [backend/yen_gov/pipeline/people_ingest.py](../backend/yen_gov/pipeline/people_ingest.py) L50-356 - parses eci_no from ac_id, JOINs on `ac_eci_no`.
- [backend/yen_gov/canonical/writer.py](../backend/yen_gov/canonical/writer.py) L875-1494 - dim_acs table/schema metadata (table name stays).
- [backend/yen_gov/core/models.py](../backend/yen_gov/core/models.py) L149-248 - Pydantic `eci_no: int = Field(ge=1)` on 3 models.
- [backend/yen_gov/coverage.py](../backend/yen_gov/coverage.py) L168 - entity_id pattern validation (eci_no stays per ADR-0044).
- [backend/yen_gov/tools/boundaries/verify_ac_parity.py](../backend/yen_gov/tools/boundaries/verify_ac_parity.py) L11-186 + [s03_t4_district_fallback.py](../backend/yen_gov/tools/boundaries/s03_t4_district_fallback.py) L16-145 - read SoT eci_no vs boundary ac_no.
- [backend/yen_gov/cli.py](../backend/yen_gov/cli.py) L1210-1610 - per-AC JSON path `/results/<eci_no>.json`.

## section 3. WRITE sites in `backend/` (7 files, ~40 refs)

- [backend/yen_gov/canonical/envelope.py](../backend/yen_gov/canonical/envelope.py) L198-208 - `DimensionAc.eci_no` -> dim_acs.parquet column.
- [backend/yen_gov/canonical/adapters/eci/rollups.py](../backend/yen_gov/canonical/adapters/eci/rollups.py) L37-76 - dim_acs rows sorted by eci_no.
- [backend/yen_gov/canonical/adapters/eci/observations.py](../backend/yen_gov/canonical/adapters/eci/observations.py) L323 - candidacies row carries eci_no.
- [backend/yen_gov/emit/csv_bundle.py](../backend/yen_gov/emit/csv_bundle.py) L24-165 - CSV column `ac_eci_no`, sort `(ac_eci_no, rank)`.
- [backend/yen_gov/tools/boundaries/snapshot.py](../backend/yen_gov/tools/boundaries/snapshot.py) L694-805 - `apply_ac_no_rewrite_by_name` writes `ac_no` + provenance `lgd_legacy_ac_no` / `lgd_ac_id`.
- [backend/yen_gov/tools/bootstrap_constituencies_from_results.py](../backend/yen_gov/tools/bootstrap_constituencies_from_results.py) L102-109 + [bootstrap_constituencies_from_geojson.py](../backend/yen_gov/tools/bootstrap_constituencies_from_geojson.py) L56-71 - emit SoT eci_no.
- [backend/yen_gov/cli.py](../backend/yen_gov/cli.py) L1372-1610 - JSON file path naming.

## section 4. SoT files (33 files)

`datasets/reference/in/states/<S01..S29, U01..U09>/constituencies.json` each list ACs as `{"eci_no": N, "name": ..., "district_id": ..., "reservation": ...}`. This is the CITIZEN-RECOGNIZABLE ballot numbering. `eci_no` is state-scoped (PK within state); `lgd_ac_id` is globally unique. Migration must preserve the citizen-facing role; a rename is not value-preserving unless the global LGD code is what citizens should see.

## section 5. Election-results parquets (28 + 2 dimension tables)

- `datasets/elections/state=in_<...>/election_results.parquet` (~4000 rows total) key `(election_id, state_code, ac_no)`; `ac_no` is the boundary-side FK, joined to SoT `eci_no` at read time.
- `datasets/elections/dim_acs.parquet` (~4500 rows) PK `ac_id` (entity_id), carries `eci_no` FK to SoT.
- `datasets/elections/elections_candidacies.parquet` (~50k+ rows) logical PK `(election_id, state_code, ac_eci_no, rank)`.

## section 6. Indicator-family tables (0)

No AC-grain indicator observation table exists as of 2026-06-01. Nothing to migrate here. Future AC-grain indicators would key off entity_id per ADR-0044.

## section 7. Frontend join logic (5 sites)

- [frontend/src/lib/view-models/constituency.ts](../frontend/src/lib/view-models/constituency.ts) L160 - `WHERE da.eci_no = ${eci_no}`.
- [frontend/src/lib/explore/presets.ts](../frontend/src/lib/explore/presets.ts) L41, L85 - `JOIN ... ON w.ac_eci_no = c.ac_eci_no`.
- [frontend/src/lib/explore/duckdb-views.ts](../frontend/src/lib/explore/duckdb-views.ts) L61, L71 - `SELECT da.eci_no AS ac_eci_no`, GROUP BY.
- [frontend/src/lib/maplibre/MapChoropleth.svelte](../frontend/src/lib/maplibre/MapChoropleth.svelte) - maplibre `match` on `properties[join_property]` (`ac_no`).
- [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) L90 - `join_property: "ac_no"` for 28 states (J&K = `seat_id`).

## section 8. Contract tests (4 files)

- [frontend/src/contracts/election-tile-layout-coverage.test.ts](../frontend/src/contracts/election-tile-layout-coverage.test.ts) L13-56 - boundary `ac_no` set vs SoT `eci_no` set.
- [frontend/src/contracts/state-ac-registry-coverage.test.ts](../frontend/src/contracts/state-ac-registry-coverage.test.ts) L91-101 - asserts `join_property` is `ac_no` (J&K `seat_id`).
- [backend/tests/test_boundary_snapshot_ac_no_rewrite.py](../backend/tests/test_boundary_snapshot_ac_no_rewrite.py) L185-450 - upstream `ac_no` -> SoT `eci_no` + provenance, 11 cases.
- [backend/tests/test_ac_parity_per_state.py](../backend/tests/test_ac_parity_per_state.py) L40 - every SoT `eci_no` appears as boundary `ac_no` + name parity.

## section 9. Two-spine state + dependency order

Spine status:
- LGD spine: `lgd_ac_id` present in boundary-feature provenance on ~30/31 states/UTs carrying `AC_ID` (only U08/J&K lacks it); SoT has 0% `lgd_ac_id` coverage (harvestable from the boundary features).
- ECI spine: `eci_no` / `ac_eci_no` across SoT + dim_acs + candidacies + frontend URLs, all 28 states.
- Translation cost: every boundary->result and boundary->candidate cross-cut needs an `ac_no <-> eci_no` lookup via SoT.

Dependency order (upstream to downstream):

```
ECI CSV / LGD GeoJSON / Wikipedia
        -> backend ingest (eci_no extraction, ac_no rewrite, SoT assembly)
        -> SoT constituencies.json (eci_no)  +  parquets (dim_acs.eci_no, candidacies.ac_eci_no, results.ac_no)
        -> boundary shards (ac_no; lgd_ac_id on ~30/31 states, only U08/J&K lacks AC_ID)
        -> frontend DuckDB (JOIN ac_no <-> eci_no)
        -> map coloring (StateAcMap) + result/candidate lists + URL nav
```

Hard couplings:
1. SoT `eci_no` and dim_acs `eci_no` are FK-linked; any value change must be atomic across both.
2. Boundary `ac_no` must match results `ac_no` and SoT `eci_no`; changing the boundary join property forces SoT + dim_acs in the same operation.
3. URL param `eci_no` -> WHERE clause -> result filtering; changing it changes citizen-visible URL semantics and needs a redirect/alias plan.

## section 10. Candidate migration strategies (for user to choose; NOT a recommendation)

R2 ESCALATES. The user picks one of these (or a hybrid); the agent will then amend the plan-doc with per-row gates in the same commit as sign-off.

- A. Big-bang corpus rewrite: rename across SoT + parquets + frontend + boundaries + tests in one coordinated cutover. Highest blast radius; one schema-major bump; needs full boundary refresh for universal lgd_ac_id.
- B. Dual-key co-existence: add `lgd_ac_id` alongside `eci_no` everywhere via an adapter/lookup layer; migrate readers incrementally; retire `eci_no` later. Lowest risk per step, longest tail, sustained two-spine cost.
- C. Read-side translation table + lazy migration: introduce one canonical `eci_no <-> lgd_ac_id` lookup; keep storage as-is; translate at query boundaries; migrate storage opportunistically.
- D. ECI-as-citizen-display, LGD-as-internal: keep `eci_no` as the citizen-facing URL/label spine; carry `lgd_ac_id` as the internal join spine; never rename the citizen surfaces.
- E. Minimal: migrate only the surfaces that a future national AC-level indicator would actually need (dim_acs + candidacies + a lookup), leave URLs/SoT display on `eci_no`.

Per-strategy soft blockers: boundary schema (`ac_no` immutable without a snapshot refresh, universal `lgd_ac_id` only after that), citizen-facing URL semantics (slug + route param), and the ECI-semantic `constituencywise_url` (built from `eci_no`, not a free rename).

## See also

- [TODO/20260530-eci-to-lgd-acid-migration-plan.md](../TODO/20260530-eci-to-lgd-acid-migration-plan.md) (Level-5 plan; Row R1 commissioned this note)
- [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) (LGD-golden doctrine)
- [docs/architecture/decisions/0044-grain-over-entity.md](../docs/architecture/decisions/0044-grain-over-entity.md) (entity_id keeps `eci_no` as FACT-grain key)
- [CLAUDE.md](../CLAUDE.md) section 6 Level-5 (design consultation only; pause work)
