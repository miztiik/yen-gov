// F2b.4 pure helper module for Matrix renderer. Mirrors the
// geo-choropleth-helpers shape so vitest (node-env) covers the
// pivot/order/domain math without a DOM.
//
// Doctrine ties:
//   - Pure functions only. No DOM, no fetches, no Svelte runes.
//   - Row shape `(entity, time, value)` per parent plan section 22.4
//     invariant #1.
//   - Tested by `matrix-helpers.test.ts` (sibling file).
//   - Shares deriveDomain semantics with geo-choropleth-helpers so the
//     two renderers paint the SAME numeric domain on the same rows.

/**
 * The minimal row shape Matrix consumes. `entity_id` indexes the
 * vertical axis; `time` indexes the horizontal axis.
 */
export interface MatrixRow {
  /** Stable entity identifier (e.g. state slug, district LGD). */
  entity_id: string | number;
  /** Time slice (year, fiscal-year label, date string). */
  time: string | number;
  /** Observation value. Null = no data (renders as hatch). */
  value: number | null;
}

/**
 * Pivot rows into a `Map<entity_id_str, Map<time_str, value>>`.
 * Stringifies both axes so int-vs-string typing does not silently
 * mis-join. Last-wins on duplicate (entity, time) pairs.
 */
export function rowsByEntityByTime(
  rows: readonly MatrixRow[],
): Map<string, Map<string, number | null>> {
  const out = new Map<string, Map<string, number | null>>();
  for (const r of rows) {
    const e = String(r.entity_id);
    const t = String(r.time);
    let inner = out.get(e);
    if (!inner) {
      inner = new Map<string, number | null>();
      out.set(e, inner);
    }
    inner.set(t, r.value);
  }
  return out;
}

/**
 * Sorted entity order (stringified). Default order is the natural
 * sort of the stringified ids. Callers that want a custom order pass
 * an explicit `entity_order` to the renderer.
 */
export function entityOrder(rows: readonly MatrixRow[]): string[] {
  const set = new Set<string>();
  for (const r of rows) set.add(String(r.entity_id));
  return Array.from(set).sort();
}

/**
 * Sorted time order. Numeric strings sort numerically; otherwise
 * lexical. This is a small heuristic that suits the FY-string and
 * year-int cases the renderer cares about most.
 */
export function timeOrder(rows: readonly MatrixRow[]): string[] {
  const set = new Set<string>();
  for (const r of rows) set.add(String(r.time));
  const arr = Array.from(set);
  const allNumeric = arr.every(s => /^-?\d+(\.\d+)?$/.test(s));
  if (allNumeric) return arr.sort((a, b) => Number(a) - Number(b));
  return arr.sort();
}

/**
 * Derive `{min, max}` from the value column. Skips null + non-finite.
 * Returns `{min: 0, max: 1}` for empty/all-null input.
 *
 * Same shape and semantics as `deriveDomain` in
 * geo-choropleth-helpers so a Matrix and a GeoChoropleth fed the
 * same rows paint the same domain.
 */
export function deriveDomain(
  rows: readonly MatrixRow[],
): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const r of rows) {
    if (r.value == null || !Number.isFinite(r.value)) continue;
    if (r.value < min) min = r.value;
    if (r.value > max) max = r.value;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: 0, max: 1 };
  }
  return { min, max };
}
