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
  import { loadIndicator } from "./canonical/indicator-from-canonical";
  import { legendCaption } from "./indicator-render";
  import { loadStates, type StateRow } from "./view-models/states";
  import TopicIcon from "./TopicIcon.svelte";
  import {
    computeYDomain,
    pathForSeries,
    latestDot,
    breakXs as projectBreakXs,
    zeroBaselineY,
    type SparkProjection,
  } from "./charts/small-multiples";

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
  // Currently-valid Indian states+UTs from taxonomy.entities. Iterated by
  // the `cards` derived to build one mini-sparkline per state. Replaces
  // STATE_NAME_TO_ECI per T.0e.
  let states_taxonomy = $state<StateRow[] | null>(null);

  loadStates()
    .then(s => (states_taxonomy = s))
    .catch(e => (load_error = String(e)));

  $effect(() => {
    artifact = null;
    load_error = null;
    loadIndicator(indicator_path)
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
  const y_domain = $derived.by(() => {
    const values: number[] = [];
    for (const arr of series.values()) for (const p of arr) values.push(p.value);
    return computeYDomain(values);
  });

  // Stable display order: home first, compare second, alphabetical thereafter.
  const cards = $derived.by(() => {
    const list = (states_taxonomy ?? []).map(s => ({
      name: s.boundary_join_name,
      code: s.eci_code,
    }));
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

  const proj = $derived<SparkProjection>({
    view_box_width: W,
    view_box_height: H,
    pad_x: PAD_X,
    pad_y: PAD_Y,
    y_domain,
    time_axis: all_times,
  });

  const break_times = $derived(artifact?.indicator.series_breaks?.map(b => b.at_time) ?? []);
  const break_xs = $derived(projectBreakXs(break_times, proj));

  // Draw a zero baseline only when it sits STRICTLY INSIDE the inner
  // plot rect (i.e. the domain has both negative and positive values).
  // When `y_domain.min === 0` or `y_domain.max === 0`, the baseline
  // would coincide with the floor/ceiling and adds no information.
  const baseline_y = $derived.by(() => {
    if (y_domain.min >= 0 || y_domain.max <= 0) return null;
    return zeroBaselineY(proj);
  });

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
          <h3 class="text-base font-semibold flex items-center gap-2 flex-wrap">
            <TopicIcon name={artifact.indicator.icon} cls="w-4 h-4 text-slate-500 shrink-0" />
            <span>{artifact.indicator.title}</span>
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
          Shared y-axis: {formatValue(y_domain.min, artifact.indicator)} → {formatValue(y_domain.max, artifact.indicator)}.
          Compare shapes to spot acceleration, plateau, or regression.
        </div>
      {/if}
    </header>

    {#if all_times.length >= 2}
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-x-3 gap-y-2 p-3">
        {#each cards as c (c.code)}
          {@const arr = series.get(c.code) ?? []}
          {@const dot = latestDot(arr, proj)}
          {@const is_home = c.code === home_state}
          {@const is_compare = !!compare_state && c.code === compare_state && c.code !== home_state}
          {@const stroke = is_home ? "#f59e0b" : is_compare ? "#10b981" : "#0284c7"}
          {@const bg = is_home ? "bg-amber-50" : is_compare ? "bg-emerald-50" : "bg-slate-50/50"}
          {@const stroke_w = is_home || is_compare ? 1.85 : 1.5}
          <div
            class="rounded-sm px-2 pt-1.5 pb-1 {bg}"
            class:ring-1={is_home || is_compare}
            class:ring-amber-300={is_home}
            class:ring-emerald-300={is_compare}
            data-state-code={c.code}
            data-is-home={is_home}
            data-is-compare={is_compare}
          >
            <div class="flex justify-between items-baseline gap-1">
              <div class="text-[11px] font-medium text-slate-700 truncate">{c.name}</div>
              {#if dot}
                <div
                  class="text-[10px] tabular-nums px-1 rounded {is_home ? 'bg-amber-100 text-amber-900' : is_compare ? 'bg-emerald-100 text-emerald-900' : 'text-slate-500'}"
                  data-testid="indicator-sm-latest-chip"
                >
                  {formatValue(dot.value, artifact.indicator)}
                </div>
              {/if}
            </div>
            {#if arr.length > 0}
              <svg viewBox="0 0 {W} {H}" class="w-full h-8" preserveAspectRatio="none">
                {#if baseline_y !== null}
                  <line
                    x1={PAD_X}
                    x2={W - PAD_X}
                    y1={baseline_y}
                    y2={baseline_y}
                    stroke="#94a3b8"
                    stroke-width="0.4"
                    stroke-dasharray="1 1"
                    data-testid="indicator-sm-baseline"
                  />
                {/if}
                {#each break_xs as bx}
                  <line x1={bx} x2={bx} y1={0} y2={H} stroke="#cbd5e1" stroke-width="0.5" stroke-dasharray="1.5 1.5" />
                {/each}
                <path
                  d={pathForSeries(arr, proj)}
                  fill="none"
                  stroke={stroke}
                  stroke-width={stroke_w}
                  stroke-linejoin="round"
                  stroke-linecap="round"
                />
                {#if dot}
                  <circle cx={dot.cx} cy={dot.cy} r={is_home || is_compare ? 2.2 : 1.8} fill={stroke} stroke="white" stroke-width="0.5" />
                {/if}
              </svg>
            {:else}
              <div class="h-8 flex items-center justify-center text-[10px] text-slate-400" data-testid="indicator-sm-no-data">no data</div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</section>
