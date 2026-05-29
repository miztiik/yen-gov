<script lang="ts">
  // About page — the citizen-facing rendering of who yen-gov is and what
  // the data on this site represents. Hans-authored copy (paste-ready
  // from TODO/20260517-folded-indicator-and-collection-inventory-handover.md
  // §8.1) — when the canonical doc evolves, this page must update in the
  // same commit per CLAUDE.md Holy Law #4. The disclaimer / liability /
  // accuracy framing now lives on its sibling /disclaimer route.
  //
  // Section anchors are addressable via a `?section=` query parameter on
  // the route URL (e.g. `/about?section=what-you-find`). We read it from
  // `location.search` and scroll the matching <section> into view on
  // mount and on popstate.
  import { onMount } from "svelte";
  import { url } from "../lib/url";
  import TopicIcon from "../lib/TopicIcon.svelte";

  function focus_section(): void {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("section");
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  onMount(() => {
    focus_section();
    window.addEventListener("popstate", focus_section);
    return () => window.removeEventListener("popstate", focus_section);
  });
</script>

<main class="max-w-3xl mx-auto p-6 space-y-8 leading-relaxed text-slate-800">
  <header class="space-y-2">
    <h1 class="text-3xl font-light flex items-center gap-3">
      <TopicIcon name="info" cls="w-7 h-7 text-slate-400 shrink-0" />
      <span>About yen-gov</span>
    </h1>
    <p class="text-sm text-slate-500">
      What this site is, what it does — and what it deliberately does not do.
    </p>
  </header>

  <section class="space-y-3">
    <div class="rounded-md border-l-4 border-sky-500 bg-sky-50/60 p-3 text-sm">
      <strong>yen-gov is not just an elections site.</strong> Elections are
      our first slice because the data is well-published and well-loved,
      but the project is a broader civic-data hub covering census &amp;
      demographics, NSO / MoSPI socio-economic series, RBI / CAG fiscal
      reporting, welfare-scheme reporting, and other public datasets that
      are scattered across portals today.
    </div>
    <p>
      yen-gov republishes Indian governance and statistical data from
      official and public sources. We preserve publisher values and
      document every transformation we perform: parsing tables, mapping
      geographies, choosing revision vintages, and computing declared
      rollups. <strong>We are a re-publisher, not a statistical agency.</strong>
    </p>
  </section>

  <section id="what-you-find" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">What you'll find on every indicator</h2>
    <p>Every indicator carries an <strong>About this data</strong> panel showing:</p>
    <ul class="list-disc pl-5 space-y-2 text-sm">
      <li><strong>What the publisher measures.</strong> The publisher's definition in plain English.</li>
      <li><strong>Who publishes it.</strong> Linked to their own methodology page where available.</li>
      <li><strong>Scope.</strong> What this indicator is meant to track — which states, which years.</li>
      <li><strong>Coverage.</strong> How much of that scope we've collected, and where the gaps are. We are loud about gaps.</li>
      <li><strong>Known caveats.</strong> Documented limitations.</li>
      <li><strong>Methodology breaks.</strong> Points where the publisher changed definition, base year, or geography — so cross-period comparisons stay honest.</li>
      <li><strong>Sources.</strong> Exact URLs with the date yen-gov read them.</li>
    </ul>
    <p class="text-sm">
      Indicators where we haven't yet documented methodology are flagged
      visibly. See
      <a class="text-sky-700 hover:underline" href={url.dataCompleteness()}>/data-completeness</a>
      for the full inventory.
    </p>
  </section>

  <section id="maps" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">Boundaries on these maps</h2>
    <p class="text-sm">
      Every map on yen-gov pulls polygon geometry from an open, public
      source. We do not redraw boundaries; we redistribute what the
      publisher released under their license, and we use the publisher's
      own numeric code as the join key everywhere.
    </p>
    <h3 class="text-base font-semibold pt-2">Default source: ramSeraph LGD admin boundaries</h3>
    <p class="text-sm">
      The India state outline, the district shapes, and most per-state
      assembly constituency layers come from
      <a class="text-sky-700 hover:underline"
         href="https://github.com/ramSeraph/indian_admin_boundaries"
         target="_blank" rel="noreferrer">github.com/ramSeraph/indian_admin_boundaries</a>
      (CC0 1.0; sourced from the Local Government Directory (LGD) and
      BharatMaps). Each feature carries its LGD numeric code
      (<code>State_LGD</code> for states, <code>dist_lgd</code> for
      districts, <code>ac_no</code> for assembly constituencies); yen-gov
      uses that code as the canonical join key. We snapshot upstream
      releases into <code>datasets/boundaries/in/</code> so the site
      loads boundaries from the same origin as the page.
    </p>
    <h3 class="text-base font-semibold pt-2">State-specific notes</h3>
    <ul class="list-disc pl-5 space-y-2 text-sm">
      <li>
        <strong>Andhra Pradesh.</strong> The upstream LGD release bundles
        pre-2014 (AP + Telangana) <code>ac_no</code> values 1-294 with
        names that don't 1:1 against the post-2014 AP-only ECI numbering
        (1-175). yen-gov rewrites the LGD numbering to the post-bifurcation
        ECI numbering through a name-based reconciliation in the snapshot
        pipeline, preserving the original LGD identity on each feature.
      </li>
      <li>
        <strong>Assam.</strong> The August 2023 Delimitation Order
        (S.O. 3553(E)) reshaped all 126 ACs but is published only as a
        text-only PDF; vectorising it requires manual QGIS work that is
        deferred to a follow-up. As an interim, the Assam AC map shows
        each new AC outlined by its <em>parent district</em> polygon
        (ramSeraph LGD districts release, CC-BY-4.0). The constituency
        name and the election-result join are correct; only the polygon
        shape is coarser than the underlying AC cell.
      </li>
      <li>
        <strong>Jammu &amp; Kashmir.</strong> The post-2022 90-AC
        delimitation has not yet been published by LGD. The map uses
        <a class="text-sky-700 hover:underline"
           href="https://github.com/shijithpk/2024_maps_supplement"
           target="_blank" rel="noreferrer">shijithpk/2024_maps_supplement</a>
        (Unlicense), georeferenced from the
        <a class="text-sky-700 hover:underline"
           href="https://ceojk.nic.in/pdf/J&K%20AC%20map%20new.pdf"
           target="_blank" rel="noreferrer">J&amp;K CEO official AC map PDF</a>.
        Property key is <code>seat_id</code> instead of <code>ac_no</code>.
      </li>
    </ul>
    <p class="text-sm pt-2">
      Found a boundary that looks wrong?
      <a class="text-sky-700 hover:underline"
         href="https://github.com/miztiik/yen-gov/issues/new"
         target="_blank" rel="noreferrer">Open an issue</a>
      and we will trace it back to the source.
    </p>
  </section>

  <section id="what-we-dont-do" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">What we don't do</h2>
    <ul class="list-disc pl-5 space-y-2 text-sm">
      <li>We do not adjust, smooth, impute, or correct published values. Publisher errors appear here; we update when the publisher does.</li>
      <li>We do not estimate. Missing cells are marked <strong>Not collected yet</strong> or <strong>Not published by source</strong> — never filled in.</li>
      <li>We do not maintain a live API. The site is a static snapshot; we collect periodically and ship a new bundle.</li>
    </ul>
  </section>

  <section id="trust" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">Trust, in one sentence</h2>
    <p>
      Trust the data exactly as far as you trust the publisher. yen-gov's
      job is to make their data more accessible without changing what
      they said.
    </p>
  </section>

  <section id="more" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">More</h2>
    <ul class="list-disc pl-5 space-y-2 text-sm">
      <li>
        Legal-style framing — accuracy, completeness, methodology
        absence-of-evidence rules, citation, corrections workflow — lives
        on <a class="text-sky-700 hover:underline" href={url.disclaimer()}>/disclaimer</a>.
      </li>
      <li>
        Per-indicator collection status, including the indicators we
        haven't yet documented:
        <a class="text-sky-700 hover:underline" href={url.dataCompleteness()}>/data-completeness</a>.
      </li>
    </ul>
  </section>
</main>
