<script lang="ts">
  import {
    fetchConstituencies,
    type ConstituencyEntry,
  } from "../lib/data";
  import { loadDistricts, type District } from "../lib/view-models/districts";
  // PR-F (Phase 1.3b): StateOverview reads state-hub data through the
  // canonical Parquet store via DuckDB-WASM (view-models/state-overview.ts),
  // replacing the per-shard result.summary.json fetch. PR-G (Phase 1.3c)
  // migrated ElectionSeatsTrend, Settings, IndiaMap and the Party-page
  // summary side onto view-models too; `fetchResultSummary` is now deleted.
  // PR-H (Phase 1.3d) closed Party.svelte off `fetchParties`. PR-I (Phase
  // 1.4) extends the view-model with `ac_winners[]` so the per-AC badges +
  // MarginHistogram both consume canonical data — the page no longer fetches
  // `results.sqlite` for its own winners chunk (StateAcMap + RacesBoard
  // still do, migrating in Phase 1.5). Phase-0 closeout T.0c-ii-B.2 ports
  // the district list off `fetchDistricts` (legacy JSON) onto
  // `loadDistricts` (taxonomy.entities via DuckDB-WASM); the JSONs under
  // `datasets/reference/in/states/<S>/districts.json` remain on disk as
  // hand-authored curator input feeding `entities.parquet`.
  import {
    loadStateOverview,
    type StateOverviewViewModel,
  } from "../lib/view-models/state-overview";
  import type { LoaderResult } from "../lib/loader-result";
  import {
    fetchTopicCatalogue,
    indicatorPathForArtifact,
    type TopicCatalogue,
  } from "../lib/catalogue";
  import PartyBar from "../lib/PartyBar.svelte";
  import SeatDonut from "../lib/SeatDonut.svelte";
  import MarginHistogram from "../lib/MarginHistogram.svelte";
  import RacesBoard from "../lib/RacesBoard.svelte";
  import SourceList from "../lib/SourceList.svelte";
  import StateAcMap from "../lib/maplibre/StateAcMap.svelte";
  import IndicatorCard from "../lib/IndicatorCard.svelte";
  import ElectionSeatsTrend from "../lib/ElectionSeatsTrend.svelte";
  import { STATE_AC } from "../lib/maplibre/sources";
  import { states } from "../lib/states.svelte";
  import { colors } from "../lib/colors/store.svelte";
  import { url } from "../lib/url";
  import {
    fetchElectionEvents,
    defaultEventForState,
    listEventsForState,
    findEvent,
    daysSincePolled,
    type ElectionEventsCatalogue,
    type ElectionEventRow,
  } from "../lib/election-events";
  import {
    fetchGovernmentTimeline,
    currentTerm,
    type GovernmentTimeline,
    type GovernmentTerm,
  } from "../lib/governments";

  interface Props { params: { state: string } }
  let { params }: Props = $props();

  // Per-state event resolution (ADR-0023). The state-overview hub used to
  // hardcode `const event = "AcGenMay2026"`; that 404'd every state outside
  // the May-2026 cohort. The catalogue now drives per-state defaults, and
  // the election block degrades gracefully (showing the upstream-pending
  // copy or a "no election data ingested" notice) when no event row exists.
  let election_catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then(c => (election_catalogue = c))
    .catch(() => (election_catalogue = null));

  // params.state is a SLUG (or, for backwards compatibility, an ECI code).
  // Resolve via the reactive states store; null while loading or unknown.
  const state_code = $derived(states.codeFromSlug(params.state));

  // Per-state event picker. Citizen lands on the catalogue default (most
  // recent assembly election); switching the picker re-resolves every
  // election-scoped fetch (summary, winners, SQLite) without leaving the
  // hub. `selected_event_id` is reset whenever the state changes so a
  // selection in TN doesn't bleed into Kerala. The list is intentionally
  // hidden when there is only one event for this state.
  let selected_event_id = $state<string | null>(null);
  const all_events = $derived<ElectionEventRow[]>(
    listEventsForState(election_catalogue, state_code),
  );
  const default_event_row = $derived<ElectionEventRow | null>(
    defaultEventForState(election_catalogue, state_code),
  );
  const event_row = $derived<ElectionEventRow | null>(
    (selected_event_id
      ? findEvent(election_catalogue, state_code, selected_event_id)
      : null) ?? default_event_row,
  );
  const event = $derived(event_row?.event_id ?? null);
  const event_status = $derived(event_row?.data_status ?? null);

  // Reset the picker when the state changes so cross-state navigation
  // never carries a now-invalid event_id.
  $effect(() => {
    void state_code;
    selected_event_id = null;
  });
  const days_since_poll = $derived(event_row ? daysSincePolled(event_row) : null);
  const is_news_cycle = $derived(
    days_since_poll !== null && days_since_poll >= 0 && days_since_poll < 90,
  );

  // Government timeline (ADR-0023 §3) — primary citizen anchor for "who
  // governs this state right now". Loads in parallel with the catalogue;
  // null when the per-state file is not yet authored (graceful degradation).
  let government = $state<GovernmentTimeline | null>(null);
  $effect(() => {
    government = null;
    const sc = state_code;
    if (!sc) return;
    fetchGovernmentTimeline(sc)
      .then(t => { if (state_code === sc) government = t; })
      .catch(() => { /* non-fatal — card just hides */ });
  });
  const cur_term = $derived<GovernmentTerm | null>(currentTerm(government));

  // Four-arm LoaderResult from the canonical view-model loader. `summary` is
  // a thin $derived that exposes `.data` on the `ok` arm only, so the
  // downstream renderer (PartyBar, SeatDonut, KPI tiles, party directory)
  // continues to read the same shape it always did. partial/failed/loading
  // get their own render arms below.
  let summaryResult = $state<LoaderResult<StateOverviewViewModel>>({ status: "loading" });
  const summary = $derived(summaryResult.status === "ok" ? summaryResult.data : null);
  let acs = $state<ConstituencyEntry[] | null>(null);
  let districts = $state<District[] | null>(null);
  let catalogue = $state<TopicCatalogue | null>(null);

  // Indicator sections on the state hub are now data-driven (P2.4 of the
  // IA reset, ADR-0022): each topic in the catalogue that ships at least
  // one `kind: "indicator"` artifact renders as a section in catalogue
  // order. The closed renderer set (IndicatorChoropleth/Ranked/SmallMultiples)
  // is reused unchanged — no per-topic bespoke chrome (per
  // docs/concepts/schema-is-the-design-system.md). Election artifacts in the
  // catalogue are intentionally skipped here; they're rendered by the
  // election-specific sections above (different renderer family).
  const indicator_topics = $derived(
    (catalogue?.topics ?? []).filter(t =>
      t.artifacts.some(a => a.kind === "indicator"),
    ),
  );

  fetchTopicCatalogue()
    .then(c => (catalogue = c))
    .catch(() => (catalogue = null));

  // Per-AC winner & margin lookup. Comes from the view-model loader (PR-I,
  // Phase 1.4) — `summary.ac_winners` is assembled from `ac-winner-party-id`
  // + `ac-margin-pct` observations JOINed to dim_acs + dim_parties. The
  // Map<eci_no, AcWinner> shape is preserved so the constituency list
  // template (line ~770) can stay unchanged.
  interface AcWinner {
    party_eci_code: string | null;
    party_short: string;
    margin_pct: number;
  }

  $effect(() => {
    summaryResult = { status: "loading" };
    acs = null;
    districts = null;
    const sc = state_code;
    const ev = event;
    if (!sc) return; // wait for slug → code resolution
    // Constituencies + districts are reference data and load even when the
    // state has no election data on disk yet (so the AC directory still
    // renders). The election summary is only fetched when we have an event.
    // Reference-data 404s are non-fatal: the AC directory simply won't render
    // for states whose reference files haven't been built yet (e.g. recently
    // ingested states). Government card + indicator sections still appear.
    if (ev && event_status !== "pending_upstream") {
      loadStateOverview(ev, sc).then(r => {
        if (state_code === sc && event === ev) summaryResult = r;
      });
    } else {
      // No election event for this state, or upstream is still pending.
      // Mark as partial/not_published so the renderer falls through to the
      // existing pending-upstream notice rather than spinning forever.
      summaryResult = {
        status: "partial",
        data: {
          election: ev ?? "",
          state: sc,
          total_seats: 0,
          totals: null,
          party_totals: [],
          ac_winners: [],
          sources: [],
        },
        reason: "not_published",
      };
    }
    const acs_p = fetchConstituencies(sc).then(c => c.constituencies).catch(() => null);
    const districts_p = loadDistricts(sc).catch(() => null);
    Promise.all([acs_p, districts_p])
      .then(([c, d]) => { acs = c; districts = d; });
  });

  // Map<eci_no, AcWinner> derived from the view-model. Keeps the template
  // lookup `winners.get(ac.eci_no)` unchanged; empty for events with no
  // per-AC observations (older cohorts) or while the loader is in flight.
  const winners = $derived.by<Map<number, AcWinner>>(() => {
    const m = new Map<number, AcWinner>();
    if (!summary) return m;
    for (const w of summary.ac_winners) {
      m.set(w.ac_eci_no, {
        party_eci_code: w.party_eci_code,
        party_short: w.party_short,
        margin_pct: w.margin_pct,
      });
    }
    return m;
  });

  // Retry callable for the failed arm (PR-E pattern). Captures current
  // event + state_code at click-time; re-invokes the loader and re-routes
  // the result back into summaryResult.
  function retryStateLoad(): void {
    const sc = state_code;
    const ev = event;
    if (!sc || !ev) return;
    summaryResult = { status: "loading" };
    loadStateOverview(ev, sc).then(r => {
      if (state_code === sc && event === ev) summaryResult = r;
    });
  }

  // Show every party from the actuals — no threshold. Earlier the bar
  // dropped parties with no seats AND <1% vote share, which silently
  // erased fringe-but-noisy parties (e.g. TVK in TN). The deselect
  // mechanism (Phase 2) lets users mute parties they don't care about.
  const ranked_parties = $derived(
    summary
      ? [...summary.party_totals].sort(
          (a, b) =>
            b.seats_won - a.seats_won ||
            b.vote_share_pct - a.vote_share_pct ||
            a.party_short.localeCompare(b.party_short),
        )
      : []
  );

  // Seats-by-party defaults to "winners only". A typical state has 7-10
  // seat-winning parties and 20+ that contested without winning anything;
  // showing all 30 floods the chart with zero-length bars and pushes the
  // signal off the screen. Zero-seat parties remain reachable via the
  // dedicated "All parties" directory below, and via this toggle.
  let show_zero_seat = $state(false);
  const winners_count = $derived(
    ranked_parties.filter(p => p.seats_won > 0).length,
  );
  const zero_seat_count = $derived(ranked_parties.length - winners_count);
  const visible_parties = $derived(
    show_zero_seat ? ranked_parties : ranked_parties.filter(p => p.seats_won > 0),
  );

  // ----- Phase 2: search + deselect -----
  //
  // `hidden_parties` keys are `party_eci_code ?? party_short` — same
  // convention used by PartyBar / SeatDonut / ParliamentArc props. Hiding
  // is purely visual; per spec we DON'T recompute seats or vote share.
  let hidden_parties = $state<Set<string>>(new Set());

  function toggleHidden(key: string): void {
    const next = new Set(hidden_parties);
    if (next.has(key)) next.delete(key); else next.add(key);
    hidden_parties = next;
  }

  // Reset the mute set whenever the loaded state changes — otherwise muting
  // "TVK" in TN would still mute "TVK" after navigating to Kerala (where
  // the party may not even be on the ballot).
  $effect(() => {
    void state_code;
    hidden_parties = new Set();
  });

  let party_query = $state("");
  // Mirror seats-by-party: hide zero-seat parties by default. The directory
  // is the canonical place to see *all* parties that contested, but in
  // practice 60-70% of them won zero seats and never even appeared on a
  // chart, so the default view is winners-only with an explicit toggle.
  let show_zero_seat_directory = $state(false);
  let ac_query = $state("");

  const filtered_parties = $derived.by(() => {
    const q = party_query.trim().toLowerCase();
    if (!summary) return [];
    const base = show_zero_seat_directory
      ? summary.party_totals
      : summary.party_totals.filter(p => p.seats_won > 0);
    if (!q) return base;
    return base.filter(p =>
      p.party_short.toLowerCase().includes(q) ||
      (p.party_full ?? "").toLowerCase().includes(q) ||
      (p.party_eci_code ?? "").toLowerCase().includes(q),
    );
  });
  const directory_zero_seat_count = $derived(
    summary ? summary.party_totals.filter(p => p.seats_won === 0).length : 0,
  );

  // Group ACs by district_id, then sort districts by AC count (descending).
  // ACs without a district_id fall under a synthetic '—' bucket so the count
  // surface is honest rather than silently dropping rows. When `ac_query`
  // is set, ACs are filtered by case-insensitive match on name OR by exact
  // eci_no string match; districts with zero matches are dropped from the
  // listing entirely.
  const by_district = $derived.by(() => {
    if (!acs) return [];
    const q = ac_query.trim().toLowerCase();
    const filter = q
      ? (ac: ConstituencyEntry) =>
          ac.name.toLowerCase().includes(q) || String(ac.eci_no) === q
      : () => true;
    const name_by_id = new Map((districts ?? []).map(d => [d.id, d.name]));
    const groups = new Map<string, ConstituencyEntry[]>();
    for (const ac of acs) {
      if (!filter(ac)) continue;
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

  const total_filtered_acs = $derived(
    by_district.reduce((s, g) => s + g.acs.length, 0),
  );
</script>

<main class="max-w-screen-2xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <p class="text-xs"><a class="text-slate-500 hover:underline" href={url.home()}>← All states</a></p>
    <h1 class="text-2xl font-bold leading-tight">{states.name(state_code)}</h1>
    <p class="text-sm text-slate-600">
      {#if event_row}
        {selected_event_id ? "Election" : "Most recent assembly election"}: {event_row.display}.
      {:else if state_code}
        No assembly election data ingested yet for this state.
      {/if}
      <span class="text-slate-400 ml-1">
        State <code class="font-mono">{state_code ?? "…"}</code>
        {#if event}· event <code class="font-mono">{event}</code>{/if}
      </span>
      {#if state_code}
        · <a class="text-blue-600 hover:underline" href={url.explore(state_code)}>Data explorer →</a>
        {#if event}
          · <a class="text-blue-600 hover:underline" href={url.lab(state_code, event)}>Psephlab →</a>
        {/if}
      {/if}
    </p>
    {#if all_events.length > 1}
      <p class="text-xs text-slate-600 flex items-center gap-2 pt-1">
        <label for="event-picker" class="font-medium text-slate-700">Election:</label>
        <select
          id="event-picker"
          class="border border-slate-300 rounded px-2 py-0.5 text-xs bg-white"
          bind:value={selected_event_id}
        >
          {#each all_events as row (row.event_id)}
            <option value={row.event_id}>
              {row.display}{row === default_event_row ? " (latest)" : ""}
            </option>
          {/each}
        </select>
        <span class="text-slate-400">{all_events.length} elections on record</span>
      </p>
    {/if}
  </header>

  {#if !state_code}
    <div class="text-slate-500">Resolving state …</div>
  {:else}
    <!-- Recency banner (ADR-0023 §3 recency rule). When polling closed
         within the last 90 days, the citizen wants to know about the
         election first; otherwise the government card leads. -->
    {#if is_news_cycle && event_row}
      <section class="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-900">
        <strong class="font-semibold">Latest:</strong>
        {event_row.display} — polled {days_since_poll} day{days_since_poll === 1 ? "" : "s"} ago.
      </section>
    {/if}

    <!-- "Your government" card (ADR-0023 §3). Anchors the page on the
         continuing condition (who governs right now) rather than the
         discrete event that produced it. Degrades to a one-line caption
         when no cm_terms.json file exists for this state yet. -->
    {#if cur_term}
      <section class="bg-white rounded-lg shadow-sm ring-1 ring-slate-200/70 p-4 space-y-2">
        <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Your government</h2>
        {#if cur_term.regime === "elected"}
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span class="text-lg font-semibold text-slate-800">{cur_term.cm_name ?? "—"}</span>
            <span class="text-sm text-slate-600">Chief Minister</span>
            {#if cur_term.alliance}
              <span class="text-sm text-slate-500">· {cur_term.alliance}</span>
            {/if}
          </div>
          <p class="text-xs text-slate-500">
            In office since {cur_term.start}. Government is an elected ministry.
          </p>
        {:else if cur_term.regime === "presidents_rule"}
          <div class="text-base font-semibold text-amber-800">President's Rule</div>
          <p class="text-xs text-slate-600">
            In effect since {cur_term.start}. The state is administered by the
            Governor under Article 356; the Legislative Assembly is dissolved
            or suspended. {cur_term.notes ?? ""}
          </p>
        {:else if cur_term.regime === "governors_rule"}
          <div class="text-base font-semibold text-amber-800">Governor's Rule</div>
          <p class="text-xs text-slate-600">
            In effect since {cur_term.start}. {cur_term.notes ?? ""}
          </p>
        {:else}
          <div class="text-base font-semibold text-slate-700">Caretaker / interim government</div>
          <p class="text-xs text-slate-600">
            In effect since {cur_term.start}. {cur_term.notes ?? ""}
          </p>
        {/if}
      </section>
    {:else if government === null && state_code}
      <!-- Timeline file not yet authored for this state. Honest one-liner
           rather than silently omitting the card. The government schema is
           v1.0 and the file path is documented in
           docs/concepts/government-vs-election.md so a contributor can fill
           it in without reverse-engineering anything. -->
      <section class="text-xs text-slate-400 italic">
        Government timeline coming soon for {states.name(state_code)}.
      </section>
    {/if}
    <!-- Indicator sections — catalogue-driven, lead the page (P2 commit B
         of IA reset, ADR-0022 §Doctrine). Welfare topics (fiscal first,
         then energy) come BEFORE the election bundle because elections
         are one indicator family among many, not the spine.

         Step #1 of TODO/20260515-state-page-ia-rework-plan.md (the IA
         rework): the per-artifact India choropleth + ranked table +
         small-multiples trio has been replaced with one IndicatorCard
         per artifact. A citizen on /s/<state> is asking "how is MY
         state doing?", not "where does it rank on a map of India?" —
         the card answers that directly (big number + sparkline +
         one-line rank + "See all states →" link to /t/<topic>). The
         triple-render components remain in use on /t/<topic> and
         /compare where the cross-state question IS the right one.
         PeerSetFilter is dropped from this surface because there is no
         visible India view to constrain on /s/<state>; the picker is
         meaningful on /t/<topic>, one click away.

         Election artifacts in the catalogue are intentionally skipped
         here — the existing election-only renderer family below handles
         them. A future refactor (P3+) can collapse the election block
         into a single catalogue dispatch slot of its own; until then
         this single move is what the doctrine actually requires:
         welfare visible first. -->
    {#each indicator_topics as topic (topic.id)}
      <section class="space-y-3">
        <h2 class="text-sm font-semibold uppercase text-slate-500">{topic.title}</h2>
        <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {#each topic.artifacts.filter(a => a.kind === "indicator") as artifact (artifact.id)}
            {@const path = indicatorPathForArtifact(artifact)}
            {#if path}
              <IndicatorCard
                {topic}
                {artifact}
                indicator_path={path}
                home_state={state_code}
              />
            {/if}
          {/each}
        </div>
      </section>
    {/each}

    <!-- Election sections — preserved unchanged in capability and layout,
         but no longer the page's lead. Per ADR-0023 these are gated on
         the per-state event row: states with `data_status: pending_upstream`
         get an honest "awaiting publication" notice; states with no row at
         all (no election data ingested) skip the block entirely. -->
    {#if event_status === "pending_upstream"}
      <section class="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-sm text-slate-700">
        <strong class="font-semibold">Election results awaiting publication.</strong>
        {#if event_row}
          {event_row.display} — polled {event_row.polled_on}.
        {/if}
        The Election Commission of India has not yet released the
        Statistical Report Section&nbsp;10 for this election (typical
        publication lag is 6–18 months). yen-gov ingests results from
        the official Statistical Reports rather than partial day-of
        feeds, so this page will populate as soon as ECI publishes.
      </section>
    {:else if event_row && summaryResult.status === "failed"}
      <!-- PR-F: failed arm — DuckDB-WASM / fetch / SQL error reading the
           canonical store. describeFailure() already mapped the raw error
           to citizen-readable copy; retry re-invokes loadStateOverview. -->
      <section class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900 text-sm space-y-2">
        <p>{summaryResult.reason}</p>
        <button
          class="text-xs underline hover:no-underline"
          onclick={retryStateLoad}
        >Retry</button>
      </section>
    {:else if event_row && summaryResult.status === "partial"}
      <!-- PR-F: partial arm — the cohort is not yet ingested into the
           canonical store. Honest "no data" notice; reference-data sections
           (indicator cards, government card, AC directory) above and below
           still render. -->
      <section class="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-sm text-slate-700">
        <strong class="font-semibold">Election results not yet in the canonical store.</strong>
        {#if event_row}
          {event_row.display} — polled {event_row.polled_on}.
        {/if}
        The pipeline has not yet ingested this cohort into the canonical
        Parquet store. The AC directory below still reflects the constituency
        reference file for this state.
      </section>
    {:else if event_row && summaryResult.status === "loading"}
      <div class="text-slate-500">Loading election data…</div>
    {:else if event_row && summary && !acs}
      <section class="bg-white rounded-lg shadow-sm p-6 text-sm text-slate-600">
        <p class="font-medium text-slate-700 mb-1">Election results loaded.</p>
        <p>
          Per-constituency directory for {event_row.display}
          isn't available yet — the constituencies reference file for this
          state still needs to be bootstrapped (run
          <code>python tools/bootstrap_constituencies_from_results.py {state_code}</code>).
        </p>
      </section>
    {:else if event_row && summary && acs}

    <!-- Top row: map (3fr) + donut + key totals (2fr).
         At <lg the donut wraps below the map (single column). -->
    <section class="grid lg:grid-cols-[3fr_2fr] gap-6 items-start">
      {#if event && STATE_AC[state_code]}
        <div class="bg-white rounded-lg shadow-sm p-4 min-w-0">
          <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Constituency map</h2>
          <StateAcMap state={state_code} rows={summary?.ac_winners ?? null} />
          <p class="text-xs text-slate-400 mt-2">
            Hover for winner & margin · click an AC to drill in. Darker fill = larger winning margin.
          </p>
        </div>
      {:else}
        <div></div>
      {/if}

      <div class="space-y-4 min-w-0">
        <!-- Donut card: subtle radial-tinted background so the chart has
             "presence" against the surrounding white cards instead of
             floating in a flat panel. -->
        <div class="rounded-xl shadow-sm p-5 ring-1 ring-slate-200/70 bg-[radial-gradient(ellipse_at_top,_rgba(248,250,252,1)_0%,_rgba(255,255,255,1)_60%)]">
          <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 mb-3 text-center">House composition</h2>
          <SeatDonut
            parties={summary.party_totals}
            total_seats={summary.total_seats}
            {hidden_parties}
            onToggleHidden={toggleHidden}
          />
        </div>
        <!-- KPI strip: three tiles. Numbers centered, single thin bottom
             border in slate. The previous coloured top accents (emerald /
             sky) added visual cost without conveying meaning — the values
             are doing the talking now. -->
        <div class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/70 p-4 space-y-3">
          <div class="grid grid-cols-3 gap-3">
            <div class="text-center px-3 py-2 border-b border-slate-200">
              <div class="text-[10px] uppercase tracking-[0.12em] text-slate-500">Total seats</div>
              <div class="text-2xl font-bold tabular-nums text-slate-800 mt-0.5">{summary.total_seats}</div>
            </div>
            <div class="text-center px-3 py-2 border-b border-slate-200">
              <div class="text-[10px] uppercase tracking-[0.12em] text-slate-500">Votes polled</div>
              <div class="text-2xl font-bold tabular-nums text-slate-800 mt-0.5">{summary.totals?.votes_polled?.toLocaleString() ?? "—"}</div>
            </div>
            <div class="text-center px-3 py-2 border-b border-slate-200">
              <div class="text-[10px] uppercase tracking-[0.12em] text-slate-500">Turnout</div>
              <div class="text-2xl font-bold tabular-nums text-slate-800 mt-0.5">
                {summary.totals?.turnout_pct != null
                  ? `${summary.totals.turnout_pct.toFixed(1)}%`
                  : "—"}
              </div>
            </div>
          </div>
          <SourceList sources={summary.sources} />
        </div>
      </div>
    </section>

    <!-- Full-width seats-by-party bar (below the map row so wide bars
         have room to breathe and 0-seat parties remain readable). -->
    <section class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/70 p-5">
      <div class="flex items-baseline justify-between mb-1 gap-2 flex-wrap">
        <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Seats by party</h2>
        <div class="flex items-center gap-3 flex-wrap">
          {#if zero_seat_count > 0}
            <button
              class="text-xs text-blue-600 hover:underline"
              onclick={() => (show_zero_seat = !show_zero_seat)}
            >{show_zero_seat
                ? `Hide ${zero_seat_count} zero-seat parties`
                : `Show ${zero_seat_count} parties with no seats`}</button>
          {/if}
          {#if hidden_parties.size > 0}
            <button
              class="text-xs text-blue-600 hover:underline"
              onclick={() => (hidden_parties = new Set())}
            >Show all ({hidden_parties.size} muted)</button>
          {/if}
        </div>
      </div>
      <p class="text-xs text-slate-500 mb-3">
        Bar length = seats won. Number in parentheses = vote share. Sorted by seats.
      </p>
      <PartyBar
        parties={visible_parties}
        total_seats={summary.total_seats}
        {hidden_parties}
        onToggleHidden={toggleHidden}
      />
    </section>

    {#if all_events.length > 1}
      <section class="bg-white rounded-lg shadow-sm p-5">
        <div class="flex items-baseline justify-between mb-1 gap-2 flex-wrap">
          <h2 class="text-sm font-semibold uppercase text-slate-500">Seat composition over time</h2>
          <span class="text-xs text-slate-400">{all_events.length} elections on record</span>
        </div>
        <p class="text-xs text-slate-500 mb-3">
          Each bar = one assembly election. Segment height = seats won by that party.
        </p>
        <ElectionSeatsTrend state_code={state_code} value="seats_won" />
      </section>
    {/if}

    {#if event}
      <section class="bg-white rounded-lg shadow-sm p-5">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Margin of victory</h2>
        <MarginHistogram rows={summary?.ac_winners ?? null} />
      </section>

      <!-- Races by competitiveness. Same per-AC margin data as the
           histogram, viewed as a NYT-style "All races" board: one column
           per top-3 winning party (their easy wins), then narrow wins,
           smaller-party wins, and a most-competitive column. The relative
           column heights are themselves the headline. -->
      <section class="bg-white rounded-lg shadow-sm p-5">
        <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Races by competitiveness</h2>
        <RacesBoard state={state_code} rows={summary?.ac_winners ?? null} />
      </section>
    {/if}

    <section class="bg-white rounded-lg shadow-sm p-5">
      <div class="flex justify-between items-baseline mb-1 gap-3 flex-wrap">
        <h2 class="text-sm font-semibold uppercase text-slate-500">All parties · directory</h2>
        <div class="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search parties…"
            bind:value={party_query}
            class="text-xs rounded border-slate-300 py-1 px-2 w-48"
            aria-label="Search parties by name or ECI code"
          />
          <span class="text-xs text-slate-400">
            {filtered_parties.length} / {summary.party_totals.length}
          </span>
        </div>
      </div>
      <p class="text-xs text-slate-500 mb-3">
        Every party that contested. Click a name to open its party page.
      </p>
      {#if filtered_parties.length === 0}
        <p class="text-sm text-slate-500 italic">No parties match <code>{party_query}</code>.</p>
      {:else}
        <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm">
          {#each filtered_parties as p}
            {#if p.party_eci_code}
              <li>
                <a class="hover:underline" href={url.party(state_code, p.party_eci_code, p.party_short)}>
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
      {/if}
      {#if directory_zero_seat_count > 0}
        <div class="pt-3">
          <button
            class="text-xs text-blue-600 hover:underline"
            onclick={() => (show_zero_seat_directory = !show_zero_seat_directory)}
          >{show_zero_seat_directory
              ? `Hide ${directory_zero_seat_count} zero-seat parties`
              : `Show ${directory_zero_seat_count} parties with no seats`}</button>
        </div>
      {/if}
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <div class="flex justify-between items-baseline mb-1 gap-3 flex-wrap">
        <h2 class="text-sm font-semibold uppercase text-slate-500">Constituencies by district</h2>
        <div class="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search ACs (name or no.)…"
            bind:value={ac_query}
            class="text-xs rounded border-slate-300 py-1 px-2 w-56"
            aria-label="Search constituencies by name or AC number"
          />
          <span class="text-xs text-slate-400">
            {by_district.length} district{by_district.length === 1 ? "" : "s"} · {total_filtered_acs} / {acs.length} ACs
          </span>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 mb-3">
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-block w-2.5 h-2.5 rounded-sm bg-slate-400"></span>
          coloured square = winning party
        </span>
        <span class="inline-flex items-center gap-1.5">
          <span class="font-mono tabular-nums">12.3</span>
          right number = winner's lead in percentage points
        </span>
        <!-- Margin-of-victory bands. Colors picked from ColorBrewer's
             RdYlBu sequential scheme (CB-safe across protanopia /
             deuteranopia / tritanopia). The previous rose/amber pair was
             too close in lightness for protanopic viewers. Larger 8-px
             swatches replace the tiny dots. -->
        <span class="inline-flex items-center gap-1.5">
          <span class="inline-block w-2.5 h-2.5 rounded-sm" style:background-color="#d7191c"></span>nail-biter (&lt; 5)
          <span class="inline-block w-2.5 h-2.5 rounded-sm ml-2" style:background-color="#fdae61"></span>contestable (&lt; 10)
          <span class="inline-block w-2.5 h-2.5 rounded-sm ml-2" style:background-color="#2c7bb6"></span>comfortable (≥ 10)
        </span>
      </div>
      {#if by_district.length === 0}
        <p class="text-sm text-slate-500 italic">No constituencies match <code>{ac_query}</code>.</p>
      {:else}
        <div class="space-y-4">
          {#each by_district as g}
            <div>
              <div class="flex items-baseline justify-between border-b border-slate-200 pb-1 mb-2">
                <h3 class="text-sm font-semibold">{g.name}</h3>
                <span class="text-xs text-slate-400 font-mono">{g.id || "—"} · {g.acs.length}</span>
              </div>
              <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm font-mono">
                {#each g.acs as ac}
                  {@const w = winners.get(ac.eci_no)}
                  <li>
                    <a class="hover:underline flex items-center gap-1.5" href={url.ac(state_code, ac.eci_no, ac.name)}>
                      <span class="text-slate-400 inline-block w-8 text-right pr-1">{ac.eci_no}</span>
                      {#if w}
                        <span
                          class="inline-block w-2 h-2 rounded-sm flex-shrink-0"
                          style:background-color={colors.fill(w.party_eci_code, w.party_short)}
                          title={`${w.party_short} · ${w.margin_pct.toFixed(1)} pt margin`}
                        ></span>
                      {:else}
                        <span class="inline-block w-2 h-2 flex-shrink-0"></span>
                      {/if}
                      <span class="truncate">{ac.name}</span>
                      {#if ac.reservation !== "GEN"}
                        <span class="text-xs text-rose-600">[{ac.reservation}]</span>
                      {/if}
                      {#if w}
                        <!-- Margin colour follows the same RdYlBu band as
                             the legend above (red < 5, orange < 10, blue
                             ≥ 10). Inline hex so the per-row swatch and
                             the legend chip can never drift apart. -->
                        {@const mc = w.margin_pct < 5 ? "#d7191c" : w.margin_pct < 10 ? "#fdae61" : "#2c7bb6"}
                        <span
                          class="ml-auto text-[10px] tabular-nums font-semibold"
                          style:color={mc}
                          title="Winner's margin (% of votes polled)"
                        >{w.margin_pct.toFixed(1)}</span>
                      {/if}
                    </a>
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        </div>
      {/if}
    </section>
    {/if}
  {/if}
</main>
