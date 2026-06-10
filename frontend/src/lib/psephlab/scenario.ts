// PR-W5a (2026-06-10): scenario URL-serialisation retired.
//
// The original module exported a base64url(JSON) round-trip
// (`encodeScenario` / `decodeScenario`) + a pair of URL bridge helpers
// (`readScenarioFromHash` / `writeScenarioToHash`) that hydrated
// Psephlab + Compare scenarios from the legacy `s` query parameter
// (and a matching pair on the Compare surface). Per the
// election-experience-overhaul plan binding constraint #8 ("Ephemeral
// scenarios. No URL-encoded scenario blob. No localStorage. Refresh
// = fresh start."), the entire URL coupling retired in this PR
// alongside the Compare route deletion. The encode / decode pair had
// no remaining live consumers and was deleted too.
//
// `EMPTY_SCENARIO` survives because Psephlab.svelte uses it as the
// initial value of its component-local scenario state.

import type { Scenario } from "./types";

export const EMPTY_SCENARIO: Scenario = {
  v: 1,
  rule: "fptp",
  mutations: [],
};

