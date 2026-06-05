// Vitest - pure helpers for IndicatorJump (U5 sub-plan U5c).
//
// Component-render tests are not possible in node-env without jsdom +
// @testing-library/svelte (Skeleton precedent + /memories/lessons.md
// note). The two module-scope exports `filterGroups` and
// `activeIdForOffsets` are the testable surfaces; the IntersectionObserver
// wiring + smooth-scroll behaviour are exercised by the in-browser
// smoke on /s/tamil-nadu per CLAUDE.md section 13.

import { describe, expect, it } from "vitest";
import {
  activeIdForOffsets,
  filterGroups,
  type JumpGroup,
} from "./IndicatorJump.svelte";

const SAMPLE_GROUPS: ReadonlyArray<JumpGroup> = [
  { id: "economy", label: "Economy", icon: "trending-up" },
  { id: "health", label: "Health and Nutrition", icon: "activity" },
  { id: "education", label: "Education and Literacy" },
  { id: "energy", label: "Energy and Pollution", icon: "zap" },
  { id: "agriculture", label: "Agriculture", icon: "wheat" },
];

describe("filterGroups", () => {
  it("returns all groups when the query is empty", () => {
    expect(filterGroups(SAMPLE_GROUPS, "")).toEqual([...SAMPLE_GROUPS]);
  });

  it("returns all groups when the query is whitespace only", () => {
    expect(filterGroups(SAMPLE_GROUPS, "   ")).toEqual([...SAMPLE_GROUPS]);
  });

  it("matches case-insensitive substrings on label", () => {
    expect(filterGroups(SAMPLE_GROUPS, "lit")).toEqual([
      { id: "education", label: "Education and Literacy" },
    ]);
    expect(filterGroups(SAMPLE_GROUPS, "LIT")).toEqual([
      { id: "education", label: "Education and Literacy" },
    ]);
  });

  it("matches infix substrings, not just prefixes", () => {
    // "and" is an infix on Health/Education/Energy; prefix would miss all three.
    const matches = filterGroups(SAMPLE_GROUPS, "and");
    expect(matches.map(g => g.id)).toEqual(["health", "education", "energy"]);
  });

  it("returns an empty array when nothing matches", () => {
    expect(filterGroups(SAMPLE_GROUPS, "fiscal")).toEqual([]);
  });

  it("preserves the input order in the result", () => {
    const matches = filterGroups(SAMPLE_GROUPS, "e");
    // All five labels contain an "e"; result must keep the input order.
    expect(matches.map(g => g.id)).toEqual([
      "economy",
      "health",
      "education",
      "energy",
      "agriculture",
    ]);
  });

  it("does not mutate the input array", () => {
    const before = [...SAMPLE_GROUPS];
    filterGroups(SAMPLE_GROUPS, "lit");
    expect(SAMPLE_GROUPS).toEqual(before);
  });

  it("returns a fresh array on the empty-query passthrough (parent may mutate)", () => {
    const out = filterGroups(SAMPLE_GROUPS, "");
    expect(out).not.toBe(SAMPLE_GROUPS); // identity differs
    expect(out).toEqual([...SAMPLE_GROUPS]); // contents match
  });
});

describe("activeIdForOffsets", () => {
  const OFFSETS: ReadonlyArray<{ id: string; top: number }> = [
    { id: "economy", top: 100 },
    { id: "health", top: 600 },
    { id: "education", top: 1200 },
    { id: "energy", top: 1800 },
  ];

  it("returns null on an empty offset list", () => {
    expect(activeIdForOffsets(0, [])).toBeNull();
    expect(activeIdForOffsets(500, [])).toBeNull();
  });

  it("returns null when scrollY is above every section", () => {
    expect(activeIdForOffsets(0, OFFSETS)).toBeNull();
    expect(activeIdForOffsets(99, OFFSETS)).toBeNull();
  });

  it("returns the first id when scrollY equals the first offset", () => {
    expect(activeIdForOffsets(100, OFFSETS)).toBe("economy");
  });

  it("returns the previous-section id when scrollY is between two offsets", () => {
    expect(activeIdForOffsets(101, OFFSETS)).toBe("economy");
    expect(activeIdForOffsets(599, OFFSETS)).toBe("economy");
    expect(activeIdForOffsets(601, OFFSETS)).toBe("health");
    expect(activeIdForOffsets(1199, OFFSETS)).toBe("health");
  });

  it("returns the matching section id when scrollY exactly hits a section top", () => {
    expect(activeIdForOffsets(600, OFFSETS)).toBe("health");
    expect(activeIdForOffsets(1200, OFFSETS)).toBe("education");
    expect(activeIdForOffsets(1800, OFFSETS)).toBe("energy");
  });

  it("returns the last id when scrollY is past every section", () => {
    expect(activeIdForOffsets(1801, OFFSETS)).toBe("energy");
    expect(activeIdForOffsets(99999, OFFSETS)).toBe("energy");
  });

  it("breaks ties by LAST occurrence (DOM-later section paints on top)", () => {
    const collapsed = [
      { id: "a", top: 100 },
      { id: "b", top: 100 },
      { id: "c", top: 500 },
    ];
    // scrollY=100 hits both a and b at the same offset. The loop assigns
    // `active = o.id` for every <= match, so the LAST in DOM order wins.
    // Citizens perceive the DOM-later section as visible because it paints
    // on top of the earlier one when their y-positions collapse.
    expect(activeIdForOffsets(100, collapsed)).toBe("b");
  });

  it("handles a single-section list", () => {
    const one = [{ id: "only", top: 200 }];
    expect(activeIdForOffsets(0, one)).toBeNull();
    expect(activeIdForOffsets(200, one)).toBe("only");
    expect(activeIdForOffsets(5000, one)).toBe("only");
  });
});
