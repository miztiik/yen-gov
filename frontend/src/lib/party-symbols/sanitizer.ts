// Party-symbol sanitizer + hasher (node-only).
//
// PR-SYM-3 per TODO/20260527-party-symbol-assets-plan.md section 8. This
// module is the gate for any SVG that lands under
// `frontend/public/party-symbols/`. It reuses the strict allowlist parser
// from `$lib/icons` so the icon registry and the party-symbol registry
// share ONE allowlist (the failure mode the plan calls out: two divergent
// allowlists, fixed by importing the same module).
//
// This module imports `node:crypto` and is therefore node-only. It is used
// by:
//   * `sanitizer.test.ts` (vitest, runs in node).
//   * Future PR-SYM-4a author-time tooling that walks raw upstream SVGs.
//
// The runtime renderer (PR-SYM-5) does NOT import this file. The renderer
// reads pre-validated bytes + pre-computed `asset_sha256` from
// `dim_parties` and derives the static URL mechanically; no Web-Crypto
// boot, no sanitizer round-trip in the citizen bundle.

import { createHash } from "node:crypto";

import { parseIcon, IconParseError } from "../icons";

export class PartySymbolSanitizerError extends Error {
  constructor(
    public readonly file: string,
    public readonly reason: string,
    public readonly cause?: unknown,
  ) {
    super(`${file}: ${reason}`);
    this.name = "PartySymbolSanitizerError";
  }
}

export interface SanitizedSvg {
  /** The SVG bytes, as they should be committed. v1 returns input bytes
   * unchanged when validation succeeds (we never rewrite the file). */
  readonly sanitizedBytes: string;
  /** SHA-256 of `sanitizedBytes` as 64-char lowercase hex. Matches the
   * `asset_sha256` regex on `election_symbol`. */
  readonly sha256: string;
}

/** Validate an SVG against the shared icon allowlist and compute the
 *  asset_sha256 that goes into `election_symbol` metadata.
 *
 *  Rejects (via PartySymbolSanitizerError):
 *    * any element not in `ALLOWED_ELEMENTS` (script, foreignObject, use,
 *      image, iframe, animate, embed, audio, video, ...);
 *    * any attribute matching `FORBIDDEN_ATTR_PATTERNS` (`on*`, `xlink:*`,
 *      `href`, `style`);
 *    * any attribute not in `ALLOWED_ATTRS` on a nested element;
 *    * malformed XML (unterminated tag, unquoted attribute, etc).
 *
 *  Accepts:
 *    * source-coloured ballot symbols (fill / stroke attributes are on
 *      the allowlist; PR-SYM-1 schema's `render_mode` records whether the
 *      asset is monochrome or source-coloured).
 *    * `xmlns` on the root (tolerated, dropped by the icon registry).
 */
export function sanitizeAndHash(svgBytes: string, file: string): SanitizedSvg {
  try {
    parseIcon(svgBytes, file, "party-symbol");
  } catch (err) {
    if (err instanceof IconParseError) {
      throw new PartySymbolSanitizerError(file, err.reason, err);
    }
    throw new PartySymbolSanitizerError(file, String(err), err);
  }
  const sha256 = createHash("sha256").update(svgBytes, "utf8").digest("hex");
  return { sanitizedBytes: svgBytes, sha256 };
}
