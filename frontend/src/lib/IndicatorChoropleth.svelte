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
  import SourceList from "./SourceList.svelte";
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
  }

  let { indicator_path, highlight_state, height = "440px" }: Props = $props();

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
    for (const v of values.values()) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
    return { min, max };
  });

  // join-property (state-name) -> fill hex. Only states in STATE_NAME_TO_ECI
  // get a colour; the rest fall through to MapChoropleth's default grey.
  const fills = $derived.by(() => {
    const out: Record<string, string> = {};
    if (!artifact) return out;
    const dir = artifact.indicator.direction;
    const scale = artifact.indicator.scale_hint ?? "linear";
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
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
</script>

<section class="bg-white rounded-lg shadow-sm overflow-hidden">
  {#if load_error}
    <div class="p-4 text-sm bg-rose-50 border border-rose-200 text-rose-900">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !artifact}
    <div class="p-4 text-sm text-slate-500">Loading indicator…</div>
  {:else}
    <header class="px-4 pt-4 pb-3 border-b border-slate-100">
      <div class="flex justify-between items-baseline gap-3 flex-wrap">
        <div>
          <h3 class="text-base font-semibold">{artifact.indicator.title}</h3>
          {#if artifact.indicator.description}
            <p class="text-xs text-slate-500 mt-0.5">{artifact.indicator.description}</p>
          {/if}
        </div>
        <div class="text-[10px] text-slate-500 tabular-nums">
          {artifact.coverage.spatial} · {artifact.coverage.temporal}
        </div>
      </div>

      {#if times.length > 1 && selected_time}
        <div class="mt-3 flex items-center gap-3">
          <label class="text-xs text-slate-500 font-medium">Year</label>
          <input
            type="range"
            min="0"
            max={times.length - 1}
            step="1"
            value={times.indexOf(selected_time)}
            oninput={(e) => {
              const idx = Number((e.target as HTMLInputElement).value);
              selected_time = times[idx] ?? null;
            }}
            class="flex-1 max-w-xs"
          />
          <span class="text-sm font-mono tabular-nums">{selected_time}</span>
        </div>
      {:else if selected_time}
        <div class="mt-2 text-xs text-slate-500">Snapshot: <span class="font-mono">{selected_time}</span></div>
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
      <!-- Legend -->
      <div>
        <div class="text-[10px] text-slate-500 uppercase tracking-wide mb-1">
          Legend · {artifact.indicator.unit}
        </div>
        <div class="flex gap-0 items-center">
          {#each legend_stops as stop}
            <div class="flex-1 flex flex-col items-start">
              <div class="h-3 w-full" style:background-color={stop.hex}></div>
              <div class="text-[10px] text-slate-600 tabular-nums mt-1">{stop.label}</div>
            </div>
          {/each}
        </div>
      </div>

      <!-- License badge -->
      <div class="flex items-center gap-2 text-[11px]">
        <span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono">
          {artifact.license.name}
        </span>
        {#if artifact.license.url}
          <a href={artifact.license.url} target="_blank" rel="noreferrer" class="text-sky-700 hover:underline">
            license terms ↗
          </a>
        {/if}
        {#if artifact.license.redistributable === false}
          <span class="text-amber-700">non-redistributable — links only</span>
        {/if}
      </div>

      {#if artifact.indicator.notes}
        <p class="text-[11px] text-slate-500 leading-relaxed">{artifact.indicator.notes}</p>
      {/if}

      <!-- Sources -->
      <SourceList sources={artifact.sources} schema_version={artifact.$schema_version} />
    </div>
  {/if}
</section>
