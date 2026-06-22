<!--
  StateEventConstituencyList - the grouped, glanceable constituency list
  for a state election event.

  History: extracted from StateElection.svelte during R3 of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15);
  rebuilt in Row 2 of
  TODO/20260622-election-constituency-grouping-plan.md (2026-06-22).

  Row 2 rebuild (Jony + Citizen, schema-is-the-design-system):
   - PROPORTIONAL segmented party strip per group: one segment per
     winning party, width proportional to seats won, top-4 parties + a
     single "Other" remainder; ALWAYS paired with a leading-party text
     label "<SHORT> n/N" (e.g. "TDP 9/17") - never colour-only.
   - [SC] / [ST] rose reservation badge per leaf (GEN renders nothing)
     via the shared ReservationBadge.
   - RdYlBu margin colour-band per leaf (< 5 nail-biter / < 10
     contestable / >= 10 comfortable), shared with StateOverview via
     marginBand().
   - The expand/collapse twisty renders the icon-registry chevron GLYPH
     (chevron-right collapsed / chevron-down expanded); the search box
     carries the magnifier glyph; a sort control (arrow-up-down glyph)
     toggles leaf order ballot (eci_no) <-> by-margin.
   - Reserved filter "(All) GEN SC ST" beside the search, AND-composed
     with the name search, plus a "N constituencies in M districts"
     count line. The Share column drops on mobile (< 640px).
   - The exported SeatRow contract declares district? + eci_no? +
     reservation? so the STATE-lane loader (Rows 4/5) fills them without
     re-authoring this component.

  All testable logic lives in ./constituency-list-tokens (one code path,
  exercised by StateEventConstituencyList.test.ts).

  The trailing "Compare with <prior event>" CTA was REMOVED 2026-06-22 as
  redundant: the SiblingEventsRail above the map already offers the
  compare affordance ("See how this election compares with <prior year>").

  Preserves data-testids: state-event-constituency-table /
  state-event-constituency-table-loading / state-event-constituency-row /
  state-event-constituency-link /
  state-event-constituency-search / state-event-constituency-district-row
  / state-event-constituency-district-toggle. ADDS:
  state-event-constituency-reserved-filter,
  state-event-constituency-reserved-option,
  state-event-constituency-sort, state-event-constituency-count,
  state-event-constituency-strip-label.
-->
<script lang="ts">
  import TopicIcon from "../TopicIcon.svelte";
  import ReservationBadge from "./ReservationBadge.svelte";
  import {
    applyFilters,
    buildPartyStrip,
    distinctDistrictCount,
    formatCountLine,
    marginBand,
    sortLeaves,
    type PartyStrip,
    type ReservationKind,
    type SortMode,
  } from "./constituency-list-tokens";

  export interface SeatRow {
    entity_id: string;
    entity_name: string;
    /** Human-readable district name when the upstream loader could
     *  derive it from the AC/PC metadata; null when no district label is
     *  available (falls back to a single "All constituencies" group).
     *  The STATE-lane loader (Row 4) fills this; until then every seat
     *  renders under one group and the fold + search still work. */
    district?: string | null;
    /** Ballot-order index (ECI constituency number) when the loader can
     *  resolve it from electoral.csv; null/undefined otherwise. Drives
     *  the "ballot" sort and the leading "eci" column. Populated by the
     *  STATE-lane loader (Row 4); ballot order falls back to the
     *  incoming array order until then. */
    eci_no?: number | null;
    /** Reservation category. "SC" / "ST" render a rose badge and feed
     *  the Reserved filter; "GEN" (or null / undefined) renders no
     *  badge. Populated by the STATE-lane loader (Row 4). */
    reservation?: string | null;
    winner_party_short: string;
    winner_party_id: string;
    winner_color: string;
    winner_share_pct: number | null;
    margin_pct: number | null;
    href: string;
  }

  interface Props {
    loading: boolean;
    seat_rows: readonly SeatRow[];
    fmtInt: (n: number | null) => string;
    fmtPct: (n: number | null) => string;
  }

  let {
    loading,
    seat_rows,
    fmtInt,
    fmtPct,
  }: Props = $props();

  type ReservedFilter = ReservationKind | "All";

  const RESERVED_OPTIONS: ReadonlyArray<{ value: ReservedFilter; label: string }> = [
    { value: "All", label: "All" },
    { value: "GEN", label: "GEN" },
    { value: "SC", label: "SC" },
    { value: "ST", label: "ST" },
  ];

  // Case-insensitive name search.
  let search_q = $state("");
  // Reserved (All/GEN/SC/ST) filter, AND-composed with the search.
  let reserved_filter = $state<ReservedFilter>("All");
  // Leaf order within an expanded group.
  let sort_mode = $state<SortMode>("ballot");
  // Set of EXPANDED district names; empty = all collapsed on first paint.
  let expanded = $state<Set<string>>(new Set());

  // Reset fold + controls when the seat-rows identity changes (event
  // navigation reuses this route), so the citizen does not carry an
  // expanded district / active filter from one event into the next.
  let prev_first_id = $state<string | null>(null);
  $effect(() => {
    const first = seat_rows[0]?.entity_id ?? null;
    if (first !== prev_first_id) {
      expanded = new Set();
      search_q = "";
      reserved_filter = "All";
      sort_mode = "ballot";
      prev_first_id = first;
    }
  });

  function toggleDistrict(d: string): void {
    const next = new Set(expanded);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    expanded = next;
  }

  function toggleSort(): void {
    sort_mode = sort_mode === "ballot" ? "margin" : "ballot";
  }

  // Show the leading "eci" column only once the loader populates eci_no
  // (Row 4); before then it would be a column of blanks.
  const has_eci = $derived(
    seat_rows.some((r) => r.eci_no !== null && r.eci_no !== undefined),
  );

  // Name + Reserved filter, AND-composed.
  const filtered = $derived.by<readonly SeatRow[]>(() =>
    applyFilters(seat_rows, search_q, reserved_filter),
  );

  const count_line = $derived(
    formatCountLine(filtered.length, distinctDistrictCount(filtered)),
  );

  interface DistrictGroup {
    district: string;
    rows: SeatRow[];
    strip: PartyStrip;
  }

  const groups = $derived.by<DistrictGroup[]>(() => {
    const by_district = new Map<string, SeatRow[]>();
    for (const r of filtered) {
      const d = r.district ?? "All constituencies";
      const list = by_district.get(d);
      if (list) list.push(r);
      else by_district.set(d, [r]);
    }
    const out: DistrictGroup[] = [];
    for (const [district, rows] of by_district) {
      out.push({
        district,
        rows: sortLeaves(rows, sort_mode),
        strip: buildPartyStrip(rows),
      });
    }
    out.sort((a, b) => a.district.localeCompare(b.district, "en"));
    return out;
  });

  // When a search query OR a Reserved filter is active, auto-expand every
  // group so the citizen sees the matches without an extra tap.
  const force_expand_all = $derived(
    search_q.trim().length > 0 || reserved_filter !== "All",
  );

  function isExpanded(d: string): boolean {
    return force_expand_all || expanded.has(d);
  }

  // Single-group special case: exactly one group AND no active filter ->
  // treat as auto-expanded so the citizen does not have to tap once to
  // see the only data. The fold shape still ships for when district data
  // lands (Row 4).
  const single_group = $derived(groups.length === 1 && !force_expand_all);
</script>

<!-- Constituency table -->
<section
  class="space-y-2"
  data-testid="state-event-constituency-table"
>
  <div class="flex flex-wrap items-baseline justify-between gap-2">
    <h2 class="text-sm font-semibold text-slate-800">
      Constituencies ({loading ? "-" : fmtInt(seat_rows.length)})
    </h2>
  </div>
  {#if loading}
    <p
      class="text-xs text-slate-500"
      data-testid="state-event-constituency-table-loading"
    >Loading constituency results...</p>
  {:else if seat_rows.length === 0}
    <p class="text-xs text-slate-500">No constituency rows yet.</p>
  {:else}
    <!-- Sticky controls: search (magnifier glyph) + Reserved filter +
         sort toggle + count line. Sticky to this section's scroll
         boundary, NOT the viewport top. -->
    <div class="sticky top-0 z-10 -mx-1 space-y-1.5 bg-white/95 px-1 py-1 backdrop-blur">
      <label class="relative block">
        <span class="sr-only">Search constituency by name</span>
        <span class="pointer-events-none absolute inset-y-0 left-2 flex items-center">
          <TopicIcon name="search" cls="h-4 w-4 shrink-0 text-slate-400" />
        </span>
        <input
          type="search"
          placeholder="Search constituency..."
          class="w-full rounded border border-slate-300 py-1.5 pl-8 pr-3 text-sm placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          data-testid="state-event-constituency-search"
          bind:value={search_q}
        />
      </label>

      <div class="flex flex-wrap items-center justify-between gap-2">
        <div
          class="flex items-center gap-1 text-xs"
          data-testid="state-event-constituency-reserved-filter"
        >
          <span class="text-slate-500">Reserved:</span>
          {#each RESERVED_OPTIONS as opt (opt.value)}
            <button
              type="button"
              class={`rounded px-1.5 py-0.5 font-medium ${
                reserved_filter === opt.value
                  ? "bg-slate-800 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
              data-testid="state-event-constituency-reserved-option"
              data-value={opt.value}
              aria-pressed={reserved_filter === opt.value}
              onclick={() => (reserved_filter = opt.value)}
            >{opt.label}</button>
          {/each}
        </div>

        <button
          type="button"
          class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
          data-testid="state-event-constituency-sort"
          aria-pressed={sort_mode === "margin"}
          title="Toggle leaf order: ballot (eci number) or by margin (nail-biters first)"
          onclick={toggleSort}
        >
          <TopicIcon name="arrow-up-down" cls="h-3.5 w-3.5 shrink-0 text-slate-500" />
          {sort_mode === "margin" ? "By margin" : "Ballot order"}
        </button>
      </div>

      <p
        class="text-xs tabular-nums text-slate-500"
        data-testid="state-event-constituency-count"
      >{count_line}</p>
    </div>

    {#if groups.length === 0}
      <p class="text-xs text-slate-500">
        No constituencies match
        <code class="rounded bg-slate-100 px-1">{search_q}</code>.
      </p>
    {:else}
      <ul class="divide-y border-y">
        {#each groups as g (g.district)}
          {@const open = isExpanded(g.district) || single_group}
          <li data-testid="state-event-constituency-district-row">
            {#if !single_group}
              <button
                type="button"
                class="flex w-full items-center justify-between gap-3 px-2 py-2 text-left text-sm hover:bg-slate-50"
                data-testid="state-event-constituency-district-toggle"
                aria-expanded={open}
                onclick={() => toggleDistrict(g.district)}
              >
                <span class="flex min-w-0 items-center gap-2">
                  <TopicIcon
                    name={open ? "chevron-down" : "chevron-right"}
                    cls="h-4 w-4 shrink-0 text-slate-400"
                  />
                  <span class="truncate font-medium text-slate-800">{g.district}</span>
                  <span class="shrink-0 text-xs tabular-nums text-slate-500">
                    {fmtInt(g.rows.length)}
                  </span>
                </span>
                <span class="flex min-w-0 items-center gap-2">
                  <!-- Proportional segmented party strip: one segment per
                       winning party, width proportional to seats won. -->
                  <span
                    aria-hidden="true"
                    class="flex h-2.5 w-16 overflow-hidden rounded-sm border border-slate-200 sm:w-24"
                  >
                    {#each g.strip.segments as seg (seg.party_id)}
                      <span
                        class="h-full"
                        style={`width:${seg.pct}%;background-color:${seg.color};`}
                        title={`${seg.party_short} ${seg.count}`}
                      ></span>
                    {/each}
                  </span>
                  <span
                    class="shrink-0 text-xs font-semibold tabular-nums text-slate-700"
                    data-testid="state-event-constituency-strip-label"
                  >{g.strip.leader_label}</span>
                </span>
              </button>
            {/if}

            {#if open}
              <table class="w-full text-sm">
                <thead class="text-left text-xs uppercase text-slate-500">
                  <tr>
                    {#if has_eci}
                      <th class="py-1 pl-6 pr-2 text-right">eci</th>
                    {/if}
                    <th class={has_eci ? "py-1" : "py-1 pl-6"}>Constituency</th>
                    <th class="py-1">Winner</th>
                    <th class="hidden py-1 text-right sm:table-cell">Share</th>
                    <th class="py-1 pr-2 text-right">Margin</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  {#each g.rows as r (r.entity_id)}
                    {@const band = marginBand(r.margin_pct)}
                    <tr
                      class="hover:bg-slate-50"
                      data-testid="state-event-constituency-row"
                    >
                      {#if has_eci}
                        <td class="py-2 pl-6 pr-2 text-right tabular-nums text-slate-400">
                          {r.eci_no ?? ""}
                        </td>
                      {/if}
                      <td class={has_eci ? "py-2" : "py-2 pl-6"}>
                        <a
                          class="text-sky-700 hover:underline"
                          href={r.href}
                          data-testid="state-event-constituency-link"
                        >{r.entity_name}</a>
                        <ReservationBadge reservation={r.reservation} cls="ml-1 align-middle" />
                      </td>
                      <td class="py-2">
                        <span
                          class="inline-block rounded px-1.5 py-0.5 text-xs font-medium text-white"
                          style={`background-color:${r.winner_color};`}
                        >{r.winner_party_short}</span>
                      </td>
                      <td class="hidden py-2 text-right tabular-nums sm:table-cell">
                        {fmtPct(r.winner_share_pct)}
                      </td>
                      <td class="py-2 pr-2 text-right">
                        <span class="inline-flex items-center justify-end gap-1 tabular-nums">
                          {#if band}
                            <span
                              aria-hidden="true"
                              class="inline-block h-2 w-2 rounded-sm"
                              style={`background-color:${band.hex};`}
                              title={band.label}
                            ></span>
                          {/if}
                          <span
                            class="font-semibold"
                            style={band ? `color:${band.hex};` : ""}
                          >{fmtPct(r.margin_pct)}</span>
                        </span>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
