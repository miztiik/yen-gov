<script lang="ts">
  // AllianceTotals - PR-W3b alliance-first display panel.
  //
  // Joins the per-event winner rows (one per AC/PC) with the alliance
  // membership table at `datasets/data/entities/party_alliances.csv`
  // (loaded via `psephlab/alliances.ts.loadAlliances(event)` which keys
  // by period_label and yields a `(party_id) -> alliance | null` lookup).
  //
  // Layout:
  //   1. Alliance-first total line: "NDA 11 / INDIA 0 / Others 0"
  //   2. Caption: "alliance as of polling date <date>"
  //   3. Toggle: "Show party breakdown"
  //      - Expands to a grouped list of (alliance -> [party x seats])
  //
  // Citizen-readable framing: parties without an alliance row collapse
  // under "Others". An alliance entry shows as "<alliance> <seats>" with
  // no comma after the last entry. The component degrades gracefully
  // when no alliance rows exist for the event (renders an inline
  // "alliance data pending" pill in lieu of the total line) per the
  // PR-W3b escalation rule in the plan-doc.

  import { loadAlliances } from "../psephlab/alliances";
  import type { AllianceLookup } from "../psephlab/types";
  import {
    deriveAllianceBreakdown,
    type AllianceBreakdown,
    type WinnerInput,
  } from "./alliance-totals-model";

  interface Props {
    event: string;
    /** One row per won seat. Length = total seats for the event/state. */
    winners: readonly WinnerInput[];
    /** Polled-on date for the caption (e.g. "2024-06-01"). Falls back
     *  to a generic caption when missing. */
    polled_on?: string | null;
  }

  let { event, winners, polled_on }: Props = $props();

  let lookup = $state<AllianceLookup | null>(null);

  $effect(() => {
    const ev = event;
    lookup = null;
    loadAlliances(ev).then((l) => {
      // Guard against stale event resolves.
      if (ev === event) lookup = l;
    });
  });

  const breakdown = $derived<AllianceBreakdown>(
    lookup === null
      ? { rows: [], by_alliance: new Map(), has_any: false }
      : deriveAllianceBreakdown(winners, lookup),
  );

  let expanded = $state(false);
  function toggle(): void {
    expanded = !expanded;
  }
</script>

<section
  class="rounded border border-slate-200 bg-white p-4"
  data-testid="alliance-totals"
>
  <h2 class="text-sm font-medium text-slate-700">Alliance totals</h2>
  {#if lookup === null}
    <p class="mt-2 text-xs text-slate-500">Loading alliance data…</p>
  {:else if !breakdown.has_any}
    <p
      class="mt-2 inline-block rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-800"
      data-testid="alliance-totals-pending"
    >
      Alliance data pending for this event.
    </p>
  {:else}
    <p
      class="mt-2 text-lg font-semibold text-slate-900"
      data-testid="alliance-totals-headline"
    >
      {#each breakdown.rows as r, i (r.alliance)}
        <span class="whitespace-nowrap">
          {r.alliance} <span class="tabular-nums">{r.seats}</span>
        </span>
        {#if i < breakdown.rows.length - 1}<span
            class="px-1.5 text-slate-400">/</span
          >{/if}
      {/each}
    </p>
    <p class="mt-1 text-xs text-slate-500">
      alliance as of polling date <span class="tabular-nums"
        >{polled_on ?? "unspecified"}</span
      >
    </p>
    <button
      type="button"
      class="mt-2 text-xs text-sky-700 hover:underline"
      data-testid="alliance-totals-toggle"
      onclick={toggle}
    >
      {expanded ? "Hide" : "Show"} party breakdown
    </button>
    {#if expanded}
      <ul
        class="mt-3 space-y-3 text-sm"
        data-testid="alliance-totals-breakdown"
      >
        {#each breakdown.rows as r (r.alliance)}
          <li>
            <div class="text-xs font-semibold uppercase text-slate-500">
              {r.alliance} ({r.seats})
            </div>
            <ul class="mt-1 ml-3 space-y-0.5 text-slate-700">
              {#each breakdown.by_alliance.get(r.alliance) ?? [] as p (p.party_id)}
                <li class="flex justify-between gap-3">
                  <span class="truncate">{p.party_short}</span>
                  <span class="tabular-nums text-slate-500">{p.seats}</span>
                </li>
              {/each}
            </ul>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
