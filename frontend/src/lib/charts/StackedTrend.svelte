<script lang="ts">
  // StackedTrend — generic stacked-bar-over-time / over-entities chart.
  // Renders any StackedTrendModel (see ./stacked-trend/types.ts).
  // Per docs/architecture/frontend/charts/stacked-trend.md.

  import type { StackedTrendModel, StackedTrendBar } from "./stacked-trend/types";
  import { OTHER_CATEGORY_ID, OTHER_CATEGORY_FILL } from "./stacked-trend/types";
  import { categoryFill } from "../colors/category-colour";
  import SourceList from "../SourceList.svelte";

  let {
    model,
    mode_override,
  }: {
    model: StackedTrendModel;
    mode_override?: "percent" | "absolute";
  } = $props();

  const mode = $derived<"percent" | "absolute">(mode_override ?? model.default_mode);

  const inUseCodes = $derived(model.categories.map((c) => c.id));
  function fillFor(category_id: string): string {
    if (category_id === OTHER_CATEGORY_ID) return OTHER_CATEGORY_FILL;
    const cat = model.categories.find((c) => c.id === category_id);
    if (cat?.fill) return cat.fill;
    return categoryFill(category_id, inUseCodes, model.dimension);
  }

  function barTotal(b: StackedTrendBar): number {
    if (b.total != null) return b.total;
    return b.segments.reduce(
      (a, s) => (s.availability === "present" && s.value != null ? a + s.value : a),
      0,
    );
  }

  const maxTotal = $derived(Math.max(1, ...model.bars.map(barTotal)));

  function segHeight(value: number, total: number, totalForBar: number): number {
    if (mode === "percent") {
      if (totalForBar <= 0) return 0;
      return (value / totalForBar) * 100;
    }
    return (value / maxTotal) * 100;
  }

  function fmtValue(v: number): string {
    if (model.unit.value_kind === "share") return `${(v * 100).toFixed(1)}%`;
    if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k ${model.unit.label}`;
    return `${v.toFixed(0)} ${model.unit.label}`;
  }

  let hovered: string | null = $state(null);
</script>

<div class="space-y-3">
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

  <div class="flex items-center gap-3 text-xs">
    <span class="text-slate-500">Mode</span>
    <span class="font-medium text-slate-800 uppercase tracking-wide">{mode}</span>
    <span class="ml-auto text-slate-500">{model.x_axis_label}</span>
  </div>

  <div class="relative h-72 w-full overflow-x-auto">
    <div
      class="flex items-end gap-1 h-full min-w-full"
      style:min-width={`${Math.max(model.bars.length * 36, 320)}px`}
    >
      {#each model.bars as bar (bar.period_id)}
        {@const total = barTotal(bar)}
        {@const heightPct = mode === "percent" ? 100 : (total / maxTotal) * 100}
        <div class="flex flex-col items-center justify-end h-full flex-1 min-w-[24px] group">
          <div
            class="relative w-full max-w-[40px] rounded-t overflow-hidden flex flex-col-reverse border border-slate-200"
            style:height={`${heightPct}%`}
            style:min-height="2px"
            onmouseenter={() => (hovered = bar.period_id)}
            onmouseleave={() => (hovered = null)}
            role="presentation"
          >
            {#each bar.segments as seg (seg.category_id)}
              {#if seg.availability === "present" && seg.value != null}
                <div
                  class="w-full"
                  style:height={`${segHeight(seg.value, total, total)}%`}
                  style:background-color={fillFor(seg.category_id)}
                  title="{seg.category_id}: {fmtValue(seg.value)}"
                ></div>
              {/if}
            {/each}
          </div>
          <div class="text-[10px] text-slate-500 mt-1 truncate w-full text-center" title={bar.period_label}>
            {bar.period_label}
          </div>
        </div>
      {/each}
    </div>
  </div>

  {#if hovered}
    {@const b = model.bars.find((x) => x.period_id === hovered)}
    {#if b}
      <div class="rounded border border-slate-200 bg-white p-2 text-xs">
        <div class="font-semibold text-slate-800">{b.period_label}</div>
        <ul class="mt-1 space-y-0.5">
          {#each b.segments as s (s.category_id)}
            {#if s.availability === "present" && s.value != null}
              <li class="flex items-center gap-2">
                <span class="inline-block w-2 h-2 rounded-sm" style:background-color={fillFor(s.category_id)}></span>
                <span class="text-slate-700">
                  {model.categories.find((c) => c.id === s.category_id)?.label ?? s.category_id}:
                </span>
                <span class="text-slate-600">{fmtValue(s.value)}</span>
                {#if barTotal(b) > 0}
                  <span class="text-slate-400">({((s.value / barTotal(b)) * 100).toFixed(1)}%)</span>
                {/if}
              </li>
            {/if}
          {/each}
        </ul>
      </div>
    {/if}
  {/if}

  <ul class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
    {#each model.categories as cat (cat.id)}
      <li class="flex items-center gap-1.5">
        <span class="inline-block w-2.5 h-2.5 rounded-sm" style:background-color={fillFor(cat.id)}></span>
        <span class="font-medium">{cat.label}</span>
      </li>
    {/each}
  </ul>

  {#if model.honesty?.notes}
    <p class="text-[12px] text-slate-700">{model.honesty.notes}</p>
  {/if}
  {#if model.honesty?.methodology_vintage}
    <p class="text-[11px] text-slate-500">Methodology · {model.honesty.methodology_vintage}</p>
  {/if}

  {#if model.sources.length > 0}
    <SourceList sources={model.sources} />
  {/if}
</div>
