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
  /** Wikipedia brand hue for the party, when joined. Threaded through so
   *  the breakdown can colour each party's seat-bar segment. */
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
}

export interface PartySeats {
  party_id: string;
  party_short: string;
  party_eci_code?: string | null;
  seats: number;
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
  /** Key in the page's `hidden_parties` mute space
   *  (`party_eci_code ?? party_short`), so an alliance/party group can be
   *  bulk-muted without re-deriving the key. */
  mute_key: string;
}

/** A ranked competitive unit on the headline: either a declared pre-poll
 *  alliance (seats summed over members) OR a single non-aligned party large
 *  enough to stand on its own (see the promotion rule in
 *  `deriveAllianceBreakdown`). Modelling a lone party as a "force" is what
 *  stops the genuinely-largest party being buried inside "Others". */
export type ForceKind = "alliance" | "party";

export interface Force {
  /** Stable key for `{#each}` and mute grouping. */
  key: string;
  /** Display name: alliance short name, or the lone party's short name. */
  name: string;
  kind: ForceKind;
  seats: number;
  /** Member parties, seats desc. A lone-party force has a single member. */
  members: PartySeats[];
  /** Mute keys for every member (drives the per-force mute toggle). */
  mute_keys: string[];
}

export interface AllianceBreakdown {
  /** Declared alliances + promoted lone non-aligned parties, ranked by
   *  seats desc (name asc tie-break). The headline reads the top two. */
  forces: Force[];
  /** Residual non-aligned parties below the promotion bar, seats desc. */
  others: PartySeats[];
  /** Total seats held by the residual "Others" bucket. */
  others_seats: number;
  /** All seats won across forces + others (denominator for seat-share). */
  total_seats: number;
  /** Seats for an outright majority: floor(total/2)+1; 0 when no seats.
   *  A force earns the emerald "majority" accent only at/above this. */
  majority_threshold: number;
  /** True when at least one party belongs to a declared alliance. The
   *  panel is suppressed entirely (R6 honesty rule) when false. */
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
  // 1. Per-party seat counts (one PartySeats per distinct party).
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
        party_eci_code: w.party_eci_code ?? null,
        seats: 1,
        brand_colour_hex: w.brand_colour_hex ?? null,
        brand_colour_confidence: w.brand_colour_confidence ?? null,
        mute_key: w.party_eci_code ?? w.party_short ?? "UNK",
      });
    }
  }

  let total_seats = 0;
  for (const p of per_party.values()) total_seats += p.seats;
  const majority_threshold =
    total_seats > 0 ? Math.floor(total_seats / 2) + 1 : 0;

  // 2. Bucket each party into its declared alliance, or the unaligned pool.
  const alliance_members = new Map<string, PartySeats[]>();
  const alliance_seats = new Map<string, number>();
  const unaligned: PartySeats[] = [];
  let has_any = false;
  for (const p of per_party.values()) {
    const alliance = lookup(p.party_id);
    if (alliance) {
      has_any = true;
      const bucket = alliance_members.get(alliance) ?? [];
      bucket.push(p);
      alliance_members.set(alliance, bucket);
      alliance_seats.set(alliance, (alliance_seats.get(alliance) ?? 0) + p.seats);
    } else {
      unaligned.push(p);
    }
  }
  for (const bucket of alliance_members.values()) {
    bucket.sort((a, b) => b.seats - a.seats);
  }

  // 3. Declared-alliance forces.
  const alliance_forces: Force[] = [];
  for (const [name, members] of alliance_members) {
    alliance_forces.push({
      key: `alliance:${name}`,
      name,
      kind: "alliance",
      seats: alliance_seats.get(name) ?? 0,
      members,
      mute_keys: members.map((m) => m.mute_key),
    });
  }

  // 4. Promotion bar (Max relational rule, parameter-free): a non-aligned
  //    party at least as large as the SMALLEST declared alliance stands as
  //    its own force, so the genuinely-largest party is never buried in
  //    "Others"; everything smaller falls to the residual bucket. When no
  //    alliance is declared the panel is suppressed (has_any=false), so the
  //    bar is +Infinity and nobody is promoted.
  const min_declared =
    alliance_forces.length > 0
      ? Math.min(...alliance_forces.map((f) => f.seats))
      : Number.POSITIVE_INFINITY;

  const party_forces: Force[] = [];
  const others: PartySeats[] = [];
  for (const p of unaligned) {
    if (p.seats >= min_declared) {
      party_forces.push({
        key: `party:${p.party_id}`,
        name: p.party_short,
        kind: "party",
        seats: p.seats,
        members: [p],
        mute_keys: [p.mute_key],
      });
    } else {
      others.push(p);
    }
  }
  others.sort((a, b) => b.seats - a.seats);
  let others_seats = 0;
  for (const p of others) others_seats += p.seats;

  // 5. Rank all forces by seats desc; name asc tie-break keeps the order
  //    deterministic across re-renders and across states/years.
  const forces = [...alliance_forces, ...party_forces].sort(
    (a, b) => b.seats - a.seats || a.name.localeCompare(b.name),
  );

  return {
    forces,
    others,
    others_seats,
    total_seats,
    majority_threshold,
    has_any,
  };
}
