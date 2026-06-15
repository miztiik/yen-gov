# PR-14 collapse receipt - RangeBrush primitive

**Date**: 2026-06-15
**Plan-doc**: [TODO/20260615-party-page-citizen-fixes-plan.md](./20260615-party-page-citizen-fixes-plan.md) PR-14
**Authority for collapse**: Plan-doc PR-14 COLLAPSE clause (Wave A) + CLAUDE.md section 10 "Don't reinvent OSS or existing primitives" + Fowler authority (deletion discipline + refactor safety).
**Outcome**: COLLAPSED. No code shipped. No branch cut. Receipt-only.

## One-sentence design call

A canonical temporal-window-selection primitive already exists at [frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.svelte](../../../frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.svelte) and is already adopted by `StackedTrendV2` via the exact opt-in prop pattern PR-14 sketches; minting `RangeBrush/RangeBrush.svelte` next to it would be parallel-primitive duplication, and the d3-brush dependency PR-14 names is not in `frontend/package.json` and is not required by the existing primitive.

## What I found before writing a line of code

Pre-implementation investigation per the brief (steps 1-4):

1. **`frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte`** - chart-internal renderer with a `bars` + `line` + `methodology_breaks` prop surface and pure `buildScales` + `pickLabelStride` helpers extracted for vitest. Two call-sites in [frontend/src/routes/Party.svelte](../../../frontend/src/routes/Party.svelte) (LS section line 674, VS section line 710) - both pass `mode="composite"` with `line={[]}` (composite-bar mode, no line series).
2. **`frontend/src/lib/charts/`** sibling primitive convention: large primitives use folder-per-component (`DualAxisBarLine/`, `composition-bar/`, `stacked-trend-v2/`, `temporal-viewport/`, `time-view-models/`); small ones are flat `.svelte` + `.test.ts` pairs. So `RangeBrush/RangeBrush.svelte` would be folder-per-component (consistent), but...
3. **`frontend/package.json`** dependency line 33: `"d3": "^7.9.0"` only - NO `d3-brush`. The brief flagged this: "if not present, the install is itself a design call".
4. **`grep -r "DualAxisBarLine" frontend/src/`**: 2 wire-up call-sites in `routes/Party.svelte` (party-page LS + VS vote-share trends), plus docstring cross-refs in `view-models/party-detail.ts` + tests. The wire-up surface is small and additive.
5. **The decisive grep**: `grep -r "TemporalViewportBrush" frontend/src/` returned 11 matches. The primitive is real, documented, tested, and live:
    - [frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.svelte](../../../frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.svelte) - the primitive.
    - [frontend/src/lib/charts/temporal-viewport/helpers.ts](../../../frontend/src/lib/charts/temporal-viewport/helpers.ts) + `types.ts` + `index.ts` - pure helpers (`buildDomain`, `fullWindow`, `clampWindow`, `presetWindow`, `filterItemsToWindow`, `windowIndices`, `parseLeadingYear`) + closed-enum types (`TemporalDomain`, `TemporalWindow`, `TemporalPreset`, `TemporalDomainKind`).
    - [frontend/src/lib/charts/temporal-viewport/README.md](../../../frontend/src/lib/charts/temporal-viewport/README.md) - the doctrine, citing Phase 1.5 of [docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md](../../archive/20260518-frontend-charting-modernisation-plan-snapshot.md).
    - [frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.test.ts](../../../frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.test.ts) - vitest pin.
    - [frontend/src/lib/charts/StackedTrendV2.svelte](../../../frontend/src/lib/charts/StackedTrendV2.svelte) lines 113 + 739 - the live adopter using the `enable_temporal_brush={true}` opt-in prop pattern.

## Why PR-14's specific framing now blocks

PR-14 brief: "Mint `frontend/src/lib/charts/RangeBrush/RangeBrush.svelte` - a thin d3-brush overlay primitive that emits `(startYear, endYear)` events. Mount as an optional opt-in prop `<DualAxisBarLine ... brush={true}>`."

Three separable claims, each surfacing a design call:

| Claim | Reality | Design call |
| --- | --- | --- |
| "Mint a new primitive" | One already exists, adopted, tested, documented under Phase 1.5 doctrine. | Mint vs. reuse - structural. Fowler + CLAUDE.md section 10. |
| "d3-brush overlay" | `d3-brush` is not a dep; the existing primitive is zero-d3, uses native button clicks + presets, no shadow-DOM, no pointer-capture machinery. | Adding `d3-brush` as a new top-level dep needs Andre + Hans sign-off (OSS-first rule). |
| "Mount as `brush={true}` on `DualAxisBarLine`" | The existing primitive is composed INSIDE the chart renderer (StackedTrendV2 precedent), additive props. That part IS clean. | Additive; no blocker. The OUTER call (mint vs. reuse) gates this. |

## Candidate paths for the future Level-3 plan-doc

Three viable paths. Each has a real product question only Hans + Max + Jony can settle.

### Path A - Reuse `TemporalViewportBrush` on `DualAxisBarLine` (Level-2 wire-up, not Level-3)

What it looks like:

```svelte
<!-- DualAxisBarLine.svelte additive props (StackedTrendV2 precedent) -->
let {
  bars,
  line,
  enable_temporal_brush = false,
  temporal_domain_kind = "year",
  temporal_recent_count = 5,
  // ... existing props
}: Props = $props();

// ... derive temporal_domain from bars; manage temporal_window in $state;
// filter visibleBars via filterItemsToWindow before render.

{#if enable_temporal_brush}
  <TemporalViewportBrush
    domain={temporal_domain}
    window={effective_window}
    recent_count={temporal_recent_count}
    period_labels={temporal_period_labels}
    on_window_change={(next) => (temporal_window = next)}
  />
{/if}
```

Then in `routes/Party.svelte`:

```svelte
<DualAxisBarLine
  mode="composite"
  bars={ls_bars_composite}
  line={[]}
  bar_color={bar_color}
  bar_y_label="Vote share %"
  bar_format={(n) => `${n.toFixed(1)}%`}
  methodology_breaks={view_model.ls_methodology_breaks}
  enable_temporal_brush
  temporal_recent_count={5}
/>
```

Pros: zero new primitives; zero new deps; mirrors `StackedTrendV2` exactly, so any chart-modernisation lesson learnt once applies twice. Tests slot under the existing `temporal-viewport` test file. Vitest + svelte-check + browser smoke all on existing rails. Level-2 (additive props on one renderer, one call-site update).

Cons: interaction model is "click first cell, click second cell, Reset to clear" + preset chips. Not a continuous drag. For the median citizen looking at 18 LS cycles, this is fine - and the presets (Recent 5 / 5y / 10y / 25y / All) cover the canonical zoom intents. The brief's "drag the brush programmatically" oracle would need to be rewritten to "click two strip cells" - cosmetic.

**Jony stub**: "defaults are the product" - the click-and-preset model IS the more honest gesture for a citizen who knows "show me the last 25 years" but does NOT know how to operate a brush drag-handle on mobile.

### Path B - Mint a true continuous-drag d3-brush primitive

What it looks like: add `d3-brush` to `frontend/package.json`; new folder `frontend/src/lib/charts/RangeBrush/`; new `RangeBrush.svelte` that wraps d3-brush's selection events into Svelte 5 runes; opt-in on `DualAxisBarLine` via additive prop; tests cover the brush-selection event emission + clamp + reset gesture.

Pros: continuous-drag is the canonical Brichter / OWID time-axis gesture; arguably better for >50-year corpora (RBI fiscal series go to 1950, NDLM monthly to 2010s).

Cons:
- New dep `d3-brush` (Andre + Hans sign-off).
- Two parallel primitives doing the same job. Per Fowler, every new contributor will ask "which one do I use?". A deprecation arc + adoption migration on `StackedTrendV2` would then be required - that's the Level-4 work the plan-doc avoided by sketching PR-14 as standalone.
- d3-brush is imperative SVG-injection - it adds DOM children outside Svelte's reconciliation. Svelte 5 runes mode does work with this (via `bind:this={svgRef}` + `$effect` to attach the brush behaviour), but the integration surface is non-trivial and the brief explicitly flagged "shadow-DOM workarounds" as a COLLAPSE trigger. Lifecycle gotchas: brush behaviour must detach on unmount, re-attach on prop change, and selection events must not race the Svelte effect graph.
- Below ~120px wide the brush is unusable on mobile - the brief flagged this too.

### Path C - Custom drag primitive on native input range

What it looks like: paired `<input type="range">` elements (min + max handles) styled as a brush track; pure CSS + DOM events; no d3, no new dep.

Pros: zero new dep; native a11y is descoped per CLAUDE.md section 0 so no `aria-*` debt; works to 120px and below on mobile.

Cons: hand-rolled UX vs. the d3-brush canonical idiom; per Andre's authority for AI/LLM rendering surfaces this gets messy if yenask wants to embed the same primitive with citizen-named ranges.

## Hans + Max persona-debate stub for the future Level-3 plan-doc

**Hans** (data shape + citizen-readable framing): "What MEASURE is the citizen asking when they touch the brush? 'Show me the most recent N years' (preset) is one question. 'Show me 1989-1999' (drag) is a different question. The first is a category, the second is a range. The party-page vote-share trend is fundamentally about CYCLES (election events), not years (continuous time) - and cycles map naturally to presets ('last 3 elections', 'Modi era', 'NDA era'). For RBI fiscal time-series, the year-grain is continuous and continuous-drag becomes the more honest gesture. Mint by GRAIN: cycle-grain charts use the existing preset primitive; year-grain continuous charts opt into a drag primitive when corpus depth > 25 years. The two primitives are NOT duplicates if they serve different grains."

**Max** (taxonomy + entity-kind): "The chart renderer already knows its `temporal_domain_kind` (`year` / `fiscal_year` / `election_cycle` / `month` / `custom`). The renderer can pick the right brush at render time from the domain-kind, not from a `brush` prop. Add ONE `enable_temporal_brush={true}` opt-in; let the primitive dispatch internally: `election_cycle` -> preset-only; `year` / `fiscal_year` -> presets + optional drag. This converges the two primitives at the consumer surface (one prop) while keeping the interaction-model split inside the temporal-viewport package."

**Convergence (Hans + Max)**: ship the existing `TemporalViewportBrush` on `DualAxisBarLine` via Path A FIRST. Defer the drag-primitive to a separate Level-3 plan-doc that lands ONLY when (a) a chart with `temporal_domain_kind="year"` AND >25 years of continuous data is on the page, AND (b) citizen feedback or yenask analytics surface the drag-gesture as a real need. The two-primitive package is the right end state - but minted by demand, not speculatively.

**Jony stub** (closes the trio): "the brush track at <120px is not just bad - it is a false promise. On mobile, no brush. The opt-in must check viewport width and quietly hide the drag handles in favour of presets-only, regardless of grain. Brichter rule: the gesture must work, or it must not appear."

**Fowler stub** (cross-cuts all three): "The temporal-viewport package is the seam. New interaction models extend the package, not parallel folders elsewhere in `charts/`. If the drag primitive lands, it lands as `temporal-viewport/TemporalViewportDrag.svelte` alongside `TemporalViewportBrush.svelte`, sharing `helpers.ts` + `types.ts`. The consumer-facing seam stays one prop on the renderer."

## Recommendation for the orchestrator

Two non-blocking follow-ons, ordered:

1. **Level-2 PR**: wire `TemporalViewportBrush` into `DualAxisBarLine` on the party-page (Path A above). Strictly additive props; mirrors `StackedTrendV2`; no new dep. ~1-2 hours of work. This satisfies the SPIRIT of PR-14 (give the citizen a window-selection gesture on the party-page vote-share trend) at the LOWEST cost.
2. **Level-3 plan-doc (deferred)**: "Continuous-drag temporal brush for year-grain charts >25 years deep". Authoring trigger: the first chart with `temporal_domain_kind="year"` AND >25 years of data PLUS one piece of evidence (citizen feedback, yenask analytics, an explicit ask) that presets-only is insufficient. Until then, the corpus depth does not justify the cost.

## What this receipt deliberately does NOT do

- No worktree was cut. No branch was created. No PR was opened. The receipt itself IS the deliverable per the brief's "If you collapse, write `TODO/...md`" instruction and the JSON output schema (`pr_url: null`).
- No code was changed. The orchestrator can pick this up and either dispatch the Level-2 follow-on as a new PR brief, or defer entirely - both are valid given the COLLAPSE clause's "the immediate fix (PR-10) is sufficient for the current corpus depth".

## See also

- [TODO/20260615-party-page-citizen-fixes-plan.md](./20260615-party-page-citizen-fixes-plan.md) - PR-14 row (collapsed); PR-15 closure should reference this receipt.
- [frontend/src/lib/charts/temporal-viewport/README.md](../../../frontend/src/lib/charts/temporal-viewport/README.md) - the existing primitive's doctrine.
- [docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md](../../archive/20260518-frontend-charting-modernisation-plan-snapshot.md) - Phase 1.5 origin doctrine for the temporal viewport primitive.
- [frontend/src/lib/charts/StackedTrendV2.svelte](../../../frontend/src/lib/charts/StackedTrendV2.svelte) lines 113 + 739 - the precedent adopter pattern for Path A.
- [CLAUDE.md](../../../CLAUDE.md) section 10 anti-patterns - "Don't reinvent OSS or existing primitives" + "Don't add features...beyond what was asked".
