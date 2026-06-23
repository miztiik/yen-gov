<!--
  StateEventMap - extracted from StateElection.svelte during R3
  (Beck two-hat: pure structural extraction, no behaviour change) of
  TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).

  Wraps the entire state-event map section:
    - AC branch  : StateAcMapD3 (when ac_view='map') OR TileCartogram
                   (when ac_view='hex'), with Winner|Margin sub-toggle
                   and the Map|Equal-seats arm toggle (latter only when
                   the state has a persisted AC tile layout).
    - PC branch  : StatePcMapD3 (when pc_view='map') OR TileCartogram
                   (when pc_view='hex'), with Winner|Margin sub-toggle
                   and the Map|Equal-seats arm toggle (latter only when
                   the state has a persisted per-state PC tile layout,
                   i.e. >= MIN_PCS_FOR_STATE_LAYOUT seats); OR the
                   pre-2009 LS placeholder card (when pc_delim_year ==
                   null).
    - Caption + sub-threshold marker legend.

  The parent owns all derived data (ac_winners_shim, ac_fills_override,
  ac_opacities_override, pc_winners, pc_fills_override,
  pc_opacities_override, pc_boundary, pc_delim_year, ac_tile_layout,
  ac_tile_rows, has_ac_equal_seats, ac_tile_layout_error, pc_tile_layout,
  pc_tile_rows, has_pc_equal_seats, pc_tile_layout_error) because those
  derives are also consumed by sibling sections (top-parties mute
  recede, scatter chip, etc.). `color_mode`, `ac_view` and `pc_view` are
  exposed as $bindable so the in-template buttons can flip them while the
  parent's override derivations continue to read the same proxy.

  R4 (the same plan-doc, Section 5) reorders this section above the
  PartyComposite + below the SiblingEventsRail and adds the
  HeroCards-driven Winner mode default; R3 preserves the legacy DOM
  + every data-testid verbatim so existing tests still pass.

  Preserves data-testids: state-event-map, state-event-map-mode,
  state-event-map-mode-winner, state-event-map-mode-margin,
  state-event-map-view, state-event-map-geo, state-event-map-hex,
  state-event-map-placeholder, state-pc-map-legend.
  Adds (PC equal-seats arm): state-event-pc-view, state-event-pc-map-geo,
  state-event-pc-map-hex.
-->
<script lang="ts">
  import StateAcMapD3 from "../charts/StateAcMapD3.svelte";
  import StatePcMapD3, {
    type PcWinnerRow,
  } from "../charts/StatePcMapD3.svelte";
  import TileCartogram from "../charts/TileCartogram.svelte";
  import MarginLegend from "./MarginLegend.svelte";
  import { link } from "../links";
  import type {
    TileLayoutRow,
    TileRow,
  } from "../view-models/election-tile-layout";
  import type { AcWinner } from "../view-models/state-overview";
  import type { BoundaryEntry } from "../boundaries/sources";

  type ColorMode = "winner" | "margin";
  type AcView = "map" | "hex";

  interface Props {
    body: "ac" | "pc" | null;
    state_code: string;
    /** Active event_id; threaded into the AC + PC map components for
     * their internal palette / boundary cache keys. */
    event_id: string;
    /** AC branch ------------------------------------------------------ */
    ac_winners_shim: AcWinner[];
    ac_fills_override: Record<number, string>;
    ac_opacities_override: Record<number, number>;
    /** PR-B: ECI state codes whose AC features to draw as the "undivided"
     * union (e.g. ["S01","S29"] for a pre-2014 Andhra Pradesh event), with
     * a name-slug winner join. Undefined = default single-state eci join. */
    ac_historical_states?: string[];
    /** Equal-seats arm: null while the scope-doc fetch is in-flight,
     * true/false once resolved. */
    has_ac_equal_seats: boolean | null;
    /** Equal-seats tile layout (null while not requested or in-flight). */
    ac_tile_layout: TileLayoutRow[] | null;
    ac_tile_layout_error: boolean;
    ac_tile_rows: TileRow[];
    onAcTileSelect: (unit_id: string) => void;
    /** PC branch ------------------------------------------------------ */
    pc_winners: PcWinnerRow[];
    /** null when the LS event has no on-disk geometry (pre-2009 LS or
     * non-LS PC event); triggers the placeholder card branch. */
    pc_delim_year: number | null;
    pc_boundary: BoundaryEntry;
    pc_fills_override: Record<string, string>;
    pc_opacities_override: Record<string, number>;
    /** Equal-seats arm (per-state PC cartogram): null while the scope-doc
     * fetch is in-flight, true/false once resolved. Mirrors
     * has_ac_equal_seats. False for states below the seat threshold, so
     * the PC page stays geographic-only. */
    has_pc_equal_seats: boolean | null;
    /** Per-state PC tile layout (null while not requested or in-flight). */
    pc_tile_layout: TileLayoutRow[] | null;
    pc_tile_layout_error: boolean;
    pc_tile_rows: TileRow[];
    onPcTileSelect: (unit_id: string) => void;
    /** True while the winners loader is in flight. Gates BOTH equal-seats
     *  arms to the "Loading..." placeholder so a mid-load buildTileRows pass
     *  never paints an all-grey "pending" hex grid (mirrors the national PC
     *  guard, PR #1179). */
    equal_seats_loading: boolean;
    /** State_slug for the PC map's name-slug join (delim=2008 only). */
    state_slug: string;
    /** Bindable UI state ---------------------------------------------- */
    color_mode: ColorMode;
    ac_view: AcView;
    pc_view: AcView;
  }

  let {
    body,
    state_code,
    event_id,
    ac_winners_shim,
    ac_fills_override,
    ac_opacities_override,
    ac_historical_states,
    has_ac_equal_seats,
    ac_tile_layout,
    ac_tile_layout_error,
    ac_tile_rows,
    onAcTileSelect,
    pc_winners,
    pc_delim_year,
    pc_boundary,
    pc_fills_override,
    pc_opacities_override,
    has_pc_equal_seats,
    pc_tile_layout,
    pc_tile_layout_error,
    pc_tile_rows,
    onPcTileSelect,
    equal_seats_loading,
    state_slug,
    color_mode = $bindable<ColorMode>("winner"),
    ac_view = $bindable<AcView>("map"),
    pc_view = $bindable<AcView>("map"),
  }: Props = $props();
</script>

{#if body === "ac"}
  <section
    class="space-y-2"
    data-testid="state-event-map"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 class="text-sm font-semibold text-slate-800">
        Constituencies
      </h2>
      <div class="flex flex-wrap items-center gap-2">
        <div
          class="inline-flex rounded border border-slate-200 bg-white p-0.5 text-xs"
          data-testid="state-event-map-mode"
        >
          <button
            type="button"
            class={color_mode === "winner"
              ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
              : "px-2 py-0.5 text-slate-500"}
            data-testid="state-event-map-mode-winner"
            onclick={() => (color_mode = "winner")}
          >Winner</button>
          <button
            type="button"
            class={color_mode === "margin"
              ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
              : "px-2 py-0.5 text-slate-500"}
            data-testid="state-event-map-mode-margin"
            onclick={() => (color_mode = "margin")}
          >Margin</button>
        </div>
        {#if has_ac_equal_seats === true}
          <div
            class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-sm"
            data-testid="state-event-map-view"
          >
            <button
              type="button"
              class="rounded-md px-3 py-1 transition-colors {ac_view === 'map'
                ? 'bg-white font-medium text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'}"
              data-view="map"
              onclick={() => (ac_view = "map")}
            >Map</button>
            <button
              type="button"
              class="rounded-md px-3 py-1 transition-colors {ac_view === 'hex'
                ? 'bg-white font-medium text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'}"
              data-view="hex"
              onclick={() => (ac_view = "hex")}
            >Equal seats</button>
          </div>
        {/if}
      </div>
    </div>
    {#if ac_view === "map"}
      <div data-testid="state-event-map-geo">
        <StateAcMapD3
          state={state_code}
          rows={ac_winners_shim}
          event={event_id}
          height="420px"
          fillsOverride={ac_fills_override}
          opacitiesOverride={ac_opacities_override}
          historical_states={ac_historical_states}
        />
      </div>
    {:else}
      <div data-testid="state-event-map-hex">
        {#if ac_tile_layout_error}
          <div
            class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
          >
            Equal-seats layout couldn't load.
          </div>
        {:else if ac_tile_layout == null || equal_seats_loading}
          <p class="p-4 text-sm text-slate-500">
            Loading equal-seats layout...
          </p>
        {:else}
          <TileCartogram
            tiles={ac_tile_rows}
            height="420px"
            onSelect={onAcTileSelect}
          />
        {/if}
      </div>
    {/if}
    {#if color_mode === "winner"}
      <p class="text-xs text-slate-500">
        Each constituency is filled with the winning party's colour.
      </p>
    {:else}
      <MarginLegend />
    {/if}
  </section>
{:else if body === "pc"}
  <!-- TODO/20260612 Row D: PC choropleth via StatePcMapD3, filtering
       the national PC topojson by `state_ut_code === state_code`.
       Replaces the "Constituency map being prepared" placeholder card
       from PR #954 for LS 2024 (delim=2024) AND LS 2019 / 2014 / 2009
       (delim=2008, ingested by FU#3 plan TODO/20260612-pc-delim-2008-
       boundary-ingest-plan.md). Pre-2009 LS events (general-2004 /
       general-1999 / ...) have no PC geometry on disk and render the
       placeholder card below.

       No "Equal seats" arm: per-state PC tile layouts have not been
       authored (only national PC + per-state AC layouts exist today).
       The note below directs the citizen to the national surface for
       the hex view. -->
  {#if pc_delim_year == null}
    <!-- Pre-2009 LS event: no PC geometry available; placeholder card
         persists. This is by design (FU#3 plan-doc Smoke 6 regression
         check). -->
    <section
      class="space-y-2"
      data-testid="state-event-map-placeholder"
    >
      <h2 class="text-sm font-semibold text-slate-800">
        Constituencies
      </h2>
      <div
        class="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
      >
        Constituency map for pre-2009 Parliament events is not yet
        available. No machine-readable GIS source for the 1976
        Delimitation Commission Order has been ingested. See the
        constituency table below for results.
      </div>
    </section>
  {:else}
    <section
      class="space-y-2"
      data-testid="state-event-map"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-sm font-semibold text-slate-800">
          Constituencies
        </h2>
        <div class="flex flex-wrap items-center gap-2">
          <div
            class="inline-flex rounded border border-slate-200 bg-white p-0.5 text-xs"
            data-testid="state-event-map-mode"
          >
            <button
              type="button"
              class={color_mode === "winner"
                ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
                : "px-2 py-0.5 text-slate-500"}
              data-testid="state-event-map-mode-winner"
              onclick={() => (color_mode = "winner")}
            >Winner</button>
            <button
              type="button"
              class={color_mode === "margin"
                ? "rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
                : "px-2 py-0.5 text-slate-500"}
              data-testid="state-event-map-mode-margin"
              onclick={() => (color_mode = "margin")}
            >Margin</button>
          </div>
          {#if has_pc_equal_seats === true}
            <div
              class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-sm"
              data-testid="state-event-pc-view"
            >
              <button
                type="button"
                class="rounded-md px-3 py-1 transition-colors {pc_view === 'map'
                  ? 'bg-white font-medium text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'}"
                data-view="map"
                onclick={() => (pc_view = "map")}
              >Map</button>
              <button
                type="button"
                class="rounded-md px-3 py-1 transition-colors {pc_view === 'hex'
                  ? 'bg-white font-medium text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'}"
                data-view="hex"
                onclick={() => (pc_view = "hex")}
              >Equal seats</button>
            </div>
          {/if}
        </div>
      </div>
      {#if pc_view === "map"}
        <div data-testid="state-event-pc-map-geo">
          <StatePcMapD3
            state={state_code}
            {state_slug}
            rows={pc_winners}
            event={event_id}
            height="420px"
            fillsOverride={pc_fills_override}
            opacitiesOverride={pc_opacities_override}
            boundary={pc_boundary}
          />
        </div>
      {:else}
        <div data-testid="state-event-pc-map-hex">
          {#if pc_tile_layout_error}
            <div
              class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
            >
              Equal-seats layout couldn't load.
            </div>
          {:else if pc_tile_layout == null || equal_seats_loading}
            <p class="p-4 text-sm text-slate-500">
              Loading equal-seats layout...
            </p>
          {:else}
            <TileCartogram
              tiles={pc_tile_rows}
              height="420px"
              onSelect={onPcTileSelect}
            />
          {/if}
        </div>
      {/if}
      {#if color_mode === "winner"}
        <p class="text-xs text-slate-500">
          Each constituency is filled with the winning party's colour.
        </p>
      {:else}
        <MarginLegend />
      {/if}
      {#if pc_view === "map" && has_pc_equal_seats !== true}
        <p
          class="text-[11px] text-slate-500"
          data-testid="state-pc-map-legend"
        >
          Equal-seats view available on the
          <a
            class="text-sky-700 hover:underline"
            href={link.nationalElection(event_id)}
          >national {event_id} surface</a>.
        </p>
      {/if}
    </section>
  {/if}
{/if}
