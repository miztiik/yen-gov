/**
 * Design-token drift contract (plan section 21.7 + 23.5).
 *
 * The CSS custom properties declared on :root in
 * frontend/src/app-tokens.css are the runtime truth for colour, type,
 * radius, elevation, and motion. The Tailwind theme.extend in
 * frontend/tailwind.config.js MIRRORS them via var(--token) so utility
 * classes and direct CSS stay aligned. This test locks that alignment
 * so a future edit can't silently drift one side.
 *
 * Asserts:
 *   - the core token set is declared in app-tokens.css
 *   - every var(--...) reference in tailwind.config.js theme.extend
 *     resolves to a --var that exists in app-tokens.css
 *   - every non-exempt --var declared in app-tokens.css has at least
 *     one Tailwind theme.extend mirror referencing it
 *
 * Per /memories/lessons.md ("vitest does NOT resolve the $lib
 * SvelteKit alias by default"), this file uses relative imports only.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
);
const tokensPath = resolve(frontendRoot, "src", "app-tokens.css");
const tailwindPath = resolve(frontendRoot, "tailwind.config.js");

// `--name: value;` on its own line. Anchored to a leading-whitespace
// boundary so `var(--name)` inside a value never registers as a
// declaration.
const VAR_DECL_RE = /^\s+(--[a-z][a-z0-9-]*)\s*:/gim;
const VAR_REF_RE = /var\(\s*(--[a-z][a-z0-9-]*)\s*\)/g;

function collectMatches(source: string, regex: RegExp): Set<string> {
  const out = new Set<string>();
  // Reset the regex's lastIndex so calling twice with the same instance
  // does not silently miss matches.
  regex.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(source)) !== null) {
    out.add(m[1]);
  }
  return out;
}

describe("yen-gov design tokens - drift contract", () => {
  const tokensSrc = readFileSync(tokensPath, "utf-8");
  const tailwindSrc = readFileSync(tailwindPath, "utf-8");

  const declaredVars = collectMatches(tokensSrc, VAR_DECL_RE);
  const referencedVars = collectMatches(tailwindSrc, VAR_REF_RE);

  it("declares the core token set in app-tokens.css", () => {
    const requiredCore = [
      // Colour
      "--ink",
      "--ink-muted",
      "--line",
      "--surface",
      "--surface-sunken",
      "--accent",
      "--pos",
      "--caution",
      "--neg",
      // Brand (U2c - LeftRail wordmark + flag-derived motifs)
      "--brand-saffron",
      "--brand-green",
      "--brand-chakra",
      // Glass surface (U2c - mobile app bar)
      "--app-bar-bg",
      // Type
      "--font-sans",
      "--font-display",
      "--font-deva",
      "--font-feature-tabular",
      "--text-xs",
      "--text-sm",
      "--text-base",
      "--text-lg",
      "--text-xl",
      "--text-2xl",
      "--text-3xl",
      "--text-4xl",
      // Radius
      "--r-sm",
      "--r-md",
      "--r-lg",
      "--r-pill",
      // Elevation
      "--e1",
      "--e2",
      "--e3",
      // Motion
      "--dur-fast",
      "--dur",
      "--dur-slow",
      "--ease-out",
      "--ease-spring",
    ];
    for (const name of requiredCore) {
      expect(
        declaredVars,
        `missing required token '${name}' in app-tokens.css`,
      ).toContain(name);
    }
  });

  it("every Tailwind theme.extend var(--...) reference points at a declared --var", () => {
    const dangling: string[] = [];
    for (const ref of referencedVars) {
      if (!declaredVars.has(ref)) dangling.push(ref);
    }
    expect(
      dangling,
      `tailwind.config.js references undeclared CSS variables: ${dangling.join(", ")}`,
    ).toEqual([]);
  });

  it("every non-exempt --var has at least one Tailwind theme.extend mirror", () => {
    // Type-scale and font-feature tokens do NOT need a Tailwind utility
    // mirror: Tailwind's stock text-xs/-sm/-base/-lg/-xl/-2xl/-3xl/-4xl
    // ladder already matches our 1.2 minor-third scale at base 16px
    // one-for-one, and font-feature-tabular is applied directly in CSS
    // (font-feature-settings declaration), not via a utility class.
    //
    // --dur (the default 200ms) is also exempt by design: Tailwind's
    // stock duration-DEFAULT is 150ms and overriding it would shift
    // every transition globally - the additive rule (plan section 23.5)
    // forbids that. The default duration is applied directly in CSS via
    // `transition-duration: var(--dur)` where components opt in.
    const exemptFromMirror = new Set([
      "--text-xs",
      "--text-sm",
      "--text-base",
      "--text-lg",
      "--text-xl",
      "--text-2xl",
      "--text-3xl",
      "--text-4xl",
      "--font-feature-tabular",
      "--dur",
      // Directional ramp hues hold bare hue-degree numbers consumed at
      // runtime by rampHue() in colors/palettes.ts, NOT via a Tailwind
      // utility - same rationale as --font-feature-tabular / --dur above.
      "--ramp-positive",
      "--ramp-negative",
      "--ramp-neutral",
    ]);
    const unmirrored: string[] = [];
    for (const decl of declaredVars) {
      if (exemptFromMirror.has(decl)) continue;
      if (!referencedVars.has(decl)) unmirrored.push(decl);
    }
    expect(
      unmirrored,
      `app-tokens.css declares vars without a Tailwind mirror: ${unmirrored.join(", ")}`,
    ).toEqual([]);
  });
});
