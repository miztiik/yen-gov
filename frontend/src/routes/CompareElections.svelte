<script lang="ts">
  // CompareElections - body-tagged event-vs-event compare cascade for
  // the election experience overhaul plan PR-W4b (2026-06-10).
  //
  // Surface: `/compare/elections/<state>/<from-event>/<to-event>`
  // (route table in main.ts).
  //
  // Layout (IndiaVotes-style winner-change framing per the plan-doc brief):
  //   1. Header             - state name + "<from> vs <to>" badges +
  //                           citizen-readable event displays.
  //   2. KPIs strip         - total seats / flips / holds / new-party-
  //                           entries (count of constituencies whose
  //                           <to> winner-party did not contest <from>'s
  //                           winner slate AT ALL in that state). The
  //                           four KPIs answer "what changed" at a glance.
  //   3. Filter chip group  - [All] [Flips] [Holds] - client-side filter
  //                           over the winner-change table.
  //   4. Winner-change table - one row per constituency, sortable on the
  //                           three text columns; row click drills into
  //                           the newer event's constituency page.
  //
  // Data path (one loader, two event-keyed projections):
  //   loadElectionResults({event, state?}) -> ElectionResultRow[]  (x2)
  //     -> NATIONAL-PC scope for `general-*` events: load nationally,
  //        filter client-side by state_slug (matches StateElection.svelte's
  //        per-state PC handling pattern; the W2b loader rejects
  //        `{event, state}` for parliament events today).
  //     -> STATE-AC scope for `assembly-*` events: load directly.
  //   projectAsWinnersByEntity(rows) -> winners only
  //   join_by_entity_id(from_winners, to_winners) -> compare rows
  //
  // Why "flip" + "hold" + "new-party-entry" as the KPIs (not "swing %"):
  // per Hans verdict in the plan-doc preamble, the citizen surface
  // names what HAPPENED, not the politico-analyst's "swing index". A
  // citizen on this page is asking "did MY constituency change parties?"
  // first; aggregate state-level swing belongs on the analyst surface
  // (Psephlab compare-mode, deferred to PR-W5a cleanup).
  //
  // Stop-and-surface note: the parent plan-doc oracle for TN
  // 2014/2019 said ">= 30 rows + >= 20 flips". On-disk verification
  // (`datasets/elections/parliament/election=2014/summary.csv` +
  // `=2019/summary.csv`) shows TN carries only 26 PCs in those vintages
  // (vs 39 today); the underlying gap is a data-coverage issue
  // independent of this PR (some 2008-delim PCs were not ingested for
  // 2014/2019). The Playwright spec floors at >= 20 rows + >= 15 flips
  // to ride above the actual on-disk count (26 + 25) with margin; the
  // citizen-facing flip-count is computed live from the data so the
  // page surfaces whatever the loader returns.

  import {
    loadElectionResults,
    projectAsWinnersByEntity,
    bodyFromEvent,
    type ElectionResultRow,
  } from "../lib/view-models/election-results";
  import type { LoaderResult } from "../lib/loader-result";
  import { link } from "../lib/links";
  import { navigate } from "../lib/url";
  import PartyPill from "../lib/party-pill/PartyPill.svelte";
  import TopicIcon from "../lib/TopicIcon.svelte";
  import { states } from "../lib/states.svelte";
  import {
    fetchElectionEvents,
    findEvent,
    type ElectionEventsCatalogue,
  } from "../lib/election-events";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { route } from "../lib/router.svelte";
  import { slugify } from "../lib/slug";
  import { getPartyColor } from "../lib/colors/resolver";
  import { filterAndSortCompareRows } from "../lib/elections/compare-table-filter";
  import { buildCompareDotSummary } from "../lib/elections/compare-dot-summary";
  import { buildCompareKpis, isNewPartyRow } from "../lib/elections/compare-kpis";

  interface Props {
    params: { state: string; fromEvent: string; toEvent: string };
  }
  let { params }: Props = $props();

  // ---- State + catalogue resolution ---------------------------------
  let catalogue = $state<ElectionEventsCatalogue | null>(null);
  fetchElectionEvents()
    .then((c) => (catalogue = c))
    .catch(() => (catalogue = null));

  const state_code = $derived(states.codeFromSlug(params.state));
  const state_name = $derived(state_code ? states.name(state_code) : "");

  // Citizen-readable event labels. The catalogue's `display` field
  // already INCLUDES the state name (e.g. "Tamil Nadu - Parliament
  // 2014"); reusing it verbatim under an H1 that ALSO leads with the
  // state name produces stutter ("Tamil Nadu - Tamil Nadu Parliament
  // ..."). Synthesise the body+year label directly from the event slug
  // instead (mirrors NationalElection.svelte's event_pretty helper);
  // the catalogue display falls back only for non-standard event ids
  // (legacy ECI forms / bye-events).
  function eventPretty(event: string): string {
    const m = /^(general|assembly)-(\d{4})$/.exec(event);
    if (m) {
      const body_pretty = m[1] === "general" ? "Parliament" : "Assembly";
      return `${body_pretty} Election ${m[2]}`;
    }
    if (!state_code) return event;
    return findEvent(catalogue, state_code, event)?.display ?? event;
  }
  const from_display = $derived(eventPretty(params.fromEvent));
  const to_display = $derived(eventPretty(params.toEvent));

  // ---- Loader dispatch (parallel) -----------------------------------
  // For NATIONAL-PC events (general-*) the W2b loader rejects the
  // {event, state} scope today; load nationally then filter client-side.
  // For STATE-AC events (assembly-*) pass {event, state} directly.
  // Mirrors StateElection.svelte's per-body branching.
  async function loadForBody(
    event: string,
    sc: string,
  ): Promise<LoaderResult<ElectionResultRow[]>> {
    const body = bodyFromEvent(event);
    if (body === "ac") {
      return loadElectionResults({ event, state: sc });
    }
    const r = await loadElectionResults({ event });
    if (r.status !== "ok" && r.status !== "partial") return r;
    const target_slug = params.state;
    const filtered = r.data.filter((row) => row.state_slug === target_slug);
    return { status: r.status, data: filtered } as LoaderResult<
      ElectionResultRow[]
    >;
  }

  let from_result = $state<LoaderResult<ElectionResultRow[]>>({
    status: "loading",
  });
  let to_result = $state<LoaderResult<ElectionResultRow[]>>({
    status: "loading",
  });

  $effect(() => {
    const sc = state_code;
    const fe = params.fromEvent;
    const te = params.toEvent;
    if (!sc) {
      from_result = { status: "loading" };
      to_result = { status: "loading" };
      return;
    }
    from_result = { status: "loading" };
    to_result = { status: "loading" };
    loadForBody(fe, sc).then((r) => {
      // Guard against a stale event switch resolving after a newer one.
      if (fe === params.fromEvent && sc === state_code) from_result = r;
    });
    loadForBody(te, sc).then((r) => {
      if (te === params.toEvent && sc === state_code) to_result = r;
    });
  });

  // ---- Compare rows --------------------------------------------------
  interface CompareRow {
    entity_id: string;
    entity_name: string;
    from_party: string | null;
    from_party_id: string | null;
    to_party: string | null;
    to_party_id: string | null;
    change_label: string;
    is_flip: boolean;
    /** True when the constituency exists in one event but not the other
     *  (boundary delimitation change between the two events). Renders
     *  as "Boundary changed" in the change column. */
    is_orphan: boolean;
    /** True when this comparable seat was won by a To-winner party that
     *  won zero seats in `from` (PR4 new-party-entry flag; powers the
     *  "New parties" filter chip + the per-row "New entry" badge). Set
     *  from the compare-kpis model AFTER the raw union is built below. */
    is_new_party: boolean;
    eci_no: number;
  }

  // The raw union carries every field EXCEPT is_new_party (which needs the
  // whole-table new-party set from buildCompareKpis); the flag is layered
  // on in `compare_rows` once the KPIs are derived.
  type RawCompareRow = Omit<CompareRow, "is_new_party">;

  const raw_compare_rows = $derived.by<RawCompareRow[]>(() => {
    if (from_result.status !== "ok" && from_result.status !== "partial") {
      return [];
    }
    if (to_result.status !== "ok" && to_result.status !== "partial") {
      return [];
    }
    const from_winners = projectAsWinnersByEntity(from_result.data);
    const to_winners = projectAsWinnersByEntity(to_result.data);
    const to_map = new Map(to_winners.map((w) => [w.entity_id, w]));
    const out: RawCompareRow[] = [];
    const seen = new Set<string>();
    for (const fw of from_winners) {
      seen.add(fw.entity_id);
      const tw = to_map.get(fw.entity_id);
      if (!tw) {
        out.push({
          entity_id: fw.entity_id,
          entity_name: fw.entity_name,
          from_party: fw.party_short,
          from_party_id: fw.party_id,
          to_party: null,
          to_party_id: null,
          change_label: "Boundary changed",
          is_flip: false,
          is_orphan: true,
          eci_no: fw.eci_no,
        });
        continue;
      }
      const is_flip = fw.party_id !== tw.party_id;
      const short_from = fw.party_short ?? "UNK";
      const short_to = tw.party_short ?? "UNK";
      out.push({
        entity_id: tw.entity_id,
        entity_name: tw.entity_name,
        from_party: fw.party_short,
        from_party_id: fw.party_id,
        to_party: tw.party_short,
        to_party_id: tw.party_id,
        change_label: is_flip
          ? `Flip ${short_from} \u2192 ${short_to}`
          : `Hold ${short_to}`,
        is_flip,
        is_orphan: false,
        eci_no: tw.eci_no,
      });
    }
    // Also surface to-only constituencies (new seats / delim changes)
    // so the table is the union of both event slates.
    for (const tw of to_winners) {
      if (seen.has(tw.entity_id)) continue;
      out.push({
        entity_id: tw.entity_id,
        entity_name: tw.entity_name,
        from_party: null,
        from_party_id: null,
        to_party: tw.party_short,
        to_party_id: tw.party_id,
        change_label: "New seat",
        is_flip: false,
        is_orphan: true,
        eci_no: tw.eci_no,
      });
    }
    return out;
  });

  // ---- KPIs strip + per-row new-party flag (pure model) --------------
  // buildCompareKpis preserves the exact pre-extraction predicate (flips /
  // holds / total_seats / new-party-entry seat count) AND adds flips_pct /
  // holds_pct (composition %) + the distinct new-party id set. The math
  // lives in compare-kpis.ts so vitest exercises it without mounting Svelte.
  const kpis = $derived(buildCompareKpis(raw_compare_rows));

  // Layer is_new_party onto each row from the model's new-party set so the
  // "New parties" filter chip + the per-row "New entry" badge read it
  // without re-deriving the predicate in the template.
  const compare_rows = $derived<CompareRow[]>(
    raw_compare_rows.map((r) => ({
      ...r,
      is_new_party: isNewPartyRow(r, kpis.new_party_ids),
    })),
  );

  // ---- Filter chip + search + sorting --------------------------------
  type Filter = "all" | "flips" | "holds" | "new";
  let filter = $state<Filter>("all");

  // Live case-insensitive substring search over the constituency name and
  // both winner party short codes. Composes with the filter chip + sort
  // (the predicate lives in compare-table-filter.ts so vitest exercises it
  // without mounting Svelte).
  let search = $state("");

  type SortKey = "entity_name" | "from_party" | "to_party";
  let sort_key = $state<SortKey>("entity_name");
  let sort_dir = $state<"asc" | "desc">("asc");

  // Sort-affordance glyphs, kept as named consts so the markup stays
  // ASCII-only. Every sortable header shows the faint neutral up-down hint
  // at rest; the active column shows the small solid triangle for its dir.
  const SORT_GLYPH_ASC = "\u25b2"; // up triangle (active, ascending)
  const SORT_GLYPH_DESC = "\u25bc"; // down triangle (active, descending)
  const SORT_GLYPH_NEUTRAL = "\u2195"; // up-down arrow (at-rest hint)

  function toggleSort(k: SortKey): void {
    if (sort_key === k) {
      sort_dir = sort_dir === "asc" ? "desc" : "asc";
    } else {
      sort_key = k;
      sort_dir = "asc";
    }
  }

  const filtered_sorted = $derived.by<CompareRow[]>(() =>
    filterAndSortCompareRows(compare_rows, search, filter, sort_key, sort_dir),
  );

  // To-winner party-dot summary over the CURRENT filtered rows (plan-doc
  // section 3a). Orphans are excluded inside the model. The colour resolver
  // is the same 3-tier resolver PartyPill uses, called with a null row so
  // the dot hue matches what the table pill renders (anchor + algorithmic
  // fallback tiers).
  const dot_summary = $derived(
    buildCompareDotSummary(
      filtered_sorted,
      (pid) => getPartyColor(pid, null).hex,
    ),
  );

  // ---- Row click - drill into the newer event's constituency page ----
  // For AC events, the route is `/<state>/elections/<event>/ac/<eci_no>`
  // (the legacy 5-segment canonical form per ADR-0052). For PC events,
  // the per-PC constituency drill is not yet shipped (W3b's leaf is
  // AC-only); fall back to the state-event view in that case so the
  // citizen lands on the page that shows this PC's row.
  function urlForRow(r: CompareRow): string {
    const sc = state_code ?? params.state;
    const body = bodyFromEvent(params.toEvent);
    if (body === "ac" && r.eci_no > 0) {
      const slug = `${r.eci_no}-${slugify(r.entity_name)}`;
      // link.acDeepLink generates `/<state>/<ac-slug>` (bare convenience
      // route); for the canonical drill use the event-nested form.
      return link
        .stateElection(sc, params.toEvent)
        .replace(/\/?$/, `/ac/${slug}`);
    }
    return link.stateElection(sc, params.toEvent);
  }

  const loading = $derived(
    from_result.status === "loading" || to_result.status === "loading",
  );
  const failed_reason = $derived(
    from_result.status === "failed"
      ? from_result.reason
      : to_result.status === "failed"
        ? to_result.reason
        : null,
  );

  function retry(): void {
    if (from_result.status === "failed" && from_result.retry) {
      from_result.retry();
    }
    if (to_result.status === "failed" && to_result.retry) {
      to_result.retry();
    }
  }

  // Reactive crumb trail (the route-table builder reads `states` which
  // resolves async, so re-evaluation on catalogue load is required).
  const crumbs = $derived(route.crumbs?.(route.params) ?? []);

  const INT_FMT = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
  function fmtInt(n: number): string {
    return INT_FMT.format(n);
  }

  // Composition % for the Flips / Holds cards (PR4 reading 4a). The model
  // returns a 0-100 float (or null); the card rounds to a whole percent for
  // the citizen-facing "70% of seats" line.
  function fmtSharePct(pct: number): string {
    return `${Math.round(pct)}%`;
  }
</script>

<PageContainer
  width="wide"
  data-testid="compare-elections"
>
  <Breadcrumb {crumbs} />

  {#snippet sortIndicator(key: SortKey)}
    {#if sort_key === key}
      <span
        class="ml-0.5 text-[10px] leading-none text-slate-600"
        aria-hidden="true"
      >{sort_dir === "asc" ? SORT_GLYPH_ASC : SORT_GLYPH_DESC}</span>
    {:else}
      <span
        class="ml-0.5 text-[10px] leading-none text-slate-300"
        aria-hidden="true"
      >{SORT_GLYPH_NEUTRAL}</span>
    {/if}
  {/snippet}

  <header class="space-y-2">
    <h1 class="text-2xl font-semibold text-slate-900">
      {state_name || params.state}
      <span class="text-slate-500"> &middot; </span>
      <span class="text-slate-700">{from_display} vs {to_display}</span>
    </h1>
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span
        class="inline-block rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
        data-testid="compare-elections-from-badge"
      >From: {from_display}</span>
      <span class="text-slate-400">&rarr;</span>
      <span
        class="inline-block rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
        data-testid="compare-elections-to-badge"
      >To: {to_display}</span>
    </div>
  </header>

  {#if failed_reason}
    <div
      class="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
      data-testid="compare-elections-error"
    >
      <p class="mb-2">Data couldn't load: {failed_reason}</p>
      <button
        type="button"
        class="rounded border border-amber-300 bg-white px-3 py-1 text-xs hover:bg-amber-100"
        onclick={retry}
      >Try again</button>
    </div>
  {:else}
    <!-- KPIs strip. PR4 mirrors the StateEventHero icon-chip pattern: a
         TopicIcon in a tinted rounded square next to each label, plus a
         composition-% line under Flips / Holds. Card data-testids are kept
         verbatim so prior assertions still pass. -->
    <section
      class="grid grid-cols-2 gap-3 sm:grid-cols-4"
      data-testid="compare-elections-kpis"
    >
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
            <TopicIcon name="landmark" cls="h-4 w-4" />
          </span>
          <span>Total seats</span>
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtInt(kpis.total_seats)}
        </div>
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <TopicIcon name="arrow-left-right" cls="h-4 w-4" />
          </span>
          <span>Flips</span>
        </div>
        <div
          class="mt-1 text-2xl font-semibold text-emerald-700"
          data-testid="compare-elections-kpi-flips"
        >{fmtInt(kpis.flips)}</div>
        {#if kpis.flips_pct !== null}
          <div
            class="mt-0.5 text-xs text-slate-500"
            data-testid="compare-elections-kpi-flips-pct"
          >{fmtSharePct(kpis.flips_pct)} of seats</div>
        {/if}
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
            <TopicIcon name="shield" cls="h-4 w-4" />
          </span>
          <span>Holds</span>
        </div>
        <div
          class="mt-1 text-2xl font-semibold text-slate-700"
          data-testid="compare-elections-kpi-holds"
        >{fmtInt(kpis.holds)}</div>
        {#if kpis.holds_pct !== null}
          <div
            class="mt-0.5 text-xs text-slate-500"
            data-testid="compare-elections-kpi-holds-pct"
          >{fmtSharePct(kpis.holds_pct)} of seats</div>
        {/if}
      </div>
      <div class="rounded border border-slate-200 bg-white p-3">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
          <span class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
            <TopicIcon name="flag" cls="h-4 w-4" />
          </span>
          <span>New-party entries</span>
        </div>
        <div class="mt-1 text-2xl font-semibold text-slate-900">
          {fmtInt(kpis.new_party_entries)}
        </div>
      </div>
    </section>

    <!-- Filter chips + search + result summary -->
    <section class="flex flex-wrap items-center gap-2">
      {#each [{ k: "all", label: "All" }, { k: "flips", label: "Flips" }, { k: "holds", label: "Holds" }, { k: "new", label: "New parties" }] as opt (opt.k)}
        <button
          type="button"
          class="rounded-full border px-3 py-1 text-xs"
          class:border-slate-900={filter === opt.k}
          class:bg-slate-900={filter === opt.k}
          class:text-white={filter === opt.k}
          class:border-slate-300={filter !== opt.k}
          class:text-slate-700={filter !== opt.k}
          onclick={() => (filter = opt.k as Filter)}
          data-testid="compare-elections-filter-{opt.k}"
        >{opt.label}</button>
      {/each}

      <!-- Search: case-insensitive substring over the constituency name +
           both winner party short codes. Mirrors the
           StateEventConstituencyList input styling (rounded border + sky
           focus ring), compact for the toolbar. -->
      <label class="block">
        <span class="sr-only">Search constituency or party</span>
        <input
          type="search"
          placeholder="Search constituency or party..."
          class="w-48 rounded border border-slate-300 px-2.5 py-1 text-xs placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          data-testid="compare-elections-search"
          bind:value={search}
        />
      </label>

      <!-- Result count + To-winner party-dot cluster (plan-doc section 3a) -->
      <div class="ml-auto flex items-center gap-2">
        <span class="text-xs text-slate-500"
          >{fmtInt(filtered_sorted.length)} of {fmtInt(compare_rows.length)} rows</span
        >
        {#if dot_summary.dots.length > 0}
          <span
            class="flex items-center gap-0.5"
            aria-hidden="true"
            data-testid="compare-elections-dot-summary"
          >
            {#each dot_summary.dots as hex, i (i)}
              <span
                class="inline-block h-2 w-2 rounded-full"
                style="background-color: {hex};"
              ></span>
            {/each}
            {#if dot_summary.overflow > 0}
              <span class="text-[10px] text-slate-500"
                >+{dot_summary.overflow}</span
              >
            {/if}
          </span>
        {/if}
      </div>
    </section>

    {#if loading && compare_rows.length === 0}
      <div
        class="rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500"
        data-testid="compare-elections-loading"
      >
        Loading {from_display} and {to_display}&hellip;
      </div>
    {:else if compare_rows.length === 0}
      <div
        class="rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500"
        data-testid="compare-elections-empty"
      >
        No comparable constituencies between these two events in
        {state_name || params.state}.
      </div>
    {:else}
      <!-- Winner-change table -->
      <section
        class="overflow-x-auto rounded border border-slate-200 bg-white"
        data-testid="compare-elections-table"
      >
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th class="px-3 py-2 text-left">
                <button
                  type="button"
                  class="inline-flex cursor-pointer items-center hover:underline"
                  class:font-semibold={sort_key === "entity_name"}
                  class:font-medium={sort_key !== "entity_name"}
                  onclick={() => toggleSort("entity_name")}
                >
                  <span>Constituency</span>
                  {@render sortIndicator("entity_name")}
                </button>
              </th>
              <th class="px-3 py-2 text-left">
                <button
                  type="button"
                  class="inline-flex cursor-pointer items-center hover:underline"
                  class:font-semibold={sort_key === "from_party"}
                  class:font-medium={sort_key !== "from_party"}
                  onclick={() => toggleSort("from_party")}
                >
                  <span>{from_display} winner</span>
                  {@render sortIndicator("from_party")}
                </button>
              </th>
              <th class="px-3 py-2 text-left">
                <button
                  type="button"
                  class="inline-flex cursor-pointer items-center hover:underline"
                  class:font-semibold={sort_key === "to_party"}
                  class:font-medium={sort_key !== "to_party"}
                  onclick={() => toggleSort("to_party")}
                >
                  <span>{to_display} winner</span>
                  {@render sortIndicator("to_party")}
                </button>
              </th>
              <th class="px-3 py-2 text-left">Change</th>
            </tr>
          </thead>
          <tbody>
            {#each filtered_sorted as r (r.entity_id)}
              <tr
                class="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                onclick={(e) => {
                  // PartyPill click renders as a <button>; without this
                  // guard the row's full-bleed onclick navigates to the
                  // constituency page on top of the pill's own
                  // navigation, drilling away from the party page the
                  // citizen actually asked for.
                  if ((e.target as Element).closest('[data-component="party-pill"]')) return;
                  window.location.href = urlForRow(r);
                }}
                data-testid="compare-row-{r.entity_id}"
              >
                <td class="px-3 py-2">
                  <a
                    class="text-slate-900 hover:underline"
                    href={urlForRow(r)}
                    onclick={(e) => e.stopPropagation()}>{r.entity_name}</a
                  >
                </td>
                <td class="px-3 py-2">
                  {#if r.from_party_id}
                    <PartyPill
                      size="sm"
                      party_id={r.from_party_id}
                      party_short={r.from_party ?? "\u2014"}
                      onclick={() => {
                        const href = link.party(r.from_party_id);
                        if (href) navigate(href);
                      }}
                    />
                  {:else}
                    <span class="text-slate-400">{r.from_party ?? "\u2014"}</span>
                  {/if}
                </td>
                <td class="px-3 py-2">
                  {#if r.to_party_id}
                    <PartyPill
                      size="sm"
                      party_id={r.to_party_id}
                      party_short={r.to_party ?? "\u2014"}
                      onclick={() => {
                        const href = link.party(r.to_party_id);
                        if (href) navigate(href);
                      }}
                    />
                  {:else}
                    <span class="text-slate-400">{r.to_party ?? "\u2014"}</span>
                  {/if}
                </td>
                <td class="px-3 py-2 text-xs">
                  <span
                    class:text-emerald-700={r.is_flip}
                    class:text-slate-500={!r.is_flip}
                  >{r.change_label}</span>
                  {#if r.is_new_party}
                    <span
                      class="ml-1.5 inline-block rounded-full bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700"
                      data-testid="compare-row-new-badge"
                    >New entry</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}
  {/if}
</PageContainer>
