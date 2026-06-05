// Vitest - ChartShell state helpers (U5 sub-plan U5a).
//
// Mirrors the shape of `actions.test.ts` (the existing pure-helper
// test in this directory). Covers the resolver's normalisation
// behaviour + the two default-copy constants.

import { describe, expect, it } from "vitest";

import {
  DEFAULT_EMPTY_MESSAGE,
  DEFAULT_ERROR_MESSAGE,
  resolveChartShellState,
  type ChartShellState,
} from "./state";

describe("resolveChartShellState", () => {
  it("returns 'data' when the input is null", () => {
    expect(resolveChartShellState(null)).toBe("data");
  });

  it("returns 'data' when the input is undefined", () => {
    expect(resolveChartShellState(undefined)).toBe("data");
  });

  it("returns 'data' explicitly when the input is 'data'", () => {
    expect(resolveChartShellState("data")).toBe("data");
  });

  it("passes through every non-default state verbatim", () => {
    const states: ChartShellState[] = ["loading", "error", "empty"];
    for (const s of states) {
      expect(resolveChartShellState(s)).toBe(s);
    }
  });

  it("defends against runtime-unknown values by defaulting to 'data'", () => {
    // The TS signature already restricts this; the runtime fallback
    // catches a caller that types around the contract.
    expect(
      // @ts-expect-error - intentional invalid input for runtime cover
      resolveChartShellState("loading_in_progress"),
    ).toBe("data");
    expect(
      // @ts-expect-error - intentional invalid input for runtime cover
      resolveChartShellState(""),
    ).toBe("data");
  });
});

describe("default-copy constants", () => {
  it("DEFAULT_ERROR_MESSAGE is a non-empty citizen-readable string", () => {
    expect(typeof DEFAULT_ERROR_MESSAGE).toBe("string");
    expect(DEFAULT_ERROR_MESSAGE.length).toBeGreaterThan(0);
    // The error copy must NOT be technical noise like "fetch failed"
    // or a stack trace fragment. The current "Data unavailable" reads
    // as a citizen-facing one-liner.
    expect(DEFAULT_ERROR_MESSAGE).not.toMatch(/error|exception|stack/i);
  });

  it("DEFAULT_EMPTY_MESSAGE is a non-empty citizen-readable string", () => {
    expect(typeof DEFAULT_EMPTY_MESSAGE).toBe("string");
    expect(DEFAULT_EMPTY_MESSAGE.length).toBeGreaterThan(0);
    expect(DEFAULT_EMPTY_MESSAGE).not.toMatch(/null|undefined|nan/i);
  });
});
