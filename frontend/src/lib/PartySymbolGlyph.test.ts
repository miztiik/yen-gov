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
