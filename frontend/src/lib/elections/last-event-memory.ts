/**
 * Per-state "last viewed election event" memory backed by localStorage.
 *
 * Used by `StateElectionsLanding.svelte` to render a "Last viewed" badge
 * next to the matching year-link (J-elevated-15 of the state-event-page
 * redesign plan). On-write from `StateElection.svelte` on every per-event
 * page mount. Per-state, 30-day expiry so a stale memory does not dominate
 * forever.
 *
 * Holy Law #1-compliant: no server roundtrip, no telemetry, no PII. The
 * localStorage key is per state slug; values carry only catalogue-public
 * fields (`event_id`, `viewed_at_iso`, `body`).
 */

export type LastEventBody =
  | "assembly"
  | "parliament"
  | "general_bye"
  | "assembly_bye"
  | "by_election";

export interface LastEventMemory {
  event_id: string;
  viewed_at_iso: string;
  body: LastEventBody;
}

const MEMORY_KEY_PREFIX = "yen-gov:last-event:";
const EXPIRY_DAYS = 30;
const EXPIRY_MS = EXPIRY_DAYS * 86_400_000;

function keyFor(state_slug: string): string {
  return MEMORY_KEY_PREFIX + state_slug;
}

/**
 * Read the persisted last-viewed event for `state_slug`. Returns `null`
 * if absent, malformed, or older than the 30-day window. Silent on
 * any I/O fault (SSR, disabled storage, quota errors) per Holy Law #5
 * (do not fail the page render because of a memo-store hiccup).
 */
export function readLastEvent(state_slug: string): LastEventMemory | null {
  if (typeof localStorage === "undefined") return null;
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(keyFor(state_slug));
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as LastEventMemory;
    if (
      typeof parsed?.event_id === "string"
      && typeof parsed?.viewed_at_iso === "string"
      && typeof parsed?.body === "string"
      && isLastEventFresh(parsed.viewed_at_iso)
    ) {
      return parsed;
    }
  } catch {
    // Malformed JSON; treat as missing.
  }
  return null;
}

/**
 * Persist the last-viewed event for `state_slug`. No-op when localStorage
 * is unavailable. Overwrites any prior memory for the same state.
 */
export function writeLastEvent(
  state_slug: string,
  event_id: string,
  body: LastEventBody,
): void {
  if (typeof localStorage === "undefined") return;
  const memory: LastEventMemory = {
    event_id,
    viewed_at_iso: new Date().toISOString(),
    body,
  };
  try {
    localStorage.setItem(keyFor(state_slug), JSON.stringify(memory));
  } catch {
    // Quota / disabled storage — silent.
  }
}

/**
 * True iff `viewed_at_iso` is within the 30-day freshness window.
 * Exported so tests can pin the boundary.
 */
export function isLastEventFresh(viewed_at_iso: string): boolean {
  const viewed_at_ms = new Date(viewed_at_iso).getTime();
  if (!Number.isFinite(viewed_at_ms)) return false;
  return Date.now() - viewed_at_ms < EXPIRY_MS;
}
