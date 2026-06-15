// Contract: an indicator card MUST NOT link to, render copy for, or
// import the routing helpers of a foreign indicator family (elections,
// parties, governments). The per-card "View latest election for <state>"
// CTA was deleted in PR #946 (Hans + Jony convergence 2026-06-11),
// silently reverted by PR #948 worktree-staleness, partially restored
// by PR #949, and rip-reapplied by PR #1048. This test is the
// structural anti-regression guard: the next worktree-staleness
// accident, copy-paste, or persona-who-thinks-they-are-being-helpful
// will fail loud here on every `bun run test`, not just on the
// env-flaky e2e absence-guard at
// frontend/e2e/election-bridges-and-map-demote.spec.ts lines 62-92.
//
// Doctrinal anchor: docs/concepts/schema-is-the-design-system.md
// lines 9-15 ("yen-gov is not an elections site that happens to also
// show fiscal data... elections are one indicator family alongside"
// the others) and docs/concepts/citizen-first.md (every family is
// equally first-class). The convergence rationale lives in
// TODO/20260615-per-card-election-cta-rip-plan.md section 0.3
// (Citizen + Jony + Max, 2026-06-15).
//
// Why static source + import-graph instead of DOM mount:
// `@testing-library/svelte` is NOT a project dependency (vitest is
// node-env per the Skeleton + IndicatorJump precedent the sibling
// IndicatorCard.test.ts cites in its module header). The static
// source contract is strictly STRONGER than a DOM-render contract
// would be: it catches the regression at template-author time, not
// just at render time, and runs in <50 ms instead of waiting for
// DuckDB-WASM boot + catalogue fetch + Svelte hydration.

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const COMPONENT_PATH = resolve(__dirname, "IndicatorCard.svelte");
const SOURCE = readFileSync(COMPONENT_PATH, "utf8");

// Template section = everything after the LAST `</script>` tag. The
// component has two <script> blocks (module + instance); after the
// instance block closes, only template markup follows. This split
// lets the CTA-text + link-call checks ignore the post-mortem comment
// block at the top of the instance script that names the deleted
// phrase as documentation.
const TEMPLATE_START = SOURCE.lastIndexOf("</script>");
if (TEMPLATE_START < 0) {
  throw new Error(
    "IndicatorCard.svelte has no </script> tag - file shape changed? " +
      "This test assumes the standard two-<script>-block Svelte layout.",
  );
}
const TEMPLATE = SOURCE.slice(TEMPLATE_START);

// FORBIDDEN: link.* helpers that route to a foreign indicator family.
// The ONLY navigation chrome an IndicatorCard may carry is the
// "See all states ->" footer link, which targets `link.topic(topic.id)`.
const FORBIDDEN_LINK_CALLS = [
  "link.stateElection",
  "link.lab",
  "link.party",
  "link.parties",
  "link.constituency",
  "link.ac",
  "link.government",
] as const;

// FORBIDDEN: data-testids that historically marked foreign-family
// chrome. Add to this list when new foreign-family chrome is
// hypothetically considered + rejected — so the contract test
// documents the rejection in code, not just in commit history.
const FORBIDDEN_TESTIDS = [
  "indicator-card-latest-election",
  "indicator-card-go-to-election",
  "indicator-card-party-link",
  "indicator-card-government",
] as const;

// FORBIDDEN: ES imports from modules whose ONLY job is foreign-family
// routing or data fetching. Importing one of these into the card is
// a structural smell that the link-call check below catches anyway,
// but blocking the import is the cheapest fail-loud signal.
const FORBIDDEN_IMPORTS = [
  "./election-events",
  "./governments",
  "./parties/",
] as const;

// FORBIDDEN: human-readable phrases the deleted CTA carried. Belt-
// and-braces: if a future agent inlines the link without using the
// `link.stateElection(...)` helper (e.g. hardcoded
// `href="/<state>/elections/<event>"`), the link-call check above
// misses it. This text-level guard catches the citizen-visible
// artifact directly. Only matches inside the template section.
const FORBIDDEN_CTA_PHRASES = [
  "View latest election",
  "Latest election:",
  "Go to latest election",
  "See the latest election",
];

describe("IndicatorCard.svelte - no cross-family per-card chrome", () => {
  it("template does not invoke any foreign-family link.* helper", () => {
    const hits = FORBIDDEN_LINK_CALLS.filter(h => TEMPLATE.includes(h));
    expect(
      hits,
      `IndicatorCard template must not link to a foreign indicator family. ` +
        `Found: [${hits.join(", ")}]. The "See all states ->" footer ` +
        `link.topic(...) is the ONLY navigation chrome an indicator card ` +
        `may carry per docs/concepts/schema-is-the-design-system.md lines ` +
        `9-15. See TODO/20260615-per-card-election-cta-rip-plan.md section 0.3.`,
    ).toEqual([]);
  });

  it("anywhere-in-file does not render any foreign-family data-testid", () => {
    const hits = FORBIDDEN_TESTIDS.filter(t =>
      SOURCE.includes(`data-testid="${t}"`),
    );
    expect(
      hits,
      `IndicatorCard must not carry a foreign-family testid. ` +
        `Found: [${hits.join(", ")}].`,
    ).toEqual([]);
  });

  it("instance script does not import from any foreign-family module", () => {
    const hits = FORBIDDEN_IMPORTS.filter(spec => {
      const escaped = spec.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const re = new RegExp(`from\\s+["']${escaped}`);
      return re.test(SOURCE);
    });
    expect(
      hits,
      `IndicatorCard must not import from a foreign-family module. ` +
        `Found: [${hits.join(", ")}]. The card's data flow is the canonical ` +
        `loader + the catalogue + the indicator descriptor — nothing else.`,
    ).toEqual([]);
  });

  it("template does not render a foreign-family CTA phrase", () => {
    const hits = FORBIDDEN_CTA_PHRASES.filter(p => TEMPLATE.includes(p));
    expect(
      hits,
      `IndicatorCard template must not render a foreign-family CTA. ` +
        `Found: [${hits.join(", ")}]. The post-mortem comment block at the ` +
        `top of the instance script may name the deleted phrase as ` +
        `documentation — but the template must not.`,
    ).toEqual([]);
  });

  it("the contract test itself is wired to the right file", () => {
    // Sanity guard: if a refactor moves IndicatorCard.svelte (or
    // splits its template into a sibling file), this test must fail
    // loudly so the contract is re-pointed in the same PR rather
    // than silently passing on an empty SOURCE.
    expect(SOURCE.length).toBeGreaterThan(0);
    expect(TEMPLATE).toContain("data-testid=\"indicator-card\"");
    expect(TEMPLATE).toContain("data-testid=\"indicator-card-see-all\"");
  });
});
