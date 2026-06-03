# ADR-0052: Election event is path identity, not a query parameter; constituency nests under the election

**Last Updated**: 2026-06-03
**Status**: Accepted
**Deciders**: User ("I dont see a reason for having two url patterns for the same data, it makes it harder to maintain two surfaces") + Jony (UI/UX, URL grammar per CLAUDE.md s0a) + Citizen.
**Supersedes**: the AC-leaf URL shape in [ADR-0048](0048-elections-drill-ia-and-tile-cartogram.md) section 1 (the bare `/s/:state/ac/:ac` leaf with `?event=` is retired as a canonical resource).

## Context

The constituency drill-down page was addressable two ways for the same resource:

- `/s/<state>/ac/<n-slug>?event=<event>` - event in the **query string**.
- `/s/<state>/elections/<event>` - the state election overview, with event in the **path**.

So the election event was sometimes a path segment (state overview) and sometimes a query parameter (constituency page). Two URL grammars for one logical thing (an election surface) is more to maintain and reason about, and it blurs the line between "which resource am I looking at" and "how am I looking at it".

## Decision

### 1. Path encodes resource identity; query encodes view-state only

Path segments encode resource identity (state, election event, constituency). The query string encodes view-state only - filters, colour mode, anything reversible that does not change *which* resource you are looking at. For elections the event **is** identity, never view-state, so it is always a path segment and never a query parameter.

### 2. URL grammar is hierarchical by zoom depth, not flat by surface

The election event is part of the resource identity, so it lives in the path on every election surface:

```
/s/<state>/elections/<event>             state election overview
/s/<state>/elections/<event>/ac/<n-slug> single-constituency drill-down, nested beneath
```

A constituency is **never addressable outside an election context**.

### 3. Bare `/s/<state>/ac/<n-slug>` is a convenience entry, not a canonical resource

It carries no election in its path, so it is not identity-complete. The constituency page resolves the state's default event and `replaceState`-redirects to the nested canonical form. It is a 302-equivalent (client-side, since the app is a static SPA on GitHub Pages with no server to issue a real 302).

### 4. Legacy `?event=` is honoured for one release

A pre-ADR-0052 bookmark of the form `/s/<state>/ac/<n-slug>?event=<event>` is read by the same redirect path: the query event is resolved and the visitor is `replaceState`-redirected to the nested path form. This keeps existing shared links working through one release; the query form is not emitted by any builder.

## Consequences

- `frontend/src/lib/url.ts`: `ac()` / `acByNo()` emit the nested path when an event is supplied, and the bare `/ac/` form (redirect target) when it is not. The event is never emitted as a query parameter.
- `frontend/src/main.ts`: canonical route `/s/:state/elections/:event/ac/:ac` -> `Constituency`; the bare `/s/:state/ac/:ac` route is retained only as the redirect entry.
- `frontend/src/routes/Constituency.svelte`: reads the event from `params.event` (path); falls back to a legacy `?event=` query, then the state default; redirects the bare form to the nested canonical URL.
- One URL grammar for elections: event in the path everywhere. No second surface to maintain.

## See also

- [ADR-0048](0048-elections-drill-ia-and-tile-cartogram.md) - elections drill IA (the AC-leaf URL shape here supersedes its section 1 leaf).
- [ADR-0023](0023-election-event-identity-per-place.md) - per-state default-event resolution (how the bare form picks the event to redirect to).
- [ADR-0050](0050-folder-naming-lgd-slug.md) / [ADR-0048](0048-elections-drill-ia-and-tile-cartogram.md) - LGD-slug state segment grammar.
