// Contract: one card per measure on a topic page. Facets of the same
// measure (species / fuel / sector) MUST live inside the card via a
// facet picker, NOT fan out as N separate cards on the topic page.
//
// See CLAUDE.md anti-pattern bullet:
//   "Do NOT add facet/grain-fanout cards to a topic page (e.g. separate
//    cards per species / fuel / facet for the same measure). One card
//    per measure; the facet picker lives inside the card."
//
// See also ADR-0044 (grain-over-entity), ADR-0045 (grapher catalogue
// split), and docs/concepts/schema-is-the-design-system.md
// "one card per measure" rule.
//
// Heuristic: within a single topic, no two artifact ids may share a
// "measure stem" (the id with the final `_<token>` segment stripped).
// Distinct measures (e.g. `naip_iv_inseminations` vs
// `naip_iv_pregnancy_diagnoses`) survive because their last tokens
// differ from their stems in citizen-meaningful ways AND their longer
// prefixes differ once the trailing token is stripped only once.
// Facet fanout (e.g. `pashu_aadhaar_count_cattle`, `..._buffalo`,
// `..._goat`) collapses to a single stem `pashu_aadhaar_count` and
// trips the assertion.

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const repoRoot = resolve(__dirname, "..", "..", "..");
const cataloguePath = resolve(
  repoRoot,
  "datasets",
  "taxonomy",
  "topics.json",
);

interface Artifact {
  kind: string;
  id: string;
}
interface Topic {
  id: string;
  artifacts?: Artifact[];
}
interface Catalogue {
  topics: Topic[];
}

function measureStem(artifactId: string): string {
  // Strip family prefix `<family>/`, then strip final `_<token>` segment.
  const slashIdx = artifactId.indexOf("/");
  const local = slashIdx >= 0 ? artifactId.slice(slashIdx + 1) : artifactId;
  const lastUnderscore = local.lastIndexOf("_");
  return lastUnderscore > 0 ? local.slice(0, lastUnderscore) : local;
}

describe("topics.json one-card-per-measure invariant", () => {
  const catalogue = JSON.parse(
    readFileSync(cataloguePath, "utf-8"),
  ) as Catalogue;

  for (const topic of catalogue.topics) {
    const artifacts = (topic.artifacts ?? []).filter(
      (a) => a.kind === "indicator",
    );
    if (artifacts.length < 2) continue;

    const stems = new Map<string, string[]>();
    for (const a of artifacts) {
      const stem = measureStem(a.id);
      const bucket = stems.get(stem) ?? [];
      bucket.push(a.id);
      stems.set(stem, bucket);
    }

    const fanouts = [...stems.entries()].filter(
      ([, ids]) => ids.length > 1,
    );

    it(`topic '${topic.id}' has no facet-fanout cards`, () => {
      expect(fanouts, JSON.stringify(fanouts, null, 2)).toEqual([]);
    });
  }
});
