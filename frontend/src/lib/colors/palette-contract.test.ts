// Palette-system contract (plan Row 4): proves the configurable + detached
// colour-token system stays sound and the topic->ramp anti-pattern is absent.
//
// Pure vitest, node env (no DOM): getComputedStyle is undefined, so `rampHue`
// returns the RAMP_HUES constants and `hueForDirection` emits 160/25/250.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { CATEGORICAL_PALETTES, RAMP_HUES } from "./palettes";
import { TOPIC_CATEGORICAL, topicCategoricalPalette } from "./topic-palette";
import { hueForDirection, type Direction } from "../indicators";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const TOPIC_PALETTE_SRC = readFileSync(resolve(HERE, "topic-palette.ts"), "utf8");

describe("palette contract", () => {
  it("every TOPIC_CATEGORICAL entry resolves to a registered, non-empty palette", () => {
    const entries = Object.entries(TOPIC_CATEGORICAL);
    expect(entries.length, "TOPIC_CATEGORICAL must seed at least one family").toBeGreaterThan(0);
    for (const [topic, name] of entries) {
      const palette = CATEGORICAL_PALETTES[name];
      expect(
        Array.isArray(palette) && palette.length > 0,
        `topic '${topic}' -> palette '${name}' is not a registered non-empty CATEGORICAL_PALETTES entry`,
      ).toBe(true);
      // The public resolver agrees with the raw map.
      expect(
        topicCategoricalPalette(topic),
        `topicCategoricalPalette('${topic}') must return the '${name}' palette`,
      ).toBe(palette);
    }
    // Unmapped families resolve to null (CATEGORICAL only, no silent default).
    expect(topicCategoricalPalette("definitely_not_a_topic")).toBeNull();
  });

  it("each Direction resolves via hueForDirection to its RAMP_HUES constant (node fallback)", () => {
    const cases: Array<[Direction, number]> = [
      ["higher_is_better", RAMP_HUES.positive],
      ["lower_is_better", RAMP_HUES.negative],
      ["neutral", RAMP_HUES.neutral],
    ];
    for (const [direction, expected] of cases) {
      const hue = hueForDirection(direction);
      expect(Number.isFinite(hue), `hueForDirection('${direction}') is not a finite number`).toBe(true);
      expect(hue, `hueForDirection('${direction}') must equal RAMP_HUES (${expected})`).toBe(expected);
    }
  });

  it("topic-palette.ts encodes NO topic -> ramp/choropleth-hue anti-pattern", () => {
    // Plan section 0.4: topic -> CATEGORICAL palette ONLY. The module must not
    // reference the directional-ramp machinery, and must not RETURN a ramp /
    // choropleth hue. (Comments may DISCUSS the doctrine; this asserts the
    // forbidden machinery SYMBOLS are absent and no `return ...hue/choropleth`
    // statement exists.)
    const FORBIDDEN_SYMBOLS = [
      "hueForDirection",
      "RAMP_HUES",
      "rampHue",
      "sequentialSwatch",
      "fillForValue",
    ];
    const referenced = FORBIDDEN_SYMBOLS.filter((s) => TOPIC_PALETTE_SRC.includes(s));
    expect(
      referenced,
      `topic-palette.ts must not reference directional-ramp machinery (found: ${referenced.join(", ")}). ` +
        "Topic -> categorical palette ONLY; ramps source their hue from indicators.ts::hueForDirection.",
    ).toEqual([]);

    const hueReturn = /return[^;\n]*\b(?:hue|choropleth)\b/i.exec(TOPIC_PALETTE_SRC);
    expect(
      hueReturn,
      `topic-palette.ts must not return a ramp/choropleth hue (matched: "${hueReturn?.[0] ?? ""}"). ` +
        "Topic colour is CATEGORICAL only.",
    ).toBeNull();
  });
});
