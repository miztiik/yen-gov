<script lang="ts">
  // Inventory panel — coverage matrix of (event × state).
  //
  // Walking-skeleton UI: a single sortable-by-completeness table. No
  // filters, no drill-down. The point of the panel is to prove the
  // round-trip (Vite proxy → FastAPI → datasets/) and surface dataset
  // freshness + provenance at a glance.

  import { api, type Inventory, type InventoryCell } from "../lib/api";

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

  function pctComplete(c: InventoryCell): number | null {
    const e = c.ac_results.expected;
    if (e == null || e === 0) return null;
    // floor, not round — we never want to show 100% when one or more
    // ACs are missing (real example: WB had 293/294, was rendering 100%).
    return Math.min(100, Math.floor((c.ac_results.found / e) * 100));
  }

  function fmtTime(iso: string | undefined | null): string {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toISOString().replace("T", " ").slice(0, 16) + "Z";
  }
</script>

<section class="space-y-4">
  <header class="flex items-baseline justify-between">
    <div>
      <h2 class="text-lg font-semibold">Inventory</h2>
      <p class="text-xs text-slate-400">
        Coverage of <code class="font-mono">datasets/elections/&lt;event&gt;/&lt;state&gt;/</code> on disk. AC counts compared against <code class="font-mono">datasets/reference/in/states/&lt;state&gt;/constituencies.json</code>.
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
  {:else if data.cells.length === 0}
    <p class="text-sm text-slate-400">No election datasets found under <code>datasets/elections/</code>.</p>
  {:else}
    <div class="overflow-x-auto rounded border border-slate-800">
      <table class="w-full text-xs tabular-nums">
        <thead class="bg-slate-900 text-slate-400 text-left">
          <tr>
            <th class="px-3 py-2 font-normal">Event</th>
            <th class="px-3 py-2 font-normal">State</th>
            <th class="px-3 py-2 font-normal text-right">ACs found / expected</th>
            <th class="px-3 py-2 font-normal text-right">Complete</th>
            <th class="px-3 py-2 font-normal">Schema</th>
            <th class="px-3 py-2 font-normal">Sources</th>
            <th class="px-3 py-2 font-normal">Sqlite</th>
            <th class="px-3 py-2 font-normal">Last write</th>
          </tr>
        </thead>
        <tbody class="bg-slate-950">
          {#each data.cells as c (c.event + "/" + c.state)}
            {@const pct = pctComplete(c)}
            <tr class="border-t border-slate-900 align-top">
              <td class="px-3 py-2 font-mono">{c.event}</td>
              <td class="px-3 py-2">
                <div class="flex items-baseline gap-2">
                  <span class="font-mono text-slate-400">{c.state}</span>
                  <span>{data.states[c.state] ?? c.state}</span>
                </div>
              </td>
              <td class="px-3 py-2 text-right">
                {c.ac_results.found}{c.ac_results.expected != null ? ` / ${c.ac_results.expected}` : ""}
              </td>
              <td class="px-3 py-2 text-right">
                {#if pct == null}
                  <span class="text-slate-600" title="No reference constituencies file">—</span>
                {:else}
                  <span
                    class="px-1.5 py-0.5 rounded"
                    class:bg-emerald-950={pct === 100}
                    class:text-emerald-300={pct === 100}
                    class:bg-amber-950={pct < 100 && pct > 0}
                    class:text-amber-300={pct < 100 && pct > 0}
                    class:bg-rose-950={pct === 0}
                    class:text-rose-300={pct === 0}
                  >{pct}%</span>
                {/if}
              </td>
              <td class="px-3 py-2 font-mono text-slate-400">{c.summary?.schema_version ?? "—"}</td>
              <td class="px-3 py-2">
                {#if c.summary?.sources && c.summary.sources.length > 0}
                  <details>
                    <summary class="cursor-pointer text-slate-300">{c.summary.sources.length} URL(s)</summary>
                    <ul class="mt-1 space-y-0.5">
                      {#each c.summary.sources as s}
                        <li class="text-[10px] text-slate-400">
                          <a class="underline hover:text-slate-200 break-all" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
                          <span class="text-slate-600"> · {fmtTime(s.fetched_at)}</span>
                        </li>
                      {/each}
                    </ul>
                  </details>
                {:else if c.summary?.error}
                  <span class="text-rose-400" title={c.summary.error}>parse error</span>
                {:else}
                  <span class="text-slate-600">—</span>
                {/if}
              </td>
              <td class="px-3 py-2">
                {#if c.sqlite}
                  <span class="text-emerald-400">✓</span>
                {:else}
                  <span class="text-slate-600">—</span>
                {/if}
              </td>
              <td class="px-3 py-2 font-mono text-slate-500">{fmtTime(c.summary?.mtime)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
