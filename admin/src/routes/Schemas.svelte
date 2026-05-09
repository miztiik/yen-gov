<script lang="ts">
  // Schemas panel — surfaces the same Tier-A + Tier-B validator that
  // gates CI (yen_gov.validate.run). One row per schema, with a
  // status pill, the current x-version, the count of data files
  // claiming the schema, and an expandable failure list.
  //
  // Failures that can't be attributed to a schema (missing $schema,
  // unknown $schema URL, $schema_version mismatch) bubble up into the
  // orphan banner above the table.

  import { api, type SchemasReport, type SchemaInfo } from "../lib/api";

  let report = $state<SchemasReport | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(false);
  let expanded = $state<string | null>(null);

  async function load(): Promise<void> {
    loading = true;
    error = null;
    try {
      report = await api.schemas();
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }
  void load();

  function statusOf(s: SchemaInfo): "ok" | "warn" | "fail" {
    if (!s.meta_ok) return "fail";
    if (s.data_failing_files > 0) return "warn";
    return "ok";
  }

  function pillClass(state: "ok" | "warn" | "fail"): string {
    return {
      ok: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
      warn: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
      fail: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
    }[state];
  }

  function toggle(id: string): void {
    expanded = expanded === id ? null : id;
  }
</script>

<section class="space-y-4 text-slate-200">
  <header class="flex items-center justify-between">
    <div>
      <h1 class="text-lg font-semibold">Schemas</h1>
      <p class="text-xs text-slate-500">
        Tier A: meta-schema + version invariants · Tier B: every
        <code class="text-slate-400">datasets/**.json</code> validates
        against its declared <code class="text-slate-400">$schema</code>.
      </p>
    </div>
    <button
      onclick={load}
      disabled={loading}
      class="text-xs px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-50"
    >{loading ? "Reloading…" : "Reload"}</button>
  </header>

  {#if error}
    <div class="p-3 rounded bg-rose-950/40 ring-1 ring-rose-500/30 text-rose-300 text-sm">
      Failed to load: <code class="font-mono">{error}</code>
    </div>
  {:else if !report}
    <div class="text-slate-500 text-sm">Loading…</div>
  {:else}
    <!-- Top-level summary strip -->
    <div class="grid grid-cols-4 gap-3 text-sm">
      <div class="p-3 rounded bg-slate-900 ring-1 ring-slate-800">
        <div class="text-[10px] uppercase tracking-wide text-slate-500">Schemas</div>
        <div class="text-xl font-semibold">{report.summary.total_schemas}</div>
      </div>
      <div class="p-3 rounded bg-slate-900 ring-1 ring-slate-800">
        <div class="text-[10px] uppercase tracking-wide text-slate-500">Meta failing</div>
        <div class="text-xl font-semibold {report.summary.meta_failing ? 'text-rose-300' : 'text-emerald-300'}">
          {report.summary.meta_failing}
        </div>
      </div>
      <div class="p-3 rounded bg-slate-900 ring-1 ring-slate-800">
        <div class="text-[10px] uppercase tracking-wide text-slate-500">Data files failing</div>
        <div class="text-xl font-semibold {report.summary.data_failing_files ? 'text-amber-300' : 'text-emerald-300'}">
          {report.summary.data_failing_files}
        </div>
      </div>
      <div class="p-3 rounded bg-slate-900 ring-1 ring-slate-800">
        <div class="text-[10px] uppercase tracking-wide text-slate-500">Orphan files</div>
        <div class="text-xl font-semibold {report.summary.orphan_files ? 'text-amber-300' : 'text-emerald-300'}">
          {report.summary.orphan_files}
        </div>
      </div>
    </div>

    {#if report.orphan_failures.length}
      <details class="rounded bg-amber-950/30 ring-1 ring-amber-500/30 p-3 text-xs">
        <summary class="cursor-pointer text-amber-300 font-medium">
          {report.orphan_failures.length} orphan failure{report.orphan_failures.length === 1 ? '' : 's'}
          (file's <code>$schema</code> is missing, unknown, or version-mismatched)
        </summary>
        <ul class="mt-2 space-y-1 font-mono text-[11px] text-amber-100/80">
          {#each report.orphan_failures as f}
            <li><span class="text-amber-400">{f.file}</span> — {f.message}</li>
          {/each}
        </ul>
      </details>
    {/if}

    <table class="w-full text-sm border-collapse">
      <thead class="text-[10px] uppercase tracking-wide text-slate-500">
        <tr class="border-b border-slate-800">
          <th class="text-left py-2 px-2">Schema</th>
          <th class="text-left py-2 px-2">Version</th>
          <th class="text-left py-2 px-2">Status</th>
          <th class="text-right py-2 px-2">Data files</th>
          <th class="text-right py-2 px-2">Failing</th>
          <th class="text-left py-2 px-2">Last change</th>
        </tr>
      </thead>
      <tbody>
        {#each report.schemas as s (s.id)}
          {@const status = statusOf(s)}
          {@const open = expanded === s.id}
          {@const has_details = s.meta_errors.length > 0 || s.data_failures.length > 0}
          <tr
            class="border-b border-slate-900 hover:bg-slate-900/50 {has_details ? 'cursor-pointer' : ''}"
            onclick={() => has_details && toggle(s.id)}
          >
            <td class="py-2 px-2 font-mono text-xs text-slate-300">
              {s.id.replace(/\.schema\.json$/, "")}
              {#if s.title}
                <div class="text-[10px] text-slate-500 normal-case font-sans">{s.title}</div>
              {/if}
            </td>
            <td class="py-2 px-2 font-mono text-xs">{s.x_version ?? "—"}</td>
            <td class="py-2 px-2">
              <span class="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded {pillClass(status)}">
                {status === 'ok' ? 'OK' : status === 'warn' ? 'data fails' : 'meta fails'}
              </span>
            </td>
            <td class="py-2 px-2 text-right font-mono text-xs">{s.data_files}</td>
            <td class="py-2 px-2 text-right font-mono text-xs {s.data_failing_files ? 'text-amber-300' : 'text-slate-500'}">
              {s.data_failing_files}
            </td>
            <td class="py-2 px-2 text-[11px] text-slate-400">
              {#if s.last_changelog}
                <span class="font-mono">{s.last_changelog.date}</span>
                <span class="text-slate-600"> · </span>
                <span title={s.last_changelog.description}>{s.last_changelog.description.length > 50 ? s.last_changelog.description.slice(0, 50) + '…' : s.last_changelog.description}</span>
              {:else}
                —
              {/if}
            </td>
          </tr>
          {#if open}
            <tr class="bg-slate-950/60">
              <td colspan="6" class="px-4 py-3 space-y-3">
                {#if s.meta_errors.length}
                  <div>
                    <div class="text-[10px] uppercase tracking-wide text-rose-400 mb-1">Tier A — meta failures</div>
                    <ul class="font-mono text-[11px] text-rose-100/80 space-y-1">
                      {#each s.meta_errors as f}
                        <li>{f.message}</li>
                      {/each}
                    </ul>
                  </div>
                {/if}
                {#if s.data_failures.length}
                  <div>
                    <div class="text-[10px] uppercase tracking-wide text-amber-400 mb-1">
                      Tier B — first {s.data_failures.length} of {s.data_failing_files} failing files
                    </div>
                    <ul class="font-mono text-[11px] text-amber-100/80 space-y-1">
                      {#each s.data_failures as f}
                        <li><span class="text-amber-400">{f.file}</span> — {f.message}</li>
                      {/each}
                    </ul>
                  </div>
                {/if}
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  {/if}
</section>
