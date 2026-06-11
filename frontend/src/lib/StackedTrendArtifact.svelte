<script lang="ts">
  // Self-fetching wrapper that turns an indicator artifact path into a
  // rendered StackedTrendV2. Used by topic / state pages to render any
  // indicator whose `chart_type === "stacked-trend"`.
  //
  // Track-D D11..D12 (docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md):
  // second (LAST) caller migration v1 `StackedTrend` → v2 `StackedTrendV2`.
  // After this PR merges, PR-17 (D13) can delete v1 — zero callers will
  // remain.
  //
  // Indicator artifacts carry their own inline `sources` array
  // (Array<{ url, fetched_at, name?, authority? }>), NOT a `source_id` FK
  // into taxonomy.sources. So we cannot JOIN the canonical citation
  // ledger here the way `ElectionSeatsTrend.svelte` does (PR-15 / D10).
  // We migrate the RENDERER only and pass `sources = []` to the
  // migrate adapter. The legacy inline source list is rendered through
  // the new SourceList component (from $lib/sources) after projecting
  // the IndicatorSource shape into a SourceRow via a small inline
  // helper. True v2.0 ledger wiring for indicator artifacts is deferred
  // to a future track.

  import { loadIndicator } from "./canonical/indicator-from-canonical";
  import StackedTrendV2 from "./charts/StackedTrendV2.svelte";
  import { SourceList, dedupeToPills, type SourceRow } from "./sources";
  import {
    indicatorToStackedTrend,
    type IndicatorDoc,
  } from "./charts/stacked-trend/adapter-indicator";
  import type { StackedTrendModel } from "./charts/stacked-trend/types";
  import {
    stackedTrendModelToV2,
    type StackedTrendV2Model,
  } from "./charts/stacked-trend-v2";
  import { loadStates, type StateRow } from "./view-models/states";
  import { humanise } from "./humanise";

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
  // Currently-valid Indian states+UTs from taxonomy.entities. Used by the
  // eci_to_state_name lookup the stacked-trend adapter consumes for both
  // spatial entity labels and temporal entity-label resolution. Replaces
  // STATE_NAME_TO_ECI per T.0e.
  let states_taxonomy = $state<StateRow[] | null>(null);
  loadStates()
    .then(s => (states_taxonomy = s))
    .catch(() => (states_taxonomy = []));

  $effect(() => {
    doc = null;
    load_error = null;
    loadIndicator(indicator_path)
      .then(a => (doc = a as unknown as IndicatorDoc))
      .catch(e => (load_error = String(e)));
  });

  const eci_to_state_name = $derived.by(() => {
    const m: Record<string, string> = {};
    for (const s of states_taxonomy ?? []) m[s.eci_code] = s.boundary_join_name;
    return m;
  });

  // Facet-label resolution chain (per indicator schema 1.4 / Phase 4 C2):
  //   1. caller-supplied `category_labels` prop (explicit override)
  //   2. artifact's own `indicator.facet_labels` (composer-as-source-of-truth)
  //   3. humanise(facet_id) fallback so a missing label never produces
  //      "other_thermal" in a citizen chart legend
  const resolved_labels = $derived.by<Record<string, string> | undefined>(() => {
    if (category_labels) return category_labels;
    const fromDoc = doc?.indicator.facet_labels;
    if (fromDoc) return fromDoc;
    if (!doc) return undefined;
    const out: Record<string, string> = {};
    for (const r of doc.rows) {
      if (r.facet && !(r.facet in out)) out[r.facet] = humanise(r.facet);
    }
    return out;
  });

  const v1_model = $derived.by<StackedTrendModel | null>(() => {
    if (!doc) return null;
    if (mode === "spatial") {
      const times = [...new Set(doc.rows.map(r => r.time))].sort();
      const t = spatial_time ?? times.at(-1);
      if (!t) return null;
      return indicatorToStackedTrend(doc, {
        mode: { kind: "spatial", time: t, entity_labels: eci_to_state_name },
        config: { coverage_ceiling, max_named_categories },
        dimension,
        category_labels: resolved_labels,
      });
    }
    if (!entity_id) return null;
    return indicatorToStackedTrend(doc, {
      mode: { kind: "temporal", entity_id, entity_label: eci_to_state_name[entity_id] },
      config: { coverage_ceiling, max_named_categories },
      dimension,
      category_labels: resolved_labels,
    });
  });

  // v2 model - bridges the v1 adapter through the migration shim. Indicator
  // artifacts do NOT carry source_id FKs into taxonomy.sources (unlike the
  // election view-model in D10), so we pass an empty pills array. The
  // citizen-visible "Sources" disclosure stays on the page via the
  // SourceList from $lib/sources below, fed by a per-render projection
  // of the inline IndicatorSource[] into PublisherPills.
  const v2_model = $derived.by<StackedTrendV2Model | null>(() => {
    if (!v1_model) return null;
    return stackedTrendModelToV2(v1_model, []);
  });

  const pills = $derived(
    v1_model
      ? dedupeToPills(
          v1_model.sources.map<SourceRow>((s) => ({
            source_id: "src-legacy-" + (s.url ?? "").slice(0, 12),
            producer: s.authority ?? s.name ?? "Unknown",
            title: s.name ?? "",
            vintage: s.fetched_at ?? "",
            url: s.url ?? null,
          })),
        )
      : [],
  );
</script>

{#if load_error}
  <div class="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
    Failed to load indicator: <code>{load_error}</code>
  </div>
{:else if !doc}
  <p class="text-sm text-slate-500">Loading…</p>
{:else if v2_model && v1_model}
  <StackedTrendV2 model={v2_model} />
  <!--
    Provenance footer - publisher pills via the new SourceList from
    $lib/sources. Indicator artifact carries inline
    `sources: Array<{url, fetched_at, name?, authority?}>` per the
    v1 IndicatorDoc contract; we project them into the canonical pill
    shape inline above. Future track migrates the IndicatorDoc contract
    itself to the canonical source.csv.
  -->
  {#if pills.length > 0}
    <SourceList {pills} />
  {/if}
{:else}
  <p class="text-sm text-slate-500">No data to render.</p>
{/if}
