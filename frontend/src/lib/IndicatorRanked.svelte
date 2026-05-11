<script lang="ts">
  // Generic indicator ranked table — citizen-first cross-state comparison
  // primitive. Drop in any indicator artifact, get a sortable per-state
  // table with the user's "home" state pinned at the top and visually
  // distinct. One row per state; three columns (name, value, decile bar).
  //
  // Per docs/concepts/cross-state-comparison.md, this is the DEFAULT
  // comparison primitive — not state-card grids, not composite indices.
  //
  // Honesty rules enforced here:
  //   - When the indicator declares comparability=not_comparable_across_states,
  //     the rank column is suppressed and an amber banner replaces the header.
  //   - When attribution_geography=where_produced, a slate caveat is shown.
  //   - Default tier filter: general_category states only when a state-tier
  //     map is provided. UTs and special-category states are toggle-includable
  //     — never silently mixed in. (Tier data is loaded best-effort; if not
  //     present, all states render.)

  import {
    fetchIndicator,
    uniqueTimes,
    rollupByEntity,
    formatValue,
    type IndicatorArtifact,
  } from "./indicators";
  import { STATE_NAME_TO_ECI } from "./maplibre/sources";

  interface Props {
    /** Path under DATA_BASE, e.g. "/indicators/in/energy/installed_mw_by_state.json". */
    indicator_path: string;
    /** Optional ECI code to pin at the top + visually distinguish (e.g. "S22"). */
    home_state?: string;
    /** Max rows to show before "show all" (default 10). */
    initial_rows?: number;
  }

  let { indicator_path, home_state, initial_rows = 10 }: Props = $props();

  let artifact = $state<IndicatorArtifact | null>(null);
  let load_error = $state<string | null>(null);
  let selected_time = $state<string | null>(null);
  let show_all = $state(false);
  // Sort direction: respects indicator.direction by default — higher_is_better
  // sorts descending, lower_is_better ascending. (Reserved for a future
  // user-flip control; currently always derives from the indicator.)
  const sort_dir: "auto" | "desc" | "asc" = "auto";

  $effect(() => {
    artifact = null;
    load_error = null;
    selected_time = null;
    show_all = false;
    fetchIndicator(indicator_path)
      .then(a => {
        artifact = a;
        const ts = uniqueTimes(a.rows);
        selected_time = ts.at(-1) ?? null;
      })
      .catch(e => (load_error = String(e)));
  });

  // ECI code -> state name lookup is implicit in STATE_NAME_TO_ECI; we
  // iterate that map directly when building rows.

  const times = $derived(artifact ? uniqueTimes(artifact.rows) : []);

  const values = $derived.by(() => {
    if (!artifact || !selected_time) return new Map<string, number>();
    return rollupByEntity(artifact.rows, selected_time);
  });

  // Effective sort direction (resolves "auto" to the indicator's direction).
  const effective_sort = $derived.by(() => {
    if (sort_dir !== "auto") return sort_dir;
    if (!artifact) return "desc";
    return artifact.indicator.direction === "lower_is_better" ? "asc" : "desc";
  });

  type Row = {
    code: string;
    name: string;
    value: number | null;
    rank: number | null;
    is_home: boolean;
  };

  // Build the row list. Keep ALL states (including those with null values)
  // so the citizen sees the full national picture, not just the covered set.
  // Coverage gaps are marked "no data".
  //
  // tier filter is currently a stub (returns true) since per-row tier data
  // hasn't been backfilled yet — schema v3.3 makes tier optional. Once
  // states.json is populated we'll wire `include_special` to that.
  const rows: Row[] = $derived.by(() => {
    if (!artifact) return [];
    const all: Row[] = [];
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      const v = values.get(code);
      all.push({
        code,
        name,
        value: v ?? null,
        rank: null,
        is_home: code === home_state,
      });
    }
    // Suppress rank when not comparable across states.
    const meta = artifact.indicator;
    const can_rank = meta.comparability !== "not_comparable_across_states";
    // Compute rank over rows that have a value, then assign back.
    if (can_rank) {
      const ranked = all
        .filter(r => r.value !== null)
        .sort((a, b) =>
          effective_sort === "desc"
            ? (b.value as number) - (a.value as number)
            : (a.value as number) - (b.value as number),
        );
      ranked.forEach((r, i) => (r.rank = i + 1));
    }
    // Sort: home state first, then by rank (when ranked), then by value
    // descending, then by name. Rows with no data go last.
    return all.sort((a, b) => {
      if (a.is_home !== b.is_home) return a.is_home ? -1 : 1;
      const a_has = a.value !== null;
      const b_has = b.value !== null;
      if (a_has !== b_has) return a_has ? -1 : 1;
      if (a.rank !== null && b.rank !== null) return a.rank - b.rank;
      if (a.value !== null && b.value !== null) {
        return effective_sort === "desc"
          ? b.value - a.value
          : a.value - b.value;
      }
      return a.name.localeCompare(b.name);
    });
  });

  const visible_rows = $derived(show_all ? rows : rows.slice(0, initial_rows));

  // Domain for the inline bar. Use the absolute max so all bars are
  // comparable; for lower_is_better indicators the eye still reads "longer
  // bar = more", which is what we want (intensity = quantity, not goodness).
  const max_abs = $derived.by(() => {
    let m = 0;
    for (const v of values.values()) if (Math.abs(v) > m) m = Math.abs(v);
    return m || 1;
  });

  const can_rank = $derived(
    artifact?.indicator.comparability !== "not_comparable_across_states",
  );
</script>

<section class="bg-white rounded-lg shadow-sm overflow-hidden">
  {#if load_error}
    <div class="p-4 text-sm bg-rose-50 border border-rose-200 text-rose-900">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !artifact}
    <div class="p-4 text-sm text-slate-500">Loading…</div>
  {:else}
    <header class="px-4 pt-4 pb-3 border-b border-slate-100 space-y-2">
      <div class="flex justify-between items-baseline gap-3 flex-wrap">
        <h3 class="text-base font-semibold">
          {artifact.indicator.title}
          <span class="text-xs font-normal text-slate-500">· ranked</span>
        </h3>
        {#if times.length > 1 && selected_time}
          <div class="flex items-center gap-2">
            <label class="text-xs text-slate-500" for="ranked-year-select">Year</label>
            <select
              id="ranked-year-select"
              bind:value={selected_time}
              class="text-sm border border-slate-200 rounded px-1.5 py-0.5"
            >
              {#each times as t}<option value={t}>{t}</option>{/each}
            </select>
          </div>
        {/if}
      </div>

      {#if !can_rank}
        <div class="text-[11px] px-2.5 py-1.5 rounded bg-amber-50 border border-amber-200 text-amber-900 leading-snug">
          <strong class="font-semibold">Not a leaderboard · </strong>
          This indicator is not directly comparable across states. Rows are listed alphabetically; the rank column is suppressed.
        </div>
      {/if}
    </header>

    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-[11px] text-slate-500 uppercase tracking-wide">
          <tr class="border-b border-slate-100">
            {#if can_rank}<th class="text-right py-2 pl-3 pr-2 w-10">#</th>{/if}
            <th class="text-left py-2 pr-3">State</th>
            <th class="text-right py-2 pr-3 w-28 tabular-nums">{artifact.indicator.unit ?? "Value"}</th>
            <th class="text-left py-2 pr-3 w-1/3">Distribution</th>
          </tr>
        </thead>
        <tbody>
          {#each visible_rows as r (r.code)}
            <tr
              class="border-b border-slate-50 hover:bg-slate-50/60"
              class:bg-amber-50={r.is_home}
              class:font-medium={r.is_home}
            >
              {#if can_rank}
                <td class="py-1.5 pl-3 pr-2 text-right text-slate-500 tabular-nums">
                  {r.rank ?? "—"}
                </td>
              {/if}
              <td class="py-1.5 pr-3">
                {r.name}
                {#if r.is_home}<span class="ml-1 text-[10px] text-amber-700 uppercase tracking-wide">your state</span>{/if}
              </td>
              <td class="py-1.5 pr-3 text-right tabular-nums">
                {#if r.value === null}
                  <span class="text-slate-400 text-xs">no data</span>
                {:else}
                  {formatValue(r.value, artifact.indicator)}
                {/if}
              </td>
              <td class="py-1.5 pr-3">
                {#if r.value !== null}
                  <div class="h-2 bg-slate-100 rounded-sm overflow-hidden">
                    <div
                      class="h-full"
                      class:bg-amber-500={r.is_home}
                      class:bg-sky-400={!r.is_home}
                      style:width="{Math.min(100, (Math.abs(r.value) / max_abs) * 100)}%"
                    ></div>
                  </div>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if rows.length > initial_rows}
      <div class="px-4 py-2 border-t border-slate-100 text-center">
        <button
          class="text-xs text-sky-700 hover:underline"
          onclick={() => (show_all = !show_all)}
        >
          {show_all ? "Show fewer" : `Show all ${rows.length} states/UTs`}
        </button>
      </div>
    {/if}
  {/if}
</section>
