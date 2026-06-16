<!--
  StateEventPartyComposite - extracted from StateElection.svelte during
  R3 (Beck two-hat: pure structural extraction, no behaviour change) of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  Wraps the top-parties section (heading + reset button + PartyBar +
  click-to-mute caption) that previously lived inline on the
  state-event route.

  `hidden_parties` is exposed as $bindable so the in-template reset
  button and the toggleHidden handler can flip it while the parent's
  `hidden_pids` / `ac_fills_override` / `pc_fills_override`
  derivations continue to read the same source-of-truth proxy. This
  preserves the cross-section mute behaviour verbatim (muting a party
  here also recedes its cells on the AC / PC maps).

  R4 (the same plan-doc, Section 5) extends this surface into a full
  per-party-row table with [symbol][short][alliance-chip][seats-bar]
  [seats-count][vote-share%] cells; R3 preserves the legacy DOM +
  every data-testid verbatim so existing tests still pass.

  Preserves data-testids: state-event-top-parties,
  state-event-top-parties-reset, state-event-top-parties-loading.
-->
<script lang="ts">
  import PartyBar from "../PartyBar.svelte";
  import type { PartyTotals } from "../data";

  interface Props {
    loading: boolean;
    top_parties: PartyTotals[];
    total_seats: number;
    hidden_parties: Set<string>;
  }

  let {
    loading,
    top_parties,
    total_seats,
    hidden_parties = $bindable<Set<string>>(new Set()),
  }: Props = $props();

  function toggleHidden(key: string): void {
    const next = new Set(hidden_parties);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    hidden_parties = next;
  }
</script>

<!-- Top parties (TODO/20260612 Row D: reuses PartyBar; vote-share +
     seats + optional alliance tag. Row F: click-to-mute via
     hidden_parties + reset button when N > 0; mute recedes matching
     cells on the AC + PC maps via the override path. -->
<section
  class="space-y-2"
  data-testid="state-event-top-parties"
>
  <div class="flex items-baseline justify-between gap-2 flex-wrap">
    <h2 class="text-sm font-medium text-slate-700">
      Top parties by seats
    </h2>
    {#if hidden_parties.size > 0}
      <button
        type="button"
        class="text-xs text-sky-700 hover:underline"
        data-testid="state-event-top-parties-reset"
        onclick={() => (hidden_parties = new Set())}
      >Show all ({hidden_parties.size} muted)</button>
    {/if}
  </div>
  {#if loading}
    <p
      class="text-xs text-slate-500"
      data-testid="state-event-top-parties-loading"
    >Loading top parties...</p>
  {:else if top_parties.length === 0}
    <p class="text-xs text-slate-500">No party totals yet.</p>
  {:else}
    <PartyBar
      parties={top_parties}
      total_seats={total_seats}
      {hidden_parties}
      onToggleHidden={toggleHidden}
    />
    <p class="text-[11px] text-slate-500">
      Click a party row to mute it; muted parties recede on the
      map. Vote totals don't recompute.
    </p>
  {/if}
</section>
