// Topic-family -> categorical palette mapping.
//
// Pure module: no Svelte, no DOM. Maps a topic-family slug (the live
// `topics[].id` values from datasets/taxonomy/topics.json) to a NAMED
// categorical palette in CATEGORICAL_PALETTES. This binding is
// CATEGORICAL-ONLY: it colours qualitative breakdowns and topic-family chrome.
//
// CRITICAL (plan section 0.4): topic -> CATEGORICAL palette ONLY. A topic
// family must NEVER select a directional choropleth ramp colour. Directional
// ramps take their colour from the DIRECTION-driven resolver in indicators.ts
// (good/bad valence) so the dark end always reads as "high value"; binding a
// topic-family colour to that ramp would destroy the valence (e.g.
// infant-mortality and vaccination would both render in the health family
// colour). Keep this module a topic -> palette-name map and nothing more.

import { CATEGORICAL_PALETTES } from "./palettes";

/**
 * Topic-family slug -> registered CATEGORICAL_PALETTES key. Slugs are the live
 * `topics[].id` values from datasets/taxonomy/topics.json. The contract test
 * asserts every value here resolves to a non-empty registered palette;
 * exhaustive family coverage is NOT required.
 */
export const TOPIC_CATEGORICAL: Record<string, string> = {
  fiscal: "set2",
  energy: "paired",
  economy: "set2",
  demography: "paired",
  environment: "set2",
  prices: "paired",
  health: "set2",
  governance: "paired",
  education: "set2",
  agriculture: "set2",
  work: "paired",
  crime: "set2",
};

/**
 * Resolve a topic family's categorical palette (array of hex strings), or null
 * when the topic has no mapping. CATEGORICAL only - never a ramp colour.
 */
export function topicCategoricalPalette(topic: string): readonly string[] | null {
  const name = TOPIC_CATEGORICAL[topic];
  if (name == null) return null;
  const palette = CATEGORICAL_PALETTES[name];
  return palette && palette.length > 0 ? palette : null;
}
