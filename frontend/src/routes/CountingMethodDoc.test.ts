import { describe, it, expect } from "vitest";
import { lookupMethod } from "./CountingMethodDoc.svelte";
import { RULES } from "../lib/psephlab/rules";

describe("lookupMethod", () => {
  it("resolves every registered counting rule by id", () => {
    for (const r of RULES) {
      const out = lookupMethod(r.id);
      expect(out.ok, `expected ok for ${r.id}`).toBe(true);
      if (out.ok) {
        expect(out.rule.id).toBe(r.id);
        expect(out.rule.label).toBeTruthy();
        expect(out.rule.validity).toMatch(/^(fully_workable|medium_validity)$/);
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

  it("every non-FPTP rule carries caveat + assumptions + requires_banner", () => {
    for (const r of RULES) {
      if (r.id === "fptp") continue;
      const out = lookupMethod(r.id);
      expect(out.ok, `expected ok for ${r.id}`).toBe(true);
      if (out.ok) {
        expect(out.rule.caveat ?? "", `${r.id} caveat`).not.toBe("");
        expect(
          (out.rule.assumptions ?? []).length,
          `${r.id} assumptions`,
        ).toBeGreaterThan(0);
        expect(out.rule.requires_banner, `${r.id} requires_banner`).toBe(true);
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
