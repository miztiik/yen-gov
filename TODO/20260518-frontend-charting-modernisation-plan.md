# Frontend Charting Modernisation Plan

**Created**: 2026-05-18
**Status**: Planned handoff for next coding agent
**Trigger**: User asked whether Svelte remains the right frontend library, whether Plotly or another charting library should replace the current graphing approach, and noted that some charts lack life and colour.
**Scope**: Public frontend chart/rendering layer, chart summary chrome, and iconography only. No code changes were made during the analysis session that produced this plan.
**Load-bearing docs**: [`docs/architecture/frontend/overview.md`](../docs/architecture/frontend/overview.md), [`docs/architecture/frontend/indicators.md`](../docs/architecture/frontend/indicators.md), [`docs/architecture/frontend/colours.md`](../docs/architecture/frontend/colours.md), [`docs/architecture/frontend/charts/stacked-trend.md`](../docs/architecture/frontend/charts/stacked-trend.md), [`docs/concepts/schema-is-the-design-system.md`](../docs/concepts/schema-is-the-design-system.md), [`docs/concepts/citizen-first.md`](../docs/concepts/citizen-first.md), [`CLAUDE.md`](../CLAUDE.md) Holy Laws #1, #3, #4, #6, #8, #10.

## Executive decision

Keep **Svelte 5 + Vite** as the public frontend framework.

Keep the public citizen chart stack as **Svelte-authored renderers + d3 as math + MapLibre for maps + DuckDB-WASM/view-model loaders**.

Do **not** wholesale migrate the public app to React, Vue, SvelteKit, Plotly, ECharts, Chart.js, Observable Plot, or Vega-Lite as the primary charting layer. This is not the same as "never use a charting library." A library-backed renderer is acceptable when it is sealed behind a yen-gov view-model adapter, can hide/replace its generic toolbar, respects the existing colour/provenance/honesty chrome, and clearly removes more complexity than it introduces.

The problem to solve is not framework choice. It is that several existing chart primitives are visually under-finished against yen-gov's own chart doctrine.

The revised product direction is: **borrow Plotly-like capabilities where citizens need them, not Plotly-like chrome everywhere.** Long-duration charts should support a sliding time window, range presets, reset/full-range, and export where useful. These controls belong to selected chart families, not to every chart by default.

The matching iconography direction is: **use icons as schema-driven wayfinding, not decoration or interpretation.** `topic.icon` and `indicator.icon` already exist as contract fields, and [`frontend/src/lib/IndicatorIcon.svelte`](../frontend/src/lib/IndicatorIcon.svelte) already provides a small Lucide-style inline SVG registry. The missing work is to complete the registry, wire icons into more surfaces, and document licensing/provenance for any non-Lucide/custom SVG.

The matching projection direction is: **let data shape decide eligibility, and metadata decide the default story.** Do not hardcode chart selection by indicator id. Do not infer the final chart solely from column names. Use closed yen-gov projection enums, sort policies, facet-axis metadata, and view-model adapters so Max/Hans/Jony can author the intended chart behaviour without creating a free-form chart-spec language.

## Findings from the read-only audit

1. **Svelte is not the bottleneck.** The app is static, component-oriented, schema-driven, and needs custom civic disclosure around every chart. Svelte is well matched to that shape.
2. **The closed renderer set is the asset.** [`docs/concepts/schema-is-the-design-system.md`](../docs/concepts/schema-is-the-design-system.md) correctly treats the schema/catalogue/view-model contract as the design system. A chart library must not become a second design system.
3. **d3 is being used correctly today.** The repo uses d3-style math and direct Svelte/SVG/MapLibre rendering, not a charting framework that hides the DOM. That keeps provenance, caveats, no-data treatment, methodology breaks, and custom controls under project control.
4. **The colour foundation is strong.** [`frontend/src/lib/colors/`](../frontend/src/lib/colors/) already uses OkLCh, party anchors, algorithmic fallbacks, and dimension anchors. The issue is not "missing palette library"; it is chart-level hierarchy and interaction polish.
5. **`IndicatorChoropleth` is the strongest current surface.** It has mature honesty banners, coverage caption, temporal slider, map, legend, source list, hatch/no-data patterns, and drill-down machinery. It needs confidence tuning, not replacement.
6. **`StackedTrend` is the flattest current surface.** [`docs/architecture/frontend/charts/stacked-trend.md`](../docs/architecture/frontend/charts/stacked-trend.md) specifies a richer chart than [`frontend/src/lib/charts/StackedTrend.svelte`](../frontend/src/lib/charts/StackedTrend.svelte) currently renders. The implementation lacks the pinned readout, segmented mode control, inline labels, missing-segment hatch, legend toggles, axis rhythm, and mode-change tween promised by the design doc.
7. **`IndicatorRanked` is useful but too table-like.** It answers the comparison question, but the citizen's state, peer band, median, and top/bottom context need stronger visual treatment.
8. **`IndicatorSmallMultiples` scans but does not yet invite interpretation.** The 32px sparklines, single-stroke treatment, and limited baseline/context make trajectories feel quiet even when the data is important.
9. **Modernisation should mean editorial clarity, not decoration.** Add life through hierarchy, motion on state changes, visible comparison anchors, and confident colour semantics. Avoid ornamental gradients, random saturated palettes, and dashboard chrome.
10. **Future inference-heavy work belongs in loaders/view-models first.** SLM/SQL/inference should produce constrained, typed chart-ready models from DuckDB-WASM/canonical data. Renderers should stay dumb, testable, and consistent.
11. **Plotly-like range controls are useful for a subset of charts.** The PM-term Gantt example shows a real citizen/analyst need: long timelines should not force either full-duration view or fixed recent window. A brush/range slider, presets, reset, and optional download are legitimate capabilities.
12. **Plotly-like modebars are not the desired public chrome.** Download, reset, zoom, and pan are separable. We should expose only the controls that fit the chart's job, in yen-gov styling, instead of inheriting a full analytics toolbar on every chart.
13. **Chart summaries need their own guardrail.** Readouts and generated/plain-language summary lines must respect the visible time window, denominator, unit, entity scope, `comparability`, and `series_breaks`. They must not imply causality, blame, or improvement from a single indicator unless the contract explicitly supports that interpretation.
14. **Iconography is partially present but not governed enough.** The schemas already expose `topic.icon` and `indicator.icon`, and `IndicatorChoropleth` renders indicator icons. Many catalogue/indicator icon names are not yet in the registry, some choices are weakly semantic (`trending-up` for GDP, fertility, mortality, prices, and expenditure), and topic/indicator cards do not consistently surface icons.
15. **The requested chart grammar is reproducible with current tooling.** Svelte + SVG + d3 scales + MapLibre + OkLCh can produce strong categorical palettes, direct end labels, horizontal bars, dumbbells, grouped/faceted panels, choropleth gradients, source footers, and time-window sliders. The missing work is chart grammar and view-model contracts, not a new framework.
16. **Sorting is a first-class chart decision.** Value sorting is right for ranked states/countries; natural/source order is right for time, economic class, age bands, education levels, and many survey categories. Sorting must come from a closed `sort_policy` plus facet-axis metadata, not ad hoc component code.
17. **Source disclosure should be compact but reproducible.** [`frontend/src/lib/SourceList.svelte`](../frontend/src/lib/SourceList.svelte) already uses a triangle disclosure. The next step is SourceList/ChartFooter v2: collapsed line shows human trust text (producer/authority/vintage/source family), expanded state shows exact URLs, citations, licence, schema/provenance details.
18. **Several recurring chart questions imply missing generic renderers.** Candidate additions are `TimeSeriesLine`, `HorizontalGroupedBar`, `OrderedCategoryBar`, `DumbbellRange`, and a `FacetPanelGrid` wrapper. These should be adapter-fed view-model renderers, not one-off components for a specific dataset.

## Rejected alternatives

### React + Vite rewrite

Rejected. React is viable and has a larger ecosystem, but it does not solve yen-gov's hard problems: static deployment, source provenance, schema dispatch, DuckDB loading, methodology breaks, peer-set comparisons, and no-data semantics. A rewrite would turn a chart-polish problem into a porting project.

### Vue rewrite

Rejected. Vue is also viable, but offers no decisive advantage over Svelte for this app. Same migration cost, same data-contract work afterward.

### SvelteKit now

Rejected for now. Static SvelteKit could eventually help with nested layouts, route data loading, and error boundaries, but the current bottleneck is not routing. Revisit only after the canonical Parquet reader and path-routed IA are stable and route/layout complexity is demonstrably costing time.

### Plotly as unconditional public chart layer

Rejected. Plotly is strong for analyst exploration and ships useful primitives such as range selectors, zoom/pan, hover readouts, and PNG export. The rejected shape is making Plotly the default public chart surface with its full generic modebar and chart grammar. A narrowly scoped Plotly-backed renderer is still allowed if a spike proves it can be lazy-loaded, styled, stripped of unwanted chrome, fed by yen-gov view-models, and integrated with the existing source/honesty layout.

### ECharts as unconditional public chart layer

Rejected as the default public layer. ECharts is the strongest off-the-shelf interactive chart alternative and may be worth a spike for dense timelines. It still brings its own grammar and theme system. Use only if a future renderer has at least two concrete needs that Svelte+d3 cannot serve without disproportionate custom work.

### Chart.js as public chart layer

Rejected. It is lightweight and simple, but too limited for the app's map/stacked/trend/provenance needs, and it does not help with schema-driven civic framing.

### Observable Plot or Vega-Lite as public chart grammar

Rejected as primary surface. They are better aligned with declarative data graphics than Plotly, but they risk creating a parallel "chart spec" contract beside `indicator.schema.json` and the topic catalogue. They are acceptable for prototyping or internal exploration behind adapters.

### Randomly brighter palettes

Rejected. The colour issue is not insufficient saturation alone. Brighter random palettes would reduce trust and break the current rule that dark means "more of the thing". Improve hierarchy and ramp tuning within OkLCh.

### Per-indicator bespoke components

Rejected. Directly violates schema-is-the-design-system. If a chart needs new behaviour, add metadata/view-model fields and extend a generic renderer.

### Keep everything exactly as is

Rejected. The stack choice is sound, but the public chart experience is not yet polished enough for the amount of socio-economic data coming in. The next work should be visual/interaction polish on the existing renderers.

### Marketplace icon grab-bag

Rejected. Downloading unrelated SVGs from Noun Project, IconScout/NounScout-like sites, Material Symbols, Tabler, Phosphor, and other sources into one mixed set would create visual drift and licensing risk. Use one house style first; import outside icons only as curated, licensed exceptions.

### Icons as interpretation

Rejected. Icons must not carry the claim that a value is good/bad, rising/falling, or attributable to a particular government/source. They are visual nouns for scanning: energy, health, fiscal, labour, industry, transport, elections. Titles, legends, caveats, numbers, and source rows carry the meaning.

### Free-form chart specification language

Rejected. Do not add arbitrary Vega/Plotly-style JSON specs, mark encodings, SQL snippets, or per-indicator layout DSLs as a shortcut to flexibility. yen-gov needs a closed set of projection/view-model enums: chart family, sort policy, facet strategy, default viewport, and footer actions.

### Data-shape inference as the final chart decision

Rejected. Inference can say a renderer is eligible; it must not decide the public default alone. A table with years can be a line chart, small multiples, two-period bar comparison, or a temporal map depending on the citizen question. Max/Hans/Jony-authored metadata chooses the default.

### Nested sunburst / multi-ring radial / composite-circle composition charts

Rejected (2026-05-19, Jony + Hans + Max review of a Gujarat+Himachal 2017 seat-share sunburst the user surfaced for evaluation). Three independent reasons, any one of which is fatal:

1. **Multi-entity composites fuse independent 100%-baselines into one frame.** Two states sharing one inner ring sized by chamber count makes the eye reconcile entity-size + party-composition + party-colour simultaneously for what should be a one-fixation read. Cleveland-McGill ranks angle/arc-area as the worst encoding for quantitative comparison; a horizontal stacked bar communicates the same composition in one fixation.
2. **"Other" routinely becomes invisible** in radial composition charts (the source artifact relegated it to a footnote with no visible wedge). At state-aggregate level the tail can be the largest party — BSP in UP 2022, the Left in WB 2021, the entire DMK/AIADMK alliance ladder in TN 2021. Hiding the tail is a §12 honesty-chrome violation.
3. **No major civic-data publisher uses the idiom for political composition.** OWID, Pew, FT, Economist, NYT Upshot, Reuters Graphics, IndiaSpend, Scroll, Mint, The Hindu Data, Indian Express Datalab, TCPD/Lokdhaba, CSDS — every shop converged on stacked bars + line trajectories + categorical choropleth + small multiples. The sunburst is an idiom imported from taxonomy/expenditure/Sankey visualisation (D3 Flare hierarchy, NYT federal-budget treemap, IEA energy-flow Sankey — all single-whole hierarchical compositions) and does not transfer to multi-entity political composition.

Use `composition_bar` (single-entity, single-period horizontal 100%-stacked bar with visible Others + visible NOTA) instead. Existing single-state `SeatDonut`, `PartyBar`, `ParliamentArc`, `MarginHistogram` remain valid where they're already used. Multi-state composition is deferred (see "Deferred work — re-enter when data is acquired" below) and only re-enters when Hans's guard rule in Phase 0.75 is satisfied.

## Build-vs-buy rule

This is the architectural decision seed. Promote this section into an ADR if/when a concrete library-backed renderer is proposed.

### Build in yen-gov when the capability is part of the civic chart grammar

Build/own the implementation when:

- the control must be consistent across multiple yen-gov renderers,
- it carries honesty semantics (`series_breaks`, `vintage`, `comparability`, no-data hatch, source/provenance),
- it needs to be driven by indicator metadata rather than a chart-specific spec,
- it is small enough to implement as pure helpers + Svelte DOM,
- it must share the OkLCh colour system or MapLibre layer model,
- it is citizen-facing chrome that should look like yen-gov, not like an analytics product.

Examples likely worth building: small segmented mode controls, readout panels, legend toggles, no-data hatching, source/license rows, direction cues, median/peer markers, simple time presets.

### Buy/use a library when the capability is complex and generic

Use Plotly/ECharts/Observable/Vega-like tooling when all of these hold:

- at least two real chart families need the same heavy interaction,
- the library can be lazy-loaded for those routes only,
- the library can consume a yen-gov view-model rather than raw arbitrary data,
- generic toolbar controls can be disabled or replaced with yen-gov controls,
- export/range/zoom behaviour works better than a quick in-house version,
- bundle impact is measured and acceptable,
- visual theming can be brought under the existing colour and typography system,
- provenance, methodology, source, and no-data semantics remain outside the library and under yen-gov control,
- the chart-spec grammar does not become a persisted contract unless a future ADR explicitly approves that.

Candidate buy/use cases: dense Gantt timelines, long-duration stock-market-style series with brush windows, highly interactive exploratory charts in `/explore` or `admin/`, and export-heavy analyst surfaces.

### Borrow the interaction even when we do not buy the renderer

The PM-term Plotly example has useful patterns independent of Plotly:

- sliding temporal viewport over a full domain,
- `All` / recent-window / fixed-duration presets,
- reset-to-full-range,
- drag-to-pan within a selected window,
- explicit download button,
- hover readout tied to marks.

These patterns should be added selectively to yen-gov renderers where they answer a real user need.

### Toolbar policy

No chart gets a generic analytics toolbar by default.

Allowed controls, when chart-appropriate:

- download SVG/PNG,
- reset view,
- fit/full range,
- time-window presets,
- pan/zoom for dense timelines,
- legend series toggle.

Avoid by default:

- always-visible multi-icon modebars,
- lasso/select tools unless the page has a real selection workflow,
- 3D rotate/camera controls,
- generic autoscale buttons whose behaviour is unclear to citizens,
- controls that appear because a library ships them, not because the chart needs them.

## Chart summary policy

This applies to any headline, readout, tooltip replacement, or generated plain-language summary added during chart polish.

Summaries should:

- derive from the same typed view-model as the chart,
- name or imply the visible time window when a window is active,
- respect denominator and unit (`%`, `per 1,000`, `INR crore`, `MW`, etc.),
- avoid crossing `series_breaks` unless the summary explicitly separates the periods,
- suppress rank/comparison claims when `comparability` forbids them,
- use neutral wording for direction unless `indicator.direction` and the indicator concept make the interpretation safe,
- avoid causal or blame language unless another explicit contract field supports it.

Examples of risky summaries: "health improved" from expenditure alone, "state failed" from one outcome, or "GDP is better" solely because a current-price rupee value rose.

Allowed generated summary families, when inputs match exactly:

- latest value within the selected entity/window,
- gap in percentage points or native units between two comparable groups,
- ratio between two ordered groups with the same universe and denominator,
- rank within a visible peer set when `comparability` permits ranking,
- composition share within an explicitly known denominator,
- change over time within one comparable series segment.

Generated summaries must recompute when the temporal viewport, selected peer set, facet, or sort changes.

## Iconography policy

Icons are orientation marks, not data encodings.

Canonical source:

- Prefer the existing Lucide-style inline SVG registry in [`frontend/src/lib/IndicatorIcon.svelte`](../frontend/src/lib/IndicatorIcon.svelte).
- Keep icons 24px viewBox, stroke-based, monochrome, `currentColor`, no gradients, no multicolour pictograms except brand marks.
- Add custom SVG only when Lucide cannot express a durable civic noun.
- Use Noun Project / IconScout / NounScout-like SVGs only as curated exceptions with explicit redistribution rights and attribution metadata.
- Avoid unclear, non-commercial, no-derivatives, or account-gated icon licences in the public bundle.

Data source:

- `topic.icon` drives topic index cards, topic headers, and topic chips.
- `indicator.icon` drives indicator cards and chart headers.
- Future dimension-value icons may live beside colour anchors for repeated facets such as `power_source`, `industry_sector`, or `labour_status`.
- Source/provenance rows stay text-first; do not use RBI/ECI/ministry logos as ordinary indicator icons.
- Renderer controls use functional icons only: download, reset, fit/full range, zoom/pan where chart-appropriate.

Inheritance rule:

1. use explicit `indicator.icon`,
2. else use dimension-value icon where the row/facet has one,
3. else use `topic.icon`,
4. else use the generic fallback.

Guardrails:

- no per-route hardcoded icon maps,
- no icon-only category labels,
- no icon as the only warning/no-data/provenance signal,
- no source logos, party symbols, state emblems, or government seals as data icons,
- no mixed filled/outline libraries on the same public surface,
- every non-Lucide/custom icon records source URL, author, licence, attribution text, and modification note.

## Projection and sorting policy

Projection metadata chooses the public chart story. The renderer implementation stays generic.

Closed concepts to define before broad pixel work:

- `default_projection`: `choropleth`, `ranked_bar`, `ordered_category_bar`, `horizontal_grouped_bar`, `time_series_line`, `small_multiples`, `stacked_trend`, `dumbbell_range`, `period_comparison_bar`, `composition_bar`, or another approved renderer enum.
- `eligible_projections`: renderer enums the data shape can support.
- `sort_policy`: `value_desc`, `value_asc`, `axis_order`, `chronological`, `pinned_then_value`, `rank_best_first`, `latest_change`, or `alphabetical`.
- `facet_strategy`: `none`, `side_by_side`, `panel_grid`, `grouped_bars`, `small_multiples`, or `dimension_filter`.
- `temporal_viewport`: `all`, `recent`, `recent_10`, `recent_25`, selected period pair, or explicit full/visible domain.
- `footer_actions`: `view_data`, `download_svg`, `download_png`, `download_csv`, `copy_link`, `share`, `reset_view`, `full_range`.

Rules:

- default projection must be one of the eligible projections,
- no indicator-id conditionals for chart dispatch,
- no value sorting for ordered axes such as poorest-to-richest unless metadata explicitly allows it,
- null/missing values sort last and remain visible unless the view explicitly filters them,
- rank claims must show the peer set/scope or be suppressed,
- temporal summaries must use only the visible window,
- **multi-entity composition guard** (Hans, 2026-05-19): a `composition_bar` (or any future composition projection) MUST NOT span multiple entities in the same chart unless ALL of (a) the citizen question is explicitly comparative and named in the page/section title (`How did BJP perform across Hindi-belt assemblies 2017–2022?` — not `2017 had two state elections`), (b) the encoding compares like-with-like ratios only (`*-pct`, `*-rate-pct`, `*-share-pct`) — raw seat counts, raw vote totals, and raw elector counts are forbidden as visual sizing across entity boundaries because the denominators differ, and (c) the peer set is principled and named (geographic region, party-system shape, election cycle, governance topology) — calendar coincidence is not a peer set. When the guard fails, render single-entity `composition_bar`s inside `FacetPanelGrid` with entity identity in the panel title, never in the segment fill (segment fill is reserved for the dimension being composed: party, power source, age band). Multi-entity composition is OUT OF SCOPE for v1 of `composition_bar`; see "Deferred work — re-enter when data is acquired" below.

Facet-axis metadata should live in the canonical facet-axis registry (`taxonomy/facet-axes.json` under the canonical pivot) or a documented legacy bridge until that registry is available. It should carry value ids, labels, order, relationship (`ordered_scale`, `composition`, `endpoint_pair`, `nominal`, etc.), colour anchors, and default facet strategy.

## Chart grammar inventory

Define reusable grammar by chart question, not by source site or one-off example.

Projection families to support over time:

- long ordered series with optional visible window: `time_series_line` + `temporal_viewport`,
- ranked entity comparison: `ranked_bar`,
- source-ordered categorical comparison: `ordered_category_bar`,
- grouped measures per row/category: `horizontal_grouped_bar` or `period_comparison_bar`,
- two-endpoint comparisons: `dumbbell_range`,
- spatial entity distribution: `choropleth`,
- repeated panels by registered facet: `facet_panel_grid`.

Colour rules:

- strong categorical palettes are reproducible through OkLCh anchors,
- categorical palettes belong to dimension registries, not individual Svelte files,
- line charts should prefer direct end labels over legend-only identification,
- choropleths should tune lightness/chroma while preserving dark = more of the thing.

## Source and action footer policy

Every chart family should eventually use one shared chart shell/footer rather than hand-placing source and action controls.

Collapsed footer line:

- show a human trust summary, e.g. `Source: RBI Handbook of Statistics on Indian States · official series · 2024-25`,
- show schema/provenance status only if it helps trust and does not crowd the chart,
- keep exact file/download URLs out of the default view.

Expanded footer disclosure:

- exact source URL/download URL,
- producer/issuing authority,
- citation, licence, vintage,
- first fetched / last seen where available,
- schema version and provenance details,
- hand-authored/internal note where `sources` is intentionally empty.

Action controls:

- `View data` opens a table for the currently visible chart/window, not the entire corpus by default,
- `Download` exports SVG/PNG/CSV only where the chart is useful as a standalone artifact,
- `Share` copies the current route plus view state: time window, sort, facet, peer set,
- controls use yen-gov icons and labels/tooltips, not a generic modebar.

## Sequencing principle

Tidy first. Keep structural work separate from behavioural UI changes.

For each phase below:

- pure helpers / view-model changes land with vitest first,
- Svelte component changes land after the helpers are covered,
- citizen-visible changes extend Playwright where appropriate,
- frontend runtime changes are smoke-tested via the integrated browser per `CLAUDE.md` section 13,
- docs under `docs/architecture/frontend/` are updated in the same branch if a design decision is promoted from this TODO.

Implementation of any phase that changes runtime behaviour is at least Correction Level 2. Present the phase slice to the user before coding unless the user explicitly says to execute this plan.

---

## Decision log (for the next agent)

This plan was authored on 2026-05-18 and amended in two persona-led review cycles on 2026-05-19 and 2026-05-20. The decisions below are **closed** \u2014 do not re-debate them. Each entry points to the in-plan section that records the full reasoning, rejected alternatives, and implementation tasks.

| Date | Decision | Status | Where it lives in this plan |
|---|---|---|---|
| 2026-05-19 | Multi-entity sunburst / nested radial composition charts are rejected for political composition. Use single-entity `composition_bar` with visible Others + visible NOTA. | Closed | "Rejected alternatives" \u2192 "Nested sunburst / multi-ring radial / composite-circle composition charts" |
| 2026-05-19 | New `composition_bar` projection added to the closed `default_projection` enum. | Closed | Phase 0.75 \u2192 enum list |
| 2026-05-19 | Multi-entity composition guard rule (a)(b)(c): explicit named comparative question + ratio-only encoding + principled peer set, otherwise render single-entity bars inside `FacetPanelGrid`. | Closed | Phase 0.75 \u2192 Rules |
| 2026-05-19 | Election composition summaries must suppress dominance verbs when top-two vote-share gap is <8 percentage points. | Closed | Phase 3.6 \u2192 Summary copy rules |
| 2026-05-19 | New Phase 3.6 \u2014 ship single-entity `CompositionBar` side-by-side with existing `<SeatDonut>` on `StateOverview.svelte` for visual A/B; no URL toggle, no feature flag. Mount route: state hub on Tamil Nadu (`/india/tamil-nadu`). | Closed | Phase 3.6 |
| 2026-05-19 | Alliance rollups for election composition deferred (data not available; user actively sourcing). | Deferred | "Deferred work" \u2192 DEFERRED-A |
| 2026-05-19 | Multi-state composition deferred (no route ships a named comparative question yet). | Deferred | DEFERRED-B |
| 2026-05-19 | `categorical_choropleth` projection deferred (separate scoping pass needed for hung-verdict + swatch-grid legend). | Deferred | DEFERRED-C |
| 2026-05-19 | Vote-share twin alongside seat-share deferred (data exists; held out of v1 to keep A/B clean). | Deferred | DEFERRED-D |
| 2026-05-19 | Longitudinal seat-share + vote-share twin deferred (blocked on Phase 1.5 temporal viewport primitive). | Deferred | DEFERRED-E |
| 2026-05-20 | URL grammar: canonical state hub is `/india/<state>` per ADR-0028; legacy `/s/<state>` rewrites via `RedirectLegacyUrl.svelte` strangler-fig until iced-bulk-ingest Phase 3 lands. All new plans / docs / smoke targets use the canonical grammar. | Closed | Phase 1 \u2022 Phase 3.6 \u2022 ADR-0028 |
| 2026-05-20 | Phase 0.5 chart-library spike resolved: **build native Svelte + d3** for every renderer in Phases 1.4\u20133.6. Single named escape hatch: ECharts `dataZoom` for Phase 1.5 timeline brush, requires its own ADR + Hans sign-off + bundle measurement. | Closed | Phase 0.5 |
| 2026-05-20 | Phase 0.75 projection-metadata home resolved: **Option C \u2014 hybrid**. Indicator artifact carries canonical `presentation` block; topic-catalogue per-artifact entry carries optional `presentation_override`. Field-level merge. Resolution order: override \u2192 indicator \u2192 inferred default. Three-step Beck sequencing (structural-first). | Closed | Phase 0.75 |
| 2026-05-20 | Phase 1.3 icon system: **folder-based** at `frontend/src/lib/icons/`, **build-time inventory plugin** with **strict allowlist parser** that REJECTS disallowed elements/attributes, **structured rendering** (no `{@html}`), **no Noun Project** (CC-BY attribution complexity), all icons stored as **local copies**. Allowlist is one source of truth in `allowlist.ts`. Six rollout sub-phases 1.3a\u20131.3f in citizen-impact order. | Closed | Phase 1.3 |\n\n### Outstanding open questions\n\nNone for the planned phases. Specific in-flight gates the next agent should watch:\n\n- **Phase 1.5 escape-hatch trigger**: only after a real native d3 attempt at the dense Gantt / fiscal stock-style brush proves disproportionately heavy. Open a single-renderer ADR; do NOT amend Phase 0.5.\n- **DEFERRED-A re-entry trigger**: when alliance observation rows land in the canonical store. Re-open Phase 3.6 to add an alliance-binding adapter.\n- **DEFERRED-D re-entry trigger**: immediately after Phase 3.6 v1 visual A/B passes. Add a second `<CompositionBar>` bound to `party-vote-share-pct` on the same card.\n\n### Personas consulted (for traceability)\n\n- **Jony (UI/UX)** \u2014 sunburst rejection (2026-05-19), URL grammar (2026-05-20), icon storage + rollout order (2026-05-19, 2026-05-20), library visual-craft (2026-05-19).\n- **Hans (Governance)** \u2014 sunburst rejection (2026-05-19), citizen-honest library defaults (2026-05-19), projection-home semantics (2026-05-19), summary copy rules (2026-05-19).\n- **Max (Indicator Scout)** \u2014 sunburst rejection (2026-05-19), projection-home catalogue scale (2026-05-19).\n- **Fowler (Engineering)** \u2014 library bundle/contract/test surface (2026-05-19), projection-home storage mechanics (2026-05-19), icon plugin security shape (2026-05-20).\n\n### Where these decisions eventually live in `docs/`\n\nThis plan is a TODO. When each phase ships, lift its decision section into the appropriate subsystem doc per Holy Law #4 (one home per concept):\n\n- Phase 0 \u2192 `docs/architecture/frontend/overview.md` (already partially populated).\n- Phase 0.5 \u2192 `docs/architecture/frontend/charts/README.md` (build-not-buy doctrine).\n- Phase 0.75 \u2192 `docs/architecture/frontend/charts/projection-contract.md` (new doc; this is the canonical Hans+Max+Fowler design surface).\n- Phase 1.3 \u2192 `docs/architecture/frontend/icons.md` (new doc; full Jony+Fowler design including allowlist, plugin sketch, sub-phase order).\n- Phase 3.6 \u2192 `docs/architecture/frontend/charts/composition-bar.md` (new doc; renderer contract + adapter pattern + summary copy rules).\n- ADR-0028 already canonicalises the URL decision; reference it from all routing-touching plans.\n\nDelete each section from this TODO when its target doc lands. The TODO is debate-output; the docs are agent memory.

---

## Phase 0 - Canonicalise the framework/charting decision

**Correction level**: 1 for docs only, 2 if paired with test or dispatch policy.

**Goal**: Prevent future agents from re-litigating Svelte vs Plotly every time a chart looks flat.

Tasks:

- [ ] Add a short decision journal entry to [`docs/architecture/frontend/overview.md`](../docs/architecture/frontend/overview.md): keep Svelte 5 + Vite; public charts use closed yen-gov renderers; external chart libraries are exploration-only unless an ADR adds a renderer.
- [ ] Add a paragraph to [`docs/concepts/schema-is-the-design-system.md`](../docs/concepts/schema-is-the-design-system.md): external chart packages must consume yen-gov view-models and must not become a parallel chart-spec grammar.
- [ ] Add a note to [`docs/architecture/frontend/charts/stacked-trend.md`](../docs/architecture/frontend/charts/stacked-trend.md) linking this plan and marking the implementation gaps that remain.
- [ ] Promote the "Build-vs-buy rule" above into a short ADR draft if the next implementation chooses a library-backed renderer.
- [ ] No package changes. If this phase touches `frontend/package.json`, it is wrong.

Verification:

- [ ] `git diff --check`.
- [ ] No runtime tests required for docs-only work.

---

## Phase 0.5 - Library capability spike for timeline interactions

**Status**: ✅ **RESOLVED 2026-05-20**. Decision below.

**Correction level**: 1 (decision recorded; no code changes from this phase).

### Decision

**Native Svelte + d3 for every chart shipping in Phases 1.4 through 3.6.** No charting library dependency added to `frontend/package.json`.

### How the decision was reached

Commissioned three independent persona reviews on 2026-05-19 — Fowler (engineering), Jony (UI/UX), Hans (governance). All three converged on `native` for different reasons. The convergence is the signal; the reasons explain what the next agent must defend against if temptation to add a library returns.

**Fowler (engineering — bundle / contract / test surface):**
- d3 already in `frontend/package.json` at 89.8 kB gzip — paid cost.
- Plotly.js full bundle ≈ 1.1 MB gzip; `plotly.js-basic-dist-min` ≈ 280–330 kB. ECharts full ≈ 324.7 kB; custom build ≈ 150–180 kB. Observable Plot ≈ 70–80 kB net incremental.
- Plotly and ECharts both require a chart-spec config object (`data: Trace[] + layout: Layout`, or ECharts' `option`) that becomes a **parallel contract** to `indicator.schema.json`. Violates Holy Law #3 (contracts before logic).
- Native SVG keeps tests in vitest+jsdom; Plotly/ECharts force every chart correctness check into Playwright.
- Plotly's TypeScript support is DefinitelyTyped only; ECharts and Plot ship first-class types.

**Jony (UI/UX — visual craft):**
- Every library imposes default visual identity yen-gov has to suppress (Plotly's blue modebar, ECharts' dashboard look, Plot's tooltip-coexistence flicker on mobile).
- Tooltip pixel-position racing: replacing the library's tooltip with `ChartTooltip.svelte` means two tooltip systems coexist; touch events fire both, citizen sees flicker on mobile that's hard to attribute.
- OkLCh perceptual uniformity (`frontend/src/lib/colors/oklch.ts`) breaks at any continuous-scale boundary the library owns; Plotly/ECharts interpolate in sRGB.
- Library legends smuggle in click-to-hide-series interactions that survive upgrades; suppressing is a config toggle that must be flipped per chart and re-audited every upgrade.

**Hans (governance — citizen-honest defaults):**
- Plotly's `legend.itemclick` default lets the citizen silently hide a methodology-break series (same disease as the folded-indicator lesson — `/memories/lessons.md` 2026-05-17).
- ECharts' `min: 'dataMin'` default truncates the x-axis to the first non-null observation, dropping pre-coverage years. yen-gov's whole longitudinal honesty story depends on the full domain being shown.
- Observable Plot's line-mark Y-domain is data-fitted (not zero-baselined), exaggerating change over narrow ranges (Rosling's *Size* instinct).
- OWID famously built Grapher rather than adopt Plotly/ECharts/Vega-Lite/Observable Plot. CLAUDE.md §0a says default to OWID; their build-not-buy reasoning is exactly the schema-is-the-design-system rule yen-gov already follows.

### Caveat — single named escape hatch for Phase 1.5

Fowler and Hans both flagged independently: ECharts' `dataZoom` brush is genuinely better than what we'd write for **one** chart family — dense Gantt / PM-term timelines / long fiscal stock-market-style viewports (Phase 1.5 target). It is pure pan/window math with no Y-axis or legend-toggle honesty risk because the brush operates on the time domain only.

**If — and only if** — Phase 1.5 work in native d3 proves disproportionately heavy after a real attempt, open a single-renderer ADR for ECharts:

- lazy-loaded for that route only,
- behind a yen-gov view-model adapter (no ECharts `option` object touches `indicator.schema.json`),
- Hans must sign off on disabled defaults (`legend.show: false`, `toolbox: undefined`, `xAxis.min` explicit, `tooltip` replaced by `ChartTooltip.svelte`),
- bundle measured before and after.

This is **not** a pre-approval for ECharts. It's an explicitly-named escape hatch with named gates, so the next agent does not re-litigate the whole library question for one renderer.

### Rejected libraries (do not re-propose)

- **Plotly.js** — bundle cost (1.1 MB gzip full), parallel contract surface, Canvas/WebGL test escape hatch, citizen-misleading legend-click-hides-series default. Plus historical "Edit in Chart Studio" link in toolbar (suppressible but defaults flip back on minor versions).
- **ECharts as default** — citizen-misleading auto-truncated x-axis default, Canvas-by-default rendering breaks vitest/jsdom tests, parallel `option` contract. *(Permitted only as the named Phase 1.5 escape hatch above.)*
- **Observable Plot** — would still pay 70–80 kB net incremental for capabilities we'd be writing ourselves with d3 primitives we already ship; declarative grammar is no closer to yen-gov view-models than imperative d3 is.
- **Vega-Lite** — same parallel-grammar problem as Plotly/ECharts (already rejected separately under "Free-form chart specification language" in the rejected-alternatives section above).

### What the next agent does about Phase 0.5

Nothing. The decision is recorded. Phase 0.5 is closed. The phase exists in the plan as a pointer; do not run a fresh capability spike. If the Phase 1.5 escape-hatch trigger fires, open a separate ADR — do not edit Phase 0.5.

---

## Phase 0.75 - Chart projection contract

**Status**: contract home ✅ **RESOLVED 2026-05-20** (option C — hybrid, indicator default + optional topic override). Implementation tasks listed below.

**Correction level**: 3 for schema/docs/tests, 4 if it touches multiple renderer adapters.

**Goal**: Define how chart type, sorting, grouping, time-window defaults, and footer actions are selected without per-indicator hardcoding.

### Decision — projection metadata home

**Option C: hybrid. Indicator artifact carries the canonical default in a `presentation` block. Topic-catalogue artifact entries carry an optional `presentation_override` for context-specific framing. Field-level merge (override `sort_policy` without re-specifying `default_projection`).**

**Resolution rule at render time** (consumed by `frontend/src/lib/topic-dispatch.ts`):

```
topic_entry.presentation_override.<field>
  ?? indicator.presentation.<field>
  ?? data-shape-inferred default
```

For election + feature_collection artifacts (which have no indicator row), the catalogue's `presentation` IS the source of truth — same field name, no parallel mechanism.

### How the decision was reached

Commissioned three independent persona reviews on 2026-05-19 — Hans (governance/data-shape semantics), Max (catalogue-scale maintenance), Fowler (storage mechanics). All three rejected option B (topic-only). Their split was Hans/Max favouring pure indicator-block (a) and Fowler favouring hybrid (c). User chose hybrid (c) because the polymorphism case was decisive — election artifacts have no indicator row to defer to, so the catalogue must carry a `presentation` field for them; making it ALSO available as an override for indicators (rare path) is one extra optional field, not a new mechanism.

**Hans (governance):**
- OWID stores `display.type` and `display.chartTypes` per-variable (per-indicator), not per-tag (per-topic). CLAUDE.md §0a → adopt OWID's pattern.
- Sibling-indicator divergence within one topic is decisive: `gdp_per_capita_current_inr` (line) vs `gdp_share_by_sector_pct` (composition_bar) under `economy/national-accounts`; `state-turnout-pct` (line) vs `party-seats-won` (composition_bar) under `elections`. Topic-level default forces one to lie.
- Schema-is-design-system: projection links the WHAT (data shape) to the HOW (renderer); it belongs with the WHAT.
- `methodology.chart_defaults` already exists at `datasets/schemas/indicator.schema.json` line 434 (folded from notes sidecar per ADR-0026); the project has already chosen indicator-block.

**Max (catalogue scale):**
- 108 indicators × 10 topics today; ~150–200 indicators planned by year-end (corpus survey).
- Both `indicator.chart_type` (since v1.2) and `topic-catalogue` per-artifact `chart_type` (since v1.2) already exist; the project is *already running a soft hybrid*, just unnamed. Topic-catalogue's own description says the indicator is the source of truth.
- Bump tool `tools/bump_indicator_schema_to_current.py` is proven (v4.1→v4.2 `where_allocated`, v4.2→v4.3 `sub_metrics`); per-bump cost is one tool invocation + one Tier-A commit, not 108 hand edits.
- Cross-topic indicators (GDP-deflator, state population) need to render the same chart everywhere they appear; topic-keyed model fractures the citizen's mental model when the same series renders differently on two pages.

**Fowler (storage):**
- The 108 `datasets/indicators/in/**/*.json` are slated to die under ADR-0030 canonical pivot; metadata moves to `taxonomy/indicators.parquet`. Putting `presentation` on the indicator artifact today is a clean *Move Field* refactor when the pivot lands — not a sidecar that gets deleted.
- A separate `taxonomy/projections.parquet` would split same-lifecycle facts (data shape and projection always change together) — exactly the inverse of the folded-indicator lesson.
- Per-topic `presentation_override` handles the polymorphism case (election + feature_collection have no indicator row) and the override-on-context case (rare; same indicator, different framing per topic page).

### Rejected projection-home designs (do not re-propose)

- **Topic-only** (option B): forces sibling indicators inside one topic to share one chart type even when their data shapes differ. Hans, Max, and Fowler unanimously rejected.
- **Standalone `taxonomy/projections.parquet` table** (option D, taxonomy-only): splits same-lifecycle facts; a contract surface for a fact that belongs on the indicator row.
- **Free-form chart-spec JSON / Vega-Lite-like grammar** (already in this plan's main rejected-alternatives section): becomes a parallel design system above the schema.
- **Per-indicator-id conditionals in `topic-dispatch.ts`** (already rejected by CLAUDE.md §6 no-hardcoding): violates the closed-renderer rule.

### Implementation tasks (Beck two-hat — structural commits BEFORE behaviour, no fusion)

**Step 1 — structural (schemas only, additive, optional field; no artifact rewrites; no renderer behaviour change):**

- [ ] Define a shared `presentation` `$defs` block: `default_projection`, `eligible_projections`, `sort_policy`, `facet_strategy`, `temporal_viewport`, `footer_actions`. Closed enums per Phase 0.75 enum list (already extended on 2026-05-19 to include `composition_bar`).
- [ ] Add `presentation` (optional) to `datasets/schemas/indicator.schema.json` via `$ref`. Schema minor bump (e.g. v4.3 → v4.4); use the existing `tools/bump_indicator_schema_to_current.py` for the mechanical $schema_version sweep across 108 artifacts.
- [ ] Add `presentation_override` (optional) to `datasets/schemas/topic-catalogue.schema.json` per-artifact entry via `$ref` to the same `$defs`. Schema minor bump.
- [ ] Tier-A discipline (per `/memories/lessons.md` 2026-05-16 #1): pair both schema bumps with the corresponding TS union widening in `frontend/src/lib/indicators.ts` AND the Zod enum in `frontend/src/lib/charts/stacked-trend/types.ts` AND any other Zod enum that mirrors a projection enum. ALL in the same commit.
- [ ] Document data-shape inference produces eligible projections only; authored metadata chooses the default.
- [ ] No artifact populates `presentation` yet; existing `chart_type` field continues to win until step 3.

**Step 2 — structural (renderer dispatch precedence, no visible behaviour change):**

- [ ] Extend `frontend/src/lib/topic-dispatch.ts` to read `topic_entry.presentation_override.*` then `indicator.presentation.*` then fall through to today's `chart_type` / `trio` default. Field-level merge.
- [ ] Vitest covers the precedence rule with three fixtures: (a) override present and field-set → override wins; (b) override absent, indicator.presentation present → indicator wins; (c) both absent → today's default. Behaviour is unchanged because no artifact populates the new fields.
- [ ] Add a guardrail/test: dispatch may not branch on indicator id; reject any new `if (id === "…")` in dispatch via a contract test.

**Step 3 — behavioural (one indicator, one override, one Playwright smoke):**

- [ ] Author `presentation` on ONE indicator artifact (recommend: `installed_capacity_total_mw` — already used by Phase 2 StackedTrend route).
- [ ] Author `presentation_override` on ONE topic-catalogue entry (recommend: a topic where the same indicator should render differently).
- [ ] Playwright smoke (per CLAUDE.md §13): both routes still render; the dispatch picked the authored projection.
- [ ] If smoke is green, deprecate `chart_type` (mark optional + `deprecated: true` in description); do NOT delete yet. Removal is a separate later commit after all 21 indicators currently using `chart_type` have migrated to `presentation.default_projection`.

**Step 4 — canonical-pivot Move Field (out of scope for this plan; inherit when ADR-0030 lands):**

- The `presentation` block on each indicator artifact moves with the rest of the indicator metadata into `taxonomy/indicators.parquet`. Pure *Move Field* refactor; no semantic change. Topic-catalogue's `presentation_override` stays put (catalogue is hand-authored JSON).

### Tests

- [ ] Unit tests for projection eligibility: ranked barred when `comparability` suppresses comparison; time series requires at least two ordered periods; choropleth requires spatial entities; dumbbell requires endpoint metadata; composition_bar requires segments-sum-to-known-whole.
- [ ] Contract test: every value of every projection enum resolves to a known renderer or a documented pending renderer.
- [ ] Contract test: dispatch does not branch on indicator id.
- [ ] Precedence test: override > indicator > inferred default, field-level.

### What the next agent does about Phase 0.75

Start at Step 1. Do NOT re-debate the contract home. The decision is recorded, the rejected designs are listed, the OWID precedent is cited.

---

## Phase 0.85 - Facet-axis registry alignment

**Correction level**: 3.

**Goal**: Give ordered/grouped categories a governed home so charts do not hardcode residence, economic-class, source-category, or sector order.

Tasks:

- [ ] Align with the canonical `taxonomy/facet-axes.json` direction in [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md); use a temporary frontend fixture/bridge only if the canonical registry is not ready.
- [ ] Define facet-axis fields: `id`, `label`, `relationship`, `values[].id`, `values[].label`, `values[].order`, optional group, default colour anchor, and default facet strategy.
- [ ] Seed axes only when backed by committed or explicitly planned yen-gov metadata; likely early candidates are `residence`, `economic_class` / wealth quintile, `power_source`, and `sector`.
- [ ] Document which axes may be value-sorted and which must preserve axis order.

Tests:

- [ ] Axis-order helper tests for committed ordered-axis fixtures such as poorest-to-richest or rural/urban.
- [ ] Contract test: any `sort_policy: axis_order` projection references a registered axis whose values have order.

---

## Phase 1 - Baseline visual audit before changing pixels

**Correction level**: 1 if only screenshots/notes, 2 if test baselines are added.

**Goal**: Capture the current chart feel so polish can be judged against actual routes, not memory.

Representative routes:

- `/t/fiscal`
- `/t/energy`
- `/t/economy`
- one state page with a featured indicator, e.g. `/india/tamil-nadu` or the current canonical state route.

Tasks:

- [ ] Start the frontend dev server from `frontend/` with `bun run dev`.
- [ ] Use integrated browser tools to capture snapshots/screenshots for the representative routes.
- [ ] Record current weak points in this file or a sibling handoff note: StackedTrend, ranked table, small multiples, choropleth ramp/legend.
- [ ] Confirm no pre-existing console errors that would confuse later smoke tests.

Verification:

- [ ] Browser `read_page` confirms routes render.
- [ ] Screenshots or written observations attached to the branch/PR description.

---

## Phase 1.25 - Summary and iconography audit

**Correction level**: 1 for audit only, 2 if tests are added.

**Goal**: Capture the two cross-renderer chrome gaps before changing visual components: summary wording and icon coverage.

Tasks:

- [ ] Audit existing chart summary/readout/headline surfaces and note where they can make unsupported claims across time windows, denominators, `comparability`, or `series_breaks`.
- [ ] Enumerate all `topic.icon` values in [`datasets/reference/in/topic-catalogue.json`](../datasets/reference/in/topic-catalogue.json).
- [ ] Enumerate all `indicator.icon` values in [`datasets/indicators/`](../datasets/indicators/).
- [ ] Compare both sets against `REGISTRY` in [`frontend/src/lib/IndicatorIcon.svelte`](../frontend/src/lib/IndicatorIcon.svelte).
- [ ] List missing registry entries and misleading semantic choices, especially generic `trending-up` / `trending-down` used for GDP, prices, fertility, mortality, pensions, deficits, or expenditure.
- [ ] Decide the first icon surface slice: topic index/header, indicator cards, or chart headers.

Verification:

- [ ] Audit output lists unknown icon ids, weak icon ids, and candidate replacements.
- [ ] `git diff --check` if the audit is written into this TODO or a sibling handoff note.

---

## Phase 1.3 - Icon system: folder-based registry + strict-allowlist build plugin

**Status**: design ✅ **RESOLVED 2026-05-20**. Sub-phases 1.3a–1.3f below.

**Correction level**: 3 for the foundation commit (1.3a — schema/plugin/test seam); 2 for each rollout sub-phase (1.3b–1.3f).

**Goal**: replace the 11-entry hand-pasted REGISTRY with a folder-based icon system so contributors drop SVGs into a folder and they're available by name across the app, without inviting a class of cross-site-scripting bugs that `<script>`/`onload`/`<foreignObject>` inside a stranger's SVG would otherwise enable.

### Decision — three things were chosen together

1. **Folder-based authoring.** Icons live in `frontend/src/lib/icons/<kebab-case-id>.svg`, one file per icon, kebab-case filename = icon id. Drop a file → it's registered. No code change to add an icon.
2. **Build-time inventory, structured rendering, NO runtime `{@html}`.** A small Vite plugin scans the folder, parses each SVG with a strict allowlist parser, REJECTS the build if anything disallowed is found, and emits a virtual module `virtual:icon-registry` that the runtime component imports. The component renders a typed structure (`<path>`, `<circle>`, etc.) — never a raw SVG string. Two layers of defence: malicious bytes are rejected at build, AND the runtime can only emit the typed shape that has no slot for `<script>` even if the parser ever regressed.
3. **No external attribution-required sources.** Lucide / Tabler / Heroicons / Phosphor only (all MIT/ISC, no per-icon attribution). The Noun Project is **explicitly excluded** to avoid attribution complexity. Every icon is stored as a local copy in the folder; no runtime CDN dependency, Holy Law #1 honoured.

### How the decision was reached

- Initial design (2026-05-19): inline REGISTRY pattern (current), extended with the 18 missing ids Jony identified during her audit. User pushed back: a centralised folder is more obvious, easier to maintain, and lets the user drop in icons without code review of path strings.
- Folder design surfaced a security concern (user, 2026-05-20, verbatim): "instead of eager glob - during build we do glob and inventorize - so maliciousness doesn't creep by dropping code in glob? or is there a better way that (agent fowler) would agree to?"
- Commissioned Fowler review (2026-05-20). Fowler verdict: option 2 — build-time inventory plugin with strict allowlist, parsed output kept STRUCTURED, NOT raw SVG strings — because the threat is at the contributor boundary (anyone with commit access can drop a malicious file), AND because Svelte 5's `{@html}` is documented as unsanitised. Closing the threat at the build closes it once.

### Rejected icon designs (do not re-propose)

- **Vite eager glob with `?raw` + `{@html svg}`** — Svelte 5's `{@html}` does not sanitise; SVG inside HTML executes inline `<script>`, fires `onload`/`onclick`, and `<foreignObject>` opens a full HTML island. Vite passes `?raw` bytes through verbatim. Rejected.
- **Runtime DOMPurify wrapping the glob** — defends the citizen's bundle against the citizen's own bundle. Threat is at the contributor boundary, not at runtime. Adds ~20 kB to every page load for zero additional safety over build-time rejection. Rejected.
- **Sprite sheet via `svg-sprite` / svgo plugin pipeline** — svgo's plugin config becomes the de-facto allowlist with no test pinning it; two sources of truth (svgo config + vitest), exactly the drift trap from `/memories/lessons.md` 2026-05-16 #1. Also kills `currentColor` per-icon tinting unless re-engineered. Rejected.
- **Inline REGISTRY of path strings** (current) — works at 11 icons but the 18-icon silent-fallback bug Jony found during the 2026-05-19 audit shows the failure mode: missing ids fall through to a generic circle and nobody notices because no page renders icons yet. Rejected as the long-term home; it's the *starting state* the foundation commit (1.3a) replaces.
- **Files in `frontend/public/icons/` loaded over HTTP** — extra HTTP request per first-paint icon, `<img>` breaks `currentColor` tinting (image is opaque), `<use href>` works but only for same-origin SVG with `stroke="currentColor"` baked in. Slower for static-first; no security improvement over the chosen design. Rejected.
- **The Noun Project** — many icons require CC-BY per-icon attribution; would need a sidecar `_attributions.json` consumed by the About route, plus contributor education on which icons need entries. User explicitly excluded for simplicity. Rejected.
- **Mixing icon sources within one icon family** (e.g. Lucide + Tabler in the same row of chart-action icons) — stroke widths and visual weight differ, breaks visual rhythm. Rule: one source per icon family; document the source in a comment near the file.

### Allowlist (one source of truth)

Elements: `svg`, `g`, `path`, `circle`, `rect`, `line`, `polyline`, `polygon`.

Attributes: `viewBox`, `fill`, `stroke`, `stroke-width`, `stroke-linecap`, `stroke-linejoin`, `fill-rule`, `clip-rule`, `d`, `cx`, `cy`, `r`, `x`, `y`, `x1`, `x2`, `y1`, `y2`, `points`, `transform`. Drop `class`, `width`, `height` from the SVG root (parent class controls size and tint via `currentColor`).

Forbidden — **rejected, not stripped** (build fails loudly with `icons/<file>.svg:<line> disallowed element <name>` so the contributor's intent is not silently laundered): `<script>`, `<style>`, `<foreignObject>`, `<image>`, `<use>` with `href`/`xlink:href`, `<a>`, any `on*=` event handler, any `xlink:*` attribute, inline `width`/`height` on root, inline `style` attributes.

Allowlist lives at `frontend/src/lib/icons/allowlist.ts`. Both the Vite plugin AND the vitest test import from this file — no parallel copies (per `/memories/lessons.md` 2026-05-16 #1 single-source-of-truth lesson).

### Folder layout

```
frontend/src/lib/icons/
  README.md                    # source priority + how to add an icon
  allowlist.ts                 # ALLOWED_ELEMENTS, ALLOWED_ATTRS — one source of truth
  parse.ts                     # pure fn: (svgText, filename) => StructuredIcon | throw
  parse.test.ts                # vitest unit + corpus contract test
  __fixtures__/                # test fixtures only — plugin SKIPS this folder
    good-zap.svg               # canonical lucide-shape
    evil-script.svg            # <script>alert(1)</script>
    evil-onload.svg            # <svg onload="alert(1)">
    evil-foreign.svg           # <foreignObject>
    evil-style.svg             # Noun-Project-style <style> case
    evil-xlink.svg             # external <use href>
    evil-inline-style.svg      # style="background:url(javascript:...)"
  zap.svg, heart.svg, ...      # real icons (one Lucide shape per file)
```

Filenames: kebab-case lowercase only — `^[a-z0-9]+(-[a-z0-9]+)*\.svg$`. Plugin skips `_*` (underscore-prefixed) and `__fixtures__/`. Filename is the icon id.

### Plugin shape (Fowler's sketch — for the next agent to implement, not literal copy)

```ts
// frontend/vite-plugins/icons.ts (sibling to existing plugins in vite.config.ts)
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Plugin } from "vite";
import { parseIconStrict } from "../src/lib/icons/parse";

const VIRTUAL = "virtual:icon-registry";

export function iconRegistryPlugin(iconDir: string): Plugin {
  return {
    name: "yen-gov-icon-registry",
    resolveId(id) { return id === VIRTUAL ? "\0" + VIRTUAL : null; },
    load(id) {
      if (id !== "\0" + VIRTUAL) return null;
      const entries: string[] = [];
      for (const f of readdirSync(iconDir).sort()) {
        if (!f.endsWith(".svg")) continue;
        if (f.startsWith("_")) continue; // skips __fixtures__/ etc.
        const slug = f.slice(0, -4);
        if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug))
          this.error(`icon filename must be kebab-case: ${f}`);
        const raw = readFileSync(join(iconDir, f), "utf8");
        const icon = parseIconStrict(raw, f); // throws on disallowed nodes/attrs
        entries.push(`  ${JSON.stringify(slug)}: ${JSON.stringify(icon)}`);
      }
      return `export const REGISTRY = {\n${entries.join(",\n")}\n} as const;`;
    },
    handleHotUpdate({ file, server }) {
      if (file.startsWith(iconDir)) {
        const mod = server.moduleGraph.getModuleById("\0" + VIRTUAL);
        if (mod) server.moduleGraph.invalidateModule(mod);
      }
    },
  };
}
```

`parse.ts` uses [`htmlparser2`](https://github.com/fb55/htmlparser2) in XML mode (small, no jsdom dep). `IndicatorIcon.svelte` becomes:

```svelte
<script lang="ts">
  import { REGISTRY } from "virtual:icon-registry";
  export let name: string;
  export let cls = "w-5 h-5 text-current";
  $: icon = REGISTRY[name as keyof typeof REGISTRY] ?? null;
</script>
{#if icon}
  <svg viewBox={icon.viewBox} class={cls} fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    {#each icon.paths as p}<path d={p.d} fill={p.fill ?? "none"} />{/each}
    {#each icon.circles as c}<circle cx={c.cx} cy={c.cy} r={c.r} />{/each}
    {#each icon.rects as r}<rect x={r.x} y={r.y} width={r.width} height={r.height} />{/each}
    {#each icon.lines as l}<line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} />{/each}
    {#each icon.polylines as p}<polyline points={p.points} />{/each}
    {#each icon.polygons as p}<polygon points={p.points} />{/each}
  </svg>
{/if}
```

No `{@html}` anywhere. Even if a malicious SVG slipped past `parseIconStrict` (defence-in-depth: the structured shape has no slot for it).

### Source priority (lives in `frontend/src/lib/icons/README.md`)

1. **Lucide** — ISC, no attribution. Default for everything. Covers ~95% of civic-data nouns.
2. **Tabler** — MIT, no attribution. Reach for it when Lucide lacks a specific noun.
3. **Heroicons** — MIT, no attribution. Reserve for chrome where heavier weight reads better.
4. **Phosphor** — MIT, no attribution. Last resort to keep visual family tight.
5. ~~Noun Project~~ — **excluded** (CC-BY attribution complexity; user direction 2026-05-20).
6. **Custom hand-drawn** — yen-gov own work. Last resort. Every custom icon is maintenance debt; only ship one when no library has the noun and no available substitute is honest.

Rule: when adding an icon, copy the SVG source from the library's official site (or its open-source repo); paste contents into `<icon-id>.svg`; commit. Add a single-line comment at the top of the file recording the source: `<!-- source: lucide v0.x / icon-name; license: ISC -->`. The plugin allows comments at the document level (HTML comments).

### Sub-phases (ordered by citizen impact, NOT alphabetical)

#### 1.3a — Foundation commit (replaces the inline REGISTRY)

One mechanical commit, no behaviour change visible to the citizen:

- [ ] Create `frontend/src/lib/icons/` folder with the layout above.
- [ ] Implement `allowlist.ts`, `parse.ts`, `parse.test.ts`, the 7 evil fixtures (`__fixtures__/evil-*.svg`) + 1 good fixture.
- [ ] Implement `frontend/vite-plugins/icons.ts` per the sketch above. Wire into `frontend/vite.config.ts`.
- [ ] Convert the 11 existing inline path entries from `frontend/src/lib/IndicatorIcon.svelte` REGISTRY into 11 SVG files in the new folder.
- [ ] Add the 18 Lucide SVGs Jony's 2026-05-19 audit identified as referenced-but-missing: `car`, `heart-pulse`, `wind`, `cloud`, `vote`, `flame`, `sun`, `atom`, `leaf`, `globe`, `shopping-bag`, `bar-chart`, `construction`, `trash-2`, `credit-card`, `file-text`, `plug`, `fuel`, `package`, `activity`, `download`, `rotate-ccw`, `maximize`, `zoom-in`. (Note: Jony's list also flagged a `droplet` vs `droplets` mismatch in the existing REGISTRY — alias `droplet` → `droplets.svg` or rename the file; pick one explicitly in the commit.)
- [ ] Rewire `IndicatorIcon.svelte` to import from `virtual:icon-registry` per the sketch above.
- [ ] Tier-A test: `parse.test.ts` asserts every `evil-*.svg` throws with a specific error class; `good-zap.svg` parses to expected `{paths: [{d: "…"}]}`. Real fixtures, no mocks (Holy Law #7).
- [ ] Corpus contract test: read every `*.svg` in `frontend/src/lib/icons/` (excluding `__fixtures__/`) and assert each parses successfully via `parseIconStrict`. Catches future drop-ins before they reach the bundle.
- [ ] Component test: render `<IndicatorIcon name="zap" />`, assert one `<path>` with the expected `d` attribute.
- [ ] Catalogue contract test (resurrects Phase 1.3 original intent): for every `topic.icon` in `datasets/reference/in/topic-catalogue.json` AND every `indicator.icon` in `datasets/indicators/`, assert the id exists in the icons folder. Fails loudly when a new artifact references an unknown icon.
- [ ] No citizen-visible page renders an icon yet — that's 1.3b onward.

**Definition of Done for 1.3a**: `bun run check` + `bun run test` green; `bun run dev` cold-start succeeds; `bun run build` succeeds with zero warnings; `<IndicatorIcon name="zap" />` renders the same SVG it did before the rewrite (visual equivalence).

#### 1.3b — Topic index `/t` cards

Front door of the site; sets visual identity for every topic surface that follows.

- [ ] Render `topic.icon` in `frontend/src/routes/TopicIndex.svelte`.
- [ ] Playwright smoke per CLAUDE.md §13: `/t` shows one icon per topic card, no console errors.

#### 1.3c — Topic landings (deep topic pages)

H1 inherits the identity the citizen just clicked on the index.

- [ ] Render `topic.icon` in `frontend/src/routes/TopicLanding.svelte` (`/t/<topic>`).
- [ ] Render `topic.icon` in `frontend/src/routes/StateTopic.svelte` (`/india/<state>/t/<topic>`).
- [ ] Playwright smoke: one route per renderer.

#### 1.3d — Indicator cards (the most-repeated grid)

Earns its keep by making 12-card grids scannable in one fixation.

- [ ] Render `indicator.icon` in `frontend/src/lib/IndicatorCard.svelte`.
- [ ] Playwright smoke on a state hub or topic landing that renders ≥6 cards.

#### 1.3e — Chart headers

Indicator icon inline with chart title; cements "this chart is about X" before the eye reaches the y-axis.

- [ ] Render `indicator.icon` in `frontend/src/lib/IndicatorRanked.svelte`.
- [ ] Render `indicator.icon` in `frontend/src/lib/IndicatorSmallMultiples.svelte`.
- [ ] Render `indicator.icon` in `frontend/src/lib/charts/StackedTrend.svelte`.
- [ ] Render `indicator.icon` in `frontend/src/lib/IndicatorChoropleth.svelte`.
- [ ] Playwright smoke per renderer.

#### 1.3f — State hub section chips + leaf pages + chrome

State-hub elections / government / topic chips; deep-link election surfaces; About / Disclaimer / Settings / DataCompleteness / Explore / CompareIndicator. LeftRail stays text-only per Phase 1.3 original contract — defer until a UI review proves group-level icons help scanning.

- [ ] Render section-chip icons in `frontend/src/routes/StateOverview.svelte`.
- [ ] Render identity icons on `Constituency.svelte`, `Party.svelte`, `Compare.svelte`, `Psephlab.svelte`, `About.svelte`, `Disclaimer.svelte`, `Settings.svelte`, `DataCompleteness.svelte`, `Explore.svelte`, `CompareIndicator.svelte`.
- [ ] Playwright smoke on one election surface and one chrome surface.
- [ ] LeftRail: no change.

### Tests (cross-sub-phase)

- [ ] `parse.test.ts` (1.3a) — strict allowlist, real fixtures.
- [ ] Corpus contract (1.3a) — every SVG in folder parses.
- [ ] Catalogue contract (1.3a) — every `topic.icon` / `indicator.icon` exists in folder.
- [ ] Component test (1.3a) — one icon renders the expected `<path>`.
- [ ] Per-sub-phase Playwright smoke (1.3b–1.3f) — one route per renderer wired.

### Eventual home in docs

When this phase ships, lift this entire section (decision + rejected designs + allowlist + folder layout + plugin sketch + source priority + sub-phase order) into `docs/architecture/frontend/icons.md` as the canonical UI/UX design doc per Holy Law #4 (docs = agent memory, one home per concept). Reference it from `docs/concepts/schema-is-the-design-system.md` and from `docs/architecture/frontend/overview.md`. Delete the section from this TODO when the doc lands.

### What the next agent does about Phase 1.3

Start at 1.3a. Do NOT re-debate the storage model, the allowlist, the source priority, or the Noun Project exclusion. The decisions are recorded; the rejected designs are listed. Implement 1.3a as one Tier-A foundation commit; ship 1.3b–1.3f as one citizen-visible commit per sub-phase.

---

## Phase 1.4 - Chart shell and action footer

**Correction level**: 3.

**Goal**: Standardise the chart footer/action pattern using yen-gov source provenance.

Tasks:

- [ ] Introduce a shared chart shell/footer primitive that can host title, subtitle, honesty banners, source disclosure, and allowed actions.
- [ ] Evolve [`frontend/src/lib/SourceList.svelte`](../frontend/src/lib/SourceList.svelte) into SourceList v2: collapsed authority/vintage line, expanded exact URLs/citation/licence/provenance details.
- [ ] Keep the triangle disclosure pattern for sources; default collapsed on dense chart pages.
- [ ] Add footer action slots for `view_data`, `download`, `copy_link/share`, `reset_view`, and `full_range`; actions appear only when the view-model says they are useful.
- [ ] `View data` should show the currently visible chart/window first, not the whole indicator corpus.
- [ ] `Share` should copy the current route/view state once URL contracts exist for that route.

Tests:

- [ ] Unit tests for source summary formatting: producer/authority/vintage fallback, host fallback, empty hand-authored source case.
- [ ] Component/e2e test: source disclosure expands and collapses; expanded state shows at least one upstream URL when available.
- [ ] Component/e2e test: action footer does not render unapproved controls.

---

## Phase 1.5 - Temporal viewport interaction primitive

**Correction level**: 3.

**Goal**: Add Plotly-like range navigation where it is useful, without inheriting Plotly's full modebar.

Target chart families:

- minister/tenure Gantt timelines,
- long fiscal/economy/prices line or area charts,
- dense party/election history charts,
- any future `TimeSeriesLine` renderer.

Core interaction:

- [ ] Full domain remains known to the chart, e.g. `1947 -> 2019`.
- [ ] Visible domain is a window, e.g. `1977 -> 2004`.
- [ ] Below the chart, a compact overview strip or brush allows dragging/resizing the visible window.
- [ ] Presets: `All`, `Recent`, `10y`, `25y` or chart-appropriate equivalents.
- [ ] Reset control returns to full range.
- [ ] Optional pan/zoom only on dense timeline charts; not universal.
- [ ] Window state should be shareable in the URL for full-page chart routes; local component state is acceptable for embedded summaries until a route contract exists.

Implementation options:

- [ ] **Default: Native Svelte+d3 brush/scale helper.** Phase 0.5 resolved 2026-05-20 to build native for every renderer; this is the starting point.
- [ ] **Named escape hatch (only if native attempt is disproportionately heavy):** ECharts `dataZoom` brush behind a yen-gov view-model adapter, lazy-loaded for this route only. Requires a single-renderer ADR + Hans sign-off on disabled defaults (`legend.show: false`, `toolbox: undefined`, `xAxis.min` explicit, tooltip replaced by `ChartTooltip.svelte`) + bundle measurement before/after. See Phase 0.5 "Caveat — single named escape hatch" for full gates. Do NOT add the dependency before the ADR lands.

Tests:

- [ ] Pure helper tests for clamping, preset-window calculation, and date parsing.
- [ ] Component/e2e test: drag or preset changes visible range and reset returns to full range.

---

## Phase 1.6 - Sorting, grouping, and projection helpers

**Correction level**: 3.

**Goal**: Move chart sorting/grouping decisions out of Svelte templates and into tested view-model helpers.

Tasks:

- [ ] Add pure helpers for `sort_policy` application: value asc/desc, axis order, chronological, pinned-then-value, rank-best-first, latest-change, alphabetical.
- [ ] Add helpers that build view-models for `ranked_bar`, `ordered_category_bar`, `horizontal_grouped_bar`, `facet_panel_grid`, `dumbbell_range`, and `time_series_line` candidates.
- [ ] Nulls/missing values stay visible and sort last unless the projection explicitly filters them.
- [ ] Shared-scale decisions for faceted panels must be explicit in the view-model.
- [ ] Direct labels should be part of the view-model where the renderer needs stable label eligibility.

Tests:

- [ ] Sorting tests: stable ties, nulls last, higher/lower direction, pinned home/compare rows, axis order.
- [ ] Grouping tests: rural/urban panels share scale when requested; economic-class bars preserve axis order.
- [ ] Dumbbell/range tests: missing endpoint, zero endpoint, delta/gap label.
- [ ] Time-series tests: direct-end-label data, visible-window filtering, series-break suppression.

---

## Phase 2 - StackedTrend v2 polish

**Correction level**: 3. This is the highest-value first coding phase.

**Goal**: Bring [`frontend/src/lib/charts/StackedTrend.svelte`](../frontend/src/lib/charts/StackedTrend.svelte) closer to its own design doc, without adding a charting dependency.

### 2.1 Structural view-model helpers

- [ ] Add pure helpers under `frontend/src/lib/charts/stacked-trend/` for per-bar totals, percent share, visible category set, label eligibility, and readout rows.
- [ ] Unit tests cover percent and absolute modes, zero totals, `__OTHER__`, missing values, and `not_applicable`.
- [ ] Keep the zod `StackedTrendModel` as the adapter/component boundary.

### 2.2 Segmented mode control

- [ ] Replace the passive `Mode ABSOLUTE/PERCENT` label with a real segmented control.
- [ ] Modes: `percent` and `absolute`, seeded from `model.default_mode`.
- [ ] Persist user-driven mode in URL query where the containing route already has a URL contract; otherwise keep it local to the component until a route-level contract is added.
- [ ] No localStorage for mode; shareable URL beats sticky hidden state.

Tests:

- [ ] Vitest for mode derivation.
- [ ] Playwright assertion that toggling mode changes visible scale/readout text on one topic route.

### 2.3 Pinned readout panel

- [ ] Replace native `title` tooltip dependence with a Svelte-rendered readout panel above or immediately below the chart.
- [ ] Hover/tap selects a bar; readout lists each category with colour chip, absolute value, and percent share.
- [ ] Unhovered bars may dim to ~0.45 opacity while selected bar stays full opacity.
- [ ] Mobile tap should select; tapping outside/different bar changes selection. No floating tooltip that hides bars.

Tests:

- [ ] Component or integration test for readout row generation.
- [ ] Playwright hover/tap smoke on a route that renders StackedTrend.

### 2.4 Inline labels and leader labels

- [ ] Implement the design doc's 3-tier rule: inline labels for large segments, leader/outside labels for medium segments if feasible, legend-only for small segments.
- [ ] Labels must use category labels, not raw facet ids.
- [ ] Keep text fitting stable on mobile; if leader labels are too costly for v1, ship inline + legend-only and document the deferral.

Tests:

- [ ] Pure label-eligibility helper tests.
- [ ] Screenshot check on `/t/energy` or whichever route has power-source StackedTrend.

### 2.5 Missing and not-applicable hatch

- [ ] Render `availability: "missing"` and `"not_applicable"` distinctly from true zero.
- [ ] Use a light grey hatch or clearly labelled placeholder, matching the map no-data convention.
- [ ] Readout must explain the difference in plain language.

Tests:

- [ ] Fixture with one missing segment and one true zero.
- [ ] Visual smoke confirms true zero is not drawn as missing data.

### 2.6 Subtle motion

- [ ] No entrance animation.
- [ ] Add a 200ms height tween only on mode changes or data changes.
- [ ] Respect reduced-motion preference.

Tests:

- [ ] Unit coverage for reduced-motion branch if logic is extracted.
- [ ] Manual/browser smoke is enough for animation if no clean test seam exists.

### 2.7 Export control

- [ ] Add a small explicit download control only if the chart is useful as a standalone artifact.
- [ ] Prefer SVG export for SVG-authored charts; add PNG export only when needed.
- [ ] Do not add a multi-icon modebar. One icon/button near the chart title or source row is enough.
- [ ] Exported image should include title, visible date window, legend, and source/provenance summary where feasible.

Tests:

- [ ] Unit test the export serializer if implemented as a helper.
- [ ] Browser smoke that clicking export produces a downloadable file or blob URL without console errors.

Phase 2 Definition of Done:

- [ ] `bun run check` in `frontend/`.
- [ ] `bun run test` in `frontend/`.
- [ ] Relevant Playwright spec added/updated if citizen-visible route changes.
- [ ] Browser smoke on `/t/energy` or another StackedTrend route shows: segmented mode, readout panel, legend, source list, no console errors.

---

## Phase 3 - Ranked comparison polish

**Correction level**: 2.

**Goal**: Make [`frontend/src/lib/IndicatorRanked.svelte`](../frontend/src/lib/IndicatorRanked.svelte) feel like a comparison chart, not only a table.

Tasks:

- [ ] Add a median marker or peer-band marker to the inline bar area.
- [ ] Make the home state pin visually stronger but still quiet: left accent, stronger value chip, or pinned mini-summary above table.
- [ ] When compare state is selected, show a plain-language gap line: "Tamil Nadu is X above/below Karnataka" with direction-aware wording.
- [ ] Preserve existing honesty rule: suppress rank when `comparability: not_comparable_across_states`.
- [ ] Keep peer-set filters honest; rank within the selected peer set only.

Tests:

- [ ] Unit test for median/peer marker calculation.
- [ ] Unit test for direction-aware gap wording.
- [ ] Existing ranked tests stay green.
- [ ] Playwright assertion on one topic route: home/compare/median marker visible where data supports it.

---

## Phase 3.5 - Generic comparison renderers

**Correction level**: 3.

**Goal**: Add the small set of generic comparison renderers implied by the chart grammar, once projection helpers exist.

Candidate renderers:

- [ ] `HorizontalGroupedBar`: two or more measures/facets per row, grouped by a registered axis.
- [ ] `OrderedCategoryBar`: ordered categories such as poorest-to-richest, age bands, education levels, or survey classes.
- [ ] `DumbbellRange`: two comparable endpoints per row, with endpoint roles supplied by metadata.
- [ ] `TimeSeriesLine`: one or more lines with direct end labels and optional temporal viewport.
- [ ] `FacetPanelGrid`: shared chart shell for rural/urban, sex, class, sector, or other registered facets.
- [ ] `CompositionBar`: single-entity, single-period horizontal 100%-stacked bar; segments sum to a known whole (seat count, total population, power-mix total MW, expenditure total); a tail bucket (`Other`, `Not stated`) is materialised as a visible segment whenever the underlying data has one, never hidden in a footnote; segment fills come from the relevant dimension's colour anchor (party palette for `elections/results/`, axis colour anchor for socio-economic facets); explicitly forbids becoming a donut, pie, or sunburst variant. Single-entity is the v1 surface; multi-entity composition only inside `FacetPanelGrid` when Phase 0.75's (a)(b)(c) guard holds. See Phase 3.6 for the first shipping slice.

Rules:

- [ ] Do not ship a renderer for a single bespoke indicator unless the user explicitly approves the exception.
- [ ] Each renderer consumes a typed view-model produced by an adapter/helper.
- [ ] Each renderer uses the shared chart shell/footer and SourceList v2.
- [ ] Each renderer has a documented projection enum and tests before topic dispatch uses it.

Verification:

- [ ] One fixture per renderer shape.
- [ ] Browser smoke on one route per shipped renderer.

---

## Phase 3.6 - Single-entity composition bar (side-by-side smoke)

**Correction level**: 3.

**Goal**: Ship the first shipping slice of `CompositionBar` (Phase 3.5 candidate) as a generic single-entity, single-period horizontal 100%-stacked bar, mounted **side-by-side with the existing election composition chart** so a human observer can A/B the two encodings on a real route. No URL toggle, no `?experimental=` flag, no feature config — placement is purely structural so removal is `git revert`-trivial.

**Why a dedicated phase instead of part of Phase 3.5**: this is the slice where the renderer's correctness and the dimension binding (party palette, NOTA wedge, FPTP framing) get exercised against real data. Phase 3.5 lists the contract; Phase 3.6 ships the first instance.

**Background**: 2026-05-19, the user surfaced a Gujarat+Himachal 2017 concentric sunburst for evaluation. Jony + Hans + Max independently rejected the multi-entity sunburst (see "Rejected alternatives" above). The honest composition encoding is a single-entity 100%-stacked bar with visible Others and visible NOTA; this phase ships that primitive, scoped to single-entity to keep v1 small and to defer the multi-entity question until Hans's Phase 0.75 guard rule can be satisfied with named comparative framing and real data.

**Renderer (generic, NOT election-specific)**:

- [ ] Component path: `frontend/src/lib/CompositionBar.svelte`.
- [ ] Props: a typed view-model (`label`, `total_value`, `total_unit`, `segments: { id, label, value, fill, swatch_role }[]`) — no domain logic in the renderer.
- [ ] Tail handling: when the upstream adapter emits an `others` segment, it renders as a visible swatch in the bar with its own label; the renderer never collapses tail to a footnote. Adapter is responsible for top-N + tail aggregation (Phase 1.6 helper).
- [ ] Fill: segment fills are passed in by the adapter; renderer never knows about parties, power sources, or age bands.
- [ ] Footer: reuse the shared chart shell + SourceList v2 (Phase 1.4). No bespoke footer.
- [ ] Forbidden: do NOT add a `variant: "donut" | "pie" | "sunburst"` prop. The whole point of this renderer is that it is NOT a radial composition chart. If a future surface wants a donut/arc for a known reason (e.g. parliamentary chamber metaphor), use `SeatDonut` / `ParliamentArc` (which already exist for single-state geometry) — do NOT generalise this renderer.

**Election binding (adapter, NOT renderer)**:

- [ ] Adapter helper: `frontend/src/lib/charts/composition-bar/adapter-elections-seats.ts` (or equivalent path under the existing `frontend/src/lib/charts/` convention).
- [ ] Input: `party-seats-won` rows for one `(state, election_event)` pair from the canonical store. No new materialized indicators required — see "Data inputs" below.
- [ ] Top-N + tail: reuse the existing helper that already feeds `SeatDonut` for top-N candidate handling (Phase 1.6 sorting/grouping helpers). Cutoff is a UX concern carried by the adapter, not a materialized fact.
- [ ] NOTA: render NOTA as its own swatch with the existing NOTA colour anchor; for elections older than 2013 NOTA is null and the segment is absent. The renderer is agnostic; the adapter decides whether NOTA is present.
- [ ] Party palette: source fills from the existing party-colour anchor system (Phase 2 / `PARTY-COLORS-REWORK.md`). No hardcoded colours in the adapter.
- [ ] Caption / framing: the FPTP doctrine footnote already used by [`frontend/src/lib/charts/stacked-trend/adapter-elections.ts`](../frontend/src/lib/charts/stacked-trend/adapter-elections.ts) line 165 is the canonical wording for FPTP context; reuse the exact string, do not paraphrase.

**Summary copy rules (Hans, 2026-05-19)**:

- [ ] Election composition summaries MUST suppress dominance verbs (`swept`, `dominated`, `crushed`, `routed`, `wiped out`) when the vote-share gap between the top two parties is <8 percentage points. Acceptable wording fixture: `BJP won 99 of 182 seats (54%) with 49% of votes cast; INC won 77 seats (42%) with 41%.` Forbidden: `BJP swept Gujarat in 2017.`
- [ ] Summary copy must name the chamber size (e.g. `182 seats`) once at the top so the citizen has the denominator without reading the bar.
- [ ] Add an enforcement test in the chart-summary contract suite (Phase 1.25): given a fixture where top-two vote-share gap is <8pp, no dominance verb appears.

**Side-by-side mount (Correction Level 2 within this phase — propose-and-confirm)**:

- [ ] Mount the new `CompositionBar` adjacent to the existing `<SeatDonut>` on the state hub elections section in [`frontend/src/routes/StateOverview.svelte`](../frontend/src/routes/StateOverview.svelte) (current `<SeatDonut>` mount is around line 561). Two charts visible at once, same data binding, no URL flag distinguishing them. Both render whenever the elections card renders.
- [ ] Removal contract: deleting `CompositionBar` is approximately three lines — the `<CompositionBar indicator={...} />` element + the `import CompositionBar from "../lib/CompositionBar.svelte";` line + (if added) the adapter import. No URL parser change, no feature flag, no analytics event to clean up.
- [ ] If the side-by-side smoke proves the new chart does NOT earn its keep (Jony / Hans review at end of phase), a single revert removes it; the renderer file and adapter file remain in the repo as Phase 3.5 inventory but with no live mount.

**Data inputs (already in canonical store — NO new materialized indicators required)**:

- [ ] `party-seats-won` (per `(state, election_event, party)` row) — already materialised, see [`docs/architecture/data/elections-indicators.md`](../docs/architecture/data/elections-indicators.md).
- [ ] `party-vote-share-pct` — already materialised; used only by the summary copy rule for the dominance-verb suppression check, not yet rendered in v1.
- [ ] `state-nota-pct` — already materialised; null pre-2013.
- [ ] Top-N + tail aggregation: client-side in the adapter using the Phase 1.6 helper. Doctrine: "cutoff is a UX concern, not a fact."
- [ ] Seat-share percentage: derived client-side (`seats / sum(seats) * 100`); not materialised because it's trivially recomputable and would only add storage churn.
- [ ] NO alliance binding in v1 — see "Deferred work — re-enter when data is acquired" below.

**Tests**:

- [ ] Unit: top-N + tail helper against fixtures with N=2, N=5, N=8 segments and a single-party degenerate case (e.g. one party holds 99 of 182, others split the rest).
- [ ] Component (vitest): renderer accepts a view-model with a tail segment and emits a visible swatch for it.
- [ ] Component (vitest): renderer accepts a view-model with NO tail segment and does NOT emit a placeholder.
- [ ] Contract (vitest): chart-summary suite asserts no dominance verb appears when top-two vote-share gap is <8pp (fixture: Gujarat 2017 BJP 49% vs INC 41% — 8pp on the borderline; assert summary uses neutral verbs).
- [ ] Playwright (e2e): on the chosen state hub route (likely `/s/<state>` for a state with both a `SeatDonut`-eligible and `CompositionBar`-eligible payload — TN works), assert BOTH `<SeatDonut>` AND `<CompositionBar>` render in the same elections card.
- [ ] §13 UI verification: agent opens the route in the integrated browser, confirms both charts render without console errors, screenshots for visual comparison.

**Definition of Done**:

- [ ] `CompositionBar.svelte` ships with view-model contract documented at the top of the file.
- [ ] Adapter ships with FPTP caption reused verbatim from the StackedTrend elections adapter.
- [ ] Side-by-side mount on the chosen route visible at `http://localhost:5173/india/<state>` (Tamil Nadu was the user's most-recently-browsed state — use as the primary smoke target unless the user picks otherwise). NOTE: the canonical URL grammar is the place-first scheme `/india/<state>` per [ADR-0028](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md); the legacy `/s/<state>` grammar is rewritten by `RedirectLegacyUrl.svelte` (strangler-fig) until the iced-bulk-ingest Phase 3 work lands. Smoke against the canonical URL; the redirect handles legacy bookmarks.
- [ ] Summary copy fixture passes the dominance-verb-suppression contract test.
- [ ] No new schemas introduced (renderer takes a view-model; adapter consumes existing canonical-store fields).
- [ ] Tier-A discipline holds: if any TS union was widened (`default_projection`), the Zod widening shipped in the same commit (see /memories/lessons.md 2026-05-16 #1).

**Mount route — resolved 2026-05-19**: state hub `StateOverview.svelte` (currently hosts `<SeatDonut>` around line 561), Tamil Nadu as primary smoke target. Canonical URL `/india/tamil-nadu` per ADR-0028; legacy `/s/tamil-nadu` rewrites via the strangler-fig until iced-bulk-ingest Phase 3 lands. No URL toggle, no `?experimental=` flag — `<CompositionBar />` is mounted unconditionally adjacent to `<SeatDonut />` so removal is `git revert`-trivial.

---

## Phase 4 - Small multiples polish

**Correction level**: 2.

**Goal**: Make [`frontend/src/lib/IndicatorSmallMultiples.svelte`](../frontend/src/lib/IndicatorSmallMultiples.svelte) better at showing trajectory, acceleration, plateau, and breaks.

Tasks:

- [ ] Add a subtle shared baseline or zero line when the domain includes zero.
- [ ] Use a signed y-scale when values can be negative. Do not rely on `Math.abs` for domains where negative values are meaningful.
- [ ] Make latest value/dot more legible: stronger dot, small value chip, or last-value label.
- [ ] Home and compare states should have distinct but restrained treatments.
- [ ] Reuse existing series-break metadata to render dashed markers consistently.
- [ ] Keep no-data placeholders visible; do not drop states silently.

Tests:

- [ ] Pure helper tests for y-domain and path generation with negative values.
- [ ] Fixture with a series break.
- [ ] Browser smoke on a long-history topic route.

---

## Phase 5 - Choropleth confidence tuning

**Correction level**: 2.

**Goal**: Keep [`frontend/src/lib/IndicatorChoropleth.svelte`](../frontend/src/lib/IndicatorChoropleth.svelte) structurally the same, but make maps feel more confident and responsive.

Tasks:

- [ ] Review `sequentialSwatch()` in [`frontend/src/lib/indicators.ts`](../frontend/src/lib/indicators.ts) for whether the current `L: 0.94 -> 0.44` and `C: 0.04 -> 0.17` range is too restrained on real maps.
- [ ] If tuning, do it with OkLCh and tests/screenshot review. Do not switch to a diverging or rainbow palette.
- [ ] Add/update a small visual-ramp fixture page or test helper if useful.
- [ ] Add smoother fill updates on time-slider movement if MapLibre paint updates can animate without violating reduced-motion.
- [ ] Make legend-current-value relationship stronger: selected year/value chip, tighter legend labels, or clearer min/mid/max ticks.

Tests:

- [ ] Existing colour tests stay green.
- [ ] Add one test for ramp monotonicity if the ramp math changes.
- [ ] Browser smoke on one choropleth route with time slider.

---

## Phase 6 - Optional internal exploration sandbox

**Correction level**: 3 if it adds a dependency or admin route.

**Goal**: If the team still wants Plotly/ECharts/Observable-style freedom beyond the approved timeline/export interactions, put it where it belongs: internal exploration first, or a specifically approved library-backed renderer.

Accepted shape:

- [ ] Admin-only or `/explore`-only experimental chart surface.
- [ ] Lazy-loaded so the public landing bundle does not pay the cost.
- [ ] Consumes yen-gov query/view-model output, not raw arbitrary files.
- [ ] Clearly labelled as exploratory, not canonical citizen rendering.
- [ ] If promoted to public frontend, backed by the Phase 0.5 matrix and an ADR.

Rejected shape:

- [ ] No unapproved Plotly/ECharts/Vega dependency in the public renderer set.
- [ ] No per-topic bespoke chart library wrappers.
- [ ] No chart-spec JSON committed as an alternative contract unless a future ADR explicitly approves it.

If adding a dependency:

- [ ] Edit `frontend/package.json` only if necessary.
- [ ] Run `bun install` in `frontend/` and stage `frontend/bun.lock` with the manifest change.
- [ ] Document bundle-size impact.

---

## Phase 7 - Documentation, tests, and smoke closure

**Correction level**: follows whatever phases changed runtime behaviour.

Tasks:

- [ ] Update [`docs/architecture/frontend/overview.md`](../docs/architecture/frontend/overview.md) visualization catalog if any component behaviour changed materially.
- [ ] Update [`docs/architecture/frontend/charts/stacked-trend.md`](../docs/architecture/frontend/charts/stacked-trend.md) so it reflects what actually shipped.
- [ ] Update [`docs/architecture/frontend/colours.md`](../docs/architecture/frontend/colours.md) if ramp or categorical colour semantics change.
- [ ] Add or update e2e coverage for the highest-traffic changed route.
- [ ] Run `bun run check`, `bun run test`, and relevant `bun run test:e2e` from `frontend/`.
- [ ] Agent browser smoke per `CLAUDE.md` section 13 on each changed citizen route.
- [ ] Grep for `[DEBUG]` before finalising.

## Out of scope for this plan

- Frontend framework rewrite.
- SvelteKit migration.
- Replacing MapLibre.
- Changing the canonical data store or DuckDB-WASM approach.
- Per-indicator bespoke chart components.
- Generic analytics toolbar on every chart.
- Mixed icon-library redesign or decorative illustration system.
- Source logos, ministry logos, state emblems, and party symbols as indicator icons.
- Free-form chart-spec JSON / Vega-lite clone as a persisted contract.
- Per-indicator hardcoded sort/chart dispatch.
- New socio-economic ingests.
- Accessibility compliance work. Project-level a11y remains descoped per `CLAUDE.md`.
- Decorative landing-page redesign.
- Nested sunburst / multi-ring radial / composite-circle composition charts (see "Rejected alternatives" for the full reasoning; do not re-propose).

## ⚠️ DEFERRED WORK — re-enter when data is acquired or a named comparative question lands

The items below are NOT "won't do." They are "cannot do honestly with what's in the canonical store today, or with the framing the current v1 routes carry." Each one is shovel-ready the moment the gating condition flips. Future planners: re-read this section BEFORE proposing anything sunburst-shaped, multi-state-composition-shaped, or alliance-shaped — the work is already scoped here and waiting for its trigger.

### DEFERRED-A: Alliance rollups for election composition

**Status**: blocked on data acquisition.

**Why it matters**: Indian state politics is alliance-led in most coalition-heavy states (TN, MH, BR, KA, KL, JH, partially MP/UP/WB). Showing only party-level composition for DMK+INC+VCK+CPI+CPM as five separate segments instead of one DMK-led-alliance segment misframes the verdict; the citizen reads "no party won a majority" when the political reality is "the DMK-led alliance won 159 of 234." Party-only composition (Phase 3.6 v1) is correct for two-party-dominant states (GJ, HP, UK, KA, MP) and is the honest first slice given current data, but it is structurally incomplete for the coalition states.

**Gating condition**: observation rows in the canonical store for alliance-grain election indicators.

**Required indicators (none of which exist today)**:

- `alliance-seats-won` per `(state, election_event, alliance_id)`.
- `alliance-seat-share-pct` (trivially derived once `alliance-seats-won` exists).
- `alliance-vote-share-pct` per `(state, election_event, alliance_id)`.
- `state-winning-alliance-id` per `(state, election_event)`, null for hung verdicts.
- `state-effective-alliances-laakso` (parallel to `state-effective-parties-laakso`).

**What exists today**: `datasets/taxonomy/dim_party_alliances.parquet` (the alliance dimension table) — but **zero observation rows** keyed to alliances. The dimension is provisioned; the facts are missing.

**Likely data sources** (user 2026-05-19: "I'll try to find those data sets"):

- TCPD (Trivedi Centre for Political Data, Ashoka) — has alliance maps for some states some years.
- Lokdhaba — same upstream as TCPD.
- ECI alliance affidavits filed pre-poll (per the symbol allocation order).
- Manual curation per state × election (slow but exhaustive); CSDS post-poll surveys sometimes carry alliance attribution.

**Re-entry trigger**: when an ingest commit lands observation rows for `alliance-seats-won` covering at least one state × election event (e.g. TN 2021 or MH 2019), reopen Phase 3.6 to add an alliance-binding adapter (`adapter-elections-alliance-seats.ts`) that swaps `dim_parties` for `dim_party_alliances` in the same `CompositionBar` renderer. The renderer needs zero changes — it is dimension-agnostic by design (Phase 3.6 contract).

**Citizen UX when alliance data lands**: the elections card on the state hub renders both `CompositionBar`s — party composition on the left, alliance composition on the right, with a one-line caption explaining the relationship. For states with no alliance (single-party verdict like GJ 2022), the alliance bar degenerates to the party bar and the caption explains why.

---

### DEFERRED-B: Multi-state composition

**Status**: blocked on (a) Hans's (b) and (c) guard rules from Phase 0.75 being satisfied by a real route, plus (b) a named comparative question existing in the page editorial.

**Why it matters**: There are legitimate multi-state composition questions ("How did BJP's seat share evolve across the Hindi belt 2017→2022?", "Which southern states gave a majority to a Dravidian-party-led alliance in each election?"). Phase 0.75's guard rule is what makes such a view honest: the question is named, the encoding is ratio-only (so chamber-size differences across states do not visually distort), the peer set is principled (Hindi belt, Dravidian states, etc. — NOT "two states that happened to vote in the same calendar year").

**Why deferred (not in v1)**: Phase 3.6 v1 ships single-entity composition because (a) the user's primary v1 goal is shipping ONE new chart side-by-side with the existing one for visual A/B; (b) the routes that currently host election composition (state hub elections card) are single-state by construction — they answer "what did this state decide?", not "how did the Hindi belt vote?"; (c) no compare route exists today that frames a named multi-state question.

**Re-entry trigger**: when a route ships that has a named multi-state question in its editorial copy AND the data is ratio-only — typical example would be `/elections/compare/?states=GJ,HP,UP&year=2017` with a written framing like "How did BJP's seat share compare across these three BJP-vs-INC states in 2017?". At that point, mount `<FacetPanelGrid>` containing one `<CompositionBar>` per state, with state identity in the panel title and party identity in the segment fill (per Phase 0.75 multi-entity composition guard, sub-rule "entity identity in panel title, never in segment fill").

**Forbidden re-entry shape**: do NOT re-introduce the sunburst/nested-radial shape that this plan rejected on 2026-05-19. The guard rule explicitly says ratio-only encoding and named comparative question; it does NOT say "use a composite circle with two centres." If a future planner wants to revisit the radial shape, re-read the "Rejected alternatives" section first.

---

### DEFERRED-C: `categorical_choropleth` projection

**Status**: blocked on a separate scoping pass with Hans (hung-verdict labelling) and Jony (swatch-grid legend visual design).

**Why it matters**: "Who won where" maps are a foundational election visualisation. The existing `choropleth` projection is sequential (low→high ramp); a categorical choropleth uses nominal fills (party-anchor palette) with a swatch-grid legend (not a ramp). It is distinct from sequential `choropleth` at the renderer level (legend semantics differ, colour interpolation is forbidden, the dark=more-of-thing rule does NOT apply) and warrants its own enum.

**Why deferred (not in v1)**: it is structurally separate from the composition question Phase 3.6 addresses. Composition answers "what did one state decide?"; categorical choropleth answers "who won where across the country/state map?" Bundling them into one phase would force premature decisions on hung-verdict treatment (does a hung verdict get a striped fill, an outline, a separate swatch, or no fill?) and on swatch-legend density (8 parties? 15? collapse to "Other"?). Both are non-trivial design questions that deserve dedicated debate.

**Re-entry trigger**: when there is a route that needs a "largest party by state" map view — typically a post-election results page (`/elections/<event>/map`) or a historical-trajectory page (`/elections/trajectory/lok-sabha`) with a time stepper. At that point, draft a Phase X spec covering:

- nominal fill from the party-anchor palette;
- hung-verdict treatment (Hans);
- swatch-grid legend with collapsed "Other parties" bucket (Jony);
- a time-stepped variant for trajectory views (with frame-to-frame fill continuity rules);
- a `state-largest-party-id` derived field if not already in the canonical store (currently we have `state-winning-party-id`, which is null for hung verdicts — that may or may not be the right shape for a map).

---

### DEFERRED-D: Vote-share twin alongside seat-share on the composition card

**Status**: data exists; held out of v1 to keep the side-by-side smoke (Phase 3.6) small.

**Why it matters**: Hans's hard requirement (2026-05-19): never show seat-share without vote-share when discussing FPTP outcomes, because the gap between them is the FPTP distortion story (49% vote share → 54% seat share in Gujarat 2017; the citizen needs both numbers to read the result honestly). The FPTP caption in v1 partially addresses this in copy, but the visual twin is the stronger fix.

**Why deferred (not in v1)**: adding a second `<CompositionBar>` bound to `party-vote-share-pct` doubles Phase 3.6's surface. Phase 3.6's primary goal is "does this renderer earn its keep against the existing `SeatDonut`?" — adding a vote-share twin makes the A/B harder to read because the comparison becomes three-way (`SeatDonut` vs `CompositionBar` seats vs `CompositionBar` votes). Ship v1 lean, then add the twin.

**Re-entry trigger**: immediately after Phase 3.6 v1 passes its visual A/B review. Mount a second `<CompositionBar>` bound to `party-vote-share-pct` (already materialised in canonical store) on the same card, paired left/right with the seat-share twin. Caption: "Seats won (left) vs vote share (right); the gap is the FPTP distortion." No new data, no new renderer, no new adapter — just a second adapter instance and a second mount.

---

### DEFERRED-E: Longitudinal seat-share + vote-share twin

**Status**: blocked on time-series renderer + temporal-viewport primitive (Phase 1.5).

**Why it matters**: Hans's "citizen-default ought to be longitudinal" principle. A single-election composition bar is a snapshot; a multi-election trajectory is the political-shift story. For the state hub elections card, the citizen-honest default is "how has this state voted across the last N elections?" not "how did it vote in 2017?"

**Why deferred (not in v1)**: Phase 1.5 (temporal viewport interaction primitive) ships before this is buildable. Also, the trajectory shape is `stacked_trend` (already exists, already adapter-fed for elections) — not `composition_bar`. So this entry is really "after Phase 1.5 ships, re-evaluate whether the state hub elections card should default to a `stacked_trend` longitudinal view with the `composition_bar` snapshot as a secondary read."

**Re-entry trigger**: after Phase 1.5 ships. Tag this with a TODO check in the Phase 1.5 Definition of Done.

---

## Definition of Done for the whole plan

- [ ] Public frontend still uses Svelte 5 + Vite with closed yen-gov renderers.
- [ ] No unapproved public dependency on Plotly/ECharts/Chart.js/Observable/Vega as primary renderers; any approved library-backed renderer is lazy-loaded, adapter-fed, and documented by ADR.
- [ ] Chart projection, sorting, grouping, and footer actions are driven by closed metadata/view-model enums, not indicator-id conditionals.
- [ ] Ordered facets such as economic class and rural/urban preserve source/natural order via a facet-axis registry.
- [ ] Long-duration chart families have an agreed temporal viewport pattern: brush/window, presets, reset, and optional export where useful.
- [ ] Source footer is compact by default and expandable to exact provenance/citation/licence details.
- [ ] Chart summaries/readouts respect visible window, denominator, comparability, and series breaks; no unsupported causal/blame wording.
- [ ] Topic and indicator icons resolve through a documented registry; no silent fallback for committed catalogue icon ids.
- [ ] StackedTrend has real mode control, readable selected-bar readout, better labels, and distinct missing-data treatment.
- [ ] Ranked views expose home state, compare state, and median/peer context more visibly.
- [ ] Small multiples better communicate trajectory and latest value.
- [ ] Choropleth colour/ramp changes, if any, preserve the rule: dark means more of the thing.
- [ ] Frontend tests and changed-route e2e are green.
- [ ] Browser smoke confirms no new console errors or data 404s.

## Handoff notes for the next coding agent

Start with **Phase 2** unless the user explicitly asks to formalise docs first. `StackedTrend` has the biggest gap between written design and shipped implementation, so it gives the most visible improvement without changing framework or data model.

Do not add a charting library to solve Phase 2 without first completing Phase 0.5. The implementation may still be achievable with Svelte, existing zod view-models, existing colour utilities, and small pure helpers; if the spike proves a library removes more complexity than it adds, promote that as an ADR-backed renderer decision.

Do not download third-party SVGs ad hoc. Start with the existing Lucide-style registry and the icon audit in Phase 1.25. If a domain noun truly needs an external icon, record source/licence/attribution before wiring it into a public route.

Do not hardcode externally inspired behaviour directly into Svelte components. Encode reusable behaviour as projection metadata, facet-axis metadata, and tested view-model helpers first; then render it with the closed renderer set.

Before changing files, check whether `TODO/VIZ-LAYER-GAPS-PLAN.md` has active work on the same files. If it does, keep this plan's polish work as a separate slice and avoid mixing it with catalogue/renderer dispatch migrations.

**2026-05-19 amendment context (Phase 3.6 + deferred section)**: a user-surfaced concentric sunburst (Gujarat + Himachal 2017 seat share, two states in one ring) triggered a Jony + Hans + Max review. All three personas independently rejected the multi-entity radial composition shape; the response was to define a generic single-entity `composition_bar` (Phase 3.6) and to LOUDLY mark the deferred work (alliance rollups, multi-state composition, categorical choropleth, vote-share twin, longitudinal twin) so a future planner can pick each up the moment its gating condition flips. Re-read the "Rejected alternatives" entry on multi-entity sunburst AND the "⚠️ DEFERRED WORK" section BEFORE proposing anything composition-shaped, multi-state-shaped, alliance-shaped, or radial-composition-shaped. The work is scoped and waiting; do not re-debate the rejection or re-scope the deferred items from scratch.