# MoSPI National Accounts Source

**Last Updated**: 2026-05-15

> **See also**:
>
> - [Long-coverage indicators](../../concepts/long-coverage-indicators.md)
> - [Dataset shapes](../../concepts/dataset-shapes.md)
> - [Data provenance](../../concepts/data-provenance.md)
> - [Backend pipeline](pipeline.md)
> - [Indicator schema](../../../datasets/schemas/indicator.schema.json)

This document is the canonical home for the MoSPI National Accounts Statistics (NAS) annual + quarterly ingest currently implemented by [`tools/ingest_merged_aq.py`](../../../tools/ingest_merged_aq.py). The scratch recommendation note in `notes/` is no longer authoritative.

## Source Surface

The input used for the first ingest is `datasets/ephemeral_datasets/Merged_Annually_Quarterly.csv`, a consolidated NAS CSV mirrored through data.gov.in from MoSPI / National Statistical Office press-note vintages. The emitted artifacts cite `https://www.data.gov.in/` with the MoSPI/NSO authority metadata and GoI Open Data license.

The source rows include:

- Annual and quarterly frequency.
- Current-price and constant-price columns.
- Two base years: `2011-12` and sparse `2022-23`.
- Multiple revision tiers from First Advance through Additional Revision.
- Headline aggregates, industry GVA, institutional-sector rows, growth rates, and subindustry rows.

## Emitted Artifacts

| Artifact | Grain | Coverage | Notes |
| --- | --- | --- | --- |
| [`national_macro_aggregates_constant_2011_12_inr_crore.json`](../../../datasets/indicators/in/economy/national_macro_aggregates_constant_2011_12_inr_crore.json) | fiscal year, facet = aggregate name | FY12-FY26 | GDP, GVA, NDP, GNI, GNDI, GFCF, saving, PFCE/GFCE, external trade, taxes/subsidies, and related aggregates. |
| [`national_gva_by_industry_constant_2011_12_inr_crore.json`](../../../datasets/indicators/in/economy/national_gva_by_industry_constant_2011_12_inr_crore.json) | fiscal year, facet = industry | FY12-FY26 | Annual GVA by published NIC-1 style industry tier. |
| [`national_gva_by_industry_quarterly_constant_2011_12_inr_crore.json`](../../../datasets/indicators/in/economy/national_gva_by_industry_quarterly_constant_2011_12_inr_crore.json) | quarter, facet = industry | 2011-Q1 through 2025-Q2 | Quarter times are stored as quarter-start `YYYY-MM`: Q1 = April, Q2 = July, Q3 = October, Q4 = January of the following calendar year. |

## Contract Decisions

- **Constant-price 2011-12 is canonical for this slice.** It is the real-growth lens used by MoSPI press notes and aligns with international macro trackers. The sparse 2022-23 rebased series is deferred until MoSPI publishes enough history or an official bridge/link factor.
- **Current-price NAS rows are not emitted here.** Nominal-vs-real confusion is more costly than a missing nominal companion in the citizen front door. Nominal national GDP from ICED remains a separate artifact with its own source doc.
- **Growth-rate rows are dropped.** MoSPI's fixed-base level series lets us derive growth from the emitted constant-price levels; emitting both would create two sources of truth.
- **Subindustry rows are dropped.** The citizen-facing story uses headline aggregates and the published broad industry tier. Subindustry detail can return as a deliberate deep-dive artifact.
- **Latest-final revision wins per key.** For each `(indicator, time, facet)` key, the ingest picks the most final revision tier and stores it in the optional row-level `vintage` field added in indicator schema v1.3.
- **Quarterly time is schema-compatible `YYYY-MM`.** The schema's `time_grain: quarter` still stores a month; the month represents the start of the fiscal quarter.

## Operator Recipe

Run from the repository root after placing the consolidated CSV at `datasets/ephemeral_datasets/Merged_Annually_Quarterly.csv`:

```powershell
python tools/ingest_merged_aq.py
```

Then run the dataset validator and the frontend/backend contract suites appropriate to indicator-schema or data-artifact changes. If the source CSV changes shape, inspect the headers first; do not extend the parser by guessing column positions.

## Rationale

A single ingest script emits the three artifact families together because they share one source file, one revision-ranking policy, one base-year policy, and one provenance claim. Splitting the script per artifact would multiply the highest-risk decisions without creating independent source boundaries.

Keeping the nominal/current-price NAS rows out of this first slice is intentional. The citizen question this slice answers is "what changed in real terms?" The nominal question is useful, but it needs a separate product treatment and inflation caveat rather than being mixed into the first renderer path.
