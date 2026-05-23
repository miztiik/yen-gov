<script lang="ts">
  // Self-fetching wrapper that pulls every available party-totals event for
  // one state from the canonical Parquet store (one DuckDB-WASM JOIN) and
  // renders the chronological seat-composition timeline as a StackedTrendV2.
  //
  // Track-D D10 (TODO/20260518-frontend-charting-modernisation-plan.md):
  // first caller migration from v1 `StackedTrend.svelte` →
  // v2 `StackedTrendV2.svelte`. The view-model loader already JOINs
  // `taxonomy.sources` (R-28) — D10 extends it to emit the full
  // v2.0 ledger row alongside the legacy `SourceRef[]` for back-compat.
  // The migrate adapter `stackedTrendModelToV2(model, sourcesV2)` is the
  // bridge — pure / sync / no DOM, unit-tested in
  // `frontend/src/lib/charts/stacked-trend-v2/migrate.test.ts`.
  //
  // R-08: v1 `StackedTrend.svelte` STILL ships untouched. Two other
  // callers (`StackedTrendArtifact.svelte`, plus v1's internal direct
  // imports) keep the v1 component alive until D11..D12 migrate them
  // and D13 deletes v1.

  import StackedTrendV2 from "./charts/StackedTrendV2.svelte";
  import SourceList from "./SourceList.svelte";
  import {
    electionsToStackedTrend,
    type ResultSummaryDoc,
  } from "./charts/stacked-trend/adapter-elections";
  import type { StackedTrendModel } from "./charts/stacked-trend/types";
  import {
    stackedTrendModelToV2,
    type StackedTrendV2Model,
  } from "./charts/stacked-trend-v2";
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

  const v1_model = $derived.by<StackedTrendModel | null>(() => {
    if (!summaries || summaries.length === 0) return null;
    return electionsToStackedTrend(summaries, {
      value,
      config: { coverage_ceiling, max_named_categories },
    });
  });

  // v2 model — bridges the v1 adapter through the migration shim,
  // injecting the v2.0 ledger rows the view-model resolved from
  // `taxonomy.sources`. The adapter `electionsToStackedTrend` is
  // unchanged (still v1) — Phase 2 polish is at the renderer seam.
  const v2_model = $derived.by<StackedTrendV2Model | null>(() => {
    if (!v1_model) return null;
    if (result.status !== "ok" && result.status !== "partial") return null;
    return stackedTrendModelToV2(v1_model, result.data.sources_v2);
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
{:else if !v2_model}
  <p class="text-sm text-slate-500">No election summaries available for this state yet.</p>
{:else}
  <StackedTrendV2 model={v2_model} />
  <!--
    Provenance footer — preserved verbatim from v1 (StackedTrend.svelte
    rendered `<SourceList sources={model.sources} />` inline). StackedTrendV2
    doesn't carry an internal source list yet (its sources slot is reserved
    for the Phase 1.4 SourceListV2 wiring), so we render the legacy footer
    from the caller to keep the citizen-visible "Sources (N)" disclosure
    on the page. The legacy SourceRef[] back-compat array on the view-model
    is filtered by `url_main` truthiness, matching v1 semantics exactly.
  -->
  {#if (result.status === "ok" || result.status === "partial") && result.data.sources.length > 0}
    <SourceList sources={result.data.sources} />
  {/if}
{/if}
