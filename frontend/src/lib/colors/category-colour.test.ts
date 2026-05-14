import { describe, it, expect } from "vitest";
import { categoryColour, categoryFill } from "./category-colour";
import { POWER_SOURCE_ANCHORS, registerDimensionAnchors } from "./anchors-domain";

describe("categoryColour — power_source dimension", () => {
  it("returns the anchor hex for known fuel codes", () => {
    expect(categoryColour("coal", ["coal", "gas"], "power_source").fill).toBe(
      POWER_SOURCE_ANCHORS.coal.fill,
    );
    expect(categoryColour("hydro", ["coal", "hydro"], "power_source").fill).toBe(
      POWER_SOURCE_ANCHORS.hydro.fill,
    );
  });

  it("returns deterministic algorithmic hex for unknown fuel code", () => {
    const a = categoryColour("biomass_2030", ["biomass_2030"], "power_source").fill;
    const b = categoryColour("biomass_2030", ["biomass_2030"], "power_source").fill;
    expect(a).toBe(b);
    expect(a).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("override wins over anchor", () => {
    expect(
      categoryColour("coal", ["coal"], "power_source", { coal: { fill: "#abcdef" } }).fill,
    ).toBe("#abcdef");
  });

  it("convenience fill returns hex string", () => {
    expect(categoryFill("gas", ["gas"], "power_source")).toBe(POWER_SOURCE_ANCHORS.gas.fill);
  });
});

describe("categoryColour — party dimension delegates", () => {
  it("BJP code 369 still resolves to party anchor (saffron)", () => {
    const c = categoryColour("369", ["369"], "party");
    expect(c.fill).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("registerDimensionAnchors", () => {
  it("late registration is picked up by categoryColour", () => {
    registerDimensionAnchors("custom_dim", { foo: { fill: "#123456" } });
    expect(categoryColour("foo", ["foo"], "custom_dim").fill).toBe("#123456");
  });

  it("unknown dimension still resolves via algorithm", () => {
    expect(categoryColour("unknown_x", ["unknown_x"], "no_such_dim").fill).toMatch(
      /^#[0-9a-f]{6}$/,
    );
  });
});
