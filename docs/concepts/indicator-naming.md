# Indicator naming — id slugs, titles, descriptions, facet labels

**Last Updated**: 2026-06-11

## 1. Why this doc exists

This doc is the convention for indicator id naming. It is binding for new ids; existing ids that violate it are listed in §8 and have been ripped. The current schema accepts only canonical indicator ids; this doc locks what humans should put inside each surface.

**2026-05-26 update** -- [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) retires the `<entity_prefix>` axis (`state_` / `district_` / `national_`). The grain rides on the observation row's `entity_id`; the catalogue declares `entity_kinds`. §2.2 was rewritten and §2.4 was deleted in the same commit as the ADR landed. §8 anti-pattern #2 was promoted from "style drift" to "MUST NOT mint." See ADR-0044 for the identity test that replaces §2.4's default-geography test.

Per [ADR-0022](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue): topic membership lives on `datasets/taxonomy/topics.json`, NOT on the indicator artifact. This doc does not re-open that decision.

## 2. The `indicator.id` slug — anatomy and rules

### 2.1 Accepted grammar during the migration window

`indicator.id` has two accepted grammars in `datasets/schemas/indicator.schema.json` v6.1:

- **Legacy folded JSON artifact ids** keep the historical slash/snake grammar:

```
^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*$
```

- **Canonical indicator ids** use the ADR-0044 single-segment kebab grammar:

```
^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$
```

Do not mix the grammars. `energy/peak-electricity-demand-mw` is neither a legacy artifact id nor a canonical id. Do not substitute a route/backcompat `legacy_artifact_id` for canonical identity.

### 2.2 Legacy folded JSON artifact shape

```
<scope>/<noun>_<aggregate?>_<unit?>_<facet?>
```

**Per [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) the `<entity_prefix>` segment is DELETED, not made optional.** The grain (country / state / district / subdistrict / village) lives on the observation row's `entity_id` and is declared on the catalogue row's `entity_kinds: array<enum>` + `default_entity_kind: enum` fields. The renderer dispatches the chart shape from the row, not from the id slug.

- **`<scope>`** — exactly one segment. By convention, MUST be a topic-id from `datasets/taxonomy/topics.json` (`fiscal`, `energy`, `environment`, `health`, `economy`, `prices`, `demography`, `transport`, `elections`, `human_development`, …). The catalogue is the source of truth for the legal set; this doc deliberately does not enumerate them. Adding a new scope means adding a topic to the catalogue first.
- **NO `<entity_prefix>`.** Ids that start with `state-` / `district-` / `national-` are rejected by Tier-B `tier_b_indicator_id_no_grain_prefix` (added dark in PR-B1, enforced in PR-B9 of the grain-rip plan). Fact-grain prefixes (`ac-`, `candidate-`, `party-`) are NOT entity-grain prefixes and stay — they encode the observation-row grain, not the entity grain.
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

**Omit** the unit suffix only when the indicator is genuinely dimensionless (`state_total_fertility_rate` — TFR is children-per-woman by definition; the noun encodes it). When in doubt, include the suffix — Max's rule: an explicit unit in the slug saves the next reader a click into the schema.

### 2.4 Entity grain — RETIRED by ADR-0044

This section formerly mandated a leading `state_` / `district_` / `national_` segment. **It is deleted.** Per [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity), entity grain rides on the observation row's `entity_id`; the catalogue row carries `entity_kinds: array<enum["country","state","district","ac"]>` + `default_entity_kind: enum`. One id per `(concept, unit, normalisation)`; rows discriminate grain.

Canonical indicator ids follow the `<measure>-<unit>-<facet>` kebab rule from ADR-0044. Topic membership and entity grain are not encoded in the id; topic membership lives in `datasets/taxonomy/indicator_topic_tags.parquet`, and grain rides on observation rows.

**Identity test** (use before minting any new id): is the (concept, unit, normalisation) tuple different from every existing indicator? If YES, mint. If NO, UPSERT into the existing id OR add a facet axis on the row. Entity-kind is NOT an identity axis.

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
3. **Source authority does NOT belong in the id.** `rbi_outstanding_debt_pct_gsdp` is wrong (the upstream changes; the fact does not). `fiscal/state_outstanding_debt_pct_gsdp` is right. Provenance lives in the `sources` array (§9 of CLAUDE.md / archived ADR-0002, superseded by [ADR-0030](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) + [ADR-0032](data-provenance.md#adr-0032-sources-citation-ledger)). The id is the citizen's noun, not the bureaucracy's catalogue number.
4. **Long-arc series get one id.** When an indicator is meant to live across a 30-year window (debt-to-GSDP, birth rate), the id should be writable in 1995 and still be the same in 2025. Methodology vintage is what changes; the id is the through-line.

## 5. `indicator.title` and `indicator.description` — citizen-readable copy rules

### 5.1 Title

- **Sentence case**, not Title Case. `"Outstanding liabilities (% of GSDP)"` not `"Outstanding Liabilities (% Of GSDP)"`. The current corpus is split — `"Crude Birth Rate"` (Title Case) vs `"Installed coal-fired capacity"` (sentence). New ids use sentence case; old ones are §8.
- **English only.** Single-script titles, no transliteration. Bilingual surfaces are a future ticket; today's frontend renders English.
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

Per the v1.4 changelog entry on `indicator.schema.json`, the composer is the source of truth for these labels — the frontend stops carrying topic-level hardcoded literals. This doc does not re-derive that decision; see the schema's changelog.

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

> *Expand → migrate → contract.* (Beck/Fowler/Sadalage's schema-evolution discipline applied to ids.) Step 1 (expand): update the catalogue to add the new id alongside an alias for the old id (the catalogue renderer follows aliases for one release). Step 2 (migrate): update the frontend's known references and contract tests to the new id; verify the route still resolves via the alias. Step 3 (contract): in the next release, drop the alias from the catalogue. Each step is its own commit. NEVER mix the rename with a behaviour change in the same commit (Beck's two-hat rule).

If no alias mechanism exists in the catalogue today, that's a TODO — flag it on the migration ticket; until then, id renames after publish require a coordinated multi-file commit and the citizen sees a brief 404 window. Don't rename ids casually.

## 8. Anti-patterns (existing-corpus examples — do NOT migrate in this commit)

These ids exist on disk and ship today. Listing them honestly so future agents know the convention is aspirational, not retroactive:

1. **`energy/installed_mw_by_state`** (retired legacy id) — entity-prefix at the END (`_by_state`), unit (`mw`) buried in the middle, no aggregate verb. Per §2.2 should be `energy/state_installed_capacity_mw`.
2. **`state-` / `district-` / `national-` / `india_` ENTITY-GRAIN PREFIXES — MUST NOT MINT NEW.** Per [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity), entity grain rides on the observation row, not the id slug. Existing ids that led with these prefixes have been ripped (grain-over-entity migration, 2026-05). New ids that re-introduce grain prefixes are rejected by Tier-B `tier_b_indicator_id_no_grain_prefix`. The old `india_*` vs `national_*` collision is moot post-rip — both shapes disappeared.
3. **`economy/india_iip_index_2011_12`** — encodes methodology base year (`2011_12`) in the id. Per §3 rule 3, vintage belongs in `methodology_vintage`, not the id. Same problem in `economy/national_gva_by_industry_constant_2011_12_inr_crore` (and these also bust the §2.5 length budget at 60+ chars).
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
4. **PINNED (lightweight): pre-ingest naming-review paragraph required on every new ingest handover doc.** Each ingest handover doc MUST include a one-paragraph naming declaration: (i) the chosen id(s), (ii) which §8 anti-patterns the choice avoids, (iii) which §3 / §4 rules it honours. Reviewed against this doc before the ingest commit lands. No new tooling required; a checklist line in the handover template.

Pending ingest handovers must include a naming-review paragraph per §9.4 before the ingest commit lands.

## 10. v1.5 honest-renderer fields — `comparability` and `renderer_rules`

Hans's v1.5 schema bump introduced two fields that bind the renderer to honest reading. They are NOT id-shape rules (so they don't belong in §2 or §3 strictly), but every ingest handover MUST set them and every renderer MUST honour them. This section is the canonical reference the schema description (`indicator.schema.json` `renderer_rules.description` and `comparability.description`) defers to.

### 10.1 `comparability` — the 4-level honest ladder

```
comparable_across_states_and_time          // level 1 — rank states, trace trends. Best case.
comparable_across_states_snapshot_only     // level 2 — rank states today; do NOT trace trends across the break.
comparable_within_state_over_time          // level 3 — trace one state, do NOT rank states.
directional_only                           // level 4 — read direction-of-change only; no rank, no growth math.
```

The three v1.0–v1.4 tokens remain valid for back-compat but are deprecated. Migration map (also annotated in the TypeScript union in `frontend/src/lib/indicators.ts`):

| Deprecated (v1.4) | Replace with (v1.5) | Reasoning |
| --- | --- | --- |
| `comparable_across_states` | `comparable_across_states_and_time` | Old token was ambiguous on the time axis. The v1.5 split forces the choice. |
| `not_comparable_across_states` | `directional_only` | Old token said only what was forbidden; the v1.5 token names what IS supported. |
| `comparable_with_normalisation` | one of the 4 levels (per-artifact decision) | Old token punted to the renderer ("normalise me first"). v1.5 forces the artifact author to commit: if the normalised view is level 1, ship the normalised artifact AS level 1 (e.g. `outstanding_debt_pct_gsdp` is level 1, the raw `outstanding_debt_inr_crore` is level 3). |

**Renderer contract (enforced today in `frontend/src/lib/indicator-card.ts:canShowRank`):**

| Token | Rank line on `/s/<state>` card | Sparkline on `/s/<state>` card | Cross-state choropleth on `/t/<topic>` |
| --- | :---: | :---: | :---: |
| `comparable_across_states_and_time` | ✅ shown | ✅ shown | ✅ shown |
| `comparable_across_states_snapshot_only` | ✅ shown | ⚠️ template-level rule (TODO: suppress trend across break) | ✅ shown (snapshot only) |
| `comparable_within_state_over_time` | ❌ suppressed | ✅ shown (per-state trace) | ❌ refuse (no cross-state comparison) |
| `directional_only` | ❌ suppressed | ✅ shown (direction only) | ⚠️ allowed with banner ("read direction only") |
| `not_comparable_across_states` (deprecated) | ❌ suppressed | as above | as above |

The `canShowRank` rule set is the single source of truth for the rank-suppression column. New comparability tokens or new `renderer_rules` slugs that should suppress ranking extend `canShowRank`, never the card template (see [indicator-card.md](indicator-card.md) §"Render decisions").

### 10.2 `renderer_rules[]` — controlled slug vocabulary

The schema validates the slug shape (`^[a-z][a-z0-9_]*$`) but does NOT enumerate the vocabulary (deliberately — new slugs need to land in data before the renderer learns them, not the other way around). The live vocabulary the frontend recognises today is mirrored in `frontend/src/lib/indicators.ts` as `RendererRuleSlug`:

| Slug | Semantic | Enforcing renderer / helper |
| --- | --- | --- |
| `no_rank_table` | Suppress the rank line on `IndicatorCard` and refuse the ranked-table view. Use when the indicator's `comparability` is otherwise permissive (e.g. nominally `_and_time`) but a domain-specific reason still makes ranking misleading (e.g. an absolute-magnitude count where the largest state always wins by population, not by performance). | `canShowRank` in `frontend/src/lib/indicator-card.ts` |
| `no_growth_across_break` | Refuse to compute YoY (or any period-over-period) growth that spans a `series_breaks[]` entry. Show the values either side of the break as separate runs, with the break annotation between them. | TODO: trend-line components (currently no live use — schema-defined, frontend-unimplemented). |
| `mask_be_in_long_view` | Visually distinguish Budget-Estimate periods from Actuals in any long-view trend (lighter stroke / hatched fill / "BE" badge). Pairs with `revision_tier_by_period[]` which declares which periods are BE vs RE vs A. | TODO: trend-line components. |
| `force_per_capita_choropleth` | Block raw-magnitude choropleth on `/t/<topic>`; the page MUST normalise by population before rendering. Use when an indicator is a raw count whose cross-state comparison is meaningless without per-capita normalisation. | TODO: `/t/<topic>` choropleth renderer. |

**Adding a new slug** is a three-place change in a single commit (Holy Law #4):

1. Add a row to the table above with the semantic and the enforcing renderer.
2. Extend `RendererRuleSlug` in `frontend/src/lib/indicators.ts` (the union is `RendererRuleSlug | (string & {})` so unknown slugs already parse; this step is for type-aware call-sites).
3. Implement the enforcement in the named renderer. A slug that has no enforcing renderer is documentation debt — citizens see no behaviour change.

**Unknown slugs are tolerated, not validated.** A v1.6 ingest may ship a new slug before this doc is updated; the schema accepts it (just `^[a-z][a-z0-9_]*$`), and the renderer ignores what it does not recognise. This forward-compat is intentional — data-side and frontend-side evolve at different cadences. The Definition-of-Done rule (§9 of CLAUDE.md) catches the doc lag at PR review.

## Design rationale

This section consolidates the rationale (Context + Decision + key Consequences, condensed) of the ADRs that define the indicator-naming convention. Each ADR's full body lives EITHER as the receipts folded below + verbatim under [Rejected alternatives](#rejected-alternatives), OR in `docs/archive/decisions/` (superseded). See the redirect map at [`docs/reference/decision-index.md`](../reference/decision-index.md).

### ADR-0025: rename-national-to-fiscal-actor-prefixes

Status: accepted 2026-05-14. Authority: User decision + Fowler (Engineering) + Hans (Governance) + Gregor Hohpe (Architect, dissent recorded).

**Context.** The `fiscal/` indicator family contained eight indicators all prefixed `national_*`: `national_devolution_central_taxes`, `national_grants_from_centre`, `national_gross_transfers` (all from RBI Appendix T2 of State Finances - Centre-to-states flows); `national_gross_fiscal_deficit`, `national_revenue_deficit`, `national_primary_deficit`, `national_primary_revenue_deficit` (all from RBI Appendix T1 - the combined borrowing of all state governments aggregated to all-India). The `national_` prefix was honest about granularity (country-level series, `entity_id="IN"`, one row per fiscal year) but silent about which fiscal actor produced the number. That silence misleads: the four T2 indicators are flows FROM the Union Government to the states (the Centre is the actor); the four T1 indicators are the COMBINED borrowing of all state governments aggregated to all-India (the states collectively are the actor - emphatically NOT the Centre). A reader scanning indicator IDs would reasonably assume `national_gross_fiscal_deficit` is the Centre's GFD (the headline "India's fiscal deficit" number that dominates Budget commentary); it is not, it is the all-states-combined GFD. This is a Factfulness Blame-instinct trap baked into the data architecture itself. A schema-validation pass would never catch this - every artifact validates fine. The defect is semantic, in the names. By yen-gov's Holy Law #6 (no hardcoded magic), names that hide their meaning are a structural problem (Holy Law #5 - fix structurally).

**Decision.** Rename all eight indicators to make the fiscal actor explicit in the slug. Two patterns, one per actor: `centre_transfers_to_states_*` for the four Centre-to-States transfer flows (`_net`, `_tax_devolution`, `_grants`, `_gross`); `states_combined_*` for the four states-aggregate fiscal balances (`_gross_fiscal_deficit`, `_revenue_deficit`, `_primary_deficit`, `_primary_revenue_deficit`). The two prefixes are deliberately patterned: the `_to_states_` infix on the transfer family prevents a future indicator like `centre_transfers_to_psu_*` from collapsing into the same namespace; the word "combined" on the deficit family matches RBI's own terminology in the State Finances volume (which uses "All States" / "Combined" headers) - "aggregate" was deliberately avoided because in Indian fiscal usage "aggregate" often denotes Centre+States consolidated, which is exactly NOT what these series are. The internal slug-segment word order is actor -> action -> object -> attribute (`centre_transfers_to_states_net`), not English noun order (`net_centre_transfers_to_states`); sort order then groups by actor first, which is what a citizen scanning a topic catalogue actually wants. No schema change in this commit. The schema stays at v1.3.

**Consequences.** Immediate: eight `git mv` operations on the fiscal indicator tree; ~100 string substitutions across 21 files (adapters, parsers, tests, reference catalogues, dataset artifacts, four docs); test suite stays green; schema unchanged; frontend untouched (no references existed). Follow-ups recorded: the Union (Centre's own) deficit indicators are absent - this rename names the actor "Centre" only as a benefactor (transfers OUT) and the actor "states_combined" as the borrower; the Centre's own borrowing (gross fiscal deficit ~5.6% of GDP in FY24, larger than states-combined ~3.2%) is missing from the data architecture (open gap: no ingest yet). Chart-trap warning (raised by Hans, captured in the fiscal-actor-naming concept doc): the four `centre_transfers_to_states_*` indicators are NOT independent series - they are one envelope decomposed (`_net = _gross - loan_recoveries`; `_gross ~= _tax_devolution + _grants + loans`); a naive stacked-bar chart that places `_net`, `_tax_devolution`, `_grants`, and `_gross` side by side lets a reader double-count. Any visualisation that groups these MUST use the decomposition explicitly (gross as the total, devolution + grants + loans as the parts, net as a separately-labelled "after recoveries" reference line) or pick one and only one for the headline view.

### ADR-0027: cadence-as-separate-field-from-time-grain

Status: accepted 2026-05-17 (superseded by [ADR-0030](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) on the placement seam - cadence now lives on the indicator catalogue row alongside `default_period_seq_for_cadence`; `period_seq:int` is the machine sort key and `period_label` is the citizen-visible string verbatim). Authority: User + Fowler (Engineering) + Gregor (Architect) + Max (Indicator Scout). Schema impact: `datasets/schemas/indicator.schema.json` v4.0 -> v4.1 (additive; new optional `indicator.cadence` field).

**Context.** Phase #1 of the coverage-temporal-range plan added a pure `derive_temporal_range(indicator)` function that returns the observed min/max time, observed period count, and a `gap_count_within_range` (expected periods at the declared cadence minus observed periods). A spike across all 110 production artifacts surfaced eight artifacts with non-zero `gap_count_within_range`. Five of the eight (Census-population x 2, UNFCCC GHG x 2, CEA capacity-pipeline) had a `gap_count_within_range` value that was actually NOISE from the function's perspective: their `time_grain=year` (or `fiscal_year`) declared an annual cadence the publisher never promised. Census is decennial; UNFCCC NATCOM/BUR is ad-hoc; CEA capacity-pipeline mixes historic + forward projections (fundamentally ad-hoc). The function was honest; the artifact was lying about cadence.

`indicator.time_grain` declares the resolution of a single `rows[].time` token. For a Census row, each observation IS stamped at year resolution - the token is `"1961"`, not `"1961-decade"`. `time_grain=year` is correct for Census: it tells the renderer how to format the time axis. The grain says nothing about how often the publisher releases a new observation. What was missing was a SECOND field that declares the publisher's release cadence. Today the schema had no such field. v4.0 explicitly removed `series_spec.expected_periods[].frequency` (and the whole `expected_periods` array) per [ADR-0026](#adr-0026-lift-collection-inventory-out-of-indicator-artifact), lifting that operator-axis state into the external completeness index. What survived was `time_grain` - and `time_grain` cannot answer "is this series expected to publish a new value every year".

**Decision.** Add a new optional field `indicator.cadence` to the indicator artifact in schema v4.0 -> v4.1 (additive minor bump per CLAUDE.md section 11). The field declares the publisher's release cadence. It is distinct from `time_grain` (which describes per-row time-token resolution) - the two carry different concepts, neither subsumes the other, and both stay on the citizen-axis artifact because both inform citizen reading. Enum (initial set, aligned with the legacy `expected_periods[].frequency` vocabulary the lifted v3 schema used): `annual_cy` / `annual_fy` / `quarterly_cy` / `quarterly_fy` / `monthly` / `weekly` / `daily` -> gap_count defined; `decennial` -> gap_count omitted (no "gaps" pill); `ad_hoc` -> gap_count omitted (no "gaps" pill). The field is optional in v4.1; when absent, `derive_temporal_range` falls back to its v4.0 behaviour (best-effort inference from `time_grain`). Adapters add `cadence` opportunistically; the four unambiguous witnesses (Census x 2, BUR-GHG x 2) are retagged in the same commit as the schema bump.

`derive_temporal_range` reads `indicator.cadence` and: for `cadence in {decennial, ad_hoc}` omits both `gap_count_within_range` AND `observed_periods_within_range` (these series have no defined expected cadence; surfacing "observed = 6 of 51 expected" or even "observed = 6" against a range invites the citizen to read patchiness into a complete record); `min_time` / `max_time` / `*_period_label` / `time_grain` are still returned (the range itself is honest). For `cadence in {annual_*, quarterly_*, monthly, weekly, daily}` computes `gap_count_within_range` against that cadence. For `cadence` absent, falls back to inferring from `time_grain` (preserves back-compat for unmigrated artifacts).

**Consequences.** Citizen surface: the caption builder reads `cadence` (not `time_grain`) to choose the grainWord slot - "annual", "every 10 years", "irregular updates", etc.; for `decennial` / `ad_hoc`, the renderer shows only the range (`1961 -> 2011 . every 10 years`) and suppresses any gap/completeness pill. Operator surface: the completeness index emitter mirrors what `derive_temporal_range` returns - index rows for decennial/ad_hoc indicators have absent `gap_count_within_range` / `observed_periods_within_range` keys; the operator reads "this indicator's cadence is undefined; gap math doesn't apply", which is the truth. Migration cost: adding one optional field is additive; four artifacts get a one-line `cadence` retag in the same commit (Census x 2, BUR-GHG x 2); three artifacts (RBI external balance, CEA capacity pipeline, HDI) are flagged for a separate adapter-quality audit. Frontend TS impact: `frontend/src/lib/indicators.ts` adds an optional `cadence?: <enum>` field to `IndicatorMeta`. Validator impact: Tier A (schema sanity) - the new enum validates as a normal additive change; Tier B (corpus conformance, local-only per CLAUDE.md section 11) - absent field on the other 106 artifacts remains valid. Doctrine impact: CLAUDE.md section 10 gains a bullet codifying the publisher-vocabulary corollary surfaced by Gregor in the debate - if `derive_temporal_range` raises mixed-vocab, fix the adapter to emit one shape per artifact OR split the artifact, do not coerce tokens to silence the error; the cadence field is the structural answer to "but my publisher publishes irregularly", coercion is not.

### ADR-0044: grain-over-entity

Status: accepted 2026-05-26. Authority: User (autonomous mandate, 2026-05-26 - "Move grain to OWID-style grain-over-entity. Stop smooshing state + district + village into one chart; create sub-pages.") + Hans + Max (data shape, per CLAUDE.md section 0a) + Gregor (contract seam) + Jony (UX surface). Supersedes: this doc's section 2.2 ("entity-prefix mandatory") + section 2.4 ("when to include `state_` / `district_` / `national_`") - both sections were rewritten in the same commit as this ADR landed.

**Context.** `indicator_id` historically encoded the entity-grain as a leading slug segment: `state-pashu-aadhaar-count-cattle` and `district-pashu-aadhaar-count-cattle` were the same concept measured at two grains, but the catalogue stored them as two rows, two allowlist entries, and two topic-page cards. As of 2026-05-26 the canonical catalogue carried 121 rows; 77 of them led with `state-` / `district-` / `national-` / `ac-` / `candidate-` / `party-`. The first three are entity-grain prefixes; the last three are fact-grain prefixes (different observation grains, not different entity grains) and stay. OWID, the World Bank, the IMF, the FAO and the UN Statistical Division converge on a different convention: one Variable per `(concept, unit, normalisation)`; the entity rides on the row, dispatched by the renderer. yen-gov's prior position ("entity-prefix mandatory", "Path A") was a localism. The cost of maintaining the localism was paid every time a sub-state-grain family landed: two ids, two cards, two test bodies, two AGENTS.md notes, and an "expand-migrate-contract" rename runbook to climb back out. The accumulated debt was visible: `/t/agriculture` was shipping 18 stacked species cards because 11 species x 2 grains had each been minted as separate ids; PR #281 + PR #284 + PR #287 + PR #304 each had to fan out per-species ids and re-author per-species caveats; the pattern was going to repeat across livestock owner-reg (14 ids), NAIP-IV (8 ids), every future sub-state-grain ingest.

Three options were considered: alpha (keep Path A; build dispatcher tooling - cheap today, expensive every PR, rejected); beta (Path B with expand-migrate-contract aliases, 60-day deprecation window - OWID-aligned eventually but pays a 60-day double-bookkeeping cost per family, rejected because user mandate is "rip-and-replace, no strangler-fig"); gamma (Path B, rip-and-replace, one PR per family with a one-shot DuckDB CTAS migration script committed under `tools/migrate/` - accepted).

**Decision.** `indicator_id` MUST NOT encode the entity-grain. The grain is a property of the OBSERVATION ROW, carried by `entity_id` and surfaced through the indicator-catalogue's `entity_kinds: array<enum["country","state","district","ac"]>` field + `default_entity_kind: enum` field. The renderer dispatches the chart shape from the row's `entity_kind`, not from the id slug. Concrete grammar: the id is `<noun>-<aggregate?>-<unit?>-<facet?>` kebab-case; the leading `<entity_prefix>-` segment is DELETED, not made optional - the regex on the catalogue schema rejects ids that start with `state-` / `district-` / `national-`; fact-grain prefixes (`ac-`, `candidate-`, `party-`) are NOT entity-grain prefixes and stay.

What rides where: concept lives on `indicator_id` noun; unit lives on `indicator_id` unit suffix + catalogue `unit` field; normalisation (raw / per-capita / per-area / share) lives on `indicator_id` (per-capita / share is part of identity per OWID rule O1); entity grain (country / state / district / subdistrict / village) lives on `observation.entity_id` + `indicator.entity_kinds[]` + `indicator.default_entity_kind`; facet (species / fuel / sector) lives on `observation.<facet_col>` (one column per facet axis) + catalogue `facet_axes`; vintage lives on `observation.source_id` + `source.csv.vintage`; methodology break lives on `methodology_breaks.parquet` row keyed on same `indicator_id`; render shape (chart_type, default_mode, renderer_rules, facet_labels, dimension) lives on the grapher catalogue per [ADR-0045](../architecture/data/indicator-catalogue.md#adr-0045-grapher-catalogue-split).

Renderer dispatch: the frontend reads each observation row's `entity_kind` and picks the renderer per grain. `IndicatorChoropleth.svelte`'s prior `entity_kind === "state"` constraint is removed; the component dispatches to the right boundary layer (state / district / subdistrict / village) from the row, not from a per-id allowlist.

Identity test (OWID-aligned, replaces the section 2.4 default-geography test): before minting a new `indicator_id`, every author MUST answer YES to ALL of: (1) is the concept different from every concept in `datasets/taxonomy/concepts.json`? (2) is the unit different from the closest concept-match? (3) is the normalisation different (raw / per-capita / per-area / share / index)? If all 3 are YES, mint a new id. If any answer is NO, UPSERT into the existing id OR add a facet axis. Entity-kind is NOT an identity axis. Same concept at country + state + district is ONE id with `entity_kinds: ["country","state","district"]` and rows distinguished by `entity_id`. The 4th identity question used in earlier drafts ("is the entity_kind different?") is explicitly retired by this ADR.

**Consequences.** Positive: catalogue row count drops by ~60% in livestock + energy + economy + fiscal blocks (the plan's standing reference table enumerates the collapses: 77 -> ~16 rows in those families); topic pages stop stacking grain-cards (the `/t/agriculture` 18-card mess is closed by PR-C2); citizen explorer surfaces `/i/<indicator>` and `/i/<indicator>/<grain>` become possible; aligns yen-gov with OWID / World Bank / IMF / FAO precedent on indicator identity; one caveat array per measure instead of one per (measure x grain x facet) - Hans-curated bullets stop fragmenting. Negative: the rename is a hard cutover - every observation CSV under `datasets/<family>/` carrying a `state-` / `district-` / `national-` `indicator_id` MUST be rewritten by a one-shot DuckDB CTAS committed under `tools/migrate/path_b_<family>.py`, reverted via `git revert <sha>` if any smoke gate fails; `/compare?i=state-X` and `/compare?i=district-X` URLs in any existing bookmarks 404 (there is no alias window; per CLAUDE.md standing limit, the citizen-route SMOKE gate must show a working successor URL before each Phase B PR merges; bookmarks ARE allowed to 404, the standing limit covers in-app routes, not external bookmarks); the frontend allowlist must learn to project a per-grain descriptor from a single catalogue row.

Permanent guardrails (shipped alongside this ADR; each enforced by a Tier-B check): #1 `indicator_id` MUST NOT start with `state-` / `district-` / `national-` (enforced by `tier_b_indicator_id_no_grain_prefix` in `backend/yen_gov/validate.py` - dark in PR-B1, enforced in PR-B9); #13 new ingest MUST FK to a row in `datasets/taxonomy/concepts.json` declaring `(concept, unit, normalisation, entity_kind)` (two indicators with the same 4-tuple are rejected by `tier_b_one_indicator_per_concept`); #16 `tier_b_facet_promotion_warning` flags per-fuel / per-species id proliferation (3+ siblings differing only in one slug segment); #19 methodology break = same id + `methodology_breaks.parquet` row, NEVER a renamed id (Rosling rule, mirrors [ADR-0042](../architecture/data/canonical-store.md#adr-0042-sources-schema-v3-vintage-as-period-anchor)).

> **ADR-0044 CSV-era note.** The grain-over-entity rule survives the CSV cutover verbatim. Under the long-format CSV regime, `indicator_id` keeps the `<noun>-<aggregate?>-<unit?>-<facet?>` kebab grammar, `entity_kinds[]` + `default_entity_kind` move onto the CSV catalogue row, and renderer dispatch reads `entity_kind` off each observation row in `datasets/data/datapoints/**/*.csv`. CLAUDE.md section 10 anti-pattern (Prefix `state-` / `district-` / `national-` on `indicator_id`) is binding for the CSV-era catalogue too.

## Rejected alternatives

This section preserves the rejected-alternatives receipts from the ADRs whose rationale is folded above. Each subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0025 rejected alternatives

- **Alternative A - blanket rename `national_* -> centre_*`**. Rejected. This was the original plan. Discovery during execution: the eight indicators do NOT share a fiscal actor; four are Centre-actor, four are states-aggregate. A blanket rename would have actively mislabelled the deficits as Centre's deficits - making the citizen confusion worse, not better.
- **Alternative B - keep `national_` and add a typed `fiscal_actor` enum field** (Gregor Hohpe's recommendation). Rejected by user. The proposal was to keep slugs as-is and add `indicator.fiscal_actor: "centre" | "states_combined" | "union" | "consolidated"` to the schema (v1.4 minor bump), letting the UI render an "Actor: States (combined)" pill alongside the title. This is structurally cleaner - the actor becomes a queryable field rather than a parser-prone substring of the slug. Overruled because slugs are the most-frequent surface (they appear in URLs, log lines, fixture filenames, copy-paste in Slack, error messages - a typed field that's three layers down in JSON helps tools, not citizens); the frontend had zero references to these eight IDs at decision time (no consumer that would benefit from a typed field RIGHT NOW; one consumer - the citizen reading the slug - who benefits from honest names IMMEDIATELY); adding both (typed field AND honest slug) is the long-term endpoint, but each step should pay its own way - slug rename pays now, typed field pays when a UI control sorts/groups by actor (Step C concern, not a Step B concern). Fowler's call: "the rename IS the structural fix; the typed field is the next refactor, not a substitute for this one."
- **Alternative C - defer the rename, ship the new indicators with the new prefix and leave the old ones alone**. Rejected. Two prefix conventions in the same directory permanently is worse than one transition. The rename was small (~100 substitutions across 21 files, atomic commit) and it is the kind of correction that compounds in cost the longer it waits - every new piece of code, doc, or test that references the old IDs is debt to repay later.

### ADR-0027 rejected alternatives

- **A. Extend `indicator.time_grain` enum to include `decennial` and `ad_hoc`** (the simpler-looking path Gregor initially recommended in the debate). Rejected because it conflates two distinct concepts onto one enum: stamp resolution (the existing `time_grain` semantics - "the token is YYYY") AND release cadence ("a new value drops every 10 years"); a `decennial` time_grain value is a category error (Census rows still use `time = "1961"`, a YYYY token at year resolution, not some decennial-stamp format). It would break the renderer's existing `time_grain -> token format` contract (`time_grain=year -> YYYY`; `time_grain=date -> YYYY-MM-DD`); adding `decennial` and `ad_hoc` to this enum gives them no defined token format, forcing per-value special cases. It would not solve the underlying problem cleanly: a future ad-hoc-but-monthly-stamped indicator (e.g. RBI press release series) would still need cadence and stamp expressed independently.
- **B. Read cadence from `series_spec.period.frequency`** (Max's first proposal; the natural home in OWID-style schemas, and the home in yen-gov's v2 folded indicator model). Rejected because v4.0 of `indicator.schema.json` ([ADR-0026](#adr-0026-lift-collection-inventory-out-of-indicator-artifact), 2026-05-17) explicitly removed `series_spec.expected_periods` and its `frequency` sub-field; in v4.0, `series_spec` is `{description}` only - there is no cadence field on the artifact anywhere. Restoring it inside `series_spec` would be re-introducing the v3 shape ADR-0026 deliberately collapsed. A new top-level `series_spec.cadence` would also have to be defined as an optional additive bump, with the same enum and the same downstream wiring as Option C - at which point the only difference is where the field lives. Putting it on `indicator` groups it with the other adapter-declared "what is this series" metadata (`time_grain`, `value_kind`, `direction`, `unit`), which is where citizen and operator surfaces already look.
- **C. No schema change; let `derive_temporal_range` infer cadence from spacing**. Tempting because zero contract change. Rejected because it would have to special-case Census ("if observed-spacing modal is 10 years, assume decennial") - that is exactly the band-aid/normaliser pattern CLAUDE.md section 10 / Holy Law #5 forbid (silently inferring a cadence the publisher never declared); puts cadence truth in code instead of data (a future renderer in TS would need to re-implement the same inference or duplicate the derivation, violating one-rule-many-consumers); the five sparse-by-design cases cannot be distinguished from "this is annual but most years are missing upstream" without a declaration - the function would have to guess, and a wrong guess on the citizen page is a credibility loss.

### ADR-0044 rejected alternatives

- **alpha - keep Path A; build dispatcher tooling**. Cheap today, expensive every PR. Rejected.
- **beta - Path B with expand-migrate-contract aliases (60-day deprecation window)**. OWID-aligned eventually; pays a 60-day double-bookkeeping cost per family. Rejected because user mandate is "rip-and-replace, no strangler-fig" (2026-05-26); everything is in git, revert via `git revert <sha>` if a smoke gate fails.
- **4th identity question on `entity_kind`** (used in earlier drafts: "is the entity_kind different?"). Rejected by this ADR. Entity-kind is NOT an identity axis; same concept at country + state + district is ONE id with `entity_kinds: ["country","state","district"]` and rows distinguished by `entity_id`. Keeping the 4th question would have minted separate ids per grain - exactly the Path A status quo this ADR retires.

## See also

- [`../../CLAUDE.md`](../../CLAUDE.md) — Holy Laws #4, #6; §11 schema versioning.
- [`place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue`](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue) — topic membership lives on the catalogue, not the artifact.
- archived ADR-0002 — why source authority does not belong in the id (superseded by [ADR-0030](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) + [ADR-0032](data-provenance.md#adr-0032-sources-citation-ledger); see [decision-index](../reference/decision-index.md)).
- [`../../datasets/schemas/indicator.schema.json`](../../datasets/schemas/indicator.schema.json) — the regex and field shapes this doc decorates.
- [`../../datasets/taxonomy/topics.json`](../../datasets/taxonomy/topics.json) — the source of truth for the legal `<scope>` set.
