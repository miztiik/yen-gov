// Grammar A URL builders — the place-first cascade per ADR-0037.
//
// As of PR-P4 (this is the sole source of truth for in-app route URLs).
// PR-P1 shipped the routes + RedirectLegacyUrl; PR-P2 swept every
// caller from the legacy `url.X()` Grammar B builders to `link.X()`
// here; PR-P3 deleted the `url.ts` Grammar B builders and the 42-test
// Grammar B contract; PR-P4 (this PR) deleted the `RedirectLegacyUrl`
// tombstone, dropped `s` from `RESERVED_PATH_TOKENS`, and closed the
// 4-phase strangler-fig. Legacy `/s/<state>/...` URLs now fall through
// to NotFound (404 with recovery links).
//
// Module name: `links.ts` because the artefact `link.stateHub("S22")`
// emits is what `<a href={...}>` consumes. The existing `paths.ts`
// already holds the runtime DATA_BASE prefix (a different concern), so
// reusing that name would mix two unrelated responsibilities.
//
// See also:
//   * ADR-0037 — the binding decision, the three-voice digest, the
//     four-phase strangler-fig, and the open user-gate questions.
//   * frontend/src/lib/url.ts — URL utility primitives only after PR-P3
//     (`withBase`, `stripBase`, `navigate`); the Grammar B `url.X()`
//     builders that used to live there are deleted.
//   * frontend/src/lib/slug.ts — the slugify primitive shared with url.ts.
//   * frontend/src/lib/paths.ts — the (unrelated) DATA_BASE prefix module.

import { slugify, partyIdToSlug } from "./slug";
import { states } from "./states.svelte";

const BASE = import.meta.env.BASE_URL; // always ends in '/'

/**
 * Prefix a path with the deploy base URL. Inputs MUST start with `/`;
 * the duplicate slash that BASE='/yen-gov/' would otherwise produce is
 * collapsed. Mirrors `url.ts:withBase` so behaviour is identical between
 * the two builder layers.
 */
export function withBase(path: string): string {
  if (!path.startsWith("/")) path = "/" + path;
  return BASE.replace(/\/$/, "") + path;
}

/** Resolve a state code OR an already-slugified state name to the
 * canonical state slug. Lower-cases unknown codes as a graceful fallback
 * so URLs are never blank — same contract as `url.ts:state()` so
 * consumers can switch without behaviour drift.
 */
function stateSlug(stateCodeOrSlug: string): string {
  const candidate = states.slug(stateCodeOrSlug);
  if (candidate) return candidate;
  return stateCodeOrSlug.toLowerCase();
}

/** AC slug under Grammar A: pure name (`mylapore`), no `167-` numeric
 * prefix. Use the existing `slug.ts:slugify` so behaviour matches the
 * generator used everywhere else; the numeric prefix is dropped here on
 * purpose per ADR-0037 §AC-slug. If two ACs in the same state ever
 * share a name (rare) the second emits as `<name>-2`, enforced at
 * emit time (Phase 2 will land the per-state collision check on AC
 * names).
 */
function acNameSlug(name: string): string {
  return slugify(name);
}

/**
 * URL builders for Grammar A — the canonical place-first cascade with
 * the state slug at the root. Every Phase 2 call-site migration replaces
 * one `url.X()` invocation with the matching `link.X()` invocation.
 *
 * Naming convention: the builder name describes the SURFACE
 * (`stateHub`, `acDeepLink`, `nationalIndicator`), not the URL shape
 * (`slashStateSlashAc`). The surface name is stable across grammar
 * revisions; the URL shape is what we're changing.
 */
export const link = {
  /** Country home (`/`). India is implicit on a `.in` domain. */
  home(): string {
    return withBase("/");
  },

  /** State or UT hub (`/tamil-nadu`). */
  stateHub(stateCodeOrSlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}`);
  },

  /** Short alias for `stateHub` mirroring `url.state` from url.ts. */
  state(stateCodeOrSlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}`);
  },

  /** AC deep-link (`/tamil-nadu/mylapore`). Pure name slug, no numeric
   * prefix per ADR-0037 §AC-slug. */
  acDeepLink(stateCodeOrSlug: string, acName: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}/${acNameSlug(acName)}`);
  },

  /** Indicator at national scope (`/installed-capacity`). */
  nationalIndicator(indicatorSlug: string): string {
    return withBase(`/${indicatorSlug}`);
  },

  /** Indicator at state scope (`/tamil-nadu/installed-capacity`). The
   * position-2 segment is an indicator slug OR an AC slug; the resolver
   * decides at runtime against the namespace-disjointness contract. */
  stateIndicator(stateCodeOrSlug: string, indicatorSlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}/${indicatorSlug}`);
  },

  /** Indicator at AC scope (`/tamil-nadu/mylapore/installed-capacity`). */
  acIndicator(
    stateCodeOrSlug: string,
    acName: string,
    indicatorSlug: string,
  ): string {
    return withBase(
      `/${stateSlug(stateCodeOrSlug)}/${acNameSlug(acName)}/${indicatorSlug}`,
    );
  },

  /** Topic Front Door index (`/t`). */
  topicsIndex(): string {
    return withBase("/t");
  },

  /** Short alias for `topicsIndex` mirroring `url.topics` from url.ts. */
  topics(): string {
    return withBase("/t");
  },

  /** Topic landing (`/t/energy`). The `/t/` namespace isolates topic
   * slugs from state slugs at the resolver layer per ADR-0037 §rejected-4.
   */
  topicLanding(topicId: string): string {
    return withBase(`/t/${encodeURIComponent(topicId)}`);
  },

  /** Short alias for `topicLanding` mirroring `url.topic` from url.ts. */
  topic(topicId: string): string {
    return withBase(`/t/${encodeURIComponent(topicId)}`);
  },

  /** Per-state topic landing (`/tamil-nadu/t/energy`). Phase 1 ships
   * the `/t/` sub-namespace for parity with the top-level topic landing;
   * Phase 2 may flatten pending user direction (see TODO open question 1).
   */
  stateTopic(stateCodeOrSlug: string, topicId: string): string {
    return withBase(
      `/${stateSlug(stateCodeOrSlug)}/t/${encodeURIComponent(topicId)}`,
    );
  },

  /** State explorer (`/tamil-nadu/explore`). */
  stateExplore(stateCodeOrSlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}/explore`);
  },

  /** Short alias for `stateExplore` mirroring `url.explore` from url.ts. */
  explore(stateCodeOrSlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}/explore`);
  },

  /** Parties index (`/parties`). The alphabetical + recognition-scope
   * + search list of every party in `datasets/data/entities/parties.csv`.
   * Top-level `parties` (plural) is reserved in RESERVED_PATH_TOKENS per
   * ADR-0053; the per-party pages live one segment deeper at
   * `/parties/<slug>` via `link.party(party_id)`. */
  parties(): string {
    return withBase("/parties");
  },

  /** Per-party page (`/parties/<slug>`). Takes the canonical `party_id`
   * directly (no state context); returns `null` when the party_id has
   * no citizen page (currently only `parties.IN.UNK`, the resolver
   * fallback). Callers MUST handle the null case — usually by skipping
   * the link wrapper and rendering plain text (the no-silent-demotion
   * rule, CLAUDE.md §10).
   *
   * Slug shape per ADR-0053: lowercased `party_id` tail with `_` -> `-`.
   * Sentinel slugs: IND -> `/parties/independent`, NOTA -> `/parties/nota`,
   * UNK -> null. See `slug.ts::partyIdToSlug` for the derivation rule.
   *
   * Examples:
   *   `link.party("parties.IN.INC")`  -> `"/parties/inc"`
   *   `link.party("parties.IN.IND")`  -> `"/parties/independent"`
   *   `link.party("parties.IN.UNK")`  -> `null`
   */
  party(party_id: string | null | undefined): string | null {
    if (!party_id) return null;
    const slug = partyIdToSlug(party_id);
    if (slug === null) return null;
    return withBase(`/parties/${slug}`);
  },

  /** AC drill (`/<state>/ac/<slug>` or, when an event is supplied,
   * `/<state>/elections/<event>/ac/<slug>` per ADR-0052 / main.ts route
   * table). AC slug is NAME-ONLY (`mylapore`) per ADR-0037 §AC-slug;
   * the numeric-prefix legacy shape (`167-mylapore`) is GONE on the
   * Grammar A surface. Callers that have an event id pass it through
   * for the canonical nested form; otherwise the bare-AC convenience
   * entry redirects to the state's default event at render time. */
  ac(
    stateCodeOrSlug: string,
    acName: string,
    event?: string | null,
  ): string {
    const slug = stateSlug(stateCodeOrSlug);
    const acSeg = acNameSlug(acName);
    return withBase(
      event
        ? `/${slug}/elections/${encodeURIComponent(event)}/ac/${acSeg}`
        : `/${slug}/ac/${acSeg}`,
    );
  },

  /** AC by eci_no fallback (`/<state>/ac/<eci_no>` or nested), used by
   * callers that don't have an AC name to hand (rare; mostly map-click
   * paths that have only the integer from the geometry property). */
  acByNo(
    stateCodeOrSlug: string,
    eci_no: number,
    event?: string | null,
  ): string {
    const slug = stateSlug(stateCodeOrSlug);
    return withBase(
      event
        ? `/${slug}/elections/${encodeURIComponent(event)}/ac/${eci_no}`
        : `/${slug}/ac/${eci_no}`,
    );
  },

  /** Per-state district landing (`/<state>/<district-slug>`). Positional
   * (no `/d/` literal marker) per Deferral 1 of
   * TODO/20260609-url-prefix-drop-phase0-plan.md + Jony's verdict
   * ("citizen forwarding yen-gov.in/tamil-nadu/d/chennai over WhatsApp
   * is sharing a system internal"). The router dispatches via
   * `StateSubRouter` (route pattern `/:state/:position2`) which
   * resolves the second segment against three registries
   * (reserved-chrome / district / AC). Under Option A (2026-06-10)
   * the shipped corpus carries 401 (state, slug) pairs where a
   * district name equals an AC name in the same state by design;
   * the dispatcher resolves district-first per Jony rule #4 and the
   * colliding AC stays reachable via the canonical event-nested URL
   * `/<state>/elections/<event>/ac/<ac>` (ADR-0052). The `d` token
   * stays in `RESERVED_PATH_TOKENS` per Jony rule #3 as a future
   * escape-hatch. */
  district(stateCodeOrSlug: string, districtSlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}/${districtSlug}`);
  },

  /** Per-state per-event election landing (`/<state>/elections/<event>`).
   * Neutral citizen permalink; distinct from Psephlab and Compare. */
  stateElection(stateCodeOrSlug: string, eventId: string): string {
    return withBase(
      `/${stateSlug(stateCodeOrSlug)}/elections/${encodeURIComponent(eventId)}`,
    );
  },

  /** National per-event view (`/t/elections/<event>`). Sibling of
   * `stateElection` for national Parliament events. Added in PR-W3d
   * (2026-06-10) so the new firehose at `/t/elections` has a typed
   * builder for click-through to the rebuilt `NationalElection.svelte`
   * page (PR-W3c) instead of hand-concatenating `/t/elections/<event>`
   * at every call-site. */
  nationalElection(eventId: string): string {
    return withBase(`/t/elections/${encodeURIComponent(eventId)}`);
  },

  /** Election lab (`/lab/<state>/<event>`). Existing surface; retained
   * verbatim from `url.ts`. */
  electionLab(stateCodeOrSlug: string, event: string): string {
    return withBase(`/lab/${stateSlug(stateCodeOrSlug)}/${event}`);
  },

  /** Short alias for `electionLab` mirroring `url.lab` from url.ts. */
  lab(stateCodeOrSlug: string, event: string): string {
    return withBase(`/lab/${stateSlug(stateCodeOrSlug)}/${event}`);
  },

  /** Method-aware Psephlab (`/lab/<state>/<event>/m/<method>`). The
   * method id is opaque to the builder; the receiving CountingRule
   * registry resolves it. */
  labMethod(
    stateCodeOrSlug: string,
    event: string,
    method_id: string,
  ): string {
    return withBase(
      `/lab/${stateSlug(stateCodeOrSlug)}/${event}/m/${encodeURIComponent(method_id)}`,
    );
  },

  // PR-W5a (2026-06-10): `electionCompare`, the `compare` short alias,
  // and `compareMethod` retired. Their sole routes were the legacy
  // 3-segment `/compare/:state/:event` and 4-segment
  // `/compare/:state/:event/m/:method` patterns that were deleted in
  // the same PR alongside `Compare.svelte`. The path-form
  // `compareElections` below is the replacement.

  /** Path-form election-vs-election compare cascade
   * (`/compare/elections/<state>/<from-event>/<to-event>`).
   *
   * PR-W4b (election experience overhaul, 2026-06-10): body-tagged
   * compare per the binding constraint #7 in the plan-doc preamble.
   * Distinct from `compareIndicator()` (a different surface) by both
   * literal `elections` in seg 2 and the path-form parameters. */
  compareElections(
    stateCodeOrSlug: string,
    fromEvent: string,
    toEvent: string,
  ): string {
    return withBase(
      `/compare/elections/${stateSlug(stateCodeOrSlug)}/${encodeURIComponent(fromEvent)}/${encodeURIComponent(toEvent)}`,
    );
  },

  /** Cross-state indicator compare (`/compare[?i=<id>&states=<csv>&peer=<peer>]`).
   * All three fields are optional; the `?` is omitted when every field
   * is empty (renders the friendly chooser at /compare). */
  compareIndicator(
    opts: {
      indicator?: string | null;
      states?: string[];
      peer?: string | null;
    } = {},
  ): string {
    const params = new URLSearchParams();
    if (opts.indicator) params.set("i", opts.indicator);
    if (opts.states && opts.states.length > 0)
      params.set("states", opts.states.join(","));
    if (opts.peer) params.set("peer", opts.peer);
    const s = params.toString();
    return withBase(s ? `/compare?${s}` : "/compare");
  },

  /** Per-indicator documentation (`/docs/indicator/<topic>/<id>`). The
   * indicatorId is the catalogue's 2-segment form (e.g. `fiscal/outstanding_debt_pct_gsdp`);
   * the embedded slash is NOT URL-encoded so the router pattern
   * `/docs/indicator/:topic/:id` matches the canonical 2-segment form
   * directly. */
  indicatorDoc(indicatorId: string): string {
    return withBase(`/docs/indicator/${indicatorId}`);
  },

  /** Counting-rule documentation (`/docs/lab/<method_id>`). Mirrors
   * `indicatorDoc()` shape: one generic CountingMethodDoc.svelte route
   * reads TS-constant caveat + assumptions from the rule registry. */
  docsLabMethod(method_id: string): string {
    return withBase(`/docs/lab/${encodeURIComponent(method_id)}`);
  },

  /** About page (`/about`, with optional `?section=` encoded). */
  about(section?: string): string {
    return withBase(
      section ? `/about?section=${encodeURIComponent(section)}` : "/about",
    );
  },

  /** Settings (`/settings`). */
  settings(): string {
    return withBase("/settings");
  },

  /** Disclaimer (`/disclaimer`). */
  disclaimer(): string {
    return withBase("/disclaimer");
  },

  /** Citizen transparency surface (`/data-completeness`). */
  dataCompleteness(): string {
    return withBase("/data-completeness");
  },
};

/**
 * Reserved positional tokens. No state slug, topic slug, indicator slug,
 * or AC slug may equal any reserved token. The disjointness contract in
 * `frontend/src/contracts/url-namespace-disjointness.test.ts` asserts
 * this against the real shipped corpus.
 *
 * Reservation rationale:
 *   * `t`            — topic-namespace marker (`/t`, `/t/<topic>`, `/<state>/t/<topic>`)
 *   * `compare`      — cross-surface compare home (`/compare`, `/compare/<state>/<event>`)
 *   * `about`        — chrome
 *   * `settings`     — chrome
 *   * `disclaimer`   — chrome
 *   * `data-completeness` — citizen transparency surface
 *   * `lab`          — election lab namespace marker (`/lab/<state>/<event>`)
 *   * `dev`          — dev-only Vite alias (existing reservation)
 *   * `ac`           — bare-AC sub-namespace marker (`/<state>/ac/<ac>`,
 *                      `/<state>/elections/<event>/ac/<ac>`)
 *   * `parties`      — top-level parties index (`/parties`) +
 *                      per-party page (`/parties/<slug>`) per ADR-0053.
 *                      Replaced the legacy state-scoped `party` (singular)
 *                      reservation in PR-0 of the party-rendering plan
 *                      (rip-and-replace; no strangler-fig redirect).
 *   * `i`            — pre-reserved fallback for the future indicator-marker
 *                      retrofit Max named (when collision test first fires)
 *   * `explore`      — state-explore sub-surface marker (`/<state>/explore`)
 *   * `d`            — Deferral 1 (2026-06-10) deleted the
 *                      `/:state/d/:district` route entry and flipped
 *                      district URLs to positional (`/<state>/<district>`).
 *                      Per Jony rule #3, `d` STAYS reserved as a future
 *                      escape-hatch so a citizen who types `/<state>/d`
 *                      on the address bar lands on the 404 instead of
 *                      being poached by a hypothetical future district
 *                      named "D". To revert Deferral 1, restore the
 *                      `/:state/d/:district` route entry in main.ts AND
 *                      drop `d` from this array.
 *
 * Removed in PR-P4 (2026-06-10): `s` was the Grammar B prefix anchor
 * for `RedirectLegacyUrl.svelte`; both are deleted in PR-P4 and the
 * token is freed. The 4-phase URL-prefix-drop strangler-fig is complete.
 */
export const RESERVED_PATH_TOKENS = Object.freeze([
  "t",
  "compare",
  "about",
  "settings",
  "disclaimer",
  "data-completeness",
  "lab",
  "dev",
  "ac",
  "parties",
  "i",
  "explore",
  "d",
] as const);

export type ReservedPathToken = (typeof RESERVED_PATH_TOKENS)[number];
