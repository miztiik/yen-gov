// Topic-route query-string contract (P3.3d).
//
// `/t/:topic` is shareable. The query string captures user-tweaked
// filter state so a citizen can paste a URL and the recipient sees the
// same view. v0 surface is a single param:
//
//   ?peer=<peer-set-id>     — overrides the catalogue's per-artifact
//                              `peer_set_default` for EVERY artifact on
//                              the page. Validated against catalogue's
//                              `PEER_SET_VALUES`; unknown values are
//                              silently dropped (don't 500 on a typo).
//
// Single-param semantics chosen for v0 because the common share use-case
// is "show this topic filtered to General-category states", not "set
// artifact A to peer X and artifact B to peer Y". Per-artifact fidelity
// (`?peer.<artifact-id>=…`) is a future iteration; the parser already
// returns a typed object so adding fields is non-breaking.
//
// This module is pure (no DOM, no fetch). Wired into TopicLanding via
// `URLSearchParams(window.location.search)` reads + `history.replaceState`
// writes; tested standalone.

import { isPeerSet, type PeerSet } from "./catalogue";

/** Decoded topic-route query state. All fields nullable for "absent". */
export interface TopicQuery {
  /** Peer-set override applied to every artifact. */
  peer: PeerSet | null;
}

/**
 * Parse a topic-route URL search string (e.g. `?peer=general_category`).
 * Accepts either the raw string (with or without leading `?`) or an
 * existing URLSearchParams. Unknown / malformed values are dropped — the
 * page should never 500 because someone hand-edited the URL.
 */
export function parseTopicQuery(search: string | URLSearchParams): TopicQuery {
  const params =
    typeof search === "string" ? new URLSearchParams(search) : search;
  const raw = params.get("peer");
  return {
    peer: raw && isPeerSet(raw) ? raw : null,
  };
}

/**
 * Serialize a TopicQuery to a leading-`?` search string suitable for
 * `history.replaceState`'s URL argument. Returns `""` (NOT `"?"`) when
 * every field is null, so the URL stays clean for the default view.
 */
export function serializeTopicQuery(q: TopicQuery): string {
  const params = new URLSearchParams();
  if (q.peer !== null) params.set("peer", q.peer);
  const s = params.toString();
  return s ? `?${s}` : "";
}
