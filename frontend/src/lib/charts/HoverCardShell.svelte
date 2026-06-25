<script lang="ts">
  // HoverCardShell - thin positioned wrapper for the standard map hover card
  // (standard-map-hover-card plan, Row 2). Chrome ONLY: it computes the
  // fixed-size card's on-screen position (with container edge-flip + clamp via
  // the pure `computeHoverCardPosition` helper) and renders the card HTML
  // string from `renderTooltipCard`. NO business logic - the 224x120 card, the
  // left party bar, and all content live INSIDE the `html` string so any map
  // surface can render the identical card via `{@html}`.
  //
  // CLAUDE.md section 0: no aria/role; visible affordances only.

  import { computeHoverCardPosition } from "./hover-card-position";

  interface Props {
    /** Cursor x within the container (px). */
    x: number;
    /** Cursor y within the container (px). */
    y: number;
    /** The complete card markup from `renderTooltipCard`. */
    html: string;
    /** Container width (px) used for the right-edge flip + clamp. */
    containerW: number;
    /** Container height (px) used for the bottom-edge flip + clamp. */
    containerH: number;
    /** Optional test hook forwarded to the positioned div. */
    testid?: string;
  }

  let { x, y, html, containerW, containerH, testid }: Props = $props();

  const pos = $derived(
    computeHoverCardPosition({
      cursorX: x,
      cursorY: y,
      containerW,
      containerH,
    }),
  );
</script>

<div
  class="pointer-events-none absolute z-10"
  style:left="{pos.left}px"
  style:top="{pos.top}px"
  data-testid={testid}
>
  {@html html}
</div>
