# The schema is the design system

**Last Updated**: 2026-05-11

This is a permanent guardrail for yen-gov. It captures the UI/UX standing position formalised during the [IA reset](../../TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) (2026-05-11) and made structural by [ADR-0022](../architecture/decisions/0022-place-first-ia-with-topic-catalogue.md).

## Companion doctrine: elections are one indicator family among many

**User-mandated 2026-05-11.** Read this before the schema rule below; it is the framing the rest of the doc lives inside.

yen-gov is not an elections site that happens to also show fiscal data. It is a civic-data site for India in which **social-welfare topics are first-class** — fiscal, education, health, livelihood, infrastructure — and elections are one indicator family alongside them. The default theme of the home India map is a welfare or coverage indicator, never the latest election leader. The catalogue order leads with welfare topics; elections appear in the list, never at the top of it.

This affects the schema-is-the-design-system rule directly: the closed renderer set must serve welfare indicators *first* and elections second. Election-only renderers (`PartyBar`, `SeatDonut`, `ParliamentArc`, etc.) remain a closed set in their own right — fully capable, but not the renderers a cold visitor sees first. If a feature request would make an election-only renderer appear on the home page or as the lead surface anywhere, it is rejected on doctrinal grounds, regardless of how clean the implementation is.

See [ADR-0022](../architecture/decisions/0022-place-first-ia-with-topic-catalogue.md) §Doctrine for the full statement.

## The rule

> **No page exists that renders a single indicator's data with code that no other indicator could reuse.**

If a chart needs custom code, the metadata is incomplete — extend the schema, not the page.

## Why

yen-gov's roadmap calls for 30+ indicators across 8+ topics, maintained by one human + AI assistance. The only way that scales is if adding the 8th fiscal indicator requires no design discussion — just a JSON file.

The opposite world is well-known: a civic-data site where Health has a facility finder, Fiscal has a stacked bar, Energy has a sankey, Demographics has a population pyramid — and each of those is its own micro-product with its own bugs, its own tests, its own designer-time. Five topics in, you have five products and zero compounding.

The contract that prevents this is the indicator schema ([ADR-0020](../architecture/decisions/0020-indicator-artifact-as-data-contract.md)) and the topic catalogue ([ADR-0022](../architecture/decisions/0022-place-first-ia-with-topic-catalogue.md)). Together they declare *what* the data means; the closed renderer set decides *how* it looks. Citizens get consistency; the maintainer gets velocity; honesty caveats (`comparability`, `attribution_geography`, `methodology_vintage`, list-badge, peer-set filter, Union-list banner) propagate structurally instead of being remembered per page.

## The closed renderer set

Every state-hub section, topic landing, and intersection view composes only from this set:

- **`MapChoropleth`** — generic state-level choropleth engine (boundary layer, fills, tooltips, legend gradient).
- **`IndicatorChoropleth`** — `MapChoropleth` driven by an indicator artifact (metadata-driven hue ramp, time slider, comparability banner, source list).
- **`IndicatorRanked`** — generic ranked table with home-state pinning, peer-set filter, honesty banners.
- **`IndicatorSmallMultiples`** — grid of per-state sparklines, shared Y-axis, series-break markers.
- **`TimeSeriesLine`** — single-state or two-state time series. *(Reserved for Phase 6+; not yet shipped.)*
- **`CoverageBadge`** — schema-driven "X of 36 states · Y years" chip.
- **Thin chrome**: `SourceList` (provenance), list-badge (Seventh Schedule), peer-set filter, theme-switch chip, ScopePicker.

Election-only renderers (`PartyBar`, `SeatDonut`, `MarginHistogram`, `RacesBoard`, `ParliamentArc`, `SwingSankey`, `AcStackedBar`, `StateAcMap`) are a closed set in their own right — bound to election data shapes, not extensible per-event.

**New component types require an ADR.** The bar to add a new renderer is high. "Health needs a facility finder because it has lat/lon points" is not enough — points go into `MapChoropleth`'s overlay slot, or they wait until Phase 7+ when a `FeatureCollectionMap` renderer is added by ADR.

## What gets rejected at PR

- Per-topic chrome on `/t/:topic` landings. Every topic landing is `IndicatorChoropleth(default_indicator) + IndicatorRanked + (IndicatorSmallMultiples)` plus standard chrome. Health does not get a facility finder. Fiscal does not get a stacked bar. Energy does not get a sankey.
- Bespoke "TN at a glance" hero on the state hub. The hero, where it exists, composes only from catalogue entries with `featured: true`, rendered via existing `IndicatorChoropleth` thumbnails. No hand-picked KPI tiles. No scrollytelling.
- Per-indicator Svelte components. If you cannot render the indicator with the closed set, the schema is incomplete — extend the schema (additive minor bump), not the page.
- Inline literal section lists. The state hub reads its sections from `topic-catalogue.json`. Adding `"Healthcare"` as a section is a catalogue edit, not a Svelte edit.
- Election-result sections appearing under `/t/:topic` landings. Election artifacts use the polymorphic catalogue dispatch (`kind: "election"`), but the renderer that handles them is the existing election-only set — not the indicator renderers. Cross-contamination of the two render pipelines is rejected.
- Curated, hand-written commentary embedded in artifact files. Editorial honesty fields (`notes`, `methodology_vintage`, `series_breaks`) are structured per ADR-0020. Long-form analysis belongs in `notes/` or a future blog directory, not in `datasets/`.

## How to extend it

When the closed set is genuinely insufficient — and only then — the path is:

1. Demonstrate that ≥2 in-flight or planned indicators need the same new affordance. One-off needs do not justify a new component.
2. Write an ADR proposing the new renderer, naming the metadata fields it consumes (which usually means a minor schema bump per ADR-0020's discipline).
3. Add the new renderer to this doc's closed set.

The order matters: schema first (so the contract describes the affordance), then renderer. Renderer-first additions are how the schema-as-design-system rule erodes.

## Honesty fields are renderer guards, not opt-ins

Because every indicator flows through the same renderers, honesty fields propagate structurally:

- `comparability: not_comparable_across_states` → `IndicatorRanked` suppresses the rank column and renders the amber banner. No per-indicator decision required.
- `attribution_geography: where_produced` → renderer adds the "siting, not consumption" caveat under the chart.
- `methodology_vintage` → rendered as a slate-500 caption below notes, on every chart, every time.
- `series_breaks[]` → time-series renderers refuse to compute trends across the break and surface a dashed marker.
- Catalogue `list: union` → cross-state ranked tables render the Union-list banner before the table.
- Catalogue `peer_set_default` → ranked tables default to the appropriate tier filter.

A future maintainer cannot accidentally publish a Union-list ranking without the banner, or a not-comparable indicator with a rank column. The contract refuses to render dishonestly.

## Indicator id encodes concept + normalisation, never the unit

**Decided 2026-05-11** by the four-persona panel (Architect Hohpe, Governance Strategist, UI/UX Lead, Citizen) — unanimous. Pinned here so the next ingest does not relitigate it.

> The indicator `id` (and its URL slug) identifies **what is measured + how it is normalised** (raw / per-capita / % of GSDP / share of revenue / index). It does **not** identify the **display unit** (₹ Crore vs ₹ Lakh vs ₹ Thousand vs USD). Unit conversions are renderer affordances; denominator changes are new sibling indicators.

Concretely:

| ✅ Allowed | ❌ Forbidden | Why |
|---|---|---|
| `fiscal/net_transfers_from_centre` | `fiscal/net_transfers_from_centre_crore` | Crore is a display unit, not an identity. |
| `fiscal/net_transfers_from_centre_per_capita` (sibling) | `fiscal/net_transfers_from_centre_inr` | Currency is a display unit; the indicator does not change when shown in USD. |
| `fiscal/net_transfers_from_centre_pct_gsdp` (sibling) | `fiscal/net_transfers_from_centre_2024` | Time is a row dimension, not an id dimension. |
| `health/imr_per_1000` (a rate is its denominator-with-units, fine in id) | `economy/gdp_billion_usd` | "billion USD" is presentation; concept is "GDP". |

The indicator artifact carries the unit in the `unit` field (free-form: `"%"`, `"INR (crore)"`, `"MW"`, `"per 100k"`, `"years"`). The renderer's legend / axis formatter is responsible for displaying it. A future "show in ₹ Lakh" or "show in USD" toggle is a thin chrome affordance that mutates a render-time prop; it never swaps the indicator id, never breaks a URL, never forks the artifact.

The test that settles edge cases: *can these two artifacts coexist as different rows in `datasets/indicators/in/`?* `_crore` and `_lakh` cannot — they're the same fact table multiplied by 100. So they must not differ in id. `_per_capita` and `_pct_gsdp` can — they're different numerator-over-denominator constructs with their own honesty fields. So they earn distinct ids.

This rule is part of the design-system contract. A renderer that special-cases on unit (instead of reading `unit` from the artifact) violates this section as much as a renderer that special-cases on indicator id violates *The rule* above.

## See also

- [ADR-0020](../architecture/decisions/0020-indicator-artifact-as-data-contract.md) — the indicator artifact as the generic data contract.
- [ADR-0022](../architecture/decisions/0022-place-first-ia-with-topic-catalogue.md) — the IA spine + topic-catalogue contract that anchors this guardrail.
- [docs/architecture/frontend/indicators.md](../architecture/frontend/indicators.md) — current state of the renderer set.
- [docs/concepts/cross-state-comparison.md](cross-state-comparison.md) — comparison primitives (ranked table first, no composite indices).
