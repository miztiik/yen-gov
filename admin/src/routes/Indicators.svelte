<script lang="ts">
  // Indicators panel — operator's view of every indicator's folded v3.0
  // completeness summary. Wraps `/api/inventory/indicators` (which in
  // turn wraps `datasets/reference/in/indicators-completeness.json`).
  //
  // The point: a single sortable + filterable table that tells the
  // operator at a glance which indicators are stubs, which are stale,
  // and which need ingest. Reuses the index file the citizen-facing
  // `/data-completeness` route consumes, so the operator and the
  // public surface are never out of sync (a folded-indicator PR
  // commitment).

  import { api, type IndicatorIndexRow, type IndicatorsInventoryResponse } from "../lib/api";

  type SortKey =
    | "topic"
    | "id"
    | "documentation_status"
    | "inventory_status"
    | "observed_count"
    | "pending_count"
    | "unavailable_count"
    | "last_collected_at";

  let data = $state<IndicatorsInventoryResponse | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(false);

  let q = $state("");
  let topic_filter = $state<string>("");
  let doc_filter = $state<string>("");
  let inv_filter = $state<string>("");
  let sort_key = $state<SortKey>("topic");
  let sort_dir = $state<"asc" | "desc">("asc");

  async function load(): Promise<void> {
    loading = true;
    error = null;
    try {
      data = await api.indicators();
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }
  void load();

  const topics = $derived.by<string[]>(() => {
    if (!data) return [];
    return [...new Set(data.indicators.map(r => r.topic))].sort();
  });

  function toggle_sort(k: SortKey): void {
    if (sort_key === k) {
      sort_dir = sort_dir === "asc" ? "desc" : "asc";
    } else {
      sort_key = k;
      sort_dir = "asc";
    }
  }

  function cmp(a: IndicatorIndexRow, b: IndicatorIndexRow): number {
    const av = a[sort_key];
    const bv = b[sort_key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return sort_dir === "asc" ? -1 : 1;
    if (av > bv) return sort_dir === "asc" ? 1 : -1;
    return 0;
  }

  const rows = $derived.by<IndicatorIndexRow[]>(() => {
    if (!data) return [];
    const needle = q.trim().toLowerCase();
    return data.indicators
      .filter(r => !topic_filter || r.topic === topic_filter)
      .filter(r => !doc_filter || r.documentation_status === doc_filter)
      .filter(r => !inv_filter || r.inventory_status === inv_filter)
      .filter(r => !needle || r.id.toLowerCase().includes(needle) || r.title.toLowerCase().includes(needle))
      .slice()
      .sort(cmp);
  });

  function fmt_date(iso: string | null): string {
    if (!iso) return "—";
    return iso.slice(0, 10);
  }

  function doc_badge(s: IndicatorIndexRow["documentation_status"]): string {
    return s === "authored"
      ? "bg-emerald-900/60 text-emerald-300"
      : s === "partial"
        ? "bg-amber-900/60 text-amber-300"
        : "bg-rose-900/60 text-rose-300";
  }
  function inv_badge(s: IndicatorIndexRow["inventory_status"]): string {
    return s === "complete"
      ? "bg-emerald-900/60 text-emerald-300"
      : s === "partial"
        ? "bg-amber-900/60 text-amber-300"
        : "bg-slate-800 text-slate-400";
  }
</script>

<section class="space-y-4">
  <header class="flex items-baseline justify-between gap-4">
    <div>
      <h2 class="text-lg font-semibold">Indicators</h2>
      <p class="text-xs text-slate-400">
        Folded v3.0 completeness summary for every indicator. Wraps
        <code class="font-mono">datasets/reference/in/indicators-completeness.json</code>;
        regenerate with
        <code class="font-mono">python tools/emit_indicators_completeness_index.py --write</code>
        then refresh.
      </p>
    </div>
    <button
      class="text-xs rounded border border-slate-700 px-3 py-1 hover:bg-slate-800 disabled:opacity-50"
      onclick={() => void load()}
      disabled={loading}
    >{loading ? "Refreshing…" : "Refresh"}</button>
  </header>

  {#if error}
    <div class="p-3 bg-rose-950 border border-rose-800 rounded text-rose-200 text-sm">
      <p class="font-semibold">Failed to reach the admin API.</p>
      <p class="text-xs mt-1 font-mono break-all">{error}</p>
    </div>
  {:else if !data}
    <p class="text-sm text-slate-400">Loading…</p>
  {:else}
    <div class="flex flex-wrap items-end gap-3 text-xs">
      <label class="flex flex-col gap-1">
        <span class="text-slate-500">Search id/title</span>
        <input
          type="search"
          bind:value={q}
          placeholder="e.g. gdp, capacity"
          class="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-48"
        />
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-slate-500">Topic</span>
        <select bind:value={topic_filter} class="bg-slate-900 border border-slate-700 rounded px-2 py-1">
          <option value="">All</option>
          {#each topics as t (t)}
            <option value={t}>{t}</option>
          {/each}
        </select>
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-slate-500">Docs</span>
        <select bind:value={doc_filter} class="bg-slate-900 border border-slate-700 rounded px-2 py-1">
          <option value="">All</option>
          <option value="stub">stub</option>
          <option value="partial">partial</option>
          <option value="authored">authored</option>
        </select>
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-slate-500">Inventory</span>
        <select bind:value={inv_filter} class="bg-slate-900 border border-slate-700 rounded px-2 py-1">
          <option value="">All</option>
          <option value="empty">empty</option>
          <option value="partial">partial</option>
          <option value="complete">complete</option>
        </select>
      </label>
      <p class="ml-auto text-slate-500">
        Showing {rows.length} of {data.count} · index mtime {fmt_date(data.index_mtime)}
      </p>
    </div>

    <div class="overflow-x-auto rounded border border-slate-800">
      <table class="w-full text-xs tabular-nums">
        <thead class="bg-slate-900 text-slate-400 text-left">
          <tr>
            <th class="px-3 py-2 font-normal cursor-pointer" onclick={() => toggle_sort("topic")}>Topic</th>
            <th class="px-3 py-2 font-normal cursor-pointer" onclick={() => toggle_sort("id")}>Indicator</th>
            <th class="px-3 py-2 font-normal cursor-pointer" onclick={() => toggle_sort("documentation_status")}>Docs</th>
            <th class="px-3 py-2 font-normal cursor-pointer" onclick={() => toggle_sort("inventory_status")}>Coverage</th>
            <th class="px-3 py-2 font-normal text-right cursor-pointer" onclick={() => toggle_sort("observed_count")}>obs</th>
            <th class="px-3 py-2 font-normal text-right cursor-pointer" onclick={() => toggle_sort("pending_count")}>pend</th>
            <th class="px-3 py-2 font-normal text-right cursor-pointer" onclick={() => toggle_sort("unavailable_count")}>unav</th>
            <th class="px-3 py-2 font-normal cursor-pointer" onclick={() => toggle_sort("last_collected_at")}>Last collected</th>
            <th class="px-3 py-2 font-normal">Path</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as r (r.path)}
            <tr class="border-t border-slate-800 hover:bg-slate-900/50">
              <td class="px-3 py-1.5 text-slate-300">{r.topic}</td>
              <td class="px-3 py-1.5">
                <div class="font-mono text-slate-200">{r.id}</div>
                <div class="text-[10px] text-slate-500">{r.title}</div>
              </td>
              <td class="px-3 py-1.5">
                <span class="rounded px-1.5 py-0.5 text-[10px] {doc_badge(r.documentation_status)}">{r.documentation_status}</span>
              </td>
              <td class="px-3 py-1.5">
                <span class="rounded px-1.5 py-0.5 text-[10px] {inv_badge(r.inventory_status)}">{r.inventory_status}</span>
                {#if r.frozen}
                  <span class="ml-1 rounded px-1.5 py-0.5 text-[10px] bg-sky-900/60 text-sky-300" title="Operator-frozen; refresh leaves rows untouched.">frozen</span>
                {/if}
              </td>
              <td class="px-3 py-1.5 text-right text-slate-300">{r.observed_count}</td>
              <td class="px-3 py-1.5 text-right text-slate-400">{r.pending_count}</td>
              <td class="px-3 py-1.5 text-right text-slate-500">{r.unavailable_count}</td>
              <td class="px-3 py-1.5 text-slate-400">{fmt_date(r.last_collected_at)}</td>
              <td class="px-3 py-1.5 font-mono text-[10px] text-slate-500 truncate max-w-[28ch]" title={r.path}>{r.path}</td>
            </tr>
          {/each}
          {#if rows.length === 0}
            <tr><td colspan="9" class="px-3 py-4 text-center text-slate-500">No indicators match these filters.</td></tr>
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</section>
