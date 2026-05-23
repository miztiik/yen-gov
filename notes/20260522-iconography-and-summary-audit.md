# Iconography and chart-summary audit — Phase 1.25

**Date**: 2026-05-22
**Plan**: [TODO/20260518-frontend-charting-modernisation-plan.md](../TODO/20260518-frontend-charting-modernisation-plan.md) — Phase 1.25
**Scope**: read-only enumeration; informs Phase 1.3a (icon foundation) and Phase 2.x (StackedTrend v2 readouts).
**Audit sources pinned per R-23**: authoring JSON only, not compiled Parquet.

## 1. Registry baseline — [`frontend/src/lib/IndicatorIcon.svelte`](../frontend/src/lib/IndicatorIcon.svelte)

11 entries, inline Lucide-style SVG paths:

`zap`, `heart`, `graduation-cap`, `coins`, `trending-up`, `users`, `droplets`, `stethoscope`, `landmark`, `scale`, `factory`.

Unknown ids fall through to a `FALLBACK` circle silently — the failure mode is invisible to citizens until 1.3a's strict-build-time inventory replaces it.

## 2. Topic icons — [`datasets/taxonomy/topics.json`](../datasets/taxonomy/topics.json)

10 references, 8 distinct ids:

| Icon id | Topics using it | In registry? |
|---|---|---|
| `landmark` | `governance` | ✅ |
| `zap` | `energy` | ✅ |
| `vote` | `elections` | ❌ MISSING |
| `trending-up` | `economy`, `fiscal` | ✅ but semantically weak (§4) |
| `users` | `population`, `governments` | ✅ |
| `cloud` | `air-quality` | ❌ MISSING |
| `car` | `transport` | ❌ MISSING |
| `heart-pulse` | `health` | ❌ MISSING |

**Topics-only missing-from-registry**: `vote`, `cloud`, `car`, `heart-pulse` (4 ids).

## 3. Indicator icons — current vs canonical home

### 3.1 Canonical home today

[`datasets/taxonomy/indicators.json`](../datasets/taxonomy/indicators.json) — the catalogue T.3 of the canonical pivot compiles to `taxonomy/indicators.parquet` — has **zero `icon` fields** as of 2026-05-22. The schema `datasets/schemas/indicator-catalogue.schema.json` does not yet expose an `icon` property.

### 3.2 Where indicator icons actually live (dying per T.3)

[`datasets/indicators/in/**/*.json`](../datasets/indicators/in/) — the folded indicator tree slated for deletion under T.3 — carries **110 `icon` references across 29 distinct ids**:

| Icon id | Usage count | In registry? |
|---|---:|---|
| `trending-up` | 28 | ✅ but semantically weak (§4) |
| `zap` | 13 | ✅ |
| `landmark` | 13 | ✅ |
| `trending-down` | 10 | ❌ MISSING and semantically weak (§4) |
| `flame` | 5 | ❌ MISSING |
| `sun` | 4 | ❌ MISSING |
| `users` | 4 | ✅ |
| `wind` | 4 | ❌ MISSING |
| `activity` | 3 | ❌ MISSING |
| `cloud` | 3 | ❌ MISSING |
| `bolt` | 2 | ❌ MISSING (likely intended as `zap`) |
| `car` | 2 | ❌ MISSING |
| `bar-chart` | 2 | ❌ MISSING |
| `factory` | 2 | ✅ |
| `shopping-cart` | 1 | ❌ MISSING |
| `dollar-sign` | 1 | ❌ MISSING (avoid for INR series) |
| `fuel` | 1 | ❌ MISSING |
| `heart-pulse` | 1 | ❌ MISSING |
| `globe` | 1 | ❌ MISSING |
| `shopping-bag` | 1 | ❌ MISSING |
| `plug` | 1 | ❌ MISSING |
| `droplet` | 1 | ❌ MISSING — naming mismatch with registry's `droplets` |
| `trash-2` | 1 | ❌ MISSING |
| `atom` | 1 | ❌ MISSING |
| `leaf` | 1 | ❌ MISSING |
| `credit-card` | 1 | ❌ MISSING |
| `construction` | 1 | ❌ MISSING |
| `package` | 1 | ❌ MISSING |
| `file-text` | 1 | ❌ MISSING |

**Folded-tree missing-from-registry**: 24 distinct ids (excluding the 5 already in registry).

### 3.3 Reconciliation with plan §1.3a expectation

Phase 1.3a lists 24 Lucide SVGs to add as the foundation commit's icon set:

`car`, `heart-pulse`, `wind`, `cloud`, `vote`, `flame`, `sun`, `atom`, `leaf`, `globe`, `shopping-bag`, `bar-chart`, `construction`, `trash-2`, `credit-card`, `file-text`, `plug`, `fuel`, `package`, `activity`, `download`, `rotate-ccw`, `maximize`, `zoom-in`.

This audit confirms 20 of those 24 are referenced by the taxonomy authoring surfaces today (`download`, `rotate-ccw`, `maximize`, `zoom-in` are chart-action chrome with no catalogue reference yet — included in 1.3a for footer-action work in Phase 1.4).

**Discoveries the 2026-05-19 Jony audit did not list** (4 ids; 1.3a should adopt):

- `trending-down` (10 usages — fiscal deficits, T&D losses)
- `bolt` (2 usages — appears to duplicate `zap`; either remove from data or alias in registry)
- `shopping-cart` (1 usage)
- `dollar-sign` (1 usage — recommend remove from data; INR series should not display USD glyph; replace with `coins` or `landmark`)

**Authoring-source mismatch** (1 id):

- `droplet` (singular) in folded tree vs `droplets` (plural) in registry. 1.3a must pick one explicitly — either alias `droplet → droplets.svg` in the build plugin or rename the data side.

## 4. Semantically weak icon choices

Per the plan's explicit guidance: generic `trending-up` / `trending-down` carry directional rhetoric and should not stand in for category nouns.

### 4.1 `trending-up` overload (28 indicators across 7 unrelated domains)

| Domain | Indicator examples | Better icon |
|---|---|---|
| GDP / GVA | `india_gdp_inr_crore`, `state_gdp_inr_crore`, `national_gva_by_industry_constant_inr_crore` | `coins` or new `bar-chart` |
| Per-capita income | `state_per_capita_nsdp_current_inr` (4 variants) | `coins` |
| Pensions | `state_pension_expenditure_inr_crore` | `credit-card` |
| Vital rates | `state_birth_rate_per_1000`, `state_death_rate_per_1000`, `state_infant_mortality_rate_per_1000`, `state_total_fertility_rate` | `users` or `heart-pulse` |
| Health expenditure | `state_public_health_expenditure_inr_crore` | `stethoscope` or `heart-pulse` |
| Price indices | `national_cpi_combined_index_annual`, `national_cpi_iw_index_annual`, `national_wpi_all_commodities_index_annual` | `shopping-cart` |
| CPI sub-inflation | `state_cpi_food_inflation_pct`, `state_cpi_fuel_inflation_pct`, `state_cpi_general_inflation_pct`, `state_cpi_housing_urban_inflation_pct` | `shopping-cart` (food, general), `fuel` (fuel), `landmark` (housing) |

**Reading**: `trending-up` is functioning as "this indicator goes up over time" — that's a chart shape, not a category. It also implies improvement, which is wrong for birth rate, IMR, CPI inflation, and arguably for nominal GDP without a denominator.

### 4.2 `trending-down` overload (10 indicators)

| Domain | Indicators | Better icon |
|---|---|---|
| Distribution losses | `state_atc_losses_pct`, `state_distribution_td_loss_pct` | `plug` or `zap` |
| Fiscal deficits | `states_combined_gross_fiscal_deficit`, `states_combined_primary_deficit`, `states_combined_primary_revenue_deficit`, `states_combined_revenue_deficit`, `union_gross_fiscal_deficit`, `union_primary_deficit`, `union_primary_revenue_deficit`, `union_revenue_deficit` | `landmark` (governance) or `coins` (money) |

**Reading**: `trending-down` for deficits encodes "deficit is bad and falling" — but a *rising* deficit indicator with a `trending-down` icon is internally contradictory chrome. The icon must be a category noun, not a direction.

## 5. Chart-summary surfaces — current claims-vs-evidence gaps

Read-only scan of summary-rendering call sites:

| Surface | File | Claim risk |
|---|---|---|
| `IndicatorChoropleth` legend/honesty banner | [`frontend/src/lib/IndicatorChoropleth.svelte`](../frontend/src/lib/IndicatorChoropleth.svelte) | Honesty chrome already present; coverage caption is mature. **Low risk.** |
| `IndicatorRanked` peer/median/rank text | [`frontend/src/lib/IndicatorRanked.svelte`](../frontend/src/lib/IndicatorRanked.svelte) | Rank-claim text does not consult `comparability` annotation; may rank across delimitation breaks. **Medium risk** — see R-04 entity-comparability work. |
| `IndicatorSmallMultiples` panel captions | [`frontend/src/lib/IndicatorSmallMultiples.svelte`](../frontend/src/lib/IndicatorSmallMultiples.svelte) | Single sparkline stroke; no median/peer baseline; no missing-segment hatch. **Low semantic risk; high "lifeless" risk** per plan finding #8. |
| `StackedTrend` readout | [`frontend/src/lib/charts/StackedTrend.svelte`](../frontend/src/lib/charts/StackedTrend.svelte) | Relies on native `title` tooltip; no pinned readout; mode toggle is a passive label. Phase 2.1–2.3 addresses. |
| Topic landing intro copy | [`frontend/src/routes/TopicLanding.svelte`](../frontend/src/routes/TopicLanding.svelte) | Static editorial; no generated summary today. Out of scope for Phase 1.25. |

Causal-verb / incumbent-attribution audit (R-14): no current generated summary uses banned verbs (`delivered`, `presided over`, `swept`, `dominated`, `crushed`). The risk is forward-looking — Phase 3.6 election composition summaries will be the first surface where the policy actively constrains template authoring.

## 6. Recommended Phase 1.3 surface slice

The plan asks for a decision: topic index, indicator cards, or chart headers first?

**Recommendation: topic index `/t` (sub-phase 1.3b).** Rationale:

- 8 distinct icons cover the entire topic landing surface (small blast radius).
- 4 of the 8 are missing today (`vote`, `cloud`, `car`, `heart-pulse`); the silent fallback is rendering a generic circle for half of all topics right now — a real citizen-visible bug.
- Lands visual identity at the site's front door before deeper renderers inherit it.
- Decouples from the dying folded indicator tree; pinned only to `taxonomy/topics.json`, which is canonical.

Sub-phases 1.3c–1.3f follow the order in the plan unchanged.

## 7. Inputs for Phase 1.3a foundation commit

Concrete list the next agent can copy into the 1.3a SVG drop:

**Already-in-registry, port as-is**: `zap`, `heart`, `graduation-cap`, `coins`, `trending-up`, `users`, `droplets`, `stethoscope`, `landmark`, `scale`, `factory` (11 files).

**Missing-but-referenced, add from Lucide ISC source**: `vote`, `cloud`, `car`, `heart-pulse`, `trending-down`, `flame`, `sun`, `wind`, `activity`, `bar-chart`, `shopping-cart`, `fuel`, `globe`, `shopping-bag`, `plug`, `trash-2`, `atom`, `leaf`, `credit-card`, `construction`, `package`, `file-text` (22 files).

**Chrome / footer-action icons for Phase 1.4 wiring**: `download`, `rotate-ccw`, `maximize`, `zoom-in` (4 files).

**Action items the audit surfaces but does NOT itself fix** (deferred to follow-up data-side PRs, separate from the chart plan):

1. Strip the `dollar-sign` reference from `national_*_usd_*.json` (or wherever it lives) — INR data should not carry a USD glyph.
2. Decide on `bolt` (2 usages): either remove from data (alias-via-build is not the right fix for a typo) or document as intentional with a distinct stroke.
3. Rename `droplet` (1 usage) → `droplets` in the data side to match the registry's plural.
4. **Critical**: design a non-directional icon migration plan for the 38 `trending-up` / `trending-down` indicators before Phase 1.3e mounts indicator-icon chrome on chart headers — otherwise the chart-header icons will silently encode "good/bad" claims on indicators where the direction is contested or wrong.

## 8. Pivot interlock (R-23 / R-25 four-facts)

For the four-facts block: this audit consumes only authoring sources.

- **Pivot status**: T.3 (`b051b9f6`, PR #98 stacked on `feat/p1-energy-pivot`) is IN-FLIGHT and adds `datasets/taxonomy/indicators.parquet` compiled from `indicators.json`. T.3 does not yet add the `icon` field to the catalogue schema — that's a follow-up data-side PR (see §7 item 4 above).
- **Authoring source**: `datasets/taxonomy/topics.json` (✅ today) and `datasets/taxonomy/indicators.json` (✅ today, no `icon` field yet) per the Taxonomy authoring contract table in the plan.
- **Manifest `table_id`**: n/a — this audit reads JSON authoring sources, not Parquet at runtime.
- **Deletion condition**: n/a — no bridge introduced.

## 9. Out of scope for this audit

- Schema bump to add `icon` to `indicator-catalogue.schema.json` (data-side PR, requires R-25 coordination with master agent's T.3).
- Migration of the 110 folded-tree `icon` values into the catalogue (data-side PR, blocks on T.3 landing).
- Phase 1.3a code (separate PR — this audit is the input).
- Phase 2.x StackedTrend readout work (separate PR per Phase 2 commit-boundary discipline).

— end of audit —
