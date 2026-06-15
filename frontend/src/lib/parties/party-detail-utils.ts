// Pure helpers shared by the Party.svelte stronghold list. Lives in
// the parties/ lib folder alongside the other party-page primitives.
//
// `stateNameFromEntityId` parses a constituency entity_id and returns
// the state ECI code + the citizen-readable state name resolved via
// the supplied `stateName` accessor. The accessor is injected (rather
// than imported) so the helper stays pure / synchronously-testable;
// production callers pass `states.name` from `lib/states.svelte.ts`
// and the live runtime resolves codes from the canonical entities
// catalogue.
//
// Two entity_id grammars are recognised:
//   - Parliament: `IN-PC-YYYY-Sxx-N`  (state code at parts[3])
//   - Assembly:   `IN-Sxx-AC-YYYY-N`  (state code at parts[1])
//
// Both produce a 5-segment dash-split. Anything else (wrong prefix,
// fewer segments, state segment that does not match `[SU]\d{2}`)
// returns the malformed-fallback `{ state_code: null, state_name: "" }`
// - the row's text-prefix is then suppressed rather than throwing.
// This matches the broader "graceful degradation, no blank UI" pattern
// used by other party-page primitives.

/** Result of parsing + resolving a constituency entity_id. */
export interface ParsedEntityState {
  /** ECI state code (e.g. `S22`) when the entity_id matches one of
   *  the expected shapes; null when the id is malformed. */
  state_code: string | null;
  /** Citizen-readable state name resolved via `stateName(code)`.
   *  Falls back to the raw code when the resolver returns null
   *  (state catalogue not yet loaded, or unknown code). Empty
   *  string when the entity_id is malformed. */
  state_name: string;
}

const STATE_CODE_RE = /^[SU]\d{2}$/;

/** Extract `state_code` from a PC/AC `entity_id` and resolve its
 *  citizen-readable state name via the supplied resolver. */
export function stateNameFromEntityId(
  entity_id: string,
  stateName: (code: string) => string | null,
): ParsedEntityState {
  if (!entity_id || typeof entity_id !== "string") {
    return { state_code: null, state_name: "" };
  }
  const parts = entity_id.split("-");
  if (parts.length < 5 || parts[0] !== "IN") {
    return { state_code: null, state_name: "" };
  }
  let code: string | null = null;
  if (parts[1] === "PC" && STATE_CODE_RE.test(parts[3])) {
    // Parliament: IN-PC-YYYY-Sxx-N
    code = parts[3];
  } else if (parts[2] === "AC" && STATE_CODE_RE.test(parts[1])) {
    // Assembly: IN-Sxx-AC-YYYY-N
    code = parts[1];
  }
  if (!code) {
    return { state_code: null, state_name: "" };
  }
  const resolved = stateName(code);
  return { state_code: code, state_name: resolved || code };
}
