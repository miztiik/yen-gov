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
