# ADR-0051: Historical Lok Sabha PC identity = override-only crosswalk + split-by-delimitation product policy

**Last Updated**: 2026-06-03
**Status**: accepted
**Deciders**: User (verbatim sign-off "author the crosswalk", supersedes per CLAUDE.md section 0a), Hans + Max (entity coding authority), Fowler (reversible-slice sequencing)

## Context

The elections experience needed the full 1999-2024 Lok Sabha general-election series at candidate grain, reusing the canonical person/candidacy model (ADR-0035) and the existing Model-C `pc-*` indicators + `IN-PC-<delim_year>-<state_code>-<pc_no>` entity scheme - no new indicator, no new id grammar.

The blocker was constituency **identity**, not data. The TCPD `All_States_GE.csv` spine carries electors/turnout/valid-votes/sex/edu/profession for every year, but the same `(tcpd_state, constituency_no)` key resolves to different canonical seats across reorganisations:

- **2008-delim splits.** Undivided Andhra Pradesh (42 seats) in 2009/2014 splits into modern AP (S01, 25) + Telangana (S29, 17) in 2019/2024. `IN-PC-2008-S01-1` is Adilabad (TG) in 2009/14 but Araku (AP) in 2019/24 - an unavoidable wrong-join, and both share delim 2008 so `delim_year` alone cannot disambiguate.
- **J&K + Ladakh.** State S09 (6 seats incl. Ladakh) in 2009/2014/2019 splits into U08 (5) + U09 (1) from 2024.
- **2000 trifurcations.** 1999 has 32 states; Chhattisgarh / Jharkhand / Uttarakhand did not yet exist - their seats were polled inside MP / Bihar / UP.
- **DNH + DD merge.** The 2020 merge to U03 collides with the `pc_id` state-code regex `[SU][0-9]{2}` (`U03-OLD` is rejected).

The 1976 vs 2008 delimitation boundary is the load-bearing axis: 1999/2004 ran on the 1976 delimitation; 2009 onward on the 2008 delimitation (boundaries frozen since, so the modern PC map paints those years fully).

## Decision

Adopt an **override-only historical PC crosswalk** plus a **split-by-delimitation product policy** that **always loads the data**.

1. **Override-only crosswalk.** `datasets/reference/in/elections/pc_historical_crosswalk.csv` (schema [pc-historical-crosswalk.schema.json](../../../datasets/schemas/pc-historical-crosswalk.schema.json), 112 rows) carries one row only for seats that need a reorganisation override. PK triple `(ge_year, tcpd_state, tcpd_constituency_no)` -> `(state_code, pc_no, match_method)`. `delim_year` is NOT a column - it is derived (`1999/2004 -> 1976`, `2009-2024 -> 2008`).
2. **Pure resolver.** `resolve_pc(ge_year, tcpd_state, constituency_no) -> (state_code, pc_no, delim_year, match_method)`: an override hit uses the row; otherwise automatic (state via `load_state_code_lookup`, `pc_no = constituency_no`, `match_method = "automatic"`).
3. **Entity coding (Hans + Max authority).** 2008-delim splits code to the **modern successor** (AP 2009/2014 -> S01 + S29; J&K 2009/2014/2019 -> U08 + U09). 1976-delim trifurcations (1999 CG/JH/UK seats) code **as-was** inside MP/Bihar/UP - zero override rows, methodology-break note only. DNH + DD -> U03 pc 1 + 2 across all years (sidesteps the `U03-OLD` regex issue).
4. **Always load the data.** 2008-delim years (2009/2014/2019/2024) paint the choropleth fully (boundaries frozen since 1976 -> zero gray). 1976-delim years (1999/2004) render **table + timeseries only** with a "1976 delimitation - boundaries differ" label. The `delim_year` embedded in each `pc_id` is the single source of truth; there is no separate `boundary_changed` boolean. Gray stripes are reserved for genuine no-coverage, which never occurs for 2009-2024.
5. **TCPD spine, no portal fetch.** The TCPD `All_States_GE.csv` (ECI-derived) is the single ingest source; the earlier Lok Dhaba portal-fetch handover was superseded once the spine was confirmed to carry all required fields. `All_States_GA.csv` stays a crosswalk reference, not the ingest source.

## Consequences

- Every GE year 1999-2024 lands 543 PCs at candidate grain, reusing the canonical person/candidacy model with no new id grammar.
- The crosswalk is auditable and minimal: only reorganised seats carry a row; the common case resolves automatically.
- The frontend grays historical (1976-delim) years from the `pc_id` prefix alone - no schema field, no per-year frontend branch.
- `dim_pcs` is generated from the ingest envelope itself, so 1976-delim `pc_id`s are self-consistent (no external boundary FK rejects them); the gray-stripe contract is covered by a unit test asserting the 1976 prefix.
- Provenance: each year carries a `source_id` FK so the postal-inclusive/exclusive and segment-sourced distinctions stay auditable.

## Alternatives considered

### A. Era-scoped identity + methodology break (new id grammar per delimitation)

Rejected. Minting a parallel id grammar for the 1976 era would fork every downstream consumer and break the single Model-C `pc-*` scheme. The `delim_year` prefix already encodes the era inside the existing grammar.

### B. Defer the conflicted states (half-coverage)

Rejected by user. Shipping a partial historical series - some states present, reorganised ones blank - damages citizen trust more than a complete table with an honest "boundaries differ" label. The product policy is always-load.

### C. Lok Dhaba portal fetch per state-year

Superseded. The signed-off fallback assumed ECI published only PDFs and the portal was the only AC-split arm; once the TCPD `All_States_GE.csv` spine was confirmed to carry electors/turnout/sex/edu/profession, the portal fetch (502-down at the time) became unnecessary.

### D. `boundary_changed` boolean column

Rejected. Redundant with the `delim_year` already embedded in every `pc_id`. Deriving the gray-stripe behaviour from the id avoids a second source of truth.

## See also

- [ADR-0035](0035-persons-fork-option-b.md) (canonical person/candidacy model this reuses)
- [ADR-0044](0044-grain-over-entity.md) (entity_id as fact-grain PK)
- [ADR-0023](0023-election-event-identity-per-place.md) (election-event identity)
- [docs/architecture/data/elections-indicators.md](../data/elections-indicators.md) (the `pc-*` indicator family)
- [docs/archive/plans/20260602-elections-experience-gap-closure-plan.md](../../archive/plans/20260602-elections-experience-gap-closure-plan.md) (the closing plan-doc, Lane B)
