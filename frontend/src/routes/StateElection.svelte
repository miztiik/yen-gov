<script lang="ts">
  // Per-state per-event election landing (/s/:state/elections/:event).
  //
  // ADR-0023 Phase 2 — the citizen-readable permalink for "this state's
  // results for THIS election". Wired 2026-05-24 alongside the Q1 fix to
  // /s/<state>/t/elections. The route was previously absent from
  // main.ts; the topic-page election card had no canonical link target
  // and citizens who tried to deep-link to a specific cohort fell through
  // to NotFound.
  //
  // Scope deliberately minimal: this is the neutral landing, not a
  // duplicate of the StateOverview election block and not the analyst
  // surface. It surfaces:
  //   * breadcrumb (State → Elections → <event display>)
  //   * one header card with the event title, polled-on date, data status
  //   * three CTAs into the existing deeper surfaces:
  //       - "View constituency results"     → /lab/<state>/<event>
  //       - "Compare across states"         → /compare/<state>/<event>
  //       - "See this state's other data"   → /s/<state>
  //
  // The two embedded chart components (ElectionSeatsTrend etc.) live on
  // /s/<state> and /lab/<state>/<event>; we don't double-render them here.
  // If a citizen wants the rich results UI they click through to one of
  // the two existing surfaces. This keeps the route a simple permalink
  // wrapper and avoids forking the rendering logic.
  //
  // 404 behaviour:
  //   * unknown state slug                 → "State not found" panel
  //   * unknown event id within the state  → "Election not found" panel
  // Never blank-page; never crash.

  import { fetchElectionEvents, findEvent, listEventsForState, type ElectionEventsCatalogue } from "../lib/election-events";
  import { states } from "../lib/states.svelte";
  import { navigate, url } from "../lib/url";
  import ElectionMap from "../lib/elections/ElectionMap.svelte";
  import ElectionTimeSlider from "../lib/elections/ElectionTimeSlider.svelte";
  import ElectionFilterRail from "../lib/elections/ElectionFilterRail.svelte";
  import { buildSliderStops } from "../lib/elections/election-time-slider";
  import { hasModeCoverage } from "../lib/elections/election-map-coloring";
  import {
    parseElectionFilters,
    serializeElectionFilters,
    type ElectionFilters,
  } from "../lib/election-filters";
  import {
    getPartyColor,
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../lib/colors/resolver";
  import { loadStateAcWinners, type AcWinner } from "../lib/view-models/state-overview";

  interface Props {
    params: { state: string; event: string };
  }
  let { params }: Props = $props();

  let catalogue = $state<ElectionEventsCatalogue | null>(null);
  let load_error = $state<string | null>(null);
  fetchElectionEvents()
    .then(c => (catalogue = c))
    .catch(e => (load_error = String(e)));

  const state_code = $derived(states.codeFromSlug(params.state));
  const state_name = $derived(state_code ? states.name(state_code) : "");
  const event_row = $derived(findEvent(catalogue, state_code, params.event));

  // PR-B6 — snapping time-slider stops. Same-grain only: the AC map scrubs
  // across this state's ASSEMBLY elections (Lok Sabha slices drill into the
  // national atlas, not this per-state surface). Chronologically ascending.
  const slider_stops = $derived(
    buildSliderStops(
      listEventsForState(catalogue, state_code).filter(e => e.kind === "assembly"),
    ),
  );

  // Scrubbing the slider just changes the route's :event segment; the
  // reactive chain below (event_row -> $effect -> ac_winners) reloads the
  // winners and recolours the map. URL is the single source of truth.
  function selectEvent(eventId: string) {
    if (state_code) navigate(url.stateElection(state_code, eventId));
  }

  const states_loading = $derived(!states.isLoaded);
  const catalogue_loading = $derived(catalogue === null && load_error === null);

  // Assembly results power the map+toggle surface. Lok Sabha (national)
  // events drill into the national atlas (PR-B4), not this per-state AC map,
  // so we only load AC winners for assembly events. `null` = loading.
  let ac_winners = $state<AcWinner[] | null>(null);
  $effect(() => {
    ac_winners = null;
    const sc = state_code;
    const ev = event_row;
    if (!sc || !ev || ev.kind !== "assembly") return;
    loadStateAcWinners(ev.event_id, sc).then(r => {
      ac_winners = r.status === "ok" || r.status === "partial" ? r.data : [];
    });
  });

  // PR-B8 — filter rail (colour-by mode + party/margin dimming). The URL is
  // the single source of truth; the rail is a controlled component. We track
  // a local mirror of the parsed query string so reactivity fires after a
  // `navigate` (which dispatches popstate and re-runs the router).
  let filter_search = $state(
    typeof window === "undefined" ? "" : window.location.search,
  );
  const filters = $derived<ElectionFilters>(parseElectionFilters(filter_search));

  function onFilterChange(next: ElectionFilters): void {
    if (typeof window === "undefined") return;
    const base = new URLSearchParams(window.location.search);
    const qs = serializeElectionFilters(next, base);
    const target =
      window.location.pathname + (qs ? `?${qs}` : "") + window.location.hash;
    navigate(target);
    filter_search = qs ? `?${qs}` : "";
  }

  // Distinct winning parties for the rail chips, palette-consistent with the
  // map (PR-SYM-6i-pre3: 3-tier resolver keyed on party_id, mirrors ElectionMap).
  function partyIdFor(r: { party_id?: string | null; party_short: string }): string {
    if (r.party_id) return r.party_id;
    const slug = (r.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }
  function rowFor(pid: string, r: AcWinner): PartyRowForResolver | null {
    if (r.brand_colour_hex == null) return null;
    return {
      party_id: pid,
      eci_code: r.party_eci_code,
      brand_colour: {
        hex: r.brand_colour_hex,
        confidence: r.brand_colour_confidence ?? "medium",
      },
    };
  }
  const party_options = $derived.by(() => {
    const list = ac_winners ?? [];
    const ids: string[] = [];
    const rowMap = new Map<string, PartyRowForResolver | null>();
    const pidByCode = new Map<string, string>();
    const seen = new Map<string, { code: string; short: string; color: string }>();
    for (const r of list) {
      const code = r.party_eci_code ?? r.party_short;
      if (pidByCode.has(code)) continue;
      const pid = partyIdFor(r);
      pidByCode.set(code, pid);
      if (!rowMap.has(pid)) {
        ids.push(pid);
        rowMap.set(pid, rowFor(pid, r));
      }
    }
    const palette = resolvePartyPalette(ids, rowMap);
    for (const r of list) {
      const code = r.party_eci_code ?? r.party_short;
      if (seen.has(code)) continue;
      const pid = pidByCode.get(code) ?? partyIdFor(r);
      seen.set(code, {
        code,
        short: r.party_short,
        color:
          palette.get(pid)?.hex ??
          getPartyColor(pid, rowMap.get(pid) ?? null).hex,
      });
    }
    return [...seen.values()];
  });

  const mode_coverage = $derived({
    turnout: hasModeCoverage(ac_winners ?? [], "turnout"),
    age: hasModeCoverage(ac_winners ?? [], "age"),
  });
</script>

<section class="p-4 sm:p-6 space-y-6 max-w-4xl">
  {#if load_error}
    <div class="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
      Failed to load election catalogue: <code>{load_error}</code>
    </div>
  {:else if catalogue_loading || states_loading}
    <p class="text-sm text-slate-500">Loading…</p>
  {:else if !state_code}
    <div class="space-y-2">
      <p class="text-sm">
        <a href={url.home()} class="text-sky-700 hover:underline">← Home</a>
      </p>
      <h1 class="text-2xl font-semibold">State not found</h1>
      <p class="text-sm text-slate-600">
        No state with slug <code class="rounded bg-slate-100 px-1">{params.state}</code>.
        Pick a state from the <a href={url.home()} class="text-sky-700 hover:underline">home page</a>.
      </p>
    </div>
  {:else if !event_row}
    <div class="space-y-2">
      <nav aria-label="Breadcrumb" class="text-xs text-slate-500">
        <ol class="flex items-center gap-1 list-none p-0 m-0">
          <li>
            <a href={url.state(state_code)} class="hover:text-sky-700 hover:underline">{state_name}</a>
          </li>
          <li aria-hidden="true" class="text-slate-400">›</li>
          <li>
            <a href={url.stateTopic(state_code, "elections")} class="hover:text-sky-700 hover:underline">Elections</a>
          </li>
          <li aria-hidden="true" class="text-slate-400">›</li>
          <li class="text-slate-700" aria-current="page">Unknown event</li>
        </ol>
      </nav>
      <h1 class="text-2xl font-semibold">Election not found</h1>
      <p class="text-sm text-slate-600">
        No election with id <code class="rounded bg-slate-100 px-1">{params.event}</code>
        is catalogued for {state_name}. See the
        <a href={url.stateTopic(state_code, "elections")} class="text-sky-700 hover:underline"
          >elections topic page</a
        >
        for the list of known events.
      </p>
    </div>
  {:else}
    {@const ev = event_row}
    <header class="space-y-2">
      <nav aria-label="Breadcrumb" class="text-xs text-slate-500">
        <ol class="flex items-center gap-1 list-none p-0 m-0">
          <li>
            <a href={url.state(state_code)} class="hover:text-sky-700 hover:underline">{state_name}</a>
          </li>
          <li aria-hidden="true" class="text-slate-400">›</li>
          <li>
            <a href={url.stateTopic(state_code, "elections")} class="hover:text-sky-700 hover:underline">Elections</a>
          </li>
          <li aria-hidden="true" class="text-slate-400">›</li>
          <li class="text-slate-700" aria-current="page">{ev.display}</li>
        </ol>
      </nav>
      <h1 class="text-2xl font-semibold">{ev.display}</h1>
      <p class="text-sm text-slate-600">
        {ev.kind === "assembly"
          ? `${state_name} Assembly election`
          : ev.kind === "lok_sabha"
            ? `Lok Sabha (national) election — ${state_name} slice`
            : `${state_name} by-election`}
        — polled {ev.polled_on}.
      </p>
    </header>

    <article
      class="rounded border border-slate-200 bg-white p-4 space-y-3"
      data-testid="state-election-card"
    >
      <dl class="grid sm:grid-cols-3 gap-3 text-sm">
        <div>
          <dt class="text-xs text-slate-500">Event</dt>
          <dd class="text-slate-900">{ev.display}</dd>
        </div>
        <div>
          <dt class="text-xs text-slate-500">Polled on</dt>
          <dd class="text-slate-900">{ev.polled_on}</dd>
        </div>
        <div>
          <dt class="text-xs text-slate-500">Data status</dt>
          <dd class="text-slate-900">
            {ev.data_status === "pending_upstream"
              ? "Awaiting publication by ECI"
              : ev.data_status === "partial"
                ? "Partial data on disk"
                : "Complete"}
          </dd>
        </div>
      </dl>
      {#if ev.notes}
        <p class="text-xs text-slate-500">{ev.notes}</p>
      {/if}
    </article>

    {#if ev.kind === "assembly"}
      <section class="space-y-2" data-testid="state-election-map">
        <h2 class="text-lg font-semibold">Results map</h2>
        <p class="text-xs text-slate-500">
          Switch between the geographic map and the equal-seats cartogram.
          Tap a constituency to open its detailed result.
        </p>
        <ElectionTimeSlider
          stops={slider_stops}
          selectedEventId={ev.event_id}
          onSelect={selectEvent}
        />
        <ElectionFilterRail
          {filters}
          parties={party_options}
          coverage={mode_coverage}
          onChange={onFilterChange}
        />
        <ElectionMap
          state={state_code}
          rows={ac_winners}
          event={ev.event_id}
          {filters}
        />
      </section>
    {/if}

    <nav class="flex flex-wrap gap-2 text-sm" aria-label="Election surfaces">
      <a
        href={url.lab(state_code, ev.event_id)}
        class="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sky-800 hover:bg-sky-100"
        data-testid="state-election-lab-link"
      >
        View constituency results →
      </a>
      <a
        href={url.compare(state_code, ev.event_id)}
        class="rounded border border-slate-200 bg-white px-3 py-2 text-slate-700 hover:bg-slate-50"
        data-testid="state-election-compare-link"
      >
        Compare across states →
      </a>
      <a
        href={url.state(state_code)}
        class="rounded border border-slate-200 bg-white px-3 py-2 text-slate-700 hover:bg-slate-50"
        data-testid="state-election-state-link"
      >
        See {state_name}'s other data →
      </a>
    </nav>
  {/if}
</section>
