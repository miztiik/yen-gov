<script lang="ts" module>
  // Content-shaped loading placeholder for a KPI tile grid (perf plan
  // Row 6). Mirrors the StateOverview KPI-grid shape so the page does not
  // jump when the real tiles land (zero layout shift). Built on the shared
  // <Skeleton> primitive (which respects prefers-reduced-motion). One of
  // exactly three closed content shapes (KPI grid / table / map frame);
  // NOT a skeleton-from-spec framework.

  /** Clamp the tile count to a sane positive integer (default 4). Pure -
   *  the testable surface (frontend vitest is node-env; the Svelte body is
   *  the rendering wrapper, mirroring Skeleton.svelte's `skeletonStyle`). */
  export function kpiTileCount(count: number | undefined): number {
    if (count == null || !Number.isFinite(count) || count < 1) return 4;
    return Math.floor(count);
  }
</script>

<script lang="ts">
  import Skeleton from "./Skeleton.svelte";

  interface Props {
    /** Number of ghost tiles. Defaults to 4 (the common KPI strip width). */
    count?: number;
    /** Height of each ghost tile. */
    tileHeight?: string;
  }

  let { count = 4, tileHeight = "4.5rem" }: Props = $props();
  const tiles = $derived(Array.from({ length: kpiTileCount(count) }, (_, i) => i));
</script>

<div
  class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
  data-component="kpi-grid-skeleton"
  aria-hidden="true"
>
  {#each tiles as i (i)}
    <Skeleton height={tileHeight} />
  {/each}
</div>
