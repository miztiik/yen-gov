// Psephlab engine type contracts.
//
// The engine is a pure function `run(actuals, scenario) -> Result`. These
// types are the contracts between the three layers:
//
//   loaders → Tallies → mutations → Tallies → counting rule → Result
//
// `Tallies` is intentionally narrow: every loader, mutation, and rule sees
// the same shape, so adding a new mutation or rule never reaches back into
// the loader. Schema bumps under `datasets/` translate at the loader edge.
//
// Mutations and rules are *plugins*: each is a value implementing the
// interfaces below, and registries (`mutations/index.ts`, `rules/index.ts`)
// expose them by id. New mutations/rules ship as new files; the engine
// itself doesn't change.

export interface Scope {
  country: "IN";
  state: string;
  election: string;
}

export interface CandidateTally {
  /** ECI party code, or "NOTA" / "IND" for the conventional sentinels. */
  party_eci_code: string;
  party_short: string;
  name: string;
  votes: number;
}

export interface AcTally {
  eci_no: number;
  name: string;
  /** Total electors registered in the AC. May be 0 when not published. */
  electorate: number;
  candidates: CandidateTally[];
}

export interface Tallies {
  scope: Scope;
  acs: AcTally[];
}

// ---------- Mutations ----------

/**
 * A mutation transforms one `Tallies` into another. The function is pure:
 * never mutates its input, returns a new `Tallies` (structural sharing of
 * unchanged ACs is fine).
 *
 * The `MutationConfig` is the discriminated union of all known mutation
 * payload shapes; concrete mutation modules narrow with their `id`.
 */
export type MutationConfig =
  | PerAcSwingConfig
  | StatewideSwingConfig
  | ThresholdDropConfig
  | PartyBagConfig;

export interface PerAcSwingConfig {
  id: "perAcSwing";
  /** AC eci_no this swing applies to. */
  eci_no: number;
  /** Source candidate parties. Many-to-one is allowed: votes are pulled from
   *  every listed party (clamped per-source to its available votes) and
   *  pooled into the destination. Single-element list = classic 1→1 swing. */
  from_party_eci_codes: string[];
  to_party_eci_code: string;
  to_candidate_name?: string;
  /** Total number of votes to move into the destination. The engine pulls
   *  proportionally from each `from_party_eci_codes` entry, clamping to
   *  what each one actually has. */
  votes: number;
}

export interface StatewideSwingConfig {
  id: "statewideSwing";
  /** Source parties. Many-to-one allowed; pct is applied to each source's
   *  per-AC votes and the result pooled into the destination. */
  from_party_eci_codes: string[];
  to_party_eci_code: string;
  /** Percentage of each from-party's votes to move, applied per-AC. 0..100. */
  pct: number;
}

export interface ThresholdDropConfig {
  id: "thresholdDrop";
  /** Drop candidates whose AC vote share is below this percent (0..100). */
  threshold_pct: number;
  /** Survivors split the freed votes proportionally to their pre-drop share. */
}

export interface PartyBagConfig {
  id: "partyBag";
  /** Display name shown in the legend. Must be unique within a scenario. */
  name: string;
  /** Member party ECI codes. Their candidates are merged into one synthetic
   *  candidate per AC (`name` = bag name, `party_eci_code` = `bag:<name>`). */
  members: string[];
  /** Optional override fill color (hex). Otherwise hashed from name. */
  color?: string;
}

export interface MutationPlugin<C extends MutationConfig = MutationConfig> {
  id: C["id"];
  /** Human-readable label for the UI. */
  label: string;
  /** Apply the mutation. Pure. */
  apply(tallies: Tallies, config: C): Tallies;
  /** Default config when the user adds this mutation from the UI. */
  defaultConfig(tallies: Tallies): C;
}

// ---------- Counting rules ----------

export interface PartyResult {
  party_eci_code: string;
  party_short: string;
  seats_won: number;
  votes: number;
  vote_share_pct: number;
}

export interface AcOutcome {
  eci_no: number;
  name: string;
  /** Winning candidate. Always set; ties broken by candidate-name asc. */
  winner: CandidateTally;
  runner_up: CandidateTally | null;
  margin_votes: number;
  margin_pct: number;
}

export interface SeatAllocation {
  by_party: PartyResult[];
  by_ac: AcOutcome[];
  /** Total votes counted across all ACs (after mutations). */
  total_votes: number;
}

export interface CountingRule {
  id: string;
  label: string;
  apply(tallies: Tallies): SeatAllocation;
}

// ---------- Scenarios ----------

export interface Scenario {
  /** Format version. Current: 1. Loaders refuse unknown versions. */
  v: 1;
  rule: string;
  mutations: MutationConfig[];
  /** ECI-code → hex color overrides. Only entries that differ from defaults. */
  colors?: Record<string, string>;
}

export interface RunResult {
  /** The mutated tallies fed to the counting rule. */
  mutated: Tallies;
  /** Output of the counting rule. */
  allocation: SeatAllocation;
  /** Same shape as `allocation.by_party` but for the unmutated actuals,
   *  for delta rendering. */
  actuals_allocation: SeatAllocation;
}
