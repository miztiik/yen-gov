<script lang="ts">
  // Pipeline panel — list runs under .runtime/logs/, view tail of a
  // selected run, and trigger a new one.
  //
  // Triggers require an explicit confirmation checkbox per run; the
  // backend additionally enforces confirm: true. The panel polls the
  // currently-viewed run every 2s while it is in 'running' state so
  // the operator sees a live tail without manual refresh.

  import { api, type PipelineRunsResponse, type PipelineRunDetail, type TriggerRequest } from "../lib/api";

  let runs_resp = $state<PipelineRunsResponse | null>(null);
  let runs_error = $state<string | null>(null);
  let selected_id = $state<string | null>(null);
  let detail = $state<PipelineRunDetail | null>(null);
  let detail_error = $state<string | null>(null);

  // Trigger form
  let cmd = $state<TriggerRequest["command"]>("validate");
  let args_text = $state("");
  let confirm = $state(false);
  let triggering = $state(false);
  let trigger_error = $state<string | null>(null);

  async function loadRuns(): Promise<void> {
    try {
      runs_resp = await api.pipelineRuns();
      // Auto-select the newest run on first load.
      if (!selected_id && runs_resp.runs.length) {
        selected_id = runs_resp.runs[0].run_id;
      }
    } catch (e) {
      runs_error = String(e);
    }
  }

  async function loadDetail(id: string): Promise<void> {
    try {
      detail = await api.pipelineRun(id);
      detail_error = null;
    } catch (e) {
      detail_error = String(e);
    }
  }

  // Initial load + polling. While the active detail is 'running', tail
  // every 2s; otherwise just keep the run list fresh every 5s.
  $effect(() => {
    void loadRuns();
    const list_id = setInterval(loadRuns, 5000);
    return () => clearInterval(list_id);
  });

  $effect(() => {
    if (!selected_id) return;
    const id = selected_id;
    void loadDetail(id);
    // Snappy poll while running, slow once finished.
    const handle = setInterval(() => {
      if (detail?.status === "running") {
        void loadDetail(id);
      }
    }, 2000);
    return () => clearInterval(handle);
  });

  async function trigger(): Promise<void> {
    trigger_error = null;
    triggering = true;
    try {
      const args = args_text.trim() ? args_text.trim().split(/\s+/) : [];
      const res = await api.triggerPipeline({ command: cmd, args, confirm: true });
      selected_id = res.run_id;
      confirm = false;
      await loadRuns();
    } catch (e) {
      trigger_error = String(e);
    } finally {
      triggering = false;
    }
  }

  function statusPill(status: string): string {
    const cls = {
      ok: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
      failed: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
      running: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30 animate-pulse",
      unknown: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
    } as Record<string, string>;
    return cls[status] ?? cls.unknown;
  }
</script>

<section class="space-y-4 text-slate-200">
  <header>
    <h1 class="text-lg font-semibold">Pipeline</h1>
    <p class="text-xs text-slate-500">
      Spawns <code class="text-slate-400">python -m yen_gov &lt;command&gt;</code>
      from the repo root. Logs land in
      <code class="text-slate-400">.runtime/logs/&lt;run-id&gt;/</code>.
    </p>
  </header>

  <!-- Trigger form -->
  <div class="p-3 rounded bg-slate-900 ring-1 ring-slate-800 space-y-2 text-sm">
    <div class="flex flex-wrap gap-2 items-end">
      <label class="flex flex-col text-xs text-slate-400">
        Command
        <select
          bind:value={cmd}
          class="mt-1 bg-slate-950 ring-1 ring-slate-800 rounded px-2 py-1 text-sm text-slate-200"
        >
          {#if runs_resp}
            {#each Object.entries(runs_resp.allowed_commands) as [k, desc]}
              <option value={k}>{k} — {desc}</option>
            {/each}
          {:else}
            <option value="validate">validate</option>
          {/if}
        </select>
      </label>
      <label class="flex flex-col text-xs text-slate-400 grow">
        Args (space-separated, e.g. <code>AcGenMay2026 S22</code>)
        <input
          type="text"
          bind:value={args_text}
          placeholder={cmd === 'run' ? 'AcGenMay2026 S22' : (cmd === 'reference' ? 'S22' : '')}
          class="mt-1 bg-slate-950 ring-1 ring-slate-800 rounded px-2 py-1 text-sm font-mono text-slate-200"
        />
      </label>
      <label class="flex items-center gap-2 text-xs text-amber-300">
        <input type="checkbox" bind:checked={confirm} class="accent-amber-500" />
        I understand: this will execute on my machine
      </label>
      <button
        onclick={trigger}
        disabled={!confirm || triggering}
        class="px-3 py-1 rounded bg-emerald-600 text-white text-sm hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
      >{triggering ? 'Starting…' : 'Trigger'}</button>
    </div>
    {#if trigger_error}
      <div class="text-xs text-rose-300 font-mono">{trigger_error}</div>
    {/if}
    {#if cmd === 'run' || cmd === 'reference'}
      <div class="text-[11px] text-amber-400/80">
        ⚠ {cmd} hits the network and writes into <code>datasets/</code>. May take several minutes.
      </div>
    {/if}
  </div>

  <div class="grid grid-cols-[260px_1fr] gap-4">
    <!-- Runs list -->
    <aside class="space-y-1 text-sm">
      <h2 class="text-[10px] uppercase tracking-wide text-slate-500 px-2">
        Runs {runs_resp ? `(${runs_resp.total})` : ''}
      </h2>
      {#if runs_error}
        <div class="text-xs text-rose-300 px-2">{runs_error}</div>
      {:else if !runs_resp}
        <div class="text-xs text-slate-500 px-2">Loading…</div>
      {:else if runs_resp.runs.length === 0}
        <div class="text-xs text-slate-500 px-2 italic">
          No runs yet. Trigger one above.
        </div>
      {:else}
        <ul class="space-y-0.5 max-h-[60vh] overflow-y-auto">
          {#each runs_resp.runs as r (r.run_id)}
            <li>
              <button
                class="w-full text-left px-2 py-1.5 rounded hover:bg-slate-800/60 {selected_id === r.run_id ? 'bg-slate-800' : ''}"
                onclick={() => (selected_id = r.run_id)}
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-mono text-[11px] truncate">{r.run_id}</span>
                  <span class="text-[10px] uppercase px-1.5 py-0.5 rounded {statusPill(r.status)}">
                    {r.status}
                  </span>
                </div>
                <div class="text-[10px] text-slate-500 mt-0.5 truncate">
                  {r.command ?? '—'}
                  {#if r.exit_code != null}· rc {r.exit_code}{/if}
                </div>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </aside>

    <!-- Detail viewer -->
    <article class="bg-slate-900 ring-1 ring-slate-800 rounded p-3 text-sm">
      {#if !selected_id}
        <p class="text-slate-500 text-sm">Pick a run to view its log.</p>
      {:else if detail_error}
        <p class="text-rose-300 font-mono text-xs">{detail_error}</p>
      {:else if !detail}
        <p class="text-slate-500">Loading…</p>
      {:else}
        <header class="flex items-center justify-between mb-2">
          <div class="space-y-0.5">
            <h2 class="font-mono text-sm">{detail.run_id}</h2>
            <p class="text-[11px] text-slate-500">
              {detail.meta.command ?? '—'}
              {#if detail.meta.args && (detail.meta.args as string[]).length}
                <code class="text-slate-400">{(detail.meta.args as string[]).join(' ')}</code>
              {/if}
              {#if detail.meta.exit_code != null}· exit {detail.meta.exit_code}{/if}
            </p>
          </div>
          <span class="text-[10px] uppercase px-2 py-0.5 rounded {statusPill(detail.status)}">
            {detail.status}
          </span>
        </header>

        {#if detail.console_tail.length}
          <pre class="text-[11px] font-mono bg-black/40 ring-1 ring-slate-800 rounded p-3 overflow-x-auto max-h-[55vh] overflow-y-auto whitespace-pre-wrap">{detail.console_tail.join('\n')}</pre>
        {:else}
          <p class="text-slate-500 text-xs italic">No console output yet.</p>
        {/if}

        {#if detail.structured_tail.length}
          <details class="mt-3">
            <summary class="text-[11px] text-slate-400 cursor-pointer">
              Structured events ({detail.structured_tail.length})
            </summary>
            <pre class="text-[10px] font-mono mt-2 bg-black/40 ring-1 ring-slate-800 rounded p-3 overflow-x-auto max-h-[30vh] overflow-y-auto whitespace-pre-wrap">{detail.structured_tail.map(e => JSON.stringify(e)).join('\n')}</pre>
          </details>
        {/if}
      {/if}
    </article>
  </div>
</section>
