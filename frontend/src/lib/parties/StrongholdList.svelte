<script module lang="ts">
  // Row E of TODO/20260617-party-page-polish-and-cdn-config-plan.md
  // (Jony P1 + Citizen). The per-body strongholds list on
  // /parties/<slug> - one mount for Parliament, one for State
  // Assembly. Replaces the prior single-line `formatStrongholdTally`
  // `<ul>` (a dense run-on sentence per row inside a heavy bordered
  // box) with a two-line row hierarchy + a colour-coded strike-rate
  // badge, capped to the top `max_visible` with an inline "Show all"
  // disclosure (mirrors `../sources/SourceList.svelte`'s "+N more"
  // pattern with a `$state` boolean).
  //
  // The rows arrive ALREADY sorted best-to-least by strike-rate from
  // the loader (`compareStrongholdsByStrikeRate` in
  // `../view-models/party-detail`); this component does NOT re-sort.
  //
  // The strike-rate badge tier palette MIRRORS the sanctioned
  // `statusBadgeClass` ramp in `routes/DataCompleteness.svelte`
  // (`bg-X-100 text-X-900 border-X-300`): emerald for a dominant seat
  // (>= 80%), amber for a contested one (50-79%), rose for a marginal
  // one (< 50%).

  /** Row E: map a whole-percent strike-rate to the sanctioned tier
   *  badge classes. Bands: >= 80 emerald, 50-79 amber, < 50 rose.
   *  Pure + exported for unit coverage of the band boundaries. */
  export function strikeRateTierClass(rate: number): string {
    if (rate >= 80) return "bg-emerald-100 text-emerald-900 border-emerald-300";
    if (rate >= 50) return "bg-amber-100 text-amber-900 border-amber-300";
    return "bg-rose-100 text-rose-900 border-rose-300";
  }
</script>

<script lang="ts">
  import {
    strongholdStrikeRate,
    type PartyStronghold,
  } from "../view-models/party-detail";
  import { stateNameFromEntityId } from "./party-detail-utils";
  import { states } from "../states.svelte";

  interface Props {
    /** Strongholds for ONE body (Parliament or State Assembly),
     *  already sorted best-to-least by strike-rate upstream. */
    rows: PartyStronghold[];
    /** Top-N rows rendered before the "Show all" disclosure.
     *  Defaults to 5 per the Jony density rule. */
    max_visible?: number;
  }

  let { rows, max_visible = 5 }: Props = $props();

  let show_all = $state(false);

  const overflow = $derived(rows.length > max_visible);
  const visible = $derived(
    overflow && !show_all ? rows.slice(0, max_visible) : rows,
  );

  /** Citizen-readable state display name for a row, resolved from the
   *  `entity_id` via the shared `stateNameFromEntityId` helper +
   *  `states.name`. Falls back to the raw `state` slug on the row when
   *  the entity_id is not state-coded, and to "" when neither resolves
   *  (the "last won YYYY" half of line 2 then stands alone). */
  function rowState(s: PartyStronghold): string {
    return (
      stateNameFromEntityId(s.entity_id, (c) => states.name(c)).state_name ||
      s.state
    );
  }
</script>

<ul class="divide-y divide-slate-100" data-testid="stronghold-list">
  {#each visible as s (s.entity_id)}
    {@const rate = strongholdStrikeRate(s)}
    {@const stateName = rowState(s)}
    <li class="py-2" data-testid="stronghold-row" data-state={s.state}>
      <div class="flex items-baseline justify-between gap-3">
        {#if s.href}
          <a
            href={s.href}
            class="text-sm font-semibold text-sky-700 hover:underline"
            data-testid="stronghold-link"
          >{s.constituency_name || s.entity_id}</a>
        {:else}
          <span class="text-sm font-semibold text-slate-800"
            >{s.constituency_name || s.entity_id}</span
          >
        {/if}
        <span
          class="shrink-0 tabular-nums text-xs px-2 py-0.5 rounded border {strikeRateTierClass(
            rate,
          )}"
          data-testid="stronghold-badge"
          >{s.wins}/{s.contested} &middot; {rate}%</span
        >
      </div>
      {#if stateName || s.last_won_year != null}
        <div class="text-xs text-slate-500" data-testid="stronghold-meta">
          {#if stateName}<span>{stateName}</span>{/if}{#if stateName && s.last_won_year != null}<span
              class="text-slate-300"
            >
              &middot;
            </span>{/if}{#if s.last_won_year != null}<span
              >last won {s.last_won_year}</span
            >{/if}
        </div>
      {/if}
    </li>
  {/each}
</ul>

{#if overflow && !show_all}
  <button
    type="button"
    class="mt-1 text-xs text-slate-500 hover:underline"
    data-testid="stronghold-show-all"
    onclick={() => (show_all = true)}>Show all {rows.length}</button
  >
{/if}
