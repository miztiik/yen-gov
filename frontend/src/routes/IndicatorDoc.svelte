<script lang="ts" module>
  // Per-indicator documentation route (`/docs/indicator/:topic/:id`).
  //
  // ONE generic component reading the catalogue + grapher render hints
  // + the indicator artifact body; renders title, description,
  // methodology, source ledger, cadence, and a direct download link.
  // Never hand-authored per indicator (parent plan section 20.12).
  //
  // The two pure helpers below are exported from the module-scope
  // `<script lang="ts" module>` so vitest can cover them without
  // mounting the component (mirrors the U2a `computeCrumbs` / U5a
  // `skeletonStyle` pattern from the U5 sub-plan).

  import type { IndicatorMeta, IndicatorMethodology, IndicatorSource } from "../lib/indicators";

  /**
   * Citizen-readable label for an indicator's publisher release cadence
   * (`IndicatorMeta.cadence`). Returns "Not declared" when the artifact
   * doesn't set it - the honest "we don't know" form (Rosling: never
   * imply a fact you cannot prove). Unknown vocabulary terms fall
   * through as-is so a new cadence string surfaced by a future ingest
   * doesn't render as silent garbage.
   *
   * Distinct from `IndicatorMeta.time_grain` (the resolution of each
   * row's `time` token): cadence is the publisher's RELEASE rhythm,
   * not the row stamp's resolution. A Census frame has time_grain=year
   * but cadence=decennial.
   */
  export function cadenceLabel(cadence: string | null | undefined): string {
    if (cadence == null || cadence === "") return "Not declared";
    switch (cadence) {
      case "annual":      return "Annual";
      case "annual_fy":   return "Annual (financial year)";
      case "annual_cy":   return "Annual (calendar year)";
      case "quarterly":   return "Quarterly";
      case "quarterly_fy":return "Quarterly (financial year)";
      case "quarterly_cy":return "Quarterly (calendar year)";
      case "monthly":     return "Monthly";
      case "weekly":      return "Weekly";
      case "daily":       return "Daily";
      case "decennial":   return "Decennial (every 10 years)";
      case "ad_hoc":      return "Ad hoc (no regular schedule)";
      default:            return cadence;
    }
  }

  /**
   * Four-field source projection per parent plan section 7
   * (`owner`/`title`/`vintage`/`url`, all OPTIONAL). The legacy
   * `IndicatorSource` ledger only carries `{url, fetched_at, name?,
   * authority?}`; this helper bends it into the canonical 4-field
   * shape using available sibling metadata as fallbacks:
   *
   *   - owner   <- methodology.publisher (the producer / department)
   *   - title   <- source.name; falls back to URL host
   *   - vintage <- indicator.methodology_vintage (the publisher
   *                edition) when set, else source.fetched_at (the
   *                operator snapshot window)
   *   - url     <- source.url
   *
   * MIGRATING (parent plan section 22.7 / chunk B2a + X1a): once the
   * canonical `datasets/data/entities/source.csv` lands, the source row
   * carries the 4-field shape natively and this projection retires.
   * Until then the projection IS the source of truth for the doc page.
   */
  export interface FourFieldSource {
    owner: string | null;
    title: string | null;
    vintage: string | null;
    url: string | null;
  }

  export function projectToFourFieldSource(
    source: IndicatorSource,
    methodology: IndicatorMethodology | null | undefined,
    indicator: IndicatorMeta | null | undefined,
  ): FourFieldSource {
    return {
      owner: methodology?.publisher ?? source.authority ?? null,
      title: source.name ?? hostFromUrl(source.url) ?? null,
      vintage:
        indicator?.methodology_vintage
        ?? source.fetched_at
        ?? null,
      url: source.url ?? null,
    };
  }

  /** Pull the hostname out of a URL for a citizen-readable title
   *  fallback (`rbi.org.in`, not the full path). Returns null on
   *  parse failure. */
  function hostFromUrl(u: string | null | undefined): string | null {
    if (!u) return null;
    try {
      return new URL(u).hostname;
    } catch {
      return null;
    }
  }
</script>

<script lang="ts">
  // Per-indicator documentation page (`/docs/indicator/:topic/:id`,
  // U5b, parent plan section 20.12 IndicatorDoc bullet).
  //
  // Reads three sources to assemble the page:
  //   1. fetchTopicCatalogue() -> resolve indicator_id to its topic +
  //      catalogue label (so the page can show "Topic: Fiscal").
  //   2. fetchGrapherIndicatorCatalogue() -> chart_types + renderer_rules
  //      shown under "How this is shown".
  //   3. fetchIndicator(indicatorPathForArtifact(...)) -> the artifact
  //      body (title, description, methodology, sources, license,
  //      coverage, cadence).
  //
  // Visual states are driven through the same `ChartShell` chrome chart
  // cards use (U5a): loading -> Skeleton, error -> "Data unavailable" +
  // source line, data -> the full doc. Unknown indicator id renders a
  // clear 404-style panel inline (never blank, never a crash; mirrors
  // TopicLanding's "Topic not found" pattern).

  import { onMount } from "svelte";
  import {
    fetchTopicCatalogue,
    indicatorPathForArtifact,
    type TopicCatalogue,
    type CatalogueTopic,
    type CatalogueArtifact,
  } from "../lib/catalogue";
  import {
    fetchGrapherIndicatorCatalogue,
    lookupIndicatorRender,
    type GrapherIndicatorCatalogue,
    type IndicatorRender,
  } from "../lib/grapher/catalogue";
  import { fetchIndicator, type IndicatorArtifact } from "../lib/indicators";
  import ChartShell from "../lib/charts/ChartShell.svelte";
  import { url } from "../lib/url";
  import { DATA_BASE } from "../lib/paths";

  interface Props {
    params: { indicator_id: string };
  }
  let { params }: Props = $props();
  const indicator_id = $derived(params.indicator_id);

  // Three fetches; each may resolve, reject, or stay pending.
  let catalogue = $state<TopicCatalogue | null>(null);
  let render_catalogue = $state<GrapherIndicatorCatalogue | null>(null);
  let artifact = $state<IndicatorArtifact | null>(null);
  let load_error = $state<string | null>(null);

  onMount(() => {
    fetchTopicCatalogue()
      .then(c => (catalogue = c))
      .catch(e => (load_error = String(e)));
    fetchGrapherIndicatorCatalogue()
      .then(c => (render_catalogue = c))
      .catch(() => {
        // Render hints are non-fatal: the doc page still works without
        // them (the "How this is shown" block just degrades to "no
        // hints declared"). Suppress to keep the citizen on the page.
        render_catalogue = null;
      });
    // The artifact path is derived from the route param. We model the
    // artifact as an `indicator` kind even though we only need its id
    // here - that's what `indicatorPathForArtifact` keys against.
    const path = indicatorPathForArtifact({
      kind: "indicator",
      id: indicator_id,
    } as CatalogueArtifact);
    if (path) {
      fetchIndicator(path)
        .then(a => (artifact = a))
        .catch(e => (load_error = String(e)));
    }
  });

  // The catalogue lookup is per-indicator scoped: walk every topic, find
  // the artifact whose id matches. `null` either means catalogue still
  // loading OR the indicator id isn't in any topic (rendered as 404).
  const matched_topic = $derived<CatalogueTopic | null>(
    catalogue?.topics.find(t =>
      t.artifacts.some(a => a.kind === "indicator" && a.id === indicator_id),
    ) ?? null,
  );
  const matched_artifact = $derived<CatalogueArtifact | null>(
    matched_topic?.artifacts.find(
      a => a.kind === "indicator" && a.id === indicator_id,
    ) ?? null,
  );

  // The indicator render row from the grapher catalogue (chart_types +
  // renderer_rules). Null when render_catalogue hasn't loaded or no row
  // for this indicator.
  const indicator_render = $derived<IndicatorRender | null>(
    render_catalogue
      ? lookupIndicatorRender(render_catalogue, indicator_id)
      : null,
  );

  // Whether the catalogue is loaded and definitively does NOT contain
  // this indicator id (the 404 condition). When `catalogue` is null we
  // are still loading; only after it loads can we judge "unknown id".
  const catalogue_loaded_unknown = $derived(
    catalogue != null && matched_artifact == null,
  );

  // The download link target (the same indicator artifact the page is
  // rendering, served as a static file). Null when artifact didn't load
  // - render guards against this.
  const download_path = $derived<string | null>(
    artifact
      ? `${DATA_BASE}/indicators/in/${indicator_id}.json`
      : null,
  );

  // ChartShell body state. `"loading"` until artifact resolves OR until
  // catalogue rules out the id; `"error"` on artifact fetch failure;
  // otherwise `"data"`. `$derived.by()` (thunk form) for the multi-branch
  // case; plain `$derived(expr)` doesn't take a callable.
  //
  // Precedence: catalogue_loaded_unknown wins over load_error so an
  // unknown indicator id renders the clear "Indicator not found" panel
  // instead of leaking the underlying 404 string into the error chrome
  // (a 404 IS the canonical signal of an unknown indicator, but the
  // citizen reads better copy from the panel than the URL fragment).
  const shell_state = $derived.by<"loading" | "error" | "data">(() => {
    if (catalogue_loaded_unknown) return "data"; // 404 panel is data-state content
    if (load_error) return "error";
    if (artifact == null) return "loading";
    return "data";
  });

  // Methodology breaks + caveats are surfaced when present; the page
  // omits the section silently when neither exists (avoids an empty
  // "Methodology" header sitting over nothing - citizen-honesty rule
  // per Jony's read-aloud review on TopicLanding).
  const methodology = $derived(artifact?.methodology ?? null);
  const indicator_meta = $derived(artifact?.indicator ?? null);
  const four_field_sources = $derived(
    artifact?.sources.map(s =>
      projectToFourFieldSource(s, methodology, indicator_meta),
    ) ?? [],
  );
</script>

<section class="p-4 sm:p-6 space-y-6 max-w-4xl">
  <nav class="text-sm">
    <a href={url.topics()} class="text-sky-700 hover:underline">All topics</a>
    {#if matched_topic}
      <span class="text-slate-400 mx-1">/</span>
      <a href={url.topic(matched_topic.id)} class="text-sky-700 hover:underline">
        {matched_topic.title}
      </a>
    {/if}
  </nav>

  <ChartShell
    title={indicator_meta?.title ?? indicator_id}
    subtitle={catalogue_loaded_unknown
      ? null
      : (indicator_meta?.description_short ?? null)}
    state={shell_state}
    error_message={load_error}
  >
    {#if catalogue_loaded_unknown}
      <div class="space-y-3">
        <h2 class="text-xl font-semibold">Indicator not found</h2>
        <p class="text-sm text-slate-600">
          No indicator with id
          <code class="rounded bg-slate-100 px-1 py-0.5 font-mono">{indicator_id}</code>
          in the catalogue. Browse the
          <a href={url.topics()} class="text-sky-700 hover:underline">topic index</a>
          to find the indicator's current home.
        </p>
      </div>
    {:else if artifact && indicator_meta}
      <div class="space-y-6">
        <!-- Description (long-form definition) -->
        {#if indicator_meta.description}
          <section>
            <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-2">
              Description
            </h2>
            <p class="text-sm leading-relaxed text-slate-800">
              {indicator_meta.description}
            </p>
          </section>
        {/if}

        <!-- Methodology -->
        {#if methodology}
          <section>
            <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-2">
              Methodology
            </h2>
            <p class="text-sm leading-relaxed text-slate-800">
              {methodology.definition}
            </p>
            {#if methodology.methodology_breaks.length > 0}
              <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500 mt-4 mb-2">
                Series breaks
              </h3>
              <ul class="list-disc pl-5 text-sm space-y-1 text-slate-800">
                {#each methodology.methodology_breaks as br (br.from)}
                  <li>
                    <span class="font-medium">{br.from}:</span> {br.note}
                  </li>
                {/each}
              </ul>
            {/if}
            {#if methodology.known_caveats.length > 0}
              <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500 mt-4 mb-2">
                Known caveats
              </h3>
              <ul class="list-disc pl-5 text-sm space-y-1 text-slate-800">
                {#each methodology.known_caveats as c}
                  <li>{c}</li>
                {/each}
              </ul>
            {/if}
          </section>
        {/if}

        <!-- Cadence + coverage -->
        <section>
          <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-2">
            Release cadence
          </h2>
          <p class="text-sm text-slate-800">
            <span class="font-medium">{cadenceLabel(indicator_meta.cadence)}</span>
            {#if artifact.coverage.temporal}
              <span class="text-slate-500">
                ({artifact.coverage.spatial}, {artifact.coverage.temporal})
              </span>
            {/if}
          </p>
          <!-- TODO: surface staleness banner driven by update_period_days
               from variables.csv once chunk B2a lands (parent plan section 20.10).
               The cadence label above is the citizen-readable label for the
               release rhythm; the staleness banner is the "this hasn't
               refreshed since X" alert layered on top. -->
        </section>

        <!-- Sources (4-field projection) -->
        <section>
          <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-2">
            Sources
          </h2>
          <ul class="space-y-3">
            {#each four_field_sources as s, i (i)}
              <li class="text-sm border-l-2 border-slate-200 pl-3">
                <div class="grid grid-cols-[5rem_1fr] gap-x-3 gap-y-1">
                  <span class="text-slate-500">Owner</span>
                  <span>{s.owner ?? "\u2014"}</span>
                  <span class="text-slate-500">Title</span>
                  <span>{s.title ?? "\u2014"}</span>
                  <span class="text-slate-500">Vintage</span>
                  <span>{s.vintage ?? "\u2014"}</span>
                  <span class="text-slate-500">URL</span>
                  <span class="break-all">
                    {#if s.url}
                      <a href={s.url} target="_blank" rel="noopener" class="text-sky-700 hover:underline">
                        {s.url}
                      </a>
                    {:else}
                      {"\u2014"}
                    {/if}
                  </span>
                </div>
              </li>
            {/each}
          </ul>
          <p class="text-xs text-slate-500 mt-3">
            <strong>Note:</strong> provenance display projects the legacy
            <code class="font-mono">sources[]</code> ledger into the
            4-field shape (owner / title / vintage / url). MIGRATING to the
            canonical <code class="font-mono">datasets/data/entities/source.csv</code>
            4-field shape once chunk B2a lands (parent plan section 7).
          </p>
        </section>

        <!-- How this is shown (render hints) -->
        {#if indicator_render}
          <section>
            <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-2">
              How this is shown
            </h2>
            {#if indicator_render.chart_types && indicator_render.chart_types.length > 0}
              <p class="text-sm text-slate-800">
                Default chart: <code class="font-mono">{indicator_render.chart_types[0]}</code>
                {#if indicator_render.chart_types.length > 1}
                  (also feasible: {indicator_render.chart_types.slice(1).join(", ")})
                {/if}
              </p>
            {/if}
            {#if indicator_render.renderer_rules && indicator_render.renderer_rules.length > 0}
              <p class="text-sm text-slate-800 mt-1">
                Renderer rules: <code class="font-mono">{indicator_render.renderer_rules.join(", ")}</code>
              </p>
            {/if}
          </section>
        {/if}

        <!-- Download (direct static link to the artifact JSON) -->
        {#if download_path}
          <section>
            <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-2">
              Download
            </h2>
            <p class="text-sm text-slate-800">
              <a href={download_path} download class="text-sky-700 hover:underline font-mono">
                {indicator_id}.json
              </a>
              <span class="text-slate-500">{"\u2014 direct static link to the artifact file."}</span>
            </p>
            <!-- MIGRATING (parent plan section 22.7 / chunks F1+X1a):
                 the artifact file format flips from JSON to long-format CSV
                 (entity, time, value) once the canonical store lands. The
                 download link target rewrites as part of that cutover. -->
          </section>
        {/if}
      </div>
    {/if}
  </ChartShell>
</section>
