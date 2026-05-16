// Pure tests for rail-groups.ts (IA-reset Step #1.5).
//
// What we're guarding:
//   - The three-group structure (This state / Across states / About) is
//     stable, in that order.
//   - "This state" is hint-only when state is null (no greyed stubs).
//   - When a state is selected, "This state" expands to Overview + the
//     fixed topic list, every entry pointing at /t/<topic-id> (national
//     topic page — per-state-topic routes are Step #2's work).
//   - "Across states" always exposes Compare states + All topics, in that
//     order, regardless of scope.
//   - "About" exposes a single About & sources entry; the previous Repo
//     external link is intentionally gone (moved to the About page).
//   - No "Centre and states" group, no "Side by side", no "Explore
//     trends", no "Settings" rail entries.
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

  it("emits the three expected groups in order", () => {
    expect(groups.map(g => g.id)).toEqual([
      "this-state",
      "across-states",
      "about",
    ]);
  });

  it("This state group is empty with a hint (no greyed stubs)", () => {
    const my = find(groups, "this-state");
    expect(my.items).toEqual([]);
    expect(my.hint).toMatch(/Pick a state/i);
  });

  it("Across states exposes Compare states + All topics (in that order)", () => {
    const cmp = find(groups, "across-states");
    expect(cmp.items.map(i => i.id)).toEqual([
      "across-states.compare",
      "across-states.all-topics",
    ]);
    const compare = cmp.items[0];
    expect(compare.label).toBe("Compare states");
    expect(compare.href).toMatch(/\/compare$/);
    const all = cmp.items[1];
    expect(all.label).toBe("All topics");
    expect(all.href).toMatch(/\/t$/);
  });

  it("About has a single About & sources entry (no Repo, no Settings)", () => {
    const s = find(groups, "about");
    expect(s.items.map(i => i.id)).toEqual(["about.about"]);
    expect(s.items[0].label).toBe("About & sources");
    expect(s.items[0].href).toMatch(/\/about$/);
    expect(s.items[0].external).toBeUndefined();
  });

  it("never emits any killed-in-step-1.5 rail entries", () => {
    const flat_ids = groups.flatMap(g => g.items.map(i => i.id));
    const flat_labels = groups.flatMap(g => g.items.map(i => i.label.toLowerCase()));
    // No legacy group IDs survive.
    expect(groups.map(g => g.id)).not.toContain("my-state");
    expect(groups.map(g => g.id)).not.toContain("how-states-compare");
    expect(groups.map(g => g.id)).not.toContain("centre-and-states");
    expect(groups.map(g => g.id)).not.toContain("settings");
    // No killed items survive.
    expect(flat_ids).not.toContain("my-state.trends");
    expect(flat_ids).not.toContain("compare.side-by-side");
    expect(flat_ids).not.toContain("centre.fiscal");
    expect(flat_ids).not.toContain("settings.settings");
    expect(flat_ids).not.toContain("settings.repo");
    // And no killed verbs by label, either.
    expect(flat_labels).not.toContain("explore trends");
    expect(flat_labels).not.toContain("side by side");
    expect(flat_labels).not.toContain("settings");
    expect(flat_labels).not.toContain("repo");
    expect(flat_labels).not.toContain("psephlab");
  });

  it("never emits an external rail item in the no-scope case", () => {
    const flat = groups.flatMap(g => g.items);
    expect(flat.every(i => !i.external)).toBe(true);
  });
});

describe("buildRailGroups (scoped state, no event)", () => {
  const groups = buildRailGroups({ state: "S22", defaultEvent: null, repoUrl: REPO });

  it("This state group has Overview + the fixed topic list (no hint)", () => {
    const my = find(groups, "this-state");
    expect(my.hint).toBeUndefined();
    const ids = my.items.map(i => i.id);
    expect(ids[0]).toBe("this-state.overview");
    expect(ids.slice(1)).toEqual([
      "this-state.topic.fiscal",
      "this-state.topic.energy",
      "this-state.topic.economy",
      "this-state.topic.health",
      "this-state.topic.environment",
      "this-state.topic.transport",
      "this-state.topic.elections",
    ]);
  });

  it("Every This state topic entry targets the national /t/<id> page (Step #2 not yet shipped)", () => {
    const my = find(groups, "this-state");
    const topic_items = my.items.filter(i => i.id.startsWith("this-state.topic."));
    expect(topic_items.length).toBeGreaterThan(0);
    for (const item of topic_items) {
      // Must end with /t/<slug>, never /s/<state>/t/<slug>.
      expect(item.href).toMatch(/\/t\/[a-z][a-z0-9-]*$/);
      expect(item.href).not.toContain("/s/");
    }
  });

  it("Across states + About are unaffected by scope", () => {
    expect(find(groups, "across-states").items.map(i => i.id)).toEqual([
      "across-states.compare",
      "across-states.all-topics",
    ]);
    expect(find(groups, "about").items.map(i => i.id)).toEqual(["about.about"]);
  });

  it("hrefs are concrete URLs (no template-string leakage)", () => {
    const overview = find(groups, "this-state").items[0];
    expect(overview.href).toMatch(/^\/?(yen-gov\/)?s\//);
    expect(overview.href).not.toContain("undefined");
  });

  it("scope/event do NOT re-introduce killed entries", () => {
    const flat_ids = groups.flatMap(g => g.items.map(i => i.id));
    expect(flat_ids).not.toContain("my-state.trends");
    expect(flat_ids).not.toContain("compare.side-by-side");
  });
});

describe("buildRailGroups (scoped state + event)", () => {
  // event is plumbed through the signature but Step #1.5 does NOT render
  // a state+event-aware rail item; the test exists to lock that in so a
  // future "Side by side" resurrection has to update this file deliberately.
  const groups = buildRailGroups({
    state: "S22",
    defaultEvent: "AcGenMay2026",
    repoUrl: REPO,
  });

  it("does NOT add any state+event-aware item under Across states", () => {
    const cmp = find(groups, "across-states");
    expect(cmp.items.map(i => i.id)).toEqual([
      "across-states.compare",
      "across-states.all-topics",
    ]);
    // And no item href encodes the event id anywhere in the rail.
    const all_hrefs = groups.flatMap(g => g.items.map(i => i.href));
    expect(all_hrefs.every(h => !h.includes("AcGenMay2026"))).toBe(true);
  });
});

describe("RailItem.match predicates", () => {
  const groups = buildRailGroups({ state: "S22", defaultEvent: "E1", repoUrl: REPO });

  it("This state Overview matches /s/<slug> but NOT its sub-pages", () => {
    const overview = find(groups, "this-state").items.find(
      i => i.id === "this-state.overview",
    )!;
    expect(overview.match("/s/tamil-nadu")).toBe(true);
    expect(overview.match("/s/tamil-nadu/explore")).toBe(false);
    expect(overview.match("/s/tamil-nadu/ac/167-mylapore")).toBe(false);
  });

  it("All topics matches exactly /t (not /t/fiscal)", () => {
    const all = find(groups, "across-states").items.find(
      i => i.id === "across-states.all-topics",
    )!;
    expect(all.match("/t")).toBe(true);
    expect(all.match("/t/fiscal")).toBe(false);
  });

  it("Topic items match their own /t/<id> exactly", () => {
    const fiscal = find(groups, "this-state").items.find(
      i => i.id === "this-state.topic.fiscal",
    )!;
    expect(fiscal.match("/t/fiscal")).toBe(true);
    expect(fiscal.match("/t")).toBe(false);
    expect(fiscal.match("/t/energy")).toBe(false);

    const energy = find(groups, "this-state").items.find(
      i => i.id === "this-state.topic.energy",
    )!;
    expect(energy.match("/t/energy")).toBe(true);
    expect(energy.match("/t/fiscal")).toBe(false);
  });

  it("Compare states matches /compare exactly", () => {
    const c = find(groups, "across-states").items.find(
      i => i.id === "across-states.compare",
    )!;
    expect(c.match("/compare")).toBe(true);
    expect(c.match("/compare/tamil-nadu/AcGenMay2026")).toBe(false);
  });

  it("About matches /about exactly", () => {
    const a = find(groups, "about").items.find(i => i.id === "about.about")!;
    expect(a.match("/about")).toBe(true);
    expect(a.match("/")).toBe(false);
  });
});
