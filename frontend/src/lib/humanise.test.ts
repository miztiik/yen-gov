import { describe, it, expect } from "vitest";
import { humanise } from "./humanise";

describe("humanise", () => {
  it("title-cases a snake_case id", () => {
    expect(humanise("other_thermal")).toBe("Other thermal");
  });

  it("title-cases a kebab-case id", () => {
    expect(humanise("small-hydro")).toBe("Small hydro");
  });

  it("handles a single token", () => {
    expect(humanise("coal")).toBe("Coal");
  });

  it("collapses repeated separators", () => {
    expect(humanise("a__b")).toBe("A b");
  });

  it("returns empty string for null / undefined / empty", () => {
    expect(humanise(null)).toBe("");
    expect(humanise(undefined)).toBe("");
    expect(humanise("")).toBe("");
  });
});
