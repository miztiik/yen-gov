<script lang="ts">
  // Disclaimer page — legal-style framing of accuracy, completeness,
  // methodology absence-of-evidence, citation, and corrections. Sibling
  // of /about per Hans-authored copy in
  // TODO/20260517-folded-indicator-and-collection-inventory-handover.md §8.2.
  // When that canonical doc changes, this page must update in the same
  // commit (CLAUDE.md Holy Law #4).
  import { url } from "../lib/url";
</script>

<main class="max-w-3xl mx-auto p-6 space-y-8 leading-relaxed text-slate-800">
  <header class="space-y-2">
    <h1 class="text-3xl font-light">Disclaimer</h1>
    <p class="text-sm text-slate-500">
      Read this before citing or making decisions from data on this site.
    </p>
  </header>

  <section class="space-y-3">
    <p>
      yen-gov is a re-publisher of government and statistical data from
      entities including the Reserve Bank of India, the Election
      Commission of India, the Comptroller and Auditor General, the
      Ministry of Statistics and Programme Implementation, and others. We
      preserve publisher values and document parser, geography, vintage,
      and rollup transformations.
    </p>
  </section>

  <section id="accuracy" class="space-y-2 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">Accuracy</h2>
    <p>
      The figures shown here reflect what the listed publishers published
      at the time we collected them. We do not independently verify,
      correct, or estimate any figure. Errors in the original publication
      appear here; we update when the publisher updates.
    </p>
  </section>

  <section id="completeness" class="space-y-2 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">Completeness</h2>
    <p>
      Many indicators are partially collected. We mark missing cells as
      <strong>Not collected yet</strong> (source expected to publish) or
      <strong>Not published by source</strong> (publisher does not
      separately report this geography or period). Empty cells are never
      filled with estimates.
    </p>
  </section>

  <section id="methodology" class="space-y-2 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">Methodology</h2>
    <p>
      Many indicators have methodology breaks, base-year revisions,
      geographic-boundary changes, or definitional shifts over time. Where
      we have documented these, they appear on the indicator's About this
      data panel. Absence of a documented break does <strong>NOT</strong>
      mean none exists — only that we have not yet documented it. See
      <a class="text-sky-700 hover:underline" href={url.dataCompleteness()}>/data-completeness</a>.
    </p>
  </section>

  <section id="citation" class="space-y-2 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">Citation</h2>
    <p>
      When citing yen-gov, please also cite the underlying publisher.
      yen-gov is a routing layer, not a primary source.
    </p>
  </section>

  <section id="corrections" class="space-y-2 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">Corrections</h2>
    <p>
      Spotted an error in our presentation? File an issue. Spotted an
      error in the data itself? Contact the original publisher; we update
      once they publish a correction.
    </p>
  </section>
</main>
