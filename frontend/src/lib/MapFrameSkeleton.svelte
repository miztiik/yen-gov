<script lang="ts" module>
  // Content-shaped loading placeholder for a map (perf plan Row 6): a
  // framed neutral box at the FINAL map dimensions with a calm pending
  // treatment (a faint cell grid + soft pulse). It needs NO fetch, so it
  // shows instantly while the geometry + data load, and occupies the same
  // box as the eventual map (zero layout shift). The recognisable
  // map-frame shape - not a bare rectangle, not a centred spinner -
  // telegraphs "a map is coming". The progressive state-silhouette
  // first-paint (once geometry resolves) is a separate (Row 7) concern.

  /** Build the inline-style string for the frame (width/height). Pure -
   *  the testable surface (frontend vitest is node-env), mirroring
   *  Skeleton.svelte's `skeletonStyle`. Returns "" when both omitted. */
  export function mapFrameStyle(args: { width?: string; height?: string }): string {
    const parts: string[] = [];
    if (args.width) parts.push(`width: ${args.width};`);
    if (args.height) parts.push(`height: ${args.height};`);
    return parts.join(" ");
  }
</script>

<script lang="ts">
  interface Props {
    /** Final map height so the placeholder occupies the same box (no CLS). */
    height?: string;
    /** Final map width. Defaults to 100% (fills the column). */
    width?: string;
  }

  let { height = "440px", width = "100%" }: Props = $props();
  const style = $derived(mapFrameStyle({ width, height }));
</script>

<div
  class="map-frame-skeleton"
  data-component="map-frame-skeleton"
  aria-hidden="true"
  {style}
></div>

<style>
  .map-frame-skeleton {
    border: 1px solid var(--surface-sunken);
    border-radius: var(--r-md);
    background-color: var(--surface-sunken);
    /* Faint cell grid - the calm "pending" treatment (no spinner). The
       grid tint is a visual constant (like Skeleton's shimmer rhythm),
       not a token. */
    background-image:
      linear-gradient(to right, rgba(100, 116, 139, 0.1) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(100, 116, 139, 0.1) 1px, transparent 1px);
    background-size: 28px 28px;
    display: block;
    animation: map-frame-pulse 1600ms ease-in-out infinite;
  }
  @keyframes map-frame-pulse {
    0%,
    100% {
      opacity: 0.6;
    }
    50% {
      opacity: 0.9;
    }
  }
  /* a11y is a project non-goal, but Skeleton already honours this and the
     drift would look inconsistent if the map frame kept pulsing. */
  @media (prefers-reduced-motion: reduce) {
    .map-frame-skeleton {
      animation: none;
      opacity: 0.75;
    }
  }
</style>
