<script lang="ts">
  // Route: `/data-completeness`
  //
  // Citizen-facing transparency surface (per
  // TODO/20260517-folded-indicator-and-collection-inventory-handover.md
  // §4 commit 10). Lists every published indicator with its editorial
  // documentation_status (stub | partial | authored) and collection
  // status (empty | partial | complete), so a reader can see at a
  // glance which indicators are still scaffold-quality vs. fully
  // editor-reviewed, and which series have known gaps.
  //
  // Data source: `/data/reference/in/indicators-completeness.json`,
  // emitted by `tools/emit_indicators_completeness_index.py` from
  // every artifact under `datasets/indicators/in/`. The page does NOT
  // fetch the 110 individual indicator JSONs; we read one pre-rolled
  // index so the page loads instantly.
  import { onMount } from "svelte";
  import { DATA_BASE } from "../lib/paths";

  interface IndicatorRow {
    id: string;
    topic: string;
    path: string;
    title: string;
    documentation_status: "stub" | "partial" | "authored";
    inventory_status: "empty" | "partial" | "complete";
    frozen: boolean;
    last_collected_at: string | null;
    observed_count: number;
    pending_count: number;
    unavailable_count: number;
  }

  interface CompletenessIndex {
    generated_at: string;
    indicators: IndicatorRow[];
  }

  type View =
    | { kind: "loading" }
    | { kind: "ready"; data: CompletenessIndex }
    | { kind: "error"; message: string };

  let view = $state<View>({ kind: "loading" });
  let topicFilter = $state<string>("all");
  let statusFilter = $state<"all" | "stub" | "partial" | "authored">("all");

  onMount(async () => {
    try {
      const res = await fetch(`${DATA_BASE}/reference/in/indicators-completeness.json`);
      if (!res.ok) throw new Error(`fetch failed: ${res.status} ${res.statusText}`);
      const data = (await res.json()) as CompletenessIndex;
      view = { kind: "ready", data };
    } catch (e) {
      view = { kind: "error", message: e instanceof Error ? e.message : String(e) };
    }
  });

  const topics = $derived(
    view.kind === "ready" ? Array.from(new Set(view.data.indicators.map((r: IndicatorRow) => r.topic))).sort() : []
  );

  const visible = $derived(
    view.kind === "ready"
      ? view.data.indicators.filter(
          (r: IndicatorRow) =>
            (topicFilter === "all" || r.topic === topicFilter) &&
            (statusFilter === "all" || r.documentation_status === statusFilter)
        )
      : []
  );

  function statusBadgeClass(status: string): string {
    switch (status) {
      case "stub":
        return "bg-amber-100 text-amber-900 border-amber-300";
      case "partial":
        return "bg-sky-100 text-sky-900 border-sky-300";
      case "authored":
        return "bg-emerald-100 text-emerald-900 border-emerald-300";
      case "complete":
        return "bg-emerald-100 text-emerald-900 border-emerald-300";
      case "empty":
        return "bg-rose-100 text-rose-900 border-rose-300";
      default:
        return "bg-slate-100 text-slate-700 border-slate-300";
    }
  }
</script>

<div class="max-w-5xl mx-auto px-4 py-6">
  <h1 class="text-2xl font-semibold text-slate-900">Data completeness</h1>
  <p class="mt-2 text-sm text-slate-600 max-w-3xl">
    Every indicator yen-gov publishes, with its editorial documentation status and
    collection status. <strong>Stub</strong> indicators are auto-derived from observed rows
    and still need an editor pass; <strong>authored</strong> indicators carry hand-curated
    methodology with publisher citation. <strong>Partial</strong> collection means some
    expected (state, period) cells are missing values; <strong>complete</strong> means every
    expected cell has been collected.
  </p>

  {#if view.kind === "loading"}
    <p class="mt-6 text-slate-500" data-testid="loading">Loading index…</p>
  {:else if view.kind === "error"}
    <p class="mt-6 text-rose-700" data-testid="error">Failed to load index: {view.message}</p>
  {:else}
    <p class="mt-2 text-xs text-slate-500">
      Generated {view.data.generated_at} · {view.data.indicators.length} indicators
    </p>

    <div class="mt-4 flex flex-wrap gap-3 items-center text-sm">
      <label class="flex items-center gap-2">
        <span class="text-slate-700">Topic:</span>
        <select bind:value={topicFilter} class="border border-slate-300 rounded px-2 py-1" data-testid="topic-filter">
          <option value="all">All ({view.data.indicators.length})</option>
          {#each topics as t (t)}
            <option value={t}>{t} ({view.data.indicators.filter((r: IndicatorRow) => r.topic === t).length})</option>
          {/each}
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-slate-700">Documentation:</span>
        <select bind:value={statusFilter} class="border border-slate-300 rounded px-2 py-1" data-testid="status-filter">
          <option value="all">All</option>
          <option value="stub">Stub ({view.data.indicators.filter((r: IndicatorRow) => r.documentation_status === "stub").length})</option>
          <option value="partial">Partial ({view.data.indicators.filter((r: IndicatorRow) => r.documentation_status === "partial").length})</option>
          <option value="authored">Authored ({view.data.indicators.filter((r: IndicatorRow) => r.documentation_status === "authored").length})</option>
        </select>
      </label>
    </div>

    <div class="mt-4 overflow-x-auto" data-testid="indicators-table">
      <table class="min-w-full text-sm">
        <thead>
          <tr class="text-left border-b border-slate-300 text-slate-700">
            <th class="py-2 pr-4 font-medium">Indicator</th>
            <th class="py-2 pr-4 font-medium">Topic</th>
            <th class="py-2 pr-4 font-medium">Documentation</th>
            <th class="py-2 pr-4 font-medium">Collection</th>
            <th class="py-2 pr-4 font-medium text-right">Observed</th>
            <th class="py-2 pr-4 font-medium text-right">Pending</th>
            <th class="py-2 pr-4 font-medium">Last collected</th>
          </tr>
        </thead>
        <tbody>
          {#each visible as row (row.id)}
            <tr class="border-b border-slate-100">
              <td class="py-2 pr-4">
                <div class="font-medium text-slate-900">{row.title}</div>
                <code class="text-xs text-slate-500">{row.id}</code>
              </td>
              <td class="py-2 pr-4 text-slate-700">{row.topic}</td>
              <td class="py-2 pr-4">
                <span class="inline-block text-xs px-2 py-0.5 rounded border {statusBadgeClass(row.documentation_status)}">
                  {row.documentation_status}
                </span>
              </td>
              <td class="py-2 pr-4">
                <span class="inline-block text-xs px-2 py-0.5 rounded border {statusBadgeClass(row.inventory_status)}">
                  {row.inventory_status}
                </span>
                {#if row.frozen}
                  <span class="ml-1 inline-block text-xs px-2 py-0.5 rounded border bg-slate-100 text-slate-700 border-slate-300">frozen</span>
                {/if}
              </td>
              <td class="py-2 pr-4 text-right tabular-nums text-slate-700">{row.observed_count}</td>
              <td class="py-2 pr-4 text-right tabular-nums text-slate-700">{row.pending_count}</td>
              <td class="py-2 pr-4 text-slate-700">{row.last_collected_at ?? "—"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
