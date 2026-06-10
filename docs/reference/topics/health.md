# Health

**Last Updated**: 2026-06-11

Reference spine for health indicators. Exact live indicator rows, periods, source ids, and entity coverage live in [data-inventory.md](../data-inventory.md), `datasets/data/variables.csv`, and `datasets/data/datapoints/geo/*.csv`.

## Current Stance

The thin legacy health shard family was retired before the CSV canonical store settled. Do not resurrect those JSON shards. A future health ingest should land directly on the canonical CSV seam with source citations in `datasets/data/entities/source.csv`.

## Candidate Source Families

| Source | Use | Notes |
| --- | --- | --- |
| SRS / ORGI | Birth rate, death rate, IMR, TFR, life expectancy | Watch for publication resumption and multi-year-window semantics. |
| NFHS | Health outcomes, fertility, nutrition, household amenities | Survey wave and sampling frame must be visible. |
| HMIS / NHM | Facility and programme service delivery | Requires careful denominator discipline. |
| PM-JAY / Ayushman Bharat | Insurance / claim coverage | Administrative coverage is not population health outcome. |

## Interpretation Rules

- Crude birth/death rates are age-structure-sensitive; do not rank as governance scores without framing.
- IMR and MMR are lower-is-better outcome rates, but publication windows can overlap.
- Survey indicators need wave labels and methodology-break handling.
- Administrative health counts need denominators before comparison across states.

## Agent Lookup

| Need | Go to |
| --- | --- |
| Live indicator list and coverage | [data-inventory.md](../data-inventory.md) |
| Variable metadata | `datasets/data/variables.csv` |
| Observation rows | `datasets/data/datapoints/geo/*.csv` |
| Source citations | `datasets/data/entities/source.csv` |
| New ingest gates | [../schemas.md](../schemas.md) and [../../architecture/backend/validator.md](../../architecture/backend/validator.md) |
