/**
 * compare-kpis: pure KPI + new-party derivation for the election-compare
 * hero strip (`CompareElections.svelte`,
 * `/compare/elections/<state>/<from>/<to>`).
 *
 * Extracted as a pure `.ts` model (PR4 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md) so the KPI math + the
 * new-party predicate are vitest-tested in the node env WITHOUT mounting
 * Svelte (the frontend vitest run has no jsdom). The Svelte component stays
 * a thin template that calls `buildCompareKpis` from its `kpis` $derived and
 * flags each row via `isNewPartyRow`.
 *
 * The predicate is preserved EXACTLY from the component's pre-extraction
 * inline `kpis` $derived:
 *   - total_seats = count of non-orphan (comparable) rows;
 *   - flips       = non-orphan rows where is_flip;
 *   - holds       = non-orphan rows where !is_flip;
 *   - new entry   = a non-orphan row whose To-winner party_id won ZERO
 *                   seats in `from`. The From-winner baseline is the set of
 *                   from_party_id over ALL rows (boundary-change orphans
 *                   still carry a real from-party), exactly as the
 *                   component computed it before extraction.
 *
 * Composition % (PR4 reading 4a): `flips_pct` / `holds_pct` express flips /
 * holds as a share of the comparable-seat base, 0-100, null when there are
 * no comparable seats (divide-by-zero guard).
 *
 * Pure: same inputs -> same output. No I/O, no shared mutable state, no
 * import of the route component.
 */

/**
 * Minimal structural shape this model reads. The route's full `CompareRow`
 * satisfies it without the model importing the route (structural typing).
 */
export interface CompareKpiRow {
  from_party_id: string | null;
  to_party_id: string | null;
  is_flip: boolean;
  is_orphan: boolean;
}

/** Hero-strip KPIs + the new-party id set used for per-row flagging. */
export interface CompareKpis {
  /** Count of comparable (non-orphan) seats. Equals `flips + holds`. */
  total_seats: number;
  /** Non-orphan seats whose winner party changed between the two events. */
  flips: number;
  /** Non-orphan seats whose winner party was unchanged. */
  holds: number;
  /** Comparable SEATS won by a party that won zero seats in `from`
   *  (a seat count, not a distinct-party count). */
  new_party_entries: number;
  /** flips as a share of total_seats, 0-100; null when total_seats === 0. */
  flips_pct: number | null;
  /** holds as a share of total_seats, 0-100; null when total_seats === 0. */
  holds_pct: number | null;
  /** Distinct To-winner party_ids that won zero seats in `from`. A
   *  non-orphan row whose to_party_id is in this set is a new-party entry
   *  (see `isNewPartyRow`). */
  new_party_ids: ReadonlySet<string>;
}

/**
 * Build the compare hero KPIs over the union of both events' winner rows.
 *
 * @param rows the union of both events' winner slates (the route's
 *             `compare_rows`).
 */
export function buildCompareKpis(rows: readonly CompareKpiRow[]): CompareKpis {
  // Set of party_ids that won at least one seat in `from`. Built over ALL
  // rows (boundary-change orphans still carry a real from-party), matching
  // the component's pre-extraction loop exactly.
  const from_winning_parties = new Set<string>();
  for (const r of rows) {
    if (r.from_party_id) from_winning_parties.add(r.from_party_id);
  }

  let flips = 0;
  let holds = 0;
  let new_party_entries = 0;
  const new_party_ids = new Set<string>();
  for (const r of rows) {
    if (r.is_orphan) continue;
    if (r.is_flip) flips++;
    else holds++;
    if (r.to_party_id && !from_winning_parties.has(r.to_party_id)) {
      new_party_entries++;
      new_party_ids.add(r.to_party_id);
    }
  }

  const total_seats = flips + holds;
  const share = (n: number): number | null =>
    total_seats === 0 ? null : (n / total_seats) * 100;

  return {
    total_seats,
    flips,
    holds,
    new_party_entries,
    flips_pct: share(flips),
    holds_pct: share(holds),
    new_party_ids,
  };
}

/**
 * Per-row new-party flag. A row is a new-party entry when it is a
 * comparable (non-orphan) seat whose To-winner party_id is in the
 * `new_party_ids` set returned by `buildCompareKpis`. Orphans are never
 * new-party rows (they are excluded from the KPI tally the same way).
 */
export function isNewPartyRow(
  row: CompareKpiRow,
  new_party_ids: ReadonlySet<string>,
): boolean {
  return (
    !row.is_orphan &&
    row.to_party_id !== null &&
    new_party_ids.has(row.to_party_id)
  );
}
