<script lang="ts">
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { fetchStates, type StateEntry } from "../lib/data";
  import { fetchTopicCatalogue, indicatorPathForArtifact, type TopicCatalogue } from "../lib/catalogue";
  import { fetchIndicator } from "../lib/indicators";
  import IndiaMap from "../lib/maplibre/IndiaMap.svelte";
  import IndicatorChoropleth from "../lib/IndicatorChoropleth.svelte";
  import { STATE_NAME_TO_ECI } from "../lib/maplibre/sources";
  import { url } from "../lib/url";
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
  // datasets/reference/in/election-events.json), so states from different
  // cohorts (May-2026, Nov-2024, Nov-2023, ...) all show up together.
  // No global "current election" — per ADR-0023 / ADR-0022.
  //
  // P5 of the IA reset adds a theme switch on top: the same India outline
  // can be re-coloured by any national-scope indicator from the catalogue
  // (`?theme=indicator/<id>`). The election theme stays default because
  // every event in election-events.json is currently `data_status: complete`
  // — see frontend/src/lib/home-theme.ts for the default-theme logic.

  let states = $state<StateEntry[] | null>(null);
  let catalogue = $state<TopicCatalogue | null>(null);
  let error = $state<string | null>(null);
  // Map of indicator-artifact id → humanised title (from each indicator
  // JSON's own `indicator.title`). Populated lazily after the catalogue
  // loads; missing entries fall through to artifact.display ?? artifact.id
  // inside homeThemeOptions, so the dropdown renders raw slugs for a
  // ~200ms window during initial load and then re-derives with human
  // labels. Fetch failures (404, network) are intentionally silent — this
  // is a degraded-UX path, not an error worth a console warning.
  let indicator_titles = $state<Map<string, string>>(new Map());
  // Tracked separately from the parsed theme so the UI can mount in
  // election mode immediately and re-derive once the catalogue arrives
  // (which is when ?theme=indicator/<id> validation can run).
  let theme = $state<HomeTheme>({ kind: "election" });

  fetchStates()
    .then(s => (states = s.states))
    .catch(e => (error = String(e)));

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
    .catch(e => (error = String(e)));

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
        fetchIndicator(path)
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
    const next = parsed ?? defaultHomeTheme(catalogue);
    if (!sameTheme(theme, next)) theme = next;
  }

  function on_theme_change(value: string): void {
    const opt = options.find(o => o.value === value);
    if (!opt) return;
    if (sameTheme(theme, opt.theme)) return;
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
  const caption = $derived(themeCaption(theme, catalogue));
  const current_value = $derived(
    theme.kind === "election" ? "election" : `indicator/${theme.id}`,
  );
  const indicator_path = $derived(
    theme.kind === "indicator" ? `/indicators/in/${theme.id}.json` : null,
  );

  // Availability is decoupled from election-data presence (ADR-0022, P2.3 of
  // IA reset). When the catalogue has any national-scope indicator artifact,
  // every state in states.json has data — indicator artifacts cover all 35+
  // entities. The election-only proxy (STATE_NAME_TO_ECI) remains a fallback
  // for the bootstrap case where the catalogue hasn't loaded yet.
  const has_national_indicator = $derived(
    (catalogue?.topics ?? []).some(t =>
      t.artifacts.some(a => a.kind === "indicator" && (a.scope ?? "national") === "national"),
    ),
  );
  const fallback_codes = new Set(Object.values(STATE_NAME_TO_ECI));
  const available = $derived(
    has_national_indicator
      ? (states ?? [])
      : (states ?? []).filter(s => fallback_codes.has(s.eci_code)),
  );
  const stub = $derived(
    has_national_indicator
      ? []
      : (states ?? []).filter(s => !fallback_codes.has(s.eci_code)),
  );
</script>

<main class="max-w-screen-2xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold">yen-gov</h1>
    <p class="text-sm text-slate-500">
      Indian civic data — fiscal capacity, energy, elections, and more,
      compared across states. Click a state to drill in.
      <a href={url.about()} class="text-sky-700 hover:underline">What is this?</a>
    </p>
  </header>

  <section class="bg-white rounded-lg shadow-sm p-4 space-y-3">
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
          <IndiaMap />
        {:else if indicator_path}
          <IndicatorChoropleth indicator_path={indicator_path} height="520px" />
        {/if}
      </div>
    {/key}
  </section>

  {#if error}
    <div class="p-4 bg-rose-50 border border-rose-200 rounded text-rose-900">
      Failed to load states: <code>{error}</code>
    </div>
  {:else if !states}
    <div class="text-slate-500">Loading…</div>
  {:else}
    <section class="bg-white rounded-lg shadow-sm p-5 space-y-3">
      <h2 class="text-sm font-semibold uppercase text-slate-500">Available</h2>
      <ul class="divide-y">
        {#each available as st}
          <li>
            <a class="flex justify-between items-center px-2 py-3 hover:bg-slate-50 rounded"
               href={url.state(st.eci_code)}>
              <span class="font-medium">{st.name}</span>
              <span class="text-xs font-mono text-slate-500">{st.eci_code} · {st.iso_3166_2}</span>
            </a>
          </li>
        {/each}
      </ul>
    </section>

    {#if stub.length}
      <section class="bg-white rounded-lg shadow-sm p-5 space-y-3 opacity-70">
        <h2 class="text-sm font-semibold uppercase text-slate-500">Other states (no data yet)</h2>
        <ul class="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm">
          {#each stub as st}
            <li class="flex justify-between">
              <span>{st.name}</span>
              <span class="text-xs font-mono text-slate-400">{st.eci_code}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</main>
