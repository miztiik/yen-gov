// Temporal viewport — barrel module.
//
// Re-exports the public surface of the temporal-viewport primitive.
// Renderers import from this barrel rather than reaching across the
// types / helpers split so the boundary stays one entry point.

export type {
  TemporalDomain,
  TemporalDomainKind,
  TemporalPreset,
  TemporalWindow,
  TemporalWindowIndices,
} from "./types";

export {
  KNOWN_DOMAIN_KINDS,
  KNOWN_PRESETS,
  buildDomain,
  clampWindow,
  filterItemsToWindow,
  fullWindow,
  isFullWindow,
  parseLeadingYear,
  presetWindow,
  type PresetWindowOptions,
} from "./helpers";

export { default as TemporalViewportBrush } from "./TemporalViewportBrush.svelte";
export { presetLabel } from "./TemporalViewportBrush.svelte";
