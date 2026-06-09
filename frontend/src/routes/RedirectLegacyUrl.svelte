<!--
  RedirectLegacyUrl - strangler-fig redirect for the Grammar B legacy
  prefix `/s/<state>/...` to the Grammar A bare `/<state>/...` shape
  per ADR-0037 Phase 2-4 (TODO/20260609-url-prefix-drop-phase0-plan.md
  PR-P1).

  Mounted by main.ts as the catch-all for `/s/*`. On mount it:
    1. Reads `window.location.pathname` (and any `?search` + `#hash`).
    2. Strips the deploy BASE.
    3. Rewrites the leading `/s/<state>` to `/<state>` via the pure
       helper in `lib/redirect-legacy-url.ts` (the only structural
       change - everything after the state segment is preserved
       verbatim, including AC slugs, party slugs, etc.).
    4. Calls `history.replaceState` so the citizen's URL bar flips
       AND the back button doesn't bounce them back to /s/.
    5. Dispatches `popstate` to re-render the router against the new
       Grammar A path (which lands on the same component the legacy
       route used to render).

  Path-only transform: query string + fragment are preserved verbatim
  via reassembly. We do NOT touch them.

  AC slug shape: the numeric-prefix drop (`167-mylapore` -> `mylapore`)
  is OUT of PR-P1 scope. PR-P2 ships that as part of the caller-migration
  sweep. Until then, `/s/<state>/ac/167-mylapore` redirects byte-for-byte
  to `/<state>/ac/167-mylapore` (the AC route still understands the
  prefixed slug per `parseAcSlug`).

  Removal: PR-P4 (deferred indefinitely) deletes this file + the route
  entry + the pure helper once telemetry shows zero `/s/*` traffic.
-->
<script lang="ts">
  import { onMount } from "svelte";
  import { stripBase, withBase } from "../lib/url";
  import { rewriteLegacyPath } from "../lib/redirect-legacy-url";

  // Params are supplied by the router compile() wildcard; not used here
  // (we read directly from window.location to preserve query + hash).
  interface Props { params: { rest?: string } }
  // The router always supplies a `rest` key for `/s/*` matches but the
  // value is unused - we re-read window.location to get the full URL
  // including query + hash, which the params object doesn't carry.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  let { params: _params }: Props = $props();

  onMount(() => {
    // Read the live URL (not the routed path) so we preserve query +
    // fragment. stripBase only consumes the deploy-base prefix.
    const rawPath = stripBase(window.location.pathname);
    const newPath = rewriteLegacyPath(rawPath);
    const search = window.location.search;
    const hash = window.location.hash;
    const target = withBase(newPath) + search + hash;
    // Replace (not push) so the legacy URL doesn't sit in history.
    history.replaceState(null, "", target);
    // Trigger the router to re-render against the new path.
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
</script>

<!--
  Brief blank-screen during redirect; the popstate dispatch is synchronous
  so this is rarely seen, but keeps citizens from staring at a blank page
  if anything stalls.
-->
<main class="max-w-md mx-auto p-12 text-center text-slate-500">
  <p>Redirecting&hellip;</p>
</main>
