// Pure-helper tests for `computeHoverCardPosition`
// (standard-map-hover-card plan, Row 2 oracle). Per repo vitest doctrine the
// `HoverCardShell.svelte` chrome is covered by the @elections Playwright smoke
// once a surface mounts it (Rows 3/4); vitest covers the placement formula in
// isolation - edge-flip + clamp - with no DOM.

import { describe, it, expect } from "vitest";

import { computeHoverCardPosition } from "../hover-card-position";

const CARD_W = 256;
const CARD_H = 140;
const OFFSET = 12;

describe("computeHoverCardPosition", () => {
  it("anchors bottom-right of the cursor in the interior", () => {
    const cursorX = 100;
    const cursorY = 100;
    const { left, top } = computeHoverCardPosition({
      cursorX,
      cursorY,
      containerW: 1000,
      containerH: 800,
    });
    expect(left).toBe(cursorX + OFFSET);
    expect(top).toBe(cursorY + OFFSET);
  });

  it("flips LEFT when the cursor is near the right edge", () => {
    const cursorX = 980;
    const containerW = 1000;
    const { left } = computeHoverCardPosition({
      cursorX,
      cursorY: 400,
      containerW,
      containerH: 800,
    });
    // The card sits to the LEFT of the cursor and never past the right edge.
    expect(left).toBeLessThan(cursorX);
    expect(left).toBe(cursorX - OFFSET - CARD_W);
    expect(left).toBeLessThanOrEqual(containerW - CARD_W);
  });

  it("flips UP when the cursor is near the bottom edge", () => {
    const cursorY = 790;
    const containerH = 800;
    const { top } = computeHoverCardPosition({
      cursorX: 400,
      cursorY,
      containerW: 1000,
      containerH,
    });
    // The card sits ABOVE the cursor and never past the bottom edge.
    expect(top).toBeLessThan(cursorY);
    expect(top).toBe(cursorY - OFFSET - CARD_H);
    expect(top).toBeLessThanOrEqual(containerH - CARD_H);
  });

  it("clamps the fixed box fully inside the container for every cursor", () => {
    const containerW = 1000;
    const containerH = 800;
    const maxLeft = containerW - CARD_W;
    const maxTop = containerH - CARD_H;
    const probes: ReadonlyArray<readonly [number, number]> = [
      [-50, -50],
      [0, 0],
      [1, 1],
      [500, 400],
      [999, 1],
      [1, 799],
      [1500, 1500],
      [980, 790],
    ];
    for (const [cursorX, cursorY] of probes) {
      const { left, top } = computeHoverCardPosition({
        cursorX,
        cursorY,
        containerW,
        containerH,
      });
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left).toBeLessThanOrEqual(maxLeft);
      expect(top).toBeGreaterThanOrEqual(0);
      expect(top).toBeLessThanOrEqual(maxTop);
    }
  });

  it("clamps to 0 when the container is smaller than the card", () => {
    const { left, top } = computeHoverCardPosition({
      cursorX: 50,
      cursorY: 40,
      containerW: 100,
      containerH: 80,
    });
    expect(left).toBe(0);
    expect(top).toBe(0);
  });
});
