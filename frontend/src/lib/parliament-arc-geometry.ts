// ParliamentArc seat-dot geometry - pure, testable derivation.
//
// Extracted from ParliamentArc.svelte (Request G) so the load-bearing
// compactness + 234-seat reconciliation invariants can be unit-tested
// without mounting the component (the repo runs vitest in node-env and
// does NOT install @testing-library/svelte).
//
// One dot per seat, arranged on concentric arcs. Parties are ordered
// left -> right (alliance-grouped when a resolver is supplied, else
// seats-descending) and the dots are painted party-by-party. A
// compactness scale shrinks BOTH radii for small chambers so a 20-seat
// house renders compact instead of stretched across the full width; the
// scale clamps to 1 at >= 140 seats, leaving large chambers (TN 234)
// byte-identical to the pre-extraction layout.
//
// Pure: no DOM, no Svelte runes, no I/O.

import type { PartyResult } from "./psephlab/types";
import { partyColourHex } from "./psephlab/colour-bridge";
import { orderArcParties } from "./parliament-arc-order";

// Base layout constants. Shared by the component and the unit test so
// there is ONE source of truth for the canvas + radii.
export const ARC_W = 720;
export const ARC_H = 380;
export const ARC_CX = ARC_W / 2;
export const ARC_CY = ARC_H - 24; // baseline of the semicircle
export const ARC_R_INNER = 140;
export const ARC_R_OUTER = 340;

export interface ArcDot {
  x: number;
  y: number;
  party_eci_code: string;
  party_short: string;
  fill: string;
}

export interface ArcGeometry {
  dots: ArcDot[];
  dot_radius: number;
  /** Effective outer radius after scaling - the component frames the viewBox
   *  + majority midline off this so both track the compact arc. */
  max_radius: number;
}

export function computeArcGeometry(params: {
  parties: PartyResult[];
  total_seats: number;
  alliance_of?: (p: PartyResult) => string | null;
}): ArcGeometry {
  const { parties, total_seats, alliance_of } = params;

  if (total_seats <= 0) {
    return { dots: [], dot_radius: 4, max_radius: ARC_R_OUTER };
  }

  // Compactness scale (the one behavioural change vs the inline version):
  // shrink BOTH radii together so small chambers use a smaller arc while the
  // arc-length RATIOS - and therefore the per-row rounding reconciliation -
  // are preserved at every size. scale == 1 for every chamber with >= 140
  // seats, so TN's 234-seat layout is byte-identical; a 20-seat chamber gets
  // scale = sqrt(20/140) = 0.378 (~62% narrower). The 0.3 floor keeps tiny
  // UT chambers visible.
  const scale = Math.min(1, Math.max(0.3, Math.sqrt(total_seats / 140)));
  const r_inner = ARC_R_INNER * scale;
  const r_outer = ARC_R_OUTER * scale;

  const cx = ARC_CX;
  const cy = ARC_CY;

  // Pick a row count so every row holds at least ~6 dots and dots stay
  // legible. Heuristic: rows = clamp(round(sqrt(total/6)), 4, 12).
  const rows = Math.min(12, Math.max(4, Math.round(Math.sqrt(total_seats / 6))));

  const radii: number[] = [];
  for (let i = 0; i < rows; i++) {
    const t = rows === 1 ? 0 : i / (rows - 1);
    radii.push(r_inner + (r_outer - r_inner) * t);
  }
  const arc_lengths = radii.map((r) => Math.PI * r);
  const total_arc = arc_lengths.reduce((s, x) => s + x, 0);
  const per_row: number[] = arc_lengths.map((L) =>
    Math.max(1, Math.round((L / total_arc) * total_seats)),
  );

  // Reconcile rounding so sum exactly equals total_seats.
  let drift = total_seats - per_row.reduce((s, x) => s + x, 0);
  let ridx = per_row.length - 1;
  while (drift !== 0) {
    per_row[ridx] += drift > 0 ? 1 : -1;
    drift += drift > 0 ? -1 : 1;
    ridx = (ridx - 1 + per_row.length) % per_row.length;
  }

  // Real spacing: along each row's arc and between rows radially. Dot radius
  // is taken as ~42% of the tighter of the two so adjacent dots never
  // visually touch; clamped to a sane visual range.
  const radial_gap = rows > 1 ? (r_outer - r_inner) / (rows - 1) : r_outer - r_inner;
  const min_arc_spacing = Math.min(
    ...radii.map((r, i) => (Math.PI * r) / Math.max(1, per_row[i] - 1)),
  );
  const min_spacing = Math.min(min_arc_spacing, radial_gap);
  const dot_radius = Math.max(4, Math.min(14, 0.42 * min_spacing));

  // Flat list of (row, position-in-row) sorted by angle (left -> right).
  const slots: { angle: number; r: number; row: number; col: number }[] = [];
  for (let r = 0; r < per_row.length; r++) {
    const n = per_row[r];
    for (let c = 0; c < n; c++) {
      // Angle from PI (left) to 0 (right).
      const angle = n === 1 ? Math.PI / 2 : Math.PI - (c / (n - 1)) * Math.PI;
      slots.push({ angle, r: radii[r], row: r, col: c });
    }
  }
  slots.sort((a, b) => b.angle - a.angle);

  // Order parties left -> right: alliance-grouped when a resolver is given,
  // else seats-descending (chamber-left tradition: largest first).
  const ordered = orderArcParties(parties, alliance_of);

  // Walk slots in order, painting dots party-by-party.
  const dots: ArcDot[] = [];
  let s = 0;
  for (const p of ordered) {
    const fill = partyColourHex(p);
    for (let k = 0; k < p.seats_won && s < slots.length; k++, s++) {
      const sl = slots[s];
      dots.push({
        x: cx + sl.r * Math.cos(sl.angle),
        y: cy - sl.r * Math.sin(sl.angle),
        party_eci_code: p.party_eci_code,
        party_short: p.party_short,
        fill,
      });
    }
  }
  return { dots, dot_radius, max_radius: r_outer };
}
