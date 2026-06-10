// Grammar A URL builders — the end-state place-first cascade per ADR-0037.
//
// This module is the FUTURE single source of truth for in-app route URLs.
// It ships in Phase 1 of the Grammar A migration with ZERO call-sites; the
// existing `frontend/src/lib/url.ts` continues to own the live `/s/<state>/...`
// builders (Grammar B) and PR #172's 42-test contract stays green against
// it. Phase 2 migrates call-sites from `url.ts` to `links.ts` one component
// at a time; Phase 4 deletes the `url.ts` legacy layer.
//
// Module name: `links.ts` because the artefact `link.stateHub("S22")`
// emits is what `<a href={...}>` consumes. The existing `paths.ts` already
// holds the runtime DATA_BASE prefix (a different concern), so reusing
// that name would mix two unrelated responsibilities.
//
// Why a parallel module instead of mutating `url.ts`:
//   * `url.ts` returns Grammar B shape; `links.ts` returns Grammar A shape.
//     The two cannot share a body without one silently mis-routing.
//   * The two builders coexisting lets Phase 2 ship per-component
//     migrations reversibly — each `<a href>` swap is a one-line diff.
//   * The 42-test contract in `url.test.ts` keeps testing the live shape.
//     A new test file (`links.test.ts`) tests Grammar A independently.
//
// See also:
//   * ADR-0037 — the binding decision, the three-voice digest, the
//     four-phase strangler-fig, and the open user-gate questions.
//   * frontend/src/lib/url.ts — the Grammar B builders being superseded.
//   * frontend/src/lib/slug.ts — the slugify primitive shared with url.ts.
//   * frontend/src/lib/paths.ts — the (unrelated) DATA_BASE prefix module.

import { slugify } from "./slug";
import { states } from "./states.svelte";
import { partySlug as buildPartySlug } from "./slug";

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

  /** Party-in-state (`/tamil-nadu/party/<slug>`). The `/party/` segment
   * is a sub-namespace marker under the state; it is INSIDE a state
   * namespace, not at root, so it doesn't reserve a top-level token. */
  partyInState(stateCodeOrSlug: string, partySlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}/party/${partySlug}`);
  },

  /** Party-in-state convenience that builds the canonical
   * `<short_name>-<eci_code_lower>` slug from caller-supplied bits.
   * Mirrors `url.party` from url.ts so the migration is a one-line
   * swap without touching the slug-building call-site. */
  party(
    stateCodeOrSlug: string,
    partyEciCode: string,
    shortName: string,
  ): string {
    const slug = buildPartySlug(shortName, partyEciCode);
    return withBase(
      `/${stateSlug(stateCodeOrSlug)}/party/${slug}-${partyEciCode.toLowerCase()}`,
    );
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

  /** Per-state district landing (`/<state>/d/<district-slug>`). The
   * `/d/` marker is retained as the disambiguator from the indicator
   * slug namespace (per ADR-0037 routing.md: positional `<state>/<x>`
   * dispatch is deferred; the `/d/` marker stays as the explicit form). */
  district(stateCodeOrSlug: string, districtSlug: string): string {
    return withBase(`/${stateSlug(stateCodeOrSlug)}/d/${districtSlug}`);
  },

  /** Per-state per-event election landing (`/<state>/elections/<event>`).
   * Neutral citizen permalink; distinct from Psephlab and Compare. */
  stateElection(stateCodeOrSlug: string, eventId: string): string {
    return withBase(
      `/${stateSlug(stateCodeOrSlug)}/elections/${encodeURIComponent(eventId)}`,
    );
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

  /** Election compare (`/compare/<state>/<event>`). Existing surface;
   * retained verbatim from `url.ts`. Distinct from the cross-state
   * indicator-compare surface which (per ADR-0037 §cross-state) collapses
   * into the indicator page itself in Phase 3+. */
  electionCompare(stateCodeOrSlug: string, event: string): string {
    return withBase(`/compare/${stateSlug(stateCodeOrSlug)}/${event}`);
  },

  /** Short alias for `electionCompare` mirroring `url.compare` from
   * url.ts. (Distinct from `compareIndicator()` which is the cross-state
   * indicator-compare surface.) */
  compare(stateCodeOrSlug: string, event: string): string {
    return withBase(`/compare/${stateSlug(stateCodeOrSlug)}/${event}`);
  },

  /** Method-aware election Compare (`/compare/<state>/<event>/m/<method>`).
   * Both sides share the active method (per-side override is deferred
   * per the 2026-06-09 Fowler verdict on the redesign). */
  compareMethod(
    stateCodeOrSlug: string,
    event: string,
    method_id: string,
  ): string {
    return withBase(
      `/compare/${stateSlug(stateCodeOrSlug)}/${event}/m/${encodeURIComponent(method_id)}`,
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
 *   * `s`            — legacy Grammar B state marker (redirect anchor through Phase 4b)
 *   * `ac`           — legacy Grammar B AC marker (redirect anchor through Phase 4b)
 *   * `party`        — party-in-state sub-namespace marker (`/<state>/party/<slug>`)
 *   * `i`            — pre-reserved fallback for the future indicator-marker
 *                      retrofit Max named (when collision test first fires)
 *   * `explore`      — state-explore sub-surface marker (`/<state>/explore`)
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
  "s",
  "ac",
  "party",
  "i",
  "explore",
] as const);

export type ReservedPathToken = (typeof RESERVED_PATH_TOKENS)[number];
