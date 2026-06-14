# `datasets/ephemeral/` ECI Form-10 Detailed Results — README

**Last updated**: 2026-06-14

Operator-dropped snapshots of the ECI-published **Form 10 (Detailed Results)** xlsx workbooks. These are the per-state per-event consolidated candidate-level statistical reports the Election Commission of India publishes after results announcement.

Used by [backend/yen_gov/canonical/adapters/eci_form10_ae.py](../../backend/yen_gov/canonical/adapters/eci_form10_ae.py) to populate the canonical per-event Assembly election store at `datasets/elections/assembly/state=<slug>/election=<year>/{candidacies,summary}.csv`.

## Provenance

- **Producer**: Election Commission of India (results.eci.gov.in)
- **Upstream URL pattern**: ECI publishes these as per-event PDFs/xlsx downloadable from the post-result statistical reports page on `results.eci.gov.in`.
- **License**: Government of India publication; treat as `unknown-public` per [docs/concepts/data-provenance.md](../../docs/concepts/data-provenance.md) until ECI publishes an explicit licence.
- **Citation**: source.csv row per (state, year) — title format `"Form 10 Detailed Results - <State> Legislative Assembly Election <Year>"`.

## On-disk file format

The xlsx workbook has ONE sheet, 14 or 15 columns depending on vintage:

| Col | 2022-23 vintage (14-col) | 2024+ vintage (15-col) |
| --- | --- | --- |
| 1 | STATE/UT NAME | STATE/UT NAME |
| 2 | AC NO. | AC NO. |
| 3 | AC NAME | AC NAME |
| 4 | CANDIDATE NAME (with leading serial) | CANDIDATE NAME (with leading serial) |
| 5 | SEX | GENDER |
| 6 | AGE | AGE |
| 7 | CATEGORY | CATEGORY |
| 8 | PARTY | PARTY |
| 9 | SYMBOL | SYMBOL |
| 10 | GENERAL (EVM votes) | GENERAL |
| 11 | POSTAL | POSTAL |
| 12 | TOTAL | TOTAL |
| 13 | % VOTES POLLED | OVER VALID VOTES + NOTA |
| 14 | TOTAL ELECTORS | OVER TOTAL ELECTORS |
| 15 | — | TOTAL ELECTORS |

NOTA rows have `PARTY="NOTA"` and blank GENDER/AGE/CATEGORY. TURN OUT marker rows have `STATE/UT NAME="TURN OUT"` and carry per-AC totals.

## Cohort coverage as of 2026-06-14

### Form 10 Detailed Results — ingested via `python -m yen_gov ingest-eci-ae-form10`

| Year | State | File | event_id ingested |
| --- | --- | --- | --- |
| 2022 | Gujarat | `2022_gujarat_10-Detailed Results.xlsx` | (not ingested — TCPD has this, see backend/yen_gov/sources/) |
| 2022 | Himachal Pradesh | `2022_state_himachal_pradesh_10-Detailed Results.xlsx` | (not ingested — TCPD has this) |
| 2022 | Punjab | `2022_punjab_10.Detailed Results.xlsx` | (not ingested — TCPD has this) |
| 2022 | Uttar Pradesh | `2022_uttar_pradesh_10-Detailed Results.xlsx` | (not ingested — TCPD has this) |
| 2023 | Chhattisgarh | `2023_Chattisgargh_Detailed_Results.xlsx` | `assembly-2023` ✓ |
| 2023 | Karnataka | `2023_state_karnataka_10-Detailed Results.xlsx` | (not ingested — TCPD has this) |
| 2023 | Madhya Pradesh | `2023_MadhyaPrashesh_Detailed_Results.xlsx` | `assembly-2023` ✓ |
| 2023 | Mizoram | `2023_mizoram_Detailed_Results.xlsx` | `assembly-2023` ✓ |
| 2023 | Rajasthan | `2023_rajasthan_Detailed_Results.xlsx` | (not ingested — already on disk via indiavotes adapter) |
| 2023 | Telangana | `2023_telengana_Detailed_Results.xlsx` | `assembly-2023` ✓ |
| 2024 | Andhra Pradesh | `2024_AP_10-Detailed-Results.xlsx` | `assembly-2024` ✓ |
| 2024 | Arunachal Pradesh | `2024_Arunachal_10-Detailed-Results.xlsx` | `assembly-2024` ✓ |
| 2024 | Haryana | `2024_haryana_10-Detailed-Results.xlsx` | `assembly-2024` ✓ |
| 2024 | Jammu & Kashmir | `2024_jk_10-Detailed-Results.xlsx` | `assembly-2024` ✓ |
| 2024 | Jharkhand | `2024_jharkhand_10-Detailed_Results_1744892172.xlsx` | `assembly-2024` ✓ |
| 2024 | Maharashtra | `2024_MH_10-Detailed_Results_1744893339.xlsx` | (already ingested via thecont1 in PR #1002) |
| 2024 | Odisha | `2024_odisha_10-Detailed-Results.xlsx` | `assembly-2024` ✓ |
| 2024 | Sikkim | `2024_sikkim_10-Detailed-Results.xlsx` | `assembly-2024` ✓ |
| 2025 | Bihar | `2025_BIHAR_10-Detailed_Results_1763549630.xlsx` | `assembly-2025` ✓ |
| 2025 | NCT of Delhi | `2025_DL_10-Detailed_Results_1744913508.xlsx` | `assembly-2025` ✓ |
| 2026 | Assam | `2026_assam_10-Detailed_Results_1778163955.xlsx` | (pending — catalogue entry needed first) |
| 2026 | Kerala | `2026_kerala_10-Detailed_Results_1778164525.xlsx` | (pending — catalogue entry needed first) |
| 2026 | Puducherry | `2026_pondy_10-Detailed_Results_1778164807.xlsx` | (pending — catalogue entry needed first) |
| 2026 | Tamil Nadu | `2026_tn_10-Detailed_Results_1778165153.xlsx` | (pending — catalogue entry needed first) |
| 2026 | West Bengal | `2026_wb_10-Detailed_Results_1779879116.xlsx` | (pending — catalogue entry needed first) |

### Other ECI snapshots (different ingest paths)

| File | Purpose |
| --- | --- |
| `2019_india_loksabha_33. Constituency Wise Detailed Result.csv` | National Parliament 2019 PC-level — separate `ingest-eci-ls` adapter |
| `2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv` | National Parliament 2024 PC-level — separate `ingest-eci-ls` adapter |
| `2014_lok_sabha_affidavits.csv` | TCPD-style affidavits — separate adapter (not yet wired) |
| `2019_eci_seizures.csv` | Pre-election seizures — separate adapter (not yet wired) |

## Re-snapshot policy

Per the operator-snapshot policy of ADR-0042, snapshots ARE committed (small file sizes; audit-trail is the value). When ECI publishes a corrected Form-10 (rare), replace in-place; the `source.csv` row's `vintage` gets a new value triggering a new deterministic `source_id` via `derive_source_id(producer, title, vintage)`.

The folder is gitignored selectively (see top-level `.gitignore`) — only `pre-regen-parquet-snapshot/`, `indiavotes-snapshots/`, and `wikidata-party-leadership-*.json` are excluded. Form-10 xlsx files are committed.
