import { describe, it, expect } from "vitest";
import { buildModeMarker, buildContextLabel } from "./ContextLabel.svelte";

describe("buildModeMarker - FPTP", () => {
  it("zero mutations -> 'actuals'", () => {
    expect(
      buildModeMarker({
        rule_id: "fptp",
        rule_label: "First-Past-The-Post",
        mutation_count: 0,
      }),
    ).toBe("actuals");
  });

  it("one mutation -> '1 what-if applied' (singular)", () => {
    expect(
      buildModeMarker({
        rule_id: "fptp",
        rule_label: "First-Past-The-Post",
        mutation_count: 1,
      }),
    ).toBe("1 what-if applied");
  });

  it("N mutations -> 'N what-ifs applied' (plural)", () => {
    expect(
      buildModeMarker({
        rule_id: "fptp",
        rule_label: "First-Past-The-Post",
        mutation_count: 2,
      }),
    ).toBe("2 what-ifs applied");
    expect(
      buildModeMarker({
        rule_id: "fptp",
        rule_label: "First-Past-The-Post",
        mutation_count: 7,
      }),
    ).toBe("7 what-ifs applied");
  });
});

describe("buildModeMarker - non-FPTP", () => {
  it("zero mutations -> 'imagined under <rule>'", () => {
    expect(
      buildModeMarker({
        rule_id: "proportional",
        rule_label: "Proportional (Sainte-Lague, state-wide)",
        mutation_count: 0,
      }),
    ).toBe("imagined under Proportional (Sainte-Lague, state-wide)");
  });

  it("N mutations -> 'imagined under <rule> + N what-ifs applied'", () => {
    expect(
      buildModeMarker({
        rule_id: "ranked-choice",
        rule_label: "Ranked-choice (proportional transfer)",
        mutation_count: 2,
      }),
    ).toBe(
      "imagined under Ranked-choice (proportional transfer) + 2 what-ifs applied",
    );
  });

  it("one mutation pluralises 'what-if' correctly under non-FPTP", () => {
    expect(
      buildModeMarker({
        rule_id: "approval",
        rule_label: "Approval (single mark)",
        mutation_count: 1,
      }),
    ).toBe("imagined under Approval (single mark) + 1 what-if applied");
  });
});

describe("buildModeMarker - compare", () => {
  it("compare_with overrides every other variant", () => {
    expect(
      buildModeMarker({
        rule_id: "fptp",
        rule_label: "First-Past-The-Post",
        mutation_count: 0,
        compare_with: "TN AC May 2026",
      }),
    ).toBe("comparing with TN AC May 2026");
  });

  it("compare_with overrides even when non-FPTP + mutations", () => {
    expect(
      buildModeMarker({
        rule_id: "proportional",
        rule_label: "Proportional",
        mutation_count: 3,
        compare_with: "TN AC Apr 2021",
      }),
    ).toBe("comparing with TN AC Apr 2021");
  });

  it("empty compare_with falls back to non-compare marker", () => {
    expect(
      buildModeMarker({
        rule_id: "fptp",
        rule_label: "First-Past-The-Post",
        mutation_count: 0,
        compare_with: "",
      }),
    ).toBe("actuals");
    expect(
      buildModeMarker({
        rule_id: "fptp",
        rule_label: "First-Past-The-Post",
        mutation_count: 0,
        compare_with: null,
      }),
    ).toBe("actuals");
  });
});

describe("buildContextLabel", () => {
  it("joins election + seats + mode with ' . '", () => {
    expect(
      buildContextLabel({
        election_display: "TN AC Apr 2021",
        seat_count: 234,
        rule_id: "fptp",
        rule_label: "FPTP",
        mutation_count: 0,
      }),
    ).toBe("TN AC Apr 2021 . 234 seats . actuals");
  });

  it("returns empty string when election_display is null (still-loading state)", () => {
    expect(
      buildContextLabel({
        election_display: null,
        seat_count: 0,
        rule_id: "fptp",
        rule_label: "FPTP",
        mutation_count: 0,
      }),
    ).toBe("");
  });

  it("surfaces the imagining language for non-FPTP without a separate banner", () => {
    const out = buildContextLabel({
      election_display: "TN AC Apr 2021",
      seat_count: 234,
      rule_id: "proportional",
      rule_label: "Proportional (Sainte-Lague, state pool)",
      mutation_count: 0,
    });
    expect(out).toContain("imagined under");
    expect(out).toContain("Proportional");
  });

  it("ASCII-only across the matrix", () => {
    const matrix = [
      buildContextLabel({
        election_display: "TN AC Apr 2021",
        seat_count: 234,
        rule_id: "fptp",
        rule_label: "FPTP",
        mutation_count: 0,
      }),
      buildContextLabel({
        election_display: "Bihar AC Oct 2020",
        seat_count: 243,
        rule_id: "proportional",
        rule_label: "Proportional (Sainte-Lague, state pool)",
        mutation_count: 2,
      }),
      buildContextLabel({
        election_display: "TN AC May 2026",
        seat_count: 234,
        rule_id: "approval",
        rule_label: "Approval (single mark)",
        mutation_count: 1,
        compare_with: "TN AC Apr 2021",
      }),
    ];
    for (const text of matrix) {
      expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
    }
  });
});
