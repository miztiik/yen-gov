<script lang="ts">
  // StackedTrendV2 — component shell (Phase 2.1b per R-09).
  //
  // STRUCTURAL ONLY. ZERO RENDER COVERAGE. NO CALLER MOUNTS THIS YET.
  //
  // This file exists so the rest of Phase 2 (segmented mode, pinned readout,
  // inline labels, missing-hatch, motion, export) can land one PR at a time
  // against a stable, type-checked seam — instead of one giant rewrite that
  // would have to land all-or-nothing.
  //
  // Per R-08 Branch by Abstraction: v2 ships ALONGSIDE
  // `frontend/src/lib/charts/StackedTrend.svelte` (v1). v1 is NOT modified,
  // NOT deprecated. Caller migration is one PR per caller (≤3 callers per PR
  // with Playwright assertion); v1 is deleted in a single final PR after the
  // last caller migrates.
  //
  // Per R-09: Phase 2.1 splits into:
  //   2.1a (PR #105) — types + zod model + fixture
  //   2.1b (THIS PR) — component shell consuming types, returns inert chart
  //                    container, type-check green
  // Behaviour starts at Phase 2.2 (segmented mode) and onward.
  //
  // Why an empty container and not `null` / `{#if false}`:
  //  - Headline + honesty banner ARE structural chrome the renderer always
  //    owns, never the caller — emitting them here pins the contract (the
  //    chart owns its disclosure surface) without committing to any bar
  //    geometry, axis math, scale, tooltip, or interactivity.
  //  - The chart-area placeholder is an empty SVG <g/> per the plan's literal
  //    R-09 wording. It reserves the SVG layer the bar/segment/label/leader
  //    primitives will fill in Phases 2.3..2.4 without forcing a layout
  //    refactor when they land.
  //  - No d3 import, no scale, no color-token lookup, no event listener, no
  //    @derived bar geometry. Anything past this line in future PRs is
  //    Phase 2.2+ behaviour and ships in its own PR.

  import type { StackedTrendV2Model } from "./stacked-trend-v2/types";

  let {
    model,
    mode_override,
  }: {
    model: StackedTrendV2Model;
    /**
     * Optional caller override of `model.default_mode`. Wired through to the
     * (future) segmented mode control in Phase 2.2. Unused in the shell.
     */
    mode_override?: "percent" | "absolute";
  } = $props();

  // Derive the mode the future renderer will use. Computed (rather than
  // ignored) so the prop's type is exercised by `svelte-check`/`tsc` and so
  // a Phase 2.2 PR can flip on the segmented control without changing the
  // prop surface.
  const mode = $derived<"percent" | "absolute">(
    mode_override ?? model.default_mode,
  );

  // Touch the prop so the unused-variable lint doesn't strip it. The Phase
  // 2.2 segmented control will replace this with real readout text.
  const modeLabel = $derived(mode.toUpperCase());
</script>

<!--
  Phase 2.1b shell. Renders ONLY the structural chrome the chart contract
  guarantees (headline + honesty banner) plus an empty SVG <g/> placeholder
  for the bar layer. No bars, no axes, no legend, no readout. Citizen-visible
  output is intentionally minimal until Phases 2.2..2.7 wire it.
-->
<div
  class="stacked-trend-v2 space-y-3"
  data-chart="stacked-trend-v2"
  data-mode={modeLabel}
>
  {#if model.headline?.text}
    <div class="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
      <div class="font-semibold text-slate-800">{model.headline.text}</div>
      {#if model.headline.so_what}
        <div class="text-slate-600 text-xs mt-0.5">{model.headline.so_what}</div>
      {/if}
    </div>
  {/if}

  {#if model.honesty?.comparability === "not_comparable_across_states"}
    <div class="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
      Read this carefully — ranking by this number is misleading.
    </div>
  {:else if model.honesty?.attribution_geography === "where_allocated"}
    <div class="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
      Values are this state's allocated share of central-sector capacity, not the location of the plant.
    </div>
  {:else if model.honesty?.attribution_geography === "where_produced"}
    <div class="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
      This shows where the asset is sited, not who uses it.
    </div>
  {/if}

  <!--
    SVG bar layer placeholder. The empty <g> is the R-09 literal contract.
    Phase 2.3+ replaces the empty group with rect/text/path primitives bound
    to `model.bars[*].segments[*]`. viewBox stays generic until the axis
    rhythm helpers from Phase 2.2 specify it.
  -->
  <svg class="stacked-trend-v2__canvas block w-full">
    <g class="stacked-trend-v2__bars" data-phase="2.1b-shell"></g>
  </svg>
</div>
