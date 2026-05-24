// Tests for $lib/yenask/timing.ts (D-22 Slice A sum-invariant helper).
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-22 — Jony AMEND verdict on Slice A. Pure-function tests covering:
// - null in any of the three phase fields → invariant not computable
// - sum within threshold of wall_ms → null (no row rendered)
// - sum below wall by > threshold → positive delta (SDK partial)
// - sum above wall by > threshold → negative delta (SDK overlap)
// - threshold floor at 5ms (sub-50ms turns)
// - threshold ceiling at 10% of wall_ms

import { describe, expect, it } from "vitest";
import { untrackedDelta } from "./timing";

describe("untrackedDelta", () => {
  it("returns null when encode_ms is null", () => {
    expect(
      untrackedDelta({
        encode_ms: null,
        generate_ms: 100,
        decode_ms: 50,
        wall_ms: 200,
      }),
    ).toBeNull();
  });

  it("returns null when generate_ms is null", () => {
    expect(
      untrackedDelta({
        encode_ms: 20,
        generate_ms: null,
        decode_ms: 50,
        wall_ms: 200,
      }),
    ).toBeNull();
  });

  it("returns null when decode_ms is null", () => {
    expect(
      untrackedDelta({
        encode_ms: 20,
        generate_ms: 100,
        decode_ms: null,
        wall_ms: 200,
      }),
    ).toBeNull();
  });

  it("returns null when sum matches wall_ms exactly", () => {
    expect(
      untrackedDelta({
        encode_ms: 50,
        generate_ms: 1500,
        decode_ms: 100,
        wall_ms: 1650,
      }),
    ).toBeNull();
  });

  it("returns null when delta is below 5ms floor on sub-50ms turn", () => {
    // wall=40, sum=37, delta=3 — 10% threshold would be 4ms (rounded);
    // 5ms floor wins; 3 < 5 → null
    expect(
      untrackedDelta({
        encode_ms: 5,
        generate_ms: 30,
        decode_ms: 2,
        wall_ms: 40,
      }),
    ).toBeNull();
  });

  it("returns null when delta is below 10% threshold on large turn", () => {
    // wall=5000, sum=4800, delta=200 — 10% = 500; 200 < 500 → null
    expect(
      untrackedDelta({
        encode_ms: 100,
        generate_ms: 4500,
        decode_ms: 200,
        wall_ms: 5000,
      }),
    ).toBeNull();
  });

  it("returns positive delta when SDK reports partial (sum below wall)", () => {
    // wall=2000, sum=1500, delta=+500 — 10% = 200; 500 ≥ 200 → 500
    expect(
      untrackedDelta({
        encode_ms: 80,
        generate_ms: 1300,
        decode_ms: 120,
        wall_ms: 2000,
      }),
    ).toBe(500);
  });

  it("returns negative delta when phases overlap (sum exceeds wall)", () => {
    // wall=1000, sum=1300, delta=-300 — 10% = 100; |−300| ≥ 100 → −300
    expect(
      untrackedDelta({
        encode_ms: 200,
        generate_ms: 1000,
        decode_ms: 100,
        wall_ms: 1000,
      }),
    ).toBe(-300);
  });

  it("uses 5ms floor when wall_ms is 0 (edge: ready-cached miss)", () => {
    // wall=0, sum=4, delta=-4 — 10% = 0 → floor 5; |−4| < 5 → null
    expect(
      untrackedDelta({
        encode_ms: 1,
        generate_ms: 2,
        decode_ms: 1,
        wall_ms: 0,
      }),
    ).toBeNull();
  });

  it("uses 5ms floor when wall_ms is very small", () => {
    // wall=20, sum=12, delta=8 — 10% = 2 → floor 5; 8 ≥ 5 → 8
    expect(
      untrackedDelta({
        encode_ms: 4,
        generate_ms: 6,
        decode_ms: 2,
        wall_ms: 20,
      }),
    ).toBe(8);
  });

  it("treats 0 as a measurement (not null) for any phase", () => {
    // wall=100, sum=100 (encode=0 measured, generate=80, decode=20) → null
    expect(
      untrackedDelta({
        encode_ms: 0,
        generate_ms: 80,
        decode_ms: 20,
        wall_ms: 100,
      }),
    ).toBeNull();
  });
});
