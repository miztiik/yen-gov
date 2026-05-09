<script lang="ts">
  import {
    fetchResultSummary, fetchConstituencies, fetchDistricts,
    type ResultSummary, type ConstituencyEntry, type PartyTotals, type DistrictEntry,
  } from "../lib/data";
  import PartyBar from "../lib/PartyBar.svelte";
  import SeatDonut from "../lib/SeatDonut.svelte";
  import MarginHistogram from "../lib/MarginHistogram.svelte";
  import StateAcMap from "../lib/maplibre/StateAcMap.svelte";
  import { STATE_AC } from "../lib/maplibre/sources";
  import { states } from "../lib/states.svelte";

  interface Props { params: { state: string } }
  let { params }: Props = $props();

  const event = "AcGenMay2026";
  const state_code = $derived(params.state);

  let summary = $state<ResultSummary | null>(null);
  let acs = $state<ConstituencyEntry[] | null>(null);
  let districts = $state<DistrictEntry[] | null>(null);
  let error = $state<string | null>(null);

  $effect(() => {
    summary = null;
    acs = null;
    districts = null;
    error = null;
    const sc = state_code;
    Promise.all([
      fetchResultSummary(event, sc),
      fetchConstituencies(sc),
      fetchDistricts(sc),
    ])
      .then(([s, c, d]) => { summary = s; acs = c.constituencies; districts = d.districts; })
      .catch(e => (error = String(e)));
  });

  const top_parties = $derived(
    summary
      ? summary.party_totals.filter((p: PartyTotals) => p.seats_won > 0 || p.vote_share_pct >= 1.0)
      : []
  );

  // Group ACs by district_id, then sort districts by AC count (descending).
  // ACs without a district_id fall under a synthetic '—' bucket so the count
  // surface is honest rather than silently dropping rows.
  const by_district = $derived.by(() => {
    if (!acs || !districts) return [];
    const name_by_id = new Map(districts.map(d => [d.id, d.name]));
    const groups = new Map<string, ConstituencyEntry[]>();
    for (const ac of acs) {
      const k = ac.district_id ?? "";
      const arr = groups.get(k) ?? [];
      arr.push(ac);
      groups.set(k, arr);
    }
    const out: { id: string; name: string; acs: ConstituencyEntry[] }[] = [];
    for (const [id, group] of groups) {
      out.push({
        id,
        name: id ? (name_by_id.get(id) ?? id) : "(unmapped)",
        acs: group.sort((a, b) => a.eci_no - b.eci_no),
      });
    }
    out.sort((a, b) => b.acs.length - a.acs.length || a.name.localeCompare(b.name));
    return out;
  });
</script>

<main class="max-w-5xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href="#/">← All states</a></p>
    <h1 class="text-2xl font-bold">{states.name(state_code)} — Legislative Assembly, May 2026</h1>
    <p class="text-sm text-slate-500">
      Event <code class="font-mono">{event}</code> · State <code class="font-mono">{state_code}</code>
      · <a class="text-blue-600 hover:underline" href={`#/s/${state_code}/explore`}>SQL explorer →</a>
      · <a class="text-blue-600 hover:underline" href={`#/lab/${state_code}/${event}`}>Psephlab →</a>
    </p>
  </header>

  {#if error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load: <code>{error}</code>
    </div>
  {:else if !summary || !acs || !districts}
    <div class="text-slate-500">Loading…</div>
  {:else}
    {#if STATE_AC[state_code]}
      <section class="bg-white rounded-lg shadow-sm p-4">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Constituency map</h2>
        <StateAcMap {event} state={state_code} />
        <p class="text-xs text-slate-400 mt-2">
          Hover for winner & margin · click an AC to drill in. Opacity ∝ margin of victory.
        </p>
      </section>
    {/if}

    <section class="grid md:grid-cols-[1fr_minmax(240px,auto)] gap-6 items-start">
      <div class="bg-white rounded-lg shadow-sm p-5">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Seats by party</h2>
        <PartyBar parties={top_parties} total_seats={summary.total_seats} />
      </div>
      <div class="bg-white rounded-lg shadow-sm p-5">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3 text-center">Seat share</h2>
        <SeatDonut parties={summary.party_totals} total_seats={summary.total_seats} />
      </div>
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5 text-sm text-slate-600">
      <div class="flex justify-between gap-4 flex-wrap">
        <div>Total votes polled: <span class="font-semibold text-slate-900">{summary.totals?.votes_polled?.toLocaleString() ?? "—"}</span></div>
        <div>Sources: <span class="font-mono text-xs">{summary.sources.length}</span></div>
        <div class="text-xs text-slate-400">Schema {summary.$schema_version}</div>
      </div>
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Margin of victory</h2>
      <MarginHistogram {event} state={state_code} />
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <div class="flex justify-between items-baseline mb-3">
        <h2 class="text-sm font-semibold uppercase text-slate-500">Parties</h2>
        <span class="text-xs text-slate-400">{summary.party_totals.length} total</span>
      </div>
      <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm">
        {#each summary.party_totals as p}
          {#if p.party_eci_code}
            <li>
              <a class="hover:underline" href={`#/s/${state_code}/party/${p.party_eci_code}`}>
                <span class="font-medium">{p.party_short}</span>
                <span class="text-slate-400 text-xs"> · {p.seats_won} seats · {p.vote_share_pct.toFixed(1)}%</span>
              </a>
            </li>
          {:else}
            <li class="text-slate-500">
              {p.party_short}
              <span class="text-slate-400 text-xs"> · {p.seats_won} seats · {p.vote_share_pct.toFixed(1)}%</span>
            </li>
          {/if}
        {/each}
      </ul>
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <div class="flex justify-between items-baseline mb-3">
        <h2 class="text-sm font-semibold uppercase text-slate-500">Constituencies by district</h2>
        <span class="text-xs text-slate-400">{by_district.length} districts · {acs.length} ACs</span>
      </div>
      <div class="space-y-4">
        {#each by_district as g}
          <div>
            <div class="flex items-baseline justify-between border-b border-slate-200 pb-1 mb-2">
              <h3 class="text-sm font-semibold">{g.name}</h3>
              <span class="text-xs text-slate-400 font-mono">{g.id || "—"} · {g.acs.length}</span>
            </div>
            <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm font-mono">
              {#each g.acs as ac}
                <li>
                  <a class="hover:underline" href={`#/s/${state_code}/ac/${ac.eci_no}`}>
                    <span class="text-slate-400 inline-block w-8 text-right pr-2">{ac.eci_no}</span>
                    <span>{ac.name}</span>
                    {#if ac.reservation !== "GEN"}
                      <span class="text-xs text-rose-600 ml-1">[{ac.reservation}]</span>
                    {/if}
                  </a>
                </li>
              {/each}
            </ul>
          </div>
        {/each}
      </div>
    </section>
  {/if}
</main>
