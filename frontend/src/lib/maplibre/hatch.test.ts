// Pure-module tests for the diagonal-hatch generator (Phase 4 d1).
import { describe, it, expect } from "vitest";
import { diagonalHatch } from "./hatch";

describe("diagonalHatch — shape + pixel layout", () => {
  it("returns an N×N RGBA buffer of the right size", () => {
    const p = diagonalHatch({ size: 8 });
    expect(p.width).toBe(8);
    expect(p.height).toBe(8);
    expect(p.data.length).toBe(8 * 8 * 4);
  });

  it("default colour is slate-400 (#94a3b8) at full opacity on stripes", () => {
    const p = diagonalHatch({ size: 8, stripe_width: 2 });
    // Pixel (0,0): (x+y)%8 == 0 < sw=2 → stripe → opaque slate-400.
    expect([p.data[0], p.data[1], p.data[2], p.data[3]]).toEqual([148, 163, 184, 255]);
  });

  it("non-stripe pixels are fully transparent", () => {
    const p = diagonalHatch({ size: 8, stripe_width: 2 });
    // Pixel (4,0): along = 4 ≥ sw=2 → off. Index = (0*8 + 4)*4 = 16.
    expect([p.data[16], p.data[17], p.data[18], p.data[19]]).toEqual([0, 0, 0, 0]);
  });

  it("stripe wraps seamlessly at the tile edge (top edge → bottom edge match)", () => {
    const p = diagonalHatch({ size: 8, stripe_width: 2 });
    // For the pattern to tile without seams, the column at x=0,y=0 and
    // x=0,y=size-1 must follow the same (x+y)%size rule, which means
    // pixel (0,7): along = 7 ≥ 2 → off. Pixel (0,0): along = 0 → on.
    const onTopLeft = p.data[3] === 255;
    const off_y7 = p.data[(7 * 8 + 0) * 4 + 3] === 0;
    expect(onTopLeft).toBe(true);
    expect(off_y7).toBe(true);
  });

  it("custom stripe colour propagates", () => {
    const p = diagonalHatch({ size: 4, stripe_width: 1, stripe_rgba: [255, 0, 0, 200] });
    expect([p.data[0], p.data[1], p.data[2], p.data[3]]).toEqual([255, 0, 0, 200]);
  });
});
