<script module lang="ts">
  // CountingMethodDoc - /docs/lab/:method route. The encouraging-tone
  // long-form pedagogy that the Election Studio ImaginingCard links to
  // via its `Read how this counting works ->` footer link.
  //
  // Per Fowler + Hans convergence (2026-06-09 debate): the caveat +
  // assumptions stay on the CountingRule TS constant so the in-app
  // ImaginingCard renders them SYNCHRONOUSLY (the honesty primitive
  // must not block on a fetch - that's the rule Hans wrote into
  // HypotheticalRecountBanner). The TS constants are mirrored here in
  // the page body verbatim, then the page links OUT to the Markdown
  // long-form prose at `docs/concepts/counting-methods/<method-id>.md`
  // for history, India-specific limitations, citizen-readable academic
  // citations.
  //
  // This route mirrors the `/docs/indicator/:topic/:id` precedent
  // (IndicatorDoc.svelte) without inheriting its catalogue-fetch shape:
  // there are FOUR counting methods and they live on the rules registry,
  // not a separate JSON catalogue. Re-projecting them into JSON would be
  // ceremony with no beneficiary.

  /** Pure helper - resolves a method-id path param to the active
   *  `CountingRule` or null when the id is unknown. Pure so vitest pins
   *  the contract without mounting. */
  export function lookupMethod(method_id: string): { ok: true; rule: import("../lib/psephlab/types").CountingRule } | { ok: false } {
    const rule = ruleById(method_id);
    // ruleById falls back to fptp on miss; explicit eq check to detect
    // the miss so the page renders a 404-style panel for the bogus id.
    if (rule.id !== method_id) return { ok: false };
    return { ok: true, rule };
  }
</script>

<script lang="ts">
  import { ruleById } from "../lib/psephlab/rules";
  import { url } from "../lib/url";
  import { docsUrl } from "../lib/repo";
  import TopicIcon from "../lib/TopicIcon.svelte";

  interface Props {
    params: { method: string };
  }
  let { params }: Props = $props();

  const method_id = $derived(params.method);
  const lookup = $derived(lookupMethod(method_id));
  const rule = $derived(lookup.ok ? lookup.rule : null);

  // Long-form Markdown for the citizen-readable history + India-specific
  // limitations. Lives in the repo at docs/concepts/counting-methods/<id>.md
  // and surfaces via the centralised docsUrl helper so a fork or a rename
  // is a one-line swap (mirrors the per-mutation info icon convention).
  const long_form_href = $derived(
    docsUrl(`docs/concepts/counting-methods/${method_id}.md`),
  );
</script>

<div class="max-w-3xl mx-auto p-4 md:p-6 space-y-4">
  <nav class="text-xs" aria-label="Breadcrumb">
    <a class="text-slate-500 hover:underline" href={url.home()}>Home</a>
    <span class="text-slate-400">/</span>
    <span class="text-slate-500">Docs</span>
    <span class="text-slate-400">/</span>
    <span class="text-slate-500">Election Studio</span>
    <span class="text-slate-400">/</span>
    <span class="text-slate-700">Counting methods</span>
  </nav>

  {#if !lookup.ok || rule == null}
    <section class="rounded-lg border border-line bg-surface p-6 shadow-sm">
      <h1 class="text-xl font-bold flex items-center gap-2">
        <TopicIcon name="flask" cls="w-5 h-5 text-slate-500" />
        Counting method not found
      </h1>
      <p class="mt-2 text-sm" style:color="var(--ink-muted, #64748b)">
        No counting method matches the id <code>{method_id}</code>. The
        Election Studio currently offers four:
      </p>
      <ul class="mt-3 text-sm space-y-1">
        <li><a class="hover:underline" style:color="var(--accent, #3538cd)" href={url.docsLabMethod("fptp")}>First-Past-The-Post</a></li>
        <li><a class="hover:underline" style:color="var(--accent, #3538cd)" href={url.docsLabMethod("proportional")}>Proportional (Sainte-Lague, state-wide)</a></li>
        <li><a class="hover:underline" style:color="var(--accent, #3538cd)" href={url.docsLabMethod("ranked-choice")}>Ranked-choice (IRV, uniform transfer)</a></li>
        <li><a class="hover:underline" style:color="var(--accent, #3538cd)" href={url.docsLabMethod("approval")}>Approval (cast = approval)</a></li>
      </ul>
    </section>
  {:else}
    <header class="space-y-2">
      <h1 class="text-2xl font-bold flex items-center gap-2">
        <TopicIcon name="flask" cls="w-6 h-6 text-slate-500 shrink-0" />
        Counting method: {rule.label}
      </h1>
      <p class="text-sm" style:color="var(--ink-muted, #64748b)">
        Method id: <code class="font-mono text-xs">{rule.id}</code>
      </p>
    </header>

    {#if rule.caveat}
      <section class="rounded-md border border-line border-l-4 bg-surface p-4 shadow-sm" style:border-left-color="var(--accent, #3538cd)">
        <h2 class="text-sm font-semibold uppercase tracking-wide" style:color="var(--ink-muted, #64748b)">In one paragraph</h2>
        <p class="mt-2 text-sm leading-relaxed" style:color="var(--ink, #0f172a)">
          {rule.caveat}
        </p>
      </section>
    {/if}

    {#if rule.assumptions && rule.assumptions.length > 0}
      <section class="rounded-md border border-line bg-surface p-4 shadow-sm">
        <h2 class="text-sm font-semibold uppercase tracking-wide" style:color="var(--ink-muted, #64748b)">Assumptions this simulator makes</h2>
        <ul role="list" class="mt-3 text-sm space-y-2" style:color="var(--ink, #0f172a)">
          {#each rule.assumptions as a}
            <li class="flex gap-2">
              <span aria-hidden="true" style:color="var(--ink-muted, #64748b)">-</span>
              <span class="flex-1">{a}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    <section class="rounded-md border border-line bg-surface p-4 shadow-sm">
      <h2 class="text-sm font-semibold uppercase tracking-wide" style:color="var(--ink-muted, #64748b)">Read more</h2>
      <p class="mt-2 text-sm" style:color="var(--ink, #0f172a)">
        The long-form explanation - history, mechanics with a worked example,
        India-specific data limitations, suggested further reading - lives in
        the repo at
        <a
          href={long_form_href}
          target="_blank"
          rel="noreferrer noopener"
          class="hover:underline font-mono text-xs"
          style:color="var(--accent, #3538cd)"
        >docs/concepts/counting-methods/{method_id}.md</a>
        and renders natively on GitHub.
      </p>
      <p class="mt-3 text-sm">
        <a
          class="hover:underline"
          style:color="var(--accent, #3538cd)"
          href={url.home()}
        >&larr; Back to Yen Gov</a>
      </p>
    </section>
  {/if}
</div>
