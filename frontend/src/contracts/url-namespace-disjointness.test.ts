/**
 * Namespace-disjointness contract for the place-first URL grammar (ADR-0037).
 *
 * The Grammar A resolver decides whether `/tamil-nadu/<x>` should render
 * a sub-geography (AC), an indicator at state-scope, or a chrome surface
 * based purely on which registry `<x>` lands in. That only works if the
 * registries don't overlap — a slug that appears in two registries is
 * an ambiguous URL.
 *
 * ## Phase 2 scope (this file, as of PR-P2)
 *
 * Phase 2 asserts disjointness for the FOUR registries currently
 * verifiable from the on-disk corpus, against the RESERVED set
 * defined in `frontend/src/lib/links.ts`:
 *
 *   1. State slugs   — slugified `display_name` from `datasets/taxonomy/entities.json`
 *   2. Topic slugs   — `id` field from `datasets/taxonomy/topics.json`
 *   3. AC slugs      — slugified `name` from `datasets/data/entities/electoral.csv`
 *                      where `entity_kind === "ac"`. The set is deduped
 *                      across states + delim years; collision is the
 *                      concern, not currency.
 *   4. RESERVED      — `RESERVED_PATH_TOKENS` from `links.ts`
 *
 * Pairwise disjointness asserted:
 *
 *   * stateSlugs ⊥ topicSlugs
 *   * stateSlugs ⊥ RESERVED
 *   * topicSlugs ⊥ RESERVED
 *   * acSlugs    ⊥ stateSlugs
 *   * acSlugs    ⊥ topicSlugs
 *   * acSlugs    ⊥ RESERVED
 *
 * ## PR-0 event-context disjointness (election experience overhaul plan)
 *
 * The election experience overhaul plan (2026-06-09) locks the new
 * election URL cascade:
 *
 *   /t/elections                                         (firehose)
 *   /t/elections/<event-slug>                            (national)
 *   /<state>/elections/<event-slug>                      (state slice)
 *   /<state>/elections/<event-slug>/<constituency-slug>  (constituency)
 *   /compare/elections/<state>/<from>/<to>               (compare)
 *
 * The path-segment literals `{"general", "assembly", "elections"}`
 * carry event-context identity at depths 2-3 of the cascade
 * (`general-` / `assembly-` as event-slug body prefixes; `elections`
 * as the middle-segment literal). PR-0 asserts no state slug, topic
 * slug, or AC name slug equals any literal in that set, so a
 * 1-segment URL like `/general` cannot be misread as a state hub.
 *
 * Event-slug grammar is regex-pinned:
 *
 *   ^(general|assembly)(-bye-[a-z0-9-]+|-\d{4})$
 *
 * `elections` is deliberately NOT added to `RESERVED_PATH_TOKENS`
 * because the firehose stays at the existing `/t/elections` (top-
 * level reservation `t` covers it). The event-context literals are
 * a separate concern from chrome reservations.
 *
 * ## Deferred registries (Phase 3)
 *
 *   * **Indicator url_slug** (Max §3i on ADR-0037). The `url_slug` field
 *     does not yet exist on `datasets/taxonomy/indicators.parquet` or
 *     `datasets/_ops/indicators-completeness.json`. Phase 3 adds
 *     the field + extends this test to assert the 5-way disjointness Max
 *     ratified.
 *
 * When this test goes red, the answer is to rename the colliding slug,
 * never to add an exception to the test. Doctrine: slugs are part of the
 * citizen contract; collisions are slug-quality bugs.
 *
 * Reading the real corpus instead of fixtures: mirrors
 * `frontend/src/contracts/datasets-conform.test.ts` — the bet that "the
 * data conforms to the contract" must be verifiable against shipped
 * artefacts, not synthetic ones.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { RESERVED_PATH_TOKENS } from "../lib/links";
import { slugify } from "../lib/slug";

const repoRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
);
const entitiesPath = resolve(repoRoot, "datasets/taxonomy/entities.json");
const topicsPath = resolve(repoRoot, "datasets/taxonomy/topics.json");
const electoralCsvPath = resolve(
  repoRoot,
  "datasets/data/entities/electoral.csv",
);

interface EntityRow {
  entity_id: string;
  entity_type: string;
  display_name: string;
  entity_valid_to?: string | null;
}

interface TopicRow {
  id: string;
}

function loadActiveStateSlugs(): string[] {
  const raw = JSON.parse(readFileSync(entitiesPath, "utf-8")) as {
    entities: EntityRow[];
  };
  const slugs = raw.entities
    .filter(
      (r) =>
        (r.entity_type === "state" || r.entity_type === "ut") &&
        (r.entity_valid_to === null || r.entity_valid_to === undefined),
    )
    .map((r) => slugify(r.display_name));
  return slugs;
}

function loadTopicSlugs(): string[] {
  const raw = JSON.parse(readFileSync(topicsPath, "utf-8")) as {
    topics: TopicRow[];
  };
  return raw.topics.map((t) => t.id);
}

/**
 * Load the deduped set of AC name-slugs from the canonical electoral
 * entities CSV. The CSV column order is
 * `entity_id, name, entity_kind, delim_year, state, parent, eci_no, aliases, reservation`
 * (verified 2026-06-10: 4734 rows, all 9 columns, zero quoted fields,
 * so the naive `split(",")` is safe — no name in the corpus contains a
 * comma).
 *
 * Include ALL AC rows across all delim_years; the disjointness concern
 * is the unique slug set, not which delimitation cohort emitted it. Two
 * ACs with the same name across states / delim cohorts collapse to one
 * slug — exactly the case we need to test against the state / topic /
 * RESERVED registries.
 */
function loadActiveAcSlugs(): string[] {
  const csv = readFileSync(electoralCsvPath, "utf-8");
  const lines = csv.split(/\r?\n/).filter((l) => l.length > 0);
  lines.shift(); // header
  const slugs = new Set<string>();
  for (const line of lines) {
    const cols = line.split(",");
    if (cols[2] !== "ac") continue;
    const name = cols[1];
    if (!name) continue;
    slugs.add(slugify(name));
  }
  return [...slugs];
}

function findDuplicates(slugs: string[]): string[] {
  const seen = new Set<string>();
  const dupes: string[] = [];
  for (const slug of slugs) {
    if (seen.has(slug)) dupes.push(slug);
    seen.add(slug);
  }
  return dupes;
}

function intersection<T>(a: readonly T[], b: readonly T[]): T[] {
  const bSet = new Set(b);
  return a.filter((x) => bSet.has(x));
}

describe("Phase 2 URL namespace disjointness (ADR-0037)", () => {
  const stateSlugs = loadActiveStateSlugs();
  const topicSlugs = loadTopicSlugs();
  const acSlugs = loadActiveAcSlugs();

  it("loads ≥28 active state+UT slugs (sanity)", () => {
    // India has 28 states + 8 UTs = 36 currently active; older snapshots
    // may carve different counts. The floor catches "registry failed to
    // load at all".
    expect(stateSlugs.length).toBeGreaterThanOrEqual(28);
  });

  it("loads ≥1 topic slug (sanity)", () => {
    expect(topicSlugs.length).toBeGreaterThanOrEqual(1);
  });

  it("loads ≥3000 unique AC name-slugs (sanity)", () => {
    // 4189 AC rows across all delim_years dedupe to ~3960 unique slugs
    // as of 2026-06-10. The floor catches "CSV failed to load at all"
    // without pinning a brittle exact count that future ingest will move.
    expect(acSlugs.length).toBeGreaterThanOrEqual(3000);
  });

  it("state slugs are internally unique", () => {
    expect(findDuplicates(stateSlugs)).toEqual([]);
  });

  it("topic slugs are internally unique", () => {
    expect(findDuplicates(topicSlugs)).toEqual([]);
  });

  it("stateSlugs ⊥ topicSlugs", () => {
    const overlap = intersection(stateSlugs, topicSlugs);
    expect(overlap).toEqual([]);
  });

  it("stateSlugs ⊥ RESERVED_PATH_TOKENS", () => {
    const overlap = intersection(stateSlugs, RESERVED_PATH_TOKENS);
    expect(overlap).toEqual([]);
  });

  it("topicSlugs ⊥ RESERVED_PATH_TOKENS", () => {
    const overlap = intersection(topicSlugs, RESERVED_PATH_TOKENS);
    expect(overlap).toEqual([]);
  });

  it("acSlugs ⊥ stateSlugs", () => {
    // STOP-AND-SURFACE rule (PR-P2 spec): if this fires with real
    // collisions, do NOT auto-rename ACs. List the colliding slugs
    // and escalate to the orchestrator — renaming an AC is a citizen-
    // visible URL change, not a mechanical fix.
    const overlap = intersection(acSlugs, stateSlugs);
    expect(overlap).toEqual([]);
  });

  it("acSlugs ⊥ topicSlugs", () => {
    const overlap = intersection(acSlugs, topicSlugs);
    expect(overlap).toEqual([]);
  });

  it("acSlugs ⊥ RESERVED_PATH_TOKENS", () => {
    const overlap = intersection(acSlugs, RESERVED_PATH_TOKENS);
    expect(overlap).toEqual([]);
  });
});

/**
 * PR-0 event-context disjointness (election experience overhaul plan,
 * 2026-06-09). Three pairwise disjointness assertions + one regex
 * sanity pin for the locked event-slug grammar. See the file header
 * `## PR-0 event-context disjointness` block for the rationale.
 *
 * Note: deliberately mounted as a separate `describe` block so the
 * Phase 2 invariants above survive an event-context regression and
 * vice versa - either failure surfaces independently.
 */
describe("PR-0 event-context disjointness (election experience overhaul plan)", () => {
  // The full set carries the three path-segment literals that appear
  // in the locked elections cascade. `general` + `assembly` are
  // event-slug BODY PREFIXES (`general-2024`, `assembly-2023`) and
  // never appear as bare segments. `elections` is the MIDDLE-segment
  // literal at `/<state>/elections/<event>` and the firehose path
  // `/t/elections`.
  const EVENT_BODY_PREFIXES = ["general", "assembly"] as const;
  const EVENT_CONTEXT_LITERALS = ["general", "assembly", "elections"] as const;
  const EVENT_SLUG_REGEX = /^(general|assembly)(-bye-[a-z0-9-]+|-\d{4})$/;

  const stateSlugs = loadActiveStateSlugs();
  const topicSlugs = loadTopicSlugs();
  const acSlugs = loadActiveAcSlugs();

  it("event-slug regex accepts the four canonical shapes", () => {
    // Sanity-pin the locked grammar so a typo in the regex itself
    // surfaces here instead of letting a malformed event-slug land in
    // datasets/taxonomy/election_events.json.
    expect("general-2024").toMatch(EVENT_SLUG_REGEX);
    expect("assembly-2023").toMatch(EVENT_SLUG_REGEX);
    expect("general-bye-2024-bihar-bastar").toMatch(EVENT_SLUG_REGEX);
    expect("assembly-bye-2024-tarikere").toMatch(EVENT_SLUG_REGEX);
  });

  it("event-slug regex rejects malformed and Hindi-token shapes", () => {
    // The No-Hindi policy (see docs/architecture/frontend/url-grammar.md
    // section "No-Hindi policy") forbids `lok-sabha` / `vidhan-sabha`
    // body prefixes. The regex must reject them so a future agent can
    // not silently reintroduce them.
    expect("lok-sabha-2024").not.toMatch(EVENT_SLUG_REGEX);
    expect("vidhan-sabha-2023").not.toMatch(EVENT_SLUG_REGEX);
    expect("LsGenJun2024").not.toMatch(EVENT_SLUG_REGEX); // legacy id form
    expect("general").not.toMatch(EVENT_SLUG_REGEX); // missing year
    expect("general-24").not.toMatch(EVENT_SLUG_REGEX); // 2-digit year
    expect("parliament-2024").not.toMatch(EVENT_SLUG_REGEX); // wrong body prefix
  });

  it("stateSlugs ⊥ {general, assembly, elections}", () => {
    const overlap = intersection(stateSlugs, EVENT_CONTEXT_LITERALS);
    expect(overlap).toEqual([]);
  });

  it("topicSlugs ⊥ {general, assembly}", () => {
    // CARVE-OUT: the topic id `elections` IS in topics.json today
    // (the elections topic family). Its `/t/elections` landing is
    // superseded by the firehose route registered ahead of
    // `/t/:topic` in main.ts (PR-W3d). The topic id stays valid for
    // discoverability + indicator-to-topic mapping; only the route
    // dispatch changes. So this assertion narrows to the two event-
    // body prefixes that have no legitimate topic identity. If a
    // future PR mints `general` or `assembly` as a topic id, that is
    // a real collision - rename the topic, never relax this test.
    const overlap = intersection(topicSlugs, EVENT_BODY_PREFIXES);
    expect(overlap).toEqual([]);
  });

  it("acSlugs ⊥ {general, assembly, elections}", () => {
    // STOP-AND-SURFACE rule (matching the Phase 2 acSlugs ⊥ stateSlugs
    // assertion above): if a real AC ever exists named `General`,
    // `Assembly`, or `Elections`, the resolution is escalation, not
    // an auto-rename. AC names are citizen-visible URL contracts.
    const overlap = intersection(acSlugs, EVENT_CONTEXT_LITERALS);
    expect(overlap).toEqual([]);
  });
});
