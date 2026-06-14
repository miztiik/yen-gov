# The schema is the design system

**Last Updated**: 2026-06-14

This is a permanent guardrail for yen-gov. It captures the UI/UX standing position formalised during the the IA reset (2026-05-11) and made structural by [ADR-0022](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue).

## Companion doctrine: elections are one indicator family among many

**User-mandated 2026-05-11.** Read this before the schema rule below; it is the framing the rest of the doc lives inside.

yen-gov is not an elections site that happens to also show fiscal data. It is a civic-data site for India in which **social-welfare topics are first-class** — fiscal, education, health, livelihood, infrastructure — and elections are one indicator family alongside them. The default theme of the home India map is a welfare or coverage indicator, never the latest election leader. The catalogue order leads with welfare topics; elections appear in the list, never at the top of it.

This affects the schema-is-the-design-system rule directly: the closed renderer set must serve welfare indicators *first* and elections second. Election-only renderers (`PartyBar`, `SeatDonut`, `ParliamentArc`, `TileCartogram` in election mode, etc.) remain a closed set in their own right — fully capable, but not the renderers a cold visitor sees first. If a feature request would make an election-only renderer appear on the home page or as the lead surface anywhere, it is rejected on doctrinal grounds, regardless of how clean the implementation is.

**Equal-seats cartogram carve-out (2026-05-31, [ADR-0048](../architecture/frontend/charts/election-views.md#adr-0048-elections-drill-ia-and-tile-cartogram)).** The generic `TileCartogram` primitive is reusable across indicator families in principle, but in v1 it is fenced to election mounts. Equal-sizing welfare or denominator indicators (population, area, budget) — where entities differ wildly in magnitude — distorts the citizen's read and is vetoed by Hans + Max. A future welfare-cartogram would need its own ADR and a fresh equal-sizing-distortion sign-off.

See [ADR-0022](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue) §Doctrine for the full statement.

## The rule

> **No page exists that renders a single indicator's data with code that no other indicator could reuse.**

If a chart needs custom code, the metadata is incomplete — extend the schema, not the page.

## Companion rule: one card per measure

> **A topic page MUST have at most ONE artifact ref per `(canonical_indicator_id, entity_kind)` tuple.**

Added 2026-05-26 per [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity). Facets (species, fuel, sector, basis, kind) live INSIDE the card via a facet picker, not as separate cards. The `/t/agriculture` page that shipped 18 stacked species cards is the cautionary tale — one Pashu Aadhaar measure became 11 species × 2 grains = 22 catalogue rows × 18 surface cards. The collapse target (PR-C2) is 1 cattle card with a species picker + (after grain sub-pages from PR-C1) a grain sub-page link.

Enforced by [frontend/src/contracts/topic-card-uniqueness.test.ts](../../frontend/src/contracts/topic-card-uniqueness.test.ts) (live as of PR #411): for each topic, no two artifact refs share `(canonical_indicator_id, entity_kind)`. Violations fail CI.

### How to add a topic without violating the rule

When adding or editing a topic page (`datasets/taxonomy/topics.json`):

- One artifact ref per `(canonical_indicator_id, entity_kind)` tuple per topic. The contract test enumerates topic rows and rejects duplicates.
- If a measure has multiple facets (species, fuel, sector, basis, kind), declare ONE ref with the facet selector inside the card — do NOT fan out into N refs.
- If a measure has multiple grains (state + district + national), declare ONE ref per `entity_kind` you intend to surface on that topic; cross-grain comparison lives in the card's grain switcher, not in a second card.
- PR #411 (`/t/agriculture`: 16 -> 7 cards) is the canonical worked example. Look at its diff for the shape of a compliant `topics.json` block.
- Run `bun run test -- topic-card-uniqueness` locally before push; the contract test prints the offending `(topic, canonical_indicator_id, entity_kind)` triple on failure.

Companion rule: render-shape fields (`chart_type`, `default_mode`, `renderer_rules`, `facet_labels`, `dimension`) do NOT live on the canonical or topic catalogue — they live in the frontend-owned grapher catalogue at `datasets/grapher/` per [ADR-0045](../architecture/data/indicator-catalogue.md#adr-0045-grapher-catalogue-split). The schema-is-the-design-system rule is preserved; "schema" now means the (canonical + grapher) pair, not canonical alone.

## Why

yen-gov's roadmap calls for 30+ indicators across 8+ topics, maintained by one human + AI assistance. The only way that scales is if adding the 8th fiscal indicator requires no design discussion — just a JSON file.

The opposite world is well-known: a civic-data site where Health has a facility finder, Fiscal has a stacked bar, Energy has a sankey, Demographics has a population pyramid — and each of those is its own micro-product with its own bugs, its own tests, its own designer-time. Five topics in, you have five products and zero compounding.

The contract that prevents this is the indicator schema ([ADR-0020](../architecture/data/indicator-catalogue.md#adr-0020-indicator-artifact-as-data-contract)) and the topic catalogue ([ADR-0022](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue)). Together they declare *what* the data means; the closed renderer set decides *how* it looks. Citizens get consistency; the maintainer gets velocity; honesty caveats (`comparability`, `attribution_geography`, `methodology_vintage`, list-badge, peer-set filter, Union-list banner) propagate structurally instead of being remembered per page.

## The closed renderer set

Every state-hub section, topic landing, and intersection view composes only from this set:

- **`MapChoropleth`** — generic state-level choropleth engine (boundary layer, fills, tooltips, legend gradient).
- **`IndicatorChoropleth`** — `MapChoropleth` driven by an indicator artifact (metadata-driven hue ramp, time slider, comparability banner, source list).
- **`IndicatorRanked`** — generic ranked table with home-state pinning, peer-set filter, honesty banners.
- **`IndicatorSmallMultiples`** — grid of per-state sparklines, shared Y-axis, series-break markers.
- **`TimeSeriesLine`** — single-state or two-state time series. *(Reserved for Phase 6+; not yet shipped.)*
- **`CoverageBadge`** — schema-driven "X of 36 states · Y years" chip.
- **Thin chrome**: `SourceList` (provenance), list-badge (Seventh Schedule), peer-set filter, theme-switch chip, ScopePicker.

Election-only renderers (`PartyBar`, `SeatDonut`, `MarginHistogram`, `RacesBoard`, `ParliamentArc`, `SwingSankey`, `AcStackedBar`, `StateAcMap`, `DualAxisBarLine`) are a closed set in their own right — bound to election data shapes, not extensible per-event.

**New component types require an ADR.** The bar to add a new renderer is high. "Health needs a facility finder because it has lat/lon points" is not enough — points go into `MapChoropleth`'s overlay slot, or they wait until Phase 7+ when a `FeatureCollectionMap` renderer is added by ADR.

## Closed-renderer extension log

Inline-folded ADRs naming each new primitive that joins the closed renderer set, with the qualifying ≥2 indicators per the extension rule above. Per the [documentation-routing contract](documentation-discipline.md#adr-0034-documentation-routing-contract): no new ADR files are minted; extensions to the closed set land as a sub-section here.

### `DualAxisBarLine` (PR-4 of [TODO/20260612-party-rendering-and-party-pages-plan.md](../../TODO/20260612-party-rendering-and-party-pages-plan.md), 2026-06-12)

Bars + line on a shared X axis with dual Y axes (left for bars, right for line / pct). Pure d3-scale + Svelte 5; no external chart lib.

**Qualifying indicators (≥2 threshold satisfied):**

1. Per-party **Lok Sabha** seats won (bars) vs vote-share pct (line) — the citizen-facing primary chart on `/parties/<slug>`.
2. Per-party **Vidhan Sabha** seats won (bars) vs vote-share pct (line) — parallel section on the same page.
3. Future: per-constituency **candidate margin** (bars) vs polling-day **turnout** (line).
4. Future: per-state **party strength index** (bars) vs **alliance share** (line) — Wave-2 of the party-rendering plan.

**Citizen-precedent.** [indiavotes per-party pages](https://www.indiavotes.com/parties/inc/) ship the same bars + line on a shared X axis (seats + vote-share over time); the user named this as the v1 reference in the 2026-06-12 direction. The renderer carries the same encoding minus the ad chrome.

**Jony verdict (B2).** Bars carry the primary count metric (seats; tabular-nums citizen anchor); the line carries the rate metric (vote-share %; trajectory citizen anchor). Dual Y axes are the only honest way to surface both at the same X step. The renderer is standalone (not extracted from `StackedTrendV2`) because the encoding is qualitatively different — `StackedTrendV2` stacks N series on one axis; `DualAxisBarLine` overlays exactly 2 series on two axes.

**Contract surface.** [docs/architecture/frontend/charts/dual-axis-bar-line.md](../architecture/frontend/charts/dual-axis-bar-line.md). The primitive lives at [frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte](../../frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte); pure helpers (`buildScales`, `pickLabelStride`, `yearFromPeriodLabel`) are extracted to its `<script module>` block per project doctrine.

**Mobile contract.** X-label stride thins to a caller-provided `mobile_label_stride` (default 4) at viewport widths < 640px. Tap-on-bar reveals year + both values via the shared `ChartTooltip`.

**Reuse guard.** Future bar+line uses MUST mount this primitive; new "bar+line" surfaces that bypass it violate the closed-set rule.

#### Mode: `composite` (PR-10 of [docs/archive/plans/20260614-party-page-reimagination-plan.md](../archive/plans/20260614-party-page-reimagination-plan.md), 2026-06-14)

Additive `mode: "composite" | "dual-axis"` prop (default `"dual-axis"` preserves the pre-PR-10 contract for every existing caller). In composite mode the renderer collapses to a SINGLE Y axis:

- **Bar height** encodes the bar series value on the left axis (caller usually passes `bar_y_label="Vote share %"` + a percent-formatting `bar_format`; the left axis is clamped to 100 when the formatter emits a `%`-suffixed string for 1.0).
- **Bar fill** splits into two stacked rects per X band — an outer `data-overlay="contested-fill"` rect at 40% opacity covering the full bar height, and an inner `data-overlay="seats-fill"` rect at 100% opacity covering `bar_height * (seats_won / seats_contested)` rooted at the bottom. The conversion ratio is clamped to `[0, 1]` (defensive against data errors); when `seats_contested <= 0`, the inner rect collapses to height 0 and the tooltip surfaces `(did not contest)` instead of the conversion line.
- **Line series + right Y axis + second legend entry are hidden.** Caller passes `line={[]}`.
- **Tooltip** swaps to the composite payload: `<year>` title, `<period_label>` subtitle, three lines (Vote share / Seats X of Y contested / Seat conversion N%) or two when contested = 0.

**Qualifying indicators (>=2 threshold satisfied):**

1. Per-party Parliament cycle history on `/parties/<slug>`: vote-share % bars with seats-of-contested overlay.
2. Per-party State Assembly cycle history on the same page: parallel section with the same encoding.
3. Future: per-event vote-share + winner margin overlay; per-state turnout + valid-vote-share overlay.

**Citizen-precedent.** The composite encoding (bar height = primary rate, bar fill = success ratio) is the OWID Grapher's "stacked discrete bar with fraction overlay" pattern. The page lift gives the citizen a single visual answer to "did the party contest widely, and how often did contesting convert to winning?" — replacing the prior two-axis seats+vote-share juxtaposition that buried the conversion question.

**Section glyphs.** Each per-body section (Parliament + State Assembly) gets a `TopicIcon` glyph on its KPI tile label, chart H2, and stronghold subheader: `landmark` for Parliament; `flag` for State Assembly. Glyphs sit inside `inline-flex items-center gap-2` wrappers preserving the H2/H3 text classes; the underlying `TopicIcon` silent-misses unknown names so an icon-pack regression never crashes the page.

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

### Editorial-workflow fields are not citizen surface

**Added 2026-06-12.** Not every metadata field is a renderer guard. Fields that describe **yen-gov's internal review state** — `methodology.documentation_status` (`stub` | `partial` | `authored`) and `inventory_status` (`empty` | `partial` | `complete`) — describe whether the maintainer has written prose / completed an inventory pass, **not** whether the underlying data is trustworthy. They surface on [/data-completeness](../../frontend/src/routes/DataCompleteness.svelte) (the transparency route for auditors) and nowhere else.

Putting them on citizen cards was a 2026-05-26 experiment: PR #322 added an amber dot to the `AboutThisData` info-icon and a "STUB" pill inside the expanded panel, both bound to `documentation_status !== "authored"`. Because every canonical-backed artifact hard-codes `documentation_status: "stub"` (see [indicator-from-canonical.ts](../../frontend/src/lib/canonical/indicator-from-canonical.ts) `synthesiseStubMethodology`), the badge fired on 100% of cards on every topic page. A signal that fires on 100% of instances is not a signal — it is chrome that mis-borrows the amber palette from the rest of the system, where amber means "this data has a caveat the citizen needs to read" ([`IndicatorRanked`](../../frontend/src/lib/IndicatorRanked.svelte) `not_comparable_across_states` banner, election year-mismatch warnings, license-terms pill).

Removed 2026-06-12 (see [AboutThisData.svelte](../../frontend/src/lib/AboutThisData.svelte) `2026-06-12` header comment).

**The doctrine.** The closed renderer set's amber palette is reserved for fields that (a) fire **less than 100%** of the time, (b) **change the citizen's read** of the chart, and (c) point at a documented publisher constraint — `comparability`, `methodology_breaks`, `attribution_geography`, `series_breaks`, licence non-redistributable, election year-mismatch. yen-gov's own editorial backlog is not in that list.

If you reach for a new badge to surface "we haven't finished documenting this," stop. The right home for that work is [/data-completeness](../../frontend/src/routes/DataCompleteness.svelte). The right shape of any new citizen-surface honesty signal is a structural renderer guard driven by a publisher-anchored field, declared in [ADR-0020](../architecture/data/indicator-catalogue.md#adr-0020-indicator-artifact-as-data-contract), not an internal-status mirror.

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

The test that settles edge cases: *can these two artifacts coexist as different rows in the canonical indicator catalogue?* `_crore` and `_lakh` cannot — they're the same fact table multiplied by 100. So they must not differ in id. `_per_capita` and `_pct_gsdp` can — they're different numerator-over-denominator constructs with their own honesty fields. So they earn distinct ids.

This rule is part of the design-system contract. A renderer that special-cases on unit (instead of reading `unit` from the artifact) violates this section as much as a renderer that special-cases on indicator id violates *The rule* above.

## See also

- [ADR-0020](../architecture/data/indicator-catalogue.md#adr-0020-indicator-artifact-as-data-contract) — the indicator artifact as the generic data contract.
- [ADR-0022](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue) — the IA spine + topic-catalogue contract that anchors this guardrail.
- [docs/architecture/frontend/indicators.md](../architecture/frontend/indicators.md) — current state of the renderer set.
- [docs/concepts/cross-state-comparison.md](cross-state-comparison.md) — comparison primitives (ranked table first, no composite indices).
