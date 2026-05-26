# Grain-over-entity + storage/visualization decoupling — rip-and-replace plan

**Last Updated**: 2026-05-26
**Status**: ▶ ACTIVE — PR-A1 ✅ PR #336; PR-A2 ✅ PR #338; PR-Z1 (doctrine bullets) ✅ PR #339; PR-A3a ✅ PR #340; PR-A3b ✅ PR #341; PR-A3c (topic-half) ✅ PR #342 (indicator-half + ingest-site tail deferred to follow-up PR-A3c-tail); PR-B1 ✅ PR #343; PR-B2 ✅ PR #344; PR-B8 ✅ PR #345 (prices collapse 4 state CPI sub-baskets → 1 facetted shard `prices/cpi_inflation_pct`); PR-B6-iip ✅ PR #346 (economy row 6 base-year-in-id rename `economy/india_iip_index_2011_12` → `economy/iip_index`; base-year retained in `methodology_vintage`; remaining B6 rows 4/5/8-11 deferred); PR-B7 (row 3 carve) ✅ PR #347 (fiscal centre-transfers 4→1 facetted shard `fiscal/centre_transfers_inr_crore`); PR-B6-row7 ✅ PR #348 (economy row 7 per-capita NSDP current `_long` twin drop + grain-prefix rip → `economy/per_capita_nsdp_current_inr`); PR-B6-row8 ✅ PR #349 (economy row 8 per-capita NSDP constant `_long` twin drop + grain-prefix rip → `economy/per_capita_nsdp_constant_inr`; ICED `_per_capita_constant_meta` writer retired); PR-D3 ✅ PR #350 (human_development family retired — single shard `state_hdi.json` deleted + topic block dropped from topics.json + `_hdi_meta`/`parse_hdi_map` writer+parser+test retired; no canonical successor planned). Phase 1 underway per guardrails-first ordering. PR-B6-row4 ✅ PR #355 (economy row 4 India GDP prefix-strip + unit-drift collapse: `economy/india_gdp_inr_crore` → `economy/gdp_inr_crore` (faceted current+constant); `economy/national_gdp_current_inr_lakh_crore` deleted as exact unit-converted subset). PR-B6-row10 ✅ PR #356 (economy row 10 state NSDP current ↔ constant collapse + grain-prefix rip: `economy/state_nsdp_current_inr_crore` + `economy/state_nsdp_constant_inr_crore` → `economy/nsdp_inr_crore` faceted `basis ∈ {current, constant}`; RBI HBS ingest tool refactored to emit one combined NSDP shard). PR-B0 schema v5.0 ✅ PR #359 (per-shard `indicator.schema.json` 4.4 → 5.0 — additive `indicator.entity_kinds[]` + `indicator.base_year` + `indicator.frequency`; `additionalProperties: false` lifted on the `indicator` block for the migration window; singular `entity_kind` stays REQUIRED for back-compat; 46 artifacts mechanically bumped to `$schema_version: 5.0` via `tools/bump_indicator_schema_to_current.py` (now walks `datasets/**` so meadow shards are included); unblocks B6-row5-tail, B6-row9, B6-rows 14-25). PR-B6-row9 ✅ PR #360 (economy row 9 state GDP CROSS-GRAIN merge — `economy/state_gdp_inr_crore` (910 rows, 34 states, current+constant) folded INTO existing `economy/gdp_inr_crore` (country shard from row 4) as ONE shard with `entity_kinds=["country","state"]` (1060 rows, 35 entities, 1950-04..2024-04); `economy/state_gdp_current_inr_lakh_crore` deleted as exact unit-converted subset; `fiscal/outstanding_debt_pct_gsdp` source_artifact pointers updated; first consumer of schema v5.0 `entity_kinds[]` for cross-grain shape). PR-Z3a (concept registry seed) ✅ PR #361 — partial of PR-Z3 (guardrails #13-#18): ADD `datasets/schemas/concepts.schema.json` v1.0 + `datasets/taxonomy/concepts.json` seeded by clustering current 183 indicator rows on `(label_short, unit, normalisation)` → 164 unique concepts (entity_kinds unioned across cluster members) + `backend/yen_gov/canonical/concept_registry.py` `find_overlap()` + `ConceptMatch` (noun-similarity + unit-equality + normalisation-equality blend → `upsert` / `add_facet` / `mint_new` recommendation) + 9 unit tests (synthetic fixtures + `tmp_path` disk-read smoke) + 5 Tier-A seed tests. DEFERRED to PR-Z3b: indicator-catalogue.schema v2.1 `concept_id` FK + `meta.justification` + `update_period_days` REQUIRED + indicators.json backfill + `check-overlap` CLI + 4 new Tier-B checks (tier_b_one_indicator_per_concept, tier_b_indicator_has_justification, tier_b_facet_promotion_warning, tier_b_indicator_freshness_declared) + `indicator-add-gate.yml` GitHub Action + CLAUDE.md §10 / docs/agents/guardrails.md / ingest-handover template updates.
**Doc-class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). Carries PR sequence + status only; rationale lives in cited ADRs and concept docs.
**Mandate**: user, 2026-05-26 — "rip-and-replace, no strangler-fig, no smooth cutover; everything is in git, we can revert." "Move grain to OWID-style grain-over-entity. Stop smooshing state + district + village into one chart; create sub-pages."
**Authority**: Hans + Max on data shape; Gregor on contracts; Fowler on engineering craft; Jony + Citizen on UX; Andre on LLM (not in scope here). See CLAUDE.md §0a.

## 0. Why this plan exists

Three concerns are addressed in sequence:

1. **Visualization is bleeding into storage.** `renderer_rules`, `chart_type`, `dimension`, `default_mode`, `facet_labels`, and meadow `datetime.now()` stamps live in canonical catalogues + committed meadow JSON. They belong in a frontend-owned grapher catalogue.
2. **Indicator identity encodes the grain.** `state-pashu-aadhaar-count-cattle` and `district-pashu-aadhaar-count-cattle` are the same concept measured at two grains; today they are two ids, two catalogue rows, two allowlist entries, two topic-page cards. Path B (grain-over-entity) collapses them: one `indicator_id`, grain dispatched from each observation row's `entity_kind`.
3. **Topic pages stack grain-cards instead of offering grain sub-pages.** `/t/agriculture` today shows 18 hand-fanned-out cards (1 district + 10 state species + 7 future). The fix is one card per measure with a facet/grain control inside, plus `/i/<indicator>/<grain>` sub-pages.

## 0ter. Standing authorizations (user, 2026-05-26 — read first)

The executing agent operates under these standing authorizations for the entire plan. Do NOT pause to re-confirm at PR time.

1. **Rip-and-replace is in force.** No strangler-fig, no alias window, no compatibility shim. Delete the old shape; ship the new shape. Everything is in git; revert via `git revert <sha>` if a smoke gate fails.
2. **The agent may force-with-lease its own branches.** When a rebase rewrites SHAs on a feature branch the agent owns, `git push --force-with-lease` is authorized. Never force-push to `main` or to a branch the agent does not own.
3. **The agent may merge its own PRs via `gh pr merge --squash --delete-branch`** once the 5-gate DoD (§3) is green. No human ratification step between gate-green and merge.
4. **The agent may amend other plan-docs** ([TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md), [TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md), [TODO/20260525-pashu-aadhaar-ingest-plan.md](20260525-pashu-aadhaar-ingest-plan.md), any `AGENTS.md`, any `docs/`) when this plan's PRs invalidate their content. Already enumerated in PR-Z1 + PR-Z2.
5. **The agent may interrupt and supersede a pending PR on another plan** when that PR ships an id or schema field this plan is rip-and-replacing. Open a coordination comment on the affected PR pointing at this plan-doc; do not silently stomp.
6. **The agent may escalate scope to Level-4** (CLAUDE.md §6) without user gate when a PR's blast-radius grows mid-flight, AS LONG AS the rip-and-replace + 5-gate DoD invariants hold.
7. **Subagent consensus is sign-off.** When Hans+Max+Gregor or Jony+Citizen converge in a `runSubagent` panel, treat their consensus as ratification per CLAUDE.md §0a. No separate user OK.
8. **The agent may delete dead docs/code without prior approval** as long as the deletion is in a named PR row of this plan or follows from PR-Z1/Z2.

**Standing limits** (the agent MUST stop and ask):
- Any change that would touch `main` history directly (no commits to main; PR-only workflow).
- Any change to YENASK runtime code (`frontend/src/lib/yenask/**`, `frontend/src/routes/Yenask.svelte`) — that arc is owned by Andre and 4 parallel worktrees.
- Any deletion of citizen-facing data the smoke gate cannot re-render (e.g. would 404 a citizen route with no successor URL).
- Any change to `CLAUDE.md` §0a authority routing or §1 Holy Laws (only the user revises these).

## 0quat. Permanent prevention guardrails (so the problem cannot creep back)

The rip-and-replace closes today's debt. These guardrails are how it stays closed. All are PR-Z1 deliverables (CLAUDE.md + guardrails.md + every AGENTS.md updated in one commit).

| # | Guardrail | Where enforced | What it catches |
| -: | --- | --- | --- |
| 1 | `indicator_id` MUST NOT start with `state-` / `district-` / `national-` | Tier-B `tier_b_indicator_id_no_grain_prefix` ([backend/yen_gov/validate.py](../backend/yen_gov/validate.py)); ADDED in PR-B1, ENFORCED post-PR-B9 | Future agents re-prefixing grain on id |
| 2 | `indicator-catalogue.schema.json` MUST NOT carry render-coupled fields (`renderer_rules`, `chart_type`, `default_mode`, `facet_labels`, `dimension`) | Schema v2.0 (PR-A3c) — those fields are simply absent; CI rejects on contract test | Future agents pushing UI hints back into canonical data |
| 3 | `topic-catalogue.schema.json` MUST NOT carry `chart_type` / `dimension` | Same — fields absent in v2.0 (PR-A3c) | Same |
| 4 | Topic page MUST have at most ONE artifact ref per `(canonical_indicator_id, entity_kind)` | New contract test in PR-C3: [frontend/src/contracts/topic-card-uniqueness.test.ts](../frontend/src/contracts/topic-card-uniqueness.test.ts) | Future agents card-fanning species/fuel/facet as separate cards |
| 5 | Committed meadow JSON MUST be byte-deterministic across re-runs (no `datetime.now()`) | New test in PR-A5: [backend/tests/test_meadow_determinism.py](../backend/tests/test_meadow_determinism.py) | Wall-clock smear in committed artifacts |
| 6 | `source_id` MUST be looked up via `source_registry.resolve(nickname)`, never hand-typed | PR-A6 deletes `SOURCE_IDS` literals; static-analysis rule in a new Tier-B `tier_b_no_hand_typed_source_id` (ADD to PR-A6 deliverables) — greps `^SOURCE_IDS\s*=` and `\"src-[0-9a-f]{12}\"` outside `taxonomy/sources.parquet` + `source_nicknames.json` | Future adapters copy-pasting hashes |
| 7 | New `_meadow/` path MUST match a citation-ledger row vintage | Existing Tier-B `tier_b_meadow_vintage_matches_source_id` | (already enforced) |
| 8 | Frontend MUST NOT fetch any `_meadow/` path | Existing CLAUDE.md §4 + Phase B allowlist routing | (already enforced) |
| 9 | `lift-<family>` MUST accept `--table <stem>` and default to a single table when invoked from CI/operator | PR-A4 — adapter `__init__.build_envelopes(*, only=None)` is the seam | Future agents writing wide rebuilds that look like per-shard fan-out |
| 10 | Every plan-doc that touches indicator ids or catalogue fields MUST cite ADR-0044 + ADR-0045 in its preamble | Doctrine in CLAUDE.md §10 (PR-Z1); reviewers enforce | Future plans relapsing into Path-A grammar |
| 11 | New schema MUST go through CLAUDE.md §11 with `x-version` major.minor + `x-changelog` | Existing Tier-A | (already enforced) |
| 12 | Citizen-facing field rename is a §6 Level-3 minimum + 5-gate DoD | CLAUDE.md §6 + §9 | (already enforced) |
| 13 | New ingest MUST FK to a row in `datasets/taxonomy/concepts.json` declaring `(concept, unit, normalisation, entity_kind)`. Two indicators with the same 4-tuple is rejected | NEW Tier-B `tier_b_one_indicator_per_concept` (ships in PR-Z3) | Future agents minting `_v2` / `_alt` / source-stamped ids for the same fact |
| 14 | Pre-ingest overlap check MUST be cited in every new-source handover doc: `python -m yen_gov check-overlap --concept "<noun>" --unit "<u>" --entity_kind "<k>"`; if overlap ≥ 70% the action is UPSERT into existing indicator or add a facet, NOT mint a new id | NEW CLI command `check-overlap` (ships in PR-Z3); handover-doc template line; doctrine in CLAUDE.md §10 | New publisher of an existing fact being minted as a parallel id |
| 15 | Default action for new data is **UPSERT into existing indicator** (writer PK is `(entity_id, year, period_label, indicator_id)`; same key = same row). Minting a new id requires `meta.justification` field with the named difference (different concept / unit / normalisation) | Writer behaviour (already); NEW required `meta.justification` field on every catalogue row added in the same PR as the first observation row; Tier-B `tier_b_indicator_has_justification` | Adapters silently fanning out parallel ids per source |
| 16 | When an adapter emits ≥3 indicators that differ only in one slug segment, Tier-B flags as proliferation and proposes the facet axis | NEW Tier-B `tier_b_facet_promotion_warning` (ships in PR-Z3) — pattern-matches `^(.+)-(coal\|gas\|hydro\|nuclear\|solar\|wind\|cattle\|buffalo\|goat\|sheep\|...)$` across the indicator catalogue and groups | Per-fuel / per-species ids being added one PR at a time |
| 17 | Any PR adding >1 row to `datasets/taxonomy/indicators.json` requires explicit Hans+Max consensus in PR body OR a per-id "facet collapse not applicable because X" line | NEW CI contract test `test_indicator_add_gate` walking the PR's diff; ships in PR-Z3 | Hidden indicator-proliferation in unrelated PRs |
| 18 | Every indicator MUST declare `update_period_days` (expected refresh cadence in days) — derived from publisher's own cadence (NDLM monthly = 30, RBI Handbook annual = 365). Operator dashboard surfaces stale indicators when `today - last_observed > 2 * update_period_days`. OWID precedent: every Grapher variable has this | Schema v2.1 additive (PR-Z3); seeded from existing `cadence` field; surfaces in `/data-completeness` | Indicators silently going stale; no rip-and-refresh prompt |
| 19 | Methodology break = SAME `indicator_id` + new `methodology_breaks.parquet` row, NEVER a new id (Rosling rule). Base-year rebases, sampling-frame changes, definition shifts stay on the same id | Existing Tier-A on `methodology_breaks` FK; doctrine line in CLAUDE.md §10 (PR-Z1) | `economy/india_iip_index_2011_12` style — base-year in id |

PR-Z1 + PR-Z2 + PR-Z3 + PR-B9 ship guardrails #1-#19 simultaneously: schema fields removed (#2,#3), Tier-B checks live (#1,#6,#13,#15,#16,#17,#18), tests live (#4,#5), CLAUDE.md §10 anti-patterns added (#10,#14,#19), `lift --table` seam shipped (#9), `check-overlap` CLI shipped (#14), concept registry shipped (#13). After all four PRs merge, the rip is permanent and the proliferation valve is closed.

## 0quint. OWID-precedent doctrine (read before any new ingest)

OWID, the World Bank, the IMF, the FAO and the UN Statistical Division converge on the same five rules for socio-economic indicator management. yen-gov adopts them verbatim. Cited so future agents can pattern-match against the source-of-truth instead of re-deriving.

| # | Rule | OWID/WB/IMF precedent | yen-gov binding |
| -: | --- | --- | --- |
| O1 | One indicator = one `(concept, unit, normalisation, entity_kind)` tuple. Identity is what is MEASURED, never WHO published it | OWID `Variable` table is M:1 from `(origin_id, dataset_id)`; same variable across origins | Guardrail #13 + concept registry |
| O2 | New vintage of same indicator = UPSERT rows; same id, source_id rotates on the row | OWID ETL `garden` tier writes new values to existing variable; old values overwritten by new ETL run | Guardrail #15; already implemented (writer PK does not include source_id) |
| O3 | New facet/sub-category on existing concept = facet axis on existing indicator, NEVER a new indicator | OWID Grapher `dimensions` (entity, year, value, plus facet); never minting `coal-capacity`, `gas-capacity` as separate variables | Guardrail #16 + PR-B4 / PR-B5 collapse |
| O4 | Methodology break = same id + annotation, NEVER a renamed id | OWID variable description carries `description_processing` + chart annotation; FAO/WB carry `series_breaks[]` on the same series | Guardrail #19; existing `methodology_breaks.parquet` |
| O5 | Refresh cadence is declared per indicator; staleness is surfaced | OWID Grapher variable has `update_period_days`; WB API has `lastUpdated` per series | Guardrail #18 (PR-Z3) |

**Test of "new indicator vs UPSERT-or-facet":** before minting a new id, every author must answer YES to ALL of these. If any answer is NO, it is a facet on an existing indicator or an UPSERT:

1. Is the **concept** different from every concept in `datasets/taxonomy/concepts.json`? (Not "GSDP from MoSPI" vs "GSDP from RBI" — those share concept "GSDP".)
2. Is the **unit** different from the closest concept-match indicator? (`_mw` vs `_gw` is not different — choose the smaller of the two and re-emit; `_mw` vs `_inr_crore` is different.)
3. Is the **normalisation** different? (per-capita / per-area / share / index vs raw absolute. Same noun with different normalisation = different indicator; same noun with same normalisation = same indicator.)
4. Is the **entity_kind** different? (Country, state, district, AC are valid entity_kinds on the SAME indicator after Path B; do NOT mint per-grain ids.)

If all 4 are YES, it is a new indicator. Otherwise UPSERT or facet.


## 0bis. Inter-plan landscape (verified 2026-05-26)

| Plan | Status | Interaction with this plan |
| --- | --- | --- |
| [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md) | ACTIVE umbrella. Row 5 ✅ done (PR-I/J/O/P). Row 6 P.1.C energy adapters in flight as PR-Q/R/S/T/U arc (PR #307/#309/#314/#316/#318 merged; 4 of 9 indicators left: plant-load-factor, power-purchase-share, final-energy-consumption, renewable-potential). Row 7 P.1.D + Row 8 Citizen-1 panel still open. | **Runs in parallel.** Do not abandon. PR-Z2 of this plan amends its §1 with a pointer. |
| [TODO/20260522-t0d-boundaries-consolidation-spec.md](20260522-t0d-boundaries-consolidation-spec.md) | ✅ MERGED `9e2ee3db` (2026-05-22). | **Zero overlap.** Boundaries are a sibling family, not indicator-catalogue. |
| [TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md) | PARKED per user mandate ("do LAST"). Phase 0 ◻ NEXT; Phase 1.D NADCP 🔒 BLOCKED on disease-enum; Phase 1.E Breeding 🔒 BLOCKED on sub-endpoint discovery; parallel agent on yen-gov-3b-species worktree. | **Partial supersede.** PR-B5 takes over Phase 2.A/2.B/2.E identity collapse. Phase 1.D NADCP + Phase 1.E Breeding continue under the livestock plan. PR-Z2 amends its §11. |
| [TODO/20260525-pashu-aadhaar-ingest-plan.md](20260525-pashu-aadhaar-ingest-plan.md) | PR #303 + PR-P #304 shipped (2 indicators + Hans caveats). | **Identity collapsed by PR-B5.** Caveats survive verbatim. |
| Completeness index ([datasets/reference/in/indicators-completeness.json](../datasets/reference/in/indicators-completeness.json)) | LIVE citizen surface at `/data-completeness`, linked from `/disclaimer`. | **KEEP.** Do NOT delete. Regenerated by `emit-taxonomy`. |
| Re-processing concern ("does .runtime get re-walked when schemas/indicators change?") | **REFUTED.** Adapters read only committed meadow JSON ([_shared.py#L211-L230](../backend/yen_gov/canonical/adapters/energy/_shared.py#L211)). `lift-*` + `emit-taxonomy` + `pytest` do NOT touch `.runtime/raw/`. The real seam is that `lift-livestock` / `lift-energy` rebuild ALL family envelopes today — addressed by PR-A2 (`--dry-run`) + PR-A4b (`--table` filter). | Already in plan; no extra action. |



Other agents are committing in parallel. Avoid these paths until the named worktree merges to `main`. Verify with `git worktree list` before each PR.

| Worktree | Owns paths | Status (2026-05-26) |
| --- | --- | --- |
| `yen-gov-pr2-ia` | `backend/yen_gov/canonical/adapters/energy/**`, `backend/tests/test_*energy*` | P.1.C coal adapter in flight |
| `yen-gov-3b-species` | `backend/yen_gov/canonical/adapters/livestock/**`, `frontend/src/lib/canonical/indicator-allowlist.ts` (livestock block ~lines 1000-1180), `tools/livestock_meadow_pashu_aadhaar.py`, `backend/tests/test_livestock_*` | 9-species district routing |
| `yen-gov-slice-e-docs`, `yen-gov-yenask-brand`, `yen-gov-yenask-device`, `yen-gov-yenask-ortrun` | `frontend/src/lib/yenask/**`, `frontend/src/routes/Yenask.svelte` | YENASK Slice E.2 |

**Rebase-or-defer rule**: any PR in this plan that wants to touch a path owned above MUST wait until that worktree merges, OR be rebased on it.

## 1bis. Pre-flight corrections (verified 2026-05-26)

Four plan errors caught and fixed; baked into the PR specs below.

| Error | Reality | Fixed by |
| --- | --- | --- |
| Plan said `chart_type` / `default_mode` / `facet_labels` live on `indicator-catalogue.schema.json` | They live on the LEGACY per-shard [datasets/schemas/indicator.schema.json](../datasets/schemas/indicator.schema.json) v4.4. Only `renderer_rules` is on the canonical catalogue. `chart_type` + `dimension` are on `topic-catalogue.schema.json`. Three schemas, not one. | A3 split into A3a/A3b/A3c |
| Plan assumed `lift-elections` + `lift-governments` commands needed to be created | **VERIFIED 2026-05-26**: elections has no `lift-*` because data is emitted via per-event `canonical-backfill-eci` + `ingest-eci-ae-panel` (one-shot ingest path, not a lift cycle). Governments `office_holdings` is taxonomy-compiled by `emit-taxonomy` from [office_holdings_seed.py](../backend/yen_gov/canonical/office_holdings_seed.py) — also no lift needed. | A4 simplified — only adds `--table` filter to existing `lift-energy` + `lift-livestock` |
| D1 prices = 9 shards | Disk shows **7** ([datasets/indicators/in/prices/](../datasets/indicators/in/prices/)) | D1 row corrected |
| Re-processing concern (`.runtime/` re-walked on schema changes) | **REFUTED 2026-05-26**: all adapters read only committed meadow JSON ([_shared.py#L211-L230](../backend/yen_gov/canonical/adapters/energy/_shared.py#L211)); zero `.runtime/raw/` reads in any `lift-*`. Schema/indicator changes are metadata-rewrite only. | No action — but A2 (`--dry-run`) + A4 (`--table` filter) address the real seam: `lift-livestock` today rebuilds ALL livestock tables on any change |

## 2. PR sequence

Each PR is ≤300 lines diff (excluding parquet binary regen). PRs marked **READY** are unblocked. PRs marked **BLOCKED-ON** must wait. All PRs follow CLAUDE.md §8 git hygiene + the worktree-list pre-flight (memory lesson PR #290 — 3rd-worktree-grabs-main trap; always run `git worktree list` from the master, not from the worker).

**Subagent column is GUIDANCE, not auto-dispatch.** The execution agent picks up the PR, reads the row, and invokes the named persona via `runSubagent` at the design-question or review step. The persona is the authority for that PR's class of decision (Hans+Max = data shape, Gregor = contracts, Fowler = engineering, Jony+Citizen = UX) per CLAUDE.md §0a. Skipping the dispatch is allowed only for trivial mechanical edits inside the named persona's domain (e.g. a typo fix in a Hans-curated caveat).

### Standing reference — concrete id mapping (used by Phase B + C2)

| # | Group | Today's ids | Today's file:line | NEW id | `entity_kinds` | facets | PR | Destructive? |
| -: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Net Centre→States transfers | `fiscal/net_transfers_from_centre`, `fiscal/centre_transfers_to_states_net` | [fiscal/net_transfers_from_centre.json](../datasets/indicators/in/fiscal/net_transfers_from_centre.json) + sibling | `centre-transfers-net-inr-crore` | `country` | — | B7 (fiscal) | YES — delete one |
| 2 | Gross Centre→States transfers | `fiscal/centre_transfers_to_states_gross`, `fiscal/centre_transfers_gross` | (2 shards) | `centre-transfers-gross-inr-crore` | `country` | — | B7 | YES |
| 3 | Centre→States transfers full decomposition (rows 1+2 + `_tax_devolution` + `_grants`) | 5 shards | (5 shards) | `centre-transfers-inr-crore` | `country` | `flow ∈ {gross,net,tax_devolution,grants}` | B7 | YES — 5→1 |
| 4 | India GDP (prefix + unit drift) | ✅ PR-B6-row4 #_pending_ — `economy/india_gdp_inr_crore` renamed to `economy/gdp_inr_crore` (faceted current+constant retained); `economy/national_gdp_current_inr_lakh_crore` deleted (exact unit-converted subset of current facet, max rel diff 1.4e-16 across 13 shared FYs). | (1 shard) | `economy/gdp_inr_crore` | `country` | `price_basis ∈ {current,constant}` | B6 (economy) | done |
| 5 | India GVA by industry (prefix + vintage-in-id + frequency) | ⚠️ PR-B6-row5 partial #358 — `economy/india_gva_by_industry_constant_inr_crore` renamed to `economy/gva_by_industry_constant_inr_crore` (ICED shard prefix-strip only). DEFERRED: collapsing `national_gva_by_industry_constant_2011_12_inr_crore` (CSO/MoSPI, 14 finer industries, FY12-FY26) + `national_gva_by_industry_quarterly_constant_2011_12_inr_crore` (8 industries, 2011-Q1 through 2025-Q2). The 2 CSO shards are NOT duplicates of the ICED shard (different industry vocabularies, different time coverage, different precision, no aggregate rows in CSO). Full collapse needs (a) schema v5.0 to expose `meta.base_year` + a per-row `frequency` axis (annual vs quarterly cannot share a single `facet` column with `industry`), and (b) facet-vocabulary reconciliation between ICED 10-industry and CSO 14-industry tiers. | (1 of 3 shards) | `gva-by-industry-constant-inr-crore` + `meta.base_year=2011_12` | `country` | `frequency ∈ {annual,quarterly}` | B6 | partial |
| 6 | India IIP (base-year-in-id) | `economy/india_iip_index_2011_12` | (1 shard) | `iip-index` + `meta.base_year=2011_12` | `country` | — | B6 | rename only |
| 7 | State per-capita NSDP current (`_long` twin) | `state_per_capita_nsdp_current_inr`, `_inr_long` | (2 shards) | `per-capita-nsdp-current-inr` | `state` | — | B6 | YES |
| 8 | State per-capita NSDP constant (`_long` + base-year-in-id) | `state_per_capita_nsdp_constant_2011_12_inr`, `_constant_inr_long` | (2 shards) | `per-capita-nsdp-constant-inr` + `meta.base_year=2011_12` | `state` | — | B6 | YES |
| 9 | State GDP unit drift (cross-grain merge into row 4) | ✅ PR-B6-row9 #360 — `economy/state_gdp_inr_crore` (910 rows, 34 states, current+constant facets) merged INTO existing `economy/gdp_inr_crore` (country shard from row 4) yielding ONE cross-grain shard with `entity_kinds=["country","state"]` (1060 rows, 35 entities, 1950-04..2024-04). `economy/state_gdp_current_inr_lakh_crore` deleted (exact unit-converted subset of merged current facet; state rows max rel diff 1.45e-16; 10 IN rows redundant with country current facet). `state_gdp_constant_2011_12_inr_lakh_crore` left in place pending future ICED-vs-MoSPI vintage reconciliation (7.7% max rel diff from `state_gdp_inr_crore` constant facet — separate methodology vintage). Schema v5.0 `entity_kinds[]` consumed; `fiscal/outstanding_debt_pct_gsdp` source_artifact pointers updated. | (1 shard) | `economy/gdp_inr_crore` | `country`, `state` | `price_basis ∈ {current,constant}` | B6 | done |
| 10 | State NSDP current ↔ constant | `state_nsdp_current_inr_crore`, `state_nsdp_constant_inr_crore` | (2 shards) | `nsdp-inr-crore` | `state` | `basis ∈ {current,constant}` | B6 | YES — collapse |
| 11 | Sectoral GVA current ↔ constant | `state_sectoral_gva_current_inr_lakh_crore`, `state_sectoral_gva_constant_2011_12_inr_lakh_crore` | (2 shards) | `sectoral-gva-inr-crore` | `state` | `basis ∈ {current,constant}`, sector | B6 | ✅ DONE PR #357 |
| 12 | India GHG emissions (sector vs subsector + unit drift) | `india_ghg_emissions_mtco2e_by_sector`, `india_ghg_emissions_by_subsector_ggco2e` | (2 shards) | `ghg-emissions-mtco2e` | `country` | `sector_grain ∈ {sector,subsector}` | D5 (environment) | YES |
| 13 | State CPI inflation (general + food + fuel + housing-urban) | `state_cpi_general_inflation_pct` + 3 sib | (4 shards) | `cpi-inflation-pct` | `state` | `group ∈ {general,food,fuel,housing_urban}` | B8 (prices) | YES |
| 14 | National installed capacity (total + 5 fuels) | `national-installed-capacity-mw` + 5 fuel children | [indicators.json#L560-L678](../datasets/taxonomy/indicators.json#L560-L678) | `installed-capacity-mw` | `country` | `fuel ∈ {all,coal,gas,hydro,nuclear,renewable}` | B4 (energy) | YES — 6→1 |
| 15 | State installed capacity (geographical, total + 5 fuels) | `state-installed-capacity-geographical-mw{,coal,gas,hydro,nuclear,renewable}` | [L704-L822](../datasets/taxonomy/indicators.json#L704) | merges into #14 (entity_kind=state, attribution=where_located) | `state` | same as #14 | B4 | YES |
| 16 | State installed capacity (allocated, total + 5 fuels) | `state-installed-capacity-allocated-mw{*}` | [L848-L966](../datasets/taxonomy/indicators.json#L848) | merges into #14 (entity_kind=state, attribution=where_allocated) | `state` | same | B4 | YES |
| 17 | State installed capacity snapshot (total + 5 fuels) | `state-installed-capacity-snapshot-mw{*}` | [L989-L1107](../datasets/taxonomy/indicators.json#L989) | DROP entirely (superseded by geographical+allocated) | — | — | B4 | YES — delete 6 |
| 18 | State generation by fuel (total + 5 fuels) | `state-electricity-generation-gwh{*}` | [L1131-L1246](../datasets/taxonomy/indicators.json#L1131) | `electricity-generation-gwh` | `state` | `fuel` | B4 | YES |
| 19 | State distribution efficiency (overall + billing + collection + td-loss) | 4 ids | [L1383-L1454](../datasets/taxonomy/indicators.json#L1383) | `distribution-efficiency-pct` | `state` | `component ∈ {overall,billing,collection,td_loss}` | B4 | YES |
| 20 | State RPO compliance (3 facets + redundant `-total` duplicate) | 4 ids incl. `state-rpo-compliance-pct-total` (= parent) | [L1502-L1571](../datasets/taxonomy/indicators.json#L1502) | `rpo-compliance-pct` | `state` | `target ∈ {solar,non_solar,total}` | B4 | YES — drop `-total` |
| 21 | India thermal capacity retired (total + 2 fuels) | `national-thermal-capacity-retired-mw{,coal,gas}` | [L1709-L1755](../datasets/taxonomy/indicators.json#L1709) | `thermal-capacity-retired-mw` | `country` | `fuel ∈ {all,coal,gas}` | B4 | YES |
| 22 | State oil-product consumption (total + 7 products) | 8 ids | [L1778-L1939](../datasets/taxonomy/indicators.json#L1778) | `oil-product-consumption-kt` | `state` | `product ∈ {diesel_hsd,petrol,lpg,kerosene,naphtha,pet_coke,others}` | B4 | YES |
| 23 | Peak electricity demand ↔ supplied | `state-peak-electricity-demand-mw`, `state-peak-electricity-supplied-mw` | [L1314, L1337](../datasets/taxonomy/indicators.json#L1314) | `peak-electricity-mw` | `state` | `kind ∈ {demand,supplied}` | B4 | YES |
| 24 | Electricity requirement ↔ availability (annual energy) | `state-electricity-requirement-mu`, `state-electricity-availability-mu` | [L1594, L1617](../datasets/taxonomy/indicators.json#L1594) | `electricity-energy-mu` | `state` | `kind ∈ {requirement,availability}` | B4 | YES |
| 25 | Per-capita electricity consumption ↔ availability | `state-per-capita-electricity-consumption-kwh`, `state-per-capita-electricity-availability-kwh` | [L1360, L1640](../datasets/taxonomy/indicators.json#L1360) | `per-capita-electricity-kwh` | `state` | `kind ∈ {consumption,availability}` | B4 | YES |
| 26 | Pashu Aadhaar district (parent + 10 species) | `district-pashu-aadhaar-count` + 10 children | [L1962+L1988..L2249](../datasets/taxonomy/indicators.json#L1962) | merges into #27 (one id, entity_kind ∈ {state,district}) | both | `species ∈ {all,cattle,buffalo,yak,mithun,sheep,goat,pig,horse,donkey,mule}` | B5 (livestock) | YES — 11→facet |
| 27 | Pashu Aadhaar state (parent + 10 species, mirror of #26) | `state-pashu-aadhaar-count` + 10 | [L2278+L2304..L2565](../datasets/taxonomy/indicators.json#L2278) | `pashu-aadhaar-count` | both | same | B5 | YES — 22→11 collapse (1 parent + 10 species, grain on row) |
| 28 | Livestock owner-reg district (parent + 6 size facets) | 7 ids | [L2594-L2765](../datasets/taxonomy/indicators.json#L2594) | merges into #29 | both | `holding_size ∈ {landless_marginal,small,semi_medium,medium,large,not_specified}` | B5 | YES |
| 29 | Livestock owner-reg state (mirror of #28) | 7 ids | [L2794-L2965](../datasets/taxonomy/indicators.json#L2794) | `livestock-owner-reg-count` | both | same | B5 | YES — 14→7 |
| 30 | Livestock NAIP-IV district (4 metrics, no parent) | 4 distinct ids | [L2994-L3072](../datasets/taxonomy/indicators.json#L2994) | each prefix-strip; KEEP 4 distinct (different units: inseminations, pregnancies, calves, farmers) | both | — | B5 | rename only |
| 31 | Livestock NAIP-IV state (mirror of #30) | 4 distinct ids | [L3098-L3176](../datasets/taxonomy/indicators.json#L3098) | merges into #30 | both | — | B5 | YES — 8→4 |
| 32 | Elections state-* (8 ids; no sibling) | `state-electors-total`, `-votes-polled`, `-turnout-pct`, `-nota-pct`, `-effective-parties-laakso`, `-winning-party-id`, `-winning-party-seats`, `-majority-threshold-acs` | [L411-L560](../datasets/taxonomy/indicators.json#L411) | drop `state-` prefix on each | `state` | — | B2 | rename only |

**Explicitly stay-split (do NOT collapse — Hans pin)**:

| Group | Why split |
| --- | --- |
| `fiscal/states_combined_*_deficit` vs `fiscal/union_*_deficit` | Different fiscal entity (28 states combined vs Union government), not different scopes of one fact. Anti-pattern resolution PIN #2 in [indicator-naming.md §9](../docs/concepts/indicator-naming.md). |
| `national_cpi_combined_index_annual` vs `national_cpi_iw_index_annual` vs `national_wpi_all_commodities_index_annual` | Different baskets/methodologies; citizens read these as different measures. |
| Election prefixes `ac-` / `candidate-` / `party-` | Different fact-grain, not entity-grain. Stay. |

---

### Phase A — Storage/visualization decoupling

| PR | Title | READY/BLOCKED | Subagent |
| -: | --- | --- | --- |
| **A1** | ADRs + concept rewrite | READY | Hans+Max+Gregor+Jony |
| **A2** | `--dry-run` flag | ✅ PR #338 | Fowler |
| **A3a** | Grapher catalogue ADDITIVE (no deletes) | ✅ PR #340 | Gregor |
| **A3b** | Reader migration to grapher catalogue | ✅ PR #341 | Gregor+Fowler |
| **A3c** | Rip `renderer_rules` + `chart_type` + `dimension` from canonical catalogues | After A3b | Gregor |
| **A4** | `--table <stem>` filter on `lift-energy` + `lift-livestock` (elections+governments don't need lift commands — see §1bis) | ✅ PR #368 | Fowler |
| **A5a** | Strip `datetime.now()` from non-livestock meadow tools | READY | Fowler |
| **A5b** | Strip `datetime.now()` from livestock meadow tools | ✅ PR #369 | Fowler |
| **A6** | Data-driven `source_id` lookup | After yen-gov-pr2-ia + yen-gov-3b-species | Fowler+Gregor |

#### PR-A1 — ADR-0044 (grain-over-entity) + ADR-0045 (grapher-catalogue split) — ✅ PR #336

- **ADD**: [docs/architecture/decisions/0044-grain-over-entity.md](../docs/architecture/decisions/0044-grain-over-entity.md), [docs/architecture/decisions/0045-grapher-catalogue-split.md](../docs/architecture/decisions/0045-grapher-catalogue-split.md). ADR-0045 MUST state the three-schema fan-out explicitly (legacy per-shard `indicator.schema.json` + canonical `indicator-catalogue.schema.json` + `topic-catalogue.schema.json`) so future agents don't repeat the scoping error from this plan's first draft.
- **MODIFY**: [docs/concepts/indicator-naming.md](../docs/concepts/indicator-naming.md) §2.2 (drop `<entity_prefix>` mandatory rule), §2.4 (delete entirely), §8 anti-pattern #2 (rewrite as DO NOT prefix grain on id); [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) (add "one card per measure" rule); [docs/research/indicator-id-grain-axis.md](../docs/research/indicator-id-grain-axis.md) flip status to RESOLVED-Path-B.
- **DELETE**: none.
- **Tests**: none (docs-only). Justified by the rest of the plan depending on the ADRs.
- **LOC**: ≈ +400 / -120, 0 parquet.
- **Worktree risk**: none.

#### PR-A2 — `--dry-run` for writer + emit-taxonomy + completeness emit

- **ADD**: [backend/tests/test_writer_dry_run.py](../backend/tests/test_writer_dry_run.py). Test asserts: (i) `bytes_planned == bytes_after`, (ii) `n_files_changed_on_disk == 0` post-dry-run, (iii) stdout contains `UNCHANGED|CHANGED (old_rows -> new_rows)` per affected file.
- **MODIFY**: [backend/yen_gov/canonical/writer.py](../backend/yen_gov/canonical/writer.py) — thread `dry_run: bool = False` through `write_batch()` + `_atomic_write_*` (~L200-L450). [backend/yen_gov/cli.py](../backend/yen_gov/cli.py) — add `--dry-run` Option to `emit-taxonomy` (~L84-L295), `lift-energy` (~L463-L513), `lift-livestock` (~L516-L563). [tools/emit_indicators_completeness_index.py](../tools/emit_indicators_completeness_index.py) — mirror `--dry-run`. [backend/yen_gov/admin/pipeline.py](../backend/yen_gov/admin/pipeline.py) — accept the kwarg or default False (verify both code paths).
- **DELETE**: none.
- **LOC**: ≈ +250 / -10.
- **Worktree risk**: LOW. `cli.py` is high-traffic — confirm `lift-energy`/`lift-livestock` signature changes are additive and don't break yen-gov-pr2-ia + yen-gov-3b-species call sites.

#### PR-A3a — Grapher catalogue introduce (ADDITIVE, zero deletions)

- **ADD**: [datasets/schemas/grapher-indicator-render.schema.json](../datasets/schemas/grapher-indicator-render.schema.json) v1.0 (fields: `indicator_id`, `chart_type`, `default_mode`, `renderer_rules[]`, `facet_labels{}`); [datasets/schemas/grapher-topic-render.schema.json](../datasets/schemas/grapher-topic-render.schema.json) v1.0 (per-topic `(indicator_id, chart_type, dimension)`); [datasets/grapher/indicator_render.json](../datasets/grapher/indicator_render.json) seeded by reading current values out of `indicator-catalogue` + `topic-catalogue` + the 69 legacy shards; [datasets/grapher/topic_render.json](../datasets/grapher/topic_render.json); [datasets/grapher/AGENTS.md](../datasets/grapher/AGENTS.md); [frontend/src/lib/grapher/catalogue.ts](../frontend/src/lib/grapher/catalogue.ts) (loader + types); [frontend/src/lib/grapher/catalogue.test.ts](../frontend/src/lib/grapher/catalogue.test.ts); [backend/tests/test_grapher_catalogue_schema.py](../backend/tests/test_grapher_catalogue_schema.py).
- **MODIFY**: none of the old schemas yet. Pure additive.
- **DELETE**: none.
- **LOC**: ≈ +500 / 0.
- **Worktree risk**: LOW (new directory).

#### PR-A3b — Reader migration to grapher catalogue

- **MODIFY**: [frontend/src/lib/topic-dispatch.ts](../frontend/src/lib/topic-dispatch.ts) L41 (`artifact.chart_type` → grapher lookup); [frontend/src/lib/catalogue.ts](../frontend/src/lib/catalogue.ts) L71-L72 (type field); [frontend/src/lib/charts/stacked-trend/adapter-indicator.ts](../frontend/src/lib/charts/stacked-trend/adapter-indicator.ts) L27, L129 (read `chart_type` + `default_mode` from grapher); [frontend/src/lib/StackedTrendArtifact.svelte](../frontend/src/lib/StackedTrendArtifact.svelte) L97 (`facet_labels`); [frontend/src/lib/humanise.ts](../frontend/src/lib/humanise.ts) L4-L13 fallback chain; [frontend/src/routes/TopicLanding.svelte](../frontend/src/routes/TopicLanding.svelte) L216 + L249 (`dimension`); [frontend/src/lib/indicator-card.ts](../frontend/src/lib/indicator-card.ts) L101 + [frontend/src/lib/IndicatorCard.svelte](../frontend/src/lib/IndicatorCard.svelte) L276 (`renderer_rules`).
- **Tests**: parity tests — for every indicator the old reader knew about, grapher-catalogue lookup returns identical values. Pin in [frontend/src/lib/grapher/catalogue.parity.test.ts](../frontend/src/lib/grapher/catalogue.parity.test.ts).
- **LOC**: ≈ +250 / -120.
- **Worktree risk**: LOW. yenask doesn't touch any of these files (verified — yenask owns only `lib/yenask/**` + `routes/Yenask.svelte`).

#### PR-A3c — Rip `renderer_rules` + `chart_type` + `dimension` from canonical catalogues

**Split 2026-05-26 into two PRs to bound blast radius:**

**PR-A3c (topic-half, this PR) ✅ #342** — TOPIC catalogue rip only. Removed `chart_type` + `dimension` from `topic-catalogue.schema.json` v2.0, `topics.json`, `topics_seed.py` (pydantic `_Artifact`, `_tag_rows` tuple, DDL `indicator_topic_tags`, INSERT placeholder count); bumped `INDICATOR_TOPIC_TAGS_ROW_SCHEMA_VERSION` 1.1→2.0; regen `topics.parquet` + `indicator_topic_tags.parquet` + `manifest.json`; updated `catalogue.parity.test.ts` to a sentinel ("legacy topics.json carries no chart_type/dimension"). Frontend reads still resolved via A3b `applyGrapherOverlay()` — render hints sourced from `datasets/grapher/topic_render.json`. 7 files +N/-M. 5-gate DoD: Gate 1 validate OK, Gate 2 1196p/46s/3deselected in 308s, Gate 3 0e/7w, Gate 4 109files/2715p/0fail in 42s, Gate 5 N/A (no new citizen-surface; render path parity-locked by A3b overlay).

**PR-A3c-tail (deferred)** — INDICATOR catalogue + ingest-site rip. Tasks: (1) `renderer_rules` removal from `indicator-catalogue.schema.json` v2.0 (no `id_aliases`+`deprecated_in` cut here — that stays for PR-B1), `indicators.json` (44 entries, livestock block), `indicators_seed.py` (pydantic + DDL + insert tuple), `indicator-allowlist.ts` (31 hard-coded `renderer_rules: [...]` entries) — REQUIRES new indicator-level overlay seam in `getCanonicalDescriptor()` (sync→async, OR move `canShowRank()` lookup onto async grapher-fetched site at card-render time). (2) ingest-site cleanup: stop writing `chart_type` + `default_mode` into emitted legacy shards from `backend/yen_gov/sources/iced_*/ingest.py` + `rbi_xlsx/ingest.py` (~25 sites). (3) Update `indicator-from-canonical.test.ts` 4 `meta.renderer_rules` reads to grapher-fed lookup. (4) `datasets/livestock/AGENTS.md` L32 reword. Worktree risk: HIGH on `indicator-allowlist.ts` livestock block (yen-gov-3b-species) — wait + rebase. Energy ingest site overlap (yen-gov-pr2-ia).

- **Original-scope reference (now split across PR-A3c + PR-A3c-tail)**: MODIFY [datasets/schemas/indicator-catalogue.schema.json](../datasets/schemas/indicator-catalogue.schema.json) → v2.0, DELETE `renderer_rules` (~L214). [datasets/schemas/topic-catalogue.schema.json](../datasets/schemas/topic-catalogue.schema.json) → v2.0, DELETE `chart_type` + `dimension` (~L159-L168). Both schemas: ADD `x-changelog` v2.0 entry. [backend/yen_gov/canonical/indicators_seed.py](../backend/yen_gov/canonical/indicators_seed.py) L138-L240 (drop the field from pydantic + DDL + insert tuple). [backend/yen_gov/canonical/topics_seed.py](../backend/yen_gov/canonical/topics_seed.py) L101-L283 (same). [datasets/taxonomy/indicators.json](../datasets/taxonomy/indicators.json) strip ~30 `renderer_rules: ["no_rank_table"]` arrays from livestock block. [datasets/taxonomy/topics.json](../datasets/taxonomy/topics.json) strip `chart_type` + `dimension` from artifact refs. [frontend/src/lib/canonical/indicator-allowlist.ts](../frontend/src/lib/canonical/indicator-allowlist.ts) — drop the 30 `renderer_rules: [...]` hard-coded entries; project from grapher catalogue at descriptor-build time. [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts) L1726-L1946 — replace `meta.renderer_rules` reads with grapher-catalogue lookup. [datasets/livestock/AGENTS.md](../datasets/livestock/AGENTS.md) L32 (drop the `renderer_rules` reference and reword without it). 8 ingest sites under [backend/yen_gov/sources/iced_*/ingest.py](../backend/yen_gov/sources/) + `rbi_xlsx/ingest.py` (~25 sites) — stop writing `chart_type` + `default_mode` into emitted legacy shards.
- **Generators**: `emit-taxonomy --dry-run` first (PR-A2 dependency), then real run.
- **LOC**: ≈ +200 / -600 + regen 4 parquets (`indicators`, `topics`, `indicator_topic_tags`, `manifest`).
- **Worktree risk**: HIGH on `indicator-allowlist.ts` livestock block (yen-gov-3b-species) — wait + rebase. Energy ingest site overlap (yen-gov-pr2-ia).
- **Legacy schema carve-out**: legacy per-shard [datasets/schemas/indicator.schema.json](../datasets/schemas/indicator.schema.json) `chart_type` / `default_mode` / `facet_labels` stay alive until D8 deletes the schema entirely. Don't double-cut.

#### PR-A4 — `--table <stem>` filter on `lift-energy` + `lift-livestock`

**Scope corrected 2026-05-26**: elections data ships via per-event `canonical-backfill-eci` + `ingest-eci-ae-panel` (one-shot, not a lift cycle); governments `office_holdings` is taxonomy-compiled by `emit-taxonomy` from [office_holdings_seed.py](../backend/yen_gov/canonical/office_holdings_seed.py). Neither needs a `lift-*` command. PR-A4 only touches the two existing lift commands.

- **MODIFY**: [backend/yen_gov/cli.py](../backend/yen_gov/cli.py) `lift-energy` (~L463-L513) + `lift-livestock` (~L516-L563) — add `--table <stem>` repeatable Option. [backend/yen_gov/canonical/adapters/energy/__init__.py](../backend/yen_gov/canonical/adapters/energy/__init__.py) L37, [backend/yen_gov/canonical/adapters/livestock/__init__.py](../backend/yen_gov/canonical/adapters/livestock/__init__.py) L37 — add `only: set[str] | None = None` kwarg, filter envelopes by `target_table_stem`, raise on unknown stem.
- **Tests**: [backend/tests/test_cli_lift_table_filter.py](../backend/tests/test_cli_lift_table_filter.py) — fail-fast-on-unknown + filter-narrows-output cases for both families.
- **LOC**: ≈ +200 / -15.
- **Worktree risk**: BLOCKED on yen-gov-pr2-ia + yen-gov-3b-species (both adapter `__init__.py` files). Rebase on both; ship as one PR after they merge.

#### PR-A5a — Strip `datetime.now()` from non-livestock meadow generators

- **ADD**: [backend/tests/test_meadow_determinism.py](../backend/tests/test_meadow_determinism.py).
- **MODIFY**: any `tools/*meadow*.py` and `tools/iced_aq_emit_from_fixture.py` etc. — add required `--snapshot-date YYYY-MM-DD` Option, refuse without, stamp `T00:00:00Z` from the supplied date.
- **CARVE-OUT**: do NOT change `datetime.now()` in [backend/yen_gov/admin/inventory.py](../backend/yen_gov/admin/inventory.py) L328, [backend/yen_gov/canonical/writer.py](../backend/yen_gov/canonical/writer.py) L1163, [backend/yen_gov/admin/pipeline.py](../backend/yen_gov/admin/pipeline.py) L76+L90 — those are control-plane carve-outs per CLAUDE.md §10.
- **LOC**: ≈ +200 / -30.
- **Worktree risk**: LOW.

#### PR-A5b — Same, for livestock meadow tools — ✅ PR #369

- **MODIFY**: [tools/livestock_meadow_pashu_aadhaar.py](../tools/livestock_meadow_pashu_aadhaar.py), [tools/livestock_meadow_owner_reg.py](../tools/livestock_meadow_owner_reg.py), [tools/livestock_meadow_naip_iv.py](../tools/livestock_meadow_naip_iv.py) — add required `--snapshot-date YYYY-MM-DD` argparse Option; validate via `dt.date.fromisoformat()`; thread `fetched_at = f"{snapshot_date}T00:00:00Z"` into each `build_*meadow*()` function (replaces in-body `dt.datetime.now()` calls). Tools refuse to run without `--snapshot-date` (argparse exits with code 2).
- **ADD**: [backend/tests/test_livestock_meadow_snapshot_date.py](../backend/tests/test_livestock_meadow_snapshot_date.py) — 9 cases: 3 missing-required + 3 malformed-date + 3 supplied-date-stamps-correctly across the 3 tools.
- **Gates**: G1 OK; G2 9p/0f targeted (0.51s); G3-G5 N/A (tools-only, no observation rows changed). Worktree was clear (yen-gov-3b-species gone since session #29). 2-commit-then-squash.

#### PR-A6 — Data-driven `source_id` lookup

- **ADD**: [backend/yen_gov/canonical/source_registry.py](../backend/yen_gov/canonical/source_registry.py) (`resolve(nickname: str, repo_root: Path) -> str` with `lru_cache` on root). [datasets/taxonomy/source_nicknames.json](../datasets/taxonomy/source_nicknames.json) (schema'd lookup table). [datasets/schemas/source-nicknames.schema.json](../datasets/schemas/source-nicknames.schema.json) v1.0. [backend/tests/test_source_registry.py](../backend/tests/test_source_registry.py).
- **MODIFY**: [backend/yen_gov/canonical/adapters/energy/_shared.py](../backend/yen_gov/canonical/adapters/energy/_shared.py) — DELETE `SOURCE_IDS` literal. [backend/yen_gov/canonical/adapters/livestock/_shared.py](../backend/yen_gov/canonical/adapters/livestock/_shared.py) L30-L37 — DELETE same. Every call site: `energy/demand_supply.py` L77/178/193/208/227/244/261/280, `energy/distribution.py` L50/89/104/129/146/174, `energy/fuel_consumption.py` L59/83/109, `livestock/pashu_aadhaar.py`, `livestock/owner_reg.py`, `livestock/naip_iv.py`.
- **LOC**: ≈ +200 / -80.
- **Worktree risk**: BLOCKED on BOTH yen-gov-pr2-ia + yen-gov-3b-species.

---

### Phase B — Grain-over-entity rip-and-replace (Path B)

Old `state-` / `district-` / `national-` ids are **deleted**, not aliased. Each PR carries a one-shot migration script committed under `tools/migrate/` for reproducibility.

#### PR-B1 — Schema v2.0 + Tier-B grain-prefix check (DARK)

- **MODIFY**: [datasets/schemas/indicator-catalogue.schema.json](../datasets/schemas/indicator-catalogue.schema.json) → v2.0: ADD `entity_kinds: array<enum["country","state","district","ac"]>` required; ADD `default_entity_kind: enum` required; DELETE `id_aliases[]` + `deprecated_in`. Bump `x-changelog`. Tighten the `id` `pattern` regex if possible OR enforce via Tier-B (preferred — keeps schema simple).
- **MODIFY**: [datasets/taxonomy/indicators.json](../datasets/taxonomy/indicators.json) — backfill `entity_kinds` + `default_entity_kind` on ALL 121 rows (use the standing reference table above; rows not in the table get `entity_kinds = [<grain inferred from current prefix>]`, `default_entity_kind = same`).
- **MODIFY**: [backend/yen_gov/validate.py](../backend/yen_gov/validate.py) — add `tier_b_indicator_id_no_grain_prefix` (rejects ids matching `^(state\|district\|national)-`). Ship **dark** (function present, NOT chained into `run()`) until B2-B5 land.
- **MODIFY**: [backend/yen_gov/canonical/indicators_seed.py](../backend/yen_gov/canonical/indicators_seed.py) — drop `id_aliases` + `deprecated_in` from pydantic + DDL + insert tuple.
- **DELETE**: [backend/yen_gov/validate.py](../backend/yen_gov/validate.py) `tier_b_indicator_alias_window` function. [backend/tests/test_validate_alias_window.py](../backend/tests/test_validate_alias_window.py) (~7 cases). 5 round-trip tests in [backend/tests/test_indicators_seed.py](../backend/tests/test_indicators_seed.py) L166-L240.
- **Tests**: new [backend/tests/test_indicator_catalogue_schema_v2.py](../backend/tests/test_indicator_catalogue_schema_v2.py); new [backend/tests/test_tier_b_indicator_id_no_grain_prefix.py](../backend/tests/test_tier_b_indicator_id_no_grain_prefix.py) with passing (`electors-total`) + failing (`state-electors-total`) fixtures.
- **LOC**: ≈ +400 / -200 + regen `taxonomy/indicators.parquet`.
- **Worktree risk**: LOW.

#### PR-B2 — Elections prefix-strip (8 ids, no collapse)

- **ADD**: [tools/migrate/path_b_elections.py](../tools/migrate/path_b_elections.py) — one-shot DuckDB CTAS rewriting `indicator_id` on every elections observation parquet (31 state shards under [datasets/elections/state=in_*/election_results.parquet](../datasets/elections/)).
- **MODIFY**: [datasets/taxonomy/indicators.json](../datasets/taxonomy/indicators.json) L411-L560 — rename per row #32 in the standing reference table. [datasets/taxonomy/topics.json](../datasets/taxonomy/topics.json) — rewrite every artifact ref. [frontend/src/lib/canonical/indicator-from-canonical.test.ts](../frontend/src/lib/canonical/indicator-from-canonical.test.ts) — update regex assertions by AUTHORED INTENT (per memory lesson PR #296), not literal substring. [frontend/src/lib/canonical/indicator-allowlist.ts](../frontend/src/lib/canonical/indicator-allowlist.ts) elections block. [frontend/src/contracts/catalogue-coverage.allowlist.json](../frontend/src/contracts/catalogue-coverage.allowlist.json). [datasets/_ops/meadow-shard-contract.txt](../datasets/_ops/meadow-shard-contract.txt). [datasets/reference/in/indicators-completeness.json](../datasets/reference/in/indicators-completeness.json). Every `AGENTS.md` referencing `state-electors-*`.
- **Generators**: run migration script → `emit-taxonomy` → `regenerate_manifest.py` → `emit_indicators_completeness_index.py --write`.
- **Tests**: refresh [backend/tests/test_canonical_parity_oracle.py](../backend/tests/test_canonical_parity_oracle.py) fixture via [tools/snapshot_canonical_parity_oracle_fixture.py](../tools/snapshot_canonical_parity_oracle_fixture.py).
- **LOC**: ≈ +300 / -100 + regen 4 taxonomy parquets + 31 elections observation parquets.
- **Worktree risk**: LOW.

#### PR-B3 — Energy state-only prefix-strip (38 rows; no collapse)

Mirrors B2 for the 38 energy `state-*` rows that have NO national/district sibling (e.g. `state-acs-arr-gap-inr-per-kwh`, the 14 distribution + 11 demand-supply + 13 other state-only ids in the energy block).

- **ADD**: [tools/migrate/path_b_energy.py](../tools/migrate/path_b_energy.py).
- **MODIFY**: indicators.json energy block; topics.json energy refs; allowlist.ts energy block; catalogue-coverage; meadow-shard-contract; completeness index; energy AGENTS.md; energy observation parquets (4 fact tables).
- **Tests**: parity oracle refresh; [backend/tests/test_*energy*](../backend/tests/) re-run unchanged.
- **LOC**: ≈ +800 / -400.
- **Worktree risk**: BLOCKED on yen-gov-pr2-ia + B1.

#### PR-B4 — Energy collapse pairs (per standing-reference rows 14-25; ~64 rows → ~16)

- **ADD**: collapse step in `tools/migrate/path_b_energy.py`.
- **MODIFY**: indicators.json — DELETE the prefix-and-fuel-cartesian rows; KEEP one `installed-capacity-mw` + facet, one `electricity-generation-gwh` + facet, etc. Add `entity_kinds: ["country","state"]` on each. Adapter emit code (under yen-gov-pr2-ia) — emit `entity_kind` column on each row. Observation parquets rewritten by the script.
- **Tests**: parity oracle refresh; new test: rows with same `indicator_id` + distinct `entity_kind` coexist; renderer dispatches correctly ([frontend/src/lib/IndicatorChoropleth.svelte](../frontend/src/lib/IndicatorChoropleth.svelte) verify L8-L11 constraint comment is removed).
- **LOC**: ≈ +400 / -300.
- **Worktree risk**: BLOCKED on yen-gov-pr2-ia + B3.

#### PR-B5 — Livestock collapse (rows 26-31; 44 → 22)

- **ADD**: [tools/migrate/path_b_livestock.py](../tools/migrate/path_b_livestock.py).
- **MODIFY**: [datasets/taxonomy/indicators.json](../datasets/taxonomy/indicators.json) L1778-L2992 — collapse per standing-reference rows 26-31. [datasets/taxonomy/topics.json](../datasets/taxonomy/topics.json) agriculture refs. [frontend/src/lib/canonical/indicator-allowlist.ts](../frontend/src/lib/canonical/indicator-allowlist.ts) livestock block (~L1000-L1180). Livestock adapters under [backend/yen_gov/canonical/adapters/livestock/](../backend/yen_gov/canonical/adapters/livestock/) — emit `entity_kind`. Livestock observation parquets rewritten by script. [backend/tests/test_livestock_pashu_aadhaar_lift.py](../backend/tests/test_livestock_pashu_aadhaar_lift.py) (~10 string literals). [datasets/livestock/AGENTS.md](../datasets/livestock/AGENTS.md) L28 — FIX the "state-level aggregates are never persisted" contradiction with ADR-0043.
- **DELETE**: 22 rows from indicators.json livestock block.
- **Tests**: parity oracle refresh; new test asserting Hans D33.8 compute-on-read parent invariant survives; livestock lift tests rewritten.
- **LOC**: ≈ +600 / -800.
- **Worktree risk**: BLOCKED on yen-gov-3b-species + B1 + A3c (A3c must have removed `renderer_rules` from catalogue schema first).

#### PR-B6 — Economy collapse + rename (standing-reference rows 4-11)

- **ADD**: [tools/migrate/path_b_economy.py](../tools/migrate/path_b_economy.py).
- **MODIFY**: 20 legacy shards under [datasets/indicators/in/economy/](../datasets/indicators/in/economy/) — rewrite shard contents to the new ids, then schedule for D7 deletion. indicators.json + topics.json + allowlist + tests as above.
- **Tests**: parity oracle refresh.
- **LOC**: ≈ +500 / -600.
- **Worktree risk**: LOW.

#### PR-B7 — Fiscal collapse + rename (standing-reference rows 1-3)

- **ADD**: [tools/migrate/path_b_fiscal.py](../tools/migrate/path_b_fiscal.py).
- **MODIFY**: 22 legacy shards under [datasets/indicators/in/fiscal/](../datasets/indicators/in/fiscal/). Same pattern.
- **STAY-SPLIT**: confirm `states_combined_*_deficit` and `union_*_deficit` are NOT collapsed (Hans pin).
- **LOC**: ≈ +500 / -600.
- **PR-B7 (row 3 carve)**: ✅ PR #347 — 4 country-grain shards (`centre_transfers_to_states_{net,gross,tax_devolution,grants}`) collapsed into `fiscal/centre_transfers_inr_crore` with `flow` facet, 76 rows. Rows 1+2 (state-grain pair `net_transfers_from_centre` + `centre_transfers_gross`) deferred to PR-B7-tail (touches `rbi_xlsx/*.py` adapter modules).

#### PR-B8 — Prices collapse + rename (standing-reference row 13)

- **ADD**: [tools/migrate/path_b_prices.py](../tools/migrate/path_b_prices.py).
- **MODIFY**: 7 legacy shards under [datasets/indicators/in/prices/](../datasets/indicators/in/prices/).
- **STAY-SPLIT**: CPI vs WPI vs CPI-IW (different baskets).
- **LOC**: ≈ +300 / -400.

#### PR-B9 — Enforce Tier-B grain-prefix check

- **MODIFY**: [backend/yen_gov/validate.py](../backend/yen_gov/validate.py) — chain `tier_b_indicator_id_no_grain_prefix` into `run()`.
- **Tests**: full Tier-B walk green.
- **LOC**: ≈ +10 / -5.
- **Worktree risk**: LOW. BLOCKED on B2+B3+B4+B5+B6+B7+B8 (all id-bearing renames done).

---

### Phase C — Topic-page slimming + grain sub-pages

#### PR-C1 — `/i/:indicator` + `/i/:indicator/:grain` routes

- **ADD**: [frontend/src/routes/IndicatorExplorer.svelte](../frontend/src/routes/IndicatorExplorer.svelte) — single component, prop `{ indicator, grain? }`. National view at `/i/<indicator>`; state choropleth + ranked table at `/i/<indicator>/state`; district choropleth + drill at `/i/<indicator>/district`. [frontend/src/routes/IndicatorExplorer.test.ts](../frontend/src/routes/IndicatorExplorer.test.ts); [frontend/e2e/indicator-explorer.spec.ts](../frontend/e2e/indicator-explorer.spec.ts).
- **MODIFY**: [frontend/src/main.ts](../frontend/src/main.ts) — add 2 routes after the existing route table. Grain validated against `state|district|subdistrict|village`; unknown → 404. [frontend/src/lib/charts/choropleth-entity-context.ts](../frontend/src/lib/charts/choropleth-entity-context.ts) — extend `ChoroplethGrain` to `"state" | "district" | "subdistrict" | "village"`. [frontend/src/lib/IndicatorChoropleth.svelte](../frontend/src/lib/IndicatorChoropleth.svelte) L8-L11 — remove the `entity_kind === "state"` constraint comment, dispatch by `entity_kind` from the observation row.
- **Drill**: state polygon click on the district choropleth → `?state=<eci_code>` via `history.pushState`; the view-model scopes the district choropleth + drill list to that state. Wires through `MapChoropleth.svelte`'s existing click handler.
- **LOC**: ≈ +500 / -30.
- **Worktree risk**: LOW. `main.ts` import-line may collide with yenask worktrees — spot-check.
- **BLOCKED ON**: A3b (reader migration so the new component reads from grapher catalogue).

#### PR-C2 — Agriculture topic 18 → 2 artifact refs

- **MODIFY**: [datasets/taxonomy/topics.json](../datasets/taxonomy/topics.json) agriculture topic — DELETE the 8 `state_pashu_aadhaar_count_<species ≠ cattle>` + 8 `district_pashu_aadhaar_count_<species ≠ cattle>` refs. KEEP the 2 cattle refs; after B5 lands they resolve to the collapsed `pashu-aadhaar-count` parent with a species facet picker inside the card. [frontend/src/lib/canonical/indicator-allowlist.ts](../frontend/src/lib/canonical/indicator-allowlist.ts) — replace 18 per-species descriptors with 1 facet-multiplexed descriptor per cattle card. [frontend/src/contracts/catalogue-coverage.allowlist.json](../frontend/src/contracts/catalogue-coverage.allowlist.json) — drop 16 stale entries.
- **DELETE**: 16 artifact refs from topics.json.
- **Tests**: agriculture topic test count update; new test asserting FacetPicker mounts on cattle card.
- **LOC**: ≈ +200 / -400 + regen `topics.parquet` + `indicator_topic_tags.parquet` + manifest.
- **Worktree risk**: BLOCKED on B5.
- **Citizen smoke**: re-confirm `/t/agriculture` reads as "Cattle + (species control)", not as "11 stacked species cards".

#### PR-C3 — Enforce "one card per measure" rule across all topics

- **MODIFY**: [datasets/taxonomy/topics.json](../datasets/taxonomy/topics.json) — audit every topic; collapse duplicate-measure-per-facet refs. Energy already done (PR #296). Apply to fiscal, economy, health, environment, demography, prices, transport. [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) — document the rule.
- **Tests**: new contract test in [frontend/src/contracts/topic-card-uniqueness.test.ts](../frontend/src/contracts/topic-card-uniqueness.test.ts) — for each topic, no two artifact refs share `(canonical_indicator_id, entity_kind)`.
- **LOC**: ≈ +400 / -800.
- **BLOCKED ON**: A3 + every B PR per family touched.

---

### Phase D — Legacy shard rip-and-replace (69 files → 0)

Per-PR pattern (applies to D1-D8 unless noted):
- **DELETE**: shard JSONs under [datasets/indicators/in/<family>/](../datasets/indicators/in/).
- **MODIFY**: [datasets/_ops/meadow-shard-contract.txt](../datasets/_ops/meadow-shard-contract.txt) (drop matching lines); [datasets/reference/in/indicators-completeness.json](../datasets/reference/in/indicators-completeness.json); [datasets/manifest.json](../datasets/manifest.json); any frontend legacy-loader code path (grep first — name unverified).
- **Generators**: `emit_indicators_completeness_index.py --write`; `regenerate_manifest.py`; `emit-taxonomy`.
- **BLAST-RADIUS guard**: before deleting any shard, grep ALL of `frontend/`, `backend/`, `tools/`, `admin/`, every `AGENTS.md` for the indicator id (per CLAUDE.md doctrine — frontend-only audit is insufficient).
- **5-gate DoD** + smoke on `/t/<family>` route.

| PR | Family | Shard count (verified) | Smoke route | BLOCKED on | Subagent |
| -: | --- | -: | --- | --- | --- |
| **D1** | prices | **7** | `/t/economy` | B8 | Max | ✅ PR #354 (3 national index-level shards retired: CPI-Combined / CPI-IW / WPI; HBS-IE Tables 36+37 ingest paused; no canonical national-inflation successor planned; survivor `prices/cpi_inflation_pct` from PR-B8 remains)
| **D2** | transport | 2 | `/t/transport` or `/t/infrastructure` | none | Max | ✅ PR #351
| **D3** | human_development | 1 | `/t/human-development` | none | Max | ✅ PR #350 |
| **D4** | demography | 3 | `/t/demography` | none | Max | partial PR #352 (2 of 3 retired; `state_population_lakhs` deferred — `frontend/src/lib/IndicatorChoropleth.svelte:396` hard-loads it for unmapped-regions chip strip, needs canonical migration first) |
| **D5** | environment | 8 | `/t/environment` | A3c (move AQ honesty into grapher catalogue first) | Max + Hans |
| **D6** | health | 6 | `/t/health` | none | Hans | ✅ PR #353 (all 6 retired; topic spine → structural placeholder; RBI Statement 27 ingest path removed) |
| **D7** | economy | 20 | `/t/economy` | B6 (rename done first to avoid id thrash) | Max |
| **D8** | fiscal | 22 + delete legacy schema | `/t/fiscal` | B7 + D7 | Hans + Max |

**Final acceptance for D8**: `git ls-tree HEAD -- datasets/indicators/in/` returns empty; [datasets/schemas/indicator.schema.json](../datasets/schemas/indicator.schema.json) deleted; [datasets/_ops/meadow-shard-contract.txt](../datasets/_ops/meadow-shard-contract.txt) deleted; the corresponding Tier-B `tier_b_meadow_shard_contract` function in [backend/yen_gov/validate.py](../backend/yen_gov/validate.py) deleted.

---

### Phase E — Grain depth (executable, not deferred)

#### PR-E1 — Subdistrict + village entity_kind enablement

- **MODIFY**: [datasets/schemas/indicator-catalogue.schema.json](../datasets/schemas/indicator-catalogue.schema.json) — extend `entity_kinds` enum to include `"subdistrict"`, `"village"`. Bump to v2.1 (additive minor).
- **ADD**: [frontend/src/lib/view-models/subdistricts.ts](../frontend/src/lib/view-models/subdistricts.ts) `loadAllSubdistrictEntities()` against `taxonomy/entities.parquet WHERE entity_type='subdistrict'`; [frontend/src/lib/view-models/villages.ts](../frontend/src/lib/view-models/villages.ts) `loadVillagesForDistrict(district_lgd)` (scoped — never load all). [frontend/src/lib/maplibre/boundaries.ts](../frontend/src/lib/maplibre/boundaries.ts) — register `INDIA_SUBDISTRICTS` + `INDIA_VILLAGES` PMTiles layers.
- **MODIFY**: [frontend/src/lib/charts/choropleth-entity-context.ts](../frontend/src/lib/charts/choropleth-entity-context.ts) — extend `entityContextForGrain` with subdistrict + village branches (each gets a `projectXEntity` shaping function).
- **Tests**: view-model unit tests; explorer E2E for `/i/<indicator>/subdistrict?state=<eci>` + `/i/<indicator>/village?district=<lgd>`.
- **LOC**: ≈ +600 / -20.
- **BLOCKED ON**: C1 (route + component contract first).

#### PR-E2 — Rollup coverage columns (ADR-0043 §"Out of scope" #3)

- **MODIFY**: [datasets/schemas/observation.schema.json](../datasets/schemas/observation.schema.json) → v1.2 (additive): ADD `coverage_member_count_observed: integer | null`, `coverage_member_count_expected: integer | null`, `coverage_fraction: number | null`. Bump `x-changelog`.
- **MODIFY**: [backend/yen_gov/canonical/writer.py](../backend/yen_gov/canonical/writer.py) — write the 3 columns on every state-rollup row (already keyed by ADR-0043 `derivation="sum"`); leave null on raw rows.
- **MODIFY**: [backend/yen_gov/canonical/adapters/livestock/pashu_aadhaar.py](../backend/yen_gov/canonical/adapters/livestock/pashu_aadhaar.py) (and every future rollup-emitting adapter) — compute `observed = COUNT(distinct district_id)` per `(state, indicator, period)`, `expected = COUNT(district WHERE entity_type='district' AND parent_entity_id=state)`.
- **MODIFY**: [frontend/src/lib/canonical/indicator-from-canonical.ts](../frontend/src/lib/canonical/indicator-from-canonical.ts) — surface coverage as a card chip when `< 0.80`; suppress rank-table for that row when `< 0.80`.
- **Tests**: new fixture asserting Delhi pashu-aadhaar rollup carries `observed=7, expected=9, coverage_fraction=0.78` per the live SHAHDARA + Mahamaya Nagar gap; renderer chips appear.
- **LOC**: ≈ +500 / -50.
- **BLOCKED ON**: B5 + the first sub-state family it touches.

#### PR-E3 — Reusable rollup helper

- **ADD**: [backend/yen_gov/canonical/rollup.py](../backend/yen_gov/canonical/rollup.py) — `sum_rollup(rows, *, group_by, sum_col, derivation="sum")` returning new `ObservationRow`s, with coverage columns computed.
- **MODIFY**: livestock adapter (pashu_aadhaar.py + the next sub-state-grain family — e.g. financial-inclusion BSR or NFHS districts) — replace inline SUM with the helper.
- **Tests**: unit tests on the helper; parity tests confirming behaviour identical to inline.
- **LOC**: ≈ +250 / -120.
- **BLOCKED ON**: E2 + at least the second sub-state-grain family landing (Fowler's rule of three).

#### PR-E4 — Boundary serving for subdistrict + village

- **MODIFY**: [datasets/boundaries/](../datasets/boundaries/) PMTiles emission — add `subdistricts.pmtiles` + per-district `villages/<lgd_district>.pmtiles` (scope by district to keep per-fetch payload <1 MB; ref [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) §"performance budget").
- **MODIFY**: [tools/boundaries/build.py](../tools/boundaries/build.py) (or successor) — pipeline step.
- **LOC**: ≈ +400 / -50, regen boundary parquet control row + new PMTiles.
- **BLOCKED ON**: E1.

#### PR-E5 — Province-of-place URL grammar reconciliation

- **MODIFY**: [docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) — record that `/i/<indicator>/<grain>` is the explorer surface that coexists with `/india/<state>/<indicator>` place-first. Document interactions: clicking a state on `/i/<indicator>/state` → `/india/<state-slug>/<indicator>` deep link.
- **MODIFY**: [frontend/src/main.ts](../frontend/src/main.ts) + [frontend/src/lib/url.ts](../frontend/src/lib/url.ts) — wire the cross-link.
- **LOC**: ≈ +150 / -40.
- **BLOCKED ON**: C1 + E1.

---

### Phase Z — Doctrine guardrails + cross-plan-doc sweep

This phase exists so the rip-and-replace does not silently break: (a) future agents' mental model (AGENTS.md drift), (b) other still-active plan-docs that reference soon-to-be-deleted ids/schemas.

#### PR-Z1 — Update CLAUDE.md + every AGENTS.md doctrine

**Status**: doctrine bullets shipped in PR #339 (CLAUDE.md §10 + docs/agents/guardrails.md). AGENTS.md per-family sweep DEFERRED to a follow-up PR after B2-B5 land (otherwise the sweep would be writing forward-looking prose against ids that still exist). The 7 new anti-pattern bullets are the load-bearing piece; the AGENTS.md sweep is clerical and tracked in PR-Z2.

- **MODIFY** [CLAUDE.md](../CLAUDE.md): add anti-patterns under §10 — "Do NOT prefix `state-` / `district-` / `national-` on `indicator_id` (grain lives on the row's `entity_kind`, dispatched at read time per ADR-0044)"; "Do NOT add UI/render fields (`chart_type`, `renderer_rules`, `default_mode`, `facet_labels`, `dimension`) to canonical or topic catalogues — they live in the grapher catalogue at `datasets/grapher/` per ADR-0045"; "Do NOT add facet/grain-fanout cards to a topic page — one card per measure, with facet picker inside (per §C3 rule)."
- **MODIFY** [datasets/livestock/AGENTS.md](../datasets/livestock/AGENTS.md): drop the line at L28 ("state-level aggregates are never persisted") — contradicts ADR-0043; rewrite invariants to reflect the new collapsed indicator-id grammar after B5.
- **MODIFY** [datasets/energy/AGENTS.md](../datasets/energy/AGENTS.md) (if present): same — drop any `state-installed-capacity-*` / `national-installed-capacity-*` doctrine after B3/B4.
- **MODIFY** [datasets/elections/AGENTS.md](../datasets/elections/AGENTS.md) (if present): drop `state-electors-*` / `state-votes-*` references after B2.
- **MODIFY** any other `**/AGENTS.md` under `datasets/`, `backend/`, `frontend/` that names removed ids or removed fields (grep first).
- **MODIFY** [docs/agents/guardrails.md](../docs/agents/guardrails.md): mirror the CLAUDE.md §10 additions.
- **BLOCKED ON**: ADRs (A1) must exist; CLAUDE.md edits cite ADR-0044 + ADR-0045.
- **LOC**: ≈ +200 / -120.
- **Subagent**: Hans (citizen-honest doctrine prose).

#### PR-Z2 — Cross-plan-doc cross-link sweep

- **MODIFY** [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md) §1: ADD a row pointing at this plan-doc with note "Identity collapse + storage/UI decoupling runs IN PARALLEL; does NOT supersede this umbrella's Row 6 (P.1.C energy adapters PR-Q/R/S/T/U arc) or Row 7 (P.1.D sweep) or Row 8 (Citizen-1 panel)." Mark Row 5 ✅ DONE.
- **MODIFY** [TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md) §11: note that Phase 2.A (owner-reg), 2.B (pashu-aadhaar), 2.E (NAIP-IV) ids will be **collapsed by PR-B5 of this plan** (next agent ships them with the new grammar from day one). Phases 1.D NADCP + 1.E Breeding continue unchanged under the livestock plan.
- **MODIFY** [TODO/20260525-pashu-aadhaar-ingest-plan.md](20260525-pashu-aadhaar-ingest-plan.md): note PR-B5 replaces the per-species sibling-id model with one `pashu-aadhaar-count` id + species facet.
- **MODIFY** [docs/research/indicator-id-grain-axis.md](../docs/research/indicator-id-grain-axis.md): status flip OPEN → RESOLVED-Path-B-rip-and-replace, cite ADR-0044.
- **MODIFY** [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md): table row "indicator id (producer-side)" — flip the divergence to "yen-gov ALIGNS with OWID on grain-over-entity after ADR-0044; prior divergence retired."
- **MODIFY** [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) §6: rewrite the indicator-catalogue field table to drop `renderer_rules`; add `entity_kinds` + `default_entity_kind`. §7: drop the `<entity>-` segment from the indicator-naming format spec.
- **DELETE**: any plan-doc cross-link list that pins removed ids.
- **LOC**: ≈ +180 / -250 across ~7 docs.
- **BLOCKED ON**: B2-B5 + D8 (so cross-links reflect post-rip reality).
- **Subagent**: none required; clerical sweep with grep.
- **STATUS**: ✅ SHIPPED PR #365. Text-only forward-pointer sweep across 5 docs (20260517-canonical-long-format-pivot §1 row added; 20260525-livestock-ndlm-ingest-plan §11 PR-B5 forward-pointer note above status table; 20260525-pashu-aadhaar-ingest-plan §3 PR-B5 supersede note; docs/concepts/owid-alignment.md table row flipped to "ALIGNS after ADR-0044"; docs/architecture/data/canonical-store.md §6 added `entity_kinds[]` + `default_entity_kind` rows + `indicator_id` MUST-NOT-carry-prefix note + §7 rewrote naming format to drop `<entity>-` segment + cite ADR-0044 + Rosling rule + rewrote 7.2 examples). docs/research/indicator-id-grain-axis.md status flip + ADR-0044 cite already shipped in PR-A1 #336. `renderer_rules` no-op (already absent from §6 table; lives in grapher catalogue per ADR-0045 / PR-A3a-c).

#### PR-Z3 — Concept registry + overlap-gate CLI + proliferation Tier-B checks (guardrails #13-#18)

- **ADD** [datasets/schemas/concepts.schema.json](../datasets/schemas/concepts.schema.json) v1.0 — fields: `concept_id` (kebab, ≤40 chars), `noun`, `unit_canonical`, `normalisation` ∈ `{absolute, per_capita, per_area, share, ratio, index}`, `entity_kinds[]`, `description_short`, `sources` (empty array — hand-authored taxonomy per ADR-0002).
- **ADD** [datasets/taxonomy/concepts.json](../datasets/taxonomy/concepts.json) — seeded from current 121 indicators by clustering on `(noun, unit, normalisation, entity_kinds)`. Estimated ~60-80 concepts after de-duplication.
- **MODIFY** [datasets/schemas/indicator-catalogue.schema.json](../datasets/schemas/indicator-catalogue.schema.json) v2.1 (additive): ADD `concept_id: string` REQUIRED FK to `concepts.json`; ADD `meta.justification: string | null` (REQUIRED when concept already has another indicator with same `entity_kinds`); ADD `update_period_days: integer` REQUIRED (publisher cadence in days; NDLM monthly = 30, RBI Handbook annual = 365, Census decennial = 3650). Bump `x-changelog`.
- **MODIFY** [datasets/taxonomy/indicators.json](../datasets/taxonomy/indicators.json) — backfill `concept_id` + `update_period_days` on all 121 rows; populate `meta.justification` for any indicator that shares a concept_id + entity_kind tuple with another (should be ~zero after Phase B collapses).
- **ADD** [backend/yen_gov/canonical/concept_registry.py](../backend/yen_gov/canonical/concept_registry.py) — `find_overlap(noun, unit, normalisation, entity_kind) -> list[ConceptMatch]`, with each match carrying `concept_id`, `match_score: float`, `existing_indicators: list[indicator_id]`, `recommended_action: Literal["upsert", "add_facet", "mint_new"]`.
- **ADD** [backend/yen_gov/cli.py](../backend/yen_gov/cli.py) — new `check-overlap` command: `python -m yen_gov check-overlap --noun "<n>" --unit "<u>" --normalisation "<r>" --entity-kind "<k>"` → prints match table; exit 1 if any match ≥ 70% with `recommended_action != "mint_new"`.
- **ADD** new Tier-B checks in [backend/yen_gov/validate.py](../backend/yen_gov/validate.py):
  - `tier_b_one_indicator_per_concept` — rejects two indicators with same `(concept_id, entity_kind)` tuple (guardrail #13).
  - `tier_b_indicator_has_justification` — when an indicator's `(concept_id, entity_kind)` matches another's `concept_id` with different `entity_kind`, require `meta.justification` non-empty (guardrail #15).
  - `tier_b_facet_promotion_warning` — pattern-matches `^(.+)-(coal|gas|hydro|nuclear|solar|wind|cattle|buffalo|goat|sheep|pig|yak|mithun|horse|donkey|mule|coal|petrol|diesel|kerosene|naphtha|lpg)$` across `indicators.parquet`; groups by prefix; if any group has ≥3 members AND no parent indicator with `dimension_values` populated, flag as proliferation (guardrail #16).
  - `tier_b_indicator_freshness_declared` — every row must have `update_period_days > 0` (guardrail #18).
- **ADD** [backend/tests/test_concept_registry.py](../backend/tests/test_concept_registry.py); [backend/tests/test_cli_check_overlap.py](../backend/tests/test_cli_check_overlap.py); [backend/tests/test_tier_b_proliferation.py](../backend/tests/test_tier_b_proliferation.py).
- **ADD** new GitHub Action job `indicator-add-gate.yml` walking the PR diff: if `git diff main -- datasets/taxonomy/indicators.json` adds >1 indicator row, parse the PR body and require either (a) string `"Hans+Max ratified"`, OR (b) one `"facet-collapse-not-applicable: <indicator_id> — <reason>"` line per added id (guardrail #17). Fail-loud if neither pattern present.
- **MODIFY** [CLAUDE.md](../CLAUDE.md) §10 — append the guardrail #14 anti-pattern: "Do NOT mint a new `indicator_id` for a dataset that is 80%+ the same fact as an existing indicator. Run `python -m yen_gov check-overlap` first; UPSERT into existing or add facet axis. Cite the overlap result in the ingest handover doc." Append guardrail #18: "Every indicator MUST declare `update_period_days`." Append guardrail #19: "Methodology break = same id + `methodology_breaks.parquet` row, NEVER a new id (Rosling rule)."
- **MODIFY** [docs/agents/guardrails.md](../docs/agents/guardrails.md) — mirror.
- **MODIFY** every ingest-handover template under `TODO/` (any file matching `*-ingest-*-plan.md` or `*-ingest-handover.md`) — add a §"Concept overlap audit" mandatory section citing `check-overlap` output.
- **LOC**: ≈ +1,200 / -300 (largest PR of the plan; consider splitting into Z3a (schema + concept registry seed) + Z3b (Tier-B + CLI + tests + CI gate) if it crosses 500 LOC at review).
- **STATUS**: Z3a SHIPPED PR #361 `ee5a831b` (concepts schema v1.0 + concepts.json seed + `find_overlap` helper). Z3b-doctrine SHIPPED PR #362 (CLAUDE.md §10 + guardrails.md anti-patterns for guardrails #13 + #18; Rosling-rule #19 already present from PR-Z1). Z3b-cli SHIPPED PR #363 (`check-overlap` CLI command consuming `find_overlap`; `tier_b_indicator_freshness_declared` DARK check + tests). Z3b-tail-actionA SHIPPED PR #364 (`.github/workflows/indicator-add-gate.yml` enforcing guardrail #17: PR adding >1 indicator row must carry "Hans+Max ratified" OR per-id `facet-collapse-not-applicable: <id> - <reason>` line in body). Z3b-tail3 SHIPPED PR #366 (`tier_b_one_indicator_per_concept` DARK function + 8 tmp_path tests; locks the (concept_id, entity_kinds) proliferation oracle for post-backfill enforcement). Z3b-tail-actionBD SHIPPED PR #367 (`tier_b_no_hand_typed_source_id` DARK + `tier_b_indicator_has_justification` DARK; 7 + 8 tmp_path tests; both functions present, NOT chained into `run()`; actionB enforces post-PR-A6 source_registry seam; actionD enforces post-PR-Z3b-tail-actionC concept_id backfill). Z3b-tail-actionC SHIPPED PR #370 (indicator-catalogue.schema.json v2.1 ADDITIVE: optional integer `update_period_days` minimum=1; all 183 indicators.json rows backfilled via cadence-derivation (annual_fy=365, monthly_cy=30, ad_hoc=365 default annual review); indicators_seed.py IndicatorRow + DDL + INSERT placeholder bumped 33->34; indicators.parquet regen; 6 schema-shape + Tier-A backfill assertion tests in `test_indicator_catalogue_schema_v21.py`; existing `test_indicator_catalogue_schema_v2.py` two tests retargeted to v2.1 tail. Unlocks chaining DARK `tier_b_indicator_freshness_declared` live in a follow-up PR. concept_id FK + meta.justification deferred). Z3b-flip SHIPPED PR #371 (chained `tier_b_indicator_freshness_declared` LIVE into `validate.run()`; dark-sentinel test flipped to live-sentinel asserting `+ tier_b_indicator_freshness_declared(root)` IS in `validate.py` source AND check passes clean against backfilled `datasets/taxonomy/indicators.json` 183 rows). Z3b-tail-D SHIPPED PR #372 (NEW [TODO/_TEMPLATE-ingest-handover.md](_TEMPLATE-ingest-handover.md) — mandatory §"Concept overlap audit" forward-reference template for future ingest authors, citing `python -m yen_gov check-overlap` per guardrail #14; no existing TODO/*-ingest-*.md docs amended since the 4 present (health-handover, ECI-multi-state, livestock-ndlm, pashu-aadhaar) are all SUPERSEDED / in-flight under their own plan-docs). Z3b-tail REMAINING: concept_id FK + meta.justification backfill. Z3b-tail-conceptFK Carve 0a SHIPPED PR #373 (indicator-catalogue.schema.json v2.1->v2.2 ADDITIVE schema-only bump: optional string `concept_id` kebab pattern maxLength=40 per guardrail #13; x-changelog v2.2 entry; 5 schema-shape Tier-A tests in new `test_indicator_catalogue_schema_v22.py`; consumer indicators.json $schema_version stamp bumped 2.1->2.2 to satisfy Tier-B `$schema_version == x-version` invariant -- no row backfill in this PR, deferred to Carve 1 which will use Z3a `find_overlap` confidence>=0.95 clustering + stub-concept auto-mint for the 183 rows). Z3b-tail-conceptFK Carve 1 SHIPPED PR #374 (NEW `tools/migrate/backfill_concept_id_fk.py` walks all 183 `datasets/taxonomy/indicators.json` rows, derives `(noun=label_short, unit, normalisation=value_kind-heuristic, entity_kind=default_entity_kind)`, calls Z3a `find_overlap`; if best match score >=0.95 FKs to it (180 rows); otherwise auto-mints a stub concept with kebab-slugified label_short + collision-safe `-N` suffix + `description_short="Auto-minted stub for indicator <id>."` and FKs to it (3 rows added to `datasets/taxonomy/concepts.json` 164->167); `indicators_seed.py` IndicatorRow + DDL + INSERT placeholder bumped 34->35; `indicators.parquet` regen 183 rows / 35 cols; 4 Tier-A backfill assertions in new `test_indicator_catalogue_concept_id_backfill.py` (FK populated on every row, valid kebab, every FK resolves to concepts.json, >=1 stub minted); `test_indicators_seed.py` retargeted v2.1 col-count test -> v2.2 35 cols. Unlocks chaining DARK `tier_b_one_indicator_per_concept` (PR #366) LIVE into `validate.run()` in a follow-up PR). Zjust SHIPPED PR #376 (indicator-catalogue.schema.json v2.2->v2.3 ADDITIVE: optional `meta` object with optional `justification` string minLength=20; backfilled `meta.justification` on the 26 known cross-grain twin rows (5x coal/gas/hydro/nuclear/renewable installed-capacity attribution facets + 2x vote-share + 2x winning-party) naming the structural difference per guardrail #15; chained DARK `tier_b_indicator_has_justification` (PR #367) LIVE into `validate.run()`; dark-sentinel test flipped to live-sentinel + new `test_indicator_catalogue_schema_v23.py` (7 schema-shape + 1 backfill-coverage Tier-A tests); `indicators_seed.py` IndicatorRow gains `meta: _IndicatorMeta | None = None` (Pydantic-validated, NOT in parquet tuple so column count stays 35)). Z3bconceptlive PARTIAL SHIPPED PR #375 (LIVE chain BLOCKED: running the DARK check against the just-backfilled `datasets/taxonomy/indicators.json` surfaces 7 known proliferation clusters per Z3a -- 2 country-grain + 2 state-grain coal-mw + 2 country + 2 state gas-mw + 3 state hydro-mw + ...; chaining into `run()` today would red the existing 5-gate pipeline. SCOPE-REDUCED per CLAUDE.md Holy Law #5 (no band-aids): keep check DARK + add warn-only diagnostic mode `python -m yen_gov validate --warn-concept-proliferation/-w` that prints the same findings as `[WARN tier B]` lines without affecting exit code, so agents/CI can surface the gap without breaking the build. 5 CliRunner tests in `backend/tests/test_cli_validate_warn_concept.py` covering flag-off / flag-on-with-prolif / short-alias `-w` / flag-on-without-prolif / dark-not-chained-sentinel-still-holds. LIVE chain DEFERRED to follow-up PR-Z3bconcept-resolve which must first reconcile the 7 clusters (UPSERT or facet-collapse per guardrail #13)). Z3bconcept-resolve cluster 1 SHIPPED PR #377 (smallest-tractable carve: the 2 country-grain clusters `(coal-mw-absolute,['country'])` + `(gas-absolute,['country'])` each held a STOCK indicator (installed capacity) plus a FLOW indicator (retired capacity) under the same concept_id. Per guardrail #13 / Hans identity rule (identity is what is MEASURED), stock vs flow are distinct measures. Minted 2 new concepts `coal-mw-retired` + `gas-mw-retired` (concepts.json 167->169); reassigned `india-thermal-capacity-retired-mw-{coal,gas}` rows' concept_id + rewrote meta.justification text to declare retirement-flow distinctness; regen indicators.parquet via `compile_to_parquet`; regen manifest. Warn-only diagnostic count drops 7->5 (5 remaining state-grain installed-capacity attribution-facet clusters: coal/gas/hydro/nuclear/renewable each at 3 rows). LIVE chain still BLOCKED on those 5; carved out as follow-up clusters 2-6. 4 Tier-A pins in new `test_concept_resolve_c1_retired_thermal.py`). Z3bconcept-resolve cluster 2 SHIPPED PR #378 (state-grain coal-MW attribution split: the 3 indicators `state-installed-capacity-{geographical,allocated,snapshot}-mw-coal` previously all FK'd to `coal-mw-absolute`. Per guardrail #13 the three attribution methods (physical siting / beneficiary allocation / CEA monthly snapshot) are distinct measures. Minted 3 new state-grain concepts `coal-mw-geographical` + `coal-mw-allocated` + `coal-mw-snapshot` (concepts.json 169->172); narrowed `coal-mw-absolute` to country-grain only (CEA national snapshot); reassigned the 3 state rows' concept_id + rewrote `meta.justification`; regen indicators.parquet + manifest. Warn count drops 5->4. 5 Tier-A pins in new `test_concept_resolve_c2_state_coal_attribution.py`). Z3bconcept-resolve cluster 3 SHIPPED PR #379 (state-grain gas-MW attribution split mirroring cluster 2: 3 indicators `state-installed-capacity-{geographical,allocated,snapshot}-mw-gas` previously all FK'd to `gas-absolute`. Minted `gas-mw-geographical` + `gas-mw-allocated` + `gas-mw-snapshot` (concepts.json 172->175); narrowed `gas-absolute` to country-grain only; reassigned 3 concept_id FKs + rewrote meta.justification; regen indicators.parquet + manifest. Warn count drops 4->3. 5 Tier-A pins in new `test_concept_resolve_c3_state_gas_attribution.py`).
- **Tests**: schema bump + Tier-B + CLI + CI-gate-script unit tests.
- **BLOCKED ON**: A1 (ADRs); A3c (catalogue v2.0 must land before v2.1).
- **Subagent**: Hans + Max (concept naming + clustering), Gregor (schema seam + Tier-B contract), Fowler (CLI ergonomics).

## 3. Acceptance gates per PR

Standard 5-gate DoD (CLAUDE.md §9):

1. `python -m yen_gov validate --root .` → 0 issues
2. `pytest -q` → green (with the 3 standing DuckDB-Windows deselects)
3. `bun run check` in `frontend/` → 0 errors
4. `bun run test` in `frontend/` → green
5. §13 browser smoke on at least one affected citizen route

PRs that delete observation rows or rename indicator ids ALSO run the parity oracle at [backend/tests/test_canonical_parity_oracle.py](../backend/tests/test_canonical_parity_oracle.py).

## 4. Subagent invocation matrix

| When to invoke | Agent | Why |
| --- | --- | --- |
| ADR-0044 / ADR-0045 draft (PR-A1) | Hans + Max + Gregor + Jony | Data-shape + UX sign-off per CLAUDE.md §0a |
| Per-family catalogue collapse (B2-B5) | Hans (citizen framing) + Max (slug correctness) | Validate the new id grammar holds the honest-renderer caveats |
| Grapher catalogue split (A3) | Gregor | Schema boundary owner |
| Tooling seams (A2, A4, A5, A6) | Fowler | Engineering craft + write-seam discipline |
| Routes + topic cleanup (C1-C3) | Jony + Citizen | UX |
| Final smoke on each PR | Citizen | "Does my non-technical Indian user understand what this chart is saying?" |

## 5. Open questions (do NOT block PRs)

These are intentionally left to the agent landing the named PR so they can be re-checked against current code rather than answered ahead of time.

1. **PR-A4a prerequisite** — does an elections + governments parquet emit path already exist somewhere outside `lift-*`? If yes, A4a just wraps it; if no, escalate to Level-4 and consult Gregor before scoping.
2. **PR-B5 / C2** — after the species facet picker mounts, does the agriculture topic need a dedicated `species` axis on [datasets/taxonomy/facet-axes.parquet](../datasets/taxonomy/facet-axes.parquet) with citizen-friendly labels, or stay slug-based? Max call at PR-C2 time.
3. **PR-E2 threshold** — 80% coverage suppression per OWID, or India-tuned (state-tier-weighted)? Hans + Max with first multi-family evidence after E2.
4. **PR-E5** — when both `/i/<indicator>/state` and `/india/<state>/<indicator>` exist, does the home page link to one or both? Jony at PR-E5 time.

## 6. Cross-refs

- [CLAUDE.md](../CLAUDE.md) — Holy Laws + §0a authority routing
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) — current spec
- [docs/concepts/indicator-naming.md](../docs/concepts/indicator-naming.md) §2.2 §2.4 §8 — to be rewritten by PR-A1
- [docs/research/indicator-id-grain-axis.md](../docs/research/indicator-id-grain-axis.md) — Path A vs Path B inputs (will be marked RESOLVED in PR-A1)
- [docs/architecture/decisions/0043-auto-rollup-at-canonical-write-time.md](../docs/architecture/decisions/0043-auto-rollup-at-canonical-write-time.md) — rollup rules that survive the collapse
- [TODO/20260517-canonical-long-format-pivot.md](20260517-canonical-long-format-pivot.md) — umbrella plan; this plan-doc registers a new arc under §1
- [TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md) — livestock family; PR-B5 supersedes its Path A sibling-id convention
- [TODO/20260525-pashu-aadhaar-ingest-plan.md](20260525-pashu-aadhaar-ingest-plan.md) — PR-B5 + C2 close the agriculture mess this plan describes

## 7. Reverse-out

User has stated rip-and-replace + git revert is acceptable. If any PR causes citizen-route regression that smoke catches, the revert is `git revert <sha>` on `main` and a follow-up PR. No alias window, no compatibility shim.

## 8. Kick-off prompt (paste this to start the autonomous run)

Give this single prompt to a fresh execution agent. It embeds every standing authorization and points at this plan-doc as the source of truth.

```
Execute TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md end-to-end autonomously. The user has signed off on every standing authorization in §0ter (rip-and-replace, force-with-lease on own branches, gh pr merge --squash --delete-branch on green DoD, amend/interrupt other plan-docs as enumerated in PR-Z1+Z2, subagent consensus = ratification, escalate to Level-4 without user gate). Stop only on the standing limits in §0ter (no direct main commits, no yenask runtime, no citizen-route 404 without successor, no CLAUDE.md §0a/§1 edits).

Per §0quat, permanent guardrails ship in PR-Z1 + PR-Z2 + PR-Z3 + PR-B9; the rip is not done until those four are on main. Read §0quint OWID-precedent doctrine before any new ingest — it is the test of "new indicator vs UPSERT-or-facet."

Workflow per PR:
1. cd to master worktree, run `git worktree list` + `gh pr list --state open` to refresh the §1 active-worktree map. Update the plan-doc §1 if anything changed.
2. Spawn a per-PR worker worktree off origin/main (never commit on master). Branch name: feat/grain-rip-<pr-id>-<short-slug>.
3. Execute the PR per its §2 row: ADD/MODIFY/DELETE files, run named generators, dispatch named subagents at design + review.
4. Run the 5-gate DoD (§3) with the 3 standing pytest deselects (see repo memory). Plus parity oracle for B-series + D-series.
5. Open PR via `gh pr create`. Once gates green, `gh pr merge <num> --squash --delete-branch`. Force-with-lease on the worker branch if rebase needed; never force on main.
6. After merge, move to the next unblocked PR per §2 dependency graph.
7. After PR-Z1 + PR-Z2 + PR-Z3 + PR-B9 land, post a final summary citing every PR# + merge SHA and confirming Tier-B grain-prefix check + Tier-B one-indicator-per-concept check + check-overlap CLI + indicator-add-gate CI job are all live.

Mandatory subagent dispatches: A1 (Hans+Max+Gregor+Jony), A3a-c (Gregor), B-series (Hans+Max), C-series (Jony+Citizen), Z1 (Hans for doctrine prose), Z3 (Hans+Max for concept clustering + naming, Gregor for Tier-B contract, Fowler for CLI). Other rows: dispatch the named agent if a non-trivial design call surfaces; otherwise execute directly.

Start with PR-A1 + PR-A2 in parallel (both READY, no worktree conflicts). Use the standing reference id-mapping table in §2 verbatim — do not re-derive.
```

**Kick-off requires nothing else from the user.** The standing authorizations in §0ter + the permanent guardrails in §0quat + the per-PR file lists in §2 are the full handover.
