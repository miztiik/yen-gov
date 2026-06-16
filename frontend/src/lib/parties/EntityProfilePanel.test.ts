// Source-string pin test for EntityProfilePanel.svelte. Per project
// doctrine (`@testing-library/svelte` is NOT installed - see
// `frontend/src/lib/parties/PartyAboutCard.test.ts` head comment),
// component render paths are exercised via §13 browser smoke; this
// test pins the structural invariants of the .svelte source so the
// citizen-visible affordances (test-id seams, conditional banner /
// provenance sections, empty-state guard) can't silently regress.
import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC = readFileSync(
  resolve(__dirname, "./EntityProfilePanel.svelte"),
  "utf8",
);

describe("EntityProfilePanel.svelte source-string pins", () => {
  test("declares the required Props interface", () => {
    expect(SRC).toContain("interface Props");
    expect(SRC).toContain("title: string");
    expect(SRC).toContain("rows: readonly ProfileRow[]");
    expect(SRC).toContain("provenance?: string");
    expect(SRC).toContain("amber_banner?: string");
    expect(SRC).toContain("entity_kind?: string");
  });

  test("exports the ProfileRow shape", () => {
    expect(SRC).toContain("export interface ProfileRow");
    expect(SRC).toContain("readonly label: string");
    expect(SRC).toContain("readonly value: string");
    expect(SRC).toContain("readonly hint?: string");
  });

  test("guards render on non-empty rows so a default mount is a no-op", () => {
    // The whole DOM tree is wrapped in `{#if rows.length > 0}` so the
    // caller can mount it unconditionally on a route and let the
    // component decide whether to render.
    expect(SRC).toMatch(/\{#if rows\.length > 0\}/);
  });

  test("carries the entity-profile-panel data-testid for §13 + e2e", () => {
    expect(SRC).toContain('data-testid="entity-profile-panel"');
  });

  test("renders the rows under a citizen-readable definition list", () => {
    // A <dl> with one <dt>/<dd> per row gives screen-readers the
    // semantic shape; the e2e + browser-smoke loops can find row
    // labels via the dt element.
    expect(SRC).toMatch(/<dl[\s\S]+?\{#each rows as r[\s\S]+?<\/dl>/);
    expect(SRC).toContain("<dt");
    expect(SRC).toContain("<dd");
  });

  test("amber-banner section is conditional and carries its testid", () => {
    expect(SRC).toMatch(/\{#if amber_banner\}/);
    expect(SRC).toContain('data-testid="entity-profile-panel-amber"');
  });

  test("provenance footer is conditional and carries its testid", () => {
    expect(SRC).toMatch(/\{#if provenance\}/);
    expect(SRC).toContain('data-testid="entity-profile-panel-provenance"');
  });

  test("emits entity_kind on the root as a data-attr for QA tooling", () => {
    expect(SRC).toContain('data-entity-kind={entity_kind ?? ""}');
  });
});
