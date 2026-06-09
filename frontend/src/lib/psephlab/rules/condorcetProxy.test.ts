// Unit tests for the Condorcet proxy rule.
//
// Under our vote-count-substitution proxy, Condorcet is algorithmically
// identical to FPTP per-AC (the rank-by-votes total order makes the
// Condorcet winner equal to the highest-vote candidate by construction).
// Tests pin the equivalence + the honesty-marker metadata.

import { describe, expect, it } from "vitest";
import { condorcetProxy } from "./condorcetProxy";
import { fptp } from "./fptp";
import { FIXTURE } from "../fixtures";

describe("condorcetProxy - equivalent to FPTP by construction", () => {
  it("returns the SAME by_party seat counts as FPTP on FIXTURE", () => {
    const c = condorcetProxy.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    expect(c.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      f.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
  });

  it("returns the SAME by_ac winners as FPTP on FIXTURE", () => {
    const c = condorcetProxy.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    expect(c.by_ac.map((o) => o.winner.party_eci_code)).toEqual(
      f.by_ac.map((o) => o.winner.party_eci_code),
    );
  });

  it("preserves total_votes against FPTP", () => {
    const c = condorcetProxy.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    expect(c.total_votes).toBe(f.total_votes);
  });
});

describe("condorcetProxy - metadata contract", () => {
  it("exposes the honesty-marker caveat + assumptions + requires_banner", () => {
    expect(condorcetProxy.requires_banner).toBe(true);
    expect(condorcetProxy.validity).toBe("medium_validity");
    expect((condorcetProxy.caveat ?? "").length).toBeGreaterThan(50);
    // The caveat MUST explicitly disclose the FPTP equivalence (the
    // structural honesty primitive parallel to Approval's disclosure).
    expect((condorcetProxy.caveat ?? "").toLowerCase()).toContain("identical");
    expect((condorcetProxy.caveat ?? "").toLowerCase()).toContain("fptp");
    expect(condorcetProxy.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      condorcetProxy.label,
      condorcetProxy.short_label ?? "",
      condorcetProxy.headline ?? "",
      condorcetProxy.caveat ?? "",
      ...(condorcetProxy.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });

  it("exposes round-2 metadata fields", () => {
    expect(condorcetProxy.id).toBe("condorcet-proxy");
    expect(condorcetProxy.label).toContain("Condorcet");
    expect(condorcetProxy.short_label).toBe("Condorcet proxy");
    expect(condorcetProxy.headline).toBeTruthy();
  });
});
