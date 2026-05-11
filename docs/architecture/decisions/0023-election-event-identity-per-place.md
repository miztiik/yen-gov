# ADR-0023: Election event identity is per-place, government-timeline is the citizen unit

**Last Updated**: 2026-05-11
**Status**: accepted
**Sequel to**: [ADR-0022 — Place-first IA with a topic-catalogue contract](0022-place-first-ia-with-topic-catalogue.md)

## Context

ADR-0022 mandated a place-first spine and demoted elections from "the spine" to "one indicator family among many". The first concrete consequence — visible on `/s/:state` for every state but the five May-2026 cohort — was a 404. A citizen typing `/s/andhra-pradesh` saw no AP page at all because seven separate route components, written when AcGenMay2026 was the only event in the system, had hardcoded `const event = "AcGenMay2026"` and asked for `/data/elections/AcGenMay2026/S01/result.summary.json`. AP has never had a May-2026 election.

The shallow fix — read the event from a global "Election" dropdown that the user picks — is the same architectural mistake at a different layer:

1. **It denies federal reality.** There is no single Indian "current election" (or "current cycle") that all states share. AP was last elected in 2024 (concurrent with Lok Sabha 2024); Bihar in 2025; Tamil Nadu and Kerala in 2026; Delhi in 2025; Jammu & Kashmir in 2024 (after six years of President's Rule). A control that asks the citizen to pick *one* election before they see *any* state encodes the falsehood that elections are nationally synchronous.
2. **It makes the wrong thing primary.** A citizen on `/s/odisha` wants to know about Odisha — the State Government, the BJD-to-BJP transition, the floods response, the 2027 budget. Whether the dropdown above the page says "May 2026" or "June 2024" is irrelevant noise; if anything the chrome encourages reading state quality through a partisan election-leader lens (the exact anti-doctrine ADR-0022 §Doctrine forbids).
3. **It bakes a temporary scaffold.** The dropdown was added when AcGenMay2026 was the only ingested event because `<select>` made the only-option case "look right". As soon as a second event landed, the dropdown became a misleading pseudo-control: it said "1 of N" but the N was global, not per-state.

A two-subagent consultation (Architect Gregor + Governance Strategist, 2026-05-11) converged independently on the same diagnosis: **election event identity is intrinsically per-place** (no two states necessarily share an event), and **government-term is the citizen unit of state politics**, with elections as the *cause* of government changes rather than the unit itself.

## Decision

Adopt a four-part structural change. None of these is optional; together they delete the global-election concept from the IA.

### 1. Per-state election inventory replaces the global dropdown

A new typed contract — `datasets/schemas/election-events.schema.json` v1.0 + `datasets/reference/in/election-events.json` — declares, for each state, the chronological list of election events for which we have data on disk. Each entry carries:

- `event_id` — the on-disk grouping name (e.g. `AcGenJun2024`), matching `events.py event_id_for(state, year)`.
- `kind` — `assembly | lok_sabha | by_election`. Assembly and Lok Sabha results are kept separate; never co-mingled (they elect different bodies).
- `display` — the citizen-facing label. Cohort codes never leak into this string.
- `polled_on` — the polling date for this state (multi-state cohorts polling on different days carry per-state dates).
- `default: true` — at most one per state. Defines what `/s/<state>/elections` resolves to.
- `data_status: complete | partial | pending_upstream` — tells the UI what to expect on disk. `pending_upstream` (e.g. Bihar 2025, where ECI has not yet published Section 10) surfaces as an honest "awaiting publication" message rather than a 404.
- `term_end_estimated` — typically `polled_on + 5 years`, used to surface "next election due" chrome in the final year.

The frontend reads this once via `frontend/src/lib/election-events.ts` and exposes:

```ts
defaultEventForState(state: string): EventRow | null
listEventsForState(state: string): EventRow[]
findEvent(state: string, eventId: string): EventRow | null
```

Every site that previously had `const event = "AcGenMay2026"` now resolves the event by state. Routes that target a *specific* historical event take an `event_id` URL segment (`/s/<state>/elections/<event_id>`) or query param — the user's choice is in the URL, not in a global picker.

### 2. The Election dropdown is deleted (not "disabled when N=1")

`scope.svelte.ts` loses its `chosen_election` rune, `setElection()`, `ELECTIONS` array, and the `"yen-gov:scope:election"` localStorage key. `ScopePicker.svelte` loses the third dropdown entirely. The country/state selectors remain — those *are* citizen-meaningful axes. Election is not an axis; it is a per-place artifact.

### 3. Government-timeline is a first-class peer

The `state_government.schema.json` (already at v1.0, already populated for S03/S11/S22/S25) is promoted from "overlay for socio-economic charts" to a primary citizen surface. `frontend/src/lib/governments.ts` exposes:

```ts
fetchGovernmentTerms(state: string): Promise<GovernmentTimeline | null>
currentGovernment(timeline: GovernmentTimeline): Term | null
```

`StateOverview.svelte` leads with a "Your government" card that names the current Chief Minister, party, alliance, and term-start. President's Rule, Governor's Rule, interim, and MCC periods render with banners, not as gaps. When the timeline file is absent, the card degrades to a one-line "Government timeline coming soon" caption — the rest of the page is unaffected.

The election-result section moves *below* the government card by default. A recency rule applies: when `polled_on` is within 90 days, a slim "Latest election" banner appears at the top of the page above the government card (the news-cycle case); otherwise the government card leads and the election section is collapsed-by-default.

### 4. CI consistency is mandatory

`backend/tests/test_datasets_integrity.py` gains two tests:

- `test_election_events_catalogue_matches_backend_registry` — every `(state, event_id)` pair in `events.py` must appear in `election-events.json` and vice versa. A new `events.py` row without a catalogue row, or a stale catalogue row after a code change, fails CI loudly.
- `test_election_events_default_uniqueness_and_data_status_alignment` — at most one `default: true` per state; `data_status: complete` rows must have `result.summary.json` on disk; `data_status: pending_upstream` rows must not. Catches both "I added the row but forgot to ingest" and "I ingested but forgot to flip the status".

## Doctrine: cause vs consequence

This is the load-bearing distinction that justifies the four parts above:

- **Election** is an *event* — a discrete, dated act of voting that produces a result.
- **Government** is a *state* — a continuing condition (this party rules, this CM holds office, this alliance is in coalition) that persists between elections, sometimes interrupted by President's Rule, defections, or coalition collapse.

The citizen's primary question on `/s/<state>` is the *state*: who governs Odisha right now, what is their record. The election is the *cause* of that state, not the state itself. A site that puts elections on the spine is showing the citizen the cause and asking them to derive the consequence themselves; the civic value is exactly inverted.

This doctrine is recorded in [docs/concepts/government-vs-election.md](../../concepts/government-vs-election.md) for renderer authors and indexed from [CLAUDE.md](../../../CLAUDE.md).

## Consequences

### Acceptable / wanted

- `/s/<state>` works for every state in `election-events.json` (15 states / UTs as of this commit), not just the May-2026 cohort.
- The citizen never picks "an election" globally. Per-state event selection happens contextually, in the URL, on the elections sub-route.
- Bihar's pending ECI publication renders honestly ("awaiting publication") rather than as a 404.
- The Strategist's mandatory edge cases — President's Rule (J&K 2018-2024), AP-Telangana split (2014), defection events, MCC periods, UT asymmetry (Delhi/Puducherry/J&K), by-elections — all have explicit homes in the schema; absence in a state's file means "not yet authored", not "doesn't exist".
- Adding a new state's election (e.g. Bihar 2025 once ECI publishes) is a one-row data change, not a code change.

### Costs accepted

- The catalogue (`election-events.json`) and the backend registry (`events.py`) are two sources of partially-overlapping truth. We accept this because (a) `events.py` has fields the frontend doesn't need (`has_partywise`) and (b) the frontend can't import Python. The CI test makes the duplication safe.
- Hand-authored `cm_terms.json` files for all 15 states is a meaningful authoring effort. We ship 4 (S03, S11, S22, S25) at this commit; the remaining 10+ are tracked as a follow-up task. The UI degrades gracefully where files are absent — explicit gap rather than wrong data.
- Citizens who arrive expecting a "current election" picker will not find one. We accept that this is a small cost for a much larger correctness gain (and the welfare-first home doctrine of ADR-0022 means most citizens never expected one anyway).

### Rejected alternatives

- **B0 hotfix** (route guard that 404s gracefully when no event for state). Rejected because the underlying control is conceptually wrong; a graceful 404 still rewards a misleading interaction.
- **N=1 disabled dropdown** (current state of `ScopePicker.svelte`). Rejected for the same reason; the dropdown's existence implies "there is a global election to pick", which is false.
- **Synthesise a "national cycle" event from union of state cohorts.** Rejected as the Federal Falsehood — there is no national assembly election; each state's cycle is its own.

## References

- [ADR-0022](0022-place-first-ia-with-topic-catalogue.md) — the IA spine this builds on.
- [ADR-0014](0014-sqlite-emitter.md) — election artifact layout under `datasets/elections/<event_id>/<state>/`.
- [ADR-0016](0016-eci-statistical-reports-canonical.md) — why ECI Statistical Reports are the canonical election source.
- [docs/concepts/government-vs-election.md](../../concepts/government-vs-election.md) — citizen-facing doctrine doc for cause-vs-consequence.
- `datasets/schemas/election-events.schema.json` v1.0 — the contract.
- `datasets/reference/in/election-events.json` — the data.
- `backend/tests/test_datasets_integrity.py::test_election_events_catalogue_matches_backend_registry` — the CI gate.
