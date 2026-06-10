# Prices

**Last Updated**: 2026-06-11

Reference spine for price and inflation indicators. Exact live indicator rows, periods, source ids, and entity coverage live in [data-inventory.md](../data-inventory.md), `datasets/data/variables.csv`, and `datasets/data/datapoints/geo/*.csv`.

## Scope

Prices covers consumer and producer price measures: state CPI inflation facets, national CPI / WPI concepts when present, and deflator context for nominal fiscal and economy series.

Main upstream families:

| Source | Use | Cadence |
| --- | --- | --- |
| NSO / MoSPI | CPI-Combined, CPI-Rural, CPI-Urban, state sub-baskets | Monthly |
| Labour Bureau | CPI-IW, wage-indexation context | Monthly |
| Office of Economic Adviser | WPI, producer-stage price context | Monthly |
| RBI Handbook | Annual averages used by yen-gov when an annual fiscal-year series is needed | Annual |

## Interpretation Rules

- CPI-Combined is the RBI monetary-policy inflation anchor. WPI is producer-stage and must not be called citizen retail inflation.
- CPI-IW, CPI-Combined, and WPI use different baskets and bases; do not splice them as one series.
- Index levels and year-on-year rates are different shapes. Compute rates only when methodology-break rules permit it.
- Base-year rebases require visible breaks. Growth across a rebase is not an inflation rate.
- State CPI sub-baskets are methodologically comparable enough for snapshots, but state consumption baskets differ; avoid over-reading small rank changes.
- Urban housing CPI has no rural counterpart in the upstream methodology.

## Adjacent Topics

- Fiscal uses price series to deflate nominal INR flows.
- Economy uses deflator concepts for real growth framing.
- Energy and agriculture explain many fuel and food price shocks.

## Agent Lookup

| Need | Go to |
| --- | --- |
| Live indicator list and coverage | [data-inventory.md](../data-inventory.md) |
| Variable metadata | `datasets/data/variables.csv` |
| Observation rows | `datasets/data/datapoints/geo/*.csv` |
| Source citations | `datasets/data/entities/source.csv` |
| Chart feasibility | [chart-index.md](../chart-index.md) |
