<script lang="ts">
  /**
   * IndiaPartyMap - the d3-geo SVG choropleth that replaces the
   * MapLibre-based `IndiaMap.svelte` on the Home page (PR-4 of
   * `TODO/20260611-elections-off-maplibre-and-map-ux-plan.md`).
   *
   * Preserves every behaviour from the legacy component:
   *
   *   - Per-state fill from the leading-party palette via
   *     `loadIndiaLeadingParties` (loader signature unchanged).
   *   - Hover tooltip with state name + top-3 party seats + event id
   *     (HTML overlay positioned at the mouse pointer).
   *   - Click a state polygon -> navigate(link.state(eci_code)).
   *   - Per-state party colour resolution via `resolvePartyPalette` +
   *     `getPartyColor` from `lib/colors/resolver.ts`.
   *   - Optional `event?: string` prop forces every state into one
   *     cohort (used by cohort-comparison views).
   *
   * Adds three citizen-named UX gaps (verified in PR-alpha against
   * IndiaVotes + Bharat Pashudhan + data-analytics; see
   * `docs/architecture/frontend/map.md` "Comparable Indian civic
   * sites"):
   *
   *   - Pan / zoom / pinch via d3-zoom on the SVG (scroll-wheel
   *     zooms without Ctrl; touch drag pans; pinch zooms).
   *   - Absolute-positioned `+` / `-` / `home` button trio over the
   *     SVG (same Tailwind classes the PR-1 MapChoropleth buttons
   *     use, for visual consistency).
   *   - Sub-threshold marker overlay: any state whose path bbox is
   *     below SUB_THRESHOLD_PX (14 px at 640x480 viewBox) gets a
   *     `<circle r=7>` at the projected centroid carrying the SAME
   *     fill / tooltip / click handler as the polygon. Closes the
   *     citizen-named "users can't see Lakshadweep" pain (live
   *     MapLibre map returns 0 hover hits in a bottom-left ocean
   *     sweep; PR-4 oracle is >= 1 hit).
   *
   * The pure marker-computation helpers live in
   * `india-party-map-helpers.ts` (sibling module) so vitest can
   * cover them against the real `states/all.topojson` without
   * mounting the Svelte component (repo vitest doctrine).
   *
   * MapLibre `IndiaMap.svelte` is deliberately NOT deleted here -
   * PR-6 deletes the entire `lib/maplibre/` directory after PR-5
   * also retires `StateAcMap.svelte`. Keeping it intact during the
   * transition lets any straggling consumer keep working.
   */

  import { onMount } from "svelte";
  import {
    geoMercator,
    geoPath,
    type GeoProjection,
    type GeoPermissibleObjects,
  } from "d3-geo";
  import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
  import { select } from "d3-selection";
  import { feature as topojsonFeature } from "topojson-client";
  import type { Topology, GeometryCollection } from "topojson-specification";
  import type {
    FeatureCollection,
    Geometry,
    GeoJsonProperties,
  } from "geojson";

  import { DATA_BASE } from "../paths";
  import { loadStates } from "../view-models/states";
  import {
    loadIndiaLeadingParties,
    type IndiaLeadingPartiesViewModel,
  } from "../view-models/legacy/india-leading-parties";
  import type { LoaderResult } from "../loader-result";
  import {
    defaultEventForState,
    fetchElectionEvents,
  } from "../election-events";
  import { getPartyColor, resolvePartyPalette } from "../colors/resolver";
  import type { PartyRowForResolver } from "../colors/resolver";
  import type { PartyTotals } from "../data";
  import { navigate } from "../url";
  import { link } from "../links";
  import {
    SUB_THRESHOLD_PX,
    computeSubThresholdMarkers,
    type MarkerOverlay,
  } from "./india-party-map-helpers";

  interface Props {
    /** Force every state to a single cohort. When omitted, each state's
     *  own default event from the catalogue is used (the Home-page case). */
    event?: string;
  }
  let { event }: Props = $props();

  // Hand-pinned constants - the same join property + topojson the
  // legacy MapChoropleth + INDIA_STATES entry consumed. The viewBox is
  // matched against `india-party-map-helpers`'s SUB_THRESHOLD_PX
  // calibration; changing one without the other re-tunes which UTs
  // get a marker.
  const TOPOJSON_PATH = "/boundaries/in/states/all.topojson";
  const WIDTH = 640;
  const HEIGHT = 480;
  const JOIN_PROPERTY = "State_LGD";
  // slate-200; same default fill the MapChoropleth used for unmapped
  // features - visible but unobtrusive against the page background.
  const DEFAULT_FILL = "#e2e8f0";

  // -----------------------------------------------------------------
  // Loader plumbing (lifted verbatim from the legacy IndiaMap.svelte
  // so the data-flow contract stays identical).
  // -----------------------------------------------------------------

  let result = $state<LoaderResult<IndiaLeadingPartiesViewModel>>({
    status: "loading",
  });
  let states_taxonomy = $state<import("../view-models/states").StateRow[] | null>(
    null,
  );
  loadStates()
    .then((s) => (states_taxonomy = s))
    .catch(() => (states_taxonomy = []));

  // Reverse lookup boundary-join-KEY (LGD code post-D.0) -> ECI used by
  // on_select.
  const KEY_TO_ECI = $derived.by(() => {
    const out: Record<string, string> = {};
    for (const s of states_taxonomy ?? [])
      out[s.boundary_join_key] = s.eci_code;
    return out;
  });

  function retryLoad(): void {
    const force_event = event;
    result = { status: "loading" };
    (async () => {
      try {
        const [catalogue, taxonomy] = await Promise.all([
          fetchElectionEvents(),
          loadStates(),
        ]);
        const state_event_map: Record<string, string> = {};
        for (const s of taxonomy) {
          const code = s.eci_code;
          const ev =
            force_event ?? defaultEventForState(catalogue, code)?.event_id;
          if (ev) state_event_map[code] = ev;
        }
        result = await loadIndiaLeadingParties(state_event_map);
      } catch (err) {
        result = {
          status: "failed",
          reason: String(err),
          retry: retryLoad,
        };
      }
    })();
  }

  $effect(() => {
    void event;
    retryLoad();
  });

  function partyIdFor(p: PartyTotals): string {
    if (p.party_id) return p.party_id;
    const slug = (p.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  }

  function rowFor(p: PartyTotals): PartyRowForResolver | null {
    if (p.brand_colour_hex == null) return null;
    return {
      party_id: partyIdFor(p),
      eci_code: p.party_eci_code,
      brand_colour: {
        hex: p.brand_colour_hex,
        confidence: p.brand_colour_confidence ?? "medium",
      },
    };
  }

  const fills = $derived.by(() => {
    const out: Record<string, string> = {};
    if (result.status !== "ok") return out;
    const per_state = result.data.per_state;
    const tops: { join_key: string; party: PartyTotals }[] = [];
    for (const s of states_taxonomy ?? []) {
      const code = s.eci_code;
      const loaded = per_state[code];
      if (!loaded) continue;
      const top = loaded.party_totals.find((p) => p.seats_won > 0);
      if (top) tops.push({ join_key: s.boundary_join_key, party: top });
    }
    const ids = tops.map((t) => partyIdFor(t.party));
    const rows = new Map<string, PartyRowForResolver | null>();
    for (const t of tops) rows.set(partyIdFor(t.party), rowFor(t.party));
    const palette = resolvePartyPalette(ids, rows);
    for (const t of tops) {
      const pid = partyIdFor(t.party);
      out[t.join_key] =
        palette.get(pid)?.hex ?? getPartyColor(pid, rowFor(t.party)).hex;
    }
    return out;
  });

  const tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    const per_state = result.status === "ok" ? result.data.per_state : {};
    for (const s of states_taxonomy ?? []) {
      const code = s.eci_code;
      const display = s.boundary_join_name;
      const join_key = s.boundary_join_key;
      const loaded = per_state[code];
      if (!loaded) {
        out[join_key] =
          `<div class="font-semibold">${escape_html(display)}</div>` +
          `<div class="text-slate-500">no data loaded</div>`;
        continue;
      }
      const top = loaded.party_totals
        .filter((p) => p.seats_won > 0)
        .slice(0, 3);
      const rows = top
        .map(
          (p) =>
            `<div>${escape_html(p.party_short)} \u00b7 ${p.seats_won}</div>`,
        )
        .join("");
      out[join_key] =
        `<div class="font-semibold">${escape_html(display)} <span class="text-slate-400 font-mono text-[10px]">${code}</span></div>` +
        `<div class="text-slate-600">${rows}</div>` +
        `<div class="text-slate-400 text-[10px] mt-1">${escape_html(loaded.event_id)} \u00b7 click to open \u2192</div>`;
    }
    return out;
  });

  function escape_html(s: string): string {
    return s.replace(/[&<>"']/g, (c) =>
      c === "&" ? "&amp;" :
      c === "<" ? "&lt;" :
      c === ">" ? "&gt;" :
      c === '"' ? "&quot;" : "&#39;",
    );
  }

  // -----------------------------------------------------------------
  // Topojson load + projection + path.
  // -----------------------------------------------------------------

  let collection = $state<FeatureCollection<Geometry, GeoJsonProperties> | null>(
    null,
  );
  let load_error = $state<string | null>(null);

  onMount(() => {
    let cancelled = false;
    const url = `${DATA_BASE}${TOPOJSON_PATH}`;
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

  const projection_path = $derived.by(() => {
    if (!collection) return null;
    const projection: GeoProjection = geoMercator().fitSize(
      [WIDTH, HEIGHT],
      collection as GeoPermissibleObjects,
    );
    const path = geoPath(projection);
    return { projection, path };
  });

  // Sub-threshold marker overlays - second-pass <circle> targets for
  // states whose polygon collapses below SUB_THRESHOLD_PX.
  const marker_overlays = $derived<MarkerOverlay[]>(
    !collection || !projection_path
      ? []
      : computeSubThresholdMarkers(
          collection.features,
          projection_path.projection,
          projection_path.path,
          (f) =>
            (f.properties?.[JOIN_PROPERTY] as string | number | null) ?? null,
        ),
  );

  function fillForKey(key: string): string {
    return fills[key] ?? DEFAULT_FILL;
  }

  function tooltipForKey(key: string): string | null {
    return tooltips[key] ?? null;
  }

  // -----------------------------------------------------------------
  // Hover state (HTML overlay tooltip).
  // -----------------------------------------------------------------

  let hover_key = $state<string | null>(null);
  let hover_x = $state(0);
  let hover_y = $state(0);

  function onFeatureEnter(e: MouseEvent, key: string): void {
    hover_key = key;
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onFeatureMove(e: MouseEvent): void {
    hover_x = e.offsetX + 12;
    hover_y = e.offsetY + 12;
  }
  function onFeatureLeave(): void {
    hover_key = null;
  }

  function onSelect(key: string): void {
    const code = KEY_TO_ECI[key];
    if (code) navigate(link.state(code));
  }

  // -----------------------------------------------------------------
  // d3-zoom wiring.
  //
  // The SVG receives the zoom behaviour; the inner <g> carries the
  // transform. Scroll-wheel zooms without Ctrl (the d3-zoom default,
  // which is exactly the citizen-named UX gap PR-1 patched on
  // MapLibre + PR-4 carries forward here). Touch drag pans + pinch
  // zooms (d3-zoom dispatches both via the touchstart/touchmove
  // handlers it installs).
  //
  // Button-driven dispatches go through the same `zoom_behavior`
  // instance so the internal `__zoom` state stays in sync with the
  // gesture-driven path. We do NOT chain `.transition()` on the
  // button handlers - the gesture path is intentionally immediate
  // (no animated tween) so a citizen tapping `+` three times sees
  // the third-step result without an interrupted half-state. The
  // wheel path's own d3-zoom default tween still applies.
  // -----------------------------------------------------------------

  let svg_el = $state<SVGSVGElement | null>(null);
  let zoom_group_el = $state<SVGGElement | null>(null);
  let zoom_behavior: ZoomBehavior<SVGSVGElement, unknown> | null = null;

  $effect(() => {
    if (!svg_el || !zoom_group_el) return;
    const sel = select(svg_el);
    const z = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 12])
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

{#if result.status === "failed"}
  <div class="p-3 text-sm bg-rose-50 border border-rose-200 rounded text-rose-900">
    <p>Failed to load state summaries: {result.reason}</p>
    <button
      type="button"
      onclick={() => result.status === "failed" && result.retry?.()}
      class="mt-2 px-3 py-1 text-xs rounded bg-rose-100 hover:bg-rose-200"
    >Retry</button>
  </div>
{/if}

<div
  class="relative w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
  style="height: 520px;"
  data-component="india-party-map"
  data-threshold-px={SUB_THRESHOLD_PX}
>
  {#if load_error}
    <div class="absolute inset-x-2 bottom-2 p-2 text-xs bg-rose-50 border border-rose-200 rounded text-rose-900">
      Map error: <code>{load_error}</code>
    </div>
  {:else if !collection || !projection_path}
    <div class="absolute inset-0 flex items-center justify-center text-xs text-slate-500">
      Loading map...
    </div>
  {:else}
    <svg
      bind:this={svg_el}
      class="block w-full h-full cursor-grab active:cursor-grabbing"
      viewBox="0 0 {WIDTH} {HEIGHT}"
      preserveAspectRatio="xMidYMid meet"
    >
      <g bind:this={zoom_group_el}>
        {#each collection.features as f, i (f.properties?.[JOIN_PROPERTY] ?? i)}
          {@const raw_key = f.properties?.[JOIN_PROPERTY]}
          {@const key = raw_key == null ? null : String(raw_key)}
          <path
            d={projection_path.path(f) ?? ""}
            fill={key ? fillForKey(key) : DEFAULT_FILL}
            stroke="#cbd5e1"
            stroke-width="0.5"
            class="india-party-map__feature"
            data-state-code={key ?? ""}
            data-state-name={String(f.properties?.STNAME ?? "")}
            onmouseenter={(e) => key && onFeatureEnter(e, key)}
            onmousemove={onFeatureMove}
            onmouseleave={onFeatureLeave}
            onclick={() => key && onSelect(key)}
          />
        {/each}

        {#each marker_overlays as m (m.key)}
          <circle
            cx={m.cx}
            cy={m.cy}
            r={7}
            fill={fillForKey(m.key)}
            stroke="#0f172a"
            stroke-width="1"
            class="india-party-map__marker"
            data-state-code={m.key}
            data-marker="sub-threshold"
            onmouseenter={(e) => onFeatureEnter(e, m.key)}
            onmousemove={onFeatureMove}
            onmouseleave={onFeatureLeave}
            onclick={() => onSelect(m.key)}
          />
        {/each}
      </g>
    </svg>

    {#if hover_key && tooltipForKey(hover_key)}
      <div
        class="absolute pointer-events-none bg-white border border-slate-200 rounded shadow px-2 py-1 text-xs leading-tight max-w-xs"
        style="left: {hover_x}px; top: {hover_y}px;"
        data-testid="india-party-map-tooltip"
      >
        {@html tooltipForKey(hover_key) ?? ""}
      </div>
    {/if}

    <!--
      +/-/home button trio over the SVG. Same Tailwind classes as the
      PR-1 MapChoropleth buttons so the citizen sees one visual
      language across both renderer paths during the transition.
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
