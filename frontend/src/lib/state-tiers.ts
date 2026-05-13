// State-tier (peer-set) loader and helpers.
//
// The taxonomy is in `datasets/reference/in/state-tiers.json`, validated
// against state-tiers.schema.json v1.0. Tiers may overlap (Sikkim is both
// `general_category` and `neh`); UTs partition cleanly into
// `ut_legislature` / `ut_no_legislature` / `nct_delhi`.
//
// Doctrine: tier identity is defined by what cites it, not by set
// equality. Don't fold near-duplicate tiers (e.g. `neh` vs `himalayan`)
// even when membership overlaps — they're cited by different policy
// documents and a future indicator may legitimately filter on one but
// not the other.

import { DATA_BASE } from "./paths";

export type DefinitionKind =
  | "constitutional"
  | "statutory"
  | "fc_derived"
  | "geographic"
  | "editorial"
  | "residual"
  | "research";

export interface StateTier {
  id: string;
  label: string;
  definition_kind: DefinitionKind;
  definition: string;
  authority?: string;
  authority_url?: string;
  members: string[];
  notes?: string;
}

export interface StateTiersFile {
  $schema: string;
  $schema_version: string;
  sources: Array<{ url: string; fetched_at: string }>;
  tiers: StateTier[];
}

/** Fetch the state-tier reference. Validated against state-tiers.schema.json v1.0. */
export async function fetchStateTiers(): Promise<StateTiersFile> {
  const res = await fetch(`${DATA_BASE}/reference/in/state-tiers.json`);
  if (!res.ok) {
    throw new Error(
      `fetch /reference/in/state-tiers.json failed: ${res.status} ${res.statusText}`,
    );
  }
  return (await res.json()) as StateTiersFile;
}

/**
 * Member ECI codes for a tier id. Returns `null` when the tier is unknown
 * so callers can distinguish "no such tier" from "empty membership"
 * (which is a real state for `research` tiers awaiting recon, e.g.
 * `fc_horizontal_devolution_share_quintile`).
 */
export function tierMembers(file: StateTiersFile | null, tier_id: string): string[] | null {
  if (!file) return null;
  const t = file.tiers.find(t => t.id === tier_id);
  return t ? t.members : null;
}

/**
 * Resolve a peer-set selector to the set of ECI codes it admits. The
 * sentinel `"all"` matches every state (returned as `null` so the caller
 * can skip filtering rather than having to compare against a 36-element
 * set). Empty membership for a real tier returns `[]` — the filter
 * applies and shows zero rows, which is the honest signal that the tier
 * is awaiting data (caller may choose to gracefully degrade to `"all"`).
 */
export function resolvePeerSet(
  file: StateTiersFile | null,
  selector: string,
): string[] | null {
  if (selector === "all") return null;
  return tierMembers(file, selector);
}

/** All tier ids whose membership is non-empty. Used to populate the filter UI. */
export function nonEmptyTierIds(file: StateTiersFile | null): string[] {
  if (!file) return [];
  return file.tiers.filter(t => t.members.length > 0).map(t => t.id);
}

/**
 * Reverse lookup: which tiers does this state belong to? Useful for
 * showing the citizen which peer sets a state participates in. Order is
 * the catalogue order (file order).
 */
export function tiersForState(file: StateTiersFile | null, eci_code: string): StateTier[] {
  if (!file) return [];
  return file.tiers.filter(t => t.members.includes(eci_code));
}
