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
import TopicIndex from "./routes/TopicIndex.svelte";
import TopicLanding from "./routes/TopicLanding.svelte";
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
startRouter({
  target: document.getElementById("route")!,
  routes: [
    { pattern: "/", component: Home },
    { pattern: "/s/:state", component: StateOverview },
    {
      pattern: "/s/:state/ac/:ac",
      component: Constituency,
      parse: ({ state, ac }) => ({
        state,
        ac_slug: ac,
        eci_no: parseAcSlug(ac) ?? -1,
      }),
    },
    {
      pattern: "/s/:state/party/:party",
      component: Party,
      parse: ({ state, party }) => ({ state, party_slug: party }),
    },
    { pattern: "/s/:state/explore", component: Explore },
    { pattern: "/lab/:state/:event", component: Psephlab },
    { pattern: "/compare/:state/:event", component: Compare },
    // Generic indicator Compare (P4) — sits alongside the more-specific
    // election Compare above; the two patterns don't overlap.
    { pattern: "/compare", component: CompareIndicator },
    { pattern: "/settings", component: Settings },
    { pattern: "/about", component: About },
    // Topic Front Door (P3.3, ADR-0022).
    { pattern: "/t", component: TopicIndex },
    { pattern: "/t/:topic", component: TopicLanding },
  ],
  notFound: { pattern: "*", component: NotFound },
});
