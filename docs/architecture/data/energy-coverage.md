# Energy coverage matrix (ICED + CEA + RBI)

**Last Updated:** 2026-06-19 (RBI/ICED publisher-split: the two dual-source blends split per-publisher; upsert_source_scoped retired; section 8 rewritten)
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
| ICED peak demand | `ingest-iced-peak-demand` | ICED `/energy/powerStatistics` | LIVE (decrypts staged ciphertext) |
| RBI fiscal cohort (6 indicators) | `ingest-rbi-hbs` | RBI Handbook | LIVE (fiscal, not energy-electricity) |

Note on CEA: `ingest-cea-installed-capacity` now **UPSERTs** each snapshot into the year axis (PK `(entity_id, time, fuel_type)`; new wins, absent rows preserved) so re-ingesting a month never drops prior years/entities -- a value the publisher later removes is kept (PR #1115).

Note on peak demand: `/energy/powerStatistics` is AES-encrypted on the wire. `ingest-iced-peak-demand` now decrypts transparently via `load_iced_response` (the staged ciphertext is decrypted before parsing; the cipher stays solely in `backend/yen_gov/sources/iced_common/crypto.py`). DONE (PR #1116) -- the full-refresh path works on encrypted staged files.

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
| Generation by fuel | electricity-generation-gwh (faceted: all + 5 fuels) | 2015-2025 | FACETED (D1 done, PR #1117) |
| Electricity sales | electricity-sales-mu | 2015-2024 | ORPHAN |
| Final energy consumption (national) | 17 sector x fuel children | 2005-2024 | ORPHAN |
| Primary energy supply (national) | 6 fuel children | 2005-2024 | ORPHAN |
| Thermal capacity retired (national) | india-thermal-capacity-retired-mw (faceted: coal, gas) | 2005-2025 | FACETED (D2 done, PR #1118) |
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
| installed-capacity-allocated-iced-mw (ICED) | 2015-2025 | LIVE (`ingest-iced-state-wise`); ICED half of the publisher-split allocated measure. See section 8. |
| installed-capacity-statewise-total-rbi-mw (RBI) | 2004-2014 | ORPHAN (RBI Handbook Table 140; no live emitter). See section 8. |
| peak-electricity-demand-iced-mw (ICED) | 2025 | LIVE (`ingest-iced-peak-demand`, FY2025 snapshot). See section 8. |
| peak-electricity-demand-rbi-mw (RBI) | 2013-2024 | ORPHAN (RBI Handbook Table 142; no live emitter). See section 8. |

Totals: 72 energy datapoint files at the survey (ICED 62, RBI 7, CEA 2, derived 1) after the 2026-06-19 RBI/ICED publisher-split turned the 2 dual-source blends into 4 single-source files. **4 LIVE re-ingest CLIs, 68 ORPHAN.** After D1/D2 the per-fuel generation (6) + retired (2) `geo/` files folded into 2 faceted `geo_by_fuel/` files; the LIVE/ORPHAN split (a re-ingest-CLI count, not a file count) is unchanged -- faceting changes shape, not the ability to add new years.

## 3. Faceting debt -- CLEARED

- **D1 - generation faceting: DONE (PR #1117).** The 5 per-fuel `geo/` files + the parent total folded into ONE faceted `geo_by_fuel/electricity-generation-gwh.csv` (fuel_type dimension column; parent total = the `all` member). Frontend repointed; the 6 `geo/` inputs deleted; migration-ledger recorded. Mirrors the capacity migration (PR #1097).
- **D2 - retired-capacity faceting: DONE (PR #1118).** The 2 per-fuel files folded into `geo_by_fuel/india-thermal-capacity-retired-mw.csv` (national-only; no `all` member -- no published total). Backend-only (no frontend consumer).

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

## 6. Future hydration roadmap (the 66 orphans)

"Hydrate all 70 for more years" is **not** a single batch job. It splits cleanly:

**Tier A -- LIVE now (4 feeds): one command each.** CEA capacity, ICED capacity, ICED peak, RBI fiscal. Stage the latest source, run the CLI. CEA UPSERTs (accumulates); ICED capacity/peak are full-refresh (one response = all years). No code needed.

**Tier B -- orphan re-ingest (the ~62 ICED + RBI energy series): one adapter rebuild per family.** The lift adapters were deleted in X1b/B4, so the on-disk CSV is read-only. To add new years for a family you rebuild its adapter once, then it becomes Tier-A LIVE. The building blocks already exist -- the parsers in `backend/yen_gov/sources/iced_*`, the decrypt (`load_iced_response`), the ECI->LGD-slug bridge, the fuel-collapse helper, the faceted/single-value emit + `validate_csv`. Each rebuild is a small PR:

| Family | Source feed | Shape | Effort |
| --- | --- | --- | --- |
| Generation (more years) | `/energy/powerStatistics` (gen) or gen-metatable | faceted (already migrated) | re-emit via the D1 spec |
| Plant load factor (8 fuels) | `/v1/plf-metatable-data` | faceted by fuel | M (no sub-fuel collapse -- PLF is a percentage) |
| Power purchase mix (12 sources) | `/statelevel-power-purchase-quantum-and-cost` | faceted by source | M |
| Distribution efficiency / RPO | `/energy/electricity/distribution/{operationalPerformanceStates,rpo}` | single-value | S each |
| Primary / final energy supply | `/analytics/state-wise-deep-dive` (TPES/FEC) | faceted national | M |
| Coal / oil consumption | `/energy/fuel-sources/{coal,oil}/...` | faceted | M |
| Retired / pipeline | `/v1/{retired-capacity-plants,plantPipelineInfo}` | faceted / single | parser survives -> S |
| RBI electricity (availability, requirement, supplied, per-capita) | RBI Handbook tables 138-142 | single-value | wire into `ingest-rbi-hbs` -- S each |

Sequencing rule: before rebuilding any family, run `check-overlap` + `pre-flight-ingest` (ADR-0046). Faceted families reuse the `FuelFamilySpec` registry in `fuel_facet_consolidation.py`.

## 7. Full-refresh procedure (ready now)

A "full refresh" of the LIVE feeds, end to end:

1. **Stage** (operator, networked): `python tools/iced_stage.py --dry-run` then `python tools/iced_stage.py` -- downloads each ICED feed (raw; encrypted blobs saved as-is) to `.runtime/raw/iced/` with a tracking run-log. CEA workbook is a manual download to `.runtime/raw/cea/`.
2. **Ingest** (no network): run the Tier-A CLIs --
   - `python -m yen_gov ingest-cea-installed-capacity --xlsx <workbook>` (UPSERTs into the year axis)
   - `python -m yen_gov ingest-iced-capacity .runtime/raw/iced/capacity_metatable_data.json` (full history in one file)
   - `python -m yen_gov ingest-iced-peak-demand .runtime/raw/iced/power_statistics.json` (decrypts the AES envelope automatically)
3. **Validate + receipt**: `python -m yen_gov validate --root .`; the staging run-log (`.runtime/raw/iced/_stage-log.json`) records what was fetched, when, sizes, and sha; this doc records the coverage state. Together they are the refresh receipt.

For the orphan families (Tier B) and the 7 new feeds (section 4), staging works today but a full refresh waits on the per-family adapter rebuild.

## 8. The RBI/ICED publisher-split (2026-06-19)

Two canonical `geo/<id>.csv` files were historically **dual-source blends**: their
rows came from two methodology-incompatible publishers, split cleanly by period.
The reference case was `installed-capacity-allocated-mw` (installed capacity
including allocated shares); the second was `peak-electricity-demand-mw`.

On 2026-06-19 the user ratified (plan TODO/20260618-iced-7-feeds-and-rbi-iced-split-plan.md
SC-1) a **publisher-split**: each blend was split into two single-source files,
one per publisher. Showing two methodology-incompatible publishers as one trend
line is dishonest; the split makes each series a distinct indicator that shares
the measure's concept but renders as its own series, never spliced.

| Old blended file | ICED-only file | RBI-only file |
| --- | --- | --- |
| `installed-capacity-allocated-mw` (770 rows) | `installed-capacity-allocated-iced-mw` (396 rows, `src-bb1d7bec8b34`, NITI "State-wise Deep Dive API", FY2015-2025) | `installed-capacity-statewise-total-rbi-mw` (374 rows, `src-3d1d55f8a94b`, RBI Handbook Table 140, FY2004-2014) |
| `peak-electricity-demand-mw` (430 rows) | `peak-electricity-demand-iced-mw` (34 rows, `src-bb1d7bec8b34`, NITI ICED, FY2025 snapshot) | `peak-electricity-demand-rbi-mw` (396 rows, `src-99ac1fee8a50`, RBI Handbook Table 142, FY2013-2024) |

**One concept, two indicators.** Each pair shares one `concept_id`
(`capacity-allocated-to-state-2` for allocated, `peak-demand` for peak); the
publisher-incompatibility justification is recorded in each variable row's
`derivation` field. This is the deliberate, signed-off exception to the
"never mint a new id for a new publisher" anti-pattern (CLAUDE.md section 10):
permitted only when the publishers are methodology-incompatible and the split is
a named plan-doc decision.

**Each file is now single-source**, so the re-ingest writers use plain `write_csv`:

- `installed-capacity-allocated-iced-mw` is produced by `ingest-iced-state-wise`;
- `peak-electricity-demand-iced-mw` is produced by `ingest-iced-peak-demand`;
- the two RBI-only files are orphan historical lifts (RBI Handbook Tables 140 +
  142) with no live emitter.

The previous `upsert_source_scoped` merge-preserving write helper -- which let one
file carry two publishers by re-emitting one source in place -- is **retired**
(deleted from [`csv_writer.py`](../../../backend/yen_gov/canonical/csv_writer.py)):
with the blends split, no canonical file carries more than one `source_id`, so the
source-scoped merge has no caller. Any future multi-source single-value need is a
methodology-incompatible publisher-split (two ids, one concept), not a blended
file.
