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

  Row 3 (Wave 2) adds an OPTIONAL parliament/PC mode to this SAME component
  (schema-is-the-design-system: ONE component, switched by DATA presence).
  When the `group_headers` prop carries an entry for a group's key, that
  group renders in PC mode: the GROUP HEADER shows the PC's parliament (MP)
  result (party chip + share + margin band + child-AC count) and the leaves
  render as navigation + their own LGD district label, with NO per-AC result
  chip. Groups WITHOUT a header entry stay in assembly mode (proportional
  party strip + per-leaf result chips) - 100% unchanged. The grouping key is
  the leaf `pc_group` (PC name) when present, else `district` (see
  buildGroups + groupKeyOf in the token module); `district` stays the leaf's
  own LGD district in both modes so a PC-mode leaf can show it inline.

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
  state-event-constituency-strip-label. Row 3 ADDS (PC mode):
  state-event-constituency-pc-header, state-event-constituency-pc-leaves,
  state-event-constituency-leaf-district.
-->
<script lang="ts">
  import TopicIcon from "../TopicIcon.svelte";
  import ReservationBadge from "./ReservationBadge.svelte";
  import {
    applyFilters,
    buildGroups,
    distinctDistrictCount,
    formatCountLine,
    marginBand,
    type ConstituencyGroup,
    type GroupHeaderResult,
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
    /** Parliament/PC-mode grouping override (Row 3). When present (general
     *  events: the leaf is an AC and this is its parent PC name) the leaf
     *  groups under this PC instead of `district`, and the PC's result is
     *  supplied separately via the `group_headers` prop. Absent in assembly
     *  mode. Populated by the STATE-lane loader (Row 5). */
    pc_group?: string | null;
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
    /** OPTIONAL parliament/PC mode (Row 3). Keyed by group key (the leaf
     *  `pc_group` in PC mode); when a group's key has an entry here that
     *  group renders the PC result (party chip + share + margin band + child
     *  AC count) in its HEADER and its leaves as navigation + district label
     *  (no per-AC result chip). Absent / null / empty -> assembly mode
     *  (unchanged). Populated by the STATE-lane loader (Row 5). */
    group_headers?: Record<string, GroupHeaderResult> | null;
    /** OPTIONAL embedded mode (Row 7 - national outer accordion). When true,
     *  HIDE this component's OWN search box, Reserved filter, sort control,
     *  count line, and the "Constituencies (N)" heading, because the
     *  embedding page (the national list) owns ONE shared search + Reserved
     *  filter across all states. Every existing consumer omits this
     *  (default false) -> the controls render exactly as before. This is
     *  additive CHROME-VISIBILITY only: the grouping + fold + leaf rendering
     *  are 100% unchanged. */
    hide_controls?: boolean;
  }

  let {
    loading,
    seat_rows,
    fmtInt,
    fmtPct,
    group_headers = null,
    hide_controls = false,
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

  // Group the filtered leaves, attaching either an assembly-mode party strip
  // or a PC-mode header result per group (buildGroups switches on whether
  // group_headers carries an entry for the group key). ONE code path, shared
  // with StateEventConstituencyList.test.ts.
  const groups = $derived.by<ConstituencyGroup<SeatRow>[]>(() =>
    buildGroups(filtered, sort_mode, group_headers),
  );

  // When a search query OR a Reserved filter is active, auto-expand every
  // group so the citizen sees the matches without an extra tap.
  const force_expand_all = $derived(
    search_q.trim().length > 0 || reserved_filter !== "All",
  );

  function isExpanded(d: string): boolean {
    return force_expand_all || expanded.has(d);
  }

  // Single-group special case: exactly one ASSEMBLY group AND no active
  // filter -> treat as auto-expanded so the citizen does not have to tap
  // once to see the only data. The fold shape still ships for when district
  // data lands (Row 4). A PC-mode group always keeps its toggle + result
  // header visible, so it never collapses into this single-group path.
  const single_group = $derived(
    groups.length === 1 && !force_expand_all && groups[0]?.mode !== "pc",
  );
</script>

<!-- Constituency table -->
<section
  class="space-y-2"
  data-testid="state-event-constituency-table"
>
  {#if !hide_controls}
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 class="text-sm font-semibold text-slate-800">
        Constituencies ({loading ? "-" : fmtInt(seat_rows.length)})
      </h2>
    </div>
  {/if}
  {#if loading}
    <p
      class="text-xs text-slate-500"
      data-testid="state-event-constituency-table-loading"
    >Loading constituency results...</p>
  {:else if seat_rows.length === 0}
    <p class="text-xs text-slate-500">No constituency rows yet.</p>
  {:else}
    {#if !hide_controls}
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
    {/if}

    {#if groups.length === 0}
      <p class="text-xs text-slate-500">
        No constituencies match
        <code class="rounded bg-slate-100 px-1">{search_q}</code>.
      </p>
    {:else}
      <ul class="divide-y border-y">
        {#each groups as g (g.group_key)}
          {@const open = isExpanded(g.group_key) || single_group}
          <li data-testid="state-event-constituency-district-row">
            {#if !single_group}
              <button
                type="button"
                class="flex w-full items-center justify-between gap-3 px-2 py-2 text-left text-sm hover:bg-slate-50"
                data-testid="state-event-constituency-district-toggle"
                aria-expanded={open}
                onclick={() => toggleDistrict(g.group_key)}
              >
                <span class="flex min-w-0 items-center gap-2">
                  <TopicIcon
                    name={open ? "chevron-down" : "chevron-right"}
                    cls="h-4 w-4 shrink-0 text-slate-400"
                  />
                  <span class="truncate font-medium text-slate-800">{g.group_key}</span>
                  {#if g.mode === "pc" && g.header_result}
                    <ReservationBadge
                      reservation={g.header_result.reservation}
                      cls="shrink-0 align-middle"
                    />
                    <span class="shrink-0 text-xs tabular-nums text-slate-500">
                      {fmtInt(g.header_result.child_count)}
                    </span>
                  {:else}
                    <span class="shrink-0 text-xs tabular-nums text-slate-500">
                      {fmtInt(g.rows.length)}
                    </span>
                  {/if}
                </span>
                {#if g.mode === "pc" && g.header_result}
                  {@const hband = marginBand(g.header_result.margin)}
                  <!-- PC mode: the GROUP HEADER carries the PC's parliament
                       (MP) result - party chip + share + margin band - in
                       place of the assembly proportional party strip. -->
                  <span
                    class="flex min-w-0 items-center gap-2"
                    data-testid="state-event-constituency-pc-header"
                  >
                    <span
                      class="inline-block rounded px-1.5 py-0.5 text-xs font-medium text-white"
                      style={`background-color:${g.header_result.color};`}
                    >{g.header_result.chip}</span>
                    <span class="hidden shrink-0 text-xs tabular-nums text-slate-600 sm:inline">
                      {fmtPct(g.header_result.share)}
                    </span>
                    <span class="inline-flex shrink-0 items-center justify-end gap-1 tabular-nums">
                      {#if hband}
                        <span
                          aria-hidden="true"
                          class="inline-block h-2 w-2 rounded-sm"
                          style={`background-color:${hband.hex};`}
                          title={hband.label}
                        ></span>
                      {/if}
                      <span
                        class="text-xs font-semibold"
                        style={hband ? `color:${hband.hex};` : ""}
                      >{fmtPct(g.header_result.margin)}</span>
                    </span>
                  </span>
                {:else if g.strip}
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
                {/if}
              </button>
            {/if}

            {#if open}
              {#if g.mode === "pc"}
                <!-- PC mode: leaves render as navigation + a district label
                     only (no per-AC result chip, no per-leaf strip cell).
                     Each leaf is a child AC of this PC, tagged with its LGD
                     district. -->
                <ul class="divide-y" data-testid="state-event-constituency-pc-leaves">
                  {#each g.rows as r (r.entity_id)}
                    <li
                      class="flex items-center justify-between gap-3 py-2 pl-6 pr-2 text-sm hover:bg-slate-50"
                      data-testid="state-event-constituency-row"
                    >
                      <span class="flex min-w-0 items-center gap-1">
                        <a
                          class="truncate text-sky-700 hover:underline"
                          href={r.href}
                          data-testid="state-event-constituency-link"
                        >{r.entity_name}</a>
                        <ReservationBadge reservation={r.reservation} cls="shrink-0 align-middle" />
                      </span>
                      {#if r.district}
                        <span
                          class="shrink-0 truncate text-xs text-slate-500"
                          data-testid="state-event-constituency-leaf-district"
                        >-&gt; {r.district}</span>
                      {/if}
                    </li>
                  {/each}
                </ul>
              {:else}
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
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
