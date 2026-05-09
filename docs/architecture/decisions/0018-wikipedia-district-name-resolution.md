# ADR-0018: Wikipedia AC-table district name resolution

**Last Updated**: 2026-05-09
**Status**: accepted

## Context

ADR-0015 added `district_id` as an optional field on `ConstituencyEntry`, populated when an authoritative source maps an AC to its parent district. The Wikipedia "List of constituencies of the X Legislative Assembly" tables already carry a District column, but the strings in that column do not match the names emitted by `parse_districts` 1:1. Real cases observed in the TN + KL pages we've onboarded:

| AC table writes  | Districts page writes      |
| ---------------- | -------------------------- |
| `Thiruvallur`    | `Tiruvallur`               |
| `Tiruvarur`      | wait, also `Thiruvarur` on AC side |
| `Tirupattur`     | `Tirupathur`               |
| `Kanniyakumari`  | `Kanyakumari`              |
| `Chennai`        | `Chennai (formerly Madras)`|
| `Kasargod`       | `Kasaragod`                |

These are not data errors — Indian district names have multiple defensible romanisations; different Wikipedia editors picked different ones. A naive casefolded equality check resolved 192 of 234 TN ACs and 135 of 140 KL ACs, leaving 47 unresolved across two states.

## Decision

A two-pass resolver in `sources.wikipedia.constituencies`:

1. **Exact key**: `_strip_parens(name).casefold().strip()` — handles the parenthesised-suffix case (`Chennai (formerly Madras)` → `chennai`).
2. **Skeleton key**: a deterministic `_norm()` that lowercases, drops non-alpha, removes every `h`, removes vowels after the first character, and collapses repeated letters. Designed to make `Thiruvallur` / `Tiruvallur` / `Tirupathur` / `Tirupattur` / `Kanniyakumari` / `Kanyakumari` / `Kasargod` / `Kasaragod` all collide with their counterpart on the districts side.

`build_district_lookup()` indexes each district under **both** keys so callers see a single dict-of-strings interface.

If both passes miss, `district_id` is left absent — the entry stays valid under the provisional schema, and the unresolved cell is silently tolerated. We do not promote `status` to `complete` on Wikipedia data alone (that requires `pc_id` too, which Wikipedia AC tables don't carry).

## Consequences

**Good**

- 100% resolution on TN (234/234) and KL (140/140) without per-state alias tables.
- The rules are general (not state-specific) so new states should mostly work without adjustment.
- Status stays `provisional` until an authoritative ECI cross-check fills `pc_id` — keeps the lifecycle honest.

**Bad**

- The skeleton can in principle collide between two genuinely different districts that share a consonant skeleton. Mitigation: `build_district_lookup()` uses `setdefault`, so the first-registered district wins, and the lookup is built per-state (collision risk is bounded by the ~38 districts in the largest state we'll see).
- The rules are heuristic and will need tuning for north-eastern states (Khasi/Garo/Mizo names) where vowel-collapse may collide. We accept that and will revisit when those states are onboarded.

## Alternatives considered

- **Hand-rolled per-state alias tables** (`{"Thiruvallur": "TAL", ...}`). Rejected: hardcoding (Holy Law #6) and unbounded maintenance — every new state needs a fresh alias table built by hand.
- **Levenshtein/Damerau-Levenshtein fuzzy match with a distance threshold**. Rejected: introduces a dependency for a problem that's already solvable with deterministic string ops; thresholds are inherently fiddly and would need a bypass when a real district name is one edit away from another in the same state.
- **Extract LGD codes from gov.in Local Government Directory and match those instead**. The right long-term answer (see CLAUDE.md §13) — when LGD codes land we'll use those for both districts.json and the AC↔district join, and this resolver becomes the fallback for states the LGD scrape doesn't cover.
