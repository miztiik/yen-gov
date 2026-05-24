# Canonical long-format pivot — handover plan

**Last Updated**: 2026-05-24
**Status**: Phase 0 ✅ + Phase 1 elections deletion sweep ✅ + T.1 (`_test/`→`_ops/` hygiene) ✅ + G.1 (office-bearers consolidation) ✅ + **T.0d (boundaries consolidation — Hive partitioning + parquet ledger) ✅ MERGED 2026-05-22 (`9e2ee3db`)** + **T.0e (`STATE_NAME_TO_ECI` retirement → states view-model via taxonomy.entities) ✅ MERGED 2026-05-22 (PR #96, `de463eca`)** + **T.2 (topic-catalogue schema bump v1.2→v1.3 + 9 placeholder topics + doc-ref scrub) ✅ MERGED 2026-05-24 (PR #182, `39f42b9c`)** + **T.3 (indicator catalogue v1.1) ✅ MERGED 2026-05-23** (PR #107, `0a8d8e83`). **Phase 2 P.1 = Energy** is the active phase; sub-commits C0-C4 MERGED to main (PR #101 umbrella `4f79e319` + PR #106 C4 replay `e04f85a6`); **C5+C6 (reader-switch + legacy retire) is the next PR and remains DEFERRED pending Hans+Max+Gregor design pass for `fetchIndicatorFromCanonical(id)` shape**. Planning + design lives at [`TODO/20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md). Other Phase 2 pre-flight rows still in-flight: S.1 (persons fork rename — ready).
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
| **S.1** | Persons Option B — one shot. Rename `dim_candidates` → `dim_persons` (schema bump major; `id_aliases` keeps old shape for one release). Add `elections/elections_candidacies.parquet` fact. Add `taxonomy/person_aliases.json` + compiled `taxonomy/persons.parquet`. Seed person clusters for TN-AE using TCPD `Candidate_ID` groupings as **editorial input only**; `source_id` cites **ECI candidate lists directly** (TCPD repackages ECI data — no separate TCPD citation per user 2026-05-22). Delete `datasets/people/AcGenApr2021/`. Fused atomic commit. Runs in parallel with T.1+T.2+T.3 (no contention). Design + rejected alternatives: [ADR-0035](../docs/architecture/decisions/0035-persons-fork-option-b.md). | ◻ READY | structural + behavioural (fused) | independent (parallel with T.x) |
| **T.0d** | Boundaries consolidation. Lift 73 `.sources.json` sidecars onto `taxonomy/sources.parquet` per §12 v2.0 (FK pattern matches Energy; **4 sources seeded** — DataMeet/HTL/shijithpk/ramSeraph; postal subtree forward-looking only). Fold 39 `.metadata.json` + 2 `.unkeyed.json` + 1 `S22-villages-index.json` into NEW `datasets/boundaries/boundary_layers.parquet` control table (15 columns; 12 required + 3 optional). Restructure `datasets/boundaries/in/` to Hive partitioning matching `elections/state=in_<S>/...` across 8 admin-spine levels (`country/`, `states/`, `districts/`, `ac/`, `pc/`, `subdistricts/`, `villages/`, `postal/`). Fused atomic per §15: 1 new schema + 3 deleted schemas + new Pydantic + `tools/boundaries/snapshot.py` rewrite + `frontend/src/lib/maplibre/sources.ts` path repointing + ADR-0031 amendment + Tier-B forbidden-paths gate + 115 sidecar deletions + 73 `git mv` of geometry files. Methodology breaks remain on `taxonomy/entities.parquet` (already canonical, no T.0d change). **Spec**: [T.0d execution spec](20260522-t0d-boundaries-consolidation-spec.md) (Gregor + Hans + Max, 2026-05-22; OPENs all resolved by user 2026-05-22). Spec at `TODO/20260522-t0d-boundaries-consolidation-spec.md` (status flipped MERGED in same docs PR). | ✅ DONE 2026-05-22 (`9e2ee3db`) | structural + behavioural (fused) | independent (parallel with T.x); can run in parallel with Energy P.1.A |
| **T.0e** | `STATE_NAME_TO_ECI` map retirement. Replace the inline frontend constant (in `frontend/src/lib/maplibre/sources.ts:217`) with a DuckDB-WASM `loadStates()` view-model querying `taxonomy.entities WHERE entity_type IN ('state','ut')`. The constant currently masks the three coexisting code systems (ECI: `S22`; LGD/MoHA: `33`; ISO 3166-2: `IN-TN`) by exposing only the ECI projection. `taxonomy/entities.parquet` already carries all three (`legacy_id`, `lgd_code`, `iso_3166_2`). 9 frontend files touched (Home, CompareIndicator, IndicatorChoropleth, IndicatorRanked, IndicatorSmallMultiples, IndiaMap, drilldown.ts + 2 routes). Many call sites are synchronous (`Object.entries(STATE_NAME_TO_ECI)`) and need converting to async-aware. §13 browser smoke MANDATORY on every indicator route + Home + Compare. Separate PR (carved out of T.0d on user direction 2026-05-22). View-model at `frontend/src/lib/view-models/states.ts` (Hive-paths consumer; exposes ECI/LGD/ISO_3166_2 alongside boundary_join_name override table). | ✅ DONE 2026-05-22 (PR #96, `de463eca`) | structural + behavioural (fused) | depends on T.0d (boundary-paths must stop using the constant first) |
| **G.1** | Office-bearers consolidation. 3-PR strangler-fig (G.1.a entity-lift → G.1.b reader-switch → G.1.c consolidate + retire). | ✅ DONE 2026-05-22 (PRs #89 / #90 / #91; see [G.1 handover](20260522-g1-cm-terms-retirement-handover.md)) | structural + behavioural (fused per sub-PR) | (ran without T.3/S.1 — office identity is its own taxonomy island per §0e.6 of the snapshot) |
| **P.\*** | **Per-family pivot — Phase 2 active phase.** Each family from the topic taxonomy becomes its own sub-PR following the §2a naming rule + FK contract + empty-parent pruning. **P.1 = Energy** (active; plan at [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md)). | ⏳ ACTIVE (P.1 = Energy; sub-commits C0-C4 MERGED via PR #101 + PR #106; C5+C6 reader-switch + legacy retire DEFERRED pending design pass) | structural + behavioural (fused per family) | T.3 (P.\* can start before T.3 if family-specific schema bump is independent — Energy is in this position) |

## §0e.8. Active retirement ledger

| Old path | Replacement | Retiring PR | Status |
| --- | --- | --- | :-: |
| `datasets/reference/in/topic-catalogue.json` | `datasets/taxonomy/topics.parquet` (compiled from `taxonomy/topics.json`) | T.2 | ✅ DONE 2026-05-24 (path lift completed in T.0b; T.2 ships schema v1.3 + 9 placeholder topics + doc-ref scrub) |
| `datasets/reference/in/election-events.json` | `datasets/taxonomy/election_events.parquet` (pure-reference table — see snapshot §0e.10.2.E) | T.2 | ◻ QUEUED |
| `datasets/reference/in/states/<S>/districts.json` | already DONE per [ADR-0033](../docs/architecture/decisions/0033-retire-wikipedia-districts-adapter.md) — districts folded into `taxonomy/entities.parquet` as `entity_type='district'` | T.0c (PR #68) | ✅ DONE 2026-05-21 |
| `datasets/indicators/in/<topic>/` | per-family Parquet at `datasets/<family>/<family>_<role>.parquet` + `datasets/taxonomy/indicators.parquet` row | P.\* (per family) | ⏳ ACTIVE (Energy first) |
| `datasets/people/AcGenApr2021/` | `datasets/elections/dim_persons.parquet` + `taxonomy/persons.parquet` | S.1 | ◻ READY |
| `datasets/boundaries/in/geojson/*.{sources,metadata,unkeyed}.json` (115 sidecars) + `S22-villages-index.json` | `datasets/boundaries/boundary_layers.parquet` + FK to `taxonomy/sources.parquet` | T.0d | ✅ DONE 2026-05-22 (`9e2ee3db`) |
| Flat `datasets/boundaries/in/geojson/*.geojson` (73 files) | Hive-partitioned `datasets/boundaries/in/{country,states,districts,ac,pc,subdistricts,villages,postal}/state=<S>/...` per [T.0d spec §1](20260522-t0d-boundaries-consolidation-spec.md) | T.0d | ✅ DONE 2026-05-22 (`9e2ee3db`) |

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
