// Pure-helper tests for HeroExplanation.

import { describe, expect, it } from "vitest";
import { defaultHeadline, validityBadgeText } from "./HeroExplanation.svelte";

describe("defaultHeadline", () => {
  it("includes the method label in the fallback headline", () => {
    expect(defaultHeadline("Borda Count")).toBe(
      "Explore the seats under Borda Count.",
    );
  });

  it("is ASCII-only", () => {
    const t = defaultHeadline("Mixed-Member (MMP)");
    expect(Array.from(t).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});

describe("validityBadgeText", () => {
  it("'Fully workable' for fully_workable, 'Experimental' for medium_validity", () => {
    expect(validityBadgeText("fully_workable")).toBe("Fully workable");
    expect(validityBadgeText("medium_validity")).toBe("Experimental");
  });
});
