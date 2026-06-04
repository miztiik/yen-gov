// Devanagari conjunct render smoke (plan section 22.6 `devanagari` gate +
// section 23.5; sub-row U1.3 of TODO/20260604-u1-tokens-fonts-subplan.md).
//
// What this asserts
// -----------------
// The self-hosted Noto Sans Devanagari subset (frontend/public/fonts/
// noto-sans-devanagari.woff2, produced by tools/build_fonts.py with
// `fonttools subset --layout-features='*'`) retains its GSUB shaping
// tables, so the browser collapses the 3-codepoint cluster
//   KA (U+0915) + VIRAMA (U+094D) + SSA (U+0937)
// into ONE ligature glyph ("kSha", written क्ष) instead of laying out
// three atomic glyphs side by side.
//
// Why the conjunct
// ----------------
// kSha is the canonical pass/fail test case for Devanagari shaping. If
// the @font-face's underlying woff2 was subset with codepoint-only
// pruning (a common mistake when copy-pasting an Inter subset recipe),
// GSUB lookups go away silently and the conjunct breaks into three
// glyphs with a visible virama between them. The page still "renders"
// and "looks Hindi" to a Latin-only reviewer, but a Devanagari reader
// sees a layout bug. A unit test on the woff2 file's GSUB lookup count
// would catch one half of this; only an in-browser shaping test catches
// the other half (the @font-face declaration, unicode-range, and the
// browser's font-fallback walk are all in scope here).
//
// How we measure shaping
// ----------------------
// Two hidden spans, identical font-family, identical font-size:
//   A. innerText = KA + VIRAMA + SSA (3 codepoints, conjunct trigger)
//   B. innerText = KA + SSA          (2 codepoints, no virama, never a
//                                     ligature - just two atomic glyphs)
// If GSUB shaping fires on A, the browser substitutes the 3-codepoint
// run with a single combined-form glyph that is visibly NARROWER than
// the 2-codepoint baseline B (the kSha ligature is denser than KA+SSA
// rendered as atomic glyphs). If shaping is broken, A renders as 3
// atomic glyphs and is WIDER than B.
//
// So the invariant is:
//   width(A) < width(B)
// which can only be true if the GSUB shaping tables are present and the
// browser is using them.
//
// Per CLAUDE.md section 13 this is the in-browser smoke for U1.3. It
// runs against `vite dev` (the playwright webServer in
// frontend/playwright.config.ts) so the live @font-face + woff2 +
// serveDatasets() wiring is what the citizen would hit.
//
// Per CLAUDE.md project-level non-goal in section 0, accessibility is
// out of scope and is not asserted here.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("Devanagari shaping smoke", () => {
  test("KA + VIRAMA + SSA renders as one conjunct ligature, narrower than KA + SSA", async ({ page }) => {
    await page.goto("/");

    // Wait for the page shell to mount so Inter (preloaded) is in the
    // FontFaceSet. We do NOT need to wait for Noto Sans Devanagari to
    // download upfront - browsers fetch a unicode-range-scoped font on
    // demand the first time a matched codepoint enters the layout tree.
    // The page.evaluate below triggers that fetch by inserting Hindi
    // text into the DOM, and then awaits document.fonts.ready so the
    // measurement happens after the woff2 swap.
    await expect(page.getByRole("heading", { name: "yen-gov", level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    const measurement = await page.evaluate(async () => {
      // Build a hidden container off-screen so the measurement does not
      // disturb the live layout. position:fixed + top:-9999px keeps the
      // probe out of the viewport without setting visibility:hidden,
      // which can cause the browser to skip shaping entirely on some
      // engines.
      const probe = document.createElement("div");
      probe.style.position = "fixed";
      probe.style.left = "-9999px";
      probe.style.top = "-9999px";
      probe.style.fontFamily = '"Noto Sans Devanagari", serif';
      probe.style.fontSize = "48px";
      probe.style.lineHeight = "1";
      probe.style.whiteSpace = "nowrap";

      const conjunct = document.createElement("span");
      conjunct.id = "yg-deva-conjunct";
      // \u0915 KA + \u094D VIRAMA + \u0937 SSA  ->  "kSha" ligature
      conjunct.textContent = "\u0915\u094D\u0937";

      const pair = document.createElement("span");
      pair.id = "yg-deva-pair";
      // \u0915 KA + \u0937 SSA  ->  always two atomic glyphs
      pair.textContent = "\u0915\u0937";

      probe.appendChild(conjunct);
      probe.appendChild(document.createElement("br"));
      probe.appendChild(pair);
      document.body.appendChild(probe);

      // Force the Devanagari woff2 to be fetched and swapped in. The
      // first call kicks off the unicode-range fetch; document.fonts
      // .ready resolves once every pending FontFace in the set has
      // settled (loaded or errored).
      await document.fonts.ready;
      // A second microtask hop lets the swap-in repaint propagate
      // before getBoundingClientRect reads the post-swap geometry.
      await new Promise((r) => requestAnimationFrame(() => r(null)));

      const widthConjunct = conjunct.getBoundingClientRect().width;
      const widthPair = pair.getBoundingClientRect().width;

      // Resolve the actual font that ended up shaping the spans. If the
      // Noto subset failed to load (404, MIME, or @font-face typo) the
      // browser falls back to the next family in the stack (serif). The
      // ratio test below would still pass on some serif fonts, so we
      // also assert that the font that actually rendered is the one we
      // shipped.
      const fontConjunct = window.getComputedStyle(conjunct).fontFamily;

      probe.remove();
      return { widthConjunct, widthPair, fontConjunct };
    });

    // Width sanity: both spans must have actually rendered. A zero
    // width means the font never resolved a glyph for these
    // codepoints (e.g. the woff2 was completely empty).
    expect(measurement.widthConjunct, "conjunct span has zero width - font did not render").toBeGreaterThan(0);
    expect(measurement.widthPair, "pair span has zero width - font did not render").toBeGreaterThan(0);

    // The font-family declaration must include Noto Sans Devanagari so
    // we know shaping ran against the shipped subset and not the
    // browser's serif fallback. computedStyle returns the full stack
    // verbatim with quoting normalised; we just substring-match.
    expect(
      measurement.fontConjunct,
      `conjunct font-family resolves to '${measurement.fontConjunct}' - Noto Sans Devanagari fell out of the stack`,
    ).toMatch(/Noto Sans Devanagari/);

    // The load-bearing assertion. If GSUB shaping is active, the
    // 3-codepoint conjunct collapses into one ligature glyph that is
    // narrower than two atomic glyphs. A codepoint-only subset would
    // render three atomic glyphs and produce widthConjunct > widthPair.
    expect(
      measurement.widthConjunct,
      `conjunct width (${measurement.widthConjunct}) >= KA+SSA pair width (${measurement.widthPair}) - GSUB shaping appears broken in noto-sans-devanagari.woff2`,
    ).toBeLessThan(measurement.widthPair);
  });
});
