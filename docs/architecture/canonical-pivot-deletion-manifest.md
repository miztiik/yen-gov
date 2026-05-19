# Canonical-pivot deletion manifest

**Last Updated**: 2026-05-19
**Status**: Phase 0 step 0.0 deliverable — doc-only. **No deletions in this PR.** Lists every file / module / concept the canonical long-format pivot retires, the phase in which retirement happens, and the replacement that supersedes it.
**Owner**: Fowler (engineering craft / deletion discipline).
**Companion**: [Migration ledger](canonical-pivot-migration-ledger.md) — covers the 137 pre-pivot **data artifacts** (110 indicators + 27 elections); this manifest covers files / modules / concepts.
**THE PLAN**: [`TODO/20260517-canonical-long-format-pivot.md`](../../TODO/20260517-canonical-long-format-pivot.md). On conflict, THE PLAN wins; update this manifest.

---

## §0. Scope and rules

1. This document **enumerates** retirements; it does **not** remove anything. Removals land in the phase named per row.
2. Retirement = file deleted, OR file marked superseded with a banner header, OR concept removed from doctrine. Each row says which.
3. Replacement column points at the canonical artifact that absorbs the responsibility. If no replacement exists yet, the row is queued behind that artifact (Phase 0.3 schemas, Phase 0.6 manifest contract, Phase 0.9 writer skeleton, etc.).
4. **Excluded from every deletion / move step (R25, §0c)**: `datasets/boundaries/`, `datasets/taxonomy/`, `datasets/schemas/`, `datasets/manifest.json`. See §6 below.
5. Any agent who finds themselves running `git rm` or `git mv` against a path not listed here (or against an §6 excluded path) MUST STOP and escalate.
6. New retirements discovered during implementation get appended here in the same commit that retires them. This file is the single audit log for the pivot's deletions.

---

## §1. Conceptual docs

| Path | Action | Retires in | Replacement |
| --- | --- | --- | --- |
| `docs/concepts/folded-indicator.md` | delete (already carries obsolescence header) | Phase 1.8 (after `_old/` deletion) | [`docs/architecture/data/canonical-store.md`](data/canonical-store.md) (Phase 0.2) + ADR-0030 |
| `docs/concepts/collection-inventory.md` | delete (already carries obsolescence header) | Phase 1.8 | `datasets/manifest.json` (D21) + indicator-catalogue coverage columns (D15 / §5) |
| `docs/concepts/dataset-shapes.md` | rewrite for canonical store, then retire if subsumed | Phase 0.2 (rewrite); Phase 1.8 (retire if subsumed) | `data/canonical-store.md` |
| `docs/concepts/data-quality.md` | rewrite — remove `{key,label,frequency}` references; re-anchor on `year:int` + `period_seq` + `period_label` | Phase 0.2 | same |
| `docs/concepts/owid-alignment.md` | reframe — change framing from "we align with OWID" to "we adopt OWID" (D1, §0a "The One Rule") | Phase 0.1 (with ADR-0030) | same |
| `docs/concepts/long-coverage-indicators.md` | re-check — concept becomes a query (`coverage_year_max - coverage_year_min`) over the catalogue | Phase 0.3 (after indicator schema) | indicator catalogue denormalised `coverage_*` columns |
| `docs/concepts/indicator-card.md` | re-check — citizen indicator card is now a view-model render (D19) | Phase 1.3 | view-model loader |
| `docs/concepts/indicator-naming.md` | rewrite to encode D30 naming convention (`<entity>-<measure>-<unit>-<facet>`, kebab-case, ≤60 chars) | Phase 0.2 (with `canonical-store.md`) | same |
| `docs/concepts/data-provenance.md` | rewrite for sources-as-table + `source_id` FK + OWID `origin.*` + yen-gov extensions (R10) | Phase 0.2 | `data/canonical-store.md` §provenance |

Notes:
- `docs/concepts/citizen-first.md`, `disclaimer.md`, `electoral-hierarchy.md`, `result-aggregation.md`, `cross-state-comparison.md`, `government-vs-election.md`, `peer-sets.md`, `fiscal-actor-naming.md`, `schema-is-the-design-system.md`, `unmapped-regions.md` survive — they are pivot-agnostic doctrine.

---

## §2. ADRs

ADRs are never deleted (audit trail). Superseded ADRs gain a header banner pointing to the new ADR; the file body stays as-is.

| ADR | Action | Retires in | Replacement |
| --- | --- | --- | --- |
| 0026 (lift collection inventory) | mark superseded | Phase 0.12 | ADR-0030 |
| 0027 (cadence as separate field) | mark superseded | Phase 0.12 | ADR-0030 (cadence lives on indicator row per D15) |

THE PLAN §4 names only 0026 and 0027 as superseded. Other ADRs (0014 sqlite-emitter, 0017 explore-page-uses-sql-js, 0019 dataset-topology, 0020 indicator-artifact-as-data-contract, 0024 backend-aggregator-for-facetted-indicators) interact with the pivot but are NOT pre-asserted as superseded here; they are queued for Phase 0.12 doc-cleanup re-check in §10. The remainder (0002, 0003, 0015, 0016, 0018, 0021, 0022, 0023, 0025, 0028, 0029) are pivot-compatible.

---

## §3. Schemas

`datasets/schemas/` is excluded from the §6 move; individual schemas inside it are retired by commit when their consumer retires.

### 3a. Retired schemas

| Schema | Retires in | Reason | Replacement |
| --- | --- | --- | --- |
| `indicators-parity.schema.json` | Phase 0.12 (after iced_parity tool dies) | Parity oracle becomes a one-shot Phase-1 test harness (D35 / §7 step 1.5), not a permanent surface | none — test fixtures only |
| `parity-observation.schema.json` | Phase 0.12 | same | same |
| `indicators-completeness.schema.json` | Phase 0.12 | Completeness emitter retires; coverage moves to denormalised columns on `taxonomy/indicators.json` (D15 / §5) | indicator catalogue `coverage_*` fields |
| `indicators-operator-state.schema.json` | Phase 0.12 | Operator-state-as-JSON-overlay-on-per-shard-files dies; new shape is hand-authored `taxonomy/operator_state.json` (D18) | new `operator-state.schema.json` written in Phase 0.3 |
| `iced-chart-titles.schema.json` | Phase 2 (after energy migrates) | ICED chart titles are a per-shard JSON helper; replaced by indicator-catalogue `label_short` / `label_long` | catalogue rows |
| `eci_pins.schema.json` | Phase 1.8 | ECI URL pinning lives on `sources.parquet` rows (`url`, `content_hash`) under canonical | sources table |

### 3b. Replaced-in-place schemas (same filename, new contract — written Phase 0.3)

| Schema | Action |
| --- | --- |
| `indicator.schema.json` | rewrite for D15 honesty surface + D29 (`parent_indicator_id`, `dimension_values:STRUCT`, per-child `source_id`, `methodology_version` FK) + D30 id-format rule |
| `processing.schema.json` | re-check; likely retire if no canonical consumer |

### 3c. New schemas (Phase 0.3 — listed here for completeness, NOT retired)

`observation.schema.json`, `source.schema.json`, `entity.schema.json`, `caveat.schema.json`, `methodology-break.schema.json`, `operator-state.schema.json`, `manifest.schema.json`, `facet-axes.schema.json` (D31).

### 3d. Pivot-compatible schemas (survive)

`boundary.*`, `constituency.schema.json`, `election.schema.json`, `election-events.schema.json`, `party.schema.json`, `result.summary.schema.json`, `result.constituency.schema.json`, `state.schema.json`, `district.schema.json`, `subdistrict.schema.json`, `postal.schema.json`, `state-tiers.schema.json`, `parties-discovered.schema.json`, `parties-master.schema.json`, `csv.sources.schema.json`, `upstream-sources.schema.json`, `topic-catalogue.schema.json`, `feature_collection.metadata.schema.json`, `boundary.unkeyed.schema.json`, `boundary.villages_index.schema.json`, `boundary.no-geometry-registry.schema.json`, `unmapped-regions.schema.json`, `elections-inventory.schema.json`, `people.entity.schema.json`, `elections-config.schema.json`, `state_government.schema.json`.

These either back boundary geometry (preserved per D25 / §0c) or back contracts that are pivot-orthogonal. Each will be re-checked in Phase 0.12 and may join §3a if a consumer dies.

---

## §4. Backend modules

| Path | Action | Retires in | Reason / replacement |
| --- | --- | --- | --- |
| `backend/yen_gov/inventory/` (`__init__.py`, `derive.py`) | delete | Phase 0.12 (after manifest contract lands in 0.6) | `datasets/manifest.json` (D21) + period-token logic is dead under §10 normalisation withdrawal |
| `backend/yen_gov/coverage.py` | re-check; delete if subsumed | Phase 0.12 | Denormalised `coverage_*` columns on indicator catalogue (§5) — emitter regenerates them |
| `backend/yen_gov/emit/sqlite.py` | delete | Phase 1.8 (after `_old/` dies) | Parquet writer (`backend/yen_gov/canonical/writer.py`, Phase 0.9) |
| `backend/yen_gov/emit/csv_bundle.py` | delete | Phase 1.8 | same |
| `backend/yen_gov/composers/energy_capacity_by_source.py` | delete | Phase 2 (energy migration) | Facet-explode pattern per D26; no backend aggregator |
| `backend/yen_gov/composers/__init__.py` | delete with the last composer | Phase 2 | — |
| `backend/yen_gov/core/io.py::write_artifact` (dict-equal write-skip gate) | delete | Phase 1.8 | UPSERT-into-DuckDB writer (R6, R7, D7) |
| `backend/yen_gov/core/events.py` | re-check; survives Phase 1, may retire when elections fully on canonical | Phase 1.8 | `datasets/elections/election_results.parquet` + `taxonomy/sources.parquet` |
| `backend/yen_gov/admin/inventory.py` | retire / rewrite per Q10 (Phase 1 step 1.7 decision) | Phase 1.7 OR Phase 5.1 | canonical Inventory panel reads `taxonomy/indicators.parquet` via DuckDB |
| `backend/yen_gov/admin/pipeline.py` | retire / rewrite per Q10 | Phase 1.7 OR Phase 5.3 | canonical Pipeline panel |
| `backend/yen_gov/admin/indicators.py` | retire / rewrite per Q10 | Phase 1.7 OR Phase 5 | canonical operator-state edit UI (D18 writes `taxonomy/operator_state.json` text) |
| `backend/yen_gov/admin/eci_recon.py` | retire / rewrite | Phase 5 | canonical recon over Parquet |
| `backend/yen_gov/admin/schemas.py` | rewrite for `tmp_path` corpus injection (already done per CLAUDE.md §10 reference fix `7d407d0`); long-term retire if covered by Phase 5.4 panel | Phase 5.4 | canonical schemas panel |
| `backend/yen_gov/admin/app.py` | survives shell; routes rewritten | Phase 5 | — |
| `backend/yen_gov/validate.py` | survives — Tier-A schema sanity (CLAUDE.md §11); extended to validate canonical schemas in Phase 0.3 | — | — |
| `backend/yen_gov/cli.py` | survives — gains `validate` subcommand (already exists), `ingest`, future canonical writer entry | — | — |
| `backend/tests/test_iced_parity.py` | delete | Phase 0.12 | replaced by Phase-1 migration parity oracle test (§7 step 1.5) |
| `backend/tests/test_emit_completeness_determinism.py` | delete | Phase 0.12 | — (completeness emitter retires) |
| `backend/tests/test_admin_indicators.py` | rewrite / retire per Q10 | Phase 1.7 or Phase 5 | — |

---

## §5. Frontend modules

| Path | Action | Retires in | Reason / replacement |
| --- | --- | --- | --- |
| `frontend/src/routes/DataCompleteness.svelte` | delete | Phase 0.12 (no readers after completeness emitter dies) | indicator-catalogue browse, OWID-style |
| `frontend/e2e/data-completeness.spec.ts` | delete | Phase 0.12 (with the route) | new golden-path assertions per §7 step 1.4 |
| `frontend/src/lib/data.ts` lines ~217, ~221, ~353, ~374 (per-shard `fetch` loaders) | replace in place | Phase 1.3 | DuckDB-WASM view-model loader (D19) |
| `frontend/src/lib/paths.ts:15` (per-shard JSON path builder) | replace in place | Phase 1.3 | manifest-driven discovery (D21) |
| Per-dataset Svelte components (if any reference per-shard JSON shapes) | re-check during Phase 1.3 | Phase 1.3 | generic renderers consuming view-model |

`frontend/.vitest-report.json` is generated; gitignore status TBD — not a retirement target.

---

## §6. Datasets — `_old/` move (Phase 0.13) — **SUPERSEDED 2026-05-18**

**Status note (Phase 1.8a, 2026-05-18)**: the planned Phase 0.13 move never happened. No commit ever ran `git mv datasets/<legacy>/** datasets/_old/`. The per-event elections JSON tree was written straight into `datasets/elections/<event>/<state>/...` and the canonical Parquet later landed alongside it. `_old/` was an empty placeholder; the placeholder directory has since been removed from disk and from HEAD.

The §6c "5-day local observation" deletion gate is therefore moot. The actual cleanup is sequenced under THE PLAN rows 1.8b–1.8f as a per-family, per-target sweep; the sub-row tables below are the audit log replacing the planned `DELETED.md` ledger.

### 6a. Per-family deletion plan (replaces the §6a single-shot move)

| THE PLAN row | Target paths | Replacement | Gate before delete | Status |
| --- | --- | --- | --- | --- |
| 1.8b (PR-O) | `datasets/elections/<event>/<state>/parties.json`, `result.summary.json`, `_inventory.json` | `dim_parties.parquet` + `dim_party_alliances.parquet` + party-totals observations (PRs G/H/I) | `git grep` shows zero live readers in `frontend/src` and `admin/src`; backend pytest + frontend vitest green | superseded by 1.8b-ii |
| 1.8b-ii (PR-O.4) | `datasets/elections/<event>/<state>/parties.json` + `result.summary.json` (110 files: 55 events x 2; per-state `_inventory.json` never existed on disk — root `datasets/elections/_inventory.json` preserved, owned by people_ingest) | canonical Parquet (`election_results.parquet`, `dim_parties.parquet`, `dim_party_alliances.parquet`) already shipped (PRs G/H/I/J/L); regression test `backend/tests/test_no_legacy_json_emit.py` blocks reintroduction | zero live readers across `frontend/src` / `admin/src` / `backend/yen_gov/pipeline/`; deploy smoke step rerouted to `election_results.parquet`; backend pytest + frontend vitest green | **completed** 2026-05-19 |
| 1.8c (PR-P) | `datasets/elections/<event>/<state>/results/<ac>.json` (~7,254 files) | `observations.parquet` + `dim_candidates.parquet` + `dim_acs.parquet` consumed via `loadConstituencyResult` (PR-E) | extended-routes Playwright green after deletion for TN + KL + WB sample ACs | pending |
| 1.8d (PR-Q) | `datasets/events/in/eci/`, `datasets/taxonomy/delimitation_lineage.json`, `datasets/taxonomy/facet-axes.json` | `taxonomy/entities.parquet` event rows; `taxonomy/*.parquet` siblings | git-grep + frontend/backend test pass | pending |
| 1.8e (PR-R) | `datasets/elections/<event>/<state>/results.sqlite` (41 files) | DuckDB-WASM views (or retirement of `/psephlab` Compare/Psephlab routes) | psephlab Compare/Psephlab migrated off `frontend/src/lib/sql.ts` / `getDb` OR routes retired | **deferred** (blocker) |
| 1.8f (PR-S) | `datasets/people/<event>/<ac>/<cand>.json` (~3,983 files) | extended `dim_candidates.parquet` (or new `dim_candidate_bio.parquet`) OR retired candidate-detail page | `fetchPerson` (`frontend/src/lib/data.ts:323`) removed or repointed | **deferred** to Phase 2+ |

### 6b. EXCLUDED from deletion (preserve in place — R25 / §0c)

| Path | Reason |
| --- | --- |
| `datasets/boundaries/` | Sibling family per D25; not legacy; preserved as-is. ADR-0031 (Phase 0.14) documents the strategy. |
| `datasets/taxonomy/` | Canonical store taxonomy (entities, indicators, operator_state, caveats, methodology_breaks, facet-axes, sources). |
| `datasets/schemas/` | Schema definitions — managed individually per §3, not bulk-moved. |
| `datasets/manifest.json` | Control-plane file (D21) — written by canonical writer, read by frontend. |

### 6c. End-of-pivot validation check (Phase 1.8 closeout)

When every sub-row above is either DONE or explicitly closed-deferred, run:

1. `git ls-files datasets/elections | grep -v '\.parquet$'` returns zero entries. (Per the directory invariant in [canonical-store.md §2](data/canonical-store.md).)
2. `find datasets -type d -empty` returns zero entries. (Per the empty-parent-pruning rule in [canonical-store.md §2](data/canonical-store.md) — no shell directories left behind after the JSON sweep.)
3. `find datasets -name 'observations.parquet' -o -name 'data.parquet' -o -name 'facts.parquet' -o -name 'main.parquet'` returns zero entries. (Per the naming convention in [canonical-store.md §2a](data/canonical-store.md) — no layer-noun filenames anywhere under `datasets/`.)
4. Admin Inventory panel reports zero `kind=other` files across `datasets/<family>/`.
5. `python -m yen_gov validate --root .` Tier-B clean.
6. Cross-reference: every legacy path enumerated in this §6a table is either gone OR has an explicit deferral row in THE PLAN naming a future phase.

---

## §7. `tools/` — one-shot migration scripts

`tools/` is a graveyard of migration scripts. Each was structurally one-shot. They retire when `_old/` is deleted (Phase 1.8) unless flagged below.

### 7a. Retire with `_old/` deletion (Phase 1.8)

| Script | Original purpose |
| --- | --- |
| `tools/rip_to_v4.py` | per-shard v3 → v4 migration |
| `tools/migrate_indicators_v15_to_v20.py` | indicator schema v1.5 → v2.0 |
| `tools/bump_indicator_schema_1_3_to_1_4.py` | indicator schema bump |
| `tools/bump_indicator_schema_version.py` | indicator schema bump utility |
| `tools/bump_indicator_schema_to_current.py` | indicator schema bump utility |
| `tools/bump_indicators_to_4_1_with_cadence.py` | indicator schema v4.0 → v4.1 cadence |
| `tools/bump_sidecars_to_1_1.py` | sidecar schema bump |
| `tools/backfill_v15_governance.py` | governance backfill |
| `tools/rewrite_retired_indicator_links.py` | indicator-link rewriter |
| `tools/emit_indicators_completeness_index.py` | **completeness emitter — superseded by catalogue `coverage_*` columns (D15 / §5)** |
| `tools/emit_iced_chart_titles.py` | replaced by catalogue labels |

### 7b. iced_parity tool (Phase 0.12 — earlier than `_old/`)

| Path | Reason |
| --- | --- |
| `tools/iced_parity/` (all of: `__init__.py`, `banner.py`, `classify.py`, `ledger.py`, `models.py`, `probe.py`, `sample.py`, `AGENTS.md`) | Parity oracle becomes a one-shot Phase-1 test harness (D35 / §7 step 1.5), not a permanent tool. The harness lives at `backend/tests/canonical/test_migration_parity.py` (location TBD Phase 1.5). |

### 7c. Re-check status (likely retire post-Phase 1 / Phase 2)

| Script | Note |
| --- | --- |
| `tools/eci_recon/**` | rewrite as canonical reader queries over Parquet OR retire when admin recon panel ships (Phase 5) |
| `tools/rbi_recon.py`, `tools/rbi_appendix_recon.py`, `tools/iced_*_recon.py`, `tools/cea_recon.py`, `tools/datagovin_recon.py` | reconciliation utilities; each retires when its corresponding adapter migrates to the canonical batch envelope (D20) |
| `tools/ingest_iced_*`, `tools/ingest_ephemeral_ae.py`, `tools/ingest_merged_aq.py`, `tools/rbi_hbs_ingest_*.py` | one-shot ingest scripts — replaced by canonical adapter pipeline |
| `tools/*probe*.py`, `tools/*inspect*.py`, `tools/*_dump_*.py` | exploratory; retire ad-hoc as needed; not blocking |

### 7d. Survives the pivot

| Path | Reason |
| --- | --- |
| `tools/boundaries/` | sibling-family layer per D25 / §0c |
| `tools/lgd/` | LGD code utilities — feed `taxonomy/entities.json` |
| `tools/eci_offline_downloader.py` | upstream fetcher — feeds canonical adapter |

---

## §8. Concepts and doctrine retirements (concept-level, not files)

The following concepts are RETIRED as doctrine. Any future commit reintroducing them is a regression.

| Retired concept | Replaced by | Authority |
| --- | --- | --- |
| Per-shard JSON files (folded-indicator v4.0; ~7,300 file proliferation) | Hive-partitioned Parquet read by DuckDB-WASM (D1) | R3 |
| `.data-card.json` sidecar per indicator | indicator-catalogue row (D15) | R4 |
| Global mutable `_inventory.json` | `datasets/manifest.json` (D21) | R5 |
| SHA-gate on Fetcher + `.meta.json` per URL | UPSERT-into-DuckDB on logical key (D7) | R6 |
| `write_text_if_changed` byte-compare helpers at write seams | UPSERT-into-DuckDB; fix non-determinism upstream of write seam | R7 |
| Period vocabulary normalisation (the `{key, label, frequency}` token) | `year:int` (D2) + `period_label` verbatim (D3) + `period_seq:int` machine sort | R1, R8 |
| Per-shard `sources[]` with `fetched_at` per entry | `taxonomy/sources.parquet` table + `source_id` FK + `first_fetched_at` immutable + `last_seen_at` telemetry (D5, D6) | CLAUDE.md §12 + R15 |
| Item-level provenance overrides in `sources[]` | per-row `source_id` on observation | R15 |
| Operator-state as JSON overlay on per-shard indicator files | hand-authored `datasets/taxonomy/operator_state.json` text → compiled `.parquet` (D18) | R10 (ADR-0026 superseded) |
| Backend aggregator for facetted indicators (ADR-0024) | facet-explode: parent indicator + `dimension_values:STRUCT` children (D26) | R26 |
| Frontend reads JSON shadow tree | DuckDB-WASM reads Parquet directly via HTTP Range (D10) | R3, R12 |
| Pre-CI dataset validation across the corpus | local pre-emit Tier-B (`python -m yen_gov validate --root .`); no CI gate on `datasets/**` (D11) | CLAUDE.md §11 |
| Strangler-fig coexistence of JSON + Parquet readers in production | rip-and-replace (D13); isolated test harness only (R21) | R9 |
| Hive partition by `year` | partition by `indicator_id` (or `topic_id`) when family > 15 MB (D8) | R18 |
| `caveats.parquet` as home for methodology breaks | `methodology_breaks.parquet` as separate typed surface (D16) | R20 |
| Single `value:DOUBLE` column on observation | `value_numeric:DOUBLE` + `value_text:VARCHAR` split (D5/D17) | R17 |
| `source_id` in the UPSERT identity hash | logical key `(entity_id, year, period_label, indicator_id)` only (D7) | R16 |
| `dimensions: MAP<VARCHAR,VARCHAR>` on every observation row | parent + `dimension_values:STRUCT` on catalogue + selective facet-explode (D26) | R26 |
| Permanent `consolidator.py` module for 110→60 collapse | one-shot dated migration `backend/yen_gov/canonical/migration/m20260520_consolidate_indicators.py` (D34) | R28 |
| Golden-byte test for consolidation migration | writer determinism + integration row-equality (D35) | R29 |
| Computing our own crime-rate denominator from interpolated Census | NCRB-published rate as canonical; count as facet (D33.3) | R30 |
| Smoothing a line across a methodology break | visible vertical-rule break-marker (D32); two `indicator_id`s for the two methodologies (D28) | R31 |
| `(ii) separate `geo_entity_id` + `fiscal_actor_id`` for entity tiering | single `entity_id` + `entity_type` enum (D27) | R27 (preference logged for Phase F revisit) |
| Production feature-flag coexistence of JSON and Parquet loaders | rip-and-replace; isolated test harness only (D13) | R21 |
| Raw observation rows returned from loader to renderers | view-model contract (D19); SQL stays in loader | R22 |
| Frontend file-discovery by path guessing | `datasets/manifest.json` (D21) | R23 |
| Forcing boundary geometry into Parquet / observation store | sibling family `datasets/boundaries/in/` with GeoJSON / PMTiles (D25, ADR-0031) | R24 |

---

## §9. CLAUDE.md / agent memory text retirements

| Section | Status |
| --- | --- |
| CLAUDE.md §0a "The One Rule" — OWID canonical | added (R9) — keeps |
| CLAUDE.md §10 — period vocabulary normalisation ban | REMOVED (R8) — done |
| CLAUDE.md §10 — `coverage.temporal` parse ban | REMOVED (R8) — done |
| CLAUDE.md §10 — `fetched_at` bullet (sources-as-table) | REWRITTEN (R10) — done |
| CLAUDE.md §10 — `write_text_if_changed` bullet (UPSERT) | REWRITTEN (R10) — done |
| CLAUDE.md §10 — no-JSON-projection + no-CI-on-datasets | ADDED — done |
| `docs/agents/guardrails.md` — sources-as-table | UPDATED — done |
| `backend/yen_gov/AGENTS.md` — canonical invariants | UPDATED — done |
| `admin/AGENTS.md` — canonical pivot invariant | UPDATED — done |
| `frontend/src/AGENTS.md` — runtime DuckDB-WASM read path | UPDATED — done |

Phase 0.12 doc cleanups remaining (from THE PLAN §4 Outstanding doc cleanups): `docs/architecture/decisions/0003-no-fetch-cache.md` re-check; `docs/concepts/data-flow.md` update for adapter→writer batch envelope (D20); `docs/architecture/frontend/data-loading.md` rewrite for DuckDB-WASM + view-model + failure-state + manifest; `docs/architecture/frontend/deployment.md` Range/MIME verify; `docs/architecture/backend/schemas.md`, `core.md`, `pipeline.md` updates; `docs/architecture/admin/overview.md` Phase 5 + interim stance note; `docs/how-to/force-recollect.md` rewrite under UPSERT semantics; README one-paragraph update.

---

## §10. Open follow-ups (tracked here so they don't get lost)

1. **ADR re-check in Phase 0.12 doc-cleanup**: 0014 (sqlite emitter — confirm SQLite path is dead under D8 before marking), 0017 (explore-page-uses-sql-js — should mark superseded by ADR-0030 / R12 DuckDB-WASM), 0019 (dataset-topology-and-column-discipline — column discipline survives, topology replaced), 0020 (indicator-artifact-as-data-contract — partial: per-shard JSON contract dies, "indicator as contract" survives in `taxonomy/indicators.json`), 0024 (backend-aggregator-for-facetted-indicators — superseded by D26 facet-explode at Phase 2 energy migration).
2. **`datasets/ephemeral/`**: name says "ephemeral" but content is frozen committed inputs (PDFs/XLS/CSV) under D7 idempotency. Either (a) rename to `datasets/inputs/frozen/` and keep committed, or (b) move to `.runtime/inputs/` and gitignore (loses frozen-in-repo guarantee). Decide in Phase 0.13. Presence of `_ingest_inventory.json` here is a separate smell to resolve.
3. **`config/elections.json`** + the elections-config schema — pivot-compatible; survives. Re-check enum overlap with `taxonomy/sources.parquet.confidence_tier` (D5) during Phase 0.4.
4. **`tools/iced_probe.py`, `tools/cea_archive_enumerate.py`, etc.** — keep until the canonical CEA/ICED adapters land (Phase 2). Then retire under §7c.
5. **`backend/yen_gov/core/io.py::write_artifact`** — `_OPERATIONAL_STRIP_PATHS` and the dict-equal write-skip gate are dead under canonical writer (R6/R7). Retire with Phase 1.8 `_old/` deletion.

---

## See also

- [THE PLAN](../../TODO/20260517-canonical-long-format-pivot.md) — single source of truth.
- [`CLAUDE.md`](../../CLAUDE.md) — engineering contract.
- [`docs/agents/guardrails.md`](../agents/guardrails.md) — rules digest.
- ADR-0030 (Phase 0.1, to author) — canonical store + DuckDB-WASM full rationale.
- ADR-0031 (Phase 0.14, to author) — boundary geometry strategy.
- `docs/architecture/data/canonical-store.md` (Phase 0.2, to author) — target architecture.
