// Vitest - pure size-style helper for Skeleton (U5 sub-plan U5a).
//
// Component-render tests are not possible in node-env without jsdom +
// @testing-library/svelte (see Skeleton.svelte comment + the
// /memories/lessons.md note). The skeletonStyle() module-scope helper
// is the testable surface; the visual smoke comes from CLAUDE.md
// section 13 in-browser verification on a route that mounts the
// skeleton.

import { describe, expect, it } from "vitest";
import { skeletonStyle } from "./Skeleton.svelte";

describe("skeletonStyle", () => {
  it("emits both dimensions when both are supplied", () => {
    expect(skeletonStyle({ width: "100%", height: "4rem" })).toBe(
      "width: 100%; height: 4rem;",
    );
  });

  it("returns an empty string when neither dim is supplied (parent stylesheet takes over)", () => {
    expect(skeletonStyle({})).toBe("");
  });

  it("emits only the supplied dimension when one is omitted", () => {
    expect(skeletonStyle({ width: "12rem" })).toBe("width: 12rem;");
    expect(skeletonStyle({ height: "200px" })).toBe("height: 200px;");
  });

  it("passes the caller's CSS length string through verbatim (no parsing, no normalisation)", () => {
    expect(skeletonStyle({ width: "calc(100% - 1rem)", height: "min(8rem, 50vh)" }))
      .toBe("width: calc(100% - 1rem); height: min(8rem, 50vh);");
  });

  it("does NOT inject any default values (caller is authoritative)", () => {
    // The Svelte component owns the prop defaults; the helper is pure.
    // This case proves the helper never sneaks "100%" / "4rem" in for
    // an omitted arg, which would mask a missing prop in a renderer.
    expect(skeletonStyle({})).not.toContain("100%");
    expect(skeletonStyle({})).not.toContain("4rem");
  });
});
