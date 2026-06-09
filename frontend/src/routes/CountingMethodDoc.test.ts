import { describe, it, expect } from "vitest";
import { lookupMethod } from "./CountingMethodDoc.svelte";

describe("lookupMethod", () => {
  it("resolves the 4 known method ids", () => {
    for (const id of ["fptp", "proportional", "ranked-choice", "approval"]) {
      const out = lookupMethod(id);
      expect(out.ok).toBe(true);
      if (out.ok) {
        expect(out.rule.id).toBe(id);
        expect(out.rule.label).toBeTruthy();
      }
    }
  });

  it("returns { ok: false } for an unknown method id", () => {
    const out = lookupMethod("made-up-future-method");
    expect(out.ok).toBe(false);
  });

  it("rejects empty string (defensive)", () => {
    const out = lookupMethod("");
    expect(out.ok).toBe(false);
  });

  it("returned rules carry caveat + assumptions for non-FPTP methods (so the page can render them)", () => {
    for (const id of ["proportional", "ranked-choice", "approval"]) {
      const out = lookupMethod(id);
      expect(out.ok).toBe(true);
      if (out.ok) {
        expect(out.rule.caveat ?? "").not.toBe("");
        expect((out.rule.assumptions ?? []).length).toBeGreaterThan(0);
        expect(out.rule.requires_banner).toBe(true);
      }
    }
  });

  it("FPTP has no caveat / assumptions / requires_banner (it is the official method)", () => {
    const out = lookupMethod("fptp");
    expect(out.ok).toBe(true);
    if (out.ok) {
      expect(out.rule.caveat).toBeUndefined();
      expect(out.rule.assumptions).toBeUndefined();
      expect(out.rule.requires_banner).toBeUndefined();
    }
  });
});
