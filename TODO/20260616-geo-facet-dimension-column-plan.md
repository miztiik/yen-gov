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

IN: the contract (`geo_by_fuel/*.csv`) + migrate all 4 installed-capacity families (~24 files -> 4)
+ net-transfers Accounts-only (L1) + doctrine docs + tests.

FAST-FOLLOW (own PR): rest of energy (generation, demand-supply, distribution, fuel-consumption,
capacity-pipeline), livestock species (`pashu-aadhaar` -> `geo_by_species`), any future faceted
measure - all reuse this contract.

## Scope-change ledger

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
| --- | --- | --- | --- |
| L1 | 2026-06-16 | net-transfers / `estimate_stage` will NOT be modelled as a facet. `estimate_stage` fails the user-ratified four-gate facet test (plan F2: different estimates, members do not sum to a whole) and plan F1 bans "BE/RE as a facet toggle". The data is degenerate (one year per stage: accounts=2023, re=2024, be=2025). Per F1, net-transfers collapses to an Accounts-only single series; BE/RE dropped. This HONORS existing ratified doctrine rather than the conversational "estimate_stage facet" framing. Overrode: nothing in code; reconciles the user's net-transfers example with their own F1/F2 freeze. | User, 2026-06-16 (clarifying question Q1 -> "Honor F1/F2") |

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
