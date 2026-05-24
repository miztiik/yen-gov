<script lang="ts">
  // YENASK browser governance insight assistant — dev-only route.
  //
  // Lives at /dev/yenask. NOT citizen-facing (not in LeftRail). See plan
  // doc TODO/20260518-browser-governance-insight-assistant-plan.md, in
  // particular §17 D-01 (lab-as-dev-route) and D-10 (PR-1 = zero model
  // code; only canned intents work).
  //
  // PR-1 commit 1 — this file is the routed entry point and the Zod
  // contract-roundtrip proof. The compiler / executor / UI table are not
  // wired yet; commit 2 adds them.

  import { CANNED_INTENTS } from "../lib/yenask/fixtures/canned-intents";
  import type { InsightIntent } from "../lib/yenask/contracts/insight-intent";

  let selected: InsightIntent | null = $state(null);

  function pick(intent: InsightIntent): void {
    selected = intent;
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
      <strong>PR-1 commit 1.</strong> Route registered. Zod contracts (InsightIntent +
      AnswerViewModel) loaded. The 4 canned intents below parse through the v0 Zod
      schema; clicking one shows the validated JSON. Compiler + DuckDB execution
      land in commit 2.
    </p>
  </header>

  <section class="space-y-3">
    <h2 class="text-lg font-semibold">Canned questions</h2>
    <ul class="grid gap-3 md:grid-cols-2">
      {#each CANNED_INTENTS as canned (canned.id)}
        <li>
          <button
            type="button"
            class="block w-full rounded-lg border border-neutral-300 bg-white p-4 text-left transition hover:border-neutral-500 hover:shadow-sm"
            data-canned-id={canned.id}
            onclick={() => pick(canned.intent)}
          >
            <span class="block font-medium">{canned.label}</span>
            <span class="mt-1 block text-xs text-neutral-600">{canned.description}</span>
          </button>
        </li>
      {/each}
    </ul>
  </section>

  {#if selected}
    <section class="space-y-3" data-testid="yenask-selected-intent">
      <h2 class="text-lg font-semibold">Validated InsightIntent (v0)</h2>
      <p class="text-xs text-neutral-600">
        Parsed via <code>insight.intent.v0</code> Zod schema. This is the
        payload the compiler would receive in commit 2.
      </p>
      <pre
        class="overflow-x-auto rounded bg-neutral-900 p-4 font-mono text-xs text-neutral-100">{JSON.stringify(
          selected,
          null,
          2,
        )}</pre>
    </section>
  {/if}
</section>
