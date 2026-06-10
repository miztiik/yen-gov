// Token layer first (CLAUDE.md doctrine + plan section 21.7) so app.css
// and any later component CSS may reference --ink / --accent / --r-md
// etc. Mirrored ADDITIVELY into tailwind.config.js theme.extend per
// plan section 23.5; drift locked by frontend/src/contracts/app-tokens.test.ts.
import "./app-tokens.css";
import "./app.css";
import { mount } from "svelte";
import { startRouter } from "./lib/router.svelte";
import { parseAcSlug } from "./lib/slug";
import LeftRail from "./lib/LeftRail.svelte";
import Home from "./routes/Home.svelte";
import StateOverview from "./routes/StateOverview.svelte";
import Constituency from "./routes/Constituency.svelte";
import Party from "./routes/Party.svelte";
import Explore from "./routes/Explore.svelte";
import Settings from "./routes/Settings.svelte";
import Psephlab from "./routes/Psephlab.svelte";
import Compare from "./routes/Compare.svelte";
import CompareIndicator from "./routes/CompareIndicator.svelte";
import About from "./routes/About.svelte";
import Disclaimer from "./routes/Disclaimer.svelte";
import TopicIndex from "./routes/TopicIndex.svelte";
import TopicLanding from "./routes/TopicLanding.svelte";
import StateTopic from "./routes/StateTopic.svelte";
import StateElection from "./routes/StateElection.svelte";
import District from "./routes/District.svelte";
import NationalElectionsAtlas from "./routes/NationalElectionsAtlas.svelte";
import DataCompleteness from "./routes/DataCompleteness.svelte";
import DevChartsSandbox from "./routes/DevChartsSandbox.svelte";
import Yenask from "./routes/Yenask.svelte";
import IndicatorDoc from "./routes/IndicatorDoc.svelte";
import CountingMethodDoc from "./routes/CountingMethodDoc.svelte";
import NotFound from "./routes/NotFound.svelte";

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

// Route params are slugs (e.g. `tamil-nadu`, `167-mylapore`). Each page
// resolves the slug to its underlying ECI id via the lib/states.svelte
// resolver (state) or by parsing the numeric prefix (AC). Party slugs are
// `{short}-{eci_code_lower}`; the page derives the ECI code from the
// trailing token to avoid needing a parties index at routing time.
//
// Route ordering (load-bearing per the first-match-wins resolver):
//   1. Chrome literals (`/`, `/about`, `/settings`, etc.) come FIRST so
//      they always win over the Grammar A `/:state` catch-all.
//   2. Multi-segment literal-rooted routes (`/lab/...`, `/compare/...`,
//      `/docs/...`, `/t/...`) come next; they're segment-count + literal
//      distinguished from Grammar A.
//   3. Grammar A routes follow, most-specific first; the 1-segment
//      `/:state` catch-all is LAST so it never poaches a literal route.
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
    { pattern: "/", component: Home },
    { pattern: "/settings", component: Settings },
    { pattern: "/about", component: About },
    { pattern: "/disclaimer", component: Disclaimer },
    // Topic Front Door (P3.3, ADR-0022).
    { pattern: "/t", component: TopicIndex },
    // Generic indicator Compare (P4) — sits alongside the more-specific
    // election Compare below; the two patterns don't overlap.
    { pattern: "/compare", component: CompareIndicator },
    // Citizen transparency surface (folded-indicator PR commit 10).
    { pattern: "/data-completeness", component: DataCompleteness },

    // === 2. Multi-segment literal-rooted routes. ===
    // Phase 6 (charting modernisation plan) — dev sandbox that mounts
    // every Phase 1.6 / 3.5 generic renderer against synthetic fixture
    // data. Not citizen-discoverable; not linked from the left rail.
    { pattern: "/dev/charts-sandbox", component: DevChartsSandbox },
    // YENASK (display name Yen-Ask) — browser governance insight
    // assistant. Mounted under /lab/ alongside the analyst lab routes
    // (/lab/:state/:event). Dev-only — not citizen-discoverable, not
    // linked from the left rail. See ADR-0040 (brand + lab-route
    // placement) and ADR-0039 (Slice E LLM-OS architecture).
    // Pattern-distinct from /lab/:state/:event (2 vs 3 segments) so
    // route order is not load-bearing. Removal = git rm of
    // routes/Yenask.svelte + lib/yenask/ + this entry.
    { pattern: "/lab/yenask", component: Yenask },
    // National Parliament PC results atlas (UK-style elections plan, PR-B4).
    // 3-segment pattern, distinct from /t/:topic (2 segments); placed first
    // so the more-specific route wins regardless of matcher order.
    { pattern: "/t/elections/:event", component: NationalElectionsAtlas },
    { pattern: "/t/:topic", component: TopicLanding },
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
    },
    { pattern: "/lab/:state/:event", component: Psephlab },
    // Method-aware Compare (2026-06-09 redesign). Same 4-segment shape
    // as labMethod above; both sides share the active method per Fowler
    // verdict (per-side method override deferred).
    {
      pattern: "/compare/:state/:event/m/:method",
      component: Compare,
      parse: ({ state, event, method }) => ({ state, event, method }),
    },
    { pattern: "/compare/:state/:event", component: Compare },
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
      parse: ({ topic, id }) => ({ indicator_id: `${topic}/${id}` }),
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
    },
    {
      pattern: "/:state/party/:party",
      component: Party,
      parse: ({ state, party }) => ({ state, party_slug: party }),
    },
    // Per-state per-district landing (U2 sub-plan U2a). Place-first geo
    // axis lives in the PATH never the querystring (parent plan section
    // 23.5 + 20.8). 3-segment pattern with literal `d`, distinct from
    // every other 3-segment pattern by its literal. The `district` slug
    // is opaque to the router and resolved at render time inside
    // District.svelte against the LGD district `display_name` via slugify().
    //
    // Reserved (NOT registered): positional `/<state>/<district>` (no
    // `/d/` marker) per ADR-0037 routing.md - requires a runtime
    // depth-2 dispatcher with a district + indicator + AC registry,
    // deferred to a follow-up.
    {
      pattern: "/:state/d/:district",
      component: District,
      parse: ({ state, district }) => ({ state, district_slug: district }),
    },
    // Per-state topic page (IA-reset Step #2).
    { pattern: "/:state/t/:topic", component: StateTopic },
    // Per-state per-event election landing (ADR-0023, Q1 2026-05-24).
    // Distinct from /lab/ (analyst surface) and /compare/ (cross-state
    // results compare) — this is the neutral citizen permalink for a
    // specific cohort's results in a specific state.
    { pattern: "/:state/elections/:event", component: StateElection },
    // Per-state explorer.
    { pattern: "/:state/explore", component: Explore },
    // State hub (1-segment catch-all). MUST be the LAST 1-segment
    // pattern in the table - every chrome literal above this line will
    // win on a name clash, and the disjointness contract guarantees no
    // state slug equals a chrome literal.
    { pattern: "/:state", component: StateOverview },
  ],
  notFound: { pattern: "*", component: NotFound },
});
