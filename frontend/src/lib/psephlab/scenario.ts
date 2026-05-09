// Scenario URL serialisation.
//
// Scenarios round-trip as `?s=<base64url(JSON)>`. Base64url avoids `=` and
// the URL-unsafe `+/` that plain base64 emits. JSON keeps the format
// human-readable when decoded — debugging is easier when you can paste
// `atob(...)` and read what's there.
//
// Format version is `Scenario.v` (currently `1`). Loaders refuse
// unknown versions rather than guessing — psephlab.md > "URL".

import type { Scenario } from "./types";

const CURRENT_VERSION = 1 as const;

export const EMPTY_SCENARIO: Scenario = {
  v: CURRENT_VERSION,
  rule: "fptp",
  mutations: [],
};

function b64url_encode(s: string): string {
  // Use TextEncoder so non-ASCII (party names with diacritics, bag labels)
  // round-trips correctly. btoa() alone breaks on >U+00FF.
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64url_decode(s: string): string {
  const padded = s.replace(/-/g, "+").replace(/_/g, "/") +
    "==".slice(0, (4 - (s.length % 4)) % 4);
  const bin = atob(padded);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

/** Serialise scenario to the value of the `s` query parameter. */
export function encodeScenario(scenario: Scenario): string {
  // Drop empty fields to keep URLs short. JSON.stringify with a replacer
  // that omits empty arrays/objects reduces the common "no overrides" case.
  const compact: Record<string, unknown> = {
    v: scenario.v,
    rule: scenario.rule,
  };
  if (scenario.mutations.length) compact.mutations = scenario.mutations;
  if (scenario.colors && Object.keys(scenario.colors).length) compact.colors = scenario.colors;
  return b64url_encode(JSON.stringify(compact));
}

/**
 * Parse the `s=` value back into a Scenario. Returns `EMPTY_SCENARIO` and
 * logs a warning when the input is malformed or carries a future version
 * we don't know how to read — the alternative (throwing) would brick the
 * page on a typo'd URL.
 */
export function decodeScenario(raw: string | null | undefined): Scenario {
  if (!raw) return EMPTY_SCENARIO;
  let parsed: unknown;
  try {
    parsed = JSON.parse(b64url_decode(raw));
  } catch (e) {
    console.warn("[psephlab] scenario decode failed:", e);
    return EMPTY_SCENARIO;
  }
  if (!parsed || typeof parsed !== "object") return EMPTY_SCENARIO;
  const obj = parsed as Record<string, unknown>;
  if (obj.v !== CURRENT_VERSION) {
    console.warn(`[psephlab] scenario version ${String(obj.v)} not supported (current: ${CURRENT_VERSION})`);
    return EMPTY_SCENARIO;
  }
  return {
    v: CURRENT_VERSION,
    rule: typeof obj.rule === "string" ? obj.rule : "fptp",
    mutations: Array.isArray(obj.mutations) ? (obj.mutations as Scenario["mutations"]) : [],
    colors:
      obj.colors && typeof obj.colors === "object"
        ? (obj.colors as Record<string, string>)
        : undefined,
  };
}

/** Pull the scenario from `window.location.hash` (`#/lab/...?s=<...>`). */
export function readScenarioFromHash(): Scenario {
  const h = window.location.hash;
  const i = h.indexOf("?");
  if (i < 0) return EMPTY_SCENARIO;
  const params = new URLSearchParams(h.slice(i + 1));
  return decodeScenario(params.get("s"));
}

/** Replace the scenario portion of the URL without triggering the router. */
export function writeScenarioToHash(path_prefix: string, scenario: Scenario): void {
  const encoded = encodeScenario(scenario);
  // history.replaceState avoids piling up entries on every slider tick.
  const next = `#${path_prefix}?s=${encoded}`;
  if (window.location.hash === next) return;
  history.replaceState(null, "", next);
}
