// F2b.6 pure helper module for CirclePack renderer. Mirrors the
// treemap-helpers shape; vitest (node-env) covers the layout +
// label-visibility math without a DOM.
//
// Doctrine ties:
//   - Pure functions only. No DOM, no fetches, no Svelte runes.
//   - Sqrt area scale - same HONESTY rule as Treemap per parent
//     §15.1: a 4x value reads as 4x area, not 16x. d3-hierarchy.pack()
//     applies value-proportional area directly when the hierarchy is
//     summed via `.sum(d => d.value)`.
//   - Two modes per parent §15.1 row 8:
//       - `pack`   = d3-hierarchy.pack() with padding=2; hierarchical
//                    (parent_id grouping respected).
//       - `bubble` = d3-hierarchy.pack() with padding=8; flat children
//                    only (parent_id ignored; one level deep).
//   - Tested by `circle-pack-helpers.test.ts` (sibling file).

import { hierarchy, pack, type HierarchyCircularNode } from "d3-hierarchy";

/**
 * The minimal row shape CirclePack consumes. Same shape as
 * TreemapRow (intentionally; the two renderers are interchangeable
 * for the same fixture so the citizen can pick the visual idiom).
 */
export interface CirclePackRow {
  /** Stable identifier. */
  id: string;
  /** Citizen-readable label. */
  label: string;
  /** Observation value. Must be >= 0; null rows are skipped. */
  value: number | null;
  /** Optional parent id for grouping (mode=pack only; ignored in bubble). */
  parent_id?: string | null;
}

/**
 * Layout-resolved circle shape consumed by the Svelte renderer.
 * Coordinates are in caller-pixel units relative to the bounding box.
 */
export interface CirclePackCircle {
  id: string;
  label: string;
  value: number;
  /** Parent id (null at the root or in bubble mode). */
  parent_id: string | null;
  /** Circle centre x in px. */
  cx: number;
  /** Circle centre y in px. */
  cy: number;
  /** Circle radius in px. */
  r: number;
}

export type CirclePackMode = "pack" | "bubble";

const PADDING_BY_MODE: Record<CirclePackMode, number> = {
  pack: 2,
  bubble: 8,
};

/**
 * Compute the circle-pack layout. Returns one circle per non-null
 * leaf row.
 *
 * `mode === "pack"`: hierarchical (respects parent_id, draws parent
 * bubbles too in the future; right now we surface leaves only since
 * the renderer paints flat).
 *
 * `mode === "bubble"`: flat children only; padding is wider so the
 * bubbles read as discrete cluster blobs rather than a tight pack.
 */
export function packLayout(
  rows: readonly CirclePackRow[],
  options: { width: number; height: number; mode: CirclePackMode },
): CirclePackCircle[] {
  const { width, height, mode } = options;
  if (width <= 0 || height <= 0) return [];

  const positive = rows.filter(
    r => r.value != null && Number.isFinite(r.value) && r.value > 0,
  );
  if (positive.length === 0) return [];

  const ROOT_ID = "__root__";
  type Node = { id: string; parent_id: string | null; label: string; value: number };
  const nodes: Node[] = [{ id: ROOT_ID, parent_id: null, label: "", value: 0 }];

  if (mode === "bubble") {
    // Flat: ignore parent_id; all leaves attach to the synthetic root.
    for (const r of positive) {
      nodes.push({
        id: r.id,
        parent_id: ROOT_ID,
        label: r.label,
        value: r.value as number,
      });
    }
  } else {
    // Hierarchical pack: respect parent_id.
    const seenIds = new Set<string>();
    for (const r of positive) seenIds.add(r.id);

    const parentIds = new Set<string>();
    for (const r of positive) {
      if (r.parent_id != null && r.parent_id !== "" && !seenIds.has(r.parent_id)) {
        parentIds.add(r.parent_id);
      }
    }
    for (const pid of parentIds) {
      nodes.push({ id: pid, parent_id: ROOT_ID, label: pid, value: 0 });
    }
    for (const r of positive) {
      const pid = r.parent_id != null && r.parent_id !== "" ? r.parent_id : ROOT_ID;
      nodes.push({
        id: r.id,
        parent_id: pid,
        label: r.label,
        value: r.value as number,
      });
    }
  }

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

  const layout = pack<Node>()
    .size([width, height])
    .padding(PADDING_BY_MODE[mode]);
  layout(h);

  const circles: CirclePackCircle[] = [];
  for (const node of h.leaves()) {
    const c = node as HierarchyCircularNode<Node>;
    if (c.data.id === ROOT_ID) continue;
    circles.push({
      id: c.data.id,
      label: c.data.label,
      value: c.data.value,
      parent_id: c.parent?.data.id === ROOT_ID ? null : c.parent?.data.id ?? null,
      cx: c.x,
      cy: c.y,
      r: c.r,
    });
  }
  return circles;
}

/**
 * Predicate: should the in-circle label render? Labels render only
 * when the radius is at least `min_radius_px`; smaller circles are
 * swatch-only with the label exposed via tooltip on hover.
 *
 * Default threshold: 24px. Caller can override.
 */
export function shouldRenderCircleLabel(
  circle: { r: number },
  min_radius_px: number = 24,
): boolean {
  return circle.r >= min_radius_px;
}
