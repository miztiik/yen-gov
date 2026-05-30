# Boundary plan follow-ups (deferred / optional / out-of-scope-recoverable inventory)

**Last Updated**: 2026-05-30

**Source plan**: [TODO/20260529-boundary-rip-and-replace-plan.md](20260529-boundary-rip-and-replace-plan.md) (CLOSED via PRs #434-#456)

**Captured by**: Explore subagent walk of the plan-doc + 11 verdict / handover notes + retired ADRs + frontend / backend code markers, on 2026-05-30 after PR #456 merged at `03e13157`.

**Status**: ALL in-scope plan rows merged. This is the residual list of items that were either (a) explicitly deferred during execution, (b) shipped with a deliberate quality carve-out, or (c) declared out-of-scope but re-scopable if a citizen need surfaces.

**How to use this file**: each item carries WHY-deferred, effort (S/M/L/XL), value (HIGH/MED/LOW), and the upstream change or citizen-trigger that would re-open it. Pick items by `value desc, effort asc` for the next sprint; or filter for HIGH-value items only when planning a follow-up cycle.

---

## Category 1 — Optional gap-fills called out in the plan but not shipped (low-priority / upstream-blocked)

- **C.2.d: Bhuvan panchayat gap-fill for 9 states/UTs** (plan-doc row C.2.d, verdict [notes/2026-05-30-c2-panchayats-source-hunt-verdict.md](../notes/2026-05-30-c2-panchayats-source-hunt-verdict.md) §"Out of scope"): LGD national release missing gram-panchayat geometry for HP, J&K, Sikkim, Meghalaya, Mizoram, Manipur, Nagaland, Arunachal Pradesh + 1 UT. Bhuvan publishes per-state panchayat layers that could fill the gap. Effort: **M** (per-state orchestrator + ~20-100 shards + test). Value: **MED** (rural governance indicators). Trigger: any PRR / MGNREGS / PRI-funds indicator needing panchayat granularity in one of these states.

- **C.3.d: Urban ward gap-fill (LivingAtlas / WB-AMRUT / Shillong) for 7 states** (plan-doc row C.3.d, verdict [notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md](../notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md) §"Out of scope"): SBM Wards upstream missing WB, Tripura, Mizoram, Manipur, Meghalaya. Three parallel sources available (WB-AMRUT for WB; Shillong CMD for Shillong MB; LivingAtlas national cross-verify). Effort: **M** per source. Value: **MED** (urban governance + sanitation tracking). Trigger: any urban-governance / Swachh-Survekshan / AMRUT indicator demanding ward granularity in <state>.

- **C.4: Ladakh villages (U09)** (plan-doc row C.4.a note, verdict [notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md](../notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md) §"Out of scope"): `Bhuvan_JK_Villages` covers U08 only; U09 absent. C.4.a shipped 14 J&K shards; U09 deferred indefinitely. Effort: **S** (parallel orchestrator `lift_villages_ladakh_bhuvan.py` mirrors C.4.a). Value: **LOW** (latent demand). Unblock trigger: ramSeraph publishes Ladakh villages OR LGD releases Ladakh village geometry.

- **C.4: Other 7-state villages gap-fill** (HP, Sikkim, Meghalaya, Mizoram, Manipur, Nagaland, Arunachal Pradesh): LGD national villages release missing. Similar pattern to C.4 Bhuvan-JK; deferred until a village-keyed indicator demands it. Effort: **S** per state. Value: **LOW** (state-specific, latent). Trigger: village-grain indicator demand per state + upstream availability check.

---

## Category 2 — Carve-outs / interim solutions that shipped with deliberate quality compromise

- **A.1.a: S01 AP LGD with pre-bifurcation residue** (PR #434, plan-doc row A.1.a): S01 LGD release carries legacy `ac_no` numbering 1-294 from pre-2014 unified AP+TG. Shipped: name-based `ac_no` rewrite to align with post-2014 SoT + preserved `lgd_legacy_ac_no` + `lgd_ac_id` on every feature. Citizen-visible gap: map renders 175 coloured ACs (correct) PLUS ~119 no-fill residual polygons (former TG territories, visible as transparent). Severity: **COSMETIC** (accepted per user mandate 2026-05-29 "accept the vintage mismatch with a ribbon"). Effort to close: **L** (wait for ramSeraph LGD v2 OR manual boundary surgery). Value: **MED** (visual polish; joins work correctly). Upstream unblock: ramSeraph LGD v2 with post-bifurcation AP geometry.

- **A.1.b: S03 Assam Tier-4 district fallback (interim)** (PR #435, plan-doc row A.1.b): S03 post-2023 delimitation boundaries not machine-readable from any upstream. Verdict: T3 PDF digitization deferred (40-60h QGIS work), T4 district fallback shipped as interim. Citizen-visible gap: `/s/assam/ac/<n>` map shows parent DISTRICT polygon instead of coloured individual ACs; tooltip declares "boundaries pending post-2023 delimitation; showing district outlines as interim." Election results still bind correctly to post-2023 SoT `eci_no` (no join breakage). Effort to close: **L** (40-60h T3 QGIS vectorization of Delimitation Order PDF + topological closure). Value: **HIGH** (blocks AC-grain electoral insights). Upstream unblock: (a) authorise T3 QGIS vectorization sprint, OR (b) ramSeraph / Delimitation Commission / community publishes post-2023 Assam AC machine-readable boundaries.

---

## Category 3 — Renderer / UX follow-ups deferred from infrastructure PRs

- **C.2.c: Panchayat district-picker UI component** (plan-doc row C.2.c §"Scope TBD"): Frontend panchayat registry ships 663 entries (state + district keyed); no district-picker UI component to navigate the ~2,500-300k panchayats per state. Scope: new Svelte component that (a) accepts state selection, (b) lists districts with panchayat coverage, (c) loads shard on selection. Effort: **M** (component + integration + E2E test). Value: **MED** (reduces per-state map performance risk). Why deferred: measured data needed to tune picker UX (typical district panchayat counts, name lengths, search patterns).

- **C.3.c: ULB ward-picker UI component** (plan-doc row C.3.c §"Scope TBD"): Frontend ward registry ships ~3,300 entries (state + ULB keyed); no ULB-picker UI component to navigate the 200-7,000 wards per state. Scope: new Svelte component keyed by ULB (not district). Effort: **M**. Value: **MED** (urban-governance rendering). Why deferred: measured data needed for UX tuning.

- **Frontend villages rendering / registry** (implicit from C.4 + C.2 + precedent): Village layer NOT currently exposed in [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) or any contract test. Villages exist on disk (645 shards + C.4.a 14 J&K shards = 659 total) but have no citizen-facing surface. Effort: **M** (registry + contract test + picker). Value: **BLOCKED** (no indicator consumer exists yet). Unblock trigger: first village-grain citizen indicator (e.g. MGNREGA person-days, micro-watershed, PMGSY road length) lands.

---

## Category 4 — Explicit Phase D non-goals that could re-scope if user need surfaces

- **Historical districts (1941-2001, 8 decadal snapshots)** (plan-doc Phase D, explicit non-goal per user mandate 2026-05-29 "focus on future not historical accuracy"): OUT OF SCOPE. Re-scope trigger: citizen indicator explicitly demanding historical district boundaries (e.g. "show agricultural productivity by 1971 district boundaries"). Effort: **L**. Value: **LOW**.

- **Census 2011 polygon snapshot**: LGD modern geometry pre-dates Census 2011 boundaries. OUT OF SCOPE per user mandate. Re-scope trigger: Census-grain historical indicator. Effort: **M**. Value: **LOW**.

- **SHRUG Census 2011 harmonized variant**: Deferred alongside Census 2011 polygon layer. Same trigger. Effort: **M**. Value: **LOW**.

- **Habitations / sub-village granularity**: OUT OF SCOPE (village is already very granular; habitation ingest would balloon storage 10-20x). Re-scope trigger: citizen indicator at sub-village granularity (unlikely). Effort: **XL**. Value: **LOW**.

- **Polling stations (7 ramSeraph sources)** (ECI 2014/2017/2022/2025 + Bhuvan AP 2014 + Punjab 2020 + NESDR Manipur): OUT OF SCOPE (election-results rendering is a `/e/` event-page concern). Re-scope trigger: event-page drill-down to polling-station grain. Effort: **L**. Value: **MED**.

- **Slums (8 sources)** (WB AMRUT, GHMC, Telangana, TN, BBMP, MCGM, Delhi GSDL, others): OUT OF SCOPE for v1 (no slum-keyed indicators shipped). Re-scope trigger: slum-welfare / urban-health indicator. Effort: **L** per source. Value: **MED**.

- **ULB cadastrals (52 ramSeraph sources)**: Per-plot urban property boundaries. OUT OF SCOPE (beyond citizen-facing geography). Re-scope trigger: property-tax / municipal-revenue indicator. Effort: **XL**. Value: **LOW**.

- **Post Offices / PostalGIS (point layer)**: OUT OF SCOPE (pincode polygons already cover postal geography; point layer adds little without a postal-service indicator). Value: **LOW**.

- **Cadastrals / water / transport / power / buildings / industries / floods / DEM / geomorphology / lithology / SOI topo / lineament**: Indicator-family concerns per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md); if needed they live in `datasets/<family>/_meadow/...`, NOT under `datasets/boundaries/`. OUT OF SCOPE for this plan. Re-scope trigger: family-specific indicator adoption. Effort: **M** per layer. Value: family-dependent.

---

## Category 5 — Corpus-wide / Level-5 migrations deferred to successor plan

- **Full `eci_no` → LGD `AC_ID` migration (join-key change across all election results + indicators)** (plan-doc LGD-golden doctrine §"Out-of-scope for any single PR"): A.1.a preserves `lgd_legacy_ac_no` + `lgd_ac_id` on features but election results + SoT files still use ECI `eci_no` as primary join key. Full migration: (a) rewrite all election-result parquet rows, (b) audit indicator-family tables for eci-code dependencies, (c) reverse-engineer AC_ID ↔ eci_no mapping for all 31 states. Effort: **XL** (multi-PR corpus rewrite). Value: **HIGH** (locks LGD identity going forward). DEFERRED to Level-5 successor plan per [CLAUDE.md §6](../CLAUDE.md).

- **Multi-source villages consolidation**: If Bhuvan-HP + Bhuvan-Sikkim land, a future "C.4.x" row may benefit from a consolidated orchestrator accepting `--source {lgd | bhuvan-<state>}` instead of parallel per-state scripts. Effort: **M** (refactor `lift_villages_*` family). Value: **LOW**. Trigger: 2nd non-J&K state villages gap-fill.

- **Sub-panchayat / GP Ward layer**: LGD defines GP wards as sub-GP elected units. No current geometry source. Effort: **M**. Value: **LOW**. Unblock: BOTH upstream availability AND citizen indicator demand at GP-ward grain.

---

## Category 6 — Test / contract / observability follow-ups

- **A.4: AC coverage >= 90% threshold deferred** (plan-doc row A.4, verdict [notes/2026-05-29-state-ac-coverage-report.md](../notes/2026-05-29-state-ac-coverage-report.md)): Original gate required >= 90% coloured AC polygons per state. Verdict: conflates boundary coverage with election-result coverage. Current A.4 gate uses 5 invariants (no pageError/requestFailed, H1 resolves to SoT name, canvas mounts, footer attribution renders, shard GET returns 200); no pixel-count threshold. Effort to re-introduce: **S** (add chromium pixel comparison). Value: **MED** (regression guard). Trigger: election-results ingest completion.

- **Pre-existing vitest `boundaries-conform.test.ts` U08/U09 villages failure** (per PR #455 lesson): 14 orphan U08/U09 village geojsons in baseline failure. Last touched in PR #449 (ULB Wards). Not introduced by this plan but surfaced repeatedly. Effort: **S** (orphan cleanup PR — either delete the 14 files OR add their entries to the conformance allow-list). Value: **MED** (removes the "1 known failure" noise from every vitest run going forward). Trigger: standalone cleanup PR.

---

## Category 7 — Plan-doc / docs hygiene + distillation follow-ups (per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md))

- **C.2 verdict + implementation plan distillation** (source: [notes/2026-05-30-c2-panchayats-source-hunt-verdict.md](../notes/2026-05-30-c2-panchayats-source-hunt-verdict.md)): Multi-tier verdict (TL;DR, upstream investigation, existing precedent, recommended path + slicing) should distill into: (a) `docs/concepts/admin-level-sourcing.md` (NEW: how we source each admin level; 3-convention rule + Bhuvan-LGD-ramSeraph lineage); (b) append "Panchayats partition strategy" section to the boundary architecture doc. Effort: **S**. Value: **HIGH** (future agents reference docs, not verdict notes).

- **C.3 verdict + implementation plan distillation** (source: [notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md](../notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md)): Same distillation shape as C.2. Append "ULB Wards partition strategy" section to boundary architecture doc. Effort: **S**. Value: **HIGH**.

- **C.4 verdict + implementation plan distillation** (source: [notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md](../notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md)): Parallel-orchestrator pattern (Bhuvan-JK-specific vs LGD-national) should distill to `docs/how-to/add-new-boundary-layer.md` (NEW: "when to fork vs consolidate orchestrators"). Effort: **S**. Value: **MED**.

- **A.1.b: Tier ladder + T3 PDF vectorization process** (source: plan-doc row A.1.b narrative + [notes/2026-05-29-phase-b-verdict-correction.md](../notes/2026-05-29-phase-b-verdict-correction.md)): The 4-tier fallback ladder (T1 machine-readable > T3 PDF digitization > T4 district fallback > T2 Voronoi) and the T3 "40-60h QGIS vectorization" mechanics should distill to `docs/how-to/digitize-ac-from-pdf.md` (NEW: step-by-step QGIS workflow for Delimitation-Order PDF → topologically-sound AC shapefiles). Effort: **M** (actual workflow + screenshots). Value: **HIGH** (unblocks S03 + future delim AC digitization).

- **ADR-0029 retirement section: backlink to D.1.A user mandate** (source: PR #455): ADR carries the "Retirement (D.1.A, 2026-05-30)" section but should embed the verbatim user mandate quote + link to plan-doc row D.1.A. Effort: **S**. Value: **HIGH** (archaeologists understand the WHY).

---

## Category 8 — Code-level TODO/FIXME markers tied to this plan-doc

- **[frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts)**: implicit TODO for district-picker UI shim (C.2.c + C.3.c). When pickers are implemented, mark `PANCHAYAT_BOUNDARY_BY_DISTRICT` + `WARD_BOUNDARY_BY_ULB` registries with `// TODO: wire district-picker on state selection`. Effort: **S** (comment annotation). Value: **LOW** (polish).

- **[frontend/src/lib/boundaries.ts](../frontend/src/lib/boundaries.ts)**: implicit TODO for villages registry. Add `// TODO: add VILLAGE_BOUNDARY_BY_DISTRICT registry when first village-grain indicator lands`. Effort: **S**. Value: **LOW**.

---

## Summary stats

| Category | Count |
| --- | ---: |
| 1. Optional gap-fills | 4 |
| 2. Carve-outs | 2 |
| 3. UX follow-ups | 3 |
| 4. Re-scopable non-goals | 9 |
| 5. Level-5 corpus migrations | 3 |
| 6. Test / contract | 2 |
| 7. Docs distillation | 5 |
| 8. Code markers | 2 |
| **Total** | **30** |

**HIGH-value items (citizen-visible quality / architecture-critical, recommended first pass)**:

1. **A.1.b S03 Assam T3 PDF vectorization** — unblocks AC-grain electoral insights for S03 (only-state-of-blocker for AC-grain India coverage). Effort L. Citizen-visible HIGH.
2. **C.2/C.3/C.4 verdict distillation** (3 items) — saves every future agent the cost of re-discovering source-hunt findings; should run as 1 docs PR. Effort 3×S. Process HIGH.
3. **A.1.b tier ladder + T3 PDF workflow docs** — pairs with #1; documents the digitization workflow so the 40-60h sprint can be picked up by anyone (not just the agent that wrote A.1.b). Effort M. Process HIGH.
4. **ADR-0029 retirement backlink** — single-edit hygiene; restores audit-trail integrity for the D.1.A retirement. Effort S. Process HIGH.
5. **Full `eci_no` → LGD `AC_ID` corpus migration** — the LGD-golden doctrine's natural conclusion; Level-5 successor plan when sprint capacity allows. Effort XL. Architecture HIGH.

**Quick wins (S effort + MED-or-HIGH value, can ship in a single afternoon)**:

- ADR-0029 retirement backlink (S, HIGH)
- 3× verdict distillations C.2 / C.3 / C.4 (3×S, HIGH / HIGH / MED)
- A.4 AC coverage threshold re-introduction post-election-results (S, MED)
- Pre-existing vitest U08/U09 villages cleanup (S, MED)
- Code-marker TODO annotations (2×S, LOW — bundle with any near-by edit)

**BLOCKED items requiring upstream change**:

- C.4 Ladakh villages (waiting for ramSeraph OR LGD)
- C.4 other 7-state villages (per-state upstream availability)
- A.1.a S01 AP residue cleanup (waiting for ramSeraph LGD v2)

**BLOCKED items requiring citizen-indicator demand to re-scope**:

- C.2.d panchayat gap-fill (9 states) — rural-governance trigger
- C.3.d ward gap-fill (7 states + WB-AMRUT / Shillong / LivingAtlas) — urban-governance trigger
- Frontend villages registry — village-grain indicator
- Polling stations (7 sources) — `/e/` event-page drill-down
- Slums (8 sources) — slum-welfare / urban-health indicator
- All Category 4 explicit non-goals

---

## How to action this list

**For the next session (recommended order if user signs off)**:

1. **Quick-wins docs PR**: bundle the 4 Category-7 docs distillations + ADR-0029 backlink into one Level-2 docs PR (~1 day; HIGH value, S effort each).
2. **Vitest cleanup PR**: drop or allow-list the 14 orphan U08/U09 village geojsons (~half day; MED value).
3. **Level-5 design checkpoint**: open a successor plan-doc for the `eci_no` → `AC_ID` corpus migration (research-only first PR; user-led scoping for the rewrite arc).
4. **S03 T3 sprint authorisation**: discuss whether the user wants to allocate the 40-60h Assam PDF vectorization sprint (HIGH value but high cost).

**For when a citizen indicator triggers a deferred gap-fill**:

- Re-read the relevant verdict note + this file's Category 1/3/4 entry
- Run [tools/boundaries/](../tools/boundaries/) precedent (e.g. mirror C.4.a `lift_villages_*` family for villages, C.2.b `lift_panchayats_*` for panchayats)
- Add the registry entry to [frontend/src/lib/maplibre/sources.ts](../frontend/src/lib/maplibre/sources.ts) + contract test
- Author the picker UI shim if grain is below state

**For when upstream releases a new source**:

- Re-check the verdict notes' "Out of scope" sections for the matching trigger condition
- Re-run the source-hunt scout subagent on the new release URL
- If the new source satisfies the trigger, the gap-fill PR template is already documented in the verdict note + this entry

---

## See also

- [TODO/20260529-boundary-rip-and-replace-plan.md](20260529-boundary-rip-and-replace-plan.md) — source plan (CLOSED)
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) — process for lifting items from this file into permanent /docs
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) — PR lifecycle for actioning any item
- [docs/architecture/decisions/0034-documentation-routing-contract.md](../docs/architecture/decisions/0034-documentation-routing-contract.md) — where each distilled item lands
- All 11 source notes under [notes/](../notes/) — primary research and verdict trail
