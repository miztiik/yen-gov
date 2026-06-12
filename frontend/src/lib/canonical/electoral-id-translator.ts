// Electoral entity_id translator: bridges the per-state long-format
// CSV at `datasets/data/datapoints/electoral/<slug>_election_results.csv`
// (whose entity_ids use the ECI state code, e.g. `IN-S22-AC-2008-167`)
// to a natural-key tuple usable for joining against the canonical
// `datasets/data/entities/electoral.csv` (whose entity_ids use the LGD
// state slug + a heterogeneous suffix that may be either an LGD-
// sequential synthetic id OR the `eci<eci_no>` fallback for the 8% of
// 2008 rows missing from the LGD export — see commit 55dc91946 for the
// dual-suffix convention).
//
// Pure string substitution between the two id shapes is impossible
// because the LGD-sequential portion was assigned at LGD-snapshot
// ingest time and cannot be derived from the publisher-emitted
// `eci_no` alone. The reliable bridge is a natural-key JOIN on the
// 4-tuple `(entity_kind, delim_year, state, eci_no)` — `state` here is
// the LGD slug, which we look up from the ECI state code via the
// 36-entry `ECI_TO_SLUG` table below.
//
// Source of truth for the ECI<->slug map: `datasets/taxonomy/lgd_states.json`
// (`.states[].{eci_st_code, slug}`, 36 rows). Backend mirror:
// `backend/yen_gov/canonical/adapters/eci/state_slug.py`.

/** ECI st_code (S01..S29 / U01..U09) -> LGD-name slug. 36 rows. Hand-
 *  authored from `datasets/taxonomy/lgd_states.json`. */
export const ECI_TO_SLUG: Record<string, string> = {
  S01: "andhra-pradesh",
  S02: "arunachal-pradesh",
  S03: "assam",
  S04: "bihar",
  S05: "goa",
  S06: "gujarat",
  S07: "haryana",
  S08: "himachal-pradesh",
  S10: "karnataka",
  S11: "kerala",
  S12: "madhya-pradesh",
  S13: "maharashtra",
  S14: "manipur",
  S15: "meghalaya",
  S16: "mizoram",
  S17: "nagaland",
  S18: "odisha",
  S19: "punjab",
  S20: "rajasthan",
  S21: "sikkim",
  S22: "tamil-nadu",
  S23: "tripura",
  S24: "uttar-pradesh",
  S25: "west-bengal",
  S26: "chhattisgarh",
  S27: "jharkhand",
  S28: "uttarakhand",
  S29: "telangana",
  U01: "andaman-and-nicobar",
  U02: "chandigarh",
  U03: "dadra-and-nagar-haveli-and-daman-and-diu",
  U04: "lakshadweep",
  U05: "delhi",
  U07: "puducherry",
  U08: "jammu-and-kashmir",
  U09: "ladakh",
};

/** Reverse of `ECI_TO_SLUG`. Derived inline at module load. */
export const SLUG_TO_ECI: Record<string, string> = Object.fromEntries(
  Object.entries(ECI_TO_SLUG).map(([eci, slug]) => [slug, eci]),
);

/** Natural-key tuple identifying an AC or PC constituency across the
 *  per-state CSV and canonical electoral.csv. */
export interface PeerEntityKey {
  /** `'ac'` or `'pc'` (matches the lowercase `entity_kind` enum on
   *  `datasets/data/entities/electoral.csv`). */
  kind: "ac" | "pc";
  /** Delimitation year (e.g. 1976, 2008). */
  delim_year: number;
  /** LGD-name slug (e.g. `"tamil-nadu"`, `"andhra-pradesh"`). */
  slug: string;
  /** ECI eci_no — the publisher's per-constituency identifier within
   *  the state+delim. */
  eci_no: number;
}

/** Parse a per-state-CSV-shape entity_id into a natural-key tuple.
 *
 *  Recognised shapes:
 *    - AC: `IN-<eci_st_code>-AC-<delim_year>-<eci_no>`
 *      e.g. `IN-S22-AC-2008-167` -> `{kind:"ac", delim_year:2008, slug:"tamil-nadu", eci_no:167}`
 *    - PC: `IN-PC-<delim_year>-<eci_st_code>-<eci_no>`
 *      e.g. `IN-PC-2008-S22-25` -> `{kind:"pc", delim_year:2008, slug:"tamil-nadu", eci_no:25}`
 *
 *  Returns `null` for shapes that aren't AC/PC winner rows: party-
 *  aggregate (`IN-S22-AcGenApr2021-PARTY-DMK`), candidate
 *  (`IN-S22-AC-2008-167-AcGenMay2026-C03`), state-rollup
 *  (`IN-S22-AcGenMay2026`), electoral.csv-shape ids
 *  (`IN-AC-2008-tamil-nadu-4025`), unknown ECI state codes (defensive),
 *  and arbitrary garbage. */
export function parsePeerEntityId(id: string): PeerEntityKey | null {
  let m = id.match(/^IN-(S\d{2}|U\d{2})-AC-(\d{4})-(\d+)$/);
  if (m) {
    const slug = ECI_TO_SLUG[m[1]!];
    if (!slug) return null;
    return { kind: "ac", delim_year: Number(m[2]), slug, eci_no: Number(m[3]) };
  }
  m = id.match(/^IN-PC-(\d{4})-(S\d{2}|U\d{2})-(\d+)$/);
  if (m) {
    const slug = ECI_TO_SLUG[m[2]!];
    if (!slug) return null;
    return { kind: "pc", delim_year: Number(m[1]), slug, eci_no: Number(m[3]) };
  }
  return null;
}
