// Token layer first (CLAUDE.md doctrine + plan section 21.7) so app.css
// and any later component CSS may reference --ink / --accent / --r-md
// etc. Mirrored ADDITIVELY into tailwind.config.js theme.extend per
// plan section 23.5; drift locked by frontend/src/contracts/app-tokens.test.ts.
import "./app-tokens.css";
import "./app.css";
import { mount } from "svelte";
import { startRouter } from "./lib/router.svelte";
import { parseAcSlug } from "./lib/slug";
import { prewarmDB } from "./lib/duckdb";
import LeftRail from "./lib/LeftRail.svelte";
import Home from "./routes/Home.svelte";
import StateOverview from "./routes/StateOverview.svelte";
import Constituency from "./routes/Constituency.svelte";
import Party from "./routes/Party.svelte";
import PartiesIndex from "./routes/PartiesIndex.svelte";
import Explore from "./routes/Explore.svelte";
import Settings from "./routes/Settings.svelte";
import Psephlab from "./routes/Psephlab.svelte";
import CompareElections from "./routes/CompareElections.svelte";
import CompareIndicator from "./routes/CompareIndicator.svelte";
import About from "./routes/About.svelte";
import Disclaimer from "./routes/Disclaimer.svelte";
import TopicIndex from "./routes/TopicIndex.svelte";
import TopicLanding from "./routes/TopicLanding.svelte";
import StateTopic from "./routes/StateTopic.svelte";
import StateElection from "./routes/StateElection.svelte";
// District + Constituency + NotFound are mounted INSIDE StateSubRouter
// (the depth-2 state-sub dispatcher) so main.ts no longer imports them
// directly. The 1-segment `/:state` catch-all still mounts StateOverview;
// the canonical 5-segment `/:state/elections/:event/ac/:ac` still mounts
// Constituency directly via its own route entry below.
import StateSubRouter from "./routes/StateSubRouter.svelte";
import NationalElection from "./routes/NationalElection.svelte";
import ElectionsFirehose from "./routes/ElectionsFirehose.svelte";
import DataCompleteness from "./routes/DataCompleteness.svelte";
import DevChartsSandbox from "./routes/DevChartsSandbox.svelte";
import Yenask from "./routes/Yenask.svelte";
import IndicatorDoc from "./routes/IndicatorDoc.svelte";
import CountingMethodDoc from "./routes/CountingMethodDoc.svelte";
import NotFound from "./routes/NotFound.svelte";
import {
  aboutCrumbs,
  compareElectionsCrumbs,
  compareIndicatorCrumbs,
  constituencyBareCrumbs,
  constituencyCanonicalCrumbs,
  constituencyLeafCrumbs,
  countingMethodDocCrumbs,
  dataCompletenessCrumbs,
  devChartsSandboxCrumbs,
  disclaimerCrumbs,
  electionsFirehoseCrumbs,
  exploreCrumbs,
  homeCrumbs,
  indicatorDocCrumbs,
  nationalElectionCrumbs,
  notFoundCrumbs,
  partiesIndexCrumbs,
  partyCrumbs,
  psephlabCrumbs,
  settingsCrumbs,
  stateElectionCrumbs,
  stateOverviewCrumbs,
  stateTopicCrumbs,
  topicIndexCrumbs,
  topicLandingCrumbs,
  yenaskCrumbs,
} from "./lib/route-crumbs";

// Mount the persistent shell once. The router replaces the contents of
// #route on every navigation; the rail at #rail stays mounted. Layout is
// a flex row on lg+ (rail | content); below lg the rail floats over the
// content as a slide-in drawer (LeftRail handles the responsive switch).
// The breakpoint is lg (1024px) — not md — so mid-width tablets and small
// laptops aren't squeezed by a 240px static rail.
const app = document.getElementById("app")!;
app.innerHTML = `
  <div class="lg:flex lg:items-stretch lg:min-h-screen">
    <div id="rail"></div>
    <main id="route" class="flex-1 min-w-0"></main>
  </div>
`;
mount(LeftRail, { target: document.getElementById("rail")! });

// Kick off the DuckDB-WASM boot in parallel with route hydration. Every
// citizen-facing surface that surfaces a choropleth (Home, /t/<topic>,
// /<state>, /<state>/t/<topic>) eventually calls registerCsvAsTable /
// registerTable / query against the WASM singleton; if we wait until the
// first such call to start the ~5 MB wasm download + worker spawn +
// instantiate, every choropleth pays a 1-2s cold-boot delay serially.
// Prewarming here moves that work onto the browser's idle-network budget
// while topic-catalogue + Svelte hydration are doing their own fetches.
// Idempotent (the singleton promise dedupes); safe to call
// unconditionally. Routes that genuinely never touch DuckDB (e.g.
// /about, /disclaimer) pay only the bundle download, which has happened
// already because main.ts imported the module.
prewarmDB();

// Route params are slugs (e.g. `tamil-nadu`, `167-mylapore`). Each page
// resolves the slug to its underlying ECI id via the lib/states.svelte
// resolver (state) or by parsing the numeric prefix (AC). Party slugs
// (per ADR-0053) are the lowercased `party_id` tail with `_` -> `-`;
// the per-party page resolves `params.slug` -> `party_id` via
// `partyIdFromSlug` and looks up the parties.csv row.
//
// Route ordering (load-bearing per the first-match-wins resolver):
//   1. Chrome literals (`/`, `/about`, `/settings`, etc.) come FIRST so
//      they always win over the Grammar A `/:state` catch-all.
//   2. Multi-segment literal-rooted routes (`/lab/...`, `/compare/...`,
//      `/docs/...`, `/t/...`) come next; they're segment-count + literal
//      distinguished from Grammar A.
//   3. Grammar A routes follow, most-specific first; the 2-segment
//      `/:state/:position2` depth-2 catch-all (StateSubRouter, dispatches
//      district / AC / chrome-defensive / notfound per ADR-0037 + Deferral
//      1) sits AFTER every literal-marker 2- or 3-segment Grammar A entry
//      (`/:state/explore`, `/:state/ac/:ac`, `/:state/t/:topic`, etc.) and
//      BEFORE the 1-segment `/:state` catch-all. The 1-segment `/:state`
//      stays LAST so it never poaches a literal route.
//
// Per ADR-0037 / TODO/20260609-url-prefix-drop-phase0-plan.md PR-P4
// (shipped 2026-06-10): the Grammar B `/s/*` redirect catch-all and the
// `RedirectLegacyUrl.svelte` tombstone are DELETED. Legacy bookmarks
// for `/s/<state>/...` URLs now fall through to NotFound (404 with
// recovery links). PRs #867/#868/#869 shipped Phases 2-4 of ADR-0037
// (Grammar A live + caller sweep + Grammar B builder deletion); PR-P4
// closes the strangler-fig.
startRouter({
  target: document.getElementById("route")!,
  routes: [
    // === 1. Root + chrome literals (single-segment, MUST come before
    //        the 1-segment Grammar A `/:state` catch-all). ===
    { pattern: "/", component: Home, crumbs: homeCrumbs },
    { pattern: "/settings", component: Settings, crumbs: settingsCrumbs },
    { pattern: "/about", component: About, crumbs: aboutCrumbs },
    { pattern: "/disclaimer", component: Disclaimer, crumbs: disclaimerCrumbs },
    // Topic Front Door (P3.3, ADR-0022).
    { pattern: "/t", component: TopicIndex, crumbs: topicIndexCrumbs },
    // Generic indicator Compare (P4) — sits alongside the more-specific
    // election Compare below; the two patterns don't overlap.
    { pattern: "/compare", component: CompareIndicator, crumbs: compareIndicatorCrumbs },
    // Citizen transparency surface (folded-indicator PR commit 10).
    { pattern: "/data-completeness", component: DataCompleteness, crumbs: dataCompletenessCrumbs },
    // Parties index + per-party detail (ADR-0053, PR-0 of the party-
    // rendering plan 2026-06-12). Top-level `/parties` plural; canonical
    // per-party page at `/parties/<slug>`. Slug = lowercased party_id
    // tail with `_` -> `-`. The disjointness contract
    // (`frontend/src/contracts/url-namespace-disjointness.test.ts`)
    // guarantees no state / topic / AC / indicator slug collides with
    // the reserved `parties` token. The 2-segment `/parties/:slug` route
    // sits BEFORE `/t/:topic` and the `/:state` catch-all because it's
    // pattern-distinct (leading literal `parties`) and most-specific.
    { pattern: "/parties", component: PartiesIndex, crumbs: partiesIndexCrumbs },
    {
      pattern: "/parties/:slug",
      component: Party,
      parse: ({ slug }) => ({ slug }),
      crumbs: partyCrumbs,
    },

    // === 2. Multi-segment literal-rooted routes. ===
    // Phase 6 (charting modernisation plan) — dev sandbox that mounts
    // every Phase 1.6 / 3.5 generic renderer against synthetic fixture
    // data. Not citizen-discoverable; not linked from the left rail.
    { pattern: "/dev/charts-sandbox", component: DevChartsSandbox, crumbs: devChartsSandboxCrumbs },
    // YENASK (display name Yen-Ask) — browser governance insight
    // assistant. Mounted under /lab/ alongside the analyst lab routes
    // (/lab/:state/:event). Dev-only — not citizen-discoverable, not
    // linked from the left rail. See ADR-0040 (brand + lab-route
    // placement) and ADR-0039 (Slice E LLM-OS architecture).
    // Pattern-distinct from /lab/:state/:event (2 vs 3 segments) so
    // route order is not load-bearing. Removal = git rm of
    // routes/Yenask.svelte + lib/yenask/ + this entry.
    { pattern: "/lab/yenask", component: Yenask, crumbs: yenaskCrumbs },
    // Elections firehose (PR-W3d). The bare `/t/elections` lists EVERY
    // election event in the catalogue (Parliament collapsed to one row
    // per event_id, Assembly + bye per-state). MUST be registered
    // BEFORE `/t/elections/:event` and `/t/:topic` because the router
    // is first-match-wins; the parameterised route's regex
    // (`^/t/elections/([^/]+)$`) does not match the bare path but the
    // generic topic route (`^/t/([^/]+)$`) WOULD greedily resolve `/t/elections`
    // to TopicLanding({topic: "elections"}) if placed first. Two-crumb
    // trail (Home -> Elections leaf) matches the middle crumb of
    // `nationalElectionCrumbs` so the chain visually nests.
    { pattern: "/t/elections", component: ElectionsFirehose, crumbs: electionsFirehoseCrumbs },
    // National event view (election experience overhaul, PR-W3c).
    // 3-segment pattern, distinct from /t/:topic (2 segments); placed first
    // so the more-specific route wins regardless of matcher order. The
    // PR-W3c rebuild dropped the per-PC "Map | Equal seats" atlas in favour
    // of a KPIs + per-state choropleth + top-parties summary; the renamed
    // component is `NationalElection.svelte` and the new crumb builder is
    // `nationalElectionCrumbs` (3-crumb trail, drops the intermediate
    // "Topics" crumb the atlas inherited from the topic-landing chain).
    { pattern: "/t/elections/:event", component: NationalElection, crumbs: nationalElectionCrumbs },
    { pattern: "/t/:topic", component: TopicLanding, crumbs: topicLandingCrumbs },
    // Method-first Psephlab route (2026-06-09 redesign, Fowler verdict).
    // 4-segment pattern - distinct from the 3-segment bare lab route by
    // segment count + literal `m`. The method_id is opaque to the router
    // and resolved at render time via `ruleById(method_id)`. Placed
    // BEFORE the 3-segment bare route so a more-specific match wins on
    // any router ordering policy.
    {
      pattern: "/lab/:state/:event/m/:method",
      component: Psephlab,
      parse: ({ state, event, method }) => ({ state, event, method }),
      crumbs: psephlabCrumbs,
    },
    { pattern: "/lab/:state/:event", component: Psephlab, crumbs: psephlabCrumbs },
    // Path-form election-vs-election compare cascade (PR-W4b,
    // 2026-06-10): body-tagged 4-segment shape
    // `/compare/elections/<state>/<from>/<to>`. The previous legacy
    // 3-segment `/compare/:state/:event` and method-aware 4-segment
    // `/compare/:state/:event/m/:method` routes were retired in PR-W5a
    // (2026-06-10) alongside the deletion of Compare.svelte; the
    // disjointness contract bans a state slug equal to `elections`
    // so this 4-segment shape is leading-literal disambiguated from
    // every surviving route.
    {
      pattern: "/compare/elections/:state/:fromEvent/:toEvent",
      component: CompareElections,
      parse: ({ state, fromEvent, toEvent }) => ({ state, fromEvent, toEvent }),
      crumbs: compareElectionsCrumbs,
    },
    // Per-indicator documentation page (U5b, parent plan section 20.12
    // IndicatorDoc bullet). 4-segment pattern with the literal `/docs/`
    // + literal `indicator/` + 2 catalogue-key segments
    // (`<topic>/<id>`), so order is not load-bearing - distinct from
    // every other route by both the `/docs/` literal and the segment
    // count. The two route params recombine into the canonical
    // 2-segment artifact id (`fiscal/outstanding_debt_pct_gsdp`) that
    // `indicatorPathForArtifact` keys against.
    {
      pattern: "/docs/indicator/:topic/:id",
      component: IndicatorDoc,
      parse: ({ topic, id }) => ({ indicator_id: `${topic}/${id}`, topic, id }),
      crumbs: indicatorDocCrumbs,
    },
    // Per-counting-method documentation page (2026-06-09 redesign,
    // Fowler verdict route topology). Mirrors /docs/indicator/ shape:
    // ONE generic CountingMethodDoc.svelte reading TS-constant caveat
    // + assumptions from the rule registry + linking out to authoritative
    // Markdown long-form at docs/concepts/counting-methods/<method>.md.
    // 3-segment pattern with literal `/docs/lab/`, distinct from every
    // other route by both the literal and the segment count.
    {
      pattern: "/docs/lab/:method",
      component: CountingMethodDoc,
      parse: ({ method }) => ({ method }),
      crumbs: countingMethodDocCrumbs,
    },

    // === 3. Grammar A: place-first cascade per ADR-0037, most-specific
    //        first. The 1-segment `/:state` catch-all MUST be last so
    //        every literal chrome route (above) wins on a name clash.
    //        Disjointness against chrome literals is guaranteed by
    //        `frontend/src/contracts/url-namespace-disjointness.test.ts`. ===
    // Canonical single-constituency drill-down (ADR-0052). Event lives
    // in PATH per ADR-0052; 5-segment pattern (state + literal
    // `elections` + event + literal `ac` + ac slug).
    {
      pattern: "/:state/elections/:event/ac/:ac",
      component: Constituency,
      parse: ({ state, event, ac }) => ({
        state,
        event,
        ac_slug: ac,
        eci_no: parseAcSlug(ac) ?? -1,
      }),
      crumbs: constituencyCanonicalCrumbs,
    },
    // Bare-AC convenience entry (ADR-0052). Not a canonical resource:
    // Constituency resolves the state's default event and
    // replaceState-redirects to the nested canonical form above.
    {
      pattern: "/:state/ac/:ac",
      component: Constituency,
      parse: ({ state, ac }) => ({
        state,
        ac_slug: ac,
        eci_no: parseAcSlug(ac) ?? -1,
      }),
      crumbs: constituencyBareCrumbs,
    },
    // Per-state per-district landing - the LIVE route is now the
    // 2-segment positional `/:state/:position2` dispatched by
    // `StateSubRouter` (registered below). Deferral 1 of
    // TODO/20260609-url-prefix-drop-phase0-plan.md dropped the
    // `/d/` literal marker per Jony's verdict ("citizen forwarding
    // yen-gov.in/tamil-nadu/d/chennai over WhatsApp is sharing a
    // system internal"). The `d` token stays in `RESERVED_PATH_TOKENS`
    // per Jony rule #3 as a future escape-hatch so a citizen who
    // types `/<state>/d` on the address bar lands on the 404 instead
    // of being poached by a hypothetical future district named "D".
    // Per-state topic page (IA-reset Step #2).
    { pattern: "/:state/t/:topic", component: StateTopic, crumbs: stateTopicCrumbs },
    // Per-state per-event election landing (ADR-0023, Q1 2026-05-24).
    // Distinct from /lab/ (analyst surface) and /compare/ (cross-state
    // results compare) — this is the neutral citizen permalink for a
    // specific cohort's results in a specific state.
    { pattern: "/:state/elections/:event", component: StateElection, crumbs: stateElectionCrumbs },
    // PR-W3b (election experience overhaul, 2026-06-10): bare-slug
    // constituency leaf at /<state>/elections/<event>/<constituency>.
    // Dispatches AC vs PC inside `Constituency.svelte` from the
    // event-slug body prefix (`general-` -> PC; `assembly-` -> AC).
    // The W3b-doctrinal shape; the legacy 5-segment
    // `/:state/elections/:event/ac/:ac` (ADR-0052) registered ABOVE
    // remains live for one release as the strangler-fig for legacy
    // bookmarks (segment count distinguishes; the more-specific
    // 5-segment wins on routes that carry the explicit `/ac/`
    // literal). Place after the 3-segment state event view so
    // most-specific-first ordering is preserved by segment count.
    {
      pattern: "/:state/elections/:event/:constituency",
      component: Constituency,
      parse: ({ state, event, constituency }) => ({
        state,
        event,
        constituency_slug: constituency,
      }),
      crumbs: constituencyLeafCrumbs,
    },
    // Per-state explorer.
    { pattern: "/:state/explore", component: Explore, crumbs: exploreCrumbs },
    // Depth-2 state-sub dispatcher (Deferral 1, 2026-06-10). Catches
    // `/<state>/<position2>` and routes via the pure
    // `state-sub-resolver` to District / Constituency / NotFound
    // based on which registry the slug lands in. MUST come AFTER
    // every literal-marker 2- or 3-segment Grammar A entry above
    // (`/:state/explore`, `/:state/t/:topic`, `/:state/elections/:event`,
    // `/:state/ac/:ac`) so the more-specific
    // routes win on a clash. MUST come BEFORE the 1-segment
    // `/:state` catch-all so the catch-all does not poach the
    // 2-segment path. Under Option A (2026-06-10) the dispatcher
    // resolves district-first per Jony rule #4; the shipped corpus
    // carries 401 (state, slug) pairs where a district name equals
    // an AC name in the same state by design and the colliding AC
    // stays reachable via the canonical event-nested URL
    // `/<state>/elections/<event>/ac/<ac>` (ADR-0052). The build-time
    // gate at `frontend/src/contracts/url-namespace-disjointness.test.ts`
    // asserts a positive presence-of-collisions baseline, not
    // strict disjointness. The crumb builder is intentionally
    // `notFoundCrumbs` here - StateSubRouter mutates `route.crumbs`
    // after dispatch so the mounted child's Breadcrumb sees the
    // right per-kind shape.
    {
      pattern: "/:state/:position2",
      component: StateSubRouter,
      crumbs: notFoundCrumbs,
    },
    // State hub (1-segment catch-all). MUST be the LAST 1-segment
    // pattern in the table - every chrome literal above this line will
    // win on a name clash, and the disjointness contract guarantees no
    // state slug equals a chrome literal.
    { pattern: "/:state", component: StateOverview, crumbs: stateOverviewCrumbs },
  ],
  notFound: { pattern: "*", component: NotFound, crumbs: notFoundCrumbs },
});
