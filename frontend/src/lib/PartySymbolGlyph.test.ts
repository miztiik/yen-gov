import { describe, expect, it } from "vitest";
import { glyphUrlFor } from "./PartySymbolGlyph.svelte";

describe("glyphUrlFor", () => {
  it("returns null for null", () => {
    expect(glyphUrlFor(null)).toBeNull();
  });
  it("returns null for undefined", () => {
    expect(glyphUrlFor(undefined)).toBeNull();
  });
  it("returns null for empty string", () => {
    expect(glyphUrlFor("")).toBeNull();
  });
  it("returns null for whitespace-only string", () => {
    expect(glyphUrlFor("   ")).toBeNull();
  });
  it("joins BASE_URL with relative path", () => {
    const url = glyphUrlFor("party-symbols/lotus.svg");
    expect(url).not.toBeNull();
    expect(url!.endsWith("party-symbols/lotus.svg")).toBe(true);
  });
  it("strips leading slashes so the join doesn't double-slash", () => {
    const url = glyphUrlFor("/party-symbols/hand.svg");
    expect(url).not.toBeNull();
    expect(url!.includes("//party-symbols")).toBe(false);
    expect(url!.endsWith("party-symbols/hand.svg")).toBe(true);
  });
});

describe("glyphUrlFor with fallback modes", () => {
  const BASE = import.meta.env.BASE_URL;

  it("returns null for null assetPath with default silent fallback", () => {
    expect(glyphUrlFor(null)).toBeNull();
    expect(glyphUrlFor(null, "silent")).toBeNull();
  });

  it("returns null for empty assetPath with default silent fallback", () => {
    expect(glyphUrlFor("")).toBeNull();
    expect(glyphUrlFor("   ", "silent")).toBeNull();
  });

  it("returns placeholder URL for null assetPath when fallback=placeholder", () => {
    expect(glyphUrlFor(null, "placeholder")).toBe(
      `${BASE}party-symbols/placeholder.svg`,
    );
    expect(glyphUrlFor(undefined, "placeholder")).toBe(
      `${BASE}party-symbols/placeholder.svg`,
    );
  });

  it("returns placeholder URL for empty assetPath when fallback=placeholder", () => {
    expect(glyphUrlFor("", "placeholder")).toBe(
      `${BASE}party-symbols/placeholder.svg`,
    );
    expect(glyphUrlFor("   ", "placeholder")).toBe(
      `${BASE}party-symbols/placeholder.svg`,
    );
  });

  it("returns unverified URL for null assetPath when fallback=unverified", () => {
    expect(glyphUrlFor(null, "unverified")).toBe(
      `${BASE}party-symbols/unverified.svg`,
    );
    expect(glyphUrlFor("", "unverified")).toBe(
      `${BASE}party-symbols/unverified.svg`,
    );
  });

  it("returns absolute path for populated assetPath regardless of fallback mode", () => {
    const expected = `${BASE}party-symbols/lotus.svg`;
    expect(glyphUrlFor("party-symbols/lotus.svg", "silent")).toBe(expected);
    expect(glyphUrlFor("party-symbols/lotus.svg", "placeholder")).toBe(expected);
    expect(glyphUrlFor("party-symbols/lotus.svg", "unverified")).toBe(expected);
  });
});
