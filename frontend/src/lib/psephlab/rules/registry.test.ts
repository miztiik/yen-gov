// Registry-level invariants for the counting-rule library.
//
// Per Fowler round-2 verdict (2026-06-09): one place to pin the
// "every rule MUST declare its validity tier" + "every rule's metadata
// is ASCII-only" + "labels and short_labels are non-empty" gates so a
// new rule landing forgets none of these. The per-rule tests still pin
// algorithmic behaviour; this test pins the cross-rule contract shape.

import { describe, it, expect } from "vitest";
import { RULES, ruleById } from "./index";

describe("rule registry - cross-rule invariants", () => {
  it("every rule declares an id, label, validity, and apply()", () => {
    for (const r of RULES) {
      expect(r.id, `rule.id must be non-empty`).toBeTruthy();
      expect(r.label, `rule.label for '${r.id}' must be non-empty`).toBeTruthy();
      expect(typeof r.apply, `rule.apply for '${r.id}' must be a function`).toBe("function");
      expect(r.validity, `rule.validity for '${r.id}' must be set`).toMatch(
        /^(fully_workable|medium_validity)$/,
      );
    }
  });

  it("every non-FPTP rule carries a caveat + at least 2 assumptions + requires_banner", () => {
    for (const r of RULES) {
      if (r.id === "fptp") continue;
      expect(r.requires_banner, `${r.id} must set requires_banner`).toBe(true);
      expect((r.caveat ?? "").length, `${r.id} caveat must be non-empty`).toBeGreaterThan(0);
      expect(
        r.assumptions?.length ?? 0,
        `${r.id} must declare at least 2 assumptions`,
      ).toBeGreaterThanOrEqual(2);
    }
  });

  it("FPTP is fully_workable and the only rule without requires_banner", () => {
    const fptp = ruleById("fptp");
    expect(fptp.validity).toBe("fully_workable");
    expect(fptp.requires_banner ?? false).toBe(false);
    const without_banner = RULES.filter((r) => !r.requires_banner);
    expect(without_banner.map((r) => r.id)).toEqual(["fptp"]);
  });

  it("ruleById falls back to fptp on unknown id (legacy share-URL contract)", () => {
    const unknown = ruleById("nonexistent-method");
    expect(unknown.id).toBe("fptp");
  });

  it("every rule's metadata is ASCII-only (CLAUDE.md section 5)", () => {
    for (const r of RULES) {
      const text = [
        r.id,
        r.label,
        r.short_label ?? "",
        r.headline ?? "",
        r.caveat ?? "",
        ...(r.assumptions ?? []),
      ].join("\n");
      const offending: string[] = [];
      for (let i = 0; i < text.length; i++) {
        if (text.charCodeAt(i) >= 128) {
          offending.push(`${r.id}: U+${text.charCodeAt(i).toString(16)} '${text[i]}'`);
        }
      }
      expect(offending, `${r.id} has non-ASCII characters`).toEqual([]);
    }
  });

  it("ids are unique across the registry", () => {
    const ids = RULES.map((r) => r.id);
    const unique = new Set(ids);
    expect(unique.size, "duplicate rule ids in registry").toBe(ids.length);
  });

  it("short_label, when present, is <= 40 chars (Jony picker-chip constraint)", () => {
    for (const r of RULES) {
      if (!r.short_label) continue;
      expect(
        r.short_label.length,
        `${r.id} short_label too long for picker chip: '${r.short_label}'`,
      ).toBeLessThanOrEqual(40);
    }
  });
});
