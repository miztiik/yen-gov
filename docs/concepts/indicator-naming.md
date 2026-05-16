# Indicator naming — id slugs, titles, descriptions, facet labels

**Last Updated**: 2026-05-15

## 1. Why this doc exists

Two ingests are about to fire in parallel — ICED NO2/SO2/PM10 ([TODO/20260515-iced-aq-no2-so2-pm10-handover.md](../../TODO/20260515-iced-aq-no2-so2-pm10-handover.md)) and RBI Statement 27 health-expenditure share ([TODO/20260515-health-ingest-handover.md](../../TODO/20260515-health-ingest-handover.md)) — and the existing `datasets/indicators/in/` corpus is internally inconsistent on slug shape (`india_*` vs `national_*` vs no scope; unit suffix sometimes present sometimes not; entity-prefix sometimes leading sometimes trailing). Without a written convention these two ingests will mint ids in different shapes and the next agent will pay for it with a renaming PR that touches the catalogue, the frontend routes, and every consumer test.

This doc is the convention. It is binding for new ids; existing ids that violate it are listed in §8 and are NOT migrated by this commit. The schema (`datasets/schemas/indicator.schema.json`, currently at `x-version: 1.5`) already locks the regex; this doc locks what humans should put inside it.

Per [ADR-0022](../architecture/decisions/0022-place-first-ia-with-topic-catalogue.md): topic membership lives on `datasets/reference/in/topic-catalogue.json`, NOT on the indicator artifact. This doc does not re-open that decision. It only RECOMMENDS that the `<scope>` segment of the id match a catalogue topic-id, as a navigation aid for grep — a soft convention, not a schema-enforced field.

**Schema v1.5 (2026-05-15) is the binding floor for new artifacts.** New ingests MUST author against v1.5 (Hans's 4-level `comparability` ladder, the `denominator` object form, `revision_tier_by_period`, `excludes`, `renderer_rules`). The 4 dissents this doc surfaced in its v1 draft are pinned in §9.

## 2. The `indicator.id` slug — anatomy and rules

### 2.1 The regex (locked, do not change)

```
^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*$
```

Lowercase, snake_case, single `/` separator (NOT `.`). Already enforced by `datasets/schemas/indicator.schema.json`.

### 2.2 Mandatory shape

```
<scope>/<entity_prefix>_<noun>_<aggregate?>_<unit?>
```

- **`<scope>`** — exactly one segment. By convention, MUST be a topic-id from `datasets/reference/in/topic-catalogue.json` (`fiscal`, `energy`, `environment`, `health`, `economy`, `prices`, `demography`, `transport`, `elections`, `human_development`, …). The catalogue is the source of truth for the legal set; this doc deliberately does not enumerate them. Adding a new scope means adding a topic to the catalogue first.
- **`<entity_prefix>`** — `national_`, `state_`, `district_`, `constituency_`, `city_`, `ward_`. **Mandatory** for state-and-below; **mandatory** for national/all-India aggregates too (use `national_`, NOT `india_`). Spatial scope is part of the indicator's identity, not just metadata — Hans's rule: "two artifacts measuring the same noun at different geographies are different facts."
- **`<noun>`** — what is being measured. Snake_case. Use the most specific concrete noun that survives across vintages (`outstanding_debt`, `birth_rate`, `installed_capacity`, `pm25_annual_mean`, `health_expenditure_share`).
- **`<aggregate>`** (optional) — the verb of aggregation when the noun does not already imply it. Canonical vocabulary, ban synonyms:

  | Use | Not |
  | --- | --- |
  | `mean` | `average`, `avg` |
  | `share` | `pct_of_total`, `proportion`, `fraction` |
  | `count` | `total`, `num`, `n` |
  | `rate` | `frequency` |
  | `ratio` | (use `ratio` only for true unit-less ratios; otherwise `share`) |
  | `index` | `idx` |

  Omit when the noun already names the aggregate (`birth_rate`, `gini_coefficient`, `unemployment_rate`).
- **`<unit>`** (optional) — see §2.3.

### 2.3 Unit suffix policy

Unit suffix is **mandatory** when the same noun could plausibly be expressed in multiple units, OR when the unit changes the citizen reading. Canonical suffixes:

| Suffix | Meaning |
| --- | --- |
| `_pct` | percentage (0–100) |
| `_pct_<denominator>` | percentage WITH denominator visible (`_pct_gsdp`, `_pct_total_expenditure`) — preferred over bare `_pct` for any share that needs Hans's denominator-visibility test |
| `_per_1000` | rate per 1,000 |
| `_per_lakh_population` | rate per 100,000 (Indian convention; do not use `_per_100k`) |
| `_per_100000_live_births` | MMR convention — spell out the denominator base |
| `_inr_crore`, `_inr_lakh_crore`, `_inr` | currency, with magnitude unit |
| `_mw`, `_gw`, `_mwh`, `_gwh` | electricity capacity / energy |
| `_ug_m3` | concentration (µg/m³) |
| `_mtco2`, `_mtco2e`, `_ggco2e` | greenhouse-gas mass |
| `_years` | duration in years |
| `_count` | dimensioned count where the noun could otherwise read as a rate |

**Omit** the unit suffix only when the indicator is genuinely dimensionless (`state_hdi`, `state_total_fertility_rate` — TFR is children-per-woman by definition; the noun encodes it). When in doubt, include the suffix — Max's rule: an explicit unit in the slug saves the next reader a click into the schema.

### 2.4 When to include `state_` / `district_` / `national_`

Always, for spatial-aware indicators. There is no "default geography" — `outstanding_debt_pct_gsdp` vs `state_outstanding_debt_pct_gsdp` are two different indicators (the first reads as union/all-India debt, the second as per-state). Where the existing corpus omits the prefix (`fiscal/outstanding_debt_pct_gsdp`, `fiscal/states_combined_*`), it is exploiting context-from-filename — that's a fragile pattern and §8 lists it as an anti-pattern to migrate later.

For the two pending ingests this means:

- ICED AQ → `environment/state_no2_annual_mean_ug_m3`, `environment/state_so2_annual_mean_ug_m3`, `environment/state_pm10_annual_mean_ug_m3` (already what the handoff specifies — this doc ratifies it).
- RBI Statement 27 → `health/state_health_expenditure_share_of_total_expenditure_pct` (already what the handoff specifies, but see §5: title/description rules and §3: Hans's denominator-visibility nudge — consider `health/state_health_expenditure_pct_total_expenditure` as the slug, with the denominator visible per §2.3).

### 2.5 Length budget

Soft cap **60 characters** for the full id including scope and slash. The longest existing id (`economy/national_gva_by_industry_quarterly_constant_2011_12_inr_crore`, 67 chars) violates this and is listed in §8. When the id wants to grow past 60 chars, the usual cause is methodology metadata sneaking in (`constant_2011_12`); pull it out into `methodology_vintage` and let `series_breaks` carry the rebase, per §3.

## 3. Hans's lens — what naming MUST encode for honest framing

Hans (Governance Strategist, channelling Rosling/Roy/Bhattacharya) reads every id as a citizen-facing claim. His non-negotiables:

1. **Denominator visibility.** A bare `_pct` hides what the percentage is OF. `outstanding_debt_pct_gsdp` is honest; `outstanding_debt_pct` is a leaderboard waiting to mislead. If the denominator matters for cross-state comparison — and it almost always does — name it. This is why the Statement 27 indicator MUST be `health/state_health_expenditure_pct_total_expenditure` (pinned in §9 dissent #1), not `..._share_of_total_expenditure_pct`. Schema v1.5 additionally lets the artifact carry a structured `indicator.denominator = {what, price_basis, base_year, source_artifact}` object — populate it; the id names the denominator, the field defines it.
2. **Comparability disclaimers stay OUT of the id.** `state_pm25_annual_mean_ug_m3_uneven_network` would be wrong. The id is the noun; the `comparability` enum + `notes` field carries the disclaimer. The id stays stable as the network improves.
3. **Methodology-break-prone series — id stays stable across vintages.** Rebases (GSDP `2011-12` → `2017-18` when MoSPI eventually rebases), sampling-frame changes (NFHS-5 → NFHS-6), and definition shifts go in `methodology_vintage` and `series_breaks`, NOT in the id. The current `economy/india_iip_index_2011_12` (and the long `economy/national_gva_..._constant_2011_12_inr_crore`) violate this — the base year is methodology vintage, not identity. They are §8 anti-patterns.
4. **Statement 27 vs HBS Table 18 crosswalk.** Per the health handoff, these two RBI tables both purport to measure state health spending but use different definitions (Statement 27 = budget share; Table 18 = absolute crore, possibly different scope). They are two indicators, not one. Naming them so the difference is visible from the slug alone — `state_health_expenditure_pct_total_expenditure` (Statement 27) vs `state_public_health_expenditure_inr_crore` (Table 18, already on disk) — is what lets the citizen tell them apart in `/t/health` without reading the schema.
5. **Urban-biased CPCB monitor network (PM2.5/NO2/SO2/PM10).** The ICED AQ indicators MUST carry `comparability: directional_only` (v1.5 4-level ladder; replaces the v1.4 `not_comparable_across_states` token, which is still accepted but deprecated) and the chart MUST refuse to render a ranked table. The id stays clean; the field carries the warning. New artifacts SHOULD also populate `renderer_rules: ["no_rank_table", "no_growth_across_break"]` where appropriate.

## 4. Max's lens — comparability and OWID-style scout discipline

Max (Indicator Scout, channelling Roser/Ritchie) reads every id as a candidate for a cross-state ranked table. His non-negotiables:

1. **Refuse leaderboard-trap nouns.** An id like `state_environment_quality_index` collapses many incommensurate things into one number for a leaderboard — Max refuses it. `state_pm25_annual_mean_ug_m3` is honest because the noun is one measurable thing with one unit; the comparability flag tells the renderer not to rank.
2. **Same id across decades; document the break, don't rename.** Rosling's instinct: if the noun is the same noun (PM2.5 mean), the id is the same id, even if the monitor count tripled in 2018. Rename ONLY when the noun itself changed (`crude_birth_rate` → `age_adjusted_birth_rate` is a new id; `birth_rate` measured by SRS in 2010 vs SRS in 2024 is the same id with a `series_break` if the frame changed).
3. **Source authority does NOT belong in the id.** `rbi_outstanding_debt_pct_gsdp` is wrong (the upstream changes; the fact does not). `fiscal/state_outstanding_debt_pct_gsdp` is right. Provenance lives in the `sources` array (§9 of CLAUDE.md / [ADR-0002](../architecture/decisions/0002-provenance-as-sources-list.md)). The id is the citizen's noun, not the bureaucracy's catalogue number.
4. **Long-arc series get one id.** When an indicator is meant to live across a 30-year window (debt-to-GSDP, birth rate), the id should be writable in 1995 and still be the same in 2025. Methodology vintage is what changes; the id is the through-line.

## 5. `indicator.title` and `indicator.description` — citizen-readable copy rules

### 5.1 Title

- **Sentence case**, not Title Case. `"Outstanding liabilities (% of GSDP)"` not `"Outstanding Liabilities (% Of GSDP)"`. The current corpus is split — `"Crude Birth Rate"` (Title Case) vs `"Installed coal-fired capacity"` (sentence). New ids use sentence case; old ones are §8.
- **English only.** No Hindi/English mixing in title. Bilingual surfaces are a future ticket; today's frontend renders English.
- **Unit in parens at the end**: `"PM2.5 annual mean (µg/m³)"`, `"Outstanding liabilities (% of GSDP)"`, `"Crude birth rate (per 1,000 population)"`.
- **≤ 60 characters** (legend space).
- **No direction-of-good in the title.** `"Air pollution — lower is better"` is wrong. The `direction` field carries that; the title stays neutral.
- **No methodology in the title.** `"State outstanding liabilities (% of GSDP, RBI State Finances 2024)"` is wrong. Source goes in `sources`, vintage in `methodology_vintage`.

### 5.2 Description

- **1–3 sentences.** What the number measures, plus one honesty caveat.
- **NOT a methodology essay.** That belongs in `notes`. The description is the elevator pitch a citizen reads under the chart.
- One sentence pattern that works across the corpus: `<what it measures>. <how it's typically read>. <one caveat>.`

  > "Annual mean concentration of fine particulate matter (PM2.5) recorded by CPCB monitors in each state. Lower readings indicate cleaner air. The monitor network is dense in metros and sparse elsewhere — state means are best read as a metro signal, not a uniform-coverage average."

### 5.3 What goes where (cheat sheet)

| Information | Field |
| --- | --- |
| Citizen noun | `title` |
| Unit display | `title` (in parens) AND `unit` |
| One-paragraph definition | `description` |
| Denominator definition (for shares) | `indicator.denominator` object form (v1.5) — the id names it, this field defines it |
| Methodology, vintage, sampling frame | `notes` + `methodology_vintage` |
| Per-period revision tier (FY 2024-25 = RE vs 2025-26 = BE) | `revision_tier_by_period[]` (v1.5) |
| What is NOT counted (citizen-facing exclusions) | `excludes[]` (v1.5) |
| Render-engine constraints | `renderer_rules[]` (v1.5 controlled vocabulary) |
| "Lower is better" | `direction` (NEVER title) |
| "Don't rank states by this" | `comparability` (v1.5 4-level ladder; NEVER title) |
| Source URL | `sources[]` (NEVER id, NEVER title) |
| Topic membership | `topic-catalogue.json` (NEVER on artifact, per ADR-0022) |

## 6. Facet and dimension labels

Facetted indicators (`chart_type: stacked-trend`, `rows[].facet` populated) declare their human-readable label per facet value via `indicator.facet_labels` (schema v1.4). Same casing rules as titles: sentence case, English, no methodology.

Per the v1.4 changelog entry on `indicator.schema.json`, the composer is the source of truth for these labels — the frontend stops carrying topic-level hardcoded literals. This doc does not re-derive that decision; see the schema's changelog and Phase 4 C2 of [TODO/VIZ-LAYER-GAPS-PLAN.md](../../TODO/VIZ-LAYER-GAPS-PLAN.md).

Example (correct):

```json
"facet_labels": {
  "coal": "Coal",
  "gas": "Gas",
  "hydro": "Hydro",
  "solar": "Solar",
  "wind": "Wind",
  "nuclear": "Nuclear",
  "other_thermal": "Other thermal"
}
```

## 7. Migration / rename policy

Renaming an `indicator.id` after publish is a **CLAUDE.md §6 Level-3 minimum** change: the id flows into `topic-catalogue.json` artifact references, the frontend route generation, every consumer contract test, and any external citation. Treat it that way.

Runbook (one paragraph; promote to a `docs/how-to/` runbook if/when used):

> *Expand → migrate → contract.* (Beck/Fowler/Sadalage's schema-evolution discipline applied to ids.) Step 1 (expand): rename the file under `datasets/indicators/in/<scope>/`, ship the new id alongside an alias entry in the catalogue (the catalogue's renderer follows aliases for one release). Step 2 (migrate): update the frontend's known references and contract tests to the new id; verify the route still resolves via the alias. Step 3 (contract): in the next release, drop the alias from the catalogue. Each step is its own commit. NEVER mix the rename with a behaviour change in the same commit (Beck's two-hat rule).

If no alias mechanism exists in the catalogue today, that's a TODO — flag it on the migration ticket; until then, id renames after publish require a coordinated multi-file commit and the citizen sees a brief 404 window. Don't rename ids casually.

## 8. Anti-patterns (existing-corpus examples — do NOT migrate in this commit)

These ids exist on disk and ship today. Listing them honestly so future agents know the convention is aspirational, not retroactive:

1. **`energy/installed_mw_by_state`** ([datasets/indicators/in/energy/installed_mw_by_state.json](../../datasets/indicators/in/energy/installed_mw_by_state.json)) — entity-prefix at the END (`_by_state`), unit (`mw`) buried in the middle, no aggregate verb. Per §2.2 should be `energy/state_installed_capacity_mw`.
2. **`economy/india_*` vs `economy/national_*` collision** — `economy/india_gdp_inr_crore`, `economy/india_iip_index_2011_12`, `economy/india_external_balance_inr_crore`, `economy/india_gva_by_industry_constant_inr_crore` use `india_`; `economy/national_gdp_current_inr_lakh_crore`, `economy/national_gva_by_industry_constant_2011_12_inr_crore`, `economy/national_macro_aggregates_*` use `national_`. Per §2.2 the convention is `national_`. Both shapes exist for the same scope.
3. **`economy/india_iip_index_2011_12`** — encodes methodology base year (`2011_12`) in the id. Per §3 rule 3, vintage belongs in `methodology_vintage`, not the id. Same problem in `economy/national_gva_by_industry_constant_2011_12_inr_crore` and `economy/state_per_capita_nsdp_constant_2011_12_inr` (and these also bust the §2.5 length budget at 60+ chars).
4. **`fiscal/states_combined_gross_fiscal_deficit`** (and siblings: `..._revenue_deficit`, `..._primary_deficit`, `..._primary_revenue_deficit`, plus `fiscal/union_*` peers) — no unit suffix. Values are `₹ crore`; per §2.3 the id should say so (`..._inr_crore`).
5. **`fiscal/net_transfers_from_centre` AND `fiscal/centre_transfers_to_states_net`** — two ids for what looks like the same concept, named in opposite directions, neither carrying a unit suffix. One should be the alias of the other (or one should be retired) per §7. Today they're both live in the catalogue.
6. **`energy/installed_capacity_coal_mw`** (and siblings: `_hydro_mw`, `_gas_mw`, `_nuclear_mw`, `_thermal_mw`, `_renewable_mw`, `_total_mw`, `_by_source_mw`) — no scope prefix at all. They are national totals; per §2.4 should be `energy/national_installed_capacity_<fuel>_mw`. Inconsistent with sibling `energy/india_thermal_capacity_retired_mw` which uses `india_` (and should be `national_` per anti-pattern 2).
7. **Title casing drift** — `"Crude Birth Rate (per 1,000 population)"`, `"Total Fertility Rate (children per woman)"`, `"Infant Mortality Rate (per 1,000 live births)"`, `"Human Development Index (...)"` are Title Case; `"Installed coal-fired capacity"`, `"PM2.5 — annual mean (state)"`, `"Net Centre-to-States transfers (all-India)"` are sentence case (or mixed). Per §5.1 the convention is sentence case; the existing Title Case titles are §8.

These are anti-pattern listings only. Migrating them is a separate change, executed via §7's expand–migrate–contract.

## 9. Pinned resolutions

The v1 draft of this doc surfaced 4 dissents. They are pinned below (decided 2026-05-16) with Hans's reading winning on the two substantive splits.

1. **PINNED (Hans wins): denominator-in-id is the convention.** When a share's denominator is a meaningful citizen reading, the id MUST spell it: `_pct_<denominator>` (e.g. `_pct_gsdp`, `_pct_total_expenditure`, `_pct_total_capacity`). When the denominator name pushes the id past the §2.5 60-char budget, prefer (a) shortening the noun or (b) blowing the budget (it is a SOFT cap) over (c) bare `_pct`. Bare `_pct` is now an anti-pattern.
   - **Concrete impact on the pending ingest**: RBI Statement 27 lands as `health/state_health_expenditure_pct_total_expenditure` (53 chars, fits), NOT `health/state_health_expenditure_share_of_total_expenditure_pct`. The handover doc's chosen id is overridden by this pin.
   - **Existing violator**: `environment/state_thermal_fgd_installed_share_pct` (took option c). Listed in §8 for later expand-migrate-contract; not migrated by this commit.
   - **Schema v1.5 reinforcement**: the artifact MUST also populate `indicator.denominator = {what, price_basis, base_year, source_artifact}`. The id is the citizen-visible label; the field is the formal definition.
2. **PINNED (Hans wins): `state_` prefix retained on "states combined" national-tier facts.** `fiscal/states_combined_gross_fiscal_deficit` and siblings keep their existing form. The noun is "states combined"; the prefix is informational and changing to `national_` would actively mislead (it isn't the Union government's deficit). Max's argument that there is no state entity per row is acknowledged and noted on the artifact via `attribution_geography` / `coverage`, not in the slug.
3. **DEFERRED: schema enum-validation of `<scope>`.** Stays as convention (match a topic-id from the catalogue) for now. Revisit after two more ingests; if drift continues, lift to a JSON-Schema `enum` constraint on the id pattern. Coupling the indicator schema to the catalogue is a real cost (ADR-0022 keeps them independent on purpose), so the convention is allowed to ride longer before being hardened.
4. **PINNED (lightweight): pre-ingest naming-review paragraph required on every new ingest handover doc.** Each ingest handover doc under `TODO/` MUST include a one-paragraph naming declaration: (i) the chosen id(s), (ii) which §8 anti-patterns the choice avoids, (iii) which §3 / §4 rules it honours. Reviewed against this doc before the ingest commit lands. No new tooling required; a checklist line in the handover template.

The two pending ingest handovers ([TODO/20260515-iced-aq-no2-so2-pm10-handover.md](../../TODO/20260515-iced-aq-no2-so2-pm10-handover.md) and [TODO/20260515-health-ingest-handover.md](../../TODO/20260515-health-ingest-handover.md)) inherit these pins immediately; the orchestrator will append the §9.4 naming-review paragraph to each before dispatching the subagent.

## See also

- [`../../CLAUDE.md`](../../CLAUDE.md) — Holy Laws #4, #6; §11 schema versioning.
- [`../architecture/decisions/0022-place-first-ia-with-topic-catalogue.md`](../architecture/decisions/0022-place-first-ia-with-topic-catalogue.md) — topic membership lives on the catalogue, not the artifact.
- [`../architecture/decisions/0002-provenance-as-sources-list.md`](../architecture/decisions/0002-provenance-as-sources-list.md) — why source authority does not belong in the id.
- [`../../datasets/schemas/indicator.schema.json`](../../datasets/schemas/indicator.schema.json) — the regex and field shapes this doc decorates.
- [`../../datasets/reference/in/topic-catalogue.json`](../../datasets/reference/in/topic-catalogue.json) — the source of truth for the legal `<scope>` set.
