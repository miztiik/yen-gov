// Local OSS-style A/B experiment bucket helper.
//
// Per TODO/20260518-frontend-charting-modernisation-plan.md Phase 3.6
// (c) + resolution R-16 ("ships behind a GrowthBook OSS A/B
// experiment, URL stays canonical, sticky cookie bucket"). The repo
// does NOT depend on the @growthbook/growthbook NPM package; this
// module reproduces the minimum surface (sticky-cookie visitor_id +
// deterministic hash bucket + targeting-rule evaluation) needed for
// the experiments shipping under
// `frontend/src/lib/charts/composition-bar/experiment-definition.json`.
//
// Doctrine ties:
//
//   - R-08 Branch by Abstraction: the helper is structural; callers
//     opt-in by calling `bucketFor(experiment, { state_code })` and
//     branching on the returned variation id.
//
//   - R-16 three-PR split: this helper ships in the (c) mount PR
//     alongside the per-route mount; renderer (a) and adapter (b)
//     already shipped.
//
//   - R-24 zero fetch telemetry: the cookie is first-party (set on
//     the same origin as the site); the visitor_id is a random UUID
//     with no identifying content; no analytics, no third-party
//     transmission.

export interface ExperimentVariation {
  readonly id: string;
  readonly key: string;
  readonly name: string;
  readonly weight: number;
  readonly description?: string;
}

export interface ExperimentTargetingRule {
  readonly id: string;
  readonly description: string;
  readonly condition: Record<string, unknown>;
  readonly enabled: boolean;
}

export interface ExperimentTargeting {
  readonly namespace: string | null;
  readonly rules: readonly ExperimentTargetingRule[];
}

export interface ExperimentDefinition {
  readonly experiment_id: string;
  readonly feature_key: string;
  readonly hash_attribute: string;
  readonly stickiness: string;
  readonly variations: readonly ExperimentVariation[];
  readonly targeting: ExperimentTargeting;
  readonly status: string;
}

export type BucketAttributes = Readonly<Record<string, unknown>>;

/**
 * The cookie key under which the sticky visitor_id is persisted.
 * First-party; no third-party transmission. Prefix `yg_` so curators
 * inspecting the document.cookie can identify yen-gov-owned cookies
 * at a glance.
 */
export const VISITOR_ID_COOKIE = "yg_visitor_id";

/**
 * Cookie lifetime — 365 days. Long enough that returning citizens
 * stay in the same variation across visits (sticky bucket invariant);
 * short enough that the cookie eventually expires without manual
 * cleanup.
 */
export const VISITOR_ID_TTL_DAYS = 365;

/**
 * Cheap, deterministic, non-cryptographic 32-bit hash. Pure; identical
 * output across browser / node so vitest can pin the bucket choice
 * without booting a DOM. djb2-style; mirrors `stringHash` in
 * `frontend/src/lib/colors/oklch.ts` (the existing in-repo hash used
 * for party-colour de-duplication).
 */
export function deterministicHash(input: string): number {
  let h = 5381;
  for (let i = 0; i < input.length; i++) {
    h = (h * 33) ^ input.charCodeAt(i);
  }
  // Force unsigned 32-bit so modulus is stable across JS engines.
  return h >>> 0;
}

/**
 * Pure bucket choice — given a visitor_id and an experiment
 * definition, return the variation. Uses weight-cumulative selection
 * so 0.0..0.5 → control, 0.5..1.0 → treatment for a 50/50 split.
 *
 * Falls back to the first variation on degenerate input (no
 * variations, all-zero weights) so the caller never has to nil-check.
 */
export function pickVariation(
  visitor_id: string,
  experiment: Pick<ExperimentDefinition, "experiment_id" | "variations">,
): ExperimentVariation {
  if (experiment.variations.length === 0) {
    throw new Error(
      `pickVariation: experiment ${experiment.experiment_id} has zero variations`,
    );
  }
  const weights = experiment.variations.map(v => v.weight);
  const total = weights.reduce((a, b) => a + b, 0);
  if (total <= 0) return experiment.variations[0];

  const hash = deterministicHash(`${visitor_id}|${experiment.experiment_id}`);
  // Convert hash to a 0..1 ratio. 2 ** 32 is the modulus that the
  // unsigned 32-bit hash can produce.
  const ratio = hash / 2 ** 32;
  let cursor = 0;
  for (const v of experiment.variations) {
    cursor += v.weight / total;
    if (ratio < cursor) return v;
  }
  return experiment.variations[experiment.variations.length - 1];
}

/**
 * Evaluate a single targeting rule against caller-supplied attributes.
 * Supports the minimum operator vocabulary used by the
 * composition-bar experiment: `$in` (membership in a list of literals).
 * Returns `true` if the rule matches AND is enabled.
 *
 * Extending: add `$eq`, `$ne`, `$gt`, etc. only when a new experiment
 * needs them — YAGNI keeps the surface minimal.
 */
export function evaluateRule(
  rule: ExperimentTargetingRule,
  attributes: BucketAttributes,
): boolean {
  if (!rule.enabled) return false;
  for (const [key, predicate] of Object.entries(rule.condition)) {
    const value = attributes[key];
    if (predicate && typeof predicate === "object" && "$in" in predicate) {
      const allowed = (predicate as { $in: unknown[] }).$in;
      if (!Array.isArray(allowed)) return false;
      if (!allowed.includes(value)) return false;
    } else {
      if (value !== predicate) return false;
    }
  }
  return true;
}

/**
 * True iff at least one enabled targeting rule matches. An experiment
 * with `targeting.rules: []` is considered always-on (returns `true`)
 * so a curator can drop the rule list when graduating an experiment.
 */
export function isInTargeting(
  experiment: Pick<ExperimentDefinition, "targeting">,
  attributes: BucketAttributes,
): boolean {
  if (experiment.targeting.rules.length === 0) return true;
  return experiment.targeting.rules.some(r => evaluateRule(r, attributes));
}

/**
 * Top-level bucket helper. Returns `null` when the visitor is NOT in
 * targeting (caller falls back to control by default); otherwise
 * returns the variation id (e.g. `"control"` / `"treatment"`).
 *
 * Pure with respect to inputs — no cookie/DOM access. Callers should
 * resolve `visitor_id` via `ensureVisitorId()` (DOM-aware) before
 * calling this function.
 */
export function bucketFor(
  experiment: ExperimentDefinition,
  attributes: BucketAttributes,
  visitor_id: string,
): string | null {
  if (experiment.status !== "running") return null;
  if (!isInTargeting(experiment, attributes)) return null;
  const variation = pickVariation(visitor_id, experiment);
  return variation.id;
}

/**
 * DOM-aware bucket helper. Reads the URL query string for a deterministic
 * override (`?yg_variant=<variation_id>`) which is intended for two
 * call sites only:
 *
 *   1. Manual QA — a curator wants to see one variant without clearing
 *      cookies.
 *   2. Playwright — pinning a variant for deterministic e2e assertions
 *      (see `frontend/e2e/composition-bar-mount.spec.ts`).
 *
 * The override is scoped per-experiment via the
 * `yg_variant_<experiment_id>` cookie set by the same query string on
 * first read, so subsequent navigations within the same session stay on
 * the pinned variant without keeping the query string in the URL bar.
 *
 * IMPORTANT: the override does NOT bypass targeting. If the visitor
 * is OUTSIDE the rollout list (e.g. TN per plan R-02), pinning
 * `?yg_variant=treatment` still returns `null` — citizen-visible
 * targeting is enforced. Curators wanting to inspect the chart on
 * an out-of-targeting state must edit the experiment definition.
 *
 * Falls back to `bucketFor` when no override is set. Treats unknown
 * variation ids as "no override" so a typo never silently mutes the
 * experiment.
 */
export function bucketForWithOverride(
  experiment: ExperimentDefinition,
  attributes: BucketAttributes,
  visitor_id: string,
): string | null {
  if (experiment.status !== "running") return null;
  if (!isInTargeting(experiment, attributes)) return null;
  const override = readOverride(experiment);
  if (override) return override;
  const variation = pickVariation(visitor_id, experiment);
  return variation.id;
}

function overrideCookieName(experiment_id: string): string {
  return `yg_variant_${experiment_id}`;
}

function readOverride(experiment: ExperimentDefinition): string | null {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return null;
  }
  const known = new Set(experiment.variations.map(v => v.id));
  // 1. Query string takes precedence — pinning a fresh variant.
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("yg_variant");
  if (fromUrl && known.has(fromUrl)) {
    writeCookie(overrideCookieName(experiment.experiment_id), fromUrl, 30);
    return fromUrl;
  }
  // 2. Sticky override cookie carries the pin forward.
  const fromCookie = readCookie(overrideCookieName(experiment.experiment_id));
  if (fromCookie && known.has(fromCookie)) return fromCookie;
  return null;
}

/**
 * Read the sticky visitor_id from document.cookie. Creates and
 * persists a new UUID if none exists. Safe to call repeatedly —
 * idempotent on first read for a given browser profile.
 *
 * SSR / non-DOM environments (vitest node-env): returns a stable
 * test-only id so the helper is invocable in vitest without a window
 * stub. The caller MUST treat this id as non-persistent.
 */
export function ensureVisitorId(): string {
  if (typeof document === "undefined") return "ssr-non-persistent";
  const existing = readCookie(VISITOR_ID_COOKIE);
  if (existing) return existing;
  const fresh = newVisitorId();
  writeCookie(VISITOR_ID_COOKIE, fresh, VISITOR_ID_TTL_DAYS);
  return fresh;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

function writeCookie(name: string, value: string, ttl_days: number): void {
  if (typeof document === "undefined") return;
  const expires = new Date(Date.now() + ttl_days * 86400_000).toUTCString();
  document.cookie =
    `${name}=${encodeURIComponent(value)}` +
    `; expires=${expires}` +
    `; path=/` +
    `; SameSite=Lax`;
}

function newVisitorId(): string {
  // Prefer crypto.randomUUID where present; fall back to a hex string
  // so vitest / older browsers without that surface still get a
  // workable id. The fallback is not cryptographically secure — but
  // we don't need it to be (visitor_id is opaque, non-identifying).
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  const rand = () => Math.random().toString(16).slice(2, 10);
  return `${rand()}-${rand()}-${rand()}-${rand()}`;
}
