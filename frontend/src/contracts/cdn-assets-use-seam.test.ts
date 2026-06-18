// Contract -- runtime static-asset `src` attributes MUST go through the
// base-aware `assetUrl` / `withBase` seam (frontend/src/lib/config/cdn.ts),
// never a hardcoded base-less path literal.
//
// The deploy base is `/yen-gov/` (GitHub Pages project site, see
// `frontend/vite.config.ts` -> `base: BASE_URL`). A hardcoded
// `<img src="/brands/wikipedia.svg">` resolves to
// `https://<user>.github.io/brands/wikipedia.svg` at runtime -- DROPPING
// the `/yen-gov/` base -- so the asset 404s on the deployed site (this is
// exactly the Wikipedia-logo bug Row A fixes). Every runtime asset `src`
// MUST be built via `assetUrl(...)` (or `withBase(...)`) from the single
// base/CDN seam at `frontend/src/lib/config/cdn.ts`, so the base prefix is
// always present in both dev ('/') and prod ('/yen-gov/').
//
// This sentinel mirrors `contracts/in-app-hrefs-use-base.test.ts` (the
// `href` sibling) -- same walkSrc + comment-skip + self-skip + test-skip
// structure -- but flags base-less ASSET `src` literals instead of `href`.
//
// NOT enforced (legitimately out of scope):
//   * CSS `url(...)` and `index.html` -- Vite rewrites those at build time;
//     and walkSrc only visits `.ts` / `.svelte` under `frontend/src`.
//   * `srcset` -- a different attribute; the `set` between `src` and `=`
//     means it never matches `src[:=]`.
//   * `data:` / `https:` URIs and protocol-relative `//host` paths -- those
//     are already absolute, so they need no base prefix.
//   * `src={someVar}` / `src={assetUrl("/x")}` -- already through the seam.
//
// Allowed:    src={assetUrl("/brands/x.svg")} | src={url} | src="https://x" | src="data:..."
// Forbidden:  src="/brands/x.svg" | src={"/brands/x.svg"} | el.src = "/x.svg"

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

const SRC_ROOT = resolve(__dirname, "..");
const SELF = "contracts/cdn-assets-use-seam.test.ts";

/**
 * `src` (NOT `srcset`, NOT `data-src`) followed by `:` or `=`, an optional
 * `{`, an opening quote / backtick, then a single `/` that is NOT followed
 * by a second `/` (so protocol-relative `//host` is excluded). Catches
 * string + object-literal + imperative `el.src = "/x"` asset paths that
 * start at the site root WITHOUT going through `assetUrl` / `withBase`.
 *
 * The `(?<![\w-])` look-behind keeps the leading `src` from matching the
 * tail of `data-src` / `imgsrc` etc.; a leading `.` (as in `el.src =`) is
 * NOT a word char, so the imperative-assignment form is still caught.
 *
 * Does NOT match (all legitimate):
 *   src={assetUrl("/x")}   -- `{` then `a`, not a quote
 *   src={url}              -- `{` then `u`, not a quote
 *   src="https://example"  -- quote then `h`, not `/`
 *   src="data:image/png"   -- quote then `d`, not `/`
 *   src="//cdn.host/x"      -- quote then `//`, excluded by `(?!\/)`
 *   srcset="/a.png 1x"      -- `set` blocks the `src[:=]` step
 */
const BASELESS_SRC_RE = /(?<![\w-])src\s*[:=]\s*(?:\{\s*)?["'`]\/(?!\/)/;

/** Skip comment lines so the docstring examples (which legitimately show
 *  the forbidden shape) do not trip the sentinel. */
function isCommentLine(line: string): boolean {
  const t = line.trim();
  return (
    t.startsWith("*") ||
    t.startsWith("//") ||
    t.startsWith("/*") ||
    t.startsWith("<!--")
  );
}

function* walkSrc(dir: string): IterableIterator<string> {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (name === "node_modules" || name.startsWith(".")) continue;
      yield* walkSrc(full);
    } else if (name.endsWith(".ts") || name.endsWith(".svelte")) {
      yield full;
    }
  }
}

function toPosix(abs: string): string {
  return relative(SRC_ROOT, abs).split(sep).join("/");
}

describe("contract -- asset src attributes use the base-aware seam", () => {
  it("no base-less absolute asset src literal anywhere under frontend/src (excl. tests)", () => {
    const violations: { file: string; lineNo: number; line: string }[] = [];
    for (const file of walkSrc(SRC_ROOT)) {
      const rel = toPosix(file);
      if (rel === SELF) continue;
      if (rel.endsWith(".test.ts") || rel.endsWith(".spec.ts")) continue;
      const text = readFileSync(file, "utf8");
      text.split(/\r?\n/).forEach((line, i) => {
        if (isCommentLine(line)) return;
        if (BASELESS_SRC_RE.test(line)) {
          violations.push({ file: rel, lineNo: i + 1, line: line.trim() });
        }
      });
    }
    expect(
      violations,
      "Base-less asset src(es) found. Route them through assetUrl(...) (or " +
        "withBase) from lib/config/cdn so the /yen-gov/ deploy base is " +
        "applied:\n" +
        violations.map(v => `  ${v.file}:${v.lineNo}  ${v.line}`).join("\n"),
    ).toEqual([]);
  });

  // Positive + negative controls: prove the guard is live -- the regex
  // WOULD catch a planted base-less src, and does NOT fire on the
  // legitimate seam / absolute-URI shapes.
  it("regex catches a planted base-less src and spares seam / absolute shapes", () => {
    // Forbidden shapes -- MUST match.
    expect(BASELESS_SRC_RE.test('src="/x.svg"')).toBe(true);
    expect(BASELESS_SRC_RE.test('<img src="/brands/wikipedia.svg" />')).toBe(
      true,
    );
    expect(BASELESS_SRC_RE.test('src={"/x.svg"}')).toBe(true);
    expect(BASELESS_SRC_RE.test('el.src = "/x.svg"')).toBe(true);

    // Allowed shapes -- MUST NOT match.
    expect(BASELESS_SRC_RE.test('src={assetUrl("/x.svg")}')).toBe(false);
    expect(BASELESS_SRC_RE.test("src={url}")).toBe(false);
    expect(BASELESS_SRC_RE.test('src="https://example.org/x.svg"')).toBe(false);
    expect(BASELESS_SRC_RE.test('src="data:image/svg+xml,abc"')).toBe(false);
    expect(BASELESS_SRC_RE.test('src="//cdn.host/x.svg"')).toBe(false);
    expect(BASELESS_SRC_RE.test('srcset="/a.png 1x, /b.png 2x"')).toBe(false);
  });
});
