<script lang="ts">
  import type { Database, QueryExecResult } from "sql.js";
  import { getDb } from "../lib/sql";
  import { states } from "../lib/states.svelte";
  import { url } from "../lib/url";
  import {
    ALL_PRESETS,
    PRESET_GROUPS,
    findPreset,
    type Preset,
  } from "../lib/explore/presets";
  import { validateSql } from "../lib/explore/sqlGuard";
  import { fmtCell, isNumericCol } from "../lib/explore/format";
  import {
    fetchElectionEvents,
    defaultEventForState,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";

  // Component responsibility: load the per-state SQLite, hold UI state
  // (selected preset, editor content, last result), and render.
  //
  // Everything else lives in `lib/explore/`:
  //   - presets.ts   — the preset/group catalog (pure data).
  //   - sqlGuard.ts  — the read-only / single-statement validator.
  //   - format.ts    — column-name based cell formatting helpers.

  interface Props { params: { state: string } }
  let { params }: Props = $props();

  // Per-state event resolution (ADR-0023): the per-state SQLite (and the
  // SQL preset queries that read it) are scoped to the state's default
  // election. States with no election data render a graceful empty state.
  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  const state_code = $derived(states.codeFromSlug(params.state));
  const event = $derived(
    defaultEventForState(election_catalogue, state_code)?.event_id ?? null,
  );

  let db = $state<Database | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let selectedId = $state<string>(ALL_PRESETS[0].id);
  let sql = $state(ALL_PRESETS[0].sql);
  let result = $state<QueryExecResult | null>(null);
  let runError = $state<string | null>(null);
  let runtimeMs = $state<number | null>(null);

  $effect(() => {
    loading = true;
    error = null;
    db = null;
    const sc = state_code;
    const ev = event;
    if (!sc || !ev) { loading = false; return; }
    getDb(ev, sc)
      .then(d => { db = d; })
      .catch(e => { error = String(e); })
      .finally(() => { loading = false; });
  });

  function run(): void {
    if (!db) return;
    runError = null;
    const guard = validateSql(sql);
    if (!guard.ok) {
      result = null;
      runtimeMs = null;
      runError = guard.reason;
      return;
    }
    const t0 = performance.now();
    try {
      const out = db.exec(sql);
      result = out.length > 0 ? out[0] : null;
      runtimeMs = performance.now() - t0;
    } catch (e) {
      result = null;
      runtimeMs = null;
      runError = String(e);
    }
  }

  function pick(p: Preset): void {
    selectedId = p.id;
    sql = p.sql;
    run();
  }

  $effect(() => {
    if (db) run();
  });

  // Tailwind class helpers depend on the column name; keep them inline since
  // they're presentation-only and can't move out cleanly without dragging
  // class-string assumptions with them.
  function cellClass(col: string): string {
    return isNumericCol(col)
      ? "py-2 pr-4 align-top tabular-nums text-right whitespace-nowrap"
      : "py-2 pr-4 align-top whitespace-nowrap";
  }
  function headClass(col: string): string {
    return isNumericCol(col)
      ? "py-2 pr-4 text-right font-medium text-slate-600"
      : "py-2 pr-4 text-left font-medium text-slate-600";
  }

  const selectedPreset = $derived(findPreset(selectedId) ?? null);
</script>

<main class="max-w-screen-2xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs">
      <a class="text-slate-500 hover:underline"
         href={state_code ? url.state(state_code) : url.home()}>
        ← {states.name(state_code)} overview
      </a>
    </p>
    <div class="flex items-baseline justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold tracking-tight">
        Data explorer <span class="text-slate-400 font-normal">— {states.name(state_code)}</span>
      </h1>
      <p class="text-xs text-slate-500">
        Ad-hoc queries against this state's results for
        <code class="font-mono">{event}</code>.
      </p>
    </div>
  </header>

  {#if loading}
    <div class="text-slate-500">Loading data…</div>
  {:else if error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load: <code>{error}</code>
    </div>
  {:else}
    <!-- Preset chooser, grouped by persona-driven question. -->
    <section class="rounded-xl border border-slate-200 bg-white/80 backdrop-blur shadow-sm p-5 space-y-5">
      {#each PRESET_GROUPS as g}
        <div class="space-y-2">
          <div class="flex items-baseline gap-3 border-b border-slate-100 pb-1">
            <h2 class="text-sm font-semibold text-slate-800 uppercase tracking-wide">{g.title}</h2>
            <p class="text-xs text-slate-500">{g.subtitle}</p>
          </div>
          <div class="flex flex-wrap gap-2 pt-1">
            {#each g.presets as p}
              {@const active = p.id === selectedId}
              <button
                type="button"
                onclick={() => pick(p)}
                title={p.blurb}
                class={"tricolor-pill" + (active ? " is-active" : "")}
                aria-pressed={active}>
                {p.label}
              </button>
            {/each}
          </div>
        </div>
      {/each}
    </section>

    <!-- SQL editor + run. -->
    <section class="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
      {#if selectedPreset}
        <div class="flex items-baseline justify-between gap-3 flex-wrap">
          <div>
            <div class="text-xs uppercase tracking-wide text-emerald-800 font-semibold">Selected query</div>
            <div class="font-medium text-slate-800">{selectedPreset.label}</div>
          </div>
          <p class="text-xs text-slate-500 max-w-prose">{selectedPreset.blurb}</p>
        </div>
      {/if}
      <textarea
        bind:value={sql}
        class="w-full h-40 font-mono text-[12.5px] leading-relaxed p-3 bg-slate-50 border border-slate-300 rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-amber-300 focus:border-amber-400"
        spellcheck="false"
      ></textarea>
      <div class="flex items-center gap-3 flex-wrap">
        <button
          type="button"
          onclick={run}
          class="run-btn">
          Run query
        </button>
        {#if runtimeMs !== null && !runError}
          <span class="text-xs text-slate-500">
            {result?.values.length ?? 0} row{(result?.values.length ?? 0) === 1 ? "" : "s"}
            · {runtimeMs.toFixed(1)} ms
          </span>
        {/if}
      </div>
    </section>

    <!-- Results. -->
    {#if runError}
      <div class="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 text-sm font-mono">
        {runError}
      </div>
    {:else if result && result.values.length > 0}
      <section class="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div class="overflow-auto max-h-[70vh]">
          <table class="text-sm w-full">
            <thead class="bg-slate-50 text-xs uppercase tracking-wide sticky top-0 z-10 border-b border-slate-200">
              <tr>
                {#each result.columns as col}
                  <th class={headClass(col)}>{col}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each result.values as row, i}
                <tr class={i % 2 === 0 ? "bg-white" : "bg-slate-50/60"}>
                  {#each row as cell, j}
                    <td class={cellClass(result.columns[j])}>
                      {fmtCell(cell, result.columns[j])}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {:else if result}
      <div class="text-slate-500 text-sm italic">Query returned no rows.</div>
    {/if}

    <p class="text-xs text-slate-400 leading-relaxed">
      Schema: <code>parties</code>(eci_code, short_name, full_name),
      <code>constituencies</code>(ac_eci_no, name, votes_polled),
      <code>candidates</code>(ac_eci_no, rank, name, party_eci_code, party_short, votes, vote_share_pct, is_winner, is_nota);
      view <code>party_totals</code>(party_short, seats_won, votes).
      Only <code>SELECT</code> / <code>WITH</code> queries are supported.
    </p>
  {/if}
</main>

<style>
  /*
   * Tricolor pill treatment.
   *
   * The selection / hover affordance uses the same flag palette that the
   * brand wordmark in LeftRail uses (saffron #FF9933, white, India green
   * #138808, sky blue) — a quiet visual tie between the chrome and this
   * control surface.
   *
   * Implementation: a conic-gradient ring is painted into a pseudo-element
   * one pixel outside the pill, then masked so only a 1px hairline shows.
   * The rotation angle is registered as a typed CSS custom property so it
   * can be animated smoothly — without @property, conic-gradient angle
   * changes are not interpolatable.
   *
   * - Idle:    ring opacity 0 (clean slate-300 border, calm in long rows).
   * - Hover:   ring fades in and revolves; pill fill warms to faint saffron.
   * - Active:  ring fully visible but static (the chosen item is settled).
   *            Fill saffron-tinted, text deep green, weight semibold.
   *
   * Reduced-motion users get the static ring on hover instead of revolution.
   */
  @property --pill-angle {
    syntax: "<angle>";
    initial-value: 0deg;
    inherits: false;
  }

  .tricolor-pill {
    position: relative;
    padding: 0.375rem 0.875rem;
    font-size: 0.75rem;
    line-height: 1rem;
    color: rgb(51 65 85);              /* slate-700 */
    background: white;
    border: 1px solid rgb(203 213 225); /* slate-300 */
    border-radius: 9999px;
    cursor: pointer;
    transition: color .15s ease, background-color .15s ease, border-color .15s ease;
    isolation: isolate;
  }

  .tricolor-pill::before {
    content: "";
    position: absolute;
    inset: -1px;
    border-radius: 9999px;
    padding: 1px;                       /* hairline ring */
    background: conic-gradient(
      from var(--pill-angle),
      #FF9933 0deg,
      #ffffff 90deg,
      #138808 180deg,
      #38bdf8 270deg,                   /* sky-400 */
      #FF9933 360deg
    );
    -webkit-mask:
      linear-gradient(#000 0 0) content-box,
      linear-gradient(#000 0 0);
            mask:
      linear-gradient(#000 0 0) content-box,
      linear-gradient(#000 0 0);
    -webkit-mask-composite: xor;
            mask-composite: exclude;
    opacity: 0;
    transition: opacity .2s ease;
    pointer-events: none;
    z-index: -1;
  }

  .tricolor-pill:hover {
    background: #FFF7ED;
    border-color: transparent;
    color: rgb(15 23 42);
  }
  .tricolor-pill:hover::before {
    opacity: 1;
    animation: pill-spin 3s linear infinite;
  }

  .tricolor-pill:focus-visible { outline: none; }
  .tricolor-pill:focus-visible::before { opacity: 1; }

  .tricolor-pill.is-active {
    background: #FFF7ED;
    border-color: transparent;
    color: #14532d;
    font-weight: 600;
  }
  .tricolor-pill.is-active::before {
    opacity: 1;
    animation: none;
  }

  @keyframes pill-spin { to { --pill-angle: 360deg; } }

  @media (prefers-reduced-motion: reduce) {
    .tricolor-pill:hover::before { animation: none; }
  }

  /*
   * Run button — soft teal vertical gradient with a hairline highlight on top.
   * Reads as "primary action" without shouting; pairs with the cool quadrant
   * of the pill ring so the page has one consistent cool-accent direction.
   */
  .run-btn {
    padding: 0.5rem 1.1rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: white;
    background-image: linear-gradient(180deg, #14b8a6 0%, #0d9488 55%, #0f766e 100%);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.25),
      0 1px 2px rgba(15, 118, 110, 0.25);
    border-radius: 0.5rem;
    transition: filter .15s ease, transform .05s ease, box-shadow .15s ease;
    cursor: pointer;
    border: none;
  }
  .run-btn:hover {
    filter: brightness(1.05) saturate(1.05);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.3),
      0 2px 6px rgba(15, 118, 110, 0.3);
  }
  .run-btn:active { transform: translateY(1px); filter: brightness(0.96); }
  .run-btn:focus-visible {
    outline: 2px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
