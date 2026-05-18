<script lang="ts">
  // TODO(PR-H / Phase 1.3d): migrate `fetchParties` onto a view-model that
  // extends dim_parties with `recognition` + `alliance` columns. The summary
  // side is already on the canonical store via `loadStateOverview` (PR-F).
  import { fetchParties, type PartyEntry, type PartyTotals } from "../lib/data";
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

  // Per-state event resolution (ADR-0023). Note: parties.json only exists
  // for events with `has_partywise=true` (May-2026 cohort today); other
  // states will surface an empty parties result gracefully.
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
  let parties = $state<PartyEntry[] | null>(null);
  let error = $state<string | null>(null);

  $effect(() => {
    summaryResult = { status: "loading" };
    parties = null;
    error = null;
    const sc = state_code;
    const ev = event;
    if (!sc || !ev) return;
    Promise.all([loadStateOverview(ev, sc), fetchParties(ev, sc)])
      .then(([s, p]) => { summaryResult = s; parties = p.parties; })
      .catch(e => (error = String(e)));
  });

  const summary = $derived(
    summaryResult.status === "ok" || summaryResult.status === "partial"
      ? summaryResult.data
      : null,
  );

  /**
   * Resolve the party from the slug. We try (1) match by ECI code in the
   * trailing token after the final `-`, then (2) match by slugified short
   * name across the loaded parties — covers older URLs that don't carry
   * the ECI suffix. Returns the canonical eci_code or null.
   */
  const party_eci_code = $derived.by<string | null>(() => {
    if (!parties && !summary) return null;
    const slug = params.party_slug;
    const dash = slug.lastIndexOf("-");
    const tail = dash >= 0 ? slug.slice(dash + 1) : slug;
    // (1) match by ECI code (case-insensitive) against parties or party_totals.
    const fromParties = parties?.find(p => p.eci_code.toLowerCase() === tail.toLowerCase())?.eci_code;
    if (fromParties) return fromParties;
    const fromTotals = summary?.party_totals.find(p => (p.party_eci_code ?? "").toLowerCase() === tail.toLowerCase())?.party_eci_code ?? null;
    if (fromTotals) return fromTotals;
    // (2) match by slugified short name.
    const head = dash >= 0 ? slug.slice(0, dash) : slug;
    const byName = parties?.find(p => slugify(p.short_name) === head)?.eci_code;
    if (byName) return byName;
    const byTotalShort = summary?.party_totals.find(p => slugify(p.party_short) === head)?.party_eci_code ?? null;
    return byTotalShort;
  });

  const party_meta = $derived(
    parties && party_eci_code
      ? (parties.find((p: PartyEntry) => p.eci_code === party_eci_code) ?? null)
      : null
  );
  const totals = $derived(
    summary && party_eci_code
      ? (summary.party_totals.find((p: PartyTotals) => p.party_eci_code === party_eci_code) ?? null)
      : null
  );
</script>

<main class="max-w-3xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={state_code ? url.state(state_code) : url.home()}>← {states.name(state_code)} overview</a></p>
    <h1 class="text-2xl font-bold">
      {#if party_meta}{party_meta.full_name}{:else}Party {party_eci_code ?? params.party_slug}{/if}
    </h1>
    {#if party_meta}
      <p class="text-sm text-slate-500">
        <span class="font-mono">{party_meta.short_name}</span>
        {#if party_meta.recognition} · {party_meta.recognition}{/if}
        {#if party_meta.alliance} · alliance: {party_meta.alliance}{/if}
      </p>
    {/if}
  </header>

  {#if error || summaryResult.status === "failed"}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load: <code>{error ?? (summaryResult.status === "failed" ? summaryResult.reason : "")}</code>
    </div>
  {:else if !summary || !parties}
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
