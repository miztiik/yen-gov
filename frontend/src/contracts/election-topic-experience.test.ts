// election-topic-experience drift guard (EGC-A2).
//
// GAP A closure: the rich Assembly election experience (map + equal-seats
// cartogram + time-slider + filter rail) must render on BOTH surfaces a
// citizen can reach it from —
//   * the event permalink  /s/:state/elections/:event   (StateElection.svelte)
//   * the topic door        /s/:state/t/elections        (StateTopic.svelte)
// Both must mount the SAME shared component (StateElectionExperience.svelte) and
// resolve the SAME default event, so the two surfaces can never drift into
// showing different results for the same state. This test fails if either route
// stops importing the shared component, stops gating on assembly events, or if
// the default-event resolver disagrees between them.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  defaultEventForState,
  type ElectionEventsCatalogue,
} from "../lib/election-events";

const routesDir = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "routes");
const stateElectionSrc = readFileSync(resolve(routesDir, "StateElection.svelte"), "utf-8");
const stateTopicSrc = readFileSync(resolve(routesDir, "StateTopic.svelte"), "utf-8");
const topicLandingSrc = readFileSync(resolve(routesDir, "TopicLanding.svelte"), "utf-8");

describe("elections experience renders on both the permalink and the topic door", () => {
  it("both routes import the shared StateElectionExperience component", () => {
    expect(stateElectionSrc).toContain("StateElectionExperience");
    expect(stateTopicSrc).toContain("StateElectionExperience");
  });

  it("both routes mount the experience only for assembly events", () => {
    // The permalink gates the mount on the event row; the topic door gates on
    // the active row. Both must guard with kind === "assembly" so Lok Sabha
    // slices keep drilling into the national atlas instead of the AC map.
    expect(stateElectionSrc).toMatch(/ev\.kind === "assembly"/);
    expect(stateTopicSrc).toMatch(/ev\.kind === "assembly"/);
  });

  it("the topic door resolves its default event via the shared resolver", () => {
    // defaultEventForState is the single source of truth for "which event leads"
    // on every house-view surface. The topic door must use it (not a bespoke
    // pick) so it agrees with every other elections surface.
    expect(stateTopicSrc).toContain("defaultEventForState");
  });
});

describe("national /t/elections topic door mounts the national atlas (EGC-A3)", () => {
  it("the topic landing mounts the national PC atlas experience", () => {
    expect(topicLandingSrc).toContain("NationalElectionsAtlas");
  });

  it("gates the national atlas mount on the elections topic", () => {
    expect(topicLandingSrc).toMatch(/topic\.id === "elections"/);
  });

  it("resolves the default Lok Sabha event via the shared national resolver", () => {
    // Same drift guard as the state door: the national default must come from
    // defaultNationalLokSabhaEvent, never a hardcoded event id.
    expect(topicLandingSrc).toContain("defaultNationalLokSabhaEvent");
  });
});

describe("shared default-event resolution (no per-surface drift)", () => {
  const catalogue: ElectionEventsCatalogue = {
    version: "test",
    states: {
      S13: [
        {
          event_id: "AcGenOct2019",
          display: "2019 Assembly",
          kind: "assembly",
          polled_on: "2019-10-21",
          data_status: "complete",
        },
        {
          event_id: "AcGenOct2014",
          display: "2014 Assembly",
          kind: "assembly",
          polled_on: "2014-10-15",
          data_status: "complete",
        },
        {
          event_id: "LsGen2024",
          display: "2024 Lok Sabha",
          kind: "lok_sabha",
          polled_on: "2024-05-13",
          data_status: "complete",
        },
      ],
    },
  } as unknown as ElectionEventsCatalogue;

  it("prefers the latest ASSEMBLY event for the AC experience", () => {
    const row = defaultEventForState(catalogue, "S13");
    expect(row?.event_id).toBe("AcGenOct2019");
    expect(row?.kind).toBe("assembly");
  });
});
