<script lang="ts">
  /**
   * IndiaPcMapD3 - the d3-geo SVG choropleth that renders 543 / 545
   * Parliamentary Constituency polygons for one national Parliament
   * event (e.g. `general-2024`). Closes the PC-choropleth deferral
   * from PR #954; restores the "Constituencies" arm of the
   * "States | Constituencies | Equal seats" toggle deliberately
   * removed in PR-W3c.
   *
   * Pattern mirrors `StateAcMapD3` + `IndiaPartyMap`:
   *   - Loads `boundaries/electoral/delim=2024/pc/all.topojson` ONCE
   *     via `topojsonFeature` (545 features; 2 J&K-territory
   *     placeholders carry no winner and render in the default fill).
   *   - JOIN on `properties.unique_id` ("<state_ut_code>_<ls_seat_code>",
   *     e.g. "S07_8"). Callers pre-compute the same key on each
   *     `PcWinnerRow` from the winner's `(state_code, eci_no)` pair
   *     so the join is O(1) per feature.
   *   - Per-PC fill from the winning party id via the 3-tier palette
   *     resolver (`resolvePartyPalette` + `getPartyColor`); per-PC
   *     opacity via the shared `cellTreatment` fork (margin ramp /
   *     party_won 0-or-1 step).
   *   - Hover tooltip via the canonical `renderTooltipCard` (no
   *     per-renderer drift). Click navigates to
   *     `link.stateElection(state_code, event)` so the citizen lands
   *     on the per-state event page (drill via that page's
   *     constituency table to the per-PC leaf).
   *   - PR-B8-style `fillsOverride` / `opacitiesOverride` precedence
   *     path keyed by `unique_id` so the party-filter rail (Row F) can
   *     recede muted-party cells without bespoke logic inside the
   *     component.
   *   - E4 (parent plan section 25.5) `highlight_mode` /
   *     `selected_party_id` / `min_margin` props route through
   *     `cellTreatment` so the shared legend axis is preserved if the
   *     parent ever mounts MapHighlightLegend on this surface
   *     (currently NationalElection uses the simpler mute-only path,
   *     but the prop surface keeps the option open).
   *
   * The TileCartogram for the same Parliament event (Equal-seats arm
   * of the 3-way toggle) is mounted by `NationalElection.svelte`
   * directly via the existing `buildTileRows` view-model; this
   * component owns the geographic arm only.
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
  import { INDIA_PC, type BoundaryEntry } from "../boundaries/sources";
  import { renderTooltipCard } from "../boundaries/tooltip-card";
  import { symbolAssetUrl } from "../boundaries/symbol-asset";
  import {
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../colors/resolver";
  import { navigate } from "../url";
  import { link } from "../links";
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
  import {
    computeIslandMarker,
    type IslandMarker,
  } from "./india-party-map-helpers";

  /**
   * One PC winner row, pre-shaped by the route for the join. The
   * route reads `ElectionResultRow.state_code` + `ElectionResultRow.eci_no`
   * and builds `unique_id = "<state_code>_<eci_no>"` so the per-feature
   * lookup is a plain `Map.get(unique_id)` here.
   */
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
    /** Per-PC winners + margin. `null` = still loading; `[]` = loaded-but-empty. */
    rows: PcWinnerRow[] | null;
    /** Canonical event id, threaded onto state-page links. */
    event?: string | null;
    /** Deprecated: no longer drives sizing (the map is responsive). Kept
     *  for backward compatibility with existing call sites. */
    height?: string;
    /**
     * Row F (party filter): per-unique_id fill override. When set, the
     * value wins over the cellTreatment fill - the route passes the
     * neutral hex for muted-party cells.
     */
    fillsOverride?: Record<string, string>;
    /** Row F: per-unique_id opacity override - low value for recede. */
    opacitiesOverride?: Record<string, number>;
    /** E4 shared-axis props (default to legacy margin-ramp behaviour). */
    highlight_mode?: HighlightMode;
    selected_party_id?: string | null;
    min_margin?: MinMargin;
    /** PC boundary layer to load + join against. Defaults to `INDIA_PC`
     *  (numeric `unique_id`, e.g. "S07_5"). The route passes
     *  `INDIA_PC_BY_NAME` for LS 2019/2014/2009 events, which joins the
     *  SAME 2024 PC geometry by name-slug (`pc_slug_uid`, e.g.
     *  "S07_karnal") instead of numeric id. Component stays grain-agnostic
     *  - it reads `boundary.join_property` + `feature.properties[that]`
     *  and matches against `row.unique_id` regardless of the shape. */
    boundary?: BoundaryEntry;
  }
  let {
    rows: input_rows,
    event = null,
    fillsOverride,
    opacitiesOverride,
    highlight_mode = DEFAULT_HIGHLIGHT_STATE.mode,
    selected_party_id = DEFAULT_HIGHLIGHT_STATE.selected_party_id,
    min_margin = DEFAULT_HIGHLIGHT_STATE.min_margin,
    boundary = INDIA_PC,
  }: Props = $props();

  // Responsive fit: project to the measured container width (clamped to
  // MAX_MAP_W so a 4K viewport does not produce a giant hero); the SVG
  // height derives from the projected content bounds (no letterboxing).
  const MAX_MAP_W = 1200;
  let container_w = $state(0);
  const DEFAULT_FILL = "#e2e8f0"; // slate-200; J&K placeholders + unmapped
  const JOIN_PROPERTY = boundary.join_property; // "unique_id"
  // `boundary` ships `.geojson` as the canonical snapshot path. Post the
  // 2026-06-16 map-geometry rip the electoral PC layer ships geojson ONLY
  // (the `.topojson` sibling was deleted), so fetch the geojson directly.
  // Fallback to the typed default catches the rare config where
  // `geojson_local_path` is omitted (BoundaryEntry treats it as optional;
  // INDIA_PC and INDIA_PC_BY_NAME both populate it).
  const GEOMETRY_PATH =
    boundary.geojson_local_path ??
    "boundaries/electoral/delim=2024/pc/all.geojson";

  // ---- ECI-keyed lookups -------------------------------------------
  const row_by_uid = $derived.by(() => {
    const m = new Map<string, PcWinnerRow>();
    for (const r of input_rows ?? []) m.set(r.unique_id, r);
    return m;
  });

  // Per-PC party palette (unique_id -> hex), resolved via the 3-tier
  // resolver. Drives the per-cell tooltip pill independently of
  // `fillsOverride` (the pill ALWAYS shows the winning party's brand
  // colour even when the filter rail recedes the underlying polygon).
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

  // Live `--party-neutral` token value for the party_won recede fill;
  // safe-default to the literal in app-tokens.css for SSR / tests.
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

  // ---- Topojson load + projection ----------------------------------
  type Collection = FeatureCollection<Geometry, GeoJsonProperties>;

  let collection = $state<Collection | null>(null);
  let load_error = $state<string | null>(null);

  onMount(() => {
    let cancelled = false;
    const url = `${DATA_BASE}/${GEOMETRY_PATH}`;
    (async () => {
      try {
        const r = await fetch(url);
        if (cancelled) return;
        if (!r.ok) {
          load_error = `geojson fetch failed: ${r.status} ${url}`;
          return;
        }
        // Post map-geometry rip the PC layer ships a plain GeoJSON
        // FeatureCollection (no topojson decode step). Use it directly.
        const fc = (await r.json()) as Collection;
        if (fc?.type !== "FeatureCollection" || !Array.isArray(fc.features)) {
          load_error = `geojson is not a FeatureCollection: ${url}`;
          return;
        }
        if (cancelled) return;
        collection = fc;
      } catch (err) {
        if (cancelled) return;
        load_error = String(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  });

  const projection_path = $derived.by(() => {
    if (!collection) return null;
    const obj = collection as GeoPermissibleObjects;
    const eff_w = Math.min(container_w || 640, MAX_MAP_W);
    const projection: GeoProjection = geoMercator().fitWidth(eff_w, obj);
    // Re-translate so the projected extent starts at (0,0); fitWidth
    // anchors x near 0 but can leave a top offset.
    const pre = geoPath(projection).bounds(obj);
    const [tx, ty] = projection.translate();
    projection.translate([tx - pre[0][0], ty - pre[0][1]]);
    const path = geoPath(projection);
    const b = path.bounds(obj);
    const w = Math.max(1, Math.ceil(b[1][0]));
    const h = Math.max(1, Math.ceil(b[1][1]));
    return { projection, path, w, h };
  });

  // ---- Per-PC paint pipeline ---------------------------------------
  function featureUid(
    props: Record<string, unknown> | undefined,
  ): string | null {
    if (!props) return null;
    const raw = props[JOIN_PROPERTY];
    if (raw == null) return null;
    return String(raw);
  }

  // Wrapper aspect-ratio: the projected content w/h once the topojson
  // loads, a neutral 640/480 default during the loading / error window so
  // the placeholder reserves space (no layout shift when the map paints).
  const wrapper_aspect = $derived(
    projection_path ? `${projection_path.w}/${projection_path.h}` : "640/480",
  );

  // Lakshadweep collapses to a ~2-3 px dot at the national fit; paint a
  // small clickable square at its centroid so the island PC stays citizen-
  // visible. Scoped by name to the one far-flung seat - no mainland PC is
  // ever marked.
  const lakshadweep_marker = $derived<IslandMarker | null>(
    !collection || !projection_path
      ? null
      : computeIslandMarker(
          collection.features,
          projection_path.projection,
          projection_path.path,
          (f) => featureUid(f.properties ?? undefined),
          (f) => String(f.properties?.ls_seat_name ?? ""),
          /laksh/i,
        ),
  );

  // The Lakshadweep feature's props drive the marker hover tooltip (the
  // same card the polygon shows). Resolved once; cheap for one feature.
  const lakshadweep_props = $derived(
    collection?.features.find((f) =>
      /laksh/i.test(String(f.properties?.ls_seat_name ?? "")),
    )?.properties ?? undefined,
  );

  // Pre-compute per-PC fill + opacity from rows. Keyed by unique_id;
  // the per-feature paint resolution looks it up via the feature's uid.
  // `buildPcCellPaint` honours the shared E4 highlight axis + the
  // PR-B8-style fillsOverride / opacitiesOverride precedence path.
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
    const state_ut_name = (props.state_ut_name as string | null) ?? null;
    if (!r) {
      // J&K placeholder or no-winner: render a minimal pending card so
      // hover still shows the PC name.
      if (!ls_seat_name) return null;
      return renderTooltipCard({
        title: state_ut_name
          ? `${ls_seat_name} (${state_ut_name})`
          : ls_seat_name,
        partyShort: "Pending",
        partyColorHex: null,
      });
    }
    return renderTooltipCard({
      title: state_ut_name
        ? `${r.pc_eci_no}. ${r.pc_name} (${state_ut_name})`
        : `${r.pc_eci_no}. ${r.pc_name}`,
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
    if (!r) {
      // J&K placeholder: navigate to the state event view via the
      // state_ut_code parsed from the uid ("S07_8" -> "S07").
      const [state_code] = uid.split("_");
      if (state_code && event) navigate(link.stateElection(state_code, event));
      return;
    }
    if (event) navigate(link.stateElection(r.state_code, event));
  }

  // ---- Hover overlay -----------------------------------------------
  let hover_uid = $state<string | null>(null);
  let hover_html = $state<string | null>(null);
  let hover_x = $state(0);
  let hover_y = $state(0);
  function onFeatureEnter(
    e: MouseEvent,
    props: Record<string, unknown> | undefined,
    uid: string | null,
  ): void {
    hover_uid = uid;
    hover_html = tooltipForUid(props, uid);
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onFeatureMove(e: MouseEvent): void {
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onFeatureLeave(): void {
    hover_uid = null;
    hover_html = null;
  }

  // ---- d3-zoom wiring (1..8 like StateAcMapD3) ---------------------
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
  data-component="india-pc-map-d3"
  data-testid="india-pc-map-d3"
>
  {#if load_error}
    <div
      class="absolute inset-x-2 bottom-2 p-2 text-xs bg-rose-50 border border-rose-200 rounded text-rose-900"
    >
      Map error: <code>{load_error}</code>
    </div>
  {:else if !collection || !projection_path}
    <div
      class="absolute inset-0 flex items-center justify-center text-xs text-slate-500"
    >
      Loading map...
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
        {#each collection.features as f, i (i)}
          {@const uid = featureUid(f.properties ?? undefined)}
          {@const p = paintForUid(uid)}
          <path
            d={safePath(f, pp.path)}
            fill={p.fill}
            fill-opacity={p.opacity}
            stroke="#94a3b8"
            stroke-width="0.4"
            class="india-pc-map-d3__feature"
            data-pc-unique-id={uid ?? ""}
            onmouseenter={(e) =>
              onFeatureEnter(e, f.properties ?? undefined, uid)}
            onmousemove={onFeatureMove}
            onmouseleave={onFeatureLeave}
            onclick={() => onSelectUid(uid)}
          />
        {/each}

        {#if lakshadweep_marker}
          {@const m = lakshadweep_marker}
          <rect
            x={m.cx - 6}
            y={m.cy - 6}
            width={12}
            height={12}
            fill={paintForUid(m.key).fill}
            stroke="#0f172a"
            stroke-width="1.25"
            class="india-pc-map-d3__island-marker"
            data-pc-unique-id={m.key}
            data-marker="island"
            onmouseenter={(e) => onFeatureEnter(e, lakshadweep_props, m.key)}
            onmousemove={onFeatureMove}
            onmouseleave={onFeatureLeave}
            onclick={() => onSelectUid(m.key)}
          />
        {/if}
      </g>
    </svg>

    {#if hover_html}
      <div
        class="absolute pointer-events-none bg-white border border-slate-200 rounded shadow px-2 py-1 text-xs leading-tight max-w-xs"
        style="left: {hover_x}px; top: {hover_y}px;"
        data-testid="india-pc-map-d3-tooltip"
      >
        {@html hover_html}
      </div>
    {/if}

    <!-- +/-/home button trio: same visual language as IndiaPartyMap +
         StateAcMapD3 so the citizen sees one zoom affordance across
         every map surface. -->
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
