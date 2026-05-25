# Canonical long-format pivot — handover plan

**Last Updated**: 2026-05-25
**Status**: Phase 0 ✅ + Phase 1 elections deletion sweep ✅ + T.1 (`_test/`→`_ops/` hygiene) ✅ + G.1 (office-bearers consolidation) ✅ + **T.0d (boundaries consolidation — Hive partitioning + parquet ledger) ✅ MERGED 2026-05-22 (`9e2ee3db`)** + **T.0e (`STATE_NAME_TO_ECI` retirement → states view-model via taxonomy.entities) ✅ MERGED 2026-05-22 (PR #96, `de463eca`)** + **T.2 (topic-catalogue schema bump v1.2→v1.3 + 9 placeholder topics + doc-ref scrub) ✅ MERGED 2026-05-24 (PR #182, `39f42b9c`)** + **T.3 (indicator catalogue v1.1) ✅ MERGED 2026-05-23** (PR #107, `0a8d8e83`). **Phase 2 P.1 = Energy** is the active phase; sub-commits C0-C4 + **C4.5 CEA per-state per-fuel snapshot lift (lift-only — reader-switch deferred per PR #177 strangler-fig lesson)** + **C4.6 RBI Handbook Table 140 FY05-FY14 long-arc splice (SHIP-LIFT-ONLY — reader-switch + legacy-shard retire deferred to follow-up)** + **C4.8 sub-fuel preservation (Option B additive — methodology_breaks row + Tier-B fence; shard retire descoped to follow-up)** + **P.1.B DISCOM finance + demand/supply extension (SHIP-LIFT-ONLY, this PR — 6 new canonical indicators on `energy_distribution_performance.parquet` + `energy_demand_supply.parquet`; +5 source ledger rows; +2 facet axes `efficiency_dimension` + `rpo_segment`; frontend allowlist + topics.json retire-edits + legacy-shard `git rm` deferred to subsequent PRs mirroring the P.1.A C5+C6 pattern)** MERGED to main (PR #101 umbrella `4f79e319` + PR #106 C4 replay `e04f85a6` + C4.5 PR + C4.6 PR + C4.8 PR + this PR); **C5+C6 (reader-switch + legacy retire) is the next PR and remains DEFERRED pending Hans+Max+Gregor design pass for `fetchIndicatorFromCanonical(id)` shape**. Planning + design lives at [`TODO/20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md). Other Phase 2 pre-flight rows still in-flight: S.1 (persons fork rename — ready).
**Spec**: [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md) (disk layout, write/read paths, schemas).
**Decision rationale**: [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) (canonical store + DuckDB-WASM, D1–D36 verbatim) + [ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) (boundaries) + [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) (sources citation ledger) + [ADR-0035](../docs/architecture/decisions/0035-persons-fork-option-b.md) (persons fork).
**Doc-class routing rule**: this is a **plan-doc** per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md); carries phase status + active PRs + TBD only; no rationale, no rejected alternatives, single-snapshot header rule applies.
**Execution history before 2026-05-22**: [`docs/archive/canonical-pivot-plan-20260522-snapshot.md`](../docs/archive/canonical-pivot-plan-20260522-snapshot.md) — verbatim pre-slim snapshot of this file with all the executed-phase narrative.

---

## §0a. The One Rule (pointer)

**OWID is the canonical reference for socio-economic data modelling** (CLAUDE.md §0a). When any data-shape question arises, first check OWID; if OWID has solved it, adopt verbatim; if yen-gov must deviate, document the deviation in [`canonical-store.md`](../docs/architecture/data/canonical-store.md) with rationale signed off by Hans + Max.

Authority assignment (resolves agent stalls): Hans + Max on data shape; Gregor on contracts; Fowler on engineering craft; Jony + Citizen on UX. User approval supersedes every agent.

## §0b. Cardinality is a moving target

Today's corpus is ~110 socio-economic indicators across 9 topics. Phase 2/3 ingestion takes this to ~500. Phase 4/5 (judiciary, healthcare, water, crime, education-deep, welfare, local-govt-finance) takes it to 1,000+. Plan for the 1,000+ shape, not the 110 shape. Every design decision is evaluated against "does this survive 10x growth" — corner cases at today's scale become governance defects at tomorrow's.

## §0c. Boundaries preservation (critical, do not delete)

`datasets/boundaries/in/` is **not** legacy. It is a sibling family to the canonical Parquet store ([ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md)). No step in this pivot moves, renames, or deletes anything under that tree; future additions (PCs, taluks, village coverage) follow the same `{geojson|pmtiles}/<layer>.<ext>` layout.

## §0d. Status vocabulary (resolves "what does DONE mean" drift)

| Token | Meaning |
| :-: | --- |
| ✅ DONE | Shipped on `main`; commit SHA cited; on-disk evidence verified. |
| ⏳ ACTIVE | PR open or in progress on a feature branch; not yet on `main`. |
| ◻ QUEUED | Designed; awaiting a prerequisite to land. |
| ⊘ DROPPED | Original scope retired; replacement pattern cited inline. |
| 🔒 BLOCKED | Cannot proceed; named blocker + responsible party cited inline. |

## §0e.7. Active PR ledger (six-PR strangler-fig sequence)

Each PR independently mergeable, each reversible. Two-hat discipline: purely structural (paths / renames / no row content change) OR purely behavioural (schema rows change). Fused atomic per the §15 paired-test discipline when `$schema_version == x-version` strict check applies.

| # | PR | Status | Hat | Depends on |
| - | --- | :-: | --- | --- |
| **T.1** | Tidy first — dir hygiene. Delete `_test/`. Create `_ops/`. Move operator state → `_ops/`. Audit `features/` (delete or document). Update `manifest.json` `path` fields. | ✅ DONE 2026-05-22 (`feat/hard-pivot-t1-and-legacy-namespace`) | structural | — |
| **T.2** | Lift topic catalogue into taxonomy. Move `reference/in/topic-catalogue.json` → `taxonomy/topics.json`. Add `backend/yen_gov/canonical/topics_seed.py`. Compile `taxonomy/topics.parquet`. **Add new top-level topics** per [topic-taxonomy concept](../docs/concepts/topic-taxonomy.md) (`governance`, `schemes`, `local_govt_finance`, `work`, `judiciary`, `crime`, `health`, `education`, `amenities`, `technology`). Retire `reference/in/`. | ✅ DONE 2026-05-24 (this PR — schema v1.2→v1.3 minor bump: `topics.items.artifacts.minItems` 1→0; pydantic `_Topic.artifacts` default `[]`; 9 placeholder topics added with empty artifacts arrays — `governance` / `schemes` / `local_govt_finance` / `work` / `judiciary` / `crime` / `education` / `amenities` / `technology` — each carrying `notes` with Hans-review flags for edge-case Seventh-Schedule placements and Jony-review flag for the `local_govt_finance` ULB acronym; per-topic landing pages OPEN on each P.\* ingestion. Lift of `reference/in/topic-catalogue.json` → `taxonomy/topics.json` happened in T.0b (`frontend/src/lib/catalogue.ts:97` already points at `taxonomy/topics.json`); this PR scrubs 7 stale doc references and 1 bonus reference in `peer-sets.md`. `health` topic already existed in `topics.json` and is NOT re-added — dedupe handled in JSON edit.) | structural | T.1 |
| **T.3** | Indicator catalogue widens for topic tags + drops topic prefix. Bump `indicator.schema.json` minor: add `topic_tags[]` (FK → `taxonomy/topics.parquet`), add `id_aliases[]` (one-release back-compat), enforce new id shape per `canonical-store.md §2a`. Migrate 110 legacy ids; populate `id_aliases` with old `<topic>/<id>` form; frontend dereferences via alias. Add `taxonomy/indicator_topic_tags.parquet` M:N join + `topic_tags[]` denormalised projection on `taxonomy/indicators.parquet`. **Fused atomic commit.** | ✅ MERGED 2026-05-23 (PR #107 v1.1 replay onto main `0a8d8e83`, after stacked PR #98 was auto-closed on PR #101 squash-merge — 5 cherry-picked commits `57c78892` / `cac95f32` / `5e450051` / `dbb304a5` / `d11901ec`). Schema v1.0→v1.1 (`topic_tags[]` + `id_aliases[]` + `deprecated_in`); Tier-B `tier_b_indicator_alias_window` enforces 60-day grace; first frontend canonical-Parquet reader landed at [`frontend/src/lib/indicator-catalogue.ts`](../frontend/src/lib/indicator-catalogue.ts). 110 legacy id rewrites + frontend dereferencer remain DESCOPED — each family's P.* PR rewrites its own ids and fills `id_aliases[]` at lift time, per the Q2 = Option A scope. | structural + behavioural (fused) | T.2 + P.1.A merge |
| **S.1** | Persons Option B — one shot. Rename `dim_candidates` → `dim_persons` (schema bump major; `id_aliases` keeps old shape for one release). Add `elections/elections_candidacies.parquet` fact. Add `taxonomy/person_aliases.json` + compiled `taxonomy/persons.parquet`. Seed person clusters for TN-AE using TCPD `Candidate_ID` groupings as **editorial input only**; `source_id` cites **ECI candidate lists directly** (TCPD repackages ECI data — no separate TCPD citation per user 2026-05-22). Delete `datasets/people/AcGenApr2021/`. Fused atomic commit. Runs in parallel with T.1+T.2+T.3 (no contention). Design + rejected alternatives: [ADR-0035](../docs/architecture/decisions/0035-persons-fork-option-b.md). | ✅ DONE 2026-05-23 (PR #176 `8d11c376` — 34906 persons / 34906 candidacies / 34906 taxonomy.persons; Layer-1 collision repair shipped; `taxonomy/person_aliases.json` ships with empty `clusters` per S.1 asserts no cross-candidacy merges yet — Layer-3 TCPD seed is a separate later effort per ADR-0035 layering) | structural + behavioural (fused) | independent (parallel with T.x) |
| **T.0d** | Boundaries consolidation. Lift 73 `.sources.json` sidecars onto `taxonomy/sources.parquet` per §12 v2.0 (FK pattern matches Energy; **4 sources seeded** — DataMeet/HTL/shijithpk/ramSeraph; postal subtree forward-looking only). Fold 39 `.metadata.json` + 2 `.unkeyed.json` + 1 `S22-villages-index.json` into NEW `datasets/boundaries/boundary_layers.parquet` control table (15 columns; 12 required + 3 optional). Restructure `datasets/boundaries/in/` to Hive partitioning matching `elections/state=in_<S>/...` across 8 admin-spine levels (`country/`, `states/`, `districts/`, `ac/`, `pc/`, `subdistricts/`, `villages/`, `postal/`). Fused atomic per §15: 1 new schema + 3 deleted schemas + new Pydantic + `tools/boundaries/snapshot.py` rewrite + `frontend/src/lib/maplibre/sources.ts` path repointing + ADR-0031 amendment + Tier-B forbidden-paths gate + 115 sidecar deletions + 73 `git mv` of geometry files. Methodology breaks remain on `taxonomy/entities.parquet` (already canonical, no T.0d change). **Spec**: [T.0d execution spec](20260522-t0d-boundaries-consolidation-spec.md) (Gregor + Hans + Max, 2026-05-22; OPENs all resolved by user 2026-05-22). Spec at `TODO/20260522-t0d-boundaries-consolidation-spec.md` (status flipped MERGED in same docs PR). | ✅ DONE 2026-05-22 (`9e2ee3db`) | structural + behavioural (fused) | independent (parallel with T.x); can run in parallel with Energy P.1.A |
| **T.0e** | `STATE_NAME_TO_ECI` map retirement. Replace the inline frontend constant (in `frontend/src/lib/maplibre/sources.ts:217`) with a DuckDB-WASM `loadStates()` view-model querying `taxonomy.entities WHERE entity_type IN ('state','ut')`. The constant currently masks the three coexisting code systems (ECI: `S22`; LGD/MoHA: `33`; ISO 3166-2: `IN-TN`) by exposing only the ECI projection. `taxonomy/entities.parquet` already carries all three (`legacy_id`, `lgd_code`, `iso_3166_2`). 9 frontend files touched (Home, CompareIndicator, IndicatorChoropleth, IndicatorRanked, IndicatorSmallMultiples, IndiaMap, drilldown.ts + 2 routes). Many call sites are synchronous (`Object.entries(STATE_NAME_TO_ECI)`) and need converting to async-aware. §13 browser smoke MANDATORY on every indicator route + Home + Compare. Separate PR (carved out of T.0d on user direction 2026-05-22). View-model at `frontend/src/lib/view-models/states.ts` (Hive-paths consumer; exposes ECI/LGD/ISO_3166_2 alongside boundary_join_name override table). | ✅ DONE 2026-05-22 (PR #96, `de463eca`) | structural + behavioural (fused) | depends on T.0d (boundary-paths must stop using the constant first) |
| **G.1** | Office-bearers consolidation. 3-PR strangler-fig (G.1.a entity-lift → G.1.b reader-switch → G.1.c consolidate + retire). | ✅ DONE 2026-05-22 (PRs #89 / #90 / #91; see [G.1 handover](20260522-g1-cm-terms-retirement-handover.md)) | structural + behavioural (fused per sub-PR) | (ran without T.3/S.1 — office identity is its own taxonomy island per §0e.6 of the snapshot) |
| **P.\*** | **Per-family pivot — Phase 2 active phase.** Each family from the topic taxonomy becomes its own sub-PR following the §2a naming rule + FK contract + empty-parent pruning. **P.1 = Energy** (active; plan at [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md)). | ⏳ ACTIVE (P.1 = Energy; sub-commits C0-C4 + C4.5 + C4.6 + C4.8 MERGED + **P.1.B SHIP-LIFT-ONLY MERGED via this PR**; C5+C6 reader-switch + legacy retire DEFERRED pending design pass; P.1.B Phases B–D + P.1.C + P.1.D follow) | structural + behavioural (fused per family) | T.3 (P.\* can start before T.3 if family-specific schema bump is independent — Energy is in this position) |

## §0e.8. Active retirement ledger

| Old path | Replacement | Retiring PR | Status |
| --- | --- | --- | :-: |
| `datasets/reference/in/topic-catalogue.json` | `datasets/taxonomy/topics.parquet` (compiled from `taxonomy/topics.json`) | T.2 | ✅ DONE 2026-05-24 (path lift completed in T.0b; T.2 ships schema v1.3 + 9 placeholder topics + doc-ref scrub) |
| `datasets/reference/in/election-events.json` | `datasets/taxonomy/election_events.parquet` (pure-reference table — see snapshot §0e.10.2.E) | T.2 | ◻ QUEUED |
| `datasets/reference/in/states/<S>/districts.json` | already DONE per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md) — districts folded into `taxonomy/entities.parquet` as `entity_type='district'` | T.0c (PR #68) | ✅ DONE 2026-05-21 |
| `datasets/indicators/in/energy/` | per-family Parquet at `datasets/<family>/<family>_<role>.parquet` + `datasets/taxonomy/indicators.parquet` row | P.\* (per family) | ⏳ ACTIVE (Energy: 4 active adapters migrated to `datasets/energy/_meadow/<source>/<vintage>/` via 7c-N PRs #249/#251/#252/#253/#255, 2026-05-25; 13 residue shards await per-shard triage per §0e.8a) |
| `datasets/people/AcGenApr2021/` | `datasets/elections/dim_persons.parquet` + `taxonomy/persons.parquet` | S.1 | ✅ DONE 2026-05-23 (PR #176 `8d11c376`) |
| `datasets/boundaries/in/geojson/*.{sources,metadata,unkeyed}.json` (115 sidecars) + `S22-villages-index.json` | `datasets/boundaries/boundary_layers.parquet` + FK to `taxonomy/sources.parquet` | T.0d | ✅ DONE 2026-05-22 (`9e2ee3db`) |
| Flat `datasets/boundaries/in/geojson/*.geojson` (73 files) | Hive-partitioned `datasets/boundaries/in/{country,states,districts,ac,pc,subdistricts,villages,postal}/state=<S>/...` per [T.0d spec §1](20260522-t0d-boundaries-consolidation-spec.md) | T.0d | ✅ DONE 2026-05-22 (`9e2ee3db`) |

## §0e.8a. Pending-work tracker (compact)

User-requested 2026-05-25 — single-glance enumeration of what's NOT done. Updated as PRs ship. Done work intentionally omitted; this is a **pending-only** view.

**Recently shipped (since prior snapshot — removed from this table per the pending-only rule)**: S.1 persons fork via PR #176 (`8d11c376`, 2026-05-23 — `dim_persons` + `elections_candidacies` + compiled `taxonomy/persons.parquet`; ledger row flipped via PR #256 `de6c4774`); 7c-N meadow-tier energy migration for the 4 active adapters via PR #249 `c98ed0e2` (7c-0 ADR-0041) + PR #251 `b071fffd` (7c-1 generation) + PR #252 `dc989509` (7c-2 distribution) + PR #253 `a5a1f3d0` (7c-3 demand_supply) + PR #255 `6a57efd8` (7c-4 installed_capacity + `load_shard()` retirement). 23 energy shards now live under `datasets/energy/_meadow/<source>/<vintage>/`; `_shared.load_shard()` deleted from `backend/yen_gov/canonical/adapters/energy/_shared.py`.

| Slice | Status | Why pending |
| --- | :-: | --- |
| **P.1 Energy — 7c-N residue triage** (13 shards still in `datasets/indicators/in/energy/` after 7c-N closed the 4 active adapters) | ◻ NEXT | Inventory + classify the 13 leftovers as one of: (a) composer/aggregate (`installed_capacity_total_mw`, `installed_capacity_thermal_mw` — compute-on-read per D33.8); (b) input to a NON-energy/installed-capacity adapter (search `load_shard` / `load_meadow` call sites in `backend/yen_gov/canonical/adapters/`); (c) dead — no consumer (forward to P.1.C/P.1.D as future-canonical input or `git rm`). Per-shard `git mv` or `git rm` once classified. Completion criterion (ADR-0041): `git ls-tree origin/main -- datasets/indicators/in/energy/` returns empty. |
| **P.1 Energy — Tier-B fence file rename** (`datasets/_ops/meadow-shard-contract.txt` → `datasets/_ops/meadow-shard-contract.txt`) | ◻ READY | DEFERRED from PR 7c-4 per ADR-0041 §Doc-impact. Rename + rewrite header from "countdown to retirement" → "perimeter for canonical-input contract" + update `backend/yen_gov/validate.py` `tier_b_meadow_shard_contract` symbol + every doc reference. Safe to fold into the 7c-residue PR. |
| **P.1 Energy — sources.parquet vintage backfill + Tier-B vintage check** | ◻ READY | The meadow path encodes `<vintage>` (e.g. `2024-25`); the citation-ledger row the shard's `source_id` resolves to MUST carry the same string in its `vintage` field. Backfill the ICED + RBI 2024-25 rows where the vintage was empty pre-7c; add Tier-B rule `tier_b_meadow_vintage_matches_source_id` that walks `_meadow/*/`, derives `(source, vintage)` from the path, and asserts the lift output's `source_id` resolves to a row with `producer = <source>` AND `vintage = <vintage>` per ADR-0041 non-negotiable #4. |
| **P.1 Energy — PR 7b.1** FacetPicker primitive + IndicatorCard facet awareness | ◻ READY | Unblocks RPO citizen render (placeholder currently shown). Independent of 7c-N. |
| **P.1 Energy — PR 7d** IA editorial pass | ◻ READY | Prune 36-card wall, ACS-ARR copy rewrite per Citizen, scroll-narrative cascade. Independent of 7c-N. |
| **Citizen-1 panel** Hans+Gregor §10 carve-out for <2s mobile first-paint vs DuckDB-WASM warm-up | ◻ OPEN ARCHITECTURE | Design question; not a PR yet. |
| **P.1 Energy — P.1.C + P.1.D** (remaining energy sub-pivots) | ◻ QUEUED | Sequenced after 7c-N residue triage closes. |
| **P.2 Livestock — NDLM ingest** (Bharat Pashudhan: owner-registrations, Pashu Aadhaar, NADCP vaccination, breeding interventions, NAIP IV outcomes; 16 indicators across 5 fact tables; new `agriculture` topic umbrella) | ◻ QUEUED | Per-family plan: [`TODO/20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md). Sub-plans: [`TODO/20260525-pashu-aadhaar-ingest-plan.md`](20260525-pashu-aadhaar-ingest-plan.md) (Hans honest-renderer call). Foundation: LGD-district recon foreclosed (588/588 join, zero FK-drops); TN download proof shipped to `.runtime/`. Phase 0 (taxonomy seed) → Phase 1 (meadow lifts × 5 endpoints) → Phase 2 (canonical writer + indicators.json) → Phase 3 (frontend allowlist). CY+FY duality natively supported by PK `(entity_id, year, period_label, indicator_id)`; no schema bump needed. Adopts meadow-tier path from day one (no Phase-C debate). |
| **Phase 2 P.2+** (~10 more families: NFHS-5, PLFS, UDISE+, AISHE, NCRB, HCES, IMD, e-GramSwaraj-PFMS, TRAI, CAG) | ◻ QUEUED | Bulk of remaining Phase 2. Each adopts the meadow-tier authoring path from day one — no Phase-C debate per family. |
| **Phase 3** Demography/Fiscal/Education/Health backfill | Sketch only | Opens when Phase 2 closes. |
| **Phase 4** SLM dispatcher | Sketch only | Opens when Phase 3 closes. |
| **Phase 5** Admin app rewrite (Schemas/Pipeline/Patches panels) | Sketch only | Inventory v0 shipped; rest waits on Phase 4. |
| **Open** `taxonomy/topics.parquet` rollout scheduling for 9 new placeholder topics | OPEN | Needs Max indicator-priority ordering. |
| **Open** `facet-axes` extensions as families need new axes | OPEN per-family | Each new axis needs Max sign-off when its family ingests. |

**Rough completion estimate**: ~18-22% of the full canonical pivot. Phase 1 done; 1 of ~11 families (Energy) with 4 of N adapters on meadow + canonical (residue triage still open); Phases 3-5 are sketches.

## §0e.8b. Strategy F — Meadow-tier rename (ratified 2026-05-25 by Hans + Max + Gregor)

**Decision**: The shards currently under `datasets/indicators/in/<topic>/<id>.json` ARE OWID's `meadow` tier — parsed publisher rows, deterministic, schema-validated, FK-bearing, but pre-canonical. They live at a misleading path (looks citizen-facing; is backend-only). The fix is to **rename** them to `datasets/<family>/_meadow/<source>/<vintage>/<file>.json` — NOT `git rm` them.

Five OWID-aligned tiers (per §0a "The One Rule"): `upstream → snapshots (ephemeral, `.runtime/raw/`) → meadow (committed, `datasets/<family>/_meadow/`) → canonical (committed, `datasets/<family>/<family>_<role>.parquet`) → grapher (frontend view-models)`.

**Why F not Hans's (c)** (reframe-in-place): the path lie persists; Tier-B validator becomes ceremony; no forcing function for Phase B allowlist completion.

**Why F not Max's (b)/α** (`datasets/_raw/<source>/` committed): Max picked the wrong OWID tier; `etl/snapshots/` is bytes-in-git (different from meadow). yen-gov already HAS the meadow tier (typed, parsed); promoting `.runtime/raw/` adds a NEW layer at high repo-size cost (~550 MB ICED alone) when the typed layer already does the job.

**Forcing function**: each per-adapter `git mv` simultaneously (a) repoints the backend canonical adapter, (b) breaks any legacy frontend `fetch('/data/indicators/in/...')` URL → forces Phase B allowlist to be the only path, (c) deletes the old path. Phase-C + Phase-D + C5 unified per slice.

**Completion criterion**: `datasets/indicators/in/` does not exist on `main`. Single `git ls-tree` query.

**Doc impact** (lands in PR 7c-0):
- NEW: [`docs/concepts/meadow-tier.md`](../docs/concepts/meadow-tier.md) — define meadow vocabulary, meadow→canonical contract, OWID precedent, "no frontend fetch from `_meadow/`" rule.
- NEW: [ADR-0041 "Meadow tier — parsed publisher rows as canonical input"](../docs/architecture/decisions/0041-meadow-tier.md) — captures F-vs-(a/b/c/d) tradeoff with rejected alternatives.
- AMEND: CLAUDE.md §4 — add "`datasets/<family>/_meadow/` is backend-internal. Frontend MUST NOT fetch from it."
- AMEND: CLAUDE.md §10 — replace "Create new indicator artifact files under `datasets/indicators/in/<topic>/<id>.json`" entry with "Write parsed publisher rows anywhere except `datasets/<family>/_meadow/<source>/<vintage>/<file>.json`."
- AMEND: [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md) §2 — add `_meadow/` to per-family directory invariant + backend-only consumer constraint.
- DEFERRED to PR 7c-4: rename `datasets/_ops/meadow-shard-contract.txt` → `meadow-shard-contract.txt`; rewrite header from "countdown to retirement" → "perimeter for canonical-input contract."

**Non-negotiables** (Gregor + Hans):
1. No backend writes outside `datasets/<family>/_meadow/<source>/<vintage>/` for staging.
2. CLAUDE.md §4 layer rule MUST land in 7c-0.
3. No network at lift, ever; `.runtime/raw/` stays gitignored ephemeral.
4. Vintage in meadow path MUST match `vintage` field of citation row the FK resolves to.
5. Sequencing: 7c-1 introduces `load_meadow`; 7c-4 retires `load_shard` atomically.
6. No editorial creep into 7c-N PRs — structural rename + adapter switch + allowlist + smoke only.
7. Methodology breaks (RBI Table 140 ↔ 142 splice etc) render visibly on chart, not just in `methodology_breaks.parquet` (Hans non-negotiable).

## §0e.9. Cross-refs

- **Disk layout + write/read paths**: [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md)
- **Topic taxonomy vocabulary**: [`docs/concepts/topic-taxonomy.md`](../docs/concepts/topic-taxonomy.md)
- **Sources citation ledger v2.0**: [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) + [`docs/concepts/data-provenance.md`](../docs/concepts/data-provenance.md)
- **Persons fork design**: [ADR-0035](../docs/architecture/decisions/0035-persons-fork-option-b.md)
- **Doc-class routing rule**: [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md)
- **Active Phase 2 P.1 (Energy) plan**: [`TODO/20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md)
- **T.0d boundaries consolidation spec**: [`TODO/20260522-t0d-boundaries-consolidation-spec.md`](20260522-t0d-boundaries-consolidation-spec.md)
- **Pre-slim execution history**: [`docs/archive/canonical-pivot-plan-20260522-snapshot.md`](../docs/archive/canonical-pivot-plan-20260522-snapshot.md)

---

## §1. Phase 2 — Per-family ingestion (active)

The Phase 2 P.\* sequence ingests one family at a time. Each family lands as a fused atomic commit per the §15 paired-test discipline (schema + Pydantic model + DDL + parquet emit + frontend reader switch + deletion of legacy shards for that family). Per-family sequencing is fluid: the order below reflects acquired authority + Max's indicator-priority ranking; deviation requires Max sign-off.

| # | Family | Status | Active doc | Notes |
| - | --- | :-: | --- | --- |
| P.1 | **Energy** | ⏳ ACTIVE | [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md) | 41 legacy indicator JSONs under `datasets/indicators/in/energy/`. Sources: RBI Handbook, ICED, CEA, NITI Aayog, MNRE. First family pivot — establishes the per-family P.\* pattern subsequent families follow. |
| P.2+ | NFHS-5 / health, PLFS / work, UDISE+ / education, AISHE / education-higher, NCRB / crime, HCES / consumption, IMD / environment, e-GramSwaraj-PFMS / local-govt-finance, TRAI / technology, CAG / fiscal-audits | ◻ QUEUED | TBD per family | Max-recommended ordering; each lands its own plan-doc when active. |

## §2. Phase 3 — Demography / Fiscal / Education / Health (sketch)

Phase 3 backfills the structural-coverage gaps after Phase 2 lands the issuing-authority series. Targets: Census 2011 H-series, SRS, CRS, GSDP base-year breaks, methodology-break ledger, HMIS monthly. Detailed plan opens when Phase 2 closes.

## §3. Phase 4 — SLM dispatcher (sketch)

Phase 4 introduces the small-language-model (Phase 4/5 spec in the [snapshot §10–§11](../docs/archive/canonical-pivot-plan-20260522-snapshot.md)) that grounds citizen Q&A against the canonical Parquet store. Detailed plan opens when Phase 3 closes.

## §4. Phase 5 — Admin rewrite (sketch)

Phase 5 rewrites the operator admin app on top of the canonical store — Inventory (already shipped Phase-0 / Phase-1 v0), Schemas, Pipeline, Patches. Detailed plan opens when Phase 4 stabilises.

## §5. Open questions (resolve before the relevant phase)

- **`taxonomy/topics.parquet` rollout for the 10 new top-level topics** (`governance` / `schemes` / `local_govt_finance` / `work` / `judiciary` / `crime` / `health` / `education` / `amenities` / `technology`) — **structural slots SHIPPED 2026-05-24 (this PR, T.2)** with empty `artifacts[]` (schema v1.3 permits `artifacts.minItems: 0`). `health` already existed pre-T.2 so 9 placeholders were authored (not 10). Per-topic landing pages open with their P.\* ingestion. Scheduling per Max indicator-priority ordering remains open.
- **`facet-axes` extension as families land** — `fuel_type` is locked for Energy; subsequent families may need new axes. Each new axis requires Max sign-off + a row in `taxonomy/facet-axes.parquet` via `backend/yen_gov/canonical/facet_axes_seed.py` per [`canonical-store.md` §8.3](../docs/architecture/data/canonical-store.md).
- **Phase 3 priority** (NFHS-5 vs PLFS first) — defer until Phase 2 P.\* sequencing stabilises and Max re-runs the priority pass with shipped-vs-pending coverage in hand.

## §6. Handoff (instructions for the next coding agent)

Read these, in this order, before touching code:

1. **[CLAUDE.md](../CLAUDE.md)** — Holy Laws, doc-class routing rule, correction levels.
2. **[ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md)** — every D1–D36 decision about the canonical store.
3. **[canonical-store.md](../docs/architecture/data/canonical-store.md)** — current disk layout + naming + schema shape.
4. **[ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md)** — sources are a citation ledger keyed on `(producer, title, vintage)`; fetch telemetry never crosses into citizen-facing rows.
5. **[ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md)** — which doc class owns which kind of statement.
6. **This file** — what's shipped, what's active, what's blocked.
7. **[Active Phase 2 P.1 (Energy) plan](20260522-phase-2-p1-energy-pivot.md)** — the family currently being pivoted.

Pre-flight check before opening a PR on this arc:

- Identify your **Correction Level** per CLAUDE.md §6. A P.\* family pivot is Level 4 (large-scale, structural + behavioural fused per family).
- Confirm your change is a **paired Tier-A commit** per CLAUDE.md §15 — schema bump + Pydantic model + DDL + parquet emit + frontend reader switch + deletion gate, all in one commit.
- Run the **parity oracle** the pivot tradition uses ([`backend/tests/test_canonical_parity_oracle.py`](../backend/tests/test_canonical_parity_oracle.py)) — assert per-AC FPTP winners byte-stable across the swap.
- Run the **§13 browser smoke** on at least one citizen-facing route the change touches.
- Validate `python -m yen_gov validate --root .` clean before commit.

When in doubt, escalate (dispatch the relevant custom agent: Hans for data shape, Max for indicator choice, Gregor for contract design, Fowler for engineering craft, Jony for UX, Citizen for sanity check). User approval supersedes every agent.
