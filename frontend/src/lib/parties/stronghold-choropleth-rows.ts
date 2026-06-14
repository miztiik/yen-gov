// PR-12 of TODO/20260613-party-deferred-followups-plan.md section 14.
//
// Pure mappers + palette helpers for `PartyStrongholdMap.svelte`. Lives
// outside the .svelte file so vitest (node-env, no DOM) covers the join
// + bucket + palette math directly. The .svelte component consumes
// these via `<script module>` re-export.
//
// Doctrine ties:
//   - Pure functions only. No DOM, no fetches, no Svelte runes.
//   - Row shape stays minimal: `(entity_key, wins, contested, bucket,
//     constituency_name, state, results)`. The component never reads
//     the original mart row shape directly.
//   - Tested by `stronghold-choropleth-rows.test.ts` (sibling file).
//
// Path-A oracle reframing (from the orchestrator brief): the plan-doc
// originally called for the choropleth to colour "all 22 DMK PCs from
// LS 2024" but the existing strongholds mart at
// `datasets/data/marts/party_pages/strongholds.csv` is top-10 PER
// (party, body) by LIFETIME wins (see `backend/yen_gov/canonical/derived/
// party_pages.py` line 419). Backend regen is forbidden by the brief;
// the citizen-facing oracle is therefore reframed to "the party's
// top-10 lifetime-strongholds per body, coloured by win-count bucket".
// The caption surfaced in `PartyStrongholdMap.svelte` makes this
// citizen-honest ("Stronghold map shows this party's top-10
// constituencies by lifetime wins").

import type { PartyStronghold } from "../view-models/party-detail";

/** Discrete bucket per win-count cohort. Six categorical states span
 *  the full [absent, all-time-sweeper] range so the same palette
 *  reads consistently across parties of any scale. */
export type StrongholdBucket =
  /** PC is not in this party's stronghold mart row set (the party
   *  either never contested OR never finished in top-10 for this
   *  constituency). Rendered as the diagonal hatch. */
  | "absent"
  /** PC is in the stronghold mart but `wins == 0` (defensive: the
   *  mart writer filters wins>=1 so this branch is unreachable in
   *  practice; keeping the bucket so the test surface is total). */
  | "zero"
  /** Exactly one win on record. */
  | "one"
  /** Exactly two wins on record. */
  | "two"
  /** Three or four wins on record. */
  | "three-four"
  /** Five or more wins on record. The top-10 cohort rarely reaches
   *  this bucket; we keep the band so the same scale fits parties
   *  with very long contest histories (BSP UP 1989-2024 spans ~10
   *  state-assembly cycles + ~9 LS cycles). */
  | "five-plus";

/** Bucket order from "less" (absent) to "more" (five-plus). Exported
 *  so tests and the component can iterate in a stable visual order. */
export const BUCKET_ORDER: readonly StrongholdBucket[] = Object.freeze([
  "absent",
  "zero",
  "one",
  "two",
  "three-four",
  "five-plus",
]);

/** The minimal row shape `PartyStrongholdMap` consumes. */
export interface StrongholdChoroplethRow {
  /** Joining key matched against `feature.properties[feature_key]`
   *  on the topojson side. For PCs: `${state_ut_code}_${ls_seat_code}`
   *  (e.g. "S22_10" for Dharmapuri). */
  entity_key: string;
  /** Raw win count (always >= 1 for mart rows; null is invalid). */
  wins: number;
  /** Total events held in this constituency on the canonical store. */
  contested: number;
  /** Discrete categorical bucket; see `bucketFromWins`. */
  bucket: StrongholdBucket;
  /** Citizen-readable constituency name from the mart's
   *  `constituency_name` column. */
  constituency_name: string;
  /** LGD state slug from the mart's `state` column (e.g. "tamil-nadu"). */
  state: string;
  /** Per-event W/L outcomes chronologically (oldest first). Length
   *  equals `contested`. */
  results: ("W" | "L")[];
}

/** Pure: classify a raw win-count into the categorical bucket. */
export function bucketFromWins(
  wins: number | null | undefined,
): StrongholdBucket {
  if (wins == null || !Number.isFinite(wins)) return "absent";
  const n = Math.trunc(wins);
  if (n <= 0) return "zero";
  if (n === 1) return "one";
  if (n === 2) return "two";
  if (n <= 4) return "three-four";
  return "five-plus";
}

/** Pure: derive the `unique_id` key the delim=2024 PC topojson carries
 *  on `feature.properties.unique_id` (e.g. "S22_10" for Dharmapuri)
 *  from a stronghold mart entity_id like `IN-PC-2008-S22-10`. Returns
 *  `null` for entity_ids that don't match the PC pattern.
 *
 *  Coverage receipt (verified 2026-06-14 via the dispatch probe over
 *  the 5 oracle parties on `datasets/data/marts/party_pages/
 *  strongholds.csv`):
 *    - DMK: 10/10 matched   - AAP: 6/6 matched
 *    - BJP: 10/10 matched   - INC: 10/10 matched
 *    - BSP: 9/10 matched (the 1 unmatched is `IN-PC-1976-S24-60`
 *      BILHOUR, a delim=1976 UP PC whose seat number does not align
 *      with the delim=2024 boundary corpus).
 *  At-corpus scale: 353/364 = 97 percent. Unmatched rows fall through
 *  to "absent" silently; the citizen sees the choropleth coloured at
 *  the coverable subset of the top-10. */
export function uniqueIdFromPcEntityId(entity_id: string): string | null {
  // Pattern: IN-PC-<delim>-<state_code>-<seat_no>
  // We split on "-" rather than regex so the function stays trivial.
  const parts = entity_id.split("-");
  if (parts.length !== 5) return null;
  if (parts[0] !== "IN" || parts[1] !== "PC") return null;
  const state_code = parts[3];
  const seat_no = parts[4];
  if (!state_code || !seat_no) return null;
  return `${state_code}_${seat_no}`;
}

/** Pure: derive the LGD state code (e.g. "S22") from a PC mart
 *  entity_id. Returns `null` for non-matching ids. Used by the
 *  state-cropping decision in the component (when home_state_codes
 *  is set the component crops the projection to the subset of
 *  features whose state matches the party's home states). */
export function stateCodeFromPcEntityId(entity_id: string): string | null {
  const parts = entity_id.split("-");
  if (parts.length !== 5) return null;
  if (parts[0] !== "IN" || parts[1] !== "PC") return null;
  return parts[3] || null;
}

/** Pure: convert PartyStronghold rows (from the strongholds mart) into
 *  the choropleth row shape the component consumes. Mart rows that
 *  fail the PC entity_id pattern are silently dropped — these are
 *  defensive guards for future schema changes; the current mart only
 *  emits PC entity_ids in the `body=parliament` partition. */
export function mapPcStrongholdsToChoroplethRows(
  strongholds: readonly PartyStronghold[],
): StrongholdChoroplethRow[] {
  const out: StrongholdChoroplethRow[] = [];
  for (const s of strongholds) {
    const entity_key = uniqueIdFromPcEntityId(s.entity_id);
    if (entity_key === null) continue;
    out.push({
      entity_key,
      wins: s.wins,
      contested: s.contested,
      bucket: bucketFromWins(s.wins),
      constituency_name: s.constituency_name,
      state: s.state,
      results: s.results,
    });
  }
  return out;
}

/** Pure: mix an `#rrggbb` brand hex with white at ratio `t` in [0, 1]
 *  where t=1 is the brand pure and t=0 is white. Linear mix in sRGB.
 *
 *  We use a flat sRGB mix rather than a perceptual OkLCh inverse
 *  because the OkLCh hexToOklch inverse is not currently in the
 *  codebase (only the forward `oklchToHex` exists at
 *  `frontend/src/lib/colors/oklch.ts:22`). The visual difference at
 *  4 lightness stops on saturated brand colours (DMK red, BJP
 *  saffron, BSP deep-blue) is acceptable per dispatch-time visual
 *  smoke — citizen reads "more saturated brand colour = more wins"
 *  unambiguously. Reserve a follow-up to derive a proper OkLCh
 *  inverse and a perceptual ramp once `hexToOklch` lands. */
export function mixWithWhite(hex: string, t: number): string {
  const clean = hex.startsWith("#") ? hex.slice(1) : hex;
  if (clean.length !== 6) {
    // Defensive: return white for malformed input so the citizen
    // never sees a CSS-broken fill swatch.
    return "#ffffff";
  }
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  if (
    !Number.isFinite(r) ||
    !Number.isFinite(g) ||
    !Number.isFinite(b)
  ) {
    return "#ffffff";
  }
  const tc = Math.max(0, Math.min(1, t));
  const mix = (c: number): number => Math.round(c * tc + 255 * (1 - tc));
  const toHex = (n: number): string => n.toString(16).padStart(2, "0");
  return `#${toHex(mix(r))}${toHex(mix(g))}${toHex(mix(b))}`;
}

/** Pure: derive a 6-entry palette from a party's brand_colour hex.
 *  Bucket "absent" returns the hatch-fill URL; "zero" returns
 *  slate-100 (#f1f5f9); the four win-count buckets return increasing
 *  saturations of the brand colour. */
export function paletteFromBrand(
  brand_hex: string | null | undefined,
): Record<StrongholdBucket, string> {
  // Defensive fallback: parties without a brand_colour use slate-500
  // (#64748b) so the choropleth still renders with a citizen-readable
  // grey ramp. brand_colour absence is rare (only legacy / sentinel
  // parties on the current parties.csv; all 5 oracle parties have
  // brand_colour populated). The output is lowercased so palette
  // stops compare byte-equal across uppercase / lowercase input
  // variants (the parties.csv carries mixed cases, e.g. "#FA2223"
  // for DMK).
  const base = brand_hex && /^#[0-9a-fA-F]{6}$/.test(brand_hex)
    ? brand_hex.toLowerCase()
    : "#64748b";
  return {
    // "absent" is rendered with the SVG hatch pattern in the
    // component; we surface a deterministic CSS-safe sentinel here
    // so the test surface can assert "absent" without inspecting the
    // hatch. Component checks `bucket === "absent"` and substitutes
    // `url(#party-stronghold-hatch)` at render time.
    "absent": "#ffffff",
    "zero": "#f1f5f9",
    "one": mixWithWhite(base, 0.20),
    "two": mixWithWhite(base, 0.40),
    "three-four": mixWithWhite(base, 0.65),
    "five-plus": base,
  };
}

/** Pure: parse the `home_state_codes` column from parties.csv into
 *  the set of ECI state codes (S/U series) the party regards as home.
 *  The column shape is `|`-separated ISO 3166-2 codes like
 *  "IN-TN|IN-PY" (DMK); we extract the ECI-equivalent suffix via the
 *  small inline lookup below. Returns an empty set when the field
 *  is blank or all entries fail the lookup. */
export function homeStateEciCodes(
  home_state_codes_field: string | null | undefined,
): Set<string> {
  const out = new Set<string>();
  if (!home_state_codes_field) return out;
  for (const tok of home_state_codes_field.split("|")) {
    const trimmed = tok.trim();
    if (!trimmed) continue;
    const eci = ISO_TO_ECI_STATE[trimmed];
    if (eci) out.add(eci);
  }
  return out;
}

/** ISO 3166-2 IN-* → ECI state code mapping. We embed the small lookup
 *  inline rather than fetching state_iso_seed.csv at module-load time:
 *  this component runs on the per-party detail page and only the 36
 *  S/U codes are needed; the lookup is a 36-row constant that never
 *  changes (state codes are stable identifiers per CLAUDE.md section
 *  3 "issuing-authority IDs"). Kept private; tests assert via
 *  `homeStateEciCodes` outputs. */
const ISO_TO_ECI_STATE: Readonly<Record<string, string>> = Object.freeze({
  "IN-AN": "U01",
  "IN-AP": "S01",
  "IN-AR": "S02",
  "IN-AS": "S03",
  "IN-BR": "S04",
  "IN-CH": "U02",
  "IN-CT": "S26",
  "IN-DH": "U03",
  "IN-DL": "U05",
  "IN-GA": "S05",
  "IN-GJ": "S06",
  "IN-HR": "S07",
  "IN-HP": "S08",
  "IN-JK": "U08",
  "IN-JH": "S27",
  "IN-KA": "S10",
  "IN-KL": "S11",
  "IN-LA": "U09",
  "IN-LD": "U06",
  "IN-MP": "S12",
  "IN-MH": "S13",
  "IN-MN": "S14",
  "IN-ML": "S15",
  "IN-MZ": "S16",
  "IN-NL": "S17",
  "IN-OR": "S18",
  "IN-PY": "U07",
  "IN-PB": "S19",
  "IN-RJ": "S20",
  "IN-SK": "S21",
  "IN-TN": "S22",
  "IN-TG": "S29",
  "IN-TR": "S23",
  "IN-UP": "S24",
  "IN-UT": "S28",
  "IN-WB": "S25",
});
