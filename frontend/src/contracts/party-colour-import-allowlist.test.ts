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
 * Forbidden import-path fragments. Any file outside the allowlist that
 * contains an `import ... from "<fragment>"` (or `from '<fragment>'`)
 * triggers the assertion.
 *
 * Keep in lockstep with the actual file paths. If a path renames, also
 * update this list.
 */
const FORBIDDEN_IMPORTS = [
  "./colors/party-colour",
  "../colors/party-colour",
  "../../colors/party-colour",
  "./colors/anchors",
  "../colors/anchors",
  "../../colors/anchors",
  "./colors/store.svelte",
  "../colors/store.svelte",
  "../../colors/store.svelte",
  "./colors/category-colour",
  "../colors/category-colour",
  "../../colors/category-colour",
] as const;

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
  "lib/colors/category-colour.ts",

  // Resolver — sanctioned bridge. Imports from `./anchors` to populate
  // the curated ANCHORS_BY_PID map per the 3-tier contract.
  "lib/colors/resolver.ts",

  // Grandfathered consumers — pending follow-up migration. Each entry
  // is a real-world consumer that still uses `colors.fill` /
  // `partyColour` / `colors.forSet`. Each PR-SYM-6f+ follow-up retires
  // these one at a time as their loader contracts gain `party_id`.
  "routes/Compare.svelte",                                        // psephlab-derived rows
  "lib/charts/composition-bar/adapter-elections-seats.ts",        // PartyRow keyed on eci_code
  "lib/charts/composition-bar/adapter-elections-seats.test.ts",   // co-located fixture
  "lib/charts/stacked-trend/adapter-elections.ts",                // stacked-trend; same shape
  "lib/charts/StackedTrendV2.svelte",                             // uses category-colour
  "lib/elections/ElectionMap.svelte",                             // colors.store
  "lib/maplibre/IndiaMap.svelte",                                 // colors.store
  "lib/ParliamentArc.svelte",                                     // colors.store
  "lib/PartyBar.svelte",                                          // colors.store
  // PR-SYM-6f1 (#TBD): SeatDonut migrated to getPartyColor resolver.
  "lib/SwingSankey.svelte",                                       // colors.store
  "lib/view-models/election-tile-layout.ts",                      // colors.store
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
    const violations: { file: string; fragment: string }[] = [];
    for (const file of walkTs(SRC_ROOT)) {
      const rel = toPosixWorkspace(file);
      if (ALLOWLIST.has(rel)) continue;
      const src = readFileSync(file, "utf8");
      for (const fragment of FORBIDDEN_IMPORTS) {
        // Match either `from "<fragment>"` or `from '<fragment>'`.
        const pattern = new RegExp(
          `from\\s+["']${fragment.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")}["']`,
        );
        if (pattern.test(src)) {
          violations.push({ file: rel, fragment });
        }
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
