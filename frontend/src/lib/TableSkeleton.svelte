<script lang="ts" module>
  // Content-shaped loading placeholder for a results table (perf plan
  // Row 6): a header band plus N ghost rows, so the page does not jump
  // when the real table lands. Built on the shared <Skeleton> primitive.

  /** Clamp the ghost-row count to a sane positive integer (default 8).
   *  Pure - the testable surface (frontend vitest is node-env). */
  export function tableSkeletonRows(rows: number | undefined): number {
    if (rows == null || !Number.isFinite(rows) || rows < 1) return 8;
    return Math.floor(rows);
  }
</script>

<script lang="ts">
  import Skeleton from "./Skeleton.svelte";

  interface Props {
    /** Number of ghost body rows. Defaults to 8. */
    rows?: number;
    /** Height of each ghost body row. */
    rowHeight?: string;
  }

  let { rows = 8, rowHeight = "2rem" }: Props = $props();
  const bodyRows = $derived(Array.from({ length: tableSkeletonRows(rows) }, (_, i) => i));
</script>

<div class="space-y-2" data-component="table-skeleton" aria-hidden="true">
  <!-- Header band -->
  <Skeleton height="2.5rem" />
  {#each bodyRows as i (i)}
    <Skeleton height={rowHeight} />
  {/each}
</div>
