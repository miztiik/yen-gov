<script lang="ts">
  // About / Disclaimer page.
  //
  // The wording on this page is the user-facing rendering of
  // docs/concepts/disclaimer.md (the canonical source of truth). When the
  // doc changes, this page should be updated in the same commit so the two
  // stay in sync (CLAUDE.md Holy Law #4 — docs and code ship together).
  //
  // Section anchors are addressable via a `?section=` query parameter on
  // the route URL (e.g. `/about?section=maps`). We read it from
  // `location.search` and scroll the matching <section> into view on mount
  // and on popstate.

  import { onMount } from "svelte";
  import { REPO_URL } from "../lib/repo";

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
    <h1 class="text-3xl font-light">About yen-gov</h1>
    <p class="text-sm text-slate-500">
      What this site is, what the data and maps are (and aren't), and how to flag mistakes.
    </p>
  </header>

  <section class="space-y-3">
    <div class="rounded-md border-l-4 border-sky-500 bg-sky-50/60 p-3 text-sm">
      <strong>yen-gov is not just an elections site.</strong> Elections are
      our first slice because the data is well-published and well-loved,
      but the project is a broader civic-data hub. Future slices will cover
      <strong>census &amp; demographics</strong>, <strong>NSO / MoSPI
      socio-economic series</strong>, <strong>welfare-scheme reporting</strong>,
      <strong>state-budget breakdowns</strong>, and other public datasets
      that are scattered across portals today.
    </div>
    <p>
      <strong>yen-gov</strong> is an open-source project that brings together
      publicly available Indian civic data into one place — fully open
      source, with the source code and the source data both visible.
    </p>
    <p>
      Today the site reads from these upstream sources:
    </p>
    <ul class="list-disc pl-5 space-y-1.5 text-sm">
      <li>
        <strong>Election Commission of India</strong> —
        <a class="text-sky-700 hover:underline" href="https://results.eci.gov.in" target="_blank" rel="noreferrer">results.eci.gov.in</a>
        for state-wise and constituency-wise results.
      </li>
      <li>
        <strong>Wikipedia</strong> — reference data for state lists,
        district lists, and constituency rosters where ECI does not
        publish a stable machine-readable form.
      </li>
      <li>
        <strong><a class="text-sky-700 hover:underline" href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HindustanTimesLabs/shapefiles</a></strong>
        — assembly-constituency boundaries (MIT licensed).
      </li>
      <li>
        <strong><a class="text-sky-700 hover:underline" href="https://github.com/datameet/maps" target="_blank" rel="noreferrer">datameet/maps</a></strong>
        — state-level India boundaries (CC BY 4.0).
      </li>
    </ul>
    <p>
      Every dataset that ships in this site carries a <code>sources</code>
      list that names the exact URL each row was pulled from and when it
      was fetched. Nothing on this site is anonymous — you can trace any
      number on any chart back to its origin.
    </p>
  </section>

  <section id="data" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">About the data</h2>
    <ul class="list-disc pl-5 space-y-2">
      <li>
        We are <strong>not the Election Commission of India</strong> and we are
        <strong>not a government source</strong>. We are a community project that
        reads public data and re-presents it.
      </li>
      <li>
        We make a <strong>best effort</strong> to be accurate and to stay close
        to the official record. Where official sources publish numbers, we
        use those numbers. Where they don't, we say so.
      </li>
      <li>
        Civic data is messy. Names get spelled multiple ways, party
        affiliations change between filing and result, postal-vote
        breakdowns arrive late, ECI itself sometimes revises numbers
        post-declaration, and socio-economic series get re-based or revised
        between releases. We try to track these, but
        <strong>errors and lag are possible.</strong>
      </li>
      <li>
        Treat anything you see here as a starting point, not the final
        word. For anything that matters — legal, journalistic, academic,
        or operational — verify against the original source we link to.
      </li>
      <li>
        Found a mistake?
        <a class="text-sky-700 hover:underline"
           href={REPO_URL} target="_blank" rel="noreferrer">
          Open an issue or a pull request on GitHub</a>.
        Patches that come with a citation get merged fastest.
      </li>
    </ul>
  </section>

  <section id="maps" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">About the maps</h2>
    <p>
      The maps you see on this site are drawn from openly licensed boundary
      files contributed by the community — primarily the
      <a class="text-sky-700 hover:underline"
         href="https://github.com/HindustanTimesLabs/shapefiles"
         target="_blank" rel="noreferrer">HindustanTimesLabs/shapefiles</a>
      and
      <a class="text-sky-700 hover:underline"
         href="https://github.com/datameet/maps"
         target="_blank" rel="noreferrer">datameet</a>
      repositories — not from the Survey of India.
    </p>
    <p>That has consequences:</p>
    <ul class="list-disc pl-5 space-y-2">
      <li>
        <strong>Boundaries are illustrative, not authoritative.</strong> They
        are accurate enough to identify a constituency or district at a
        glance, but they are <strong>not</strong> survey-grade. Do not use
        them for any legal, surveying, navigational, or boundary-dispute
        purpose.
      </li>
      <li>
        <strong>The depiction of international and internal borders</strong>
        on these maps follows the boundary files we use; it does
        <strong>not</strong> represent the position of the Government of
        India, of yen-gov, or of any contributor. For the official
        depiction of India's borders, refer to maps published by the
        <a class="text-sky-700 hover:underline"
           href="https://www.surveyofindia.gov.in/"
           target="_blank" rel="noreferrer">Survey of India</a>.
      </li>
      <li>
        Boundaries can be <strong>out of date.</strong> Constituencies are
        redrawn during delimitation; districts are created, merged, and
        renamed by state governments. Whatever vintage the upstream file
        is, our map inherits.
      </li>
      <li>
        Coverage is <strong>uneven</strong> — we currently have AC-level
        boundaries for a handful of states and add more as upstream
        sources publish them.
      </li>
    </ul>
    <p>
      If you spot a wrong boundary, the right place to fix it is usually
      upstream (HindustanTimesLabs / datameet); once the upstream file is
      corrected, our pipeline picks it up on the next refresh.
    </p>
  </section>

  <section id="project" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">About this project</h2>
    <p>
      yen-gov is built and maintained on a volunteer basis. There is no
      company behind it, no advertising, no analytics, no user accounts,
      and no data collected from you. The whole site is a static bundle
      served from GitHub Pages — what you download in your browser is
      everything there is.
    </p>
    <p>
      Source code, data files, and contribution guidelines:
      <a class="text-sky-700 hover:underline"
         href={REPO_URL} target="_blank" rel="noreferrer">{REPO_URL.replace(/^https?:\/\//, "")}</a>.
    </p>
  </section>

  <section id="as-is" class="space-y-3 scroll-mt-6">
    <h2 class="text-xl font-semibold border-b border-slate-200 pb-1">"As-is", in plain language</h2>
    <p>
      We provide this site <strong>as-is, with no warranty.</strong> We don't
      promise it's correct, complete, or current. We don't accept
      responsibility for decisions made on the basis of what you read
      here. If accuracy matters for what you're doing, go to the original
      source we cite.
    </p>
    <p>
      That said — if something looks wrong, please tell us. We want it to
      be right.
    </p>
  </section>
</main>
