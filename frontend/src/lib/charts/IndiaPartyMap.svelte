<script lang="ts">
  /**
   * IndiaPartyMap - the d3-geo SVG choropleth that replaces the
   * MapLibre-based `IndiaMap.svelte` on the Home page (PR-4 of
   * `TODO/20260611-elections-off-maplibre-and-map-ux-plan.md`) and
   * the per-event national choropleth in NationalElection.svelte
   * (PR-4b of the same plan).
   *
   * Preserves every behaviour from the legacy component:
   *
   *   - Per-state fill from the leading-party palette via
   *     `loadIndiaLeadingParties` (loader signature unchanged).
   *   - Hover tooltip with state name + top-3 party seats + event id
   *     (HTML overlay positioned at the mouse pointer).
   *   - Click a state polygon -> default `navigate(link.state(eci_code))`
   *     (state hub) OR, when the consumer supplies the PR-4c
   *     `onSelect` prop, the prop fires with the ECI code so the
   *     consumer can route however it wants (e.g. NationalElection
   *     stays in the per-event cohort via `link.stateElection`).
   *   - Per-state party colour resolution via `resolvePartyPalette` +
   *     `getPartyColor` from `lib/colors/resolver.ts`.
   *   - Optional `event?: string` prop forces every state into one
   *     cohort (used by cohort-comparison views).
   *
   * Two consumers as of PR-4b/4c:
   *   - `routes/Home.svelte` (PR-4) - bare `<IndiaPartyMap />`,
   *     no props. Click navigates to `/<state>` (state hub).
   *   - `routes/NationalElection.svelte` (PR-4b) -
   *     `<IndiaPartyMap event={event} onSelect={(code) =>
   *     navigate(link.stateElection(code, event))} />`. Click
   *     navigates to `/<state>/elections/<event>` so the citizen
   *     stays in the same election cohort instead of falling out
   *     to the state hub's default-event resolver. Default behaviour
   *     (Home) is unchanged because Home does not pass the prop.
   *
   * Adds two citizen-named UX gaps (verified in PR-alpha against
   * IndiaVotes + Bharat Pashudhan + data-analytics; see
   * `docs/architecture/frontend/map.md` "Comparable Indian civic
   * sites"):
   *
   *   - Pan / zoom / pinch via d3-zoom on the SVG (scroll-wheel
   *     zooms without Ctrl; touch drag pans; pinch zooms).
   *   - Absolute-positioned `+` / `-` / `home` button trio over the
   *     SVG (same Tailwind classes the PR-1 MapChoropleth buttons
   *     use, for visual consistency).
   *
   * The PR-4c click-action resolver lives in
   * `india-party-map-helpers.ts` (sibling module) so vitest can cover
   * it without mounting the Svelte component (repo vitest doctrine).
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
  import { fetchGeometryJson } from "./geometry-cache";
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
    resolveStateClickAction,
    computeIslandMarker,
    hasNoDataFeature,
    type IslandMarker,
  } from "./india-party-map-helpers";
  import MapFrameSkeleton from "../MapFrameSkeleton.svelte";

  interface Props {
    /** Force every state to a single cohort. When omitted, each state's
     *  own default event from the catalogue is used (the Home-page case). */
    event?: string;
    /** Optional click-navigation override. When supplied, the prop is
     *  invoked with the clicked state's ECI code instead of the default
     *  `navigate(link.state(code))`. Used by NationalElection.svelte to
     *  stay in the per-event cohort (`link.stateElection(code, event)`).
     *  When omitted (Home page), default behaviour applies. */
    onSelect?: (eciCode: string) => void;
  }
  let { event, onSelect: onSelectProp }: Props = $props();

  // Hand-pinned constants - the combined country topojson's `states`
  // object carries the same `State_LGD` join key the deleted
  // states/all.topojson did (Row 2 map-geometry rip: country/all.topojson
  // is the sole surviving topojson).
  const TOPOJSON_PATH = "/boundaries/in/country/all.topojson";
  // Responsive fit: project to the measured container width (clamped to
  // MAX_MAP_W so a 4K viewport does not produce a giant hero); the SVG
  // height derives from the projected content bounds (no letterboxing).
  const MAX_MAP_W = 1200;
  const JOIN_PROPERTY = "State_LGD";
  // No-data fill: the same subtle gray dot-grid the welfare choropleth
  // (GeoChoropleth) paints for no-data regions, so the two home themes
  // (Winning party / welfare indicator) show "no data" the same way.
  // Defined as an SVG <pattern> inside the <svg> below; states with no
  // loaded winner (e.g. J&K, Ladakh) and any feature missing a join key
  // fall through to it instead of the prior flat slate-200. Paired with
  // the "No data" chip under the map so the idiom is self-explanatory.
  const NO_DATA_FILL = "url(#india-party-map-nodata)";

  // Measured wrapper width (px) driving the responsive projection. Starts
  // 0 before first layout; the projection falls back to 640 until the
  // wrapper's bind:clientWidth reports a real width.
  let container_w = $state(0);

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
        result = await loadIndiaLeadingParties(state_event_map, catalogue);
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
        // Row 3b: fetchGeometryJson caches the fetched + parsed country
        // topojson per URL (throws on a non-OK status, caught below) so
        // revisiting the home map does not re-download it.
        const topo = (await fetchGeometryJson(url)) as Topology;
        // The combined country topojson carries TWO objects (`states` +
        // `districts`); decode the NAMED `states` object - objectKeys[0]
        // would be ambiguous and could yield the 785-district layer.
        const states_object = topo.objects?.states;
        if (!states_object) {
          load_error = `country topojson missing 'states' object: ${url}`;
          return;
        }
        const fc = topojsonFeature(
          topo,
          states_object as GeometryCollection,
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
    const obj = collection as GeoPermissibleObjects;
    const eff_w = Math.min(container_w || 640, MAX_MAP_W);
    const projection: GeoProjection = geoMercator().fitWidth(eff_w, obj);
    // fitWidth anchors the content near x=0 but can leave a top offset;
    // re-translate so the projected extent starts at (0,0) and the SVG
    // height can equal the content height (no letterboxing).
    const pre = geoPath(projection).bounds(obj);
    const [tx, ty] = projection.translate();
    projection.translate([tx - pre[0][0], ty - pre[0][1]]);
    const path = geoPath(projection);
    const b = path.bounds(obj);
    const w = Math.max(1, Math.ceil(b[1][0]));
    const h = Math.max(1, Math.ceil(b[1][1]));
    return { projection, path, w, h };
  });

  // Wrapper aspect-ratio: the projected content w/h once the collection
  // loads, a neutral 640/480 default during the loading / error window so
  // the placeholder reserves space (no layout shift when the map paints).
  const wrapper_aspect = $derived(
    projection_path ? `${projection_path.w}/${projection_path.h}` : "640/480",
  );

  // Lakshadweep collapses to a ~2-3 px dot at the national fit; paint a
  // small clickable square at its centroid so it stays citizen-visible.
  // Scoped by name to the one far-flung island - no mainland state is
  // ever marked.
  const lakshadweep_marker = $derived<IslandMarker | null>(
    !collection || !projection_path
      ? null
      : computeIslandMarker(
          collection.features,
          projection_path.projection,
          projection_path.path,
          (f) => f.properties?.[JOIN_PROPERTY],
          (f) => String(f.properties?.STNAME ?? ""),
          /laksh/i,
        ),
  );

  function fillForKey(key: string): string {
    return fills[key] ?? NO_DATA_FILL;
  }

  // True once the loader has settled AND at least one rendered feature
  // has no loaded winner (so it paints the no-data dot-grid). Drives the
  // "No data" chip below the map. Gated on `result.status === "ok"` so
  // the chip does not flash during the load window (when `fills` is
  // still empty and every state would momentarily read as no-data).
  const has_no_data = $derived.by<boolean>(() =>
    collection != null &&
    result.status === "ok" &&
    hasNoDataFeature(
      collection.features,
      fills,
      (f) => f.properties?.[JOIN_PROPERTY],
    ),
  );

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

  function handleStateClick(key: string): void {
    const action = resolveStateClickAction(
      key,
      KEY_TO_ECI,
      onSelectProp != null,
    );
    switch (action.kind) {
      case "callback":
        onSelectProp?.(action.eciCode);
        return;
      case "navigate-default":
        navigate(link.state(action.eciCode));
        return;
      case "noop":
        return;
    }
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
  bind:clientWidth={container_w}
  class="relative w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
  style="aspect-ratio:{wrapper_aspect};"
  data-component="india-party-map"
>
  {#if load_error}
    <div class="absolute inset-x-2 bottom-2 p-2 text-xs bg-rose-50 border border-rose-200 rounded text-rose-900">
      Map error: <code>{load_error}</code>
    </div>
  {:else if !collection || !projection_path}
    <div class="absolute inset-0">
      <MapFrameSkeleton height="100%" />
    </div>
  {:else}
    <svg
      bind:this={svg_el}
      class="block w-full cursor-grab active:cursor-grabbing"
      viewBox="0 0 {projection_path.w} {projection_path.h}"
      width="100%"
      style="height:auto; aspect-ratio:{projection_path.w}/{projection_path.h};"
    >
      <defs>
        <!-- No-data dot-grid (matches GeoChoropleth's
             #geo-choropleth-nodata): a subtle gray dot tile painted
             behind states with no loaded winner. Same visual language
             as the welfare map so the citizen reads "no data" the same
             way across both home themes. -->
        <pattern
          id="india-party-map-nodata"
          width="8"
          height="8"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <rect width="8" height="8" fill="#f8fafc" />
          <circle cx="4" cy="4" r="0.9" fill="#cbd5e1" fill-opacity="0.5" />
        </pattern>
      </defs>
      <g bind:this={zoom_group_el}>
        {#each collection.features as f, i (f.properties?.[JOIN_PROPERTY] ?? i)}
          {@const raw_key = f.properties?.[JOIN_PROPERTY]}
          {@const key = raw_key == null ? null : String(raw_key)}
          <path
            d={projection_path.path(f) ?? ""}
            fill={key ? fillForKey(key) : NO_DATA_FILL}
            stroke="#cbd5e1"
            stroke-width="0.5"
            class="india-party-map__feature"
            data-state-code={key ?? ""}
            data-state-name={String(f.properties?.STNAME ?? "")}
            onmouseenter={(e) => key && onFeatureEnter(e, key)}
            onmousemove={onFeatureMove}
            onmouseleave={onFeatureLeave}
            onclick={() => key && handleStateClick(key)}
          />
        {/each}

        {#if lakshadweep_marker}
          {@const m = lakshadweep_marker}
          <rect
            x={m.cx - 6}
            y={m.cy - 6}
            width={12}
            height={12}
            fill={fillForKey(m.key)}
            stroke="#0f172a"
            stroke-width="1.25"
            class="india-party-map__island-marker"
            data-state-code={m.key}
            data-marker="island"
            onmouseenter={(e) => onFeatureEnter(e, m.key)}
            onmousemove={onFeatureMove}
            onmouseleave={onFeatureLeave}
            onclick={() => handleStateClick(m.key)}
          />
        {/if}
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

{#if has_no_data}
  <!--
    No-data chip - mirrors GeoChoropleth's `data-slot="nodata-key"` so
    the election map and the welfare maps surface "no data" identically.
    The swatch reuses the same dot-grid (#f8fafc base + #cbd5e1 dots) as
    the in-map <pattern> above. Only shown once the loader settles and a
    no-data state is actually painted.
  -->
  <div
    class="mt-2 inline-flex items-center gap-1.5 text-[11px] text-slate-500"
    data-slot="nodata-key"
  >
    <span
      class="inline-block h-3.5 w-3.5 rounded-[3px] border border-slate-200"
      style="background-color:#f8fafc;background-image:radial-gradient(rgba(203,213,225,0.5) 0.9px, transparent 1.1px);background-size:4px 4px;"
      aria-hidden="true"
    ></span>
    No data
  </div>
{/if}
