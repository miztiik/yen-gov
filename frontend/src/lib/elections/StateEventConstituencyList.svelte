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
  state-event-constituency-pc-header, state-event-constituency-leaf-district.

  Row 3 (Option-E margin-bar, 2026-06-25) RIPS the flex `justify-between`
  PC header AND the dashed result <table> and REPLACES both with a single
  6-track CSS subgrid (the shared GRID_COLS ruler from
  ./constituency-list-tokens): every group header and every AC leaf is a
  `grid grid-cols-subgrid col-span-full` row, so the PC header, the AC
  leaf, and (Row 4) the national state rail align column-for-column on ONE
  ruler. The per-group `state-event-constituency-pc-leaves` <ul> wrapper is
  GONE (the leaves are flattened into the subgrid; no test referenced it).
  The AC leaf is now a WHOLE-ROW <a> link (Tailwind `group`) carrying a
  trailing arrow-up-right jump glyph + a map-pin district cell; unlinked
  ACs pool in the PENDING_GROUP bucket (muted "data pending", never a
  dashed cell). Both share AND signed-margin tokens now render below 640px.
-->
<script lang="ts">
  import TopicIcon from "../TopicIcon.svelte";
  import ReservationBadge from "./ReservationBadge.svelte";
  import {
    applyFilters,
    buildGroups,
    distinctDistrictCount,
    fmtMarginSigned,
    fmtShare,
    formatCountLine,
    GRID_COLS,
    marginBand,
    marginBarSegment,
    PENDING_GROUP,
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

  // PC mode for the WHOLE call: when group_headers is supplied every leaf is
  // navigation + its LGD district (the result lives on the PC header, and the
  // state-level result on the Row 4 rail), so the per-AC result columns
  // (tracks 4-6) stay EMPTY on the leaf. Mirrors the token module's `pc_mode`
  // switch in buildGroups so the renderer and the grouping never disagree.
  const pc_mode = $derived(group_headers != null);

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
      <!-- Option-E subgrid (Row 3 rip-and-replace): ONE 6-track ruler
           (GRID_COLS) is declared on this parent <ul>; every group header and
           every leaf is a `grid grid-cols-subgrid col-span-full` row, so the
           PC header, the AC leaf, and (Row 4) the national state rail align
           column-for-column on the SAME ruler. The old flex `justify-between`
           PC header and the dashed result <table> are GONE: share + margin
           live in fixed tracks that never shift, and both stay visible below
           640px. Tracks: 1 twist | 2 name | 3 context | 4 party | 5 share |
           6 margin+bar. Horizontal padding is kept OFF the subgrid rows on
           purpose - a subgrid item's inline padding shifts its own tracks out
           of alignment; the inset lives on this root grid instead. -->
      <ul class={`grid ${GRID_COLS} gap-x-2 divide-y border-y px-1`}>
        {#each groups as g (g.group_key)}
          {@const open = isExpanded(g.group_key) || single_group}
          {@const pending = g.group_key === PENDING_GROUP}
          <!-- The single-group auto-expand hides a redundant header (e.g. a
               lone district name) and renders its leaves flat. The pending
               bucket is the ONE exception: its "Parliament seat pending" title
               is meaningful context (D5), so it is NEVER suppressed - a
               whole-state all-pending event (Delhi 70/70) collapses to ONE
               PENDING_GROUP group and must keep its header. The leaves still
               auto-expand via `open` above. -->
          {@const hide_header = single_group && !pending}
          <li
            data-testid="state-event-constituency-district-row"
            class="col-span-full grid grid-cols-subgrid divide-y"
          >
            {#if !hide_header}
              <button
                type="button"
                class={`col-span-full grid grid-cols-subgrid items-center py-2 text-left text-sm hover:bg-slate-50 ${
                  open ? "bg-slate-50" : ""
                }`}
                data-testid="state-event-constituency-district-toggle"
                aria-expanded={open}
                onclick={() => toggleDistrict(g.group_key)}
              >
                <!-- track 1: expand/collapse twist -->
                <TopicIcon
                  name={open ? "chevron-down" : "chevron-right"}
                  cls="col-start-1 h-4 w-4 shrink-0 justify-self-center text-slate-400"
                />
                {#if g.mode === "pc" && g.header_result}
                  {@const hbar = marginBarSegment(g.header_result.margin)}
                  {@const hhex = marginBand(g.header_result.margin)?.hex}
                  <!-- PC mode: the GROUP HEADER carries the PC's parliament
                       (MP) result across tracks 2-6 (name + badge, child-AC
                       count, party chip, share, signed margin + bar). -->
                  <span class="col-start-2 flex min-w-0 items-center gap-1.5 pl-1">
                    <span class="truncate font-medium text-slate-800">{g.group_key}</span>
                    <ReservationBadge
                      reservation={g.header_result.reservation}
                      cls="shrink-0 align-middle"
                    />
                  </span>
                  <span class="col-start-3 truncate text-xs tabular-nums text-slate-500">
                    {fmtInt(g.header_result.child_count)} Assembly seats
                  </span>
                  <span
                    class="col-start-4 inline-block justify-self-start rounded px-1.5 py-0.5 text-xs font-medium text-white"
                    style={`background-color:${g.header_result.color};`}
                    data-testid="state-event-constituency-pc-header"
                  >{g.header_result.chip}</span>
                  <span class="col-start-5 justify-self-end text-xs tabular-nums text-slate-600">
                    {fmtShare(g.header_result.share)}
                  </span>
                  <span class="col-start-6 flex items-center justify-end gap-1.5 tabular-nums">
                    <span
                      aria-hidden="true"
                      class="inline-block h-1.5 w-8 shrink-0 overflow-hidden rounded-sm bg-slate-100"
                    >
                      <span
                        class="block h-full"
                        style={`width:${hbar.pct}%;background-color:${hbar.hex};`}
                      ></span>
                    </span>
                    <span
                      class="text-xs font-semibold"
                      style={hhex ? `color:${hhex};` : ""}
                    >{fmtMarginSigned(g.header_result.margin)}</span>
                  </span>
                {:else if pending}
                  <!-- Pending bucket: the SAME header shape, but the PC result
                       is not known yet, so tracks 5-6 read a muted "data
                       pending" instead of a dashed result cell. -->
                  <span class="col-start-2 flex min-w-0 items-center gap-1.5 pl-1">
                    <span class="truncate font-medium text-slate-500">{PENDING_GROUP}</span>
                  </span>
                  <span class="col-start-3 truncate text-xs tabular-nums text-slate-500">
                    {fmtInt(g.rows.length)} Assembly seats
                  </span>
                  <span class="justify-self-end text-xs italic text-slate-400 [grid-column:5/-1]">
                    data pending
                  </span>
                {:else}
                  <!-- Assembly mode: district name + the proportional party
                       strip glance (the per-AC result chips live on the leaves
                       below). -->
                  <span class="col-start-2 flex min-w-0 items-center gap-1.5 pl-1">
                    <span class="truncate font-medium text-slate-800">{g.group_key}</span>
                    <span class="shrink-0 text-xs tabular-nums text-slate-500">{fmtInt(g.rows.length)}</span>
                  </span>
                  {#if g.strip}
                    <span class="flex min-w-0 items-center justify-end gap-2 [grid-column:3/-1]">
                      <!-- Proportional segmented party strip: one segment per
                           winning party, width proportional to seats won. -->
                      <span
                        aria-hidden="true"
                        class="flex h-2.5 w-16 shrink-0 overflow-hidden rounded-sm border border-slate-200 sm:w-24"
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
                {/if}
              </button>
            {/if}

            {#if open}
              {#each g.rows as r (r.entity_id)}
                <!-- Leaf: the WHOLE row is the AC link (Tailwind `group`), so
                     the entire band is clickable; track 2 carries a muted
                     arrow-up-right jump glyph that brightens on hover. Tracks
                     4-6 stay EMPTY in PC mode (the result lives on the PC
                     header) and carry the per-AC chip + share + margin in
                     assembly mode. -->
                <a
                  href={r.href}
                  class="group col-span-full grid grid-cols-subgrid items-center py-2 text-sm hover:bg-slate-50"
                  data-testid="state-event-constituency-row"
                >
                  <!-- track 1: leaf connector (depth 2) -->
                  <span
                    aria-hidden="true"
                    class="col-start-1 block h-px w-2.5 justify-self-center bg-slate-300"
                  ></span>
                  <!-- track 2: ballot-number prefix + AC name + badge + jump glyph -->
                  <span class="col-start-2 flex min-w-0 items-center gap-1 pl-5">
                    {#if has_eci && r.eci_no !== null && r.eci_no !== undefined}
                      <span class="shrink-0 text-xs tabular-nums text-slate-400">{r.eci_no}</span>
                    {/if}
                    <span
                      class="truncate text-sky-700 group-hover:underline"
                      data-testid="state-event-constituency-link"
                    >{r.entity_name}</span>
                    <ReservationBadge reservation={r.reservation} cls="shrink-0 align-middle" />
                    <TopicIcon
                      name="arrow-up-right"
                      cls="h-3.5 w-3.5 shrink-0 text-slate-300 group-hover:text-sky-600"
                    />
                  </span>
                  <!-- track 3: LGD district (map-pin) or pending fallback;
                       drops UNDER the name on < 640px so the result columns
                       keep their width on a phone. -->
                  <span
                    class="col-start-3 flex min-w-0 items-center gap-1 text-xs text-slate-500 max-sm:col-start-2 max-sm:row-start-2 max-sm:pl-5"
                    data-testid="state-event-constituency-leaf-district"
                  >
                    {#if r.district}
                      <TopicIcon name="map-pin" cls="h-3 w-3 shrink-0 text-slate-400" />
                      <span class="truncate">{r.district}</span>
                    {:else}
                      <span class="truncate italic text-slate-400">District pending</span>
                    {/if}
                  </span>
                  {#if !pc_mode}
                    {@const lbar = marginBarSegment(r.margin_pct)}
                    {@const lhex = marginBand(r.margin_pct)?.hex}
                    <!-- tracks 4-6: per-AC winner chip + share + signed margin
                         + bar (assembly mode only). -->
                    <span
                      class="col-start-4 inline-block justify-self-start rounded px-1.5 py-0.5 text-xs font-medium text-white"
                      style={`background-color:${r.winner_color};`}
                    >{r.winner_party_short}</span>
                    <span class="col-start-5 justify-self-end text-xs tabular-nums text-slate-600">
                      {fmtShare(r.winner_share_pct)}
                    </span>
                    <span class="col-start-6 flex items-center justify-end gap-1.5 tabular-nums">
                      <span
                        aria-hidden="true"
                        class="inline-block h-1.5 w-8 shrink-0 overflow-hidden rounded-sm bg-slate-100"
                      >
                        <span
                          class="block h-full"
                          style={`width:${lbar.pct}%;background-color:${lbar.hex};`}
                        ></span>
                      </span>
                      <span
                        class="text-xs font-semibold"
                        style={lhex ? `color:${lhex};` : ""}
                      >{fmtMarginSigned(r.margin_pct)}</span>
                    </span>
                  {/if}
                </a>
              {/each}
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>
