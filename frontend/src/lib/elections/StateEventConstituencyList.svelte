<!--
  StateEventConstituencyList - extracted from StateElection.svelte during
  R3 (Beck two-hat: pure structural extraction, no behaviour change) of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  R4 (same plan-doc, Section 5) rebuilds this surface per the Jony +
  Citizen verdict baked into the row spec:
   - Sticky search input ABOVE the list (sticky to this section's
     scroll boundary, not page-top).
   - District-grouped folded list: each row [district][N constituencies]
     [winner-party-mix dot-strip]; tap expands inline. ALL districts
     collapsed on first paint (mobile + desktop).
   - The flat 288-row table is RETIRED on this surface; it was carrying
     no narrative beyond what the grouped fold offers (the per-AC
     drill-down route remains the path for citizens who want the row).

  The trailing "Compare with <prior event>" CTA was REMOVED 2026-06-22 as
  redundant: the SiblingEventsRail above the map already offers the
  compare affordance ("See how this election compares with <prior year>").

  Preserves data-testids: state-event-constituency-table /
  state-event-constituency-table-loading / state-event-constituency-row /
  state-event-constituency-link. R4 ADDS:
  state-event-constituency-search,
  state-event-constituency-district-row,
  state-event-constituency-district-toggle.
-->
<script lang="ts">
  export interface SeatRow {
    entity_id: string;
    entity_name: string;
    /** Human-readable district name when the upstream loader could
     *  derive it from the AC/PC metadata; null when no district label
     *  is available (rare; falls back to a single "All constituencies"
     *  group). The current ElectionResultRow loader does NOT carry
     *  district yet - that is a parallel ingest concern - so the
     *  default is null and every seat renders under one group. This
     *  preserves the fold + search benefit without blocking on the
     *  ingest. When district lands, the grouping becomes
     *  meaningful without a re-author of this component. */
    district?: string | null;
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

  // Search query (case-insensitive substring match on entity_name).
  let search_q = $state("");

  // Fold state: a Set of district names that are EXPANDED. Default
  // empty = all districts collapsed on first paint.
  let expanded = $state<Set<string>>(new Set());

  // Reset fold + search when the seat-rows identity changes (event
  // navigation). The list re-mounts on each new event so the citizen
  // does not carry "expanded Dharavi" from Maharashtra 2024 into
  // Maharashtra 2019.
  let prev_first_id = $state<string | null>(null);
  $effect(() => {
    const first = seat_rows[0]?.entity_id ?? null;
    if (first !== prev_first_id) {
      expanded = new Set();
      search_q = "";
      prev_first_id = first;
    }
  });

  function toggleDistrict(d: string): void {
    const next = new Set(expanded);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    expanded = next;
  }

  // Filter by search query first; then group by district.
  const filtered = $derived.by<readonly SeatRow[]>(() => {
    const q = search_q.trim().toLowerCase();
    if (!q) return seat_rows;
    return seat_rows.filter((r) => r.entity_name.toLowerCase().includes(q));
  });

  interface DistrictGroup {
    district: string;
    rows: SeatRow[];
    /** Up to 6 winner-color hex strings for the dot-strip on the
     *  collapsed row. We dedupe by hex so repeats don't dominate the
     *  glance. */
    dot_strip: string[];
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
      const seen = new Set<string>();
      const dot_strip: string[] = [];
      for (const r of rows) {
        if (seen.has(r.winner_color)) continue;
        seen.add(r.winner_color);
        dot_strip.push(r.winner_color);
        if (dot_strip.length >= 6) break;
      }
      out.push({ district, rows, dot_strip });
    }
    out.sort((a, b) => a.district.localeCompare(b.district, "en"));
    return out;
  });

  // When a search query is active, auto-expand every group so the
  // citizen sees the matches without an extra tap. When the query
  // clears, return to the user's manual fold state.
  const force_expand_all = $derived(search_q.trim().length > 0);

  function isExpanded(d: string): boolean {
    return force_expand_all || expanded.has(d);
  }

  // Single-group special case: when there's exactly one group AND no
  // search filter, treat it as "auto-expanded" so the citizen doesn't
  // have to tap once to see the only data. The grouping shape still
  // ships so when district lands later we get the fold benefit for
  // free.
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
    <!-- Sticky search input (R4 J-elevated-8 - sticky to section's
         scroll boundary, NOT page top). On wide screens the input
         still scrolls naturally with the section so it doesn't
         pin to the viewport edge. -->
    <div class="sticky top-0 z-10 -mx-1 bg-white/95 px-1 py-1 backdrop-blur">
      <label class="block">
        <span class="sr-only">Filter constituencies</span>
        <input
          type="search"
          placeholder="Filter constituencies..."
          class="w-full rounded border border-slate-300 px-3 py-1.5 text-sm placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          data-testid="state-event-constituency-search"
          bind:value={search_q}
        />
      </label>
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
                <span class="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    class="inline-block w-2 text-slate-400"
                  >{open ? "v" : ">"}</span>
                  <span class="font-medium text-slate-800">{g.district}</span>
                </span>
                <span class="flex items-center gap-2">
                  <span class="text-xs text-slate-500 tabular-nums">
                    {fmtInt(g.rows.length)}
                  </span>
                  <span aria-hidden="true" class="flex gap-0.5">
                    {#each g.dot_strip as hex (hex)}
                      <span
                        class="inline-block h-2 w-2 rounded-full"
                        style="background-color: {hex};"
                      ></span>
                    {/each}
                  </span>
                </span>
              </button>
            {/if}

            {#if open}
              <table class="w-full text-sm">
                <thead class="text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th class="py-1 pl-6">Constituency</th>
                    <th class="py-1">Winner</th>
                    <th class="py-1 text-right">Share</th>
                    <th class="py-1 pr-2 text-right">Margin</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  {#each g.rows as r (r.entity_id)}
                    <tr
                      class="hover:bg-slate-50"
                      data-testid="state-event-constituency-row"
                    >
                      <td class="py-2 pl-6">
                        <a
                          class="text-sky-700 hover:underline"
                          href={r.href}
                          data-testid="state-event-constituency-link"
                        >{r.entity_name}</a>
                      </td>
                      <td class="py-2">
                        <span
                          class="inline-block rounded px-1.5 py-0.5 text-xs font-medium text-white"
                          style={`background-color:${r.winner_color};`}
                        >{r.winner_party_short}</span>
                      </td>
                      <td class="py-2 text-right tabular-nums">
                        {fmtPct(r.winner_share_pct)}
                      </td>
                      <td class="py-2 pr-2 text-right tabular-nums">
                        {fmtPct(r.margin_pct)}
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
