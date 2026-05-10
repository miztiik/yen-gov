import "./app.css";
import { mount } from "svelte";
import { startRouter } from "./lib/router.svelte";
import LeftRail from "./lib/LeftRail.svelte";
import Home from "./routes/Home.svelte";
import StateOverview from "./routes/StateOverview.svelte";
import Constituency from "./routes/Constituency.svelte";
import Party from "./routes/Party.svelte";
import Explore from "./routes/Explore.svelte";
import Settings from "./routes/Settings.svelte";
import Psephlab from "./routes/Psephlab.svelte";
import Compare from "./routes/Compare.svelte";
import About from "./routes/About.svelte";
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

startRouter({
  target: document.getElementById("route")!,
  routes: [
    { pattern: "/", component: Home },
    { pattern: "/s/:state", component: StateOverview },
    {
      pattern: "/s/:state/ac/:eci_no",
      component: Constituency,
      parse: ({ state, eci_no }) => ({ state, eci_no: parseInt(eci_no, 10) }),
    },
    { pattern: "/s/:state/party/:party_eci_code", component: Party },
    { pattern: "/s/:state/explore", component: Explore },
    { pattern: "/lab/:state/:event", component: Psephlab },
    { pattern: "/compare/:state/:event", component: Compare },
    { pattern: "/settings", component: Settings },
    { pattern: "/about", component: About },
  ],
  notFound: { pattern: "*", component: NotFound },
});
