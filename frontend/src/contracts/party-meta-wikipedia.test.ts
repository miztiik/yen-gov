/**
 * Row B of the party-page header polish - the Wikipedia link in the
 * Party.svelte header meta-strip.
 *
 * After Row A repaired the logo `src` (it now routes through the
 * base-aware `assetUrl` seam so the `/yen-gov/` deploy base is applied),
 * Row B drops the visible word "Wikipedia": the logo image alone with a
 * hover tooltip is enough chrome. The icon-only link stays
 * self-describing via `title` + `aria-label` (free affordances; a11y is a
 * project Non-Goal but these cost nothing).
 *
 * The project does NOT install `@testing-library/svelte`, so - exactly
 * like `party-avatar-shape.test.ts` and every other Tier-A contract test
 * under `frontend/src/contracts/` - the contract is enforced on the
 * source text of Party.svelte directly (the page template is also
 * covered by the e2e spec + the CLAUDE.md section 13 in-browser smoke).
 *
 * Regression guards (each a separate `it` so one failure names the exact
 * rollback that needs fixing):
 *   - the wiki anchor carries `title="Wikipedia"` + `aria-label="Wikipedia"`;
 *   - the anchor renders the seam-routed `wikipedia.svg` <img> with
 *     `title="Wikipedia"` + `alt="Wikipedia"` (Row A's src is unchanged);
 *   - the visible "Wikipedia" text node is gone (icon-only);
 *   - the new-tab affordance (target=_blank rel=noopener noreferrer) stays.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const PARTY_SVELTE = resolve(here, "..", "routes", "Party.svelte");

const SOURCE = readFileSync(PARTY_SVELTE, "utf-8");

// The full wiki anchor block, anchored on its data-testid so a
// regression elsewhere in the file does not poison these assertions.
// `[^>]*` spans the multi-line opening tag (no `>` until the tag closes),
// then `[\s\S]*?</a>` captures the inner markup lazily.
const ANCHOR_BLOCK = SOURCE.match(
  /<a[^>]*data-testid="party-meta-wikipedia"[^>]*>[\s\S]*?<\/a>/,
)?.[0];

describe("Party.svelte wiki meta-strip (Row B - icon-only)", () => {
  it("finds the party-meta-wikipedia anchor block", () => {
    expect(
      ANCHOR_BLOCK,
      'wiki anchor (the <a data-testid="party-meta-wikipedia">) not found in Party.svelte',
    ).toBeTruthy();
  });

  it("the wiki anchor carries title + aria-label tooltips (self-describing icon link)", () => {
    const block = ANCHOR_BLOCK as string;
    // The opening tag only (everything up to the first `>`).
    const openTag = block.match(
      /<a[^>]*data-testid="party-meta-wikipedia"[^>]*>/,
    )?.[0] as string;
    expect(openTag).toMatch(/aria-label="Wikipedia"/);
    expect(openTag).toMatch(/title="Wikipedia"/);
  });

  it("renders the seam-routed wikipedia.svg img with title + alt 'Wikipedia'", () => {
    const block = ANCHOR_BLOCK as string;
    const img = block.match(/<img[\s\S]*?\/>/)?.[0] as string;
    expect(img, "no <img> inside the wiki anchor").toBeTruthy();
    // Row A's base-aware seam src MUST be left untouched.
    expect(img).toMatch(/src=\{assetUrl\("\/brands\/wikipedia\.svg"\)\}/);
    expect(img).toMatch(/title="Wikipedia"/);
    expect(img).toMatch(/alt="Wikipedia"/);
  });

  it("drops the visible 'Wikipedia' word from the meta-strip (icon-only)", () => {
    const block = ANCHOR_BLOCK as string;
    // The removed text node specifically...
    expect(block).not.toMatch(/<span>\s*Wikipedia\s*<\/span>/);
    // ...and, more generally, NO bare "Wikipedia" text node between tags.
    // (`title="Wikipedia"` / `aria-label="Wikipedia"` are attributes - a
    // `"` precedes them, not a `>` - so they do not trip this guard.)
    expect(block).not.toMatch(/>\s*Wikipedia\s*</);
  });

  it("keeps the new-tab affordance (target=_blank rel=noopener noreferrer)", () => {
    const block = ANCHOR_BLOCK as string;
    expect(block).toMatch(/target="_blank"/);
    expect(block).toMatch(/rel="noopener noreferrer"/);
  });

  // Control: prove the "no visible word" guard is live - it WOULD catch a
  // re-introduced text node, and does NOT fire on the attribute form.
  it("the visible-word guard catches a planted text node, spares attributes", () => {
    const VISIBLE_TEXT_RE = /<span>\s*Wikipedia\s*<\/span>|>\s*Wikipedia\s*</;
    expect(VISIBLE_TEXT_RE.test("<span>Wikipedia</span>")).toBe(true);
    expect(VISIBLE_TEXT_RE.test(">Wikipedia<")).toBe(true);
    expect(VISIBLE_TEXT_RE.test('title="Wikipedia"')).toBe(false);
    expect(VISIBLE_TEXT_RE.test('aria-label="Wikipedia"')).toBe(false);
  });
});
