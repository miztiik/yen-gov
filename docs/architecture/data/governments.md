# Governments Data Family

**Last Updated**: 2026-06-07
**Owner**: data layer (Hans + Max own source hierarchy and constitutional semantics; Gregor owns contracts)

This doc is the current-shape home for the governments data family. It records how hand-authored office-tenure rows become canonical long-format CSV. Rationale for the broader canonical store remains in the canonical-store doc; this doc records the operational contract.

> **B3-followup (2026-06-07)**: the legacy `datasets/governments/{dim_offices,governments_office_holdings}.parquet` pair RETIRED per umbrella plan O1 (no strangler-fig). CSV under `datasets/data/` is the only citizen-visible artifact for this family; the previous Parquet was always an intermediate that the term-shape reingest had to walk anyway.

## Scope

`datasets/taxonomy/office_holdings.json` is the authoring surface for political and constitutional office tenures. It compiles to:

| Output | Grain | Source |
| --- | --- | --- |
| `datasets/data/entities/office.csv` | one office identity present in holdings | `taxonomy/entities.parquet` rows with `entity_type = 'office_bearer'` |
| `datasets/data/entities/holder.csv` | one person identity (deduped across holdings) | distinct `person_slug` extracted from `office_holdings.json` |
| `datasets/data/datapoints/office_holdings.csv` | one tenure or explicit regime/vacancy interval | `taxonomy/office_holdings.json` `holdings[]` |

The row grain is office occupancy, not election results. Chief Minister rows answer "who governed this state on this date?" President and Vice President rows answer "who held this constitutional office on this date?" They share the table because they share the same `(office_id, start_date, end_date, person_name, source_id)` spine.

## Authoring Contract

`office-holdings.schema.json` v1.1 keeps the G.1.c Chief Minister shape and adds official-source citation groups for non-CM offices.

Legacy CM rows may omit `citation_group_id`. The compiler derives one Wikipedia source row per CM office from `office_citations` so the existing 31-state timelines keep compiling.

New non-CM rows must set `citation_group_id`. The referenced top-level `citation_groups` entry carries the same fields as `datasets/data/entities/source.csv` minus `source_id`: `producer`, `title`, `vintage`, `license`, `confidence_tier`, `is_issuing_authority`, `verification_method`, `url_main`, and optional `citation_full` / `notes`. The compiler derives `source_id` with `derive_source_id(producer, title, vintage)`; the row itself lives in `data/entities/source.csv` (seeded once via B2a/source_csv, not per emit-taxonomy run).

`regime` describes governing condition and can be null. Chief Minister rows usually use `elected`; President's Rule rows use `presidents_rule` and have no person. President and Vice President tenures use `regime: null`, `selection_method: electoral_college`, and `tenure_status: substantive` because they are constitutional office tenures, not state-government regimes.

`selection_method` is the accession route: `legislature_confidence`, `electoral_college`, `appointed_by_president`, or `constitutional_succession`. `tenure_status` is the tenure kind: `substantive`, `acting`, or `additional_charge`.

## CSV Columns (post-B3-followup, 2026-06-07)

`datasets/data/datapoints/office_holdings.csv` columns:

| Column | Meaning |
| --- | --- |
| `office_id` | FK to `data/entities/office.csv` |
| `term_start`, `term_end` | inclusive ISO-date tenure bounds; `term_end` null for current holdings |
| `holder_id` | FK to `data/entities/holder.csv`; null for no-person regime rows (President's Rule, vacancy windows) |
| `source_id` | FK to `data/entities/source.csv`; never hand-authored |

`data/entities/office.csv` columns: `office_id`, `name`, `office_kind`, `jurisdiction_entity_id`, `portfolio`. `office_kind` comes from `entities.entity_code` lower-cased (`cm`, `pres`, `vpres`, etc.). `jurisdiction_entity_id` re-keys ECI st_code to the LGD slug used by `data/entities/geo.csv`.

`data/entities/holder.csv` columns: `holder_id`, `person_name`, `party_id`. `party_id` resolves via `data/entities/parties.csv.eci_codes`.

## Source Hierarchy

Official government sources are canonical when they exist. The first v1.1 slice uses the President's Secretariat and Vice President Office, Government of India as `gold` issuing-authority sources. TCPD Governor / President / Vice President CSVs are seed and QA checklists only; Wikipedia/Wikidata are validation or fallback aids, not citizen-facing provenance for rows with official pages.

If a future row truly needs non-official fallback provenance, it needs explicit user approval and a new citation group that makes the fallback status visible through `confidence_tier`, `is_issuing_authority`, and `notes`.

## Current Coverage

As of 2026-05-25, the authored national constitutional-office slice is deliberately narrow:

| Office | Rows |
| --- | --- |
| `IN-PRES` | Shri Ram Nath Kovind (2017-07-25 to 2022-07-25); Smt. Droupadi Murmu (2022-07-25 to open) |
| `IN-VPRES` | Shri M. Venkaiah Naidu (2017-08-11 to 2022-08-10); Shri Jagdeep Dhankhar (2022-08-11 to 2025-07-21); Shri C. P. Radhakrishnan (2025-09-12 to open) |

Acting President intervals are deferred until official source rows with exact dates are captured. The 2025 Vice President gap is left as a vacancy/gap, not guessed into an acting row.

Governors are deferred. The TCPD governors CSV has 825 rows and needs official Raj Bhavan/state validation in batches before import. Do not bulk-import unvalidated governor rows.

## Regeneration

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path backend).Path
python -m yen_gov emit-taxonomy --root .
```

This refreshes `taxonomy/entities.parquet`, the 3 CSV term-shape files under `datasets/data/`, and the manifest. The seed still drives parquet creation in a per-run tempdir for the in-memory pipeline; no parquet survives under `datasets/governments/`.

## See also

- [canonical-store.md](canonical-store.md) - canonical Parquet store and family layout.
- [government-vs-election.md](../../concepts/government-vs-election.md) - concept boundary between governments, elections, and constitutional office tenures.
- [data-provenance.md](../../concepts/data-provenance.md) - source ledger semantics.
- [ADR-0032](../../reference/decision-index.md) - citation-ledger rationale.