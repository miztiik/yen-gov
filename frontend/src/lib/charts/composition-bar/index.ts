// CompositionBar — barrel.
//
// Re-exports the contract + helpers so adapter code can import via a
// single module path. The Svelte renderer lives one level up at
// `frontend/src/lib/charts/CompositionBar.svelte` and is imported by
// Svelte module resolution, not from this barrel.

export {
  MIN_VISUAL_WIDTH_PCT,
  formatSegmentReadout,
  projectSegments,
  segmentsSumMatchesTotal,
  shareOfTotalPct,
  totalSegmentValue,
  type CompositionBarSegmentProjection,
} from "./helpers";

export {
  CompositionBarHonestyBanner,
  CompositionBarModel,
  CompositionBarSegment,
} from "./types";

export {
  CAPTION_FPTP,
  DEFAULT_TOP_N,
  assembleCompositionBar,
  loadCompositionBarElectionSeats,
  projectSourcesV2,
  reduceToTopNWithTail,
  resolvePartyFill,
  sortPartiesBySeats,
  type CompositionBarLoadedRows,
  type CompositionBarPartyRow,
  type CompositionBarSourceJoinRow,
  type CompositionBarV2Source,
  type LoadCompositionBarOptions,
  type LoadedCompositionBar,
} from "./adapter-elections-seats";
