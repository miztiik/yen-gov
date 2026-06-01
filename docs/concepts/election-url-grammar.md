# Election filter URL grammar

The election maps (`/s/:state/elections/:event` today; `/t/elections/:event`
once PR-B9 lands) carry their filter state entirely in the URL query string.
On a static bundle the URL is the only state-sharing channel
(CLAUDE.md Holy Law #1), so the query string **is** the contract: a shared
link must reproduce the screen, must survive a citizen hand-editing it, and
must be reused verbatim across the state and national routes.

A single typed translator owns the grammar:
[`frontend/src/lib/election-filters.ts`](../../frontend/src/lib/election-filters.ts)
(`parseElectionFilters` / `serializeElectionFilters`). Neither the state
component nor the national component re-implements `URLSearchParams` parsing —
they both go through this Message Translator boundary.

## The four rules

1. **Multi-value via comma-delimited CSV.** `?party=BJP,INC` keeps two parties
   highlighted. This mirrors the existing `url.ts` `states.join(",")`
   precedent. `URLSearchParams.toString()` percent-encodes the whole value, so
   the list round-trips through `.get()`. Party codes are comma-free
   alphanumeric ECI tokens, so a comma is unambiguously the separator.

2. **Defaults are omitted.** A key appears in the URL **iff** it differs from
   its default. The clean default view `/s/maharashtra/elections/AcGenOct2019`
   carries no query string at all. Defaults: `party` empty, `margin=all`,
   `mode=winner` (and `view=geo`).

3. **Enum values clamp; data values pass through.** An unknown **enum** token
   (`?mode=swing`, `?margin=xyz`) degrades silently to the default, so an older
   bundle that doesn't know a future mode still renders a coherent screen. An
   unknown-but-well-formed **party code** is kept verbatim — a code this event
   doesn't contain simply highlights nothing; dropping it would corrupt a link
   shared across events or grains.

4. **One typed translator, shared across routes.** The same
   `election-filters.ts` is used by the state route (PR-B8) and the national PC
   route (PR-B9). The serializer takes an optional `base: URLSearchParams` so
   it owns exactly the three filter keys (`party`, `margin`, `mode`) while
   preserving params it does not own (e.g. `view=hex`).

## Vocabulary

| Key      | Values                              | Default  |
| -------- | ----------------------------------- | -------- |
| `party`  | CSV of ECI party short codes        | (empty)  |
| `margin` | `all` \| `lt2` \| `gt20`            | `all`    |
| `mode`   | `winner` \| `margin` \| `turnout` \| `age` | `winner` |
| `view`   | `geo` \| `hex`                      | `geo`    |

`margin` bands read off the constituency margin of victory: `lt2` = decided by
under 2 points (knife-edge), `gt20` = won by more than 20 points (landslide).

`mode=turnout` and `mode=age` are **coverage-gated**: the option is only offered
when enough winners in the loaded `(state, event)` carry the field
(`hasModeCoverage`, 80% threshold). Turnout is conditionally emitted per event;
winner age is affidavit-sourced (dense for recent events, null for older ones).

## Example

```
/t/elections/LsGenJun2024?party=BJP,INC&margin=lt2&mode=margin&view=hex
```

Filters are **modifiers on a fully-populated default view**, never
preconditions: removing every query param always yields a complete, coherent
map.
