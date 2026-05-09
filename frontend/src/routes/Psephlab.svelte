<script lang="ts">
  // Psephlab v1 — what-if simulator.
  //
  // Loads actuals (Tallies) for the (event, state) and runs the engine on
  // every scenario change. Scenario lives in the URL fragment query
  // (`?s=...`); changes are flushed back via history.replaceState so the
  // back button doesn't accumulate one entry per slider tick.

  import { loadActuals } from "../lib/psephlab/actuals";
  import { run } from "../lib/psephlab/engine";
  import { MUTATIONS, mutationById } from "../lib/psephlab/mutations";
  import { RULES } from "../lib/psephlab/rules";
  import {
    EMPTY_SCENARIO,
    decodeScenario,
    writeScenarioToHash,
  } from "../lib/psephlab/scenario";
  import type {
    MutationConfig,
    PartyResult,
    PerAcSwingConfig,
    PartyBagConfig,
    Scenario,
    StatewideSwingConfig,
    Tallies,
    ThresholdDropConfig,
  } from "../lib/psephlab/types";
  import { colors } from "../lib/colors/store.svelte";
  import ParliamentArc from "../lib/ParliamentArc.svelte";
  import SwingSankey from "../lib/SwingSankey.svelte";

  interface Props { params: { state: string; event: string } }
  let { params }: Props = $props();

  const event = $derived(params.event);
  const state_code = $derived(params.state);

  let actuals = $state<Tallies | null>(null);
  let actuals_error = $state<string | null>(null);

  // Initial scenario from URL (read once, then we own the mutable state).
  let scenario = $state<Scenario>(initialScenario());

  function initialScenario(): Scenario {
    const h = window.location.hash;
    const i = h.indexOf("?");
    if (i < 0) return EMPTY_SCENARIO;
    return decodeScenario(new URLSearchParams(h.slice(i + 1)).get("s"));
  }

  $effect(() => {
    actuals = null;
    actuals_error = null;
    const ev = event, st = state_code;
    loadActuals(ev, st)
      .then(t => (actuals = t))
      .catch(e => (actuals_error = String(e)));
  });

  // Persist scenario → URL on every change. The path prefix mirrors the
  // current route so deep links work; history.replaceState avoids back-stack
  // pollution.
  $effect(() => {
    void scenario;
    writeScenarioToHash(`/lab/${state_code}/${event}`, scenario);
  });

  // Engine run. Pure & synchronous; for TN-scale (234 ACs) takes <5ms.
  // $derived recomputes on any scenario or actuals change.
  const result = $derived.by(() => {
    if (!actuals) return null;
    return run(actuals, scenario);
  });

  // Distinct parties pulled from actuals — populates the swap dropdowns.
  const party_choices = $derived.by(() => {
    if (!actuals) return [];
    const seen = new Map<string, string>();
    for (const ac of actuals.acs) {
      for (const c of ac.candidates) {
        if (!seen.has(c.party_eci_code)) seen.set(c.party_eci_code, c.party_short);
      }
    }
    return [...seen.entries()]
      .map(([code, short]) => ({ code, short }))
      .sort((a, b) => a.short.localeCompare(b.short));
  });

  // Top parties by seats (excludes long tail) for compact charts.
  const ranked_parties = $derived.by(() => {
    if (!result) return { mut: [], act: [] };
    const top = (rs: PartyResult[]) => rs.filter(p => p.seats_won > 0).slice(0, 12);
    return { mut: top(result.allocation.by_party), act: top(result.actuals_allocation.by_party) };
  });

  const total_seats = $derived(actuals?.acs.length ?? 0);
  const majority = $derived(Math.ceil(total_seats / 2));

  // ----- Mutation stack management -----

  function addMutation(id: string): void {
    const plug = mutationById(id);
    if (!plug || !actuals) return;
    scenario = { ...scenario, mutations: [...scenario.mutations, plug.defaultConfig(actuals)] };
  }

  function removeMutation(idx: number): void {
    scenario = { ...scenario, mutations: scenario.mutations.filter((_, i) => i !== idx) };
  }

  function updateMutation(idx: number, patch: Partial<MutationConfig>): void {
    scenario = {
      ...scenario,
      mutations: scenario.mutations.map((m, i) =>
        i === idx ? ({ ...m, ...patch } as MutationConfig) : m,
      ),
    };
  }

  function moveMutation(idx: number, dir: -1 | 1): void {
    const target = idx + dir;
    if (target < 0 || target >= scenario.mutations.length) return;
    const next = scenario.mutations.slice();
    [next[idx], next[target]] = [next[target], next[idx]];
    scenario = { ...scenario, mutations: next };
  }

  function resetScenario(): void {
    scenario = EMPTY_SCENARIO;
  }

  async function copyShareUrl(): Promise<void> {
    try {
      await navigator.clipboard.writeText(window.location.href);
      share_state = "copied";
      setTimeout(() => (share_state = "idle"), 1500);
    } catch {
      share_state = "failed";
    }
  }
  let share_state = $state<"idle" | "copied" | "failed">("idle");

  // ----- Diff tagging for the result table -----

  function deltaFor(code: string): number {
    if (!result) return 0;
    const a = result.actuals_allocation.by_party.find(p => p.party_eci_code === code);
    const m = result.allocation.by_party.find(p => p.party_eci_code === code);
    return (m?.seats_won ?? 0) - (a?.seats_won ?? 0);
  }

  function partyLabel(code: string): string {
    return party_choices.find(p => p.code === code)?.short ?? code;
  }
</script>

<div class="max-w-6xl mx-auto p-4 md:p-6 space-y-4">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={`#/s/${state_code}`}>← {state_code} overview</a></p>
    <div class="flex items-baseline justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold">Psephlab — {state_code}</h1>
      <p class="text-xs text-slate-500">
        Counting rule: <code class="font-mono">{scenario.rule}</code> · {scenario.mutations.length} mutation(s)
      </p>
    </div>
  </header>

  {#if actuals_error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load actuals: <code>{actuals_error}</code>
    </div>
  {:else if !actuals || !result}
    <div class="text-slate-500 p-8 text-center">Loading actuals…</div>
  {:else}
    <div class="grid lg:grid-cols-[360px_1fr] gap-4 items-start">
      <!-- ============== Mutation panel ============== -->
      <section class="bg-white rounded-lg shadow-sm p-4 space-y-3 lg:sticky lg:top-4">
        <div class="flex items-center justify-between gap-2">
          <h2 class="text-sm font-semibold uppercase text-slate-500">Mutations</h2>
          <select
            class="text-xs rounded border-slate-300 py-1 px-2"
            value=""
            onchange={(e) => {
              const v = (e.target as HTMLSelectElement).value;
              if (v) { addMutation(v); (e.target as HTMLSelectElement).value = ""; }
            }}
          >
            <option value="">+ Add mutation…</option>
            {#each MUTATIONS as m}
              <option value={m.id}>{m.label}</option>
            {/each}
          </select>
        </div>

        {#if scenario.mutations.length === 0}
          <p class="text-xs text-slate-500 italic">
            No mutations. The result mirrors the actuals; add one above to start exploring.
          </p>
        {/if}

        <ul class="space-y-3">
          {#each scenario.mutations as cfg, i (i + ':' + cfg.id)}
            <li class="border border-slate-200 rounded p-2 space-y-2 bg-slate-50/50">
              <div class="flex items-center justify-between gap-1 text-xs">
                <span class="font-medium text-slate-700">
                  {i + 1}. {mutationById(cfg.id)?.label ?? cfg.id}
                </span>
                <span class="flex items-center gap-1">
                  <button
                    class="px-1 hover:bg-slate-200 rounded disabled:opacity-30"
                    disabled={i === 0}
                    title="Move up"
                    onclick={() => moveMutation(i, -1)}>↑</button>
                  <button
                    class="px-1 hover:bg-slate-200 rounded disabled:opacity-30"
                    disabled={i === scenario.mutations.length - 1}
                    title="Move down"
                    onclick={() => moveMutation(i, 1)}>↓</button>
                  <button
                    class="px-1 hover:bg-rose-100 rounded text-rose-700"
                    title="Remove"
                    onclick={() => removeMutation(i)}>✕</button>
                </span>
              </div>

              {#if cfg.id === 'perAcSwing'}
                {@const c = cfg as PerAcSwingConfig}
                {@const ac = actuals.acs.find(a => a.eci_no === c.eci_no)}
                <label class="block text-xs">
                  AC
                  <select
                    class="mt-0.5 w-full rounded border-slate-300 py-1 px-2 text-xs"
                    value={String(c.eci_no)}
                    onchange={(e) => updateMutation(i, { eci_no: Number((e.target as HTMLSelectElement).value) })}
                  >
                    {#each actuals.acs as a}
                      <option value={String(a.eci_no)}>{a.eci_no}. {a.name}</option>
                    {/each}
                  </select>
                </label>
                <div class="space-y-1 text-xs">
                  <div class="text-slate-600">From <span class="text-slate-400">(check one or many)</span></div>
                  <div class="max-h-28 overflow-y-auto pr-1 border border-slate-200 rounded p-1 bg-white">
                    {#each ac?.candidates ?? [] as cand}
                      <label class="flex items-center gap-2 py-0.5">
                        <input
                          type="checkbox"
                          checked={c.from_party_eci_codes.includes(cand.party_eci_code)}
                          onchange={(e) => {
                            const on = (e.target as HTMLInputElement).checked;
                            const next = on
                              ? [...c.from_party_eci_codes, cand.party_eci_code]
                              : c.from_party_eci_codes.filter(x => x !== cand.party_eci_code);
                            updateMutation(i, { from_party_eci_codes: next });
                          }}
                        />
                        <span class="flex-1 truncate">{cand.party_short}</span>
                        <span class="font-mono text-[10px] text-slate-500 tabular-nums">{cand.votes.toLocaleString()}</span>
                      </label>
                    {/each}
                  </div>
                </div>
                <label class="block text-xs">To
                  <select
                    class="mt-0.5 w-full rounded border-slate-300 py-1 px-2 text-xs"
                    value={c.to_party_eci_code}
                    onchange={(e) => updateMutation(i, { to_party_eci_code: (e.target as HTMLSelectElement).value })}
                  >
                    {#each ac?.candidates ?? [] as cand}
                      <option value={cand.party_eci_code}>{cand.party_short}</option>
                    {/each}
                  </select>
                </label>
                {@const pool = (ac?.candidates ?? [])
                  .filter(x => c.from_party_eci_codes.includes(x.party_eci_code))
                  .reduce((s, x) => s + x.votes, 0)}
                <label class="block text-xs">
                  Move <span class="font-mono">{c.votes.toLocaleString()}</span> of <span class="font-mono">{pool.toLocaleString()}</span> available votes
                  <input
                    type="range" class="w-full"
                    min="0" max={pool}
                    step="100"
                    value={c.votes}
                    oninput={(e) => updateMutation(i, { votes: Number((e.target as HTMLInputElement).value) })}
                  />
                </label>

              {:else if cfg.id === 'statewideSwing'}
                {@const c = cfg as StatewideSwingConfig}
                <div class="space-y-1 text-xs">
                  <div class="text-slate-600">From <span class="text-slate-400">(check one or many)</span></div>
                  <div class="max-h-28 overflow-y-auto pr-1 border border-slate-200 rounded p-1 bg-white">
                    {#each party_choices as p}
                      <label class="flex items-center gap-2 py-0.5">
                        <input
                          type="checkbox"
                          checked={c.from_party_eci_codes.includes(p.code)}
                          onchange={(e) => {
                            const on = (e.target as HTMLInputElement).checked;
                            const next = on
                              ? [...c.from_party_eci_codes, p.code]
                              : c.from_party_eci_codes.filter(x => x !== p.code);
                            updateMutation(i, { from_party_eci_codes: next });
                          }}
                        />
                        <span class="font-mono text-[10px] text-slate-400 w-10">{p.code}</span>
                        <span>{p.short}</span>
                      </label>
                    {/each}
                  </div>
                </div>
                <label class="block text-xs">To
                  <select
                    class="mt-0.5 w-full rounded border-slate-300 py-1 px-2 text-xs"
                    value={c.to_party_eci_code}
                    onchange={(e) => updateMutation(i, { to_party_eci_code: (e.target as HTMLSelectElement).value })}
                  >
                    {#each party_choices as p}<option value={p.code}>{p.short}</option>{/each}
                  </select>
                </label>
                <label class="block text-xs">
                  Swing <span class="font-mono">{c.pct.toFixed(1)}%</span> of {c.from_party_eci_codes.map(partyLabel).join(' + ') || '\u2026'} → {partyLabel(c.to_party_eci_code)}
                  <input
                    type="range" class="w-full" min="0" max="50" step="0.5"
                    value={c.pct}
                    oninput={(e) => updateMutation(i, { pct: Number((e.target as HTMLInputElement).value) })}
                  />
                </label>

              {:else if cfg.id === 'thresholdDrop'}
                {@const c = cfg as ThresholdDropConfig}
                <label class="block text-xs">
                  Drop candidates below <span class="font-mono">{c.threshold_pct.toFixed(1)}%</span> per AC
                  <input
                    type="range" class="w-full" min="0" max="20" step="0.5"
                    value={c.threshold_pct}
                    oninput={(e) => updateMutation(i, { threshold_pct: Number((e.target as HTMLInputElement).value) })}
                  />
                </label>
                <p class="text-[10px] text-slate-500">
                  Freed votes redistributed to surviving candidates proportionally.
                </p>

              {:else if cfg.id === 'partyBag'}
                {@const c = cfg as PartyBagConfig}
                <label class="block text-xs">
                  Bag name
                  <input
                    class="mt-0.5 w-full rounded border-slate-300 py-1 px-2 text-xs"
                    value={c.name}
                    oninput={(e) => updateMutation(i, { name: (e.target as HTMLInputElement).value })}
                  />
                </label>
                <fieldset class="text-xs space-y-1 max-h-40 overflow-y-auto pr-1">
                  <legend class="text-[10px] uppercase tracking-wide text-slate-500">Members</legend>
                  {#each party_choices as p}
                    <label class="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={c.members.includes(p.code)}
                        onchange={(e) => {
                          const on = (e.target as HTMLInputElement).checked;
                          const members = on
                            ? [...c.members, p.code]
                            : c.members.filter(x => x !== p.code);
                          updateMutation(i, { members });
                        }}
                      />
                      <span class="font-mono text-[10px] text-slate-400 w-10">{p.code}</span>
                      <span>{p.short}</span>
                    </label>
                  {/each}
                </fieldset>
              {/if}
            </li>
          {/each}
        </ul>

        <div class="pt-2 border-t border-slate-200 space-y-2">
          <label class="block text-xs">
            Counting rule
            <select
              class="mt-0.5 w-full rounded border-slate-300 py-1 px-2 text-xs"
              value={scenario.rule}
              onchange={(e) => (scenario = { ...scenario, rule: (e.target as HTMLSelectElement).value })}
            >
              {#each RULES as r}
                <option value={r.id}>{r.label}</option>
              {/each}
            </select>
          </label>
          <div class="flex gap-2">
            <button
              class="flex-1 text-xs rounded border border-slate-300 py-1.5 hover:bg-slate-50"
              onclick={copyShareUrl}
            >
              {share_state === "copied" ? "✓ Copied" : share_state === "failed" ? "Copy failed" : "Copy share URL"}
            </button>
            <button
              class="text-xs rounded border border-slate-300 py-1.5 px-3 hover:bg-slate-50"
              onclick={resetScenario}
            >Reset</button>
          </div>
        </div>
      </section>

      <!-- ============== Result canvas ============== -->
      <section class="space-y-4 min-w-0">
        <!-- Compact summary strip -->
        <div class="bg-white rounded-lg shadow-sm p-4 grid grid-cols-3 gap-4 text-sm">
          <div>
            <div class="text-[10px] uppercase tracking-wide text-slate-500">Total seats</div>
            <div class="text-lg font-semibold">{total_seats}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wide text-slate-500">Majority mark</div>
            <div class="text-lg font-semibold">{majority}</div>
          </div>
          <div>
            <div class="text-[10px] uppercase tracking-wide text-slate-500">Mutated total votes</div>
            <div class="text-lg font-semibold">{result.allocation.total_votes.toLocaleString()}</div>
          </div>
        </div>

        <!-- Parliament arc -->
        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-sm font-semibold uppercase text-slate-500 mb-2">Scenario seats</h3>
          <ParliamentArc parties={result.allocation.by_party} total_seats={total_seats} />
        </div>

        <!-- Vote-flow Sankey -->
        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-sm font-semibold uppercase text-slate-500 mb-2">Vote flow (actuals → scenario)</h3>
          <SwingSankey actuals={result.actuals_allocation.by_party} scenario={result.allocation.by_party} />
        </div>

        <!-- Before / After party bar -->
        <div class="grid md:grid-cols-2 gap-4">
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-sm font-semibold uppercase text-slate-500 mb-3">Actuals</h3>
            <ul class="space-y-1.5">
              {#each ranked_parties.act as p (p.party_eci_code)}
                <li class="flex items-center gap-2 text-xs">
                  <span class="w-16 text-right truncate font-medium" title={p.party_short}>{p.party_short}</span>
                  <span class="relative flex-1 h-5 bg-slate-100 rounded">
                    <span
                      class="absolute inset-y-0 left-0 rounded transition-[width] duration-300"
                      style:width="{(p.seats_won / Math.max(1, total_seats)) * 100}%"
                      style:background-color={colors.fill(p.party_eci_code, p.party_short)}
                    ></span>
                    <span class="absolute inset-y-0 px-2 flex items-center text-[10px] font-semibold text-slate-900">{p.seats_won}</span>
                  </span>
                </li>
              {/each}
            </ul>
          </div>

          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-sm font-semibold uppercase text-slate-500 mb-3">Scenario</h3>
            <ul class="space-y-1.5">
              {#each ranked_parties.mut as p (p.party_eci_code)}
                {@const delta = deltaFor(p.party_eci_code)}
                <li class="flex items-center gap-2 text-xs">
                  <span class="w-16 text-right truncate font-medium" title={p.party_short}>{p.party_short}</span>
                  <span class="relative flex-1 h-5 bg-slate-100 rounded">
                    <span
                      class="absolute inset-y-0 left-0 rounded transition-[width] duration-300"
                      style:width="{(p.seats_won / Math.max(1, total_seats)) * 100}%"
                      style:background-color={colors.fill(p.party_eci_code, p.party_short)}
                    ></span>
                    <span class="absolute inset-y-0 px-2 flex items-center text-[10px] font-semibold text-slate-900">{p.seats_won}</span>
                  </span>
                  <span
                    class="w-10 text-right font-mono text-[11px]"
                    class:text-emerald-700={delta > 0}
                    class:text-rose-700={delta < 0}
                    class:text-slate-400={delta === 0}
                  >
                    {delta > 0 ? '+' : ''}{delta}
                  </span>
                </li>
              {/each}
            </ul>
          </div>
        </div>

        <!-- Detailed delta table -->
        <div class="bg-white rounded-lg shadow-sm p-4 overflow-x-auto">
          <h3 class="text-sm font-semibold uppercase text-slate-500 mb-3">Party deltas</h3>
          <table class="w-full text-xs">
            <thead class="text-slate-500">
              <tr class="border-b border-slate-200">
                <th class="text-left py-1 pr-3">Party</th>
                <th class="text-right py-1 px-2">Actual seats</th>
                <th class="text-right py-1 px-2">Scenario seats</th>
                <th class="text-right py-1 px-2">Δ seats</th>
                <th class="text-right py-1 px-2">Scenario votes</th>
                <th class="text-right py-1 pl-2">Scenario %</th>
              </tr>
            </thead>
            <tbody>
              {#each result.allocation.by_party.filter(p => p.seats_won > 0 || p.vote_share_pct >= 0.5) as p (p.party_eci_code)}
                {@const delta = deltaFor(p.party_eci_code)}
                {@const act = result.actuals_allocation.by_party.find(x => x.party_eci_code === p.party_eci_code)}
                <tr class="border-b border-slate-100 hover:bg-slate-50">
                  <td class="py-1 pr-3 font-medium" style:color={colors.fill(p.party_eci_code, p.party_short)}>
                    {p.party_short}
                  </td>
                  <td class="text-right tabular-nums px-2">{act?.seats_won ?? 0}</td>
                  <td class="text-right tabular-nums px-2 font-semibold">{p.seats_won}</td>
                  <td
                    class="text-right tabular-nums px-2"
                    class:text-emerald-700={delta > 0}
                    class:text-rose-700={delta < 0}
                    class:text-slate-400={delta === 0}
                  >
                    {delta > 0 ? '+' : ''}{delta}
                  </td>
                  <td class="text-right tabular-nums px-2">{p.votes.toLocaleString()}</td>
                  <td class="text-right tabular-nums pl-2">{p.vote_share_pct.toFixed(2)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  {/if}
</div>
