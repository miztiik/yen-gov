# Visualization-Layer Gaps — Implementation Plan

**Created**: 2026-05-17
**Authors (audit)**: Jony (UI/UX), Fowler (Engineering), Hans (Governance)
**Source docs**: [`docs/reference/data-coverage-report.md` §6](../docs/reference/data-coverage-report.md#6-frontend-wiring-gaps-visualization-layer), [`docs/reference/data-inventory.md` §1Z](../docs/reference/data-inventory.md)

## Problem in one paragraph

The data layer crossed a threshold around 2026-05-15/16: with NSDP back to FY 1994–95, CPI back to FY 1974–75, and SRS vital rates per state, yen-gov can now sustain *trend* narratives, not just snapshots. The auto-inventory says **43 of 80 indicator artifacts on disk are unreachable from the IA today** — three whole categories (`prices/`, `health/`, `human_development/`) and most of the new RBI Handbook spliced fiscal/economy long-history wedge. Mechanically wiring them now would render, but citizens would see (a) base-year-rebase artifacts with continuous polylines and "+3,400%" headlines, (b) a year dropdown mixing `"2024"` / `"2024-04"` / `"2025-03"` with no labelling, (c) `vintage` silently dropped from RBI splice rows, (d) crude death rate misread as Kerala's "health failure", (e) absolute ₹ Crore for pension expenditure favouring large states. **Tidy first, then wire.**

## Sequencing principle (Tidy First / Beck)

Each phase ships only structural OR behavioural changes per commit, never both. Each phase MUST land its own tests in the same commit (CLAUDE.md §15). Phases 0–2 are blockers for the new wedges; Phase 3 is the wiring (citizen-visible payoff); Phase 4 is the deferred polish that can land alongside.

---

## Phase 0 — Drift detector (Correction Level 2)

**Goal**: make catalogue/disk drift impossible to ship silently. The auto-inventory now prints a wiring summary; CI must fail on regression, not just print it.

- [ ] **`frontend/src/contracts/catalogue-coverage.test.ts`** (new). Glob `datasets/indicators/in/**/*.json`; load `datasets/reference/in/topic-catalogue.json` and collect every `kind:"indicator"` `id`. Assert: every artifact id appears in the catalogue OR in an explicit `frontend/src/contracts/catalogue-coverage.allowlist.json` (with a `reason` per entry). Initially seed the allowlist with the 43 currently-unwired ids so the test passes; each Phase 3 commit removes ids from the allowlist as they get wired.
- [ ] **Wire the test into `npm test`** — already runs by default if it lives under `src/`. Verify red→green by temporarily removing one allowlist entry.

**Risk**: trivial. **Tests first**: by definition.

---

## Phase 1 — Renderer guardrails for the new shapes (Correction Level 2)

**Goal**: extract the small primitives that the prices / health / NSDP-long-history wedges depend on, so the wiring commits in Phase 3 are pure additions.

Land each as a separate commit, structural-then-behavioural. Each lists test-first work and component change.

### 1.1 `formatTimeLabel(time, grain)`

- [ ] Pure helper in [`frontend/src/lib/indicators.ts`](../frontend/src/lib/indicators.ts).
- [ ] Vitest cases: `("2024-04","fiscal_year")→"FY 2024-25"`, `("2024","year")→"2024"`, `("2025-03","date")→"as of Mar 2025"`, `("2024-Q2","quarter")→"Q2 FY25"`.
- [ ] Swap raw `{t}` rendering in `IndicatorRanked.svelte`, `IndicatorChoropleth.svelte` slider tick, `IndicatorSmallMultiples.svelte`. **Without this, a topic page mixing CEA snapshot + ICED FY + SRS CY is visually dishonest.**

### 1.2 `splitOnBreaks(rows, breaks)` + `series_breaks`-aware sparkline

- [ ] Extract pure helper. Vitest: N-1 segments for N break points; segment endpoints inclusive at break-time.
- [ ] [`IndicatorSmallMultiples.svelte`](../frontend/src/lib/IndicatorSmallMultiples.svelte) `pathFor()` emits one `<path>` per segment. Drop the `Math.abs` in `y_max` (let Y include negatives — required by deflation / deficit values).
- [ ] Snapshot test against fixture WPI artifact: 5 segments rendered, no straight line through any rebase tick.

### 1.3 `growthSafeAcross(bars, breaks)` guard in `headline.ts`

- [ ] Pure helper next to [`frontend/src/lib/charts/stacked-trend/headline.ts`](../frontend/src/lib/charts/stacked-trend/headline.ts) `soWhat()`.
- [ ] Vitest: bars spanning a `definition_change` break → `null`; bars spanning a `coverage_change` only → permitted but with a flag; bars wholly within one segment → unchanged behaviour.
- [ ] Wire the guard so headline emits "see notes" when null.

### 1.4 `vintage` round-trip (Correction Level 1, additive type)

- [ ] Add `vintage?: string` to `IndicatorRow` in [`frontend/src/lib/indicators.ts`](../frontend/src/lib/indicators.ts) and to `IndicatorDoc.rows` in [`frontend/src/lib/charts/stacked-trend/adapter-indicator.ts`](../frontend/src/lib/charts/stacked-trend/adapter-indicator.ts). Pure additive — schema v1.3 already ships the field.
- [ ] One vitest asserting an RBI splice fixture round-trips `vintage` through the loader.
- [ ] Tooltip render is a separate commit (Phase 4.1) — Tidy First.

### 1.5 `value_kind: "index"` first-class in StackedTrend

- [ ] Add `"index"` to the StackedTrend `value_kind` zod union in [`adapter-indicator.ts`](../frontend/src/lib/charts/stacked-trend/adapter-indicator.ts) `MAP_VALUE_KIND`.
- [ ] Branch in `headline.ts`: index → never emits `pctDelta` ("change in an index level is misleading without a base-year statement").
- [ ] Vitest: feed a national WPI fixture; assert no `+x%` claim, assert tooltip-friendly base-year text is set.

**Phase 1 verdict gate**: all five primitives green + new tests passing → proceed to Phase 2.

---

## Phase 2 — Honesty primitives in the citizen-facing chrome (Correction Level 2)

Small new components. Ship each with a Svelte testing-library vitest.

- [ ] **`SeriesBreakAnnotation.svelte`** — vertical dashed rule + caret label on any time axis (line, sparkline, year-slider tick). Mandatory before any long-history series wires.
- [ ] **`SnapshotBadge.svelte`** — extracted from `IndicatorChoropleth.svelte`'s stale-chip. Reused by `IndicatorRanked.svelte` and `IndicatorSmallMultiples.svelte` so a CEA single-month artifact is consistently flagged.
- [ ] **`DirectionLegendCue`** — one-word verbal tag in legend ("lower is better", "neutral · darker = higher", "higher is better"). One Tailwind utility, ~5 lines. Eliminates the colour-only signalling smell flagged by Jony for IMR (orange ramp) + CPI (blue neutral).
- [ ] **`VintageTooltipLine`** — addition to [`ChartTooltip.svelte`](../frontend/src/lib/ChartTooltip.svelte) showing per-row `vintage` ("Base 2011-12", "First Advance Estimates"). Depends on Phase 1.4.
- [ ] **`RebaseBanner.svelte`** — small amber strip on `IndicatorChoropleth.svelte` when the year slider lands on or past a `series_breaks` boundary. "Base-year change at YYYY; values not directly comparable to earlier slider positions."

**E2E gate**: extend [`frontend/e2e/golden-path.spec.ts`](../frontend/e2e/golden-path.spec.ts) (or a sibling) with one route that exercises a long-history artifact; assert (a) page-error-clean, (b) at least one `[data-series-break]` element rendered, (c) `[data-vintage]` text present in tooltip on hover.

---

## Phase 3 — Wire the new wedges (Correction Level 2 per topic; pure additive)

Each topic is one PR. The Phase 0 catalogue-coverage test fails on each PR until the wiring lands; the same PR also removes the corresponding allowlist entries.

### 3.1 Topic: `prices` (Prices & Inflation)

- [ ] Add `prices` topic to `datasets/reference/in/topic-catalogue.json` (between `fiscal` and `economy`). `direction: "neutral"` throughout. Featured.
- [ ] Wire 4 state CPI sub-index inflation rates (`state_cpi_general_inflation_pct` featured; food / fuel / housing-urban siblings unfeatured).
- [ ] Wire 3 national index series (`national_cpi_combined_index_annual` featured; `national_cpi_iw_index_annual` + `national_wpi_all_commodities_index_annual` unfeatured). All three carry `series_breaks`.
- [ ] Catalogue-coverage allowlist: remove the 7 prices ids.
- [ ] First-render sentence on the topic page (Hans wording): *"Inflation in your state vs the RBI's 4% medium-term target — neither high nor low is automatically good; food / fuel are largely set by national / global conditions."*
- [ ] Footnote on `state_cpi_housing_urban_inflation_pct`: *"Urban-only by NSO methodology — no rural housing component is collected."*

### 3.2 Topic: `health` (Vital statistics & health)

- [ ] Add `health` topic. List `state`. Featured.
- [ ] Wire IMR (featured, `direction: lower_is_better`); birth rate / death rate / TFR (`direction: neutral`); public health expenditure (input, `neutral`).
- [ ] Catalogue-coverage allowlist: remove the 5 health ids.
- [ ] **Per-artifact framing tooltips (mandatory, not optional)** — these are the corrective-framing rows from `data-coverage-report.md` §5d. Specifically:
  - Crude Death Rate: *"Not age-adjusted — older states (Kerala, TN, Punjab) read structurally higher. Read alongside IMR."*
  - Birth rate: *"Falls naturally as a population ages; below ~21 = at or near replacement fertility."*
  - TFR: *"Replacement-level is 2.1; India crossed below replacement around 2020."*
  - Public health expenditure: *"Spending is an input — pair with IMR / Life Expectancy. FY24/FY25 are RE / BE."* Default render must be per-capita (₹/person), NOT absolute ₹ Crore.

### 3.3 Topic: `transport` (Mobility)

- [ ] Add `transport` topic. Not featured initially (only 2 artifacts).
- [ ] Wire EV registrations + EV-share.
- [ ] Catalogue-coverage allowlist: remove the 2 transport ids.

### 3.4 Extend `economy`

- [ ] Wire 4 RBI-spliced state NSDP / per-capita-NSDP siblings. Mark `state_per_capita_nsdp_constant_inr_long` featured (long-history hero). Each renders with `SeriesBreakAnnotation` and `RebaseBanner` automatically (Phase 2). Per-row `vintage` in tooltip (Phase 1.4 + 4.1).
- [ ] Wire 4 `national_*` aggregates (GDP / GVA / quarterly GVA / macro aggregates).
- [ ] **Mandatory framing on `state_per_capita_nsdp_current_inr*`**: *"Current prices include inflation. For real change, switch to constant prices."* Default toggle should be constant.
- [ ] Telangana per-row badge: *"Pre-FY15 back-projected from undivided AP."* J&K per-row badge: *"Post-FY20 covers UT-only J&K."*
- [ ] Catalogue-coverage allowlist: remove the 8 economy ids.

### 3.5 Extend `fiscal`

- [ ] Wire 7 RBI per-state long-history series (`state_external_debt_inr_crore`, `state_grants_in_aid_inr_crore`, `state_non_tax_revenue_inr_crore`, `state_own_tax_revenue_inr_crore`, `state_pension_expenditure_inr_crore`, `state_revenue_expenditure_inr_crore`, `state_share_central_taxes_inr_crore`).
- [ ] Promote `state_pension_expenditure_inr_crore` to **featured** (OPS political salience). Default render: % of state revenue receipts (derived view — see Phase 5), not absolute ₹ Crore.
- [ ] Catalogue-coverage allowlist: remove the 7 fiscal ids.

### 3.6 Extend `energy`

- [ ] Wire `state_per_capita_electricity_consumption_kwh` as featured.
- [ ] Wire 7 other per-state cuts unfeatured (RBI Handbook duplicates of ICED series; keep them addressable for power users).
- [ ] Catalogue-coverage allowlist: remove the 8 energy ids.

### 3.7 `human_development/state_hdi` — pinned card on `StateOverview`

- [ ] Surface as a single hero stat on [`StateOverview.svelte`](../frontend/src/routes/StateOverview.svelte), not a dedicated topic.
- [ ] Tooltip: producer + methodology vintage (HDI is composite — UNDP 2010 / 2014 / 2020 weightings differ).
- [ ] Catalogue-coverage allowlist: remove the human_development id.

**Phase 3 done = allowlist is empty + `npm test` and `npm run test:e2e` green + agent-driven smoke per CLAUDE.md §13 on `/t/prices`, `/t/health`, one updated state hub.**

---

## Phase 4 — Deferred polish (Correction Level 1–2; non-blocking)

These can land alongside Phase 3 commits or in a follow-up sweep.

- [ ] **4.1** Tooltip surfaces `vintage` (depends on Phase 1.4).
- [ ] **4.2** Quarterly time formatter — `national_gva_by_industry_quarterly_constant_2011_12_inr_crore` slider ticks.
- [ ] **4.3** Move `category_labels` for `installed_capacity_by_source_mw` out of `TopicLanding.svelte` into the indicator artifact's `notes` / `facet_labels`.
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

## Anti-patterns to avoid (lessons embedded)

- **Big-bang catalogue regen.** Do NOT auto-replace the hand-authored catalogue with the inventory. The drift test (Phase 0) is enough; humans still curate ordering and `featured` bits.
- **Mock-instead-of-fixture.** New component tests must use real artifacts from `datasets/`. Holy Law #7. Only `fetch` may be mocked, in loader unit tests.
- **Mixed-hat commit.** When extracting `formatTimeLabel`, ship structural commit (extract + tests, no behaviour change yet — render still passes raw) then a separate behavioural commit that swaps the year dropdown. Two PRs, two reviews.
- **Skipping the framing tooltip "to ship faster".** The Hans corrective-framing rows in §5d are not nice-to-haves; without them, citizens read crude death rate as Kerala's failure and current-prices PCNSDP as growth. Ship the framing in the same commit as the wiring or revert the wiring.
