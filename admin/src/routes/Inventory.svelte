<script lang="ts">
  // Inventory panel — family-agnostic view of the canonical Parquet store.
  //
  // Two tables, one query:
  //   1. Stores  — every Parquet under `datasets/` (observations, dim,
  //                taxonomy). Family = top-level dir. The day energy /
  //                demography / fiscal / health land their own
  //                `<family>/observations.parquet`, they show up here
  //                automatically with zero code change.
  //   2. Indicators — per-indicator rollup across every observations.parquet.
  //                   Complementary to the docs-completeness Indicators
  //                   panel: this one says "is there data for it on disk".

  import { api, type Inventory, type InventoryStore, type InventoryIndicator } from "../lib/api";

  let data = $state<Inventory | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(false);

  async function load(): Promise<void> {
    loading = true;
    error = null;
    try {
      data = await api.inventory();
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }
  void load();

  function fmtTime(iso: string | undefined | null): string {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toISOString().replace("T", " ").slice(0, 16) + "Z";
  }

  // Bytes shown as KB / MB / GB so a 14 MB observations.parquet doesn't
  // render as "14772201" and crowd the column.
  function fmtBytes(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
    return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  function fmtNum(n: number | null | undefined): string {
    return n == null ? "—" : n.toLocaleString();
  }

  function fmtYearRange(a: number | null, b: number | null): string {
    if (a == null && b == null) return "—";
    if (a === b) return String(a);
    return `${a ?? "?"} – ${b ?? "?"}`;
  }

  function kindBadge(k: InventoryStore["kind"]): string {
    switch (k) {
      case "observations": return "bg-emerald-950 text-emerald-300";
      case "dim":          return "bg-sky-950 text-sky-300";
      case "taxonomy":     return "bg-amber-950 text-amber-300";
      default:             return "bg-slate-800 text-slate-400";
    }
  }
</script>

<section class="space-y-6">
  <header class="flex items-baseline justify-between">
    <div>
      <h2 class="text-lg font-semibold">Inventory</h2>
      <p class="text-xs text-slate-400">
        Canonical Parquet store under <code class="font-mono">datasets/</code>.
        Every <code class="font-mono">&lt;family&gt;/observations.parquet</code>
        is summarised by DuckDB; <code class="font-mono">dim_*</code> and
        <code class="font-mono">taxonomy/*</code> show row counts only.
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
      <p class="text-xs mt-2">
        Make sure <code class="font-mono">uvicorn yen_gov.admin:app --port 8000</code> is running.
      </p>
    </div>
  {:else if !data}
    <p class="text-sm text-slate-400">Loading…</p>
  {:else}
    <!-- Stores table — one row per .parquet file. -->
    <div>
      <h3 class="text-sm uppercase tracking-wide text-slate-400 font-semibold mb-2">
        Stores
        <span class="text-slate-600 font-normal normal-case">· {data.stores.length} file{data.stores.length === 1 ? "" : "s"}</span>
      </h3>
      {#if data.stores.length === 0}
        <p class="text-sm text-slate-400">No Parquet files found under <code class="font-mono">datasets/</code>.</p>
      {:else}
        <div class="overflow-x-auto rounded border border-slate-800">
          <table class="w-full text-xs tabular-nums">
            <thead class="bg-slate-900 text-slate-400 text-left">
              <tr>
                <th class="px-3 py-2 font-normal">Family</th>
                <th class="px-3 py-2 font-normal">Kind</th>
                <th class="px-3 py-2 font-normal">Path</th>
                <th class="px-3 py-2 font-normal text-right">Rows</th>
                <th class="px-3 py-2 font-normal text-right">Indicators</th>
                <th class="px-3 py-2 font-normal text-right">Entities</th>
                <th class="px-3 py-2 font-normal text-right">Periods</th>
                <th class="px-3 py-2 font-normal text-right">Years</th>
                <th class="px-3 py-2 font-normal text-right">Sources</th>
                <th class="px-3 py-2 font-normal text-right">Size</th>
                <th class="px-3 py-2 font-normal">Last write</th>
              </tr>
            </thead>
            <tbody class="bg-slate-950">
              {#each data.stores as s (s.path)}
                <tr class="border-t border-slate-900 align-top">
                  <td class="px-3 py-2 font-mono">{s.family}</td>
                  <td class="px-3 py-2">
                    <span class={"px-1.5 py-0.5 rounded text-[10px] font-mono " + kindBadge(s.kind)}>{s.kind}</span>
                  </td>
                  <td class="px-3 py-2 font-mono text-slate-300 break-all">{s.path}</td>
                  <td class="px-3 py-2 text-right">{fmtNum(s.row_count)}</td>
                  <td class="px-3 py-2 text-right">{fmtNum(s.stats?.indicators)}</td>
                  <td class="px-3 py-2 text-right">{fmtNum(s.stats?.entities)}</td>
                  <td class="px-3 py-2 text-right">{fmtNum(s.stats?.periods)}</td>
                  <td class="px-3 py-2 text-right text-slate-400">
                    {fmtYearRange(s.stats?.min_year ?? null, s.stats?.max_year ?? null)}
                  </td>
                  <td class="px-3 py-2 text-right">{fmtNum(s.stats?.sources)}</td>
                  <td class="px-3 py-2 text-right text-slate-400">{fmtBytes(s.size_bytes)}</td>
                  <td class="px-3 py-2 font-mono text-slate-500">{fmtTime(s.mtime)}</td>
                </tr>
                {#if s.error}
                  <tr class="bg-rose-950/40">
                    <td colspan="11" class="px-3 py-1 text-rose-300 font-mono text-[11px] break-all">{s.error}</td>
                  </tr>
                {/if}
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

    <!-- Indicators table — per-indicator rollup across all observations parquets. -->
    <div>
      <h3 class="text-sm uppercase tracking-wide text-slate-400 font-semibold mb-2">
        Indicators
        <span class="text-slate-600 font-normal normal-case">
          · {data.indicators.length} indicator{data.indicators.length === 1 ? "" : "s"}
          across {new Set(data.indicators.map(i => i.family)).size} famil{new Set(data.indicators.map(i => i.family)).size === 1 ? "y" : "ies"}
        </span>
      </h3>
      {#if data.indicators.length === 0}
        <p class="text-sm text-slate-400">No <code class="font-mono">observations.parquet</code> found.</p>
      {:else}
        <div class="overflow-x-auto rounded border border-slate-800">
          <table class="w-full text-xs tabular-nums">
            <thead class="bg-slate-900 text-slate-400 text-left">
              <tr>
                <th class="px-3 py-2 font-normal">Family</th>
                <th class="px-3 py-2 font-normal">Indicator</th>
                <th class="px-3 py-2 font-normal text-right">Observations</th>
                <th class="px-3 py-2 font-normal text-right">Entities</th>
                <th class="px-3 py-2 font-normal text-right">Periods</th>
                <th class="px-3 py-2 font-normal text-right">Years</th>
              </tr>
            </thead>
            <tbody class="bg-slate-950">
              {#each data.indicators as i (i.family + "/" + i.indicator_id)}
                <tr class="border-t border-slate-900">
                  <td class="px-3 py-2 font-mono">{i.family}</td>
                  <td class="px-3 py-2 font-mono text-slate-300">{i.indicator_id}</td>
                  <td class="px-3 py-2 text-right">{fmtNum(i.obs_count)}</td>
                  <td class="px-3 py-2 text-right">{fmtNum(i.entity_count)}</td>
                  <td class="px-3 py-2 text-right">{fmtNum(i.period_count)}</td>
                  <td class="px-3 py-2 text-right text-slate-400">
                    {fmtYearRange(i.min_year, i.max_year)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

    <p class="text-[10px] text-slate-600 font-mono">
      generated_at: {data.generated_at}
    </p>
  {/if}
</section>
