// TileCartogram label-paint + size-knob tests (plan Row 6 / R-I).
//
// vitest runs node-env (no jsdom), so the size knobs are exercised through
// the pure `tile-cartogram-geometry` helpers the component renders with, and
// the label-paint contract (no stroke halo; per-hex `readableText` fill) is
// proven by a source scan of TileCartogram.svelte - the same house pattern
// as src/contracts/*.test.ts.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { readableText } from "../../boundaries/tooltip-card";
import {
  DEFAULT_HEX_RADIUS,
  cartogramSize,
  cartogramViewBox,
  hexMetrics,
  hexPoints,
  tileBounds,
  type AxialCoord,
} from "../tile-cartogram-geometry";

const chartsDir = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const componentSrc = readFileSync(
  resolve(chartsDir, "TileCartogram.svelte"),
  "utf8",
);

/** The single in-hex `<text>...</text>` code-label block from the component. */
const textBlock = componentSrc.match(/<text[\s\S]*?<\/text>/)?.[0] ?? "";

const tiles: AxialCoord[] = [
  { q: 0, r: 0 },
  { q: 2, r: 1 },
  { q: 1, r: 3 },
];

describe("TileCartogram label paint (Row 6 / R-I #1)", () => {
  it("found the in-hex <text> code label", () => {
    expect(textBlock).not.toBe("");
    expect(textBlock).toContain("data-tile-code");
  });

  it("has no double-stroke halo on the label (no paint-order / stroke*)", () => {
    expect(textBlock).not.toContain("paint-order");
    expect(textBlock).not.toMatch(/\bstroke\b/);
    expect(textBlock).not.toContain("stroke-width");
    expect(textBlock).not.toContain("stroke-opacity");
    expect(textBlock).not.toContain("stroke-linejoin");
  });

  it("paints the label with a per-hex readable fill via readableText", () => {
    expect(textBlock).toMatch(/fill=\{readableText\(/);
    // No hard-coded single fill colour remains on the label.
    expect(textBlock).not.toMatch(/fill="#[0-9a-fA-F]{3,8}"/);
  });

  it("readableText is white on a saturated fill, slate-900 on a pale fill", () => {
    expect(readableText("#1d4ed8")).toBe("#ffffff"); // blue-700 (saturated)
    expect(readableText("#e2e8f0")).toBe("#0f172a"); // slate-200 (pale / pending)
  });
});

describe("TileCartogram size knobs (Row 6 / R-I #2)", () => {
  it("exposes S + height props and raises the default height to 960px", () => {
    expect(componentSrc).toMatch(/height\s*=\s*"960px"/);
    expect(componentSrc).toMatch(/\bS\s*=\s*DEFAULT_HEX_RADIUS\b/);
    expect(componentSrc).toContain("style:height");
  });

  it("the S knob changes the emitted viewBox", () => {
    const b = tileBounds(tiles);
    const vbSmall = cartogramViewBox(b, hexMetrics(DEFAULT_HEX_RADIUS));
    const vbLarge = cartogramViewBox(b, hexMetrics(DEFAULT_HEX_RADIUS * 2));
    expect(vbSmall).not.toBe(vbLarge);
  });

  it("doubling S doubles the cartogram extent (geometry scales linearly)", () => {
    const b = tileBounds(tiles);
    const small = cartogramSize(b, hexMetrics(10));
    const large = cartogramSize(b, hexMetrics(20));
    expect(large.w).toBeCloseTo(small.w * 2, 6);
    expect(large.h).toBeCloseTo(small.h * 2, 6);
  });

  it("the S knob changes the emitted hex vertex geometry", () => {
    const pts10 = hexPoints(hexMetrics(10), 0, 0);
    const pts20 = hexPoints(hexMetrics(20), 0, 0);
    expect(DEFAULT_HEX_RADIUS).toBeGreaterThan(0);
    expect(pts10).not.toBe(pts20);
  });
});
