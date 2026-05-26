# Canonical long-format pivot -- handover plan (CLOSED 2026-05-26)

> **This plan-doc is CLOSED.** Per user mandate 2026-05-26, the canonical-long-format pivot is done-and-dusted as a single coordinating plan. Phase 1 (infrastructure) + Phase 2 P.1 (Energy family) shipped end-to-end. Remaining work has been **decomposed into separate plan-docs** -- each future family ingest (Phase 2 P.3+), Phase 3 backfill, Phase 4 SLM, Phase 5 admin rewrite all get their own plan-doc when activated. This file is preserved as historical record + status pointer; no further rows will be added.

**Last Updated**: 2026-05-26 (CLOSED)
**Doc class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md) -- carries phase status + active PRs + TBD only; no rationale, no rejected alternatives, no executed-work narrative.

## Now playing

**Plan-doc CLOSED 2026-05-26.** Phase 1 + Phase 2 P.1 (Energy) shipped. All remaining rows decomposed into separate plan-docs -- see [`§1 closeout table`](#1-pending-work-tracker-your-queue-in-order) + [`§9 successor-doc index`](#9-successor-doc-index-2026-05-26-closeout). No more rows will be added here; future canonical-pivot work lands in the per-family / per-phase successor docs.

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
| 5 | **Caveat-authoring next batch** (extend PR-E + PR-H pattern to ~92 stub indicators; campaign as 5-7 per-family PRs) | ✅ DONE PRs #297+#301+#302+#304 | **Audit (2026-05-25)**: 24 canonical-allowlist descriptors + 68 legacy artifacts had empty/missing `methodology.known_caveats[]` (vs ~30 plan-doc estimate -- actual gap was ~92). Tier-1 high-citizen-visibility PRs all shipped: **PR-I energy distribution** (4 indicators: sales-MU + billing-eff + collection-eff + T&D-loss; AT&C-decomposition cohort; ✅ DONE PR #297 `39db2bda`), **PR-J fiscal Centre transfers** (3 indicators: tax-devolution Item I + grants Item II + net Item VI; Finance-Commission-cycle cohort; ✅ DONE PR #301 `e02d16f6`), **PR-O economy GDP** (3 indicators: state-GDP-current + state-per-capita-NSDP-constant + state-sectoral-GVA-current; macro headline cohort; ✅ DONE PR #302 `8a7d73b2`), **PR-P livestock Pashu Aadhaar** (3 indicators: cattle + buffalo + goat; canonical-allowlist pathway; tagged-COUNT-vs-population framing; ✅ DONE PR #304 `8addcdca`). Total 13 indicators authored across 4 PRs. Tier-2 deferred: health (6), environment (5), prices (7), transport (2) pending topic featurisation. |
| 6 | **P.1 Energy -- P.1.C** (9 indicators: coal / oil / primary / final / pipeline / thermal-retired / renewable-grid / plant-load-factor / renewable-potential) | ✅ DONE PR-Q #307 `f26ece21` + PR-R #309 `bd8e97d2` + PR-S #314 `c8bda3bc` + PR-T #316 `8c99e042` + PR-U #318 `1d0153d3` + PR-V #322 `570e6d79` + PR-W #325 `35b58219` + PR-X #327 `69e67d46` + PR-Y #329 `10703714` (9/9 ALL SHIPPED -- coal + rooftop solar + thermal-retired + oil-product + primary-energy-supply + plant-load-factor + power-purchase-share + final-energy-consumption + renewable-grid-capacity) | Sequenced AFTER PR 1 -- bucket-(b) shards become P.1.C meadow input. PR-Q (2026-05-25) ships `state-coal-consumption-mt` via NEW `energy_fuel_consumption` parquet stem (450 obs, FY 2006-07 to 2024-25, 26 sub-national entities + IN-prefix; ICED 2024-25 source `src-c222a8e2cd61`; 3 Hans caveats). PR-R (2026-05-25) ships `state-rooftop-solar-capacity-mw` onto the EXISTING `energy_installed_capacity` parquet stem (321 obs, FY 2017-04 to 2025-04, ICED `src-018bb42f9519`; 3 Hans caveats: rooftop-ONLY vs utility-scale, tariff-economics-not-insolation, cumulative-not-annual). PR-S (2026-05-26) ships `india-thermal-capacity-retired-mw` -- FIRST Pattern A-facet in the P.1.C cohort -- onto `energy_installed_capacity` (29 obs, FY 2005-04 to 2025-04 national-only, 2-facet on `fuel_type` axis: coal + gas with publisher `oil-gas` -> canonical `gas` collapse per Hans D33.8; ICED 2024-25 source `src-fd152bd3c6c6`; 3 Hans caveats: national-only-CEA-for-states, gas-bundles-oil-fired-diesel-gas-fired, retirements-not-equal-exit). PR-T (2026-05-26) ships `state-oil-product-consumption-kt` -- SECOND Pattern A-facet in P.1.C; introduces NEW `oil_product` facet axis (7 children: diesel-hsd / petrol / lpg / kerosene / naphtha / petroleum-coke / others; 1:1 with publisher, NO sub-bucket collapse; `allow_compute_on_read_total=True`) onto NEW shared parquet `energy_fuel_consumption` (2901 obs, FY 2010-04 to 2024-04, 36 distinct states/UTs + IN-prefix; ICED 2024-25 source `src-cba8334fedc5`; 3 Hans caveats: diesel-mobility-vs-stationary, LPG-domestic-vs-commercial, kerosene-erosion-via-PMUY). Sibling-widening of PR-Q's `test_parquet_has_single_indicator` -> `test_parquet_contains_coal_consumption_indicator` (set-equality -> set-membership) per the NO_CAVEATS_DESCRIPTOR pattern (PR-H lesson). PR-U (2026-05-26) ships `india-primary-energy-supply-mtoe` -- THIRD Pattern A-facet in P.1.C; FIRST `entity_kind: "country"` indicator in the cohort; EXTENDS existing `fuel_type` axis with `oil` + `renewable` value_ids (no axis count change); compute-on-read parent semantics filter 20 publisher `total` rows at adapter (140 raw -> 120 canonical: 20 FYs x 6 fuel children); publisher `renewables` plural -> canonical `renewable` singular per indicator-naming.md; ICED 2024-25 source `src-170d3536d908`; 3 Hans caveats: national-only-grain, TPES-not-end-use, mtoe-not-citizen-unit). PR-V (2026-05-26) ships `state-plant-load-factor-pct` -- THIRD Pattern A-facet in P.1.C; on the EXISTING `fuel_type` axis WITHOUT SUB_FUEL_TO_CANONICAL collapse (PLF is a percentage that cannot be summed across fuels; uses dedicated `_PLF_PUBLISHER_TO_CANONICAL_FUEL` 1:1 dict instead -- bio-power->biomass, small-hydro->small-hydro, oil-gas->gas, others 1:1); 8 children onto EXISTING `energy_generation` parquet (1652 obs, FY 2015-04 to 2025-04, 36 distinct states/UTs, state-grain only with no national IN rollup; ICED 2024-25 source `src-7eb929cbf2d8`; 3 Hans caveats: not-comparable-across-fuels, resource-vs-performance, outliers-and-zero-rows-are-real; introduces PR-V exemption in `test_energy_fuel_type_enum.py::sub_fuel_exempt_prefixes`). PR-W (2026-05-26) ships `state-power-purchase-share-pct` -- FOURTH Pattern A-facet in P.1.C; on the EXISTING `fuel_type` axis EXTENDED with 2 NEW value_ids `hybrid_bundled` + `trading_other` (procurement-channel categories); 12 children onto EXISTING `energy_demand_supply` parquet (2658 obs, FY 2015-04 to 2024-04, 36 distinct states/UTs, state-grain only; ICED 2024-25 source `src-1401f8087b0d`; 3 Hans caveats: procurement-vs-generation, hybrid-bundled-is-contract-not-fuel, trading-share-not-stress-signal; NO sub-fuel collapse since procurement share is a percentage; sibling-widening of `test_parquet_has_six_distinct_indicators_after_p1b` from set-equality to set-superset). PR-X (2026-05-26) ships `india-final-energy-consumption-mtoe` -- FIFTH Pattern A-facet in P.1.C; introduces NEW `sector_fuel_pair` facet axis (axis #19, 18 sparse value_ids); national-only entity; publisher 'sector | fuel' compound facet sanitised to kebab pair-id; 18 children onto EXISTING `energy_demand_supply` parquet (360 obs, FY 2005-04 to 2024-04, IN-only; ICED 2024-25 source `src-29ecbb6dce9d`; 3 Hans caveats: final-vs-primary-distinction, sparse-pairs-not-zero, sector-naming-is-MoSPI-taxonomy). Row 6 P.1.C cohort COMPLETE (9/9 PRs shipped 2026-05-25..2026-05-26). PR-Y (final) ships `state-renewable-grid-capacity-mw` -- Pattern A-SINGLE (no facet axis); RBI Handbook Table 143 source (`src-1f51c8d742bf`); 585 obs / 36 states/UTs / 18 calendar years (2007-2024); 3 Hans caveats: combined-RE-no-source-split, installed-not-generation-delivered, end-March-stock-snapshot-vs-FY-flow. Subagent: Max (indicator IDs), Hans (tier assignments), Gregor (paired-test atomicity per §15). |
| 7 | **P.1 Energy -- P.1.D** (sweep + retire + Tier-B allowlist scrub for whole family) | ✅ DONE (2026-05-26, no-op closeout) | All three sub-tasks verified as NO-OPs by prior PRs: (a) **3 acquires** -- all 33 energy meadow shards (21 ICED + 7 RBI + 5 CEA) have canonical adapters under `backend/yen_gov/canonical/adapters/energy/`; (b) **retirement audit** -- `datasets/indicators/in/energy/` is empty (PR #290 cleared it; `git ls-tree origin/main` returns 0 paths); (c) **Tier-B allowlist scrub** -- zero `energy/...` path entries remain in `datasets/_ops/meadow-shard-contract.txt` (only comment-text mentions). Closes P.1 Energy row of §2 Phase 2 table. |
| 8 | **Citizen-1 panel** Hans + Gregor §10 carve-out for <2s mobile first-paint vs DuckDB-WASM warm-up | ⊘ DROPPED (2026-05-26) | User mandate 2026-05-26: too early to mint this ADR -- other optimizations are pending upstream of the warm-up question. Re-scope when warranted (e.g. when a measured first-paint regression appears on real mid-tier-Android / patchy-4G smoke). Subagent invocation MANDATE (Gregor + Hans + Citizen + Andre) preserved here for when this row is re-opened. |
| 9 | **P.2 Livestock -- NDLM ingest** (16 indicators across 5 fact tables; new `agriculture` topic umbrella) | ⊘ HANDED OFF (2026-05-26) | Owned by a separate plan-doc and a parallel agent. Sub-plan: [`20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md) + [`20260525-pashu-aadhaar-ingest-plan.md`](20260525-pashu-aadhaar-ingest-plan.md). Meadow download still in flight on the parallel branch; this canonical-pivot plan-doc no longer tracks NDLM status. |
| 10 | **Phase 2 P.3+** (~10 more families: NFHS-5, PLFS, UDISE+, AISHE, NCRB, HCES, IMD, e-GramSwaraj-PFMS, TRAI, CAG) | ⊘ DECOMPOSED (2026-05-26) | Each family adopts the meadow-tier path established by P.1 Energy and ships under its own plan-doc when activated (template: [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md)). No longer tracked as a single row here; each per-family plan-doc lands as `TODO/<date>-phase-2-p<n>-<family>-pivot.md` at activation time. |
| 11 | **Phase 3** Demography / Fiscal / Education / Health backfill (Census 2011 H-series, SRS, CRS, GSDP base-year breaks, methodology-break ledger, HMIS monthly) | ⊘ DEFERRED (2026-05-26) | Opens as a new plan-doc when Phase 2 P.3+ families have landed enough current-data coverage to make backfill worthwhile. Plain-English scope retained here for future reference: fill historical holes + register methodological discontinuities so trend lines stay honest (Census housing, SRS / CRS vital stats, GSDP base-year-2011-12 break, central methodology-break ledger, monthly HMIS). |
| 12 | **Phase 4** SLM dispatcher | ⊘ HANDED OFF (2026-05-26) | User mandate 2026-05-26: SLM dispatcher is OUT OF SCOPE of this plan-doc going forward. A separate SLM plan-doc owns the design + delivery; this row stays as a placeholder pointer only. Original sketch + Phase-3 sequencing assumption no longer apply here. |
| 13 | **Phase 5** Admin app rewrite (Schemas / Pipeline / Patches panels) | ⊘ DEFERRED (2026-05-26) | User mandate 2026-05-26: admin rewrite is OUT OF SCOPE of this canonical-pivot plan-doc. Inventory v0 already shipped (Phase 0 / Phase 1); Schemas / Pipeline / Patches panels open under a separate admin-rewrite plan-doc when prioritised. |
| -- | **Open** `taxonomy/topics.parquet` rollout scheduling for 9 placeholder topics | OPEN | Needs Max indicator-priority ordering. |
| -- | **Open** `facet-axes` extensions as families need new axes | OPEN per-family | Each new axis needs Max sign-off when its family ingests. |
| -- | **Pointer** Identity-collapse + storage/UI decoupling (grain-over-entity, ADR-0044 / ADR-0045) | ⏳ ACTIVE in parallel | Owned by [TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md](20260526-grain-over-entity-and-storage-decoupling-plan.md). Runs **IN PARALLEL** to this umbrella; **does NOT supersede** Row 6 (P.1.C energy adapter arc — DONE), Row 7 (P.1.D sweep — DONE), or Row 8 (Citizen-1 panel — DROPPED). The grain-rip rewrites indicator-id grammar (drops `<entity>-` prefix) + splits the indicator catalogue (canonical vs grapher render hints) + adds a concept registry + closes the proliferation valve. Phase B of that plan amends `agriculture/state-pashu-aadhaar-*` + `district-pashu-aadhaar-*-<species>` ids via CTAS migration; this row exists so future agents pick up the cross-link rather than re-deriving it. |

**Rough completion estimate**: ~18-22% of the full canonical pivot. Phase 1 done; 1 of ~11 families (Energy) with 4 of N adapters on meadow + canonical (residue triage still open); Phases 3-5 are sketches.

## §2. Phase 2 -- Per-family ingestion table

| # | Family | Status | Active doc | Notes |
| - | --- | :-: | --- | --- |
| P.1 | **Energy** | ✅ DONE (2026-05-26) | [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md) | Closed at chore PR #330 `a1f90682` (Row 6 P.1.C 9/9) + chore PR for Row 7 P.1.D no-op closeout (this commit). All 33 energy meadow shards (21 ICED + 7 RBI + 5 CEA) carry canonical adapters; `datasets/indicators/in/energy/` empty; Tier-B allowlist contains 0 energy entries. Establishes the per-family P.* pattern for P.3+. |
| P.2 | **Livestock (NDLM)** | ⊘ HANDED OFF (2026-05-26) | [`20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md) | Bharat Pashudhan: 16 indicators across 5 fact tables; new `agriculture` topic. Meadow download still in flight; parallel agent + separate plan-doc own status going forward. This canonical-pivot plan-doc no longer tracks NDLM. |
| P.3+ | NFHS-5 / health, PLFS / work, UDISE+ / education, AISHE / education-higher, NCRB / crime, HCES / consumption, IMD / environment, e-GramSwaraj-PFMS / local-govt-finance, TRAI / technology, CAG / fiscal-audits | ⊘ DECOMPOSED (2026-05-26) | per-family plan-doc when activated | Each family follows the P.1 Energy template ([`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md)) and lands its own `TODO/<date>-phase-2-p<n>-<family>-pivot.md` when prioritised. Max-recommended ordering still applies. |

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

## §8. Closeout summary (2026-05-26)

This plan-doc shipped 1 closing campaign and is now CLOSED.

**What landed end-to-end under this plan-doc** (Phase 1 + Phase 2 P.1):

- Phase 1 (infrastructure): T.1 / T.2 / T.3 / T.0d / T.0e / G.1 / S.1 all DONE.
- Phase 2 P.1 (Energy family): P.1.A + P.1.B + P.1.C (9-PR cohort PR-Q..PR-Y, 2026-05-25..26) + P.1.D (no-op family sweep). All 33 energy meadow shards (21 ICED + 7 RBI + 5 CEA) carry canonical adapters; legacy `datasets/indicators/in/energy/` retired; Tier-B allowlist scrubbed; IA editorial pass + Tier-1 caveat-authoring batch all shipped.

**What is being decomposed / handed off**:

- Phase 2 P.2 Livestock NDLM -> own plan-doc (parallel agent; meadow download in flight).
- Phase 2 P.3+ (10 more families) -> per-family plan-docs at activation.
- Phase 3 backfill -> own plan-doc when Phase 2 P.3+ has enough coverage.
- Phase 4 SLM dispatcher -> own SLM plan-doc (already underway).
- Phase 5 Admin rewrite -> own admin-rewrite plan-doc when prioritised.
- Row 8 Citizen-1 panel ADR -> DROPPED (re-open trigger: measured first-paint regression on real mid-tier-Android / patchy-4G smoke).

**Why close this plan-doc now**: it has served its purpose as the coordinating doc for the canonical-store pivot. Phase 1 is structurally complete; one full family (Energy) is shipped end-to-end and serves as the template for every future family. Continuing to track 10+ future families + 3 future phases in a single doc would inflate the doc beyond ADR-0034's "plan-doc carries phase status + active PRs only" mandate. Per-family + per-phase plan-docs are the better unit going forward.

## §9. Successor-doc index (2026-05-26 closeout)

When you need to pick up work that this plan-doc used to track, go to its successor doc:

| Closed row | Successor doc(s) | Owner |
| --- | --- | --- |
| §1 row 9 (livestock NDLM) | [`20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md) + [`20260525-pashu-aadhaar-ingest-plan.md`](20260525-pashu-aadhaar-ingest-plan.md) | Parallel livestock agent |
| §1 row 10 (Phase 2 P.3+ families) | per-family plan-doc at activation; template = [`20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md) (P.1 Energy reference) | TBD per family |
| §1 row 11 (Phase 3 backfill) | future `TODO/<date>-phase-3-backfill-plan.md` when Phase 2 P.3+ matures | TBD |
| §1 row 12 (Phase 4 SLM) | separate SLM plan-doc (already authored) | Andre persona |
| §1 row 13 (Phase 5 Admin rewrite) | future `TODO/<date>-phase-5-admin-rewrite-plan.md` when prioritised | TBD |
| §1 row 8 (Citizen-1 panel ADR) | re-open this row + mint ADR when real-device first-paint regression is measured | Gregor + Hans + Citizen + Andre |

**Cross-cutting authority pointers carried forward** (these survive the closeout; new plan-docs reference them):

- Spec: [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md)
- Decision rationale: [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) + [ADR-0031](../docs/architecture/decisions/0031-boundary-geometry-strategy.md) + [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) + [ADR-0035](../docs/architecture/decisions/0035-persons-fork-option-b.md) + [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) + [ADR-0042](../docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md)
- Concept docs: [`meadow-tier.md`](../docs/concepts/meadow-tier.md), [`topic-taxonomy.md`](../docs/concepts/topic-taxonomy.md), [`data-provenance.md`](../docs/concepts/data-provenance.md), [`indicator-naming.md`](../docs/concepts/indicator-naming.md)
- Authority routing: CLAUDE.md §0a
- Doc-class routing rule: [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md)
