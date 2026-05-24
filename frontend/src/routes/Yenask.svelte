<script lang="ts">
  // YENASK browser governance insight assistant — dev-only route.
  //
  // Lives at /dev/yenask. See plan-doc
  // TODO/20260518-browser-governance-insight-assistant-plan.md §17
  // for the design decision log (D-01..D-18).
  //
  // PR-2: multi-turn CHAT surface backed by the same pipeline as PR-1.
  //   user types question
  //     → extractIntent(question, catalogue, adapter)   (model)
  //     → compileIntent(intent, catalogue)              (pure)
  //     → executePlan(plan)                             (DuckDB-WASM)
  //     → append assistant turn to conversation log
  //
  // Canned questions are "starter prompts" — clicking one shortcuts past
  // the model (intent is already known + validated) but still appends to
  // the same conversation log. This keeps the e2e canned-button path
  // model-free, and proves the chat surface renders the same answer
  // shape regardless of how the intent was produced.
  //
  // Per D-18: each user turn is extracted INDEPENDENTLY of prior turns
  // in v0. Multi-turn awareness ("what about Kerala?") is a PR-3
  // quality dimension; today's contract is "self-contained questions
  // per turn".

  import { onMount, tick } from "svelte";
  import { CANNED_INTENTS } from "../lib/yenask/fixtures/canned-intents";
  import type { InsightIntent } from "../lib/yenask/contracts/insight-intent";
  import type { AnswerViewModel } from "../lib/yenask/contracts/answer-viewmodel";
  import type { SemanticCatalogue } from "../lib/yenask/types";
  import { loadSemanticCatalogue } from "../lib/yenask/semantic-catalogue";
  import { compileIntent } from "../lib/yenask/compile-intent";
  import { executePlan } from "../lib/yenask/execute-plan";
  import SourceListV2 from "../lib/SourceListV2.svelte";
  import type { SourceV2Row } from "../lib/source-list-v2";
  import {
    MODEL_REGISTRY,
    DEFAULT_MODEL_ID,
    getModelById,
    getDefaultModel,
  } from "../lib/yenask/model-registry";
  import type { ModelAdapter, ReadinessStatus } from "../lib/yenask/model-adapter";
  import { createAdapter } from "../lib/yenask/model-adapter";
  import { extractIntent } from "../lib/yenask/extract-intent";
  import type { ExtractAttempt } from "../lib/yenask/extract-intent";

  // -------- chat turn discriminated union -----------------------------------

  /**
   * Per-turn debug payload. Per D-21 the SQL + raw model output stay
   * OUT of the citizen-facing turn body and move into the bottom
   * "Debug log" section. The turn keeps a compact summary footer
   * (attempts + tokens + wall_ms); the full breakdown is rendered
   * once per turn inside the debug panel.
   */
  interface ExtractDebug {
    readonly attempts: number;
    readonly raw: string;
    readonly attempts_log: readonly ExtractAttempt[];
  }

  /** One entry in the assistant readiness timeline (D-20). */
  interface StatusEvent {
    readonly ts: number;
    readonly status: ReadinessStatus;
  }

  type ChatTurn =
    | { readonly id: number; readonly kind: "user"; readonly text: string }
    | { readonly id: number; readonly kind: "assistant-loading" }
    | {
        readonly id: number;
        readonly kind: "assistant-answer";
        readonly intent: InsightIntent;
        readonly answer: AnswerViewModel;
        readonly debug?: ExtractDebug;
        readonly skipped_extract: boolean;
      }
    | {
        readonly id: number;
        readonly kind: "assistant-failure";
        readonly reason: string;
        readonly debug?: ExtractDebug;
      };

  // -------- localStorage --------------------------------------------------------

  // Versioned so a future schema change can invalidate cleanly without
  // colliding with a stale value. See plan-doc §17 D-15.
  const LS_MODEL_KEY = "yenask.model.id.v1";

  // -------- state ---------------------------------------------------------------

  let catalogue: SemanticCatalogue | null = $state(null);
  let catalogueError: string | null = $state(null);
  let catalogueLoading = $state(true);

  let conversation: ChatTurn[] = $state([]);
  let composer = $state("");
  let chatScroll: HTMLDivElement | undefined = $state();

  let selectedModelId = $state<string>(initialModelId());
  let adapter: ModelAdapter | null = $state(null);
  let modelStatus = $state<ReadinessStatus>({ kind: "idle" });
  // Running tail of every readiness transition since page load. Capped
  // at 50 to keep the DOM small; the most recent kind is also in
  // `modelStatus` so the timeline is supplementary, not primary.
  let statusHistory: StatusEvent[] = $state([]);

  const selectedModel = $derived(
    getModelById(selectedModelId) ?? getDefaultModel(),
  );

  const modelReady = $derived(modelStatus.kind === "ready");
  const modelBusy = $derived(
    modelStatus.kind === "downloading" || modelStatus.kind === "compiling",
  );
  const isThinking = $derived(
    conversation.at(-1)?.kind === "assistant-loading",
  );
  const canSendCanned = $derived(!!catalogue && !isThinking);
  const canSendComposer = $derived(
    !!catalogue && modelReady && !isThinking && composer.trim().length > 0,
  );

  let nextTurnId = 0;
  function newId(): number {
    nextTurnId += 1;
    return nextTurnId;
  }

  function initialModelId(): string {
    if (typeof localStorage === "undefined") return DEFAULT_MODEL_ID;
    try {
      const stored = localStorage.getItem(LS_MODEL_KEY);
      if (stored && getModelById(stored)) return stored;
    } catch {
      // localStorage may throw in private-browsing modes; fall through.
    }
    return DEFAULT_MODEL_ID;
  }

  $effect(() => {
    if (typeof localStorage === "undefined") return;
    try {
      localStorage.setItem(LS_MODEL_KEY, selectedModelId);
    } catch {
      // ignore quota / private-mode errors
    }
  });

  // -------- lifecycle -----------------------------------------------------------

  onMount(() => {
    void (async () => {
      try {
        catalogue = await loadSemanticCatalogue();
        catalogueLoading = false;
      } catch (err) {
        catalogueError = errorMessage(err, "Failed to load semantic catalogue.");
        catalogueLoading = false;
      }
    })();
  });

  // -------- helpers -------------------------------------------------------------

  function errorMessage(err: unknown, fallback: string): string {
    if (err instanceof Error) return err.message;
    if (typeof err === "string") return err;
    return fallback;
  }

  function formatCell(value: unknown, format: string): string {
    if (value == null) return "—";
    if (format === "integer") return Number(value).toLocaleString("en-IN");
    if (format === "thousands") return Number(value).toLocaleString("en-IN");
    if (format === "percentage") {
      const n = Number(value);
      return Number.isFinite(n) ? `${n.toFixed(2)}%` : "—";
    }
    return String(value);
  }

  function formatBytes(b: number): string {
    if (!Number.isFinite(b) || b <= 0) return "";
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / 1024 / 1024).toFixed(1)} MB`;
  }

  /** "~32" when approximate, "32" when exact. Keeps the UI honest. */
  function fmtTokens(n: number, approximate: boolean): string {
    if (!Number.isFinite(n) || n < 0) return "–";
    return `${approximate ? "~" : ""}${n.toLocaleString("en-IN")}`;
  }

  function fmtMs(ms: number): string {
    if (!Number.isFinite(ms) || ms < 0) return "–";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function fmtClock(ts: number): string {
    const d = new Date(ts);
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  }

  /** Aggregate per-turn totals from attempts_log for the footer. */
  function turnTotals(
    log: readonly ExtractAttempt[],
  ): {
    attempts: number;
    tokens_in: number;
    tokens_out: number;
    wall_ms: number;
    approximate: boolean;
  } {
    let tokens_in = 0;
    let tokens_out = 0;
    let wall_ms = 0;
    let approximate = false;
    for (const a of log) {
      tokens_in += a.tokens_in;
      tokens_out += a.tokens_out;
      wall_ms += a.wall_ms;
      if (a.tokens_approximate) approximate = true;
    }
    return { attempts: log.length, tokens_in, tokens_out, wall_ms, approximate };
  }

  async function scrollToBottom(): Promise<void> {
    await tick();
    if (chatScroll) {
      chatScroll.scrollTop = chatScroll.scrollHeight;
    }
  }

  function appendTurn(t: ChatTurn): void {
    conversation = [...conversation, t];
    void scrollToBottom();
  }

  function replaceLastTurn(t: ChatTurn): void {
    conversation = [...conversation.slice(0, -1), t];
    void scrollToBottom();
  }

  // -------- send pipeline -------------------------------------------------------

  async function sendUserTurn(
    text: string,
    cannedIntent?: InsightIntent,
  ): Promise<void> {
    if (!catalogue) return;
    appendTurn({ id: newId(), kind: "user", text });
    appendTurn({ id: newId(), kind: "assistant-loading" });

    let intent: InsightIntent;
    let debug: ExtractDebug | undefined;
    const skipped_extract = !!cannedIntent;

    if (cannedIntent) {
      intent = cannedIntent;
    } else {
      if (!adapter || modelStatus.kind !== "ready") {
        replaceLastTurn({
          id: newId(),
          kind: "assistant-failure",
          reason: "Prepare the assistant first.",
        });
        return;
      }
      const result = await extractIntent(text, catalogue, adapter);
      debug = {
        attempts: result.diagnostics.attempts,
        raw: result.diagnostics.last_raw_output,
        attempts_log: result.diagnostics.attempts_log,
      };
      if (!result.ok) {
        replaceLastTurn({
          id: newId(),
          kind: "assistant-failure",
          reason: `Could not extract a valid intent: ${result.error}`,
          debug,
        });
        return;
      }
      intent = result.intent;
    }

    try {
      const plan = compileIntent(intent, catalogue);
      const answer = await executePlan(plan);
      replaceLastTurn({
        id: newId(),
        kind: "assistant-answer",
        intent,
        answer,
        debug,
        skipped_extract,
      });
    } catch (err) {
      replaceLastTurn({
        id: newId(),
        kind: "assistant-failure",
        reason: errorMessage(err, "Compile or execute failed."),
        debug,
      });
    }
  }

  function clickCanned(intent: InsightIntent, label: string): void {
    void sendUserTurn(label, intent);
  }

  function submitComposer(): void {
    if (!canSendComposer) return;
    const text = composer.trim();
    composer = "";
    void sendUserTurn(text);
  }

  function onComposerKeydown(e: KeyboardEvent): void {
    // Enter to send, Shift+Enter for newline. Mirrors the conventional
    // chat-textarea contract; doesn't fight the citizen's habit.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitComposer();
    }
  }

  function clearConversation(): void {
    conversation = [];
  }

  // -------- model preparation ---------------------------------------------------

  async function prepareModel(): Promise<void> {
    pushStatus({
      kind: "downloading",
      file: "",
      percent: 0,
      loaded: 0,
      total: 0,
    });
    try {
      const a = createAdapter(selectedModel);
      adapter = a;
      await a.prepare((s) => {
        pushStatus(s);
      });
    } catch {
      // The listener already wrote a `failed` status; nothing more to do.
    }
  }

  /**
   * Update `modelStatus` AND append to `statusHistory` for the debug
   * timeline. Coalesces consecutive `downloading` percent updates for
   * the same `file` so the timeline doesn't get spammed by hundreds of
   * progress ticks — only the LAST progress event per file is kept.
   */
  function pushStatus(s: ReadinessStatus): void {
    modelStatus = s;
    const last = statusHistory.at(-1);
    const isProgress = s.kind === "downloading";
    const lastIsSameProgress =
      last?.status.kind === "downloading" &&
      s.kind === "downloading" &&
      last.status.file === s.file;
    if (isProgress && lastIsSameProgress) {
      statusHistory = [
        ...statusHistory.slice(0, -1),
        { ts: Date.now(), status: s },
      ];
    } else {
      statusHistory = [...statusHistory, { ts: Date.now(), status: s }];
    }
    if (statusHistory.length > 50) {
      statusHistory = statusHistory.slice(-50);
    }
  }
</script>

<svelte:head>
  <title>YENASK — dev preview</title>
</svelte:head>

<section class="mx-auto flex max-w-5xl flex-col gap-4 p-6" data-route="yenask">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold tracking-tight">YENASK</h1>
    <p class="text-sm text-neutral-600">
      Browser governance insight assistant. Dev-only route — not a citizen
      surface. See
      <a
        href="https://github.com/miztiik/yen-gov/blob/main/TODO/20260518-browser-governance-insight-assistant-plan.md"
        class="underline decoration-dotted">plan doc §17</a
      >
      for the design log.
    </p>
    <p class="rounded bg-amber-50 px-3 py-2 text-xs text-amber-900">
      <strong>PR-2.</strong> Multi-turn chat. Canned starter prompts work
      without a model. Free-text needs the small in-browser assistant
      (one-time download, cached in IndexedDB). Model entry is
      config-driven — swap it via
      <code>frontend/src/lib/yenask/model-registry.ts</code>.
    </p>
  </header>

  {#if catalogueLoading}
    <p class="text-sm text-neutral-600" data-status="loading-catalogue">
      Loading semantic catalogue…
    </p>
  {/if}

  {#if catalogueError}
    <p class="rounded bg-rose-50 px-3 py-2 text-sm text-rose-900" data-testid="yenask-catalogue-error">
      {catalogueError}
    </p>
  {/if}

  <!-- Model panel ----------------------------------------------------------- -->
  <section
    class="space-y-3 rounded-lg border border-neutral-200 p-4"
    data-testid="yenask-model-panel"
  >
    <div class="flex items-center justify-between gap-3">
      <h2 class="text-lg font-semibold">Assistant</h2>
      <span
        class="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700"
        data-testid="yenask-model-status"
        data-status-kind={modelStatus.kind}
      >{modelStatus.kind}</span>
    </div>

    <div class="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
      <label class="block text-sm">
        <span class="text-neutral-700">Model</span>
        <select
          class="mt-1 block w-full rounded border border-neutral-300 px-2 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          bind:value={selectedModelId}
          disabled={modelBusy}
          data-testid="yenask-model-picker"
        >
          {#each MODEL_REGISTRY as m (m.id)}
            <option value={m.id}>
              {m.display_name} · {m.params_label} · ~{m.estimated_download_mb} MB
            </option>
          {/each}
        </select>
        <span class="mt-1 block text-xs text-neutral-500">{selectedModel.notes}</span>
      </label>
      <button
        type="button"
        class="rounded bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-60"
        onclick={prepareModel}
        disabled={modelBusy || modelReady}
        data-testid="yenask-prepare-button"
      >
        {#if modelReady}
          Assistant ready
        {:else if modelBusy}
          Preparing…
        {:else}
          Prepare assistant
        {/if}
      </button>
    </div>

    {#if modelStatus.kind === "downloading"}
      <div class="space-y-1">
        <div class="h-2 w-full overflow-hidden rounded bg-neutral-200">
          <div
            class="h-full bg-neutral-700 transition-all"
            style="width: {Math.max(0, Math.min(100, modelStatus.percent)).toFixed(1)}%"
            data-testid="yenask-progress-bar"
          ></div>
        </div>
        <p class="text-xs text-neutral-600" data-testid="yenask-progress-label">
          Downloading
          {#if modelStatus.file}<code class="rounded bg-neutral-100 px-1">{modelStatus.file}</code>{/if}
          {modelStatus.percent.toFixed(1)}%
          {#if modelStatus.total > 0}
            ({formatBytes(modelStatus.loaded)} / {formatBytes(modelStatus.total)})
          {/if}
        </p>
      </div>
    {:else if modelStatus.kind === "compiling"}
      <p class="text-xs text-neutral-600">Compiling model into the runtime…</p>
    {:else if modelStatus.kind === "failed"}
      <p
        class="rounded bg-rose-50 px-3 py-2 text-xs text-rose-900"
        data-testid="yenask-model-error"
      >
        <strong>Model failed to load.</strong> {modelStatus.error}
      </p>
    {:else if modelStatus.kind === "ready"}
      <p class="text-xs text-emerald-700">
        Loaded in your browser. Cached — next visit is instant.
      </p>
    {/if}
  </section>

  <!-- Chat log -------------------------------------------------------------- -->
  <section
    class="flex min-h-[300px] flex-col rounded-lg border border-neutral-200"
    data-testid="yenask-chat"
  >
    <div
      class="flex-1 overflow-y-auto p-4"
      bind:this={chatScroll}
      data-testid="yenask-chat-log"
    >
      {#if conversation.length === 0}
        <div class="text-center text-sm text-neutral-500" data-testid="yenask-empty-state">
          <p class="mb-3">No questions yet.</p>
          <p class="text-xs">
            Try a starter prompt below, or prepare the assistant and type a question.
          </p>
        </div>
      {:else}
        <ul class="space-y-4">
          {#each conversation as turn (turn.id)}
            <li>
              {#if turn.kind === "user"}
                <div class="flex justify-end" data-turn-kind="user">
                  <div class="max-w-[85%] rounded-2xl rounded-br-sm bg-neutral-900 px-3 py-2 text-sm text-white">
                    {turn.text}
                  </div>
                </div>
              {:else if turn.kind === "assistant-loading"}
                <div class="flex" data-turn-kind="assistant-loading">
                  <div class="max-w-[85%] rounded-2xl rounded-bl-sm bg-neutral-100 px-3 py-2 text-sm text-neutral-700">
                    <span class="inline-flex items-center gap-2">
                      <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-neutral-500"></span>
                      Thinking…
                    </span>
                  </div>
                </div>
              {:else if turn.kind === "assistant-failure"}
                <div class="flex" data-turn-kind="assistant-failure">
                  <div class="max-w-[85%] space-y-2 rounded-2xl rounded-bl-sm border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900" data-testid="yenask-failure">
                    <strong>Could not answer.</strong>
                    <p class="text-xs">{turn.reason}</p>
                    {#if turn.debug}
                      <details class="text-xs" data-testid="yenask-extract-debug">
                        <summary class="cursor-pointer">Model output (attempts: {turn.debug.attempts})</summary>
                        <pre class="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-white p-2 font-mono text-[11px] leading-snug text-neutral-700">{turn.debug.raw}</pre>
                      </details>
                    {/if}
                  </div>
                </div>
              {:else}
                {@const a = turn.answer}
                <div class="space-y-2" data-turn-kind="assistant-answer" data-testid="yenask-answer">
                  <div class="flex">
                    <div class="w-full max-w-[95%] space-y-3 rounded-2xl rounded-bl-sm border border-neutral-200 bg-white px-3 py-3 text-sm">
                      <header class="space-y-1">
                        <h3 class="text-sm font-semibold">{a.question}</h3>
                        {#if a.provenance_status === "missing"}
                          <p
                            class="rounded bg-amber-100 px-2 py-1 text-xs text-amber-900"
                            data-testid="yenask-source-missing"
                          >
                            <strong>Source unattested.</strong> The compiler could not resolve a citation for this answer. Treat values as provisional.
                          </p>
                        {/if}
                      </header>

                      {#if a.rows.length === 0}
                        <p class="text-xs text-neutral-600" data-testid="yenask-empty-rows">
                          No matching rows. The data may not be published yet for this slice.
                        </p>
                      {:else}
                        <div class="overflow-x-auto rounded border border-neutral-200">
                          <table class="w-full text-xs" data-testid="yenask-answer-table">
                            <thead class="bg-neutral-50 text-left text-[11px] uppercase tracking-wide text-neutral-600">
                              <tr>
                                {#each a.column_order as col}
                                  <th class="px-3 py-1.5 font-medium">{a.column_labels[col] ?? col}</th>
                                {/each}
                              </tr>
                            </thead>
                            <tbody class="divide-y divide-neutral-100">
                              {#each a.rows as row, i (i)}
                                <tr>
                                  {#each a.column_order as col}
                                    <td class="px-3 py-1.5 align-top tabular-nums">
                                      {formatCell(row[col], a.column_formats[col] ?? "text")}
                                    </td>
                                  {/each}
                                </tr>
                              {/each}
                            </tbody>
                          </table>
                        </div>
                      {/if}

                      <div class="rounded border border-neutral-200 p-2" data-testid="yenask-source-strip">
                        <SourceListV2 sources={a.source_strip as readonly SourceV2Row[]} />
                      </div>

                      <!--
                        Per-turn footer. Per D-21 the SQL + raw model
                        output are NOT a citizen surface; they live in
                        the Debug log section below the chat. This
                        footer is the compact at-a-glance summary
                        (attempts + tokens + wall_ms).
                      -->
                      <p
                        class="text-[11px] text-neutral-500"
                        data-testid="yenask-turn-footer"
                      >
                        {#if turn.skipped_extract}
                          Canned starter prompt — no model used.
                        {:else if turn.debug && turn.debug.attempts_log.length > 0}
                          {@const t = turnTotals(turn.debug.attempts_log)}
                          Answered with {selectedModel.display_name}: {t.attempts}× attempt ·
                          {fmtTokens(t.tokens_in, t.approximate)} tokens in ·
                          {fmtTokens(t.tokens_out, t.approximate)} out ·
                          {fmtMs(t.wall_ms)} total. See <em>Debug log</em> below for details.
                        {:else if turn.debug}
                          Model output captured but no attempts recorded — see <em>Debug log</em> below.
                        {/if}
                      </p>
                    </div>
                  </div>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <!-- Starter prompts (only when chat is empty) -->
    {#if conversation.length === 0}
      <div class="border-t border-neutral-200 p-3" data-testid="yenask-starter-chips">
        <p class="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-500">Starter prompts</p>
        <ul class="grid gap-2 sm:grid-cols-2">
          {#each CANNED_INTENTS as canned (canned.id)}
            <li>
              <button
                type="button"
                class="block w-full rounded-lg border border-neutral-300 bg-white p-2.5 text-left transition hover:border-neutral-500 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
                data-canned-id={canned.id}
                disabled={!canSendCanned}
                onclick={() => clickCanned(canned.intent, canned.label)}
              >
                <span class="block text-sm font-medium">{canned.label}</span>
                <span class="mt-0.5 block text-xs text-neutral-600">{canned.description}</span>
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <!-- Composer -->
    <div class="flex items-end gap-2 border-t border-neutral-200 p-3" data-testid="yenask-composer">
      <textarea
        class="flex-1 resize-none rounded border border-neutral-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:bg-neutral-50 disabled:opacity-60"
        rows="2"
        placeholder={modelReady
          ? "Ask a question… (Enter to send, Shift+Enter for newline)"
          : "Prepare the assistant to enable free-text."}
        bind:value={composer}
        disabled={!modelReady || isThinking}
        onkeydown={onComposerKeydown}
        data-testid="yenask-question-input"
      ></textarea>
      <div class="flex flex-col gap-1">
        <button
          type="button"
          class="rounded bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-60"
          onclick={submitComposer}
          disabled={!canSendComposer}
          data-testid="yenask-ask-button"
        >Send</button>
        {#if conversation.length > 0}
          <button
            type="button"
            class="rounded border border-neutral-300 bg-white px-3 py-1 text-xs text-neutral-600 hover:bg-neutral-50"
            onclick={clearConversation}
            disabled={isThinking}
            data-testid="yenask-clear-button"
          >Clear</button>
        {/if}
      </div>
    </div>
  </section>

  <!--
    Debug log section. Per D-21 the SQL + raw model output stay OUT of
    the citizen-facing turn body and live here. Per D-20 every model
    call's attempts_log (tokens in/out + wall_ms + parse status) is
    rendered as well so the reader who hit the WebGPU bug can watch
    what the assistant is actually doing. Always-visible while we
    stabilise the lab — collapse later if it becomes noise.
  -->
  <section
    class="space-y-4 rounded-lg border border-dashed border-neutral-300 bg-neutral-50/60 p-4"
    data-testid="yenask-debug-panel"
  >
    <header class="space-y-1">
      <h2 class="text-sm font-semibold text-neutral-700">Debug log</h2>
      <p class="text-xs text-neutral-500">
        Dev observability — assistant lifecycle events + per-turn SQL +
        per-attempt model trace. Not a citizen surface (see plan-doc §17 D-21).
      </p>
    </header>

    <details open data-testid="yenask-debug-status-timeline">
      <summary class="cursor-pointer text-xs font-medium text-neutral-700">
        Assistant status timeline ({statusHistory.length})
      </summary>
      {#if statusHistory.length === 0}
        <p class="mt-2 text-xs text-neutral-500">
          No status changes yet. Click <em>Prepare assistant</em> above to start.
        </p>
      {:else}
        <ul class="mt-2 space-y-1 font-mono text-[11px] leading-snug text-neutral-700">
          {#each statusHistory as ev, i (i)}
            <li>
              <span class="text-neutral-500">[{fmtClock(ev.ts)}]</span>
              <span class="font-semibold">{ev.status.kind}</span>
              {#if ev.status.kind === "downloading"}
                <span class="text-neutral-600">
                  {ev.status.file || "(boot)"} — {ev.status.percent.toFixed(1)}%
                  {#if ev.status.total > 0}
                    ({formatBytes(ev.status.loaded)} / {formatBytes(ev.status.total)})
                  {/if}
                </span>
              {:else if ev.status.kind === "failed"}
                <span class="text-rose-700">— {ev.status.error}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </details>

    {#if conversation.some((t) => t.kind === "assistant-answer" || t.kind === "assistant-failure")}
      <div class="space-y-3" data-testid="yenask-debug-turns">
        <h3 class="text-xs font-semibold uppercase tracking-wide text-neutral-600">
          Per-turn details
        </h3>
        {#each conversation as turn (turn.id)}
          {#if turn.kind === "assistant-answer"}
            {@const a = turn.answer}
            <details
              open
              class="rounded border border-neutral-200 bg-white p-2 text-xs"
              data-testid="yenask-computation"
            >
              <summary class="cursor-pointer font-medium text-neutral-700">
                Turn {turn.id} — {a.question}
                {#if turn.skipped_extract}
                  <span class="ml-1 rounded bg-neutral-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-neutral-600">canned</span>
                {:else}
                  <span class="ml-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-emerald-700">model</span>
                {/if}
              </summary>
              <div class="mt-2 space-y-2">
                <div>
                  <span class="text-neutral-600">Concept:</span>
                  <code class="ml-1 rounded bg-neutral-100 px-1.5 py-0.5">{a.computation.concept_id}</code>
                </div>
                <div>
                  <span class="text-neutral-600">Slices registered:</span>
                  <ul class="mt-1 list-disc pl-5">
                    {#each a.computation.slice_registrations as s}
                      <li>
                        <code>{s.table_id}</code>
                        <span class="text-neutral-500">
                          where {Object.entries(s.partition_filter)
                            .map(([k, v]) => `${k}="${v}"`)
                            .join(", ")}
                        </span>
                      </li>
                    {/each}
                  </ul>
                </div>
                <div>
                  <span class="text-neutral-600">Main SQL:</span>
                  <pre class="mt-1 overflow-x-auto rounded bg-neutral-900 p-2 font-mono text-[10px] leading-snug text-neutral-100">{a.computation.main_sql}</pre>
                </div>
                <div>
                  <span class="text-neutral-600">Provenance SQL:</span>
                  <pre class="mt-1 overflow-x-auto rounded bg-neutral-900 p-2 font-mono text-[10px] leading-snug text-neutral-100">{a.computation.provenance_sql}</pre>
                </div>
                {#if turn.debug && turn.debug.attempts_log.length > 0}
                  <div>
                    <span class="text-neutral-600">
                      Extract attempts ({turn.debug.attempts_log.length}):
                    </span>
                    <table class="mt-1 w-full text-[11px]" data-testid="yenask-debug-attempts">
                      <thead class="bg-neutral-50 text-left text-[10px] uppercase tracking-wide text-neutral-600">
                        <tr>
                          <th class="px-2 py-1 font-medium">#</th>
                          <th class="px-2 py-1 font-medium">prompt chars</th>
                          <th class="px-2 py-1 font-medium">tokens in</th>
                          <th class="px-2 py-1 font-medium">tokens out</th>
                          <th class="px-2 py-1 font-medium">wall</th>
                          <th class="px-2 py-1 font-medium">status</th>
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-neutral-100">
                        {#each turn.debug.attempts_log as att (att.attempt)}
                          <tr>
                            <td class="px-2 py-1 tabular-nums">{att.attempt}</td>
                            <td class="px-2 py-1 tabular-nums">{att.prompt_chars.toLocaleString("en-IN")}</td>
                            <td class="px-2 py-1 tabular-nums">{fmtTokens(att.tokens_in, att.tokens_approximate)}</td>
                            <td class="px-2 py-1 tabular-nums">{fmtTokens(att.tokens_out, att.tokens_approximate)}</td>
                            <td class="px-2 py-1 tabular-nums">{fmtMs(att.wall_ms)}</td>
                            <td class="px-2 py-1">
                              <span
                                class="rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide {att.parse_status === 'ok' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}"
                              >
                                {att.parse_status}
                              </span>
                              {#if att.parse_error}
                                <span class="ml-1 text-rose-700">{att.parse_error}</span>
                              {/if}
                            </td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                    <details class="mt-2">
                      <summary class="cursor-pointer text-[11px] text-neutral-600">
                        Raw model output (last attempt)
                      </summary>
                      <pre class="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded bg-neutral-50 p-2 font-mono text-[10px] leading-snug text-neutral-700">{turn.debug.raw}</pre>
                    </details>
                  </div>
                {/if}
              </div>
            </details>
          {:else if turn.kind === "assistant-failure"}
            <details
              class="rounded border border-rose-200 bg-rose-50 p-2 text-xs"
              data-testid="yenask-debug-failure"
            >
              <summary class="cursor-pointer font-medium text-rose-900">
                Turn {turn.id} — failure
              </summary>
              <div class="mt-2 space-y-2">
                <p class="text-rose-900">{turn.reason}</p>
                {#if turn.debug && turn.debug.attempts_log.length > 0}
                  <table class="w-full text-[11px]" data-testid="yenask-debug-failure-attempts">
                    <thead class="bg-white/60 text-left text-[10px] uppercase tracking-wide text-neutral-600">
                      <tr>
                        <th class="px-2 py-1 font-medium">#</th>
                        <th class="px-2 py-1 font-medium">tokens in</th>
                        <th class="px-2 py-1 font-medium">tokens out</th>
                        <th class="px-2 py-1 font-medium">wall</th>
                        <th class="px-2 py-1 font-medium">status</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-rose-100">
                      {#each turn.debug.attempts_log as att (att.attempt)}
                        <tr>
                          <td class="px-2 py-1 tabular-nums">{att.attempt}</td>
                          <td class="px-2 py-1 tabular-nums">{fmtTokens(att.tokens_in, att.tokens_approximate)}</td>
                          <td class="px-2 py-1 tabular-nums">{fmtTokens(att.tokens_out, att.tokens_approximate)}</td>
                          <td class="px-2 py-1 tabular-nums">{fmtMs(att.wall_ms)}</td>
                          <td class="px-2 py-1">
                            <span class="rounded bg-rose-200 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-rose-900">
                              {att.parse_status}
                            </span>
                            {#if att.parse_error}
                              <span class="ml-1 text-rose-800">{att.parse_error}</span>
                            {/if}
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                  {#if turn.debug.raw}
                    <details>
                      <summary class="cursor-pointer text-[11px] text-rose-900">
                        Raw model output (last attempt)
                      </summary>
                      <pre class="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded bg-white p-2 font-mono text-[10px] leading-snug text-neutral-800">{turn.debug.raw}</pre>
                    </details>
                  {/if}
                {/if}
              </div>
            </details>
          {/if}
        {/each}
      </div>
    {/if}
  </section>
</section>
