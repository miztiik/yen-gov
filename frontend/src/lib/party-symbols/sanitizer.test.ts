// PR-SYM-3 sanitizer contract test. Two surfaces:
//   1. Walks every SVG actually committed under
//      `frontend/public/party-symbols/` and asserts they all pass the
//      sanitizer. The placeholder is the only file in this PR; PR-SYM-4a
//      adds the first ~40 party SVGs and this walk grows automatically.
//   2. Asserts the sanitizer rejects each class of malicious SVG that the
//      shared icon allowlist forbids (script, event handler, foreignObject,
//      external href, embedded raster, inline style, <use>, ...).
//
// Runs in vitest (node). Imports `node:crypto` via the sanitizer.

import { describe, expect, test } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  PartySymbolSanitizerError,
  sanitizeAndHash,
} from "./sanitizer";

const PUBLIC_PARTY_SYMBOLS_DIR = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
  "public",
  "party-symbols",
);

function listSvgFiles(dir: string): string[] {
  try {
    return readdirSync(dir)
      .filter((name) => name.endsWith(".svg"))
      .map((name) => join(dir, name))
      .filter((path) => statSync(path).isFile());
  } catch {
    return [];
  }
}

describe("party-symbol sanitizer - real assets under frontend/public/party-symbols", () => {
  const files = listSvgFiles(PUBLIC_PARTY_SYMBOLS_DIR);

  test("placeholder.svg exists and passes the sanitizer", () => {
    const placeholder = files.find((p) => p.endsWith("placeholder.svg"));
    expect(placeholder, `expected placeholder.svg under ${PUBLIC_PARTY_SYMBOLS_DIR}`).toBeDefined();
    const bytes = readFileSync(placeholder!, "utf8");
    const result = sanitizeAndHash(bytes, "placeholder.svg");
    expect(result.sha256).toMatch(/^[a-f0-9]{64}$/);
    expect(result.sanitizedBytes).toBe(bytes);
  });

  test("every shipped SVG passes the sanitizer (none, ever, smuggled past review)", () => {
    expect(files.length).toBeGreaterThan(0);
    for (const path of files) {
      const bytes = readFileSync(path, "utf8");
      expect(() => sanitizeAndHash(bytes, path), `sanitizer rejected ${path}`).not.toThrow();
    }
  });

  test("filenames are kebab-case + lowercase .svg", () => {
    const ICON_FILENAME_REGEX = /^[a-z0-9]+(-[a-z0-9]+)*\.svg$/;
    for (const path of files) {
      const basename = path.split(/[\\/]/).pop()!;
      expect(basename, `${basename} must be kebab-case lower-snake `).toMatch(ICON_FILENAME_REGEX);
    }
  });
});

describe("party-symbol sanitizer - malicious / forbidden constructs are rejected", () => {
  const reject = (label: string, body: string) =>
    test(`rejects ${label}`, () => {
      const svg = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
      expect(() => sanitizeAndHash(svg, `inline-${label}.svg`)).toThrow(PartySymbolSanitizerError);
    });

  reject("script-element", `<script>alert(1)</script>`);
  reject("foreignObject", `<foreignObject><div></div></foreignObject>`);
  reject("use-href", `<use href="#x" />`);
  reject("image-element", `<image x="0" y="0" width="24" height="24" />`);
  reject("iframe-element", `<iframe></iframe>`);
  reject("embed-element", `<embed />`);
  reject("animate-element", `<animate attributeName="x" />`);
  reject("anchor-href", `<a href="https://evil.example"><circle cx="12" cy="12" r="6" /></a>`);
  reject("style-element", `<style>circle { fill: red; }</style>`);
  reject("inline-style-attr", `<circle cx="12" cy="12" r="6" style="fill: red" />`);
  reject("onclick-attr", `<circle cx="12" cy="12" r="6" onclick="alert(1)" />`);
  reject("onload-attr", `<circle cx="12" cy="12" r="6" onload="alert(1)" />`);
  reject("xlink-href-attr", `<circle cx="12" cy="12" r="6" xlink:href="#x" />`);
});

describe("party-symbol sanitizer - hash stability", () => {
  test("sha256 is stable across calls on the same bytes", () => {
    const svg = `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="6" /></svg>`;
    const a = sanitizeAndHash(svg, "stable.svg");
    const b = sanitizeAndHash(svg, "stable.svg");
    expect(a.sha256).toBe(b.sha256);
    expect(a.sha256).toMatch(/^[a-f0-9]{64}$/);
  });

  test("sha256 changes when a single byte changes", () => {
    const svgA = `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="6" /></svg>`;
    const svgB = `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7" /></svg>`;
    const a = sanitizeAndHash(svgA, "a.svg");
    const b = sanitizeAndHash(svgB, "b.svg");
    expect(a.sha256).not.toBe(b.sha256);
  });
});
