// Government timeline loader. See ADR-0023 + docs/concepts/government-vs-election.md.
//
// One file per state at datasets/governments/in/states/<state>/cm_terms.json.
// 4 of 15 ingested states have files at this commit (S03 Assam, S11 Kerala,
// S22 Tamil Nadu, S25 West Bengal). The remaining 10+ are tracked as a
// follow-up authoring task; the UI degrades gracefully (returns null) when
// a file is absent rather than treating it as an error.
//
// Schema: datasets/schemas/state_government.schema.json v1.0.

import { DATA_BASE } from "./paths";

export type Regime = "elected" | "presidents_rule" | "governors_rule" | "interim";

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
  sources: { url: string; fetched_at: string; name?: string; authority?: string }[];
  state: string;
  terms: GovernmentTerm[];
}

const _cache = new Map<string, Promise<GovernmentTimeline | null>>();

/**
 * Fetch a state's government timeline. Returns null on 404 (file not yet
 * authored — graceful degradation per ADR-0023). Other failures throw.
 * Per-state Promise cache prevents duplicate fetches across components.
 */
export function fetchGovernmentTimeline(stateCode: string): Promise<GovernmentTimeline | null> {
  const cached = _cache.get(stateCode);
  if (cached) return cached;
  const p = fetch(`${DATA_BASE}/governments/in/states/${stateCode}/cm_terms.json`)
    .then(async res => {
      if (res.status === 404) return null;
      if (!res.ok) {
        throw new Error(
          `fetch /governments/in/states/${stateCode}/cm_terms.json failed: ${res.status} ${res.statusText}`,
        );
      }
      return (await res.json()) as GovernmentTimeline;
    });
  _cache.set(stateCode, p);
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
