// Permanent re-introduction sentinel for retired party-colour modules.
//
// These modules were retired across PRs #570-#599 (PR-SYM-6 spine) and
// deleted in PR-SYM-6i (the closing PR of the spine). Re-introducing any
// of these import paths is forbidden.
//
//   - lib/colors/party-colour.ts     (algorithmic + anchor lookup helper)
//   - lib/colors/anchors.ts          (curated iconic colour map; inlined
//                                     into lib/colors/resolver.ts)
//   - lib/colors/store.svelte.ts     (reactive override store, retired
//                                     along with the user-override UI)
//
// To resolve party colours, use `getPartyColor(party_id, row)` or
// `resolvePartyPalette(party_ids, rows)` from
// `frontend/src/lib/colors/resolver.ts`. For Svelte route helpers, see
// `partyColourHex` in `frontend/src/lib/psephlab/colour-bridge.ts`.
//
// The sentinel is PERMANENT -- there is no allowlist of grandfathered
// consumers. Any match is a regression.
//
// File name kept (`party-colour-import-allowlist.test.ts`) to preserve
// git history continuity with PRs #596, #597 that authored / patched it.

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

const SRC_ROOT = resolve(__dirname, "..");

/**
 * Forbidden import-path pattern. Matches any import of the three retired
 * party-colour modules (`party-colour`, `anchors`, `store.svelte`) at
 * any depth, via relative path (with or without a `lib/` segment) or
 * via the SvelteKit `$lib/` alias.
 *
 * Examples matched:
 *   from "./colors/party-colour"
 *   from "../colors/store.svelte"
 *   from "../../colors/anchors"
 *   from "../lib/colors/store.svelte"
 *   from "../../lib/colors/anchors"
 *   from "$lib/colors/anchors"
 */
const FORBIDDEN_IMPORT_RE =
  /from\s+["'](?:(?:\.\.?\/)+(?:lib\/)?|\$lib\/)colors\/(?:party-colour|anchors|store\.svelte)["']/;

const SELF = "contracts/party-colour-import-allowlist.test.ts";

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

describe("sentinel -- retired party-colour modules MUST NOT be re-introduced", () => {
  it("no imports of party-colour / anchors / store.svelte anywhere under frontend/src", () => {
    const violations: { file: string; line: string }[] = [];
    for (const file of walkTs(SRC_ROOT)) {
      const rel = toPosixWorkspace(file);
      // Exempt this file itself -- the docstring above contains example
      // import strings that the regex would otherwise flag.
      if (rel === SELF) continue;
      const src = readFileSync(file, "utf8");
      const match = src.match(FORBIDDEN_IMPORT_RE);
      if (match) {
        violations.push({ file: rel, line: match[0] });
      }
    }
    expect(
      violations,
      `Re-introduction of retired party-colour module(s) detected.
These modules were deleted in PR-SYM-6i (the closing PR of the SYM-6
spine, PRs #570-#599). Use \`getPartyColor\` / \`resolvePartyPalette\`
from \`frontend/src/lib/colors/resolver.ts\` instead.\n\n${JSON.stringify(violations, null, 2)}`,
    ).toEqual([]);
  });
});
