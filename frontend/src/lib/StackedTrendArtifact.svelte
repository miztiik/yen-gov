<script lang="ts">
  // Self-fetching wrapper that turns an indicator artifact path into a
  // rendered StackedTrend. Used by topic / state pages to render any
  // indicator whose `chart_type === "stacked-trend"`.

  import { fetchIndicator } from "./indicators";
  import StackedTrend from "./charts/StackedTrend.svelte";
  import {
    indicatorToStackedTrend,
    type IndicatorDoc,
  } from "./charts/stacked-trend/adapter-indicator";
  import type { StackedTrendModel } from "./charts/stacked-trend/types";
  import { STATE_NAME_TO_ECI } from "./maplibre/sources";

  interface Props {
    indicator_path: string;
    /** "spatial" picks one time slice and bars by entity; "temporal" picks one entity and bars by time. */
    mode: "spatial" | "temporal";
    /** For spatial mode: which time. Defaults to latest in the artifact. */
    spatial_time?: string;
    /** For temporal mode: which entity. */
    entity_id?: string;
    /** Dimension name for colour anchors (e.g. "power_source"). */
    dimension: string;
    /** Optional category labels for legend / tooltips. */
    category_labels?: Record<string, string>;
    /** Top-N rollup config. */
    coverage_ceiling?: number;
    max_named_categories?: number;
  }

  let {
    indicator_path,
    mode,
    spatial_time,
    entity_id,
    dimension,
    category_labels,
    coverage_ceiling = 0.95,
    max_named_categories = 8,
  }: Props = $props();

  let doc = $state<IndicatorDoc | null>(null);
  let load_error = $state<string | null>(null);

  $effect(() => {
    doc = null;
    load_error = null;
    fetchIndicator(indicator_path)
      .then(a => (doc = a as unknown as IndicatorDoc))
      .catch(e => (load_error = String(e)));
  });

  const eci_to_state_name = $derived.by(() => {
    const m: Record<string, string> = {};
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) m[code] = name;
    return m;
  });

  const model = $derived.by<StackedTrendModel | null>(() => {
    if (!doc) return null;
    if (mode === "spatial") {
      const times = [...new Set(doc.rows.map(r => r.time))].sort();
      const t = spatial_time ?? times.at(-1);
      if (!t) return null;
      return indicatorToStackedTrend(doc, {
        mode: { kind: "spatial", time: t, entity_labels: eci_to_state_name },
        config: { coverage_ceiling, max_named_categories },
        dimension,
        category_labels,
      });
    }
    if (!entity_id) return null;
    return indicatorToStackedTrend(doc, {
      mode: { kind: "temporal", entity_id, entity_label: eci_to_state_name[entity_id] },
      config: { coverage_ceiling, max_named_categories },
      dimension,
      category_labels,
    });
  });
</script>

{#if load_error}
  <div class="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
    Failed to load indicator: <code>{load_error}</code>
  </div>
{:else if !doc}
  <p class="text-sm text-slate-500">Loading…</p>
{:else if model}
  <StackedTrend {model} />
{:else}
  <p class="text-sm text-slate-500">No data to render.</p>
{/if}
