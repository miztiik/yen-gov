<script lang="ts">
  // IndicatorCard — per-state card primitive used on /s/<state>.
  //
  // Replaces the per-artifact triple-render (IndicatorChoropleth +
  // IndicatorRanked + IndicatorSmallMultiples) on the state hub with a
  // single citizen-scaled card: big number for THIS state + sparkline of
  // THIS state's series + one-line rank against all states + "See all
  // states →" link to /t/<topic>.
  //
  // The triple-render components stay in use on /t/<topic> and /compare
  // where the cross-state question is the right one. On /s/<state> the
  // citizen is asking "how is MY state doing?" — the card answers that
  // and links out to the India view rather than mounting one per card.
  //
  // Plan doc: TODO/20260515-state-page-ia-rework-plan.md §2 + §9 row 1.
  // Doctrine: docs/concepts/schema-is-the-design-system.md (composition
  // over the existing renderer set + sparkline primitive; not a new
  // renderer family — no ADR required).
  // Naming policy: docs/concepts/indicator-naming.md — `renderer_rules:
  // [no_rank_table]` and `comparability: not_comparable_across_states |
  // directional_only` both suppress the rank line. Single-time-point
  // indicators (series < 2) suppress the sparkline, same rule
  // IndicatorSmallMultiples applies.
  import {
    fetchIndicator,
    formatValue,
    type IndicatorArtifact,
  } from "./indicators";
  import {
    latestForEntity,
    seriesForEntity,
    rankForEntity,
    canShowRank,
    ordinal,
  } from "./indicator-card";
  import type { CatalogueTopic, CatalogueArtifact } from "./catalogue";
  import AboutThisData from "./AboutThisData.svelte";
  import ListBadge from "./ListBadge.svelte";
  import { url } from "./url";

  interface Props {
    /** Catalogue topic this card belongs to (drives header + "See all states" link). */
    topic: CatalogueTopic;
    /** Catalogue artifact reference (for display labels / future overrides). */
    artifact: CatalogueArtifact;
    /** Path under DATA_BASE, e.g. "/indicators/in/fiscal/outstanding_debt_pct_gsdp.json". */
    indicator_path: string;
    /** ECI code of the state on this page (e.g. "S22"). Null while resolving. */
    home_state: string | null;
  }

  let { topic, artifact, indicator_path, home_state }: Props = $props();

  let data = $state<IndicatorArtifact | null>(null);
  let load_error = $state<string | null>(null);

  $effect(() => {
    data = null;
    load_error = null;
    fetchIndicator(indicator_path)
      .then(a => (data = a))
      .catch(e => (load_error = String(e)));
  });

  const meta = $derived(data?.indicator ?? null);
  const home_latest = $derived(
    data && home_state ? latestForEntity(data.rows, home_state) : null,
  );
  const series = $derived(
    data && home_state ? seriesForEntity(data.rows, home_state) : [],
  );
  const rank_info = $derived(
    data && home_state && meta
      ? rankForEntity(data.rows, home_state, meta.direction, canShowRank(meta))
      : null,
  );

  // Sparkline geometry — same conventions as IndicatorSmallMultiples
  // (single Y axis = max abs across this state's series; no axes; latest
  // value gets a dot). Wider/taller than the small-multiples tile because
  // there's only one of these per topic, not 36.
  const W = 240;
  const H = 48;
  const PAD_X = 2;
  const PAD_Y = 3;
  const span = $derived(series.length > 1 ? series.length - 1 : 1);
  const y_max = $derived.by(() => {
    let m = 0;
    for (const p of series) if (Math.abs(p.value) > m) m = Math.abs(p.value);
    return m || 1;
  });
  const sparkline_path = $derived.by(() => {
    if (series.length < 2) return "";
    const inner_w = W - 2 * PAD_X;
    const inner_h = H - 2 * PAD_Y;
    return series
      .map((p, i) => {
        const x = PAD_X + (i / span) * inner_w;
        const y = PAD_Y + inner_h - (Math.abs(p.value) / y_max) * inner_h;
        return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  });
  const sparkline_dot = $derived.by(() => {
    if (series.length < 2) return null;
    const last = series[series.length - 1];
    const inner_w = W - 2 * PAD_X;
    const inner_h = H - 2 * PAD_Y;
    const idx = series.length - 1;
    return {
      cx: PAD_X + (idx / span) * inner_w,
      cy: PAD_Y + inner_h - (Math.abs(last.value) / y_max) * inner_h,
    };
  });

  // Per indicator-naming.md, `higher_is_better` keeps a green tinge,
  // `lower_is_better` red, `neutral` blue. Sparkline stroke only — we do
  // NOT colour the big number (intensity coding stays in the choropleth).
  const stroke = $derived.by(() => {
    if (!meta) return "#0284c7";
    if (meta.direction === "higher_is_better") return "#059669";
    if (meta.direction === "lower_is_better") return "#dc2626";
    return "#0284c7";
  });

  // Link to the topic page until /i/<indicator> exists (per plan §2:
  // "See all states →" → `url.topic(topic.id)`).
  const see_all_href = $derived(url.topic(topic.id));
</script>

<section
  class="bg-white rounded-lg shadow-sm ring-1 ring-slate-200/70 p-4 space-y-3"
  data-testid="indicator-card"
>
  {#if load_error}
    <div class="text-sm bg-rose-50 border border-rose-200 text-rose-900 rounded px-3 py-2">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !data || !meta}
    <div class="text-sm text-slate-500">Loading…</div>
  {:else}
    <header class="flex items-baseline gap-2 flex-wrap">
      <h3 class="text-sm font-semibold text-slate-800">{meta.title}</h3>
      {#if artifact.display && artifact.display !== meta.title}
        <span class="text-xs text-slate-400">· {artifact.display}</span>
      {/if}
    </header>

    <!-- Big number + sparkline row. On narrow viewports they stack; the
         sparkline is decorative when home data is missing. -->
    <div class="flex items-end justify-between gap-4 flex-wrap">
      <div class="min-w-0">
        {#if home_latest}
          <div class="text-3xl font-bold tabular-nums text-slate-900 leading-none">
            {formatValue(home_latest.value, meta)}
          </div>
          <div class="text-[11px] uppercase tracking-[0.1em] text-slate-500 mt-1">
            {home_latest.time}
          </div>
        {:else}
          <div class="text-sm text-slate-400 italic">No data for this state yet.</div>
        {/if}
      </div>

      {#if sparkline_path}
        <svg
          viewBox="0 0 {W} {H}"
          class="w-40 h-12 flex-shrink-0"
          preserveAspectRatio="none"
          aria-hidden="true"
          data-testid="indicator-card-sparkline"
        >
          <path
            d={sparkline_path}
            fill="none"
            stroke={stroke}
            stroke-width="1.5"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          {#if sparkline_dot}
            <circle cx={sparkline_dot.cx} cy={sparkline_dot.cy} r="2" fill={stroke} />
          {/if}
        </svg>
      {/if}
    </div>

    <!-- Rank line. Suppressed when the indicator is not comparable across
         states or carries renderer_rules: [no_rank_table] (canShowRank
         encapsulates both). When only one state has data, rank is "1 of 1"
         which is meaningless — suppress total=1 too. -->
    {#if rank_info && rank_info.total > 1}
      <p class="text-xs text-slate-600">
        {ordinal(rank_info.rank)} of {rank_info.total} states, {rank_info.time}.
      </p>
    {/if}

    <footer class="flex items-center justify-between gap-3 pt-1 border-t border-slate-100">
      <ListBadge list={topic.list} compact />
      <a
        class="text-xs text-blue-600 hover:underline"
        href={see_all_href}
        data-testid="indicator-card-see-all"
      >See all states →</a>
    </footer>

    <AboutThisData artifact={data} />
  {/if}
</section>
