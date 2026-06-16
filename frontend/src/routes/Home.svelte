<script lang="ts">
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { fetchTopicCatalogue, indicatorPathForArtifact, type TopicCatalogue } from "../lib/catalogue";
  import { loadIndicator } from "../lib/canonical/indicator-from-canonical";
  import IndiaPartyMap from "../lib/charts/IndiaPartyMap.svelte";
  import IndicatorChoropleth from "../lib/IndicatorChoropleth.svelte";
  import { link } from "../lib/links";
  import Breadcrumb from "../lib/Breadcrumb.svelte";
  import PageContainer from "../lib/layout/PageContainer.svelte";
  import { route } from "../lib/router.svelte";
  import HomeElectionsRail from "../lib/elections/HomeElectionsRail.svelte";
  import {
    buildHomeElectionsRailFast,
    refineHookCard,
    type HomeElectionsRailPayload,
  } from "../lib/view-models/home-elections-rail";
  import {
    defaultHomeTheme,
    homeThemeOptions,
    parseHomeTheme,
    sameTheme,
    serializeHomeTheme,
    themeCaption,
    type HomeTheme,
  } from "../lib/home-theme";

  // The IndiaMap colours each state by its leading party in that state's
  // *own* default election event (resolved from
  // datasets/taxonomy/election_events.json), so states from different
  // cohorts (May-2026, Nov-2024, Nov-2023, ...) all show up together.
  // No global "current election" — per ADR-0023 / ADR-0022.
  //
  // P5 of the IA reset adds a theme switch on top: the same India outline
  // can be re-coloured by any national-scope indicator from the catalogue
  // (`?theme=indicator/<id>`). The election theme stays default because
  // every event in election-events.json is currently `data_status: complete`
  // — see frontend/src/lib/home-theme.ts for the default-theme logic.

  let catalogue = $state<TopicCatalogue | null>(null);
  // Map of indicator-artifact id → humanised title (from each indicator
  // JSON's own `indicator.title`). Populated lazily after the catalogue
  // loads; missing entries fall through to artifact.display ?? artifact.id
  // inside homeThemeOptions, so the dropdown renders raw slugs for a
  // ~200ms window during initial load and then re-derives with human
  // labels. Fetch failures (404, network) are intentionally silent — this
  // is a degraded-UX path, not an error worth a console warning.
  let indicator_titles = $state<Map<string, string>>(new Map());
  // Tracked separately from the parsed theme so the UI can mount in a
  // skeleton state immediately and re-derive once the catalogue arrives
  // (which is when ?theme=indicator/<id> validation can run AND when the
  // PR-2 day-of-year default-theme rotation has the catalogue it needs).
  // Initialising as null avoids a ~200ms flash of the previous "always
  // election" default before the rotation kicks in.
  let theme = $state<HomeTheme | null>(null);

  fetchTopicCatalogue()
    .then(c => {
      catalogue = c;
      // Re-parse now that we can validate indicator ids.
      sync_theme_from_url();
      // Fire-and-forget: humanise the dropdown labels once the catalogue
      // tells us which national indicators are wired. Per-artifact failures
      // do not block other titles from resolving.
      load_indicator_titles(c);
    })
    .catch(e => console.warn("[home] fetchTopicCatalogue failed:", e));

  async function load_indicator_titles(cat: TopicCatalogue): Promise<void> {
    const targets: Array<{ id: string; path: string }> = [];
    for (const t of cat.topics) {
      for (const a of t.artifacts) {
        if (a.kind !== "indicator") continue;
        if ((a.scope ?? "national") !== "national") continue;
        const path = indicatorPathForArtifact(a);
        if (path === null) continue;
        targets.push({ id: a.id, path });
      }
    }
    const results = await Promise.all(
      targets.map(({ id, path }) =>
        loadIndicator(path)
          .then(art => ({ id, title: art.indicator?.title ?? null }))
          .catch(() => ({ id, title: null as string | null })),
      ),
    );
    const next = new Map<string, string>();
    for (const { id, title } of results) {
      if (title) next.set(id, title);
    }
    indicator_titles = next;
  }

  function sync_theme_from_url(): void {
    const parsed = parseHomeTheme(window.location.search, catalogue);
    // Explicit user choice (?theme=<x>) wins immediately even before the
    // catalogue resolves - parseHomeTheme already handles a null catalogue
    // for the election case. For the bare URL (no ?theme= slot) we must
    // wait for the catalogue: defaultHomeTheme(null) falls back to election
    // and would flash for ~200ms before the PR-2 curated-pool rotation
    // settles. Leave `theme` null so the skeleton stays up instead.
    if (parsed !== null) {
      if (theme === null || !sameTheme(theme, parsed)) theme = parsed;
      return;
    }
    if (catalogue === null) return;
    const next = defaultHomeTheme(catalogue);
    if (theme === null || !sameTheme(theme, next)) theme = next;
  }

  function on_theme_change(value: string): void {
    const opt = options.find(o => o.value === value);
    if (!opt) return;
    if (theme !== null && sameTheme(theme, opt.theme)) return;
    theme = opt.theme;
    const search = serializeHomeTheme(opt.theme);
    const next = search ? `${window.location.pathname}?theme=${search}` : window.location.pathname;
    window.history.replaceState(null, "", next);
  }

  onMount(() => {
    sync_theme_from_url();
    window.addEventListener("popstate", sync_theme_from_url);
    return () => window.removeEventListener("popstate", sync_theme_from_url);
  });

  const options = $derived(homeThemeOptions(catalogue, indicator_titles));
  const caption = $derived(theme ? themeCaption(theme, catalogue, indicator_titles) : "");
  const current_value = $derived(
    theme === null ? "" : theme.kind === "election" ? "election" : `indicator/${theme.id}`,
  );
  const indicator_path = $derived(
    theme?.kind === "indicator" ? `/indicators/in/${theme.id}.json` : null,
  );

  // Home topic grid: 5 featured catalogue topics + a hardcoded Elections
  // tile. Elections is a first-class section group per ADR-0022, not a
  // featured topic, so it is appended explicitly after the catalogue's
  // featured list (Jony + Citizen verdict, plan-doc PR-3 / section 0.4 of
  // the home-page-citizen-experience plan). Cap at 5 featured + 1
  // Elections = 6 cards; if the catalogue has fewer than 5 featured
  // topics the grid renders shorter and degrades gracefully.
  interface TopicCard {
    title: string;
    summary: string;
    href: string;
  }
  const topic_cards = $derived.by<TopicCard[]>(() => {
    const cards: TopicCard[] = [];
    const featured = (catalogue?.topics ?? []).filter(t => t.featured === true);
    for (const t of featured.slice(0, 5)) {
      cards.push({ title: t.title, summary: t.summary, href: link.topic(t.id) });
    }
    cards.push({
      title: "Elections",
      summary: "Assembly + parliament results, party by party",
      href: link.topic("elections"),
    });
    return cards;
  });

  // PR-W1d: per-route crumb chain. Reactive on route navigation AND
  // on async catalogue load (the builder reads states.svelte inside).
  const crumbs = $derived(route.crumbs ? route.crumbs(route.params) : []);

  // PR-W4d (2026-06-10): 3-card elections rail (anchor + hook + door).
  // Replaces the prior "almost useless, hangs without context" elections
  // experience on Home per Jony Q4 verdict. Two-phase load:
  //   1. Fast phase (catalogue only, ~200ms): renders anchor + door cards
  //      immediately with a degraded "Latest event highlights" hook.
  //   2. Refine phase (NATIONAL-PC loader, 10-30s cold DuckDB-WASM): swaps
  //      in the closest-race hook silently when the loader returns.
  // Builder failure (e.g. no eligible parliament event in the catalogue)
  // is swallowed; the skeleton stays mounted rather than throwing.
  let rail = $state<HomeElectionsRailPayload | null>(null);
  buildHomeElectionsRailFast()
    .then((p) => {
      rail = p;
      // Anchor event_id is encoded in the anchor card's href:
      //   /t/elections/<event_id>
      // Extract it for the refine call rather than threading a second
      // state field.
      const event_id = p.anchor.href.split("/").pop() ?? "";
      if (event_id) {
        refineHookCard(p, event_id)
          .then((refined) => (rail = refined))
          .catch((e) => console.warn("[home-elections-rail] refine failed:", e));
      }
    })
    .catch((e) => console.warn("[home-elections-rail] fast build failed:", e));
  // Note (PR-3): IndiaMap loads states internally via loadStates(); Home
  // no longer fetches the states list because the topic-grid front door
  // replaces the alphabetical state-name section the prior layout had.
</script>

<Breadcrumb {crumbs} />

<PageContainer width="wide">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold">yen-gov</h1>
    <p class="text-sm text-slate-500">
      Open data on India's socio-economic and electoral landscape, organised
      by topic and compared across states. Pick a topic below, or open the
      map for state-by-state comparison.
      <a href={link.about()} class="text-sky-700 hover:underline">What is this?</a>
    </p>
  </header>

  <section class="bg-white rounded-lg shadow-sm p-5 space-y-3" data-testid="home-topic-grid">
    <h2 class="text-sm font-semibold uppercase text-slate-500">Pick a topic</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {#each topic_cards as card}
        <a
          href={card.href}
          class="block p-4 bg-slate-50 hover:bg-slate-100 rounded border border-slate-200 transition-colors"
          data-testid="home-topic-card"
        >
          <div class="text-base font-semibold text-slate-900">{card.title}</div>
          {#if card.summary}
            <div class="text-xs text-slate-600 mt-1 line-clamp-2">{card.summary}</div>
          {/if}
        </a>
      {/each}
    </div>
  </section>

  <section class="bg-white rounded-lg shadow-sm p-4 space-y-3 md:-mx-6 lg:-mx-12">
    {#if theme}
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <h2 class="text-sm font-semibold uppercase text-slate-500">
          India —
          {#key caption}
            <span
              in:fade={{ duration: 180 }}
              out:fade={{ duration: 120 }}
              class="inline-block normal-case font-semibold text-slate-700"
            >{caption}</span>
          {/key}
        </h2>
        {#if options.length > 1}
          <label class="flex items-center gap-2 text-xs text-slate-600">
            <span class="uppercase tracking-wide text-[10px] text-slate-500">Theme</span>
            <select
              class="border border-slate-300 rounded px-2 py-1 text-sm bg-white"
              value={current_value}
              onchange={(e) => on_theme_change((e.currentTarget as HTMLSelectElement).value)}
            >
              {#each Array.from(new Set(options.map(o => o.group))) as group}
                <optgroup label={group}>
                  {#each options.filter(o => o.group === group) as opt}
                    <option value={opt.value}>{opt.label}</option>
                  {/each}
                </optgroup>
              {/each}
            </select>
          </label>
        {/if}
      </div>
      {#key current_value}
        <div in:fade={{ duration: 200 }}>
          {#if theme.kind === "election"}
            <IndiaPartyMap />
          {:else if indicator_path}
            <IndicatorChoropleth indicator_path={indicator_path} height="520px" />
          {/if}
        </div>
      {/key}
    {:else}
      <!--
        Bootstrap skeleton: catalogue + URL not yet resolved, so the
        PR-2 default-theme rotation has nothing to pick from. Hide the
        header + dropdown entirely until `theme` resolves rather than
        flash a half-built chrome (cleanest single-frame placeholder).
      -->
      <div
        class="h-[440px] bg-slate-50 rounded animate-pulse"
        data-testid="home-map-loading"
        aria-hidden="true"
      ></div>
    {/if}
  </section>

  {#if rail}
    <HomeElectionsRail anchor={rail.anchor} hook={rail.hook} door={rail.door} />
  {:else}
    <div
      class="h-24 bg-slate-50 rounded animate-pulse"
      data-testid="home-elections-rail-loading"
      aria-hidden="true"
    ></div>
  {/if}
</PageContainer>
