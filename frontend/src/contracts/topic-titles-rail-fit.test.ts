// Contract: every catalogue topic title must fit the LeftRail width
// budget. The rail derives its label for THIS STATE → topic items from
// `topic-catalogue.json` `topic.title` (Jony 2026-05-16 review — rail
// title and page H1 are the SAME string, sourced once). The rail column
// renders at ~13rem wide with ~0.875rem text; titles longer than ~24
// characters wrap onto a second line and break visual rhythm.
//
// This is a soft typographic budget, not a hard render constraint, so we
// cap at 24 characters and document the rationale here rather than in
// `topic-catalogue.schema.json` — keeping the schema free of UI-specific
// constraints (a future surface might want longer titles).

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const repoRoot = resolve(__dirname, "..", "..", "..");
const cataloguePath = resolve(
  repoRoot,
  "datasets",
  "reference",
  "in",
  "topic-catalogue.json",
);

interface Topic {
  id: string;
  title: string;
}
interface Catalogue {
  topics: Topic[];
}

const RAIL_BUDGET = 24;

describe("topic-catalogue.json rail-fit budget", () => {
  const catalogue = JSON.parse(readFileSync(cataloguePath, "utf-8")) as Catalogue;

  it(`every topic.title fits the rail width budget (<= ${RAIL_BUDGET} chars)`, () => {
    const offenders = catalogue.topics
      .filter(t => t.title.length > RAIL_BUDGET)
      .map(t => `${t.id} -> "${t.title}" (${t.title.length} chars)`);
    expect(
      offenders,
      [
        `${offenders.length} topic title(s) exceed the rail width budget of ${RAIL_BUDGET} chars.`,
        "Rail labels are sourced from topic-catalogue.json `topic.title`",
        "(rail-groups.ts derives label from the catalogue, not from a",
        "local synonym table). Either shorten the title in the catalogue",
        "or widen the rail. See TODO/20260515-state-page-ia-rework-plan.md §11 #5.",
      ].join("\n"),
    ).toEqual([]);
  });

  it("the rail's seven THIS STATE ids are all present in the catalogue", () => {
    // Co-anchor the rail-vs-catalogue contract: ids the rail surfaces
    // MUST exist in the catalogue, else `topicTitles.get(id) ?? id`
    // silently falls back to a raw slug in production.
    const RAIL_IDS = [
      "fiscal",
      "energy",
      "economy",
      "health",
      "environment",
      "transport",
      "elections",
    ];
    const catalogue_ids = new Set(catalogue.topics.map(t => t.id));
    const missing = RAIL_IDS.filter(id => !catalogue_ids.has(id));
    expect(missing, `rail topic ids missing from catalogue: ${missing.join(", ")}`).toEqual([]);
  });
});
