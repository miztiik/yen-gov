// F2b.5 pure helper module for Treemap renderer. Lives separately
// from the .svelte file so vitest (node-env) covers the layout +
// label-visibility math without a DOM.
//
// Doctrine ties:
//   - Pure functions only. No DOM, no fetches, no Svelte runes.
//   - Row shape `(id, value, parent?)` per parent plan section 22.4
//     invariant #1.
//   - Sqrt area scale - HONESTY per parent §15.1: a 4x value reads
//     as 4x area, not 16x. d3-hierarchy.treemap() applies the layout
//     to the value sums directly; the caller's sum(d => d.value)
//     accumulator is what enforces the proportional area.
//   - Tested by `treemap-helpers.test.ts` (sibling file).

import { hierarchy, treemap, type HierarchyRectangularNode } from "d3-hierarchy";

/**
 * The minimal row shape Treemap consumes. Flat list with optional
 * `parent_id` for two-level grouping (e.g. region -> state ->
 * indicator value). When `parent_id` is null/undefined for ALL rows,
 * the treemap renders as one flat level.
 */
export interface TreemapRow {
  /** Stable identifier (e.g. entity id, slug). */
  id: string;
  /** Citizen-readable label. */
  label: string;
  /** Observation value. Must be >= 0; null rows are skipped. */
  value: number | null;
  /** Optional parent id for grouping. When ALL rows omit this, the
   *  treemap is single-level. */
  parent_id?: string | null;
}

/**
 * Layout-resolved tile shape consumed by the Svelte renderer.
 * Coordinates are in caller-pixel units relative to the treemap's
 * top-left corner.
 */
export interface TreemapTile {
  id: string;
  label: string;
  value: number;
  /** Parent id (for tooltip/breadcrumb). Null at the root. */
  parent_id: string | null;
  /** Tile rectangle in pixels. */
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  /** Convenience: width + height. */
  width: number;
  height: number;
}

/**
 * Compute the treemap layout. Returns one tile per non-null leaf row.
 * Null-valued and non-positive rows are dropped before layout (d3
 * treemap requires non-negative weights).
 *
 * The layout uses d3-hierarchy's default tile method
 * (`treemapSquarify`) which produces aspect-ratio-balanced tiles -
 * the standard treemap appearance OWID uses for breakdown charts.
 */
export function treemapLayout(
  rows: readonly TreemapRow[],
  options: { width: number; height: number },
): TreemapTile[] {
  const { width, height } = options;
  if (width <= 0 || height <= 0) return [];

  const positive = rows.filter(r => r.value != null && Number.isFinite(r.value) && r.value > 0);
  if (positive.length === 0) return [];

  const hasParents = positive.some(r => r.parent_id != null && r.parent_id !== "");

  // Build the hierarchical input. d3-hierarchy.stratify() needs
  // parent ids that themselves appear as ids; we synthesise a single
  // root and re-parent any orphans to it.
  const ROOT_ID = "__root__";
  const seenIds = new Set<string>();
  for (const r of positive) seenIds.add(r.id);

  type Node = { id: string; parent_id: string | null; label: string; value: number };
  const nodes: Node[] = [{ id: ROOT_ID, parent_id: null, label: "", value: 0 }];

  if (hasParents) {
    // Add parent nodes that aren't themselves leaves.
    const parentIds = new Set<string>();
    for (const r of positive) {
      if (r.parent_id != null && r.parent_id !== "" && !seenIds.has(r.parent_id)) {
        parentIds.add(r.parent_id);
      }
    }
    for (const pid of parentIds) {
      nodes.push({ id: pid, parent_id: ROOT_ID, label: pid, value: 0 });
    }
    // Add leaves.
    for (const r of positive) {
      const pid = r.parent_id != null && r.parent_id !== "" ? r.parent_id : ROOT_ID;
      nodes.push({ id: r.id, parent_id: pid, label: r.label, value: r.value as number });
    }
  } else {
    // Flat: all leaves attach to the synthetic root.
    for (const r of positive) {
      nodes.push({ id: r.id, parent_id: ROOT_ID, label: r.label, value: r.value as number });
    }
  }

  // Build the d3-hierarchy tree by id->children map.
  const childrenById = new Map<string, Node[]>();
  for (const n of nodes) {
    if (n.parent_id != null) {
      const arr = childrenById.get(n.parent_id) ?? [];
      arr.push(n);
      childrenById.set(n.parent_id, arr);
    }
  }
  const root = nodes.find(n => n.id === ROOT_ID);
  if (!root) return [];

  const h = hierarchy<Node>(root, n => childrenById.get(n.id))
    .sum(n => (childrenById.get(n.id) ? 0 : n.value))
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  const layout = treemap<Node>().size([width, height]).padding(2);
  layout(h);

  const tiles: TreemapTile[] = [];
  for (const node of h.leaves()) {
    const rect = node as HierarchyRectangularNode<Node>;
    if (rect.data.id === ROOT_ID) continue;
    tiles.push({
      id: rect.data.id,
      label: rect.data.label,
      value: rect.data.value,
      parent_id: rect.parent?.data.id === ROOT_ID ? null : rect.parent?.data.id ?? null,
      x0: rect.x0,
      x1: rect.x1,
      y0: rect.y0,
      y1: rect.y1,
      width: rect.x1 - rect.x0,
      height: rect.y1 - rect.y0,
    });
  }
  return tiles;
}

/**
 * Predicate: should the in-tile label render? Labels render only
 * when the tile is wider than the minimum width threshold AND taller
 * than the minimum height threshold; small tiles render as a swatch
 * only with the label exposed via tooltip on hover.
 *
 * Default thresholds: 40px wide, 18px tall. Caller can override.
 */
export function shouldRenderTileLabel(
  tile: { width: number; height: number },
  min_width_px: number = 40,
  min_height_px: number = 18,
): boolean {
  return tile.width >= min_width_px && tile.height >= min_height_px;
}

/**
 * Derive total value of all non-null rows. Useful for the legend
 * footer ("100% = INR X cr"). Returns 0 for empty/all-null input.
 */
export function totalValue(rows: readonly TreemapRow[]): number {
  let total = 0;
  for (const r of rows) {
    if (r.value == null || !Number.isFinite(r.value) || r.value < 0) continue;
    total += r.value;
  }
  return total;
}
