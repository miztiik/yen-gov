<script lang="ts">
  import { type PartyTotals } from "../lib/data";
  import {
    loadStateOverview,
    type StateOverviewViewModel,
  } from "../lib/view-models/state-overview";
  import type { LoaderResult } from "../lib/loader-result";
  import {
    fetchElectionEvents,
    defaultEventForState,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";
  import { states } from "../lib/states.svelte";
  import { url } from "../lib/url";
  import { slugify } from "../lib/slug";

  // params.party_slug is `<short>-<eci_code_lower>`. The ECI code is the
  // disambiguator on the tail; everything before the final dash is the
  // (cosmetic) short-name slug. We split on the LAST dash so multi-word
  // shorts ("all-india-trinamool-congress-aitc") parse correctly.
  interface Props { params: { state: string; party_slug: string } }
  let { params }: Props = $props();

  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  const state_code = $derived(states.codeFromSlug(params.state));
  const event = $derived(
    defaultEventForState(election_catalogue, state_code)?.event_id ?? null,
  );

  let summaryResult = $state<LoaderResult<StateOverviewViewModel>>({
    status: "loading",
  });
  let error = $state<string | null>(null);

  $effect(() => {
    summaryResult = { status: "loading" };
    error = null;
    const sc = state_code;
    const ev = event;
    if (!sc || !ev) return;
    loadStateOverview(ev, sc)
      .then(s => (summaryResult = s))
      .catch(e => (error = String(e)));
  });

  const summary = $derived(
    summaryResult.status === "ok" || summaryResult.status === "partial"
      ? summaryResult.data
      : null,
  );

  /**
   * Resolve the party from the slug directly to its PartyTotals row.
   * Slug shape: `<short-slug>-<eci-code-lower>`. We try (1) match by ECI
   * code on the trailing token, then (2) match by slugified short name
   * — covers older URLs without the ECI suffix AND the canonical-store
   * gap where many parties have `eci_code = NULL` (e.g. DMK), so the
   * tail token is the short itself.
   */
  const totals = $derived.by<PartyTotals | null>(() => {
    if (!summary) return null;
    const slug = params.party_slug;
    const dash = slug.lastIndexOf("-");
    const tail = dash >= 0 ? slug.slice(dash + 1) : slug;
    const byEci = summary.party_totals.find(
      p => (p.party_eci_code ?? "").toLowerCase() === tail.toLowerCase() && p.party_eci_code,
    );
    if (byEci) return byEci;
    const head = dash >= 0 ? slug.slice(0, dash) : slug;
    return summary.party_totals.find(p => slugify(p.party_short) === head) ?? null;
  });
  const party_eci_code = $derived(totals?.party_eci_code ?? null);
</script>

<main class="max-w-3xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={state_code ? url.state(state_code) : url.home()}>← {states.name(state_code)} overview</a></p>
    <h1 class="text-2xl font-bold">
      {#if totals}{totals.party_full ?? totals.party_short}{:else}Party {party_eci_code ?? params.party_slug}{/if}
    </h1>
    {#if totals}
      <p class="text-sm text-slate-500">
        <span class="font-mono">{totals.party_short}</span>
        {#if totals.recognition} · {totals.recognition}{/if}
        {#if totals.alliance} · alliance: {totals.alliance}{/if}
      </p>
    {/if}
  </header>

  {#if error || summaryResult.status === "failed"}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load: <code>{error ?? (summaryResult.status === "failed" ? summaryResult.reason : "")}</code>
    </div>
  {:else if !summary}
    <div class="text-slate-500">Loading…</div>
  {:else if !totals}
    <div class="p-4 bg-amber-50 border border-amber-200 rounded text-amber-900">
      Party <code>{party_eci_code ?? params.party_slug}</code> not found in {states.name(state_code)} totals.
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
