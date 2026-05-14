# StackedTrend chart

> **Status**: design draft 2026-05-14 (Level-4 cross-cutting), revised after Gregor / UI-UX / Citizen review same day. Confidence target ≥ 90% before code. Component target path: [`frontend/src/lib/charts/StackedTrend.svelte`](../../../../frontend/src/lib/charts/).

## What it is

A **single** Svelte component that renders ordered categorical bars stacked by sub-category. Same component, three first-day domains:

1. **Election trend per constituency** — bars are elections (2009 LS, 2014 LS, 2019 LS …); segments are parties; values are votes.
2. **Energy mix per state** — bars are states; segments are fuel types (coal, hydro, solar …); values are MW. Single-snapshot today; future per-year version uses the same component with no API change.
3. **Fiscal composition per year** — bars are FYs; segments are budget heads; values are ₹ crore.

The component is the **third sibling** of the indicator-renderer family — alongside [`IndicatorChoropleth`](../../../../frontend/src/lib/IndicatorChoropleth.svelte) (spatial snapshot) and [`IndicatorRanked`](../../../../frontend/src/lib/IndicatorRanked.svelte) (spatial rank). It reads the same [`indicator.schema.json`](../../../../datasets/schemas/indicator.schema.json) (bumped to v1.2 by this change), surfaces the same honesty banners, and reuses the same OkLCh colour module.

## Why now (and why generic)

The trigger was a citizen request to see "party vote share over multiple elections in my constituency" as a stacked bar. The naive solution is a one-off `ConstituencyVoteHistory.svelte`. We are not doing that. Per [`indicators.md`](../indicators.md) §"Why one component, not many", per-indicator forks defeat citizen consistency and honesty enforcement.

The same chart shape (X = ordered periods, Y = quantity, segments = sub-categories with rollup) shows up in elections, energy mix, fiscal heads, scheme outlays, sector employment, demographic age-bands. One primitive serves them all.

## Position in repo

Creates a new subfolder convention `frontend/src/lib/charts/`. Existing chart components stay flat in `lib/`; migrating them is out of scope (tracked as follow-up — see [Decisions journal](#decisions-journal)). The migration trigger is `lib/charts/` reaching ≥ 3 inhabitants.

```
frontend/src/lib/charts/
  StackedTrend.svelte                 # presentational component
  StackedTrend.test.ts                # vitest cases against view-model fixtures
  stacked-trend/
    types.ts                          # canonical view-model TS type + zod schema
    types.test.ts                     # zod-validation cases
    rollup.ts                         # global-union top-N + coverage-ceiling rollup (pure)
    rollup.test.ts                    # vitest unit tests for rollup
    headline.ts                       # headline strategy registry
    headline.test.ts
    adapter-indicator.ts              # indicator.json → StackedTrendModel
    adapter-indicator.test.ts
    adapter-elections.ts              # multiple constituency-results → StackedTrendModel
    adapter-elections.test.ts
    color-resolver.ts                 # uses colors.forSetIn(domain, codes)
config/charts/
  stacked-trend.json                  # tunable knobs (cutoff %, max categories, etc.)
datasets/schemas/
  stacked-trend-config.schema.json    # validates the config above
  dimensions.schema.json              # validates dimensions registry
datasets/reference/
  dimensions.json                     # registry of every dimension key the chart accepts
backend/yen_gov/composers/
  energy_capacity_by_source.py        # NEW backend Aggregator (per ADR-0024)
datasets/indicators/in/energy/
  installed_capacity_by_source_mw.json  # NEW composed indicator (facetted)
```

The new docs page (this file) lives at `docs/architecture/frontend/charts/stacked-trend.md`. Sibling subsystem docs at `docs/architecture/frontend/colours.md`, `indicators.md`, `map.md`. Adding `charts/` as a sub-folder mirrors the new code subfolder.

## Schema impact (indicator schema bump 1.1 → 1.2)

This change bumps `indicator.schema.json` from **1.1 → 1.2**. Additive only (no existing artifacts break):

- `indicator.chart_type` (optional enum) — declares which renderer to use: `"choropleth" | "ranked" | "stacked-trend"`. When absent, `IndicatorChoropleth` remains the default per the existing convention. Per Gregor S5: makes the catalogue → renderer mapping explicit instead of buried in page code.
- `indicator.default_mode` (optional enum) — `"percent" | "absolute"` for stacked-trend renderer; ignored by other renderers. Per UI-UX M2: lets the artifact declare what's sensible (energy-mix-per-state defaults to `percent`; capacity-comparison-across-states wants `absolute`). User toggle persists in URL only.

Both schema fields land in the same commit as the new chart, with the standard `x-changelog` entry. Validator catches any artifact whose `chart_type` is `"stacked-trend"` but lacks `facet` rows.

## The canonical view-model

The component takes one object. It is **never persisted** (lives only in memory at render time), so no JSON Schema under `datasets/schemas/`. It IS validated at runtime via **zod** at the adapter→component boundary (per Gregor S1) — a malformed adapter output is caught in dev and in vitest contract tests, not at render time.

```ts
// frontend/src/lib/charts/stacked-trend/types.ts

import { z } from "zod";

export const StackedTrendCategory = z.object({
  /** Stable ID. ECI party code for parties, "coal"/"hydro" for fuels, etc. */
  id: z.string().min(1),
  label: z.string().min(1),
  /** Optional pre-resolved fill hex; otherwise resolved via colour resolver. */
  fill: z.string().regex(/^#[0-9a-f]{6}$/i).optional(),
  /** Optional sort weight (lower = closer to baseline). Stable across all bars. */
  order: z.number().optional(),
});

export const StackedTrendSegment = z.object({
  /** FK → StackedTrendCategory.id; the catch-all "Other" uses category id "__OTHER__". */
  category_id: z.string().min(1),
  /** Absolute value in declared unit. NEVER pre-percent. Null when availability != "present". */
  value: z.number().nullable(),
  /**
   * Generic three-state availability (per Gregor M3):
   *   "present"        — value is real, citizen can rely on it.
   *   "missing"        — series is normally there but data is unavailable for this bar.
   *   "not_applicable" — series structurally doesn't exist here (party didn't contest;
   *                      fuel category didn't exist that year; scheme not yet launched).
   * Default: "present".
   */
  availability: z.enum(["present", "missing", "not_applicable"]).default("present"),
  /** Optional per-cell explanation surfaced in tooltip / footnote. */
  availability_label: z.string().optional(),
});

export const StackedTrendBar = z.object({
  /** Stable ID for this period (e.g. "AcGenMay2026", "S22", "FY2024-25"). */
  period_id: z.string().min(1),
  /** Display label, two lines allowed (e.g. "2026\nAssembly"). */
  period_label: z.string().min(1),
  /** Sort key, ascending. Required — the chart never invents an order. */
  order: z.number(),
  /** Period taxonomy (NOT chart rendering mode): "loksabha"|"assembly"|"snapshot"|"fy". */
  kind: z.string().optional(),
  /** All segments at this bar. May omit segments where availability == "not_applicable" if adapter chooses. */
  segments: z.array(StackedTrendSegment),
  /** Optional total override (when source data ships a known total separate from sum). */
  total: z.number().optional(),
});

export const StackedTrendHonesty = z.object({
  comparability: z.enum(["comparable_across_states", "comparable_with_normalisation", "not_comparable_across_states"]).optional(),
  attribution_geography: z.enum(["where_produced", "where_consumed", "where_billed", "where_resident", "where_administered"]).optional(),
  methodology_vintage: z.string().optional(),
  series_breaks: z.array(z.object({
    at_period_id: z.string(),
    kind: z.string(),
    note: z.string(),
  })).optional(),
  /** Per Gregor S4 — fiscal/unit changes mid-window. */
  unit_changed_at: z.array(z.object({
    at_period_id: z.string(),
    from_unit: z.string(),
    to_unit: z.string(),
    note: z.string(),
  })).optional(),
  notes: z.string().optional(),
}).optional();

export const StackedTrendHeadline = z.object({
  /** Strategy enum, even if v1 only ships max_latest_with_streak. (Per Gregor M4.) */
  rule: z.enum(["max_latest_with_streak", "designated", "max_lifetime", "none"]),
  /** Computed line. Empty string means "no clean story; render neutral label instead". */
  text: z.string(),
  /** Sub-line ("DMK 42% → 51% over 5 elections"). Empty if no clean trend. */
  so_what: z.string().optional(),
  /** Optional party/category id for tinting the headline pill. */
  highlight_category_id: z.string().optional(),
}).optional();

export const StackedTrendModel = z.object({
  unit: z.object({
    id: z.string(),
    label: z.string(),
    value_kind: z.enum(["count", "currency", "rate", "share", "raw"]),
  }),
  x_axis_label: z.string(),
  /** Sort policy declared for this view; chart respects it. */
  bar_sort: z.enum(["by_order_ascending", "by_total_descending", "by_pinned_then_order"]).default("by_order_ascending"),
  /** Stable category set, post-rollup. Includes the synthetic __OTHER__ if present. */
  categories: z.array(StackedTrendCategory).min(1),
  /** Bars in render order (already sorted per bar_sort). */
  bars: z.array(StackedTrendBar).min(1),
  /** Pre-computed headline. Adapter decides; chart renders honestly. */
  headline: StackedTrendHeadline,
  /** Indicator-style metadata for honesty banners. */
  honesty: StackedTrendHonesty,
  /** Provenance, mandatory per CLAUDE.md §12. */
  sources: z.array(z.object({
    url: z.string().url(),
    fetched_at: z.string(),
    name: z.string().optional(),
    authority: z.string().optional(),
  })).min(0), // empty array allowed (hand-authored composed views)
  /** Dimension key (must match an entry in datasets/reference/dimensions.json — per Gregor S2). */
  dimension: z.string().min(1),
  /** Mode the adapter recommends; chart starts here unless URL overrides. */
  default_mode: z.enum(["percent", "absolute"]).default("percent"),
});

export type StackedTrendModel = z.infer<typeof StackedTrendModel>;
```

The runtime validation runs at adapter exit in dev/test (`StackedTrendModel.parse(model)`); in prod it's a no-op pass-through (parse cost is negligible at the data sizes we expect, but the gate exists so prod never silently renders garbage).

## Data flow

```
elections JSON (N files)  ─┐
                            ├─ adapter ─→ StackedTrendModel ─→ <StackedTrend />
indicator.json (1 file,    ─┘     │                                 │
  with facet rows)                │                          colours via
                                  │                    colors.forSetIn(dimension, codes)
                                  └─ runtime zod validation
                                     in dev/test
```

For the energy proof-of-value, **no multi-file adapter is shipped**. The backend composer (`backend/yen_gov/composers/energy_capacity_by_source.py`) emits a single `installed_capacity_by_source_mw.json` artifact with `facet` rows; the indicator-adapter reads ONE file. See [ADR-0024](../../decisions/0024-backend-aggregator-for-facetted-indicators.md) (created with this change) for the full rationale on why this is backend Aggregator territory, not adapter territory.

## Dimensions registry (per Gregor S2)

`datasets/reference/dimensions.json` is the closed enumeration of every `dimension` value the chart accepts:

```json
{
  "$schema": "https://yen-gov.github.io/schemas/dimensions.schema.json",
  "$schema_version": "1.0",
  "sources": [],
  "dimensions": [
    { "id": "party",         "label": "Party",                       "anchor_module": "anchors-party.ts" },
    { "id": "power_source",  "label": "Power source (fuel type)",    "anchor_module": "anchors-domain.ts" },
    { "id": "expenditure_head", "label": "Expenditure head",         "anchor_module": "anchors-domain.ts" },
    { "id": "generic",       "label": "Generic categorical",         "anchor_module": null }
  ]
}
```

Mandatory registration: at module import time, each anchor module **must** call `registerDimensionAnchors(id, anchorMap)`. An adapter that emits a model with an unregistered `dimension` value triggers a runtime error in dev/test and, in prod, a console error + grey-fallback render (the component degrades, doesn't crash). This is the failure mode the dimensions registry exists to prevent — silent fall-through to an unstyled chart.

## Top-N + coverage-ceiling rollup

Recommendation: **global union with per-bar floor**, applied in the **adapter** (not the component, not the backend).

The rule: take every category that appears in any bar's "top-N until cumulative ≥ ceiling%" set. The union becomes the named set. Within each bar, anything outside the union collapses into `__OTHER__`.

Why global, not per-bar: per-bar coverage gives clean math per column, but a category can flip in/out across bars (a colour disappears from one bar to the next). The eye loses the trend, which is the whole reason the chart exists.

Why in the adapter: cutoff (~85%) and max-categories cap are tunable knobs (Holy Law #6), owned by `config/charts/stacked-trend.json`. The component must stay dumb so it can be unit-tested against fixtures without taxonomy knowledge.

Why not in the backend: the cutoff is a *view* decision, not a fact about the data. A researcher view might want 99%; a citizen view wants 85%. Backend pre-rolling commits the data to one rendering.

**Scale boundary** (per Gregor APPROVED note): the adapter assumes O(10⁴) cells (~36 entities × 30 periods × 14 series). Beyond that, escalate to backend pre-composition. Not a v1 concern.

Config shape (validated by `stacked-trend-config.schema.json`):

```json
{
  "$schema": "https://yen-gov.github.io/schemas/stacked-trend-config.schema.json",
  "$schema_version": "1.0",
  "sources": [],
  "defaults": {
    "coverage_ceiling": 0.85,
    "max_named_categories": 10,
    "min_segment_pct_for_inline_label": 0.06,
    "min_segment_pct_for_leader_label": 0.03,
    "min_segment_height_px_for_inline_label": 18,
    "min_segment_height_px_for_leader_label": 12,
    "other_position": "top",
    "stack_order": "by_largest_descending"
  },
  "domain_overrides": {
    "party":           { "coverage_ceiling": 0.85 },
    "power_source":    { "coverage_ceiling": 0.95, "max_named_categories": 8 },
    "expenditure_head":{ "coverage_ceiling": 0.80 }
  }
}
```

## Headline strategy (per Gregor M4 + Citizen #1)

Headline rule is enum-typed, even though v1 only implements `max_latest_with_streak`:

| Rule | Trigger | Example output |
|---|---|---|
| `max_latest_with_streak` | Most-recent-period winner has ≥ 4-of-N or ≥ 3-period streak | "DMK won Chennai Central in 4 of the last 5 elections" |
| `designated` | Adapter passes a fixed text | (manual override) |
| `max_lifetime` | One category dominates ≥ 60% of total across all bars | "Coal accounts for 51% of TN's installed capacity" |
| `none` | No clean story | "" (empty — chart renders neutral label) |

When `text` is empty, the page renders a **neutral one-line label**: e.g. "Chennai Central — last 5 assembly elections" with a small coloured pill showing the most-recent winner. No fabricated story (Citizen explicit ask).

The `so_what` sub-line follows the `value_kind` template (per UI-UX S6):

| `value_kind` | so_what format |
|---|---|
| `share` | `"DMK: 42% → 51% (+9pp over 5 elections)"` |
| `count` | `"DMK: 320k → 450k votes (+41% over 5 elections)"` |
| `currency` | `"₹X cr → ₹Y cr (+Z% over N years)"` (auto-promote ₹cr → ₹lakh-cr above 100k) |
| `raw` (e.g. MW) | `"50 GW → 95 GW (+90% since 2014)"` (auto-promote MW→GW above 1000) |

Direction arrow uses the indicator's `direction` field to tint green/red/grey. Arrow + number do the work; colour is reinforcement.

## Colour resolution

Extend the existing OkLCh resolver. **Do NOT introduce a new palette.** Earlier exploratory advice recommending Observable 10 was wrong; the existing module already does perceptual colour math correctly and is citizen-tested.

### Plan

1. Generalise `partyColour` → `categoryColour(code, inUseCodes, dimensionAnchors, overrides)`. Existing `partyColour` becomes a thin wrapper supplying `PARTY_ANCHORS`.
2. Add `frontend/src/lib/colors/anchors-domain.ts` with anchor maps:
   ```ts
   export const POWER_SOURCE_ANCHORS: Record<string, PartyColor> = {
     coal:       { fill: "#374151", text: "#f3f4f6" },  // slate-700 — coal grey
     gas:        { fill: "#0891b2" },                   // cyan-600  — natural gas
     hydro:      { fill: "#1e3a8a" },                   // blue-800  — deep water (per UI-UX S1)
     nuclear:    { fill: "#a855f7" },                   // purple-500 — radiating
     solar:      { fill: "#f59e0b" },                   // amber-500 — sun
     wind:       { fill: "#10b981" },                   // emerald-500 — turbine
     biomass:    { fill: "#a16207" },                   // amber-700 — burnt organic (per UI-UX M1)
     other_re:   { fill: "#6366f1" },                   // indigo-500 — catch-all renewable
   };
   export const EXPENDITURE_HEAD_ANCHORS: Record<string, PartyColor> = { /* TBD when fiscal ships */ };
   ```
3. Extend `colors` store with `colors.forSetIn(dimension, codes)` returning a `Map<code, PartyColor>` resolved via the registered dimension anchor map then the existing algorithmic OkLCh fallback.
4. The synthetic `__OTHER__` category resolves to **`#9ca3af`** (gray-400, true neutral; not slate-400 — per UI-UX S2). Same colour everywhere; never sorted by value; always at the top of the stack.

### Why these power-source hexes (UI-UX-validated)

- Coal-grey, hydro-deep-blue, nuclear-purple, solar-amber, wind-emerald, biomass-burnt-amber, other_re-indigo are **mnemonic** (citizen reads colour and recalls fuel without looking at legend).
- Hue/lightness separation in OkLCh ensures solar-amber (h≈85°, L≈0.78) and biomass-amber-burnt (h≈55°, L≈0.50) never blur in the same stack.
- Wind-emerald and biomass-burnt-amber are now in different hue families (was a green-on-green collision risk per UI-UX M1).
- Hydro-deep-blue (b800) separates from gas-cyan (c600) by lightness AND hue.
- No cross-collision with party anchors (party reserved bands are 25°-saffron, 230°-INC-blue, 135°-AITC-green, 195°-AAP-cyan; power-source uses 55°/85°/150°/240°/270° — comfortable separation).

## Modes: percent (default) and absolute (toggle)

Default mode comes from the **indicator's `default_mode` field** (per UI-UX M2), not a global chart constant. Energy-mix-per-state defaults `percent`; raw-capacity-comparison-across-states defaults `absolute`. Elections-vote-trend defaults `percent`; seats-trend defaults `absolute`.

The component prop optionally overrides:

```svelte
<StackedTrend {model} mode_override="absolute" />
```

User-driven mode-switch persists in URL only (no localStorage — keeps the citizen's chosen view shareable).

The hover/tap readout ALWAYS shows percent in the headline + absolute in lighter text alongside (per Citizen #4): `DMK: 47% (87k votes)`.

## Special cases

### `availability` (generalised from earlier "did_not_contest")

Three states (per Gregor M3):

- `"present"` — real value.
- `"missing"` — series exists but data unavailable for this bar (CEA data gap, etc.).
- `"not_applicable"` — series structurally absent (party didn't contest; scheme didn't exist).

Visual treatment (per UI-UX M3): **diagonal-hatched empty rectangle** at the colour-key position in the stack, light-grey 45° hatch (`#e5e7eb` over `#f9fafb`) for both `missing` and `not_applicable`, with a `*` marker at the X-tick footnoting the difference. A true `value: 0` with `availability: "present"` draws as a 0-height bar (different signal). The legend's per-category badge uses the citizen-validated phrasing: "Contested 3 of 5" (per Citizen #3) for elections, "Present in 30 of 35 states" for the spatial case, etc.

### Mixed period kinds (Lok Sabha + Assembly)

The component does NOT enforce "don't mix LS and AC". That's a **page** decision: the page using `StackedTrend` for elections instantiates two charts (one for LS, one for AC) or renders a kind-toggle. The component DOES use `bar.kind` for the under-tick label ("2026\nAssembly") and as a hook for future kind-grouped backgrounds; v1 ships only the label.

`bar.kind` is **period taxonomy** (a fact about the period), distinct from chart rendering mode. Future grouped/sankey consumers can use it without coupling to elections semantics.

### Series breaks

Vertical 1px dashed marker (`#9ca3af`, `4,4` dash) at the **midpoint between** affected X-ticks (NOT on a tick — on-tick reads as a year boundary). Above the line, a `†` marker keys to a footnote (per UI-UX S5; rotated text was rejected as visually noisy).

The footnote uses **plain language** (per Citizen #5): "Boundaries changed", not "delimitation" or "methodology change". On tap of the marker:

> "Before 2008, 'Chennai Central' covered different villages/wards. The trends in vote share are still meaningful, but absolute vote counts before and after this line aren't directly comparable. Switching to **percent mode** removes most of this distortion."

When chart mode is `percent`, the footer adds a one-liner: "Showing percent — comparable across the boundary change."

### Mode switch & hover policy (per UI-UX M4)

- **Initial render**: NO entrance animation. Bars draw at final position. Citizen is reading, not being entertained.
- **Mode toggle** (% ↔ abs): 200ms tween on bar heights only; no colour interpolation.
- **Hover**: snap to nearest X-bar (simple band). Un-hovered bars dim to opacity 0.4 over 100ms. Pinned readout panel **above the chart** (NOT a floating tooltip — floating occludes the segments the user is comparing). Panel shows year label + every series value (percent + absolute), plus OTHER and any `not_applicable` labelled.
- **Tap on bar segment** (mobile): same readout as hover, dismissable by tapping outside.
- **Cursor**: `crosshair` on chart area; `pointer` on legend swatches.
- **Legend swatch click**: toggles series visibility (`visible` set persists in URL). Single line of code given the view-model; large payoff for "show me only renewables" (per UI-UX CONSIDER C3).

## Honesty layer (mirrors `IndicatorChoropleth`)

Above the chart:

1. **Headline** (`model.headline.text`) — only when non-empty per the headline-rule logic.
2. **so_what sub-line** (`model.headline.so_what`) — citizen's "what changed" line.
3. **Comparability banner** — same logic as [`indicators.md`](../indicators.md) §"How the metadata drives the UI".
4. **Coverage caption + stale-data chip** when applicable.

Below the chart:

5. **Notes** (slate-700 / 12px).
6. **Methodology vintage + series-break captions** + **unit-change captions** (slate-500 / 11px).
7. **License row.**
8. **Provenance** — collapsed `SourceList` reused. Source labels use **full names + domain** per Citizen #6 (e.g. "Election Commission of India (results.eci.gov.in) — fetched 8 May 2026"), not bare acronyms.

A citizen reading any indicator-style chart on yen-gov sees the same eight signals in the same eight positions.

## Adapters

### `adapter-indicator.ts`

```ts
indicatorToStackedTrend(
  indicator: Indicator,                 // already-fetched indicator.json
  opts: {
    entity_id?: string;                 // when set: time-series of facets for one entity
    time?: string;                      // when set: spatial snapshot of facets across entities
    config: StackedTrendConfig;
    dimension: "power_source" | "expenditure_head" | "generic";
    pin_entity_ids?: string[];          // for spatial mode: pinned bars sort first
  }
): StackedTrendModel
```

Two modes:
- **Temporal mode** (`entity_id` set): bars are unique `time` values; segments are `facet → value`.
- **Spatial mode** (`time` set): bars are unique `entity_id` values; segments are `facet → value`. This is how energy-mix-per-state works.

Both call `rollup.applyGlobalUnion(...)` with the dimension's configured cutoff. Both carry through every honesty field from `indicator.indicator.*`.

### `adapter-elections.ts`

```ts
electionsToStackedTrend(
  results: ConstituencyResult[],        // multiple election snapshots, same constituency
  opts: {
    config: StackedTrendConfig;
    election_kinds?: ("loksabha" | "assembly")[];  // pre-filter
  }
): StackedTrendModel
```

Each `ConstituencyResult` becomes a bar (`period_id = result.election`, `kind = "loksabha"|"assembly"` from the election registry). Segments are parties. Rollup with `dimension: "party"`.

`availability` is computed: a party in the global union but absent from a particular bar's candidates list gets `availability: "not_applicable"` and `value: null`. Sources unioned across all input results.

## Files this change creates / modifies

**New (frontend):**

| Path | What |
|---|---|
| `frontend/src/lib/charts/StackedTrend.svelte` | Component. |
| `frontend/src/lib/charts/StackedTrend.test.ts` | Vitest cases against fixtures. |
| `frontend/src/lib/charts/stacked-trend/types.ts` | Zod schema + TS types. |
| `frontend/src/lib/charts/stacked-trend/types.test.ts` | Zod-validation cases. |
| `frontend/src/lib/charts/stacked-trend/rollup.ts` | Pure rollup. |
| `frontend/src/lib/charts/stacked-trend/rollup.test.ts` | 8+ cases. |
| `frontend/src/lib/charts/stacked-trend/headline.ts` | Strategy registry. |
| `frontend/src/lib/charts/stacked-trend/headline.test.ts` | Per-rule cases. |
| `frontend/src/lib/charts/stacked-trend/adapter-indicator.ts` | Indicator adapter. |
| `frontend/src/lib/charts/stacked-trend/adapter-indicator.test.ts` | Against energy fixture. |
| `frontend/src/lib/charts/stacked-trend/adapter-elections.ts` | Elections adapter. |
| `frontend/src/lib/charts/stacked-trend/adapter-elections.test.ts` | Against TN fixtures across 2 elections. |
| `frontend/src/lib/charts/stacked-trend/color-resolver.ts` | Wraps `colors.forSetIn`. |
| `frontend/e2e/stacked-trend.spec.ts` | Playwright golden path. |

**Modified (frontend):**

| Path | What |
|---|---|
| `frontend/src/lib/colors/party-colour.ts` | `partyColour` becomes wrapper over generalised `categoryColour`. |
| `frontend/src/lib/colors/party-colour.test.ts` | Existing 15 cases stay green; new tests for `categoryColour` + dimension anchors. |
| `frontend/src/lib/colors/store.svelte.ts` | Adds `forSetIn(dimension, codes)` and `fillIn(dimension, code)`. |
| `frontend/src/lib/colors/anchors-domain.ts` (new) | `POWER_SOURCE_ANCHORS`; `EXPENDITURE_HEAD_ANCHORS` placeholder; `registerDimensionAnchors`. |
| One existing route page (TBD: `ConstituencyOverview.svelte` or new) | Wired to elections adapter for proof-of-value. |
| One existing or new page | Wired to energy-mix indicator for proof-of-value. |
| `frontend/package.json` + `frontend/bun.lock` | `zod` added; lockfile regenerated and staged in same commit (CLAUDE.md §9 + §10). |

**New (backend, per ADR-0024):**

| Path | What |
|---|---|
| `backend/yen_gov/composers/energy_capacity_by_source.py` | Aggregator merging the 8 fuel files into one facetted indicator. |
| `backend/tests/test_energy_capacity_composer.py` | Pytest against real fixture. |
| `datasets/indicators/in/energy/installed_capacity_by_source_mw.json` | Composed output (facetted, indicator schema v1.2 with `chart_type: "stacked-trend"`, `default_mode: "percent"`). |

**New (config + reference):**

| Path | What |
|---|---|
| `config/charts/stacked-trend.json` | Tunable knobs. |
| `datasets/schemas/stacked-trend-config.schema.json` | Validates the config. |
| `datasets/reference/dimensions.json` | Dimension registry. |
| `datasets/schemas/dimensions.schema.json` | Validates the registry. |

**Modified (schemas + docs):**

| Path | What |
|---|---|
| `datasets/schemas/indicator.schema.json` | Bumped 1.1 → 1.2 (additive: `chart_type`, `default_mode`). New `x-changelog` entry. |
| `docs/architecture/frontend/charts/stacked-trend.md` | This file. |
| `docs/architecture/frontend/colours.md` | Updated: dimension anchors + mandatory registration section. |
| `docs/architecture/frontend/indicators.md` | Updated: `chart_type` field; how to declare a stacked-trend indicator. |
| `docs/reference/schemas.md` | Indicator-schema v1.2 row. |
| `docs/architecture/decisions/0024-backend-aggregator-for-facetted-indicators.md` (new) | Documents why option B beat option A. |

## v1 scope (what ships)

**In:**

- Component, both modes (percent/absolute), with `default_mode` from indicator.
- Hover (snap-to-band) + tap (mobile) with pinned-above-chart readout (percent + absolute).
- Global-union top-N rollup with config-driven ceiling.
- Dimension anchors for `party` (existing) and `power_source` (new).
- Legend below the chart, full-width, single row wrapping, reverse order to match top-of-stack-first (per UI-UX S3). Swatch click toggles visibility (URL-persisted).
- 3-tier label rule: inline (≥6%, ≥18px), leader-line outside (3–6%, 12–18px), legend-only (<3% or <12px) (per UI-UX S4).
- Series-break vertical markers + `†` footnote.
- Honesty layer (banner / coverage / notes / methodology / unit-change / license / provenance).
- `availability` (3-state) with hatched-rectangle treatment.
- Per Gregor: `headline_rule` enum (one rule implemented: `max_latest_with_streak`).
- Backend Aggregator emitting `installed_capacity_by_source_mw.json`.
- Indicator schema bump 1.1 → 1.2.
- ADR-0024.
- One citizen route wired with elections; one with energy.
- Vitest unit + adapter tests; Playwright golden path; backend pytest for the composer.

**Explicitly out (v1 non-goals — say no now):**

- Animated entrance; only the mode-switch tween (200ms heights) is allowed.
- X-axis brush/zoom.
- Dual-axis (a code smell — make it two charts).
- Per-bar coverage ceiling (rejected; see [Decisions journal](#decisions-journal)).
- Per-indicator forks (rejected on principle).
- Migrating existing flat-`lib/` chart components into `lib/charts/`.
- Per-capita derivation from a denominator indicator (Phase 6A queue).
- Reading colour overrides from a JSON registry under `datasets/reference/in/` instead of TS code (Holy Law #6 debt; see follow-up).
- Multi-comparison overlays (e.g. "show Chennai Central vs Chennai South side-by-side"). Page-level concern, not chart.
- CSV / PNG export.
- Mobile horizontal-bar mode for spatial-many-entities case (energy-by-state on phone). v1 ships best-effort responsive vertical bars; the full mobile UX is a separate piece of work tracked under §14 of CLAUDE.md.
- Print/PDF export.
- Touch-tap detail bottom sheet (separate from segment-tap readout).

## Tests

Per CLAUDE.md §15:

- **Unit (`rollup.test.ts`)**: ~10 cases (single bar, two bars, ceiling exact-hit, max-cap binds before ceiling, empty bar, all-other, ties at cutoff, non-monotonic across bars, all-not-applicable, mixed availability).
- **Unit (`headline.test.ts`)**: per-rule cases including `none` empty-string output.
- **Unit (`types.test.ts`)**: zod accepts canonical fixtures, rejects malformed (missing dimension, bad hex, value+availability mismatch).
- **Unit (`adapter-indicator.test.ts`)**: against the real composed `installed_capacity_by_source_mw.json` fixture; asserts model shape AND that ALL `indicator.indicator.*` honesty fields flow through.
- **Unit (`adapter-elections.test.ts`)**: against two real Tamil Nadu constituency-result fixtures; asserts global-union behaviour, `not_applicable` correctness, and `kind` propagation.
- **Component (`StackedTrend.test.ts`)**: vitest-svelte rendering smoke cases — initial render, mode-toggle, legend toggle (URL bound), hover snap.
- **Contract**: `datasets-conform.test.ts` validates the new composed indicator against schema 1.2; the new config and dimensions registry against their schemas.
- **Backend (`test_energy_capacity_composer.py`)**: pytest against real fuel-file fixtures, asserts composed indicator validates against schema 1.2.
- **End-to-end (`stacked-trend.spec.ts`)**: route loads, no `pageerror`, headline + chart + legend + SourceList present, mode toggle changes Y-axis label, legend swatch click hides a series.

## Decisions journal

- **2026-05-14 — global-union rollup, not per-bar.** Per-bar gives clean math per column but breaks the trend the chart exists to show.
- **2026-05-14 — adapter performs the rollup, not backend, not component.** Backend would prematurely commit to one cutoff; component would need taxonomy knowledge.
- **2026-05-14 — extend the existing OkLCh module; do NOT introduce Observable 10.** Earlier exploratory recommendation was based on incomplete knowledge of the existing colour system.
- **2026-05-14 — no JSON Schema for the view-model; use zod at runtime.** The view-model is in-memory only; CLAUDE.md §11 schemas are for files at rest. Zod gives the runtime contract that §15 Tier 2 expects.
- **2026-05-14 — `default_mode` belongs on the indicator schema, not the chart prop.** Lets the data declare what's sensible per indicator. Schema bump 1.1 → 1.2 (additive).
- **2026-05-14 — `__OTHER__` always at top of stack, slate→neutral grey (#9ca3af).** Citizen learns the convention once.
- **2026-05-14 — `availability` (3-state), generalised from `presence: did_not_contest`.** Per Gregor M3: domain-specific terminology was leaking into the canonical model.
- **2026-05-14 — `kind` on `bar` is period taxonomy, not chart rendering mode.** A fact about the period (LS vs AC), not a hint to the chart. Future consumers can use it without coupling to elections semantics.
- **2026-05-14 — backend Aggregator (option B) for the energy proof-of-value, not a multi-file frontend adapter (option A).** Adapter composing N source files is the wrong layering. ADR-0024 documents the rejected alternative.
- **2026-05-14 — dimension registry mandatory; silent fallthrough to grey is forbidden.** Per Gregor S2/S3.
- **2026-05-14 — headline rule is enum-typed, even though v1 implements one.** Future rule additions become config not refactor.
- **2026-05-14 — headline only when story is clean** (per Citizen #1). 4-of-5+ or 3-period streak. Otherwise empty headline; page renders neutral label.
- **2026-05-14 — full hover/animation policy specified in this doc** (per UI-UX M4). Initial render no animation; mode-switch 200ms heights only; hover snap-to-band with pinned-above-chart readout, NOT a floating tooltip.
- **2026-05-14 — fuel anchors revised**: biomass to amber-700 (`#a16207`), hydro to blue-800 (`#1e3a8a`), to break two visual collisions (wind/biomass green-on-green; gas/hydro blue-on-blue).
- **2026-05-14 — 3-tier label rule** (inline / leader-line / legend-only) instead of two-tier. The 3–6% segment range is common in fuel mix and dropping straight to legend forces colour-matching saccades.
- **2026-05-14 — plain-language source attribution** (per Citizen #6): "Election Commission of India (results.eci.gov.in)" not "ECI".
- **2026-05-14 — "Boundaries changed", not "delimitation"** (per Citizen #5). Plain English everywhere citizen-facing.
- **2026-05-14 — separate adapters per domain**, not one mega-adapter. Different upstream shapes; the rollup is shared.
- **2026-05-14 — new `lib/charts/` subfolder, existing flat charts not moved.** Migration trigger: ≥3 inhabitants under `lib/charts/`.
- **2026-05-14 — ADR-0024 created** for the backend-aggregator decision (meets Holy Law #4 both-tests bar: credible rejected alternative + cross-cutting precedent for every future composed indicator).

## Related docs

- [`docs/architecture/decisions/0020-indicator-artifact-as-data-contract.md`](../../decisions/0020-indicator-artifact-as-data-contract.md) — upstream contract.
- [`docs/architecture/decisions/0024-backend-aggregator-for-facetted-indicators.md`](../../decisions/0024-backend-aggregator-for-facetted-indicators.md) — option-A vs option-B for energy.
- [`docs/architecture/frontend/indicators.md`](../indicators.md) — sibling renderer family.
- [`docs/architecture/frontend/colours.md`](../colours.md) — colour module (will be updated).
- [`docs/concepts/data-provenance.md`](../../../concepts/data-provenance.md) — `sources` array discipline.
- [`CLAUDE.md`](../../../../CLAUDE.md) §§3, 6, 11, 12, 15.
