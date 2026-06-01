// Typed translator for the election-map filter-rail query grammar (PR-B8).
//
// The URL is the only state-sharing channel on a static bundle (CLAUDE.md
// Holy Law #1), so the query string IS the contract: a shared link must
// reproduce the screen, must survive citizen hand-editing, and must be
// reused verbatim by the national PC route (PR-B9). Per Gregor's verdict
// this is a Message Translator — ONE typed boundary converts the wire
// format to/from the domain object, so neither the state component nor the
// national component re-implements `URLSearchParams.get()` parsing.
//
// Grammar (all keys omitted when equal to their default — Q2):
//   ?party=BJP,INC   multi-select party codes, comma-delimited, per-token
//                    encoded (Q1). Empty list => key omitted.
//   ?margin=lt2      one of all|lt2|gt20 (a constituency margin <2 pts or
//                    >20 pts). `all` is default/omitted.
//   ?mode=turnout    one of winner|margin|turnout|age. `winner` default.
//
// Degradation (Q4): invalid enum vocabulary clamps silently to the default
// (an old bundle that doesn't know a future `mode` still renders a coherent
// screen); unknown-but-well-formed party codes pass through verbatim (a
// code this event doesn't contain simply highlights nothing — dropping it
// would corrupt a link shared across events/grains).

export const MARGIN_BANDS = ["all", "lt2", "gt20"] as const;
export type MarginBand = (typeof MARGIN_BANDS)[number];

export const COLOUR_MODES = ["winner", "margin", "turnout", "age"] as const;
export type ColourMode = (typeof COLOUR_MODES)[number];

/** Margin-band thresholds (percentage points), matching the explore presets. */
export const MARGIN_CLOSE_MAX = 2;
export const MARGIN_LANDSLIDE_MIN = 20;

export interface ElectionFilters {
  /** Party codes to keep highlighted; [] means "no party filter" (default). */
  parties: string[];
  /** Margin band; "all" is the default (omitted from URL). */
  margin: MarginBand;
  /** Colour-by mode; "winner" is the default (omitted from URL). */
  mode: ColourMode;
}

export const DEFAULT_ELECTION_FILTERS: ElectionFilters = {
  parties: [],
  margin: "all",
  mode: "winner",
};

/**
 * Parse filter state from a query string (or URLSearchParams).
 * Unknown/invalid ENUM values degrade to the default (clamp, never throw).
 * Unknown party codes are kept verbatim (forward-compatible; see Q4).
 */
export function parseElectionFilters(
  search: string | URLSearchParams,
): ElectionFilters {
  const p = typeof search === "string" ? new URLSearchParams(search) : search;

  const rawParty = p.get("party");
  // `URLSearchParams.get` has already percent-decoded the value, so the
  // comma is the structural delimiter and we just split + trim. ECI party
  // codes are comma-free alphanumeric tokens, so a literal comma can only
  // be a separator (a comma INSIDE a code is unsupportable via this grammar
  // and does not occur in the dataset).
  const parties = rawParty
    ? rawParty
        .split(",")
        .map((c) => c.trim())
        .filter((c) => c.length > 0)
    : [];

  const rawMargin = p.get("margin") ?? "";
  const margin = (MARGIN_BANDS as readonly string[]).includes(rawMargin)
    ? (rawMargin as MarginBand)
    : "all";

  const rawMode = p.get("mode") ?? "";
  const mode = (COLOUR_MODES as readonly string[]).includes(rawMode)
    ? (rawMode as ColourMode)
    : "winner";

  return { parties, margin, mode };
}

/**
 * Serialize filters to a query string WITHOUT a leading "?".
 * Defaults are omitted (Q2). Caller composes: `path + (qs ? `?${qs}` : "")`.
 *
 * `base` lets the serializer preserve params it does NOT own (e.g. `view`)
 * while owning exactly the three filter keys — this is what keeps a future
 * `view`-consolidation cheap and stops PR-B8 clobbering `?view=hex`.
 */
export function serializeElectionFilters(
  filters: ElectionFilters,
  base?: URLSearchParams,
): string {
  const p = new URLSearchParams(base);
  // Own exactly the three filter keys: clear then re-set so toggling off works.
  p.delete("party");
  p.delete("margin");
  p.delete("mode");

  if (filters.parties.length > 0) {
    // URLSearchParams.toString() percent-encodes the whole value, so the
    // comma-joined list round-trips through `.get()` (Q1).
    p.set("party", filters.parties.join(","));
  }
  if (filters.margin !== "all") p.set("margin", filters.margin);
  if (filters.mode !== "winner") p.set("mode", filters.mode);

  return p.toString();
}

/** True when an absolute-value margin (in pts) falls inside the chosen band. */
export function matchesMarginBand(
  margin_pct: number | null | undefined,
  band: MarginBand,
): boolean {
  if (band === "all") return true;
  if (margin_pct == null || Number.isNaN(margin_pct)) return false;
  const m = Math.abs(margin_pct);
  if (band === "lt2") return m < MARGIN_CLOSE_MAX;
  return m > MARGIN_LANDSLIDE_MIN; // gt20 (landslide)
}

/** Count of filters that differ from the default — drives the reset chip. */
export function activeFilterCount(filters: ElectionFilters): number {
  let n = 0;
  if (filters.parties.length > 0) n += 1;
  if (filters.margin !== "all") n += 1;
  if (filters.mode !== "winner") n += 1;
  return n;
}
