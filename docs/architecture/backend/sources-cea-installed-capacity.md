# CEA Installed Capacity (`sources/cea_installed_capacity`)

**Module**: [`backend/yen_gov/sources/cea_installed_capacity/`](../../../backend/yen_gov/sources/cea_installed_capacity/)
**Topic**: `energy`
**See also**: [`overview.md`](overview.md), [Holy Law #4](../../../CLAUDE.md), [Data Provenance](../../concepts/data-provenance.md), [Long-coverage indicators ledger](../../concepts/long-coverage-indicators.md)

## What this adapter does

Reads the Central Electricity Authority's monthly **All-India Installed Capacity (Utilities)** workbook — the canonical statutory snapshot of nameplate generation capacity for grid-connected utilities, broken down by state/UT, ownership tier (State / Private / Central), and fuel mode (Coal / Lignite / Gas / Diesel / Nuclear / Hydro / RES-MNRE).

One workbook → 7 indicator artifacts, one per fuel category we ship. Each artifact carries one row per state/UT for the snapshot period.

## Source workbook

| File | Cached path | Edition stamp | Coverage | Status |
| --- | --- | --- | --- | --- |
| All-India Installed Capacity (Utilities) | `.runtime/raw/cea/installed_capacity_2026_03.xlsx` | March 2026 (As on 31.03.2026) | Snapshot only — single month | Shipped |

Upstream cadence is monthly. The adapter detects the snapshot date from the `(As on DD.MM.YYYY)` cell in the IC sheet's header band and emits artifacts with `time_grain="month"`, `period="YYYY-MM"`. Each ingest run replaces the existing artifacts wholesale (single-snapshot semantics — no historical accretion in this version).

### Operator recipe (resumability)

If the cached workbook is missing or stale:

1. Visit the [CEA Installed Capacity Report listing page](https://cea.nic.in/installed-capacity-report/?lang=en).
2. Download the latest **Installed Capacity Report** Excel file (look for the link reading something like *"As on 31.03.2026"*).
3. Save as `.runtime/raw/cea/installed_capacity_<YYYY>_<MM>.xlsx` (relative to repo root) — the leaf name pattern MUST match `installed_capacity_YYYY_MM.xlsx` so the cache lookup picks the lex-largest file as latest.
4. Re-run `python -m yen_gov ingest-energy-cea --root .`

Alternative: set `$CEA_INSTALLED_CAPACITY_PATH` to an absolute path to bypass the cache lookup entirely.

#### SSL-fallback gotcha

`cea.nic.in`'s certificate chain is not in `certifi`'s default trust store on Windows-without-corporate-CA setups. Both `urllib` and `httpx.get(..., verify=certifi.where())` fail with `CERTIFICATE_VERIFY_FAILED`. PowerShell's `Invoke-WebRequest` uses the Windows trust store, which does include the chain. One-liner:

```powershell
Invoke-WebRequest `
  -Uri "https://cea.nic.in/wp-content/uploads/installed/2026/03/Website-1.xlsx" `
  -OutFile ".runtime/raw/cea/installed_capacity_2026_03.xlsx"
```

(URL changes per edition — use the exact link off the listing page. The `installed_capacity_<YYYY>_<MM>.xlsx` save name is what matters.)

On Linux / macOS where `httpx` succeeds, a future fetcher integration can pull this directly. For now operator-cached.

## Indicator catalog

All entries below: `entity_kind=state`, `time_grain=month`, `value_kind=raw`, `unit="MW"`, `direction=neutral`, `coverage.admin_level=state`, `attribution_geography=where_produced`, `comparability=comparable_with_normalisation`, `implementing_authority=joint`. Each row's value is the workbook's per-state Sub-Total (= State + Private + Central tiers) for the named fuel column. 35 rows per artifact (all CEA-reported state/UT entities).

| Indicator id | Workbook column (col index 0-based) | Notes |
| --- | --- | --- |
| `energy/installed_capacity_total_mw` | Grand Total (col 12) | Headline. Sum of thermal + nuclear + renewable. |
| `energy/installed_capacity_thermal_mw` | Thermal Total (col 7) | Coal + lignite + gas + diesel. |
| `energy/installed_capacity_coal_mw` | Coal (col 3) | Largest single fuel mode in most states. |
| `energy/installed_capacity_gas_mw` | Gas (col 5) | Includes natural gas and CCGT. |
| `energy/installed_capacity_nuclear_mw` | Nuclear (col 8) | Per-state attribution only — central-unallocated nuclear (~1,230 MW) is dropped. |
| `energy/installed_capacity_hydro_mw` | Hydro (col 9) | Large hydro only — small hydro under 25 MW counts in RES. |
| `energy/installed_capacity_renewable_mw` | Renewable Total (col 11) | Hydro + RES-MNRE (solar / wind / biomass / small-hydro). |

Lignite and diesel are **not** shipped as separate indicators (small / declining shares — their values fold into `thermal`).

## Carve-outs and caveats

- **Sub-Total tier, not State tier.** The "Sub-Total" row aggregates State + Private + Central ownership for that state — this is the figure citizens experience as the state's installed capacity. Reading only the "State" tier would underreport private and central plants located in that state.
- **Central PSUs dropped.** Rows labelled `NLC`, `DVC`, and `Central - Unallocated` look syntactically like state rows (col B carries the name) but represent central public-sector entities whose capacity is not state-attributable. They are explicitly skipped — see `_NON_STATE_LABELS` in `parsers.py`.
- **Region totals dropped.** Rows like "Total (Northern Region)" are roll-ups, not states. The state-name normaliser returns `None` for these. Context-reset logic between blocks ensures their `Sub-Total` rows do not leak capacity onto the previous state.
- **J&K + Ladakh bundled to U08.** CEA combines Jammu & Kashmir and Ladakh into one row. We attribute the entire bundled capacity to U08 (Jammu & Kashmir UT) since splitting would be fabrication. Documented in each artifact's `notes`.
- **Nuclear national sum < workbook total.** Per-state nuclear sums to ~7,550 MW vs the workbook's ~8,780 MW national total. The 1,230 MW gap is central-unallocated nuclear capacity that we deliberately drop (not state-attributable).
- **Nameplate, not generation.** MW is installed capacity, not energy generated. A 1,000 MW plant running at 50% PLF generates the same as a 500 MW plant at 100% PLF. For energy-generated indicators see future CEA Generation reports (not yet wired).
- **Snapshot only, no history (yet).** This adapter ships one period per ingest run. Historical multi-decade coverage requires scraping the monthly archive (~360+ workbooks for 30 years) and is deferred — see the long-coverage ledger.

## Schema

Each artifact validates against [`indicator.schema.json`](../../../datasets/schemas/indicator.schema.json) v1.1. Shape:

```json
{
  "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
  "$schema_version": "1.1",
  "sources": [
    { "url": "https://cea.nic.in/installed-capacity-report/?lang=en",
      "fetched_at": "<ingest timestamp>" }
  ],
  "license": "GoI-Open",
  "coverage": {
    "admin_level": "state",
    "spatial": "35 states/UTs (all CEA-reported per-state entities)",
    "temporal": "<snapshot period, e.g. 2026-03>"
  },
  "indicator": {
    "id": "energy/installed_capacity_<fuel>_mw",
    "title": "...",
    "description": "...",
    "icon": "zap | flame | atom | droplet | sun",
    "entity_kind": "state",
    "time_grain": "month",
    "value_kind": "raw",
    "unit": "MW",
    "direction": "neutral",
    "attribution_geography": "where_produced",
    "comparability": "comparable_with_normalisation",
    "implementing_authority": "joint",
    "methodology_vintage": "<snapshot period>",
    "rows": [ { "entity_id": "S22", "time": "2026-03", "value": 70945.38 }, ... ]
  }
}
```

## How to add the next monthly snapshot

1. Operator-cache the next month's workbook per the recipe above.
2. Re-run `python -m yen_gov ingest-energy-cea --root .` — artifacts overwrite with the newer snapshot's period.
3. `python -m yen_gov validate --root .` to confirm clean.
4. Commit. (No code edit required for cadence — only when CEA changes the workbook layout.)

## How to add a new fuel column

If CEA adds (e.g.) a separate "Battery Storage" column or you want to ship the currently-folded `lignite` / `diesel`:

1. Append a `FuelColumn(indicator_id, column_index, title)` entry to `SHIPPED_COLUMNS` in `parsers.py`.
2. Add a matching `IndicatorMeta` entry (title / description / icon / fuel-specific notes) to `INDICATOR_META` in `ingest.py`.
3. Add the indicator to the `energy` topic in `datasets/reference/in/topic-catalogue.json`.
4. Re-run ingest + validate. Add a parser test asserting the new column emits expected values.

## Tests

[`backend/tests/test_sources_cea_installed_capacity.py`](../../../backend/tests/test_sources_cea_installed_capacity.py) — pure-parser tests using in-memory `openpyxl.Workbook` instances (no real CEA bytes). Covers: snapshot date detection, state-name normalisation (incl. J&K-Ladakh bundle, A&N variants), NLC/DVC/Central-Unallocated drop, region-total drop and context reset, Sub-Total tier selection, null-token coercion, and column-set integrity.
