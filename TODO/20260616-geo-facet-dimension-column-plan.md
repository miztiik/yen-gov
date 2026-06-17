# Geo facet / dimension column - de-fragmentation plan

**Created**: 2026-06-16
**Status**: IN PROGRESS
**Level**: 5 (core data model). Authority: Hans + Max (data shape) / Gregor (contract) / Fowler (craft) per CLAUDE.md section 0a.
**Branch**: `feat/geo-facet-dimension-column`

## Problem

The geo datapoint file-class (`datasets/data/datapoints/geo/<id>.csv`) is fixed at 4 columns
(`entity_id, time, value, source_id`). Indicators with a real analytical facet are forced to
fan out into N separate files - one `indicator_id` + `concept_id` + CSV per facet member:

- `installed-capacity-*`: 4 families x (1 total + 5 fuel children) = ~24 files (`fuel_type` axis)
- `net-transfers-from-centre-inr-crore-{accounts,re,be}`: 3 files (`estimate_stage` - see ledger L1)
- `pashu-aadhaar-count-{species}`: 10 files (`species` axis - fast-follow)

This is a workaround, not a design: the RBI + ICED adapters already KNOW the facet at emit
time but split because the writer rejects undeclared columns.

## Locked design (Hans + Max + Gregor + Fowler debate, 2026-06-16)

- ADOPT the dimension-column model (plan section 21.6 option a): one long CSV per measure with a
  facet column joining the PK. OWID "dimensions" model.
- TOPOLOGY (Gregor, contract authority): a per-axis homogeneous SIBLING file-class
  `datasets/data/datapoints/geo_by_<axis>/*.csv`, declaring the facet column + closed enum in
  `columns.json`, composite PK `(entity_id, time, <facet>)`. Generalises the proven
  `electoral_geo` `sex` precedent. Reader stays `columns.json`-only (NO `variables.csv` dispatch).
  Reject ARCH-A (variables.csv dimensions dispatch) - it forks the header contract across two
  files and adds a second drift site.
- VOCABULARY (Hans + Max): facet enum includes an explicit `all` aggregate member where a
  published total exists (installed-capacity); `all` is flagged non-summable via a grapher render
  hint, never computed-on-read. `estimate_stage` is NOT a facet (fails four-gate F2 - see L1).
- SCHEMA: MINOR bump `columns.json` 2.6 -> 2.7 (additive; existing `geo/*.csv` unchanged).
- ADAPTER (Fowler): adapters MUST emit the facet column (delete the per-facet split); regen via
  M1 (re-run adapter), not a transform band-aid (Holy Law #5).
- FRONTEND: FacetPicker UI unchanged (reads `rows[].facet`); the facet-multiplexed reader switches
  from UNION-ALL-N-files to ONE faceted-file read + facet-column projection.
- COMMIT TOPOLOGY (Fowler, Tidy-First): deferred deletion - old files survive until the final
  structural commit so main is green at every rest state.
- VALIDATOR: tighten PK sort from non-decreasing to strict-ascending so composite-PK duplicates
  fail at validate time (the bug masked while `(entity_id, time)` alone was unique).

## Scope (user-ratified 2026-06-16)

IN: the contract (`geo_by_fuel/*.csv`) + migrate the 3 fuel-faceted installed-capacity families
(geographical-mw, snapshot-mw, mw; 16 files -> 3 - see L2) + net-transfers Accounts-only (L1) +
catalogue collapse (15 child indicators/concepts) + frontend faceted read + doctrine docs + tests.
allocated-mw STAYS single-value (no fuel children on disk -> fails the four-gate test).

FAST-FOLLOW (own PR): rest of energy (generation, demand-supply, distribution, fuel-consumption,
capacity-pipeline), livestock species (`pashu-aadhaar` -> `geo_by_species`), any future faceted
measure - all reuse this contract.

ENERGY ADAPTER RECONCILIATION (own PR - discovered during C6/C7): four source adapters still emit
the now-collapsed per-fuel `variable_id`s and are DISCONNECTED from the on-disk canonical store
(their output names / grains never matched the committed files; none is the live producer):
`sources/cea_installed_capacity` + `sources/iced_power` + `sources/power_plants` (all emit
`installed-capacity-mw-<fuel>`), and `sources/rbi_xlsx` (`_FACET_SUFFIX` emits net-transfers
`-revised-estimate`/`-budget-estimate`, never the on-disk `-re`/`-be`). They are tmp_path-tested
(never read the committed corpus), so deleting the on-disk files is safe, but they should be
reconciled to emit the faceted `geo_by_fuel` shape (and Accounts-only for net-transfers per F1) so
a future re-ingest does not re-fragment. Touching them entails updating their `*_csv_repoint`
tests; out of scope here.

**RESOLVED 2026-06-17 (PR follow-on `fix/energy-adapter-facet-reconcile`).** The literal
"reconcile the adapters to emit the faceted shape" turned out to be IMPOSSIBLE as a mechanical
follow-on: the C4 sub-fuel collapse mapping the adapters would need
(`backend/yen_gov/canonical/adapters/energy/_shared.py:SUB_FUEL_TO_CANONICAL`) was DELETED in X1b,
and the adapters emit raw upstream sub-fuels (`small-hydro`, `natural-gas`, `pumped-storage-hydro`,
`diesel`, `thermal`, `total`) that do not fit the closed `[coal, gas, hydro, nuclear, renewable,
all]` enum - mapping them (e.g. small-hydro -> renewable per MNRE) is a Hans+Max data-shape call,
not a mechanical reconcile. Verified ALL FOUR adapters are ORPHAN (no `@app.command` invokes them;
zero external importers except `rbi_xlsx.normalise_state_label`, reused by `datagovin_ogd`).
Delivery: a SOURCE-AGNOSTIC contract fence `tier_b_no_refragmented_fuel_facet_csv`
(`backend/yen_gov/validate.py`), the CSV-era sibling of the established `tier_b_no_new_sub_fuel_shards`
precedent. It rejects any re-fragmented per-fuel / parent-single-file installed-capacity CSV and any
net-transfers estimate-stage variant under `datasets/data/datapoints/geo/`, pointing them at
`geo_by_fuel/`. This makes "a re-ingest cannot re-fragment" computationally enforced regardless of
producer - the orphan adapters are thereby neutralised (their output cannot pass Tier-B). DEFERRED:
full deletion of the ~2000 LOC orphan parsers (cea / iced_power / power_plants + the rbi_xlsx
net-transfers emit) is a separate, irreversible "retire orphan source adapters" decision - the
fence already removes the re-fragmentation risk, so the parsers can stay fenced as a dormant
re-acquisition path until the project decides those sources are abandoned.

## Scope-change ledger

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
| --- | --- | --- | --- |
| L1 | 2026-06-16 | net-transfers / `estimate_stage` will NOT be modelled as a facet. `estimate_stage` fails the user-ratified four-gate facet test (plan F2: different estimates, members do not sum to a whole) and plan F1 bans "BE/RE as a facet toggle". The data is degenerate (one year per stage: accounts=2023, re=2024, be=2025). Per F1, net-transfers collapses to an Accounts-only single series; BE/RE dropped. This HONORS existing ratified doctrine rather than the conversational "estimate_stage facet" framing. Overrode: nothing in code; reconciles the user's net-transfers example with their own F1/F2 freeze. | User, 2026-06-16 (clarifying question Q1 -> "Honor F1/F2") |
| L2 | 2026-06-16 | The "all 4 installed-capacity families ~24->4" framing was inaccurate (my error, surfaced before building per CLAUDE.md section 10). On-disk reality: only 3 families are fuel-faceted (geographical-mw: states + parent total; snapshot-mw: 35 states x 1 year; mw: 1-row all-India), 16 files total. allocated-mw has NO fuel children (single-value, 770 rows) -> correctly STAYS unfaceted (the four-gate test excludes it). Net: 16 files -> 3 faceted + allocated unchanged. The 3 energy SOURCE adapters' taxonomy mismatch (see ENERGY ADAPTER RECONCILIATION) is a separate pre-existing concern. | User, 2026-06-16 (clarifying question Q2 -> "All 3 faceted families") |

## Answers folded into doctrine (user questions 2026-06-16)

- No topic / grain prefix on ids (ADR-0044 + ADR-0022). "energy" is the topic column, not an
  `india-energy-` prefix. Reaffirm in `indicator-naming.md`.
- Split-grain = `entity_kind` on rows + `entity_kinds` on the catalogue (ADR-0044), never separate ids.
- Facets = LONG file + facet column, never wide columns. Gate every facet with the four-gate test (F2).
- pashu-aadhaar -> one long `pashu-aadhaar-count.csv` with a `species` facet (fast-follow).
- The contract is GENERAL (any closed-facet axis); migration is incremental + four-gate-gated.

## Commit sequence (deferred deletion; main green at each rest state)

- C1 structural: `columns.json` `geo_by_fuel/*.csv` file-class + bump 2.6 -> 2.7 + `geo/*.csv` note
  rewrite; validator strict-ascending PK; drift + contract tests. (green-dark - nothing emits yet)
- C2 docs: `indicator-naming.md` facet-storage section; `csv-column-contract.md` section 3.3; plan
  section 21.6 seam ruling; `owid-alignment.md` no-flatten divergence; `fiscal-estimate-stage.md`.
- C3 behavioural: `installed_capacity.py` emits faceted (`fuel_type` incl `all`) + adapter test +
  regen the 4 faceted CSVs (alongside the old per-fuel files).
- C4 behavioural: `variables.csv` + `concepts.csv` collapse to 4 measures + migration-ledger rows.
- C5 behavioural: frontend descriptor (facet-multiplexed -> single faceted `csv_path`) +
  `indicator-from-canonical` single faceted read + FE unit test.
- C6 behavioural: net-transfers -> Accounts-only (`rbi_xlsx` delete `_FACET_SUFFIX`) + catalogue + descriptor.
- C7 structural: delete orphan per-fuel + net-transfers CSVs + child catalogue rows + `facet_values` +
  grep-confirm zero dangling.

## Gates

backend `pytest -q`; frontend `vitest` + `build`; CLAUDE.md section 13 browser smoke on `/t/energy`
+ a state page; drift test green.
