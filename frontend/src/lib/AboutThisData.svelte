<script lang="ts">
  // AboutThisData — citizen-facing disclosure that surfaces an
  // indicator's methodology, scope, coverage, and source provenance in
  // one collapsible block. Mounts at the foot of every IndicatorCard so
  // any rendered indicator carries its own paper-trail without the
  // citizen having to leave the page.
  //
  // Design rules (Hans-authored copy from
  // TODO/20260517-folded-indicator-and-collection-inventory-handover.md
  // §8.1 — the "What you'll find on every indicator" panel):
  //
  //   1. Read-only consumption of folded v3.0 IndicatorArtifact fields
  //      (`methodology`, `series_spec`, `collection_inventory`,
  //      `sources`). No fetches; everything is in the artifact.
  //   2. Sections hide themselves when their data is empty/absent — no
  //      "N/A" stubs. The shorter the artifact, the shorter the panel.
  //   3. Period labels render verbatim (publisher's own form). No
  //      normalisation per CLAUDE.md \u00a710 anti-pattern.
  //   4. Caveats / breaks list the publisher's documented constraints;
  //      absence of a documented break is NOT a guarantee none exists
  //      (the /disclaimer page is loud about this).
  //   5. Provenance ("Sources") delegates to SourceList so the row
  //      shape stays consistent across every surface that cites data.

  import type { IndicatorArtifact } from "./indicators";
  import SourceList from "./SourceList.svelte";

  interface Props {
    artifact: IndicatorArtifact;
    /** When true (default), the panel starts collapsed behind a
     *  disclosure button. Set false to render expanded inline (e.g.
     *  inside a dedicated route that's already the disclosure). */
    collapsed?: boolean;
  }

  const { artifact, collapsed = true }: Props = $props();

  let open = $state(!collapsed);

  const methodology = $derived(artifact.methodology);
  const series = $derived(artifact.series_spec);
  const inventory = $derived(artifact.collection_inventory);

  const has_definition = $derived(!!methodology?.definition);
  const has_publisher = $derived(!!methodology?.publisher);
  const has_caveats = $derived(!!methodology?.known_caveats?.length);
  const has_breaks = $derived(!!methodology?.methodology_breaks?.length);
  const has_scope = $derived(!!series?.description || !!series?.expected_geographies?.length);
  const has_coverage = $derived(!!inventory);
  const doc_status = $derived(methodology?.documentation_status ?? "stub");
</script>

<details
  class="rounded-md border border-slate-200 bg-slate-50/60 text-sm"
  bind:open
  data-testid="about-this-data"
>
  <summary class="cursor-pointer px-3 py-2 select-none font-medium text-slate-700 hover:bg-slate-100">
    About this data
    {#if doc_status !== "authored"}
      <span
        class="ml-2 inline-block rounded-sm bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800"
        title="Methodology documentation is incomplete on yen-gov; see /data-completeness for the full list."
      >{doc_status}</span>
    {/if}
  </summary>

  <div class="px-3 pb-3 pt-1 space-y-4 text-slate-700">
    {#if has_definition}
      <section class="space-y-1">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">What the publisher measures</h4>
        <p>{methodology!.definition}</p>
      </section>
    {/if}

    {#if has_publisher}
      <section class="space-y-1">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">Who publishes it</h4>
        <p>
          {methodology!.publisher}
          {#if methodology!.publisher_methodology_url}
            &middot;
            <a
              class="text-sky-700 hover:underline"
              href={methodology!.publisher_methodology_url}
              target="_blank"
              rel="noopener noreferrer"
            >Publisher methodology &#8599;</a>
          {/if}
        </p>
      </section>
    {/if}

    {#if has_scope}
      <section class="space-y-1">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">Scope</h4>
        {#if series!.description}
          <p>{series!.description}</p>
        {/if}
        {#if series!.expected_geographies?.length}
          <p class="text-xs text-slate-500">
            Tracked for {series!.expected_geographies.length} geograph{series!.expected_geographies.length === 1 ? "y" : "ies"}.
          </p>
        {/if}
      </section>
    {/if}

    {#if has_coverage}
      {@const obs = inventory!.observed_periods?.length ?? 0}
      {@const pend = inventory!.pending_periods?.length ?? 0}
      {@const unav = inventory!.unavailable_periods?.length ?? 0}
      <section class="space-y-1">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">Coverage</h4>
        <p>
          Status: <strong>{inventory!.status}</strong>.
          Observed {obs} period{obs === 1 ? "" : "s"};
          {pend} not collected yet;
          {unav} not published by source.
        </p>
        {#if inventory!.last_collected_at}
          <p class="text-xs text-slate-500">Last collected from source on {inventory!.last_collected_at.slice(0, 10)}.</p>
        {/if}
      </section>
    {/if}

    {#if has_caveats}
      <section class="space-y-1">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">Known caveats</h4>
        <ul class="list-disc pl-5 space-y-1">
          {#each methodology!.known_caveats as caveat (caveat)}
            <li>{caveat}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if has_breaks}
      <section class="space-y-1">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">Methodology breaks</h4>
        <ul class="list-disc pl-5 space-y-1">
          {#each methodology!.methodology_breaks as brk (brk.from)}
            <li><strong>{brk.from}</strong>: {brk.note}</li>
          {/each}
        </ul>
      </section>
    {/if}

    <section class="space-y-1">
      <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">Sources</h4>
      <SourceList sources={artifact.sources} schema_version={artifact.$schema_version} />
    </section>
  </div>
</details>
