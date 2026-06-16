// Per-route breadcrumb builders.
//
// PR-W1d (election experience overhaul, 2026-06-10): each registered
// route in main.ts owns a `crumbs(params): Crumb[]` function. This
// module collects them in one place so they stay testable as pure
// functions (vitest runs in node-env per /memories/lessons.md +
// GeoBreadcrumb.svelte's `computeCrumbs` precedent; mounting Svelte
// components needs jsdom + @testing-library/svelte which the project
// intentionally does not install). main.ts imports the builders by
// name and assigns them to each Route entry's `crumbs` field.
//
// Reactivity contract: each builder reads `states` reactively. When
// the consumer wraps `route.crumbs?.(route.params)` in `$derived`,
// the derivation re-runs on (a) navigation (route.params changes),
// (b) state catalogue async-load (states.entries changes). Builders
// fall back to `slugToTitle(slug)` when the states store has not
// resolved yet so the breadcrumb is never blank.
//
// Citizen-facing label policy (PR-W1d, supersedes the U2b
// "India" leaf): the root crumb label is "Home". Per the parent
// plan-doc 20260609-election-experience-overhaul-plan.md PR-W1d
// scope brief.

import { link } from "./links";
import { parseAcSlug } from "./slug";
import { states } from "./states.svelte";
import type { Crumb } from "./breadcrumb-types";

/**
 * Title-case a dash-separated slug. Used wherever the URL token IS
 * the display name's slugified form and no catalogue resolver is
 * available. `"north-24-parganas"` -> `"North 24 Parganas"`.
 */
function slugToTitle(slug: string): string {
  return slug
    .split("-")
    .filter(s => s.length > 0)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * Resolve a state slug to its citizen-visible label. Reads the
 * reactive `states` catalogue; falls back to the title-cased slug
 * when the catalogue has not yet loaded OR the slug is unknown.
 * The fallback keeps the breadcrumb visible during the catalogue
 * fetch (states.json on first paint) AND makes the per-builder
 * tests trivial - no test fixture or store mocking required.
 */
function stateLabel(stateSlug: string): string {
  const code = states.codeFromSlug(stateSlug);
  const name = code ? states.name(code) : "";
  return name || slugToTitle(stateSlug);
}

/**
 * Recover the AC display name from an AC slug. The slug shape under
 * the canonical nested route is `<eci_no>-<name-slug>` (e.g.
 * `167-mylapore`). Bare `<eci_no>` (no name half) renders as
 * `"AC <n>"`. Pure-name slugs (post-ADR-0037 §AC-slug) fall through
 * to slugToTitle.
 */
function acLabelFromSlug(slug: string): string {
  const eci_no = parseAcSlug(slug);
  if (eci_no === null) return slugToTitle(slug);
  const dash = slug.indexOf("-");
  if (dash < 0) return `AC ${eci_no}`;
  return slugToTitle(slug.slice(dash + 1));
}

// Root crumb. `home: leaf` for the Home route only; everywhere else
// the root is an ascend link.
const ROOT_LEAF: Crumb = { label: "Home", isLeaf: true };
const ROOT_LINK: Crumb = { label: "Home", href: link.home() };

// =============================================================
// Chrome literals
// =============================================================

export function homeCrumbs(): Crumb[] {
  return [ROOT_LEAF];
}

export function settingsCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Settings", isLeaf: true }];
}

export function aboutCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "About", isLeaf: true }];
}

export function disclaimerCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Disclaimer", isLeaf: true }];
}

export function topicIndexCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Topics", isLeaf: true }];
}

export function compareIndicatorCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Compare", isLeaf: true }];
}

export function dataCompletenessCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Data completeness", isLeaf: true }];
}

export function devChartsSandboxCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Charts sandbox", isLeaf: true }];
}

export function yenaskCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Yen-Ask", isLeaf: true }];
}

export function notFoundCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Not found", isLeaf: true }];
}

// =============================================================
// National election + topic surfaces
// =============================================================

export function nationalElectionCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  // PR-W3c (2026-06-10): 3-crumb trail per the election experience
  // overhaul plan brief. Drops the intermediate "Topics" crumb the
  // pre-rebuild atlas carried (it descended via the topic-landing
  // ascend chain); the citizen's mental model on a national event view
  // is "Home -> Elections firehose -> this event", not "Home -> Topics
  // -> Elections -> this event". The middle crumb links to
  // /t/elections; PR-W3d ships the firehose there - until then the
  // existing TopicLanding handles `/t/elections` as the elections topic
  // page, which is a sensible parent for now.
  const event = typeof params.event === "string" ? params.event : "";
  return [
    ROOT_LINK,
    { label: "Elections", href: link.topicLanding("elections") },
    { label: event, isLeaf: true },
  ];
}

export function topicLandingCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  const topic = typeof params.topic === "string" ? params.topic : "";
  return [
    ROOT_LINK,
    { label: "Topics", href: link.topicsIndex() },
    { label: slugToTitle(topic), isLeaf: true },
  ];
}

/**
 * General elections (`/t/elections`). PR-E4 (2026-06-15) of the
 * elections-redesign-plan renames the firehose to the General-elections
 * route. Two-crumb trail (Home -> General elections leaf) matches the
 * nationalElection chain's middle crumb so a per-event drill-down sits
 * one level deeper.
 */
export function generalElectionsCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "General elections", isLeaf: true }];
}

/**
 * Assembly elections (`/t/elections/assemblies`). New route in PR-E4
 * (2026-06-15). Two-crumb trail (Home -> Assembly elections leaf); the
 * tab strip on the page surfaces the General-elections sibling.
 */
export function assemblyElectionsCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Assembly elections", isLeaf: true }];
}

// =============================================================
// Election lab / compare (state + event scoped)
// =============================================================

function stateElectionAscendChain(
  stateSlug: string,
  event: string,
): Crumb[] {
  const sName = stateLabel(stateSlug);
  return [
    ROOT_LINK,
    { label: sName, href: link.stateHub(stateSlug) },
    { label: `${sName} elections`, href: link.stateTopic(stateSlug, "elections") },
    { label: event, href: link.stateElection(stateSlug, event) },
  ];
}

export function psephlabCrumbs(params: Record<string, unknown>): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const event = typeof params.event === "string" ? params.event : "";
  const method = typeof params.method === "string" ? params.method : null;
  const chain = stateElectionAscendChain(stateSlug, event);
  if (method) {
    return [
      ...chain,
      { label: "Lab", href: link.electionLab(stateSlug, event) },
      { label: method, isLeaf: true },
    ];
  }
  return [...chain, { label: "Lab", isLeaf: true }];
}

// PR-W5a (2026-06-10): `compareCrumbs` retired. Its sole consumers were
// the two legacy compare routes (`/compare/:state/:event` and
// `/compare/:state/:event/m/:method`) that were deleted in the same PR
// alongside `Compare.svelte`. The path-form `compareElectionsCrumbs`
// below remains for `/compare/elections/<state>/<from>/<to>`.

/**
 * Path-form election-vs-election compare cascade
 * (`/compare/elections/<state>/<from-event>/<to-event>`).
 *
 * PR-W4b (election experience overhaul, 2026-06-10): four-crumb trail
 * matching the new compare surface. The middle crumbs ascend to the
 * state hub + state-elections topic (parent of every event view) so a
 * citizen on a compare page can drop back to the state's elections
 * landing without re-typing the URL. The leaf label is "<from> vs
 * <to>" so the breadcrumb reads as the page's title.
 */
export function compareElectionsCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const fromEvent =
    typeof params.fromEvent === "string" ? params.fromEvent : "";
  const toEvent = typeof params.toEvent === "string" ? params.toEvent : "";
  const sName = stateLabel(stateSlug);
  return [
    ROOT_LINK,
    { label: sName, href: link.stateHub(stateSlug) },
    {
      label: `${sName} elections`,
      href: link.stateTopic(stateSlug, "elections"),
    },
    { label: `${fromEvent} vs ${toEvent}`, isLeaf: true },
  ];
}

// =============================================================
// Docs
// =============================================================

export function indicatorDocCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  // The router's `parse` collapses topic+id into `indicator_id`; the
  // raw `topic` + `id` segments are still present in params from the
  // pattern compiler so the chain can name both.
  const topic = typeof params.topic === "string" ? params.topic : "";
  const id = typeof params.id === "string" ? params.id : "";
  return [
    ROOT_LINK,
    { label: "Docs", isLeaf: false },
    { label: slugToTitle(topic), isLeaf: false },
    { label: slugToTitle(id), isLeaf: true },
  ];
}

export function countingMethodDocCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  const method = typeof params.method === "string" ? params.method : "";
  return [
    ROOT_LINK,
    { label: "Docs", isLeaf: false },
    { label: method, isLeaf: true },
  ];
}

// =============================================================
// Place-first cascade (Grammar A)
// =============================================================

export function constituencyCanonicalCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  // Canonical nested form: /<state>/elections/<event>/ac/<ac>.
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const event = typeof params.event === "string" ? params.event : "";
  const ac = typeof params.ac_slug === "string" ? params.ac_slug : "";
  const sName = stateLabel(stateSlug);
  return [
    ROOT_LINK,
    { label: sName, href: link.stateHub(stateSlug) },
    { label: `${sName} elections`, href: link.stateTopic(stateSlug, "elections") },
    { label: event, href: link.stateElection(stateSlug, event) },
    { label: acLabelFromSlug(ac), isLeaf: true },
  ];
}

export function constituencyBareCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  // Bare-AC convenience: /<state>/ac/<ac>. Three crumbs (Constituency
  // resolves the state's default event and replaceState-redirects to
  // the canonical nested form before the first paint usually
  // completes, but the crumbs MUST render correctly during the brief
  // pre-redirect window).
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const ac = typeof params.ac_slug === "string" ? params.ac_slug : "";
  return [
    ROOT_LINK,
    { label: stateLabel(stateSlug), href: link.stateHub(stateSlug) },
    { label: acLabelFromSlug(ac), isLeaf: true },
  ];
}

/** PR-W3b constituency leaf: /<state>/elections/<event>/<constituency>.
 *  Five crumbs ending in the bare constituency-name slug. Mirrors the
 *  ascend chain of `constituencyCanonicalCrumbs` (the same route's
 *  legacy 5-segment AC-only sibling) so a citizen who arrives via the
 *  bare-slug URL sees the same breadcrumb shape. */
export function constituencyLeafCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const event = typeof params.event === "string" ? params.event : "";
  const constituency =
    typeof params.constituency_slug === "string"
      ? params.constituency_slug
      : "";
  const sName = stateLabel(stateSlug);
  return [
    ROOT_LINK,
    { label: sName, href: link.stateHub(stateSlug) },
    { label: `${sName} elections`, href: link.stateTopic(stateSlug, "elections") },
    { label: event, href: link.stateElection(stateSlug, event) },
    { label: slugToTitle(constituency), isLeaf: true },
  ];
}

export function partiesIndexCrumbs(): Crumb[] {
  return [ROOT_LINK, { label: "Parties", isLeaf: true }];
}

export function partyCrumbs(params: Record<string, unknown>): Crumb[] {
  // Per ADR-0053 (PR-0 of the party-rendering plan, 2026-06-12): the
  // per-party page is party-scoped at `/parties/<slug>` (not the
  // legacy state-scoped `/<state>/party/<slug>`). The slug is the
  // lowercased `party_id` tail with `_` -> `-`; sentinel overrides:
  // IND -> "independent", NOTA -> "nota", UNK -> no page.
  //
  // Breadcrumb label policy: pre-data-load, the leaf is the title-
  // cased slug (`Inc`, `Bjp`, `Cpi-m`). The Party.svelte page sets
  // its own H1 from the parties.csv `short` once loaded; the
  // breadcrumb stays driven by the URL slug for the no-flicker case.
  const slug = typeof params.slug === "string" ? params.slug : "";
  return [
    ROOT_LINK,
    { label: "Parties", href: link.parties() },
    { label: slugToTitle(slug), isLeaf: true },
  ];
}

export function districtCrumbs(params: Record<string, unknown>): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const district = typeof params.district_slug === "string" ? params.district_slug : "";
  return [
    ROOT_LINK,
    { label: stateLabel(stateSlug), href: link.stateHub(stateSlug) },
    { label: slugToTitle(district), isLeaf: true },
  ];
}

export function stateTopicCrumbs(params: Record<string, unknown>): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const topic = typeof params.topic === "string" ? params.topic : "";
  return [
    ROOT_LINK,
    { label: stateLabel(stateSlug), href: link.stateHub(stateSlug) },
    { label: slugToTitle(topic), isLeaf: true },
  ];
}

export function stateElectionCrumbs(params: Record<string, unknown>): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const event = typeof params.event === "string" ? params.event : "";
  const sName = stateLabel(stateSlug);
  return [
    ROOT_LINK,
    { label: sName, href: link.stateHub(stateSlug) },
    { label: `${sName} elections`, href: link.stateTopic(stateSlug, "elections") },
    { label: event, isLeaf: true },
  ];
}

/** Crumbs for `/<state>/elections/` landing (R2 of the state-event-page
 * redesign plan, 2026-06-15). One short hop from the state hub to the
 * landing list; the leaf is the literal "elections". */
export function stateElectionsLandingCrumbs(
  params: Record<string, unknown>,
): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  const sName = stateLabel(stateSlug);
  return [
    ROOT_LINK,
    { label: sName, href: link.stateHub(stateSlug) },
    { label: `${sName} elections`, isLeaf: true },
  ];
}

export function exploreCrumbs(params: Record<string, unknown>): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  return [
    ROOT_LINK,
    { label: stateLabel(stateSlug), href: link.stateHub(stateSlug) },
    { label: "Explore", isLeaf: true },
  ];
}

export function stateOverviewCrumbs(params: Record<string, unknown>): Crumb[] {
  const stateSlug = typeof params.state === "string" ? params.state : "";
  return [
    ROOT_LINK,
    { label: stateLabel(stateSlug), isLeaf: true },
  ];
}
