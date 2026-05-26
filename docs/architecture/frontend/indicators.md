# Indicator system

> **Status**: live as of 2026-05-14. Schema `indicator.schema.json` v1.2; renderers `IndicatorChoropleth.svelte` (default trio) and `StackedTrend.svelte` (facetted). The first consumer was `energy/installed_mw_by_state` (choropleth on TN/KL/AS/WB state hubs) — retired in PR-A 2026-05-25 once the per-fuel CEA capacity family (`installed_capacity_{coal,gas,nuclear,hydro,renewable,total,thermal}_mw`) shipped with all-states coverage. The `energy/installed_capacity_by_source_mw` stacked-trend artifact composed by `backend/yen_gov/composers/energy_capacity_by_source.py` per ADR-0024 was retired in PR 7b; the StackedTrend adapter contract still exists (tested via inline synthetic fixture in `frontend/src/lib/charts/stacked-trend/adapter-indicator.test.ts`) and is reachable from `stacked-trend-v2/migrate.ts`.
>
> v1.2 additive fields (2026-05-14): optional `chart_type` (`choropleth` / `ranked` / `stacked-trend`) and `default_mode` (`absolute` / `percent`). Topic-catalogue v1.2 mirrors `chart_type` + `dimension` at the artifact entry level so `TopicLanding.svelte` can dispatch the right renderer without peeking at every indicator JSON. See [`charts/stacked-trend.md`](./charts/stacked-trend.md) for the chart's contract.

## What this exists for

yen-gov began as an election-data viewer. The **indicator system** is the contract that lets it grow into a "compare states across categories" site without per-indicator UI code. One Svelte component renders any indicator declared by an artifact under `datasets/indicators/in/<category>/<id>.json`.

The mandate (2026-05-11): "we should be able to compare states' performance and categorise them based on categories like how are we doing on power." Power is the first category; demographics, economy, health, education, livelihood, infrastructure, governance, and fiscal are queued (see `TODO/PLAN.md` Phase 6).

## The shape of an indicator

Schema: [`datasets/schemas/indicator.schema.json`](../../../datasets/schemas/indicator.schema.json) (v1.1). Long-form fact rows:

```jsonc
{
  "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
  "$schema_version": "1.1",
  "sources": [{ "url": "...", "fetched_at": "...", "name": "...", "authority": "..." }],
  "license": { "id": "...", "name": "...", "url": "...", "redistributable": true },
  "coverage": { "spatial": "...", "temporal": "2020-2024", "admin_level": "state" },
  "indicator": {
    "id": "energy/per_capita_consumption_kwh",
    "title": "Per-capita electricity consumption",
    "entity_kind": "state",
    "time_grain": "year",
    "value_kind": "rate",
    "direction": "neutral",
    "scale_hint": "linear",
    "unit": "kWh/person/year",
    "denominator": "people/population_total",
    "icon": "zap",
    "attribution_geography": "where_consumed",
    "comparability": "comparable_across_states",
    "implementing_authority": "joint",
    "methodology_vintage": "CEA General Review (annual)",
    "notes": "..."
  },
  "rows": [
    { "entity_id": "S22", "time": "2024", "value": 1432.5, "facet": null }
  ]
}
```

Every field on the `indicator` block is metadata that drives rendering. The frontend never branches on the indicator's `id` — only on these declared properties.

## How the metadata drives the UI

| Field | What the renderer does with it |
|---|---|
| `value_kind` | Picks the number formatter. `count` → integer with thousands-separator (Indian-locale lakhs/crores). `share` → "%" (auto-detects 0..1 vs 0..100 by checking max value). `currency` → SI-suffix + unit. `rate`/`index`/`duration` → SI-suffix + unit. `raw` → SI-suffix + unit (escape hatch). |
| `direction` | Picks the sequential ramp hue. `higher_is_better` → teal (160°). `lower_is_better` → red (25°). `neutral` → blue (250°). **Dark always means "more of the thing"** regardless of direction — colour intensity reads as quantity, not as goodness. |
| `scale_hint` | Picks normalisation. `linear` (default), `log` (positive values only; falls back to linear if min ≤ 0), `symlog` (handles negatives), `quantile` (placeholder; treated as linear pending a real ranked-bucket implementation). |
| `unit` | Eyebrow label on the legend; appended to formatted values in tooltips. |
| `comparability` | Drives a banner above the map. `not_comparable_across_states` → amber: "ranking by this number is misleading". `comparable_with_normalisation` without a `denominator` → slate: "per-capita normalisation recommended". |
| `attribution_geography` | When `where_produced` (asset siting), banner says: "shows where the asset is sited, not who uses it". |
| `implementing_authority` | Chip next to the title: "Centre + state" / "Central" / "Local body" / "Parastatal" — surfaces the governance attribution honestly. |
| `funding_split` | Shown as a tooltip on the implementing-authority chip ("Centre 60% / state 40%"). |
| `methodology_vintage` | Footer caption: "Methodology · GSDP base 2011-12". |
| `cadence` | (v4.1+, optional) Publisher release cadence — `annual_cy`/`annual_fy`/`quarterly_*`/`monthly`/`weekly`/`daily`/`decennial`/`ad_hoc`. **Distinct from `time_grain`** (which is the resolution of one row's `time` token). Drives the temporal-range caption: `decennial`/`ad_hoc` suppress any gap/completeness pill because the cadence is undefined. Per [ADR-0027](../decisions/0027-cadence-as-separate-field-from-time-grain.md). |
| `series_breaks[]` | Footer captions: "Series break · 2011-12 (rebase): GSDP series moved from 2004-05 to 2011-12 base." Charts must refuse to compute trends across breaks (planned).  |
| `icon` | Lucide icon name OR path under `frontend/src/lib/icons/indicators/`. Currently optional and not yet rendered (icon system landing in Phase 6A).  |
| `notes` | Promoted from "buried in footer" to high-priority caption directly below the legend. Shapes interpretation. |
| `denominator` | When set, signals that the value is already a rate (e.g. per-capita); the chart trusts the value as-is. Future: enable per-capita derivation for `count`-kind indicators when a denominator indicator is also loaded. |

## Layout (top → bottom inside the section card)

1. **Title + implementing-authority chip** (e.g. "Per-capita electricity consumption · Centre + state").
2. **One-line description**.
3. **Comparability banner** — only when an honesty caveat applies (`not_comparable_across_states`, `where_produced`, or missing-denominator). Amber for hard caveats, slate for soft.
4. **Coverage caption + stale-data chip** — first-class info above the map, not a footnote. "4 of 35 states/UTs have data on this map. The rest are grey because data is missing, not because they have zero." Plus an amber "Snapshot · 2019 (7 years old)" chip when single-snapshot indicators are stale.
5. **Time slider** — only when `times.length > 1`. HTML `<datalist>` ticks for year notches (browsers render them under the track natively).
6. **Map** — generic `MapChoropleth` driven by a `fills` map (state-name → hex) and `tooltips` map (state-name → HTML).
7. **Legend** — continuous gradient bar (CSS `linear-gradient`) with a 3-tick numeric axis (min / mid / max). Replaces an earlier 5-swatch design that fragmented the eye-stop.
8. **Notes** — shapes interpretation; slate-700 / 12px (visually elevated from the rest of the footer).
9. **Methodology vintage + series-break captions** — slate-500 / 11px.
10. **License row** — name + optional license-terms link + amber "non-redistributable" chip when `license.redistributable === false`.
11. **Provenance** — collapsed `SourceList` with `$schema_version`. Full upstream URLs revealed on click.

## What honesty metadata looks like in practice

The original `energy/installed_mw_by_state` artifact (retired in PR-A 2026-05-25) was the canonical *cautionary tale* — the lesson it taught lives on as the rationale for the `attribution_geography` + `comparability` fields on every indicator:
- It rolled plant nameplate capacity by the state in whose polygon the plant sat.
- Much of TN's capacity (e.g. Kudankulam) feeds the southern grid and serves multiple states.
- Therefore: `attribution_geography: "where_produced"` and `comparability: "not_comparable_across_states"`.
- The renderer surfaced an amber banner above the map: *"Read this carefully · This map shows where the asset is sited, not who uses it. Ranking states by this number is misleading."*
- The footer surfaced the methodology vintage: *"OpenStreetMap-derived plant inventory snapshot, community-curated; cross-referenced against CEA broad-strokes only."*
- The notes paragraph promoted the v1 limitation explicitly: *"v1: rollup is restricted to TN, KL, AS, WB. Of 35 states/UTs, only 4 render on this map; the other 31 appear grey because we lack data, not because they have zero capacity."*

The successor `energy/installed_capacity_*_mw` per-fuel family (CEA monthly Executive Summary, all 35 states/UTs) is the v2 that the original was a placeholder for — the schema and renderer needed no UI changes for the swap, exactly as the original methodology note predicted.

## Adding a new indicator

1. Pick a category and id: `<category>/<verbose_snake_id>`. Example: `health/imr_per_thousand_births`.
2. Create `datasets/indicators/in/<category>/<file>.json` with the shape above.
3. Always set `attribution_geography` and `comparability` honestly. If unsure, default to `not_comparable_across_states` and explain in `notes`.
4. Set `direction` from the citizen's POV: lower IMR is better, so `lower_is_better` → red ramp.
5. Set `value_kind` to match how the value should be formatted. For "per 1000 births" pick `rate` with `unit: "per 1000 births"`.
6. **Populate `description_short` and `short_unit`** (PR-T row 1.10 gate, 2026-05-19). `description_short` is a ≤280-char Plain-Facts caption that renders directly under the chart's H3 title via `legendCaption()` in [`indicator-render.ts`](../../../frontend/src/lib/indicator-render.ts) — it MUST distinguish input vs output vs outcome, MUST NOT embed source attribution (the source card handles that), MUST NOT be a tautological restatement of `title` + `unit`. `short_unit` is the compact glyph form for the legend swatch row — e.g. `"₹cr"` for `unit: "INR crore"`, `"kWh/cap"` for `unit: "kWh per person per year"`, `"/1k LB"` for `unit: "per 1,000 live births"`. Both are formally `optional` in the schema (v4.4) but **required for any new indicator authored after 2026-05-19** — the chart wrapper falls back to `description` and then `title` for the legacy tail, but new artifacts MUST NOT lean on that. Rationale: auto-stubbed captions look authoritative on a legend but are factually empty to a citizen (rejected design — see [PR-T plan §11](../../../TODO/20260517-canonical-long-format-pivot.md)).
7. Run `python -m yen_gov validate` to confirm schema + version compliance.
8. Wire it into `StateOverview.svelte` (or a dedicated indicators page) by passing `indicator_path` to `IndicatorChoropleth`. **No new component code is needed.**

## Pure helpers (vitest-tested)

[`frontend/src/lib/indicators.ts`](../../../frontend/src/lib/indicators.ts) is a pure module:

- `uniqueTimes(rows)` — sorted unique time stamps (for the slider's range).
- `rollupByEntity(rows, time)` — sums values per entity at a given time, skipping nulls.
- `facetsByEntity(rows, time)` — per-entity facet breakdown for tooltip rendering.
- `hueForDirection(direction)` — hue degrees per the table above.
- `normalise(value, min, max, scale)` — to 0..1 with linear / log / symlog support.
- `sequentialSwatch(t, hue)` — OkLCh ramp swatch at lightness `0.94..0.44`, chroma `0.04..0.17`.
- `fillForValue(value, min, max, direction, scale, fallback)` — end-to-end resolver.
- `formatValue(value, meta)` — citizen-readable formatting per `value_kind` + `unit`.
- `formatCompact(value)` — short SI suffixes (1234 → "1.2k", 12_345_678 → "12.3M").

22 vitest cases cover all of these; see [`frontend/src/lib/indicators.test.ts`](../../../frontend/src/lib/indicators.test.ts).

## Why one component, not many

A previous draft had per-category component files (`PowerMap`, `HealthIndex`, `EconomyTimeline`). That direction was rejected for three reasons:

1. **Citizen consistency**: every indicator should read the same way. A site where the legend is in a different place per indicator family is harder to learn.
2. **Honesty enforcement**: routing every indicator through one renderer means the comparability banner / coverage caption / stale-data chip / methodology footer are *guaranteed* to appear on every chart — not contingent on whoever wrote the per-indicator component remembering to include them.
3. **Roadmap velocity**: the plan calls for 30+ indicators. One generic component scales; thirty per-indicator components do not.

Per-indicator overrides are still possible later (e.g. a custom small-multiples view for vote-swing indicators) but they should be the exception.

## Canonical -> legacy `admin_level` dispatch (PR B.02)

The canonical pivot ([data/canonical-store.md](../data/canonical-store.md)) types `IndicatorMeta.entity_kind` as a `country | state | district | subdistrict | constituency | city | ward` union; the legacy `IndicatorCoverage.admin_level` field is a free-form `string | null` populated by `"country"` / `"state"` / `"national"` / `null` on disk. The canonical-to-legacy adapter ([`frontend/src/lib/canonical/indicator-from-canonical.ts`](../../../frontend/src/lib/canonical/indicator-from-canonical.ts)) translates between the two via one dispatch helper:

```ts
export function entityKindToAdminLevel(kind: EntityKind | undefined): string | null {
  if (kind === undefined) return null;
  switch (kind) {
    case "country":      return "country";
    case "state":        return "state";
    case "district":     return "district";
    case "subdistrict":  return "subdistrict";
    case "constituency":
    case "city":
    case "ward":         return null; // no canonical consumer yet
  }
}
```

The helper is the single seam: both `buildIndicatorArtifact()` (single descriptors) and `loadFacetMultiplexedFromCanonical()` (RPO-style fused artifacts) read `admin_level` from it instead of hard-coding `"state"`. A load-bearing contract test asserts the round-trip for every entry in `CANONICAL_BACKED_INDICATORS`. This retires the regression class introduced by [ADR-0043](../decisions/0043-auto-rollup-at-canonical-write-time.md) — once a single canonical adapter started emitting BOTH state-grain (SUM rollup) AND district-grain (source-of-truth) rows under different `entity_kind`s, every state-only literal in the reader path became a bug waiting for the first district descriptor.

Companion translation: `canonicalEntityToLegacy()` strips `IN-` from every shape (`IN` -> `IN`, `IN-S22` -> `S22`, `IN-S03-D280` -> `S03-D280`). The legacy district code form `S<n>-D<lgd>` (resp. `U<n>-D<lgd>` for UT districts) is what AboutThisData.svelte and the district choropleth boundary picker consume; no per-shape branch is required because `slice(3)` handles every length uniformly.

## First district-grain allowlist entry (PR B.03)

PR B.03 added `district-pashu-aadhaar-count-cattle` (legacy id `agriculture/district_pashu_aadhaar_count_cattle`) to `CANONICAL_BACKED_INDICATORS` — the first descriptor with `entity_kind: "district"`. The B.02 dispatch helper translates it to `admin_level: "district"` end-to-end; the load-bearing contract test that loops over every allowlist descriptor automatically validates the round-trip, and a dedicated `buildIndicatorArtifact — district-grain (PR B.03 smoke proof)` describe block in `indicator-from-canonical.test.ts` exercises real district id shapes (`IN-S03-D280` -> `S03-D280`, `IN-U05-D640` -> `U05-D640`) on a live allowlist entry — not a synthesised one. The descriptor reads the same canonical fact-table (`livestock.livestock_pashu_aadhaar`) as its state-grain sibling `state-pashu-aadhaar-count-cattle`; the auto-rollup writer ([ADR-0043](../decisions/0043-auto-rollup-at-canonical-write-time.md)) populates both grains in one adapter run.

The descriptor is intentionally NOT wired into `datasets/taxonomy/topics.json`. `IndicatorChoropleth.svelte` only supports `entity_kind === "state"` today (per the source comment at the top of the file: "the only boundary layer in production that joins by ECI state code"); a national district-grain choropleth (or a district-grain extension to `IndicatorChoropleth`) is the next architectural PR in the livestock B-series. Mounting the district descriptor on a topic page before that renderer lands would create a broken citizen surface — the descriptor would load successfully but the renderer would refuse to map it. The descriptor still earns its place in the allowlist because (a) the dispatch helper is now proven on a real district entry, not just a unit-test synthesis, and (b) the moment the district renderer lands, the single one-line `topics.json` insertion is all that's needed to surface it. The order matters: data plumbing first, renderer second, citizen surface third.

## Decisions journal

- **2026-05-11 — Schema bumped 1.0 → 1.1**: added `attribution_geography`, `comparability`, `funding_split`, `implementing_authority`, `methodology_vintage`, `series_breaks`, `icon`. All optional; existing artifacts remain valid. Driven by Governance Strategist agent review which surfaced the comparability fallacy ("installed MW is a siting statistic, not a service statistic") that v1.0 silently allowed.
- **2026-05-11 — Citizen agent walkthrough**: caused these UI changes — coverage caption above the map (was buried in notes); stale-data chip; comparability banner (was implicit in the unread notes); legend gradient bar replacing 5-swatch grid (single eye-stop); notes promoted from slate-500/11px to slate-700/12px; license row separated from provenance row.
- **2026-05-11 — UX agent review**: caused legend redesign + datalist year-tick notches on the time slider + footer reordering by editorial priority.
- **2026-05-14 — Honesty primitives + components (Phase 1+2 of the viz-layer plan)**. Driven by the Jony / Fowler / Hans audit (`TODO/VIZ-LAYER-GAPS-PLAN.md`). The audit found that `series_breaks`, `methodology_vintage`, and `value_kind: "index"` were declared in v1.1 artifacts but the renderer ignored them — citizens saw a +3,400% NSDP "growth" across a base-year splice; WPI's level numbers (155 / 220 / etc.) were read as rupees not as "% of base year"; and direction-asymmetric indicators (lower-is-better IMR, higher-is-better HDI) had no legend cue distinguishing them from neutral indicators.
  - **Phase 1** added `frontend/src/lib/indicator-render.ts` — five pure renderer primitives (`formatTimeLabel`, `splitOnBreaks`, `growthSafeAcross`, `vintageTooltipLine`, `indexAxisHint`) with 33 unit tests. The non-obvious one is `growthSafeAcross`: it returns `null` (not a number) when a break point falls inside (prev, curr], so a vintage-spliced series cannot accidentally publish a base-year jump as if it were real growth. The CPI-Combined regex (`(\d{4}(?:-\d{2,4})?)\s*=\s*100`) extracts base-year captions from existing unit strings without requiring an artifact change.
  - **Phase 2** added `frontend/src/lib/honesty/` — five thin Svelte 5 wrappers over the Phase 1 logic: `RebaseBanner` (above index-series charts, gated on `value_kind === "index"`), `DirectionLegendCue` (↑/↓/↔ glyph + "higher = better" / "lower = better" / "neither direction is good or bad" alongside the legend unit), `SnapshotBadge` (urban-only / rural-only / nominal-prices), `SeriesBreakAnnotation` (SVG dashed line for line charts), `VintageTooltipLine` (tooltip composer). Components are presentation only; pure logic stays in Phase 1 and is the unit-tested layer.
  - **Phase 3.1 wiring decision — push down, not thread up**. `TopicLanding.svelte` is catalogue-driven and does not fetch the indicator artifact (the inner `IndicatorChoropleth` does). Rather than re-fetch the artifact at the topic level, `RebaseBanner` and `DirectionLegendCue` were imported directly into `IndicatorChoropleth.svelte` — `RebaseBanner` self-gates on `value_kind === "index"` and renders nothing for rate / share / count series; `DirectionLegendCue` sits in the legend row and renders the appropriate cue for any direction value. Net effect: a single edit benefits every current and future indicator on every topic page, with zero change to the topic catalogue API. `StackedTrendArtifact` and `IndicatorRanked` retain their own future wiring path; the choropleth was the highest-traffic surface.
  - **Phase 3.1 catalogue additions** (same commit): three new topics — `prices` (7 artifacts, `list: "union"` because monetary policy is RBI/Centre — Hans's mis-framing guard), `transport` (2 artifacts, `list: "concurrent"` because roads are state but FAME-II is centrally driven), `health` (5 artifacts, `list: "state"` because Entry 6 of the State List). The 14 artifacts moved from `frontend/src/contracts/catalogue-coverage.allowlist.json` (where they sat under `phase3-pending` reasons) into the topic catalogue. The drift detector (`catalogue-coverage.test.ts`) verifies neither side regressed.
  - **`indexAxisHint` as a one-stop unit transformer**: when `value_kind === "index"` and the unit string lacks a base caption (e.g. WPI which has been rebased five times), the hint suffix becomes `index (rebased)` and the chart legend shows that instead of the raw unit. This is what surfaces the Hans-style "this is a level, not a price" disclosure into every legend tick without per-indicator code.

- **Deferred to Phase 6A**: icon rendering (schema field is reserved); per-capita derivation when both indicator and denominator are loaded; touch-tap tooltip on `MapChoropleth` (currently mouse-only — see [`docs/architecture/frontend/map.md`](map.md) for the planned change); double-stroke highlight outline.

## Related docs

- [`docs/concepts/cross-state-comparison.md`](../../concepts/cross-state-comparison.md) — what it means to compare states fairly.
- [`docs/architecture/frontend/colours.md`](colours.md) — how the indicator ramp uses the same OkLCh module as the party-colour resolver.
- [`docs/architecture/data-flow.md`](../data-flow.md) — where indicators sit in the build/serve pipeline.
- [`docs/reference/schemas.md`](../../reference/schemas.md) — schema-version table.

## Decisions journal — 2026-05-15

**Phase 3.4 fiscal extension (catalogue-only, no schema or component change).** Wired the seven per-state RBI fiscal components — `state_own_tax_revenue_inr_crore`, `state_non_tax_revenue_inr_crore`, `state_share_central_taxes_inr_crore`, `state_grants_in_aid_inr_crore`, `state_revenue_expenditure_inr_crore`, `state_pension_expenditure_inr_crore`, `state_external_debt_inr_crore` — into the `fiscal` topic of `topic-catalogue.json` between the union deficit quartet and the topic notes. Hans-vetted ordering (state revenue side first, then expenditure, then debt). All seven are absolute ₹Cr with `comparability: comparable_with_normalisation` and `value_kind: currency`, so the existing `IndicatorChoropleth` honesty stack (comparability banner + DirectionLegendCue) handles framing without per-artifact code: `state_external_debt` is the only `lower_is_better` of the seven (cue: "lower = better"), the other six are neutral (cue: "neither direction is good or bad"). Featured=false on all seven — the citizen-facing headlines remain `centre_transfers_to_states_net` (devolution + grants) and `states_combined_gross_fiscal_deficit` (borrowing aggregate); these new ones are contextual decomposition. Per-capita / share-of-GSDP derived ratios (own-tax / GSDP, pension / revenue-expenditure) are deferred to Phase 5 — the topic notes explicitly call this out so a citizen reading the chart knows large-state dominance is sizing, not management. Allowlist `catalogue-coverage.allowlist.json` shrunk 32→25 (only economy + energy phase-3 entries remain). Smoke-verified at `http://localhost:5174/t/fiscal`: all seven sections render, "lower = better" appears once for `state_external_debt`, no new console errors. vitest 9,795/9,795 green; topic-prices Playwright 10/10 still green.

## Decisions journal — 2026-05-15 (continued)

**Phase 3.5 economy + 3.6 energy extensions (catalogue-only).** Wired three state-scope economy artifacts (nsdp_inr_crore [faceted current+constant], per_capita_nsdp_constant_inr, per_capita_nsdp_current_inr) and eight state-scope energy artifacts (state_installed_capacity_total_mw, state_peak_demand_mw, state_peak_met_mw, state_power_requirement_mu, state_power_availability_mu, state_per_capita_availability_kwh, state_per_capita_electricity_consumption_kwh, state_renewable_grid_capacity_mw) into their respective topic blocks. All eleven are state-entity choropleth-compatible; the existing IndicatorChoropleth + RebaseBanner + DirectionLegendCue + comparability-banner stack handles framing without per-artifact code. Featured=true only on state_per_capita_electricity_consumption_kwh (it is comparable_across_states — the headline citizen 'how electrified is daily life here' read); the rest are featured=false contextual decomposition.

**Eight artifacts kept allowlisted with sharper reasons (phase4-pending or permanent).** Five economy + three energy national-entity multi-facet series (GDP-current, GVA-by-industry annual & quarterly, macro-aggregates, primary-energy-supply, final-energy-consumption-by-sector, renewable-potential-vs-installed) all need country-entity renderers (stacked-area, paired-bar, KPI tile) that IndicatorChoropleth cannot honestly substitute for — promoted from phase3 to phase4 with explicit blockers. (The historical `state_per_capita_nsdp_current_inr` shorter-history shard was retired in PR-B6-row7; the RBI-spliced longer history now ships as `economy/per_capita_nsdp_current_inr`.)

**Hans framing in topic notes.** Economy notes now explain the SeriesBreakAnnotation interaction with the spliced _long indicators (FY81→FY26 across four base-year revisions). Energy notes explain why peak demand/met and requirement/availability ship as raw pairs rather than derived shortfall ratios — surfacing both numbers respects citizen agency over which framing answers their question, and keeps us from pre-committing to one ratio.

**Allowlist 25→8.** Drift detector re-validated; vitest 9799/9799 (up 4 from 9795 as drift sees newly-wired ids); /t/economy and /t/energy smoked at http://localhost:5174 — all eleven new sections render, DirectionLegendCue shows "higher = better" on the three citizen-positive series, no new console errors.

## Decisions journal — 2026-05-19 (PR-T row 1.10 proto-ontology)

**Schema v4.3 → v4.4 additive (T-1).** Added eight optional grounding fields to `indicator.schema.json`: `description_short` (≤280 chars, Plain-Facts caption), `short_unit` (compact glyph form for legend chrome), `description_long` (≥description for citizen "Learn more" surface), `derivation_note` (one-paragraph methodology rationale), `source_ref[]` (per-row provenance pin), `valid_period_grain` (`annual_fy` / `monthly` / etc. — explicit obligation), `valid_entity_grain` (`country` / `state` / `district`), `is_input_output_outcome` (governance taxonomy — input = budget, output = service delivered, outcome = citizen welfare). All fields ship `additionalProperties: false`-compatible and validators stay green for the legacy corpus. Paired TS widening in [`frontend/src/lib/indicators.ts`](../../../frontend/src/lib/indicators.ts) `IndicatorMeta` in the same commit per the Tier-A rule. Authority: Hans + Max + Gregor 2026-05-18 vote.

**Party-schema v1.0 → v2.0 breaking (T-2).** Crossed rename of `predecessor_of` → `successor_party_id` and `successor_of` → `predecessor_party_id` in `datasets/schemas/taxonomy-parties.schema.json`. The previous naming inverted the FK direction relative to OWID's `predecessor_*` / `successor_*` convention (predecessor_of pointed FORWARD, which is the opposite of every other genealogy contract). Migrated 32 rows in `datasets/taxonomy/parties.json` and updated the matching test fixture. Major version bump because the rename is cross-cutting and a downstream consumer would silently invert the lineage graph.

**T-3 backfill: 110 short_units + 31 description_shorts.** Wrote a one-shot tool (deleted post-run per CLAUDE.md §3 "no tools/ scratch") that walked all 110 indicator artifacts and added `short_unit` for every row (mechanical via a `_SHORT_UNIT` dict — ALL existing `unit` strings have a compact glyph form). Hand-authored `description_short` for the top-31 citizen-facing indicators spanning all 9 indicator families (one or two per family — the headline that lands on a topic page's choropleth). The tail ~80 indicators remain on the v3 `description` fallback path until their next natural touch — Hans+Max Q3 verdict explicitly rejected auto-stubbed `{title} ({unit})` because tautological captions look authoritative but are factually empty to a citizen AND poison downstream LLM grounding.

**T-4 chart-wrapper wiring.** Two pure helpers in [`indicator-render.ts`](../../../frontend/src/lib/indicator-render.ts):

- `axisUnitLabel(meta) -> short_unit ?? unit ?? ""` — read by the legend swatch row of all three indicator visualizations (Choropleth, Ranked, SmallMultiples) at the slot that used to hard-code `{indicator.unit}`. Result: legend chrome now shows `₹cr` / `₹L cr` / `kWh/cap` / `/1k LB` instead of `INR (crore)` / `INR (lakh crore)` / `kWh per person per year` / `per 1,000 live births`. Smaller, scan-faster, and reserves the H3 + caption real estate for the actual story.
- `legendCaption(meta) -> description_short ?? description ?? title ?? ""` — read by the caption slot beneath each chart's H3 title. 3-tier (not the literal 2-tier from the spec) so the ~79 tail indicators that today render their existing `description` paragraph keep doing so during the per-family backfill window; the top-31 immediately benefit from the tighter Plain-Facts caption; `title` is last-resort defensive fallback. The middle tier becomes dead code once T-5's per-family PR-template gate has driven the tail to full backfill.

`data-testid="indicator-caption"` / `"indicator-legend-unit"` added at each seam for future Playwright assertions. 8 new vitest cases on the two pure helpers (4 on `axisUnitLabel`, 4 on `legendCaption`); test count 9368 / 9368 stays green. svelte-check clean except 2 pre-existing errors in `constituency.test.ts` / `state-overview.test.ts` (unrelated `.retry().status` on `void`).

**T-5 authoring gate (this commit).** Added step 6 to "Adding a new indicator" above: every new indicator artifact MUST populate `description_short` and `short_unit`. The schema fields remain `optional` (so the legacy tail stays valid until per-family backfill) but the human authoring discipline is "required for any new artifact authored after 2026-05-19". The chart wrapper's 3-tier fallback is for migration ergonomics, NOT a license to ship new artifacts without the short caption.

**Why one PR, four commits (1.10 sequencing).** Schema bump (T-1) → contract migration (T-2) → data backfill (T-3) → consumer wiring (T-4) → authoring gate (T-5). Each commit is independently green; the schema-bump and TS-widening pair is atomic (commit `3df5644e`) because schema-version-strict validation would reject mid-state if split. The party-schema rename (T-2) was independent and could have shipped separately; bundled here to keep the proto-ontology context in one PR for review.

**Smoke (CLAUDE.md §13).** Opened http://localhost:5173/, navigated to `/t/economy`; confirmed legend chrome shows `["₹L cr", "₹", "₹cr"]`; confirmed hand-authored `description_short` renders for backfilled indicators (`Gross State Domestic Product at current prices, in ₹ lakh crore. The size of each state's economy…`); confirmed `description` fallback still renders for tail (graceful degradation). No new console errors introduced.

**Rejected designs (do NOT re-propose).** (R1) Auto-stub `description_short = f"{title} ({unit})"` for the tail to make the 3-tier fallback a 2-tier: rejected — tautological captions are LLM-grounding poison and citizen-surface noise (Hans+Max Q3 2026-05-18). (R2) Literal 2-tier `description_short ?? title` fallback as spec'd: rejected — would visually regress the ~79 tail indicators whose existing `description` is informative, even though slightly long. (R3) Make the new fields `required` in the v4.4 schema: rejected — would reject the entire existing corpus and require either a v4.4-with-110-backfill mega-commit or a doomed gradual rollout. The "soft-required by authoring discipline, hard-validated at PR review" path is the OWID-aligned pragmatic shape (per /memories/patterns.md OWID-alignment fallback).

## Decisions journal — 2026-05-24 (Q1 elections-topic renderer + PR-2 `default`-field retirement)

PR #193 (merge commit `c8700b4f`) landed two coordinated changes against the same data spine: the `/s/<state>/t/elections` renderer was widened to render election artifacts (not just indicators) and the now-redundant `default: true` boolean on `election-events.json` rows was retired in favour of computing the per-state default at read time via `max(polled_on)`.

**Q1 — polymorphic artifact dispatch reaches the elections topic.** [IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR §3](../../../TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) decided in 2026-05-11 that catalogue artifacts dispatch on a `kind` field (`indicator` | `feature_collection` | `election`). The first two kinds shipped immediately; the `election` kind sat in the schema until PR #193 because the elections topic was previously rendered by hand-baked code that read `topic.notes` as citizen prose and resolved the per-state default event via the hand-authored `default: true` flag. PR #193 makes the elections topic conform to the same shape every other topic uses:

- [StateTopic.svelte](../../../frontend/src/routes/StateTopic.svelte) now dispatches on each artifact's `kind`. `indicator` and `feature_collection` paths are unchanged; the new `election` branch lazy-loads the `election-events.json` catalogue (cached single-Promise via [`election-events.ts`](../../../frontend/src/lib/election-events.ts)), resolves the default event for the page's state via `defaultEventForState(state_code)`, and renders a header card (citizen-friendly `display` + `polled_on` + CTA into `/lab/<state>/<event>`) followed by a collapsed-by-default `<details data-testid="election-topic-others">` list of the other events on file. The empty-state copy is honest ("No election data on file yet for this state") rather than a 404.
- Topic-catalogue schema bumped v1.3 → **v1.4**: `id` becomes conditionally required (only when `kind ∈ [indicator, feature_collection]`). The election artifact entry carries `kind: "election"` + `display: "Latest assembly election"` + `scope: "state"` — no hardcoded `event_id`. The concrete event id is computed per visiting state at read time.
- The `notes` field on the elections topic in `topics.json` (a 5-paragraph operator narrative about provenance) was removed. Citizen-bleed: operator notes about data status do not belong on the citizen surface.

**Q1 collateral — new `/s/<state>/elections/<event>` route.** [StateElection.svelte](../../../frontend/src/routes/StateElection.svelte) renders the per-state per-event landing page: breadcrumb (`state → Elections → <event display>`), `<dl>` with Event / Polled on / Data status, and three CTAs — "View constituency-level results →" (`/lab`), "Compare across states →" (`/compare`), "See state's other data →" (`/s/<state>`). Honest 404 panels for unknown slugs and unknown event ids (no fall-through to the home page). The Grammar B path `/s/<state>/elections/<event>` is what ships today; the Grammar A end-state per [ADR-0037](../decisions/0037-url-grammar-drop-india-prefix.md) drops the `/s/` prefix to `<state>/elections/<event>`. Builder helper `url.stateElection(stateCode, eventId)` exists today on the legacy [`url.ts`](../../../frontend/src/lib/url.ts) and will move to `links.ts` in the Grammar A migration's Phase 2.

**PR-2 — `default: true` field retired.** Driven by PR #191's discovery that eight states (Meghalaya, Tripura, UP, Uttarakhand, Punjab, Goa, Gujarat, Karnataka) silently rendered the wrong default event because their on-disk rows had no `default: true` set and the selector fell through to `rows[0]` (the oldest event, since the catalogue was authored oldest-first). PR #191 fixed the selector to use `max(polled_on)`; PR #193 retires the now-dead field across the spine:

- `election-events.schema.json` v1.0 → **v1.1 (breaking)**: `default` boolean removed from the row shape. Changelog entry has full rationale and reversal path.
- `datasets/taxonomy/election_events.json`: all 23 `"default": true` lines stripped; `$schema_version` 1.0 → 1.1.
- `backend/yen_gov/canonical/election_events_seed.py`: `_Event.default` field dropped; the at-most-one-default Pydantic raise removed; `is_default BOOLEAN NOT NULL` column dropped from the Parquet emit (`SCHEMA_VERSION` 1.0 → 1.1).
- [`frontend/src/lib/election-events.ts`](../../../frontend/src/lib/election-events.ts): `ElectionEventRow.default?: boolean` removed from the type; `defaultEventForState` docstring records the `max(polled_on)` rule + the OLDEST-fallback bug it replaced.
- Tier-A test swap: retired `test_compile_rejects_two_defaults_per_state` (asserted the at-most-one invariant on the dropped field); retired `test_election_events_default_uniqueness` (the corpus-level uniqueness gate). Replacement: new `test_compile_rejects_unknown_default_field` — a symmetric `extra="forbid"` guard against any legacy fixture (in-tree or downstream) re-introducing the dead field via Pydantic.

**Collateral — `INDICATOR_TOPIC_TAGS_ROW_SCHEMA_VERSION` 1.0 → 1.1.** The topic-catalogue v1.4 bump made `artifact_id` conditionally optional on artifact entries; the M:N tag table that mirrors topic ↔ indicator membership inherits the same NULLABLE-`artifact_id` shape. The lockstep version bump prevents the two contract surfaces from diverging.

**Rejected designs (Q1, do NOT re-propose).**

- **(QR1) Bake the concrete `event_id` literal into `topics.json`.** A first-pass draft of the elections artifact entry had `{ kind: "election", id: "AcGenMay2026", display: "Tamil Nadu Assembly · May 2026" }` — literally an `AcGenMay2026` hardcode in the catalogue, mirroring the rejected pattern from IA-RESET's example block. Rejected because every state needs a per-state default event but `topics.json` is global. Either we ship one global default (which is the Federal Falsehood — [ADR-0023 §rejected-N=1](../decisions/0023-election-event-identity-per-place.md)), or we duplicate the artifact entry 31 times under a per-state branch (which the catalogue schema doesn't support and shouldn't — the catalogue is the *topic* contract, not the per-state-per-topic contract). The chosen shape — `kind: "election"` + `scope: "state"`, no event_id — defers concrete resolution to read time, where the state context is available.
- **(QR2) Keep `topic.notes` as a citizen-facing prose strip rendered above the artifact list.** Rejected because the existing 5-paragraph note on the elections topic was operator documentation (data-status framing, ECI publication delays, federal-falsehood reminder) — useful in the catalogue file as a reviewer's anchor, useless and noisy on the citizen surface. Citizen-bleed (CLAUDE.md §0). The future-honest path for citizen-facing topic context is a hand-authored intro paragraph composed at design time per topic, not the operator's working notes.
- **(QR3) Render election artifact for non-state scopes (country, district).** Rejected for the same reason ADR-0023 §Federal-Falsehood rejects a global election picker: there is no national election (each state's cycle is its own). The `election` artifact carries `scope: "state"`; the StateTopic renderer asserts the scope matches before rendering and silently skips the artifact otherwise. A country-scope or district-scope election renderer is not on the roadmap and would need its own ADR if proposed (the constitutional-honesty cost is non-trivial).
- **(QR4) Add a `<select>` event picker on `/s/<state>/t/elections` next to the header card, defaulting to latest.** Rejected — would duplicate the picker contract already present on `/s/<state>` (the per-state event picker per ADR-0023 Addendum 2026-05-13). The topic page is a *topic*, not the elections landing; if the citizen wants to switch events, the cleaner gesture is the URL (`/s/<state>/elections/<event_id>`) or the existing per-state picker on the state hub. The collapsed `<details>` "Other elections on file" list on the topic page is the lightweight discovery surface, not a control.

**Rejected designs (PR-2, do NOT re-propose).**

- **(2R1) Keep `default: true` but fix the loader's fallback (e.g. sort by `polled_on DESC` before `rows[0]`).** Rejected because the bug isn't the loader's tie-breaker — it's that the field exists at all. As long as `default: true` is in the schema, every new event row has to either set it (and we have to clear the predecessor row in the same commit) or leave it unset (and rely on the loader's tie-breaker). The first path is error-prone (the 8 silently-wrong states were exactly this class of error); the second path makes the field decorative, which CLAUDE.md §10 explicitly forbids ("no magic strings / decorative fields"). Computing the default from `max(polled_on)` is deterministic, requires zero per-row maintenance, and survives any future event-addition correctly.
- **(2R2) Soft-retire (mark the field deprecated in v1.0 changelog, leave it readable for one release cycle).** Rejected as Holy Law #5 violation (no band-aids). Soft-retire would mean the seed code, the row type, and 23 on-disk rows still carry the field, the loader still reads it, the citizen surface still depends on it being correct — for a strangler-fig window with no clear endpoint. The selector swap in PR #191 already silenced the field's runtime effect; PR #193 deletes the now-truly-dead carrier in lockstep. Reversal cost is bounded: re-adding the field would be another breaking schema bump, but the bug it caused (OLDEST-fallback for unflagged states) would also return.
- **(2R3) Replace `default: true` with a new explicit `default_for: ["S22", "S29"]` array on each event row.** Rejected — same maintenance trap as 2R1 with extra coupling (now the catalogue authors have to know which states' defaults they own, not just whether *this* event is one state's default). And the array is still hand-authored, still drift-prone, still a magic value.

**Deferred (Jony / Hans / future work; track in [handover-2026-05-11.md](../handover-2026-05-11.md) §follow-ups).**

- **Election timeline strip on `/s/<state>/t/elections`.** A chronological visualisation showing all events on file for the state (chips along a date axis, current event highlighted) would be a stronger citizen surface than the current "header card + collapsed details" pattern. Deferred because the `<details>` collapsed list is a workable v1 and the chip-strip overlaps in scope with the deferred B4 history-routes plan in handover-2026-05-11.md item #4 (see below). Promote when ≥1 state crosses 4+ events on file.
- **"Next election due" countdown chrome.** [election-events.schema.json](../../../datasets/schemas/election-events.schema.json) carries `term_end_estimated` (typically `polled_on + 5 years`); a slim banner in the final year of a term would be a meaningful civic surface. Deferred because the surface needs Hans+Jony design pass (where it sits, what it says when an election is overdue, how it interacts with the "Latest election" recency banner per ADR-0023 §Decision/3).
- **Government-card cross-link on the StateElection page.** Per [ADR-0023 §Doctrine](../decisions/0023-election-event-identity-per-place.md), election is the cause and government is the consequence. The new `/s/<state>/elections/<event>` page currently links forward to `/lab` (results) and `/compare` (cross-state); it does NOT link sideways to "the government this election produced" on `/s/<state>`. Deferred because the government-card on `/s/<state>` indexes by current term, not by elected-via-event, and the mapping is non-trivial for the cohort-event cases (Lok Sabha 2024 elected MPs, not state governments). Needs an editorial decision before wiring.
- **Render election results inline on the topic page (party-bar / seats-donut / turnout %).** Today the topic page shows event identity only; the actual results are one click away on `/lab/<state>/<event>`. A summarised preview (top 3 parties by seats, turnout pill, women-elected pill) on the topic page would shorten the citizen path. Deferred because the preview is real component work, not a catalogue/renderer tweak, and would need a Tier-A contract test against `dim_acs` / `elections_candidacies` to prevent silent drift.
- **Promote turnout %, women candidates %, party-share etc. to first-class `indicator` artifacts under the elections topic.** Today these live as derivable facts in the per-event Parquets but not as catalogue entries the StateTopic renderer can dispatch on. Promoting them would let the elections topic render `[election header card] + [turnout choropleth] + [women-elected ranked list] + ...` via the existing polymorphic dispatch, with zero new component code. Deferred because the canonical-store pivot for elections (TODO/20260517-canonical-long-format-pivot.md) needs to land first so the indicators have a proper Parquet home.
- **Topic-grid `/t/elections` page (cross-state).** The `/s/<state>/t/elections` per-state path now dispatches the election artifact; the global `/t/elections` page does NOT yet (it has different renderer wiring under [TopicLanding.svelte](../../../frontend/src/routes/TopicLanding.svelte)). Deferred because the cross-state question on elections is "which states polled most recently / how does turnout compare nationally" — which is the indicator-promotion path above, not the per-event-card path.

**Five gates green** (per CLAUDE.md §9). `bun run check` (svelte-check) 0/7. `bun run test` (vitest) 1726/6/0 across 92 files. `python -m yen_gov validate --root .` OK. `pytest -q` 882/41/0. §13 browser smoke on 5 routes (TN/HP/BR `/s/<state>/t/elections` + `/s/tamil-nadu/elections/AcGenMay2026` deep-link + `/s/tamil-nadu/elections/AcGenUnknown` 404 panel). The HP regression is the headline confirmation: `/s/himachal-pradesh/t/elections` now correctly resolves AcGenNov2022 (2022-11-12) via `max(polled_on)`, bypassing the previously-stale `default: true` that pointed at the OLDER AcGenNov2017.

