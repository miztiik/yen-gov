# 2026-06-15 elections-catalogue completeness handover

**Last Updated**: 2026-06-15

> Spawned out of [TODO/20260615-state-election-event-page-redesign-plan.md](20260615-state-election-event-page-redesign-plan.md) \u00a70.3 / \u00a72.5 + the 5-persona review round 2 (2026-06-15) by Hans + Max + Jony convergence. This is a population-debt handover, NOT a schema-debt handover. Authority per [CLAUDE.md](../CLAUDE.md) \u00a70a: Hans + Max own data shape; Jony + Citizen own the citizen-facing honesty copy; Gregor sanity-checks any contract surface that surfaces during execution.
>
> **Scope discipline**: this doc inventories WHAT is missing, RANKS by priority, and PRESCRIBES the curation seam. It does NOT pre-author the catalogue rows. The curator (Hans + Max) ships per-row PRs against `datasets/taxonomy/election_events.json` and per-event disk dirs in batches; this doc is the run book for those PRs.

## 1. Problem statement

Today's [datasets/taxonomy/election_events.json](../datasets/taxonomy/election_events.json) declares 303 assembly events across all 36 polities. On-disk under [datasets/elections/assembly/state=*/election=*/summary.csv](../datasets/elections/assembly) there are 870 per-event dirs holding REAL winner rows (each `summary.csv` has 1 row per AC with non-null `winner_*` columns). The gap is **567 disk-only events**, spanning **31 of 36 polities** (top-10 gaps below).

Citizen consequence today: any frontend surface that lists \"elections this state has held\" - the `/<state>/elections/` landing route (Row R2 of the parent plan), the AssemblyElections card grid at `/t/elections/assemblies`, the year-chip rail (R4 chrome) - reflects the catalogue, not the disk. Citizens see a UI-shaped pretence that India has held ~300 assembly elections when the actual corpus is ~870. Per Hans (Rosling rule): silence on a population we know about IS a methodology call; the absence must be either FIXED (publish the rows) or DISCLOSED (footer / coverage caption naming the boundary).

## 2. The wider audit (2026-06-15)

Top-10 gaps (cat_asm = catalogue assembly events; disk = on-disk per-event dirs; gap = disk - cat):

| polity | cat_asm | disk | gap |
| --- | --- | --- | --- |
| Andhra Pradesh (S01) | varies | varies | 40 |
| Uttar Pradesh (S24) | varies | varies | 37 |
| Madhya Pradesh (S12) | varies | varies | 36 |
| West Bengal (S25) | varies | varies | 30 |
| Bihar (S04) | 12 | 41 | 29 |
| Karnataka (S10) | varies | varies | 28 |
| Maharashtra (S13) | varies | varies | 28 |
| Rajasthan (S20) | varies | varies | 26 |
| Gujarat (S06) | varies | varies | 25 |
| Punjab (S19) | varies | varies | 23 |
| Jammu & Kashmir (U08) | 1 | 22 | 21 |

Other 21 of 31 affected polities each contribute fewer (range 1-20). 5 polities have gap = 0 (no-legislature UTs and recently-cleaned states). Re-run the audit before each batch PR so the orchestrator works from fresh counts; the bounded audit helper used by the parent plan \u00a70.3 should be promoted to a permanent CLI subcommand in the first batch PR (see \u00a75 below).

## 3. NOT a schema issue

Catalogue schema [datasets/schemas/election-events.schema.json](../datasets/schemas/election-events.schema.json) is v1.3 and ALREADY supports every kind of event the disk holds:

- `kind` enum: `{assembly, parliament, general_bye, assembly_bye, by_election}` - covers regular polls + general by-elections + assembly by-elections + miscellaneous by-elections.
- `event_id` regex: `^(assembly|parliament|general-bye|assembly-bye|by-election)-\\d{4}(?:-[a-z0-9-]+)?$` - covers the long-form `assembly-bye-<YYYY>-<seat-slug>` grammar that the existing on-disk dir `state=karnataka/election=2024-channapatna-bye/` already uses.
- `event_id_aliases` field carries `AcGenFeb2005` / `AcGenNov2005` / `BeAcS04AC182_2018` / ECI internal codes verbatim.
- `polled_on` is required; `polled_on_to` available for multi-phase polls.

The 567-gap is purely the work of authoring 567 rows. No schema bump. No new fields. No new event kinds. If a future curation finds a new shape (e.g. council elections, panchayat aggregates), THAT triggers a schema discussion - but the 567-known-gap does not.

## 4. Priority ordering (Max + Hans, ratified)

Curation order:

- **(d) Latest-decade contemporary by-elections** (2014-2024 across all states) - HIGHEST PRIORITY. These are events citizens are actively comparing now; visible drift from real political life is the largest citizen-honesty cost. ~150-200 events estimated; mostly `assembly_bye` kind.
- **(b) Mid-period regular assembly polls** (1977-2014, excluding by-elections) - SECOND. Anchors the cross-event SwingSankey (R5 in the parent plan) and the year-chip rail. ~200 events.
- **(a) Recent historical by-elections** (1990-2014) - THIRD. Lower citizen-recognition density; still essential for Karnataka 2008-2014 anti-defection drama, BJP-JDS coalition wobble, etc. ~120 events.
- **(c) Pre-1977 historical assembly polls + President's-Rule-era events** - LAST. Highest-effort curation (source files thin; party-id resolution often non-trivial because pre-1977 entities don't all map to today's seven national parties); lowest citizen-comparison density. ~90 events.

Rationale per Max: the citizen mental model anchors on \"what has my state done in my lifetime\". Latest-decade-first respects the mental model. Pre-1977 is research-grade depth that the long-arc trajectory rails (Brichter-style year scrub) can show but no citizen is querying directly on first visit.

## 5. Pipeline plan

- **Catalogue rows**: per-event entries appended to [datasets/taxonomy/election_events.json](../datasets/taxonomy/election_events.json) under the right `eci_code` key; one entry per event with `kind`, `event_id`, `display`, `polled_on`, optional `polled_on_to`, `event_id_aliases`, `topic_ids`.
- **Source identity**: each new catalogue row's mart projection requires a source row in [datasets/data/entities/source.csv](../datasets/data/entities/source.csv). Default source = ECI Statistical Reports (one per (publisher, title, vintage) per [CLAUDE.md \u00a712](../CLAUDE.md) + [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md)). `source_id` derived via `backend.yen_gov.canonical.citation.derive_source_id` - NEVER hand-authored.
- **Per-event disk dirs**: most exist already; the gap is catalogue, not disk. Curator verifies each on-disk dir against the new catalogue row (schema-conformance + winner count plausibility); if disk dir is malformed, file a separate STOP-AND-SURFACE.
- **Mart regen**: after each batch, `python -m yen_gov derive-event-summary --root .` lights up the new rows in [datasets/data/marts/elections/event_summary.csv](../datasets/data/marts/elections/event_summary.csv). Idempotence + no-flush invariants per parent plan's R1.5 gates.
- **Audit helper -> CLI**: in the first batch PR of this handover, promote the parent plan's runtime audit helper to a permanent Typer command, e.g. `python -m yen_gov audit-catalogue-vs-disk --kind assembly`. Output: per-state cat/disk/gap table. Lives at `backend/yen_gov/cli.py` + tested via tmp_path fixture (no live corpus walk per [CLAUDE.md \u00a710](../CLAUDE.md)).

## 6. Citizen-honesty footer (Hans + Jony co-authored)

Until the gap closes to zero (or to a known-bounded residual), every citizen-facing surface that lists assembly events for a state MUST carry a coverage footer. The copy lives in a single component (`frontend/src/lib/elections/CoverageFooter.svelte` NEW) consumed by:

- `AssemblyElections.svelte` (the card grid at `/t/elections/assemblies`).
- `StateElectionsLanding.svelte` (the new landing route from parent plan R2).
- Any future per-state election index.

Footer copy v1 (slate-600, small caps; placement at the bottom of the page):

> Coverage note: this view shows the {N_cat} assembly elections currently in our catalogue for {state_name}. Our disk corpus holds {N_disk} per-event files; the {gap} unlisted events are being curated batch-by-batch. See the coverage tracker at [TODO/20260615-elections-catalogue-completeness-handover.md] for the schedule.

Numbers source: a small `coverage.json` artifact emitted by the audit CLI, served as static data to the frontend. Hans's rule: NEVER imply we have complete coverage; the citizen who notices the gap learns about the curation work and can audit the schedule. The footer disappears automatically once `gap == 0` for that state.

Failure mode to avoid: the footer becomes a permanent decoration nobody reads. Jony's mitigation: the footer text is dense + slate-600 + small; it does NOT render as a chip/badge/pill that catches the eye. It is a citation note, not chrome.

## 7. Acceptance gates per batch PR

Each batch PR (one batch = one priority tier or one state group, curator's call) ships with:

- [ ] G1 `python -m yen_gov validate --root .` exit 0 (catalogue + mart schema-conformance).
- [ ] G2 Catalogue PK invariant test (NEW or extended) passes: no duplicate `(eci_code, kind, event_id)` tuples across the catalogue. Inherits from parent plan R1.6.
- [ ] G3 Mart regen idempotent: rerun produces 0 changed bytes.
- [ ] G4 Audit CLI shows the targeted state's gap shrinking by the expected count; no OTHER state's gap regresses.
- [ ] G5 `bun run test` green (frontend); `bun x playwright test e2e/golden-path.spec.ts` green.
- [ ] G6 Browser smoke per [CLAUDE.md \u00a713](../CLAUDE.md): `/t/elections/assemblies` shows the newly-lit cards; the AssemblyElections grid does not regress on any other state; the CoverageFooter renders the right `(N_cat, N_disk, gap)` for at least 3 sample states (full + partial + empty).
- [ ] G7 Doctrinal: each new catalogue row carries `source_id` FK to a `datasets/data/entities/source.csv` row (Holy Law #9); `update_period_days` recorded where applicable (typically irrelevant for one-shot historical events, but the catalogue-level publisher cadence stays declared on the source row).

## 8. Out of scope (do NOT pull in)

- Parliament events (`kind=parliament`). The same gap class likely exists; handle in a sibling handover-doc. Hans + Max own that scoping decision.
- Council elections (`kind=council`? - not yet a catalogue kind). If discovered during curation, file a separate schema discussion; do NOT mint a new kind silently.
- Local body elections (panchayat / municipal). Out of canonical-store scope per current doctrine; cite [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) if a citizen requests them.
- Pre-1952 events. Lower-priority research; deferred indefinitely unless a specific use case surfaces.
- Any retroactive party-id reassignment across history (e.g. Janata Party splits, Lok Dal lineages). Party-id resolution per row uses the same `parties.csv` + `party_alliances.csv` discipline; novel cases route through `docs/concepts/parties-and-alliances.md`.

## 9. Open questions

- (1) Should pre-2008-delim Bihar / J&K / AP rows resolve their AC entity_ids against the pre-delim AC enumeration or be carried as opaque strings? Max's instinct: opaque strings keyed on the source-XLSX form, with a column note disclosing the delim era. Hans + Gregor to ratify.
- (2) Should the coverage footer link to this handover-doc directly, or to a curator-facing dashboard? Jony's instinct: link to a frontend-rendered tracker page (e.g. `/about/coverage/elections`) that mirrors this doc but is citizen-readable; the handover-doc itself stays operator-facing. Carve out work for a follow-up plan.
- (3) Bihar 2005 collision (the duplicate `assembly-2005`) is handled by parent plan R1.6 (schema bump 1.3 -> 1.4 + grammar extension to `<kind>-<YYYY>-<month-slug>`). If any other same-year same-kind collision is found during this curation, it inherits the same grammar. Verify gate 2 (catalogue PK invariant) catches it.

## 10. References

- Parent plan: [TODO/20260615-state-election-event-page-redesign-plan.md](20260615-state-election-event-page-redesign-plan.md) Sections 0.3 + 2.5 + 2.6 + Section 9 review round 2.
- [CLAUDE.md](../CLAUDE.md) \u00a70a (authority table) + \u00a76 (correction levels) + \u00a710 (STOP-AND-SURFACE) + \u00a712 (provenance).
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md), [docs/agents/guardrails.md](../docs/agents/guardrails.md).
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) (Rosling rule on silence).
- [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md) (citation ledger + source_id derivation).
- [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) (catalogue location + bridges).
- [datasets/schemas/election-events.schema.json](../datasets/schemas/election-events.schema.json) (v1.3 - the schema that ALREADY covers all kinds; no bump for this handover).
- [backend/yen_gov/sources/eci/events.py](../backend/yen_gov/sources/eci/events.py) (backend already encodes most ECI internal codes; cross-reference when assigning `event_id_aliases`).
- [docs/architecture/backend/sources-eci.md](../docs/architecture/backend/sources-eci.md) (Bihar 2005 anchor doctrine + ECI source identity contract).

## 11. Ledger

| Date | Note |
| --- | --- |
| 2026-06-15 | Spawned from parent-plan review round 2. Outline owned by Max (priority ranking d > b > a > c); footer copy owned by Hans + Jony (CoverageFooter component); per-batch gates owned by Fowler (test discipline) + Gregor (contract surfaces). No batch PRs filed yet. |
