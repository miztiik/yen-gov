/**
 * seat-flow-model: FACTUAL seat-transition projection for gap-closure G5
 * (TODO/20260616-state-event-page-gap-closure-plan.md).
 *
 * Replaces the vote-flow APPROXIMATION (cross-event-sankey-model +
 * SwingSankey) with the exact hold/loss matrix the user asked for: "for a
 * given constituency a party either holds or loses to another, so we can
 * sum up across parties and draw a Sankey".
 *
 * Mechanism (exact, not estimated): each constituency (AC/PC) has exactly
 * one winner in the prior event and one in the current event. Joining the
 * two winner sets on `entity_id` yields, per seat, a `(prev_party ->
 * curr_party)` transition. A seat where the same party won both times is a
 * HOLD (self-loop); a seat that changed hands is a FLIP. Summing the
 * transitions across all seats gives the flow matrix. Ribbon width = number
 * of seats. No vote redistribution, no proportional estimate - every ribbon
 * is a literal seat count.
 *
 * Delimitation guard: a current seat whose `entity_id` has no prior-event
 * match (boundary redraw, new state, first contest) is counted as
 * `unmatched` and surfaced as a distinct "New / redrawn" source node rather
 * than silently dropped. The caller surfaces the unmatched count in the
 * caption (ESCALATE trigger in the plan-doc when the rate is high).
 */

import type { ElectionResultRow } from "../view-models/election-results";

/**
 * Loader state for the previous event's winners. The parent route derives
 * this from a Promise-based loader call + the `previous_same_body` derive;
 * the Sankey component consumes it directly so the citizen sees
 * skeleton-on-loading / no-prior-on-first-event / populated-when-ready
 * without the component owning the fetch. (Relocated from the retired
 * cross-event-sankey-model in gap-closure G5.)
 */
export type PrevWinnersState =
  | { status: "no_prior" }
  | { status: "loading" }
  | { status: "ok"; rows: readonly ElectionResultRow[] }
  | { status: "failed"; reason: string };

/** A node on one side of the Sankey (a party, or the synthetic
 *  "Others" / "New seat" buckets). */
export interface SeatFlowNode {
  /** Canonical party id, or a synthetic key for the buckets
   *  ("__others__" / "__new__"). */
  key: string;
  /** Citizen-readable label ("BJP", "Others", "New / redrawn"). */
  label: string;
  /** Total seats this node carries on its side. */
  seats: number;
  /** True for the synthetic Others / New buckets (no party identity). */
  is_bucket: boolean;
  /** Party id for colour resolution; null for buckets. */
  party_id: string | null;
}

/** A flow ribbon from a left (prior) node to a right (current) node. */
export interface SeatFlow {
  from_key: string;
  to_key: string;
  /** Number of seats that moved along this edge. */
  seats: number;
  /** True when from_key === to_key (a HOLD / self-loop). */
  is_hold: boolean;
}

export interface SeatFlowModel {
  /** Left column = prior-event winners (+ "New / redrawn" when unmatched). */
  left: SeatFlowNode[];
  /** Right column = current-event winners. */
  right: SeatFlowNode[];
  /** Aggregated transition ribbons. */
  flows: SeatFlow[];
  /** Headline counts (exact). */
  total_seats: number;
  holds: number;
  flips: number;
  /** Current seats with no prior match (delimitation / new contest). */
  unmatched: number;
  /** True when no prior event exists - the section renders the no-prior copy. */
  no_prior: boolean;
}

const OTHERS_KEY = "__others__";
const NEW_KEY = "__new__";

/** Derive a stable party id from a winner row. Mirrors the helper used
 *  across the election surfaces so the colour resolver keys identically. */
function partyIdFor(w: {
  party_id: string | null;
  party_short: string | null;
}): string {
  if (w.party_id) return w.party_id;
  const slug = (w.party_short ?? "UNK").trim().toUpperCase();
  return `parties.IN.${slug}`;
}

/** Pick the single winner row per entity_id. The loader projects one
 *  winner row per seat at STATE-AC / NATIONAL-PC scope, but guard against
 *  duplicate candidate rows (CONSTITUENCY scope) by keeping the
 *  `is_winner` row, falling back to the first row seen. */
function winnersByEntity(
  rows: readonly ElectionResultRow[],
): Map<string, ElectionResultRow> {
  const out = new Map<string, ElectionResultRow>();
  for (const r of rows) {
    const existing = out.get(r.entity_id);
    if (!existing) {
      out.set(r.entity_id, r);
    } else if (!existing.is_winner && r.is_winner) {
      out.set(r.entity_id, r);
    }
  }
  return out;
}

export interface BuildSeatFlowInput {
  current: readonly ElectionResultRow[];
  previous: readonly ElectionResultRow[] | null;
  /** Max distinct parties per side before bucketing into "Others".
   *  Default 6 (matches the vote-flow precedent + keeps the diagram
   *  readable on mobile). */
  topN?: number;
}

/**
 * Build the factual seat-flow model. Pure: no DOM, no fetch, no colour
 * resolution (the component resolves colours off `party_id` so the model
 * stays testable in node).
 */
export function buildSeatFlowModel(input: BuildSeatFlowInput): SeatFlowModel {
  const { current, previous, topN = 6 } = input;

  if (!previous || previous.length === 0) {
    return {
      left: [],
      right: [],
      flows: [],
      total_seats: 0,
      holds: 0,
      flips: 0,
      unmatched: 0,
      no_prior: true,
    };
  }

  const curr = winnersByEntity(current);
  const prev = winnersByEntity(previous);

  // Per-seat transitions keyed by (prev_pid -> curr_pid).
  const flowCounts = new Map<string, number>();
  const leftSeats = new Map<string, { label: string; party_id: string; seats: number }>();
  const rightSeats = new Map<string, { label: string; party_id: string; seats: number }>();
  let holds = 0;
  let flips = 0;
  let unmatched = 0;

  function bump(
    map: Map<string, { label: string; party_id: string; seats: number }>,
    pid: string,
    label: string,
  ): void {
    const e = map.get(pid);
    if (e) e.seats += 1;
    else map.set(pid, { label, party_id: pid, seats: 1 });
  }

  for (const [entity_id, cw] of curr) {
    const currPid = partyIdFor(cw);
    const currLabel = cw.party_short ?? "UNK";
    bump(rightSeats, currPid, currLabel);

    const pw = prev.get(entity_id);
    if (!pw) {
      // No prior winner for this seat - delimitation / new contest.
      unmatched += 1;
      const fk = `${NEW_KEY}->${currPid}`;
      flowCounts.set(fk, (flowCounts.get(fk) ?? 0) + 1);
      continue;
    }
    const prevPid = partyIdFor(pw);
    const prevLabel = pw.party_short ?? "UNK";
    bump(leftSeats, prevPid, prevLabel);

    if (prevPid === currPid) holds += 1;
    else flips += 1;

    const fk = `${prevPid}->${currPid}`;
    flowCounts.set(fk, (flowCounts.get(fk) ?? 0) + 1);
  }

  // Rank parties for each side by seats; bucket the long tail into Others.
  function rankAndBucket(
    map: Map<string, { label: string; party_id: string; seats: number }>,
  ): { nodes: SeatFlowNode[]; keptKeys: Set<string> } {
    const sorted = [...map.values()].sort((a, b) => b.seats - a.seats);
    const kept = sorted.slice(0, topN);
    const tail = sorted.slice(topN);
    const keptKeys = new Set(kept.map((k) => k.party_id));
    const nodes: SeatFlowNode[] = kept.map((k) => ({
      key: k.party_id,
      label: k.label,
      seats: k.seats,
      is_bucket: false,
      party_id: k.party_id,
    }));
    if (tail.length > 0) {
      nodes.push({
        key: OTHERS_KEY,
        label: "Others",
        seats: tail.reduce((s, t) => s + t.seats, 0),
        is_bucket: true,
        party_id: null,
      });
    }
    return { nodes, keptKeys };
  }

  const leftRanked = rankAndBucket(leftSeats);
  const rightRanked = rankAndBucket(rightSeats);

  // Map a raw party key to its display key (itself when kept, else Others).
  function leftDisplayKey(pid: string): string {
    if (pid === NEW_KEY) return NEW_KEY;
    return leftRanked.keptKeys.has(pid) ? pid : OTHERS_KEY;
  }
  function rightDisplayKey(pid: string): string {
    return rightRanked.keptKeys.has(pid) ? pid : OTHERS_KEY;
  }

  // Re-aggregate flows onto display keys (so Others collapses correctly).
  const displayFlows = new Map<string, number>();
  for (const [fk, n] of flowCounts) {
    const [fromRaw, toRaw] = fk.split("->");
    const from = leftDisplayKey(fromRaw);
    const to = rightDisplayKey(toRaw);
    const dk = `${from}->${to}`;
    displayFlows.set(dk, (displayFlows.get(dk) ?? 0) + n);
  }

  const left: SeatFlowNode[] = [...leftRanked.nodes];
  if (unmatched > 0) {
    left.push({
      key: NEW_KEY,
      label: "New / redrawn",
      seats: unmatched,
      is_bucket: true,
      party_id: null,
    });
  }

  const flows: SeatFlow[] = [...displayFlows.entries()]
    .map(([dk, seats]) => {
      const [from_key, to_key] = dk.split("->");
      return {
        from_key,
        to_key,
        seats,
        is_hold: from_key === to_key && from_key !== OTHERS_KEY && from_key !== NEW_KEY,
      };
    })
    .sort((a, b) => b.seats - a.seats);

  return {
    left,
    right: rightRanked.nodes,
    flows,
    total_seats: curr.size,
    holds,
    flips,
    unmatched,
    no_prior: false,
  };
}
