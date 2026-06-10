# Government vs Election: cause and consequence

**Last Updated**: 2026-05-25

**Audience**: anyone authoring a renderer, route, or copy-string that touches state-level politics.

**TL;DR**: A *government* is the continuing condition of who rules a state on a given date. An *election* is the discrete event that produced (or failed to produce) that condition. The citizen's primary question is the government; the election is part of its provenance. Constitutional office tenures (President, Vice President, Governor) share the same office-holdings table, but they are not state-government regimes.

## The distinction

| | Election | Government |
|---|---|---|
| **What it is** | A discrete, dated act of voting | A continuing condition between events |
| **Schema** | `result.summary.schema.json`, `result.constituency.schema.json` | `office-holdings.schema.json` |
| **On disk** | `datasets/elections/<event_id>/<state>/` | `datasets/taxonomy/office_holdings.json` (consolidated long-form; G.1.c 2026-05-22) |
| **Indexed by** | `event_id` (e.g. `AcGenJun2024`) | A date — pick a date, look up the holding covering it |
| **Citizen question** | "What did people vote in 2024?" | "Who governs Odisha right now?" |
| **Gap behaviour** | Empty if not yet polled | Filled with `regime: presidents_rule | governors_rule | interim` |
| **Ends** | The day polling closes | When a successor takes office (or never, for the current holding) |

A government term is what *is*; an election is part of how that term came to be. Other parts include defections, coalition collapses, no-confidence motions, dismissals under Article 356. All of these are first-class events in `office_holdings.json` `notes` and `references`; not all of them are elections.

The same authoring file also carries constitutional office tenures. For these rows, `regime` can be `null`: the President of India and Vice President of India are office-holders, but their tenures are not `elected | presidents_rule | governors_rule | interim` state-government conditions. `selection_method` records how the person reaches the office (`electoral_college` for President/VP, `appointed_by_president` for Governors when validated batches land). `tenure_status` records whether the row is `substantive`, `acting`, or `additional_charge`.

## Why we treat them as peers, not parent-child

The naive model says: an election produces a government, so government is downstream of election, so election should lead. Three problems:

1. **President's Rule.** J&K had no elected government from 2018 to 2024. There was no "current election" — just six years of central administration under Article 356, which is itself the government during that window. A site that displays "the current election" for J&K either lies or shows a 2014 result that is causally disconnected from who actually governed in 2020.
2. **Mid-term churn.** The government that polls produced is not always the government that holds office at any given mid-cycle moment. Maharashtra 2019: the post-poll alliance collapsed, BJP-led briefly, then MVA, then Eknath Shinde's split. Every one of those is a distinct row in `office_holdings.json`; the election was one event, the governments were several.
3. **State asymmetry.** Some states haven't polled in five years; others polled last month. A spine that asks "which election" before showing "which state" assumes a national synchrony that doesn't exist (see [ADR-0023](electoral-hierarchy.md#adr-0023-election-event-identity-per-place)).

The correct model: *government is the resource a citizen is asking about*; *election is one kind of provenance for it*. They are sibling concepts joined at the term boundary, not parent and child.

## Renderer implications

When you write a route or component that touches `/s/<state>`:

1. **Lead with the government, not the election.** The "Your government" card (current CM, party, alliance, term-start) is the citizen's primary anchor.
2. **Use the recency rule for the election.** If the most recent `polled_on` for the state's default event is within 90 days, surface a slim "Latest election" banner above the government card. Otherwise the election section is collapsed-by-default below the government card.
3. **Render regime gaps explicitly.** A `regime: presidents_rule` term is a government term, not a missing election. Render it with the President's Rule banner; do not show "no government" or "election overdue".
4. **Never co-mingle assembly and Parliament.** They elect different bodies. A state's MPs go to Delhi; the state government is not affected by Parliament results. Keep the two artifact families on separate sub-routes (`/s/<state>/elections` for assembly; Parliament gets its own surface when ingested).
5. **Cohort codes are invisible.** `AcGenMay2026` (the backend cohort id in `events.py` and the on-disk CSV `period_label`) never appears in citizen-facing chrome. Per PR-W2a (2026-06-10) the catalogue at `datasets/taxonomy/election_events.json` exposes the citizen-readable `event_id` (`assembly-2026`) plus a `display` field (*"Tamil Nadu Assembly - May 2026"*); the prior cohort id lives in `event_id_aliases` as a one-release strangler.

## Authoring implications

When you add a new state's data:

1. **Add the election event** to `datasets/taxonomy/election_events.json` with the citizen-facing `display`, the polling date, and a `data_status`. The CI test will hold the catalogue in sync with `backend/yen_gov/sources/eci/events.py`.
2. **Add the government term(s)** to `datasets/taxonomy/office_holdings.json` (long-form `holdings[]` array; G.1.c 2026-05-22). At minimum, add the current term (start_date = swearing-in date, regime = `elected`, party_eci_code, alliance, person_name). Earlier terms can be backfilled later; the file degrades gracefully.
3. **Don't author from memory.** CM rows still use the legacy `office_citations` path plus per-term `references[]` where useful. National constitutional-office rows must cite official Government of India `citation_groups`; TCPD can seed and QA candidate rows, but it is not canonical citizen-facing provenance while official sources exist.

## Edge cases the schemas already accommodate

- **President's Rule / Governor's Rule**: `regime` enum values; `cm_name`, `party_code`, `alliance` are nullable.
- **Caretaker / interim governments**: `regime: interim`.
- **Defection-driven CM changes**: a new term begins on the date of swearing-in; `notes` records the defection / split / no-confidence trigger.
- **By-elections**: a separate row in `election-events.json` with `kind: by_election`. By-elections do not produce a new government term (they backfill seats); they don't appear in `office_holdings.json` unless they triggered a CM change.
- **AP-Telangana split (2014)**: pre-split terms in S01 (combined Andhra Pradesh) end on 2014-06-01; post-split terms in S01 (residual AP) and S29 (Telangana) start on 2014-06-02. The schema allows a `notes` field on each term to record the structural cause.
- **MCC (Model Code of Conduct) periods**: not yet a first-class regime in the schema; current convention is to record in `notes` of the in-force term. A future schema bump may add `mcc_active_from`/`mcc_active_to` if surface demand emerges.
- **UT asymmetry**: Delhi (Article 239AA — limited subjects), Puducherry (30 elected + 3 nominated), J&K (UT since 2019 — narrower than full state). Recorded in the `notes` of each respective `election-events.json` entry; UI banners can branch on the state's `tier` from `state.schema.json` v3.3.
- **Constitutional offices**: President / Vice President rows use `regime: null`, `selection_method: electoral_college`, `tenure_status: substantive`, and official `citation_group_id` provenance. Acting intervals are deferred until official source rows are captured; gaps remain gaps rather than guessed acting tenures.
- **Governors**: Governor rows are deferred to source-validated batches because the TCPD governors CSV is only a seed/QA checklist and the 825 rows require Raj Bhavan/state validation.

## See also

- [ADR-0022](place-first-ia.md#adr-0022-place-first-ia-with-topic-catalogue) — place-first IA spine; elections-are-one-of-many doctrine.
- [ADR-0023](electoral-hierarchy.md#adr-0023-election-event-identity-per-place) — the structural decision this doc supports.
- `datasets/schemas/election-events.schema.json` v1.0 — per-state election inventory contract.
- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) -- canonical store for election-results and government-tenure CSVs.
- [governments.md](../architecture/data/governments.md) — governments family authoring and compile contract.
- `datasets/schemas/office-holdings.schema.json` v1.1 — government-office holdings contract (replaces the retired `state_government.schema.json`; G.1.c 2026-05-22).
