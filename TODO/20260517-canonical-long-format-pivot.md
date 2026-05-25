# Canonical long-format pivot -- handover plan

**Last Updated**: 2026-05-25
**Doc class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md) -- carries phase status + active PRs + TBD only; no rationale, no rejected alternatives, no executed-work narrative.

## Now playing

**Phase 2 (per-family ingestion)** is the active phase. Phase 1 + all infrastructure (T.1 / T.2 / T.3 / T.0d / T.0e / G.1 / S.1) ✅ DONE. P.1 Energy mostly done (P.1.A + P.1.B SHIP-LIFT-ONLY merged; 7c-N residue triage + Tier-B fence rename + sources-parquet vintage backfill done as of 2026-05-25; C5+C6 reader-switch + P.1.C + P.1.D + IA editorial pass + caveat-authoring pending). P.2 Livestock-NDLM in progress on parallel branch.

**Next agent**: see [`20260525-phase-2-completion-handover.md`](20260525-phase-2-completion-handover.md) for the operational runbook + PR-by-PR queue.

**Executed-work narrative + retired ledger entries + Strategy F decision rationale**: [`docs/archive/canonical-pivot-plan-20260522-snapshot.md`](../docs/archive/canonical-pivot-plan-20260522-snapshot.md) (verbatim lifts at L1-L4 of the 2026-05-25 supplement).

## Authority + spec pointers

- **Spec**: [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md) (disk layout, write/read paths, schemas).
- **Decision rationale**: [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) (canonical store + DuckDB-WASM) + [ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) (boundaries) + [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) (sources citation ledger) + [ADR-0035](../docs/architecture/decisions/0035-persons-fork-option-b.md) (persons fork) + [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) (meadow tier).
- **Concept docs**: [`meadow-tier.md`](../docs/concepts/meadow-tier.md), [`topic-taxonomy.md`](../docs/concepts/topic-taxonomy.md), [`data-provenance.md`](../docs/concepts/data-provenance.md), [`indicator-naming.md`](../docs/concepts/indicator-naming.md).
- **Authority routing**: CLAUDE.md §0a. Hans + Max on data shape; Gregor on contracts; Fowler on engineering craft; Jony + Citizen on UX; Andre on LLM/SLM. User approval supersedes every agent.

## §0a. The One Rule

**OWID is the canonical reference for socio-economic data modelling** (CLAUDE.md §0a). When any data-shape question arises, first check OWID; if OWID has solved it, adopt verbatim; if yen-gov must deviate, document the deviation in [`canonical-store.md`](../docs/architecture/data/canonical-store.md) with rationale signed off by Hans + Max.

## §0b. Cardinality is a moving target

Today's corpus is ~110 socio-economic indicators across 9 topics. Phase 2/3 ingestion takes this to ~500. Phase 4/5 takes it to 1,000+. Plan for the 1,000+ shape, not the 110 shape.

## §0c. Boundaries preservation (critical)

`datasets/boundaries/in/` is **not** legacy. It is a sibling family to the canonical Parquet store ([ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md)). No step in this pivot moves, renames, or deletes anything under that tree; future additions (PCs, taluks, village coverage) follow the same `{geojson|pmtiles}/<layer>.<ext>` layout.

## §0d. Status vocabulary

| Token | Meaning |
| :-: | --- |
| ✅ DONE | Shipped on `main`; commit SHA cited; on-disk evidence verified. |
| ⏳ ACTIVE | PR open or in progress on a feature branch; not yet on `main`. |
| ◻ QUEUED | Designed; awaiting a prerequisite to land. |
| ◻ READY | All prerequisites in place; next-PR candidate. |
| ◻ NEXT | Recommended next-PR pick. |
| ⊘ DROPPED | Original scope retired; replacement pattern cited inline. |
| 🔒 BLOCKED | Cannot proceed; named blocker + responsible party cited inline. |

## §1. Pending-work tracker (your queue, in order)

This is the only authoritative source of what's NOT done. PRs flip rows from ◻ to ✅ in the same commit they ship (per CLAUDE.md §9 DoD). For PR-by-PR scoping see [`20260525-phase-2-completion-handover.md`](20260525-phase-2-completion-handover.md).

| # | Slice | Status | Why pending |
| - | --- | :-: | --- |
| 1 | **P.1 Energy -- 7c-N residue triage** (10 shards retired from `datasets/indicators/in/energy/`) | ✅ DONE PR #290 | Per-shard classified into bucket (a) delete-no-successor (2 shards: `installed_capacity_total_mw` + `installed_capacity_thermal_mw`) or bucket (b) move to `datasets/energy/_meadow/iced/2024-25/` pending P.1.C canonical adapter (8 shards: `india_thermal_capacity_retired_mw`, `national_final_energy_consumption_by_sector_mtoe`, `national_primary_energy_supply_mtoe`, `state_coal_consumption_mt`, `state_oil_product_consumption_kt`, `state_plant_load_factor_pct`, `state_power_purchase_share_pct`, `state_rooftop_solar_capacity_mw`). Completion criterion ([ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md)) met: `git ls-tree origin/main -- datasets/indicators/in/energy/` now empty. |
| 2 | **P.1 Energy -- Tier-B fence file rename** (`datasets/_ops/legacy-folded-indicator-shards.txt` -> `datasets/_ops/meadow-shard-contract.txt`) | ✅ DONE PR #265 `bf425001` | Shipped 2026-05-25 alongside PR-A energy residue retirement. Tier-B symbol renamed `tier_b_legacy_folded_indicator_shards` -> `tier_b_meadow_shard_contract`; header rewritten as dual-role allowlist + meadow-staging perimeter; 14 doc/TODO references cascaded; CLAUDE.md §10 anti-pattern cite updated. |
| 3 | **P.1 Energy -- sources.parquet vintage backfill + Tier-B vintage check** | ✅ DONE PR #272 `2ba7eb45` | Shipped 2026-05-25. 5 NITI Aayog ICED + 6 RBI 2024-25 rows backfilled in `datasets/taxonomy/sources.parquet`; Tier-B rule `tier_b_meadow_vintage_matches_source_id` added per ADR-0041 non-negotiable #4 + ADR-0042 (vintage as period anchor). |
| 4 | **P.1 Energy -- PR 7d IA editorial pass** | ✅ DONE PR #296 | Pruned 23 cards to 5 on `/s/<state>/t/energy` per Jony's scroll-narrative (per-capita consumption -> generation-by-source [FACET-5] -> installed-capacity-by-source [FACET-5] -> AT&C losses -> RPO compliance [FACET-3]). 5 heading rewrites + 2 description rewrites + caveats[] update for all 5 cards (Card 1 bullet 0 replaced with Gujarat-Punjab anchor; Cards 2 + 3 new arrays with coordinated cross-card pair; Card 4 4th bullet appended for UDAY-PFC FY18 break; Card 5 3rd bullet appended for obligation-MET vs share). Topic summary rewritten (4-clause scroll-narrative). 18 demoted cards retain /i/<id> routing. 4 follow-ups queued: (D1) IndicatorGapChart primitive for demand-vs-supply pairs, (D2) descriptor description rewrite for Cards 1+2+3, (D3) FacetPicker default-pill policy, (Hans-1) methodology-breaks sparkline primitive (hard-break + vintage-band-shading), (Hans-2) TopicHonestyBanner primitive. |
| 5 | **Caveat-authoring next batch** (extend PR-E + PR-H pattern to ~92 stub indicators; campaign as 5-7 per-family PRs) | ⏳ ACTIVE PR-J open | **Audit (2026-05-25)**: 24 canonical-allowlist descriptors + 68 legacy artifacts have empty/missing `methodology.known_caveats[]` (vs ~30 plan-doc estimate -- actual gap is ~92). Tier-1 high-citizen-visibility PR ordering: **PR-I energy distribution** (4 indicators: sales-MU + billing-eff + collection-eff + T&D-loss; AT&C-decomposition cohort; ✅ DONE PR #297), **PR-J fiscal Centre transfers** (3 indicators: tax-devolution Item I + grants Item II + net Item VI; Finance-Commission-cycle cohort; ⏳ PR #_pending_), **PR-O economy GDP** (3 indicators), **PR-P livestock Pashu Aadhaar cattle+buffalo+goat** (3 indicators). Tier-2 deferred: health (6), environment (5), prices (7), transport (2) pending topic featurisation. Row 5 closes when Tier-1 4 PRs all merge. |
| 6 | **P.1 Energy -- P.1.C** (9 indicators: coal / oil / primary / final / pipeline / thermal-retired / renewable-grid / plant-load-factor / renewable-potential) | ◻ QUEUED | Sequenced AFTER PR 1 -- bucket-(b) shards become P.1.C meadow input. Subagent: Max (indicator IDs), Hans (tier assignments), Gregor (paired-test atomicity per §15). |
| 7 | **P.1 Energy -- P.1.D** (sweep + retire + Tier-B allowlist scrub for whole family) | ◻ QUEUED | 3 acquires + retirement audit + Tier-B scrub. Closes P.1 Energy row of §2 Phase 2 table. |
| 8 | **Citizen-1 panel** Hans + Gregor §10 carve-out for <2s mobile first-paint vs DuckDB-WASM warm-up | ◻ OPEN ARCHITECTURE | Design question, not a PR yet. MANDATORY subagent invocation: Gregor + Hans + Citizen + (if SLM-touching) Andre. Mint ADR before any code. |
| 9 | **P.2 Livestock -- NDLM ingest** (16 indicators across 5 fact tables; new `agriculture` topic umbrella) | 🔒 PARKED | User mandate 2026-05-25: do LAST. Parallel agent active. Sub-plan: [`20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md) + [`20260525-pashu-aadhaar-ingest-plan.md`](20260525-pashu-aadhaar-ingest-plan.md). |
| 10 | **Phase 2 P.3+** (~10 more families: NFHS-5, PLFS, UDISE+, AISHE, NCRB, HCES, IMD, e-GramSwaraj-PFMS, TRAI, CAG) | ◻ QUEUED | Bulk of remaining Phase 2. Each adopts meadow-tier path from day one -- no Phase-C debate per family. |
| 11 | **Phase 3** Demography / Fiscal / Education / Health backfill | Sketch only | Opens when Phase 2 closes. |
| 12 | **Phase 4** SLM dispatcher | Sketch only | Opens when Phase 3 closes. |
| 13 | **Phase 5** Admin app rewrite (Schemas / Pipeline / Patches panels) | Sketch only | Inventory v0 shipped; rest waits on Phase 4. |
| -- | **Open** `taxonomy/topics.parquet` rollout scheduling for 9 placeholder topics | OPEN | Needs Max indicator-priority ordering. |
| -- | **Open** `facet-axes` extensions as families need new axes | OPEN per-family | Each new axis needs Max sign-off when its family ingests. |

**Rough completion estimate**: ~18-22% of the full canonical pivot. Phase 1 done; 1 of ~11 families (Energy) with 4 of N adapters on meadow + canonical (residue triage still open); Phases 3-5 are sketches.

## §2. Phase 2 -- Per-family ingestion table

| # | Family | Status | Active doc | Notes |
| - | --- | :-: | --- | --- |
| P.1 | **Energy** | ⏳ ACTIVE | [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md) | 10 residue shards remain under `datasets/indicators/in/energy/`; P.1.C + P.1.D outstanding. Establishes the per-family P.* pattern. |
| P.2 | **Livestock (NDLM)** | ⏳ ACTIVE (parallel agent) | [`20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md) | Bharat Pashudhan: 16 indicators across 5 fact tables; new `agriculture` topic. PRs #276 / #278 / #281 shipped. PARKED for non-livestock agents per §1 row 9. |
| P.3+ | NFHS-5 / health, PLFS / work, UDISE+ / education, AISHE / education-higher, NCRB / crime, HCES / consumption, IMD / environment, e-GramSwaraj-PFMS / local-govt-finance, TRAI / technology, CAG / fiscal-audits | ◻ QUEUED | TBD per family | Max-recommended ordering; each lands its own plan-doc when active. |

## §3. Phase 3 -- Demography / Fiscal / Education / Health (sketch)

Phase 3 backfills the structural-coverage gaps after Phase 2 lands the issuing-authority series. Targets: Census 2011 H-series, SRS, CRS, GSDP base-year breaks, methodology-break ledger, HMIS monthly. Detailed plan opens when Phase 2 closes.

## §4. Phase 4 -- SLM dispatcher (sketch)

Phase 4 introduces the small-language-model dispatcher (full spec in the [archive §10-§11](../docs/archive/canonical-pivot-plan-20260522-snapshot.md)) that grounds citizen Q&A against the canonical Parquet store. Detailed plan opens when Phase 3 closes.

## §5. Phase 5 -- Admin rewrite (sketch)

Phase 5 rewrites the operator admin app on top of the canonical store -- Inventory (already shipped Phase 0 / Phase 1 v0), Schemas, Pipeline, Patches. Detailed plan opens when Phase 4 stabilises.

## §6. Handoff (instructions for the next coding agent)

**Operational runbook** (read this first; it specialises the rules below to the Phase-2 closing context): [`20260525-phase-2-completion-handover.md`](20260525-phase-2-completion-handover.md).

Read these, in this order, before touching code:

1. **[CLAUDE.md](../CLAUDE.md)** -- Holy Laws, doc-class routing rule, correction levels.
2. **[ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md)** -- every D1-D36 decision about the canonical store.
3. **[ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md)** + **[meadow-tier.md](../docs/concepts/meadow-tier.md)** -- the 5-tier vocabulary your PRs operate inside.
4. **[canonical-store.md](../docs/architecture/data/canonical-store.md)** -- current disk layout + naming + schema shape.
5. **[ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md)** + **[ADR-0042](../docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md)** -- sources are a citation ledger keyed on `(producer, title, vintage)`; vintage = period anchor; fetch telemetry never crosses into citizen-facing rows.
6. **[ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md)** -- which doc class owns which kind of statement.
7. **This file** (§1 pending tracker) + **[`20260525-phase-2-completion-handover.md`](20260525-phase-2-completion-handover.md)** -- what's next and how to ship it.
8. **[Active Phase 2 P.1 (Energy) plan](20260522-phase-2-p1-energy-pivot.md)** -- the family currently being pivoted (covers PRs 1, 6, 7 from §1).

Pre-flight check before opening a PR on this arc:

- Identify your **Correction Level** per CLAUDE.md §6. A P.* family pivot is Level 4 (large-scale, structural + behavioural fused per family).
- Confirm your change is a **paired Tier-A commit** per CLAUDE.md §15 -- schema bump + Pydantic model + DDL + parquet emit + frontend reader switch + deletion gate, all in one commit.
- Run the **parity oracle** the pivot tradition uses ([`backend/tests/test_canonical_parity_oracle.py`](../backend/tests/test_canonical_parity_oracle.py)) when retiring legacy shards.
- Run the **§13 browser smoke** on at least one citizen-facing route the change touches.
- Validate `python -m yen_gov validate --root .` clean before commit.

**Multi-agent isolation rule** (carried over from §0e operational discipline; binding): never commit on the master worktree. Spawn a worker worktree per PR. Other worktrees are parallel-agent territory -- read-only to you. Pin `PYTHONPATH=(Resolve-Path backend).Path` on every Python command (per the 2026-05-24 PR #194/#195 lesson).

**On doubt**: dispatch the relevant custom agent (Hans for data shape, Max for indicator choice, Gregor for contract design, Fowler for engineering craft, Jony for UX, Citizen for sanity check, Andre for LLM/SLM, Explore for read-only multi-file research). When subagents converge, their consensus is the spec. When they disagree, surface to the user. User approval supersedes every agent.

## §7. Cross-refs

- **Disk layout + write/read paths**: [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md)
- **Meadow tier vocabulary + 5-tier table**: [`docs/concepts/meadow-tier.md`](../docs/concepts/meadow-tier.md)
- **Topic taxonomy vocabulary**: [`docs/concepts/topic-taxonomy.md`](../docs/concepts/topic-taxonomy.md)
- **Sources citation ledger v3.0**: [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) + [ADR-0042](../docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) + [`docs/concepts/data-provenance.md`](../docs/concepts/data-provenance.md)
- **Persons fork design**: [ADR-0035](../docs/architecture/decisions/0035-persons-fork-option-b.md)
- **Doc-class routing rule**: [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md)
- **Active Phase 2 P.1 (Energy) plan**: [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md)
- **Active Phase 2 P.2 (Livestock) plan**: [`20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md)
- **Next-agent operational runbook**: [`20260525-phase-2-completion-handover.md`](20260525-phase-2-completion-handover.md)
- **T.0d boundaries consolidation spec**: [`20260522-t0d-boundaries-consolidation-spec.md`](20260522-t0d-boundaries-consolidation-spec.md)
- **Executed-work narrative + retired ledger entries + Strategy F decision rationale**: [`docs/archive/canonical-pivot-plan-20260522-snapshot.md`](../docs/archive/canonical-pivot-plan-20260522-snapshot.md) (2026-05-25 supplement §L1-L4)
