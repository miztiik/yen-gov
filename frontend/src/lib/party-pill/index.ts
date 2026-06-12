// E2 PartyPill public surface barrel.
export { default as PartyPill } from "./PartyPill.svelte";
export { default as PartyTooltip } from "./PartyTooltip.svelte";
export {
  pickInkForFill,
  resolvePartyPill,
  type PartyPillResolved,
  type PartyPillTreatment,
} from "./party-pill-resolve";
// PR-1 tooltip state machine (pure helpers + types exported from
// PartyPill.svelte's <script module>). Consumers that need to drive
// the tooltip imperatively (none today; reserved for future chart
// affordances that want to surface party metadata on click without
// rendering a PartyPill chip) reach for these via the barrel.
export {
  shouldOpenTooltipFor,
  tooltipClosed,
  tooltipReducer,
  type TooltipState,
} from "./PartyPill.svelte";
// PR-1 tooltip view-model (pure projection from PartyMeta -> renderable
// shape). Exported so the tooltip's vitest can pin every conditional
// without mounting Svelte.
export {
  buildTooltipViewModel,
  clampTooltipPlacement,
  type TooltipViewModel,
} from "./PartyTooltip.svelte";
