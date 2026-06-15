<!--
  StateEventCrossEventSankey - R5 of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  Mounts at section 11 of the state-event page (between the constituency
  list and the all-parties directory if/when that lands). Default-off
  Sankey behind a "Show vote-flow" pill; always-on diverging bar above
  it carries the load-bearing per-party signed seat-delta.

  Wraps the existing SwingSankey primitive (frontend/src/lib/SwingSankey.svelte)
  by passing the prev event's per-party totals as `actuals` and the
  current event's per-party totals as `scenario`. SwingSankey already
  ships the diff-arithmetic + ribbon rendering; this wrapper just
  threads the per-event input + adds the section chrome (caption +
  toggle).

  No-prior case: when previous_winners is null OR empty, the section
  renders the no-prior copy with no button and no diverging bar (Max +
  Jony verdict baked into the plan-doc Section 6 R5 spec).

  Loading case: when prev_winners is `loading`, render a small
  skeleton so the citizen sees the section is alive rather than
  flickering blank then suddenly populated.

  Caption (always visible below the Sankey when expanded):
    "Approximate flow: each party's net seat loss is redistributed to
     gainers in proportion to each gainer's net seat gain. We do not
     track constituency-level flips; this is a state-total estimate."
-->
<script lang="ts">
  import SwingSankey from "../SwingSankey.svelte";
  import {
    buildCrossEventSankeyModel,
    type PartyDelta,
    type PrevWinnersState,
  } from "./cross-event-sankey-model";
  import type { ElectionResultRow } from "../view-models/election-results";

  interface Props {
    /** Current event's winners (already loaded by the parent). */
    current_winners: readonly ElectionResultRow[];
    /** Prev same-body event's winners as a loader state. */
    prev_winners: PrevWinnersState;
    /** Human-readable label of the prior event for the caption (e.g.
     *  "Assembly 2019"). Required when prev_winners.status === "ok". */
    prev_event_label: string | null;
    /** Human-readable label of the current event for the caption
     *  (e.g. "Assembly 2024"). */
    current_event_label: string;
    /** Body discriminator ("Assembly" / "Parliament") - used for the
     *  no-prior copy ("Vote-flow comparison needs a prior
     *  {body} election"). */
    body_pretty: string;
    /** State name for the no-prior copy. */
    state_name: string;
  }

  let {
    current_winners,
    prev_winners,
    prev_event_label,
    current_event_label,
    body_pretty,
    state_name,
  }: Props = $props();

  // Sankey is collapsed by default; the "Show vote-flow" pill flips
  // this on. Stays on across event navigation - the citizen who
  // expanded it on /maharashtra/elections/assembly-2024 sees it
  // expanded when they pop over to assembly-2019.
  let sankey_expanded = $state(false);

  const model = $derived.by(() => {
    if (prev_winners.status === "ok") {
      return buildCrossEventSankeyModel({
        current: current_winners,
        previous: prev_winners.rows,
      });
    }
    if (prev_winners.status === "no_prior") {
      return buildCrossEventSankeyModel({
        current: current_winners,
        previous: null,
      });
    }
    return null; // loading / failed
  });

  function fmtSignedInt(n: number): string {
    if (n > 0) return `+${n}`;
    return String(n);
  }

  // Bar layout: max abs(delta) sets the half-width; each row's bar
  // width = |delta| / max * 50 (so half the row width fits the
  // largest signed mover). Zero-delta rows show a 1px tick at the
  // axis so the citizen reads "no change" not "missing".
  const max_abs_delta = $derived.by<number>(() => {
    if (!model || model.no_prior) return 1;
    let m = 0;
    for (const r of model.diverging) {
      const a = Math.abs(r.delta);
      if (a > m) m = a;
    }
    return m > 0 ? m : 1;
  });

  function barWidthPct(d: PartyDelta): number {
    return (Math.abs(d.delta) / max_abs_delta) * 50;
  }
</script>

<section class="space-y-3" data-testid="state-event-cross-event-sankey">
  <h2 class="text-sm font-medium text-slate-700">
    Vote-flow comparison
  </h2>

  {#if prev_winners.status === "loading"}
    <p
      class="text-xs text-slate-500"
      data-testid="state-event-cross-event-sankey-loading"
    >Loading prior event data...</p>
  {:else if prev_winners.status === "failed"}
    <p class="text-xs text-rose-600">
      Vote-flow comparison data could not load: {prev_winners.reason}
    </p>
  {:else if !model || model.no_prior}
    <p
      class="text-xs text-slate-500"
      data-testid="state-event-cross-event-sankey-no-prior"
    >
      Vote-flow comparison needs a prior election; this is the first
      {body_pretty} event on record for {state_name}.
    </p>
  {:else}
    <!-- Always-on diverging bar - the load-bearing visual. -->
    <div
      class="rounded border border-slate-200 bg-white p-3"
      data-testid="state-event-cross-event-diverging-bar"
    >
      <p class="mb-2 text-xs italic text-slate-600">
        Net seat change vs the previous {body_pretty} event ({prev_event_label}).
      </p>
      <ul class="space-y-1.5">
        {#each model.diverging as r (r.party_id)}
          {@const positive = r.delta >= 0}
          {@const w = barWidthPct(r)}
          <li
            class="flex items-center gap-2 text-xs"
            data-testid="state-event-cross-event-diverging-row"
          >
            <span
              aria-hidden="true"
              class="inline-block h-2 w-2 shrink-0 rounded-full"
              style="background-color: {r.color_hex};"
            ></span>
            <span class="w-16 shrink-0 truncate font-medium text-slate-700">
              {r.party_short}
            </span>
            <!-- Bar track: two halves; axis at 50% -->
            <span class="relative flex h-2.5 flex-1 items-center">
              <span class="absolute inset-y-0 left-1/2 w-px bg-slate-300"></span>
              {#if positive}
                <span
                  class="absolute inset-y-0 left-1/2 rounded-r bg-emerald-500"
                  style="width: {w}%;"
                ></span>
              {:else}
                <span
                  class="absolute inset-y-0 rounded-l bg-rose-500"
                  style="right: 50%; width: {w}%;"
                ></span>
              {/if}
            </span>
            <span
              class="w-12 shrink-0 text-right font-mono tabular-nums {positive
                ? 'text-emerald-700'
                : 'text-rose-700'}"
            >{fmtSignedInt(r.delta)}</span>
          </li>
        {/each}
      </ul>
    </div>

    <!-- Sankey opt-in toggle + caption. -->
    <button
      type="button"
      class="inline-flex items-center rounded-yen-pill border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
      data-testid="state-event-cross-event-sankey-toggle"
      aria-expanded={sankey_expanded}
      onclick={() => (sankey_expanded = !sankey_expanded)}
    >{sankey_expanded ? "Hide vote-flow" : "Show vote-flow"}</button>

    {#if sankey_expanded}
      <div
        class="rounded border border-slate-200 bg-white p-3"
        data-testid="state-event-cross-event-sankey-panel"
      >
        <p class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {prev_event_label} -> {current_event_label}
        </p>
        <SwingSankey
          actuals={model.sankey_actuals}
          scenario={model.sankey_scenario}
        />
        <p
          class="mt-2 text-xs italic text-slate-600"
          data-testid="state-event-cross-event-sankey-caption"
        >
          Approximate flow: each party's net seat loss is redistributed to
          gainers in proportion to each gainer's net seat gain. We do not
          track constituency-level flips; this is a state-total estimate.
        </p>
      </div>
    {/if}
  {/if}
</section>
