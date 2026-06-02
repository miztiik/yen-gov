// Unit tests for the party-colour source chip helper (PR-SYM-6b).

import { describe, expect, it } from "vitest";

import { chipFor } from "./chip";

describe("chipFor", () => {
  it("returns a distinct label for each resolver source tier", () => {
    expect(chipFor("anchor").label).toBe("anchor");
    expect(chipFor("brand").label).toBe("brand");
    expect(chipFor("fallback").label).toBe("fallback");
  });

  it("encodes the tier in border-style (anchor solid / brand solid / fallback dashed) so the chip is readable without colour vision", () => {
    expect(chipFor("anchor").className).toContain("border-solid");
    expect(chipFor("brand").className).toContain("border-solid");
    expect(chipFor("fallback").className).toContain("border-dashed");
  });

  it("attaches a non-empty tooltip explaining provenance for each tier", () => {
    for (const src of ["anchor", "brand", "fallback"] as const) {
      const p = chipFor(src);
      expect(p.tooltip.length).toBeGreaterThan(10);
    }
  });

  it("fallback tooltip explicitly admits the colour is invented (Hans honesty contract)", () => {
    const tip = chipFor("fallback").tooltip.toLowerCase();
    expect(tip).toMatch(/hash|invented|decoration|no editorial/);
  });
});
