<script module lang="ts">
  /**
   * F2b.3 GeoChoropleth - the d3-geo SVG static welfare-map primitive
   * per parent plan section 14.5 ("d3-geo SVG for ALL static welfare
   * choropleths; maplibre-gl fenced to the election AC pan/zoom
   * explorer only"). Replaces the maplibre-based IndicatorChoropleth
   * for the citizen-facing static-map renderer surface.
   *
   * Doctrine ties (parent plan section 14.3 + 14.5 + 15.1):
   *   - C1 in section 14.3. Renders ALL geometry; no-data regions get
   *     the C4 hatch fill (the same diagonal-stripe SVG pattern
   *     CategoryBar inherited from the retired OrderedCategoryBar /
   *     HorizontalGroupedBar bodies post-F2a).
   *   - Loads the topojson via fetch + decodes via topojson-client
   *     `feature(topo, topo.objects[objectKey])`; projection via
   *     geoMercator().fitSize per the F4 island-render-smoke contract.
   *     The smoke ([frontend/src/contracts/topojson-island-render.test.ts])
   *     is the regression contract for this loader; this renderer
   *     does NOT re-add or duplicate the smoke.
   *   - Mounts the F2b.2 C2 (ChoroplethLegend), C3 (MapTooltip), C5
   *     (SourceLine) primitives. Color resolution via the F2b.2
   *     binnedSequential() helper - one palette, shared with Matrix
   *     per parent plan section 14.5 doctrine #5.
   *   - CLAUDE.md section 0: no aria/role on the SVG body. Visible
   *     affordances only (the tooltip + cursor change are visible).
   *
   * Pure helper functions live in `geo-choropleth-helpers.ts`
   * (sibling module) so vitest can cover them without mounting a
   * DOM. The svelte component is the wiring layer.
   */
  export { rowsByFeatureKey, deriveDomain } from "./geo-choropleth-helpers";
</script>

<script lang="ts">
  import { onMount } from "svelte";
  import {
    geoMercator,
    geoPath,
    type GeoPermissibleObjects,
    type GeoProjection,
  } from "d3-geo";
  import { feature as topojsonFeature } from "topojson-client";
  import type { Topology, GeometryCollection } from "topojson-specification";
  import type {
    Feature,
    FeatureCollection,
    Geometry,
    GeoJsonProperties,
  } from "geojson";

  import { DATA_BASE } from "../paths";
  import { type Direction } from "../indicators";
  import {
    binnedSequential,
    type BinnedSequentialScale,
  } from "./color-scale";
  import ChoroplethLegend from "./ChoroplethLegend.svelte";
  import MapTooltip from "./MapTooltip.svelte";
  import SourceLine from "./SourceLine.svelte";
  import {
    deriveDomain,
    rowsByFeatureKey,
    type GeoChoroplethRow,
  } from "./geo-choropleth-helpers";

  interface Props {
    /** DATA_BASE-relative topojson path, e.g.
     *  `/boundaries/in/states/all.topojson` (the F4-shipped corpus). */
    topojson_path: string;
    /** The feature.properties[feature_key] field carrying the entity
     *  id used to join rows (e.g. "st_lgd", "dist_lgd"). */
    feature_key: string;
    /** Observation rows; one per entity-time pair. */
    rows: readonly GeoChoroplethRow[];
    /** Optional time slice filter; when supplied, only rows with
     *  matching `time` contribute to the rendered values. Null = all
     *  rows go through (single-slice case). */
    selected_time?: string | number | null;
    /** Optional explicit domain override; defaults to deriveDomain(rows). */
    domain?: { min: number; max: number };
    /** Indicator direction; drives the OkLCh ramp hue per
     *  hueForDirection(). */
    direction?: Direction;
    /** Bins for the legend ColorScale. Defaults to 5. */
    bins?: number;
    /** d3-format tick label string. */
    format_tick?: string;
    /** Citizen-readable value formatter for the tooltip (e.g. "24.1 GW").
     *  Defaults to d3-format ".2s". */
    format_value?: (v: number) => string;
    /** Chart title (shown above the map). */
    title: string;
    /** Source attribution: publisher name (mandatory for C5). */
    source_owner: string;
    /** Source vintage label (e.g. "FY 2023-24"). */
    source_vintage: string;
    /** Optional source URL; renders the source line as a link. */
    source_url?: string | null;
    /** SVG width in px. Caller controls layout. */
    width?: number;
    /** SVG height in px. */
    height?: number;
  }

  const {
    topojson_path,
    feature_key,
    rows,
    selected_time = null,
    domain: domain_override,
    direction = "neutral",
    bins = 5,
    format_tick = ".2s",
    format_value,
    title,
    source_owner,
    source_vintage,
    source_url = null,
    width = 640,
    height = 480,
  }: Props = $props();

  let collection = $state<FeatureCollection<Geometry, GeoJsonProperties> | null>(null);
  let load_error = $state<string | null>(null);

  // Hover state - drives both the C3 tooltip + the C2 legend
  // value-tick. The hovered feature's value is the value-tick.
  let hover_feature_key = $state<string | number | null>(null);
  let hover_x = $state<number>(0);
  let hover_y = $state<number>(0);

  // Citizen-readable value formatter. d3-format SI by default.
  const fmt = $derived.by(() => {
    if (format_value) return format_value;
    // Lazy: import format at use-time to keep the typed surface small.
    // Inline closure over d3-format string for callers that don't
    // supply their own formatter.
    return (v: number): string => {
      // Avoid an import cycle by relying on toLocaleString for the
      // tooltip default; the legend ticks use d3-format via
      // color-scale.ts so the look is consistent.
      if (!Number.isFinite(v)) return "-";
      if (Math.abs(v) >= 1000) {
        return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
      }
      return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    };
  });

  // Load the topojson once on mount. The 404-as-null + topojson-only
  // contract is appropriate for F2b: this renderer is fenced to the
  // F4-shipped national topojsons + state shards; geojson fallback
  // belongs in the older maplibre loader, not here.
  onMount(() => {
    let cancelled = false;
    const url = `${DATA_BASE}${topojson_path}`;
    (async () => {
      try {
        const r = await fetch(url);
        if (!r.ok) {
          load_error = `topojson fetch failed: ${r.status} ${url}`;
          return;
        }
        const topo = (await r.json()) as Topology;
        const objectKeys = Object.keys(topo.objects ?? {});
        if (objectKeys.length === 0) {
          load_error = `topojson has no objects: ${url}`;
          return;
        }
        const fc = topojsonFeature(
          topo,
          topo.objects[objectKeys[0]] as GeometryCollection,
        ) as unknown as FeatureCollection<Geometry, GeoJsonProperties>;
        if (cancelled) return;
        collection = fc;
      } catch (e) {
        if (cancelled) return;
        load_error = String(e);
      }
    })();
    return () => {
      cancelled = true;
    };
  });

  // Filter rows by selected_time once at the top of the pipeline.
  const time_rows = $derived(
    selected_time == null
      ? rows
      : rows.filter(r => r.time === selected_time),
  );

  // Build the feature-key -> value map. Pure helper.
  const value_by_key = $derived(rowsByFeatureKey(time_rows));

  // Derive the domain from the filtered rows (unless caller supplied one).
  const resolved_domain = $derived(domain_override ?? deriveDomain(time_rows));

  // Build the binned color scale. Drives both fills + the legend.
  const scale: BinnedSequentialScale = $derived(
    binnedSequential({
      domain: resolved_domain,
      bins,
      direction,
      format_tick,
    }),
  );

  // Build the d3-geo projection + path once the collection is loaded.
  const projection_path = $derived.by(() => {
    if (!collection) return null;
    const projection: GeoProjection = geoMercator().fitSize(
      [width, height],
      collection as GeoPermissibleObjects,
    );
    const path = geoPath(projection);
    return { projection, path };
  });

  // Resolve fill for a feature: lookup the row by feature_key, then
  // colorForValue. Null/missing rows fall through to the hatch (via
  // a special return value). The hatch is rendered as a fill
  // referencing the SVG <pattern> defined inside this component.
  const HATCH_FILL = "url(#geo-choropleth-hatch)";
  function fillForFeature(f: Feature<Geometry, GeoJsonProperties>): string {
    const key = f.properties?.[feature_key];
    if (key == null) return HATCH_FILL;
    const value = value_by_key.get(String(key));
    if (value == null) return HATCH_FILL;
    return scale.colorForValue(value);
  }

  // Tooltip payload for the hovered feature. Null when no hover or
  // when the hovered feature has no value (we still show the tooltip
  // but with the "no data" placeholder so the citizen sees the region
  // name they're hovering).
  const hover_payload = $derived.by(() => {
    if (hover_feature_key == null || !collection) return null;
    const f = collection.features.find(
      x => String(x.properties?.[feature_key]) === String(hover_feature_key),
    );
    if (!f) return null;
    const key = String(f.properties?.[feature_key]);
    const value = value_by_key.get(key);
    return {
      // Label fallback chain matches the existing IndicatorChoropleth
      // NAME_KEYS (lib/IndicatorChoropleth.svelte line ~449) plus the
      // state-topojson convention (`Remarks` carries the title-case
      // name; `STNAME` carries the uppercase form). Citizen-readable
      // labels are preferred (Remarks > name > dtname > STNAME > ST_NM).
      region_label: String(
        f.properties?.label ??
          f.properties?.Remarks ??
          f.properties?.name ??
          f.properties?.dtname ??
          f.properties?.STNAME ??
          f.properties?.ST_NM ??
          key,
      ),
      parent_label: f.properties?.parent_label
        ? String(f.properties.parent_label)
        : null,
      value,
      formatted_value: value == null ? "No data" : fmt(value),
      swatch_color: value == null ? "#e2e8f0" : scale.colorForValue(value),
    };
  });

  function onFeatureMouseEnter(
    f: Feature<Geometry, GeoJsonProperties>,
    e: MouseEvent,
  ): void {
    hover_feature_key = f.properties?.[feature_key] ?? null;
    hover_x = e.offsetX + 10;
    hover_y = e.offsetY + 10;
  }
  function onFeatureMouseMove(e: MouseEvent): void {
    hover_x = e.offsetX + 10;
    hover_y = e.offsetY + 10;
  }
  function onFeatureMouseLeave(): void {
    hover_feature_key = null;
  }
</script>

<div
  class="geo-choropleth"
  data-component="geo-choropleth"
  data-mode="fill"
  style="width: {width}px;"
>
  <div class="geo-choropleth__title">{title}</div>

  <div
    class="geo-choropleth__canvas"
    style="position: relative; width: {width}px; height: {height}px;"
  >
    {#if load_error}
      <div class="geo-choropleth__error">{load_error}</div>
    {:else if collection && projection_path}
      <svg
        class="geo-choropleth__svg"
        width={width}
        height={height}
        viewBox="0 0 {width} {height}"
      >
        <defs>
          <!-- C4 diagonal-stripe hatch for no-data regions. Same
               visual language as the existing CategoryBar bodies
               (carried over from the retired
               OrderedCategoryBar.ocb__hatch / HorizontalGroupedBar.hgb__cell-hatch
               post-F2a) so the citizen sees one no-data idiom across
               the whole chart family. -->
          <pattern
            id="geo-choropleth-hatch"
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="#ffffff" />
            <rect width="2" height="6" fill="#d8d8d8" />
          </pattern>
        </defs>
        {#each collection.features as f}
          <path
            d={projection_path.path(f) ?? ""}
            fill={fillForFeature(f)}
            stroke="var(--line)"
            stroke-width="0.5"
            class="geo-choropleth__feature"
            data-feature-key={f.properties?.[feature_key] ?? ""}
            onmouseenter={(e) => onFeatureMouseEnter(f, e)}
            onmousemove={onFeatureMouseMove}
            onmouseleave={onFeatureMouseLeave}
          />
        {/each}
      </svg>

      {#if hover_payload}
        <MapTooltip
          x={hover_x}
          y={hover_y}
          region_label={hover_payload.region_label}
          parent_label={hover_payload.parent_label}
          formatted_value={hover_payload.formatted_value}
          swatch_color={hover_payload.swatch_color}
        />
      {/if}
    {:else}
      <div class="geo-choropleth__loading">Loading map...</div>
    {/if}
  </div>

  <div class="geo-choropleth__legend">
    <ChoroplethLegend
      {scale}
      domain={resolved_domain}
      {title}
      value_tick={hover_payload?.value ?? null}
      value_tick_label={hover_payload
        ? `${hover_payload.region_label}: ${hover_payload.formatted_value}`
        : null}
      width={Math.min(width, 320)}
    />
  </div>

  <div class="geo-choropleth__source">
    <SourceLine
      owner={source_owner}
      vintage={source_vintage}
      url={source_url}
    />
  </div>
</div>

<style>
  .geo-choropleth {
    font-family: var(--font-sans);
    color: var(--ink);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .geo-choropleth__title {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }
  .geo-choropleth__canvas {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    overflow: hidden;
  }
  .geo-choropleth__svg {
    display: block;
  }
  .geo-choropleth__feature {
    cursor: pointer;
    transition: stroke-width 120ms ease-out;
  }
  .geo-choropleth__feature:hover {
    stroke-width: 1.5;
    stroke: var(--ink);
  }
  .geo-choropleth__loading,
  .geo-choropleth__error {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--ink-muted);
    font-size: 12px;
    padding: 24px;
    text-align: center;
  }
  .geo-choropleth__error {
    color: var(--neg);
  }
  .geo-choropleth__legend {
    margin-top: 4px;
  }
</style>
