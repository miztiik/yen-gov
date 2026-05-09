# Compare

**Last Updated**: 2026-05-09

Compare is the Phase 3 split-screen surface for asking "what changes if…?" by putting two outputs of the same engine side by side.

Route: `#/compare/:state/:event?mode=scn|elec&a=<scenario>&b=<scenario>&eventb=<event>` ([Compare.svelte](../../../frontend/src/routes/Compare.svelte)).

## Two modes

| Mode | What is fixed | What varies | Status |
| --- | --- | --- | --- |
| `scn` (default) | state + event (actuals) | two independent scenarios, each a Psephlab `Scenario` decoded from `?a=` / `?b=` | ✅ shipped |
| `elec` | state | two events (`params.event` vs `eventb`) | empty-state until additional event datasets land under `datasets/elections/` |

Both modes render three columns: column A → delta strip → column B. The delta strip is a per-party `seats_won` table with `Δ = B − A`, sorted by max(left, right). Coloured swatches use the same overrides store as the rest of the app.

## Why "paste a Psephlab URL" instead of an embedded editor

Compare is intentionally **a viewer of two scenarios, not a builder of two scenarios**. The mutation editor is large (sticky panel with multiple control types — see [psephlab.md](psephlab.md)); duplicating it in a split-screen layout would either bury the parliament arcs or force two cramped editors. Composition rules:

- The user builds a scenario in [Psephlab](psephlab.md), copies its share URL.
- Pastes that URL (or just the `?s=…` token) into the column-A or column-B input on Compare. The `applyPasted()` helper accepts: a full URL, a hash fragment, a `?s=…` substring, or a bare base64url token.
- Decoded with the same `decodeScenario()` used by Psephlab (no separate codec).

This keeps Compare a thin route — no mutation logic, no engine alternative, no second source of truth for scenario shape. If a strategist wants to tweak scenario A they go back to Psephlab in another tab; share URLs round-trip.

## URL persistence

Compare mirrors Psephlab's pattern: every field that differs from default is encoded into the fragment query string on every state change (single `$effect` writing via `history.replaceState`). The route component re-mounts on `:state` or `:event` change, so initial state reads from the hash once at mount via `untrack()` (avoids the Svelte `state_referenced_locally` warning).

`mode=scn` is the default and is omitted from the URL when active (shorter URLs for the common case).

## Election-vs-Election: why the empty state ships now

Only `AcGenMay2026` exists under `datasets/elections/` today. We could have hidden the mode tab until a second event lands, but exposing it now:

- documents the planned shape for the maintainer (URL parameter `eventb`),
- exercises the same `loadActuals(event, state)` boundary that the pipeline must satisfy when a prior election lands,
- gives a real failure surface (the amber empty-state banner) instead of a 404.

When a second event's datasets ship, the mode just starts working — no Compare-side change required.

## What is *not* in Compare v1

- **Per-AC delta map.** A scenario-aware choropleth diff is a natural next step; it lives under [map.md](map.md) when it ships. Today, drilling into per-AC differences means opening each scenario's Psephlab view in adjacent tabs.
- **Embedded editor.** See above — composition wins over duplication.
- **More than two columns.** A three-way compare (e.g. actuals vs scenario A vs scenario B) is degenerate: actuals = empty scenario, just paste an empty `?s=` into one column. Hard-coding three columns would only force a wider layout.
- **A `lib/diff.ts` helper.** The phasing table mentioned this; it was unnecessary — the per-party seat union is computed inline since it has no other consumer. Extract only when a second view needs the same shape.

## See also

- [Psephlab](psephlab.md) — scenario builder, share-URL format, mutation catalog.
- [Frontend overview](overview.md) — phasing, route table.
