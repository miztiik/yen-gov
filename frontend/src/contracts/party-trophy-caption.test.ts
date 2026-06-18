/**
 * Row D of the party-page polish plan - the two chart captions in
 * Party.svelte read "best: N seats in YYYY", a lower-case word that
 * clashes with the page's "peak" vocabulary and names no metric. Row D
 * drops the word "best:" and prefixes a registry TROPHY glyph (the same
 * Lucide trophy the MarginHistogram winner badge ships) before the
 * figure, so the figure names its own celebration metric.
 *
 * The project does NOT install `@testing-library/svelte`, so - exactly
 * like `party-meta-wikipedia.test.ts` and every other Tier-A contract
 * test under `frontend/src/contracts/` - the contract is enforced on the
 * source text of Party.svelte directly (the rendered page is also covered
 * by the e2e spec + the CLAUDE.md section 13 in-browser smoke).
 *
 * Regression guards (each a separate `it` so one failure names the exact
 * caption that regressed):
 *   - the Parliament (LS) caption renders <TopicIcon name="trophy" .../>
 *     + the `{ls_peak} seats in {ls_peak_year}` figure, and no "best:";
 *   - the State-Assembly (VS) caption renders <TopicIcon name="trophy" .../>
 *     + the `{vs_peak} seats in {vs_peak_year}` figure, and no "best:";
 *   - the trophy.svg glyph the captions reference exists in the registry.
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const PARTY_SVELTE = resolve(here, "..", "routes", "Party.svelte");
const TROPHY_SVG = resolve(here, "..", "..", "public", "icons", "trophy.svg");

const SOURCE = readFileSync(PARTY_SVELTE, "utf-8");

// Each caption is the `<span class="text-xs ...">` guarded by its
// `{#if <peak> > 0}`. NOTE there is an EARLIER `{#if ls_peak > 0}` on the
// party subline ("peak N Parliament seats in YYYY"), so we anchor on the
// caption's `text-xs` span class - not the bare `{#if}` - to target the
// chart caption and not the subline. The TopicIcon is self-closing, so
// the lazy `[\s\S]*?</span>` stops at the caption span's own close tag.
const LS_CAPTION = SOURCE.match(
  /\{#if ls_peak > 0\}\s*<span class="text-xs[\s\S]*?<\/span>/,
)?.[0];
const VS_CAPTION = SOURCE.match(
  /\{#if vs_peak > 0\}\s*<span class="text-xs[\s\S]*?<\/span>/,
)?.[0];

describe("Party.svelte chart captions (Row D - trophy glyph, no 'best:')", () => {
  it("finds both peak-seats caption blocks", () => {
    expect(LS_CAPTION, "Parliament (ls_peak) caption block not found").toBeTruthy();
    expect(VS_CAPTION, "State-Assembly (vs_peak) caption block not found").toBeTruthy();
  });

  it("the Parliament caption renders the trophy glyph before the figure, dropping 'best:'", () => {
    const block = LS_CAPTION as string;
    expect(block).toMatch(/<TopicIcon[\s\S]*?name="trophy"[\s\S]*?\/>/);
    expect(block).toMatch(/\{ls_peak\} seats in \{ls_peak_year\}/);
    expect(block).not.toMatch(/best:/);
  });

  it("the State-Assembly caption renders the trophy glyph before the figure, dropping 'best:'", () => {
    const block = VS_CAPTION as string;
    expect(block).toMatch(/<TopicIcon[\s\S]*?name="trophy"[\s\S]*?\/>/);
    expect(block).toMatch(/\{vs_peak\} seats in \{vs_peak_year\}/);
    expect(block).not.toMatch(/best:/);
  });

  it("the trophy glyph the captions reference exists in the icon registry directory", () => {
    expect(
      existsSync(TROPHY_SVG),
      "frontend/public/icons/trophy.svg must exist for the registry to tint it via currentColor",
    ).toBe(true);
    const svg = readFileSync(TROPHY_SVG, "utf-8");
    expect(svg).toMatch(/viewBox="0 0 24 24"/);
    expect(svg).toMatch(/<path /);
  });
});
