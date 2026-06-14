/**
 * `PartyAllianceContext.test.ts` - vitest pin for the pure formatters
 * exported from `PartyAllianceContext.svelte` (PR-8 of TODO/20260614-
 * party-page-reimagination-plan.md).
 *
 * Per project doctrine, vitest does not mount Svelte. The pin covers
 * the pure helpers that live in the component's `<script module>`
 * block (`formatPartnerList` + `formatAllianceLine`); the rendered-
 * DOM smoke is in `Party.test.ts` (which mounts the route) and the
 * manual section 13 browser smoke recorded in the PR body.
 */
import { describe, expect, it } from "vitest";

import {
  formatAllianceLine,
  formatPartnerList,
} from "./PartyAllianceContext.svelte";

describe("formatPartnerList", () => {
  it("returns empty string for empty partner list", () => {
    expect(formatPartnerList([], 0)).toBe("");
  });

  it("returns comma-joined list when not truncated", () => {
    expect(formatPartnerList(["JD(U)"], 1)).toBe("JD(U)");
    expect(formatPartnerList(["JD(U)", "TDP"], 2)).toBe("JD(U), TDP");
    expect(formatPartnerList(["A", "B", "C"], 3)).toBe("A, B, C");
  });

  it("appends (+N others) when partner_count exceeds list length", () => {
    expect(formatPartnerList(["JD(U)"], 3)).toBe("JD(U) (+2 others)");
    expect(formatPartnerList(["A", "B", "C", "D", "E"], 10)).toBe(
      "A, B, C, D, E (+5 others)",
    );
  });

  it("uses singular 'other' for a single truncated partner", () => {
    expect(formatPartnerList(["A", "B"], 3)).toBe("A, B (+1 other)");
  });
});

describe("formatAllianceLine", () => {
  it("renders 'contested alone' when alliance is null", () => {
    expect(formatAllianceLine("alone", null, [], 0)).toBe("contested alone");
    // Role override: even if a buggy caller passes 'led' with null
    // alliance, the null-alliance branch wins.
    expect(formatAllianceLine("led", null, [], 0)).toBe("contested alone");
  });

  it("renders 'led <alliance> with <partners>' for role='led'", () => {
    expect(formatAllianceLine("led", "NDA", ["JD(U)", "TDP"], 2)).toBe(
      "led NDA with JD(U), TDP",
    );
  });

  it("renders 'junior in <alliance> with <partners>' for role='junior'", () => {
    expect(formatAllianceLine("junior", "NDA", ["BJP"], 1)).toBe(
      "junior in NDA with BJP",
    );
  });

  it("renders honest 'partner data pending' for role='alone' with non-null alliance", () => {
    expect(formatAllianceLine("alone", "Mahayuti", [], 0)).toBe(
      "Mahayuti alliance, partner data pending",
    );
  });

  it("omits the 'with <partners>' tail when partner list is empty for led/junior", () => {
    expect(formatAllianceLine("led", "NDA", [], 0)).toBe("led NDA");
    expect(formatAllianceLine("junior", "INDIA", [], 0)).toBe("junior in INDIA");
  });

  it("appends (+N others) tail when partners are truncated", () => {
    expect(
      formatAllianceLine("led", "NDA", ["JD(U)", "TDP"], 7),
    ).toBe("led NDA with JD(U), TDP (+5 others)");
  });
});
