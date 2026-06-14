<script module lang="ts">
  /**
   * PR-12 of TODO/20260613-party-deferred-followups-plan.md section 14.
   *
   * PartyStrongholdMap: a thin d3-geo SVG choropleth purpose-built for
   * the per-party page LS stronghold visualization. Renders the
   * delim=2024 PC topojson coloured by win-count bucket; PCs absent
   * from the party's stronghold mart fall through to the diagonal
   * hatch (no data).
   *
   * Why this is a sibling of `lib/charts/GeoChoropleth.svelte` rather
   * than a caller of it: the brand-colour-derived 6-bucket categorical
   * palette doesn't compose with `binnedSequential` (the F2b palette
   * is OkLCh sequential keyed on `Direction`; adding a `palette[]`
   * override prop ripples through ChoroplethLegend + color-scale.test
   * + IndicatorChoropleth callers — STOP-AND-SURFACE condition #1 in
   * the brief). The standalone implementation here is ~170 LOC and
   * keeps GeoChoropleth's API frozen.
   *
   * Doctrine ties:
   *   - Pure helpers (bucket / palette / mapper) live in the sibling
   *     `stronghold-choropleth-rows.ts`; this file is the wiring layer.
   *   - DATA_BASE-relative topojson_path matches the F4 island-render
   *     contract; topojson decoded via `topojson-client.feature`.
   *   - CLAUDE.md section 0: no aria/role on the SVG body. Visible
   *     affordances only (tooltip + cursor change).
   *   - State-cropping: when the party's home_state_codes set is
   *     non-empty AND <= 3 states, the projection fits ONLY the home
   *     state features (Citizen 3b override of Jony 2c). Otherwise
   *     full-India.
   *
   * Backend untouched per brief constraint. AC choropleth deferred
   * per brief STOP #3: the delim=2024 AC topojson does NOT exist on
   * disk (only delim=2008 ACs survive), AND the strongholds mart's
   * AC entity_ids are delim=1976 for the older states (DMK TN AC#2 =
   * HARBOUR in 1976 numbering, NOT Ponneri (SC) in delim=2008
   * numbering). A semantically-correct AC choropleth requires a
   * delim-aware AC renumbering crosswalk that lives upstream of this
   * PR.
   */
  export type {
    StrongholdBucket,
    StrongholdChoroplethRow,
  } from "./stronghold-choropleth-rows";

  export {
    BUCKET_ORDER,
    bucketFromWins,
    mapPcStrongholdsToChoroplethRows,
    paletteFromBrand,
    stateCodeFromPcEntityId,
    uniqueIdFromPcEntityId,
  } from "./stronghold-choropleth-rows";

  import type { Feature, Geometry, GeoJsonProperties } from "geojson";
  import type { StrongholdChoroplethRow } from "./stronghold-choropleth-rows";

  /** Pure: subset features to the party's home-state PCs when
   *  state-cropping. Returns the full feature list when home_states
   *  is empty (national party, no crop). The `state_property` is the
   *  feature.properties key that carries the LGD state code (e.g.
   *  "state_ut_code" for the delim=2024 PC topojson). */
  export function selectFitFeatures(
    features: ReadonlyArray<Feature<Geometry, GeoJsonProperties>>,
    home_states: ReadonlySet<string>,
    state_property: string,
  ): Feature<Geometry, GeoJsonProperties>[] {
    if (home_states.size === 0) return [...features];
    if (home_states.size > 3) return [...features];
    return features.filter((f) => {
      const code = f.properties?.[state_property];
      return typeof code === "string" && home_states.has(code);
    });
  }

  /** Pure: build the entity_key -> StrongholdChoroplethRow lookup the
   *  renderer consumes. Duplicates are silently overwritten (the
   *  mart is keyed on entity_id so duplicates indicate a corrupt
   *  upstream; the renderer takes the last). */
  export function rowsByEntityKey(
    rows: ReadonlyArray<StrongholdChoroplethRow>,
  ): Map<string, StrongholdChoroplethRow> {
    const out = new Map<string, StrongholdChoroplethRow>();
    for (const r of rows) {
      out.set(r.entity_key, r);
    }
    return out;
  }
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
  import type { FeatureCollection } from "geojson";
  // Feature / Geometry / GeoJsonProperties / StrongholdChoroplethRow
  // come from the <script module> block above (declared+imported there
  // so the helpers can carry their types). Svelte concatenates the two
  // scripts so re-importing here would conflict.

  import { DATA_BASE } from "../paths";
  import { paletteFromBrand } from "./stronghold-choropleth-rows";

  interface Props {
    /** DATA_BASE-relative topojson path (e.g.
     *  "/boundaries/electoral/delim=2024/pc/all.topojson"). */
    topojson_path: string;
    /** feature.properties key for the join (e.g. "unique_id"). */
    feature_key: string;
    /** feature.properties key carrying the LGD state code (e.g.
     *  "state_ut_code" for delim=2024 PC). Used for state-cropping. */
    state_property: string;
    /** Choropleth rows from `mapPcStrongholdsToChoroplethRows`. */
    rows: readonly StrongholdChoroplethRow[];
    /** Party brand_colour hex (e.g. "#FA2223" for DMK). Null falls
     *  through to the slate-500 grey ramp. */
    brand_colour: string | null;
    /** Home-state ECI codes from `homeStateEciCodes(meta.home_state_codes)`.
     *  Empty set = full-India crop. Size <= 3 triggers state-crop. */
    home_states: ReadonlySet<string>;
    /** Chart title (rendered above the SVG). */
    title: string;
    /** One-line caption (rendered below the SVG; Jony 2i secondary). */
    caption?: string | null;
    /** SVG width in px. Caller controls layout. */
    width?: number;
    /** SVG height in px. */
    height?: number;
    /** Test ID hook for the wrapper div. */
    data_testid?: string;
    /** Test ID hook for each polygon (default "pc-stronghold"). */
    polygon_testid?: string;
    /** Extra Tailwind classes on the wrapper div. */
    extra_class?: string;
  }

  const {
    topojson_path,
    feature_key,
    state_property,
    rows,
    brand_colour,
    home_states,
    title,
    caption = null,
    width = 320,
    height = 360,
    data_testid = "party-stronghold-map",
    polygon_testid = "pc-stronghold",
    extra_class = "",
  }: Props = $props();

  let collection = $state<FeatureCollection<Geometry, GeoJsonProperties> | null>(
    null,
  );
  let load_error = $state<string | null>(null);

  // Hover state
  let hover_entity_key = $state<string | null>(null);
  let hover_x = $state<number>(0);
  let hover_y = $state<number>(0);

  // Load the topojson once on mount.
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
          topo.objects[objectKeys[0]!] as GeometryCollection,
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

  // Map rows by entity_key for O(1) join.
  const row_by_key = $derived(rowsByEntityKey(rows));

  // Derive the 6-bucket palette from brand_colour.
  const palette = $derived(paletteFromBrand(brand_colour));

  // Build the d3-geo projection + path once the collection is loaded.
  // State-cropping: fit to home-state features when applicable, but
  // render every feature so the surrounding India outline still
  // surfaces (faint stroke) for geographic context.
  const projection_path = $derived.by(() => {
    if (!collection) return null;
    const fit_features = selectFitFeatures(
      collection.features,
      home_states,
      state_property,
    );
    const fit_collection: FeatureCollection<Geometry, GeoJsonProperties> = {
      type: "FeatureCollection",
      features: fit_features,
    };
    const projection: GeoProjection = geoMercator().fitSize(
      [width, height],
      fit_collection as GeoPermissibleObjects,
    );
    const path = geoPath(projection);
    return { projection, path };
  });

  /** Resolve the visible features list. When state-cropping, render
   *  ONLY the cropped subset so the citizen sees the home state in
   *  focus without ghost outlines of the rest of India. When not
   *  cropping, render all features. */
  const visible_features = $derived.by(() => {
    if (!collection) return [];
    return selectFitFeatures(collection.features, home_states, state_property);
  });

  function fillForFeature(
    f: Feature<Geometry, GeoJsonProperties>,
  ): string {
    const key = f.properties?.[feature_key];
    if (key == null) return "url(#party-stronghold-hatch)";
    const row = row_by_key.get(String(key));
    if (!row) return "url(#party-stronghold-hatch)";
    const color = palette[row.bucket];
    // Bucket "absent" is sentinel-white in the palette; substitute
    // hatch at render time so the citizen never sees an unmapped
    // bucket as plain white.
    if (row.bucket === "absent") return "url(#party-stronghold-hatch)";
    return color;
  }

  function bucketForFeature(
    f: Feature<Geometry, GeoJsonProperties>,
  ): string {
    const key = f.properties?.[feature_key];
    if (key == null) return "absent";
    const row = row_by_key.get(String(key));
    if (!row) return "absent";
    return row.bucket;
  }

  function onFeatureMouseEnter(
    f: Feature<Geometry, GeoJsonProperties>,
    e: MouseEvent,
  ): void {
    const key = f.properties?.[feature_key];
    hover_entity_key = key == null ? null : String(key);
    hover_x = e.offsetX + 10;
    hover_y = e.offsetY + 10;
  }

  function onFeatureMouseMove(e: MouseEvent): void {
    hover_x = e.offsetX + 10;
    hover_y = e.offsetY + 10;
  }

  function onFeatureMouseLeave(): void {
    hover_entity_key = null;
  }

  // Tooltip payload: the hovered row + its derived swatch / label.
  const hover_payload = $derived.by(() => {
    if (hover_entity_key == null) return null;
    const row = row_by_key.get(hover_entity_key);
    if (!row) return null;
    return {
      region_label: row.constituency_name || hover_entity_key,
      state_label: row.state,
      wins: row.wins,
      contested: row.contested,
      swatch: palette[row.bucket],
    };
  });
</script>

<div
  class="party-stronghold-map {extra_class}"
  data-component="party-stronghold-map"
  data-testid={data_testid}
  style="width: 100%; max-width: {width}px;"
>
  <div class="party-stronghold-map__title">{title}</div>

  <div
    class="party-stronghold-map__canvas"
    style="position: relative; width: 100%; aspect-ratio: {width} / {height};"
  >
    {#if load_error}
      <div class="party-stronghold-map__error" data-testid="party-stronghold-map-error">
        {load_error}
      </div>
    {:else if collection && projection_path}
      <svg
        class="party-stronghold-map__svg"
        width="100%"
        height="100%"
        viewBox="0 0 {width} {height}"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <!-- Diagonal-stripe hatch for absent PCs (party never
               contested OR not in top-10 lifetime strongholds).
               Mirrors the GeoChoropleth.geo-choropleth-hatch
               pattern so the no-data idiom is uniform across
               the chart family. -->
          <pattern
            id="party-stronghold-hatch"
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="#ffffff" />
            <rect width="2" height="6" fill="#d8d8d8" />
          </pattern>
        </defs>
        {#each visible_features as f (f.properties?.[feature_key] ?? Math.random())}
          {@const bucket = bucketForFeature(f)}
          {@const uid = f.properties?.[feature_key] ?? ""}
          <path
            d={projection_path.path(f) ?? ""}
            fill={fillForFeature(f)}
            stroke="#475569"
            stroke-width="0.4"
            vector-effect="non-scaling-stroke"
            class="party-stronghold-map__feature"
            data-testid={polygon_testid}
            data-bucket={bucket}
            data-unit-id={String(uid)}
            onmouseenter={(e) => onFeatureMouseEnter(f, e)}
            onmousemove={onFeatureMouseMove}
            onmouseleave={onFeatureMouseLeave}
          />
        {/each}
      </svg>

      {#if hover_payload}
        <div
          class="party-stronghold-map__tooltip"
          style="left: {hover_x}px; top: {hover_y}px;"
          data-testid="party-stronghold-map-tooltip"
        >
          <div class="party-stronghold-map__tooltip-header">
            <span
              class="party-stronghold-map__tooltip-swatch"
              style="background: {hover_payload.swatch};"
            ></span>
            <span class="party-stronghold-map__tooltip-region">
              {hover_payload.region_label}
            </span>
          </div>
          {#if hover_payload.state_label}
            <div class="party-stronghold-map__tooltip-parent">
              {hover_payload.state_label}
            </div>
          {/if}
          <div class="party-stronghold-map__tooltip-value">
            Won {hover_payload.wins} of {hover_payload.contested} contests
          </div>
        </div>
      {/if}
    {:else}
      <div class="party-stronghold-map__loading">Loading map...</div>
    {/if}
  </div>

  {#if caption}
    <div
      class="party-stronghold-map__caption"
      data-testid="party-stronghold-map-caption"
    >
      {caption}
    </div>
  {/if}
</div>

<style>
  .party-stronghold-map {
    font-family: var(--font-sans);
    color: var(--ink);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .party-stronghold-map__title {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink);
  }
  .party-stronghold-map__canvas {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--r-md);
    overflow: hidden;
  }
  .party-stronghold-map__svg {
    display: block;
  }
  .party-stronghold-map__feature {
    cursor: pointer;
    transition: stroke-width 120ms ease-out;
  }
  .party-stronghold-map__feature:hover {
    stroke-width: 1.2;
    stroke: var(--ink);
  }
  .party-stronghold-map__loading,
  .party-stronghold-map__error {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--ink-muted);
    font-size: 12px;
    padding: 24px;
    text-align: center;
  }
  .party-stronghold-map__error {
    color: var(--neg);
  }
  .party-stronghold-map__tooltip {
    position: absolute;
    pointer-events: none;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid var(--line);
    border-radius: var(--r-sm);
    padding: 6px 8px;
    font-size: 12px;
    color: var(--ink);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
    max-width: 220px;
    z-index: 10;
  }
  .party-stronghold-map__tooltip-header {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
  }
  .party-stronghold-map__tooltip-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    border: 1px solid var(--line);
  }
  .party-stronghold-map__tooltip-parent {
    color: var(--ink-muted);
    font-size: 11px;
    margin-top: 1px;
  }
  .party-stronghold-map__tooltip-value {
    margin-top: 4px;
  }
  .party-stronghold-map__caption {
    font-size: 11px;
    color: rgb(148 163 184); /* slate-400, mirrors PR-W4c degraded-UX pattern */
    line-height: 1.4;
  }
</style>
