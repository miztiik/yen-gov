// Public surface of the StackedTrendV2 module (Phase 2.1a structural slice).
//
// Per R-08 Branch by Abstraction: this module ships ALONGSIDE
// `frontend/src/lib/charts/stacked-trend/` (v1). v1 stays untouched until
// the last caller migrates. Consumers should import from this `index.ts`
// (not from the individual files) so the internal layout stays
// refactorable while v2 is incomplete.
//
// Phase 2.1b (PR-6) adds the component shell at
// `frontend/src/lib/charts/StackedTrendV2.svelte` (one level up so it
// sits next to v1's `StackedTrend.svelte`). The shell is intentionally
// NOT re-exported here — Svelte components are imported by their
// `.svelte` path directly, not through a barrel.

// Re-export the runtime zod schemas (which carry their inferred types
// via z.infer<typeof X>). A separate `export type { ... }` block would
// duplicate the identifiers and break svelte-check.
export {
  OTHER_CATEGORY_FILL_V2,
  OTHER_CATEGORY_ID_V2,
  StackedTrendV2Bar,
  StackedTrendV2Category,
  StackedTrendV2Headline,
  StackedTrendV2Honesty,
  StackedTrendV2Model,
  StackedTrendV2Segment,
  StackedTrendV2SeriesBreak,
  StackedTrendV2Source,
  StackedTrendV2UnitChange,
} from "./types";

// Phase 2.1 pure view-model helpers. These are plain functions and the
// `ReadoutRow` interface — exporting them by name (not via `*`) keeps
// the public surface explicit. Importers can also reach into
// `./helpers` directly when they want only one symbol.
export {
  DEFAULT_LABEL_THRESHOLD_PCT,
  barTotal,
  isLabelEligible,
  maxBarTotal,
  readoutRows,
  segmentSharePct,
  segmentVisualHeightPct,
  visibleCategoryIds,
} from "./helpers";
export type { ReadoutRow } from "./helpers";
