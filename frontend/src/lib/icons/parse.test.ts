// Vitest for the strict-allowlist parser. Every test reads a fixture from
// __fixtures__/ — these are the same files a contributor would commit,
// shaped so each one isolates exactly one rejection rule. This makes
// "what does the parser actually defend against?" answerable by listing
// the fixture files.

import { describe, expect, test } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseIcon, IconParseError } from "./parse";
import { ALLOWED_ELEMENTS, ALLOWED_ATTRS } from "./allowlist";

const FIXTURES = resolve(fileURLToPath(new URL(".", import.meta.url)), "__fixtures__");
const readFix = (name: string) => readFileSync(resolve(FIXTURES, name), "utf8");

describe("icon allowlist parser — accepts valid SVG", () => {
  test("valid-simple.svg: root + path + circle is accepted", () => {
    const icon = parseIcon(readFix("valid-simple.svg"), "valid-simple.svg", "valid-simple");
    expect(icon.name).toBe("valid-simple");
    expect(icon.viewBox).toBe("0 0 24 24");
    expect(icon.children).toHaveLength(2);
    expect(icon.children[0].name).toBe("path");
    expect(icon.children[1].name).toBe("circle");
    expect(icon.children[1].attrs.cx).toBe("12");
  });

  test("valid-nested.svg: comments + groups + self-closing primitives", () => {
    const icon = parseIcon(readFix("valid-nested.svg"), "valid-nested.svg", "valid-nested");
    expect(icon.children).toHaveLength(2);
    const g = icon.children[0];
    expect(g.name).toBe("g");
    expect(g.attrs.transform).toBe("translate(0,0)");
    expect(g.children).toHaveLength(2);
    expect(g.children[0].name).toBe("path");
    expect(g.children[1].name).toBe("line");
    expect(icon.children[1].name).toBe("circle");
  });
});

describe("icon allowlist parser — rejects forbidden elements", () => {
  test("invalid-script.svg: <script> is rejected with file:line:col", () => {
    expect(() => parseIcon(readFix("invalid-script.svg"), "invalid-script.svg", "invalid-script")).toThrow(IconParseError);
    try {
      parseIcon(readFix("invalid-script.svg"), "invalid-script.svg", "invalid-script");
    } catch (e) {
      expect(e).toBeInstanceOf(IconParseError);
      const err = e as IconParseError;
      expect(err.file).toBe("invalid-script.svg");
      expect(err.reason).toContain("forbidden element <script>");
      expect(err.message).toMatch(/invalid-script\.svg:\d+:\d+/);
    }
  });

  test("invalid-foreignobject.svg: <foreignObject> is rejected (HTML island vector)", () => {
    expect(() => parseIcon(readFix("invalid-foreignobject.svg"), "invalid-foreignobject.svg", "x")).toThrow(/forbidden element <foreignObject>/);
  });

  test("invalid-xlink.svg: <use> is rejected (would let xlink:href load remote sprites)", () => {
    expect(() => parseIcon(readFix("invalid-xlink.svg"), "invalid-xlink.svg", "x")).toThrow(/forbidden element <use>/);
  });
});

describe("icon allowlist parser — rejects forbidden attributes", () => {
  test("invalid-onload.svg: onload=… is rejected by FORBIDDEN_ATTR_PATTERNS", () => {
    expect(() => parseIcon(readFix("invalid-onload.svg"), "invalid-onload.svg", "x")).toThrow(/forbidden attribute 'onload'/);
  });

  test("invalid-style.svg: style=… is rejected (legacy expression vector)", () => {
    expect(() => parseIcon(readFix("invalid-style.svg"), "invalid-style.svg", "x")).toThrow(/forbidden attribute 'style'/);
  });
});

describe("icon allowlist parser — structural rejections", () => {
  test("invalid-no-root-svg.svg: file without root <svg> is rejected", () => {
    expect(() => parseIcon(readFix("invalid-no-root-svg.svg"), "invalid-no-root-svg.svg", "x")).toThrow(/root element must be <svg>/);
  });

  test("invalid-no-viewbox.svg: root <svg> missing viewBox is rejected", () => {
    expect(() => parseIcon(readFix("invalid-no-viewbox.svg"), "invalid-no-viewbox.svg", "x")).toThrow(/missing required attribute viewBox/);
  });

  test("invalid-text-content.svg: non-whitespace text content is rejected", () => {
    expect(() => parseIcon(readFix("invalid-text-content.svg"), "invalid-text-content.svg", "x")).toThrow(/text content is not allowed/);
  });
});

describe("allowlist self-consistency", () => {
  test("every shipped icon SVG parses cleanly", () => {
    // Walk frontend/public/icons/*.svg (the live icon registry per plan
    // section 21.10; SVG bytes live under public/, the allowlist + parser
    // are code and stay here under src/lib/icons/). Each .svg must
    // round-trip through parseIcon without throwing — this is the
    // build-time gate, asserted as a unit test.
    const here = resolve(fileURLToPath(new URL(".", import.meta.url)));
    const root = resolve(here, "..", "..", "..", "public", "icons");
    const entries = readdirSync(root, { withFileTypes: true });
    const svgs = entries.filter((e) => e.isFile() && e.name.endsWith(".svg") && !e.name.startsWith("_"));
    expect(svgs.length).toBeGreaterThan(0);
    for (const entry of svgs) {
      const src = readFileSync(resolve(root, entry.name), "utf8");
      const name = entry.name.replace(/\.svg$/, "");
      expect(() => parseIcon(src, entry.name, name), `icon ${entry.name} must parse`).not.toThrow();
    }
  });

  test("arrow-left-right.svg is registered for the compare hero card (PR4)", () => {
    // PR4 of TODO/20260617-election-compare-ux-overhaul-plan.md adds the
    // Flips KPI glyph. Assert the SVG exists in the registry directory and
    // parses to the 4 Lucide stroke paths the icon ships with.
    const here = resolve(fileURLToPath(new URL(".", import.meta.url)));
    const file = resolve(here, "..", "..", "..", "public", "icons", "arrow-left-right.svg");
    const icon = parseIcon(readFileSync(file, "utf8"), "arrow-left-right.svg", "arrow-left-right");
    expect(icon.name).toBe("arrow-left-right");
    expect(icon.viewBox).toBe("0 0 24 24");
    expect(icon.children).toHaveLength(4);
    expect(icon.children.every((c) => c.name === "path")).toBe(true);
  });

  test("ALLOWED_ELEMENTS and ALLOWED_ATTRS are non-empty (contract surfaces)", () => {
    expect(ALLOWED_ELEMENTS.size).toBeGreaterThan(0);
    expect(ALLOWED_ATTRS.size).toBeGreaterThan(0);
  });
});
