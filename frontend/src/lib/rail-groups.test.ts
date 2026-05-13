// Pure tests for rail-groups.ts (P3.3c).
//
// What we're guarding:
//   - The four-group structure (My state / How states compare /
//     Centre and states / Settings) is stable.
//   - "Side by side" appears ONLY when state + defaultEvent are both set
//     (no greyed stub when missing).
//   - "My state" group is hint-only when state is null (no greyed stubs).
//   - Group hrefs flow through `url.*` builders (so deploy base prefixing
//     isn't bypassed) — asserted by checking the produced strings.

import { describe, it, expect } from "vitest";
import { buildRailGroups, type RailGroup } from "./rail-groups";

const REPO = "https://example.com/repo";

function find(groups: RailGroup[], id: string): RailGroup {
  const g = groups.find(x => x.id === id);
  if (!g) throw new Error(`group ${id} missing — got ${groups.map(g => g.id).join(", ")}`);
  return g;
}

describe("buildRailGroups (no scope)", () => {
  const groups = buildRailGroups({ state: null, defaultEvent: null, repoUrl: REPO });

  it("emits the four expected groups in order", () => {
    expect(groups.map(g => g.id)).toEqual([
      "my-state",
      "how-states-compare",
      "centre-and-states",
      "settings",
    ]);
  });

  it("My state group is empty with a hint (no greyed stubs)", () => {
    const my = find(groups, "my-state");
    expect(my.items).toEqual([]);
    expect(my.hint).toMatch(/Pick a state/i);
  });

  it("How states compare omits Side by side when no scope", () => {
    const cmp = find(groups, "how-states-compare");
    const ids = cmp.items.map(i => i.id);
    expect(ids).toContain("compare.all-topics");
    expect(ids).toContain("compare.fiscal");
    expect(ids).toContain("compare.energy");
    expect(ids).toContain("compare.elections");
    expect(ids).not.toContain("compare.side-by-side");
  });

  it("How states compare always exposes the generic Compare states tool (P4)", () => {
    const cmp = find(groups, "how-states-compare");
    const ci = cmp.items.find(i => i.id === "compare.indicator");
    expect(ci).toBeDefined();
    // Bare /compare URL — friendly empty state, no precondition.
    expect(ci!.href).toMatch(/\/compare$/);
    expect(ci!.label).toBe("Compare states");
  });

  it("Centre and states has fiscal + a 'more coming' hint", () => {
    const cs = find(groups, "centre-and-states");
    expect(cs.items.map(i => i.id)).toEqual(["centre.fiscal"]);
    expect(cs.hint).toMatch(/more topics/i);
  });

  it("Settings has Settings + About + external Repo", () => {
    const s = find(groups, "settings");
    const ids = s.items.map(i => i.id);
    expect(ids).toEqual(["settings.settings", "settings.about", "settings.repo"]);
    const repo = s.items.find(i => i.id === "settings.repo")!;
    expect(repo.external).toBe(true);
    expect(repo.href).toBe(REPO);
  });

  it("never emits a Psephlab/Analyze/Compare-as-verb item anywhere", () => {
    const flat = groups.flatMap(g => g.items.map(i => i.label.toLowerCase()));
    expect(flat).not.toContain("psephlab");
    expect(flat).not.toContain("analyze trends");
    expect(flat).not.toContain("explore"); // "Explore trends" lives under My state when scoped, "Explore" alone is the killed verb
  });
});

describe("buildRailGroups (scoped state, no event)", () => {
  const groups = buildRailGroups({ state: "S22", defaultEvent: null, repoUrl: REPO });

  it("My state group has Overview + Explore trends", () => {
    const my = find(groups, "my-state");
    expect(my.items.map(i => i.id)).toEqual(["my-state.overview", "my-state.trends"]);
    expect(my.hint).toBeUndefined();
  });

  it("Side by side still hidden when event is missing", () => {
    const cmp = find(groups, "how-states-compare");
    expect(cmp.items.map(i => i.id)).not.toContain("compare.side-by-side");
  });

  it("hrefs are concrete URLs (no template-string leakage)", () => {
    const overview = find(groups, "my-state").items[0];
    expect(overview.href).toMatch(/^\/?(yen-gov\/)?s\//);
    expect(overview.href).not.toContain("undefined");
  });
});

describe("buildRailGroups (scoped state + event)", () => {
  const groups = buildRailGroups({
    state: "S22",
    defaultEvent: "AcGenMay2026",
    repoUrl: REPO,
  });

  it("Side by side appears under How states compare", () => {
    const cmp = find(groups, "how-states-compare");
    const sbs = cmp.items.find(i => i.id === "compare.side-by-side");
    expect(sbs).toBeDefined();
    expect(sbs!.href).toContain("AcGenMay2026");
  });

  it("Side by side is the LAST item under How states compare", () => {
    const cmp = find(groups, "how-states-compare");
    expect(cmp.items[cmp.items.length - 1].id).toBe("compare.side-by-side");
  });
});

describe("RailItem.match predicates", () => {
  const groups = buildRailGroups({ state: "S22", defaultEvent: "E1", repoUrl: REPO });

  it("My state Overview matches /s/<slug> but NOT /s/<slug>/explore", () => {
    const overview = find(groups, "my-state").items.find(i => i.id === "my-state.overview")!;
    expect(overview.match("/s/tamil-nadu")).toBe(true);
    expect(overview.match("/s/tamil-nadu/explore")).toBe(false);
    expect(overview.match("/s/tamil-nadu/ac/167-mylapore")).toBe(false);
  });

  it("My state Explore trends matches /s/<slug>/explore", () => {
    const trends = find(groups, "my-state").items.find(i => i.id === "my-state.trends")!;
    expect(trends.match("/s/tamil-nadu/explore")).toBe(true);
    expect(trends.match("/s/tamil-nadu")).toBe(false);
  });

  it("All topics matches exactly /t (not /t/fiscal)", () => {
    const all = find(groups, "how-states-compare").items.find(i => i.id === "compare.all-topics")!;
    expect(all.match("/t")).toBe(true);
    expect(all.match("/t/fiscal")).toBe(false);
  });

  it("topic items match their own /t/<id> exactly", () => {
    const fiscal = find(groups, "how-states-compare").items.find(i => i.id === "compare.fiscal")!;
    expect(fiscal.match("/t/fiscal")).toBe(true);
    expect(fiscal.match("/t")).toBe(false);
    expect(fiscal.match("/t/energy")).toBe(false);
  });
});
