// Oracle unit tests for the national constituency list's pure logic (Row 7
// of TODO/20260622-election-constituency-grouping-plan.md). The national
// page (`NationalElection.svelte`) wraps the SAME PC-mode
// StateEventConstituencyList in an outer State accordion and is a thin
// renderer over these two helpers, so testing the helpers IS testing the
// outer-accordion contract (states-as-top-groups; per-state PC -> AC ->
// District via buildPcGrouping; the ONE national search/Reserved filter).
//
// Pure: node-env, no DOM, no Svelte mount, no DuckDB. BOUNDED in-memory
// fixtures (2 states / 3 PCs / 5 ACs) - NEVER the live corpus (the
// no-frontend-corpus-explosion guard). No mocks - every assertion runs the
// real exported function the UI calls.

import { describe, it, expect } from "vitest";

import {
  buildNationalStateGroups,
  buildPcGrouping,
  filterNationalBranches,
  type AcEntity,
  type NationalBranchInput,
  type NationalPcWinner,
} from "./constituency-district-loader";

// ---- Bounded fixtures (2 states) --------------------------------------

function ac(
  over: Partial<AcEntity> & { entity_id: string; name: string; state: string },
): AcEntity {
  return {
    entity_id: over.entity_id,
    name: over.name,
    parent_pc_id: over.parent_pc_id ?? null,
    state: over.state,
    delim_year: over.delim_year ?? 2008,
    district_name: over.district_name ?? null,
    reservation: over.reservation ?? null,
    eci_no: over.eci_no ?? null,
  };
}

// State "alpha": PC "Alpha North" (2 ACs) + PC "Alpha South" (1 AC).
// State "beta":  PC "Beta East"  (2 ACs, one SC-reserved leaf).
const AC_ENTITIES: AcEntity[] = [
  ac({ entity_id: "alpha-ac-1", name: "Anand", state: "alpha", parent_pc_id: "alpha-pc-1", district_name: "Dist-A", eci_no: 1 }),
  ac({ entity_id: "alpha-ac-2", name: "Borsad", state: "alpha", parent_pc_id: "alpha-pc-1", district_name: "Dist-A", eci_no: 2 }),
  ac({ entity_id: "alpha-ac-3", name: "Cumbum", state: "alpha", parent_pc_id: "alpha-pc-2", district_name: "Dist-B", eci_no: 3 }),
  ac({ entity_id: "beta-ac-1", name: "Delta", state: "beta", parent_pc_id: "beta-pc-1", district_name: "Dist-C", eci_no: 1 }),
  ac({ entity_id: "beta-ac-2", name: "Echo", state: "beta", parent_pc_id: "beta-pc-1", district_name: "Dist-C", reservation: "SC", eci_no: 2 }),
  // A re-delimitation orphan: state alpha, no parent PC (plan 7.2 "Other").
  ac({ entity_id: "alpha-ac-orphan", name: "Orphanford", state: "alpha", parent_pc_id: null, district_name: "Dist-Z", eci_no: 9 }),
];

const WINNERS: NationalPcWinner[] = [
  { entity_id: "alpha-pc-1", entity_name: "Alpha North", state_code: "S01", state_slug: "alpha" },
  { entity_id: "alpha-pc-2", entity_name: "Alpha South", state_code: "S01", state_slug: "alpha" },
  { entity_id: "beta-pc-1", entity_name: "Beta East", state_code: "S02", state_slug: "beta" },
];

const DELIM = 2008;

// ---- buildNationalStateGroups: states-as-top-groups + per-state PC/AC ----

describe("buildNationalStateGroups", () => {
  it("returns one branch per state, sorted by slug", () => {
    const groups = buildNationalStateGroups(WINNERS, AC_ENTITIES, DELIM);
    expect(groups.map((g) => g.state_slug)).toEqual(["alpha", "beta"]);
    expect(groups.map((g) => g.state_code)).toEqual(["S01", "S02"]);
  });

  it("groups each state's PCs and child ACs via buildPcGrouping (counts match)", () => {
    const groups = buildNationalStateGroups(WINNERS, AC_ENTITIES, DELIM);
    const alpha = groups.find((g) => g.state_slug === "alpha")!;
    const beta = groups.find((g) => g.state_slug === "beta")!;

    // Sampled state PC count.
    expect(alpha.pcs.map((p) => p.name)).toEqual(["Alpha North", "Alpha South"]);
    expect(beta.pcs.map((p) => p.name)).toEqual(["Beta East"]);

    // Sampled PC child-AC count == what buildPcGrouping yields directly.
    const alphaDirect = buildPcGrouping(alpha.pcs, AC_ENTITIES, "alpha", DELIM);
    expect(alpha.childCountByPcId.get("alpha-pc-1")).toBe(2);
    expect(alpha.childCountByPcId.get("alpha-pc-2")).toBe(1);
    expect(alpha.childCountByPcId.get("alpha-pc-1")).toBe(
      alphaDirect.childCountByPcId.get("alpha-pc-1"),
    );

    // Every child leaf carries its parent PC name + a real district label.
    const north = alpha.leaves.filter((l) => l.pc_group === "Alpha North");
    expect(north.map((l) => l.name).sort()).toEqual(["Anand", "Borsad"]);
    expect(north.every((l) => l.district_name === "Dist-A")).toBe(true);

    // The orphan AC is retained (pc_group null), never dropped (plan 7.2).
    const orphan = alpha.leaves.find((l) => l.entity_id === "alpha-ac-orphan")!;
    expect(orphan.pc_group).toBeNull();
    expect(orphan.district_name).toBe("Dist-Z");
  });
});

// ---- filterNationalBranches: search/Reserved across state/PC/AC names ----

describe("filterNationalBranches", () => {
  const groups = buildNationalStateGroups(WINNERS, AC_ENTITIES, DELIM);
  const alpha = groups.find((g) => g.state_slug === "alpha")!;
  const beta = groups.find((g) => g.state_slug === "beta")!;

  const BRANCHES: NationalBranchInput[] = [
    {
      state_code: "S01",
      state_slug: "alpha",
      state_name: "Alpha",
      pcs: [
        { entity_id: "alpha-pc-1", name: "Alpha North", reservation: "GEN" },
        { entity_id: "alpha-pc-2", name: "Alpha South", reservation: "GEN" },
      ],
      leaves: alpha.leaves,
    },
    {
      state_code: "S02",
      state_slug: "beta",
      state_name: "Beta",
      pcs: [{ entity_id: "beta-pc-1", name: "Beta East", reservation: "SC" }],
      leaves: beta.leaves,
    },
  ];

  it("first paint (no query/filter): all states, full content, collapsed", () => {
    const out = filterNationalBranches(BRANCHES, "", "All");
    expect(out.map((b) => b.state_slug)).toEqual(["alpha", "beta"]);
    expect(out.every((b) => b.auto_expand === false)).toBe(true);
    expect(out[0].pcs.length).toBe(2);
    expect(out[0].leaves.length).toBe(alpha.leaves.length);
  });

  it("PC-name search auto-expands ONLY the matching state branch", () => {
    const out = filterNationalBranches(BRANCHES, "Alpha North", "All");
    expect(out.map((b) => b.state_slug)).toEqual(["alpha"]);
    expect(out[0].auto_expand).toBe(true);
    // Only the matched PC + its children survive.
    expect(out[0].pcs.map((p) => p.name)).toEqual(["Alpha North"]);
    expect(out[0].leaves.map((l) => l.name).sort()).toEqual(["Anand", "Borsad"]);
  });

  it("AC-name search auto-expands ONLY the parent state branch (lands on the seat)", () => {
    const out = filterNationalBranches(BRANCHES, "echo", "All");
    expect(out.map((b) => b.state_slug)).toEqual(["beta"]);
    expect(out[0].auto_expand).toBe(true);
    expect(out[0].pcs.map((p) => p.name)).toEqual(["Beta East"]);
    // The whole parent PC is shown so the seat composition is visible.
    expect(out[0].leaves.map((l) => l.name).sort()).toEqual(["Delta", "Echo"]);
  });

  it("state-name search returns the whole matching state", () => {
    const out = filterNationalBranches(BRANCHES, "beta", "All");
    expect(out.map((b) => b.state_slug)).toEqual(["beta"]);
    expect(out[0].pcs.length).toBe(1);
    expect(out[0].leaves.length).toBe(2);
  });

  it("orphan AC is searchable by its own name", () => {
    const out = filterNationalBranches(BRANCHES, "orphanford", "All");
    expect(out.map((b) => b.state_slug)).toEqual(["alpha"]);
    expect(out[0].leaves.map((l) => l.entity_id)).toEqual(["alpha-ac-orphan"]);
  });

  it("Reserved=SC narrows to SC parliament seats (PC-level)", () => {
    const out = filterNationalBranches(BRANCHES, "", "SC");
    // Only beta's PC is SC-reserved; alpha (GEN PCs) drops out.
    expect(out.map((b) => b.state_slug)).toEqual(["beta"]);
    expect(out[0].auto_expand).toBe(true);
    expect(out[0].leaves.length).toBe(2);
  });

  it("a non-matching query hides every branch", () => {
    const out = filterNationalBranches(BRANCHES, "zzz-no-such-seat", "All");
    expect(out).toEqual([]);
  });
});
