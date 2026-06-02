// Pure-helper tests for WinnerBadge.svelte's module-scoped `glyphUrlFor`.
//
// PR-SYM-6b3: WinnerBadge renders the party's ballot-symbol glyph when
// `winner.election_symbol_asset_path` (mirror of
// `dim_parties.election_symbol_asset_path`) is populated. The asset path
// is repo-relative under `frontend/public/party-symbols/`; the helper
// resolves it through `import.meta.env.BASE_URL` so the URL is correct in
// both dev (`/party-symbols/...`) and the project-Pages subpath build
// (`/yen-gov/party-symbols/...`).
//
// Pure (no DOM, no Svelte mounting). Component-level rendering is
// exercised by the route-level browser smoke + the existing Playwright
// constituency specs.

import { describe, it, expect } from "vitest";
import { glyphUrlFor } from "./WinnerBadge.svelte";

describe("glyphUrlFor", () => {
  it("returns null when the asset path is null", () => {
    expect(glyphUrlFor(null)).toBeNull();
  });

  it("returns null when the asset path is undefined", () => {
    expect(glyphUrlFor(undefined)).toBeNull();
  });

  it("returns null when the asset path is an empty / whitespace string", () => {
    expect(glyphUrlFor("")).toBeNull();
    expect(glyphUrlFor("   ")).toBeNull();
  });

  it("prefixes a populated asset path with Vite's BASE_URL", () => {
    // vitest defaults BASE_URL to "/"; the helper just concatenates so a
    // dim_parties path like "party-symbols/broom.png" becomes the served
    // URL "/party-symbols/broom.png".
    const url = glyphUrlFor("party-symbols/broom.png");
    expect(url).toBe(`${import.meta.env.BASE_URL}party-symbols/broom.png`);
    expect(url?.endsWith("party-symbols/broom.png")).toBe(true);
  });
});
