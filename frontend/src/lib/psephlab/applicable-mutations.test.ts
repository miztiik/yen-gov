import { describe, it, expect } from "vitest";
import {
  applicableMutationsFor,
  isMutationInertUnder,
  inertReasonFor,
} from "./applicable-mutations";

describe("applicableMutationsFor", () => {
  it("returns all 4 mutations under fptp", () => {
    const ids = applicableMutationsFor("fptp").map((m) => m.id).sort();
    expect(ids).toEqual(["partyBag", "perAcSwing", "statewideSwing", "thresholdDrop"]);
  });

  it("filters perAcSwing + thresholdDrop out under proportional", () => {
    const ids = applicableMutationsFor("proportional").map((m) => m.id).sort();
    expect(ids).toEqual(["partyBag", "statewideSwing"]);
  });

  it("returns all 4 mutations under ranked-choice", () => {
    const ids = applicableMutationsFor("ranked-choice").map((m) => m.id).sort();
    expect(ids).toEqual(["partyBag", "perAcSwing", "statewideSwing", "thresholdDrop"]);
  });

  it("returns all 4 mutations under approval", () => {
    const ids = applicableMutationsFor("approval").map((m) => m.id).sort();
    expect(ids).toEqual(["partyBag", "perAcSwing", "statewideSwing", "thresholdDrop"]);
  });

  it("includes mutations with no allowed_rules declaration (rule-agnostic)", () => {
    // statewideSwing + partyBag both omit allowed_rules; they must appear under every rule.
    for (const rule of ["fptp", "proportional", "ranked-choice", "approval", "unknown-future-rule"]) {
      const ids = applicableMutationsFor(rule).map((m) => m.id);
      expect(ids).toContain("statewideSwing");
      expect(ids).toContain("partyBag");
    }
  });
});

describe("isMutationInertUnder", () => {
  it("is true for perAcSwing + thresholdDrop under proportional", () => {
    expect(isMutationInertUnder("perAcSwing", "proportional")).toBe(true);
    expect(isMutationInertUnder("thresholdDrop", "proportional")).toBe(true);
  });

  it("is false for the same mutations under FPTP / IRV / Approval", () => {
    for (const rule of ["fptp", "ranked-choice", "approval"]) {
      expect(isMutationInertUnder("perAcSwing", rule)).toBe(false);
      expect(isMutationInertUnder("thresholdDrop", rule)).toBe(false);
    }
  });

  it("is false for rule-agnostic mutations under every rule", () => {
    for (const rule of ["fptp", "proportional", "ranked-choice", "approval"]) {
      expect(isMutationInertUnder("statewideSwing", rule)).toBe(false);
      expect(isMutationInertUnder("partyBag", rule)).toBe(false);
    }
  });

  it("returns false for unknown mutation ids (defensive)", () => {
    expect(isMutationInertUnder("madeUpFuture", "fptp")).toBe(false);
  });
});

describe("inertReasonFor", () => {
  it("returns a perAcSwing-specific reason under proportional", () => {
    const reason = inertReasonFor(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { id: "perAcSwing" } as any,
      "proportional",
    );
    expect(reason).toMatch(/state-wide totals/i);
    expect(reason).toMatch(/Proportional/);
  });

  it("returns a thresholdDrop-specific reason under proportional", () => {
    const reason = inertReasonFor(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { id: "thresholdDrop" } as any,
      "proportional",
    );
    expect(reason).toMatch(/state-wide totals/i);
    expect(reason).toMatch(/Proportional/);
  });

  it("returns null when the mutation IS applicable under the rule", () => {
    expect(
      inertReasonFor(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        { id: "perAcSwing" } as any,
        "fptp",
      ),
    ).toBeNull();
    expect(
      inertReasonFor(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        { id: "statewideSwing" } as any,
        "proportional",
      ),
    ).toBeNull();
  });

  it("returns ASCII-only reasons (CLAUDE.md section 5)", () => {
    for (const rule of ["proportional"]) {
      for (const mid of ["perAcSwing", "thresholdDrop"]) {
        const reason = inertReasonFor(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          { id: mid } as any,
          rule,
        );
        expect(reason).not.toBeNull();
        expect(Array.from(reason!).every((c) => c.charCodeAt(0) < 128)).toBe(true);
      }
    }
  });
});
