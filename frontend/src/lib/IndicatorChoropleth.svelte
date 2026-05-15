<script lang="ts">
  // Generic indicator choropleth: drop in any indicator artifact under
  // `datasets/indicators/`, get a state-level map with time slider, legend,
  // tooltips, and source / license attribution. Driven entirely by the
  // metadata in the artifact's `indicator` block (value_kind, direction,
  // scale_hint, unit) — no per-indicator code required.
  //
  // Only `entity_kind === "state"` is supported in this version (the only
  // boundary layer in production that joins by ECI state code). District
  // and constituency variants are a follow-up: swap `INDIA_STATES` for the
  // appropriate BoundaryEntry and use a corresponding lookup table.

  import MapChoropleth from "./maplibre/MapChoropleth.svelte";
  import { INDIA_STATES, STATE_NAME_TO_ECI } from "./maplibre/sources";
  import type { GeoLevel } from "./boundaries";
  import SourceList from "./SourceList.svelte";
  import IndicatorIcon from "./IndicatorIcon.svelte";
  import RebaseBanner from "./honesty/RebaseBanner.svelte";
  import DirectionLegendCue from "./honesty/DirectionLegendCue.svelte";
  import {
    fetchIndicator,
    uniqueTimes,
    rollupByEntity,
    facetsByEntity,
    hueForDirection,
    sequentialSwatch,
    fillForValue,
    formatValue,
    type IndicatorArtifact,
  } from "./indicators";

  interface Props {
    /** Path under DATA_BASE, e.g. "/indicators/in/energy/installed_mw_by_state.json". */
    indicator_path: string;
    /** Optional ECI code to outline as the "focused" state (e.g. "S22" on
     *  the TN overview). The map highlights its boundary so the citizen
     *  can read "where do I stand?" relative to the national distribution. */
    highlight_state?: string;
    /** CSS height for the map. */
    height?: string;
    /**
     * Optional peer-set restriction. When non-null, ONLY states whose
     * ECI code is in this list receive a colour fill; non-members fall
     * through to MapChoropleth's default grey. The `highlight_state` is
     * always outlined regardless. Domain (min/max for the colour scale)
     * is computed over the peer set only — a peer-restricted choropleth
     * tells an honest within-peer story, not a softly-clipped national one.
     */
    peer_set_members?: string[] | null;
    /**
     * Geographic level to render. Default `"state"` preserves the v1 behaviour
     * (national choropleth keyed by ECI state code). Phase 3 of
     * TODO/TN-GRANULAR-GEO-PLAN.md introduces this prop as the seam for
     * district / subdistrict / village drill-downs; deeper levels are wired
     * in subsequent commits (commit 2: loader-exposed join key; commit 3:
     * loadBoundary fetch + drill click). At this commit the prop is accepted
     * but only the `"state"` branch has behaviour — passing anything else
     * still renders the state-level map (no-op), which keeps the structural
     * change reversible.
     */
    geoLevel?: GeoLevel;
  }

  let {
    indicator_path,
    highlight_state,
    height = "440px",
    peer_set_members = null,
    geoLevel = "state",
  }: Props = $props();

  let artifact = $state<IndicatorArtifact | null>(null);
  let load_error = $state<string | null>(null);
  let selected_time = $state<string | null>(null);

  // Reverse map: ECI code -> state name (for the join layer's join-property).
  const ECI_TO_NAME = $derived.by(() => {
    const out: Record<string, string> = {};
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) out[code] = name;
    return out;
  });

  $effect(() => {
    artifact = null;
    load_error = null;
    selected_time = null;
    const path = indicator_path;
    fetchIndicator(path)
      .then(a => {
        artifact = a;
        const times = uniqueTimes(a.rows);
        selected_time = times.at(-1) ?? null;
      })
      .catch(e => (load_error = String(e)));
  });

  const times = $derived(artifact ? uniqueTimes(artifact.rows) : []);

  // Aggregated value per ECI state code at the selected time.
  const values = $derived.by(() => {
    if (!artifact || !selected_time) return new Map<string, number>();
    return rollupByEntity(artifact.rows, selected_time);
  });

  const facets = $derived.by(() => {
    if (!artifact || !selected_time) {
      return new Map<string, Array<{ facet: string; value: number }>>();
    }
    return facetsByEntity(artifact.rows, selected_time);
  });

  const domain = $derived.by(() => {
    let min = Infinity;
    let max = -Infinity;
    const member_set = peer_set_members ? new Set(peer_set_members) : null;
    for (const [code, v] of values) {
      if (member_set && !member_set.has(code)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
    return { min, max };
  });

  // join-property (state-name) -> fill hex. Only states in STATE_NAME_TO_ECI
  // get a colour; the rest fall through to MapChoropleth's default grey.
  // When peer_set_members is set, non-members also fall through (greyed).
  const fills = $derived.by(() => {
    const out: Record<string, string> = {};
    if (!artifact) return out;
    const dir = artifact.indicator.direction;
    const scale = artifact.indicator.scale_hint ?? "linear";
    const member_set = peer_set_members ? new Set(peer_set_members) : null;
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      if (member_set && !member_set.has(code)) continue;
      const v = values.get(code);
      if (v === undefined) continue;
      out[name] = fillForValue(v, domain.min, domain.max, dir, scale);
    }
    return out;
  });

  const tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    if (!artifact) return out;
    const meta = artifact.indicator;
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      const v = values.get(code);
      if (v === undefined) {
        out[name] = `<div class="font-semibold">${escape_html(name)}</div>` +
                    `<div class="text-slate-500">no data for ${escape_html(selected_time ?? "")}</div>`;
        continue;
      }
      const formatted = formatValue(v, meta);
      const breakdown = facets.get(code) ?? [];
      const has_real_facets = breakdown.length > 1 || (breakdown[0]?.facet ?? "") !== "";
      const rows_html = has_real_facets
        ? breakdown.slice(0, 5).map(f =>
            `<div class="flex justify-between gap-2"><span>${escape_html(humanFacet(f.facet))}</span>` +
            `<span class="tabular-nums text-slate-500">${escape_html(formatValue(f.value, meta))}</span></div>`,
          ).join("")
        : "";
      out[name] =
        `<div class="font-semibold">${escape_html(name)} <span class="text-slate-400 font-mono text-[10px]">${code}</span></div>` +
        `<div class="tabular-nums">${escape_html(formatted)}</div>` +
        (rows_html ? `<div class="text-slate-600 mt-1 text-xs">${rows_html}</div>` : "");
    }
    return out;
  });

  const highlight_key = $derived(highlight_state ? ECI_TO_NAME[highlight_state] : undefined);

  function escape_html(s: string): string {
    return s.replace(/[&<>"']/g, c =>
      c === "&" ? "&amp;" :
      c === "<" ? "&lt;" :
      c === ">" ? "&gt;" :
      c === '"' ? "&quot;" : "&#39;",
    );
  }

  function humanFacet(f: string): string {
    if (!f) return "value";
    // "coal_power_plant" -> "Coal power plant"
    const s = f.replace(/_/g, " ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  // Legend swatches at 0, 0.25, 0.5, 0.75, 1 of the ramp.
  const legend_stops = $derived.by(() => {
    const a = artifact;
    if (!a) return [] as Array<{ t: number; hex: string; label: string }>;
    const hue = hueForDirection(a.indicator.direction);
    const ts = [0, 0.25, 0.5, 0.75, 1];
    return ts.map(t => ({
      t,
      hex: sequentialSwatch(t, hue),
      label: formatValue(domain.min + t * (domain.max - domain.min), a.indicator),
    }));
  });

  // CSS gradient string for the new continuous legend bar (UX P0-1).
  const legend_gradient = $derived.by(() => {
    if (!artifact) return "";
    const stops = legend_stops.map(s => `${s.hex} ${(s.t * 100).toFixed(0)}%`).join(", ");
    return `linear-gradient(to right, ${stops})`;
  });

  // Coverage caption (Citizen P0 + UX P0-2): make "4 of 35 states" first-class
  // info above the map, not a footnote. Honours the peer-set restriction:
  // when active, both numerator and denominator are computed within the
  // peer set (otherwise the caption would mislead — e.g. "31 of 36" makes
  // no sense when only 18 general-category states are on the map).
  const coverage_summary = $derived.by(() => {
    if (!artifact) return null;
    const member_set = peer_set_members ? new Set(peer_set_members) : null;
    const all_codes = Object.values(STATE_NAME_TO_ECI);
    const peer_codes = member_set
      ? all_codes.filter(c => member_set.has(c))
      : all_codes;
    const total = peer_codes.length;
    let covered = 0;
    for (const c of peer_codes) if (values.has(c)) covered++;
    if (covered === total) return null;
    return { covered, total };
  });

  // Stale-data chip (UX P0-2): if the only year is more than ~2 years stale,
  // surface that prominently rather than burying it in slate-500 11px.
  const STALE_THRESHOLD_YEARS = 2;
  const TODAY_YEAR = new Date().getFullYear();
  const stale_chip = $derived.by(() => {
    if (!artifact || !selected_time || times.length > 1) return null;
    const yr = parseInt(selected_time.slice(0, 4), 10);
    if (!Number.isFinite(yr)) return null;
    const age = TODAY_YEAR - yr;
    if (age <= STALE_THRESHOLD_YEARS) return null;
    return { year: yr, age };
  });

  // Comparability banner (Governance §1 + Citizen): if the indicator declares
  // not_comparable_across_states OR attribution_geography is where_produced,
  // tell the citizen the choropleth is illustrative, not a ranking.
  const comparability_banner = $derived.by(() => {
    if (!artifact) return null;
    const ind = artifact.indicator;
    if (ind.comparability === "not_comparable_across_states") {
      return {
        kind: "amber" as const,
        text: ind.attribution_geography === "where_produced"
          ? "This map shows where the asset is sited, not who uses it. Ranking states by this number is misleading."
          : "Values are not directly comparable across states without normalisation. Treat the colour ramp as illustrative.",
      };
    }
    if (ind.attribution_geography === "where_produced") {
      return {
        kind: "slate" as const,
        text: "Values reflect siting (where the asset is located), not service (who consumes/benefits).",
      };
    }
    if (ind.comparability === "comparable_with_normalisation" && !ind.denominator) {
      return {
        kind: "slate" as const,
        text: "Per-capita / per-area normalisation is recommended for cross-state comparison.",
      };
    }
    return null;
  });
</script>

<section class="bg-white rounded-lg shadow-sm overflow-hidden">
  {#if load_error}
    <div class="p-4 text-sm bg-rose-50 border border-rose-200 text-rose-900">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !artifact}
    <div class="p-4 text-sm text-slate-500">Loading indicator…</div>
  {:else}
    <header class="px-4 pt-4 pb-3 border-b border-slate-100 space-y-2">
      <div class="flex justify-between items-baseline gap-3 flex-wrap">
        <div class="min-w-0">
          <h3 class="text-base font-semibold flex items-baseline gap-2">
            {#if artifact.indicator.icon}
              <IndicatorIcon
                name={artifact.indicator.icon}
                cls="w-4 h-4 text-slate-500 self-center"
                title={artifact.indicator.title}
              />
            {/if}
            <span>{artifact.indicator.title}</span>
            {#if artifact.indicator.implementing_authority && artifact.indicator.implementing_authority !== "state"}
              <span
                class="text-[10px] font-normal px-1.5 py-0.5 rounded bg-slate-100 text-slate-600"
                title={artifact.indicator.funding_split
                  ? `Centre ${artifact.indicator.funding_split.centre_pct}% / state ${artifact.indicator.funding_split.state_pct}%`
                  : "Centre involvement in funding or implementation"}
              >
                {artifact.indicator.implementing_authority === "joint" ? "Centre + state" :
                 artifact.indicator.implementing_authority === "centre" ? "Central" :
                 artifact.indicator.implementing_authority === "local_body" ? "Local body" : "Parastatal"}
              </span>
            {/if}
          </h3>
          {#if artifact.indicator.description}
            <p class="text-xs text-slate-500 mt-0.5 leading-relaxed">{artifact.indicator.description}</p>
          {/if}
        </div>
      </div>

      <!-- Comparability / attribution banner: surfaces honesty metadata above
           the map so a citizen reads the caveat BEFORE forming a verdict. -->
      {#if comparability_banner}
        <div
          class="text-[11px] px-2.5 py-1.5 rounded leading-snug"
          class:bg-amber-50={comparability_banner.kind === "amber"}
          class:text-amber-900={comparability_banner.kind === "amber"}
          class:border={comparability_banner.kind === "amber"}
          class:border-amber-200={comparability_banner.kind === "amber"}
          class:bg-slate-50={comparability_banner.kind === "slate"}
          class:text-slate-700={comparability_banner.kind === "slate"}
        >
          <strong class="font-semibold">Read this carefully · </strong>{comparability_banner.text}
        </div>
      {/if}

      <!-- Phase 2 honesty: rebase banner for index-series indicators.
           Component self-gates on value_kind === "index"; renders nothing
           for currency/rate/share/count series. -->
      <RebaseBanner meta={artifact.indicator} />

      <!-- Coverage + temporal: first-class info, not a footnote. -->
      <div class="flex justify-between items-center gap-3 flex-wrap text-[11px]">
        {#if coverage_summary}
          <span class="text-amber-800">
            <strong class="font-semibold tabular-nums">{coverage_summary.covered} of {coverage_summary.total}</strong>
            states/UTs have data on this map. The rest are grey because data is missing, not because they have zero.
          </span>
        {:else}
          <span class="text-slate-500">{artifact.coverage.spatial}</span>
        {/if}
        {#if stale_chip}
          <span
            class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 font-medium"
            title="The election you came for is much more recent than this data."
          >Snapshot · {stale_chip.year} ({stale_chip.age} years old)</span>
        {/if}
      </div>

      {#if times.length > 1 && selected_time}
        <div class="flex items-center gap-3 pt-1">
          <label class="text-xs text-slate-500 font-medium" for="indicator-year-slider">Year</label>
          <input
            id="indicator-year-slider"
            type="range"
            min="0"
            max={times.length - 1}
            step="1"
            value={times.indexOf(selected_time)}
            list={`indicator-year-ticks-${artifact.indicator.id.replace(/[^a-z0-9]/gi, "_")}`}
            oninput={(e) => {
              const idx = Number((e.target as HTMLInputElement).value);
              selected_time = times[idx] ?? null;
            }}
            class="flex-1 max-w-xs"
          />
          <datalist id={`indicator-year-ticks-${artifact.indicator.id.replace(/[^a-z0-9]/gi, "_")}`}>
            {#each times as t, i}
              <option value={i}>{t}</option>
            {/each}
          </datalist>
          <span class="text-sm font-mono tabular-nums">{selected_time}</span>
        </div>
      {/if}
    </header>

    <div>
      <MapChoropleth
        entry={INDIA_STATES}
        {fills}
        {tooltips}
        {height}
        highlight_key={highlight_key}
      />
    </div>

    <div class="px-4 py-3 border-t border-slate-100 space-y-3">
      <!-- Legend: continuous gradient bar + single 3-tick numeric axis,
           replacing 5 separate swatches with 5 separately-formatted unit
           labels (UX P0-1). One eye-stop, one numeric reading. -->
      <div>
        <div class="text-[10px] text-slate-500 uppercase tracking-wide mb-1 flex items-center gap-2 flex-wrap">
          <span>Legend</span>
          <span class="text-slate-400 normal-case font-normal">{artifact.indicator.unit}</span>
          <!-- Phase 2 honesty: ↑/↓/↔ cue so the citizen reads the colour ramp
               correctly for direction-asymmetric indicators (e.g. IMR=lower
               is better; HDI=higher is better). -->
          <span class="ml-auto normal-case font-normal">
            <DirectionLegendCue direction={artifact.indicator.direction} />
          </span>
        </div>
        <div class="h-3 w-full rounded-sm" style:background={legend_gradient}></div>
        <div class="flex justify-between text-[10px] text-slate-600 tabular-nums mt-1">
          <span>{legend_stops[0]?.label ?? ""}</span>
          <span>{legend_stops[2]?.label ?? ""}</span>
          <span>{legend_stops[4]?.label ?? ""}</span>
        </div>
      </div>

      <!-- Notes promoted to high priority: it shapes interpretation. -->
      {#if artifact.indicator.notes}
        <p class="text-[12px] text-slate-700 leading-relaxed">{artifact.indicator.notes}</p>
      {/if}

      <!-- Methodology vintage + series breaks (governance honesty). -->
      {#if artifact.indicator.methodology_vintage || (artifact.indicator.series_breaks?.length ?? 0) > 0}
        <div class="text-[11px] text-slate-500 space-y-0.5">
          {#if artifact.indicator.methodology_vintage}
            <div><span class="text-slate-400">Methodology · </span>{artifact.indicator.methodology_vintage}</div>
          {/if}
          {#each artifact.indicator.series_breaks ?? [] as br}
            <div><span class="text-amber-700">Series break · </span>{br.at_time} ({br.kind}): {br.note}</div>
          {/each}
        </div>
      {/if}

      <!-- License + provenance: legally significant; demoted only by being last. -->
      <div class="flex items-center gap-2 text-[11px] flex-wrap">
        <span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
          {artifact.license.name}
        </span>
        {#if artifact.license.url}
          <a href={artifact.license.url} target="_blank" rel="noreferrer" class="text-sky-700 hover:underline">
            license terms ↗
          </a>
        {/if}
        {#if artifact.license.redistributable === false}
          <span class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 font-medium">non-redistributable — links only</span>
        {/if}
      </div>

      <SourceList sources={artifact.sources} schema_version={artifact.$schema_version} />
    </div>
  {/if}
</section>
