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
  /**
   * Canonical taxonomy id (e.g. `parties.IN.DMK`). Required as of
   * PR-SYM-6g2 (closes PR-SYM-6g #595 optional carve-out). The canonical
   * loader populates this via the dim_parties JOIN; hand-built test
   * fixtures synthesise `parties.IN.<eci_code>` (or `parties.IN.NOTA` /
   * `parties.IN.IND` for sentinels) inline. See `partyIdFor` in
   * `psephlab/colour-bridge.ts`.
   */
  party_id: string;
  /**
   * Wikipedia-sourced brand colour from dim_parties.brand_colour_hex.
   * Forwarded to the 3-tier resolver as Tier-2 input.
   */
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
  /**
   * Sanitised party ballot-symbol asset path from
   * `dim_parties.election_symbol_asset_path` (e.g. `"party-symbols/lotus.svg"`).
   * Threaded through so the ParliamentArc symbol-ring legend can render
   * a glyph next to the party token without a second dim_parties query.
   * Optional; null when the symbol is not yet curated or the party is
   * the synthetic NOTA / IND sentinel.
   */
  election_symbol_asset_path?: string | null;
}

export interface AcTally {
  eci_no: number;
  name: string;
  /** Total electors registered in the AC. May be 0 when not published. */
  electorate: number;
  candidates: CandidateTally[];
}

/**
 * Per-(party_id) alliance label at the time of the active election event.
 * Returned by `lib/psephlab/alliances.ts::loadAlliances(event)`. Returns
 * `null` for a party with no curated alliance row for the event - the
 * caller (alliance-aware counting rule) treats null as "unallied" and
 * falls back to its proportional sibling for that party's transfer.
 *
 * Per Fowler verdict (2026-06-09 round 2): the lookup is a function, not
 * a Map, so rules carry zero CSV knowledge and tests can inject a 3-line
 * stub `() => null` for the no-alliance branch.
 */
export type AllianceLookup = (party_id: string) => string | null;

export interface Tallies {
  scope: Scope;
  acs: AcTally[];
  /**
   * Optional party-to-alliance lookup for the active election event.
   * Populated by `canonical-loaders.ts::loadActuals` via
   * `lib/psephlab/alliances.ts::loadAlliances(event)`. Two alliance-aware
   * rules (TRS Round 2 alliance + Ranked-choice alliance-transfer) read
   * this; every other rule ignores it. When the CSV has no rows for
   * the active event the field is `() => null` (transparent fallback),
   * NOT undefined - downstream code can call without guarding.
   */
  alliances?: AllianceLookup;
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
  /** One-sentence tooltip shown on hover of the info icon in the UI. */
  summary: string;
  /**
   * Anchor (without leading `#`) inside `docs/architecture/frontend/psephlab.md`
   * that the info icon deep-links to. The UI prefixes the repo blob URL.
   */
  docs_anchor: string;
  /**
   * Counting-rule ids this mutation is meaningful under. Omit (or set
   * undefined) to apply under every rule. Per Fowler verdict
   * (2026-06-09): each mutation OWNS the constraint that defines when
   * its effect is visible. perAcSwing and thresholdDrop are per-AC
   * vote transfers that preserve state-wide totals - they have zero
   * visible effect under Proportional, which aggregates state-wide.
   * statewideSwing and partyBag DO change state-wide totals so they
   * stay rule-agnostic.
   *
   * The Psephlab "+ Add what-if" menu filters MUTATIONS by
   * `applicableMutationsFor(rule_id)` (lib/psephlab/applicable-mutations.ts).
   * Already-encoded scenarios with disallowed mutations are kept-but-
   * struck-through with explanatory micro-copy (never silently dropped
   * - share-URL contract).
   */
  allowed_rules?: ReadonlyArray<string>;
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
  /**
   * Canonical taxonomy id. Required as of PR-SYM-6g2. Propagated from the
   * first CandidateTally row contributing to this party total by
   * `rules/fptp.ts` (CandidateTally.party_id is itself required).
   */
  party_id: string;
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
  /**
   * Sanitised party ballot-symbol asset path (forwarded from the
   * first CandidateTally contributing to this party). Used by the
   * ParliamentArc symbol-ring legend to render the glyph next to each
   * party. Optional; null when the symbol is not curated.
   */
  election_symbol_asset_path?: string | null;
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
  /**
   * Optional chamber size override for rules that allocate beyond the
   * constituency count. Defaults to `tallies.acs.length` when absent.
   *
   * Required by Mixed-Member Proportional (MMP), which keeps all
   * constituency winners AND adds list-tier seats - the chamber grows
   * by the list-tier count (round-2 addition). Every other rule omits
   * this field; the host (Psephlab.svelte) reads it via
   * `allocation.chamber_seats ?? tallies.acs.length` so ParliamentArc +
   * majority math + summary strip stay consistent.
   */
  chamber_seats?: number;
}

/**
 * Validity tier for a counting rule. Surfaced inline on the MethodPicker
 * card + the hero explanation so the citizen knows whether the method's
 * output is a mechanical re-arrangement of FPTP data (fully_workable) or
 * rests on a load-bearing assumption that India does not publish data
 * for (medium_validity). Hans-non-negotiable: this MUST stay inline -
 * hiding it would be a more subtle form of dishonesty than the Round-1
 * "HYPOTHETICAL RECOUNT" banner. See Hans verdict round 2 section 9.
 *
 * - `fully_workable`: every input the rule consumes is in the FPTP
 *   ballot. Examples: FPTP, Proportional (D'Hondt / Sainte-Lague /
 *   Hamilton), MMP. Includes Approval-as-cast (the cleanest example
 *   of the tier's lower bound - the rule operates exactly, the
 *   answer happens to mirror FPTP).
 * - `medium_validity`: the rule REQUIRES data India does not collect
 *   (ranked ballots, alliance-transfer preferences, pairwise rankings).
 *   The simulator holds an explicit assumption constant so the rule
 *   can operate; the assumption is named in `assumptions[]` and the
 *   load-bearing one is repeated as a hero-card line.
 */
export type ValidityTier = "fully_workable" | "medium_validity";

export interface CountingRule {
  id: string;
  label: string;
  apply(tallies: Tallies): SeatAllocation;
  /**
   * Optional honesty-marker text shown alongside `ImaginingCard`
   * when the rule represents a counterfactual rather than the official
   * result. FPTP (the official method) omits this field; rules added per
   * E6 sub-plan (TODO/20260608-e6-user-override-and-pl2-pl3-execution-subplan.md)
   * MUST set it.
   */
  caveat?: string;
  /**
   * Optional list of structured assumptions the simulator makes (e.g.
   * "Voters cast the same ballots as under FPTP"). Surfaced as bullets
   * inside the ImaginingCard so the citizen sees the load-bearing
   * assumptions inline with the counterfactual seat tally.
   */
  assumptions?: string[];
  /**
   * When true, the host UI (Psephlab) mounts `ImaginingCard`
   * above the result panel. FPTP and any other "official-result" rule
   * omits this; counterfactual rules (Sainte-Lague PR, IRV, Approval)
   * set it to true.
   */
  requires_banner?: boolean;
  /**
   * Validity tier. Required as of round 2 (2026-06-09). FPTP is
   * fully_workable (it IS the data). PR variants + MMP are
   * fully_workable (mechanical re-arrangement). Approval is
   * fully_workable (the rule operates exactly; the answer mirrors
   * FPTP). Ranked-choice + Borda + Condorcet + TRS-r2 variants are
   * medium_validity (require ranked-ballot / alliance / pairwise
   * data India does not publish).
   */
  validity: ValidityTier;
  /**
   * Optional one-line headline (<= 12 words, encouraging-visionary
   * register) shown above the hero explanation card. Defaults to
   * generated copy when absent. Hans's round-2 headline + per-method
   * rewrites should be the source.
   */
  headline?: string;
  /**
   * Optional citizen-readable short label (<= 30 chars, encouraging
   * tone) for the MethodPicker chip + the URL pill. Falls back to
   * `label` when absent. Round-2 picker reads this preferentially.
   */
  short_label?: string;
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
