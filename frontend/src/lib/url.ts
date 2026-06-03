// Single source of truth for in-app URL construction and navigation.
//
// Every internal `<a href>` and programmatic navigation goes through here.
// That gives us:
//
//   * One place to honour `import.meta.env.BASE_URL` so the app works at
//     both `/` (custom domain) and `/yen-gov/` (project Pages subpath).
//   * One place that owns the hash-vs-history decision. Today the router
//     is history-based (clean paths); a switch back to hash routing would
//     be a one-line change here, not a 50-file diff.
//   * One place that knows how to turn a state's ECI code + an AC's eci_no
//     into the slugified URL form, so callers don't reinvent the format.

import { acSlug, partySlug } from "./slug";
import { states } from "./states.svelte";

const BASE = import.meta.env.BASE_URL; // always ends in '/'

/**
 * Prefix a path with the deploy base URL. Inputs MUST start with `/`;
 * we collapse the duplicate slash that would otherwise appear when BASE
 * is `/yen-gov/`.
 */
export function withBase(path: string): string {
  if (!path.startsWith("/")) path = "/" + path;
  return BASE.replace(/\/$/, "") + path;
}

/** Strip the deploy base from `location.pathname` to get the route path. */
export function stripBase(pathname: string): string {
  const baseNoSlash = BASE.replace(/\/$/, "");
  if (baseNoSlash && pathname.startsWith(baseNoSlash)) {
    const tail = pathname.slice(baseNoSlash.length);
    return tail === "" ? "/" : tail;
  }
  return pathname || "/";
}

/**
 * Programmatic navigation — pushes a new entry; triggers the router.
 *
 * Accepts a URL produced by one of the `url.X()` builders above (i.e. already
 * base-prefixed). We deliberately do NOT call `withBase()` here: every call
 * site uses a builder, and double-prefixing produced `/yen-gov/yen-gov/...`
 * URLs on project Pages deploys. As a safety net, an unprefixed path that
 * starts with `/` is auto-prefixed so legacy/raw paths still work.
 */
export function navigate(path: string, opts: { replace?: boolean } = {}): void {
  const baseNoSlash = BASE.replace(/\/$/, "");
  const alreadyPrefixed =
    !!baseNoSlash && (path === baseNoSlash || path.startsWith(baseNoSlash + "/"));
  const target = alreadyPrefixed ? path : withBase(path);
  if (opts.replace) history.replaceState(null, "", target);
  else history.pushState(null, "", target);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/**
 * URL builders. Every page that wants an in-app link calls one of these
 * instead of constructing strings inline. The `state` argument may be EITHER
 * an ECI code (`S22`) OR an LGD slug (`tamil-nadu`):
 *  - ECI code -> resolved via `states.slug()` to the LGD slug.
 *  - LGD slug -> passes through `states.slug()` (no match) and the
 *    `|| stateCode.toLowerCase()` fallback returns the slug as-is.
 * Both paths produce the same `/s/<lgd-slug>` URL form per ADR-0048 /
 * ADR-0050. New callers SHOULD prefer passing slugs directly; the ECI
 * acceptance is for backwards compatibility with view-models keyed on
 * ECI codes (the relational join key in dim_acs / dim_pcs).
 */
export const url = {
  home(): string {
    return withBase("/");
  },
  about(section?: string): string {
    return withBase(section ? `/about?section=${encodeURIComponent(section)}` : "/about");
  },
  settings(): string {
    return withBase("/settings");
  },
  state(stateCode: string): string {
    return withBase(`/s/${states.slug(stateCode) || stateCode.toLowerCase()}`);
  },
  ac(stateCode: string, eci_no: number, name: string, event?: string | null): string {
    const slug = states.slug(stateCode) || stateCode.toLowerCase();
    const acSeg = acSlug(eci_no, name);
    // ADR-0052: the election event is resource identity, so it lives in the
    // path nested under /elections/<event>. The bare /ac/ form (no event) is
    // the convenience entry that redirects to the default-event nested URL.
    return withBase(
      event
        ? `/s/${slug}/elections/${encodeURIComponent(event)}/ac/${acSeg}`
        : `/s/${slug}/ac/${acSeg}`,
    );
  },
  // AC link without a name (used by callers that don't have one to hand).
  acByNo(stateCode: string, eci_no: number, event?: string | null): string {
    const slug = states.slug(stateCode) || stateCode.toLowerCase();
    // ADR-0052: event in path (see `ac()` above).
    return withBase(
      event
        ? `/s/${slug}/elections/${encodeURIComponent(event)}/ac/${eci_no}`
        : `/s/${slug}/ac/${eci_no}`,
    );
  },
  party(stateCode: string, partyEciCode: string, shortName: string): string {
    const slug = partySlug(shortName, partyEciCode);
    return withBase(`/s/${states.slug(stateCode) || stateCode.toLowerCase()}/party/${slug}-${partyEciCode.toLowerCase()}`);
  },
  explore(stateCode: string): string {
    return withBase(`/s/${states.slug(stateCode) || stateCode.toLowerCase()}/explore`);
  },
  lab(stateCode: string, event: string): string {
    return withBase(`/lab/${states.slug(stateCode) || stateCode.toLowerCase()}/${event}`);
  },
  compare(stateCode: string, event: string): string {
    return withBase(`/compare/${states.slug(stateCode) || stateCode.toLowerCase()}/${event}`);
  },
  /** Topic Front Door index — `/t`. (P3.3b, ADR-0022.) */
  topics(): string {
    return withBase("/t");
  },
  /** Topic landing — `/t/<topic-id>`. (P3.3a, ADR-0022.) */
  topic(topicId: string): string {
    return withBase(`/t/${topicId}`);
  },
  /**
   * Per-state topic page — `/s/<state-slug>/t/<topic-id>`. (IA-reset
   * Step #2.) The state slug is derived the same way as `state()` so
   * the URL shape stays citizen-readable; the topic id stays opaque
   * (catalogue key), matching `topic()`.
   */
  stateTopic(stateCode: string, topicId: string): string {
    const slug = states.slug(stateCode) || stateCode.toLowerCase();
    return withBase(`/s/${slug}/t/${encodeURIComponent(topicId)}`);
  },
  /**
   * Per-state per-event election landing — `/s/<state-slug>/elections/<event-id>`.
   *
   * Citizen-readable deep link to a specific election cohort for a state
   * (e.g. `/s/tamil-nadu/elections/AcGenMay2026`). The route is the shareable
   * permalink for "this state's results for THIS election" and the natural
   * link target from the `/s/<state>/t/elections` topic page's default-event
   * card. Distinct from `lab(state, event)` (analyst surface) and
   * `compare(state, event)` (cross-state results compare): this is the
   * neutral citizen landing that doesn't pre-commit to either tool.
   *
   * The event id is the ECI cohort code from `taxonomy/election_events.json`
   * (e.g. `AcGenMay2026`, `LsGen2024`) — opaque to citizens but stable and
   * already used as the URL token on `/lab/` and `/compare/`.
   */
  stateElection(stateCode: string, eventId: string): string {
    const slug = states.slug(stateCode) || stateCode.toLowerCase();
    return withBase(`/s/${slug}/elections/${encodeURIComponent(eventId)}`);
  },
  /**
   * Generic indicator Compare — `/compare?i=<id>&states=<csv>&peer=<peer>`.
   * (P4, ADR-0022.) Distinct from `compare(state, event)` which is the
   * election-results compare under `/compare/:state/:event`. All three
   * fields are optional; the page renders a friendly chooser when `i` is
   * absent. The `?` is omitted when every field is empty.
   */
  compareIndicator(
    opts: { indicator?: string | null; states?: string[]; peer?: string | null } = {},
  ): string {
    const params = new URLSearchParams();
    if (opts.indicator) params.set("i", opts.indicator);
    if (opts.states && opts.states.length > 0) params.set("states", opts.states.join(","));
    if (opts.peer) params.set("peer", opts.peer);
    const s = params.toString();
    return withBase(s ? `/compare?${s}` : "/compare");
  },
  /** Citizen transparency surface — `/data-completeness`. */
  dataCompleteness(): string {
    return withBase("/data-completeness");
  },
  /** Legal-style framing — `/disclaimer`. */
  disclaimer(): string {
    return withBase("/disclaimer");
  },
};
