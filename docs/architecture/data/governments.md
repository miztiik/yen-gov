# Governments Data Family

**Last Updated**: 2026-05-25
**Owner**: data layer (Hans + Max own source hierarchy and constitutional semantics; Gregor owns contracts)

This doc is the current-shape home for the governments data family. It records how hand-authored office-tenure rows become canonical Parquet and where source authority lives. Rationale for the broader canonical store remains in [ADR-0030](../decisions/0030-canonical-store-duckdb-wasm.md); this doc records the operational contract.

## Scope

`datasets/taxonomy/office_holdings.json` is the authoring surface for political and constitutional office tenures. It compiles to:

| Output | Grain | Source |
| --- | --- | --- |
| `datasets/governments/dim_offices.parquet` | one office identity present in holdings | `taxonomy/entities.parquet` rows with `entity_type = 'office_bearer'` |
| `datasets/governments/governments_office_holdings.parquet` | one tenure or explicit regime/vacancy interval | `taxonomy/office_holdings.json` `holdings[]` |

The row grain is office occupancy, not election results. Chief Minister rows answer "who governed this state on this date?" President and Vice President rows answer "who held this constitutional office on this date?" They share the table because they share the same `(office_id, start_date, end_date, person_name, source_id)` spine.

## Authoring Contract

`office-holdings.schema.json` v1.1 keeps the G.1.c Chief Minister shape and adds official-source citation groups for non-CM offices.

Legacy CM rows may omit `citation_group_id`. The compiler derives one Wikipedia source row per CM office from `office_citations` so the existing 31-state timelines keep compiling.

New non-CM rows must set `citation_group_id`. The referenced top-level `citation_groups` entry carries the same fields as `sources.parquet` minus `source_id`: `producer`, `title`, `vintage`, `license`, `confidence_tier`, `is_issuing_authority`, `verification_method`, `url_main`, and optional `citation_full` / `notes`. The compiler derives `source_id` with `derive_source_id(producer, title, vintage)` and UPSERTs that row into `datasets/taxonomy/sources.parquet`.

`regime` describes governing condition and can be null. Chief Minister rows usually use `elected`; President's Rule rows use `presidents_rule` and have no person. President and Vice President tenures use `regime: null`, `selection_method: electoral_college`, and `tenure_status: substantive` because they are constitutional office tenures, not state-government regimes.

`selection_method` is the accession route: `legislature_confidence`, `electoral_college`, `appointed_by_president`, or `constitutional_succession`. `tenure_status` is the tenure kind: `substantive`, `acting`, or `additional_charge`.

## Parquet Columns

`governments_office_holdings.parquet` v1.1 columns are:

| Column | Meaning |
| --- | --- |
| `office_id` | FK to `taxonomy/entities.parquet.entity_id` for an `office_bearer` row |
| `start_date`, `end_date` | inclusive tenure bounds; `end_date` null for current holdings |
| `regime` | nullable governing condition (`elected`, `presidents_rule`, `governors_rule`, `interim`) |
| `selection_method` | nullable route to office |
| `tenure_status` | nullable substantive/acting/additional-charge flag |
| `person_slug`, `person_name` | derived slug plus verbatim publisher person name; both null for no-person regime rows |
| `party_eci_code`, `alliance` | nullable party/alliance context, used for CM-style political governments |
| `notes` | optional editorial context |
| `source_id` | FK to `taxonomy/sources.parquet`; never hand-authored |

`dim_offices.parquet` columns stay `office_id`, `entity_id`, `role`, `label`, `source_id`. `role` comes from `entities.entity_code` (`CM`, `PRES`, `VPRES`, etc.).

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

This refreshes `taxonomy/entities.parquet`, `governments/dim_offices.parquet`, `governments/governments_office_holdings.parquet`, `taxonomy/sources.parquet`, and the manifest.

## See also

- [canonical-store.md](canonical-store.md) - canonical Parquet store and family layout.
- [government-vs-election.md](../../concepts/government-vs-election.md) - concept boundary between governments, elections, and constitutional office tenures.
- [data-provenance.md](../../concepts/data-provenance.md) - source ledger semantics.
- [ADR-0032](../decisions/0032-sources-citation-ledger.md) - citation-ledger rationale.