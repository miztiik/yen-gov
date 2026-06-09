// Pure transform of a BASE-stripped legacy Grammar B pathname into its
// Grammar A equivalent. Used by RedirectLegacyUrl.svelte at runtime and
// by the unit test directly.
//
// Per TODO/20260609-url-prefix-drop-phase0-plan.md PR-P1 / ADR-0037
// Phase 2-4: the only structural change is dropping the leading `/s`
// segment. Everything after the state slug is preserved verbatim,
// including AC slugs (`167-mylapore` shape is NOT collapsed here -
// PR-P2 ships that as part of the caller-migration sweep).
//
//   `/s/tamil-nadu`                          -> `/tamil-nadu`
//   `/s/tamil-nadu/t/elections`              -> `/tamil-nadu/t/elections`
//   `/s/karnataka/elections/AcGenMay2023`    -> `/karnataka/elections/AcGenMay2023`
//   `/s/chhattisgarh/elections/x/ac/1-bastar` -> `/chhattisgarh/elections/x/ac/1-bastar`
//   `/s/`                                    -> `/`        (degenerate; lands on Home)
//   `/s`                                     -> `/`        (degenerate)
//
// Path that doesn't start with `/s/` is returned unchanged - defensive
// (the router only mounts the redirect on `/s/*` matches, but the
// pure-function contract makes it safe to call from anywhere).
export function rewriteLegacyPath(path: string): string {
  if (path === "/s" || path === "/s/") return "/";
  if (!path.startsWith("/s/")) return path;
  return path.slice(2); // drop the leading `/s`, keep the next `/`
}
