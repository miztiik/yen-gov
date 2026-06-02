# ADR-0048: Elections drill IA, generic TileCartogram, AC/PC grain split, and filter URL grammar

**Last Updated**: 2026-06-02
**Status**: Accepted
**Deciders**: User (autonomous mandate 2026-05-31 - "Build a UK-elections-style experience; elections may break the 'one topic on the generic state page' constraint for this work.") + Gregor (contract / URL grammar, per CLAUDE.md s0a) + Jony + Citizen (UX) + Hans + Max (data shape, cartogram-on-welfare veto).
**Plan reference**: [TODO/20260531-uk-style-elections-experience-plan.md](../../../TODO/20260531-uk-style-elections-experience-plan.md).

## Context

yen-gov ships AC (assembly-constituency) election results today but has no national Lok Sabha (PC / parliamentary-constituency) experience, no equal-seats cartogram, no cross-year change visualisation, and no faceted constituency filtering. The user approved a UK-elections-style experience (reference: the UK `data-analytics` geographic-vs-hex toggle; `indian_mlas` faceted filters) and explicitly authorised breaking the "elections is just one topic on the generic state page" constraint for this work only.

Indian election results have a **constituency grain** - AC for state assembly, PC for Lok Sabha. Constituencies do NOT nest into villages or sub-districts; the honest drill stops at the constituency leaf. This ADR locks the contracts the three execution lanes (docs, backend PC ingest, frontend machinery) build against.

## Decision

### 1. Drill IA

```
/t/elections/:event   (NEW national PC atlas)
   -> /s/:state/elections/:event   (existing state surface; canonical shared URL. `/lab/:state/:event` is a dev-only alias, never the shared link)
       -> ?d=<district>     (a FILTER on the state surface, NOT a route)
           -> /s/:state/ac/:ac   (existing constituency leaf)
```

The place page `/s/:state` remains the spine. There is **NO village/sub-district level for election results** - the drill terminates at the constituency leaf.

### 2. Grain split

National = PC grain; state = AC grain. UI components are **grain-agnostic**: a "unit" is a constituency of either kind. The same `TileCartogram` / choropleth / loader code serves both; the grain is dispatched from the observation row's `entity_kind` (`ac` | `pc`), never from a hardcoded constant. This follows [ADR-0044](0044-grain-over-entity.md) (grain rides on the row).

### 3. Generic TileCartogram, election-mount-only in v1

One reusable SVG primitive (`frontend/src/lib/charts/TileCartogram.svelte`) fed by a layout dataset. It is **NOT** wired to welfare / denominator indicators in v1 - equal-sizing welfare data (where population, area, or budget differ wildly per entity) is misleading (Hans + Max veto). Tile layouts are **frontend-owned render data** under `datasets/grapher/` per [ADR-0045](0045-grapher-catalogue-split.md), NOT canonical election data, and carry their own schema + `source_id` + `derivation_method`.

### 4. Toggle

A segmented control labelled **`Map`** / **`Equal seats`** (never the jargon "choropleth" / "cartogram"). Default is geographic (`Map`) at all levels. The mode persists to the URL as `?view=geo|hex`. The `Equal seats` arm carries the legend line **"Each tile = one seat."**

### 5. Cross-year ship order

1. Seat-composition bars + per-party swing arrows (default-on; cheapest signal).
2. Snapping time-slider on the map/cartogram - snaps to election years only, **no interpolation, no autoplay**.
3. Opt-in 2-election capped sankey (top-6 parties + merged "Others"), labelled "Flow (beta)", collapsed by default. Honesty banner: seat deltas, not voter-panel tracking.

### 6. Filter URL grammar (the contract PR-B8 / PR-B9 implement)

| Param | Values | Default | Scope | Meaning |
| --- | --- | --- | --- | --- |
| `party` | csv of party short codes, lower-case (e.g. `bjp,inc`), from the party taxonomy short-code vocabulary (`datasets/taxonomy/parties.json`) | absent = all parties shown, none dimmed | national + state | highlight winners of these parties; dim the rest |
| `margin` | `all` \| `lt2` \| `gt20` | `all` | national + state | single highlight band on margin = winner_share - runner_up_share (pp); `all` = no band. Non-partition: the 2-20 pp middle has no v1 value |
| `mode` | `winner` \| `margin` \| `turnout` \| `age` | `winner` | national + state | colour-by dimension. `mode=age` colours by winner-candidate age and depends on a candidate-age measure that may not exist at PC grain in v1; if absent it falls back to `winner` rather than rendering empty |
| `view` | `geo` \| `hex` | `geo` | national + state | geographic vs equal-seats |
| `d` | `<district lgd key>` | absent = all districts | state only (ignored on `/t/elections/:event`) | district filter on the state surface (not a route) |

Filters are **modifiers on a fully-populated default view, never preconditions**. A bare `/t/elections/2024-ls` renders the complete national map at every param's default (`mode=winner`, `margin=all`, `view=geo`, no `party`, no `d`); params only narrow / recolour it.

**Composition:** params combine with **AND** across params and **OR** within a csv (e.g. `party=bjp,inc&margin=lt2` = units won by BJP *or* INC, *and* in a close band). `party` and `d` narrow the highlighted *set*; `mode` and `view` only change *rendering* and never remove units.

**Fail-soft / versioning:** an unknown param key, or an unknown value for a known param (a value from a newer bundle, or a typo), is **ignored and falls back to that param's default** - never an error, never a blank screen. Adding a new `mode`/`margin`/`view` value is additive (minor); removing or renaming one is breaking. If applied filters narrow to zero units, the map still renders all units at base styling with an inline "no constituencies match these filters" note - filters never blank the canvas. Full example:

```
/t/elections/2024-ls?party=bjp&margin=lt2&mode=margin&view=hex
```

### 7. Do-not-build list (v1)

- Village / sub-district levels for results.
- Full (>2-election) sankey.
- A second `/t/elections/country/state/...` URL spine (the place spine `/s/:state` is reused).
- Per-state hand-placed bespoke hex layouts (layouts are generated from centroids + persisted; manual cleanup only where Jony flags overlaps).
- Autoplay / interpolated transitions.
- Demographic cross-tabs beyond "colour by".

## Addendum (2026-06-02): topic doors mount the experience (supersedes s1 topic-as-card)

**Status of this addendum**: Accepted. **Deciders**: User (autonomous mandate 2026-06-02 - "promote the experience onto the topic doors; no redirect; top-level `/t/elections` must work as the experience too") + Gregor (IA contract) + Jony + Citizen (UX). **Plan reference**: [TODO/20260602-elections-experience-gap-closure-plan.md](../../../TODO/20260602-elections-experience-gap-closure-plan.md) rows EGC-A1..A4.

**What s1 originally said.** The drill-IA section above drew the experience (`ElectionMap` + time-slider + filter rail) onto the **event** routes only - `/s/:state/elections/:event` (state) and `/t/elections/:event` (national) - while the **topic doors** citizens actually click from a place/topic hub (`/s/:state/t/elections` and the bare national `/t/elections`) rendered a summary **card that linked out**. That was a deliberate "topic = card, event = experience" choice.

**Why it was wrong for the user.** A citizen who clicks "Elections" on a state hub (or the national Elections topic) expects the results map - not a card asking them to click again. The card-and-link landed them one click short of the thing they came for, and the national `/t/elections` door rendered the empty indicator grid because elections carries no Seventh-Schedule indicator family. This was a wrong-for-user **contract**, not a bug.

**Decision (supersedes s1's topic-as-card for elections).** The topic door **mounts the experience**, no redirect:

- `/s/:state/t/elections` mounts the shared Assembly experience at the state's **default assembly event** (resolved read-time via `defaultEventForState`); lok_sabha / by-election slices keep a card-and-link (they drill into the national atlas, not the AC map). A collapsed "Other elections on file" `<details>` preserves the rest of the catalogue.
- The bare national `/t/elections` mounts the **national PC atlas** at the **default Lok Sabha event** (resolved read-time via `defaultNationalLokSabhaEvent`), with a collapsed "Other Lok Sabha elections on file" list below. No redirect; `/t/elections/:event` remains the per-cohort permalink.
- The experience is a **single shared component** (`frontend/src/lib/elections/StateElectionExperience.svelte` for AC; `NationalElectionsAtlas.svelte` for PC) mounted by both the event route and the topic door, so the two surfaces can never drift into showing different results for one place. Event-selection **policy** stays with the parent (the permalink navigates the `:event` path; the topic door updates local state via an `onSelectEvent` callback) - neither surface forks the experience logic.

**Options rejected.**

- **Redirect the topic door to the default event route.** Rejected: a redirect throws away the topic door's URL identity and its ability to render **mixed artifacts** (a topic door can carry both the experience and an "other elections" inventory; an event permalink is single-cohort). It also makes the back button land on a surface the citizen never chose.
- **Merge topic and event into one route.** Rejected for the same mixed-artifact + canonical-identity reasons; the place spine `/s/:state` and the per-cohort permalink are distinct, durable URLs (s7 do-not-build: no second URL spine).

**Default-event resolution is read-time, not a schema bump.** Both doors resolve "which event leads" from the catalogue at read time (`defaultEventForState` / `defaultNationalLokSabhaEvent`); no new catalogue field, no event-identity change. The shared resolver is the single source of truth for the default, so the topic door and the event route agree by construction.

## Load-bearing contracts from Lane A (PC ingest)

Two backend decisions ride alongside this ADR and are recorded here because the frontend depends on them:

- **PC shares the `elections` family + `state=` partition.** PC `ObservationRow`s write into the existing `datasets/elections/state=<key>/election_results.parquet`, discriminated by `entity_id` prefix (`IN-PC-...` vs `IN-<state>-AC-...`) + `indicator_id` (`pc-*` vs `ac-*`). No sibling family, no `grain=` partition dimension (Gregor). The `<state_code>` segment in both PC (`IN-PC-<delim_year>-<state_code>-...`) and AC (`IN-<state_code>-AC-<delim_year>-...`) `entity_id`s MUST draw from the same vocabulary as the `state=<key>` partition key, so PC and AC rows for one state co-locate in the same `datasets/elections/state=<key>/` partition. Segment order differs between the two forms (PC carries `state_code` in position 3, AC in position 1); readers MUST recover state/grain from the `entity_kind` and dedicated state columns, never by positional `entity_id` parsing. `<delim_year>` is the 4-digit delimitation year (e.g. `2008`), never a 2-digit form. The national PC query selects by measure + grain column: `WHERE indicator_id='pc-winner-party-id' AND entity_kind='pc'`. Grain is dispatched from the `entity_kind` column (per ADR-0044), never by parsing `entity_id`; the `IN-PC-%` prefix is an identity convenience, not the dispatch key, so the two cannot drift. PC `entity_id` is `IN-PC-<delim_year>-<state_code>-<pc_no>` (globally unique; ECI `pc_no` is per-state).
- **`pc-*` indicators are sanctioned (Model C - per-grain PC sibling concepts).** The grain-prefix gate (`GRAIN_PREFIX_RE = ^(state|district|national)-` in `backend/yen_gov/preflight/predicates.py` + Tier-B `tier_b_indicator_id_no_grain_prefix`) never matches `ac-`/`pc-` - [ADR-0044](0044-grain-over-entity.md) preserves those as fact-grain prefixes. **Model C (Gregor, 2026-06-01; supersedes the earlier "Option B with concept-binding"):** each `pc-*` indicator FKs to its OWN pc-grain sibling concept in `datasets/taxonomy/concepts.json` with `entity_kinds: ["pc"]` and a grain-suffixed noun, mirroring the `winning-party-ac` / `winning-party-state` precedent. MP/PC is a genuinely different office on a different boundary than MLA/AC, so each grain owns a distinct concept - NOT a shared concept whose `entity_kinds` spans both grains. The 13 minted concept_ids: `electors-pc`, `votes-polled-pc`, `turnout-pc`, `nota-votes-pc`, `nota-share-pc`, `winner-pc`, `winning-party-pc`, `margin-absolute-pc`, `margin-pc`, `others-votes-pc`, `others-share-pc`, `candidates-total-pc`, `effective-candidates-pc`. **Option B is rejected** (every `pc-*` sharing ONE `concept_id` with its `ac-*` sibling, extending that concept's `entity_kinds` to `[ac, pc]`): it would break the cluster-8 Tier-A guardrail pins (`backend/tests/test_concept_resolve_c8_winning_party_grain.py` hard-asserts disjoint per-grain `entity_kinds`), re-merge the deliberate cluster-8 grain split, and is partially impossible - 4 of the 13 PC measures (`pc-nota-pct`, `pc-others-pct`, `pc-candidates-total`, `pc-effective-candidates-laakso`) have NO `ac-*` concept to share. The `entity_kinds` enum gained `pc` in a MINOR additive bump (PR-A2 of the completed UK-style plan).

## Consequences

- The drill IA and URL grammar are versionable contracts; PR-B8 / PR-B9 serialize filter state to URL exactly per section 6, so a shared URL reproduces the screen.
- `TileCartogram` is reusable but deliberately fenced to election mounts in v1; a future welfare-cartogram decision would need its own ADR + a Hans/Max sign-off on the equal-sizing distortion.
- Reusing the place spine (`/s/:state`) instead of a second election URL tree keeps one canonical place identity.

## See also

- [TODO/20260602-elections-experience-gap-closure-plan.md](../../../TODO/20260602-elections-experience-gap-closure-plan.md) the gap-closure plan whose EGC-A1..A4 rows ship the topic-door mount in the addendum above.
- [ADR-0044](0044-grain-over-entity.md) grain over entity.
- [ADR-0045](0045-grapher-catalogue-split.md) grapher catalogue split (render data is frontend-owned).
- [ADR-0023](0023-election-event-identity-per-place.md) election event identity per place.
- [docs/concepts/schema-is-the-design-system.md](../../concepts/schema-is-the-design-system.md) renderer doctrine.
- [docs/architecture/frontend/map.md](../frontend/map.md) Map / Equal seats mode contract.
- [docs/architecture/data/elections-indicators.md](../data/elections-indicators.md) AC + PC indicator catalogue.
