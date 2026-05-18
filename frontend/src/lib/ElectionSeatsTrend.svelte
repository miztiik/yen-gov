<script lang="ts">
  // Self-fetching wrapper that pulls every available party-totals event for
  // one state from the canonical Parquet store (one DuckDB-WASM JOIN) and
  // renders the chronological seat-composition timeline as a StackedTrend.
  // Migrated off per-shard result.summary.json in PR-G (Phase 1.3c).

  import StackedTrend from "./charts/StackedTrend.svelte";
  import {
    electionsToStackedTrend,
    type ResultSummaryDoc,
  } from "./charts/stacked-trend/adapter-elections";
  import type { StackedTrendModel } from "./charts/stacked-trend/types";
  import {
    loadElectionSeatsTrend,
    type ElectionSeatsTrendViewModel,
  } from "./view-models/election-seats-trend";
  import type { LoaderResult } from "./loader-result";
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

  let result = $state<LoaderResult<ElectionSeatsTrendViewModel>>({
    status: "loading",
  });

  function retryLoad(): void {
    const sc = state_code;
    result = { status: "loading" };
    (async () => {
      try {
        const cat = await fetchElectionEvents();
        const events = listEventsForState(cat, sc);
        result = await loadElectionSeatsTrend(
          sc,
          events.map((e) => e.event_id),
        );
      } catch (err) {
        result = {
          status: "failed",
          reason: String(err),
          retry: retryLoad,
        };
      }
    })();
  }

  $effect(() => {
    // Reactive read of state_code so the effect re-runs when the prop changes.
    void state_code;
    retryLoad();
  });

  const summaries = $derived.by<ResultSummaryDoc[] | null>(() => {
    if (result.status !== "ok" && result.status !== "partial") return null;
    const vm = result.data;
    if (vm.events.length === 0) return null;
    return vm.events.map((e) => ({
      sources: vm.sources,
      election: e.event_id,
      state: vm.state,
      body: "assembly",
      total_seats: e.total_seats,
      party_totals: e.party_totals.map((p) => ({
        party_short: p.party_short,
        seats_contested: p.seats_contested ?? 0,
        seats_won: p.seats_won,
        votes: p.votes,
        vote_share_pct: p.vote_share_pct,
      })),
    }));
  });

  const model = $derived.by<StackedTrendModel | null>(() => {
    if (!summaries || summaries.length === 0) return null;
    return electionsToStackedTrend(summaries, {
      value,
      config: { coverage_ceiling, max_named_categories },
    });
  });
</script>

{#if result.status === "failed"}
  <div class="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
    <p>Failed to load election history: {result.reason}</p>
    <button
      type="button"
      onclick={() => result.status === "failed" && result.retry?.()}
      class="mt-2 px-3 py-1 text-xs rounded bg-rose-100 hover:bg-rose-200"
    >Retry</button>
  </div>
{:else if result.status === "loading"}
  <p class="text-sm text-slate-500">Loading election history…</p>
{:else if !model}
  <p class="text-sm text-slate-500">No election summaries available for this state yet.</p>
{:else}
  <StackedTrend {model} />
{/if}
