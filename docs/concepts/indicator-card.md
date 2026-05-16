# IndicatorCard

**Last Updated**: 2026-05-16

The per-state card primitive used on `/s/<state>`. One card per indicator artifact in the catalogued topic — replaces the per-artifact `IndicatorChoropleth + IndicatorRanked + IndicatorSmallMultiples` triple that previously rendered on the state hub.

This doc is the formal contract for the card. The component lives at [frontend/src/lib/IndicatorCard.svelte](../../frontend/src/lib/IndicatorCard.svelte) with pure helpers in [frontend/src/lib/indicator-card.ts](../../frontend/src/lib/indicator-card.ts). The plan that motivated it is [TODO/20260515-state-page-ia-rework-plan.md](../../TODO/20260515-state-page-ia-rework-plan.md) §2.

## Why a card, not the triple

The triple-render (choropleth + ranked + small-multiples) answers a cross-state question: *"how do states compare on indicator X?"*. That question is the right one on `/t/<topic>` and `/compare`, where it stays.

On `/s/<state>` the citizen is asking *"how is **my** state doing?"*. The triple buries that answer in three components, each repeating the map's choropleth N times down the page. The card answers it in one glance — big number for this state, sparkline of this state's series, one line of context against the other states — and links out to the India view (`See all states →`) for the citizen who wants more.

This is composition over the existing closed renderer set plus a single sparkline primitive, not a new renderer family. No ADR required ([schema is the design system](schema-is-the-design-system.md)).

## Where it renders

| Route                | Cards | Source of topic list                       |
| -------------------- | ----- | ------------------------------------------ |
| `/s/<state>`         | All artifacts of all topics, grouped by topic title | `topic-catalogue.json`, iterated in catalogue order |
| `/s/<state>/t/<topic>` | All artifacts of the one topic | `topic-catalogue.json`, filtered to `topic.id` |

The card NEVER renders on `/t/<topic>` (national view), `/compare`, or `/` (home). Those surfaces use the triple-render renderers or theme-switched choropleth respectively.

## Props contract

```ts
interface Props {
  topic: CatalogueTopic;          // drives header grouping + "See all states" href
  artifact: CatalogueArtifact;    // catalogue reference; carries `display` override if any
  indicator_path: string;         // e.g. "/indicators/in/fiscal/outstanding_debt_pct_gsdp.json"
  home_state: string | null;      // ECI code, e.g. "S22"; null while the route is resolving
}
```

The card fetches the indicator artifact itself (via the same `fetchIndicator` loader the triple uses). Callers pass references and a path, not the loaded data — keeps the card composable across routes without parent-side fan-out.

## Visual anatomy (top to bottom)

1. **Header** — `meta.title` from the indicator JSON. If the catalogue entry carries a different `display` override, it appears as a `·` sub-label after the title (rare; only when the catalogue intentionally renames an artifact in a topic context).
2. **Big number** — `formatValue(home_latest.value, meta)`. Uses the indicator's own formatter (handles unit, sign, %, currency, scaling). Below it: the time period as a small grey label (e.g. `2024`, `FY24`, `2024-Q2`).
3. **Sparkline** — this state's series over time. Single line, no axes, latest-point dot. Stroke colour follows `meta.direction`: green for `higher_is_better`, red for `lower_is_better`, blue for `neutral`. NOT a coloured big number — intensity coding stays in the choropleth (where the colour scale is the whole point).
4. **Rank line** — `1-line` text: `"3rd of 28 states, 2024."`. Sourced from `rankForEntity` over the indicator's latest available period for the home state.
5. **List badge** — `topic.list` (Seventh Schedule Union/State/Concurrent) rendered compact next to the footer.
6. **See all states →** — anchor to `url.topic(topic.id)`. The destination is intentionally the national `/t/<topic>` page until a per-indicator `/i/<id>` route exists.
7. **SourceList** — provenance ([data-provenance.md](data-provenance.md)). Always present. The card never ships a value without its source.

## Rules driven by indicator metadata

The card is metadata-driven; nothing about its behaviour is per-indicator code. The rules below all live in [indicator-card.ts](../../frontend/src/lib/indicator-card.ts) as pure functions and are covered by vitest.

| Metadata signal | Effect on the card |
| --- | --- |
| `meta.direction === "higher_is_better"` | Sparkline stroke green (`#059669`) |
| `meta.direction === "lower_is_better"` | Sparkline stroke red (`#dc2626`) |
| `meta.direction === "neutral"` (default) | Sparkline stroke blue (`#0284c7`) |
| `series.length < 2` | Sparkline omitted (single-time-point indicator); big number still shows |
| `home_latest === null` | Big number replaced by italic "No data for this state yet."; sparkline still draws if other-state series exist (decorative) |
| `canShowRank(meta) === false` | Rank line suppressed |
| `rank_info.total <= 1` | Rank line suppressed (rank of 1 of 1 is meaningless) |
| `meta.indicator.renderer_rules` includes `"no_rank_table"` | Suppresses rank (via `canShowRank`) |
| `meta.indicator.comparability === "snapshot_only"` | Suppresses rank (via `canShowRank`) |
| `meta.indicator.comparability === "directional_only"` | Suppresses rank (via `canShowRank`) |
| `meta.indicator.comparability === "comparable_within_state_over_time"` | Suppresses rank (via `canShowRank`) |

`canShowRank` is the single funnel. New comparability tiers or new `renderer_rules` slugs that should suppress ranking extend `canShowRank`, never the card template.

## Loading and error states

- While `data` is null: `Loading…` text. No skeleton — the card is small enough that flicker beats spinner choreography.
- If `fetchIndicator` throws (404, network, invalid JSON): a small inline rose-tinted error panel inside the card, with the error string in a `<code>`. The other cards on the page continue to load — one failure does not block the others.
- Pre-existing `comparability_caveats` / `series_breaks` / `notes` from the artifact are NOT surfaced on the card (deliberate — the card is the citizen's first read). They DO surface on the `/t/<topic>` triple-render where the cross-state context makes the caveats meaningful.

## What the card does NOT do

- It does NOT render a peer-set filter, comparability banner, list-badge union banner, or attribution-geography banner. Those are surfaces of `/t/<topic>`. On `/s/<state>` the citizen has not opted into a cross-state comparison; the rank line is the only cross-state signal, and `canShowRank` already guards it.
- It does NOT switch units / time aggregation / scale. The indicator artifact dictates those via metadata; the card just renders.
- It does NOT show a chart legend. The sparkline is one line of one state — a legend would be noise.
- It does NOT mount a map. The map is one click away via "See all states →".
- It does NOT carry election-only props or branches. Election artifacts are filtered out before the catalogue iteration that mounts cards. The existing election renderer family handles those separately on the state hub.

## Tests

- Unit: [indicator-card.test.ts](../../frontend/src/lib/indicator-card.test.ts) covers every helper (`latestForEntity`, `seriesForEntity`, `rankForEntity`, `canShowRank`, `ordinal`) including all comparability tiers and `renderer_rules: [no_rank_table]`.
- Contract: covered transitively by `frontend/src/contracts/datasets-conform.test.ts` — any indicator the card consumes must validate against `indicator.schema.json`.
- E2E: [frontend/e2e/golden-path.spec.ts](../../frontend/e2e/golden-path.spec.ts) asserts at least one `[data-testid="indicator-card"]` is present on `/s/tamil-nadu` and on `/s/tamil-nadu/t/fiscal`, and that the SourceList renders inside the card.

## See also

- [schema-is-the-design-system.md](schema-is-the-design-system.md) — the doctrine that says cards compose from the closed set instead of being a new renderer family.
- [indicator-naming.md](indicator-naming.md) — comparability ladder, `renderer_rules` controlled vocab, direction tagging — all consumed by the card.
- [data-provenance.md](data-provenance.md) — the SourceList contract the card always honours.
- [cross-state-comparison.md](cross-state-comparison.md) — the rules that govern when the rank line is honest to show.
- ADR-0022 — place-first IA + topic catalogue (the routing context the card lives inside).
