# Energy coverage matrix (ICED + CEA + RBI)

**Last Updated:** 2026-06-17
**Tracked by:** this doc is the receipt; the staging tool [tools/iced_stage.py](../../../tools/iced_stage.py) reads the same feed list and its run-log records each download.

This document answers: **for the energy indicator category, what ICED / CEA / RBI data yen-gov already HAS (with year coverage), what we do NOT yet have (the agreed download targets), and -- crucially -- which of it can actually be (re)ingested today versus needs an adapter built first.**

The hard fact that shapes everything below: the legacy energy lift adapters (`backend/yen_gov/canonical/adapters/energy/`) and the network fetchers were **deleted** in the 2026-06 rip (X1b / B4-pt2). So most energy data on disk is **read-only** -- the code that produced it is gone. Only four energy ingest paths survive. Re-collecting "all years" therefore splits into "trivial for 4 feeds" and "needs an adapter rebuild for the rest".

## See also

- [docs/architecture/data/canonical-store.md](canonical-store.md) - energy fact-table schema lock
- [docs/concepts/indicator-naming.md](../../concepts/indicator-naming.md) - indicator id conventions + the fuel-facet rule
- [docs/concepts/data-provenance.md](../../concepts/data-provenance.md) - source citation ledger (source_id)
- [docs/reference/topics/energy.md](../../reference/topics/energy.md) - citizen-facing energy topic
- [tools/iced_stage.py](../../../tools/iced_stage.py) - the ICED staging tool driven by this receipt

## 1. Ingest reality (what can be (re)ingested today)

| Feed | Live ingest CLI | Source | Status |
| --- | --- | --- | --- |
| CEA installed capacity (snapshot) | `ingest-cea-installed-capacity` | CEA monthly workbook (manual download) | LIVE |
| ICED installed capacity (geographical) | `ingest-iced-capacity` | ICED `/v1/capacity-metatable-data` | LIVE |
| ICED peak demand | `ingest-iced-peak-demand` | ICED `/energy/powerStatistics` | LIVE (but see note) |
| RBI fiscal cohort (6 indicators) | `ingest-rbi-hbs` | RBI Handbook | LIVE (fiscal, not energy-electricity) |

Note on peak demand: `/energy/powerStatistics` is **AES-encrypted** on the wire; the current `ingest-iced-peak-demand` does `json.loads` and expects an **already-decrypted** JSON. A real staged response must be decrypted first (the decrypt logic lives in `backend/yen_gov/sources/iced_common/crypto.py`). This is a known phase-2 fix.

**Everything else below is ORPHAN: data is on disk, but the ingest code was deleted.** Re-collecting more years for an orphan feed = rebuilding its adapter (a per-feed PR), not running an existing command.

## 2. What we HAVE (as of 2026-06-17)

Year coverage is the min..max `time` actually present in each datapoint CSV. Grain `n_ent` = distinct entities (37 ~ 36 states/UTs + India; 1 = national-only).

### CEA-sourced (2 files, faceted)

| Indicator | Years | Rows | Grain | Re-ingest |
| --- | --- | ---: | ---: | --- |
| installed-capacity-snapshot-mw | 2026 | 175 | 35 | LIVE (`ingest-cea-installed-capacity`) |
| installed-capacity-mw | 2026 | 5 | 1 | LIVE (CEA all-India total) |

### ICED-sourced (60 files)

| Group | Indicators | Years | Re-ingest |
| --- | --- | --- | --- |
| Installed capacity (geographical, faceted) | installed-capacity-geographical-mw | 2015-2025 | LIVE (`ingest-iced-capacity`) |
| Generation by fuel | electricity-generation-gwh + 5 fuel children | 2015-2025 | ORPHAN (D1 faceting pending) |
| Electricity sales | electricity-sales-mu | 2015-2024 | ORPHAN |
| Final energy consumption (national) | 17 sector x fuel children | 2005-2024 | ORPHAN |
| Primary energy supply (national) | 6 fuel children | 2005-2024 | ORPHAN |
| Thermal capacity retired (national) | coal, gas | 2005-2025 | ORPHAN (D2; parser survives) |
| Plant load factor | 8 fuel children | 2015-2025 | ORPHAN |
| Power purchase mix | 12 source children | 2015-2024 | ORPHAN |
| Rooftop solar capacity | rooftop-solar-capacity-mw | 2017-2025 | ORPHAN |
| RPO compliance | solar, non-solar, total | 2018-2020 | ORPHAN |
| Under-construction capacity | under-construction-capacity-gw | 2011-2031 | ORPHAN (parser survives) |
| Per-capita electricity consumption | per-capita-electricity-consumption-kwh | 2009-2023 | ORPHAN |

### RBI-Handbook-sourced (5 files) + joint (2)

| Indicator | Years | Re-ingest |
| --- | --- | --- |
| electricity-availability-mu | 2004-2024 | ORPHAN (no energy RBI adapter) |
| electricity-requirement-mu | 2004-2024 | ORPHAN |
| peak-electricity-supplied-mw | 2013-2024 | ORPHAN |
| per-capita-electricity-availability-kwh | 2004-2024 | ORPHAN |
| renewable-grid-capacity-mw | 2007-2024 | ORPHAN |
| installed-capacity-allocated-mw (ICED+RBI) | 2004-2025 | ORPHAN |
| peak-electricity-demand-mw (ICED+RBI) | 2013-2025 | LIVE (`ingest-iced-peak-demand`, snapshot only) |

Totals: 70 energy datapoint files -- ICED 60, RBI 5, CEA 2, ICED/RBI 2, derived 1. **4 LIVE, 66 ORPHAN.**

## 3. Faceting debt (have the data, wrong shape)

- **D1 - generation faceting:** `electricity-generation-gwh-{coal,gas,hydro,nuclear,renewable}` (5 per-fuel `geo/` files) should fold into ONE faceted `geo_by_fuel/electricity-generation-gwh.csv` (the same move PR #1097 did for capacity). This is a shape change on data we already hold -- no new download needed. Frontend reader migration + consolidation; a #1097-style PR.
- **D2 - retired-capacity disposition:** `india-thermal-capacity-retired-mw-{coal,gas}` (national-only, 2-fuel). Either fold to a faceted file or leave as-is; low priority (no current frontend consumer).

## 4. What we do NOT have -- the agreed download targets

Confirmed genuinely new (not in `variables.csv`; `check-overlap` < 0.70). Daily peak demand (last-30-days) was explicitly **dropped** by the data owner.

| # | Feed | ICED path | Encrypted | Adapter status |
| --- | --- | --- | --- | --- |
| 1 | Renewable potential - solar | `/energy/fuel-sources/solar/potential` | yes (AES) | none (new) |
| 1 | Renewable potential - wind | `/energy/fuel-sources/wind/potential` | yes | none (new) |
| 1 | Renewable potential - bio-energy | `/energy/fuel-sources/bio-energy/potential` | yes | none (new) |
| 2 | EV vs ICE registrations (Vahan) | `/analytics/ice-ev-vahan` | yes | none (new) |
| 3 | Captive power by industry | `/energy/electricity/captive-power/captive-power-industry` | yes | none (new) |
| 4 | Transmission substations | `/energy/electricity/transmission/substation-list` | yes | none (new) |
| 5 | Coal-plant AQI impact | `/analytics/aqi-impact-due-to-coal-plants-list` | yes | none (new, treat as model output) |

**All 7 are AES-encrypted and have NO parser/adapter yet.** Staging them (phase 1) produces raw blobs; landing them in the canonical store (phase 2) is a per-feed adapter PR: decrypt -> parse -> map entity (ECI -> LGD slug) -> faceted/single-value CSV -> `validate_csv`.

## 5. Two-phase collection model

1. **Phase 1 - stage (this receipt + [tools/iced_stage.py](../../../tools/iced_stage.py)).** Operator runs the tool; it downloads each feed to `.runtime/raw/iced/<file>.json` (raw; encrypted blobs saved as-is) and writes a tracking run-log. No backend involvement; the pipeline stays no-network. CEA stays a manual workbook download.
2. **Phase 2 - ingest (per-feed adapter).** For the 4 LIVE feeds, run the existing CLI. For the orphan re-ingests and the 7 new feeds, build the adapter (decrypt where needed, parse, canonical emit, validate). Each is its own PR gated by `check-overlap` + `pre-flight-ingest` (ADR-0046).

The staging tool's feed list is the machine-readable mirror of section 4 here; this doc is the human receipt.
