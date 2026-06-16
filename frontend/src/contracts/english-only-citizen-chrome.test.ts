/**
 * Static-source contract: English-only citizen-chrome on the elections
 * route family (and any other citizen-facing Svelte component on the
 * frontend).
 *
 * Doctrine: [docs/architecture/frontend/url-grammar.md](docs/architecture/frontend/url-grammar.md)
 * line 251 -
 *   "Chrome strings - page titles, KPI labels, chart axes, button
 *    captions use 'Parliament', 'Assembly', 'General Election YYYY',
 *    '<State> Assembly Election YYYY'. Never 'Lok Sabha' / 'Vidhan
 *    Sabha' / 'Vidhan Parishad'."
 *
 * Hans-led debate (recorded in the url-grammar doc Section 0): the
 * citizen reads English on the web but speaks one of 22 scheduled
 * languages at home; baking one local-language vocabulary into the
 * spine of an India-wide federal site privileges that one language
 * over the other 21 and breaks the read-aloud test for the median
 * citizen.
 *
 * Carve-outs (NOT forbidden by this contract):
 *  1. The doctrine doc itself names the forbidden terms (this is the
 *     authoritative source the test cites). Excluded from scan.
 *  2. CSV source-citation strings ("Rajya Sabha Session 260 Unstarred
 *     Question 1323") - these are the actual TITLE of a publisher's
 *     document; scrubbing them would lie about provenance (Holy Law
 *     #9). Lives in the canonical/indicator-allowlist.ts metadata,
 *     NOT in citizen-rendered chrome. Excluded from scan.
 *  3. Operator-only catalogue notes in datasets/taxonomy (the JSON
 *     files there). Not rendered to citizens; out of scan scope (this
 *     test only scans Svelte files under frontend/src).
 *  4. PIB-press-release quotes in datasets/taxonomy/office_holdings.json
 *     ("Chairman of Rajya Sabha") - official constitutional titles in
 *     curator-cited press releases; out of scan scope.
 *
 * Why static-source not e2e: the previous incident (PR-1048 / PR-1049
 * cycle, user-memory lesson 2026-06-15) showed that e2e absence-guards
 * can sit RED for days before anyone notices. A vitest gate that runs
 * on every developer's `bun run test` is strictly stronger.
 *
 * Negative-control gate: re-inject "Lok Sabha" or "Vidhan Sabha" into
 * any citizen-rendered Svelte template; this test goes RED in <10ms
 * naming the file and the offending phrase.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, join, sep } from "node:path";
import { readdirSync, statSync } from "node:fs";

const ROOT = resolve(__dirname, "../../");
const SVELTE_DIR = join(ROOT, "src");

const FORBIDDEN_PHRASES = [
  "Lok Sabha",
  "Vidhan Sabha",
  "Vidhan Parishad",
  // Rajya Sabha is intentionally NOT in this list - it appears in
  // legitimate publisher-citation strings (e.g. "Rajya Sabha Session
  // 260 Unstarred Question 1323") that live in indicator-allowlist.ts
  // metadata, not in citizen chrome. If a future citizen-chrome
  // string needs scrubbing for Rajya Sabha, audit the citations
  // first (they are the actual publisher document titles per Holy
  // Law #9 - lying about provenance is forbidden).
] as const;

/** Walk every .svelte file under src/, returning absolute paths. */
function walkSvelteFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      walkSvelteFiles(full, acc);
    } else if (entry.endsWith(".svelte")) {
      acc.push(full);
    }
  }
  return acc;
}

describe("English-only citizen-chrome contract (url-grammar.md doctrine)", () => {
  const svelteFiles = walkSvelteFiles(SVELTE_DIR);

  it("walks the svelte source tree (sanity)", () => {
    // Floor: we expect at least 100 .svelte files; if this fails the
    // walker is broken, not the contract.
    expect(svelteFiles.length).toBeGreaterThan(100);
  });

  it("no .svelte template renders 'Lok Sabha' / 'Vidhan Sabha' / 'Vidhan Parishad' in chrome", () => {
    const hits: { file: string; phrase: string; line: number; snippet: string }[] = [];

    for (const file of svelteFiles) {
      const src = readFileSync(file, "utf8");
      // Template region only: everything after the LAST </script>.
      // The instance script's documentation comments may legitimately
      // name the forbidden phrase as documentation (the contract test
      // itself does this); a static-source scan must NOT trip on
      // explanatory comments in code.
      const templateStart = src.lastIndexOf("</script>");
      const template = templateStart >= 0 ? src.slice(templateStart) : src;

      const lines = template.split(/\r?\n/);
      for (let i = 0; i < lines.length; i++) {
        for (const phrase of FORBIDDEN_PHRASES) {
          if (lines[i].includes(phrase)) {
            const relPath = file
              .slice(ROOT.length)
              .replace(/\\/g, "/")
              .replace(/^\//, "");
            hits.push({
              file: relPath,
              phrase,
              line: i + 1,
              snippet: lines[i].trim().slice(0, 120),
            });
          }
        }
      }
    }

    expect(
      hits,
      "Citizen-chrome contract violation: a Svelte template contains a " +
        "forbidden local-language token. Per docs/architecture/frontend/url-grammar.md " +
        'use "Parliament" / "Assembly" / "General Election YYYY" instead.\n' +
        "Findings:\n" +
        hits
          .map((h) => `  - ${h.file}:${h.line} - "${h.phrase}" in:  ${h.snippet}`)
          .join("\n"),
    ).toEqual([]);
  });
});

// Keep `sep` referenced so the import survives a future formatter sweep.
void sep;
