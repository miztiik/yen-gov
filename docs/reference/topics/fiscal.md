# Fiscal

**Last Updated**: 2026-06-11

Reference spine for fiscal indicators. Exact live indicator rows, periods, source ids, and entity coverage live in [data-inventory.md](../data-inventory.md), `datasets/data/variables.csv`, and `datasets/data/datapoints/geo/*.csv`.

## Scope

Fiscal covers Union and State public-finance flows and stocks: own-tax revenue, devolution, grants, revenue expenditure, pension expenditure, deficits, liabilities, and Centre-to-state transfers.

Main upstream families:

| Source | Use | Cadence |
| --- | --- | --- |
| RBI Handbook of Statistics on Indian Economy | Union and all-states-combined fiscal series | Annual |
| RBI Handbook of Statistics on Indian States | Per-state revenue, expenditure, pension, and debt series | Annual |
| Union Budget documents | A/RE/BE source tables behind Centre aggregates | Annual |
| Finance Commission reports | Award-period formula and grant framing | Five-year award cycle |

## Interpretation Rules

- Centre, all-states-combined, and general-government views are distinct. Do not compare them as the same fiscal unit.
- Devolution, grants, cess/surcharge, and loans are legally different transfer streams.
- Nominal INR-crore flows should not be ranked across states without size normalisation.
- Most recent fiscal years are usually BE/RE, not audited actuals. Render provisional tails differently when row metadata carries revision tier.
- Debt-to-GSDP ratios inherit GSDP denominator revisions; small year-on-year changes are often noise.
- Pension stress is better read as a share of revenue receipts or own-tax revenue than as absolute INR crore.

## Adjacent Topics

- Economy owns GSDP/NSDP denominators.
- Prices owns inflation deflators.
- Energy owns DISCOM losses and ACS-ARR gaps, which can become quasi-fiscal liabilities.

## Agent Lookup

| Need | Go to |
| --- | --- |
| Live indicator list and coverage | [data-inventory.md](../data-inventory.md) |
| Variable metadata | `datasets/data/variables.csv` |
| Observation rows | `datasets/data/datapoints/geo/*.csv` |
| Source citations | `datasets/data/entities/source.csv` |
| Provenance rules | [../data-sources.md](../data-sources.md) |
