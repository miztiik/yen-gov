// Sort policy helpers — pure functions that apply a `SortPolicy` to an
// array of `SortItem` rows.
//
// Doctrine:
//   - CLAUDE.md §10 closed enums: `KNOWN_SORT_POLICIES` is the
//     authoritative array; `applySortPolicy` switches over the closed
//     union and TypeScript enforces exhaustiveness via the `never`
//     branch at the end of the switch.
//   - All sorts return a NEW array; inputs are never mutated.
//   - Sorts are STABLE — V8 / SpiderMonkey / JavaScriptCore have
//     stable `Array.prototype.sort` since ECMAScript 2019.
//   - Nulls / missing values SORT LAST in numeric policies per
//     plan rule: "Nulls/missing values stay visible and sort last
//     unless the projection explicitly filters them."

import { parseLeadingYear } from "../temporal-viewport/helpers";
import type { SortItem, SortOptions, SortPolicy } from "./types";

/**
 * The canonical list of supported sort policies. Adding a value here
 * REQUIRES extending the `SortPolicy` union in `./types.ts` AND adding
 * a switch arm to `applySortPolicy` below — the three-place rule that
 * keeps closed enums truly closed (CLAUDE.md §10).
 */
export const KNOWN_SORT_POLICIES: readonly SortPolicy[] = Object.freeze([
  "value_asc",
  "value_desc",
  "axis_order",
  "chronological",
  "pinned_then_value",
  "rank_best_first",
  "latest_change",
  "alphabetical",
]);

/**
 * Apply the requested `policy` to `items`. Returns a new array.
 * Inputs are never mutated. Stable. Nulls / missing keys sort LAST
 * in numeric and date policies.
 *
 * Renderers should call this from their view-model builder, AFTER
 * projecting their domain shape onto `SortItem`.
 */
export function applySortPolicy(
  items: readonly SortItem[],
  policy: SortPolicy,
  options: SortOptions = {},
): SortItem[] {
  // Copy first — sort mutates in place and we promised purity.
  const copy = items.slice();
  switch (policy) {
    case "value_asc":
      return copy.sort(compareByValueAsc);
    case "value_desc":
      return copy.sort(compareByValueDesc);
    case "axis_order":
      return copy.sort(compareByAxisOrder);
    case "chronological":
      return copy.sort(compareByChronological);
    case "pinned_then_value":
      return copy.sort(compareByPinnedThenValue);
    case "rank_best_first":
      return options.best_is_high === false
        ? copy.sort(compareByValueAsc)
        : copy.sort(compareByValueDesc);
    case "latest_change":
      return copy.sort(compareByLatestChange);
    case "alphabetical":
      return copy.sort(compareByAlphabetical);
    default: {
      // Exhaustiveness check — if a new SortPolicy is added without
      // a switch arm here, TypeScript fails the build.
      const exhaustive: never = policy;
      throw new Error(`Unknown sort policy: ${exhaustive as string}`);
    }
  }
}

// ─── comparators (all pure, all null-last) ─────────────────────────

function isMissing(v: number | null | undefined): boolean {
  return v === null || v === undefined || Number.isNaN(v);
}

function compareByValueAsc(a: SortItem, b: SortItem): number {
  const av = a.value;
  const bv = b.value;
  const aMissing = isMissing(av);
  const bMissing = isMissing(bv);
  // Both missing → equal → stable preserves insertion order.
  if (aMissing && bMissing) return 0;
  // One missing → it sorts LAST.
  if (aMissing) return 1;
  if (bMissing) return -1;
  // Both present.
  return (av as number) - (bv as number);
}

function compareByValueDesc(a: SortItem, b: SortItem): number {
  // Re-use compareByValueAsc and flip — but only for the
  // present-vs-present case; missing-last is preserved.
  const av = a.value;
  const bv = b.value;
  const aMissing = isMissing(av);
  const bMissing = isMissing(bv);
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  return (bv as number) - (av as number);
}

function compareByAxisOrder(a: SortItem, b: SortItem): number {
  // Missing `order` → treat as +Infinity → sorts LAST.
  const ao = a.order ?? Number.POSITIVE_INFINITY;
  const bo = b.order ?? Number.POSITIVE_INFINITY;
  if (ao === bo) return 0;
  return ao - bo;
}

function compareByChronological(a: SortItem, b: SortItem): number {
  // Re-use the temporal-viewport's `parseLeadingYear` for parity with
  // the brush. Unparseable period_ids (or missing period_id) sort LAST.
  const ay = a.period_id ? parseLeadingYear(a.period_id) : null;
  const by = b.period_id ? parseLeadingYear(b.period_id) : null;
  const aMissing = ay === null;
  const bMissing = by === null;
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  if (ay === by) {
    // Same year — fall back to lexical period_id compare so
    // 2024-01 sorts before 2024-09 deterministically.
    const ap = a.period_id as string;
    const bp = b.period_id as string;
    if (ap < bp) return -1;
    if (ap > bp) return 1;
    return 0;
  }
  return (ay as number) - (by as number);
}

function compareByPinnedThenValue(a: SortItem, b: SortItem): number {
  // Pinned rows first, in `pinned_rank` order (lower = earlier).
  // Unpinned (null/undefined) sort AFTER all pinned rows, then by value_desc.
  const ar = a.pinned_rank ?? null;
  const br = b.pinned_rank ?? null;
  const aPinned = ar !== null;
  const bPinned = br !== null;
  if (aPinned && bPinned) {
    if (ar === br) return 0;
    return (ar as number) - (br as number);
  }
  if (aPinned) return -1;
  if (bPinned) return 1;
  // Both unpinned → value_desc.
  return compareByValueDesc(a, b);
}

function compareByLatestChange(a: SortItem, b: SortItem): number {
  // Delta = |latest - previous|. Series with a missing endpoint have
  // null delta and sort LAST.
  const da = absDelta(a.latest_two);
  const db = absDelta(b.latest_two);
  const aMissing = da === null;
  const bMissing = db === null;
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  return (db as number) - (da as number);
}

function absDelta(
  pair: readonly [number | null, number | null] | undefined,
): number | null {
  if (!pair) return null;
  const [prev, latest] = pair;
  if (isMissing(prev) || isMissing(latest)) return null;
  return Math.abs((latest as number) - (prev as number));
}

function compareByAlphabetical(a: SortItem, b: SortItem): number {
  // Case-insensitive, locale-aware. Empty labels sort LAST.
  const al = a.label ?? "";
  const bl = b.label ?? "";
  if (al === "" && bl === "") return 0;
  if (al === "") return 1;
  if (bl === "") return -1;
  return al.localeCompare(bl, undefined, { sensitivity: "base" });
}

// ─── direction helper for renderers ────────────────────────────────

/**
 * For renderers that want to display a "sort direction" arrow icon,
 * returns "asc" | "desc" | "neutral" for a given policy. Neutral
 * means the policy isn't numeric (axis_order, chronological,
 * alphabetical, pinned_then_value).
 *
 * `rank_best_first` resolves to "desc" when `best_is_high` (default)
 * and "asc" otherwise.
 */
export function sortDirectionForPolicy(
  policy: SortPolicy,
  options: SortOptions = {},
): "asc" | "desc" | "neutral" {
  switch (policy) {
    case "value_asc":
      return "asc";
    case "value_desc":
    case "latest_change":
      return "desc";
    case "rank_best_first":
      return options.best_is_high === false ? "asc" : "desc";
    case "axis_order":
    case "chronological":
    case "pinned_then_value":
    case "alphabetical":
      return "neutral";
    default: {
      const exhaustive: never = policy;
      throw new Error(`Unknown sort policy: ${exhaustive as string}`);
    }
  }
}
