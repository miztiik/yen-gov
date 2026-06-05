// Pure-helper tests for TopicIcon.svelte's module-scoped exports +
// a CONTRACT test asserting every topic.icon referenced in
// datasets/taxonomy/topics.json has a matching SVG in the icon registry.
//
// The contract test is the load-bearing one: it catches the class of bug
// "author wrote topic.icon = 'foo' but the SVG never landed" at unit-test
// time, BEFORE any topic card silently swallows the missing icon. Per
// TopicIcon.svelte's docstring, runtime miss is silent (so layout never
// breaks), which is exactly why we MUST catch the miss at test time.
//
// Both tests are pure: no DOM, no Svelte mounting (vitest is node-env).
// The Svelte component itself is exercised by the Playwright smoke in
// frontend/e2e/extended-routes.spec.ts (added in this PR).

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { lookupIcon, registeredIconNames } from "./TopicIcon.svelte";

const REPO_ROOT = resolve(__dirname, "../../..");
const TOPICS_PATH = resolve(REPO_ROOT, "datasets/taxonomy/topics.json");

interface TopicLike {
  id: string;
  icon?: string;
}
interface TopicsFile {
  topics: TopicLike[];
}

const TOPICS = JSON.parse(readFileSync(TOPICS_PATH, "utf8")) as TopicsFile;

describe("TopicIcon helpers", () => {
  describe("lookupIcon", () => {
    it("returns null for undefined name (silent miss is contractual)", () => {
      expect(lookupIcon(undefined)).toBeNull();
    });

    it("returns null for null name", () => {
      expect(lookupIcon(null)).toBeNull();
    });

    it("returns null for empty string name", () => {
      expect(lookupIcon("")).toBeNull();
    });

    it("returns null for an icon id not in the registry", () => {
      // Use a name that no Lucide icon would ever take.
      expect(lookupIcon("__definitely_not_a_real_icon__")).toBeNull();
    });

    it("returns the Icon record for a registered name", () => {
      const icon = lookupIcon("vote");
      expect(icon).not.toBeNull();
      expect(icon?.name).toBe("vote");
      expect(icon?.viewBox).toBe("0 0 24 24");
      expect(icon?.children.length).toBeGreaterThan(0);
    });

    it("returned icon record carries a non-empty children tree", () => {
      const icon = lookupIcon("landmark");
      expect(icon).not.toBeNull();
      // landmark.svg = 5 <line>s + 1 <polygon> = 6 top-level children
      expect(icon?.children.length).toBe(6);
    });
  });

  describe("registeredIconNames", () => {
    it("returns the icon ids sorted alphabetically", () => {
      const names = registeredIconNames();
      expect(names.length).toBeGreaterThanOrEqual(8);
      const sorted = [...names].sort();
      expect(names).toEqual(sorted);
    });

    it("includes every icon shipped in frontend/public/icons/*.svg", () => {
      const names = registeredIconNames();
      // Icons currently shipped — keeps this assertion tight so a
      // contributor deleting an icon WITHOUT updating the test sees the
      // failure here, not on a citizen-visible regression elsewhere.
      // Phase 1.3b shipped 8 (car, cloud, heart-pulse, landmark,
      // trending-up, users, vote, zap). Phase 1.3d added 5 more
      // (trending-down, flame, sun, wind, activity) to cover the
      // state-hub indicator-card corpus. Phase 1.3f added 8 chrome /
      // identity glyphs (bar-chart, check, compass, flag, flask, info,
      // settings, shield) for the state-hub topic chips, Constituency,
      // Party, Compare, CompareIndicator, Psephlab, Explore, About,
      // Disclaimer, Settings, DataCompleteness routes.
      expect(names).toEqual([
        "activity",
        "bar-chart",
        "car",
        "check",
        "cloud",
        "compass",
        "flag",
        "flame",
        "flask",
        "heart-pulse",
        "info",
        "landmark",
        "settings",
        "shield",
        "sun",
        "trending-down",
        "trending-up",
        "users",
        "vote",
        "wind",
        "zap",
      ]);
    });
  });
});

describe("topics.json icon-coverage contract", () => {
  // This test fails LOUDLY if a topic.icon points at an SVG that hasn't
  // shipped. Topic cards silently no-op on miss (good for layout robustness)
  // but the failure mode "author wrote a typo and noticed nothing" must be
  // caught here.

  const REFERENCED = new Set<string>();
  for (const t of TOPICS.topics) {
    if (typeof t.icon === "string" && t.icon.length > 0) REFERENCED.add(t.icon);
  }

  it("references at least one icon (else the rollout is pointless)", () => {
    expect(REFERENCED.size).toBeGreaterThan(0);
  });

  it("every referenced icon exists in the registry", () => {
    const missing: string[] = [];
    for (const name of REFERENCED) {
      if (lookupIcon(name) === null) missing.push(name);
    }
    expect(
      missing,
      `topics.json references icons that are not in the registry: ${missing.join(", ")}`,
    ).toEqual([]);
  });
});
