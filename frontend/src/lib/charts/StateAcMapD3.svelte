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
   *   - Optional outline silhouette of the active state painted ABOVE
   *     the AC fills (loaded via `loadStateSilhouette` from the shared
   *     `boundaries/in/states/all.geojson` corpus - no new fetch).
   *   - The PR-B8 `fillsOverride` / `opacitiesOverride` precedence path
   *     stays intact so the filter rail keeps working without code
   *     changes on its side.
   *   - E4 (parent plan section 25.5) `highlight_mode` /
   *     `selected_party_id` / `min_margin` props still route through
   *     `cellTreatment` so the shared legend axis is preserved.
   *
   * Adds the three UX gaps PR-4 named for the national map (now
   * extended to the per-state surface):
   *
   *   - Pan / zoom / pinch via d3-zoom on the SVG (scroll-wheel zooms
   *     WITHOUT Ctrl; touch drag pans; pinch zooms). `scaleExtent`
   *     bounded 1..8 per the PR-5 brief (per-state view does not need
   *     the national map's 1..12).
   *   - Absolute-positioned `+` / `-` / `home` button trio over the SVG
   *     (same Tailwind classes as PR-1 + PR-4 for one visual language
   *     across both renderer paths during the transition).
   *   - Sub-threshold dot-marker overlay for any AC whose path bbox
   *     max-dim < SUB_THRESHOLD_PX (14 px at 640x480) at the per-state
   *     fitSize. Dense urban states (Delhi, Chennai, Mumbai) have tiny
   *     city ACs that this catches; each marker carries the SAME fill
   *     + tooltip + click handler as the underlying polygon.
   *
   * Pure helpers (per-row paint formula, focus-dim multiplier, stroke
   * style) live in `state-ac-map-helpers.ts`; the sub-threshold marker
   * pipeline is reused as-is from `india-party-map-helpers.ts`.
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

  import { DATA_BASE } from "../paths";
  import { STATE_AC } from "../maplibre/sources";
  import { renderTooltipCard } from "../maplibre/tooltip-card";
  import { recoverEciNo } from "../maplibre/ac-key-recovery";
  import { parseReservation } from "../maplibre/ac-reservation";
  import { symbolAssetUrl } from "../maplibre/symbol-asset";
  import {
    resolvePartyPalette,
    type PartyRowForResolver,
  } from "../colors/resolver";
  import { navigate } from "../url";
  import { link } from "../links";
  import type { AcWinner } from "../view-models/state-overview";
  import { loadAcLgdLookup } from "../view-models/ac-crosswalk";
  import {
    loadStateSilhouette,
    type StateSilhouetteFeature,
  } from "../state-silhouette";
  import {
    DEFAULT_HIGHLIGHT_STATE,
    NEUTRAL_HEX_FALLBACK,
    type HighlightMode,
    type MinMargin,
  } from "./map-highlight-utils";
  import {
    SUB_THRESHOLD_PX,
    computeSubThresholdMarkers,
    type MarkerOverlay,
  } from "./india-party-map-helpers";
  import {
    acFillForRow,
    acOpacityForRow,
    acStrokeForHighlight,
    type AcCellInput,
  } from "./state-ac-map-helpers";

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
    /** Override map CSS height; width fills the parent. */
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
  }
  let {
    state: state_code,
    rows: input_rows,
    highlight_eci_no,
    height = "520px",
    event = null,
    fillsOverride,
    opacitiesOverride,
    highlight_mode = DEFAULT_HIGHLIGHT_STATE.mode,
    selected_party_id = DEFAULT_HIGHLIGHT_STATE.selected_party_id,
    min_margin = DEFAULT_HIGHLIGHT_STATE.min_margin,
  }: Props = $props();

  // viewBox dimensions - match the PR-4 IndiaPartyMap calibration so the
  // 14-px sub-threshold marker rule reads consistently across both
  // renderer paths. The svg's CSS height comes from the `height` prop;
  // `preserveAspectRatio="xMidYMid meet"` keeps the projection square.
  const WIDTH = 640;
  const HEIGHT = 480;
  const DEFAULT_FILL = "#e2e8f0"; // slate-200; matches MapChoropleth default
  const SILHOUETTE_STROKE = NEUTRAL_HEX_FALLBACK; // E3 outline stroke

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

  // --- Crosswalk + silhouette + neutral hex ---------------------------

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

  // E3 (parent plan section 25.4): per-state silhouette painted ABOVE the
  // AC fills so the citizen instantly recognises which state the per-state
  // map shows. Uses the shared `boundaries/in/states/all.topojson` corpus
  // via `loadStateSilhouette` (no new fetch; see that module's receipt).
  let silhouette_feature = $state<StateSilhouetteFeature | null>(null);
  $effect(() => {
    const sc = state_code;
    silhouette_feature = null;
    loadStateSilhouette(sc)
      .then((f) => {
        if (state_code === sc) silhouette_feature = f;
      })
      .catch(() => {
        if (state_code === sc) silhouette_feature = null;
      });
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

  // --- Boundary GeoJSON fetch + projection ----------------------------
  //
  // The per-state AC layer lives at `<DATA_BASE>/<entry.geojson_local_path>`
  // (e.g. `data/boundaries/electoral/delim=2008/ac/state=tamil-nadu/
  // all.geojson`). Reload when `state_code` changes.

  type Collection = FeatureCollection<Geometry, GeoJsonProperties>;

  let collection: Collection | null = $state(null);
  let load_error: string | null = $state(null);
  // Token bumped whenever a new fetch is issued; the in-flight callback
  // ignores its result if the token has moved on (state change mid-fetch).
  let fetch_token = $state(0);

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
    const e = STATE_AC[sc];
    if (!e?.geojson_local_path) return;
    const my_token = ++fetch_token;
    const url = `${DATA_BASE}/${e.geojson_local_path}`;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(url);
        if (cancelled || my_token !== fetch_token) return;
        if (!r.ok) {
          load_error = `geojson fetch failed: ${r.status} ${url}`;
          return;
        }
        const fc = (await r.json()) as FeatureCollection<
          Geometry,
          GeoJsonProperties
        >;
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
    if (!initial_load_done) {
      initial_load_done = true;
      return;
    }
    const e = STATE_AC[sc];
    collection = null;
    load_error = null;
    if (!e?.geojson_local_path) return;
    const my_token = ++fetch_token;
    const url = `${DATA_BASE}/${e.geojson_local_path}`;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(url);
        if (cancelled || my_token !== fetch_token) return;
        if (!r.ok) {
          load_error = `geojson fetch failed: ${r.status} ${url}`;
          return;
        }
        const fc = (await r.json()) as FeatureCollection<
          Geometry,
          GeoJsonProperties
        >;
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
    // `fitSize` streams every feature through the projection to compute
    // bounds; on a malformed geometry ring (some TN / Maharashtra / WB AC
    // features have an empty `ring[0]`) it throws synchronously with
    // "Cannot read properties of undefined (reading '0')". Filter those
    // features OUT for fitSize, then build the path over the SAME
    // filtered collection so the broken features never reach `path()`
    // either. The underlying topology bug is upstream (ramSeraph LGD
    // release) and out of PR-5 scope.
    const safe_features = collection.features.filter((f) =>
      isFeatureProjectable(f),
    );
    if (safe_features.length === 0) return null;
    const safe_collection: FeatureCollection<Geometry, GeoJsonProperties> = {
      type: "FeatureCollection",
      features: safe_features,
    };
    let projection: GeoProjection;
    try {
      projection = geoMercator().fitSize(
        [WIDTH, HEIGHT],
        safe_collection as GeoPermissibleObjects,
      );
    } catch {
      // Defensive belt-and-braces: even after filtering, an unknown
      // failure mode should not blank the whole map. Use a default
      // Mercator centered on India and let `safePath` skip broken
      // features one-by-one.
      projection = geoMercator()
        .center([82.5, 22.5])
        .scale(700)
        .translate([WIDTH / 2, HEIGHT / 2]);
    }
    const path = geoPath(projection);
    return { projection, path };
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

  // eci_no -> Feature index. Lets the sub-threshold marker overlay
  // resolve its underlying feature in O(1) for the per-marker
  // fill/opacity/tooltip/click resolution.
  const feature_by_eci = $derived.by(() => {
    const m = new Map<number, Feature<Geometry, GeoJsonProperties>>();
    if (!collection || !entry) return m;
    const rl = reverse_lookup;
    const join = entry.join_property;
    for (const f of collection.features) {
      const eci = featureEci(f.properties ?? undefined, join, rl);
      if (eci != null) m.set(eci, f);
    }
    return m;
  });

  // Sub-threshold marker overlays - second-pass <circle> targets for
  // any AC whose polygon collapses below SUB_THRESHOLD_PX at the
  // per-state fitSize. Each marker carries the SAME eci-keyed fill /
  // opacity / tooltip / click as the underlying polygon.
  const marker_overlays = $derived.by<MarkerOverlay[]>(() => {
    if (!collection || !projection_path || !entry) return [];
    const rl = reverse_lookup;
    const join = entry.join_property;
    return computeSubThresholdMarkers(
      collection.features,
      projection_path.projection,
      projection_path.path,
      (f) => featureEci(f.properties ?? undefined, join, rl),
    );
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
      title: `${r.eci_no}. ${r.name}`,
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
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onFeatureMove(e: MouseEvent): void {
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
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
    class="relative w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
    style="height: {height};"
    data-component="state-ac-map-d3"
    data-state={state_code}
    data-threshold-px={SUB_THRESHOLD_PX}
  >
    {#if load_error}
      <div
        class="absolute inset-x-2 bottom-2 p-2 text-xs bg-rose-50 border border-rose-200 rounded text-rose-900"
      >
        Map error: <code>{load_error}</code>
      </div>
    {:else if !collection || !projection_path}
      <div class="absolute inset-0 flex items-center justify-center text-xs text-slate-500">
        Loading map...
      </div>
    {:else}
      {@const pp = projection_path}
      {@const join_property = entry.join_property}
      {@const rl = reverse_lookup}
      <svg
        bind:this={svg_el}
        class="block w-full h-full cursor-grab active:cursor-grabbing"
        viewBox="0 0 {WIDTH} {HEIGHT}"
        preserveAspectRatio="xMidYMid meet"
      >
        <g bind:this={zoom_group_el}>
          {#each collection.features as f, i (i)}
            {@const eci = featureEci(f.properties ?? undefined, join_property, rl)}
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

          {#each marker_overlays as m, mi (mi)}
            {@const eci = Number(m.key)}
            {@const matching = feature_by_eci.get(eci)}
            {@const p = paintForEci(eci)}
            <circle
              cx={m.cx}
              cy={m.cy}
              r={7}
              fill={p.fill}
              fill-opacity={p.opacity}
              stroke="#0f172a"
              stroke-width="1"
              class="state-ac-map-d3__marker"
              data-ac-eci-no={m.key}
              data-marker="sub-threshold"
              onmouseenter={(e) =>
                onFeatureEnter(e, matching?.properties ?? undefined, eci)}
              onmousemove={onFeatureMove}
              onmouseleave={onFeatureLeave}
              onclick={() => onSelect(eci)}
            />
          {/each}

          {#if silhouette_feature}
            <path
              d={safePath(silhouette_feature, pp.path)}
              fill="none"
              stroke={SILHOUETTE_STROKE}
              stroke-width="1.5"
              pointer-events="none"
              class="state-ac-map-d3__silhouette"
              data-component="state-ac-map-d3-silhouette"
            />
          {/if}
        </g>
      </svg>

      {#if hover_html}
        <div
          class="absolute pointer-events-none bg-white border border-slate-200 rounded shadow px-2 py-1 text-xs leading-tight max-w-xs"
          style="left: {hover_x}px; top: {hover_y}px;"
          data-testid="state-ac-map-d3-tooltip"
        >
          {@html hover_html}
        </div>
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
