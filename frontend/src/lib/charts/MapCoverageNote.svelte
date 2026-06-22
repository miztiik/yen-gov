<script lang="ts">
  /**
   * MapCoverageNote - the one-line honesty caption shown beneath any
   * election choropleth that renders an OLD event on the CURRENT boundary
   * set. It states how many constituencies/districts could be placed and
   * why the rest are grey, and AUTO-HIDES when coverage is complete (the
   * normal current-vintage case).
   *
   * Pure presentation: all logic lives in `./map-coverage.ts`
   * (`coverageNoteText` encodes the auto-hide + the ratified wording). The
   * map component computes `{ matched, total }` from its own
   * feature<->result join and passes it in; this component never fetches,
   * joins, or touches the SVG. One primitive serves PC, AC and district
   * maps unchanged.
   *
   * Doctrine: TODO/20260622-undivided-state-election-history-proposal.md.
   */
  import {
    coverageNoteText,
    type MapCoverage,
    type MapUnit,
  } from "./map-coverage";

  interface Props {
    /** Render-time coverage from the map's feature<->result join. `null`
     *  while the geometry is still loading (renders nothing). */
    coverage: MapCoverage | null;
    /** Countable noun. PC + AC = "constituencies"; admin = "districts". */
    unit?: MapUnit;
    /** Snapshot vintage of the geometry on screen (e.g. "2024"), read by
     *  the parent map from its boundary path's `delim=YYYY` marker. */
    geometryYear?: string | null;
    /** True when the event PREDATES the geometry on screen (an old election
     *  drawn on the current boundary set via the historical name-slug join).
     *  The caption only appears in this case - a current-vintage map never
     *  captions, so structural placeholder misses do not trip it. */
    onOldGeometry?: boolean;
  }

  let {
    coverage,
    unit = "constituencies",
    geometryYear = null,
    onOldGeometry = false,
  }: Props = $props();

  const text = $derived(
    coverageNoteText(coverage, unit, geometryYear, onOldGeometry),
  );
</script>

{#if text}
  <p
    class="px-1 pt-1.5 text-[11px] leading-snug text-slate-500"
    data-testid="map-coverage-note"
  >
    {text}
  </p>
{/if}
