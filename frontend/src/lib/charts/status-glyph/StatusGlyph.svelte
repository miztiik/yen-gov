<script lang="ts">
  // StatusGlyph — direction-coloured marker rendered at the latest
  // visible point of a state series when a national reference line
  // is shown.
  //
  // Per parent plan section 20.11 (Max + Hans):
  //
  //   - The glyph carries the position-against-reference verdict
  //     under the indicator's direction semantics. The verdict is
  //     computed once by `computeStatusVerdict` and passed in; the
  //     glyph is a pure SVG primitive.
  //
  //   - Colour mapping (mirrors `ranked-comparison/helpers.ts`
  //     gapDirection vocabulary + IndicatorCard token palette):
  //       'better'  -> teal/green   rgb(22 163 74)  -- slate-700-on-emerald-500
  //       'worse'   -> red          rgb(220 38 38)  -- slate-700-on-red-500
  //       'equal'   -> amber        rgb(217 119 6)  -- amber-600
  //       'neutral' -> slate        rgb(100 116 139) -- slate-500
  //       'missing' -> nothing rendered (the parent renderer should
  //                    not mount StatusGlyph for a missing-data series;
  //                    we honour the verdict here as a defence in depth)
  //
  //   - SVG primitive: a small filled triangle pointing UP (state is
  //     "ahead" of reference under its own direction), DOWN (state is
  //     "behind"), or a filled CIRCLE (state equal to reference) /
  //     hollow CIRCLE (neutral direction, undecided reading).
  //
  //   - The mapping POSITION x DIRECTION -> SHAPE:
  //
  //       better -> triangle UP    (state is in the good zone)
  //       worse  -> triangle DOWN  (state is in the bad zone)
  //       equal  -> filled circle  (state matches reference exactly)
  //       neutral -> hollow circle (direction undecided)
  //
  //   - No `<title>` / no aria per CLAUDE.md section 0 (a11y descoped).
  //     The tooltip data is consumed by the parent IndicatorCard's
  //     existing "About this data" disclosure.
  //
  //   - The glyph is positional, not animated. Citizen reads it at
  //     a glance alongside the state line's last point.

  import type { StatusVerdict } from "./helpers";

  interface Props {
    /** Verdict from `computeStatusVerdict(state, reference, direction)`. */
    verdict: StatusVerdict;
    /** Bounding box edge in CSS px. Default 12. */
    size_px?: number;
    /** SVG x coordinate of the glyph centre (caller positions it). */
    cx: number;
    /** SVG y coordinate of the glyph centre. */
    cy: number;
  }

  let { verdict, size_px = 12, cx, cy }: Props = $props();

  // Colour mapping. Kept inline because the palette is tiny + tied
  // to a closed-union verdict; pulling it into a token table would
  // be over-engineering for 4 colours.
  function colourFor(v: StatusVerdict): string {
    switch (v) {
      case "better":
        return "rgb(22 163 74)"; // green-600
      case "worse":
        return "rgb(220 38 38)"; // red-600
      case "equal":
        return "rgb(217 119 6)"; // amber-600
      case "neutral":
        return "rgb(100 116 139)"; // slate-500
      case "missing":
        return "transparent";
    }
  }

  const colour = $derived(colourFor(verdict));
  const half = $derived(size_px / 2);

  // Triangle path centred on (cx, cy). `up=true` -> point up,
  // `up=false` -> point down. Equilateral-ish for tidy reading at
  // 10-16 px sizes.
  function trianglePath(up: boolean): string {
    const top_y = cy - half;
    const bottom_y = cy + half;
    const left_x = cx - half;
    const right_x = cx + half;
    if (up) {
      return `M ${cx.toFixed(2)} ${top_y.toFixed(2)} L ${right_x.toFixed(2)} ${bottom_y.toFixed(2)} L ${left_x.toFixed(2)} ${bottom_y.toFixed(2)} Z`;
    }
    return `M ${left_x.toFixed(2)} ${top_y.toFixed(2)} L ${right_x.toFixed(2)} ${top_y.toFixed(2)} L ${cx.toFixed(2)} ${bottom_y.toFixed(2)} Z`;
  }
</script>

{#if verdict !== "missing"}
  <g
    class="status-glyph"
    data-component="status-glyph"
    data-verdict={verdict}
  >
    {#if verdict === "better"}
      <path d={trianglePath(true)} fill={colour} />
    {:else if verdict === "worse"}
      <path d={trianglePath(false)} fill={colour} />
    {:else if verdict === "equal"}
      <circle {cx} {cy} r={half * 0.85} fill={colour} />
    {:else if verdict === "neutral"}
      <circle {cx} {cy} r={half * 0.85} fill="none" stroke={colour} stroke-width="1.5" />
    {/if}
  </g>
{/if}

<style>
  .status-glyph {
    pointer-events: none;
  }
</style>
