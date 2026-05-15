<script lang="ts">
  // Generic choropleth map. Parents pass a boundary `entry`, a `fills` map
  // keyed by the join-property value (state name for India / AC_NO for AC
  // layers), and optional opacities + tooltip text. The component owns
  // map lifecycle, source loading (PMTiles via manifest or raw GeoJSON
  // fallback — see ./sources.ts), and hover/click events.
  //
  // maplibre-gl is loaded via dynamic import so it's split out of the
  // main bundle. Pages that don't render a map don't pay the ~300 KB cost.
  //
  // Coloring uses a `match` paint expression rebuilt whenever `fills`
  // changes — works without per-feature ids and avoids the `setFeatureState`
  // dance for layers loaded from raw GeoJSON.

  import { onMount, onDestroy } from "svelte";
  import maplibregl from "maplibre-gl";
  import "maplibre-gl/dist/maplibre-gl.css";
  import { Protocol } from "pmtiles";
  import { resolveSource, type BoundaryEntry } from "./sources";
  import { diagonalHatch } from "./hatch";

  interface FeatureSelection {
    /** Join-key value (string for state name, number for AC_NO). */
    key: string | number;
    /** Raw GeoJSON properties of the clicked/hovered feature. */
    properties: Record<string, unknown>;
  }

  interface Props {
    entry: BoundaryEntry;
    /** key (from entry.join_property) → fill hex color. */
    fills: Record<string | number, string>;
    /** Optional per-feature opacity (0..1). */
    opacities?: Record<string | number, number>;
    /** Tooltip HTML by key. Plain text safe; HTML rendered as-is. */
    tooltips?: Record<string | number, string>;
    /** Default fill for features with no entry in `fills`. */
    default_fill?: string;
    /** CSS height; width fills the parent. */
    height?: string;
    /**
     * When set, the feature whose join-property value equals this key is
     * outlined with a thick contrasting stroke. Used to emphasise a single
     * focused feature (e.g. the current AC on the constituency drilldown).
     */
    highlight_key?: string | number;
    /**
     * When true, every feature whose join-key is NOT a key in `fills`
     * renders with a diagonal-hatch fill instead of `default_fill`. The
     * citizen-cartography convention for "no data here" — distinguishes
     * a missing measurement from the lowest choropleth bucket. Default
     * off for back-compat (existing consumers stay flat-filled).
     */
    hatch_unmapped?: boolean;
    /**
     * Recentre signal. Any change to this number (typically a monotonic
     * counter from the parent) triggers a re-fit to the data bounds.
     * Used by the drill-down breadcrumb's "re-click active crumb"
     * affordance — the user has panned/zoomed away and wants to snap
     * back to the current layer's extent. Initial mount is NOT a
     * recentre (the load handler already fits bounds).
     */
    recentre_signal?: number;
    onSelect?: (sel: FeatureSelection) => void;
    onHover?: (sel: FeatureSelection | null) => void;
  }

  let {
    entry,
    fills,
    opacities = {},
    tooltips = {},
    default_fill = "#e2e8f0", // slate-200 — visible but unobtrusive
    height = "420px",
    highlight_key,
    hatch_unmapped = false,
    recentre_signal,
    onSelect,
    onHover,
  }: Props = $props();

  let container: HTMLDivElement;
  let error = $state<string | null>(null);
  let loading = $state(true);

  // Map + popup handles. Typed loosely to avoid pulling maplibre-gl types
  // into every consumer.
  let map: any = null;
  let popup: any = null;
  // Cached bbox of the loaded data so the resize observer can re-fit
  // without re-fetching the GeoJSON.
  let data_bbox: [[number, number], [number, number]] | null = null;
  let resize_obs: ResizeObserver | null = null;
  // Module-level guard so we only register the pmtiles protocol once per page.
  let pmtiles_registered = false;

  const FILL_LAYER_ID = "yen-fill";
  const FILL_HATCH_LAYER_ID = "yen-fill-hatch";
  const HATCH_IMAGE_ID = "yen-hatch";
  const LINE_LAYER_ID = "yen-line";
  const HIGHLIGHT_LAYER_ID = "yen-highlight";
  // Halo layer drawn beneath HIGHLIGHT_LAYER_ID so the slate-900 stroke
  // reads against any underlying fill colour (UX review P1-3 — without
  // the halo, dark strokes on dark choropleth fills are hard to spot).
  const HIGHLIGHT_HALO_LAYER_ID = "yen-highlight-halo";
  const SOURCE_ID = "yen-src";

  // Build a maplibre `match` expression from the fills map. Numeric keys
  // (AC_NO) and string keys (state names) both work because `match` does
  // strict equality. Empty fills → no expression, paint stays at default.
  //
  // Property-type wrinkle: the upstream HTL shapefiles vary in whether
  // AC_NO is exported as a number or a string ("2" vs 2). `["match"]` does
  // strict equality, so a numeric key never matches a string property
  // (causing every polygon to fall through to default_fill — looks blank).
  // When the caller's keys all parse as integers we coerce the property
  // with `["to-number"]` so both shapes resolve. ST_NM (state name) is
  // genuinely a string, so the coercion is gated on the key kind.
  function keys_are_numeric(keys: string[]): boolean {
    return keys.length > 0 && keys.every(k => /^-?\d+$/.test(k));
  }

  function get_join_value(numeric: boolean): unknown {
    return numeric
      ? ["to-number", ["get", entry.join_property]]
      : ["get", entry.join_property];
  }

  function fill_expression(): unknown {
    const keys = Object.keys(fills);
    if (keys.length === 0) return default_fill;
    const numeric = keys_are_numeric(keys);
    const expr: unknown[] = ["match", get_join_value(numeric)];
    for (const k of keys) {
      const join_key: string | number = numeric ? Number(k) : k;
      expr.push(join_key, fills[k]);
    }
    expr.push(default_fill);
    return expr;
  }

  function opacity_expression(): unknown {
    const keys = Object.keys(opacities);
    if (keys.length === 0) return 0.85;
    const numeric = keys_are_numeric(keys);
    const expr: unknown[] = ["match", get_join_value(numeric)];
    for (const k of keys) {
      const join_key: string | number = numeric ? Number(k) : k;
      expr.push(join_key, opacities[k]);
    }
    expr.push(0.5); // default for unmatched
    return expr;
  }

  function highlight_filter(): unknown[] {
    // Filter expression that matches only the focused feature, or nothing
    // when no highlight is set. Same numeric/string wrinkle as above.
    if (highlight_key === undefined || highlight_key === null) {
      return ["==", ["literal", 1], ["literal", 0]]; // always-false
    }
    const k_str = String(highlight_key);
    const numeric = /^-?\d+$/.test(k_str);
    const join_key: string | number = numeric ? Number(k_str) : k_str;
    return ["==", get_join_value(numeric), join_key];
  }

  function hatch_filter(): unknown[] {
    // The hatch layer covers features whose join-key is NOT in fills.
    // Always-false when hatch_unmapped is off OR fills is empty (nothing
    // to "exclude from", so nothing to hatch — every feature is unmapped
    // and the citizen would see hatching everywhere, which is noise).
    if (!hatch_unmapped) return ["==", ["literal", 1], ["literal", 0]];
    const keys = Object.keys(fills);
    if (keys.length === 0) return ["==", ["literal", 1], ["literal", 0]];
    const numeric = keys_are_numeric(keys);
    const literal_keys = keys.map(k => (numeric ? Number(k) : k));
    return ["!", ["in", get_join_value(numeric), ["literal", literal_keys]]];
  }

  function repaint(): void {
    if (!map || !map.getLayer(FILL_LAYER_ID)) return;
    map.setPaintProperty(FILL_LAYER_ID, "fill-color", fill_expression());
    map.setPaintProperty(FILL_LAYER_ID, "fill-opacity", opacity_expression());
    const f = highlight_filter();
    if (map.getLayer(HIGHLIGHT_HALO_LAYER_ID)) {
      map.setFilter(HIGHLIGHT_HALO_LAYER_ID, f);
    }
    if (map.getLayer(HIGHLIGHT_LAYER_ID)) {
      map.setFilter(HIGHLIGHT_LAYER_ID, f);
    }
    if (map.getLayer(FILL_HATCH_LAYER_ID)) {
      map.setFilter(FILL_HATCH_LAYER_ID, hatch_filter());
    }
  }

  // Recompute paint expressions on any prop change. Cheap — just a few
  // setPaintProperty calls, no source reload.
  $effect(() => {
    void fills;
    void opacities;
    void highlight_key;
    void hatch_unmapped;
    repaint();
  });

  // Recentre on signal change. The first observed value is the initial
  // mount — the load handler already fits bounds, so we skip it. Any
  // subsequent change re-fits to the cached data_bbox (no re-fetch).
  let _last_recentre_signal: number | undefined = undefined;
  let _seen_first_signal = false;
  $effect(() => {
    const sig = recentre_signal;
    if (!_seen_first_signal) {
      _seen_first_signal = true;
      _last_recentre_signal = sig;
      return;
    }
    if (sig === _last_recentre_signal) return;
    _last_recentre_signal = sig;
    if (map && data_bbox) {
      map.fitBounds(data_bbox as any, { padding: 16, animate: true, duration: 400 });
    }
  });

  onMount(() => {
    let cancelled = false;

    (async () => {
      try {
        const resolved = await resolveSource(entry);
        if (cancelled) return;

        // PMTiles path requires registering the protocol shim once per page.
        if (resolved.kind === "pmtiles" && !pmtiles_registered) {
          const proto = new Protocol();
          maplibregl.addProtocol("pmtiles", proto.tile);
          pmtiles_registered = true;
        }

        // Style: minimal — no basemap tiles. Election polygons are the
        // primary content; a noisy basemap dilutes them and adds an
        // external dependency we don't want for a static deploy.
        // Cast to `any` because the conditional source/layer shapes don't
        // narrow to maplibre's StyleSpecification union without verbose
        // discriminator boilerplate that adds nothing here.
        const style: any = {
          version: 8 as const,
          sources: {
            [SOURCE_ID]:
              resolved.kind === "pmtiles"
                ? {
                    type: "vector",
                    url: resolved.url,
                  }
                : {
                    type: "geojson",
                    data: resolved.url,
                  },
          },
          layers: [
            {
              id: "bg",
              type: "background",
              paint: { "background-color": "#f8fafc" }, // slate-50
            },
            {
              id: FILL_LAYER_ID,
              type: "fill",
              source: SOURCE_ID,
              ...(resolved.kind === "pmtiles"
                ? { "source-layer": resolved.source_layer! }
                : {}),
              paint: {
                "fill-color": fill_expression(),
                "fill-opacity": opacity_expression(),
              },
            },
            // Hatched overlay for "no data" polygons (Phase 4 d1). Drawn
            // above the flat fill, below lines/highlight. Filtered to
            // never paint when hatch_unmapped=false (back-compat).
            {
              id: FILL_HATCH_LAYER_ID,
              type: "fill",
              source: SOURCE_ID,
              ...(resolved.kind === "pmtiles"
                ? { "source-layer": resolved.source_layer! }
                : {}),
              filter: hatch_filter(),
              paint: {
                "fill-pattern": HATCH_IMAGE_ID,
                "fill-opacity": 0.85,
              },
            },
            {
              id: LINE_LAYER_ID,
              type: "line",
              source: SOURCE_ID,
              ...(resolved.kind === "pmtiles"
                ? { "source-layer": resolved.source_layer! }
                : {}),
              paint: {
                "line-color": "#475569", // slate-600
                "line-width": 0.4,
              },
            },
            // Highlight = double-stroke (white halo + slate-900 inner) so
            // the focused feature reads against any choropleth fill colour.
            // UX review P1-3: a single dark stroke on a dark fill was easy
            // to miss; the white halo gives a guaranteed luminance contrast.
            // Filter is rebuilt on highlight_key change via repaint().
            {
              id: HIGHLIGHT_HALO_LAYER_ID,
              type: "line",
              source: SOURCE_ID,
              ...(resolved.kind === "pmtiles"
                ? { "source-layer": resolved.source_layer! }
                : {}),
              filter: highlight_filter(),
              paint: {
                "line-color": "#ffffff",
                "line-width": 5,
                "line-opacity": 0.9,
              },
            },
            {
              id: HIGHLIGHT_LAYER_ID,
              type: "line",
              source: SOURCE_ID,
              ...(resolved.kind === "pmtiles"
                ? { "source-layer": resolved.source_layer! }
                : {}),
              filter: highlight_filter(),
              paint: {
                "line-color": "#0f172a", // slate-900
                "line-width": 2.5,
              },
            },
          ],
        };

        map = new maplibregl.Map({
          container,
          style,
          attributionControl: {
            compact: true,
            // Append a single "About these maps" link so the disclaimer lives
            // alongside the upstream attribution. Previously we rendered a
            // duplicate top-right badge for the same purpose; merging into
            // the maplibre control gives one info surface, not two.
            customAttribution:
              entry.attribution +
              ' · <a href="' + (import.meta.env.BASE_URL.replace(/\/$/, "") + "/about?section=maps") + '">About these maps</a>',
          },
          // Bounds get computed from the loaded data on first idle.
          center: [80, 22],
          zoom: 3,
          dragRotate: false,
          pitchWithRotate: false,
          // Suppress horizontal world wrap. Without this, at low zoom (the
          // brief moment between map.create() and fitBounds(), and any time
          // the user shrinks the viewport so the data fits in less than a
          // world width) Mercator paints multiple copies of every polygon
          // marching across the canvas — users read this as "the map is
          // rotating" or "there are tiny duplicate states". Subnational
          // choropleths never need world wrap, so we turn it off globally
          // for this component.
          renderWorldCopies: false,
          // Cooperative gestures: scroll-wheel without Ctrl/Cmd scrolls
          // the page, not the map; one-finger drag on touch pans the page,
          // two-finger drag pans the map. Citizen-review feedback ("the
          // map fights my scroll") + standard practice on long-form pages
          // that embed maps. Maplibre renders an instructional overlay
          // automatically when the user attempts a non-cooperative gesture.
          cooperativeGestures: true,
        });
        map.touchZoomRotate.disableRotation();

        popup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          className: "yen-map-popup",
          maxWidth: "260px",
          offset: 8,
        });

        map.on("load", () => {
          // Register the hatch pattern as a maplibre image. Done inside the
          // load handler so the style is ready; the FILL_HATCH_LAYER_ID
          // layer references this image via fill-pattern. Idempotent
          // (hasImage guards re-registration if a parent re-mounts).
          if (!map.hasImage(HATCH_IMAGE_ID)) {
            const h = diagonalHatch();
            map.addImage(HATCH_IMAGE_ID, { width: h.width, height: h.height, data: h.data });
          }
          // Fit bounds to the data extent. For GeoJSON we have it locally;
          // for vector tiles maplibre exposes querySourceFeatures only for
          // visible tiles, which isn't enough — fall back to the same bbox
          // we'd compute from the GeoJSON. Phase 1d ships only the GeoJSON
          // path; PMTiles bounds will be solved when the manifest carries
          // them (planned in tools/boundaries/build.py).
          if (resolved.kind === "geojson") {
            fetch(resolved.url)
              .then(r => r.json())
              .then(gj => {
                const b = bbox(gj);
                if (b) {
                  data_bbox = b;
                  map.fitBounds(b as any, { padding: 16, animate: false });
                  // Refit whenever the canvas resizes (browser zoom,
                  // sidebar toggle, window resize). Without this, the
                  // initial fit is correct but a subsequent resize leaves
                  // TN as a tiny shape stranded in a now-larger canvas.
                  // We debounce via rAF so we don't refit mid-layout
                  // (the page reflows multiple times during initial load
                  // and each intermediate size triggered a stale fit
                  // that then "stuck" once the canvas settled). We also
                  // skip zero-sized callbacks since maplibre's first
                  // observed size is often 0×0 before mount.
                  if (typeof ResizeObserver !== "undefined" && container) {
                    let rAF = 0;
                    resize_obs = new ResizeObserver((entries) => {
                      const cr = entries[0]?.contentRect;
                      if (!cr || cr.width < 4 || cr.height < 4) return;
                      if (rAF) cancelAnimationFrame(rAF);
                      rAF = requestAnimationFrame(() => {
                        if (map && data_bbox) {
                          map.resize();
                          map.fitBounds(data_bbox as any, { padding: 16, animate: false });
                        }
                      });
                    });
                    resize_obs.observe(container);
                  }
                }
              })
              .catch(() => {
                // Bounds are nice-to-have; rendering still works at the
                // default center/zoom if the bbox fetch fails.
              });
          }
          loading = false;
        });

        map.on("error", (ev: any) => {
          // maplibre fires noisy errors for missing tiles at world zoom;
          // surface only the first to the user, log the rest.
          if (!error) error = String(ev.error?.message ?? ev.error ?? "map error");
          // eslint-disable-next-line no-console
          console.warn("[map]", ev.error);
        });

        map.on("mousemove", FILL_LAYER_ID, (e: any) => {
          const f = e.features?.[0];
          if (!f) return;
          map.getCanvas().style.cursor = "pointer";
          const key = f.properties?.[entry.join_property];
          const html = tooltips[key];
          if (html) {
            popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
          } else {
            popup.remove();
          }
          onHover?.({ key, properties: f.properties ?? {} });
        });
        map.on("mouseleave", FILL_LAYER_ID, () => {
          map.getCanvas().style.cursor = "";
          popup.remove();
          onHover?.(null);
        });
        map.on("click", FILL_LAYER_ID, (e: any) => {
          const f = e.features?.[0];
          if (!f) return;
          const key = f.properties?.[entry.join_property];
          // UX review P0-3: touch devices don't fire `mousemove`, so the
          // hover-only popup never appeared on phones/tablets. Show the
          // popup on click as well — desktop users get it on hover and
          // again on click (idempotent), touch users get it on tap.
          const html = tooltips[key];
          if (html && popup) {
            popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
          }
          onSelect?.({ key, properties: f.properties ?? {} });
        });
      } catch (e) {
        if (!cancelled) {
          error = String(e);
          loading = false;
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  });

  onDestroy(() => {
    if (resize_obs) resize_obs.disconnect();
    if (popup) popup.remove();
    if (map) map.remove();
  });

  // Compute a [[w,s],[e,n]] bbox from a GeoJSON FeatureCollection. Iterates
  // every coordinate; fast enough for a few thousand features and avoids
  // pulling in @turf/bbox just for one helper.
  function bbox(gj: any): [[number, number], [number, number]] | null {
    let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    function visit(c: any): void {
      if (typeof c[0] === "number") {
        if (c[0] < minx) minx = c[0];
        if (c[0] > maxx) maxx = c[0];
        if (c[1] < miny) miny = c[1];
        if (c[1] > maxy) maxy = c[1];
        return;
      }
      for (const child of c) visit(child);
    }
    const feats = gj.features ?? (gj.type === "Feature" ? [gj] : []);
    for (const f of feats) {
      if (f?.geometry?.coordinates) visit(f.geometry.coordinates);
    }
    if (!isFinite(minx)) return null;
    return [[minx, miny], [maxx, maxy]];
  }
</script>

<div class="relative w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50" style:height>
  <!--
    Container is absolute-positioned to fill the wrapper. We set height/width
    inline rather than relying on Tailwind's `absolute inset-0`, because
    maplibre-gl.css declares `.maplibregl-map { position: relative }` which
    overrides Tailwind's `absolute` once maplibre adds its class on init,
    collapsing the box to 0 height.
  -->
  <div bind:this={container} style="position:absolute;inset:0;width:100%;height:100%;"></div>
  {#if loading}
    <div class="absolute inset-0 flex items-center justify-center text-xs text-slate-500 pointer-events-none">
      Loading map…
    </div>
  {/if}
  {#if error}
    <div class="absolute inset-x-2 bottom-2 p-2 text-xs bg-rose-50 border border-rose-200 rounded text-rose-900">
      Map error: <code>{error}</code>
    </div>
  {/if}
</div>

<style>
  /* maplibre's default popup styling is heavier than we want; flatten it. */
  :global(.yen-map-popup .maplibregl-popup-content) {
    padding: 6px 10px;
    border-radius: 6px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.08);
    font-size: 12px;
    line-height: 1.35;
  }
  :global(.yen-map-popup .maplibregl-popup-tip) {
    display: none;
  }
</style>
