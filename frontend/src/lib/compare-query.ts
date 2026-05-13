// Generic Compare route query-string contract (P4).
//
// `/compare?i=<indicator-id>&states=<csv>&peer=<peer-set-id>` is the
// shareable URL shape for cross-state indicator comparison. Three slots:
//
//   i       — required to render content. Indicator id of the form
//             "<topic>/<id>" (matches catalogue.indicatorPathForArtifact
//             input). When absent, the page renders an indicator chooser
//             instead of 500-ing.
//   states  — comma-separated state slugs (e.g. "tamil-nadu,kerala,karnataka").
//             When present, those states are pinned at the top of the
//             ranked table. Order is preserved. Unknown / malformed
//             slugs are silently dropped (don't kill the page on a typo).
//             Resolution to ECI codes happens at the call site (needs the
//             states resolver, which is async).
//   peer    — optional peer-set id (same enum as topic-query). Restricts
//             the candidate state pool to that peer set. Pinned states
//             are always visible regardless (citizen never loses a
//             state they explicitly asked for).
//
// Pure module: no DOM, no fetch, no state resolution. The caller is
// responsible for translating slugs to ECI codes once the resolver is
// loaded; this module only owns the URL <-> typed-object bijection.

import { isPeerSet, type PeerSet } from "./catalogue";

/** Decoded `/compare` query state. All fields nullable for "absent". */
export interface CompareQuery {
  /** Indicator id, e.g. "fiscal/outstanding_debt_pct_gsdp". */
  indicator: string | null;
  /** State slugs, in user-visible pin order. Empty array when absent. */
  states: string[];
  /** Peer-set restriction. */
  peer: PeerSet | null;
}

// Loose validator for indicator IDs. Real validation happens when the
// catalogue is loaded and we look the id up. Here we only guard against
// obvious garbage that could end up in the DOM (path traversal, schemes).
function isLikelyIndicatorId(s: string): boolean {
  if (s.length === 0 || s.length > 200) return false;
  // Match catalogue convention "<segment>/<segment>[/<segment>]" with
  // lowercase ascii + digits + underscore. NOT the full backend
  // `^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*$` — we tolerate but don't
  // require the leading-letter rule here so a future id starting with a
  // digit doesn't get silently dropped at the URL boundary.
  return /^[a-z0-9_]+(\/[a-z0-9_]+)+$/.test(s);
}

// Slug pattern for states — see lib/slug.ts. Lowercase letters / digits
// separated by single hyphens, no leading / trailing hyphen.
function isLikelyStateSlug(s: string): boolean {
  if (s.length === 0 || s.length > 80) return false;
  return /^[a-z0-9]+(-[a-z0-9]+)*$/.test(s);
}

/**
 * Parse a `/compare` URL search string. Accepts either the raw string
 * (with or without leading `?`) or a URLSearchParams. Malformed values
 * are dropped silently.
 */
export function parseCompareQuery(search: string | URLSearchParams): CompareQuery {
  const params =
    typeof search === "string" ? new URLSearchParams(search) : search;
  const i_raw = params.get("i");
  const states_raw = params.get("states") ?? "";
  const peer_raw = params.get("peer");

  const states = states_raw
    .split(",")
    .map(s => s.trim())
    .filter(s => s.length > 0 && isLikelyStateSlug(s));
  // De-dupe while preserving order — first occurrence wins.
  const seen = new Set<string>();
  const states_unique: string[] = [];
  for (const s of states) {
    if (!seen.has(s)) {
      seen.add(s);
      states_unique.push(s);
    }
  }

  return {
    indicator: i_raw && isLikelyIndicatorId(i_raw) ? i_raw : null,
    states: states_unique,
    peer: peer_raw && isPeerSet(peer_raw) ? peer_raw : null,
  };
}

/**
 * Serialize a CompareQuery to a leading-`?` search string. Omits absent
 * fields entirely so default URLs stay clean. Returns `""` (NOT `"?"`)
 * when every field is empty.
 */
export function serializeCompareQuery(q: CompareQuery): string {
  const params = new URLSearchParams();
  if (q.indicator !== null) params.set("i", q.indicator);
  if (q.states.length > 0) params.set("states", q.states.join(","));
  if (q.peer !== null) params.set("peer", q.peer);
  const s = params.toString();
  return s ? `?${s}` : "";
}
