<script lang="ts">
  // Compare — Phase 3 surface, two modes:
  //
  //   * scn (default): same state + event, two independent Psephlab scenarios
  //     encoded into URL fragments `?a=…&b=…`. Each side runs the engine,
  //     the middle column shows seat deltas (B − A).
  //   * elec: same state, two events (event_b vs params.event). Until other
  //     event datasets land under datasets/elections/, this empty-states.
  //
  // Scenario encoding is the same base64url JSON as Psephlab's `?s=` —
  // operators paste the trailing `s=…` value into `a=` or `b=` here.

  import { untrack } from "svelte";
  import { loadActuals } from "../lib/psephlab/actuals";
  import { run } from "../lib/psephlab/engine";
  import {
    EMPTY_SCENARIO,
    decodeScenario,
    encodeScenario,
  } from "../lib/psephlab/scenario";
  import type {
    PartyResult,
    RunResult,
    Scenario,
    Tallies,
  } from "../lib/psephlab/types";
  import { colors } from "../lib/colors/store.svelte";
  import ParliamentArc from "../lib/ParliamentArc.svelte";
  import { states } from "../lib/states.svelte";
  import { url } from "../lib/url";

  interface Props { params: { state: string; event: string } }
  let { params }: Props = $props();

  type Mode = "scn" | "elec";

  function fragmentParams(): URLSearchParams {
    return new URLSearchParams(window.location.search);
  }

  const state_code = $derived(states.codeFromSlug(params.state));

  let mode = $state<Mode>(fragmentParams().get("mode") === "elec" ? "elec" : "scn");
  let scenario_a = $state<Scenario>(decodeScenario(fragmentParams().get("a")));
  let scenario_b = $state<Scenario>(decodeScenario(fragmentParams().get("b")));
  // Initialise from URL once. Wrap the prop read in `untrack` so the
  // compiler doesn't flag a transient capture of `params` (the route
  // remounts on `:event` change anyway, so the initial value is correct).
  let event_b = $state<string>(
    fragmentParams().get("eventb") ?? untrack(() => params.event),
  );
  let pasted_a = $state<string>("");
  let pasted_b = $state<string>("");

  // Persist state to URL.
  $effect(() => {
    const p = new URLSearchParams();
    if (mode !== "scn") p.set("mode", mode);
    const a = encodeScenario(scenario_a);
    if (a !== encodeScenario(EMPTY_SCENARIO)) p.set("a", a);
    const b = encodeScenario(scenario_b);
    if (b !== encodeScenario(EMPTY_SCENARIO)) p.set("b", b);
    if (mode === "elec" && event_b !== params.event) p.set("eventb", event_b);
    const q = p.toString();
    const next = window.location.pathname + (q ? "?" + q : "");
    if (window.location.pathname + window.location.search !== next) {
      history.replaceState(null, "", next);
    }
  });

  let actuals_left = $state<Tallies | null>(null);
  let actuals_right = $state<Tallies | null>(null);
  let load_error_right = $state<string | null>(null);

  $effect(() => {
    actuals_left = null;
    const sc = state_code;
    if (!sc) return;
    void loadActuals(params.event, sc).then(t => (actuals_left = t)).catch(() => {});
  });
  $effect(() => {
    actuals_right = null;
    load_error_right = null;
    const sc = state_code;
    if (!sc) return;
    const ev = mode === "elec" ? event_b : params.event;
    void loadActuals(ev, sc)
      .then(t => (actuals_right = t))
      .catch(e => (load_error_right = String(e)));
  });

  const result_left = $derived.by<RunResult | null>(() =>
    actuals_left ? run(actuals_left, mode === "scn" ? scenario_a : EMPTY_SCENARIO) : null,
  );
  const result_right = $derived.by<RunResult | null>(() =>
    actuals_right ? run(actuals_right, mode === "scn" ? scenario_b : EMPTY_SCENARIO) : null,
  );

  // Union of party rows across both sides; sorted by max seats.
  interface DeltaRow {
    code: string;
    short: string;
    left: number;
    right: number;
    delta: number;
  }
  const compared_parties = $derived.by<DeltaRow[]>(() => {
    if (!result_left || !result_right) return [];
    const map = new Map<string, DeltaRow>();
    const upsert = (p: PartyResult, side: "left" | "right"): void => {
      const e = map.get(p.party_eci_code) ?? {
        code: p.party_eci_code,
        short: p.party_short,
        left: 0,
        right: 0,
        delta: 0,
      };
      e[side] = p.seats_won;
      e.short = p.party_short || e.short;
      map.set(p.party_eci_code, e);
    };
    for (const p of result_left.allocation.by_party) upsert(p, "left");
    for (const p of result_right.allocation.by_party) upsert(p, "right");
    const rows = [...map.values()];
    for (const r of rows) r.delta = r.right - r.left;
    return rows
      .filter(r => r.left > 0 || r.right > 0)
      .sort((a, b) => Math.max(b.left, b.right) - Math.max(a.left, a.right));
  });

  // Decode a pasted Psephlab share-URL fragment into a scenario for one side.
  function applyPasted(side: "a" | "b"): void {
    const raw = side === "a" ? pasted_a : pasted_b;
    if (!raw.trim()) return;
    // Accept: full URL, hash fragment, ?s=… or bare base64url.
    let token = raw.trim();
    const eq = token.lastIndexOf("s=");
    if (eq >= 0) token = token.slice(eq + 2);
    const amp = token.indexOf("&");
    if (amp >= 0) token = token.slice(0, amp);
    const next = decodeScenario(token);
    if (side === "a") { scenario_a = next; pasted_a = ""; }
    else { scenario_b = next; pasted_b = ""; }
  }
  function resetSide(side: "a" | "b"): void {
    if (side === "a") scenario_a = EMPTY_SCENARIO;
    else scenario_b = EMPTY_SCENARIO;
  }
  function swapSides(): void {
    const tmp = scenario_a;
    scenario_a = scenario_b;
    scenario_b = tmp;
  }

  let share_state = $state<"idle" | "copied" | "failed">("idle");
  async function copyShareUrl(): Promise<void> {
    try {
      await navigator.clipboard.writeText(window.location.href);
      share_state = "copied";
      setTimeout(() => (share_state = "idle"), 1500);
    } catch {
      share_state = "failed";
    }
  }
</script>

<div class="max-w-screen-2xl mx-auto p-4 md:p-6 space-y-4">
  <header class="space-y-1">
    <p class="text-xs">
      <a class="text-slate-500 hover:underline" href={state_code ? url.state(state_code) : url.home()}>← {states.name(state_code)} overview</a>
    </p>
    <div class="flex items-baseline justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold">Compare — {states.name(state_code)}</h1>
      <div class="flex items-center gap-2 text-xs">
        <div class="inline-flex rounded border border-slate-300 overflow-hidden">
          <button
            class="px-3 py-1"
            class:bg-slate-900={mode === 'scn'} class:text-white={mode === 'scn'}
            onclick={() => (mode = 'scn')}
          >Scenario vs Scenario</button>
          <button
            class="px-3 py-1"
            class:bg-slate-900={mode === 'elec'} class:text-white={mode === 'elec'}
            onclick={() => (mode = 'elec')}
          >Election vs Election</button>
        </div>
        <button
          class="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50"
          onclick={copyShareUrl}
        >{share_state === 'copied' ? '✓ Copied' : share_state === 'failed' ? 'Copy failed' : 'Copy URL'}</button>
      </div>
    </div>
  </header>

  {#if mode === 'scn'}
    <p class="text-xs text-slate-500">
      Both columns work on actuals for <code class="font-mono">{params.event}</code> in {states.name(state_code)}.
      Build each scenario in <a class="text-blue-600 hover:underline" href={state_code ? url.lab(state_code, params.event) : url.home()}>Psephlab</a>, copy its share URL, then paste it into the box below for column A or B.
    </p>

    <div class="grid lg:grid-cols-[1fr_minmax(180px,auto)_1fr] gap-3 items-start">
      <!-- Column A -->
      <section class="bg-white border border-slate-200 rounded p-3 space-y-3">
        <header class="flex items-center justify-between">
          <h2 class="text-sm font-semibold">Scenario A</h2>
          <button class="text-xs text-slate-500 hover:underline" onclick={() => resetSide('a')}>Reset</button>
        </header>
        <div class="flex gap-1">
          <input
            type="text" class="flex-1 rounded border-slate-300 py-1 px-2 text-xs font-mono"
            placeholder="paste Psephlab URL or ?s=…"
            value={pasted_a}
            oninput={(e) => (pasted_a = (e.target as HTMLInputElement).value)}
          />
          <button class="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
            onclick={() => applyPasted('a')}>Load</button>
        </div>
        <div class="text-[10px] text-slate-500">{scenario_a.mutations.length} mutation(s) · rule {scenario_a.rule}</div>
        {#if result_left}
          <ParliamentArc parties={result_left.allocation.by_party} total_seats={result_left.allocation.by_ac.length} />
        {:else}
          <p class="text-xs text-slate-400">Loading…</p>
        {/if}
      </section>

      <!-- Delta column -->
      <section class="bg-white border border-slate-200 rounded p-3 space-y-2">
        <h2 class="text-sm font-semibold text-center">Δ seats (B − A)</h2>
        {#if compared_parties.length === 0}
          <p class="text-xs text-slate-400 text-center">—</p>
        {:else}
          <table class="w-full text-xs tabular-nums">
            <thead class="text-slate-500">
              <tr><th class="text-left font-normal">Party</th><th class="text-right font-normal">A</th><th class="text-right font-normal">B</th><th class="text-right font-normal">Δ</th></tr>
            </thead>
            <tbody>
              {#each compared_parties as r}
                <tr>
                  <td class="py-0.5 flex items-center gap-1.5">
                    <span class="inline-block w-2.5 h-2.5 rounded-sm" style="background:{colors.fill(r.code, r.short)}"></span>
                    <span class="truncate">{r.short}</span>
                  </td>
                  <td class="text-right">{r.left}</td>
                  <td class="text-right">{r.right}</td>
                  <td class="text-right" class:text-emerald-600={r.delta > 0} class:text-rose-600={r.delta < 0}>
                    {r.delta > 0 ? '+' : ''}{r.delta}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>

      <!-- Column B -->
      <section class="bg-white border border-slate-200 rounded p-3 space-y-3">
        <header class="flex items-center justify-between">
          <h2 class="text-sm font-semibold">Scenario B</h2>
          <button class="text-xs text-slate-500 hover:underline" onclick={() => resetSide('b')}>Reset</button>
        </header>
        <div class="flex gap-1">
          <input
            type="text" class="flex-1 rounded border-slate-300 py-1 px-2 text-xs font-mono"
            placeholder="paste Psephlab URL or ?s=…"
            value={pasted_b}
            oninput={(e) => (pasted_b = (e.target as HTMLInputElement).value)}
          />
          <button class="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
            onclick={() => applyPasted('b')}>Load</button>
        </div>
        <div class="text-[10px] text-slate-500">{scenario_b.mutations.length} mutation(s) · rule {scenario_b.rule}</div>
        {#if result_right}
          <ParliamentArc parties={result_right.allocation.by_party} total_seats={result_right.allocation.by_ac.length} />
        {:else}
          <p class="text-xs text-slate-400">Loading…</p>
        {/if}
      </section>
    </div>

    <div class="text-center">
      <button
        class="text-xs rounded border border-slate-300 px-3 py-1 hover:bg-slate-50"
        onclick={swapSides}
      >⇄ Swap A and B</button>
    </div>

  {:else}
    <p class="text-xs text-slate-500">
      Compare actuals across two events for {states.name(state_code)}. Until additional events land under
      <code class="font-mono">datasets/elections/</code>, only <code class="font-mono">{params.event}</code> is loaded.
    </p>

    <label class="text-xs flex items-center gap-2">
      Compare against
      <input
        class="rounded border-slate-300 py-1 px-2 text-xs font-mono w-64"
        value={event_b}
        oninput={(e) => (event_b = (e.target as HTMLInputElement).value)}
        placeholder="e.g. AcGenMay2021"
      />
    </label>

    {#if load_error_right}
      <div class="p-4 bg-amber-50 border border-amber-200 rounded text-amber-900 text-sm">
        No dataset for <code class="font-mono">{event_b}</code> in {states.name(state_code)}. The election-vs-election view will activate as soon as the pipeline emits prior-election artifacts under <code class="font-mono">datasets/elections/{event_b}/{state_code}/</code>.
        <div class="text-xs text-amber-800 mt-1 font-mono break-all">{load_error_right}</div>
      </div>
    {/if}

    <div class="grid lg:grid-cols-[1fr_minmax(180px,auto)_1fr] gap-3 items-start">
      <section class="bg-white border border-slate-200 rounded p-3 space-y-3">
        <h2 class="text-sm font-semibold font-mono">{params.event}</h2>
        {#if result_left}
          <ParliamentArc parties={result_left.allocation.by_party} total_seats={result_left.allocation.by_ac.length} />
        {:else}
          <p class="text-xs text-slate-400">Loading…</p>
        {/if}
      </section>

      <section class="bg-white border border-slate-200 rounded p-3 space-y-2">
        <h2 class="text-sm font-semibold text-center">Δ seats</h2>
        {#if compared_parties.length === 0}
          <p class="text-xs text-slate-400 text-center">—</p>
        {:else}
          <table class="w-full text-xs tabular-nums">
            <thead class="text-slate-500">
              <tr><th class="text-left font-normal">Party</th><th class="text-right font-normal" title={params.event}>A</th><th class="text-right font-normal" title={event_b}>B</th><th class="text-right font-normal">Δ</th></tr>
            </thead>
            <tbody>
              {#each compared_parties as r}
                <tr>
                  <td class="py-0.5 flex items-center gap-1.5">
                    <span class="inline-block w-2.5 h-2.5 rounded-sm" style="background:{colors.fill(r.code, r.short)}"></span>
                    <span class="truncate">{r.short}</span>
                  </td>
                  <td class="text-right">{r.left}</td>
                  <td class="text-right">{r.right}</td>
                  <td class="text-right" class:text-emerald-600={r.delta > 0} class:text-rose-600={r.delta < 0}>
                    {r.delta > 0 ? '+' : ''}{r.delta}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>

      <section class="bg-white border border-slate-200 rounded p-3 space-y-3">
        <h2 class="text-sm font-semibold font-mono">{event_b}</h2>
        {#if load_error_right}
          <p class="text-xs text-slate-400">No data.</p>
        {:else if result_right}
          <ParliamentArc parties={result_right.allocation.by_party} total_seats={result_right.allocation.by_ac.length} />
        {:else}
          <p class="text-xs text-slate-400">Loading…</p>
        {/if}
      </section>
    </div>
  {/if}
</div>
