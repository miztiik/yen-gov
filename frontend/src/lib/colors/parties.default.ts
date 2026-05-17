// Canonical default party color palette, keyed by ECI party code.
//
// Why ECI code, not short name: short names collide and drift (e.g. "CPI(M)" vs
// "CPM" vs "CPI-M" across portals); ECI codes are stable identifiers issued by
// the Election Commission and cited verbatim in datasets/elections/*/parties.json.
// Per CLAUDE.md §3 ("never invent IDs when an issuing authority publishes one").
//
// This is presentation, NOT a contract surface — colors live in the frontend,
// not under datasets/reference/. Users override per party from /settings; the
// merged map (default + overrides) is read by every chart and the map.
//
// Adding a party here is an additive change. Removing or recoloring an existing
// entry shifts what every screenshot in the wild looks like — coordinate before
// changing, and prefer adding overrides via the user-facing Settings page.
//
// Colors picked from each party's flag/symbol where unambiguous; falls back to
// d3-scale-chromatic categorical palette for parties without iconic colors.

export interface PartyColor {
  fill: string;       // primary fill (hex, no alpha)
  text?: string;      // text color when used on the fill (default: auto by luminance)
}

export const DEFAULT_PARTY_COLORS: Record<string, PartyColor> = {
  // Tamil Nadu (S22, AcGenMay2026)
  "3679": { fill: "#7c2d12" },                  // TVK — Tamilaga Vettri Kazhagam
  "582":  { fill: "#dc2626" },                  // DMK — rising sun red
  "75":   { fill: "#16a34a" },                  // ADMK — twin leaves green
  "742":  { fill: "#1d4ed8" },                  // INC — Congress hand blue
  "1272": { fill: "#facc15", text: "#1f2937" }, // PMK — mango yellow
  "772":  { fill: "#15803d" },                  // IUML — green
  "544":  { fill: "#b91c1c" },                  // CPI — red
  "1847": { fill: "#0f766e" },                  // VCK — teal/blue
  "547":  { fill: "#991b1b" },                  // CPI(M) — deeper red
  "369":  { fill: "#ea580c" },                  // BJP — saffron
  "581":  { fill: "#0ea5e9" },                  // DMDK
  "2866": { fill: "#a855f7" },                  // AMMK

  // Assam (S03, AcGenMay2026) — colors picked from each party's flag/symbol
  // where available. INC/BJP are shared with TN above.
  "83":   { fill: "#f97316" },                  // AGP — Asom Gana Parishad, saffron flag
  "436":  { fill: "#84cc16" },                  // BOPF — Bodoland People's Front, lime
  "145":  { fill: "#166534" },                  // AIUDF — All India United Democratic Front, dark green crescent
  "3289": { fill: "#ca8a04", text: "#1f2937" }, // RJRD — Raijor Dal, ochre
  "140":  { fill: "#15803d" },                  // AITC — Trinamool Congress green (also S25 second party; see below)

  // Kerala (S11, AcGenMay2026) — INC/CPI(M)/IUML/CPI/BJP shared above.
  "911":  { fill: "#9d174d" },                  // KEC — Kerala Congress, magenta
  "913":  { fill: "#be185d" },                  // KEC(J) — Kerala Congress (Jacob), pink
  "1534": { fill: "#7f1d1d", text: "#fafaf9" }, // RSP — Revolutionary Socialist Party (red, distinct from CPI/CPI(M))
  "1420": { fill: "#65a30d" },                  // RJD — Rashtriya Janata Dal, green lantern

  // West Bengal (S25, AcGenMay2026) — BJP/INC/CPI(M)/AITC shared above.
  // AJUP and AISF have weak iconic colors → fallback palette stays in play.

  // Generic / cross-state
  "NOTA": { fill: "#64748b" },                  // slate-500 (canonical NOTA stand-in)
  "IND":  { fill: "#94a3b8" },                  // independents
};

// Categorical fallback palette for parties not in the canonical map. Picked
// from d3.schemeTableau10 for distinguishability without re-importing d3 here.
const FALLBACK_PALETTE: string[] = [
  "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
  "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
];

// Stable assignment: same code always maps to the same fallback color.
function fallbackFor(eci_code: string): PartyColor {
  let h = 0;
  for (let i = 0; i < eci_code.length; i++) h = (h * 31 + eci_code.charCodeAt(i)) | 0;
  return { fill: FALLBACK_PALETTE[Math.abs(h) % FALLBACK_PALETTE.length] };
}

export function defaultColorFor(eci_code: string | null | undefined, short_name?: string): PartyColor {
  if (!eci_code) {
    // No ECI code — independents, NOTA-like, or unmapped. Try short_name.
    if (short_name && DEFAULT_PARTY_COLORS[short_name]) return DEFAULT_PARTY_COLORS[short_name];
    return DEFAULT_PARTY_COLORS["IND"];
  }
  return DEFAULT_PARTY_COLORS[eci_code] ?? fallbackFor(eci_code);
}
