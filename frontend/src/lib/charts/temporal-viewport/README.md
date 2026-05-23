# Temporal viewport primitive

Pure helper module for the temporal viewport (brush + presets) that
lands across the chart family in Phase 1.5 of
[`TODO/20260518-frontend-charting-modernisation-plan.md`](../../../../TODO/20260518-frontend-charting-modernisation-plan.md).

## Contract

A **temporal domain** is the full extent of period_ids the chart knows
about. A **temporal window** is a contiguous sub-range
(`{from_period_id, to_period_id}`, inclusive both ends) that the
brush UI selects. Both are typed in [`types.ts`](./types.ts).

## Public surface (via `./index.ts`)

| Symbol | Purpose |
|---|---|
| `TemporalDomain` / `TemporalWindow` / `TemporalPreset` / `TemporalDomainKind` | Closed-enum types. |
| `KNOWN_PRESETS` / `KNOWN_DOMAIN_KINDS` | Frozen canonical arrays. |
| `buildDomain(period_ids, kind)` | Construct a frozen `TemporalDomain` from an adapter-supplied ordered id sequence. Parses `min_year`/`max_year` for year-derivable kinds. |
| `parseLeadingYear(period_id)` | Extract a 4-digit year prefix from `"2024"` / `"FY2021"` / `"2024-05"` shapes. Returns `null` for election-cycle / custom ids. |
| `fullWindow(domain)` | `{first..last}` window. |
| `isFullWindow(window, domain)` | Detect the default state. |
| `windowIndices(window, domain)` | Resolve to `{from_idx, to_idx}`; returns `{-1, -1}` for stale ids. |
| `clampWindow(window, domain)` | Snap to bounds + normalise reversed pairs. Stale ids fall back to `fullWindow`. |
| `presetWindow(preset, domain, opts?)` | `all` / `recent` / `5y` / `10y` / `25y` → window or `null` when not applicable. |
| `filterItemsToWindow(items, getPeriodId, window, domain)` | Generic filter used by every renderer to apply the brush selection to bars/points/gantt rows. |

## Design rules

1. **Index-first, date-on-top.** The brush operates on indices into
   `ordered_period_ids`; year arithmetic is applied only for
   `presetWindow` of the year-derivable presets. This means the
   primitive works for non-uniform sequences (election cycles, fiscal
   years, custom dimensions) without coupling to date math.

2. **Stale ids degrade to full window.** A `period_id` that doesn't
   appear in the domain never throws; helpers return `fullWindow`. A
   serialised URL hash can outlive a data revision (e.g. a bar is
   dropped because the source removed it) and the brush must not
   panic.

3. **Reversed windows normalise.** The brush UI naturally produces
   `from > to` while the user drags one handle past the other;
   `clampWindow` swaps silently.

4. **Single-period windows valid.** The brush UI can collapse to a
   single bar selection; helpers preserve it.

5. **Pure functions.** No DOM, no Svelte, no Blob, no clipboard.
   Component-level integration lands in a follow-up PR with the brush
   primitive.

## Doctrine ties

- **Phase 1.5 task list** — pure-helper foundation precedes the brush
  primitive precedes per-renderer adoption.
- **R-07 (URL grammar)** — temporal window is local component state
  by default; if shareable, rides ADR-0028 place-first cascade as a
  path segment (`/elections/lok-sabha/since-1977`), NEVER query
  strings or matrix URIs. This module is URL-agnostic.
- **CLAUDE.md §10 (closed enums)** — `TemporalDomainKind` and
  `TemporalPreset` are closed string unions; adding a value requires
  editing 3 places in lockstep (the union, the `KNOWN_*` array, the
  plan task list).

## Out of scope for this PR

- The brush Svelte component itself.
- Per-renderer adoption (StackedTrendV2, ministerial Gantt, fiscal
  lines).
- URL serialisation helpers (will live alongside the brush primitive).
