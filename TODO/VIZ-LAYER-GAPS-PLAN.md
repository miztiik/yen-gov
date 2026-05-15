# Visualization-Layer Gaps — Implementation Plan

**Created**: 2026-05-17
**Authors (audit)**: Jony (UI/UX), Fowler (Engineering), Hans (Governance)
**Status updated**: 2026-05-15 (handover for next agent — Fowler + Jony concurred)
**Source docs**: [`docs/reference/data-coverage-report.md` §6](../docs/reference/data-coverage-report.md#6-frontend-wiring-gaps-visualization-layer), [`docs/reference/data-inventory.md` §1Z](../docs/reference/data-inventory.md)

> **Status snapshot (2026-05-15)** — Phases 0, 1, 2, 3.1–3.6 ✅ on `origin/main`. Allowlist down from 43 → 8 entries. Phase 4 C1 ✅ (`5f6735d`, dispatch seam extracted) and Phase 4 C2 ✅ (`f11c92c`, facet labels lifted into schema 1.4). **Next**: Phase 4 C3 (split into C3a structural + C3b behavioural per Fowler) — see "Handover" section near the bottom of this doc.

## Problem in one paragraph

The data layer crossed a threshold around 2026-05-15/16: with NSDP back to FY 1994–95, CPI back to FY 1974–75, and SRS vital rates per state, yen-gov can now sustain *trend* narratives, not just snapshots. The auto-inventory says **43 of 80 indicator artifacts on disk are unreachable from the IA today** — three whole categories (`prices/`, `health/`, `human_development/`) and most of the new RBI Handbook spliced fiscal/economy long-history wedge. Mechanically wiring them now would render, but citizens would see (a) base-year-rebase artifacts with continuous polylines and "+3,400%" headlines, (b) a year dropdown mixing `"2024"` / `"2024-04"` / `"2025-03"` with no labelling, (c) `vintage` silently dropped from RBI splice rows, (d) crude death rate misread as Kerala's "health failure", (e) absolute ₹ Crore for pension expenditure favouring large states. **Tidy first, then wire.**

## Sequencing principle (Tidy First / Beck)

Each phase ships only structural OR behavioural changes per commit, never both. Each phase MUST land its own tests in the same commit (CLAUDE.md §15). Phases 0–2 are blockers for the new wedges; Phase 3 is the wiring (citizen-visible payoff); Phase 4 is the deferred polish that can land alongside.

---

## Phase 0 — Drift detector (Correction Level 2)

**Goal**: make catalogue/disk drift impossible to ship silently. The auto-inventory now prints a wiring summary; CI must fail on regression, not just print it.

- [x] **`frontend/src/contracts/catalogue-coverage.test.ts`** (new). Glob `datasets/indicators/in/**/*.json`; load `datasets/reference/in/topic-catalogue.json` and collect every `kind:"indicator"` `id`. Assert: every artifact id appears in the catalogue OR in an explicit `frontend/src/contracts/catalogue-coverage.allowlist.json` (with a `reason` per entry). Initially seed the allowlist with the 43 currently-unwired ids so the test passes; each Phase 3 commit removes ids from the allowlist as they get wired.
- [x] **Wire the test into `npm test`** — already runs by default if it lives under `src/`. Verify red→green by temporarily removing one allowlist entry.

**Risk**: trivial. **Tests first**: by definition.

---

## Phase 1 — Renderer guardrails for the new shapes (Correction Level 2)

**Goal**: extract the small primitives that the prices / health / NSDP-long-history wedges depend on, so the wiring commits in Phase 3 are pure additions.

Land each as a separate commit, structural-then-behavioural. Each lists test-first work and component change.

### 1.1 `formatTimeLabel(time, grain)`

- [x] Pure helper in [`frontend/src/lib/indicators.ts`](../frontend/src/lib/indicators.ts).
- [x] Vitest cases: `("2024-04","fiscal_year")→"FY 2024-25"`, `("2024","year")→"2024"`, `("2025-03","date")→"as of Mar 2025"`, `("2024-Q2","quarter")→"Q2 FY25"`.
- [x] Swap raw `{t}` rendering in `IndicatorRanked.svelte`, `IndicatorChoropleth.svelte` slider tick, `IndicatorSmallMultiples.svelte`. **Without this, a topic page mixing CEA snapshot + ICED FY + SRS CY is visually dishonest.**

### 1.2 `splitOnBreaks(rows, breaks)` + `series_breaks`-aware sparkline

- [x] Extract pure helper. Vitest: N-1 segments for N break points; segment endpoints inclusive at break-time.
- [x] [`IndicatorSmallMultiples.svelte`](../frontend/src/lib/IndicatorSmallMultiples.svelte) `pathFor()` emits one `<path>` per segment. Drop the `Math.abs` in `y_max` (let Y include negatives — required by deflation / deficit values).
- [x] Snapshot test against fixture WPI artifact: 5 segments rendered, no straight line through any rebase tick.

### 1.3 `growthSafeAcross(bars, breaks)` guard in `headline.ts`

- [x] Pure helper next to [`frontend/src/lib/charts/stacked-trend/headline.ts`](../frontend/src/lib/charts/stacked-trend/headline.ts) `soWhat()`.
- [x] Vitest: bars spanning a `definition_change` break → `null`; bars spanning a `coverage_change` only → permitted but with a flag; bars wholly within one segment → unchanged behaviour.
- [x] Wire the guard so headline emits "see notes" when null.

### 1.4 `vintage` round-trip (Correction Level 1, additive type)

- [x] Add `vintage?: string` to `IndicatorRow` in [`frontend/src/lib/indicators.ts`](../frontend/src/lib/indicators.ts) and to `IndicatorDoc.rows` in [`frontend/src/lib/charts/stacked-trend/adapter-indicator.ts`](../frontend/src/lib/charts/stacked-trend/adapter-indicator.ts). Pure additive — schema v1.3 already ships the field.
- [x] One vitest asserting an RBI splice fixture round-trips `vintage` through the loader.
- [x] Tooltip render is a separate commit (Phase 4.1) — Tidy First.

### 1.5 `value_kind: "index"` first-class in StackedTrend

- [x] Add `"index"` to the StackedTrend `value_kind` zod union in [`adapter-indicator.ts`](../frontend/src/lib/charts/stacked-trend/adapter-indicator.ts) `MAP_VALUE_KIND`.
- [x] Branch in `headline.ts`: index → never emits `pctDelta` ("change in an index level is misleading without a base-year statement").
- [x] Vitest: feed a national WPI fixture; assert no `+x%` claim, assert tooltip-friendly base-year text is set.

**Phase 1 verdict gate**: all five primitives green + new tests passing → proceed to Phase 2.

---

## Phase 2 — Honesty primitives in the citizen-facing chrome (Correction Level 2)

Small new components. Ship each with a Svelte testing-library vitest.

- [x] **`SeriesBreakAnnotation.svelte`** — vertical dashed rule + caret label on any time axis (line, sparkline, year-slider tick). Mandatory before any long-history series wires.
- [x] **`SnapshotBadge.svelte`** — extracted from `IndicatorChoropleth.svelte`'s stale-chip. Reused by `IndicatorRanked.svelte` and `IndicatorSmallMultiples.svelte` so a CEA single-month artifact is consistently flagged.
- [x] **`DirectionLegendCue`** — one-word verbal tag in legend ("lower is better", "neutral · darker = higher", "higher is better"). One Tailwind utility, ~5 lines. Eliminates the colour-only signalling smell flagged by Jony for IMR (orange ramp) + CPI (blue neutral).
- [x] **`VintageTooltipLine`** — addition to [`ChartTooltip.svelte`](../frontend/src/lib/ChartTooltip.svelte) showing per-row `vintage` ("Base 2011-12", "First Advance Estimates"). Depends on Phase 1.4.
- [x] **`RebaseBanner.svelte`** — small amber strip on `IndicatorChoropleth.svelte` when the year slider lands on or past a `series_breaks` boundary. "Base-year change at YYYY; values not directly comparable to earlier slider positions."

**E2E gate**: extend [`frontend/e2e/golden-path.spec.ts`](../frontend/e2e/golden-path.spec.ts) (or a sibling) with one route that exercises a long-history artifact; assert (a) page-error-clean, (b) at least one `[data-series-break]` element rendered, (c) `[data-vintage]` text present in tooltip on hover.

---

## Phase 3 — Wire the new wedges (Correction Level 2 per topic; pure additive)

Each topic is one PR. The Phase 0 catalogue-coverage test fails on each PR until the wiring lands; the same PR also removes the corresponding allowlist entries.

### 3.1 Topic: `prices` (Prices & Inflation)

- [x] Add `prices` topic to `datasets/reference/in/topic-catalogue.json` (between `fiscal` and `economy`). `direction: "neutral"` throughout. Featured.
- [x] Wire 4 state CPI sub-index inflation rates (`state_cpi_general_inflation_pct` featured; food / fuel / housing-urban siblings unfeatured).
- [x] Wire 3 national index series (`national_cpi_combined_index_annual` featured; `national_cpi_iw_index_annual` + `national_wpi_all_commodities_index_annual` unfeatured). All three carry `series_breaks`.
- [x] Catalogue-coverage allowlist: remove the 7 prices ids.
- [x] First-render sentence on the topic page (Hans wording): *"Inflation in your state vs the RBI's 4% medium-term target — neither high nor low is automatically good; food / fuel are largely set by national / global conditions."*
- [x] Footnote on `state_cpi_housing_urban_inflation_pct`: *"Urban-only by NSO methodology — no rural housing component is collected."*

### 3.2 Topic: `health` (Vital statistics & health)

- [x] Add `health` topic. List `state`. Featured.
- [x] Wire IMR (featured, `direction: lower_is_better`); birth rate / death rate / TFR (`direction: neutral`); public health expenditure (input, `neutral`).
- [x] Catalogue-coverage allowlist: remove the 5 health ids.
- [x] **Per-artifact framing tooltips (mandatory, not optional)** — these are the corrective-framing rows from `data-coverage-report.md` §5d. Specifically:
  - Crude Death Rate: *"Not age-adjusted — older states (Kerala, TN, Punjab) read structurally higher. Read alongside IMR."*
  - Birth rate: *"Falls naturally as a population ages; below ~21 = at or near replacement fertility."*
  - TFR: *"Replacement-level is 2.1; India crossed below replacement around 2020."*
  - Public health expenditure: *"Spending is an input — pair with IMR / Life Expectancy. FY24/FY25 are RE / BE."* Default render must be per-capita (₹/person), NOT absolute ₹ Crore.

### 3.3 Topic: `transport` (Mobility)

- [x] Add `transport` topic. Not featured initially (only 2 artifacts).
- [x] Wire EV registrations + EV-share.
- [x] Catalogue-coverage allowlist: remove the 2 transport ids.

### 3.4 Extend `economy`

- [x] Wire 4 RBI-spliced state NSDP / per-capita-NSDP siblings. Mark `state_per_capita_nsdp_constant_inr_long` featured (long-history hero). Each renders with `SeriesBreakAnnotation` and `RebaseBanner` automatically (Phase 2). Per-row `vintage` in tooltip (Phase 1.4 + 4.1).
- [x] Wire 4 `national_*` aggregates (GDP / GVA / quarterly GVA / macro aggregates).
- [x] **Mandatory framing on `state_per_capita_nsdp_current_inr*`**: *"Current prices include inflation. For real change, switch to constant prices."* Default toggle should be constant.
- [x] Telangana per-row badge: *"Pre-FY15 back-projected from undivided AP."* J&K per-row badge: *"Post-FY20 covers UT-only J&K."*
- [x] Catalogue-coverage allowlist: remove the 8 economy ids.

### 3.5 Extend `fiscal`

- [x] Wire 7 RBI per-state long-history series (`state_external_debt_inr_crore`, `state_grants_in_aid_inr_crore`, `state_non_tax_revenue_inr_crore`, `state_own_tax_revenue_inr_crore`, `state_pension_expenditure_inr_crore`, `state_revenue_expenditure_inr_crore`, `state_share_central_taxes_inr_crore`).
- [x] Promote `state_pension_expenditure_inr_crore` to **featured** (OPS political salience). Default render: % of state revenue receipts (derived view — see Phase 5), not absolute ₹ Crore.
- [x] Catalogue-coverage allowlist: remove the 7 fiscal ids.

### 3.6 Extend `energy`

- [x] Wire `state_per_capita_electricity_consumption_kwh` as featured.
- [x] Wire 7 other per-state cuts unfeatured (RBI Handbook duplicates of ICED series; keep them addressable for power users).
- [x] Catalogue-coverage allowlist: remove the 8 energy ids.

### 3.7 `human_development/state_hdi` — pinned card on `StateOverview`

- [x] Surface as a single hero stat on [`StateOverview.svelte`](../frontend/src/routes/StateOverview.svelte), not a dedicated topic.
- [x] Tooltip: producer + methodology vintage (HDI is composite — UNDP 2010 / 2014 / 2020 weightings differ).
- [x] Catalogue-coverage allowlist: remove the human_development id.

**Phase 3 done = allowlist is empty + `npm test` and `npm run test:e2e` green + agent-driven smoke per CLAUDE.md §13 on `/t/prices`, `/t/health`, one updated state hub.**

---

## Phase 4 — Deferred polish (Correction Level 1–2; non-blocking)

These can land alongside Phase 3 commits or in a follow-up sweep.

- [ ] **4.1** Tooltip surfaces `vintage` (depends on Phase 1.4).
- [ ] **4.2** Quarterly time formatter — `national_gva_by_industry_quarterly_constant_2011_12_inr_crore` slider ticks.
- [x] **4.3** Move `category_labels` for `installed_capacity_by_source_mw` out of `TopicLanding.svelte` into the indicator artifact's `notes` / `facet_labels`.
- [ ] **4.4** `IndicatorCache` (Strangler Fig). Defer until a real page measurably feels slow.
- [ ] **4.5** Snapshot-aware fallback in `IndicatorRanked` + `IndicatorSmallMultiples` (`chart_type: "snapshot"` dispatch in catalogue) — citizen-trust fix for CEA per-fuel artifacts.

---

## Phase 5 — Derived views (composable; no new fetch)

Hans's lens: today we ship the inputs but not the citizen-relevant ratios. Each is a pure derivation in the loader / a new artifact emitted by the backend (decision deferred).

- [ ] `fiscal/derived/own_tax_to_gsdp_ratio` — `state_own_tax_revenue_inr_crore` ÷ `state_gdp_current_inr_lakh_crore`.
- [ ] `economy/derived/real_gsdp_growth_yoy_pct` — YoY of `state_nsdp_constant_inr_crore` with rebase-aware gaps.
- [ ] `economy/derived/per_capita_real_view` — paired current + constant chart on one canvas.
- [ ] `fiscal/derived/state_capex_share` — capex as % total expenditure and as % GSDP.
- [ ] `fiscal/derived/pension_share_of_revenue_receipts` — denominator extracted from RBI HBS-IS Table 167.
- [ ] `health/derived/per_capita_public_health_spend` — ₹ Crore ÷ population.

Decision needed: derive in the frontend loader (cheap, no backend round-trip) or emit as first-class artifacts in `datasets/indicators/in/derived/` (durable, shows up in inventory + contract tests). Recommendation: emit as first-class — keeps the schema-first contract honest and lets contract tests cover the derivation.

---

## Phase 6 — New ingests (longer horizon; out of this plan's scope)

Tracked here only as the natural successor; each becomes its own ingest plan + adapter. Order is Hans's priority ranking from `data-coverage-report.md` §5a:

1. `fiscal.fc.horizontal_devolution_share` (15th FC Annex 8.1; hand-author, one row per state).
2. `fiscal.union.cess_surcharge_share_of_gross_tax`.
3. `fiscal.gst.state_collections_and_compensation` (methodology guard: SGST + settled IGST).
4. `labour.plfs.state_unemployment_lfpr_wpr` (with NSS EUS → PLFS `definition_change` at 2017-18).
5. `rural.mgnrega.persondays_and_real_wage`.
6. `fiscal.css.transfers_per_state`.
7. `health.srs.maternal_mortality_ratio` + `health.srs.life_expectancy_at_birth` (deferred from 2026-05-16 SRS batch — different shapes).
8. `education.nas.reading_arithmetic_grade_5`.

---

## Definition of Done for this plan

- [ ] Catalogue-coverage allowlist empty (Phase 0 + Phase 3).
- [ ] `frontend/src/lib/indicators.test.ts`, `IndicatorSmallMultiples.test.ts`, `headline.test.ts`, `adapter-indicator.test.ts` all green with the new helpers covered.
- [ ] At least one E2E spec covers a long-history rebased artifact and asserts visible break markers + vintage tooltip.
- [ ] `python -m yen_gov coverage` reports `Frontend wiring: 80 of 80` (or whatever the count is at that point).
- [ ] `data-coverage-report.md` §6 updated to "complete" status (this plan deleted from the in-flight list).
- [ ] Mis-framing-debt rows in §5d each have a sentence on the live page (manually verified per CLAUDE.md §13).

## Handover for the next agent — 2026-05-15

> Compiled with concurrence from **Fowler (Engineering)** and **Jony (UI/UX)** before this session ended. Both reviewed the full state below; their refinements are folded in where relevant.

### State as of HEAD

- Latest plan-relevant commits on `origin/main`: `f11c92c` (Phase 4 C2), `5f6735d` (Phase 4 C1), `0fd9816` (Phases 0–3 wiring batch). All pushed.
- Validation evidence at handover time: backend `pytest` 414 passed / 3 skipped; frontend `vitest` 10,230 passed across 40 files; `svelte-check` 0 errors (4 pre-existing a11y warnings — descoped per CLAUDE.md §0); Playwright e2e 15 passed (chromium golden-path + extended-routes + topic-prices).
- Allowlist (`frontend/src/contracts/catalogue-coverage.allowlist.json`) holds **8 entries**: 4 `economy/national_*` + 2 `energy/national_*` country-entity series (all `phase4-pending`, promoted by C3b below); 1 `energy/national_renewable_potential_vs_installed_mw` (paired-bar, deferred to C6); 1 `economy/state_per_capita_nsdp_current_inr` (permanent, superseded by `_long`).

### Fowler one-line summary

> Two structural commits (C1 dispatch extract, C2 facet-label lift) have landed clean with zero behaviour change; the closed-enum dispatch seam exists and is consumed by exactly one branch today, no half-built behaviour is in flight, and C3 is the first commit that will move user-visible pixels.

### Jony one-line summary

> The page is honest about every series it shows, but the macro frame is missing — country-entity series sit unwired on the allowlist, so the citizen reads state detail without ever seeing the national number it ladders up to.

### Immediate next work — Phase 4 C3, **split into C3a (structural) + C3b (behavioural)**

Fowler's mandatory split — a single C3 commit mixes a schema bump, a composer mirror, an enum extension, an allowlist promotion, and a new visual variant; the diff becomes unreviewable and rollback is coarse. Two-hat rule.

#### C3a — STRUCTURAL (zero pixel change; tests prove identity)

Files:

1. `datasets/schemas/catalogue.schema.json` — additive optional `entity_kind?: "country" | "state" | "district" | …` on `CatalogueArtifact`. Bump `x-version` 1.2 → 1.3 + `x-changelog` entry. **Optional, not required** (Fowler): mirroring is enforced by a contract test, not schema requiredness — the `chart_type` mirror precedent applies.
2. `backend/yen_gov/composers/topic_catalogue.py` (or wherever the catalogue is composed) — when emitting an artifact entry whose source indicator JSON has `entity_kind`, mirror it onto the catalogue entry. Re-run `python -m yen_gov coverage` and stage the regenerated `datasets/reference/in/topic-catalogue.json`.
3. `frontend/src/contracts/catalogue-coverage.test.ts` (or a new sibling `catalogue-mirror.test.ts`) — assert: for every catalogue entry that points at an indicator artifact, if the indicator has `entity_kind`, the catalogue entry's mirrored `entity_kind` MUST equal it.
4. `frontend/src/lib/topic-dispatch.ts` — extend `RenderKind` enum with `"national-series"`. Add dispatch rule: `entity_kind === "country"` → `"national-series"`. Add a unit test for the new rule.
5. `frontend/src/routes/TopicLanding.svelte` — **before extending the dispatch**, verify the consumer is shaped as an exhaustive `switch (kind)` with a `default` arm of `kind satisfies never` (Fowler: if it's an `if/else if` chain, the closed-enum safety net doesn't fire — fix the shape as a tiny tidy *before* C3a, not inside it). Then add a `"national-series"` branch that renders the existing `StackedTrendArtifact` with **no variant prop yet** — visually identical to today.

C3a Definition of Done: full test suite green, agent-driven §13 smoke confirms `/t/economy` and `/t/energy` look pixel-identical to before.

#### C3b — BEHAVIOURAL (ships the macro frame)

Files:

1. `frontend/src/lib/StackedTrendArtifact.svelte` — add `variant: "national" | "spatial" = "spatial"` prop. National variant **keeps**: `SeriesBreakAnnotation`, `RebaseBanner`, `SnapshotBadge`, `VintageTooltipLine`. National variant **drops**: `DirectionLegendCue` (n=1, no ranking), comparability banner. National variant **adds**: y-axis unit eyebrow.
   - **Jony refinement**: the unit eyebrow MUST source from `doc.indicator.unit` (the same indicator metadata C2 just lifted into the data layer), NOT a hardcoded literal. Re-introducing a literal here undoes C2's lesson.
   - **Jony hard rule (UX risk)**: when the national series resolves to a single facet (n=1), the renderer MUST bypass the stack reducer and render as a single line (or line + light fill below), NEVER as stacked-against-zero. A "stacked" area collapsed to one facet reads as "parts are hidden" — citizen mistrusts the chart. Same component, gated reduction.
2. `frontend/src/routes/TopicLanding.svelte` — sort `(entity_kind === "country" ? 0 : 1, catalogue_order)` so country-entity sections appear first. Insert a thin horizontal rule + "How states compare" eyebrow between the country block and the first state-entity section. National branch passes `variant="national"` to `StackedTrendArtifact`.
3. `frontend/src/contracts/catalogue-coverage.allowlist.json` — remove the **6 `phase4-pending` country-series** entries (4 economy + 2 energy). Keep the renewable paired-bar entry (deferred to C6) and the permanent `state_per_capita_nsdp_current_inr` entry. The drift detector + the new render branch must be atomic — promoting an allowlist entry without rendering it (or vice versa) is the anti-pattern Fowler called out.
4. `frontend/e2e/golden-path.spec.ts` (or a sibling spec) — add at least one assertion on `/t/economy`: country section renders, contains the unit-eyebrow text from the indicator's `unit`, the "How states compare" separator is present before the state grid, no `pageerror`. Tier-e2e per CLAUDE.md §15.
5. CLAUDE.md §13 smoke on `/t/economy` and `/t/energy` via the agent's browser tools — `read_page` snapshot must show the country section above the state grid with the eyebrow + unit, no new console errors.

C3b Definition of Done: full test suite + new e2e green; allowlist down from 8 → 2 entries; smoke screenshots saved to commit message; `python -m yen_gov coverage` regenerated.

### Out of scope for C3 (do NOT bundle)

- **C6** — paired-bar component for `national_renewable_potential_vs_installed_mw`. Independent renderer; its own commit.
- **Phase 4.1, 4.2, 4.4, 4.5** — vintage tooltip surfacing, quarterly time formatter, IndicatorCache (defer until a page measurably feels slow), snapshot-aware fallback for `IndicatorRanked` / `IndicatorSmallMultiples`.
- **Phase 3.7** — `human_development/state_hdi` IA decision. **Jony recommendation**: migrate to a hero card on `StateOverview.svelte` and drop the dedicated topic. Reason: HDI is one number per state per (rare) vintage — no time slider, no facets, no within-state ranking — it's a chart-shaped object pretending to be a chart. Frees `/t/human_development` for when NFHS / NSO indicators arrive. Bundle this with C3 will pollute the diff with an IA argument; ship it as its own slice.
- **Phase 5** — derived views (own-tax/GSDP, real GSDP YoY, capex share, pension share, per-capita health spend). Settled approach: emit as first-class artifacts under `datasets/indicators/in/derived/`. **Fowler hard rule**: do NOT start Phase 5 before C3b is green and on `main` — derived artifacts will land as new catalogue entries, and adding them on top of a half-migrated dispatch surface means re-touching the same files twice.
- **Phase 6** — new ingests (FC devolution, GST collections, PLFS, MGNREGA, SRS MMR/LE, NAS).

### Anti-patterns the next agent must avoid (Fowler + Jony, distilled)

- **Do NOT land C3 as a single commit.** Split into C3a (structural, visually identical) + C3b (behavioural). Mixing violates the two-hat rule and makes the schema diff unreviewable.
- **Do NOT add `entity_kind` as a third inline condition inside `TopicLanding.svelte`.** Extend `RenderKind` first, let TS complain about the missing case, then add the branch. Inline conditions are the smell C1 was extracted to prevent.
- **Do NOT widen `entity_kind` to required on the catalogue schema** "to make sure people remember to mirror it." Use a contract test that asserts catalogue mirror == indicator source of truth — that's the right enforcement layer per CLAUDE.md §15.
- **Do NOT promote an allowlist entry without wiring its render in the same commit** (and vice versa). The allowlist *is* the ratchet; atomicity is the contract.
- **Do NOT stack-render a single-facet country series.** Single line / line+light-fill only. Stacked-against-zero lies about composition.
- **Do NOT hardcode the y-axis unit string in the national variant.** Source it from `doc.indicator.unit` so we don't re-introduce the literal C2 just lifted out.
- **Do NOT touch Phase 3.7 (`state_hdi` IA) inside C3.** Separate slice.
- **Do NOT start Phase 5 before C3b is green on `main`.**

### Watch-outs / gotchas observed this session (Windows + PowerShell)

- `python -c "<multi-line>"` HANGS the terminal in PowerShell 5.1 — always write a script file under `tools/` and run it. Bulk schema-version bumps are trivial when scripted; the `tools/bump_indicator_schema_1_3_to_1_4.py` from C2 is a template for the next bump.
- `npm run dev | Out-File ../.tmp_dev.log` does not flush on Windows — log file stays empty. For smoke verification, run the Playwright e2e suites instead (they auto-start the dev server) and treat green-e2e as smoke-equivalent for routes the spec covers; for new routes, use the agent's `open_browser_page` + `read_page` tools per CLAUDE.md §13.
- `git log --oneline -10` after a fresh push to `main` may not show your commits in the first 10 lines if there's parallel-work history between HEAD and your commits. Use `git merge-base --is-ancestor <sha> HEAD` to confirm reachability before assuming a commit "didn't land".
- Schema bumps: hand-typed `_schema_version = "x.y"` in production code is forbidden by CLAUDE.md §11 — always go through `yen_gov.core.schema_registry.schema_version("<file>")`. Test fixtures may seed legacy versions on purpose; production emitters may not.

---

## Anti-patterns to avoid (lessons embedded)

- **Big-bang catalogue regen.** Do NOT auto-replace the hand-authored catalogue with the inventory. The drift test (Phase 0) is enough; humans still curate ordering and `featured` bits.
- **Mock-instead-of-fixture.** New component tests must use real artifacts from `datasets/`. Holy Law #7. Only `fetch` may be mocked, in loader unit tests.
- **Mixed-hat commit.** When extracting `formatTimeLabel`, ship structural commit (extract + tests, no behaviour change yet — render still passes raw) then a separate behavioural commit that swaps the year dropdown. Two PRs, two reviews.
- **Skipping the framing tooltip "to ship faster".** The Hans corrective-framing rows in §5d are not nice-to-haves; without them, citizens read crude death rate as Kerala's failure and current-prices PCNSDP as growth. Ship the framing in the same commit as the wiring or revert the wiring.
