<script module lang="ts">
  // E4 shared map-highlight legend (parent plan section 25.5).
  //
  // ONE legend component drives BOTH StateAcMap (maplibre choropleth)
  // and TileCartogram (SVG hex cartogram). The parent orchestrator
  // (e.g. `StateEventMap.svelte`) holds the shared $state for
  // `{ mode, selected_party_id, min_margin }`, renders THIS legend
  // ONCE, and then threads the three knobs down to both map surfaces
  // as props. There is no per-map widget; the legend-drift contract
  // (parent plan section 22.6) enforces ONE legend, both surfaces.
  //
  // Composes:
  //   - SegmentedControl (U4 #748): margin / party_won mode picker.
  //   - PartyPill (E2 #800): tap-to-select party in legend.
  //   - Stepped chip-group for min_margin (0/10/20/30 pp).
  //
  // Reuses tokens:
  //   - `--party-neutral` + `--party-neutral-text` for muted pills
  //     (already wired into PartyPill via `muted` prop) and for the
  //     receding cell fill (cellTreatment).
  //
  // Pure helpers (`marginOpacity`, `cellTreatment`, `advanceLegendState`)
  // live in the sibling `./map-highlight-utils.ts` so vitest can cover
  // every transition without a DOM (per repo vitest doctrine -
  // node-env, no jsdom canvas, no @testing-library/svelte). The
  // component below is a thin Svelte shell that forwards user events
  // to `advanceLegendState` and re-emits the new state via
  // `on_change`.
  //
  // Re-exports `advanceLegendState` + the discriminated `LegendAction`
  // type so consumers (and tests) can drive the reducer directly.

  export {
    DEFAULT_HIGHLIGHT_STATE,
    MIN_MARGIN_STEPS,
    advanceLegendState,
    type HighlightMode,
    type HighlightState,
    type LegendAction,
    type MinMargin,
  } from "./map-highlight-utils";
</script>

<script lang="ts">
  import SegmentedControl from "../SegmentedControl.svelte";
  import PartyPill from "../party-pill/PartyPill.svelte";
  import type { PartyRowForResolver } from "../colors/resolver";
  import {
    MIN_MARGIN_STEPS,
    advanceLegendState,
    type HighlightMode,
    type HighlightState,
    type MinMargin,
  } from "./map-highlight-utils";

  /** One legend party - just what the legend needs to render a pill. */
  export interface LegendParty {
    /** Canonical `parties.IN.<SLUG>` id (or any stable identifier the
     *  consumer keys cells by). */
    party_id: string;
    /** Citizen-readable short label (e.g. "BJP"). */
    party_short: string;
    /** Optional party row carrying `brand_colour` for the 3-tier
     *  resolver (anchor / brand / fallback). Null is fine. */
    row?: PartyRowForResolver | null;
  }

  interface Props {
    /** Current shared highlight state. */
    state: HighlightState;
    /** Distinct parties to render as tap-to-select pills. */
    parties: readonly LegendParty[];
    /** Called with the next state after every user gesture. */
    on_change: (next: HighlightState) => void;
    /** Optional outer class for the host. */
    cls?: string;
    /** Playwright `data-testid` root (sub-elements derive `${testid}-x`). */
    testid?: string;
  }

  const {
    state,
    parties,
    on_change,
    cls = "",
    testid = "map-highlight-legend",
  }: Props = $props();

  /** The first legend party's id - auto-selected on margin -> party_won
   *  flip when no party is currently selected, so the recede effect is
   *  visible on the first tap of the mode toggle. Null when the legend
   *  has no parties (e.g. results pending). */
  const first_party_id = $derived<string | null>(
    parties.length > 0 ? parties[0].party_id : null,
  );

  function setMode(next: HighlightMode): void {
    on_change(
      advanceLegendState(
        state,
        { kind: "set_mode", next },
        { first_party_id },
      ),
    );
  }

  function tapParty(party_id: string): void {
    on_change(advanceLegendState(state, { kind: "tap_party", party_id }));
  }

  function setMinMargin(next: MinMargin): void {
    on_change(advanceLegendState(state, { kind: "set_min_margin", next }));
  }

  /** Mode-picker segment options. The label is the citizen-readable
   *  hover tooltip; SegmentedControl falls back to it as text when no
   *  glyph is registered. Plain text keeps the legend honest until the
   *  16.3a glyph pair lands in the icon registry (margin glyph / target
   *  glyph). */
  const mode_options = [
    { value: "margin" as const, label: "Margin ramp", glyph: "margin" },
    { value: "party_won" as const, label: "Party wins", glyph: "target" },
  ];

  /** Selected party for the chip-header in party_won mode (`null` when
   *  none selected - the slider is hidden then since `min_margin` is a
   *  no-op). */
  const selected_party = $derived(
    state.selected_party_id == null
      ? null
      : (parties.find((p) => p.party_id === state.selected_party_id) ?? null),
  );
</script>

<div
  class="map-highlight-legend space-y-2 {cls}"
  data-testid={testid}
  data-mode={state.mode}
  data-selected-party-id={state.selected_party_id ?? ""}
  data-min-margin={state.min_margin}
>
  <!-- Mode picker + (party_won only) stepped margin slider. -->
  <div class="flex flex-wrap items-center gap-3">
    <SegmentedControl
      testid="{testid}-mode"
      options={mode_options}
      value={state.mode}
      onChange={setMode}
    />
    {#if state.mode === "party_won"}
      <div
        class="flex items-center gap-1 text-xs text-slate-600"
        data-testid="{testid}-min-margin"
      >
        <span class="mr-1">Margin &ge;</span>
        {#each MIN_MARGIN_STEPS as step (step)}
          {@const active = state.min_margin === step}
          <button
            type="button"
            class="min-margin-step rounded border border-slate-200 px-2 py-1 text-xs"
            class:is-active={active}
            data-min-margin-step={step}
            data-active={active}
            onclick={() => setMinMargin(step)}
            title={step === 0 ? "Any margin" : `Margin >= ${step}%`}
          >
            {step === 0 ? "Any" : `${step}%`}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Party pills (tap-to-select). In party_won mode every non-selected
       pill is muted via the `--party-neutral` token (already wired into
       PartyPill via the `muted` prop). In margin mode every pill is at
       full saturation - the legend acts as a colour key only. -->
  <div
    class="flex flex-wrap items-center gap-1.5"
    data-testid="{testid}-parties"
  >
    {#if state.mode === "party_won" && selected_party}
      <span class="mr-1 text-xs text-slate-500" data-testid="{testid}-selection-label">
        Showing
      </span>
    {/if}
    {#each parties as p (p.party_id)}
      {@const muted =
        state.mode === "party_won" && state.selected_party_id !== p.party_id}
      <PartyPill
        party_id={p.party_id}
        party_short={p.party_short}
        row={p.row ?? null}
        size="sm"
        muted={muted}
        onclick={() => tapParty(p.party_id)}
      />
    {/each}
  </div>
</div>

<style>
  .min-margin-step {
    background: white;
    color: rgb(71 85 105); /* slate-600 */
    cursor: pointer;
    transition: background-color 120ms ease-out, color 120ms ease-out, border-color 120ms ease-out;
  }
  .min-margin-step:hover:not(.is-active) {
    background: rgb(248 250 252); /* slate-50 */
  }
  .min-margin-step.is-active {
    background: rgb(15 23 42); /* slate-900 */
    color: white;
    border-color: rgb(15 23 42);
    cursor: default;
  }
</style>
