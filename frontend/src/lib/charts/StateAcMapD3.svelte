<script lang="ts">
  /**
   * StateAcMapD3 - the d3-geo SVG choropleth that replaces the
   * MapLibre-based `lib/maplibre/StateAcMap.svelte` on every per-state
   * AC surface (StateOverview / StateElection / Constituency / the
   * ElectionMap legend wrapper). PR-5 of
   * `TODO/20260611-elections-off-maplibre-and-map-ux-plan.md`,
   * following the PR-4 IndiaPartyMap template.
   *
   * Preserves every behaviour from the legacy component:
   *
   *   - Per-AC fill from the winner's party id via the 3-tier palette
   *     (`resolvePartyPalette` + `getPartyColor`), unchanged.
   *   - Per-AC opacity proportional to margin via the shared `cellTreatment`
   *     fork (margin-ramp 0.35..0.95; party_won 0/1 step). The
   *     `highlight_eci_no` focus-dim (matched AC -> 1.0, all others ->
   *     base * 0.18) is preserved; the matched AC ALSO gets a slate-900
   *     2.5px stroke outline.
   *   - Hover tooltip: AC name + winner candidate + party pill +
   *     margin %, rendered via the SAME `renderTooltipCard` template
   *     the legacy map used (no per-renderer drift).
   *   - Click an AC polygon -> `navigate(link.ac(state_code, ac_name,
   *     event))`. AC name lookup mirrors the legacy `name_by_eci`.
   *   - The PR-B8 `fillsOverride` / `opacitiesOverride` precedence path
   *     stays intact so the filter rail keeps working without code
   *     changes on its side.
   *   - E4 (parent plan section 25.5) `highlight_mode` /
   *     `selected_party_id` / `min_margin` props still route through
   *     `cellTreatment` so the shared legend axis is preserved.
   *
   * Adds the two UX gaps PR-4 named for the national map (now
   * extended to the per-state surface):
   *
   *   - Pan / zoom / pinch via d3-zoom on the SVG (scroll-wheel zooms
   *     WITHOUT Ctrl; touch drag pans; pinch zooms). `scaleExtent`
   *     bounded 1..8 per the PR-5 brief (per-state view does not need
   *     the national map's 1..12).
   *   - Absolute-positioned `+` / `-` / `home` button trio over the SVG
   *     (same Tailwind classes as PR-1 + PR-4 for one visual language
   *     across both renderer paths during the transition).
   *
   * Pure helpers (per-row paint formula, focus-dim multiplier, stroke
   * style) live in `state-ac-map-helpers.ts`.
   *
   * MapLibre `lib/maplibre/StateAcMap.svelte` is deliberately NOT
   * deleted here - PR-6 deletes the entire `lib/maplibre/` directory
   * after this PR retires it from the four call sites.
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
  import { feature as topojsonFeature } from "topojson-client";
  import type { Topology, GeometryCollection } from "topojson-specification";

  import { DATA_BASE } from "../paths";
  import { fetchGeometryJson } from "./geometry-cache";
  import { STATE_AC } from "../boundaries/sources";
  import { renderTooltipCard } from "../boundaries/tooltip-card";
  import HoverCardShell from "./HoverCardShell.svelte";
  import { recoverEciNo } from "../boundaries/ac-key-recovery";
  import { parseReservation } from "../boundaries/ac-reservation";
  import { symbolAssetUrl } from "../boundaries/symbol-asset";
  import {
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../colors/resolver";
  import { navigate } from "../url";
  import { link } from "../links";
  import type { AcWinner } from "../view-models/state-overview";
  import { loadStates } from "../view-models/states";
  import { loadAcLgdLookup } from "../view-models/ac-crosswalk";
  import { rewindCollectionForD3 } from "./geo-rewind";
  import { slugify } from "../slug";
  import {
    computeCoverage,
    delimVintageFromPath,
    type MapCoverageEmit,
  } from "./map-coverage";
  import {
    DEFAULT_HIGHLIGHT_STATE,
    NEUTRAL_HEX_FALLBACK,
    type HighlightMode,
    type MinMargin,
  } from "./map-highlight-utils";
  import {
    acFillForRow,
    acOpacityForRow,
    acStrokeForHighlight,
    type AcCellInput,
  } from "./state-ac-map-helpers";
  import MapFrameSkeleton from "../MapFrameSkeleton.svelte";

  interface Props {
    state: string;
    /** Per-AC winners + margin. Parent loads via `loadStateOverview` (state
     *  hub) or `loadStateAcWinners` (constituency drill-down) and passes
     *  them in. `null` = still loading; `[]` = loaded but empty
     *  (not_published). */
    rows: AcWinner[] | null;
    /**
     * When set, the map dims every other AC to ~18% opacity so this one
     * stands out, and paints a slate-900 2.5 px stroke around the matched
     * polygon. Used by the per-AC drill-down page to render a state map
     * with the focused constituency emphasised.
     */
    highlight_eci_no?: number;
    /** Deprecated: no longer drives sizing (the map is responsive). Kept
     *  for backward compatibility with existing call sites. */
    height?: string;
    event?: string | null;
    /**
     * PR-B8 colour-by override. When set, replaces the default winner-party
     * fills / margin-based opacities (keyed by `ac_eci_no`). Lets the
     * filter rail recolour + dim the SAME choropleth without a bespoke
     * widget. `highlight_eci_no` still wins for the per-AC drill-down.
     */
    fillsOverride?: Record<number, string>;
    opacitiesOverride?: Record<number, number>;
    /**
     * E4 (parent plan section 25.5): shared map-highlight axis driven by
     * `MapHighlightLegend`. Defaults preserve the existing margin-ramp
     * behaviour; `highlight_mode === "party_won"` swaps fills + opacities
     * via `cellTreatment` (the selected party's wins at full opacity in
     * their party colour; non-matching cells recede to `--party-neutral`
     * at low opacity).
     */
    highlight_mode?: HighlightMode;
    selected_party_id?: string | null;
    min_margin?: MinMargin;
    /**
     * PR-B (undivided / historical render). A non-empty list of ECI state
     * codes (e.g. ["S01","S29"] for an undivided Andhra Pradesh event whose
     * results predate the 2014 bifurcation) makes the map draw the UNION of
     * those states' AC features and join winners by constituency NAME slug
     * instead of eci_no (the numbering does not survive a delimitation
     * change). Unmatched seats render grey; the shortfall shows in the
     * coverage caption. Undefined/empty = the default single-state eci_no
     * join (behaviour unchanged).
     */
    historical_states?: string[];
    /** Lifts the render-time coverage tuple to the parent so the caption
     *  renders below the per-state party legend (not inside the map card). */
    oncoverage?: (e: MapCoverageEmit) => void;
  }
  let {
    state: state_code,
    rows: input_rows,
    highlight_eci_no,
    event = null,
    fillsOverride,
    opacitiesOverride,
    highlight_mode = DEFAULT_HIGHLIGHT_STATE.mode,
    selected_party_id = DEFAULT_HIGHLIGHT_STATE.selected_party_id,
    min_margin = DEFAULT_HIGHLIGHT_STATE.min_margin,
    historical_states,
    oncoverage,
  }: Props = $props();

  // Responsive fit: project to the measured container width (clamped to
  // MAX_MAP_W so a 4K viewport does not produce a giant hero); the SVG
  // height derives from the projected content bounds (no letterboxing).
  const MAX_MAP_W = 1200;
  let container_w = $state(0);
  let container_h = $state(0);
  const DEFAULT_FILL = "#e2e8f0"; // slate-200; matches MapChoropleth default

  // Parent-state label for the hover card (R-D parent row). The AC feature
  // `st_name` is border-sliver contaminated (a single AC feature can carry a
  // neighbouring state's name, and some carry none), so resolve the page
  // state's clean citizen-facing display name from the reliable `state_code`
  // prop via the canonical states loader (cached; plain fetch, no DuckDB
  // boot) rather than the geometry properties.
  let state_name = $state<string | null>(null);
  $effect(() => {
    const sc = state_code;
    let cancelled = false;
    loadStates()
      .then((states) => {
        if (cancelled) return;
        state_name =
          states.find((s) => s.eci_code === sc)?.display_name ?? null;
      })
      .catch(() => {
        if (!cancelled) state_name = null;
      });
    return () => {
      cancelled = true;
    };
  });

  interface Row {
    eci_no: number;
    name: string;
    party_id: string;
    winner_party_eci_code: string | null;
    winner_party_short: string;
    margin_pct: number;
    winner_candidate_name: string | null;
    symbol_asset_path: string | null;
    brand_colour_hex: string | null;
    brand_colour_confidence: "high" | "medium" | "low" | null;
  }

  // --- AcWinner -> Row mapping (verbatim from legacy StateAcMap) -----
  const rows = $derived<Row[] | null>(
    input_rows == null
      ? null
      : input_rows.map((w) => ({
          eci_no: w.ac_eci_no,
          name: w.ac_name,
          party_id: w.party_id,
          winner_party_eci_code: w.party_eci_code,
          winner_party_short: w.party_short,
          margin_pct: w.margin_pct,
          winner_candidate_name: w.winner_candidate_name ?? null,
          symbol_asset_path: w.symbol_asset_path ?? null,
          brand_colour_hex: w.brand_colour_hex ?? null,
          brand_colour_confidence: w.brand_colour_confidence ?? null,
        })),
  );

  const entry = $derived(STATE_AC[state_code]);

  // ECI-keyed lookups for the per-row tooltip + fill + nav.
  const row_by_eci = $derived.by(() => {
    const m = new Map<number, Row>();
    for (const r of rows ?? []) m.set(r.eci_no, r);
    return m;
  });
  const name_by_eci = $derived.by(() => {
    const m = new Map<number, string>();
    for (const r of rows ?? []) m.set(r.eci_no, r.name);
    return m;
  });

  // PR-B: undivided / historical render. `render_states` is the set of ECI
  // state codes whose AC features to draw (the union for an undivided
  // event; just `state` otherwise). `name_join` switches the per-feature
  // winner lookup from eci_no to constituency-name slug, since the eci_no
  // numbering does not survive a delimitation change.
  const render_states = $derived(
    historical_states && historical_states.length
      ? historical_states
      : [state_code],
  );
  const name_join = $derived(
    !!(historical_states && historical_states.length),
  );
  // name-slug -> eci_no, so a historical feature resolves to a winner by
  // its constituency name (the persisted ~60% of pre-delimitation seats).
  const eci_by_name_slug = $derived.by(() => {
    const m = new Map<string, number>();
    for (const r of rows ?? []) {
      const k = slugify(r.name);
      if (k && !m.has(k)) m.set(k, r.eci_no);
    }
    return m;
  });

  // Per-AC party palette (eci_no -> hex), resolved once via the 3-tier
  // resolver. Drives BOTH the default choropleth fill and the tooltip
  // party pill independently of `fillsOverride` (the pill ALWAYS shows
  // the winning party's colour even when the filter rail recolours the
  // choropleth by some other dimension).
  const party_colors = $derived.by(() => {
    const list = rows ?? [];
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
    const out = new Map<number, string>();
    for (const r of list) {
      const hex = palette.get(r.party_id)?.hex;
      if (hex) out.set(r.eci_no, hex);
    }
    return out;
  });

  // --- Crosswalk + neutral hex ----------------------------------------

  // ADR-0049 Row B2: lgd_ac_id <-> eci_no crosswalk. Covered states get a
  // non-empty map and the polygon's `lgd_ac_id` join is reverse-mapped to
  // eci_no for fills / tooltips / navigation. Uncovered states (S03 Assam
  // district-fallback, U08 J&K seat_id) get an empty map and ride their
  // own join property directly. Errors degrade to the legacy join rather
  // than blanking the choropleth.
  let lgd_lookup = $state<Map<number, number> | null>(null);
  $effect(() => {
    const sc = state_code;
    lgd_lookup = null;
    loadAcLgdLookup(sc)
      .then((m) => {
        if (state_code === sc) lgd_lookup = m;
      })
      .catch(() => {
        if (state_code === sc) lgd_lookup = null;
      });
  });

  const reverse_lookup = $derived.by(() => {
    if (!lgd_lookup) return null;
    const out = new Map<number, number>();
    for (const [eci, lgd] of lgd_lookup) out.set(lgd, eci);
    return out;
  });

  // E4: the live `--party-neutral` token value, used as the recede fill in
  // `party_won` mode via `cellTreatment`. Read once from `:root` (where
  // app-tokens.css defines it). Falls back to the literal in SSR / tests.
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

  // --- Boundary geometry fetch + per-state filter + projection --------
  //
  // Post the 2026-06-16 map-geometry rip (Row 3) EVERY AC state's
  // geometry is served from the ONE national, DERIVED topojson
  // `boundaries/electoral/delim=2024/ac/all.topojson` (object `ac`,
  // each feature stamped with `state_ut_code`). We fetch + decode it,
  // then filter to the features whose `state_ut_code === state_code`.
  // The per-state PAINT join (`entry.join_property` + the lgd<->eci
  // crosswalk) is unchanged - only the geometry SOURCE moved from 31
  // per-state geojson shards to this single national composite.

  type Collection = FeatureCollection<Geometry, GeoJsonProperties>;

  const STATE_FILTER_PROPERTY = "state_ut_code";

  let collection: Collection | null = $state(null);
  let load_error: string | null = $state(null);
  // Token bumped whenever a new fetch is issued; the in-flight callback
  // ignores its result if the token has moved on (state change mid-fetch).
  let fetch_token = $state(0);

  // Fetch the national AC topojson, decode the named object, and return
  // ONLY the features for `sc` (stamped `state_ut_code`). Return-only by
  // design: the Svelte-5 quirk requires the `$state` write to originate
  // inside the onMount / $effect IIFE, so this helper never touches
  // `collection` - the caller assigns the value it returns.
  async function fetchStateAcCollection(
    sc: string,
    filter_states?: readonly string[],
  ): Promise<Collection> {
    const e = STATE_AC[sc];
    if (!e?.geojson_local_path) {
      throw new Error(`no AC geometry path for ${sc}`);
    }
    const url = `${DATA_BASE}/${e.geojson_local_path}`;
    // Row 3b: cache the fetched + parsed geometry per URL so revisiting
    // this state's AC map does not re-download the (large) geometry file.
    // fetchGeometryJson throws on a non-OK status, matching the previous
    // explicit `!r.ok` throw (the caller's try/catch handles it).
    const raw = (await fetchGeometryJson(url)) as Topology | Collection;
    let fc: Collection;
    if (e.geojson_local_path.endsWith(".topojson")) {
      const topo = raw as Topology;
      const obj = e.topojson_object
        ? topo.objects?.[e.topojson_object]
        : undefined;
      if (!obj) {
        throw new Error(
          `topojson object '${e.topojson_object ?? "?"}' missing in ${url}`,
        );
      }
      fc = topojsonFeature(topo, obj as GeometryCollection) as Collection;
    } else {
      fc = raw as Collection;
    }
    const keep = new Set(
      filter_states && filter_states.length ? filter_states : [sc],
    );
    const features = fc.features.filter((f) =>
      keep.has(
        String(
          (f.properties as Record<string, unknown> | null)?.[
            STATE_FILTER_PROPERTY
          ] ?? "",
        ),
      ),
    );
    // A plain-GeoJSON AC layer (post map-geometry rip) carries RFC 7946
    // counter-clockwise-exterior winding; d3-geo wants clockwise exteriors.
    // Rewind so polygons don't paint the whole viewBox. Idempotent, so the
    // topojson-decoded branch (already clockwise) is unaffected.
    return rewindCollectionForD3({ type: "FeatureCollection", features });
  }

  // First fetch via onMount (IndiaPartyMap-proven pattern: $state writes
  // from a `(async () => { ... })()` IIFE inside `onMount(...)` propagate
  // to the template; the same writes from `.then(...)` callbacks invoked
  // by a separate helper function do NOT (Svelte 5 reactivity quirk
  // observed empirically during PR-5 development).
  // First fetch via onMount. NB the IndiaPartyMap-proven pattern -
  // `$state` writes from a `(async () => { ... })()` IIFE inside
  // `onMount(...)` propagate to the template, but the same writes
  // from `.then(...)` callbacks invoked through a separate helper
  // function do NOT (observed during PR-5 development, Svelte v5.x).
  onMount(() => {
    const sc = state_code;
    const states = render_states;
    if (!STATE_AC[sc]?.geojson_local_path) return;
    const my_token = ++fetch_token;
    let cancelled = false;
    (async () => {
      try {
        const fc = await fetchStateAcCollection(sc, states);
        if (cancelled || my_token !== fetch_token) return;
        collection = fc;
      } catch (err) {
        if (cancelled || my_token !== fetch_token) return;
        load_error = String(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  });

  // Re-fetch on subsequent state_code changes (parent navigates between
  // states without unmounting). Skip the FIRST run so onMount's fetch
  // owns the initial load.
  let initial_load_done = false;
  $effect(() => {
    const sc = state_code;
    const states = render_states;
    if (!initial_load_done) {
      initial_load_done = true;
      return;
    }
    collection = null;
    load_error = null;
    if (!STATE_AC[sc]?.geojson_local_path) return;
    const my_token = ++fetch_token;
    let cancelled = false;
    (async () => {
      try {
        const fc = await fetchStateAcCollection(sc, states);
        if (cancelled || my_token !== fetch_token) return;
        collection = fc;
      } catch (err) {
        if (cancelled || my_token !== fetch_token) return;
        load_error = String(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  });

  const projection_path = $derived.by(() => {
    if (!collection) return null;
    // `fitWidth` streams every feature through the projection to compute
    // bounds; on a malformed geometry ring (some TN / Maharashtra / WB AC
    // features have an empty `ring[0]`) it throws synchronously with
    // "Cannot read properties of undefined (reading '0')". Filter those
    // features OUT first, then build the path over the SAME filtered
    // collection so the broken features never reach `path()` either. The
    // underlying topology bug is upstream (ramSeraph LGD release) and out
    // of PR-5 scope.
    const safe_features = collection.features.filter((f) =>
      isFeatureProjectable(f),
    );
    if (safe_features.length === 0) return null;
    const safe_collection: FeatureCollection<Geometry, GeoJsonProperties> = {
      type: "FeatureCollection",
      features: safe_features,
    };
    const obj = safe_collection as GeoPermissibleObjects;
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
      // Defensive belt-and-braces: even after filtering, an unknown
      // failure mode should not blank the whole map. Use a default
      // Mercator centered on India and let `safePath` skip broken
      // features one-by-one.
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

  /** Quick projectability probe: try to compute the bounds of a feature
   *  through a throwaway projection. Returns false when d3-geo throws on
   *  the feature's geometry (e.g. an empty polygon ring). Used to filter
   *  the per-state AC collection before `fitSize`. */
  function isFeatureProjectable(
    f: Feature<Geometry, GeoJsonProperties>,
  ): boolean {
    try {
      const proj = geoMercator();
      const p = geoPath(proj);
      const b = p.bounds(f);
      return (
        Number.isFinite(b[0][0]) &&
        Number.isFinite(b[0][1]) &&
        Number.isFinite(b[1][0]) &&
        Number.isFinite(b[1][1])
      );
    } catch {
      return false;
    }
  }

  // Per-feature ECI extractor. The covered-state polygon emits
  // `lgd_ac_id` as the canonical join property (ADR-0049 Row B3); the
  // helper reverse-maps it through `reverse_lookup` to the eci_no the
  // winner rows are keyed by. Uncovered states whose join property is
  // already eci-valued / seat-valued pass through unchanged.
  function featureEci(
    props: Record<string, unknown> | undefined,
    join_property: string,
    reverse: Map<number, number> | null,
  ): number | null {
    if (!props) return null;
    const raw = props[join_property];
    if (raw == null) return null;
    const eci = recoverEciNo(raw as string | number, props, reverse);
    return Number.isFinite(eci) ? eci : null;
  }

  // Wrapper aspect-ratio: the projected content w/h once the collection
  // loads, a neutral 640/480 default during the loading / error window so
  // the placeholder reserves space (no layout shift when the map paints).
  const wrapper_aspect = $derived(
    projection_path ? `${projection_path.w}/${projection_path.h}` : "640/480",
  );

  // PR-B coverage caption: in name-join mode, how many rendered AC features
  // bound a winner by name slug (the persisted seats) vs total on screen.
  // Auto-hides outside name-join mode (onOldGeometry=false).
  const ac_coverage = $derived.by(() => {
    if (!name_join || !collection) return null;
    return computeCoverage(
      collection.features.map((f) =>
        slugify(
          String(
            (f.properties as Record<string, unknown> | null)?.ac_name ?? "",
          ),
        ),
      ),
      (k) => eci_by_name_slug.has(String(k)),
    );
  });
  const ac_geometry_year = $derived(
    delimVintageFromPath(STATE_AC[state_code]?.geojson_local_path),
  );
  // Lift coverage to the parent (StateEventMap -> StateElection) so the
  // caption renders below the per-state party legend instead of inside the
  // map card.
  $effect(() => {
    oncoverage?.({
      coverage: ac_coverage,
      geometryYear: ac_geometry_year,
      onOldGeometry: name_join,
    });
    // Clear on unmount (e.g. the parent switches to the hex / equal-seats
    // arm) so the parent never shows a stale caption for a map that is no
    // longer drawn.
    return () =>
      oncoverage?.({
        coverage: null,
        geometryYear: null,
        onOldGeometry: false,
      });
  });

  // Pre-compute per-AC fill + opacity from rows. Keyed by eci_no; the
  // per-feature paint resolution looks it up via the feature's
  // recovered eci. cellTreatment is called per row inside
  // `acFillForRow` / `acOpacityForRow` so the legend axis flips
  // (margin <-> party_won) re-derive the whole map at once.
  const cell_treatments = $derived.by(() => {
    const out = new Map<number, { fill: string; opacity: number }>();
    for (const r of rows ?? []) {
      const input: AcCellInput = {
        party_id: r.party_id,
        margin_pct: r.margin_pct,
        winner_party_hex: party_colors.get(r.eci_no) ?? "#94a3b8",
        neutral_hex,
        mode: highlight_mode,
        selected_party_id,
        min_margin,
      };
      const fill = acFillForRow(input, fillsOverride?.[r.eci_no]);
      const opacity = acOpacityForRow(
        input,
        r.eci_no,
        opacitiesOverride?.[r.eci_no],
        highlight_eci_no,
      );
      out.set(r.eci_no, { fill, opacity });
    }
    return out;
  });

  interface Paint {
    fill: string;
    opacity: number;
    stroke: string;
    strokeWidth: number;
  }

  function paintForEci(eci: number | null): Paint {
    const stroke = acStrokeForHighlight(
      eci ?? -1, // -1 never matches highlight_eci_no, so falls through to hairline
      highlight_eci_no,
    );
    if (eci == null) {
      return {
        fill: DEFAULT_FILL,
        opacity: 1,
        stroke: stroke.stroke,
        strokeWidth: stroke.strokeWidth,
      };
    }
    const t = cell_treatments.get(eci);
    if (!t) {
      return {
        fill: DEFAULT_FILL,
        opacity: 1,
        stroke: stroke.stroke,
        strokeWidth: stroke.strokeWidth,
      };
    }
    return {
      fill: t.fill,
      opacity: t.opacity,
      stroke: stroke.stroke,
      strokeWidth: stroke.strokeWidth,
    };
  }

  function safePath(
    f: Feature<Geometry, GeoJsonProperties>,
    geo_path: ReturnType<typeof geoPath>,
  ): string {
    // d3-geo's `path(feature)` throws synchronously on a malformed
    // geometry ring (e.g. some TN / Maharashtra / WB AC features have an
    // empty `ring[0]`). Skip the broken feature visually rather than
    // crashing the entire reactive flush; the underlying topology bug is
    // upstream (ramSeraph LGD release) and out of PR-5 scope.
    try {
      return geo_path(f) ?? "";
    } catch {
      return "";
    }
  }

  function tooltipForFeature(
    props: Record<string, unknown> | undefined,
    eci: number | null,
  ): string | null {
    if (!props || eci == null) return null;
    const r = row_by_eci.get(eci);
    if (!r) return null;
    return renderTooltipCard({
      title: r.name,
      grain: "AC",
      parentLabel: state_name,
      reservation: parseReservation(props),
      candidateName: r.winner_candidate_name,
      partyShort: r.winner_party_short,
      partyColorHex: party_colors.get(eci) ?? null,
      symbolAsset: symbolAssetUrl(r.symbol_asset_path),
      marginPct: r.margin_pct,
    });
  }

  function onSelect(eci: number | null): void {
    if (eci == null || !Number.isFinite(eci)) return;
    navigate(link.ac(state_code, name_by_eci.get(eci) ?? "", event));
  }

  // --- Hover state (HTML overlay tooltip) -----------------------------

  let hover_eci = $state<number | null>(null);
  let hover_html = $state<string | null>(null);
  let hover_x = $state(0);
  let hover_y = $state(0);

  function onFeatureEnter(
    e: MouseEvent,
    props: Record<string, unknown> | undefined,
    eci: number | null,
  ): void {
    hover_eci = eci;
    hover_html = tooltipForFeature(props, eci);
    hover_x = e.offsetX;
    hover_y = e.offsetY;
  }
  function onFeatureMove(e: MouseEvent): void {
    hover_x = e.offsetX;
    hover_y = e.offsetY;
  }
  function onFeatureLeave(): void {
    hover_eci = null;
    hover_html = null;
  }

  // --- d3-zoom wiring (1..8 per the PR-5 brief) -----------------------
  //
  // The SVG receives the zoom behaviour; the inner <g> carries the
  // transform. Scroll-wheel zooms without Ctrl (d3-zoom default).
  // Touch drag pans + pinch zooms. Button-driven dispatches go through
  // the same zoom_behavior instance so the internal `__zoom` state
  // stays in sync; we do NOT chain `.transition()` on the button
  // handlers (PR-4 found the `.transition()` form silently no-op'd in
  // browser smoke; the gesture path stays immediate).

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

  // Reset the zoom transform whenever the responsive width changes so a
  // stale transform from the previous width does not cause a visual jump.
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

{#if !entry}
  <div class="p-3 text-sm text-slate-500">
    No boundary source registered for state <code>{state_code}</code>.
  </div>
{:else}
  <div
    bind:clientWidth={container_w}
    bind:clientHeight={container_h}
    class="relative w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
    style="aspect-ratio:{wrapper_aspect};"
    data-component="state-ac-map-d3"
    data-state={state_code}
  >
    {#if load_error}
      <div
        class="absolute inset-x-2 bottom-2 p-2 text-xs bg-rose-50 border border-rose-200 rounded text-rose-900"
      >
        Map error: <code>{load_error}</code>
      </div>
    {:else if !collection || !projection_path}
      <div class="absolute inset-0">
        <MapFrameSkeleton height="100%" />
      </div>
    {:else}
      {@const pp = projection_path}
      {@const join_property = entry.join_property}
      {@const rl = reverse_lookup}
      <svg
        bind:this={svg_el}
        class="block w-full cursor-grab active:cursor-grabbing"
        viewBox="0 0 {pp.w} {pp.h}"
        width="100%"
        style="height:auto; aspect-ratio:{pp.w}/{pp.h};"
      >
        <g bind:this={zoom_group_el}>
          {#each collection.features as f, i (i)}
            {@const eci = name_join
              ? (eci_by_name_slug.get(
                  slugify(String(f.properties?.ac_name ?? "")),
                ) ?? null)
              : featureEci(f.properties ?? undefined, join_property, rl)}
            {@const p = paintForEci(eci)}
            <path
              d={safePath(f, pp.path)}
              fill={p.fill}
              fill-opacity={p.opacity}
              stroke={p.stroke}
              stroke-width={p.strokeWidth}
              class="state-ac-map-d3__feature"
              data-ac-eci-no={eci ?? ""}
              data-ac-name={String(f.properties?.ac_name ?? "")}
              onmouseenter={(e) => onFeatureEnter(e, f.properties ?? undefined, eci)}
              onmousemove={onFeatureMove}
              onmouseleave={onFeatureLeave}
              onclick={() => onSelect(eci)}
            />
          {/each}
        </g>
      </svg>

      {#if hover_html}
        <HoverCardShell
          x={hover_x}
          y={hover_y}
          html={hover_html}
          containerW={container_w}
          containerH={container_h}
          testid="state-ac-map-d3-tooltip"
        />
      {/if}

      <!--
        +/-/home button trio over the SVG. Same Tailwind classes as PR-1
        MapChoropleth + PR-4 IndiaPartyMap so the citizen sees ONE
        visual language across all map surfaces during the transition.
      -->
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
        >{"\u2212"}</button>
        <button
          type="button"
          aria-label="Reset view"
          class="w-8 h-8 rounded-full bg-white border border-slate-300 text-slate-700 text-lg leading-none flex items-center justify-center shadow hover:bg-slate-100 active:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          onclick={homeButton}
        >{"\u2302"}</button>
      </div>
    {/if}
  </div>
{/if}
