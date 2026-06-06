// countSeats(method, candidacies, rules) - swappable counting-method seam.
//
// Per parent plan section 25.6b-seam (`TODO/20260603-data-and-charting-platform-reset-plan.md`):
//
//   "a pure function `countSeats(method, candidacies, rules) -> SeatTally`
//    where `method = "fptp"` is the only shipped implementation. `SeatTally`
//    is the exact contract `ParliamentArc` / `SeatDonut` / `RacesBoard`
//    already consume."
//
// Today FPTP is the ONLY shipped method. Alternate methods (ranked-choice,
// approval, proportional what-ifs) are E6 territory and gated behind a
// Citizen + Hans second opinion + a "hypothetical recount, not official
// result" honesty banner; see plan section 25.6 / chunk E6. This seam
// pre-shapes the contract so the future swap is a renderer-free change.
//
// Hard invariant (per plan section 25.6a / gate `seats-invariant-test`):
//
//   sum over parties of seats_won  ==  total_seats
//                                  ==  count of DISTINCT constituencies
//                                       in the (state, year) result
//
// `assertSeatTallyInvariant` is the boundary check every consumer (state-
// overview view-model, Psephlab FPTP rule) MUST call BEFORE handing a
// SeatTally to ParliamentArc / SeatDonut / RacesBoard. Failures throw with
// the actual numbers in the message - never silently halve, never clamp.
// (Plan section 25.6a wording: "fail-fast, fix the join, never silently
// halve".)

/** Counting method discriminator. Today only "fptp" is implemented; the
 *  remaining values are reserved for E6 sub-plan and throw at the call site. */
export type SeatTallyMethod =
  | "fptp"
  | "ranked-choice"
  | "approval"
  | "proportional";

/** One party row in a tally. `party_id` is the canonical taxonomy id
 *  (`parties.IN.<SLUG>` for real parties, `OTHER` for the
 *  unattributed-winner bucket the long-tail TCPD shortcodes collapse into,
 *  `parties.IN.NOTA` / `parties.IN.IND` for the conventional sentinels). */
export interface SeatTallyParty {
  readonly party_id: string;
  readonly seats_won: number;
}

/** The exact contract `ParliamentArc` / `SeatDonut` / `RacesBoard` consume
 *  for the COUNTING SIDE (display fields like party_short, brand_colour,
 *  vote_share_pct are merged in by the caller). */
export interface SeatTally {
  readonly total_seats: number;
  readonly parties: ReadonlyArray<SeatTallyParty>;
}

/** Rule overrides per method. Empty for FPTP; future methods (ranked-choice
 *  quota thresholds, proportional divisor) place their knobs here. */
export interface SeatTallyRules {
  // No-op for FPTP; placeholder for future methods.
  readonly _seam_version?: 1;
}

/** Flat candidacy row. Same shape state-overview's per-AC SQL produces and
 *  Psephlab's fptp rule iterates. `position` is the rank-after-counting
 *  (1 = winner; rank ties broken by name-asc per ECI convention). */
export interface SeatTallyCandidacyRow {
  readonly entity_id: string;
  readonly party_id: string | null;
  readonly position: number;
}

/** Count seats for a (state, year) result. FPTP today; throws for any
 *  other method (E6 sub-plan gates ranked-choice / approval / proportional). */
export function countSeats(
  method: SeatTallyMethod,
  candidacies: ReadonlyArray<SeatTallyCandidacyRow>,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  rules: SeatTallyRules = {},
): SeatTally {
  if (method !== "fptp") {
    throw new Error(
      `countSeats: unsupported method "${method}" (only "fptp" is shipped today; ` +
        `alternate methods are E6 sub-plan and require a Citizen + Hans ` +
        `second opinion plus a "hypothetical recount, not official result" ` +
        `honesty banner - section 25.6b-seam).`,
    );
  }

  // FPTP: one winner per constituency = one seat per constituency.
  // Build winners-by-constituency from position=1 rows. If the input
  // accidentally carries TWO position=1 rows for the same entity_id
  // (e.g. a JOIN double-count), the Map collapses them to one - the
  // sum invariant catches the upstream bug at the assertion boundary
  // rather than masking it here. Defensive: prefer the FIRST seen.
  const winnersByConstituency = new Map<string, string | null>();
  for (const row of candidacies) {
    if (row.position === 1 && !winnersByConstituency.has(row.entity_id)) {
      winnersByConstituency.set(row.entity_id, row.party_id);
    }
  }

  const total_seats = winnersByConstituency.size;

  // Aggregate party wins. NULL party_id rows stay unattributed (per
  // orchestrator section 25.6b-seam comment: "unbindable party_id stays
  // unattributed"). Callers that need a strict sum-equals-total invariant
  // (e.g. the state-overview SQL which COALESCEs to 'OTHER') should
  // pre-coalesce nulls BEFORE calling countSeats; assertSeatTallyInvariant
  // enforces equality not <=.
  const tally = new Map<string, number>();
  for (const party_id of winnersByConstituency.values()) {
    if (party_id == null) continue;
    tally.set(party_id, (tally.get(party_id) ?? 0) + 1);
  }

  // Stable order: seats_won DESC, party_id ASC (deterministic tiebreak).
  const parties: SeatTallyParty[] = [...tally.entries()]
    .map(([party_id, seats_won]) => ({ party_id, seats_won }))
    .sort(
      (a, b) =>
        b.seats_won - a.seats_won || a.party_id.localeCompare(b.party_id),
    );

  return Object.freeze({ total_seats, parties: Object.freeze(parties) });
}

/** Throws if `sum over parties of seats_won != total_seats`. The whole
 *  point of the seam: every consumer (state-overview view-model,
 *  Psephlab fptp rule) MUST gate its SeatTally through this before
 *  handing the tally to ParliamentArc / SeatDonut / RacesBoard. Fixes
 *  the ~2x double-count regression class (plan section 25.6a). */
export function assertSeatTallyInvariant(
  tally: SeatTally,
  label?: string,
): void {
  const sum = tally.parties.reduce((s, p) => s + p.seats_won, 0);
  if (sum !== tally.total_seats) {
    const ctx = label ? ` (${label})` : "";
    throw new Error(
      `SeatTally invariant violated${ctx}: sum(seats_won)=${sum} != ` +
        `total_seats=${tally.total_seats}. The seats feed double-counted ` +
        `or under-counted upstream; see plan section 25.6a / gate ` +
        `seats-invariant-test.`,
    );
  }
}
