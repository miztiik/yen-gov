<!--
  StateEventAllParties - "All parties - directory" section for the
  state-event page. Gap-closure G3
  (TODO/20260616-state-event-page-gap-closure-plan.md): the directory
  existed on StateOverview but was never mounted on the election route.

  Searchable grid of every party that contested the event. Each entry is
  a PartyPill linking to /parties/<slug>, with seats + vote-share. Mirrors
  the StateOverview "All parties - directory" surface so the two pages
  read identically. Zero-seat parties collapse behind a toggle so the
  default view stays scannable.

  PartyPill carries suppress_tooltip (G1) because the directory rows are
  links - the row itself is the affordance, not a hover popover.
-->
<script lang="ts">
  import PartyPill from "../party-pill/PartyPill.svelte";
  import { partyRowForResolver } from "../colors/party-row";
  import { link } from "../links";
  import type { PartyTotals } from "../data";

  interface Props {
    parties: readonly PartyTotals[];
    loading?: boolean;
  }

  let { parties, loading = false }: Props = $props();

  let query = $state("");
  let show_zero_seat = $state(false);

  // Split contested-with-seats vs zero-seat so the default directory
  // stays scannable; the zero-seat tail is one toggle away.
  const with_seats = $derived(parties.filter((p) => p.seats_won > 0));
  const zero_seat = $derived(parties.filter((p) => p.seats_won === 0));

  const visible = $derived(show_zero_seat ? parties : with_seats);

  const filtered = $derived.by<readonly PartyTotals[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) return visible;
    return visible.filter(
      (p) =>
        p.party_short.toLowerCase().includes(q) ||
        (p.party_eci_code ?? "").toLowerCase().includes(q) ||
        (p.party_full ?? "").toLowerCase().includes(q),
    );
  });
</script>

<section
  class="rounded border border-slate-200 bg-white p-4"
  data-testid="state-event-all-parties"
>
  <div class="mb-1 flex flex-wrap items-baseline justify-between gap-3">
    <h2 class="text-sm font-semibold text-slate-800">
      All parties &middot; directory
    </h2>
    <div class="flex items-center gap-3">
      <input
        type="search"
        placeholder="Search parties..."
        bind:value={query}
        class="w-44 rounded border border-slate-300 px-2 py-1 text-xs"
        aria-label="Search parties by name or ECI code"
        data-testid="state-event-all-parties-search"
      />
      <span class="text-xs text-slate-400 tabular-nums">
        {filtered.length} / {parties.length}
      </span>
    </div>
  </div>
  <p class="mb-3 text-xs text-slate-500">
    Every party that contested. Click a name to open its party page.
  </p>

  {#if loading}
    <p class="text-xs text-slate-500" data-testid="state-event-all-parties-loading">
      Loading parties...
    </p>
  {:else if parties.length === 0}
    <p class="text-xs text-slate-500">No party totals yet.</p>
  {:else if filtered.length === 0}
    <p class="text-sm italic text-slate-500">
      No parties match <code class="rounded bg-slate-100 px-1">{query}</code>.
    </p>
  {:else}
    <ul class="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 md:grid-cols-3">
      {#each filtered as p (p.party_id ?? p.party_short)}
        {@const href = p.party_id ? link.party(p.party_id) : null}
        {@const pill_row = partyRowForResolver(p)}
        <li data-testid="state-event-all-parties-row">
          {#if href}
            <a class="inline-flex items-center gap-1.5 hover:underline" {href}>
              <PartyPill
                size="sm"
                party_id={p.party_id}
                party_short={p.party_short}
                row={pill_row}
                suppress_tooltip
              />
              <span class="text-xs text-slate-400 tabular-nums">
                &middot; {p.seats_won} seats &middot; {p.vote_share_pct.toFixed(1)}%
              </span>
            </a>
          {:else}
            <span class="inline-flex items-center gap-1.5">
              <PartyPill
                size="sm"
                party_id={p.party_id}
                party_short={p.party_short}
                row={pill_row}
                suppress_tooltip
              />
              <span class="text-xs text-slate-400 tabular-nums">
                &middot; {p.seats_won} seats &middot; {p.vote_share_pct.toFixed(1)}%
              </span>
            </span>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if !loading && zero_seat.length > 0}
    <div class="pt-3">
      <button
        type="button"
        class="text-xs text-sky-700 hover:underline"
        data-testid="state-event-all-parties-zero-toggle"
        onclick={() => (show_zero_seat = !show_zero_seat)}
      >
        {show_zero_seat
          ? `Hide ${zero_seat.length} zero-seat parties`
          : `Show ${zero_seat.length} parties with no seats`}
      </button>
    </div>
  {/if}
</section>
