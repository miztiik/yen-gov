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
  // Module-level guard so we only register the pmtiles protocol once per page.
  let pmtiles_registered = false;

  const FILL_LAYER_ID = "yen-fill";
  const LINE_LAYER_ID = "yen-line";
  const HIGHLIGHT_LAYER_ID = "yen-highlight";
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
  // with `["to-number"]` so both shapes resolve. NAME_1 (state name) is
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

  function repaint(): void {
    if (!map || !map.getLayer(FILL_LAYER_ID)) return;
    map.setPaintProperty(FILL_LAYER_ID, "fill-color", fill_expression());
    map.setPaintProperty(FILL_LAYER_ID, "fill-opacity", opacity_expression());
    if (map.getLayer(HIGHLIGHT_LAYER_ID)) {
      map.setFilter(HIGHLIGHT_LAYER_ID, highlight_filter());
    }
  }

  // Recompute paint expressions on any prop change. Cheap — just a few
  // setPaintProperty calls, no source reload.
  $effect(() => {
    void fills;
    void opacities;
    void highlight_key;
    repaint();
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
            // Highlight layer drawn on top so the focused feature reads first.
            // Filter is rebuilt on highlight_key change via repaint().
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
          attributionControl: { compact: true, customAttribution: entry.attribution },
          // Bounds get computed from the loaded data on first idle.
          center: [80, 22],
          zoom: 3,
          dragRotate: false,
          pitchWithRotate: false,
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
                if (b) map.fitBounds(b as any, { padding: 16, animate: false });
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
  <div bind:this={container} class="absolute inset-0"></div>
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
