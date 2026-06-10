// PR-W1d (election experience overhaul, 2026-06-10): per-route crumb
// builders for both election + socio-econ cascades. Tests run in
// node-env per /memories/lessons.md (vitest has no jsdom +
// @testing-library/svelte by design); the rendering component
// Breadcrumb.svelte is exercised by the in-browser smoke per
// CLAUDE.md section 13. This file asserts on the per-route builder
// outputs - the testable surface that drives the renderer.
//
// Each builder is pure: takes a params record, returns Crumb[]. The
// `states` catalogue is not loaded in test fixtures, so the
// stateLabel() fallback path (slugToTitle()) is what the assertions
// land on. That matches what the live UI renders during the brief
// pre-catalogue-load window and proves the builders never block on
// async resolution.

import { describe, it, expect } from "vitest";
import {
  homeCrumbs,
  stateOverviewCrumbs,
  stateTopicCrumbs,
  stateElectionCrumbs,
  constituencyCanonicalCrumbs,
  constituencyBareCrumbs,
  topicLandingCrumbs,
} from "./route-crumbs";

describe("Breadcrumb / route-crumbs - 6 canonical URLs", () => {
  it("/ -> single leaf 'Home' crumb", () => {
    const crumbs = homeCrumbs();
    expect(crumbs).toHaveLength(1);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[0].isLeaf).toBe(true);
    expect(crumbs[0].href).toBeUndefined();
  });

  it("/tamil-nadu -> [Home (link), Tamil Nadu (leaf)]", () => {
    const crumbs = stateOverviewCrumbs({ state: "tamil-nadu" });
    expect(crumbs).toHaveLength(2);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[0].href).toBe("/");
    expect(crumbs[0].isLeaf).toBeUndefined();
    expect(crumbs[1].label).toBe("Tamil Nadu");
    expect(crumbs[1].isLeaf).toBe(true);
    expect(crumbs[1].href).toBeUndefined();
  });

  it("/tamil-nadu/t/elections -> [Home, Tamil Nadu, Elections (leaf)] (socio-econ cascade through state topic)", () => {
    const crumbs = stateTopicCrumbs({
      state: "tamil-nadu",
      topic: "elections",
    });
    expect(crumbs).toHaveLength(3);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[0].href).toBe("/");
    expect(crumbs[1].label).toBe("Tamil Nadu");
    expect(crumbs[1].href).toBe("/tamil-nadu");
    expect(crumbs[2].label).toBe("Elections");
    expect(crumbs[2].isLeaf).toBe(true);
  });

  it("/tamil-nadu/elections/AcGenMay2026 -> 4 crumbs (state hub -> state-elections hub -> event leaf)", () => {
    const crumbs = stateElectionCrumbs({
      state: "tamil-nadu",
      event: "AcGenMay2026",
    });
    expect(crumbs).toHaveLength(4);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[0].href).toBe("/");
    expect(crumbs[1].label).toBe("Tamil Nadu");
    expect(crumbs[1].href).toBe("/tamil-nadu");
    expect(crumbs[2].label).toBe("Tamil Nadu elections");
    expect(crumbs[2].href).toBe("/tamil-nadu/t/elections");
    expect(crumbs[3].label).toBe("AcGenMay2026");
    expect(crumbs[3].isLeaf).toBe(true);
  });

  it("/tamil-nadu/elections/AcGenMay2026/ac/167-mylapore -> 5 crumbs (canonical nested AC)", () => {
    // The canonical nested constituency URL exposes the full ascend
    // chain: state hub, state-elections hub, event, AC (leaf). The
    // brief PR-W1d spec REQUIRES this 5-crumb chain - this is the
    // user-visible behavioural lift over the legacy 3-crumb
    // GeoBreadcrumb derivation, which collapsed to [Home, state, AC].
    const crumbs = constituencyCanonicalCrumbs({
      state: "tamil-nadu",
      event: "AcGenMay2026",
      ac_slug: "167-mylapore",
    });
    expect(crumbs).toHaveLength(5);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[0].href).toBe("/");
    expect(crumbs[1].label).toBe("Tamil Nadu");
    expect(crumbs[1].href).toBe("/tamil-nadu");
    expect(crumbs[2].label).toBe("Tamil Nadu elections");
    expect(crumbs[2].href).toBe("/tamil-nadu/t/elections");
    expect(crumbs[3].label).toBe("AcGenMay2026");
    expect(crumbs[3].href).toBe("/tamil-nadu/elections/AcGenMay2026");
    expect(crumbs[4].label).toBe("Mylapore");
    expect(crumbs[4].isLeaf).toBe(true);
    expect(crumbs[4].href).toBeUndefined();
  });

  it("/tamil-nadu/ac/167-mylapore -> 3 crumbs (bare-AC pre-redirect window)", () => {
    // The bare-AC convenience URL hands the citizen a sensible chain
    // during the brief window before Constituency.svelte's
    // replaceState pushes them to the canonical nested form.
    const crumbs = constituencyBareCrumbs({
      state: "tamil-nadu",
      ac_slug: "167-mylapore",
    });
    expect(crumbs).toHaveLength(3);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[1].label).toBe("Tamil Nadu");
    expect(crumbs[1].href).toBe("/tamil-nadu");
    expect(crumbs[2].label).toBe("Mylapore");
    expect(crumbs[2].isLeaf).toBe(true);
  });

  it("/t/energy -> [Home, Topics, Energy (leaf)] (socio-econ topic-landing cascade)", () => {
    // The socio-econ cascade through the topic-front-door surface.
    // Same component (Breadcrumb.svelte) renders this AND the election
    // cascade above - exercising the ONE-component design.
    const crumbs = topicLandingCrumbs({ topic: "energy" });
    expect(crumbs).toHaveLength(3);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[0].href).toBe("/");
    expect(crumbs[1].label).toBe("Topics");
    expect(crumbs[1].href).toBe("/t");
    expect(crumbs[2].label).toBe("Energy");
    expect(crumbs[2].isLeaf).toBe(true);
  });
});

describe("Breadcrumb / route-crumbs - structural invariants", () => {
  it("the leaf crumb is ALWAYS marked isLeaf:true and has no href", () => {
    const allBuilders = [
      homeCrumbs(),
      stateOverviewCrumbs({ state: "tamil-nadu" }),
      stateTopicCrumbs({ state: "tamil-nadu", topic: "fiscal" }),
      stateElectionCrumbs({ state: "tamil-nadu", event: "AcGenMay2026" }),
      constituencyCanonicalCrumbs({
        state: "tamil-nadu",
        event: "AcGenMay2026",
        ac_slug: "167-mylapore",
      }),
      constituencyBareCrumbs({
        state: "tamil-nadu",
        ac_slug: "167-mylapore",
      }),
      topicLandingCrumbs({ topic: "energy" }),
    ];
    for (const chain of allBuilders) {
      const leaf = chain[chain.length - 1];
      expect(leaf.isLeaf).toBe(true);
      expect(leaf.href).toBeUndefined();
    }
  });

  it("every non-leaf crumb carries an href", () => {
    const allBuilders = [
      stateOverviewCrumbs({ state: "tamil-nadu" }),
      stateTopicCrumbs({ state: "tamil-nadu", topic: "fiscal" }),
      stateElectionCrumbs({ state: "tamil-nadu", event: "AcGenMay2026" }),
      constituencyCanonicalCrumbs({
        state: "tamil-nadu",
        event: "AcGenMay2026",
        ac_slug: "167-mylapore",
      }),
      topicLandingCrumbs({ topic: "energy" }),
    ];
    for (const chain of allBuilders) {
      const ascend = chain.slice(0, -1);
      for (const crumb of ascend) {
        expect(crumb.href).toBeTypeOf("string");
        expect(crumb.href).not.toBe("");
        expect(crumb.isLeaf).toBeFalsy();
      }
    }
  });

  it("recovers AC display name from <eci_no>-<slug> shape (Mylapore from 167-mylapore)", () => {
    const crumbs = constituencyCanonicalCrumbs({
      state: "tamil-nadu",
      event: "AcGenMay2026",
      ac_slug: "167-mylapore",
    });
    expect(crumbs.at(-1)?.label).toBe("Mylapore");
  });

  it("title-cases multi-word AC slug (cooch-behar-uttar -> Cooch Behar Uttar)", () => {
    const crumbs = constituencyCanonicalCrumbs({
      state: "west-bengal",
      event: "AcGenMay2026",
      ac_slug: "42-cooch-behar-uttar",
    });
    expect(crumbs.at(-1)?.label).toBe("Cooch Behar Uttar");
  });

  it("falls back to 'AC <n>' when slug has no name half (bare 167)", () => {
    const crumbs = constituencyCanonicalCrumbs({
      state: "tamil-nadu",
      event: "AcGenMay2026",
      ac_slug: "167",
    });
    expect(crumbs.at(-1)?.label).toBe("AC 167");
  });

  it("title-cases multi-word topic slug (state-finance -> State Finance)", () => {
    const crumbs = stateTopicCrumbs({
      state: "tamil-nadu",
      topic: "state-finance",
    });
    expect(crumbs.at(-1)?.label).toBe("State Finance");
  });
});
