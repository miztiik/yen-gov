# ChartShell — shared chart shell and action footer

Phase 1.4 task 1 of
[`docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md`](../../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md).

## What this is

A renderer-agnostic Svelte 5 component plus its typed contract. Every
yen-gov chart that ships citizen-facing chrome eventually mounts inside
`<ChartShell>` so the title row, honesty banners, source disclosure, and
action footer follow the same rules and look the same.

This PR ships the **shell structure and the action vocabulary** only.
Zero existing renderers are migrated in this PR (R-08 Branch by
Abstraction).

## Surfaces

| Path | Role |
|---|---|
| [`types.ts`](./types.ts) | `ChartShellAction` closed enum, `ChartShellActionSpec`, `ChartShellHonestyBanner`, re-export of `PublisherPill`. |
| [`actions.ts`](./actions.ts) | Pure helpers: `ALLOWED_ACTIONS`, `filterAllowedActions`, `sortActionsForFooter`. |
| [`actions.test.ts`](./actions.test.ts) | Vitest contract pinning the 6-action vocabulary and the sort/filter behaviour. |
| [`index.ts`](./index.ts) | Barrel — re-exports the contract. |
| [`../ChartShell.svelte`](../ChartShell.svelte) | The Svelte 5 component (lives one level up next to `StackedTrendV2.svelte` to match existing renderer placement). |

## Action vocabulary (closed enum)

Per Phase 1.4 plan task 4. Adding a new action requires editing
`types.ts` + `actions.ts` + the plan in lockstep. The Phase 1.4 contract
test "action footer does not render unapproved controls" is enforced
two ways:

1. `filterAllowedActions` drops any unknown id at the helper boundary
   (`actions.test.ts`).
2. The renderer in `ChartShell.svelte` calls `filterAllowedActions(...)`
   on its `actions` prop and then `sortActionsForFooter(...)` on the
   result before iterating — so the DOM cannot contain a button whose
   id is not in `ALLOWED_ACTIONS`.

| id | When to surface |
|---|---|
| `view_data` | When a tabular view of the currently-visible rows exists. Per plan: "show currently visible window first, not the whole indicator corpus". |
| `download` | When the renderer can serialise itself to SVG/PNG/CSV. |
| `copy_link` | When the route has a stable URL contract for the current view-state. |
| `share` | When `navigator.share` is available; falls back to `copy_link`. |
| `reset_view` | When the renderer holds non-temporal interaction state (pin, hidden parties, etc). |
| `full_range` | When the renderer has a temporal viewport (Phase 1.5 brush). |

## What the renderer guarantees

- **R-24** — no fetch-telemetry. The shell hosts the new `<SourceList>` from `\/sources` which
  refuses `url`, `fetched_at`, `content_hash`.
- **R-28** — sources arrive as a typed array, resolved upstream from
  `taxonomy.sources` via the manifest-registered `table_id`. The shell
  never sees a parquet path literal.
- **R-08** — v1 chart headers/footers continue to ship. Per-renderer
  migration onto ChartShell happens one PR at a time.

## What is intentionally NOT in this PR

| Out of scope | Where it lands |
|---|---|
| Mounting on any existing renderer. | Per-renderer migration PRs after this lands. |
| `view_data` payload formatting. | Phase 1.4 task 5 (depends on URL contract). |
| `share` Web Share API integration. | Phase 1.4 task 5 (depends on URL contract). |
| Temporal viewport brush. | Phase 1.5. |
| Sorting / grouping helpers. | Phase 1.6. |
| GrowthBook A/B bucket wiring. | Phase 3.6 (c). |

## Test gates

- `actions.test.ts` — 13 cases covering the closed enum, filter
  behaviour, stable sort, defence-in-depth on unknown ids, and the
  filter+sort composition.
- No vitest component test — the project's vitest is node-env without
  jsdom (see [`frontend/src/lib/boundaries.integration.test.ts`](../../boundaries.integration.test.ts)
  comment line 4). Component-level assertions land in Playwright after
  the first renderer adopts the shell.
- No Playwright — the shell has zero callers in this PR (R-08).
