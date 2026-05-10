<script lang="ts">
  import {
    fetchResultSummary, fetchConstituencies, fetchDistricts,
    type ResultSummary, type ConstituencyEntry, type DistrictEntry,
  } from "../lib/data";
  import PartyBar from "../lib/PartyBar.svelte";
  import SeatDonut from "../lib/SeatDonut.svelte";
  import MarginHistogram from "../lib/MarginHistogram.svelte";
  import SourceList from "../lib/SourceList.svelte";
  import StateAcMap from "../lib/maplibre/StateAcMap.svelte";
  import { STATE_AC } from "../lib/maplibre/sources";
  import { states } from "../lib/states.svelte";
  import { getDb } from "../lib/sql";
  import { colors } from "../lib/colors/store.svelte";
  import { url } from "../lib/url";

  interface Props { params: { state: string } }
  let { params }: Props = $props();

  const event = "AcGenMay2026";
  // params.state is a SLUG (or, for backwards compatibility, an ECI code).
  // Resolve via the reactive states store; null while loading or unknown.
  const state_code = $derived(states.codeFromSlug(params.state));

  let summary = $state<ResultSummary | null>(null);
  let acs = $state<ConstituencyEntry[] | null>(null);
  let districts = $state<DistrictEntry[] | null>(null);
  let error = $state<string | null>(null);

  // Per-AC winner & margin lookup. Loaded from results.sqlite (same DB the
  // map and histogram use; the lib/sql cache means this is a single fetch
  // shared across components on this page). Indexed by ac_eci_no so the
  // constituency list can render a coloured dot + margin badge inline.
  interface AcWinner {
    party_eci_code: string | null;
    party_short: string;
    margin_pct: number;
  }
  let winners = $state<Map<number, AcWinner>>(new Map());

  $effect(() => {
    summary = null;
    acs = null;
    districts = null;
    winners = new Map();
    error = null;
    const sc = state_code;
    if (!sc) return; // wait for slug → code resolution
    Promise.all([
      fetchResultSummary(event, sc),
      fetchConstituencies(sc),
      fetchDistricts(sc),
    ])
      .then(([s, c, d]) => { summary = s; acs = c.constituencies; districts = d.districts; })
      .catch(e => (error = String(e)));
    // Winners load is independent of the JSON fetches so the page renders
    // even if the SQLite is briefly unavailable -- the badges just stay
    // empty rather than blocking everything else.
    (async () => {
      try {
        if (!sc) return;
        const db = await getDb(event, sc);
        const sql = `
          SELECT c.ac_eci_no AS ac, w.party_eci_code, w.party_short,
                 100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0) AS margin_pct
          FROM constituencies c
          JOIN candidates w  ON w.ac_eci_no = c.ac_eci_no AND w.is_winner = 1
          JOIN candidates r2 ON r2.ac_eci_no = c.ac_eci_no AND r2.rank = 2 AND r2.is_nota = 0;
        `;
        const res = db.exec(sql);
        const m = new Map<number, AcWinner>();
        if (res[0]) for (const v of res[0].values) {
          m.set(v[0] as number, {
            party_eci_code: v[1] as string | null,
            party_short: v[2] as string,
            margin_pct: v[3] as number,
          });
        }
        if (state_code === sc) winners = m;
      } catch {
        // Non-fatal: list still renders without badges.
      }
    })();
  });

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
    if (!acs || !districts) return [];
    const q = ac_query.trim().toLowerCase();
    const filter = q
      ? (ac: ConstituencyEntry) =>
          ac.name.toLowerCase().includes(q) || String(ac.eci_no) === q
      : () => true;
    const name_by_id = new Map(districts.map(d => [d.id, d.name]));
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
    <h1 class="text-2xl font-bold">{states.name(state_code)} — Legislative Assembly, May 2026</h1>
    <p class="text-sm text-slate-500">
      Event <code class="font-mono">{event}</code> · State <code class="font-mono">{state_code ?? "…"}</code>
      · <a class="text-blue-600 hover:underline" href={state_code ? url.explore(state_code) : url.home()}>Data explorer →</a>
      · <a class="text-blue-600 hover:underline" href={state_code ? url.lab(state_code, event) : url.home()}>Psephlab →</a>
    </p>
  </header>

  {#if !state_code}
    <div class="text-slate-500">Resolving state …</div>
  {:else if error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load: <code>{error}</code>
    </div>
  {:else if !summary || !acs || !districts}
    <div class="text-slate-500">Loading…</div>
  {:else}
    <!-- Top row: map (3fr) + donut + key totals (2fr).
         At <lg the donut wraps below the map (single column). -->
    <section class="grid lg:grid-cols-[3fr_2fr] gap-6 items-start">
      {#if STATE_AC[state_code]}
        <div class="bg-white rounded-lg shadow-sm p-4 min-w-0">
          <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Constituency map</h2>
          <StateAcMap {event} state={state_code} />
          <p class="text-xs text-slate-400 mt-2">
            Hover for winner & margin · click an AC to drill in. Opacity ∝ margin of victory.
          </p>
        </div>
      {:else}
        <div></div>
      {/if}

      <div class="space-y-4 min-w-0">
        <div class="bg-white rounded-lg shadow-sm p-5">
          <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3 text-center">Seat share</h2>
          <SeatDonut
            parties={summary.party_totals}
            total_seats={summary.total_seats}
            {hidden_parties}
            onToggleHidden={toggleHidden}
          />
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 space-y-3">
          <!-- Three tiles instead of four. The previous fourth tile ("Schema 3.0")
               leaked an internal version into a user-facing KPI grid; provenance
               + schema now live in the on-demand <SourceList/> footer below. -->
          <div class="grid grid-cols-3 gap-3 text-sm">
            <div>
              <div class="text-[10px] uppercase tracking-wide text-slate-500">Total seats</div>
              <div class="text-lg font-semibold">{summary.total_seats}</div>
            </div>
            <div>
              <div class="text-[10px] uppercase tracking-wide text-slate-500">Votes polled</div>
              <div class="text-lg font-semibold">{summary.totals?.votes_polled?.toLocaleString() ?? "—"}</div>
            </div>
            <div>
              <div class="text-[10px] uppercase tracking-wide text-slate-500">Turnout</div>
              <div class="text-lg font-semibold">
                {summary.totals?.turnout_pct != null
                  ? `${summary.totals.turnout_pct.toFixed(1)}%`
                  : "—"}
              </div>
            </div>
          </div>
          <SourceList sources={summary.sources} schema_version={summary.$schema_version} />
        </div>
      </div>
    </section>

    <!-- Full-width seats-by-party bar (below the map row so wide bars
         have room to breathe and 0-seat parties remain readable). -->
    <section class="bg-white rounded-lg shadow-sm p-5">
      <div class="flex items-baseline justify-between mb-1 gap-2">
        <h2 class="text-sm font-semibold uppercase text-slate-500">Seats by party</h2>
        {#if hidden_parties.size > 0}
          <button
            class="text-xs text-blue-600 hover:underline"
            onclick={() => (hidden_parties = new Set())}
          >Show all ({hidden_parties.size} muted)</button>
        {/if}
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
      {#if zero_seat_count > 0}
        <div class="pt-3">
          <button
            class="text-xs text-blue-600 hover:underline"
            onclick={() => (show_zero_seat = !show_zero_seat)}
          >{show_zero_seat
              ? `Hide ${zero_seat_count} zero-seat parties`
              : `Show ${zero_seat_count} parties with no seats`}</button>
        </div>
      {/if}
    </section>

    <section class="bg-white rounded-lg shadow-sm p-5">
      <h2 class="text-sm font-semibold uppercase text-slate-500 mb-3">Margin of victory</h2>
      <MarginHistogram {event} state={state_code} />
    </section>

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
        <span class="inline-flex items-center gap-1.5">
          <span class="text-rose-600 font-mono">•</span>&lt; 5
          <span class="text-amber-600 font-mono ml-2">•</span>&lt; 10
          <span class="text-slate-400 font-mono ml-2">•</span>≥ 10
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
                        <span
                          class="ml-auto text-[10px] tabular-nums"
                          class:text-rose-600={w.margin_pct < 5}
                          class:text-amber-600={w.margin_pct >= 5 && w.margin_pct < 10}
                          class:text-slate-400={w.margin_pct >= 10}
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
</main>
