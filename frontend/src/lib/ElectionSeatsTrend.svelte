<script lang="ts">
  // Self-fetching wrapper that pulls every result.summary.json available
  // for one state (across all elections in the catalogue) and renders the
  // chronological seat-composition timeline as a StackedTrend.

  import StackedTrend from "./charts/StackedTrend.svelte";
  import {
    electionsToStackedTrend,
    type ResultSummaryDoc,
  } from "./charts/stacked-trend/adapter-elections";
  import type { StackedTrendModel } from "./charts/stacked-trend/types";
  import { fetchResultSummary, type ResultSummary } from "./data";
  import { fetchElectionEvents, listEventsForState } from "./election-events";

  interface Props {
    state_code: string;
    /** Which value to stack: "seats_won" (default) or "vote_share_pct". */
    value?: "seats_won" | "vote_share_pct";
    coverage_ceiling?: number;
    max_named_categories?: number;
  }

  let {
    state_code,
    value = "seats_won",
    coverage_ceiling = 0.95,
    max_named_categories = 8,
  }: Props = $props();

  let summaries = $state<ResultSummaryDoc[] | null>(null);
  let load_error = $state<string | null>(null);

  $effect(() => {
    summaries = null;
    load_error = null;
    (async () => {
      try {
        const cat = await fetchElectionEvents();
        const events = listEventsForState(cat, state_code);
        // Pull every event the catalogue lists for this state; tolerate
        // 404s (event known to catalogue but result.summary.json not yet
        // ingested) by skipping that event rather than failing the chart.
        const results = await Promise.allSettled(
          events.map(e => fetchResultSummary(e.event_id, state_code)),
        );
        summaries = results
          .filter((r): r is PromiseFulfilledResult<ResultSummary> => r.status === "fulfilled")
          .map(r => r.value as unknown as ResultSummaryDoc);
      } catch (e) {
        load_error = String(e);
      }
    })();
  });

  const model = $derived.by<StackedTrendModel | null>(() => {
    if (!summaries || summaries.length === 0) return null;
    return electionsToStackedTrend(summaries, {
      value,
      config: { coverage_ceiling, max_named_categories },
    });
  });
</script>

{#if load_error}
  <div class="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
    Failed to load election summaries: <code>{load_error}</code>
  </div>
{:else if !summaries}
  <p class="text-sm text-slate-500">Loading election history…</p>
{:else if !model}
  <p class="text-sm text-slate-500">No election summaries available for this state yet.</p>
{:else}
  <StackedTrend {model} />
{/if}
