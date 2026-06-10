# Energy

**Last Updated**: 2026-06-11

Reference spine for energy indicators. Exact live indicator rows, periods, source ids, and entity coverage live in [data-inventory.md](../data-inventory.md), `datasets/data/variables.csv`, and `datasets/data/datapoints/geo/*.csv`.

## Scope

Energy covers electricity supply, electricity demand, distribution health, non-electricity energy, and renewable-capacity policy signals.

Main upstream families:

| Source | Use | Cadence |
| --- | --- | --- |
| ICED / NITI Aayog | Long-history state series for capacity, generation, demand, sales, and distribution metrics | Annual / portal refresh |
| Central Electricity Authority | Latest installed-capacity and power-system snapshots | Monthly |
| Power Finance Corporation | DISCOM financial and operational metrics | Annual |
| MNRE | Renewable capacity and scheme progress | Monthly / annual |

## Interpretation Rules

- Installed capacity is not generation. Use generation for electrons produced, sales for electricity consumed, and capacity for infrastructure stock.
- Geographical capacity and allocated capacity answer different questions. Geographical = plant physically located in the state. Allocated = power the state has access to through central/joint sector shares.
- DISCOM health needs at least AT&C losses plus ACS-ARR gap. T&D loss alone misses billing and collection failure.
- Per-capita electricity consumption is distorted by industrial load. Pair with economic structure when ranking states.
- CEA monthly snapshots should render as snapshots, not as a connected continuation of ICED annual series.

## Adjacent Topics

- [Fiscal](fiscal.md) owns state-budget subsidy and fiscal-stress framing.
- [Prices](prices.md) owns household fuel/electricity inflation.
- Environment indicators own emissions and air-quality consequences.
- Economy and demography provide denominators for per-capita and demand projections.

## Agent Lookup

| Need | Go to |
| --- | --- |
| Live indicator list and coverage | [data-inventory.md](../data-inventory.md) |
| Variable metadata | `datasets/data/variables.csv` |
| Observation rows | `datasets/data/datapoints/geo/*.csv` |
| Source citations | `datasets/data/entities/source.csv` |
| Frontend render options | [chart-index.md](../chart-index.md) |
