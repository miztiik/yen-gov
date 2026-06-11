<script lang="ts">
  // ElectionsFirehose - new top-level firehose route for the election
  // experience overhaul plan PR-W3d (2026-06-10).
  //
  // Surface: `/t/elections` (route registered in main.ts BEFORE the
  // parameterised `/t/elections/:event` so first-match-wins resolves the
  // bare path to this firehose, not to a `:event = ""` accident).
  //
  // What it lists: EVERY election event in
  // `datasets/taxonomy/election_events.json` - 6 unique Parliament
  // event_ids (1999/2004/2009/2014/2019/2024) collapsed to one "All
  // India" row each, plus 303 per-state Assembly events and 1 bye
  // election, for a current row count near 310.
  //
  // Row spine (always rendered immediately):
  //   Year | Body chip | State (or "All India") | Display | arrow
  //
  // Derived cells (lazy-hydrated to keep the initial render snappy):
  //   Leading party pill | Seats won/total | Turnout % | Runners-up
  //
  // Hydration strategy:
  //   - Parliament rows (6): auto-hydrate on mount. Each row is one
  //     NATIONAL-PC loader call (~543 PCs scanned via DuckDB-WASM).
  //   - Assembly rows (303): lazy-hydrate via IntersectionObserver as
  //     rows scroll into view. Each row is one STATE-AC loader call
  //     (~200-400 ACs scanned per state). Rate-limited to a small
  //     promise pool so we don't fire 100+ DuckDB queries at once.
  //   - Bye rows: skipped (data_status === "pending_upstream"; no
  //     summary.csv on disk yet).
  //
  // Click semantics:
  //   - Parliament row -> /t/elections/<event-slug> (NationalElection)
  //   - Assembly / bye row -> /<state>/elections/<event-slug>
  //     (StateElection)
  //
  // The whole row is an anchor (<a>) so middle-click / cmd-click opens
  // in a new tab; the router intercepts the regular click for SPA
  // navigation.

  import {
    fetchElectionEvents,
    type ElectionEventRow,
    type ElectionEventsCatalogue,
    type EventKind,
    type DataStatus,
  } from "../lib/election-events";
  import {
    loadElectionResults,
    type ElectionResultRow,
  } from "../lib/view-models/election-results";
  import { states } from "../lib/states.svelte";
  import { link } from "../lib/links";
  import {
    getPartyColor,
    type PartyRowForResolver,
  } from "../lib/colors/resolver";

  // ---- Row + hydration types ------------------------------------------
  type BodyFilter = "all" | "parliament" | "assembly" | "bye";
  type SortDir = "asc" | "desc";
  // `has-data` hides rows the catalogue knows have no per-event files
  // (data_status === "pending_upstream"); `all` shows them with a calm
  // slate "Pending" badge. Default `has-data` keeps the firehose useful
  // even when 272 of 513 catalogue rows are not yet ingested.
  type AvailabilityFilter = "has-data" | "all";

  interface PartyInfo {
    party_id: string;
    short: string;
    color: string;
  }

  type HydrationState =
    | { status: "idle" }
    | { status: "loading" }
    | {
        status: "ok";
        leading: PartyInfo | null;
        seats_won: number;
        seats_total: number;
        turnout_pct: number | null;
        runners_up: PartyInfo[];
      }
    | { status: "skipped"; reason: string }
    // "pending" = catalogue says no per-event files yet; we never
    // attempted a fetch. Renders a slate "Pending" badge.
    | { status: "pending"; reason: string }
    // "failed" = catalogue said complete but the fetch failed. This is
    // the genuine-bug arm; renders an amber "error" badge.
    | { status: "failed"; reason: string };

  interface FirehoseRow {
    row_id: string; // testid suffix - unique across all rows
    event_id: string;
    state_code: string | null; // null = collapsed national Parliament row
    state_label: string; // "All India" or resolved state name
    state_slug: string | null; // slug for stateHub link; null for national
    kind: EventKind;
    display: string;
    polled_on: string; // ISO date
    data_status: DataStatus | null;
  }

  // ---- Catalogue load + row build -------------------------------------
  let catalogue = $state<ElectionEventsCatalogue | null>(null);
  let catalogue_err = $state<string | null>(null);
  fetchElectionEvents()
    .then((c) => (catalogue = c))
    .catch((e: unknown) => {
      catalogue_err = e instanceof Error ? e.message : String(e);
    });

  // Build the row spine. Parliament events collapse to ONE row per
  // event_id ("All India"); Assembly + bye events keep per-state
  // granularity. The collapse is keyed on event_id alone because
  // Parliament rows in the catalogue carry the same event_id across
  // every state slice (verified in data: 6 unique general-* event_ids
  // across 209 state rows).
  const all_rows = $derived.by<FirehoseRow[]>(() => {
    if (!catalogue) return [];
    const seen_parliament = new Set<string>();
    const out: FirehoseRow[] = [];
    for (const state_code of Object.keys(catalogue.states)) {
      const state_name = states.name(state_code) || state_code;
      const state_slug = states.slug(state_code) || state_code.toLowerCase();
      for (const ev of catalogue.states[state_code] ?? []) {
        if (ev.kind === "parliament") {
          if (seen_parliament.has(ev.event_id)) continue;
          seen_parliament.add(ev.event_id);
          out.push({
            row_id: ev.event_id,
            event_id: ev.event_id,
            state_code: null,
            state_label: "All India",
            state_slug: null,
            kind: ev.kind,
            display: prettyNationalDisplay(ev),
            polled_on: ev.polled_on,
            data_status: ev.data_status ?? null,
          });
        } else {
          // Include polled_on in the row_id so re-elections (legitimate
          // historical data: e.g. Bihar 2005 had two assembly elections
          // because the Feb hung result was re-polled in Oct) get
          // disambiguated keys. Without polled_on, S04+assembly-2005
          // produces two rows with the same row_id and Svelte 5 fires
          // each_key_duplicate.
          out.push({
            row_id: `${state_code}-${ev.event_id}-${ev.polled_on}`,
            event_id: ev.event_id,
            state_code,
            state_label: state_name,
            state_slug,
            kind: ev.kind,
            display: ev.display,
            polled_on: ev.polled_on,
            data_status: ev.data_status ?? null,
          });
        }
      }
    }
    return out;
  });

  // Rewrite the per-state "Tamil Nadu - Parliament 2024" display into a
  // national "Parliament Election 2024" string since the collapse hides
  // the state qualifier. Falls back to the catalogue display verbatim
  // for non-standard slugs.
  function prettyNationalDisplay(ev: ElectionEventRow): string {
    const m = /^general-(\d{4})$/.exec(ev.event_id);
    if (m) return `Parliament Election ${m[1]}`;
    return ev.display;
  }

  // ---- Filter + sort --------------------------------------------------
  let body_filter = $state<BodyFilter>("all");
  let availability_filter = $state<AvailabilityFilter>("has-data");
  let sort_dir = $state<SortDir>("desc");

  const filtered_rows = $derived.by<FirehoseRow[]>(() => {
    const want_kind = (k: EventKind): boolean => {
      switch (body_filter) {
        case "all":
          return true;
        case "parliament":
          return k === "parliament";
        case "assembly":
          return k === "assembly";
        case "bye":
          return (
            k === "assembly_bye" ||
            k === "general_bye" ||
            k === "by_election"
          );
      }
    };
    const want_availability = (r: FirehoseRow): boolean => {
      if (availability_filter === "all") return true;
      return r.data_status !== "pending_upstream";
    };
    const filt = all_rows.filter((r) => want_kind(r.kind) && want_availability(r));
    // polled_on is ISO YYYY-MM-DD; lexicographic compare == chronological.
    const sorted = [...filt].sort((a, b) =>
      sort_dir === "desc"
        ? b.polled_on.localeCompare(a.polled_on)
        : a.polled_on.localeCompare(b.polled_on),
    );
    return sorted;
  });

  // Count of pending rows in scope of the current body filter so the
  // "Show pending" toggle can be honest about how many extra rows it
  // would surface.
  const pending_in_scope_count = $derived.by<number>(() => {
    const want_kind = (k: EventKind): boolean => {
      switch (body_filter) {
        case "all":
          return true;
        case "parliament":
          return k === "parliament";
        case "assembly":
          return k === "assembly";
        case "bye":
          return (
            k === "assembly_bye" ||
            k === "general_bye" ||
            k === "by_election"
          );
      }
    };
    return all_rows.filter(
      (r) => want_kind(r.kind) && r.data_status === "pending_upstream",
    ).length;
  });

  function toggleSort(): void {
    sort_dir = sort_dir === "desc" ? "asc" : "desc";
  }

  // ---- Hydration cache + concurrency-limited fetcher ------------------
  //
  // The cache is keyed by row_id so a row that has already hydrated stays
  // hydrated across filter / sort changes. Map values are reactive
  // because we re-assign the Map reference on every put; consumers read
  // via `hydration_state.get(row.row_id)` inside a $derived.

  let hydration_state = $state<Map<string, HydrationState>>(new Map());

  function getHydration(row_id: string): HydrationState {
    return hydration_state.get(row_id) ?? { status: "idle" };
  }

  function setHydration(row_id: string, h: HydrationState): void {
    const next = new Map(hydration_state);
    next.set(row_id, h);
    hydration_state = next;
  }

  // A tiny promise pool so we don't fire all 303 Assembly loaders the
  // instant the user scrolls; 4 concurrent DuckDB-WASM queries is the
  // empirical sweet spot on mid-tier mobile (citizen-target per
  // CLAUDE.md).
  const MAX_CONCURRENT = 4;
  let in_flight = 0;
  const pending: (() => Promise<void>)[] = [];

  function enqueue(task: () => Promise<void>): void {
    pending.push(task);
    pump();
  }

  function pump(): void {
    while (in_flight < MAX_CONCURRENT && pending.length > 0) {
      const t = pending.shift()!;
      in_flight++;
      void t().finally(() => {
        in_flight--;
        pump();
      });
    }
  }

  async function hydrateRow(row: FirehoseRow): Promise<void> {
    const current = getHydration(row.row_id);
    if (current.status !== "idle") return;
    // Catalogue declares this event has no per-event files on disk
    // yet (data_status === "pending_upstream"). Skip the fetch
    // entirely so the citizen sees a calm "Pending" badge instead of
    // an amber "error" badge from the inevitable 404. The honesty
    // tool `tools.election_events_honesty` is the single writer that
    // marks rows pending_upstream based on on-disk truth.
    if (row.data_status === "pending_upstream") {
      setHydration(row.row_id, {
        status: "pending",
        reason: "catalogue: pending_upstream (no per-event files on disk)",
      });
      return;
    }
    // Bye-election rows have no on-disk results today; skip cleanly.
    // (The catalogue should already mark these pending_upstream; this
    // guard is a defence-in-depth backstop for any future bye row that
    // slips through with data_status:complete.)
    if (
      row.kind === "assembly_bye" ||
      row.kind === "general_bye" ||
      row.kind === "by_election"
    ) {
      setHydration(row.row_id, {
        status: "skipped",
        reason: "bye election - results not on disk",
      });
      return;
    }
    setHydration(row.row_id, { status: "loading" });
    enqueue(async () => {
      try {
        const scope =
          row.state_code === null
            ? { event: row.event_id }
            : { event: row.event_id, state: row.state_code };
        const result = await loadElectionResults(scope);
        if (result.status === "failed") {
          setHydration(row.row_id, {
            status: "failed",
            reason: result.reason,
          });
          return;
        }
        const rows: ElectionResultRow[] =
          result.status === "ok" || result.status === "partial"
            ? result.data
            : [];
        if (rows.length === 0) {
          setHydration(row.row_id, {
            status: "skipped",
            reason: "no rows on disk",
          });
          return;
        }
        setHydration(row.row_id, summarise(rows));
      } catch (err) {
        setHydration(row.row_id, {
          status: "failed",
          reason: err instanceof Error ? err.message : String(err),
        });
      }
    });
  }

  // Aggregate the loader's winner rows into the firehose row's derived
  // cells: leading party + seats won/total + average turnout +
  // top-2 runners up.
  function summarise(rows: ElectionResultRow[]): HydrationState {
    const by_party = new Map<
      string,
      { seats: number; sample: ElectionResultRow }
    >();
    let turnout_sum = 0;
    let turnout_known = 0;
    for (const w of rows) {
      const pid = partyIdFor(w);
      const cur = by_party.get(pid);
      if (cur) {
        cur.seats += 1;
      } else {
        by_party.set(pid, { seats: 1, sample: w });
      }
      if (w.turnout_pct != null) {
        turnout_sum += w.turnout_pct;
        turnout_known += 1;
      }
    }
    const ranked = [...by_party.entries()]
      .sort(([, a], [, b]) => b.seats - a.seats)
      .map(([pid, entry]) => ({
        party_id: pid,
        short: entry.sample.party_short ?? "UNK",
        color: fillForParty(pid, entry.sample),
        seats: entry.seats,
      }));
    const leader = ranked[0];
    const runners = ranked.slice(1, 3).map((p) => ({
      party_id: p.party_id,
      short: p.short,
      color: p.color,
    }));
    return {
      status: "ok",
      leading:
        leader == null
          ? null
          : {
              party_id: leader.party_id,
              short: leader.short,
              color: leader.color,
            },
      seats_won: leader?.seats ?? 0,
      seats_total: rows.length,
      turnout_pct: turnout_known > 0 ? turnout_sum / turnout_known : null,
      runners_up: runners,
    };
  }

  function partyIdFor(w: {
    party_id: string | null;
    party_short: string | null;
  }): string {
    if (w.party_id) return w.party_id;
    const slug = (w.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }

  function fillForParty(pid: string, w: ElectionResultRow): string {
    if (w.brand_colour_hex == null) {
      return getPartyColor(pid, null).hex;
    }
    const row: PartyRowForResolver = {
      party_id: pid,
      eci_code: w.party_eci_code,
      brand_colour: {
        hex: w.brand_colour_hex,
        confidence: w.brand_colour_confidence ?? "medium",
      },
    };
    return getPartyColor(pid, row).hex;
  }

  // ---- Auto-hydrate Parliament rows on mount --------------------------
  $effect(() => {
    for (const r of all_rows) {
      if (r.kind === "parliament") void hydrateRow(r);
    }
  });

  // ---- IntersectionObserver action for lazy hydration -----------------
  // Svelte 5 `use:` action - fires hydrateRow once when the row scrolls
  // into view, then disconnects. Safe to call repeatedly: hydrateRow
  // short-circuits when state is not `idle`.
  function lazyHydrate(node: HTMLElement, row: FirehoseRow): {
    destroy(): void;
  } {
    if (typeof IntersectionObserver === "undefined") {
      // SSR / older browsers - hydrate eagerly so the row still gets
      // populated. The promise pool keeps the burst manageable.
      void hydrateRow(row);
      return { destroy: () => undefined };
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            void hydrateRow(row);
            observer.disconnect();
            break;
          }
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(node);
    return {
      destroy(): void {
        observer.disconnect();
      },
    };
  }

  // ---- Click handler (whole-row navigation) ---------------------------
  function hrefFor(row: FirehoseRow): string {
    if (row.state_code === null) {
      return link.nationalElection(row.event_id);
    }
    return link.stateElection(row.state_code, row.event_id);
  }

  // ---- Body chip styling ---------------------------------------------
  function chipClass(kind: EventKind): string {
    switch (kind) {
      case "parliament":
        return "bg-indigo-100 text-indigo-700";
      case "assembly":
        return "bg-emerald-100 text-emerald-700";
      case "assembly_bye":
      case "general_bye":
      case "by_election":
        return "bg-amber-100 text-amber-700";
    }
  }

  function chipLabel(kind: EventKind): string {
    switch (kind) {
      case "parliament":
        return "Parliament";
      case "assembly":
        return "Assembly";
      case "assembly_bye":
        return "Assembly bye";
      case "general_bye":
        return "Parliament bye";
      case "by_election":
        return "Bye-election";
    }
  }

  // ---- Formatters -----------------------------------------------------
  function fmtPct(n: number | null): string {
    return n == null ? "-" : `${n.toFixed(1)}%`;
  }

  function year(iso: string): string {
    return iso.slice(0, 4);
  }

  // ---- Filter chip definitions ---------------------------------------
  const BODY_FILTERS: { id: BodyFilter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "parliament", label: "Parliament" },
    { id: "assembly", label: "Assembly" },
    { id: "bye", label: "Bye-elections" },
  ];
  const AVAILABILITY_FILTERS: { id: AvailabilityFilter; label: string }[] = [
    { id: "has-data", label: "Has data" },
    { id: "all", label: "All including pending" },
  ];
</script>

<main class="mx-auto max-w-6xl space-y-4 p-4">
  <header class="space-y-1">
    <h1 class="text-2xl font-semibold text-slate-900">Elections firehose</h1>
    <p class="text-sm text-slate-600">
      Every Indian election event in the catalogue - Parliament, state
      Assembly, and by-elections. Click any row to drill in.
    </p>
  </header>

  {#if catalogue_err}
    <div
      class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      Catalogue couldn't load: {catalogue_err}
    </div>
  {:else}
    <!-- Body filter chips ------------------------------------------- -->
    <div
      class="flex flex-wrap gap-2"
      data-testid="firehose-body-filter"
      role="group"
      aria-label="Filter by body"
    >
      {#each BODY_FILTERS as opt (opt.id)}
        <button
          type="button"
          class="rounded-full border px-3 py-1 text-xs font-medium transition-colors {body_filter ===
          opt.id
            ? 'border-slate-900 bg-slate-900 text-white'
            : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}"
          aria-pressed={body_filter === opt.id}
          onclick={() => (body_filter = opt.id)}
        >
          {opt.label}
        </button>
      {/each}
      <span class="ml-auto self-center text-xs text-slate-500">
        {filtered_rows.length} event{filtered_rows.length === 1 ? "" : "s"}
      </span>
    </div>

    <!-- Availability filter chips ----------------------------------- -->
    <div
      class="flex flex-wrap items-center gap-2"
      data-testid="firehose-availability-filter"
      role="group"
      aria-label="Filter by data availability"
    >
      <span class="text-xs text-slate-500">Show:</span>
      {#each AVAILABILITY_FILTERS as opt (opt.id)}
        <button
          type="button"
          class="rounded-full border px-3 py-1 text-xs font-medium transition-colors {availability_filter ===
          opt.id
            ? 'border-slate-900 bg-slate-900 text-white'
            : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}"
          aria-pressed={availability_filter === opt.id}
          onclick={() => (availability_filter = opt.id)}
        >
          {opt.label}
        </button>
      {/each}
      {#if availability_filter === "has-data" && pending_in_scope_count > 0}
        <span class="text-xs text-slate-400">
          ({pending_in_scope_count} pending hidden)
        </span>
      {/if}
    </div>

    <!-- Table ------------------------------------------------------- -->
    <div class="overflow-x-auto rounded border border-slate-200 bg-white">
      <table
        class="w-full text-left text-sm"
        data-testid="elections-firehose-table"
      >
        <thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th class="px-3 py-2">
              <button
                type="button"
                class="flex items-center gap-1 hover:text-slate-700"
                onclick={toggleSort}
                aria-label="Sort by year"
              >
                Year
                <span aria-hidden="true">{sort_dir === "desc" ? "↓" : "↑"}</span>
              </button>
            </th>
            <th class="px-3 py-2">Body</th>
            <th class="px-3 py-2">State</th>
            <th class="px-3 py-2">Winning party</th>
            <th class="px-3 py-2">Seats</th>
            <th class="px-3 py-2">Turnout</th>
            <th class="px-3 py-2">Runners-up</th>
            <th class="px-3 py-2 sr-only">Open</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered_rows as row (row.row_id)}
            {@const hyd = getHydration(row.row_id)}
            <tr
              class="border-t border-slate-100 odd:bg-white even:bg-slate-50 hover:bg-sky-50"
              data-testid={`firehose-row-${row.row_id}`}
              use:lazyHydrate={row}
            >
              <td class="px-3 py-2 align-top font-mono text-xs text-slate-700">
                {year(row.polled_on)}
              </td>
              <td class="px-3 py-2 align-top">
                <span
                  class="inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold {chipClass(
                    row.kind,
                  )}"
                >
                  {chipLabel(row.kind)}
                </span>
              </td>
              <td class="px-3 py-2 align-top">
                {#if row.state_slug}
                  <a
                    href={link.stateHub(row.state_slug)}
                    class="text-slate-700 hover:text-sky-700 hover:underline"
                    onclick={(e) => e.stopPropagation()}
                  >
                    {row.state_label}
                  </a>
                {:else}
                  <span class="font-medium text-slate-700">
                    {row.state_label}
                  </span>
                {/if}
              </td>
              <td class="px-3 py-2 align-top">
                {#if hyd.status === "loading"}
                  <span class="text-xs text-slate-400">loading...</span>
                {:else if hyd.status === "ok" && hyd.leading}
                  <span
                    class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
                    style:background-color={hyd.leading.color}
                  >
                    {hyd.leading.short}
                  </span>
                {:else if hyd.status === "pending"}
                  <span
                    class="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500"
                    data-testid="firehose-pending-badge"
                    title="Data not yet ingested"
                  >
                    Pending
                  </span>
                {:else if hyd.status === "skipped"}
                  <span class="text-xs text-slate-400">-</span>
                {:else if hyd.status === "failed"}
                  <span
                    class="text-xs text-amber-600"
                    title={hyd.reason}>error</span
                  >
                {:else}
                  <span class="text-xs text-slate-300">-</span>
                {/if}
              </td>
              <td class="px-3 py-2 align-top text-slate-700">
                {#if hyd.status === "ok"}
                  <span class="font-mono text-xs">
                    {hyd.seats_won}/{hyd.seats_total}
                  </span>
                {:else}
                  <span class="text-xs text-slate-300">-</span>
                {/if}
              </td>
              <td class="px-3 py-2 align-top text-slate-700">
                {#if hyd.status === "ok"}
                  <span class="font-mono text-xs">{fmtPct(hyd.turnout_pct)}</span>
                {:else}
                  <span class="text-xs text-slate-300">-</span>
                {/if}
              </td>
              <td class="px-3 py-2 align-top">
                {#if hyd.status === "ok" && hyd.runners_up.length > 0}
                  <span class="flex flex-wrap gap-1">
                    {#each hyd.runners_up as ru (ru.party_id)}
                      <span
                        class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                        style:background-color={ru.color}
                      >
                        {ru.short}
                      </span>
                    {/each}
                  </span>
                {:else}
                  <span class="text-xs text-slate-300">-</span>
                {/if}
              </td>
              <td class="px-3 py-2 align-top text-right">
                <a
                  href={hrefFor(row)}
                  class="inline-flex items-center text-slate-400 hover:text-sky-700"
                  aria-label="Open {row.display}"
                  title={row.display}
                >
                  &rarr;
                </a>
              </td>
            </tr>
          {/each}
          {#if filtered_rows.length === 0 && catalogue !== null}
            <tr>
              <td
                colspan="8"
                class="px-3 py-6 text-center text-sm text-slate-500"
              >
                No events match this filter.
              </td>
            </tr>
          {/if}
          {#if catalogue === null}
            <tr>
              <td
                colspan="8"
                class="px-3 py-6 text-center text-sm text-slate-400"
              >
                Loading catalogue...
              </td>
            </tr>
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</main>
