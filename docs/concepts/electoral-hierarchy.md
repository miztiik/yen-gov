# Electoral Hierarchy

**Last Updated**: 2026-06-05

> Indian electoral geography is a layered hierarchy. Every Assembly Constituency (AC) sits inside exactly one Lok Sabha (Parliamentary) Constituency (PC), but its relationship to districts is many-valued: an AC usually lies within one district yet can span several (urban-rural boundary cases, and post-delimitation district carve-outs). yen-gov treats the AC->PC link as a single `parent`, and the AC/PC->district link as a 1:many membership table (`entities/electoral_district_membership.csv`, round-7). See the data-and-charting platform reset plan section 3.

## The hierarchy

```
Country (IN)
└── State / UT (S22 = Tamil Nadu, …)
    ├── District (LGD code or Wikipedia slug)
    │   └── Assembly Constituency (AC)        ← `body=AC`, `eci_no` 1..N within state
    └── Parliamentary Constituency (PC)       ← `body=PC`, `eci_no` 1..M within state
        └── (each AC also nests under one PC)
```

One strict fact and one many-valued fact govern ACs:

1. **An AC maps to one or more districts (1:many).** District boundaries are administrative; AC boundaries are NOT guaranteed to respect them. The Local Government Directory (LGD) Constituency Coverage Report (the canonical source, parsed from the LGD portal export into `entities/electoral_district_membership.csv`) records every `(ac, district)` coverage edge: most ACs cover exactly one district (`is_primary`), but urban-rural cases and post-delimitation district carve-outs make some ACs span two or more. The old "an AC is wholly inside one district" invariant was FALSE and is retired (round-7); the relationship lives in `entities/electoral_district_membership.csv`, never a single `district_id`.
2. **An AC is wholly inside one PC (strict, 1:1).** This is set by the Election Commission's [Delimitation of Parliamentary and Assembly Constituencies Order, 2008](https://eci.gov.in/delimitation-website/) and revised only when delimitation is redone (currently scheduled post-2026 census). This is the AC's single `parent` in `entities/electoral.csv`.

PCs themselves do *not* nest inside districts — a single PC routinely spans 6–8 districts. So `district_id` is required on AC items but absent from PC items, and `pc_id` is required on AC items but forbidden on PC items.

## Why this matters for the schema

Without these two fields you cannot answer questions every consumer of this dataset will ask:

- "Show me all ACs in Coimbatore district" — needs `district_id` on each AC.
- "How did the 7 ACs that make up the Sriperumbudur Lok Sabha seat split between alliances?" — needs `pc_id` on each AC.
- "What is the district-level swing between 2021 and 2026?" — needs `district_id` to aggregate AC results.
- Free-text search for "Coimbatore" returning both the PC and its constituent ACs — needs the link.

These are the bread-and-butter queries of election analysis, not edge cases. Reference data that omits the hierarchy forces every consumer to reinvent it from PDFs, which is exactly the kind of work the project exists to eliminate once.

## The `status` lifecycle

Reference files declare a `status`:

- **`provisional`** — bootstrapped from a single source (typically Wikipedia). Hierarchy fields MAY be absent. Useful for shipping the long tail quickly without lying about validation.
- **`complete`** — cross-checked against an authoritative ECI source (Delimitation Order 2008 or `results.eci.gov.in`). For `body=AC`, `district_id` and `pc_id` are REQUIRED on every item. Promotion to `complete` adds the ECI URL to `sources[]` in the same commit.

This is enforced by the validator via JSON Schema `if/then`. A `complete` AC file missing `pc_id` on any item fails CI.

See [data-model.md](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle) for the full rationale.

## Source cascade

For Indian electoral geography, the trustworthy sources in descending order:

| Source | Authority for | Trade-off |
| ------ | ------------- | --------- |
| ECI Delimitation Order 2008 (PDF) | AC↔PC↔district mapping, reservation, AC/PC numbering | Authoritative but PDF; one-time scrape per state |
| `results.eci.gov.in` constituency pages | ECI numbering, name spelling, reservation | Live; no district/PC mapping |
| CEO state office (`ceo<state>.nic.in`) | Electoral roll counts, polling station lists | Inconsistent format across states |
| LGD portal (`lgdirectory.gov.in`) | District codes, names, lineage | Authoritative for districts, irrelevant for constituencies |
| Wikipedia constituency-list pages | All of the above, in one table | Crowd-sourced; useful for bootstrap, never sufficient alone for `complete` |

## What goes where

| Field | Lives on | Why |
| ----- | -------- | --- |
| `district_id`, `pc_id` | constituency reference (`constituency.schema.json`) | Stable hierarchy; doesn't change between elections |
| `electors` (snapshot) | constituency reference, optional | Roll snapshot is closer to a constituency property than to a result |
| `established_year` | constituency reference, optional | Property of the boundary, not of any one election |
| Turnout %, votes-cast counts, change vs. previous election | result schemas (`result.constituency.schema.json`) | Properties of an *election event*, not of the constituency itself |
| Winner, candidate list | result schemas | Same |

This split keeps reference data stable across elections and makes result-time data composable.

## Design rationale

This section folds in the receipts from the originating ADRs that pinned the electoral-hierarchy model (`docs/architecture/decisions/` originating files deleted in D-DOC3.10 closure), per [parent plan section 9](../../TODO/20260603-data-and-charting-platform-reset-plan.md) (keep-receipts ADR retirement) and [decision-index.md](../reference/decision-index.md). The verbatim rejected alternatives live under [Rejected alternatives](#rejected-alternatives).

### ADR-0015: constituency-hierarchy-fields

**Context.** Schema v3.0 of `constituency.schema.json` carried only `eci_no`, `name`, `reservation`, and an OPTIONAL `district_id`. That shape lets a state's constituency list bootstrap from Wikipedia in one shot but loses two relationships intrinsic to Indian electoral geography: (1) every AC sits inside one or more districts (the LGD Constituency Coverage Report records every `(ac, district)` coverage edge; most ACs are 1:1 but urban-rural and post-delimitation carve-outs make some span two or more); (2) every AC nests under exactly one Parliamentary Constituency per the Election Commission's [Delimitation Order 2008](https://eci.gov.in/delimitation-website/). User direction (verbatim): "district has to be mandatory, which Lok Sabha constituency it is part of has to be mandatory because these two are hierarchical entities. They should always exist." The user also distinguished `electors` (a stable-ish constituency property) from "change from previous election" (a derived comparison that belongs in `result.constituency.schema.json`, not in reference data) - which motivated a `status` lifecycle to ship Wikipedia-bootstrapped data immediately without claiming ECI validation.

**Decision.** Schema v4.0 adds four item-level fields - `district_id` (string; required when `body=AC and status=complete`), `pc_id` (string `^[SU]\d{2}-PC-\d+$`; required when `body=AC and status=complete`; FORBIDDEN when `body=PC`), `electors` (integer >= 0; never required), `established_year` (integer; never required) - plus one file-level field `status: "provisional" | "complete"` (required). Per ADR-0049 the canonical INTERNAL join key is now `lgd_ac_id`; `eci_no` and the `<state>-PC-<eci_no>` composite stay as the citizen-facing display + URL label. Conditional requirement is enforced via JSON Schema `if/then/allOf` so a single schema covers AC + PC files and both lifecycle states. A `complete` file MUST have at least one ECI-domain URL in `sources[]`. Acceptable ECI sources in order of authority: Delimitation Order 2008 PDF; results portal constituency pages (`results.eci.gov.in`); CEO state office publications (`ceo<state>.nic.in`). Wikipedia stays a valid `provisional` source and may stay in `sources[]` after promotion (multi-entry `sources` per archived ADR-0002).

**Consequences.** AC<->PC<->district relationships are first-class, machine-readable, and validator-enforced for any file claiming completeness. Frontend search, district rollups, and PC-level analytics work without extra joins. `status` lets Wikipedia-bootstrapped reference data ship immediately without lying that it has been ECI-validated. The result-time / reference-time split keeps both schemas honest. Cost: `provisional` files exist in the repo, so a reader skimming a file must check `status` before trusting that `district_id`/`pc_id` exhaust the universe (mitigated by surfacing `status` in the file and any visualization). Promoting to `complete` is real work (for TN it means reading the 2008 Delimitation Order to confirm 234 AC<->PC mappings and 234 AC<->district mappings) - acceptable because that work is the entire point.

### ADR-0023: election-event-identity-per-place

**Context.** ADR-0022 mandated a place-first spine and demoted elections from "the spine" to "one indicator family among many". The first concrete consequence on `/s/:state` for every state but the five May-2026 cohort was a 404: a citizen typing `/s/andhra-pradesh` saw no AP page because seven separate route components had hardcoded `const event = "AcGenMay2026"` and asked for `/data/elections/AcGenMay2026/S01/result.summary.json`. AP has never had a May-2026 election. The shallow fix (a global "Election" dropdown) was the same architectural mistake at a different layer: (1) it denies federal reality - there is no single Indian "current election" that all states share; AP was last elected in 2024, Bihar in 2025, TN/Kerala in 2026, J&K in 2024 after six years of President's Rule; (2) it makes the wrong thing primary - a citizen on `/s/odisha` wants Odisha (the State Government, the BJD-to-BJP transition, the 2027 budget), not whether the dropdown above the page says "May 2026" or "June 2024"; (3) it bakes a temporary scaffold - the dropdown was added when AcGenMay2026 was the only ingested event so `<select>` made the only-option case "look right", and as soon as a second event landed the dropdown became a misleading pseudo-control. A two-subagent consultation (Architect Gregor + Governance Strategist, 2026-05-11) converged independently: **election event identity is intrinsically per-place** (no two states necessarily share an event), and **government-term is the citizen unit of state politics**, with elections as the *cause* of government changes rather than the unit itself.

**Decision.** Four-part structural change, none optional: (1) per-state election inventory replaces the global dropdown - a new typed contract (`datasets/schemas/election-events.schema.json` v1.0 + `datasets/reference/in/election-events.json`) declares per state the chronological list of election events on disk with `event_id`, `kind` (`assembly | lok_sabha | by_election`; never co-mingled), `display`, `polled_on`, `data_status: complete | partial | pending_upstream`, `term_end_estimated`. (Per the 2026-05-24 update: the hand-authored `default: true` field and its uniqueness test were retired; per-state default is now derived from `max(polled_on)` after eight states silently rendered the wrong default event because their on-disk rows had no `default: true` set and the selector fell through to `rows[0]` (= the oldest event)). Frontend reads via `frontend/src/lib/election-events.ts` exposing `defaultEventForState(state)`, `listEventsForState(state)`, `findEvent(state, eventId)`. (2) The Election dropdown is DELETED (not "disabled when N=1"): `scope.svelte.ts` loses `chosen_election`, `setElection()`, `ELECTIONS`, and the localStorage key; `ScopePicker.svelte` loses the third dropdown entirely. The country/state selectors remain - those ARE citizen-meaningful axes. (3) Government-timeline is a first-class peer: `office-holdings.schema.json` v1.0 (populated for all 31 states in `datasets/taxonomy/office_holdings.json` since G.1.c on 2026-05-22) is promoted to a primary citizen surface; `StateOverview.svelte` leads with a "Your government" card. The election-result section moves BELOW the government card by default; when `polled_on` is within 90 days a slim "Latest election" banner appears above the government card (the news-cycle case). (4) CI consistency is mandatory via `test_election_events_catalogue_matches_backend_registry` (every `(state, event_id)` pair in `events.py` must appear in `election-events.json` and vice versa) and the data_status / result.summary.json alignment test.

**Doctrine: cause vs consequence.** Election is an EVENT (a discrete dated act of voting that produces a result). Government is a STATE (a continuing condition - this party rules, this CM holds office, this alliance coalesces - that persists between elections, sometimes interrupted by President's Rule, defections, or coalition collapse). The citizen's primary question on `/s/<state>` is the STATE (who governs Odisha right now, what is their record); the election is the CAUSE of that state, not the state itself. A site that puts elections on the spine shows the citizen the cause and asks them to derive the consequence - the civic value is exactly inverted. The 2026-05-13 addendum permits a per-state event picker on `/s/<state>` (small `<select>` next to the header) when `listEventsForState(state).length > 1`; the picker is per-state-bounded (resets on navigation; disappears when N=1), preserves URL-segment deep-linking, and is a UI shortcut on top of the URL-segment route - not a global picker.

**Consequences.** `/s/<state>` works for every state in `election-events.json`. The citizen never picks an election globally - per-state event selection happens contextually in the URL on the elections sub-route. Bihar's pending ECI publication renders honestly ("awaiting publication") rather than as 404. The Strategist's mandatory edge cases (President's Rule J&K 2018-2024, AP-Telangana split 2014, defection events, MCC periods, UT asymmetry, by-elections) all have explicit homes in the schema; absence in a state's file means "not yet authored", not "doesn't exist". Adding a new state's election is a one-row data change, not a code change. Costs: the catalogue + backend registry are two partially-overlapping sources of truth (events.py has fields the frontend doesn't need; the frontend cannot import Python - the CI test makes the duplication safe). Hand-authored CM-tenure data for 31 states is meaningful authoring effort; ship-and-degrade-gracefully where holdings are absent.

### ADR-0049: canonical-ac-join-key

**Context.** AC identity in yen-gov had two spines. Boundary shards key on `lgd_ac_id` (the LGD numeric Assembly Constituency code) per the LGD-golden doctrine (`docs/concepts/admin-level-sourcing.md`), while election-results parquets, indicator-family tables, SoT `constituencies.json` files, and the frontend boundary<->data join still key on `eci_no` (ECI's per-state 1..N ballot enumeration). Every cross-cut paid a name-based translation cost, and no national AC-level indicator could adopt a single primary key. The R1 audit (now Appendix A of [TODO/20260530-eci-to-lgd-acid-migration-plan.md](../../TODO/20260530-eci-to-lgd-acid-migration-plan.md); originally `notes/20260601-eci-to-acid-migration-surface-audit.md`, lifted 2026-06-08 G4) mapped ~95 files / ~260 references across 8 surfaces. A direct boundary-file inspection on 2026-06-01 corrected an earlier framing: **30 of 31 AC partitions already carry the LGD code** in feature properties as `AC_ID` (2-digit `State_LGD` + 3-digit `ac_no`, globally unique). Only **U08 (J&K)** genuinely lacks it (post-2022 delimitation, `seat_id` only). The SoT JSON 0% coverage is true but misleading: the LGD data lives in the boundary shards, not the SoT files. The real gap was a single binding table, not external sourcing. ADR-0044 keeps `entity_id` (`IN-<state>-AC-<delim>-<eci_no>`) as the fact-grain PK; this ADR does not reopen it.

**Decision.** Adopt **Strategy-D-hardened**: `lgd_ac_id` becomes the canonical INTERNAL join key; `eci_no` is demoted from identity to the citizen-facing display + URL label. (1) Crosswalk as one Canonical Data Model: `datasets/taxonomy/ac_crosswalk.parquet` (schema `ac-crosswalk.schema.json`) holds one row per `(state_code, eci_no)`, total over every SoT AC, binding it to `lgd_ac_id` (nullable) plus `ac_id`, `ac_name`, `delim_year`, `match_method`, `source_id`. (2) `entity_id` stays PK (ADR-0044 untouched); `lgd_ac_id` is a nullable join attribute, not a new identity. (3) Harvest-then-fill: crosswalk harvested from existing boundary `AC_ID` provenance for the ~30 covered states (`match_method=lgd_direct` where ECI and LGD numbering coincide, `name_reservation_join` where they diverge); U08 and any unresolved AC get `lgd_ac_id=null, match_method=unmapped` and ride `ac_no`/`eci_no` until filled. (4) Bijection-and-completeness invariant: a single contract test (`ac_crosswalk.assert_bijection`) is the migration's load-bearing safety net (PK totality, `lgd_ac_id` global uniqueness, strict bijection on the covered subset, and `lgd_ac_id IS NULL` iff `match_method = unmapped`). (5) Reader-before-writer cutover per ADR-0047 (schema-compatibility): consumers adopt the crosswalk join before any default flips; behavioural cutover rows carry a result-parity oracle. (6) URL grammar: the AC route is `/s/<state-slug>/ac/<eci_no>-<name-slug>` (e.g. `/s/tamil-nadu/ac/42-tekkali`); `eci_no` stays the leading parse key, the name slug is decorative + parse-tolerant; `lgd_ac_id` is INTERNAL-ONLY and never appears in a URL.

**Consequences.** One join surface replaces scattered name-based `ac_no <-> eci_no` translation; the legacy `apply_ac_no_rewrite_by_name` seam can be retired once coverage is effectively 100% `lgd_direct`. A national AC-level indicator can key on `lgd_ac_id` directly. Citizens keep the ballot number they recognize in the URL, now with a readable name suffix. The migration is far smaller than first framed: ~30 states are harvestable with no external sourcing; only U08/J&K needs data work. Provenance: every `lgd_ac_id` binding carries a `source_id` FK to `datasets/data/entities/source.csv` (per the migrating provenance contract).

### ADR-0051: historical-pc-crosswalk-and-delimitation-policy

**Context.** The elections experience needed the full 1999-2024 Lok Sabha general-election series at candidate grain, reusing the canonical person/candidacy model (ADR-0035) and the existing Model-C `pc-*` indicators + `IN-PC-<delim_year>-<state_code>-<pc_no>` entity scheme - no new indicator, no new id grammar. The blocker was constituency **identity**, not data. The TCPD `All_States_GE.csv` spine carries electors/turnout/valid-votes/sex/edu/profession for every year, but the same `(tcpd_state, constituency_no)` key resolves to different canonical seats across reorganisations: (a) 2008-delim splits - undivided AP (42 seats) in 2009/2014 splits into modern AP (S01, 25) + Telangana (S29, 17) in 2019/2024; `IN-PC-2008-S01-1` is Adilabad (TG) in 2009/14 but Araku (AP) in 2019/24 (unavoidable wrong-join; both share delim 2008 so `delim_year` alone cannot disambiguate). (b) J&K + Ladakh - State S09 (6 seats incl. Ladakh) in 2009/2014/2019 splits into U08 (5) + U09 (1) from 2024. (c) 2000 trifurcations - 1999 has 32 states; Chhattisgarh / Jharkhand / Uttarakhand did not yet exist (their seats were polled inside MP / Bihar / UP). (d) DNH + DD merge - the 2020 merge to U03 collides with the `pc_id` state-code regex `[SU][0-9]{2}` (`U03-OLD` is rejected). The 1976 vs 2008 delimitation boundary is the load-bearing axis: 1999/2004 ran on the 1976 delimitation; 2009 onward on the 2008 delimitation (boundaries frozen since, so the modern PC map paints those years fully).

**Decision.** Adopt an **override-only historical PC crosswalk** plus a **split-by-delimitation product policy** that **always loads the data**. (1) Override-only crosswalk: `datasets/data/entities/pc_historical_crosswalk.csv` (schema `pc-historical-crosswalk.schema.json`, 112 rows; G8 2026-06-08: moved from `datasets/reference/in/elections/` per plan-doc section 9) carries one row only for seats that need a reorganisation override; PK triple `(ge_year, tcpd_state, tcpd_constituency_no) -> (state_code, pc_no, match_method)`; `delim_year` is NOT a column - it is derived (`1999/2004 -> 1976`, `2009-2024 -> 2008`). (2) Pure resolver: `resolve_pc(ge_year, tcpd_state, constituency_no) -> (state_code, pc_no, delim_year, match_method)` - an override hit uses the row; otherwise automatic (state via `load_state_code_lookup`, `pc_no = constituency_no`, `match_method = "automatic"`). (3) Entity coding (Hans + Max authority): 2008-delim splits code to the MODERN SUCCESSOR (AP 2009/2014 -> S01 + S29; J&K 2009/2014/2019 -> U08 + U09); 1976-delim trifurcations (1999 CG/JH/UK seats) code AS-WAS inside MP/Bihar/UP (zero override rows, methodology-break note only); DNH + DD -> U03 pc 1 + 2 across all years (sidesteps the `U03-OLD` regex issue). (4) Always load the data: 2008-delim years (2009/2014/2019/2024) paint the choropleth fully (boundaries frozen since 1976 -> zero gray); 1976-delim years (1999/2004) render **table + timeseries only** with a "1976 delimitation - boundaries differ" label; the `delim_year` embedded in each `pc_id` is the single source of truth (no separate `boundary_changed` boolean); gray stripes are reserved for genuine no-coverage, which never occurs for 2009-2024. (5) TCPD spine, no portal fetch: the TCPD `All_States_GE.csv` (ECI-derived) is the single ingest source; the earlier Lok Dhaba portal-fetch handover was superseded once the spine was confirmed to carry all required fields; `All_States_GA.csv` stays a crosswalk reference, not the ingest source.

**Consequences.** Every GE year 1999-2024 lands 543 PCs at candidate grain, reusing the canonical person/candidacy model with no new id grammar. The crosswalk is auditable and minimal: only reorganised seats carry a row; the common case resolves automatically. The frontend grays historical (1976-delim) years from the `pc_id` prefix alone - no schema field, no per-year frontend branch. `dim_pcs` is generated from the ingest envelope itself, so 1976-delim `pc_id`s are self-consistent (no external boundary FK rejects them); the gray-stripe contract is covered by a unit test asserting the 1976 prefix. Provenance: each year carries a `source_id` FK so the postal-inclusive/exclusive and segment-sourced distinctions stay auditable.

## Rejected alternatives

This section preserves the rejected-alternatives receipts for the ADRs whose rationale is folded above, verbatim and append-only per [parent plan section 9](../../TODO/20260603-data-and-charting-platform-reset-plan.md). Each subsection is anchored as `#adr-NNNN-rejected-alternatives` for the redirect index.

### ADR-0015 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **Make `district_id` and `pc_id` unconditionally required.** Rejected: forces ECI cross-check before any reference file can land, blocking the entire frontend on the slowest data path. The user explicitly approved a two-commit rollout, which `status=provisional` operationalizes cleanly.
- **Embed Lok Sabha constituency by *name* rather than id.** Rejected: PC names are not unique across states (e.g. multiple "Bangalore"s historically), and they are renamed more often than ECI numbers change. An id-based reference is a foreign key; a name is a label.
- **Add `previous_name` / `succeeded_by` lineage fields now.** Rejected as scope creep. Useful but not requested; can land in a future minor bump.
- **Put `electors` and "change from previous" both on the constituency object.** Rejected: see "where does change-from-previous live" above. Conflating entity and event always rots.
- **Use a separate `hierarchy.json` file mapping AC->PC->district instead of inline fields.** Rejected: one more file to keep in sync, no real upside. The hierarchy IS the constituency definition; splitting it across files is bureaucracy.

### ADR-0023 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **B0 hotfix** (route guard that 404s gracefully when no event for state). Rejected because the underlying control is conceptually wrong; a graceful 404 still rewards a misleading interaction.
- **N=1 disabled dropdown** (then-current state of `ScopePicker.svelte`). Rejected for the same reason; the dropdown's existence implies "there is a global election to pick", which is false.
- **Synthesise a "national cycle" event from union of state cohorts.** Rejected as the Federal Falsehood - there is no national assembly election; each state's cycle is its own.

### ADR-0049 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **A. Big-bang corpus rewrite to lgd_ac_id everywhere (drop eci_no).** Rejected. Discards the ballot number citizens recognize and forces every results/indicator parquet to rewrite at once with no parity net. The crosswalk gives the same internal benefit incrementally.
- **B. Dual-key co-existence with a permanent adapter layer.** Rejected. Leaves both spines live forever; the translation cost this ADR removes would persist. The crosswalk IS the adapter, but with an explicit retirement path (Row D1).
- **C. Keep eci_no as the internal key; treat lgd as display.** Rejected. `eci_no` is per-state, not globally unique, and cannot key a national AC table. The LGD code already is globally unique and already present in 30/31 boundary shards.
- **D. lgd_ac_id in the URL.** Rejected by user. The opaque registry integer (e.g. 33042) is not citizen-legible; the ballot number + name slug is. `lgd_ac_id` stays internal-only.

### ADR-0051 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **A. Era-scoped identity + methodology break (new id grammar per delimitation).** Rejected. Minting a parallel id grammar for the 1976 era would fork every downstream consumer and break the single Model-C `pc-*` scheme. The `delim_year` prefix already encodes the era inside the existing grammar.
- **B. Defer the conflicted states (half-coverage).** Rejected by user. Shipping a partial historical series - some states present, reorganised ones blank - damages citizen trust more than a complete table with an honest "boundaries differ" label. The product policy is always-load.
- **C. Lok Dhaba portal fetch per state-year.** Superseded. The signed-off fallback assumed ECI published only PDFs and the portal was the only AC-split arm; once the TCPD `All_States_GE.csv` spine was confirmed to carry electors/turnout/sex/edu/profession, the portal fetch (502-down at the time) became unnecessary.
- **D. `boundary_changed` boolean column.** Rejected. Redundant with the `delim_year` already embedded in every `pc_id`. Deriving the gray-stripe behaviour from the id avoids a second source of truth.

## Operational note: PC binding for ECI raw exports (2024+ vintages)

When ingesting a new ECI raw export (e.g. Statement 33 "Constituency Wise Detailed Result" for a future LS cycle), the natural two-step PC lookup `(state_slug, pc_name) -> eci_no` then `(state_slug, eci_no) -> entity_id` SILENTLY DROPS PCs because `datasets/data/entities/electoral.csv` carries 22 PCs with `eci_no=0` (legitimate publisher gaps - AP Araku / Kadapa / Vizianagaram, Bihar x6, Kerala x13, etc.). The second-step map collides on the zero.

Use a **single-step lookup** instead:

```python
# (state_slug, normalised_pc_name) -> (entity_id, eci_no_from_spine_row)
pc_lookup: dict[tuple[str, str], tuple[str, int]] = {
    (row["state"], _normalise(row["name"])): (row["entity_id"], int(row["eci_no"]))
    for row in electoral_rows
    if row["entity_kind"] == "pc" and row["delim_year"] == "2008"
}
```

PC name is unique per `(state_slug, delim_year)` in the spine, so no collision. Emit `eci_no` verbatim into `candidacies.csv` (may be `0` if the spine doesn't know it) so the parity oracle can still bind. The same pattern applies to AC ingest (AC name is unique per `(state_slug, delim_year)`).

Reference implementation: `backend/yen_gov/canonical/reingest/parliament_2024_eci.py` (G16, PR #836). The function `_build_pc_lookup` is the canonical example; copy it shape-for-shape for the next ECI raw cycle.

## See also

- [data-model.md — Constituency hierarchy fields and status lifecycle](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle)
- [backend/sources-eci.md — ECI Statistical Reports as canonical past-election source](../architecture/backend/sources-eci.md#authority-hierarchy-for-past-elections)
- [`docs/reference/data-sources.md`](../reference/data-sources.md) — live catalogue of every external source
- [`datasets/schemas/constituency.schema.json`](../../datasets/schemas/constituency.schema.json) (v4.0)
- [`docs/concepts/data-provenance.md`](data-provenance.md) — how `sources[]` interacts with `status`
- CLAUDE.md §3 — identifier convention (ECI / LGD / Wikipedia slug)
