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
  //   1. Read-only consumption of folded v4.0 IndicatorArtifact fields
  //      (`methodology`, `series_spec`, `sources`). No fetches;
  //      everything is in the artifact. Coverage / completeness moved
  //      to /data-completeness in v4.0 per ADR-0026 — this panel no
  //      longer renders a per-indicator coverage block.
  //   2. Sections hide themselves when their data is empty/absent — no
  //      "N/A" stubs. The shorter the artifact, the shorter the panel.
  //   3. Period labels render verbatim (publisher's own form). No
  //      normalisation per CLAUDE.md \u00a710 anti-pattern.
  //   4. Caveats / breaks list the publisher's documented constraints;
  //      absence of a documented break is NOT a guarantee none exists
  //      (the /disclaimer page is loud about this).
  //   5. Provenance ("Sources") delegates to SourceList so the row
  //      shape stays consistent across every surface that cites data.
  //
  // 2026-05-26 (PR #322 — user mandate: "about maps we can just use
  // the I icon, we don't have to expand everything while it is showing
  // in the front end... we just need to just show it I"). The collapsed
  // surface is now a small info-icon button instead of the full
  // "About this data" text+chevron row. The expanded body carries the
  // disclosure provenance (publisher, scope, caveats, sources) once the
  // citizen opens it.
  //
  // 2026-06-12. Removed the amber stub-dot + STUB pill that previously
  // mirrored `methodology.documentation_status` on this surface. The
  // badge fired on 100% of canonical-backed indicators (every artifact
  // hard-codes `documentation_status: "stub"` until prose is authored)
  // and mis-borrowed amber's "data caution" semantics from
  // `IndicatorRanked` + the election warning panels, where amber means
  // "be careful with this data." Editorial-workflow state lives on
  // /data-completeness (the transparency route), not on citizen cards.
  // See docs/concepts/schema-is-the-design-system.md §"Honesty fields
  // are renderer guards, not opt-ins".

  import type { IndicatorArtifact } from "./indicators";
  import { indicatorArtifactPills } from "./canonical/indicator-from-canonical";
  import { SourceList, type PublisherPill } from "./sources";
  import TopicIcon from "./TopicIcon.svelte";

  interface Props {
    artifact: IndicatorArtifact;
    /** Optional explicit pills array, snapshotted by the parent BEFORE
     *  the parent assigned `artifact` into its own `$state`. Required
     *  for canonical-backed artifacts because
     *  `indicatorArtifactPills(artifact)` returns `undefined` when
     *  `artifact` is wrapped in a Svelte 5 `$state` Proxy (the WeakMap
     *  key identity is lost through the Proxy). Test fixtures and
     *  legacy on-disk JSON artifacts can omit this and rely on the
     *  accessor fallback below. See user-memory pattern "WeakMap-keyed
     *  accessor + Svelte 5 $state Proxy". */
    pills?: readonly PublisherPill[];
    /** When true (default), the panel starts collapsed behind a
     *  disclosure button. Set false to render expanded inline (e.g.
     *  inside a dedicated route that's already the disclosure). */
    collapsed?: boolean;
  }

  const { artifact, pills: pills_prop, collapsed = true }: Props = $props();

  let open = $state(!collapsed);

  const methodology = $derived(artifact.methodology);
  const series = $derived(artifact.series_spec);
  const pills = $derived(pills_prop ?? indicatorArtifactPills(artifact) ?? []);

  const has_definition = $derived(!!methodology?.definition);
  const has_publisher = $derived(!!methodology?.publisher);
  const has_caveats = $derived(!!methodology?.known_caveats?.length);
  const has_breaks = $derived(!!methodology?.methodology_breaks?.length);
  const has_scope = $derived(!!series?.description);
</script>

<details
  class="text-sm [&[open]]:rounded-md [&[open]]:border [&[open]]:border-slate-200 [&[open]]:bg-slate-50/60"
  bind:open
  data-testid="about-this-data"
>
  <summary
    class="inline-flex cursor-pointer list-none select-none rounded-md p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700 [&::-webkit-details-marker]:hidden"
    title="About this data"
    aria-label="About this data"
  >
    <TopicIcon name="info" cls="w-4 h-4 shrink-0" />
  </summary>

  <div class="px-3 pb-3 pt-2 space-y-4 text-slate-700">
    <section class="border-b border-slate-200 pb-2">
      <h3 class="text-sm font-semibold text-slate-700">About this dataset</h3>
    </section>

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
        <p>{series!.description}</p>
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
      <SourceList {pills} />
    </section>
  </div>
</details>
