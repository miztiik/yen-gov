/**
 * Row C contract: the /parties/<slug> provenance footer refactor.
 *
 * Row C replaces the FIVE inline per-card `<SourceList>` mounts + the
 * standalone "About this page" link in Party.svelte with ONE
 * `<PartyProvenanceFooter>` page-foot block (which itself renders the
 * mapped provenance sentence AND the single About link).
 *
 * `@testing-library/svelte` is NOT installed, so - exactly like
 * `party-meta-wikipedia.test.ts` and every other contract test under
 * `frontend/src/contracts/` - this pins the refactor on the SOURCE
 * TEXT of the components (the rendered page is covered by the e2e
 * specs + the CLAUDE.md section 13 in-browser smoke).
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const PARTY_SVELTE = resolve(here, "..", "routes", "Party.svelte");
const SOURCE = readFileSync(PARTY_SVELTE, "utf-8");

const FOOTER_SVELTE = resolve(
  here,
  "..",
  "lib",
  "parties",
  "PartyProvenanceFooter.svelte",
);
const FOOTER_SOURCE = readFileSync(FOOTER_SVELTE, "utf-8");

describe("Party.svelte provenance footer (Row C)", () => {
  it("has ZERO inline <SourceList> mounts (the 5 per-card pill rows retired)", () => {
    expect(SOURCE).not.toMatch(/<SourceList\b/);
  });

  it("no longer imports SourceList (no dangling import)", () => {
    expect(SOURCE).not.toMatch(/import\s*\{\s*SourceList\s*\}/);
  });

  it("mounts <PartyProvenanceFooter> exactly once", () => {
    const matches = SOURCE.match(/<PartyProvenanceFooter\b/g) ?? [];
    expect(matches).toHaveLength(1);
  });

  it("passes the party VM provenance envelope to the footer", () => {
    expect(SOURCE).toMatch(
      /<PartyProvenanceFooter[^>]*provenance=\{view_model\.provenance\}/,
    );
  });

  it("imports PartyProvenanceFooter from lib/parties", () => {
    expect(SOURCE).toMatch(
      /import\s+PartyProvenanceFooter\s+from\s+"\.\.\/lib\/parties\/PartyProvenanceFooter\.svelte"/,
    );
  });

  it("keeps no standalone 'About this page' link element in Party.svelte (it moved into the footer)", () => {
    // Key on the link's testid (a comment may still mention the words
    // "About this page"; only the actual <a> element is forbidden here).
    expect(SOURCE).not.toMatch(/data-testid="party-page-coverage-link"/);
  });
});

describe("PartyProvenanceFooter.svelte (Row C - the one foot block)", () => {
  it("owns the single About-this-page link (page-coverage affordance)", () => {
    expect(FOOTER_SOURCE).toMatch(/data-testid="party-page-coverage-link"/);
    expect(FOOTER_SOURCE).toMatch(/About this page/);
  });

  it("renders publisher pills with the SourceList link/plain mirror (Holy Law #9 - every name clickable)", () => {
    // Link branch: url present -> <a target=_blank rel=noopener>.
    expect(FOOTER_SOURCE).toMatch(/href=\{pill\.url\}/);
    expect(FOOTER_SOURCE).toMatch(/target="_blank"/);
    expect(FOOTER_SOURCE).toMatch(/rel="noopener noreferrer"/);
    // Plain branch: url-less pill renders a span (no fabricated link).
    expect(FOOTER_SOURCE).toMatch(/\{:else\}<span class="text-slate-700">/);
  });

  it("drives its clauses from the pure footer model (no inline grouping)", () => {
    expect(FOOTER_SOURCE).toMatch(
      /import\s*\{\s*buildProvenanceFooterClauses\s*\}\s*from\s*"\.\/party-provenance-footer-model"/,
    );
  });
});
