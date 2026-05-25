// Government timeline loader. See ADR-0023 + docs/concepts/government-vs-election.md.
//
// Reads the consolidated long-form `datasets/taxonomy/office_holdings.json`
// (G.1.c 2026-05-22; replaced the 31 per-state cm_terms.json files).
// Filters by `office_id == "IN-<state>-CM"` per state and adapts the
// long-form row shape (start_date / end_date / person_name /
// party_eci_code) to the existing `GovernmentTerm` field names
// (start / end / cm_name / party_code) so downstream Svelte components
// don't have to change. Whole file fetched once and cached globally;
// subsequent state lookups are pure filter ops over the cached holdings.
//
// Schema: datasets/schemas/office-holdings.schema.json v1.1 (replaced
// the retired state_government.schema.json). v1.1 adds non-CM national
// offices whose raw `regime` may be null; this loader filters to CM rows.

import { DATA_BASE } from "./paths";

export type Regime = "elected" | "presidents_rule" | "governors_rule" | "interim";
type SelectionMethod = "legislature_confidence" | "electoral_college" | "appointed_by_president" | "constitutional_succession";
type TenureStatus = "substantive" | "acting" | "additional_charge";

export interface GovernmentTerm {
  start: string;            // YYYY-MM-DD
  end: string | null;       // YYYY-MM-DD, null for the current ongoing term
  regime: Regime;
  party_code: string | null;
  alliance: string | null;
  cm_name: string | null;
  notes?: string;
  references?: { url: string; note?: string }[];
}

export interface GovernmentTimeline {
  $schema: string;
  $schema_version: string;
  sources: { url: string; fetched_at?: string; name?: string; authority?: string }[];
  state: string;
  terms: GovernmentTerm[];
}

interface _OfficeHolding {
  office_id: string;
  start_date: string;
  end_date: string | null;
  regime: Regime | null;
  citation_group_id?: string;
  selection_method?: SelectionMethod;
  tenure_status?: TenureStatus;
  person_name: string | null;
  party_eci_code: string | null;
  alliance: string | null;
  notes?: string | null;
  references?: { url: string; note?: string }[];
}

interface _OfficeHoldingsFile {
  $schema: string;
  $schema_version: string;
  office_citations: Record<string, { url_main: string }>;
  citation_groups?: Record<string, unknown>;
  holdings: _OfficeHolding[];
}

let _allHoldings: Promise<_OfficeHoldingsFile | null> | null = null;
const _byState = new Map<string, Promise<GovernmentTimeline | null>>();

function _loadAll(): Promise<_OfficeHoldingsFile | null> {
  if (_allHoldings) return _allHoldings;
  _allHoldings = fetch(`${DATA_BASE}/taxonomy/office_holdings.json`)
    .then(async res => {
      if (res.status === 404) return null;
      if (!res.ok) {
        throw new Error(
          `fetch /taxonomy/office_holdings.json failed: ${res.status} ${res.statusText}`,
        );
      }
      return (await res.json()) as _OfficeHoldingsFile;
    });
  return _allHoldings;
}

type _ChiefMinisterHolding = _OfficeHolding & { regime: Regime };

function _adapt(holding: _ChiefMinisterHolding): GovernmentTerm {
  return {
    start: holding.start_date,
    end: holding.end_date,
    regime: holding.regime,
    party_code: holding.party_eci_code,
    alliance: holding.alliance,
    cm_name: holding.person_name,
    notes: holding.notes ?? undefined,
    references: holding.references,
  };
}

/**
 * Fetch a state's government timeline. Returns null when no CM
 * holdings exist for the state in `office_holdings.json` (graceful
 * degradation per ADR-0023). Other failures throw. Cached per state.
 */
export function fetchGovernmentTimeline(stateCode: string): Promise<GovernmentTimeline | null> {
  const cached = _byState.get(stateCode);
  if (cached) return cached;
  const office_id = `IN-${stateCode}-CM`;
  const p = _loadAll().then(file => {
    if (!file) return null;
    const terms = file.holdings
      .filter((h): h is _ChiefMinisterHolding => h.office_id === office_id && h.regime !== null)
      .map(_adapt);
    if (terms.length === 0) return null;
    const url_main = file.office_citations[office_id]?.url_main;
    const sources = url_main
      ? [{ url: url_main, name: `List of Chief Ministers of ${stateCode}`, authority: "Wikipedia" }]
      : [];
    return {
      $schema: file.$schema,
      $schema_version: file.$schema_version,
      sources,
      state: stateCode,
      terms,
    } satisfies GovernmentTimeline;
  });
  _byState.set(stateCode, p);
  return p;
}

/**
 * The current term is the one with `end === null`. By schema, at most one
 * such term exists. Falls back to the chronologically last term if none
 * is open (defensive — should not happen in well-authored files).
 */
export function currentTerm(timeline: GovernmentTimeline | null): GovernmentTerm | null {
  if (!timeline || timeline.terms.length === 0) return null;
  return timeline.terms.find(t => t.end === null) ?? timeline.terms[timeline.terms.length - 1];
}

/**
 * Find the term covering a given date (used by the date-slider overlay
 * on socio-economic charts — not yet wired into B3).
 */
export function termAt(timeline: GovernmentTimeline | null, date: string): GovernmentTerm | null {
  if (!timeline) return null;
  return timeline.terms.find(t => {
    if (t.start > date) return false;
    if (t.end === null) return true;
    return t.end >= date;
  }) ?? null;
}

