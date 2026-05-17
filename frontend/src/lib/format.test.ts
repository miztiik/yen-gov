import { describe, it, expect } from "vitest";
import { formatPopulationShort } from "./format";

describe("formatPopulationShort", () => {
  it("renders sub-1k as exact integer", () => {
    expect(formatPopulationShort(0)).toBe("0");
    expect(formatPopulationShort(640)).toBe("640");
    expect(formatPopulationShort(999)).toBe("999");
  });

  it("renders 1k..<1M rounded to nearest k", () => {
    expect(formatPopulationShort(1_000)).toBe("1k");
    expect(formatPopulationShort(64_000)).toBe("64k");
    expect(formatPopulationShort(274_000)).toBe("274k");
    expect(formatPopulationShort(380_500)).toBe("381k");
    expect(formatPopulationShort(999_499)).toBe("999k");
  });

  it("renders ≥1M with one decimal, drops trailing zero", () => {
    expect(formatPopulationShort(1_000_000)).toBe("1M");
    expect(formatPopulationShort(1_240_000)).toBe("1.2M");
    expect(formatPopulationShort(13_500_000)).toBe("13.5M");
    expect(formatPopulationShort(1_400_000_000)).toBe("1400M");
  });

  it("returns em-dash for null / NaN / negative", () => {
    expect(formatPopulationShort(null)).toBe("—");
    expect(formatPopulationShort(undefined)).toBe("—");
    expect(formatPopulationShort(Number.NaN)).toBe("—");
    expect(formatPopulationShort(-1)).toBe("—");
  });
});
