# Alliance data backfill for election events (research + ingest plan) — 2026-06-12

**Status:** READY-FOR-RESEARCH (no implementation yet)
**Correction level:** Level-3 (data ingest, multi-event)
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §0a (Hans + Max own data shape) · §12 provenance · §10 anti-patterns (one indicator per concept; no UI fields in catalogue) · [docs/concepts/data-spine.md](../docs/concepts/data-spine.md).
**Predecessors:**
- PR [#954](https://github.com/miztiik/yen-gov/pull/954) (event-page UX polish, `76ab5101d` 2026-06-12) — `AllianceTotals` already loads `loadAlliances(event)`; renders "Alliance data pending for this event" when the lookup is empty.
- PR [#958](https://github.com/miztiik/yen-gov/pull/958) (PC choropleth + TileCartogram + party filter rail, `315f14e15` 2026-06-12) — `PartyBar` interface already has `alliance_short?: string | null`; tag renders zero-code-change once data lands.

## Why this exists

The user asked on 2026-06-12 (during the PR #954 follow-up) to "keep track of the alliance backfill research job — lets do that next after pc boundary integration." PC boundary integration shipped in PR #958. This plan-doc is the queued next step.

The frontend infrastructure to surface alliance affiliation is ALREADY in place across two PRs:
- `AllianceTotals` panel on every state/national event page (renders alliance×seats summary when data is present).
- `PartyBar.alliance_short?` tag (renders next to party short name when data is present).

What is missing is the upstream data. `loadAlliances(event)` returns an empty `AllianceLookup` for `general-2024` and other recent events. This plan-doc scopes the research + ingest work to fill that gap.

## Scope of research (before any ingest)

A subagent (likely Max + Hans) should produce a research report covering:

### R1. Current state audit
- What is the contract shape of `AllianceLookup` (read `frontend/src/lib/psephlab/alliances.ts` end-to-end)?
- Where is the canonical alliance data sourced from today? Walk every read path the loader uses.
- For which events DOES `loadAlliances` return non-empty lookup data? Report the per-event coverage table:
  - `general-2024`, `general-2019`, `general-2014`, `general-2009`
  - `assembly-*` (per state, per year)
- For events with non-empty lookups, what is the data shape? Sample 3 alliance rows verbatim.

### R2. Upstream sources
- Where do publishers (ECI, TCPD, Wikipedia, IndiaVotes, news outlets) record party→alliance affiliation per election?
- Are there machine-readable feeds, or is this PDF/HTML transcription work?
- For each candidate source, evaluate: licence, methodology stability, comparability across events, citation cost. Use the [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md) source-vetting discipline.

### R3. Identity model
- Alliance identity: is it `(election_event, alliance_id)` or `(alliance_id)` global-with-vintage?
- Alliance composition: does a single party belong to multiple alliances simultaneously (e.g. state-level vs national-level)? If yes, the model must carry alliance scope.
- Naming: how do we handle alliance name evolution (NDA III vs NDA II vs UPA)? Vintage-stable IDs per OWID precedent?
- Where does this fit in the canonical store? Likely a new long-format CSV under `datasets/data/entities/` per CLAUDE.md §3 doctrine; provenance FK to `data/entities/source.csv` per §12.

### R4. Citizen UX once data lands
- Does `AllianceTotals` already render correctly when data IS present? Check on an event that has non-empty lookup (from R1's coverage table). If not, what gaps remain?
- Does the `PartyBar.alliance_short` tag render correctly when populated? Test with a synthetic fixture.
- Should there be an "alliance filter" affordance on the maps (mirrors the party filter shipped in PR #958)? Out of scope for the initial backfill; flag for a Phase-2 plan.

### R5. Scope verdict
The research subagent's final block should propose ONE of:
- **(a) Ship-as-is data scope:** the data exists somewhere we can ingest; here is the per-event coverage we can realistically deliver in Phase 1 (e.g. "general-2024 + general-2019 from TCPD"). Open implementation plan-doc.
- **(b) Partial data scope:** only some events have credible sources. Phase 1 ships what we have; placeholder copy on uncovered events.
- **(c) No-data verdict:** the gap is genuinely upstream (no publisher carries this in machine-readable form). Either commit to manual curation discipline OR retire the `AllianceTotals` panel.

Each verdict carries a Hans + Max sign-off requirement and a citizen-impact framing.

## Stop conditions

- Any proposal to mint a new alliance ID without an FK to a row declaring the alliance's `(name, vintage, election_event_scope)` → BLOCKED per identity discipline.
- Any proposal to store alliance affiliation as a field on the indicator catalogue (`datasets/taxonomy/indicators.json`) → BLOCKED per CLAUDE.md §10 anti-pattern (no UI/render fields on indicator catalogue).
- Any proposal to JSON-project alliance data for the frontend → BLOCKED per §10 (no JSON projections of canonical data; must be long-format CSV via DuckDB-WASM read).
- Any proposal to fetch alliance data from a remote source at frontend runtime → BLOCKED per Holy Law #1 (static-first; everything ships in the bundle).

## Implementation discipline (when the research verdict lands)

- Subagent works in `..\yen-gov-alliance-backfill` on `feat/data-alliance-backfill-phase-N`.
- Research is read-only first; no ingest until the verdict gates pass user sign-off.
- Provenance FK to `data/entities/source.csv` per §12.
- Tests at the per-tier level per §14.
- §13 browser smoke on AT LEAST one event with newly-populated alliance data — verify `AllianceTotals` and `PartyBar.alliance_short` both render.

## Out of scope (this plan)

- Implementation. This plan opens the RESEARCH; a separate implementation plan-doc opens after Hans + Max sign off on the R5 verdict.
- "Alliance filter" map affordance (Phase 2 if useful; not now).
- Historical reconstruction beyond ~2004 LS / equivalent assembly events.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | open | Plan-doc opened per user verdict during PR #958 ask-questions. Predecessor frontend infra (AllianceTotals + PartyBar.alliance_short) is already in place; this plan covers the data backfill that lights them up. |
