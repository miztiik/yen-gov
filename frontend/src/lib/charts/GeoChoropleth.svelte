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
    geoCentroid,
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
  import { fetchGeometryJson } from "./geometry-cache";
  import { type Direction } from "../indicators";
  import {
    binnedSequential,
    sqrtAreaScale,
    type BinnedSequentialScale,
  } from "./color-scale";
  import ChoroplethLegend from "./ChoroplethLegend.svelte";
  import MapTooltip from "./MapTooltip.svelte";
  import SourceLine from "./SourceLine.svelte";
  import MapFrameSkeleton from "../MapFrameSkeleton.svelte";
  import {
    deriveDomain,
    rowsByFeatureKey,
    type GeoChoroplethRow,
  } from "./geo-choropleth-helpers";

  /** Renderer mode discriminator (F2b.7 extension to F2b.3).
   *   - "fill" (default): chloropleth - polygons filled by colour scale.
   *   - "symbol":         icon-cartogram - one centroid-positioned glyph
   *                       per region, area-sized via sqrt(value). Base
   *                       outline still renders behind glyphs (faint)
   *                       so the citizen sees geography context.
   */
  export type GeoChoroplethMode = "fill" | "symbol";

  interface Props {
    /** DATA_BASE-relative topojson path, e.g.
     *  `/boundaries/in/country/all.topojson` (the sole surviving topojson
     *  after the 2026-06-16 map-geometry rip). */
    topojson_path: string;
    /** Named topojson object to decode. The combined country file carries
     *  TWO objects (`states` + `districts`); pass e.g. `"states"` so the
     *  right layer is selected. When omitted, the first object name is
     *  decoded (single-object case). */
    object_name?: string;
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
    /** Optional citizen-readable unit suffix appended to tooltip
     *  values + shown above the legend (e.g. "%", "GW", "INR crore").
     *  When absent, values render bare. The publisher's `short_unit`
     *  is preferred (e.g. "%" over "percent") for tooltip density.
     *  IndicatorMeta carries both `unit` and `short_unit`; the caller
     *  picks. */
    unit_label?: string;
    /** Renderer mode. Default "fill" preserves F2b.3 byte-identical
     *  behaviour for callers that don't supply the prop. */
    mode?: GeoChoroplethMode;
    /** Symbol mode: minimum glyph radius in px. Default 6. */
    symbol_min_radius_px?: number;
    /** Symbol mode: maximum glyph radius in px. Default 36. */
    symbol_max_radius_px?: number;
  }

  const {
    topojson_path,
    object_name,
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
    width = 800,
    height = 560,
    unit_label,
    mode = "fill",
    symbol_min_radius_px = 6,
    symbol_max_radius_px = 36,
  }: Props = $props();

  let collection = $state<FeatureCollection<Geometry, GeoJsonProperties> | null>(null);
  let load_error = $state<string | null>(null);

  // Hover state - drives both the C3 tooltip + the C2 legend
  // value-tick. The hovered feature's value is the value-tick.
  let hover_feature_key = $state<string | number | null>(null);
  let hover_x = $state<number>(0);
  let hover_y = $state<number>(0);

  // Citizen-readable value formatter. d3-format SI by default; appends
  // the unit suffix when supplied so tooltips read e.g. "27.4 %" rather
  // than a bare "27.4" that requires the citizen to infer the unit
  // from the title.
  const fmt = $derived.by(() => {
    const suffix = unit_label ? " " + unit_label : "";
    if (format_value) {
      return (v: number): string => format_value(v) + suffix;
    }
    // Inline closure over d3-format string for callers that don't
    // supply their own formatter.
    return (v: number): string => {
      if (!Number.isFinite(v)) return "-";
      if (Math.abs(v) >= 1000) {
        return v.toLocaleString(undefined, { maximumFractionDigits: 1 }) + suffix;
      }
      return v.toLocaleString(undefined, { maximumFractionDigits: 2 }) + suffix;
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
        // Row 3b: fetchGeometryJson caches the fetched + parsed JSON per
        // URL (throws on a non-OK status, caught below) so revisiting this
        // choropleth does not re-download the geometry.
        const topo = (await fetchGeometryJson(url)) as Topology;
        const objectKeys = Object.keys(topo.objects ?? {});
        if (objectKeys.length === 0) {
          load_error = `topojson has no objects: ${url}`;
          return;
        }
        // Decode the caller-named object when present (the combined
        // country file carries TWO objects - `states` + `districts` - so
        // objectKeys[0] is ambiguous); else decode the first object name.
        const objectKey =
          object_name && topo.objects[object_name] ? object_name : objectKeys[0];
        const fc = topojsonFeature(
          topo,
          topo.objects[objectKey] as GeometryCollection,
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

  // Citizen-honest default tick format. d3-format's SI notation (".2s")
  // produces nonsense like `−500m` (milli-prefix = millionths) for small
  // percent values like -0.0005 - which the inflation choropleth's domain
  // edge surfaced on Home in PR #940. Rules of thumb:
  //   * Caller-supplied `format_tick` always wins (escape hatch).
  //   * Indicators carrying `%` as unit: fixed-precision; never SI.
  //   * Domain max < 1000: fixed-precision; SI would only abbreviate above 1k.
  //   * Otherwise: SI (`.2s`) - the right choice for INR-crore / MW / etc.
  const effective_format_tick = $derived.by(() => {
    if (format_tick !== ".2s") return format_tick;
    const is_percent = unit_label === "%" || unit_label === "percent";
    if (is_percent) return ".2f";
    const abs_max = Math.max(
      Math.abs(resolved_domain.min),
      Math.abs(resolved_domain.max),
    );
    if (!Number.isFinite(abs_max)) return ".2s";
    if (abs_max < 1000) return ".2f";
    return ".2s";
  });

  // Build the binned color scale. Drives both fills + the legend.
  const scale: BinnedSequentialScale = $derived(
    binnedSequential({
      domain: resolved_domain,
      bins,
      direction,
      format_tick: effective_format_tick,
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

  // Symbol-mode sqrt-area scale (F2b.7). Sized by sqrt(value) per
  // parent §15.1 HONESTY rule (a 4x value reads as 2x glyph radius,
  // not 4x). Built on F2b.2's sqrtAreaScale helper.
  const symbol_size_scale = $derived.by(() => {
    return sqrtAreaScale({
      max_value: Math.max(0, resolved_domain.max),
      range_min_px: symbol_min_radius_px,
      range_max_px: symbol_max_radius_px,
    });
  });

  // Symbol-mode centroids: project each feature's geoCentroid via
  // the same projection the fill mode uses, so glyph positions stay
  // exactly on top of the feature they represent. Returns null until
  // the topojson loads (the renderer falls through to "Loading...").
  const symbol_features = $derived.by(() => {
    if (mode !== "symbol" || !collection || !projection_path) return null;
    const items: Array<{
      key: string;
      cx: number;
      cy: number;
      r: number;
      fill: string;
      raw_value: number | null;
    }> = [];
    for (const f of collection.features) {
      const key = f.properties?.[feature_key];
      if (key == null) continue;
      const value = value_by_key.get(String(key)) ?? null;
      // Project the geoCentroid via the SAME projection so glyphs
      // sit exactly on top of the polygon they represent.
      const [lng, lat] = geoCentroid(f);
      if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue;
      const projected = projection_path.projection([lng, lat]);
      if (!projected || !Number.isFinite(projected[0]) || !Number.isFinite(projected[1])) {
        continue;
      }
      items.push({
        key: String(key),
        cx: projected[0],
        cy: projected[1],
        r: symbol_size_scale(value),
        fill: value == null ? "#cbd5e1" : scale.colorForValue(value),
        raw_value: value,
      });
    }
    return items;
  });

  // Resolve fill for a feature: lookup the row by feature_key, then
  // colorForValue. Null/missing rows fall through to the no-data
  // dot-grid (via a special return value), rendered as a fill
  // referencing the SVG <pattern> defined inside this component.
  const NO_DATA_FILL = "url(#geo-choropleth-nodata)";
  function fillForFeature(f: Feature<Geometry, GeoJsonProperties>): string {
    const key = f.properties?.[feature_key];
    if (key == null) return NO_DATA_FILL;
    const value = value_by_key.get(String(key));
    if (value == null) return NO_DATA_FILL;
    return scale.colorForValue(value);
  }

  // True when at least one rendered feature has no value. Drives the
  // "No data" legend chip so a fully-covered indicator stays chip-free
  // and the chip only appears when the dot-grid fill is actually on
  // screen.
  const has_no_data = $derived.by<boolean>(() => {
    if (!collection) return false;
    for (const f of collection.features) {
      const key = f.properties?.[feature_key];
      if (key == null) return true;
      if (value_by_key.get(String(key)) == null) return true;
    }
    return false;
  });

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
  data-mode={mode}
  style="width: 100%; max-width: {width}px;"
>
  <div class="geo-choropleth__title">{title}</div>
  {#if unit_label}
    <div class="geo-choropleth__unit" data-slot="unit">{unit_label}</div>
  {/if}

  <div
    class="geo-choropleth__canvas"
    style="position: relative; width: 100%; aspect-ratio: {width} / {height};"
  >
    {#if load_error}
      <div class="geo-choropleth__error">{load_error}</div>
    {:else if collection && projection_path}
      <svg
        class="geo-choropleth__svg"
        width="100%"
        height="100%"
        viewBox="0 0 {width} {height}"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <!-- No-data fill: a subtle gray dot-grid (Jony 2026-06-16).
               Replaces the prior diagonal-stripe hatch, which read as
               "broken / hazard". A faint dot-grid reads as
               "intentionally empty" and does not compete with the data
               fills. Paired with the "No data" legend chip below so the
               idiom is self-explanatory without being obtrusive. -->
          <pattern
            id="geo-choropleth-nodata"
            width="8"
            height="8"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="8" height="8" fill="#f8fafc" />
            <circle cx="4" cy="4" r="0.9" fill="#cbd5e1" fill-opacity="0.5" />
          </pattern>
        </defs>
        {#if mode === "fill"}
          {#each collection.features as f}
            <path
              d={projection_path.path(f) ?? ""}
              fill={fillForFeature(f)}
              stroke="#475569"
              stroke-width="0.6"
              vector-effect="non-scaling-stroke"
              class="geo-choropleth__feature"
              data-feature-key={f.properties?.[feature_key] ?? ""}
              onmouseenter={(e) => onFeatureMouseEnter(f, e)}
              onmousemove={onFeatureMouseMove}
              onmouseleave={onFeatureMouseLeave}
            />
          {/each}
        {:else}
          <!-- Symbol mode (F2b.7): faint base outline so the citizen
               sees geography context, then one centroid-positioned
               glyph per region sized by sqrt(value). Per parent §15.1
               "Missing glyph falls back to a plain sized dot" - this
               first symbol-mode implementation uses a plain <circle>
               for every region (the future hook for per-region SVG
               icons reads from the closed party-symbols allowlist;
               same fallback shape). -->
          {#each collection.features as f}
            <path
              d={projection_path.path(f) ?? ""}
              fill="var(--surface-sunken, #f1f5f9)"
              stroke="var(--line)"
              stroke-width="0.5"
              class="geo-choropleth__base-outline"
              pointer-events="none"
            />
          {/each}
          {#if symbol_features}
            {#each symbol_features as s (s.key)}
              <circle
                cx={s.cx}
                cy={s.cy}
                r={s.r}
                fill={s.fill}
                stroke="var(--ink)"
                stroke-width="0.75"
                fill-opacity={s.raw_value == null ? 0.4 : 0.85}
                class="geo-choropleth__symbol"
                data-feature-key={s.key}
                onmouseenter={(e) => {
                  hover_feature_key = s.key;
                  hover_x = e.offsetX + 10;
                  hover_y = e.offsetY + 10;
                }}
                onmousemove={onFeatureMouseMove}
                onmouseleave={onFeatureMouseLeave}
              />
            {/each}
          {/if}
        {/if}
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
      <div class="geo-choropleth__loading-frame">
        <MapFrameSkeleton height="100%" />
      </div>
    {/if}
  </div>

  <div class="geo-choropleth__legend">
    <ChoroplethLegend
      {scale}
      domain={resolved_domain}
      {title}
      value_tick={hover_payload?.value ?? null}
      width={Math.min(width, 320)}
    />
    {#if mode === "fill" && has_no_data}
      <div class="geo-choropleth__nodata-key" data-slot="nodata-key">
        <span class="geo-choropleth__nodata-swatch" aria-hidden="true"></span>
        No data
      </div>
    {/if}
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
  .geo-choropleth__unit {
    font-size: 11px;
    color: var(--ink-muted);
    margin-top: -8px;
    margin-bottom: 4px;
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
    stroke-width: 1.8;
    stroke: var(--ink);
  }
  .geo-choropleth__base-outline {
    /* Symbol mode: faint outline behind glyphs gives geography
       context without competing with the data layer. */
    opacity: 0.4;
  }
  .geo-choropleth__symbol {
    cursor: pointer;
    transition: stroke-width 120ms ease-out;
  }
  .geo-choropleth__symbol:hover {
    stroke-width: 1.5;
  }
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
  .geo-choropleth__loading-frame {
    height: 100%;
  }
  .geo-choropleth__error {
    color: var(--neg);
  }
  .geo-choropleth__legend {
    margin-top: 4px;
  }
  .geo-choropleth__nodata-key {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    font-size: 11px;
    color: var(--ink-muted);
  }
  .geo-choropleth__nodata-swatch {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid var(--line);
    background-color: #f8fafc;
    background-image: radial-gradient(rgba(203, 213, 225, 0.5) 0.9px, transparent 1.1px);
    background-size: 4px 4px;
  }
</style>
