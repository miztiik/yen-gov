<script lang="ts">
  import {
    fetchResultSummary, fetchParties,
    type ResultSummary, type PartyEntry, type PartyTotals,
  } from "../lib/data";
  import { states } from "../lib/states.svelte";

  interface Props { params: { state: string; party_eci_code: string } }
  let { params }: Props = $props();

  const event = "AcGenMay2026";

  let summary = $state<ResultSummary | null>(null);
  let parties = $state<PartyEntry[] | null>(null);
  let error = $state<string | null>(null);

  $effect(() => {
    summary = null; parties = null; error = null;
    Promise.all([fetchResultSummary(event, params.state), fetchParties(event, params.state)])
      .then(([s, p]) => { summary = s; parties = p.parties; })
      .catch(e => (error = String(e)));
  });

  const party_meta = $derived(
    parties ? (parties.find((p: PartyEntry) => p.eci_code === params.party_eci_code) ?? null) : null
  );
  const totals = $derived(
    summary
      ? (summary.party_totals.find((p: PartyTotals) => p.party_eci_code === params.party_eci_code) ?? null)
      : null
  );
</script>

<main class="max-w-3xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={`#/s/${params.state}`}>← {states.name(params.state)} overview</a></p>
    <h1 class="text-2xl font-bold">
      {#if party_meta}{party_meta.full_name}{:else}Party {params.party_eci_code}{/if}
    </h1>
    {#if party_meta}
      <p class="text-sm text-slate-500">
        <span class="font-mono">{party_meta.short_name}</span>
        {#if party_meta.recognition} · {party_meta.recognition}{/if}
        {#if party_meta.alliance} · alliance: {party_meta.alliance}{/if}
      </p>
    {/if}
  </header>

  {#if error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load: <code>{error}</code>
    </div>
  {:else if !summary || !parties}
    <div class="text-slate-500">Loading…</div>
  {:else if !totals}
    <div class="p-4 bg-amber-50 border border-amber-200 rounded text-amber-900">
      Party <code>{params.party_eci_code}</code> not found in {states.name(params.state)} totals.
    </div>
  {:else}
    <section class="bg-white rounded-lg shadow-sm p-5 grid sm:grid-cols-3 gap-4 text-sm">
      <div>
        <div class="text-xs uppercase text-slate-500">Seats won</div>
        <div class="text-2xl font-bold">{totals.seats_won}</div>
        <div class="text-slate-500">of {summary.total_seats}</div>
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Vote share</div>
        <div class="text-2xl font-bold">{totals.vote_share_pct.toFixed(2)}%</div>
        <div class="text-slate-500">{totals.votes.toLocaleString()} votes</div>
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Seats contested</div>
        <div class="text-2xl font-bold">{totals.seats_contested ?? "—"}</div>
        <div class="text-slate-500">strike rate {totals.seats_contested ? ((totals.seats_won / totals.seats_contested) * 100).toFixed(1) + "%" : "—"}</div>
      </div>
    </section>
  {/if}
</main>
