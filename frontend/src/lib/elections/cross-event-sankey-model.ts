/**
 * cross-event-sankey-model: pure projection for R5 of
 * TODO/20260615-state-election-event-page-redesign-plan.md (2026-06-15).
 *
 * Two outputs from the same input pair (current + previous same-body
 * winners):
 *
 *  1. **Diverging bar (always-on)** - the structurally honest baseline.
 *     Per top-N party + a bucketed "Others", a signed integer delta of
 *     (seats_current - seats_prev). Positive bars extend right
 *     (emerald), negative left (rose). This is the load-bearing visual:
 *     it carries the real per-party gain/loss without any approximation
 *     about flow direction.
 *
 *  2. **Sankey actuals/scenario pair (opt-in)** - the approximate ribbon
 *     flow that the SwingSankey primitive consumes. Per Max + Jony's
 *     2026-06-15 verdict the Sankey is COLLAPSED by default behind a
 *     "Show vote-flow" pill; the caption (rendered when expanded)
 *     names the approximation: each loser party's net seat loss is
 *     redistributed to gainers in proportion to each gainer's net seat
 *     gain. The shape passes the prev winners as "actuals" and the
 *     current winners as "scenario" - SwingSankey already implements
 *     that diff arithmetic.
 *
 * No-prior case: when no previous same-body event exists, the section
 * renders the no-prior copy with no button and no DivergingBar. The
 * `no_prior` flag exposes that decision.
 */

import type { ElectionResultRow } from "../view-models/election-results";
import type { PartyResult } from "../psephlab/types";
import { getPartyColor } from "../colors/resolver";

/**
 * Loader state for the previous event's winners. The parent route
 * derives this from a Promise-based loader call + the
 * `previous_same_body` derive. R5's Svelte wrapper component
 * `StateEventCrossEventSankey.svelte` consumes this directly so the
 * citizen sees skeleton-on-loading / no-prior-on-first-event /
 * populated-when-ready without the component having to own the
 * fetch.
 */
export type PrevWinnersState =
  | { status: "no_prior" }
  | { status: "loading" }
  | { status: "ok"; rows: readonly ElectionResultRow[] }
  | { status: "failed"; reason: string };

/** Top-N + "Others" bucket value. */
export interface PartyDelta {
  party_id: string;
  party_short: string;
  seats_current: number;
  seats_prev: number;
  /** Signed seat delta: positive = gain vs prior, negative = loss. */
  delta: number;
  /** Brand color hex; resolved via the canonical 3-tier resolver. */
  color_hex: string;
  /** True for the synthetic "Others" bucket; false for real parties. */
  is_others: boolean;
}

export interface CrossEventSankeyModel {
  /** True when no prior same-body event exists - the section renders
   *  the no-prior copy with no button. */
  no_prior: boolean;
  /** Per-party signed delta. Sorted by max(seats_current, seats_prev)
   *  desc (so the visually largest parties read first); Others always
   *  last when present. Empty when no_prior is true. */
  diverging: PartyDelta[];
  /** Sankey input - the prev event's per-party totals consumed as
   *  "actuals" by SwingSankey. Empty when no_prior is true. */
  sankey_actuals: PartyResult[];
  /** Sankey input - the current event's per-party totals consumed as
   *  "scenario" by SwingSankey. Empty when no_prior is true. */
  sankey_scenario: PartyResult[];
}

/** Default top-N count for the diverging bar. */
export const DEFAULT_TOP_N = 6;

/**
 * Derive a stable party_id from a result row. Prefers the canonical
 * `party_id` when populated by the loader; falls back to
 * `parties.IN.<UPPER(short)>` for legacy producers that have not yet
 * propagated the field. Mirrors the helper inlined in StateElection.svelte
 * and PartyBar.svelte so the projection here can resolve the same
 * brand-color the citizen sees on the page.
 */
function partyIdFor(w: {
  party_id: string | null;
  party_short: string | null;
}): string {
  if (w.party_id) return w.party_id;
  const slug = (w.party_short ?? "UNK").trim().toUpperCase();
  return `parties.IN.${slug}`;
}

interface AggBucket {
  party_id: string;
  party_short: string;
  party_eci_code: string | null;
  seats: number;
  votes: number;
  brand_colour_hex: string | null;
  brand_colour_confidence: "high" | "medium" | "low" | null;
}

function aggregateByParty(rows: readonly ElectionResultRow[]): Map<string, AggBucket> {
  const by = new Map<string, AggBucket>();
  for (const r of rows) {
    const pid = partyIdFor(r);
    let b = by.get(pid);
    if (!b) {
      b = {
        party_id: pid,
        party_short: r.party_short ?? "UNK",
        party_eci_code: r.party_eci_code,
        seats: 0,
        votes: 0,
        brand_colour_hex: r.brand_colour_hex,
        brand_colour_confidence: r.brand_colour_confidence,
      };
      by.set(pid, b);
    }
    b.seats += 1;
    // Use the per-row vote-share-implied vote count when available;
    // matches the same pattern StateElection.svelte uses for the
    // top-parties aggregation. Skipped when missing - the Sankey is
    // an approximation anyway.
    if (r.votes_polled != null && r.vote_share_pct != null) {
      b.votes += (r.votes_polled * r.vote_share_pct) / 100;
    }
  }
  return by;
}

function bucketToPartyResult(b: AggBucket, total_votes: number): PartyResult {
  return {
    party_eci_code: b.party_eci_code ?? b.party_short,
    party_short: b.party_short,
    seats_won: b.seats,
    votes: Math.round(b.votes),
    vote_share_pct: total_votes > 0 ? (b.votes / total_votes) * 100 : 0,
    party_id: b.party_id,
    brand_colour_hex: b.brand_colour_hex,
    brand_colour_confidence: b.brand_colour_confidence,
  };
}

/**
 * Build the cross-event sankey model.
 *
 * Pure projection; deterministic given the same inputs. When
 * `previous` is null OR the previous winners array is empty, the
 * model returns `no_prior=true` and empty diverging / sankey arrays.
 */
export function buildCrossEventSankeyModel({
  current,
  previous,
  top_n = DEFAULT_TOP_N,
}: {
  current: readonly ElectionResultRow[];
  previous: readonly ElectionResultRow[] | null;
  top_n?: number;
}): CrossEventSankeyModel {
  if (!previous || previous.length === 0) {
    return {
      no_prior: true,
      diverging: [],
      sankey_actuals: [],
      sankey_scenario: [],
    };
  }

  const cur_by = aggregateByParty(current);
  const prev_by = aggregateByParty(previous);

  // Union of party_ids across both events.
  const all_ids = new Set<string>([...cur_by.keys(), ...prev_by.keys()]);

  // Build the full per-party delta list, then split into top-N + Others.
  interface ScoredDelta extends PartyDelta {
    sort_key: number;
  }
  const scored: ScoredDelta[] = [];
  for (const pid of all_ids) {
    const cur = cur_by.get(pid);
    const prev = prev_by.get(pid);
    const seats_current = cur?.seats ?? 0;
    const seats_prev = prev?.seats ?? 0;
    const delta = seats_current - seats_prev;
    // Prefer the current event's row for colour resolution (it's the
    // event the citizen is reading); fall back to prev when the party
    // is no longer contesting (or its rows dropped from the loader).
    const ref = cur ?? prev;
    if (!ref) continue;
    const color_hex = getPartyColor(pid, {
      party_id: pid,
      eci_code: ref.party_eci_code,
      brand_colour: ref.brand_colour_hex
        ? {
            hex: ref.brand_colour_hex,
            confidence: ref.brand_colour_confidence ?? "medium",
          }
        : null,
    }).hex;
    scored.push({
      party_id: pid,
      party_short: ref.party_short,
      seats_current,
      seats_prev,
      delta,
      color_hex,
      is_others: false,
      sort_key: Math.max(seats_current, seats_prev),
    });
  }

  // Sort by max(current, prev) desc so the visually largest parties
  // surface first. Ties broken by absolute delta desc so a 100-seat
  // party that moved 1 seat does NOT outrank a 100-seat party that
  // moved 30.
  scored.sort(
    (a, b) =>
      b.sort_key - a.sort_key ||
      Math.abs(b.delta) - Math.abs(a.delta) ||
      a.party_short.localeCompare(b.party_short),
  );

  const head = scored.slice(0, top_n);
  const tail = scored.slice(top_n);

  // Bucket the tail into one synthetic "Others" row when non-empty.
  // Color = slate-400 (#94a3b8) to read as residual.
  const others_seats_current = tail.reduce((s, r) => s + r.seats_current, 0);
  const others_seats_prev = tail.reduce((s, r) => s + r.seats_prev, 0);
  const diverging: PartyDelta[] = head.map(({ sort_key: _ignored, ...rest }) => {
    void _ignored;
    return rest;
  });
  if (tail.length > 0) {
    diverging.push({
      party_id: "__others__",
      party_short: "Others",
      seats_current: others_seats_current,
      seats_prev: others_seats_prev,
      delta: others_seats_current - others_seats_prev,
      color_hex: "#94a3b8",
      is_others: true,
    });
  }

  // Sankey input: full aggregated lists (not just top-N). The
  // approximation already collapses small movers into the ribbon
  // arithmetic; pre-bucketing them would over-collapse and hide real
  // small-party flows the citizen might want to inspect.
  const cur_total_votes = [...cur_by.values()].reduce((s, b) => s + b.votes, 0);
  const prev_total_votes = [...prev_by.values()].reduce((s, b) => s + b.votes, 0);
  const sankey_scenario: PartyResult[] = [...cur_by.values()].map((b) =>
    bucketToPartyResult(b, cur_total_votes),
  );
  const sankey_actuals: PartyResult[] = [...prev_by.values()].map((b) =>
    bucketToPartyResult(b, prev_total_votes),
  );

  return {
    no_prior: false,
    diverging,
    sankey_actuals,
    sankey_scenario,
  };
}
