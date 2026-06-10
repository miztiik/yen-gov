<script lang="ts">
  // Psephlab v1 — what-if simulator.
  //
  // Loads actuals (Tallies) for the (event, state) and runs the engine on
  // every scenario change. PR-W5a (2026-06-10): scenarios are now
  // EPHEMERAL component-local state per the election-experience-overhaul
  // plan binding constraint #8 ("No URL-encoded scenario blob. No
  // localStorage. Refresh = fresh start."). The previous URL-hydration
  // helpers (`decodeScenario` / `writeScenarioToHash`) are gone; the
  // only surviving URL coupling is the optional `/m/:method` path
  // segment that pre-selects the counting rule at mount time.

  // PR-R.2 (Phase 1.8e): switched from legacy `psephlab/actuals` (sql.js +
  // per-state results.sqlite) to `psephlab/canonical-loaders` (DuckDB-WASM
  // over canonical Parquet). Same `loadActuals(event, state)` signature,
  // same `Tallies` shape; engine + mutations untouched. Legacy file +
  // sql.js runtime delete in PR-R.3.
  import { loadActuals } from "../lib/psephlab/canonical-loaders";
  import { run } from "../lib/psephlab/engine";
  import { MUTATIONS, mutationById } from "../lib/psephlab/mutations";
  import { RULES, ruleById } from "../lib/psephlab/rules";
  import {
    applicableMutationsFor,
    inertReasonFor,
  } from "../lib/psephlab/applicable-mutations";
  import { buildMethodPreviews } from "../lib/psephlab/method-preview";
  import { EMPTY_SCENARIO } from "../lib/psephlab/scenario";
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
  import { partyColourHex } from "../lib/psephlab/colour-bridge";
  import ParliamentArc from "../lib/ParliamentArc.svelte";
  import SwingSankey from "../lib/SwingSankey.svelte";
  import MethodPickerPill from "../lib/MethodPickerPill.svelte";
  import MethodDrawer from "../lib/MethodDrawer.svelte";
  import HeroExplanation from "../lib/HeroExplanation.svelte";
  import ContextLabel from "../lib/ContextLabel.svelte";
  import GallagherDisproportionality from "../lib/charts/GallagherDisproportionality.svelte";
  import { states } from "../lib/states.svelte";
  import { navigate } from "../lib/url";
  import { link } from "../lib/links";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import { docsUrl } from "../lib/repo";
  import { majorityFor } from "../lib/electoral";
  import { fade } from "svelte/transition";
  import {
    fetchElectionEvents,
    findEvent,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";

  /** params.method is the optional 4-segment path discriminator
   *  (`/lab/:state/:event/m/:method`). When present it pre-selects the
   *  counting rule at mount time. PR-W5a (2026-06-10) collapsed the
   *  prior strangler-fig fallback: scenarios no longer hydrate from a
   *  URL-encoded scenario blob, so the path segment is the SOLE rule
   *  source for the initial scenario. */
  interface Props {
    params: { state: string; event: string; method?: string };
  }
  let { params }: Props = $props();

  const event = $derived(params.event);
  const state_code = $derived(states.codeFromSlug(params.state));
  /** Method id from the optional `/m/<method>` path segment. Empty when
   *  the citizen is on the bare 3-segment route (defaults to FPTP). */
  const path_method = $derived(params.method ?? "");

  let actuals = $state<Tallies | null>(null);
  let actuals_error = $state<string | null>(null);
  let event_catalogue = $state<ElectionEventsCatalogue | null>(null);

  // Initial scenario is EMPTY_SCENARIO with the optional path-method
  // override pre-selected. PR-W5a (2026-06-10): no URL-hydration, no
  // history.replaceState flush; scenarios live and die with this
  // component instance per the plan-doc binding constraint #8.
  let scenario = $state<Scenario>(initialScenario());

  function initialScenario(): Scenario {
    if (path_method) {
      return { ...EMPTY_SCENARIO, rule: path_method };
    }
    return EMPTY_SCENARIO;
  }

  // Fetch the election catalogue once so ContextLabel can show the
  // citizen-readable event display string ("TN AC Apr 2021") instead
  // of the opaque event id.
  $effect(() => {
    fetchElectionEvents()
      .then((c) => (event_catalogue = c))
      .catch(() => (event_catalogue = null));
  });

  $effect(() => {
    actuals = null;
    actuals_error = null;
    const ev = event, st = state_code;
    if (!st) return;
    loadActuals(ev, st)
      .then(t => (actuals = t))
      .catch(e => (actuals_error = String(e)));
  });

  // ----- Method-first navigation (2026-06-09 redesign) -----
  //
  // Switching counting rule navigates to the 4-segment
  // `/lab/<state>/<event>/m/<method-id>` route so the URL telegraphs
  // the active method (per Jony + Fowler convergence). The scenario
  // blob's `rule` field is kept in sync as a legacy fallback for
  // existing share URLs (Fowler strangler-fig EXPAND).
  function selectMethod(method_id: string): void {
    if (method_id === scenario.rule) return;
    scenario = { ...scenario, rule: method_id };
    if (state_code) {
      navigate(link.labMethod(state_code, event, method_id), { replace: true });
    }
  }

  /** Citizen-readable election display string from the catalogue. */
  const election_display = $derived(
    state_code
      ? findEvent(event_catalogue, state_code, event)?.display ?? null
      : null,
  );
  /** Live preview map: rule_id -> { top: PreviewItem[]; chamber }.
   *  Computed ONCE when actuals load (memoised in $derived; recomputes
   *  only on actuals identity change, which happens on event switch =
   *  page reload). 12 rule.apply() runs at ~3ms each = ~40ms one-time
   *  cost on TN-234; well under the page-mount budget which is
   *  dominated by the DuckDB-WASM 800-1500ms boot.
   *
   *  Per Jony + Fowler ship-loop verdict (2026-06-09): the drawer
   *  cards render this as a citizen-readable "DMK 133 / AIADMK 66 /
   *  INC 18" line below the headline, plus MMP chamber suffix. */
  const method_previews = $derived(buildMethodPreviews(actuals, RULES));

  /** All 12 method options the picker drawer renders. Carries each
   *  rule's validity + headline + short_label so the drawer + pill
   *  read the rule's own copy without a second translation layer.
   *  Threads the precomputed preview (top-3 + chamber) so each card
   *  shows the live seat outcome under that rule. */
  const method_options = $derived(
    RULES.map((r) => ({
      id: r.id,
      label: r.label,
      short_label: r.short_label,
      headline: r.headline,
      validity: r.validity,
      preview: method_previews?.get(r.id),
      constituency_seats: actuals?.acs.length,
    })),
  );

  /** Drawer open/close state (host owns; drawer is purely controlled). */
  let drawer_open = $state(false);

  // PR-W5a (2026-06-10): scenario -> URL flush retired. Scenarios are
  // ephemeral component-local state per the election-experience-overhaul
  // plan binding constraint #8. Refresh = fresh start.

  // Engine run. Pure & synchronous; for TN-scale (234 ACs) takes <5ms.
  // $derived recomputes on any scenario or actuals change.
  const result = $derived.by(() => {
    if (!actuals) return null;
    return run(actuals, scenario);
  });

  // E6 alternate-counting metadata (Hans's "fabricated-input" gate per
  // TODO/20260608-e6-user-override-and-pl2-pl3-execution-subplan.md).
  // - current_rule: full CountingRule for the active scenario; used to
  //   read caveat / assumptions / requires_banner.
  // - fptp_official: the SAME tally run under FPTP, regardless of the
  //   active rule. Used to (a) compose the "Official result: ..." label
  //   the banner cites + (b) feed GallagherDisproportionality (which
  //   measures the OFFICIAL FPTP system's disproportionality, NOT the
  //   counterfactual rule's). Per Hans verdict, Gallagher is a measurement
  //   of FPTP, not of any counterfactual.
  const current_rule = $derived(ruleById(scenario.rule));
  const fptp_official = $derived.by(() => {
    if (!actuals) return null;
    return ruleById("fptp").apply(actuals);
  });
  const official_result_label = $derived.by(() => {
    if (!fptp_official || fptp_official.by_party.length === 0) return undefined;
    const seats_total = actuals?.acs.length ?? 0;
    const top = fptp_official.by_party[0];
    if (top.seats_won === 0) return undefined;
    return `${top.party_short} won ${top.seats_won} of ${seats_total} seats (FPTP)`;
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
  /** Active rule's effective chamber size (MMP grows past the
   *  constituency count via overhang compensation; every other rule
   *  uses total_seats as-is). Read from allocation.chamber_seats with
   *  a fallback to constituency count. Used by ParliamentArc, the
   *  majority computation, the summary strip, and the Actuals/Scenario
   *  bar widths. */
  const chamber_seats = $derived(result?.allocation.chamber_seats ?? total_seats);
  // Majority threshold = strictly more than half the seats (FPTP convention).
  // Shared helper from `lib/electoral` so Donut, Bar, ParliamentArc and
  // every Psephlab readout agree on the same number. For TN 234 it's 118;
  // for Parliament 543 it's 272. When MMP grows the chamber, majority
  // adjusts (272 in 543 -> 353 in 705).
  const majority = $derived(majorityFor(chamber_seats));

  // ----- Hide-party state (Phase 2 deselect) -----
  //
  // Scenarios are about *what-ifs*: muting a party while a scenario is
  // being authored confuses "did I hide them?" with "did the mutation
  // erase them?". Per spec we therefore RESET the mute set the moment a
  // scenario gains its first mutation. Adding more mutations after the
  // first does NOT reset (the user has already opted into the experiment).
  let hidden_parties = $state<Set<string>>(new Set());
  let prev_mutation_count = 0;
  $effect(() => {
    const n = scenario.mutations.length;
    if (prev_mutation_count === 0 && n > 0 && hidden_parties.size > 0) {
      hidden_parties = new Set();
    }
    prev_mutation_count = n;
  });
  function togglePartyHidden(code: string): void {
    const next = new Set(hidden_parties);
    if (next.has(code)) next.delete(code); else next.add(code);
    hidden_parties = next;
  }

  // ----- Mutation stack management -----

  function addMutation(id: string): void {
    const plug = mutationById(id);
    if (!plug || !actuals) return;
    scenario = { ...scenario, mutations: [...scenario.mutations, plug.defaultConfig(actuals)] };
  }

  /** Applicable mutations under the active counting rule. Filters out
   *  per-AC mutations that have zero visible effect under Proportional
   *  (perAcSwing + thresholdDrop) per Fowler allow-list seam. The
   *  rule-agnostic ones (statewideSwing + partyBag) always render. */
  const applicable_mutations = $derived(applicableMutationsFor(scenario.rule));

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

  // The info icon next to each mutation row jumps to the matching
  // subsection of the Psephlab architecture doc on GitHub (which renders
  // the embedded mermaid diagrams natively). Per CLAUDE.md §1 there's no
  // docs server we own; the canonical Markdown source on the repo's
  // configured branch is the single source of truth. The repo URL itself
  // is centralised in lib/repo.ts so a fork or rename is a one-line swap.
  const PSEPHLAB_DOC = "docs/architecture/frontend/psephlab.md";
</script>

<div class="max-w-6xl mx-auto p-4 md:p-6 space-y-4">
  <header class="space-y-3">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={state_code ? link.state(state_code) : link.home()}>← {states.name(state_code)} overview</a></p>
    <div class="flex items-baseline justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold flex items-center gap-2">
        <TopicIcon name="flask" cls="w-6 h-6 text-slate-500 shrink-0" />
        <span>Election Studio &mdash; {states.name(state_code)}</span>
      </h1>
    </div>
    <!--
      Method-first nav v2 (Jony + Fowler + Hans verdict round 2,
      2026-06-09). The 4-method horizontal-scroll segmented control
      (MethodTabs) retires - 12 methods do not fit that affordance.
      The pill + drawer pattern scales: one button + categorised cards
      in a native <dialog> bottom-sheet on mobile / modal-sheet on
      desktop. URL still telegraphs the active method as
      `/lab/<state>/<event>/m/<method-id>`.
    -->
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <MethodPickerPill
        active_label={current_rule.short_label ?? current_rule.label}
        onopen={() => (drawer_open = true)}
      />
      <a
        class="text-xs font-medium hover:underline inline-flex items-center gap-1"
        style:color="var(--accent, #3538cd)"
        href={link.docsLabMethod(current_rule.id)}
      >
        <span>Read about counting methods</span>
        <span aria-hidden="true">-&gt;</span>
      </a>
    </div>
    <MethodDrawer
      methods={method_options}
      active_method_id={scenario.rule}
      open={drawer_open}
      onpick={selectMethod}
      onclose={() => (drawer_open = false)}
    />
    <ContextLabel
      election_display={election_display}
      seat_count={chamber_seats}
      rule_id={scenario.rule}
      rule_label={current_rule.label}
      mutation_count={scenario.mutations.length}
    />
  </header>

  {#if actuals_error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load actuals: <code>{actuals_error}</code>
    </div>
  {:else if !actuals || !result}
    <div class="text-slate-500 p-8 text-center">Loading actuals…</div>
  {:else}
    <!--
      Full-width hero explanation (Jony + Hans round-2 verdict). Sits
      above the chamber so the citizen reads top-to-bottom: which
      election, which rule, what it does, what it looks like. FPTP
      gets the card too (round-1 missed this teaching moment); the
      `is_official` flag drops the civic-indigo rail + validity badge
      for the baseline rule.
    -->
    <HeroExplanation
      method_label={current_rule.short_label ?? current_rule.label}
      headline={current_rule.headline ?? `Explore the seats under ${current_rule.label}.`}
      caveat={current_rule.caveat}
      validity={current_rule.validity}
      assumptions={current_rule.assumptions ?? []}
      official_result_label={official_result_label}
      docs_href={link.docsLabMethod(current_rule.id)}
      is_official={current_rule.id === "fptp"}
    />

    <!--
      Single-column chamber-first layout (Jony round-2 verdict). The
      sticky 360px left rail retires; mutations move to a horizontal
      Workbench below the arc. Full canvas width for the result.
    -->
    <section class="space-y-4 min-w-0">
      <!-- Compact summary strip -->
      <div class="bg-white rounded-lg shadow-sm p-4 grid grid-cols-3 gap-4 text-sm">
        <div>
          <div class="text-[10px] uppercase tracking-wide text-slate-500">Total seats</div>
          <div class="text-lg font-semibold tabular-nums">{chamber_seats}</div>
        </div>
        <div>
          <div class="text-[10px] uppercase tracking-wide text-slate-500">Majority mark</div>
          <div class="text-lg font-semibold tabular-nums">{majority}</div>
        </div>
        <div>
          <div class="text-[10px] uppercase tracking-wide text-slate-500">Total votes</div>
          <div class="text-lg font-semibold tabular-nums">{result.allocation.total_votes.toLocaleString()}</div>
        </div>
      </div>

      <!--
        ParliamentArc - full width. {#key scenario.rule} forces a fresh
        mount on method switch so Svelte's in:fade animates the new
        chamber painting in. Duration token --dur (200ms); collapses
        to ~1ms under prefers-reduced-motion via the same token
        override that already governs --dur globally.
      -->
      <div class="bg-white rounded-lg shadow-sm p-4">
        <div class="flex items-baseline justify-between mb-2 gap-2">
          <h3 class="text-sm font-semibold uppercase text-slate-500">Scenario seats</h3>
          {#if hidden_parties.size > 0}
            <button
              class="text-xs text-blue-600 hover:underline"
              onclick={() => (hidden_parties = new Set())}
            >Show all ({hidden_parties.size} muted)</button>
          {:else}
            <span class="text-xs text-slate-400">Click a legend chip to mute &middot; resets on first mutation</span>
          {/if}
        </div>
        {#key scenario.rule}
          <div in:fade={{ duration: 200 }}>
            <ParliamentArc
              parties={result.allocation.by_party}
              total_seats={chamber_seats}
              {hidden_parties}
              onToggleHidden={togglePartyHidden}
            />
          </div>
        {/key}
      </div>

      <!--
        Horizontal Workbench (Jony round-2 verdict, user ask #5).
        Mutation cards are flex-wrap items at ~280-360px wide; on lg
        we get 2-3 columns; mobile stacks. Each card keeps its existing
        per-mutation editor body - the layout change is the
        container, not the editor surface.
      -->
      <section class="bg-white rounded-lg shadow-sm p-4 space-y-3" data-component="workbench">
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <h2 class="text-sm font-semibold uppercase text-slate-500">
            What-ifs <span class="text-slate-400 font-normal normal-case">({scenario.mutations.length} applied)</span>
          </h2>
          <div class="flex items-center gap-2">
            <select
              class="text-xs rounded border-slate-300 py-1 px-2"
              value=""
              onchange={(e) => {
                const v = (e.target as HTMLSelectElement).value;
                if (v) { addMutation(v); (e.target as HTMLSelectElement).value = ""; }
              }}
            >
              <option value="">+ Add what-if...</option>
              {#each applicable_mutations as m}
                <option value={m.id}>{m.label}</option>
              {/each}
            </select>
            <button
              class="text-xs rounded border border-slate-300 py-1 px-3 hover:bg-slate-50"
              onclick={copyShareUrl}
              title="Copy the share URL with this scenario encoded"
            >
              {share_state === "copied" ? "Copied" : share_state === "failed" ? "Copy failed" : "Copy share URL"}
            </button>
            {#if scenario.mutations.length > 0}
              <button
                class="text-xs rounded border border-slate-300 py-1 px-3 hover:bg-slate-50"
                onclick={resetScenario}
              >Reset</button>
            {/if}
          </div>
        </div>

        {#if scenario.mutations.length === 0}
          <p class="text-xs text-slate-500 italic">
            No what-ifs yet. Use the menu above to add a swing, threshold drop, or party bag - and watch the chamber re-paint.
          </p>
        {/if}

        <ul class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3" data-component="workbench-cards">
          {#each scenario.mutations as cfg, i (i + ':' + cfg.id)}
            {@const plug = mutationById(cfg.id)}
            {@const inert_reason = inertReasonFor(cfg, scenario.rule)}
            <li
              class="border rounded p-2 space-y-2"
              class:bg-amber-50={inert_reason !== null}
              class:border-amber-200={inert_reason !== null}
              class:bg-slate-50={inert_reason === null}
              class:border-slate-200={inert_reason === null}
            >
              {#if inert_reason}
                <p class="text-[11px] text-amber-900 leading-snug">
                  {inert_reason}
                </p>
              {/if}
              <div class="flex items-center justify-between gap-1 text-xs">
                <span class="flex items-center gap-1 font-medium text-slate-700">
                  <span>{i + 1}. {plug?.label ?? cfg.id}</span>
                  {#if plug?.docs_anchor}
                    <a
                      class="text-slate-400 hover:text-sky-700 inline-flex items-center"
                      href={docsUrl(PSEPHLAB_DOC, plug.docs_anchor)}
                      target="_blank"
                      rel="noreferrer"
                      title={`${plug.summary}\n\nClick to open the full explanation (with diagrams) on GitHub.`}
                      aria-label={`How ${plug.label} works — open documentation`}
                    >
                      <!-- Heroicons: information-circle (mini) -->
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3.5 h-3.5">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z" clip-rule="evenodd" />
                      </svg>
                    </a>
                  {/if}
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
                    type="range" class="w-full" min="0" max="100" step="0.5"
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
                      <span>{p.short}</span>
                    </label>
                  {/each}
                </fieldset>
              {/if}
            </li>
          {/each}
        </ul>
      </section>

      <!-- Vote-flow Sankey + E7 Gallagher disproportionality side by side -->
      <div class="grid md:grid-cols-2 gap-4">
        <div class="bg-white rounded-lg shadow-sm p-4">
          <h3 class="text-sm font-semibold uppercase text-slate-500 mb-2">Vote flow (actuals -&gt; scenario)</h3>
          <SwingSankey actuals={result.actuals_allocation.by_party} scenario={result.allocation.by_party} />
        </div>
        {#if fptp_official}
          <div class="bg-white rounded-lg shadow-sm p-4">
            <h3 class="text-sm font-semibold uppercase text-slate-500 mb-3">
              Gallagher index (official FPTP result)
            </h3>
            <p class="text-xs text-slate-500 mb-3">
              How much did seat shares diverge from vote shares in the actual
              FPTP election? Lower is more proportional. This always measures
              the official result, not any counterfactual rule above.
            </p>
            <GallagherDisproportionality
              allocation={fptp_official}
              total_seats={total_seats}
            />
          </div>
        {/if}
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
                    style:background-color={partyColourHex(p)}
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
                    style:width="{(p.seats_won / Math.max(1, chamber_seats)) * 100}%"
                    style:background-color={partyColourHex(p)}
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
              <th class="text-right py-1 px-2">Delta seats</th>
              <th class="text-right py-1 px-2">Scenario votes</th>
              <th class="text-right py-1 pl-2">Scenario %</th>
            </tr>
          </thead>
          <tbody>
            {#each result.allocation.by_party.filter(p => p.seats_won > 0 || p.vote_share_pct >= 0.5) as p (p.party_eci_code)}
              {@const delta = deltaFor(p.party_eci_code)}
              {@const act = result.actuals_allocation.by_party.find(x => x.party_eci_code === p.party_eci_code)}
              <tr class="border-b border-slate-100 hover:bg-slate-50">
                <td class="py-1 pr-3 font-medium" style:color={partyColourHex(p)}>
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
  {/if}
</div>
