<script lang="ts">
  // Generic indicator choropleth: drop in any indicator artifact under
  // `datasets/indicators/`, get a state-level map with time slider, legend,
  // tooltips, and source / license attribution. Driven entirely by the
  // metadata in the artifact's `indicator` block (value_kind, direction,
  // scale_hint, unit) — no per-indicator code required.
  //
  // Only `entity_kind === "state"` is supported in this version (the only
  // boundary layer in production that joins by ECI state code). District
  // and constituency variants are a follow-up: swap `INDIA_STATES` for the
  // appropriate BoundaryEntry and use a corresponding lookup table.

  import MapChoropleth from "./maplibre/MapChoropleth.svelte";
  import { INDIA_STATES, STATE_NAME_TO_ECI } from "./maplibre/sources";
  import {
    joinKeyFor,
    boundaryBasename,
    loadBoundary,
    type GeoLevel,
    type BoundaryFeatureCollection,
  } from "./boundaries";
  import {
    initialDrillState,
    drillTo,
    goBack,
    nextLevel,
    isLevelEnabled,
    blockedCrumbTooltip,
    type DrillState,
  } from "./drilldown";
  import type { BoundaryEntry } from "./maplibre/sources";
  import SourceList from "./SourceList.svelte";
  import IndicatorIcon from "./IndicatorIcon.svelte";
  import RebaseBanner from "./honesty/RebaseBanner.svelte";
  import DirectionLegendCue from "./honesty/DirectionLegendCue.svelte";
  import {
    fetchIndicator,
    uniqueTimes,
    rollupByEntity,
    facetsByEntity,
    hueForDirection,
    sequentialSwatch,
    fillForValue,
    formatValue,
    type IndicatorArtifact,
  } from "./indicators";

  interface Props {
    /** Path under DATA_BASE, e.g. "/indicators/in/energy/installed_mw_by_state.json". */
    indicator_path: string;
    /** Optional ECI code to outline as the "focused" state (e.g. "S22" on
     *  the TN overview). The map highlights its boundary so the citizen
     *  can read "where do I stand?" relative to the national distribution. */
    highlight_state?: string;
    /** CSS height for the map. */
    height?: string;
    /**
     * Optional peer-set restriction. When non-null, ONLY states whose
     * ECI code is in this list receive a colour fill; non-members fall
     * through to MapChoropleth's default grey. The `highlight_state` is
     * always outlined regardless. Domain (min/max for the colour scale)
     * is computed over the peer set only — a peer-restricted choropleth
     * tells an honest within-peer story, not a softly-clipped national one.
     */
    peer_set_members?: string[] | null;
    /**
     * Geographic level to render. Default `"state"` preserves the v1 behaviour
     * (national choropleth keyed by ECI state code). Phase 3 of
     * TODO/TN-GRANULAR-GEO-PLAN.md introduces this prop as the seam for
     * district / subdistrict / village drill-downs; deeper levels are wired
     * in subsequent commits (commit 2: loader-exposed join key; commit 3:
     * loadBoundary fetch + drill click). At this commit the prop is accepted
     * but only the `"state"` branch has behaviour — passing anything else
     * still renders the state-level map (no-op), which keeps the structural
     * change reversible.
     */
    geoLevel?: GeoLevel;
  }

  let {
    indicator_path,
    highlight_state,
    height = "440px",
    peer_set_members = null,
    geoLevel = "state",
  }: Props = $props();

  let artifact = $state<IndicatorArtifact | null>(null);
  let load_error = $state<string | null>(null);
  let selected_time = $state<string | null>(null);

  // Reverse map: ECI code -> state name (for the join layer's join-property).
  const ECI_TO_NAME = $derived.by(() => {
    const out: Record<string, string> = {};
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) out[code] = name;
    return out;
  });

  $effect(() => {
    artifact = null;
    load_error = null;
    selected_time = null;
    const path = indicator_path;
    fetchIndicator(path)
      .then(a => {
        artifact = a;
        const times = uniqueTimes(a.rows);
        selected_time = times.at(-1) ?? null;
      })
      .catch(e => (load_error = String(e)));
  });

  const times = $derived(artifact ? uniqueTimes(artifact.rows) : []);

  // Aggregated value per ECI state code at the selected time.
  const values = $derived.by(() => {
    if (!artifact || !selected_time) return new Map<string, number>();
    return rollupByEntity(artifact.rows, selected_time);
  });

  const facets = $derived.by(() => {
    if (!artifact || !selected_time) {
      return new Map<string, Array<{ facet: string; value: number }>>();
    }
    return facetsByEntity(artifact.rows, selected_time);
  });

  const domain = $derived.by(() => {
    let min = Infinity;
    let max = -Infinity;
    const member_set = peer_set_members ? new Set(peer_set_members) : null;
    for (const [code, v] of values) {
      if (member_set && !member_set.has(code)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
    return { min, max };
  });

  // join-property (state-name) -> fill hex. Only states in STATE_NAME_TO_ECI
  // get a colour; the rest fall through to MapChoropleth's default grey.
  // When peer_set_members is set, non-members also fall through (greyed).
  const fills = $derived.by(() => {
    const out: Record<string, string> = {};
    if (!artifact) return out;
    const dir = artifact.indicator.direction;
    const scale = artifact.indicator.scale_hint ?? "linear";
    const member_set = peer_set_members ? new Set(peer_set_members) : null;
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      if (member_set && !member_set.has(code)) continue;
      const v = values.get(code);
      if (v === undefined) continue;
      out[name] = fillForValue(v, domain.min, domain.max, dir, scale);
    }
    return out;
  });

  const tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    if (!artifact) return out;
    const meta = artifact.indicator;
    for (const [name, code] of Object.entries(STATE_NAME_TO_ECI)) {
      const v = values.get(code);
      if (v === undefined) {
        out[name] = `<div class="font-semibold">${escape_html(name)}</div>` +
                    `<div class="text-slate-500">no data for ${escape_html(selected_time ?? "")}</div>`;
        continue;
      }
      const formatted = formatValue(v, meta);
      const breakdown = facets.get(code) ?? [];
      const has_real_facets = breakdown.length > 1 || (breakdown[0]?.facet ?? "") !== "";
      const rows_html = has_real_facets
        ? breakdown.slice(0, 5).map(f =>
            `<div class="flex justify-between gap-2"><span>${escape_html(humanFacet(f.facet))}</span>` +
            `<span class="tabular-nums text-slate-500">${escape_html(formatValue(f.value, meta))}</span></div>`,
          ).join("")
        : "";
      out[name] =
        `<div class="font-semibold">${escape_html(name)} <span class="text-slate-400 font-mono text-[10px]">${code}</span></div>` +
        `<div class="tabular-nums">${escape_html(formatted)}</div>` +
        (rows_html ? `<div class="text-slate-600 mt-1 text-xs">${rows_html}</div>` : "");
    }
    return out;
  });

  const highlight_key = $derived(highlight_state ? ECI_TO_NAME[highlight_state] : undefined);

  // Loader-exposed join-key for the current geoLevel. At "state" this resolves
  // to "ST_NM" — the same value INDIA_STATES.join_property carries — so the
  // state branch is unchanged. The `current_join_key` derivation is the seam
  // c3 will use to dispatch on level (district → "dist_lgd",
  // subdistrict → "subdt_lgd", village → "vil_lgd"); commit 2 only introduces
  // the dependency and a dev-only consistency check.
  const current_join_key = $derived(joinKeyFor(geoLevel));

  // Dev-only invariant: the join-key the loader names for `geoLevel === "state"`
  // MUST match the one the v1 BoundaryEntry hardcodes — otherwise a future
  // edit to one without the other would silently produce blank polygons. Fires
  // only in dev (drops out of the prod bundle via the dead-code branch).
  $effect(() => {
    if (import.meta.env.DEV && geoLevel === "state" && current_join_key !== INDIA_STATES.join_property) {
      // eslint-disable-next-line no-console
      console.warn(
        `[IndicatorChoropleth] join-key drift: loader says ${current_join_key}, INDIA_STATES says ${INDIA_STATES.join_property}`,
      );
    }
  });

  // -- Drill-down state machine (Phase 3 c3 of TN-GRANULAR-GEO-PLAN) ---------
  //
  // The drill is enabled only on TN-scoped indicators (highlight_state ===
  // "S22"); other indicators keep the v1 single-level state choropleth. A
  // single $state object holds (current level, parent district lgd, state
  // lgd, breadcrumb stack) — kept tight per the plan. All state transitions
  // route through pure helpers in ./drilldown.ts so the orchestration is
  // unit-testable without mounting Svelte/maplibre.
  //
  // Boundary fetch: lazy via loadBoundary on every drill click. While
  // fetching, the map is dimmed to 60% and a spinner overlays the polygon
  // the user just tapped (Phase 4 d2 — declarative `pending` + `pending_at`
  // props on MapChoropleth; the maplibre handle stays sealed, per Fowler +
  // Gregor verdict 2026-05-15). Falls back to centre when no click position
  // is known (e.g. programmatic level changes).
  // Failure: inline toast, breadcrumb does NOT advance, parent layer stays
  // visible. Same 404-as-null contract as the loader.
  //
  // Empty-state polygon (no value at this level): currently rendered with
  // the default soft slate; the diagonal-hatch fill the plan specifies
  // requires extending MapChoropleth with a fill-pattern image registration
  // (~30 LOC) and is deferred to a polish commit. The "no data" count is
  // surfaced in the legend AND in the per-polygon tooltip (Jony edit #5).

  const TN_ECI = "S22";
  const TN_LGD = "33";
  const drill_enabled = $derived(highlight_state === TN_ECI);

  let drill_state = $state<DrillState>(initialDrillState("state"));
  // Reset when the indicator path changes.
  $effect(() => {
    void indicator_path;
    drill_state = initialDrillState("state");
    deeper_fc = null;
    deeper_fetch_error = null;
    deeper_fetching = false;
    pending_pos = null;
  });

  let deeper_fc = $state<BoundaryFeatureCollection | null>(null);
  let deeper_fetching = $state(false);
  let deeper_fetch_error = $state<string | null>(null);
  // Lng/lat of the most recent drill click. Forwarded to MapChoropleth's
  // `pending_at` so the loading spinner pins over the polygon the user just
  // tapped (Phase 4 d2). Cleared at indicator-path change and on reset.
  let pending_pos = $state<[number, number] | null>(null);

  // 250ms ease-out; instant when the user prefers reduced motion.
  const reduced_motion = (() => {
    if (typeof window === "undefined") return false;
    if (typeof window.matchMedia !== "function") return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  })();
  const drill_transition_ms = reduced_motion ? 0 : 250;

  $effect(() => {
    const lvl = drill_state.level;
    const parent = drill_state.parentDistrictLgd;
    const stateLgd = drill_state.stateLgd;
    if (lvl === "state") {
      // Reset deeper data; the state-level branch uses INDIA_STATES.
      deeper_fc = null;
      deeper_fetching = false;
      deeper_fetch_error = null;
      return;
    }
    deeper_fetching = true;
    deeper_fetch_error = null;
    const my_token = ++_fetch_token;
    loadBoundary(lvl, parent, stateLgd)
      .then(fc => {
        if (my_token !== _fetch_token) return; // stale
        if (!fc) {
          deeper_fetch_error = `${lvl} boundaries unavailable`;
          deeper_fetching = false;
          // Roll back the breadcrumb advance (plan §Phase 3 goal #4).
          drill_state = goBack(drill_state, drill_state.breadcrumbStack.length - 1);
          return;
        }
        deeper_fc = fc;
        deeper_fetching = false;
      })
      .catch(() => {
        if (my_token !== _fetch_token) return;
        deeper_fetch_error = `${lvl} boundaries unavailable`;
        deeper_fetching = false;
        drill_state = goBack(drill_state, drill_state.breadcrumbStack.length - 1);
      });
  });

  let _fetch_token = 0;

  /** Synthesise a BoundaryEntry pointing at the loader's basename for the
   *  current drill level. Reuses MapChoropleth's existing geojson_local_path
   *  resolution path — no contract change required. */
  function synthesiseEntry(state: DrillState): BoundaryEntry {
    if (state.level === "state") return INDIA_STATES;
    const basename = boundaryBasename(
      state.level,
      state.parentDistrictLgd,
      state.stateLgd,
    );
    const join_property = joinKeyFor(state.level) ?? "id";
    return {
      id: `drill-${state.level}-${state.parentDistrictLgd ?? "_"}-${state.stateLgd ?? "_"}`,
      label: `${state.level} (drill)`,
      geojson_local_path: `boundaries/in/geojson/${basename}`,
      geojson_url: "",
      join_property,
      attribution: INDIA_STATES.attribution,
    };
  }

  const current_entry = $derived(synthesiseEntry(drill_state));

  // Fills + tooltips for the active level. State-level reuses the existing
  // values/tooltips; deeper levels currently render as "no data" because no
  // indicator emits district/subdistrict/village rows yet — the empty-state
  // legend chip + per-polygon tooltip surface this honestly.
  const deeper_no_data_count = $derived.by(() => {
    if (drill_state.level === "state") return 0;
    return deeper_fc?.features.length ?? 0;
  });

  const deeper_tooltips = $derived.by(() => {
    const out: Record<string, string> = {};
    if (drill_state.level === "state") return out;
    if (!deeper_fc) return out;
    const join = joinKeyFor(drill_state.level);
    if (!join) return out;
    // Property names that typically carry the human label per ramSeraph
    // upstream: subdt_name / vlgname / dtname for subdistrict / village /
    // district. Fall back to the join-key value as label.
    const NAME_KEYS = ["dtname", "subdt_name", "vlgname", "name", "ST_NM"];
    for (const f of deeper_fc.features) {
      const k = f.properties?.[join];
      if (k === undefined || k === null) continue;
      let label: string = String(k);
      for (const nk of NAME_KEYS) {
        const v = f.properties?.[nk];
        if (typeof v === "string" && v.length) { label = v; break; }
      }
      // Tamil-script secondary line when the feature carries name_ta
      // (Phase 4 of TN-GRANULAR-GEO-PLAN — registry schemas v3.4 / v1.1 now
      // allow it; tooltip surfaces it on the line below the English label
      // when a producer eventually joins it into feature properties).
      const ta = f.properties?.["name_ta"];
      const ta_html = (typeof ta === "string" && ta.length)
        ? `<div class="text-slate-700 text-xs" lang="ta">${escape_html(ta)}</div>`
        : "";
      // Jony edit #4 / #5: hatched polygon tooltip is specific, not generic.
      out[String(k)] =
        `<div class="font-semibold">${escape_html(label)}</div>` +
        ta_html +
        `<div class="text-slate-500">no data, ${escape_html(selected_time ?? "")}</div>`;
    }
    return out;
  });

  // Click handler — drill or no-op. State-level click resolves ECI → LGD
  // (TN-only at v0; other states fall through to no-op + toast).
  function handleSelect(sel: { key: string | number; properties: Record<string, unknown>; at?: [number, number] }): void {
    if (!drill_enabled) return;
    const min_grain = artifact?.indicator.min_grain;
    const nl = nextLevel(drill_state.level);
    if (!nl || !isLevelEnabled(nl, min_grain)) return;
    let label = String(sel.key);
    let stateLgd: string | undefined;
    if (drill_state.level === "state") {
      const eci = STATE_NAME_TO_ECI[String(sel.key)];
      if (eci !== TN_ECI) {
        // Only TN has deeper boundaries on disk at v0.
        deeper_fetch_error = "deeper boundaries available for Tamil Nadu only";
        return;
      }
      stateLgd = TN_LGD;
      label = String(sel.key);
    } else {
      // For deeper levels, prefer the human name carried on the feature.
      const props = sel.properties ?? {};
      for (const nk of ["dtname", "subdt_name", "vlgname"]) {
        const v = props[nk];
        if (typeof v === "string" && v.length) { label = v; break; }
      }
    }
    pending_pos = sel.at ?? null;
    drill_state = drillTo(
      drill_state,
      { key: sel.key, label, feature: { type: "Feature", properties: sel.properties, geometry: {} }, stateLgd },
      min_grain,
    );
  }

  function handleCrumbClick(idx: number): void {
    drill_state = goBack(drill_state, idx);
  }

  // Re-click on the active-level pill (rendered after the crumbs) is the
  // recentre signal Jony asked for in the Phase 3 sign-off — the user is
  // already at this level; tapping it should snap the camera back to the
  // layer's bounds. Implemented as a monotonic counter forwarded to
  // MapChoropleth's `recentre_signal` prop (Phase 4 d3).
  let recentre_count = $state(0);
  function handleRecentre(): void {
    recentre_count += 1;
  }

  // Inline 14px monochrome SVG glyph for a breadcrumb crumb (Jony edit #2).
  // Renders the centroid as a tiny dot inside a rounded rectangle when the
  // centroid is known; falls back to a generic dot when absent (root India
  // crumb, or features that lacked geometry on click).
  function crumbGlyphPath(c: { centroid: [number, number] | null }): string {
    if (!c.centroid) return "M2,7 a5,5 0 1,0 10,0 a5,5 0 1,0 -10,0 Z";
    // 14×14 viewBox; the centroid normalises into a small dot at centre.
    return "M1,3 h12 v8 h-12 z M5,7 h4 v0.5 h-4 z";
  }


  function escape_html(s: string): string {
    return s.replace(/[&<>"']/g, c =>
      c === "&" ? "&amp;" :
      c === "<" ? "&lt;" :
      c === ">" ? "&gt;" :
      c === '"' ? "&quot;" : "&#39;",
    );
  }

  function humanFacet(f: string): string {
    if (!f) return "value";
    // "coal_power_plant" -> "Coal power plant"
    const s = f.replace(/_/g, " ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  // Legend swatches at 0, 0.25, 0.5, 0.75, 1 of the ramp.
  const legend_stops = $derived.by(() => {
    const a = artifact;
    if (!a) return [] as Array<{ t: number; hex: string; label: string }>;
    const hue = hueForDirection(a.indicator.direction);
    const ts = [0, 0.25, 0.5, 0.75, 1];
    return ts.map(t => ({
      t,
      hex: sequentialSwatch(t, hue),
      label: formatValue(domain.min + t * (domain.max - domain.min), a.indicator),
    }));
  });

  // CSS gradient string for the new continuous legend bar (UX P0-1).
  const legend_gradient = $derived.by(() => {
    if (!artifact) return "";
    const stops = legend_stops.map(s => `${s.hex} ${(s.t * 100).toFixed(0)}%`).join(", ");
    return `linear-gradient(to right, ${stops})`;
  });

  // Methodology / series-break summary for the legend "i" glyph (Phase 3
  // Jony edit §g — methodology context lives in the legend, NOT on every
  // polygon). Joins methodology_vintage + each series_break into a single
  // newline-delimited title-attribute string. Returns "" when there's
  // nothing worth surfacing — the glyph then renders as empty (the
  // template wraps the badge in `{#if methodology_summary}`).
  const methodology_summary = $derived.by(() => {
    if (!artifact) return "";
    const ind = artifact.indicator;
    const lines: string[] = [];
    if (ind.methodology_vintage) {
      lines.push(`Methodology: ${ind.methodology_vintage}`);
    }
    for (const br of ind.series_breaks ?? []) {
      lines.push(`Series break ${br.at_time} (${br.kind}): ${br.note}`);
    }
    return lines.join("\n");
  });

  // Coverage caption (Citizen P0 + UX P0-2): make "4 of 35 states" first-class
  // info above the map, not a footnote. Honours the peer-set restriction:
  // when active, both numerator and denominator are computed within the
  // peer set (otherwise the caption would mislead — e.g. "31 of 36" makes
  // no sense when only 18 general-category states are on the map).
  const coverage_summary = $derived.by(() => {
    if (!artifact) return null;
    const member_set = peer_set_members ? new Set(peer_set_members) : null;
    const all_codes = Object.values(STATE_NAME_TO_ECI);
    const peer_codes = member_set
      ? all_codes.filter(c => member_set.has(c))
      : all_codes;
    const total = peer_codes.length;
    let covered = 0;
    for (const c of peer_codes) if (values.has(c)) covered++;
    if (covered === total) return null;
    return { covered, total };
  });

  // Stale-data chip (UX P0-2): if the only year is more than ~2 years stale,
  // surface that prominently rather than burying it in slate-500 11px.
  const STALE_THRESHOLD_YEARS = 2;
  const TODAY_YEAR = new Date().getFullYear();
  const stale_chip = $derived.by(() => {
    if (!artifact || !selected_time || times.length > 1) return null;
    const yr = parseInt(selected_time.slice(0, 4), 10);
    if (!Number.isFinite(yr)) return null;
    const age = TODAY_YEAR - yr;
    if (age <= STALE_THRESHOLD_YEARS) return null;
    return { year: yr, age };
  });

  // Comparability banner (Governance §1 + Citizen): if the indicator declares
  // not_comparable_across_states OR attribution_geography is where_produced,
  // tell the citizen the choropleth is illustrative, not a ranking.
  const comparability_banner = $derived.by(() => {
    if (!artifact) return null;
    const ind = artifact.indicator;
    if (ind.comparability === "not_comparable_across_states") {
      return {
        kind: "amber" as const,
        text: ind.attribution_geography === "where_produced"
          ? "This map shows where the asset is sited, not who uses it. Ranking states by this number is misleading."
          : "Values are not directly comparable across states without normalisation. Treat the colour ramp as illustrative.",
      };
    }
    if (ind.attribution_geography === "where_produced") {
      return {
        kind: "slate" as const,
        text: "Values reflect siting (where the asset is located), not service (who consumes/benefits).",
      };
    }
    if (ind.comparability === "comparable_with_normalisation" && !ind.denominator) {
      return {
        kind: "slate" as const,
        text: "Per-capita / per-area normalisation is recommended for cross-state comparison.",
      };
    }
    return null;
  });
</script>

<section class="bg-white rounded-lg shadow-sm overflow-hidden">
  {#if load_error}
    <div class="p-4 text-sm bg-rose-50 border border-rose-200 text-rose-900">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !artifact}
    <div class="p-4 text-sm text-slate-500">Loading indicator…</div>
  {:else}
    <header class="px-4 pt-4 pb-3 border-b border-slate-100 space-y-2">
      <div class="flex justify-between items-baseline gap-3 flex-wrap">
        <div class="min-w-0">
          <h3 class="text-base font-semibold flex items-baseline gap-2">
            {#if artifact.indicator.icon}
              <IndicatorIcon
                name={artifact.indicator.icon}
                cls="w-4 h-4 text-slate-500 self-center"
                title={artifact.indicator.title}
              />
            {/if}
            <span>{artifact.indicator.title}</span>
            {#if artifact.indicator.implementing_authority && artifact.indicator.implementing_authority !== "state"}
              <span
                class="text-[10px] font-normal px-1.5 py-0.5 rounded bg-slate-100 text-slate-600"
                title={artifact.indicator.funding_split
                  ? `Centre ${artifact.indicator.funding_split.centre_pct}% / state ${artifact.indicator.funding_split.state_pct}%`
                  : "Centre involvement in funding or implementation"}
              >
                {artifact.indicator.implementing_authority === "joint" ? "Centre + state" :
                 artifact.indicator.implementing_authority === "centre" ? "Central" :
                 artifact.indicator.implementing_authority === "local_body" ? "Local body" : "Parastatal"}
              </span>
            {/if}
          </h3>
          {#if artifact.indicator.description}
            <p class="text-xs text-slate-500 mt-0.5 leading-relaxed">{artifact.indicator.description}</p>
          {/if}
        </div>
      </div>

      <!-- Comparability / attribution banner: surfaces honesty metadata above
           the map so a citizen reads the caveat BEFORE forming a verdict. -->
      {#if comparability_banner}
        <div
          class="text-[11px] px-2.5 py-1.5 rounded leading-snug"
          class:bg-amber-50={comparability_banner.kind === "amber"}
          class:text-amber-900={comparability_banner.kind === "amber"}
          class:border={comparability_banner.kind === "amber"}
          class:border-amber-200={comparability_banner.kind === "amber"}
          class:bg-slate-50={comparability_banner.kind === "slate"}
          class:text-slate-700={comparability_banner.kind === "slate"}
        >
          <strong class="font-semibold">Read this carefully · </strong>{comparability_banner.text}
        </div>
      {/if}

      <!-- Phase 2 honesty: rebase banner for index-series indicators.
           Component self-gates on value_kind === "index"; renders nothing
           for currency/rate/share/count series. -->
      <RebaseBanner meta={artifact.indicator} />

      <!-- Coverage + temporal: first-class info, not a footnote. -->
      <div class="flex justify-between items-center gap-3 flex-wrap text-[11px]">
        {#if coverage_summary}
          <span class="text-amber-800">
            <strong class="font-semibold tabular-nums">{coverage_summary.covered} of {coverage_summary.total}</strong>
            states/UTs have data on this map. The rest are grey because data is missing, not because they have zero.
          </span>
        {:else}
          <span class="text-slate-500">{artifact.coverage.spatial}</span>
        {/if}
        {#if stale_chip}
          <span
            class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 font-medium"
            title="The election you came for is much more recent than this data."
          >Snapshot · {stale_chip.year} ({stale_chip.age} years old)</span>
        {/if}
      </div>

      {#if times.length > 1 && selected_time}
        <div class="flex items-center gap-3 pt-1">
          <label class="text-xs text-slate-500 font-medium" for="indicator-year-slider">Year</label>
          <input
            id="indicator-year-slider"
            type="range"
            min="0"
            max={times.length - 1}
            step="1"
            value={times.indexOf(selected_time)}
            list={`indicator-year-ticks-${artifact.indicator.id.replace(/[^a-z0-9]/gi, "_")}`}
            oninput={(e) => {
              const idx = Number((e.target as HTMLInputElement).value);
              selected_time = times[idx] ?? null;
            }}
            class="flex-1 max-w-xs"
          />
          <datalist id={`indicator-year-ticks-${artifact.indicator.id.replace(/[^a-z0-9]/gi, "_")}`}>
            {#each times as t, i}
              <option value={i}>{t}</option>
            {/each}
          </datalist>
          <span class="text-sm font-mono tabular-nums">{selected_time}</span>
        </div>
      {/if}
    </header>

    <div>
      {#if drill_enabled && drill_state.breadcrumbStack.length > 0}
        <!-- Breadcrumb (Phase 3 c3 of TN-GRANULAR-GEO-PLAN). Each crumb is a
             back-affordance; re-clicking the active crumb is a recentre
             signal (Jony edit #1). 14px monochrome SVG glyph beside each
             crumb name (Jony edit #2). -->
        <nav class="px-3 py-1.5 border-b border-slate-100 flex items-center gap-1 text-[12px] text-slate-700 flex-wrap" aria-label="map drill breadcrumb">
          {#each drill_state.breadcrumbStack as c, i (i)}
            {@const min_g = artifact?.indicator.min_grain}
            {@const blocked = min_g ? !isLevelEnabled(c.level, min_g) : false}
            {#if i > 0}<span class="text-slate-300">›</span>{/if}
            <button
              type="button"
              class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-slate-100 transition-colors"
              class:text-slate-400={blocked}
              class:cursor-help={blocked}
              title={blocked && min_g ? blockedCrumbTooltip(min_g) : undefined}
              onclick={() => handleCrumbClick(i)}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" class="text-current">
                <path d={crumbGlyphPath(c)} fill="currentColor" />
              </svg>
              <span>{c.label}</span>
            </button>
          {/each}
          {#if drill_state.level !== "state" || drill_state.breadcrumbStack.length > 1}
            <span class="text-slate-300">›</span>
            <button
              type="button"
              class="px-1.5 py-0.5 text-slate-500 italic rounded hover:bg-slate-100 transition-colors"
              title="recentre map on this layer"
              onclick={handleRecentre}
            >{drill_state.level}</button>
          {/if}
        </nav>
      {/if}
      <div class="relative">
        <!-- 250 ms ease-out fade for the drill transition; instant when the
             user prefers reduced motion (plan §Phase 3 goal #7). -->
        <div
          style:transition={`opacity ${drill_transition_ms}ms ease-out`}
          style:opacity={deeper_fetching ? 0.6 : 1}
        >
          {#key `${drill_state.level}|${drill_state.parentDistrictLgd ?? ""}|${drill_state.stateLgd ?? ""}`}
            <MapChoropleth
              entry={current_entry}
              fills={drill_state.level === "state" ? fills : {}}
              tooltips={drill_state.level === "state" ? tooltips : deeper_tooltips}
              {height}
              highlight_key={drill_state.level === "state" ? highlight_key : undefined}
              hatch_unmapped={drill_state.level !== "state"}
              recentre_signal={recentre_count}
              pending={deeper_fetching}
              pending_at={pending_pos ?? undefined}
              pending_label={`Loading ${drill_state.level} boundaries…`}
              pinch_to_drill={drill_enabled}
              onSelect={handleSelect}
            />
          {/key}
        </div>
        {#if deeper_fetch_error}
          <div class="absolute inset-x-2 bottom-2 px-2.5 py-1.5 text-[11px] bg-amber-50 border border-amber-200 text-amber-900 rounded shadow-sm">
            {deeper_fetch_error}
            <button
              type="button"
              class="ml-2 underline text-amber-800"
              onclick={() => (deeper_fetch_error = null)}
            >dismiss</button>
          </div>
        {/if}
      </div>
      {#if drill_state.level !== "state" && deeper_no_data_count > 0}
        <!-- Empty-state legend chip (Jony edit #5) — labelled with unit so
             "12 districts, no data" reads unambiguously next to value
             buckets. -->
        <div class="px-4 py-2 text-[11px] text-slate-600 flex items-center gap-2">
          <span class="inline-block w-3 h-3 rounded bg-slate-200 border border-slate-300"></span>
          {deeper_no_data_count} {drill_state.level}{deeper_no_data_count === 1 ? "" : "s"}, no data
        </div>
      {/if}
    </div>

    <div class="px-4 py-3 border-t border-slate-100 space-y-3">
      <!-- Legend: continuous gradient bar + single 3-tick numeric axis,
           replacing 5 separate swatches with 5 separately-formatted unit
           labels (UX P0-1). One eye-stop, one numeric reading. -->
      <div>
        <div class="text-[10px] text-slate-500 uppercase tracking-wide mb-1 flex items-center gap-2 flex-wrap">
          <span>Legend</span>
          <span class="text-slate-400 normal-case font-normal">{artifact.indicator.unit}</span>
          {#if methodology_summary}
            <!-- Phase 3 Jony edit §g — methodology context lives in the
                 legend, NOT on every polygon. The full text already renders
                 in the source card at the foot; this glyph is the legend-
                 slot pointer so a citizen can see "the values come with a
                 caveat" without scrolling. Native title= keeps it cheap
                 (no popover library, no new component). -->
            <span
              class="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-slate-200 text-slate-700 text-[9px] font-semibold normal-case cursor-help"
              title={methodology_summary}
            >i</span>
          {/if}
          <!-- Phase 2 honesty: ↑/↓/↔ cue so the citizen reads the colour ramp
               correctly for direction-asymmetric indicators (e.g. IMR=lower
               is better; HDI=higher is better). -->
          <span class="ml-auto normal-case font-normal">
            <DirectionLegendCue direction={artifact.indicator.direction} />
          </span>
        </div>
        <div class="h-3 w-full rounded-sm" style:background={legend_gradient}></div>
        <div class="flex justify-between text-[10px] text-slate-600 tabular-nums mt-1">
          <span>{legend_stops[0]?.label ?? ""}</span>
          <span>{legend_stops[2]?.label ?? ""}</span>
          <span>{legend_stops[4]?.label ?? ""}</span>
        </div>
      </div>

      <!-- Notes promoted to high priority: it shapes interpretation. -->
      {#if artifact.indicator.notes}
        <p class="text-[12px] text-slate-700 leading-relaxed">{artifact.indicator.notes}</p>
      {/if}

      <!-- Methodology vintage + series breaks (governance honesty). -->
      {#if artifact.indicator.methodology_vintage || (artifact.indicator.series_breaks?.length ?? 0) > 0}
        <div class="text-[11px] text-slate-500 space-y-0.5">
          {#if artifact.indicator.methodology_vintage}
            <div><span class="text-slate-400">Methodology · </span>{artifact.indicator.methodology_vintage}</div>
          {/if}
          {#each artifact.indicator.series_breaks ?? [] as br}
            <div><span class="text-amber-700">Series break · </span>{br.at_time} ({br.kind}): {br.note}</div>
          {/each}
        </div>
      {/if}

      <!-- License + provenance: legally significant; demoted only by being last. -->
      <div class="flex items-center gap-2 text-[11px] flex-wrap">
        <span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
          {artifact.license.name}
        </span>
        {#if artifact.license.url}
          <a href={artifact.license.url} target="_blank" rel="noreferrer" class="text-sky-700 hover:underline">
            license terms ↗
          </a>
        {/if}
        {#if artifact.license.redistributable === false}
          <span class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 font-medium">non-redistributable — links only</span>
        {/if}
      </div>

      <SourceList sources={artifact.sources} schema_version={artifact.$schema_version} />
    </div>
  {/if}
</section>
