<script lang="ts">
  import {
    type CandidateBio,
    type ConstituencyResult,
  } from "../lib/data";
  import { loadConstituencyResult } from "../lib/view-models/constituency";
  import { loadStateAcWinners, type AcWinner } from "../lib/view-models/state-overview";
  import type { LoaderResult } from "../lib/loader-result";
  import {
    fetchElectionEvents,
    defaultEventForState,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";
  import AcStackedBar from "../lib/AcStackedBar.svelte";
  import StateAcMap from "../lib/maplibre/StateAcMap.svelte";
  import { STATE_AC } from "../lib/maplibre/sources";
  import { states } from "../lib/states.svelte";
  import { url } from "../lib/url";

  // params.state is a slug; params.eci_no is the parsed AC number from
  // the AC slug (e.g. `167-mylapore` → 167). When the prefix is missing
  // or unparseable, eci_no is -1 and we render the not-published path.
  interface Props { params: { state: string; eci_no: number; ac_slug: string } }
  let { params }: Props = $props();

  // Per-state event resolution (ADR-0023): no global "current election".
  // The state's default event from datasets/reference/in/election-events.json
  // names the artifact directory we read from.
  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  const state_code = $derived(states.codeFromSlug(params.state));
  const event_row = $derived(defaultEventForState(election_catalogue, state_code));
  const event = $derived(event_row?.event_id ?? null);

  // PR-E (Phase 1.3a): the canonical view-model loader fronts DuckDB-WASM.
  // The result is a discriminated union — render all four arms.
  let loaderResult = $state<LoaderResult<ConstituencyResult>>({ status: "loading" });
  const result = $derived(
    loaderResult.status === "ok" || loaderResult.status === "partial"
      ? loaderResult.data
      : null,
  );
  const not_published = $derived(
    loaderResult.status === "partial" && loaderResult.reason === "not_published",
  );

  // Biographic columns (sex/age/education/profession/constituency_type/
  // party_type) now ride on `result.candidates[i].bio` directly from
  // dim_candidates.parquet v1.2 (PR-S.2 / canonical pivot 1.8f). No more
  // per-candidate JSON fan-out; one DuckDB query already projected them.

  // State-map context for the "Location in {state}" panel. Lean loader —
  // pulls only ac_winners[] (no party totals / state scope / sources), so
  // the constituency page doesn't pay for queries it never renders.
  // `null` = still loading; `[]` = loaded with no rows (not_published).
  let ac_winners = $state<AcWinner[] | null>(null);

  $effect(() => {
    loaderResult = { status: "loading" };
    ac_winners = null;
    const sc = state_code;
    const ev = event;
    if (!sc || !ev || params.eci_no <= 0) return;
    loadConstituencyResult(ev, sc, params.eci_no).then(r => (loaderResult = r));
    loadStateAcWinners(ev, sc).then(r => {
      ac_winners = r.status === "ok" || r.status === "partial" ? r.data : [];
    });
  });

  async function retryLoad() {
    const sc = state_code;
    const ev = event;
    if (!sc || !ev || params.eci_no <= 0) return;
    loaderResult = { status: "loading" };
    loaderResult = await loadConstituencyResult(ev, sc, params.eci_no);
  }

  function fmtBiographic(bio: CandidateBio | null | undefined): string {
    if (!bio) return "";
    const parts: string[] = [];
    if (bio.sex) parts.push(bio.sex);
    if (bio.age) parts.push(`age ${bio.age}`);
    if (bio.education) parts.push(bio.education);
    if (bio.profession) parts.push(bio.profession);
    return parts.join(" · ");
  }

  function pct(n: number): string { return n.toFixed(2) + "%"; }
</script>

<main class="max-w-4xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={state_code ? url.state(state_code) : url.home()}>← {states.name(state_code)} overview</a></p>
    <h1 class="text-2xl font-bold">
      {#if result}{result.constituency_name ?? `AC ${result.eci_no}`}{:else}AC {params.eci_no}{/if}
    </h1>
    <p class="text-sm text-slate-500">
      {states.name(state_code)} · constituency #{params.eci_no}
    </p>
  </header>

  {#if loaderResult.status === "failed"}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900 space-y-2">
      <p>{loaderResult.reason}</p>
      {#if loaderResult.retry}
        <button
          type="button"
          class="text-sm font-semibold underline hover:no-underline"
          onclick={retryLoad}
        >Retry</button>
      {/if}
    </div>
  {:else if not_published}
    <div class="p-5 bg-amber-50 border border-amber-200 rounded space-y-2">
      <h2 class="text-sm font-semibold uppercase text-amber-900">No result published</h2>
      <p class="text-sm text-amber-900">
        The Election Commission has not published a result for AC #{params.eci_no} in {states.name(state_code)}.
        This typically means the constituency was <strong>countermanded</strong> or <strong>postponed</strong>
        — for example, if a contesting candidate died before polling, or polling was deferred.
      </p>
      <p class="text-xs text-amber-800">
        The backend's Section 10 parser deliberately skips these stubs (see
        <code class="font-mono">docs/architecture/backend/sources-eci.md</code>) rather than emit a misleading
        zero-vote record.
      </p>
    </div>
  {:else if !result}
    <div class="text-slate-500">Loading…</div>
  {:else}
    <section class="bg-white rounded-lg shadow-sm p-5 grid sm:grid-cols-3 gap-4 text-sm">
      <div>
        <div class="text-xs uppercase text-slate-500">Winner</div>
        <div class="font-semibold">{result.winner.name}</div>
        <div class="text-slate-500">{result.winner.party_short}</div>
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Margin</div>
        <div class="font-semibold">{result.winner.margin_votes.toLocaleString()}</div>
        <div class="text-slate-500">{pct(result.winner.margin_pct)}</div>
      </div>
      <div>
        <div class="text-xs uppercase text-slate-500">Turnout</div>
        <div class="font-semibold">{result.totals.turnout_pct?.toFixed(2) ?? "—"}%</div>
        <div class="text-slate-500">{result.totals.votes_polled.toLocaleString()} polled</div>
      </div>
    </section>

    {#if event && state_code && STATE_AC[state_code]}
      <section class="bg-white rounded-lg shadow-sm p-4">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Location in {states.name(state_code)}</h2>
        <StateAcMap state={state_code} rows={ac_winners} highlight_eci_no={params.eci_no} height="360px" />
        <p class="text-xs text-slate-400 mt-2">
          Highlighted: AC #{params.eci_no}. Other constituencies are dimmed for context. Click any to drill in.
        </p>
      </section>
    {/if}

    <section class="bg-white rounded-lg shadow-sm p-5">
      <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Vote share</h2>
      <AcStackedBar {result} />
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">
        {#if result.candidates_total && result.candidates_total > result.top_n_cutoff}
          Top {result.top_n_cutoff} of {result.candidates_total} candidates
        {:else}
          {result.top_n_cutoff} candidate{result.top_n_cutoff === 1 ? "" : "s"}
        {/if}
      </h2>
      <table class="w-full text-sm">
        <thead class="text-left text-xs text-slate-500 uppercase">
          <tr><th class="py-2 w-10">#</th><th>Candidate</th><th>Party</th><th class="text-right">Votes</th><th class="text-right">Share</th></tr>
        </thead>
        <tbody class="divide-y">
          {#each result.candidates as c}
            {@const bio = fmtBiographic(c.bio)}
            <tr class={c.is_winner ? "bg-emerald-50" : ""}>
              <td class="py-2 text-slate-400 align-top">{c.rank}</td>
              <td class="font-medium align-top">
                <div>{c.name}</div>
                {#if c.bio}
                  <div class="text-xs text-slate-500 mt-0.5" data-testid="candidate-biographics">
                    {#if bio}{bio}{:else}Not declared{/if}
                  </div>
                {/if}
              </td>
              <td class="align-top">
                {#if c.party_eci_code && state_code}
                  <a class="hover:underline" href={url.party(state_code, c.party_eci_code, c.party_short)}>{c.party_short}</a>
                {:else}{c.party_short}{/if}
              </td>
              <td class="text-right tabular-nums align-top">{c.votes.toLocaleString()}</td>
              <td class="text-right tabular-nums align-top">{pct(c.vote_share_pct)}</td>
            </tr>
          {/each}
          <tr class="text-slate-500">
            <td></td><td>NOTA</td><td></td>
            <td class="text-right tabular-nums">{result.nota.votes.toLocaleString()}</td>
            <td class="text-right tabular-nums">{pct(result.nota.vote_share_pct)}</td>
          </tr>
          {#if result.others}
            <tr class="text-slate-500">
              <td></td><td>Others ({result.others.candidate_count})</td><td></td>
              <td class="text-right tabular-nums">{result.others.votes.toLocaleString()}</td>
              <td class="text-right tabular-nums">{pct(result.others.vote_share_pct)}</td>
            </tr>
          {/if}
        </tbody>
      </table>
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5 text-xs text-slate-500">
      Sources:
      <ul class="mt-1 space-y-1">
        {#each result.sources as s}
          <li><a class="font-mono hover:underline break-all" href={s.url} target="_blank" rel="noreferrer">{s.url}</a></li>
        {/each}
      </ul>
    </section>
  {/if}
</main>
