/**
 * compare-table-filter: pure filter + sort projection for the
 * election-compare table (`CompareElections.svelte`,
 * `/compare/elections/<state>/<from>/<to>`).
 *
 * Extracted as a pure `.ts` model (PR3 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md) so the predicate is
 * vitest-tested in the node env WITHOUT mounting Svelte (the frontend
 * vitest run has no jsdom). The Svelte component stays a thin template
 * that calls `filterAndSortCompareRows` from its `filtered_sorted`
 * `$derived`.
 *
 * Three orthogonal controls compose, in this fixed order:
 *   1. filter chip  - "all" | "flips" | "holds"  (the EXACT predicate the
 *                     component used before extraction: flips = is_flip;
 *                     holds = !is_flip && !is_orphan).
 *   2. search query - live case-insensitive substring over the
 *                     constituency name AND both winner party short codes
 *                     (from_party / to_party, e.g. "DMK").
 *   3. column sort  - "entity_name" | "from_party" | "to_party", asc/desc,
 *                     null-coalesced to "" so missing parties sort first.
 *
 * Pure: same inputs -> same output. No I/O, no shared mutable state, no
 * import of the route component.
 */

/** Filter-chip selection. */
export type CompareFilter = "all" | "flips" | "holds";

/** Sortable text column. */
export type CompareSortKey = "entity_name" | "from_party" | "to_party";

/** Sort direction. */
export type CompareSortDir = "asc" | "desc";

/**
 * Minimal structural shape this model reads. The route's full `CompareRow`
 * satisfies it without the model importing the route (structural typing).
 */
export interface CompareTableRow {
  entity_name: string;
  from_party: string | null;
  to_party: string | null;
  is_flip: boolean;
  is_orphan: boolean;
}

/** True when `q` (already lowercased + trimmed) is a substring of the
 *  constituency name or either winner party short code. */
function matchesQuery(row: CompareTableRow, q: string): boolean {
  if (row.entity_name.toLowerCase().includes(q)) return true;
  if ((row.from_party ?? "").toLowerCase().includes(q)) return true;
  if ((row.to_party ?? "").toLowerCase().includes(q)) return true;
  return false;
}

/**
 * Filter (chip + search) then sort the compare rows.
 *
 * Generic over `R extends CompareTableRow` so the caller gets its concrete
 * row type back (the route passes `CompareRow[]` and receives `CompareRow[]`).
 *
 * @param rows     compare rows (the union of both events' winner slates).
 * @param query    raw search box value; trimmed + lowercased internally.
 * @param filter   active filter chip.
 * @param sort_key active sort column.
 * @param sort_dir active sort direction.
 */
export function filterAndSortCompareRows<R extends CompareTableRow>(
  rows: readonly R[],
  query: string,
  filter: CompareFilter,
  sort_key: CompareSortKey,
  sort_dir: CompareSortDir,
): R[] {
  // 1. filter chip (exact predicate preserved from the component).
  let rs: readonly R[] = rows;
  if (filter === "flips") {
    rs = rs.filter((r) => r.is_flip);
  } else if (filter === "holds") {
    rs = rs.filter((r) => !r.is_flip && !r.is_orphan);
  }

  // 2. search query (composes with the chip).
  const q = query.trim().toLowerCase();
  if (q) {
    rs = rs.filter((r) => matchesQuery(r, q));
  }

  // 3. column sort (null-coalesced, stable copy).
  const cmp = (a: R, b: R): number => {
    const av = a[sort_key] ?? "";
    const bv = b[sort_key] ?? "";
    const diff = av < bv ? -1 : av > bv ? 1 : 0;
    return sort_dir === "asc" ? diff : -diff;
  };
  return [...rs].sort(cmp);
}
