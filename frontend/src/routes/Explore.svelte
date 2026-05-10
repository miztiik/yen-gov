<script lang="ts">
  import type { Database, QueryExecResult } from "sql.js";
  import { getDb } from "../lib/sql";
  import { states } from "../lib/states.svelte";

  interface Props { params: { state: string } }
  let { params }: Props = $props();

  const event = "AcGenMay2026";

  const PRESETS: { label: string; sql: string }[] = [
    { label: "Party totals (winners)", sql: "SELECT party_short, seats_won, votes FROM party_totals ORDER BY seats_won DESC, votes DESC;" },
    { label: "Top 10 winning margins", sql: "SELECT c.ac_eci_no, c.name, w.name AS winner, w.party_short, w.votes - r2.votes AS margin\nFROM constituencies c\nJOIN candidates w ON w.ac_eci_no = c.ac_eci_no AND w.is_winner = 1\nJOIN candidates r2 ON r2.ac_eci_no = c.ac_eci_no AND r2.rank = 2\nORDER BY margin DESC LIMIT 10;" },
    { label: "Closest 10 contests", sql: "SELECT c.ac_eci_no, c.name, w.party_short AS winner, r2.party_short AS runner_up, w.votes - r2.votes AS margin\nFROM constituencies c\nJOIN candidates w ON w.ac_eci_no = c.ac_eci_no AND w.is_winner = 1\nJOIN candidates r2 ON r2.ac_eci_no = c.ac_eci_no AND r2.rank = 2\nORDER BY margin ASC LIMIT 10;" },
    { label: "Candidates per constituency (avg/min/max)", sql: "SELECT AVG(n) AS avg, MIN(n) AS min, MAX(n) AS max FROM (SELECT ac_eci_no, COUNT(*) AS n FROM candidates WHERE is_nota = 0 GROUP BY ac_eci_no);" },
    { label: "NOTA share by constituency (top 10)", sql: "SELECT c.ac_eci_no, c.name, n.vote_share_pct AS nota_pct, n.votes AS nota_votes\nFROM constituencies c\nJOIN candidates n ON n.ac_eci_no = c.ac_eci_no AND n.is_nota = 1\nORDER BY n.vote_share_pct DESC LIMIT 10;" },
  ];

  let db = $state<Database | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let sql = $state(PRESETS[0].sql);
  let result = $state<QueryExecResult | null>(null);
  let runError = $state<string | null>(null);

  $effect(() => {
    loading = true;
    error = null;
    db = null;
    const sc = params.state;
    getDb(event, sc)
      .then(d => { db = d; })
      .catch(e => { error = String(e); })
      .finally(() => { loading = false; });
  });

  function run(): void {
    if (!db) return;
    runError = null;
    try {
      const out = db.exec(sql);
      result = out.length > 0 ? out[0] : null;
    } catch (e) {
      result = null;
      runError = String(e);
    }
  }

  function pick(preset: string): void {
    sql = preset;
    run();
  }

  $effect(() => {
    if (db) run();
  });
</script>

<main class="max-w-screen-2xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={`#/s/${params.state}`}>← {states.name(params.state)} overview</a></p>
    <h1 class="text-2xl font-bold">Explore — {states.name(params.state)}</h1>
    <p class="text-sm text-slate-500">
      Ad-hoc SQL against <code class="font-mono">results.sqlite</code> for event <code>{event}</code>. Runs in your browser via sql.js.
    </p>
  </header>

  {#if loading}
    <div class="text-slate-500">Loading SQLite database…</div>
  {:else if error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load: <code>{error}</code>
    </div>
  {:else}
    <section class="bg-white rounded-lg shadow-sm p-5 space-y-3">
      <div class="flex flex-wrap gap-2">
        {#each PRESETS as p}
          <button class="px-3 py-1 text-xs rounded border border-slate-300 hover:bg-slate-50"
                  onclick={() => pick(p.sql)}>{p.label}</button>
        {/each}
      </div>
      <textarea
        bind:value={sql}
        class="w-full h-32 font-mono text-sm p-3 border border-slate-300 rounded resize-y"
        spellcheck="false"
      ></textarea>
      <div class="flex gap-2">
        <button onclick={run}
                class="px-4 py-2 text-sm bg-slate-900 text-white rounded hover:bg-slate-700">
          Run
        </button>
        <span class="text-xs text-slate-400 self-center">⌘/Ctrl+Enter not bound — click Run.</span>
      </div>
    </section>

    {#if runError}
      <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900 text-sm">
        <code>{runError}</code>
      </div>
    {:else if result}
      <section class="bg-white rounded-lg shadow-sm p-5 overflow-auto">
        <div class="text-xs text-slate-500 mb-2">{result.values.length} row{result.values.length === 1 ? "" : "s"}</div>
        <table class="text-sm w-full">
          <thead class="text-left text-xs text-slate-500 uppercase">
            <tr>
              {#each result.columns as col}<th class="py-1 pr-4">{col}</th>{/each}
            </tr>
          </thead>
          <tbody class="divide-y">
            {#each result.values as row}
              <tr>
                {#each row as cell}
                  <td class="py-1 pr-4 align-top tabular-nums">
                    {cell === null ? "—" : String(cell)}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {:else}
      <div class="text-slate-500 text-sm">Query returned no rows.</div>
    {/if}

    <p class="text-xs text-slate-400">
      Schema: <code>parties</code>(eci_code, short_name, full_name), <code>constituencies</code>(eci_no, name, votes_polled), <code>candidates</code>(constituency_eci_no, rank, name, party_eci_code, party_short, votes, vote_share_pct, is_winner, is_nota); view <code>party_totals</code>(party_short, seats_won, votes). See docs/architecture/backend/emit-sqlite.md.
    </p>
  {/if}
</main>
