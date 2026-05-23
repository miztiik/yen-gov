// Public surface of the StackedTrendV2 module (Phase 2.1a structural slice).
//
// Per R-08 Branch by Abstraction: this module ships ALONGSIDE
// `frontend/src/lib/charts/stacked-trend/` (v1). v1 stays untouched until
// the last caller migrates. Consumers should import from this `index.ts`
// (not from the individual files) so the internal layout stays
// refactorable while v2 is incomplete.

export type {
  StackedTrendV2Bar,
  StackedTrendV2Category,
  StackedTrendV2Headline,
  StackedTrendV2Honesty,
  StackedTrendV2Model,
  StackedTrendV2Segment,
  StackedTrendV2Source,
} from "./types";

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
