<script lang="ts">
  // Generic indicator choropleth: drop in any indicator artifact under
  // `datasets/indicators/` (legacy JSON) or any allowlisted canonical-
  // backed indicator, get a state-level map with legend, tooltip, and
  // source attribution. Driven entirely by the metadata in the
  // artifact's `indicator` block (value_kind, direction, scale_hint,
  // unit) - no per-indicator code required.
  //
  // ## G30 wave-4 (2026-06-10) - maplibre arm retired
  //
  // This component used to dispatch between a legacy maplibre-gl
  // `<MapChoropleth>` body (~900 LOC of header/legend/drill state
  // machine/comparability banner/etc.) and an opt-in d3-geo SVG
  // `<GeoChoropleth>` (F2b.3) gated by `renderer_override:
  // "geo-choropleth-f2b"` on the allowlist descriptor. G29 + G30
  // wave-2 + wave-3 flipped all 56 state-grain welfare descriptors
  // to the opt-in flag, leaving the maplibre arm reachable only by
  // legacy non-allowlisted paths AND non-state-grain artifacts that
  // were never declared as `chart_type: "choropleth"` in the
  // grapher catalogue (0/19 district + 0/11 country at audit time).
  //
  // G30 wave-4 deletes the maplibre arm and makes `<GeoChoropleth>`
  // the unconditional render path at state grain. Non-state-grain
  // artifacts get a defensive empty-state ("Map view not available
  // for <grain>-grain data") so a future district-mounted descriptor
  // degrades gracefully rather than crashing. The `renderer_override`
  // field on `CanonicalIndicatorDescriptor` survives as a historical
  // opt-in marker - removing it from the type signature is a
  // separate question (whether to retire the seam entirely) deferred
  // to a follow-up. Per ADR-routing rule, this PR keeps the type +
  // the field on the 56 descriptors.
  //
  // The maplibre engine (`./maplibre/MapChoropleth.svelte`) is now
  // election-only - the surviving callers are `IndiaMap` (national
  // leading-party choropleth), `StateAcMap` (per-state AC overlay),
  // and `NationalElectionsAtlas` (national PC choropleth).

  import { uniqueTimes, type IndicatorArtifact } from "./indicators";
  import {
    indicatorArtifactSourcesV2,
    loadIndicator,
  } from "./canonical/indicator-from-canonical";
  import type { SourceV2Row } from "./source-list-v2";
  import GeoChoropleth from "./charts/GeoChoropleth.svelte";
  import type { GeoChoroplethRow } from "./charts/geo-choropleth-helpers";
  import {
    entityContextForGrain,
    type EntityRow,
    type ChoroplethGrain,
  } from "./charts/choropleth-entity-context";

  interface Props {
    /** Path under DATA_BASE, e.g.
     *  "/indicators/in/energy/state_per_capita_electricity_consumption_kwh.json". */
    indicator_path: string;
    /** CSS height for the map. Default mirrors the legacy default. */
    height?: string;
    /**
     * Optional peer-set restriction. When non-null, ONLY states whose
     * ECI code is in this list receive a colour fill; non-members emit
     * value=null which the renderer paints with the hatch. Domain
     * (min/max for the colour scale) is computed over the peer set
     * only - a peer-restricted choropleth tells an honest within-peer
     * story, not a softly-clipped national one.
     */
    peer_set_members?: string[] | null;
  }

  let {
    indicator_path,
    height = "440px",
    peer_set_members = null,
  }: Props = $props();

  let artifact = $state<IndicatorArtifact | null>(null);
  let load_error = $state<string | null>(null);
  let selected_time = $state<string | null>(null);

  // Choropleth grain - derived from `artifact.coverage.admin_level`.
  // Anything other than "district" routes to state (the historical
  // default that preserves the pre-B.05 contract). Currently only
  // state grain is renderable; district + other grains fall through
  // to the empty-state below.
  const grain: ChoroplethGrain = $derived(
    artifact?.coverage.admin_level === "district" ? "district" : "state",
  );

  // Per-grain entity context (boundary entry + entity loader + display
  // shape). The loader fires once per grain change; at state grain
  // returns the 36-row states+UTs taxonomy.
  const ctx = $derived(entityContextForGrain(grain));
  let entities_taxonomy = $state<EntityRow[] | null>(null);
  $effect(() => {
    const loader = ctx.load_entities;
    let cancelled = false;
    loader()
      .then(e => {
        if (cancelled) return;
        entities_taxonomy = e;
      })
      .catch(e => {
        if (cancelled) return;
        load_error = String(e);
      });
    return () => {
      cancelled = true;
    };
  });

  $effect(() => {
    artifact = null;
    sources_v2_snapshot = undefined;
    load_error = null;
    selected_time = null;
    const path = indicator_path;
    loadIndicator(path)
      .then(a => {
        // CRITICAL: snapshot sources_v2 BEFORE the `artifact = a`
        // assignment wraps `a` in Svelte 5's `$state` Proxy. The
        // accessor uses WeakMap identity, which the Proxy breaks; if
        // we read after the assignment the citation row is invisible.
        sources_v2_snapshot = indicatorArtifactSourcesV2(a);
        artifact = a;
        const times = uniqueTimes(a.rows);
        selected_time = times.at(-1) ?? null;
      })
      .catch(e => (load_error = String(e)));
  });

  // Local snapshot of `sources_v2` captured at load time. NB: cannot
  // be derived through `indicatorArtifactSourcesV2(artifact)` because
  // `artifact` is wrapped by Svelte 5's `$state` Proxy, which breaks
  // the WeakMap identity lookup the accessor relies on. We grab the
  // array off the raw fetched object BEFORE assigning it to `$state`
  // so the citation row survives into the renderer (otherwise the
  // source line silently collapses to "Source: Source (as of <year>)"
  // because the v1 `sources[]` is empty for canonical-backed artifacts).
  let sources_v2_snapshot = $state<readonly SourceV2Row[] | undefined>(undefined);

  const sources_v2 = $derived(
    sources_v2_snapshot ?? (artifact ? indicatorArtifactSourcesV2(artifact) : undefined),
  );

  // Build the (entity_key=LGD code, time, value) row set the
  // GeoChoropleth consumes. We honour peer_set_members so that
  // TopicLanding's peer-set filter still gates which states get a
  // value (non-members emit value=null which the renderer paints
  // with the hatch). Only the LATEST time slice is emitted; multi-
  // year TimeControl integration is deferred to a follow-on.
  const geo_rows = $derived.by<GeoChoroplethRow[]>(() => {
    if (!artifact || selected_time == null) return [];
    if (grain !== "state") return [];
    const member_set = peer_set_members ? new Set(peer_set_members) : null;
    const out: GeoChoroplethRow[] = [];
    // Rollup observation rows by entity at the selected time. The
    // collapse mirrors `rollupByEntity` in ./indicators but inlined
    // so the component does not depend on that helper for this one
    // call - keeps the import surface small.
    const values = new Map<string, number>();
    for (const row of artifact.rows) {
      if (String(row.time) !== selected_time) continue;
      if (typeof row.value !== "number" || !Number.isFinite(row.value)) continue;
      if (!values.has(row.entity_id)) values.set(row.entity_id, 0);
      values.set(row.entity_id, (values.get(row.entity_id) ?? 0) + row.value);
    }
    for (const e of entities_taxonomy ?? []) {
      if (member_set && !member_set.has(e.code)) continue;
      const v = values.get(e.code);
      out.push({
        entity_key: e.boundary_join_key,
        time: selected_time,
        value: v ?? null,
      });
    }
    return out;
  });

  // Source attribution rendered inside the GeoChoropleth's own
  // SourceLine. Falls back to the v1 `sources[]` block when the
  // artifact carries no sources_v2 rows (legacy on-disk JSON path),
  // then to the indicator title's publisher as the LAST honest hint.
  // A bare "Source" placeholder reads as a missing-data bug to
  // citizens; we'd rather degrade to "Source not on file".
  const geo_source = $derived.by(() => {
    const v2 = sources_v2;
    const first_v2 = v2 && v2.length > 0 ? v2[0] : null;
    const first_v1 = artifact?.sources?.[0];
    return {
      owner:
        first_v2?.producer ??
        first_v1?.authority ??
        first_v1?.name ??
        "Source not on file",
      vintage:
        first_v2?.vintage ??
        first_v1?.fetched_at ??
        (selected_time ?? ""),
      url: first_v2?.url_main ?? first_v1?.url ?? null,
    };
  });
</script>

<section
  class="bg-white rounded-lg shadow-sm overflow-hidden p-4"
  style:min-height={height}
  data-testid="indicator-choropleth"
>
  {#if load_error}
    <div class="text-sm bg-rose-50 border border-rose-200 text-rose-900 rounded px-3 py-2">
      Failed to load indicator: <code>{load_error}</code>
    </div>
  {:else if !artifact || selected_time == null}
    <div class="text-sm text-slate-500">Loading indicator...</div>
  {:else if grain !== "state"}
    <!-- Defensive empty-state for non-state-grain artifacts (district,
         country). G30 wave-4 retired the legacy maplibre choropleth body
         that used to handle the district drill; the d3-geo
         `<GeoChoropleth>` primitive only supports the state polygon
         layer today. Citizens see this gentle copy instead of a broken
         card. A future re-introduction of district-mounted choropleths
         (via the same allowlist seam + a district-aware GeoChoropleth
         variant) would replace this branch. -->
    <div class="text-sm text-slate-600">
      Map view is not available for {grain}-grain data on this card.
    </div>
  {:else}
    <GeoChoropleth
      topojson_path="/boundaries/in/states/all.topojson"
      feature_key="State_LGD"
      rows={geo_rows}
      selected_time={selected_time}
      direction={artifact.indicator.direction}
      title={artifact.indicator.title}
      unit_label={artifact.indicator.short_unit ?? artifact.indicator.unit}
      source_owner={geo_source.owner}
      source_vintage={geo_source.vintage}
      source_url={geo_source.url}
    />
  {/if}
</section>
