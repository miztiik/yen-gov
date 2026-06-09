# Office-Holders

**Last Updated**: 2026-06-09

> Government office, electoral alliances, and CM / PM / cabinet appointments are all the same Canonical Data Model entity: **a role held by a person or party over a term.** The office-holders family models this term-shape uniformly across elected Chief Ministers, constitutional Presidents and Vice Presidents, cabinet members, and political alliances.

This concept doc captures the design decision from [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 20.4, folded in per [CLAUDE.md](../../CLAUDE.md) section 9 (ADR-retire-keep-receipts rule) + [docs/concepts/documentation-discipline.md](documentation-discipline.md) (ADR-0034 routing-contract). The originating ADR fully retires into this file: the `## Design rationale` and `## Rejected alternatives` sections below are the immutable anti-re-litigation record.

## What an office-holder is

An **office** is a named role in government - e.g. Chief Minister of Tamil Nadu = `IN-S22-CM`, President of India = `IN-PRES`, Vice President of India = `IN-VPRES`, Finance Minister = `IN-FM` (future). An **office-holder** (or just "holder") is a person who occupied that office over a specific term. A **holding** is the row that records that tenure: `(office_id, term_start, holder_id, term_end, source_id)`.

Two worked examples:

- **Office `IN-S22-CM`** (Chief Minister of Tamil Nadu) has been held by many people since 1952. One holding: M. G. Ramachandran held it from 1977-06-30 to 1987-12-24. Source: the Wikipedia "List of Chief Ministers of Tamil Nadu" article, cited once per state through the `office_citations` map.
- **Office `IN-PRES`** (President of India) is held by exactly one person at a time. Multiple holdings form the succession: Dr. Rajendra Prasad 1950-01-26 to 1962-05-13, Dr. Sarvepalli Radhakrishnan 1962-05-13 to 1967-05-13, and so on. Recent holdings cite their own detail / profile pages on the President's Secretariat site through the typed `citation_groups` map.
- **A vacancy or President's Rule interval** is also a real row: `IN-S22-CM` from one date to another with no person assigned (`holder_id = null`). The interval has a source and a duration; it does NOT pretend a person held the office.

## Three-CSV model

The office-holders family stores term-shape data as three CSV files under `datasets/data/` per plan section 20.4:

- **`entities/office.csv`** - the office register. One row per office identity. Columns: `office_id, name, office_kind, jurisdiction_entity_id, portfolio`. Example: `IN-S22-CM, Chief Minister of Tamil Nadu, cm, tamil-nadu, <null>`. `office_kind` is intentionally open-ended (`cm | pm | president | vice_president | cabinet_minister | ...`) so new office types land without a schema bump. `portfolio` (e.g. "Finance", "Defence") is reserved for future cabinet rows.

- **`entities/holder.csv`** - the holder register. One row per distinct person who has held any office. Columns: `holder_id, person_name, party_id`. The `holder_id` is a deterministic slug derived from `person_name` (e.g. `m-g-ramachandran` from `M. G. Ramachandran`). `party_id` is a nullable FK to `entities/parties.csv` because some holders are constitutionally non-partisan (President, Vice President) and some had no party affiliation at the time of holding.

- **`datapoints/office_holdings.csv`** - the term-shape observations. One row per `(office_id, term_start)` pair. Columns: `office_id, term_start, holder_id, term_end, source_id`. PK is `(office_id, term_start)`. Example: `IN-S22-CM, 1977-06-30, m-g-ramachandran, 1987-12-24, src-<wikipedia-cm-list-tamil-nadu>`.

The column contract is enforced at write time by [backend/yen_gov/canonical/csv_writer.py](../../backend/yen_gov/canonical/csv_writer.py) against [datasets/data/_schema/columns.json](../../datasets/data/_schema/columns.json).

## Term-shape invariants

- **One row per `(office_id, term_start)` (PK).** Multiple holders of the same office yield multiple rows with the same `office_id` and distinct `term_start` values.
- **`term_end` null = incumbent.** Never `datetime.now()` - that violates CLAUDE.md anti-pattern #7. The open future stays open; on a re-election or defeat, a new row is appended with the prior tenure's `term_end` filled.
- **`holder_id` is nullable.** A vacancy, President's Rule, governor's rule, or interim administration is represented with `holder_id = null` and a real source citing the gazette / notification / press release that documents the office was unassigned during that interval.
- **`source_id` is mandatory** (Holy Law #9). Every row carries a FK to exactly one row in `datasets/data/entities/source.csv`.

## Provenance

Every observation row carries a `source_id` FK to `datasets/data/entities/source.csv` per Holy Law #9. The citation ledger stores the four optional fields per plan section 7: `owner` (publisher), `title` (report or list name), `vintage` (edition or snapshot window), and `url`.

The seed file `datasets/taxonomy/office_holdings.json` supports two complementary citation mechanisms:

- **`office_citations` map.** Keyed by `office_id`, typically `IN-S<NN>-CM`. One entry per state CM office points to that state's Wikipedia "List of Chief Ministers of <State>" article. This map serves all per-state CM holdings through one URL per state - a 31-row map that drives ~700 holding rows.
- **`citation_groups` map.** Keyed by a free-form group id (e.g. `president-kovind-detail`, `vp-former-list`, `president-former-list`). Each entry carries the rich citation context (producer, title, vintage, license, confidence_tier, is_issuing_authority, verification_method, url_main, citation_full, notes). Holding rows reference a group via the `citation_group_id` field. This mechanism powers the official Government of India provenance for President / Vice President rows (President's Secretariat, Vice President Office).

A holding row uses either `citation_group_id` (rich) OR falls back to the `office_citations` map keyed on its `office_id` (concise). The compiler [backend/yen_gov/canonical/office_holdings_seed.py](../../backend/yen_gov/canonical/office_holdings_seed.py) enforces this at compile time: a holding row must resolve to one of the two; an unresolvable row is a build-break, not a silent emit.

## Why merge governments + alliances + office-holders into one family

Government office, electoral alliances, and cabinet memberships all share one structural pattern: **a role held by an entity (person or party) over a temporal interval.** The three datasets are not separate data families; they are three instantiations of one term-shape:

- A Chief Minister term = `office_id=IN-S22-CM`, `holder_id=m-g-ramachandran`, `term_start=1977-06-30`, `term_end=1987-12-24`.
- A party-alliance membership term = `alliance_id=UPA`, `party_id=parties.IN.INC`, `term_start=2004-05-14`, `term_end=2014-05-26`.
- A future cabinet appointment = `office_id=IN-FM`, `holder_id=<finance-minister-slug>`, `term_start=...`, `term_end=...`.

Archigos (the canonical political-science head-of-government events table, 2009) and OWID's national-office records both use this term-shape. Merging yen-gov's three datasets avoids the semantic duplication of three stores for one structural pattern.

The alliance datapoint lives at `datasets/data/datapoints/alliance_membership.csv` with columns `(alliance_id, party_id, term_start, term_end, source_id)`. It shares the term-shape spine with `office_holdings.csv` but is NOT a fourth entity table - alliances are a free-text label (NDA, UPA, SPA, AIADMK+, Mahagathbandhan) since no upstream issuing authority publishes a stable alliance identity register, and modelling alliances as a fourth entity would introduce a redundant register without a curator. The membership rows are back-filled from two existing sources: per-CM-tenure `alliance` fields on `office_holdings.json` (with real start_date / end_date boundaries) and per-event `party_alliances.csv` (with the election event polled_on date as the term start).

## Design rationale

This section folds in the rationale from the originating design decision [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 20.4 (Gregor verdict Q4, 2026-06-04).

### Why a term-shape datapoint instead of a one-row-per-office snapshot

A snapshot model would carry only the **current** office-holder and discard every prior tenure. Term-shape lets the citizen see: "How many Chief Ministers has Tamil Nadu had?", "Who held office during the Green Revolution?", "How long did each tenure last?", "When did the party of government shift?" - the bread-and-butter questions of civic history and comparative governance. Snapshots answer only "Who is the CM today?", which is current affairs, not governance depth.

### Why office identity is a separate register

The office itself (its name, jurisdiction, constitutional rank) is a slow-moving reference entity that many people and tenures map to. Storing office metadata in a separate `office.csv` avoids repeating it on every holding row. When a state's boundary changes or its office is renamed, one office row is edited; the hundreds of historical holdings stay unchanged. This is the same economy that makes Archigos maintainable across decades and OWID's heads-of-government dataset comparable across countries.

### Why holder identity is a separate register

A person may hold multiple offices over a lifetime (e.g. M.G. Ramachandran was an MLA before becoming CM; Sarvepalli Radhakrishnan was Vice President 1952-1962 before becoming President 1962-1967). One holder register lets the citizen ask "All offices held by <name>" without duplication. The slug derivation rule (`M. G. Ramachandran` -> `m-g-ramachandran`, deterministic lowercase-hyphenated) means different name spellings or transliteration variants can be mapped to one canonical identity through aliases without rewriting the datapoint rows.

### Why the citation_groups mechanism supports both Wikipedia URL maps and official provenance

The legacy CM ingest used a Wikipedia "List of Chief Ministers of <state>" per-state URL. A naive per-office citation row would multiply that into ~31 rows. The `office_citations` map keyed by `office_id` serves all CM holdings of a given state through one URL entry. When new constitutional office rows land (President, Vice President) with official Government of India provenance, the typed `citation_groups` mechanism lets each group carry the full citation context (producer, title, vintage, license, confidence_tier, is_issuing_authority, verification_method, url_main). The two mechanisms coexist: legacy bulk rows fall back to `office_citations`; new official-source rows use `citation_groups`. Per-role citation overrides are earned when a second concrete role lands - not pre-built.

## Rejected alternatives

The following designs were rejected. They are preserved here as an anti-re-litigation guard per [CLAUDE.md](../../CLAUDE.md) section 9 (ADR-retire-keep-receipts). Reproduced verbatim from the originating seed module docstring at [backend/yen_gov/canonical/office_holdings_seed.py](../../backend/yen_gov/canonical/office_holdings_seed.py). Do NOT re-propose any of these without an explicit user-signed scope-change row in the active plan-doc.

1. **Keep per-state cm_terms.json + add a thin index layer.** Doubles the operator's edit surface (32 files instead of 1). Loses Hans's "single git history for all CM provenance" win.

2. **Deterministic Wikipedia URL template** `f"https://en.wikipedia.org/wiki/List_of_chief_ministers_of_{state.replace(' ', '_')}"`. S19 Punjab requires a `Punjab,_India` disambiguation suffix; any template would mis-handle this and any future irregularly named office (e.g. UT-only offices with disambiguation). The `office_citations` map in `office_holdings.json` is the typed fix.

3. **Add a `role` column to office_holdings.json holdings[] rows.** Role is encoded in the office_id grammar (`IN-S22-CM`, `IN-PM`, ...); a separate column would let the two drift. Premature generalisation per Fowler review - earned when a 2nd concrete role lands.

4. **Emit one `office_citations` row per `(office_id, citation_role)`** to anticipate per-role citation overrides. YAGNI - today every office has exactly one citation (the Wikipedia list). When DCM / Gov / PM land, the per-role template plus this map handles them. Schema-evolve later if needed.

5. **Have this seed OVERWRITE `sources.parquet`** rather than upsert. Moot post-B3-pt2 (2026-06-06) - this seed no longer writes to `sources.parquet` at all. The citation rows live in `datasets/data/entities/source.csv` seeded once via the B2a/source_csv path; the canonical singleton-ledger contract still requires accumulation (B2a uses CSV-row UPSERT keyed on `source_id`, not overwrite).

6. **Materialise one office row per regime** (separate `office_id` for "elected-CM" vs "presidents_rule-Governor"). The OFFICE is the CM seat in both cases; the regime difference is captured on the holding row, not by inventing parallel offices. Unchanged from cm_terms_seed.py rejected #5.

## See also

- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) - the canonical data store design; governs the CSV column contract for every family including office-holders.
- [docs/concepts/data-provenance.md](data-provenance.md) - the source.csv citation ledger, mandatory for every observation row per Holy Law #9.
- [docs/concepts/electoral-hierarchy.md](electoral-hierarchy.md) - parallel concept for electoral entities; same LGD-joinable spine architecture.
- [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 20.4 - the binding design decision.
- [backend/yen_gov/canonical/office_holdings_seed.py](../../backend/yen_gov/canonical/office_holdings_seed.py) - compiler reading `datasets/taxonomy/office_holdings.json` and emitting the in-process parquets that feed the term-shape CSV emitter.
- [backend/yen_gov/canonical/reingest/governments_term_shape.py](../../backend/yen_gov/canonical/reingest/governments_term_shape.py) - the 3-CSV term-shape emitter (office.csv + holder.csv + datapoints/office_holdings.csv).
- [backend/yen_gov/canonical/alliance_membership_csv.py](../../backend/yen_gov/canonical/alliance_membership_csv.py) - the alliance_membership.csv emitter; back-fills from office_holdings.json (per-CM-tenure alliance) and party_alliances.csv (per-event snapshot).
- [datasets/data/_schema/columns.json](../../datasets/data/_schema/columns.json) - column contract for `office.csv`, `holder.csv`, `datapoints/office_holdings.csv`, and `datapoints/alliance_membership.csv`.
