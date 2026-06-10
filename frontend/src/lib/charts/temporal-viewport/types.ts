// Temporal viewport — typed contract for the temporal viewport
// primitive that lands across the chart family in Phase 1.5 of
// `docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md`.
//
// This file is the **contract** — types only, no runtime, no Svelte,
// no DOM. The pure helpers in `./helpers.ts` operate on these types;
// the brush component (later PR) and the temporal-aware renderers
// (StackedTrendV2, ministerial Gantt, fiscal lines) consume them.
//
// Doctrine ties:
//
//   - Phase 1.5 task list: "Full domain remains known to the chart …
//     visible domain is a window … presets `All` / `Recent` / `10y` /
//     `25y`". This module gives those concepts a single source of
//     truth so every renderer talks the same language.
//
//   - R-07 (URL grammar): the temporal window is local component
//     state by default. Where shareable state is genuinely needed it
//     rides ADR-0028 place-first cascade as a path segment (e.g.
//     `/elections/parliament/since-1977`); query strings and matrix
//     URIs are explicitly REJECTED. This contract is URL-agnostic so
//     callers can serialise / not as the route demands.
//
//   - CLAUDE.md §10 (closed enums): `TemporalDomainKind` and
//     `TemporalPreset` are CLOSED string unions, never `string`.
//     Adding a kind / preset is a deliberate 3-place edit:
//       1. The union in this file.
//       2. The `KNOWN_PRESETS` / `KNOWN_DOMAIN_KINDS` arrays in
//          `./helpers.ts`.
//       3. The Phase 1.5 plan task list.

/**
 * The closed enum of temporal-domain kinds the viewport understands.
 *
 *   - `year`           — period_id is a 4-digit calendar year string
 *                        ("1977", "2024"). Date arithmetic-aware
 *                        presets (`10y`, `25y`) apply.
 *
 *   - `election_cycle` — period_id is a stable election-event id
 *                        ("AcGenMay2023", "GeJun2024"). Index-based
 *                        presets (`recent`) apply; date-arithmetic
 *                        presets fall back to `presetByCount`.
 *
 *   - `month`          — period_id is `YYYY-MM` ("2024-05"). Year-
 *                        bucketed presets convert window into
 *                        N×12 months (10y → 120 months).
 *
 *   - `fiscal_year`    — period_id is `FYNNNN` ("FY2023") covering
 *                        the financial year. Treat year-equivalent
 *                        for preset arithmetic; the renderer prints
 *                        the FY prefix on the axis.
 *
 *   - `custom`         — any other ordered sequence. The viewport
 *                        operates index-only; date presets are
 *                        unsupported and `presetWindow` returns null.
 */
export type TemporalDomainKind =
  | "year"
  | "election_cycle"
  | "month"
  | "fiscal_year"
  | "custom";

/**
 * The closed enum of preset window-shapes the viewport supports.
 * Presets are SUGGESTIONS; the caller decides which to surface in
 * the brush toolbar.
 *
 *   - `all`     — full domain. The chart's default.
 *   - `recent`  — last N periods where N is domain-kind-specific
 *                 (default 5; configurable via `presetWindow`'s
 *                 `recent_count` opt).
 *   - `10y`     — last 10 years on `year` / `fiscal_year` / `month`
 *                 domains. Null on `election_cycle` / `custom`.
 *   - `25y`     — last 25 years (same caveats as `10y`).
 *   - `5y`      — last 5 years (added at Hans review 2026-05-22 for
 *                 economic-class indicators that turn over fast).
 *
 * Note: presets that fall outside the full domain (e.g. `25y` on a
 * 12-year history) are CLAMPED to the full domain — the renderer
 * MUST NOT silently show an empty chart.
 */
export type TemporalPreset = "all" | "recent" | "5y" | "10y" | "25y";

/**
 * The full temporal extent the chart knows about. Constructed by the
 * adapter from the bar list; the renderer never recomputes it.
 *
 *   - `domain_kind`          — see `TemporalDomainKind`.
 *
 *   - `ordered_period_ids`   — the canonical ordered sequence of bar
 *                              period_ids, oldest first. The brush
 *                              indexes into this array; the renderer
 *                              filters its bar list against this
 *                              array's prefix/suffix.
 *
 *   - `min_year` / `max_year` — convenience numerics filled IFF
 *                              `domain_kind` is year-derivable
 *                              (`year`, `fiscal_year`, `month`).
 *                              Helpers return null for `custom` /
 *                              `election_cycle`; callers can fall
 *                              back to index arithmetic.
 */
export interface TemporalDomain {
  readonly domain_kind: TemporalDomainKind;
  readonly ordered_period_ids: readonly string[];
  readonly min_year: number | null;
  readonly max_year: number | null;
}

/**
 * The visible window inside a `TemporalDomain`. Inclusive on both
 * ends. The two period_ids must both appear in the parent domain's
 * `ordered_period_ids`; `clampWindow` enforces this invariant.
 *
 * Reversed inputs (`from` later than `to`) are normalised by
 * `clampWindow` rather than rejected — the brush UI can produce
 * either order while the user drags.
 */
export interface TemporalWindow {
  readonly from_period_id: string;
  readonly to_period_id: string;
}

/**
 * Index pair returned by `windowIndices`. Both -1 when either end
 * cannot be located in the parent domain (treat as "use full
 * domain" — never throw, the brush's interaction handlers must not
 * panic if the URL serialiser hands them a stale id).
 */
export interface TemporalWindowIndices {
  readonly from_idx: number;
  readonly to_idx: number;
}
