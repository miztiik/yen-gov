<!--
  StrongholdDotStrip.svelte
  ============================
  10-cell SVG dot strip used in the per-row Party.svelte stronghold
  list. Replaces the prior Unicode block-glyph sparkline (PR-5 of
  TODO/20260614-party-page-reimagination-plan.md, doctrine row J2 +
  H3).

  Encoding:
    - `W` (won)            -> filled circle in the party brand colour
    - `L` (lost)           -> hollow circle (slate-200 ring on surface)
    - `DNC` (did-not-contest, padded by the component when results
                          .length < cell_count) -> hatched circle

  The padding is right-aligned chronologically: when the party's
  results array has fewer than `cell_count` events, the missing
  cells appear on the LEFT of the strip (oldest end) so the rightmost
  cells always show the most recent results. When the array has more
  than `cell_count` cells the strip shows the most recent `cell_count`.

  The hatch pattern reuses the visual idiom from PartyStrongholdMap
  (DNC = "data not joined" there, same here = "did not contest").
  Width = cell_count * 12 + 4 (right pad). Default cell_count=10 ->
  124px.
-->
<script lang="ts" module>
  /** Stronghold dot-strip cell value. */
  export type StrongholdDotCell = "W" | "L" | "DNC";

  /** Pure: pad / right-window a results array to the fixed cell count.
   *  Padding is LEFT-side (oldest end), so the rightmost cells always
   *  show the party's most recent results. When the input is longer
   *  than `cell_count`, the oldest cells are dropped and the most
   *  recent `cell_count` are kept. Exported so tests can pin the
   *  boundary cases without mounting. */
  export function padResults(
    results: readonly ("W" | "L")[],
    cell_count: number,
  ): StrongholdDotCell[] {
    const out: StrongholdDotCell[] = [...results];
    while (out.length < cell_count) out.unshift("DNC");
    return out.slice(-cell_count);
  }
</script>

<script lang="ts">
  interface Props {
    /** Chronological per-event outcomes (oldest first). */
    results: readonly ("W" | "L")[];
    /** Party brand colour for `W` cells (any CSS colour string). */
    brand_colour: string;
    /** Number of cells in the strip. Defaults to 10. */
    cell_count?: number;
  }
  let { results, brand_colour, cell_count = 10 }: Props = $props();

  const padded = $derived(padResults(results, cell_count));
  const width = $derived(cell_count * 12 + 4);
</script>

<svg
  width={width}
  height="10"
  viewBox={`0 0 ${width} 10`}
  aria-hidden="true"
  data-testid="stronghold-dot-strip"
>
  <defs>
    <pattern
      id="stronghold-dnc-hatch"
      patternUnits="userSpaceOnUse"
      width="4"
      height="4"
      patternTransform="rotate(45)"
    >
      <rect width="4" height="4" fill="var(--surface)" />
      <line x1="0" y1="0" x2="0" y2="4" stroke="#cbd5e1" stroke-width="1" />
    </pattern>
  </defs>
  {#each padded as r, i (i)}
    <circle
      cx={6 + i * 12}
      cy="5"
      r="3"
      fill={r === "W"
        ? brand_colour
        : r === "L"
          ? "var(--surface)"
          : "url(#stronghold-dnc-hatch)"}
      stroke={r === "L" ? "#cbd5e1" : "none"}
      stroke-width="1"
      data-cell={r}
    />
  {/each}
</svg>
