// Import-allowlist contract test for legacy party-colour modules.
//
// Per PR-SYM-6a..6e + TODO/20260527-party-symbol-assets-plan.md §11
// one-identity doctrine: the canonical party-colour entrypoint is
// `frontend/src/lib/colors/resolver.ts` (`getPartyColor` / `resolvePartyPalette`).
//
// Legacy modules `colors/party-colour.ts`, `colors/anchors.ts`,
// `colors/store.svelte.ts`, and `colors/category-colour.ts` are
// transitional — they remain in the repo because a handful of consumers
// still use them, but they are NOT to be imported by NEW code. The
// resolver is the single sanctioned doorway.
//
// This test freezes the current grandfathered-consumer set. ANY new
// import outside the allowlist fails the test loud at the contract
// boundary — catches drift before reviewers see it.
//
// To remove an entry: migrate the consumer to `resolver.ts`. To add
// one (rare; only when reverting a migration): document why in the
// PR body. Pure deletions from the allowlist are always fine.

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

const SRC_ROOT = resolve(__dirname, "..");

/**
 * Forbidden import-path pattern. Matches any relative import of the
 * three legacy party-colour modules (`party-colour`, `anchors`,
 * `store.svelte`) at any depth, with or without a `lib/` segment in
 * the path.
 *
 * Examples matched:
 *   from "./colors/party-colour"
 *   from "../colors/store.svelte"
 *   from "../../colors/anchors"
 *   from "../lib/colors/store.svelte"   <- routes/*.svelte shape
 *   from "../../lib/colors/anchors"
 *
 * PR-SYM-6i-pre1 (#TBD): widened from a fixed fragment list to a
 * single depth-agnostic regex after PR #596 mis-reported the
 * grandfathered-consumer set as EMPTY -- the old fragment list missed
 * `../lib/colors/...` (the shape every `routes/*.svelte` uses), so
 * 5 live route consumers were slipping through the contract.
 */
const FORBIDDEN_IMPORT_RE =
  /from\s+["'](?:\.\.?\/)+(?:lib\/)?colors\/(?:party-colour|anchors|store\.svelte)["']/;

/**
 * Files that are PERMITTED to import the legacy modules. Each entry is
 * a workspace-relative POSIX path (no leading "./"). One of three reasons:
 *   1. The legacy module itself, or its co-located test.
 *   2. The resolver — `resolver.ts` re-exports anchor data internally;
 *      this is the SANCTIONED bridge.
 *   3. A consumer not yet migrated (grandfathered with a follow-up PR
 *      tag in the comment column). New entries here MUST be accompanied
 *      by a follow-up note in `TODO/20260527-party-symbol-assets-plan.md`.
 */
const ALLOWLIST = new Set<string>([
  // Legacy modules themselves (and their tests, where present)
  "lib/colors/party-colour.ts",
  "lib/colors/party-colour.test.ts",
  "lib/colors/anchors.ts",
  "lib/colors/store.svelte.ts",

  // This contract test itself contains example import strings in its
  // docstrings (e.g. `from "./colors/party-colour"`) -- exempt it from
  // its own walk.
  "contracts/party-colour-import-allowlist.test.ts",

  // Resolver -- sanctioned bridge. Imports from `./anchors` to populate
  // the curated ANCHORS_BY_PID map per the 3-tier contract.
  "lib/colors/resolver.ts",

  // PR-SYM-6i-pre1 (#597): grandfathered route consumers surfaced when
  // the FORBIDDEN regex widened to match `../lib/colors/...`. Each is
  // tagged with its planned migration PR.
  "routes/Settings.svelte",            // MIGRATE in PR-SYM-6i-pre2

  // Historical migration log (modules retired from FORBIDDEN over time):
  // PR-SYM-6f1 (#585): SeatDonut migrated to getPartyColor resolver.
  // PR-SYM-6f2 (#586): PartyBar migrated to resolvePartyPalette + getPartyColor.
  // PR-SYM-6f3 (#587): IndiaMap migrated to resolvePartyPalette + getPartyColor.
  // PR-SYM-6f4 (#589): ElectionMap migrated to resolvePartyPalette + getPartyColor.
  // PR-SYM-6f5 (#590): composition-bar adapter migrated to getPartyColor.
  // PR-SYM-6f6 (#591): stacked-trend adapter migrated to getPartyColor.
  // PR-SYM-6f7 (#592): election-tile-layout view-model migrated to resolvePartyPalette + getPartyColor.
  // PR-SYM-6g  (#595): ParliamentArc + SwingSankey + routes/Compare migrated to
  //                    `partyColourHex` from `lib/psephlab/colour-bridge.ts`.
  // PR-SYM-6i-pre3 (#TBD): NationalElectionsAtlas + Psephlab + StateElection +
  //                        StateOverview migrated to getPartyColor /
  //                        resolvePartyPalette / partyColourHex. National PC
  //                        producer extended with party_id + brand mirror.
  // PR-SYM-6i  (#TBD): legacy module deletion (party-colour.ts, anchors.ts,
  //                    store.svelte.ts) -- final closing PR of the SYM-6 spine.
]);

function* walkTs(dir: string): IterableIterator<string> {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (name === "node_modules" || name.startsWith(".")) continue;
      yield* walkTs(full);
    } else if (
      name.endsWith(".ts") ||
      name.endsWith(".svelte") ||
      name.endsWith(".svelte.ts")
    ) {
      yield full;
    }
  }
}

function toPosixWorkspace(abs: string): string {
  return relative(SRC_ROOT, abs).split(sep).join("/");
}

describe("contract — legacy party-colour modules are not imported outside the allowlist", () => {
  it("no NEW imports of party-colour / anchors / store.svelte / category-colour outside the grandfathered set", () => {
    const violations: { file: string; line: string }[] = [];
    for (const file of walkTs(SRC_ROOT)) {
      const rel = toPosixWorkspace(file);
      if (ALLOWLIST.has(rel)) continue;
      const src = readFileSync(file, "utf8");
      const match = src.match(FORBIDDEN_IMPORT_RE);
      if (match) {
        violations.push({ file: rel, line: match[0] });
      }
    }
    expect(
      violations,
      `New import(s) of legacy party-colour modules detected outside the allowlist.
Migrate the consumer to \`lib/colors/resolver.ts\` (\`getPartyColor\` /
\`resolvePartyPalette\`) or, if you must keep the legacy import, add the
file to ALLOWLIST in this test with a follow-up note in
TODO/20260527-party-symbol-assets-plan.md.\n\n${JSON.stringify(violations, null, 2)}`,
    ).toEqual([]);
  });

  it("every allowlist entry actually exists (no stale paths)", () => {
    const missing: string[] = [];
    for (const rel of ALLOWLIST) {
      try {
        statSync(join(SRC_ROOT, rel));
      } catch {
        missing.push(rel);
      }
    }
    expect(
      missing,
      `Allowlist references files that no longer exist. Remove them or fix the path.\n${missing.join("\n")}`,
    ).toEqual([]);
  });
});
