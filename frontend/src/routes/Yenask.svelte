<script lang="ts">
  // YENASK browser governance insight assistant — dev-only route.
  //
  // Lives at /dev/yenask. See plan-doc
  // TODO/20260518-browser-governance-insight-assistant-plan.md §17
  // for the design decision log (D-01..D-11).
  //
  // PR-1 commit 2 — wires the full pipeline:
  //   click canned intent button
  //     → compileIntent(intent, catalogue)   (pure)
  //     → executePlan(plan)                  (DuckDB-WASM)
  //     → render AnswerViewModel             (table + provenance + computation)
  //
  // PR-1 ships ZERO model code (D-10). The free-text input is intentionally
  // absent until PR-2 lands the SLM adapter.

  import { onMount } from "svelte";
  import { CANNED_INTENTS } from "../lib/yenask/fixtures/canned-intents";
  import type { InsightIntent } from "../lib/yenask/contracts/insight-intent";
  import type { AnswerViewModel } from "../lib/yenask/contracts/answer-viewmodel";
  import type { SemanticCatalogue } from "../lib/yenask/types";
  import { loadSemanticCatalogue } from "../lib/yenask/semantic-catalogue";
  import { compileIntent } from "../lib/yenask/compile-intent";
  import { executePlan } from "../lib/yenask/execute-plan";
  import SourceListV2 from "../lib/SourceListV2.svelte";
  import type { SourceV2Row } from "../lib/source-list-v2";

  type Status =
    | { kind: "idle" }
    | { kind: "loading-catalogue" }
    | { kind: "ready" }
    | { kind: "executing"; intent_id: string }
    | { kind: "answered"; intent_id: string; answer: AnswerViewModel }
    | { kind: "failed"; intent_id: string | null; reason: string };

  let catalogue: SemanticCatalogue | null = $state(null);
  let status: Status = $state({ kind: "loading-catalogue" });
  let disclosureOpen = $state(false);

  onMount(() => {
    void (async () => {
      try {
        catalogue = await loadSemanticCatalogue();
        status = { kind: "ready" };
      } catch (err) {
        status = {
          kind: "failed",
          intent_id: null,
          reason: errorMessage(err, "Failed to load semantic catalogue."),
        };
      }
    })();
  });

  async function runIntent(intent_id: string, intent: InsightIntent): Promise<void> {
    if (!catalogue) {
      status = {
        kind: "failed",
        intent_id,
        reason: "Catalogue not loaded yet — please retry in a moment.",
      };
      return;
    }
    status = { kind: "executing", intent_id };
    disclosureOpen = false;
    try {
      const plan = compileIntent(intent, catalogue);
      const answer = await executePlan(plan);
      status = { kind: "answered", intent_id, answer };
    } catch (err) {
      status = {
        kind: "failed",
        intent_id,
        reason: errorMessage(err, "Compile or execute failed."),
      };
    }
  }

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
</script>

<svelte:head>
  <title>YENASK — dev preview</title>
</svelte:head>

<section class="mx-auto max-w-5xl space-y-6 p-6">
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
      <strong>PR-1.</strong> Four canned questions are wired to the canonical
      Parquet store via DuckDB-WASM. Click one to see the validated answer.
      The free-text input lands in PR-2 with the SLM adapter.
    </p>
  </header>

  {#if status.kind === "loading-catalogue"}
    <p class="text-sm text-neutral-600" data-status="loading-catalogue">
      Loading semantic catalogue…
    </p>
  {/if}

  <section class="space-y-3">
    <h2 class="text-lg font-semibold">Canned questions</h2>
    <ul class="grid gap-3 md:grid-cols-2">
      {#each CANNED_INTENTS as canned (canned.id)}
        {@const busy = status.kind === "executing" && status.intent_id === canned.id}
        <li>
          <button
            type="button"
            class="block w-full rounded-lg border border-neutral-300 bg-white p-4 text-left transition hover:border-neutral-500 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
            data-canned-id={canned.id}
            disabled={status.kind === "loading-catalogue" || status.kind === "executing"}
            onclick={() => runIntent(canned.id, canned.intent)}
          >
            <span class="block font-medium">{canned.label}</span>
            <span class="mt-1 block text-xs text-neutral-600">{canned.description}</span>
            {#if busy}
              <span class="mt-2 block text-xs italic text-neutral-500">Running…</span>
            {/if}
          </button>
        </li>
      {/each}
    </ul>
  </section>

  {#if status.kind === "failed"}
    <section
      class="space-y-2 rounded-lg border border-rose-300 bg-rose-50 p-4"
      data-testid="yenask-failure"
    >
      <h2 class="text-sm font-semibold text-rose-900">Could not answer</h2>
      <p class="text-xs text-rose-800">{status.reason}</p>
    </section>
  {/if}

  {#if status.kind === "answered"}
    {@const a = status.answer}
    <section class="space-y-3" data-testid="yenask-answer">
      <header class="space-y-1">
        <h2 class="text-lg font-semibold">{a.question}</h2>
        {#if a.provenance_status === "missing"}
          <p
            class="rounded bg-amber-100 px-3 py-2 text-xs text-amber-900"
            data-testid="yenask-source-missing"
          >
            <strong>Source unattested.</strong> The compiler could not resolve
            a citation for this answer. Treat the values as provisional.
          </p>
        {/if}
      </header>

      {#if a.rows.length === 0}
        <p class="text-sm text-neutral-600" data-testid="yenask-empty-rows">
          No matching rows. The data may not be published yet for this slice.
        </p>
      {:else}
        <div class="overflow-x-auto rounded border border-neutral-200">
          <table class="w-full text-sm" data-testid="yenask-answer-table">
            <thead class="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-600">
              <tr>
                {#each a.column_order as col}
                  <th class="px-3 py-2 font-medium">{a.column_labels[col] ?? col}</th>
                {/each}
              </tr>
            </thead>
            <tbody class="divide-y divide-neutral-100">
              {#each a.rows as row, i (i)}
                <tr>
                  {#each a.column_order as col}
                    <td class="px-3 py-2 align-top tabular-nums">
                      {formatCell(row[col], a.column_formats[col] ?? "text")}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      <div class="rounded border border-neutral-200 p-3" data-testid="yenask-source-strip">
        <SourceListV2 sources={a.source_strip as readonly SourceV2Row[]} />
      </div>

      <details
        class="rounded border border-neutral-200 p-3 text-xs"
        bind:open={disclosureOpen}
        data-testid="yenask-computation"
      >
        <summary class="cursor-pointer font-medium text-neutral-700">
          How was this computed?
        </summary>
        <div class="mt-3 space-y-3">
          <div>
            <span class="text-neutral-600">Concept:</span>
            <code class="ml-1 rounded bg-neutral-100 px-1.5 py-0.5">{a.computation.concept_id}</code>
          </div>
          <div>
            <span class="text-neutral-600">Slices registered:</span>
            <ul class="mt-1 list-disc pl-5">
              {#each a.computation.slice_registrations as s}
                <li>
                  <code>{s.table_id}</code> &nbsp;
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
            <pre
              class="mt-1 overflow-x-auto rounded bg-neutral-900 p-3 font-mono text-[11px] leading-snug text-neutral-100">{a.computation.main_sql}</pre>
          </div>
          <div>
            <span class="text-neutral-600">Provenance SQL:</span>
            <pre
              class="mt-1 overflow-x-auto rounded bg-neutral-900 p-3 font-mono text-[11px] leading-snug text-neutral-100">{a.computation.provenance_sql}</pre>
          </div>
        </div>
      </details>
    </section>
  {/if}
</section>
