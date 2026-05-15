<script lang="ts">
  /**
   * DirectionLegendCue — single-character arrow + word that tells the
   * citizen which direction is "good" for this indicator. (Phase 2 of
   * the viz-layer plan; consumes IndicatorMeta.direction.)
   *
   * The audit (docs/reference/data-coverage-report.md §6) found that
   * many indicators are direction-asymmetric — for IMR, lower is
   * better; for HDI, higher is better; for inflation, neither — and
   * the legend gave no cue. The colour ramp's dark end always means
   * "more of the thing", which can be the BAD end. Without explicit
   * disclosure, a darker = bigger = worse map gets read as a "ranking
   * of best states."
   *
   * The cue is deliberately tiny — one ↑/↓/↔ glyph + 1-2 words —
   * because it must fit inside a chart legend without crowding the
   * actual scale.
   */

  import type { Direction } from "../indicators";

  interface Props {
    direction: Direction;
    /** Optional terse override word; defaults to "better" / "worse" /
     *  "neutral". */
    label?: string;
  }

  const { direction, label }: Props = $props();

  const cue = $derived(makeCue(direction, label));

  function makeCue(d: Direction, override?: string): { glyph: string; text: string } {
    switch (d) {
      case "higher_is_better":
        return { glyph: "↑", text: override ?? "higher = better" };
      case "lower_is_better":
        return { glyph: "↓", text: override ?? "lower = better" };
      case "neutral":
        return { glyph: "↔", text: override ?? "neither direction is good or bad" };
    }
  }
</script>

<span
  class="direction-cue inline-flex items-center gap-1 text-[11px] font-medium text-slate-600"
  data-direction={direction}
>
  <span class="font-bold leading-none">{cue.glyph}</span>
  <span>{cue.text}</span>
</span>
