import { describe, expect, it } from "vitest";

import {
  clampWindow,
  defaultWindow,
  panTo,
  setEnd,
  setStart,
  windowSize,
} from "./helpers";

describe("election-window helpers", () => {
  it("defaults to the latest three elections for an 11-election domain", () => {
    expect(defaultWindow({ count: 11 })).toEqual({ start: 8, end: 10 });
  });

  it("defaults to the full domain when fewer than three elections exist", () => {
    expect(defaultWindow({ count: 2 })).toEqual({ start: 0, end: 1 });
    expect(defaultWindow({ count: 1 })).toEqual({ start: 0, end: 0 });
  });

  it("computes inclusive window size", () => {
    expect(windowSize({ start: 3, end: 5 })).toBe(3);
    expect(windowSize({ start: 5, end: 3 })).toBe(0);
  });

  it("normalizes reversed ranges before clamping", () => {
    expect(clampWindow({ start: 7, end: 3 }, { count: 11 })).toEqual({
      start: 3,
      end: 5,
    });
  });

  it("clamps an over-wide range to the maximum size", () => {
    expect(clampWindow({ start: -4, end: 10 }, { count: 11 })).toEqual({
      start: 0,
      end: 2,
    });
  });

  it("respects custom min and max sizes while clamping", () => {
    expect(
      clampWindow({ start: 5, end: 5 }, { count: 11, minSize: 2, maxSize: 4 }),
    ).toEqual({ start: 5, end: 6 });
  });

  it("setStart clamps over-wide left drags to maxSize", () => {
    expect(setStart({ start: 8, end: 10 }, 0, { count: 11 })).toEqual({
      start: 8,
      end: 10,
    });
  });

  it("setStart past the end collapses to a single election", () => {
    expect(setStart({ start: 4, end: 6 }, 9, { count: 11 })).toEqual({
      start: 6,
      end: 6,
    });
  });

  it("setEnd clamps past the right edge within bounds", () => {
    expect(setEnd({ start: 7, end: 8 }, 99, { count: 11 })).toEqual({
      start: 7,
      end: 9,
    });
  });

  it("setEnd before the start collapses to a single election", () => {
    expect(setEnd({ start: 4, end: 6 }, 1, { count: 11 })).toEqual({
      start: 4,
      end: 4,
    });
  });

  it("panTo beyond the right edge preserves size and clamps", () => {
    expect(panTo({ start: 4, end: 6 }, 20, { count: 11 })).toEqual({
      start: 8,
      end: 10,
    });
  });

  it("panTo beyond the left edge clamps to start zero", () => {
    expect(panTo({ start: 4, end: 6 }, -20, { count: 11 })).toEqual({
      start: 0,
      end: 2,
    });
  });
});