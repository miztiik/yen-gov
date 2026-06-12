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
 * ## Phase 3 — indicator url_slug (live as of Deferral 2, 2026-06-10)
 *
 * The `url_slug` field landed on
 * `datasets/schemas/indicator-catalogue.schema.json` v3.0 +
 * `datasets/taxonomy/indicators.json` (per Deferral 2 of
 * `TODO/20260609-url-prefix-drop-phase0-plan.md`, Hans + Max + Gregor
 * unanimous 2026-06-10). This file's Phase 3 describe-block extends the
 * 4-way disjointness above to the FIVE registries the place-first URL
 * grammar dispatches on:
 *
 *   1. State slugs        — from `entities.json`
 *   2. Topic slugs        — from `topics.json`
 *   3. AC slugs           — from `electoral.csv`
 *   4. Indicator url_slug — from `indicators.json` (current + every
 *                            `url_slug_history[]` entry, since
 *                            historical slugs continue to resolve via
 *                            the forever-redirect ledger)
 *   5. RESERVED           — `RESERVED_PATH_TOKENS` from `links.ts`
 *
 * Pairwise: indicator slugs are disjoint from each of the other four
 * registries, AND internally unique across current + historical entries.
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
import { slugify, partyIdToSlug } from "../lib/slug";

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
const indicatorsPath = resolve(repoRoot, "datasets/taxonomy/indicators.json");
const partiesCsvPath = resolve(repoRoot, "datasets/data/entities/parties.csv");

interface EntityRow {
  entity_id: string;
  entity_type: string;
  display_name: string;
  entity_valid_to?: string | null;
  parent_entity_id?: string | null;
  entity_code?: string | null;
}

interface TopicRow {
  id: string;
}

interface IndicatorRow {
  indicator_id: string;
  url_slug: string;
  url_slug_history?: string[];
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

/**
 * Load the deduped set of PC (Parliament constituency) name-slugs from
 * the canonical electoral entities CSV. PR-W3b (election experience
 * overhaul, 2026-06-10): the new 4-segment leaf route
 * `/<state>/elections/<event>/<constituency>` dispatches AC vs PC from
 * the event-slug body prefix and resolves the bare name slug against
 * electoral.csv. PC name-slugs must therefore be disjoint from the
 * event-slug regex for the same reason AC name-slugs are - a
 * constituency named `general-2024` would mis-route as an event
 * cascade rather than a leaf.
 */
function loadActivePcSlugs(): string[] {
  const csv = readFileSync(electoralCsvPath, "utf-8");
  const lines = csv.split(/\r?\n/).filter((l) => l.length > 0);
  lines.shift(); // header
  const slugs = new Set<string>();
  for (const line of lines) {
    const cols = line.split(",");
    if (cols[2] !== "pc") continue;
    const name = cols[1];
    if (!name) continue;
    slugs.add(slugify(name));
  }
  return [...slugs];
}

/**
 * Per-state district slug map for the Deferral 1 disjointness gate.
 *
 * Returns `Map<stateSlug, Set<districtSlug>>` derived from the SAME
 * `taxonomy/entities.json` rowset that `routes/StateSubRouter.svelte`
 * loads at runtime. The runtime loader filters by `parent_entity_id
 * === "IN-${eci_code}"`; this function mirrors that join (entity_id
 * of the state row -> parent_entity_id of the district rows) so the
 * test failure mode matches a runtime collision exactly.
 *
 * Only currently-valid (`entity_valid_to == null`) districts whose
 * parent is a currently-valid state/UT are included; the disjointness
 * concern is the live URL surface, not the historical entity set.
 */
function loadDistrictSlugsByState(): Map<string, Set<string>> {
  const raw = JSON.parse(readFileSync(entitiesPath, "utf-8")) as {
    entities: EntityRow[];
  };
  // Build state entity_id -> stateSlug once so the district loop is
  // a single pass.
  const stateSlugByEid = new Map<string, string>();
  for (const r of raw.entities) {
    if (
      (r.entity_type === "state" || r.entity_type === "ut") &&
      (r.entity_valid_to === null || r.entity_valid_to === undefined)
    ) {
      stateSlugByEid.set(r.entity_id, slugify(r.display_name));
    }
  }
  const byState = new Map<string, Set<string>>();
  for (const r of raw.entities) {
    if (r.entity_type !== "district") continue;
    if (r.entity_valid_to !== null && r.entity_valid_to !== undefined) continue;
    if (!r.parent_entity_id) continue;
    const parentSlug = stateSlugByEid.get(r.parent_entity_id);
    if (!parentSlug) continue;
    const slug = slugify(r.display_name);
    if (!slug) continue;
    let set = byState.get(parentSlug);
    if (!set) {
      set = new Set<string>();
      byState.set(parentSlug, set);
    }
    set.add(slug);
  }
  return byState;
}

/**
 * Per-state AC slug map for the Deferral 1 disjointness gate.
 *
 * Returns `Map<stateSlug, Set<acSlug>>` derived from the SAME
 * `datasets/data/entities/electoral.csv` the runtime loader reads.
 * The `state` column (index 4) is already in lower-case slug form
 * (`tamil-nadu`, `andhra-pradesh`) so no extra normalisation is
 * needed.
 *
 * Includes ALL AC rows across all delim_years (the runtime
 * StateSubRouter loads them via fetchConstituencies which is
 * per-state); for the disjointness gate the slug-set union per
 * state is what matters.
 */
function loadAcSlugsByState(): Map<string, Set<string>> {
  const csv = readFileSync(electoralCsvPath, "utf-8");
  const lines = csv.split(/\r?\n/).filter((l) => l.length > 0);
  lines.shift(); // header
  const byState = new Map<string, Set<string>>();
  for (const line of lines) {
    const cols = line.split(",");
    if (cols[2] !== "ac") continue;
    const name = cols[1];
    const stateSlug = cols[4];
    if (!name || !stateSlug) continue;
    const slug = slugify(name);
    if (!slug) continue;
    let set = byState.get(stateSlug);
    if (!set) {
      set = new Set<string>();
      byState.set(stateSlug, set);
    }
    set.add(slug);
  }
  return byState;
}

/**
 * Load the union of every `url_slug` AND every `url_slug_history[]`
 * entry from `datasets/taxonomy/indicators.json`. v3.0 of the catalogue
 * (Deferral 2 of `TODO/20260609-url-prefix-drop-phase0-plan.md`, 2026-06-10)
 * makes `url_slug` REQUIRED on every row; `url_slug_history` is OPTIONAL
 * but ALSO disjointness-relevant because historical slugs continue to
 * resolve via the forever-redirect ledger.
 *
 * Returns the FULL list (with duplicates) so the internal-uniqueness
 * assertion can name the colliding slug. The disjointness pairings
 * intersect against this list directly.
 */
function loadIndicatorUrlSlugs(): string[] {
  const raw = JSON.parse(readFileSync(indicatorsPath, "utf-8")) as {
    indicators: IndicatorRow[];
  };
  const slugs: string[] = [];
  for (const row of raw.indicators) {
    if (typeof row.url_slug === "string" && row.url_slug.length > 0) {
      slugs.push(row.url_slug);
    }
    if (Array.isArray(row.url_slug_history)) {
      for (const slug of row.url_slug_history) {
        if (typeof slug === "string" && slug.length > 0) slugs.push(slug);
      }
    }
  }
  return slugs;
}

/**
 * Load the deduped set of party URL slugs from
 * `datasets/data/entities/parties.csv`.
 *
 * Per ADR-0053 (PR-0 of TODO/20260612-party-rendering-and-party-pages-plan.md,
 * 2026-06-12) the canonical per-party page lives at `/parties/<slug>`
 * where the slug is derived from `party_id` via `partyIdToSlug`
 * (lowercased tail with `_` -> `-`, with sentinel overrides for IND
 * -> "independent" and UNK -> NULL).
 *
 * Slugs are deduped (UNK skipped entirely; everything else unique by
 * construction since `party_id` is the PK of parties.csv). The
 * `partySlugs` internal-uniqueness assertion below catches the
 * regression where someone hand-edits parties.csv and accidentally
 * creates a duplicate `party_id`.
 *
 * CSV column order from the v1.1 schema: `party_id, short, full,
 * eci_codes, brand_colour, symbol_asset, wikipedia, aliases,
 * recognition_scope, home_state_codes, founded_year, dissolved_year,
 * predecessor_party_ids, successor_party_ids, name_history,
 * claims_to_parent_name, name_native_script, is_sentinel`. Only the
 * first column (party_id) is needed for the disjointness gate.
 *
 * The parties.csv is hand-authored + tool-edited; rows may contain
 * commas inside quoted fields (e.g. `aliases` joining multiple
 * variants). The naive `split(",")` is safe for the FIRST column
 * because party_id never contains commas (`parties.IN.<UPPER_TOKEN>`
 * by construction); a more robust CSV parser is unnecessary just to
 * read column 0.
 */
function loadPartySlugs(): string[] {
  const csv = readFileSync(partiesCsvPath, "utf-8");
  const lines = csv.split(/\r?\n/).filter((l) => l.length > 0);
  lines.shift(); // header
  const slugs = new Set<string>();
  for (const line of lines) {
    const party_id = line.split(",", 1)[0];
    if (!party_id) continue;
    const slug = partyIdToSlug(party_id);
    if (slug === null) continue; // UNK: no citizen page
    slugs.add(slug);
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

  it("constituency name-slugs (AC + PC) do not match the event-slug regex", () => {
    // PR-W3b (election experience overhaul, 2026-06-10): the new
    // 4-segment leaf route `/<state>/elections/<event>/<constituency>`
    // shares a path segment with the event-slug position one segment
    // up. A constituency named e.g. "general-2024" would slugify to
    // exactly the event-slug shape and the router would lose the
    // ability to tell them apart. STOP-AND-SURFACE: a real such name
    // is escalation (rename the seat in electoral.csv with
    // Hans+Max signoff, NOT a router-side workaround).
    const acSlugs = loadActiveAcSlugs();
    const pcSlugs = loadActivePcSlugs();
    const constituency_slugs = [...new Set([...acSlugs, ...pcSlugs])];
    const collisions = constituency_slugs.filter((s) =>
      EVENT_SLUG_REGEX.test(s),
    );
    expect(collisions).toEqual([]);
  });
});

/**
 * Deferral 1 per-state district vs AC resolver gate (Option A, ratified
 * 2026-06-10 by the orchestrator after a STOP-AND-SURFACE).
 *
 * **What changed vs the original Jony rule #2 strict-disjointness draft**:
 * the strict per-state `districts ⊥ ACs` assertion is DROPPED. The
 * shipped corpus carries 401 collisions across 25 states (verified
 * 2026-06-10) because Indian electoral geography names many ACs after
 * their district HQ (e.g. an AC named `Coimbatore` inside Coimbatore
 * district is the rule, not the exception). Forcing a strict gate
 * would either:
 *   1. Block PR-D1 on a Hans+Max-signed-off corpus rename of ~401
 *      AC rows (a citizen-visible URL change touching the canonical
 *      data spine — Holy Law-level work that does NOT belong inside a
 *      routing PR), or
 *   2. Auto-rename ACs without the data team's signoff (Anti-pattern
 *      #1 in CLAUDE.md s10: silent demotion of a user-named artifact).
 *
 * Option A's verdict: the depth-2 state-sub dispatcher
 * (`routes/StateSubRouter.svelte` + `lib/state-sub-resolver.ts`,
 * shipped 2026-06-10) IS the gate. It resolves district-first per
 * Jony rule #4 resolution order; the colliding AC stays reachable
 * via the canonical event-nested URL `/<state>/elections/<event>/ac/<ac>`
 * per ADR-0052 (bare positional AC was always a convenience entry,
 * never a canonical resource). Citizens reach every AC; the
 * positional URL `/<state>/<slug>` resolves deterministically.
 *
 * This describe block keeps the SANITY floors (catch "registry
 * failed to load at all") + adds a positive presence-of-collisions
 * check ("collisions exist by design — the resolver wins"). The
 * absence of strict-disjointness is now a documented design choice,
 * not an oversight: see
 *   * `docs/architecture/frontend/routing.md` § "Depth-2 dispatcher
 *     resolution rule" — the design choice + the canonical AC URL
 *     escape hatch.
 *   * `frontend/src/lib/state-sub-resolver.ts` module docstring —
 *     resolution order + 401-baseline citation.
 *   * `TODO/20260609-url-prefix-drop-phase0-plan.md` § "Follow-up
 *     deferrals" — the optional Hans+Max corpus rename row that
 *     would enable bare-positional AC URLs (NOT BLOCKING).
 *
 * Cross-state collisions remain NOT a concern: `/tamil-nadu/coimbatore`
 * (district) and `/maharashtra/coimbatore` (hypothetical AC) live
 * under different `<state>` segments and the dispatcher filters its
 * registries to one state at a time before resolving. The
 * pre-existing `acSlugs ⊥ stateSlugs` / `acSlugs ⊥ RESERVED_PATH_TOKENS`
 * assertions above handle the cross-cutting concerns.
 *
 * The OTHER six pairwise disjointness contracts above (state⊥topic,
 * state⊥reserved, topic⊥reserved, ac⊥state, ac⊥topic, ac⊥reserved)
 * STAY STRICT — those collision classes are real bugs and Option A
 * does not relax any of them. Option A applies SOLELY to the
 * per-state district vs AC pair.
 */
describe("Deferral 1 per-state resolver gate (districts vs ACs; Option A)", () => {
  const districtsByState = loadDistrictSlugsByState();
  const acsByState = loadAcSlugsByState();
  const stateSlugs = loadActiveStateSlugs();

  it("loads districts for >=28 states (sanity: catches registry-load failure)", () => {
    // India has 28 states + 8 UTs currently. Not every UT has
    // districts ingested yet, but the floor of 28 catches the
    // "entities.json failed to parse" or "wrong join key" failure
    // mode where the per-state map collapses to empty.
    expect(districtsByState.size).toBeGreaterThanOrEqual(28);
  });

  it("loads ACs for >=15 states (sanity: catches CSV-load failure)", () => {
    // The corpus carries AC rows for every state with a published
    // electoral catalogue (>20 states as of 2026-06-10). 15 is a
    // conservative floor that catches "electoral.csv failed to load
    // at all" without pinning a brittle exact count.
    expect(acsByState.size).toBeGreaterThanOrEqual(15);
  });

  it("at least one state has both districts AND ACs loaded (sanity)", () => {
    // Tamil Nadu has 38 districts + ~234 ACs and is the canonical
    // first-slice state. If neither registry loaded for any state, the
    // collision-counting loop below would be vacuously zero; this
    // sanity anchor prevents a silently-passing test.
    let bothFor = 0;
    for (const s of stateSlugs) {
      if ((districtsByState.get(s)?.size ?? 0) > 0 && (acsByState.get(s)?.size ?? 0) > 0) {
        bothFor += 1;
      }
    }
    expect(bothFor).toBeGreaterThanOrEqual(1);
  });

  it("district-AC name collisions exist; resolver wins per Jony rule #4 (this is by design)", () => {
    // POSITIVE presence-of-collisions check (the OPPOSITE of strict
    // disjointness). The shipped corpus has 401 (state, slug) pairs
    // where a district name equals an AC name in the same state
    // (verified 2026-06-10); this assertion catches the "corpus got
    // accidentally renamed to remove all collisions" regression OR
    // the "registry-loading silently collapsed" regression - either
    // would surface as `collisions.length === 0` and be a real bug.
    //
    // On a real collision (the dominant case) the dispatcher
    // resolves the bare positional URL `/<state>/<slug>` to the
    // DISTRICT per Jony rule #4. The colliding AC remains reachable
    // via the canonical event-nested URL
    //   /<state>/elections/<event>/ac/<ac>
    // per ADR-0052; the bare positional AC URL was always a
    // convenience entry, never a canonical resource.
    //
    // If a future agent wants STRICT per-state disjointness back,
    // that is a Hans+Max-signed-off corpus rename (~401 AC rows -> N
    // suffix) - see the "Follow-up deferrals" row in
    // TODO/20260609-url-prefix-drop-phase0-plan.md. It is NOT a
    // routing-PR concern.
    const collisions: { state: string; slug: string }[] = [];
    for (const s of stateSlugs) {
      const districts = districtsByState.get(s);
      const acs = acsByState.get(s);
      if (!districts || !acs) continue;
      for (const slug of districts) {
        if (acs.has(slug)) collisions.push({ state: s, slug });
      }
    }
    expect(
      collisions.length,
      "expected the shipped corpus to carry >=1 district/AC name collision (Option A design baseline); zero collisions means either the corpus was renamed without signoff OR the registry-loading silently collapsed",
    ).toBeGreaterThan(0);
  });
});

/**
 * Phase 3 URL namespace disjointness — indicator url_slug (Deferral 2 of
 * TODO/20260609-url-prefix-drop-phase0-plan.md, 2026-06-10). Five-way
 * disjointness: indicator url_slug (union of current + every
 * url_slug_history[] entry) is disjoint from each of the FOUR earlier
 * registries AND internally unique.
 *
 * Reads the real `datasets/taxonomy/indicators.json` -- mirrors the
 * Phase 2 + PR-0 corpus-walking pattern above. The bet is "the data
 * conforms to the contract" against shipped artefacts, not synthetic
 * fixtures.
 *
 * Mounted as a separate `describe` block (matching Phase 2 vs PR-0) so
 * a Phase 3 regression surfaces independently of the four earlier
 * registries.
 */
describe("Phase 3 URL namespace disjointness — indicator url_slug (Deferral 2)", () => {
  const stateSlugs = loadActiveStateSlugs();
  const topicSlugs = loadTopicSlugs();
  const acSlugs = loadActiveAcSlugs();
  const indicatorSlugs = loadIndicatorUrlSlugs();

  it("loads ≥100 indicator url_slugs (sanity)", () => {
    // 175 rows in the v3.0 catalogue at landing time; floor catches
    // "catalogue failed to load at all" without pinning a brittle
    // exact count that future PRs will move.
    expect(indicatorSlugs.length).toBeGreaterThanOrEqual(100);
  });

  it("indicator url_slugs are internally unique (current + historical)", () => {
    // Mirrors the per-row uniqueness throw in
    // `buildIndicatorCatalogueIndex` (frontend/src/lib/indicator-catalogue.ts
    // v3.0). The runtime index would throw at load time on any duplicate;
    // surfacing it here as a static check gives the operator a faster
    // signal than waiting for a page-load failure.
    expect(findDuplicates(indicatorSlugs)).toEqual([]);
  });

  it("indicatorSlugs ⊥ stateSlugs", () => {
    // A 1-segment URL `/<state>` MUST never collide with an indicator
    // url_slug at depth 2 (`/<state>/<slug>`); if it did, a state-hub
    // bookmark would silently resolve to an indicator page when the
    // route table dispatches at depth-1.
    const overlap = intersection(indicatorSlugs, stateSlugs);
    expect(overlap).toEqual([]);
  });

  it("indicatorSlugs ⊥ topicSlugs", () => {
    // Topic slugs at `/t/<topic>` could otherwise collide with indicator
    // slugs at `/<state>/<slug>` and confuse the discovery surface (the
    // citizen sees the same name for two different things).
    const overlap = intersection(indicatorSlugs, topicSlugs);
    expect(overlap).toEqual([]);
  });

  it("indicatorSlugs ⊥ acSlugs", () => {
    // STOP-AND-SURFACE rule (matching Phase 2 acSlugs ⊥ stateSlugs): if
    // an indicator url_slug collides with an AC name slug, the
    // resolution is to RENAME THE INDICATOR'S url_slug (operator-side,
    // single editorial change) rather than rename the AC (citizen-side,
    // boundary-data change). The Hans + Max + Gregor 2026-06-10 verdict
    // pinned url_slug as hand-authored precisely so collisions can be
    // resolved by the operator without disturbing the on-disk corpus.
    const overlap = intersection(indicatorSlugs, acSlugs);
    expect(overlap).toEqual([]);
  });

  it("indicatorSlugs ⊥ RESERVED_PATH_TOKENS", () => {
    // RESERVED_PATH_TOKENS holds chrome paths (`about`, `t`, `compare`,
    // `settings`, `disclaimer`, etc.). An indicator url_slug colliding
    // with any of these would mask the chrome route at depth 2 of
    // `/<state>/<slug>`.
    const overlap = intersection(indicatorSlugs, RESERVED_PATH_TOKENS);
    expect(overlap).toEqual([]);
  });
});

/**
 * ADR-0053 6-way URL namespace disjointness — party slug registry
 * (PR-0 of TODO/20260612-party-rendering-and-party-pages-plan.md,
 * 2026-06-12).
 *
 * Extends the disjointness contract to SIX registries:
 *   1. State slugs        — from `entities.json`
 *   2. Topic slugs        — from `topics.json`
 *   3. AC slugs           — from `electoral.csv`
 *   4. Indicator url_slug — from `indicators.json` (current + history)
 *   5. RESERVED           — `RESERVED_PATH_TOKENS` from `links.ts`
 *   6. Party slugs        — derived from `parties.csv` via `partyIdToSlug`
 *
 * Pairwise: party slugs are disjoint from each of the OTHER five
 * registries, AND internally unique across the parties.csv corpus.
 * Reading the real `datasets/data/entities/parties.csv` -- mirrors
 * the Phase 2 + PR-0 + Phase 3 corpus-walking pattern above.
 *
 * Mounted as a separate `describe` block so an ADR-0053 regression
 * surfaces independently of the five earlier registries.
 *
 * STOP-AND-SURFACE rule: if any of these go red with real collisions,
 * the resolution is ALWAYS to fix the party slug (rename the party_id
 * tail, OR add a sentinel override in `slug.ts`) — NEVER add an
 * exception to the test. Doctrine: slugs are part of the citizen
 * contract; collisions are slug-quality bugs.
 */
describe("ADR-0053 URL namespace disjointness — party slugs (6-way)", () => {
  const stateSlugs = loadActiveStateSlugs();
  const topicSlugs = loadTopicSlugs();
  const acSlugs = loadActiveAcSlugs();
  const indicatorSlugs = loadIndicatorUrlSlugs();
  const partySlugs = loadPartySlugs();

  it("loads ≥1000 party slugs (sanity)", () => {
    // parties.csv has 2259 rows at PR-0 landing time (2026-06-12);
    // floor catches "parties.csv failed to load at all" without
    // pinning a brittle exact count that future ingest will move.
    expect(partySlugs.length).toBeGreaterThanOrEqual(1000);
  });

  it("party slugs are internally unique", () => {
    // party_id is the PK of parties.csv; the slug derivation is
    // lossless (lowercased tail with `_` -> `-`); therefore the slug
    // set is unique by construction. A duplicate here means someone
    // hand-edited parties.csv and accidentally created a duplicate
    // party_id row — the FK-closure backend test catches the same
    // class of bug from the other side.
    expect(findDuplicates(partySlugs)).toEqual([]);
  });

  it("partySlugs ⊥ stateSlugs", () => {
    // A party named after a state ("Tamil Nadu People's Party") slugs
    // its party_id tail (e.g. `tnpp`), never the state slug; a real
    // collision here would mean the party_id was minted with the
    // state slug as its tail — a data-quality bug.
    const overlap = intersection(partySlugs, stateSlugs);
    expect(overlap).toEqual([]);
  });

  it("partySlugs ⊥ topicSlugs", () => {
    const overlap = intersection(partySlugs, topicSlugs);
    expect(overlap).toEqual([]);
  });

  it("partySlugs ⊥ acSlugs", () => {
    // STOP-AND-SURFACE: if a party slug collides with an AC name slug
    // (e.g. some state happened to mint an AC named "BJP"), the
    // resolution is to fix the AC name in `electoral.csv`, NOT the
    // party slug. Party slugs are anchored to the party_id PK and
    // citizen-visible everywhere; AC names are local to one state.
    const overlap = intersection(partySlugs, acSlugs);
    expect(overlap).toEqual([]);
  });

  it("partySlugs ⊥ indicatorSlugs", () => {
    // An indicator url_slug colliding with a party slug would only
    // ambiguate at `/<state>/<slug>` (state-scoped indicator) vs
    // `/parties/<slug>` (party page); the leading literal `parties`
    // disambiguates by route but a colliding slug literal would
    // still confuse citizen recall. Resolution: rename the indicator
    // url_slug (operator-side editorial change per the Phase 3
    // STOP-AND-SURFACE rule above).
    const overlap = intersection(partySlugs, indicatorSlugs);
    expect(overlap).toEqual([]);
  });

  it("partySlugs ⊥ RESERVED_PATH_TOKENS", () => {
    // RESERVED includes `parties` (the new top-level token reserved
    // by ADR-0053) and `t`, `compare`, etc. A party_id whose tail
    // slugs to any of these (e.g. a fictional `parties.IN.T`) would
    // generate `/parties/t` which masks no route per se (the literal
    // `parties` prefix disambiguates) but a citizen typing the bare
    // `t` slug would still hit the topic index. Belt + braces.
    const overlap = intersection(partySlugs, RESERVED_PATH_TOKENS);
    expect(overlap).toEqual([]);
  });
});
