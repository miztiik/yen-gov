<script lang="ts">
  /**
   * StatePcMapD3 - the per-state Parliamentary Constituency choropleth
   * for a state event view (`/<state>/elections/general-2024`).
   * Closes the PC-choropleth deferral on PR #954: replaces the
   * "Constituency map being prepared" placeholder card with a real
   * choropleth filtered from the national PC topojson by
   * `state_ut_code === state_code`.
   *
   * Pattern mirrors `IndiaPcMapD3` (national counterpart):
   *   - Loads `boundaries/electoral/delim=2024/pc/all.topojson` ONCE
   *     via `topojsonFeature`, then filters features by
   *     `properties.state_ut_code === state_code`.
   *   - JOIN on `properties.unique_id` (e.g. "S22_1"). Callers
   *     pre-compute `unique_id = "<state_code>_<eci_no>"` on each
   *     `PcWinnerRow` so the lookup is O(1) per feature.
   *   - Per-PC fill from the 3-tier palette + cellTreatment (margin
   *     mode / party_won), with PR-B8-style `fillsOverride` /
   *     `opacitiesOverride` precedence for the party-filter rail.
   *   - Hover tooltip via the canonical `renderTooltipCard`. Click
   *     navigates to the per-PC leaf:
   *     `/<state>/elections/<event>/<pc-name-slug>` (matches the
   *     bare-slug grammar of the constituency table in StateElection).
   *   - `fitWidth` projects to the FILTERED feature set so each state's
   *     PCs fill the responsive width cleanly.
   *
   * No "Equal-seats" arm: per-state PC tile layouts have NOT been
   * authored. The plan-doc surfaces this as an inline note inside
   * StateElection.svelte ("Equal-seats view available on the national
   * 2024 surface.") - this component does NOT render that note.
   *
   * CLAUDE.md §0: no aria/role beyond native; visible affordances only.
   */

  import { onMount } from "svelte";
  import {
    geoMercator,
    geoPath,
    type GeoPermissibleObjects,
    type GeoProjection,
  } from "d3-geo";
  import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
  import { select } from "d3-selection";
  import type {
    Feature,
    FeatureCollection,
    GeoJsonProperties,
    Geometry,
  } from "geojson";

  import { DATA_BASE } from "../paths";
  import { fetchGeometryJson } from "./geometry-cache";
  import { INDIA_PC, INDIA_PC_BY_NAME, type BoundaryEntry } from "../boundaries/sources";
  import { renderTooltipCard } from "../boundaries/tooltip-card";
  import { symbolAssetUrl } from "../boundaries/symbol-asset";
  import {
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../colors/resolver";
  import { navigate } from "../url";
  import { slugify } from "../slug";
  import {
    DEFAULT_HIGHLIGHT_STATE,
    NEUTRAL_HEX_FALLBACK,
    type HighlightMode,
    type MinMargin,
  } from "./map-highlight-utils";
  import {
    buildPcCellPaint,
    type PcCellRow,
    type PcCellPaint,
  } from "./india-pc-map-helpers";
  import { rewindCollectionForD3 } from "./geo-rewind";
  import {
    computeCoverage,
    delimVintageFromPath,
    type MapCoverageEmit,
  } from "./map-coverage";

  /** Per-PC winner row, pre-shaped by the route for the join. Mirrors
   *  the IndiaPcMapD3 shape verbatim so the route can reuse the same
   *  builder for both surfaces. */
  export interface PcWinnerRow {
    unique_id: string;
    state_code: string;
    pc_eci_no: number;
    pc_name: string;
    party_id: string;
    party_short: string;
    party_eci_code: string | null;
    brand_colour_hex: string | null;
    brand_colour_confidence: "high" | "medium" | "low" | null;
    margin_pct: number;
    winner_candidate_name: string | null;
    symbol_asset_path: string | null;
  }

  interface Props {
    /** ECI state code, e.g. "S07". Filters the national PC topojson. */
    state: string;
    /** LGD state slug, e.g. "haryana". Used to build the per-PC leaf
     *  URL (`/<state_slug>/elections/<event>/<pc-name-slug>`) that
     *  matches the bare-slug grammar StateElection's constituency
     *  table uses. */
    state_slug: string;
    /** Per-PC winners + margin for this state. `null` = loading. */
    rows: PcWinnerRow[] | null;
    /** Canonical event id, threaded onto per-PC leaf links. */
    event?: string | null;
    /** Deprecated: no longer drives sizing (the map is responsive). Kept
     *  for backward compatibility with existing call sites. */
    height?: string;
    /** Row F party-filter overrides keyed by unique_id. */
    fillsOverride?: Record<string, string>;
    opacitiesOverride?: Record<string, number>;
    /** E4 shared-axis props (default to legacy margin-ramp behaviour). */
    highlight_mode?: HighlightMode;
    selected_party_id?: string | null;
    min_margin?: MinMargin;
    /** PC boundary layer to load + join against. Defaults to `INDIA_PC`
     *  (numeric `unique_id`). The route passes `INDIA_PC_BY_NAME` for LS
     *  2019/2014/2009 events, which joins the SAME 2024 PC geometry by
     *  name-slug (`pc_slug_uid`) instead of numeric ls_seat_code.
     *  Component stays grain-agnostic - it reads `boundary.join_property`
     *  + `feature.properties[that]` and matches against `row.unique_id`
     *  regardless of the shape. */
    boundary?: BoundaryEntry;
    /** Lifts the render-time coverage tuple to the parent so the caption
     *  renders below the per-state party legend (not inside the map card). */
    oncoverage?: (e: MapCoverageEmit) => void;
  }
  let {
    state: state_code,
    state_slug,
    rows: input_rows,
    event = null,
    fillsOverride,
    opacitiesOverride,
    highlight_mode = DEFAULT_HIGHLIGHT_STATE.mode,
    selected_party_id = DEFAULT_HIGHLIGHT_STATE.selected_party_id,
    min_margin = DEFAULT_HIGHLIGHT_STATE.min_margin,
    boundary = INDIA_PC,
    oncoverage,
  }: Props = $props();

  // Responsive fit: project to the measured container width (clamped to
  // MAX_MAP_W so a 4K viewport does not produce a giant hero); the SVG
  // height derives from the projected content bounds (no letterboxing).
  const MAX_MAP_W = 1200;
  let container_w = $state(0);
  const DEFAULT_FILL = "#e2e8f0"; // slate-200
  const JOIN_PROPERTY = boundary.join_property; // "unique_id"
  const STATE_FILTER_PROPERTY = "state_ut_code";
  // `boundary` ships `.geojson` as the canonical snapshot path. Post the
  // 2026-06-16 map-geometry rip the electoral PC layer ships geojson ONLY,
  // so fetch the geojson directly. Same fallback pattern as IndiaPcMapD3
  // for the optional `geojson_local_path` field.
  const GEOMETRY_PATH =
    boundary.geojson_local_path ??
    "boundaries/electoral/delim=2024/pc/all.geojson";

  // ---- Lookups -----------------------------------------------------
  const row_by_uid = $derived.by(() => {
    const m = new Map<string, PcWinnerRow>();
    for (const r of input_rows ?? []) m.set(r.unique_id, r);
    return m;
  });

  const party_colors = $derived.by(() => {
    const list = input_rows ?? [];
    const partyRowMap = new Map<string, PartyRowForResolver>();
    for (const r of list) {
      if (partyRowMap.has(r.party_id)) continue;
      partyRowMap.set(r.party_id, {
        party_id: r.party_id,
        brand_colour: r.brand_colour_hex
          ? {
              hex: r.brand_colour_hex,
              confidence: r.brand_colour_confidence ?? "medium",
            }
          : null,
      });
    }
    const palette = resolvePartyPalette(
      list.map((r) => r.party_id),
      partyRowMap,
    );
    const out = new Map<string, string>();
    for (const r of list) {
      const hex = palette.get(r.party_id)?.hex;
      if (hex) out.set(r.unique_id, hex);
    }
    return out;
  });

  let neutral_hex = $state<string>(NEUTRAL_HEX_FALLBACK);
  $effect(() => {
    if (typeof document === "undefined") return;
    if (typeof getComputedStyle === "undefined") return;
    try {
      const v = getComputedStyle(document.documentElement)
        .getPropertyValue("--party-neutral")
        .trim();
      neutral_hex = v || NEUTRAL_HEX_FALLBACK;
    } catch {
      neutral_hex = NEUTRAL_HEX_FALLBACK;
    }
  });

  // ---- Topojson load + per-state filter -----------------------------
  type Collection = FeatureCollection<Geometry, GeoJsonProperties>;

  let all_features = $state<readonly Feature<Geometry, GeoJsonProperties>[] | null>(
    null,
  );
  let load_error = $state<string | null>(null);

  onMount(() => {
    let cancelled = false;
    const url = `${DATA_BASE}/${GEOMETRY_PATH}`;
    (async () => {
      try {
        // Post map-geometry rip the PC layer ships a plain GeoJSON
        // FeatureCollection (no topojson decode step). It carries RFC 7946
        // (counter-clockwise-exterior) winding; d3-geo wants clockwise
        // exteriors, so rewind before projecting or every polygon paints
        // the whole viewBox (the map renders as one solid block).
        // Row 3b: fetchGeometryJson caches the fetched + parsed JSON per
        // URL (throws on a non-OK status, caught below) so revisiting this
        // map does not re-download the geometry.
        const fc = (await fetchGeometryJson(url)) as Collection;
        if (cancelled) return;
        if (fc?.type !== "FeatureCollection" || !Array.isArray(fc.features)) {
          load_error = `geojson is not a FeatureCollection: ${url}`;
          return;
        }
        all_features = rewindCollectionForD3(fc).features;
      } catch (err) {
        if (cancelled) return;
        load_error = String(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  });

  // Per-state feature filter: state_ut_code === state_code. Re-derives
  // when the route parameter changes (the parent navigates between
  // states without unmounting).
  const state_features = $derived<readonly Feature<Geometry, GeoJsonProperties>[]>(
    !all_features
      ? []
      : all_features.filter(
          (f) =>
            String(
              (f.properties as Record<string, unknown> | null)?.[
                STATE_FILTER_PROPERTY
              ] ?? "",
            ) === state_code,
        ),
  );

  const projection_path = $derived.by(() => {
    if (state_features.length === 0) return null;
    const safe_fc: Collection = {
      type: "FeatureCollection",
      features: state_features as Feature<Geometry, GeoJsonProperties>[],
    };
    const obj = safe_fc as GeoPermissibleObjects;
    const eff_w = Math.min(container_w || 640, MAX_MAP_W);
    let projection: GeoProjection;
    try {
      projection = geoMercator().fitWidth(eff_w, obj);
      // Re-translate so the projected extent starts at (0,0); fitWidth
      // anchors x near 0 but can leave a top offset.
      const pre = geoPath(projection).bounds(obj);
      const [tx, ty] = projection.translate();
      projection.translate([tx - pre[0][0], ty - pre[0][1]]);
    } catch {
      projection = geoMercator()
        .center([82.5, 22.5])
        .scale(700)
        .translate([eff_w / 2, eff_w / 2]);
    }
    const path = geoPath(projection);
    let w = eff_w;
    let h = eff_w;
    try {
      const b = path.bounds(obj);
      w = Math.max(1, Math.ceil(b[1][0]));
      h = Math.max(1, Math.ceil(b[1][1]));
    } catch {
      // keep the eff_w x eff_w fallback box on a bounds failure
    }
    return { projection, path, w, h };
  });

  // ---- Per-PC paint ------------------------------------------------
  function featureUid(
    props: Record<string, unknown> | undefined,
  ): string | null {
    if (!props) return null;
    const raw = props[JOIN_PROPERTY];
    if (raw == null) return null;
    return String(raw);
  }

  // Wrapper aspect-ratio: the projected content w/h once the topojson
  // loads + filters, a neutral 640/480 default during the loading / empty
  // window so the placeholder reserves space (no layout shift on paint).
  const wrapper_aspect = $derived(
    projection_path ? `${projection_path.w}/${projection_path.h}` : "640/480",
  );

  // ---- Coverage caption (honesty layer) ----------------------------
  // matched = rendered PCs that bind a winner; total = rendered PCs. The
  // caption auto-hides when matched === total (full coverage). Vintage is
  // read from the geometry path's `delim=` marker, never hardcoded.
  const coverage = $derived(
    state_features.length === 0
      ? null
      : computeCoverage(
          state_features.map((f) => featureUid(f.properties ?? undefined)),
          (k) => row_by_uid.has(String(k)),
        ),
  );
  const geometry_year = $derived(delimVintageFromPath(GEOMETRY_PATH));
  // Old-election signal: the route swaps in the name-slug boundary
  // (INDIA_PC_BY_NAME) only for pre-2024 LS events; the numeric default
  // (INDIA_PC) means a current-vintage map, where the caption stays hidden.
  const on_old_geometry = $derived(boundary.id === INDIA_PC_BY_NAME.id);
  // Lift coverage to the parent (StateEventMap -> StateElection) so the
  // caption renders below the per-state party legend instead of inside the
  // map card.
  $effect(() => {
    oncoverage?.({
      coverage,
      geometryYear: geometry_year,
      onOldGeometry: on_old_geometry,
    });
    // Clear on unmount (e.g. the parent switches to the hex / equal-seats
    // arm, or navigates to a PC event with no on-disk geometry) so the
    // parent never shows a stale caption for a map that is no longer drawn.
    return () =>
      oncoverage?.({
        coverage: null,
        geometryYear: null,
        onOldGeometry: false,
      });
  });

  const cell_paint = $derived.by<Map<string, PcCellPaint>>(() => {
    const cell_rows: PcCellRow[] = [];
    for (const r of input_rows ?? []) {
      cell_rows.push({
        unique_id: r.unique_id,
        party_id: r.party_id,
        margin_pct: r.margin_pct,
        winner_party_hex: party_colors.get(r.unique_id) ?? "#94a3b8",
      });
    }
    return buildPcCellPaint(
      cell_rows,
      {
        mode: highlight_mode,
        selected_party_id,
        min_margin,
        neutral_hex,
      },
      fillsOverride,
      opacitiesOverride,
    );
  });

  interface Paint {
    fill: string;
    opacity: number;
  }
  function paintForUid(uid: string | null): Paint {
    if (uid == null) return { fill: DEFAULT_FILL, opacity: 1 };
    const t = cell_paint.get(uid);
    if (!t) return { fill: DEFAULT_FILL, opacity: 1 };
    return t;
  }

  function safePath(
    f: Feature<Geometry, GeoJsonProperties>,
    geo_path: ReturnType<typeof geoPath>,
  ): string {
    try {
      return geo_path(f) ?? "";
    } catch {
      return "";
    }
  }

  function tooltipForUid(
    props: Record<string, unknown> | undefined,
    uid: string | null,
  ): string | null {
    if (!props || uid == null) return null;
    const r = row_by_uid.get(uid);
    const ls_seat_name = (props.ls_seat_name as string | null) ?? null;
    if (!r) {
      if (!ls_seat_name) return null;
      return renderTooltipCard({
        title: ls_seat_name,
        partyShort: "Pending",
        partyColorHex: null,
      });
    }
    return renderTooltipCard({
      title: `${r.pc_eci_no}. ${r.pc_name}`,
      candidateName: r.winner_candidate_name,
      partyShort: r.party_short,
      partyColorHex: party_colors.get(r.unique_id) ?? null,
      symbolAsset: symbolAssetUrl(r.symbol_asset_path),
      marginPct: r.margin_pct,
    });
  }

  function onSelectUid(uid: string | null): void {
    if (uid == null) return;
    const r = row_by_uid.get(uid);
    if (!r || !event) return;
    // Navigates to the bare-slug constituency leaf: same shape the
    // constituency table on StateElection emits. PR-W3b URL contract.
    const pc_slug = slugify(r.pc_name);
    navigate(`/${state_slug}/elections/${encodeURIComponent(event)}/${pc_slug}`);
  }

  // ---- Hover overlay -----------------------------------------------
  let hover_html = $state<string | null>(null);
  let hover_x = $state(0);
  let hover_y = $state(0);
  function onFeatureEnter(
    e: MouseEvent,
    props: Record<string, unknown> | undefined,
    uid: string | null,
  ): void {
    hover_html = tooltipForUid(props, uid);
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onFeatureMove(e: MouseEvent): void {
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onFeatureLeave(): void {
    hover_html = null;
  }

  // ---- d3-zoom wiring ----------------------------------------------
  let svg_el = $state<SVGSVGElement | null>(null);
  let zoom_group_el = $state<SVGGElement | null>(null);
  let zoom_behavior: ZoomBehavior<SVGSVGElement, unknown> | null = null;
  $effect(() => {
    if (!svg_el || !zoom_group_el) return;
    const sel = select(svg_el);
    const z = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .on("zoom", (e) => {
        if (zoom_group_el) {
          zoom_group_el.setAttribute("transform", e.transform.toString());
        }
      });
    zoom_behavior = z;
    sel.call(z);
    return () => {
      sel.on(".zoom", null);
      zoom_behavior = null;
    };
  });
  // Reset the zoom transform when the responsive width changes so a stale
  // transform from the previous width does not cause a visual jump.
  $effect(() => {
    void container_w;
    if (svg_el && zoom_behavior) {
      select(svg_el).call(zoom_behavior.transform, zoomIdentity);
    }
  });
  function zoomInButton(): void {
    if (!svg_el || !zoom_behavior) return;
    select(svg_el).call(zoom_behavior.scaleBy, 1.5);
  }
  function zoomOutButton(): void {
    if (!svg_el || !zoom_behavior) return;
    select(svg_el).call(zoom_behavior.scaleBy, 1 / 1.5);
  }
  function homeButton(): void {
    if (!svg_el || !zoom_behavior) return;
    select(svg_el).call(zoom_behavior.transform, zoomIdentity);
  }
</script>

<div
  bind:clientWidth={container_w}
  class="relative w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
  style="aspect-ratio:{wrapper_aspect};"
  data-component="state-pc-map-d3"
  data-testid="state-pc-map-d3"
  data-state={state_code}
>
  {#if load_error}
    <div
      class="absolute inset-x-2 bottom-2 p-2 text-xs bg-rose-50 border border-rose-200 rounded text-rose-900"
    >
      Map error: <code>{load_error}</code>
    </div>
  {:else if !all_features || !projection_path}
    <div
      class="absolute inset-0 flex items-center justify-center text-xs text-slate-500"
    >
      Loading map...
    </div>
  {:else if state_features.length === 0}
    <div
      class="absolute inset-0 flex items-center justify-center text-xs text-slate-500"
      data-testid="state-pc-map-d3-empty"
    >
      No Parliament constituencies on file for state <code>{state_code}</code>.
    </div>
  {:else}
    {@const pp = projection_path}
    <svg
      bind:this={svg_el}
      class="block w-full cursor-grab active:cursor-grabbing"
      viewBox="0 0 {pp.w} {pp.h}"
      width="100%"
      style="height:auto; aspect-ratio:{pp.w}/{pp.h};"
    >
      <g bind:this={zoom_group_el}>
        {#each state_features as f, i (i)}
          {@const uid = featureUid(f.properties ?? undefined)}
          {@const p = paintForUid(uid)}
          <path
            d={safePath(f, pp.path)}
            fill={p.fill}
            fill-opacity={p.opacity}
            stroke="#94a3b8"
            stroke-width="0.5"
            class="state-pc-map-d3__feature"
            data-pc-unique-id={uid ?? ""}
            onmouseenter={(e) =>
              onFeatureEnter(e, f.properties ?? undefined, uid)}
            onmousemove={onFeatureMove}
            onmouseleave={onFeatureLeave}
            onclick={() => onSelectUid(uid)}
          />
        {/each}
      </g>
    </svg>

    {#if hover_html}
      <div
        class="absolute pointer-events-none bg-white border border-slate-200 rounded shadow px-2 py-1 text-xs leading-tight max-w-xs"
        style="left: {hover_x}px; top: {hover_y}px;"
        data-testid="state-pc-map-d3-tooltip"
      >
        {@html hover_html}
      </div>
    {/if}

    <div class="absolute bottom-2 right-2 flex flex-col gap-1 z-10">
      <button
        type="button"
        aria-label="Zoom in"
        class="w-8 h-8 rounded-full bg-white border border-slate-300 text-slate-700 text-lg leading-none flex items-center justify-center shadow hover:bg-slate-100 active:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        onclick={zoomInButton}
      >+</button>
      <button
        type="button"
        aria-label="Zoom out"
        class="w-8 h-8 rounded-full bg-white border border-slate-300 text-slate-700 text-lg leading-none flex items-center justify-center shadow hover:bg-slate-100 active:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        onclick={zoomOutButton}
      >&minus;</button>
      <button
        type="button"
        aria-label="Reset zoom"
        class="w-8 h-8 rounded-full bg-white border border-slate-300 text-slate-700 text-xs leading-none flex items-center justify-center shadow hover:bg-slate-100 active:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        onclick={homeButton}
      >home</button>
    </div>
  {/if}
</div>
