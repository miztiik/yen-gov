<!--
  MarginLegend - the depth-band strip for "Margin" mode on the election maps.

  Shown in place of the bare one-line caption whenever a map surface is in
  Margin mode (national map, national equal-seats, assembly map, assembly
  equal-seats). In Margin mode each seat keeps its WINNING PARTY's colour and
  that colour is paled toward a knife-edge / deepened toward a safe seat. The
  legend demonstrates that pale->deep depth axis on a NEUTRAL base (so it
  implies no single party), with each band paired to a pp label (house rule:
  colour is never the only signal). The "Results pending" row uses the off-ramp
  slate so "no data" stays distinct from a knife-edge win.

  Self-contained + presentational: no props beyond an optional spacing class,
  no party/data dependency. Decision: docs/architecture/frontend/colours.md.
-->
<script lang="ts">
  import {
    marginLegendStops,
    marginBandLegendStops,
    type MarginBands,
  } from "./election-map-coloring";

  interface Props {
    /** Extra classes for the wrapper (spacing only). */
    class?: string;
    /** Per-election competitiveness bands (quantile-classed margins). When
     *  provided, the legend shows one swatch per band labelled with its real pp
     *  range; when omitted it falls back to the fixed illustrative bands. */
    bands?: MarginBands;
    /** When true, prepend a single one-time hint line introducing the
     *  Parliament-seat -> Assembly-seat -> District nesting used by the
     *  national + state constituency lists. Mounted ONCE above a list (never
     *  per row); every MAP call site omits it (default false) so the map
     *  legends are unchanged. */
    nesting_hint?: boolean;
  }
  let { class: klass = "", bands, nesting_hint = false }: Props = $props();

  const stops = $derived(
    bands ? marginBandLegendStops(bands) : marginLegendStops(),
  );
</script>

<div class="space-y-1 {klass}" data-testid="margin-legend">
  {#if nesting_hint}
    <!-- One-time hierarchy hint (D3/D10): the ONLY place the Parliament-seat
         -> Assembly-seat -> District nesting is spelled out, paired once. No
         per-row PC/AC tags anywhere else. -->
    <p
      class="text-xs font-medium text-slate-600"
      data-testid="margin-legend-nesting-hint"
    >
      Parliament seats hold Assembly seats, grouped by District.
    </p>
  {/if}
  <p class="text-xs text-slate-500">
    Each seat shows its winning party's colour; deeper = safer seat, pale = won
    by a whisker.{bands
      ? " Bands split this election's seats into equal-sized groups by margin."
      : " Shades below are illustrative."}
  </p>
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-600">
    {#each stops as s (s.label)}
      <span class="inline-flex items-center gap-1">
        <span
          class="inline-block h-3 w-3 rounded-sm ring-1 ring-slate-200"
          style:background-color={s.hex}
          data-pending={s.pending ? "true" : "false"}
        ></span>
        {s.label}
      </span>
    {/each}
  </div>
</div>

