<script lang="ts">
  // Self-fetching wrapper that pulls every available party-totals event for
  // one state from the canonical Parquet store (one DuckDB-WASM JOIN) and
  // renders the chronological seat-composition timeline as a StackedTrendV2.
  //
  // Track-D D10 (docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md):
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
  import SourceListV2 from "./SourceListV2.svelte";
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
        party_eci_code: p.party_eci_code,
        seats_contested: p.seats_contested ?? 0,
        seats_won: p.seats_won,
        votes: p.votes,
        vote_share_pct: p.vote_share_pct,
        party_id: p.party_id ?? null,
        brand_colour_hex: p.brand_colour_hex ?? null,
        brand_colour_confidence: p.brand_colour_confidence ?? null,
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
  <!--
    Phase 1.5 first renderer adopter — temporal viewport brush.
    Enabled here because state-level election histories often span
    1952..2024 (15+ elections for legacy states like Tamil Nadu,
    West Bengal) and the brush gives citizens a way to zoom into a
    political-era window without losing the full domain context.

    `temporal_domain_kind="month"` matches the period_id shape
    `"YYYY-MM"` emitted by `parseElectionEventId` in
    `frontend/src/lib/charts/stacked-trend/adapter-elections.ts` —
    the helper's `parseLeadingYear` matches "year-followed-by-separator",
    keeping the 5y/10y/25y presets active alongside "All" / "Recent 5".
  -->
  <StackedTrendV2
    model={v2_model}
    enable_temporal_brush={true}
    temporal_domain_kind="month"
  />
  <!--
    Provenance footer — SourceListV2 reads the full v2.0 `taxonomy.sources`
    ledger row (producer / title / vintage / license / confidence_tier /
    verification_method / url_main / citation_full / notes) per ADR-0032.
    The view-model's `sources_v2` field is `StackedTrendV2Source[]`, which
    is structurally identical to the `SourceV2Row` shape SourceListV2
    consumes (the zod schema in `stacked-trend-v2/types.ts` documents this
    deliberate mirror; the contract test `sources-v2-shape.test.ts`
    enforces both sides stay in sync). Phase 1.4 step C of the chart-plan.
  -->
  {#if (result.status === "ok" || result.status === "partial") && result.data.sources_v2.length > 0}
    <SourceListV2 sources={result.data.sources_v2} />
  {/if}
{/if}
