import { describe, it, expect } from "vitest";
import {
  tierMembers,
  resolvePeerSet,
  nonEmptyTierIds,
  tiersForState,
  type StateTiersFile,
} from "./state-tiers";

const FIXTURE: StateTiersFile = {
  $schema: "https://yen-gov.github.io/schemas/state-tiers.schema.json",
  $schema_version: "1.0",
  sources: [],
  tiers: [
    {
      id: "general_category",
      label: "General",
      definition_kind: "residual",
      definition: "x",
      members: ["S22", "S10"],
    },
    {
      id: "neh",
      label: "NEH",
      definition_kind: "statutory",
      definition: "x",
      authority: "NEHC Act 1971",
      members: ["S03", "S21"],
    },
    {
      id: "fc_quintile",
      label: "FC quintile",
      definition_kind: "research",
      definition: "x",
      authority: "FC-XV",
      members: [],
    },
  ],
};

describe("tierMembers", () => {
  it("returns the members for a known tier", () => {
    expect(tierMembers(FIXTURE, "neh")).toEqual(["S03", "S21"]);
  });
  it("returns null for an unknown tier", () => {
    expect(tierMembers(FIXTURE, "no_such_tier")).toBeNull();
  });
  it("returns the empty array for a known but empty tier", () => {
    expect(tierMembers(FIXTURE, "fc_quintile")).toEqual([]);
  });
  it("returns null when the file is null", () => {
    expect(tierMembers(null, "neh")).toBeNull();
  });
});

describe("resolvePeerSet", () => {
  it("returns null for the `all` sentinel (no filter)", () => {
    expect(resolvePeerSet(FIXTURE, "all")).toBeNull();
  });
  it("returns the members for a real tier", () => {
    expect(resolvePeerSet(FIXTURE, "general_category")).toEqual(["S22", "S10"]);
  });
  it("returns the empty array for a tier awaiting data", () => {
    // Honest signal: filter applies, shows zero rows. Caller may choose to
    // degrade to `all`; this resolver does not make that decision.
    expect(resolvePeerSet(FIXTURE, "fc_quintile")).toEqual([]);
  });
  it("returns null for an unknown selector (treated as no filter)", () => {
    expect(resolvePeerSet(FIXTURE, "no_such_tier")).toBeNull();
  });
});

describe("nonEmptyTierIds", () => {
  it("filters out empty tiers (these don't show in the filter UI yet)", () => {
    expect(nonEmptyTierIds(FIXTURE)).toEqual(["general_category", "neh"]);
  });
  it("returns an empty array when the file is null", () => {
    expect(nonEmptyTierIds(null)).toEqual([]);
  });
});

describe("tiersForState", () => {
  it("returns every tier a state belongs to, in catalogue order", () => {
    const result = tiersForState(FIXTURE, "S22");
    expect(result.map(t => t.id)).toEqual(["general_category"]);
  });
  it("supports states with multiple memberships", () => {
    const file: StateTiersFile = {
      ...FIXTURE,
      tiers: [
        ...FIXTURE.tiers,
        {
          id: "extra",
          label: "Extra",
          definition_kind: "editorial",
          definition: "x",
          members: ["S22"],
        },
      ],
    };
    expect(tiersForState(file, "S22").map(t => t.id)).toEqual([
      "general_category",
      "extra",
    ]);
  });
  it("returns an empty array for a state in no tiers", () => {
    expect(tiersForState(FIXTURE, "U99")).toEqual([]);
  });
});
