// Lightweight client-side SQL guard for the Data Explorer.
//
// Why this exists: the database is an in-memory copy in the user's tab, so a
// write isn't a *security* threat — there's no shared state to corrupt and no
// backend to attack. But two cheap guards make the experience saner:
//
//   1. read-only:    reject statements that would mutate the in-memory copy.
//                    Catches typos as much as bad intent (a stray DELETE in a
//                    hand-edited preset blows away the working set until the
//                    next page refresh, which is just confusing).
//   2. single-stmt:  reject queries with more than one ;-terminated statement
//                    so we never silently run a chained second statement whose
//                    results sql.js would discard.
//
// Both checks run on a comment-stripped copy so a forbidden word inside
// `-- a comment` or `/* ... */` is allowed.

/** SQL keywords whose presence (as a whole word) blocks execution. */
export const FORBIDDEN_KEYWORDS = [
  "INSERT", "UPDATE", "DELETE", "REPLACE", "MERGE",
  "DROP", "TRUNCATE", "ALTER", "CREATE",
  "ATTACH", "DETACH", "REINDEX", "VACUUM", "PRAGMA",
] as const;

export type GuardResult = { ok: true } | { ok: false; reason: string };

function stripComments(s: string): string {
  return s
    .replace(/--[^\n]*/g, " ")          // line comments
    .replace(/\/\*[\s\S]*?\*\//g, " "); // block comments
}

/**
 * Validate a single SQL string against the read-only / single-statement rules.
 * Pure function — no side effects, safe to unit-test.
 */
export function validateSql(raw: string): GuardResult {
  const cleaned = stripComments(raw).trim();
  if (!cleaned) return { ok: false, reason: "Empty query." };

  // Single statement only. Allow exactly one optional trailing ';'.
  const withoutTrailing = cleaned.replace(/;\s*$/, "");
  if (withoutTrailing.includes(";")) {
    return { ok: false, reason: "Only one statement is allowed per run." };
  }

  // Read-only: reject any forbidden keyword as a whole word (case-insensitive).
  const upper = withoutTrailing.toUpperCase();
  for (const kw of FORBIDDEN_KEYWORDS) {
    if (new RegExp(`\\b${kw}\\b`).test(upper)) {
      return { ok: false, reason: `Read-only mode: \`${kw}\` is not allowed.` };
    }
  }
  return { ok: true };
}
