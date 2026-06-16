// Contract -- in-app navigation hrefs MUST go through the base-aware
// `link.*` builders (or `withBase`), never a hardcoded base-less path
// literal.
//
// The deploy base is `/yen-gov/` (GitHub Pages project site, see
// `frontend/vite.config.ts` -> `base: BASE_URL`). A hardcoded
// `href="/t/elections"` resolves to `https://miztiik.github.io/t/elections`
// at runtime -- DROPPING the `/yen-gov/` base -- so a reload, a new-tab
// open, or a shared link 404s. Every in-app link MUST be built via the
// `link.*` builders in `frontend/src/lib/links.ts` (each applies
// `withBase`), so the base prefix is always present.
//
// This sentinel was authored alongside the 2026-06-16 home-redesign PR,
// which fixed five base-less hrefs (the Home elections-rail door, the
// ElectionsRouteTabs nav, StateEventMap's national-surface link,
// StateElection's seat-row PC links, and the SiblingEventsRail chips).
// It exists to stop the same error from creeping back in.
//
// Allowed:    link.topic("elections") | withBase("/t") | {card.href} | "#..." | "https://..."
// Forbidden:  href="/t/elections" | href={`/${state}/elections/${ev}`} | href: "/t/elections"

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

const SRC_ROOT = resolve(__dirname, "..");
const SELF = "contracts/in-app-hrefs-use-base.test.ts";

/**
 * `href` followed by `:` or `=`, then an optional `{`, then an opening
 * quote / backtick, then `/`. Catches string + template-literal hrefs
 * that start at the site root WITHOUT going through `link.*` / `withBase`.
 *
 * Does NOT match (all legitimate):
 *   href={link.topic("x")}     -- `{` then `l`, not a quote
 *   href={withBase("/t")}      -- `{` then `w`, not a quote
 *   href={card.href}           -- `{` then `c`, not a quote
 *   href="#section"            -- quote then `#`, not `/`
 *   href="https://example.org" -- quote then `h`, not `/`
 *   href={`${base}/x`}         -- backtick then `$`, not `/`
 */
const BASELESS_HREF_RE = /href\s*[:=]\s*(?:\{\s*)?["'`]\//;

/** Skip comment lines so docstring examples (which legitimately show the
 *  forbidden shape) do not trip the sentinel. */
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

describe("contract -- in-app hrefs use the base-aware link.* builders", () => {
  it("no base-less absolute href literal anywhere under frontend/src (excl. tests)", () => {
    const violations: { file: string; lineNo: number; line: string }[] = [];
    for (const file of walkSrc(SRC_ROOT)) {
      const rel = toPosix(file);
      if (rel === SELF) continue;
      if (rel.endsWith(".test.ts") || rel.endsWith(".spec.ts")) continue;
      const text = readFileSync(file, "utf8");
      text.split(/\r?\n/).forEach((line, i) => {
        if (isCommentLine(line)) return;
        if (BASELESS_HREF_RE.test(line)) {
          violations.push({ file: rel, lineNo: i + 1, line: line.trim() });
        }
      });
    }
    expect(
      violations,
      "Base-less in-app href(s) found. Use link.* (or withBase) so the " +
        "/yen-gov/ deploy base is applied:\n" +
        violations.map(v => `  ${v.file}:${v.lineNo}  ${v.line}`).join("\n"),
    ).toEqual([]);
  });
});
