<script lang="ts">
  // Phase 0.11 — DuckDB-WASM failure-state UX harness.
  //
  // Lives at /dev/duckdb-harness. NOT a citizen route. Its job is to prove,
  // end-to-end in a real browser, that:
  //   1. The Phase 0.8 loader can boot DuckDB-WASM, register the canonical
  //      elections.election_results Parquet via HTTP, and run a query.
  //   2. The D17 failure-state contract holds — forced failures render
  //      plain-language copy with a retry, no stack traces.
  //
  // Playwright drives the buttons; assertions live in
  // frontend/e2e/duckdb-harness.spec.ts.

  import { onMount } from "svelte";
  import { __resetForTests, loadManifest, query, registerTable } from "../lib/duckdb";
  import { describeFailure, type LoaderResult } from "../lib/loader-result";

  type Reading = { row_count: number; event_count: number };

  let result: LoaderResult<Reading> = $state({ status: "loading" });

  async function runRealQuery() {
    result = { status: "loading" };
    try {
      // Force a fresh manifest fetch each run so "Force 404" recovers cleanly.
      await loadManifest();
      await registerTable("elections.election_results");
      const rows = await query<{ n: bigint; events: bigint }>(
        "SELECT COUNT(*) AS n, COUNT(DISTINCT period_label) AS events FROM election_results",
      );
      const r = rows[0];
      result = {
        status: "ok",
        data: { row_count: Number(r.n), event_count: Number(r.events) },
      };
    } catch (err) {
      result = { status: "failed", reason: describeFailure(err), retry: runRealQuery };
    }
  }

  async function forceManifest404() {
    result = { status: "loading" };
    __resetForTests();
    const originalFetch = globalThis.fetch;
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/data/manifest.json")) {
        return Promise.resolve(
          new Response("not found", { status: 404, statusText: "Not Found" }),
        );
      }
      return originalFetch(input, init);
    }) as typeof fetch;
    try {
      await loadManifest();
      result = {
        status: "failed",
        reason: "Forced failure did not trigger — fetch override missed.",
        retry: runRealQuery,
      };
    } catch (err) {
      result = { status: "failed", reason: describeFailure(err), retry: runRealQuery };
    } finally {
      globalThis.fetch = originalFetch;
    }
  }

  async function forceUnknownTable() {
    result = { status: "loading" };
    try {
      await loadManifest();
      await registerTable("energy.observations", { viewName: "energy_obs" });
      result = {
        status: "failed",
        reason: "Forced failure did not trigger — unknown table did not throw.",
        retry: runRealQuery,
      };
    } catch (err) {
      result = { status: "failed", reason: describeFailure(err), retry: runRealQuery };
    }
  }

  onMount(() => {
    // Auto-run the real query so a Playwright visit sees an ok state without
    // needing to click first. The buttons below still let the human + the
    // failure-spec drive the harness through the other paths.
    void runRealQuery();
  });
</script>

<svelte:head>
  <title>DuckDB-WASM harness — yen-gov</title>
</svelte:head>

<section class="mx-auto max-w-3xl space-y-6 p-6">
  <header>
    <h1 class="text-2xl font-semibold">DuckDB-WASM failure-state harness</h1>
    <p class="text-sm text-slate-600">
      Phase 0.11 deliverable. Drives the Phase 0.8 loader through real and
      forced-failure paths so the D17 citizen-facing copy can be asserted in
      Playwright. Not a citizen route.
    </p>
  </header>

  <div class="flex flex-wrap gap-2">
    <button
      type="button"
      class="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
      data-testid="btn-real"
      onclick={runRealQuery}
    >
      Real query
    </button>
    <button
      type="button"
      class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100"
      data-testid="btn-force-404"
      onclick={forceManifest404}
    >
      Force manifest 404
    </button>
    <button
      type="button"
      class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100"
      data-testid="btn-force-unknown"
      onclick={forceUnknownTable}
    >
      Force unknown table
    </button>
  </div>

  <div class="rounded border border-slate-200 p-4" data-testid="result-pane">
    {#if result.status === "loading"}
      <p data-testid="state-loading" class="text-sm text-slate-600">
        Loading data…
      </p>
    {:else if result.status === "ok"}
      <div data-testid="state-ok" class="space-y-1">
        <p class="text-sm font-medium text-emerald-700">Query OK</p>
        <p class="text-sm">
          <span data-testid="row-count">{result.data.row_count}</span> rows across
          <span data-testid="event-count">{result.data.event_count}</span> election events.
        </p>
      </div>
    {:else if result.status === "failed"}
      <div data-testid="state-failed" class="space-y-3">
        <p class="text-sm font-medium text-rose-700">Data unavailable</p>
        <p data-testid="failure-reason" class="text-sm text-slate-700">
          {result.reason}
        </p>
        {#if result.retry}
          <button
            type="button"
            class="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
            data-testid="btn-retry"
            onclick={result.retry}
          >
            Try again
          </button>
        {/if}
      </div>
    {/if}
  </div>
</section>
