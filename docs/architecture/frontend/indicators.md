# Indicator system

> **Status**: live as of 2026-05-14. Schema `indicator.schema.json` v1.2; renderers `IndicatorChoropleth.svelte` (default trio) and `StackedTrend.svelte` (facetted). First consumers: `energy/installed_mw_by_state` (choropleth on TN/KL/AS/WB state hubs) and `energy/installed_capacity_by_source_mw` (stacked-trend on `/t/energy`, composed by `backend/yen_gov/composers/energy_capacity_by_source.py` per ADR-0024).
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

The `energy/installed_mw_by_state` artifact is the canonical *cautionary tale*:
- It rolls plant nameplate capacity by the state in whose polygon the plant sits.
- Much of TN's capacity (e.g. Kudankulam) feeds the southern grid and serves multiple states.
- Therefore: `attribution_geography: "where_produced"` and `comparability: "not_comparable_across_states"`.
- The renderer surfaces an amber banner above the map: *"Read this carefully · This map shows where the asset is sited, not who uses it. Ranking states by this number is misleading."*
- The footer surfaces the methodology vintage: *"OpenStreetMap-derived plant inventory snapshot, community-curated; cross-referenced against CEA broad-strokes only."*
- The notes paragraph promotes the v1 limitation explicitly: *"v1: rollup is restricted to TN, KL, AS, WB. Of 35 states/UTs, only 4 render on this map; the other 31 appear grey because we lack data, not because they have zero capacity."*

A v2 ingest (CEA monthly Installed Capacity report → all states + proper methodology) is documented in [`docs/research/energy-power-plants.md`](../../research/energy-power-plants.md). The schema and renderer are ready for that swap with no UI changes.

## Adding a new indicator

1. Pick a category and id: `<category>/<verbose_snake_id>`. Example: `health/imr_per_thousand_births`.
2. Create `datasets/indicators/in/<category>/<file>.json` with the shape above.
3. Always set `attribution_geography` and `comparability` honestly. If unsure, default to `not_comparable_across_states` and explain in `notes`.
4. Set `direction` from the citizen's POV: lower IMR is better, so `lower_is_better` → red ramp.
5. Set `value_kind` to match how the value should be formatted. For "per 1000 births" pick `rate` with `unit: "per 1000 births"`.
6. Run `python -m yen_gov validate` to confirm schema + version compliance.
7. Wire it into `StateOverview.svelte` (or a dedicated indicators page) by passing `indicator_path` to `IndicatorChoropleth`. **No new component code is needed.**

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

## Decisions journal

- **2026-05-11 — Schema bumped 1.0 → 1.1**: added `attribution_geography`, `comparability`, `funding_split`, `implementing_authority`, `methodology_vintage`, `series_breaks`, `icon`. All optional; existing artifacts remain valid. Driven by Governance Strategist agent review which surfaced the comparability fallacy ("installed MW is a siting statistic, not a service statistic") that v1.0 silently allowed.
- **2026-05-11 — Citizen agent walkthrough**: caused these UI changes — coverage caption above the map (was buried in notes); stale-data chip; comparability banner (was implicit in the unread notes); legend gradient bar replacing 5-swatch grid (single eye-stop); notes promoted from slate-500/11px to slate-700/12px; license row separated from provenance row.
- **2026-05-11 — UX agent review**: caused legend redesign + datalist year-tick notches on the time slider + footer reordering by editorial priority.
- **Deferred to Phase 6A**: icon rendering (schema field is reserved); per-capita derivation when both indicator and denominator are loaded; touch-tap tooltip on `MapChoropleth` (currently mouse-only — see [`docs/architecture/frontend/map.md`](map.md) for the planned change); double-stroke highlight outline.

## Related docs

- [`docs/concepts/cross-state-comparison.md`](../../concepts/cross-state-comparison.md) — what it means to compare states fairly.
- [`docs/architecture/frontend/colours.md`](colours.md) — how the indicator ramp uses the same OkLCh module as the party-colour resolver.
- [`docs/architecture/data-flow.md`](../data-flow.md) — where indicators sit in the build/serve pipeline.
- [`docs/reference/schemas.md`](../../reference/schemas.md) — schema-version table.
