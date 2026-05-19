<script lang="ts">
  // Generic indicator small-multiples — one mini sparkline per state on a
  // single page. Per docs/concepts/cross-state-comparison.md, this is the
  // "trajectory" primitive: a citizen scanning a 28-state grid can spot
  // who's accelerating, who's stalled, and who's regressing in one glance.
  //
  // Honesty rules:
  //   - All sparklines share a Y axis (max across all states) so heights
  //     are visually comparable. A per-state Y axis would lie about scale.
  //   - When the indicator declares comparability=not_comparable_across_states,
  //     an amber banner explains that heights aren't directly comparable.
  //   - States with no data show a slate-200 "no data" placeholder rather
  //     than being silently dropped.
  //   - Series breaks (definition_change / rebase) draw a dashed vertical
  //     marker at the break time. The citizen sees the discontinuity.
  //
  // Sparkline = SVG polyline + dot at latest value. No axes, no gridlines.
  // The shared Y range and the explicit latest-value tag carry the load.

  import {
    fetchIndicator,
    seriesByEntity,
    formatValue,
    type IndicatorArtifact,
  } from "./indicators";
  import { legendCaption } from "./indicator-render";
  import { STATE_NAME_TO_ECI } from "./maplibre/sources";

  interface Props {
    /** Path under DATA_BASE, e.g. "/indicators/in/energy/installed_mw_by_state.json". */
    indicator_path: string;
    /** Optional ECI code to highlight (amber). */
    home_state?: string;
    /** Optional second ECI code to highlight (emerald). */
    compare_state?: string | null;
  }

  let { indicator_path, home_state, compare_state = null }: Props = $props();

  let artifact = $state<IndicatorArtifact | null>(null);
  let load_error = $state<string | null>(null);

  $effect(() => {
    artifact = null;
    load_error = null;
    fetchIndicator(indicator_path)
      .then(a => (artifact = a))
      .catch(e => (load_error = String(e)));
  });

  const series = $derived(artifact ? seriesByEntity(artifact.rows) : new Map());
  const all_times = $derived.by(() => {
    if (!artifact) return [] as string[];
    const set = new Set<string>();
    for (const arr of series.values()) for (const p of arr) set.add(p.time);
    return [...set].sort();
  });
  const time_index = $derived.by(() => {
    const m = new Map<string, number>();
    all_times.forEach((t, i) => m.set(t, i));
    return m;
  });
  const y_max = $derived.by(() => {
    let m = 0;
    for (const arr of series.values()) {
      for (const p of arr) if (Math.abs(p.value) > m) m = Math.abs(p.value);
    }
    return m || 1;
  });

  // Stable display order: home first, compare second, alphabetical thereafter.
  const cards = $derived.by(() => {
    const list = Object.entries(STATE_NAME_TO_ECI).map(([name, code]) => ({ name, code }));
    list.sort((a, b) => {
      if (a.code === home_state) return -1;
      if (b.code === home_state) return 1;
      if (a.code === compare_state) return -1;
      if (b.code === compare_state) return 1;
      return a.name.localeCompare(b.name);
    });
    return list;
  });

  const W = 100;
  const H = 32;
  const PAD_X = 2;
  const PAD_Y = 3;

  function pathFor(arr: Array<{ time: string; value: number }>): string {
    if (arr.length === 0 || all_times.length < 2) return "";
    const span = all_times.length - 1;
    const inner_w = W - 2 * PAD_X;
    const inner_h = H - 2 * PAD_Y;
    return arr
      .map((p, i) => {
        const idx = time_index.get(p.time) ?? 0;
        const x = PAD_X + (idx / span) * inner_w;
        const y = PAD_Y + inner_h - (Math.abs(p.value) / y_max) * inner_h;
        return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  }

  function dotFor(arr: Array<{ time: string; value: number }>): { cx: number; cy: number } | null {
    if (arr.length === 0 || all_times.length < 2) return null;
    const last = arr[arr.length - 1];
    const span = all_times.length - 1;
    const inner_w = W - 2 * PAD_X;
    const inner_h = H - 2 * PAD_Y;
    const idx = time_index.get(last.time) ?? 0;
    return {
      cx: PAD_X + (idx / span) * inner_w,
      cy: PAD_Y + inner_h - (Math.abs(last.value) / y_max) * inner_h,
    };
  }

  function breakXs(): number[] {
    if (!artifact || all_times.length < 2) return [];
    const breaks = artifact.indicator.series_breaks ?? [];
    const span = all_times.length - 1;
    const inner_w = W - 2 * PAD_X;
    return breaks
      .map(b => time_index.get(b.at_time))
      .filter((i): i is number => i !== undefined)
      .map(i => PAD_X + (i / span) * inner_w);
  }

  const can_compare = $derived(
    artifact?.indicator.comparability !== "not_comparable_across_states",
  );
</script>

<section class="bg-white rounded-lg shadow-sm overflow-hidden">
  {#if load_error}
    <div class="p-4 text-sm bg-rose-50 border border-rose-200 text-rose-900">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !artifact}
    <div class="p-4 text-sm text-slate-500">Loading…</div>
  {:else}
    <header class="px-4 pt-4 pb-3 border-b border-slate-100 space-y-2">
      <div class="flex justify-between items-baseline gap-3 flex-wrap">
        <div class="min-w-0">
          <h3 class="text-base font-semibold">
            {artifact.indicator.title}
            <span class="text-xs font-normal text-slate-500">· small multiples</span>
          </h3>
          {#if artifact.indicator.description || artifact.indicator.description_short}
            <p class="text-xs text-slate-500 mt-0.5 leading-relaxed" data-testid="indicator-caption">{legendCaption(artifact.indicator)}</p>
          {/if}
        </div>
        {#if all_times.length > 1}
          <div class="text-xs text-slate-500 tabular-nums">
            {all_times[0]} → {all_times[all_times.length - 1]}
          </div>
        {/if}
      </div>

      {#if all_times.length < 2}
        <div class="text-[11px] px-2.5 py-1.5 rounded bg-slate-50 border border-slate-200 text-slate-700 leading-snug">
          <strong class="font-semibold">Single time point · </strong>
          This indicator has only one observation per state — no trajectory to draw.
          Use the ranked table or choropleth instead.
        </div>
      {:else if !can_compare}
        <div class="text-[11px] px-2.5 py-1.5 rounded bg-amber-50 border border-amber-200 text-amber-900 leading-snug">
          <strong class="font-semibold">Heights not directly comparable · </strong>
          Sparkline shapes (the trajectory) are still meaningful, but the absolute
          height of bars between states reflects different definitions, not different reality.
        </div>
      {:else}
        <div class="text-[11px] text-slate-500">
          All sparklines share a single Y axis (0 → {formatValue(y_max, artifact.indicator)}).
          Compare shapes to spot acceleration, plateau, or regression.
        </div>
      {/if}
    </header>

    {#if all_times.length >= 2}
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-x-3 gap-y-2 p-3">
        {#each cards as c (c.code)}
          {@const arr = series.get(c.code) ?? []}
          {@const dot = dotFor(arr)}
          {@const is_home = c.code === home_state}
          {@const is_compare = !!compare_state && c.code === compare_state && c.code !== home_state}
          {@const stroke = is_home ? "#f59e0b" : is_compare ? "#10b981" : "#0284c7"}
          {@const bg = is_home ? "bg-amber-50" : is_compare ? "bg-emerald-50" : "bg-slate-50/50"}
          <div class="rounded-sm px-2 pt-1.5 pb-1 {bg}">
            <div class="flex justify-between items-baseline gap-1">
              <div class="text-[11px] font-medium text-slate-700 truncate">{c.name}</div>
              {#if dot && arr.length > 0}
                <div class="text-[10px] text-slate-500 tabular-nums">
                  {formatValue(arr[arr.length - 1].value, artifact.indicator)}
                </div>
              {/if}
            </div>
            {#if arr.length > 0}
              <svg viewBox="0 0 {W} {H}" class="w-full h-8" preserveAspectRatio="none" aria-hidden="true">
                {#each breakXs() as bx}
                  <line x1={bx} x2={bx} y1={0} y2={H} stroke="#cbd5e1" stroke-width="0.5" stroke-dasharray="1.5 1.5" />
                {/each}
                <path d={pathFor(arr)} fill="none" stroke={stroke} stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
                {#if dot}
                  <circle cx={dot.cx} cy={dot.cy} r="1.6" fill={stroke} />
                {/if}
              </svg>
            {:else}
              <div class="h-8 flex items-center justify-center text-[10px] text-slate-400">no data</div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</section>
