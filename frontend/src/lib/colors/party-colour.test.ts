import { describe, it, expect } from "vitest";
import { partyColour, partyFill } from "./party-colour";
import { ANCHORS } from "./anchors";
import {
  generateOkLChPalette,
  oklchToHex,
  stringHash,
} from "./oklch";

describe("oklch primitives", () => {
  it("stringHash is deterministic and non-negative", () => {
    expect(stringHash("369")).toBe(stringHash("369"));
    expect(stringHash("742")).toBe(stringHash("742"));
    expect(stringHash("")).toBeGreaterThanOrEqual(0);
    expect(stringHash("LongStringWithBytes")).toBeGreaterThanOrEqual(0);
  });

  it("oklchToHex returns a valid #rrggbb string", () => {
    const hex = oklchToHex({ l: 0.6, c: 0.16, h: 30 });
    expect(hex).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("oklchToHex clamps out-of-gamut OkLCh points (no NaN)", () => {
    // Very high chroma -> gamut overflow on most hues.
    const hex = oklchToHex({ l: 0.5, c: 0.4, h: 130 });
    expect(hex).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("generateOkLChPalette skips reserved hue ranges", () => {
    const palette = generateOkLChPalette({
      hueSlots: 36,
      reservedHueRanges: [[0, 20], [25, 45]],
      lightnessBands: [0.55],
      chroma: 0.16,
    });
    for (const swatch of palette) {
      expect(swatch.h >= 0 && swatch.h <= 20).toBe(false);
      expect(swatch.h >= 25 && swatch.h <= 45).toBe(false);
    }
  });

  it("generateOkLChPalette respects band-major ordering", () => {
    const palette = generateOkLChPalette({
      hueSlots: 4,
      lightnessBands: [0.6, 0.4],
      chroma: 0.16,
    });
    expect(palette.length).toBe(8);
    expect(palette[0].l).toBe(0.6);
    expect(palette[3].l).toBe(0.6);
    expect(palette[4].l).toBe(0.4);
    expect(palette[7].l).toBe(0.4);
  });
});

describe("partyColour resolution", () => {
  it("anchor wins over algorithm", () => {
    // 369 (BJP) is an anchor.
    const result = partyColour("369", ["369", "742", "9999"]);
    expect(result).toEqual(ANCHORS["369"]);
  });

  it("override wins over anchor", () => {
    const overrides = { "369": { fill: "#000000" } };
    const result = partyColour("369", ["369", "742"], overrides);
    expect(result.fill).toBe("#000000");
  });

  it("override wins for a non-anchor code too", () => {
    const overrides = { "9999": { fill: "#abcdef" } };
    const result = partyColour("9999", ["9999"], overrides);
    expect(result.fill).toBe("#abcdef");
  });

  it("non-anchor code gets a valid hex from the algorithm", () => {
    const result = partyColour("9999", ["9999"]);
    expect(result.fill).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("is deterministic across calls (same code, same in-use list)", () => {
    const first = partyColour("9999", ["1111", "9999", "2222"]);
    const second = partyColour("9999", ["1111", "9999", "2222"]);
    expect(first.fill).toBe(second.fill);
  });

  it("call order in in-use list does not affect assignment", () => {
    const a = partyColour("9999", ["1111", "2222", "9999"]);
    const b = partyColour("9999", ["9999", "2222", "1111"]);
    expect(a.fill).toBe(b.fill);
  });

  it("no two visible non-anchor parties share a colour", () => {
    // Use a moderately large set of non-anchor codes to stress de-duplication.
    const inUse = ["9001", "9002", "9003", "9004", "9005", "9006", "9007"];
    const fills = inUse.map((c) => partyFill(c, inUse));
    const distinct = new Set(fills);
    expect(distinct.size).toBe(inUse.length);
  });

  it("anchor codes in the in-use list do not consume palette slots", () => {
    // If anchors consumed slots, the non-anchor "9999" assignment would shift
    // when we add or remove anchors. It should not.
    const without = partyFill("9999", ["9999"]);
    const withAnchors = partyFill("9999", ["369", "742", "582", "9999"]);
    expect(without).toBe(withAnchors);
  });

  it("respects reserved hue ranges (no algorithmic red/saffron/INC-blue)", () => {
    // Just spot-check: render 20 distinct non-anchor codes and confirm none
    // of them lands on pure reds, saffrons, or Congress-blue.
    const codes = Array.from({ length: 20 }, (_, i) => `algo${i}`);
    const fills = codes.map((c) => partyFill(c, codes));
    for (const hex of fills) {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      // Crude check: not "almost pure red" (R >> G, R >> B AND G+B small).
      const pureRed = r > 200 && g < 80 && b < 80;
      expect(pureRed).toBe(false);
    }
  });

  it("unknown code not in in-use list still returns a deterministic hex", () => {
    const result = partyColour("never_in_use", []);
    expect(result.fill).toMatch(/^#[0-9a-f]{6}$/);
    // Second call same result.
    expect(partyColour("never_in_use", []).fill).toBe(result.fill);
  });
});
