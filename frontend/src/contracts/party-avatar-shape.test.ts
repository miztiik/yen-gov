/**
 * PR-4 of TODO/20260614-party-page-reimagination-plan.md - the
 * citizen-facing party-page avatar treatment.
 *
 * Asserts the Party.svelte avatar block ships Jony J4's verbatim
 * geometry: a circle (NOT a square), with a brand-colour ring + the
 * party's election-symbol image when available, or the short token
 * otherwise, or a sentinel slate-200 token when `is_sentinel` is
 * true. The project does NOT install `@testing-library/svelte` so the
 * contract is enforced on the source text of Party.svelte directly -
 * the same precedent used by every other Tier-A contract test in
 * `frontend/src/contracts/` (parties-symbol-asset.test.ts,
 * methodology-tooltip-no-leaks.test.ts, ...).
 *
 * Regression guards (each is a separate `it` so a single failure
 * names the exact rollback that needs fixing):
 *   - the avatar div is `rounded-full` (NOT `rounded-md`);
 *   - the helper's `AvatarKind` is the new 3-value union
 *     (`"symbol" | "token" | "sentinel"`), not the 4-value
 *     anchor/brand/fallback/sentinel taxonomy;
 *   - the markup renders a child `<img>` for `kind === "symbol"`;
 *   - the old swatch corner-dot affordance is gone;
 *   - the sentinel fill is slate-200 (`#e2e8f0`) and the sentinel ink
 *     is slate-600 (`#475569`).
 *
 * This test complements `frontend/src/routes/Party.test.ts`, which
 * pins the helper's return shape. This test pins the markup that
 * consumes the helper - the two together fence in both ends of the
 * Party.svelte avatar contract.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const PARTY_SVELTE = resolve(here, "..", "routes", "Party.svelte");

const SOURCE = readFileSync(PARTY_SVELTE, "utf-8");

describe("Party.svelte avatar shape (PR-4 Jony J4)", () => {
  it("declares the new 3-value AvatarKind union (symbol|token|sentinel)", () => {
    expect(SOURCE).toMatch(
      /export type AvatarKind\s*=\s*"symbol"\s*\|\s*"token"\s*\|\s*"sentinel"/,
    );
    // The old 4-value union MUST be gone (no string token of it
    // anywhere in the file).
    expect(SOURCE).not.toMatch(/"anchor"\s*\|\s*"brand"\s*\|\s*"fallback"/);
  });

  it("avatar div is a circle (rounded-full), not a square (rounded-md)", () => {
    // Pull out the single avatar block (between the open-tag and the
    // matching </div>). We anchor on data-testid="party-avatar" so a
    // regression elsewhere in the file does not poison this assertion.
    const blockMatch = SOURCE.match(
      /<div[^>]*data-testid="party-avatar"[^>]*>[\s\S]*?<\/div>/,
    );
    expect(
      blockMatch,
      'avatar block (the <div data-testid="party-avatar">) not found in Party.svelte',
    ).not.toBeNull();
    const block = blockMatch![0];
    expect(block).toMatch(/rounded-full/);
    expect(block).not.toMatch(/rounded-md/);
    // 80px geometry per Jony J4: `h-20 w-20`.
    expect(block).toMatch(/h-20\b/);
    expect(block).toMatch(/w-20\b/);
  });

  it("avatar block renders <img> when kind=symbol, with a 48x48 sized image", () => {
    // The `{#if avatar.kind === "symbol" ...}` branch + the <img>
    // bound to `avatar.symbol_url`.
    expect(SOURCE).toMatch(/\{#if\s+avatar\.kind\s*===\s*"symbol"/);
    expect(SOURCE).toMatch(/<img[\s\S]*?src=\{avatar\.symbol_url\}/);
    expect(SOURCE).toMatch(/<img[\s\S]*?width="48"/);
    expect(SOURCE).toMatch(/<img[\s\S]*?height="48"/);
  });

  it("removes the old swatch corner-dot affordance", () => {
    // The pre-PR-4 markup carried `{#if avatar.swatch}` with a
    // `-bottom-1 -right-1` corner-pip. Both must be gone.
    expect(SOURCE).not.toMatch(/avatar\.swatch/);
    expect(SOURCE).not.toMatch(/-bottom-1 -right-1/);
  });

  it("sentinel treatment uses slate-200 fill and slate-600 ink", () => {
    // The sentinel branch of getAvatarStyle returns the canonical
    // sentinel hexes. We assert both literals appear in the file
    // (regression guard if a future edit drifts the sentinel
    // palette without authoring an explicit contract update).
    expect(SOURCE).toMatch(/"#e2e8f0"/); // slate-200 fill
    expect(SOURCE).toMatch(/"#475569"/); // slate-600 ink
    // The pre-PR-4 sentinel hexes MUST be gone (slate-300 #cbd5e1 +
    // slate-700 #334155 were Jony's prior shade pairing; the new
    // pairing is the citizen-facing one shipped here).
    expect(SOURCE).not.toMatch(/"#cbd5e1"/);
    expect(SOURCE).not.toMatch(/"#334155"/);
  });

  it("helper signature takes symbol_asset as the 4th argument", () => {
    // `getAvatarStyle(party_id, row, is_sentinel, symbol_asset)`.
    // We assert the parameter list ends with `symbol_asset: string |
    // null` so a future caller passing the wrong arity fails type-
    // check rather than silently dropping the symbol.
    expect(SOURCE).toMatch(/symbol_asset:\s*string\s*\|\s*null/);
    // Call-site passes meta.symbol_asset (4th positional arg).
    expect(SOURCE).toMatch(/meta\.symbol_asset/);
  });
});
