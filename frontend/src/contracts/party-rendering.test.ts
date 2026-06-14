// Party-rendering contract (PR-2 of
// TODO/20260612-party-rendering-and-party-pages-plan.md).
//
// Enforces docs/architecture/frontend/party-rendering.md "the single
// rule": every citizen-facing party reference renders via the
// `<PartyPill>` component AND links to `/parties/<slug>` via
// `link.party(party_id)`, unless it falls into one of the four named
// doctrinal exclusions (KPI numerators in prose, sort column headers,
// breadcrumb labels, tooltip body itself).
//
// Scope: every `.svelte` file under `frontend/src/routes/` AND
// `frontend/src/lib/charts/`. Auto-excludes:
//   - `frontend/src/lib/party-pill/**` (PartyPill internals; the tooltip
//     body exclusion #4 covers PartyTooltip.svelte).
//   - `frontend/src/routes/DevChartsSandbox.svelte` (developer surface
//     not on the citizen route table).
//
// What counts as a violation: any rendered text `{X.party_short}` or
// `{X.party_id}` Svelte template expression (NOT inside a `<script>` /
// `<style>` block, NOT inside a `${...}` JS template-literal interpolation,
// NOT a `{#each}` / `{:else}` / `{/if}` / `{@const}` block directive, NOT
// an attribute / component prop expression like `party_id={X.party_id}`)
// whose 5-line preceding context does NOT contain any of:
//   - `<PartyPill\b`            (the surface adopted PartyPill)
//   - `href={link.party(`       (the surface wraps the token in the
//                                canonical per-party link)
//   - `data-allow="party-text-<reason>"` (parent element declares an
//                                explicit named doctrinal exception)
//
// Fix paths when this test goes red:
//   - wrap the token in `<PartyPill size="sm" party_id={X.party_id}
//     party_short={X.party_short} row={X}/>` and put it inside an
//     `<a href={link.party(X.party_id)}>` when the surface should
//     navigate; OR
//   - if the token IS a doctrinal exception (one of the four named in
//     party-rendering.md), add `data-allow="party-text-<reason>"` to
//     the parent element so the next reader sees the named carve-out.
//
// Do NOT silently expand the allowlist for new violations. The bias is
// FIX (wrap in PartyPill), not allowlist - the doctrine is the
// PartyPill is the SINGLE coloured party-rendering primitive.

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

// ----- Configuration --------------------------------------------------

// `__dirname` -> `frontend/src/contracts`; go up two for the frontend root.
const FRONTEND_ROOT = resolve(__dirname, "..", "..");
const SCAN_DIRS = ["src/routes", "src/lib/charts"];

// Files explicitly excluded from the scan (developer-only surfaces).
const EXCLUDE_FILES = new Set<string>([
  "src/routes/DevChartsSandbox.svelte",
]);

// Path PREFIXES that are auto-excluded (PartyPill + PartyTooltip
// internals; the tooltip body exclusion is doctrinal #4).
const EXCLUDE_PREFIXES = [
  "src/lib/party-pill/",
];

// Sanity floor on the number of `.svelte` files actually scanned. Trips
// when a glob/import change empties the scan (catches "the test passed
// because no files matched"). Calibrated to leave headroom under the
// current count (~ 38 across routes + charts as of 2026-06-12).
const FLOOR_FILE_COUNT = 30;

// ----- Token + allowance regex ---------------------------------------

/**
 * Match a Svelte template expression of the shape `{<X>.party_short}` or
 * `{<X>.party_id}` where `<X>` is any non-`{`/`}`/newline expression.
 *
 * Defenses against false positives:
 *   - `(?<!\$)` - the `{` MUST NOT be preceded by `$`. Skips
 *     `${X.party_short}` JS template-literal interpolations that bleed
 *     out of stripped script blocks (rare; defensive).
 *   - `(?![#:/@])` - the `{` MUST NOT be followed by `#`, `:`, `/`, or
 *     `@`. Skips Svelte block directives (`{#if}` / `{:else}` /
 *     `{/each}` / `{@const}` / `{@html}` / `{@debug}`).
 *
 * The match anchor is the OPENING `{` plus the property-access tail;
 * the closing `}` is not required for the match (this means
 * expressions with nested braces or trailing `??` defaults still
 * register; the violation IS the `.party_short` mention regardless of
 * surrounding glue).
 */
const TOKEN_RE = /(?<!\$)\{(?![#:/@])[^{}\n]*\.party_(?:short|id)\b/g;

const ALLOW_PILL = /<PartyPill\b/;
const ALLOW_LINK = /href=\{link\.party\(/;
const ALLOW_ATTR = /data-allow="party-text-[\w-]+"/;
// 12-line lookback comfortably covers a multi-line `<PartyPill` open
// with 8 props + a trailing `/>` (a real-world max in the MapHighlight
// + PartyBar surfaces); 5 lines was tight enough that a prop on line
// N missed the PartyPill opener on line N-7.
const CONTEXT_BEFORE = 12;

// ----- Filesystem walking -------------------------------------------

function* walkSvelte(dir: string): IterableIterator<string> {
  const stack: string[] = [dir];
  while (stack.length > 0) {
    const cur = stack.pop() as string;
    let entries;
    try {
      entries = readdirSync(cur, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const ent of entries) {
      const abs = join(cur, ent.name);
      if (ent.isDirectory()) {
        if (ent.name === "node_modules" || ent.name.startsWith(".")) continue;
        stack.push(abs);
      } else if (ent.isFile() && ent.name.endsWith(".svelte")) {
        yield abs;
      }
    }
  }
}

function toRelPosix(abs: string): string {
  return relative(FRONTEND_ROOT, abs).split(sep).join("/");
}

// ----- Script/style stripping (preserves line numbers) --------------

/**
 * Replace every `<script ...>...</script>` and `<style ...>...</style>`
 * block with the same number of newlines so token line-positions
 * reported in error messages still match the original source. Script
 * blocks are not citizen-facing render output; their `p.party_short`
 * references are derivation logic, not rendered text.
 */
function stripScriptStyle(src: string): string {
  return src.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/g, (m) => {
    const nl = m.match(/\n/g);
    return nl ? "\n".repeat(nl.length) : "";
  });
}

// ----- Violation finder ---------------------------------------------

interface Violation {
  file: string;
  line: number;
  text: string;
}

function findViolations(rel: string, src: string): Violation[] {
  const stripped = stripScriptStyle(src);
  const lines = stripped.split("\n");
  const violations: Violation[] = [];

  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    TOKEN_RE.lastIndex = 0;
    const renderedMatches = [...ln.matchAll(TOKEN_RE)].filter((m) => {
      const index = m.index ?? 0;
      return !/=\s*$/.test(ln.slice(0, index));
    });
    if (renderedMatches.length === 0) continue;

    // Context: this line + up to CONTEXT_BEFORE prior lines. PartyPill
    // / link / data-allow may sit on this line OR an opening line of a
    // multi-line component / element.
    const start = Math.max(0, i - CONTEXT_BEFORE);
    const ctx = lines.slice(start, i + 1).join("\n");

    if (ALLOW_PILL.test(ctx)) continue;
    if (ALLOW_LINK.test(ctx)) continue;
    if (ALLOW_ATTR.test(ctx)) continue;

    violations.push({ file: rel, line: i + 1, text: ln.trim() });
  }
  return violations;
}

// ----- The test ------------------------------------------------------

describe("party-rendering contract (PR-2)", () => {
  const files: string[] = [];
  for (const sub of SCAN_DIRS) {
    for (const abs of walkSvelte(join(FRONTEND_ROOT, sub))) {
      const rel = toRelPosix(abs);
      if (EXCLUDE_FILES.has(rel)) continue;
      if (EXCLUDE_PREFIXES.some((p) => rel.startsWith(p))) continue;
      files.push(rel);
    }
  }
  files.sort();

  it(`scans at least ${FLOOR_FILE_COUNT} .svelte files (catches glob regressions)`, () => {
    expect(
      files.length,
      `Only ${files.length} files matched; expected >= ${FLOOR_FILE_COUNT}.\n` +
        `Files seen:\n  ${files.join("\n  ")}`,
    ).toBeGreaterThanOrEqual(FLOOR_FILE_COUNT);
  });

  it("every party_short / party_id template token renders via PartyPill, <a href={link.party(...)}>, or a named data-allow", () => {
    const all: Violation[] = [];
    for (const rel of files) {
      const abs = join(FRONTEND_ROOT, rel);
      const src = readFileSync(abs, "utf-8");
      for (const v of findViolations(rel, src)) all.push(v);
    }
    const message =
      all.length === 0
        ? "OK"
        : `Found ${all.length} party-rendering violations:\n` +
          all
            .map((v) => `  ${v.file}:${v.line}\n      ${v.text}`)
            .join("\n") +
          "\n\nFix by wrapping in <PartyPill .../> or " +
          "<a href={link.party(...)}>, or add " +
          'data-allow="party-text-<reason>" to the parent element. ' +
          "See docs/architecture/frontend/party-rendering.md.";
    expect(all, message).toEqual([]);
  });

  it("recognises a PartyPill mention in the 5-line preceding context", () => {
    const sample = [
      `<PartyPill`,
      `  size="sm"`,
      `  party_id={p.party_id}`,
      `  party_short={p.party_short}`,
      `/>`,
    ].join("\n");
    expect(findViolations("test", sample)).toEqual([]);
  });

  it("recognises a link.party() href on the SAME line", () => {
    const sample = `<a href={link.party(c.party_id)}>{c.party_short}</a>`;
    expect(findViolations("test", sample)).toEqual([]);
  });

  it("recognises a data-allow=\"party-text-...\" attribute in context", () => {
    const sample = `<span data-allow="party-text-self-identity">{party_id}</span>\n<p>{ex.party_short}</p>`;
    // The {party_id} bare token has no leading dot so TOKEN_RE doesn't
    // even consider it; the {ex.party_short} line is preceded by the
    // data-allow attribute and is allowed.
    expect(findViolations("test", sample)).toEqual([]);
  });

  it("flags a bare {X.party_short} with no allowance in context", () => {
    const sample = `<span class="font-medium">{p.party_short}</span>`;
    const vs = findViolations("test", sample);
    expect(vs).toHaveLength(1);
    expect(vs[0].text).toContain("party_short");
  });

  it("ignores {#each ... (x.party_id)} block-directive key expressions", () => {
    const sample = `{#each parties as p (p.party_id)}\n  <PartyPill party_id={p.party_id}/>\n{/each}`;
    expect(findViolations("test", sample)).toEqual([]);
  });

  it("ignores party_id / party_short attribute and component-prop expressions", () => {
    const sample = [
      `<a data-party-id={p.party_id}>`,
      `  <RecognitionStrip party_id={p.party_id} />`,
      `  <PartyPill party_id={p.party_id} party_short={p.party_short} />`,
      `</a>`,
    ].join("\n");
    expect(findViolations("test", sample)).toEqual([]);
  });

  it("ignores party_short references inside <script> blocks", () => {
    const sample = `<script lang="ts">\nconst s = p.party_short;\nfunction f(){ return p.party_id; }\n</script>\n<p>plain text</p>`;
    expect(findViolations("test", sample)).toEqual([]);
  });
});
