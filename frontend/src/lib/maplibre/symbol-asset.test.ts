import { describe, expect, it } from "vitest";
import { symbolAssetUrl } from "./symbol-asset";

// Vitest inherits the Vite config, so import.meta.env.BASE_URL is "/".
const BASE = import.meta.env.BASE_URL;

describe("symbolAssetUrl", () => {
  it("prepends the deployed base path to a root-relative asset", () => {
    expect(symbolAssetUrl("party-symbols/lotus.svg")).toBe(
      `${BASE}party-symbols/lotus.svg`,
    );
  });

  it("never produces a double slash when base ends in '/' and path starts with '/'", () => {
    expect(symbolAssetUrl("/party-symbols/broom.png")).toBe(
      `${BASE}party-symbols/broom.png`,
    );
  });

  it("returns null for null / undefined / empty (silent degrade)", () => {
    expect(symbolAssetUrl(null)).toBeNull();
    expect(symbolAssetUrl(undefined)).toBeNull();
    expect(symbolAssetUrl("")).toBeNull();
  });

  it("always starts with the base path", () => {
    const url = symbolAssetUrl("party-symbols/conch.svg");
    expect(url?.startsWith(BASE)).toBe(true);
  });
});

describe("symbolAssetUrl with fallback modes", () => {
  it("returns null for null assetPath with default silent fallback", () => {
    expect(symbolAssetUrl(null)).toBeNull();
    expect(symbolAssetUrl(null, "silent")).toBeNull();
  });

  it("returns null for empty assetPath with default silent fallback", () => {
    expect(symbolAssetUrl("")).toBeNull();
    expect(symbolAssetUrl(undefined, "silent")).toBeNull();
  });

  it("returns placeholder URL for null assetPath when fallback=placeholder", () => {
    expect(symbolAssetUrl(null, "placeholder")).toBe(
      `${BASE}party-symbols/placeholder.svg`,
    );
    expect(symbolAssetUrl(undefined, "placeholder")).toBe(
      `${BASE}party-symbols/placeholder.svg`,
    );
  });

  it("returns placeholder URL for empty assetPath when fallback=placeholder", () => {
    expect(symbolAssetUrl("", "placeholder")).toBe(
      `${BASE}party-symbols/placeholder.svg`,
    );
  });

  it("returns unverified URL for null/empty assetPath when fallback=unverified", () => {
    expect(symbolAssetUrl(null, "unverified")).toBe(
      `${BASE}party-symbols/unverified.svg`,
    );
    expect(symbolAssetUrl("", "unverified")).toBe(
      `${BASE}party-symbols/unverified.svg`,
    );
  });

  it("returns absolute path for populated assetPath regardless of fallback mode", () => {
    const expected = `${BASE}party-symbols/lotus.svg`;
    expect(symbolAssetUrl("party-symbols/lotus.svg", "silent")).toBe(expected);
    expect(symbolAssetUrl("party-symbols/lotus.svg", "placeholder")).toBe(
      expected,
    );
    expect(symbolAssetUrl("party-symbols/lotus.svg", "unverified")).toBe(
      expected,
    );
  });
});
