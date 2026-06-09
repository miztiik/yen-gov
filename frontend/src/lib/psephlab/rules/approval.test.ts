// Unit tests for approval rule (E6).
//
// Approval-as-cast is mathematically identical to FPTP by construction.
// Tests pin the equivalence + the honesty-marker metadata (caveat must
// explicitly tell the citizen the result equals FPTP and why).

import { describe, it, expect } from "vitest";
import { approval } from "./approval";
import { fptp } from "./fptp";
import { FIXTURE } from "../fixtures";

describe("approval — cast = approval (FPTP-equivalent by construction)", () => {
  it("returns the SAME by_party seat counts as fptp on FIXTURE", () => {
    const a = approval.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    expect(a.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      f.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
  });

  it("returns the SAME by_ac winners as fptp on FIXTURE", () => {
    const a = approval.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    expect(a.by_ac.map((o) => o.winner.party_eci_code)).toEqual(
      f.by_ac.map((o) => o.winner.party_eci_code),
    );
  });

  it("preserves total_votes against fptp", () => {
    const a = approval.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    expect(a.total_votes).toBe(f.total_votes);
  });

  it("exposes the honesty-marker caveat + assumptions + requires_banner", () => {
    expect(approval.requires_banner).toBe(true);
    expect(approval.caveat ?? "").not.toBe("");
    // The honesty marker MUST explicitly say the result equals FPTP - this
    // is the structural disclosure that gives the citizen the right answer
    // to "what would approval voting produce?" without fabrication.
    expect((approval.caveat ?? "").toLowerCase()).toContain("first-past-the-post");
    expect((approval.caveat ?? "").toLowerCase()).toContain("identical");
    expect(approval.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("caveat + assumptions are ASCII-only", () => {
    const allText = [approval.caveat ?? "", ...(approval.assumptions ?? []), approval.label].join(
      "\n",
    );
    expect(Array.from(allText).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
