// Pure derivation for AllianceTotals.svelte (PR-W3b, 2026-06-10).
//
// The Svelte component's $derived.by is too coupled to the runtime to
// unit-test without jsdom. This module exposes the same derivation as
// a pure function so the join can be exercised in node-env vitest.
// Mirror precedent: lib/route-crumbs.ts extracts breadcrumb builders
// out of GeoBreadcrumb.svelte for the same reason.

import type { AllianceLookup } from "../psephlab/types";

/** Per-entity winner row consumed by `deriveAllianceBreakdown`. */
export interface WinnerInput {
  party_id: string | null;
  party_short: string | null;
  party_eci_code?: string | null;
}

export interface AllianceTotal {
  alliance: string;
  seats: number;
}
export interface PartySeats {
  party_id: string;
  party_short: string;
  seats: number;
}
export interface AllianceBreakdown {
  /** Total-line order: declared alliances by seats desc; "Others" last. */
  rows: AllianceTotal[];
  /** alliance -> [parties under it, sorted by seats desc]. */
  by_alliance: Map<string, PartySeats[]>;
  /** True when at least one party belongs to a declared alliance.
   *  Drives the "alliance data pending" placeholder. */
  has_any: boolean;
}

/** Build the canonical party_id when the row didn't carry one. Matches
 *  the per-row fallback used elsewhere in the elections cascade
 *  (state-overview, national-elections). */
export function partyKey(w: WinnerInput): string {
  if (w.party_id) return w.party_id;
  const eci = w.party_eci_code ?? w.party_short ?? "UNK";
  return `parties.IN.${eci.toUpperCase()}`;
}

export function deriveAllianceBreakdown(
  winners: readonly WinnerInput[],
  lookup: AllianceLookup,
): AllianceBreakdown {
  const by_alliance = new Map<string, PartySeats[]>();
  const totals = new Map<string, number>();
  let has_any = false;
  // Per-party seat counts first; then bucket parties by alliance.
  const per_party = new Map<string, PartySeats>();
  for (const w of winners) {
    const pid = partyKey(w);
    const cur = per_party.get(pid);
    if (cur) {
      cur.seats += 1;
    } else {
      per_party.set(pid, {
        party_id: pid,
        party_short: w.party_short ?? "UNK",
        seats: 1,
      });
    }
  }
  for (const p of per_party.values()) {
    const alliance = lookup(p.party_id) ?? "Others";
    if (alliance !== "Others") has_any = true;
    const bucket = by_alliance.get(alliance) ?? [];
    bucket.push(p);
    by_alliance.set(alliance, bucket);
    totals.set(alliance, (totals.get(alliance) ?? 0) + p.seats);
  }
  for (const bucket of by_alliance.values()) {
    bucket.sort((a, b) => b.seats - a.seats);
  }
  const declared: AllianceTotal[] = [];
  let others_seats = 0;
  for (const [alliance, seats] of totals) {
    if (alliance === "Others") others_seats = seats;
    else declared.push({ alliance, seats });
  }
  declared.sort((a, b) => b.seats - a.seats);
  const rows: AllianceTotal[] = declared.slice();
  if (others_seats > 0) rows.push({ alliance: "Others", seats: others_seats });
  return { rows, by_alliance, has_any };
}
