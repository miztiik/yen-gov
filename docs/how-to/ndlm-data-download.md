# How to download data from Bharat Pashudhan (NDLM)

**Last Updated**: 2026-05-26 (Recipe 3 extended to 32 vintages; NADCP closure note added)

> Use this when you need to refresh livestock / vaccination / breeding / Pashu Aadhaar data for the `livestock` family ingest plan ([TODO/20260525-livestock-ndlm-ingest-plan.md](../../TODO/20260525-livestock-ndlm-ingest-plan.md)) or you want to inspect the raw NDLM API shape before opening a Phase 1 PR. Takes ~5 minutes to run; ~30 minutes if looping all 36 states x N years x 5 endpoints.

## What you get

- **Snapshots** at `.runtime/raw/ndlm/<vintage>/<endpoint>_state-<stateCd>.json`. **Gitignored, ephemeral** (CLAUDE.md §2; ADR-0041 non-negotiable #3).
- **Recon summary** at `.runtime/raw/ndlm/_recon/lgd-district-alignment.json` if you run the LGD recon. Tells you how many NDLM districts resolve to yen-gov `taxonomy/entities.parquet` rows.

This how-to **does NOT** mint meadow files at `datasets/livestock/_meadow/ndlm/<vintage>/...`. That's the Phase 1 PR's job. This recipe stops at the snapshot tier so you can inspect shape before committing meadow JSON.

## Pre-requisite — the API

NDLM exposes a public REST API at:

```text
https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/
```

No auth. Nginx fronts it. Accepts JSON POST. The portal at `https://bharatpashudhan.ndlm.co.in/keyStatistics` blocks DevTools via an aggressive modal; the API doesn't care -- you call it directly from Python.

The 6 endpoints we use:

| Endpoint | Method | Body | Returns |
| --- | :-: | --- | --- |
| `getState` | GET | -- | 36 states with `stateCode` (= LGD MoHA code) + `stateName` |
| `getOwnerRegLandHoldingByDistrict` | POST | `{stateCd, year, isYearFinancial}` | per-district owner-registration counts, faceted by landholding x gender |
| `getAnimalRegistrationDistrictWise` | POST | `{stateCd, year, isYearFinancial}` | per-district Pashu Aadhaar counts, faceted by species x gender |
| `getNADCPVaccinationDistrictWise` | POST | `{stateCd, year, isYearFinancial, diseaseCd, roundNumber, isRoundWise}` | per-district vaccination counts |
| `getNaipIVDistrict` | POST | `{stateCd, year, isYearFinancial}` | per-district AI / pregnancy / calf-born counts under NAIP IV |
| `getNaipHeaderCount` | GET `?year=YYYY` | -- | cumulative national totals (returns the SAME numbers across years 2022-2025; do not trust the year param) |

Verified 2026-05-25: NDLM `stateCode` IS the LGD MoHA code (AP=28, TN=33). NDLM district `code` (576=Karur, 577=Krishnagiri) IS the LGD district code -- recon confirmed 588/588 NDLM districts resolve to yen-gov entities; zero FK-drops.

## Recipe 1 -- one-state proof (~30 seconds)

Pulls Tamil Nadu (stateCd=33) for both CY 2024 and FY 2024-25 across 4 endpoints. Useful when you want to inspect column names before scoping a Phase 1 PR.

```powershell
python tools\ndlm_download_proof.py
```

Output: 8 JSON files (~92 KB total) under `.runtime/raw/ndlm/2024/` and `.runtime/raw/ndlm/2024-25/`, plus a summary at `.runtime/raw/ndlm/_recon/tn-proof-summary.json`.

To use a different state, edit `STATE_CD = 33` at the top of [tools/ndlm_download_proof.py](../../tools/ndlm_download_proof.py).

## Recipe 2 -- LGD-district alignment recon (~90 seconds)

Walks all 36 states x NAIP IV 2024 CY, compares NDLM district codes to yen-gov `entities.json`. Run this BEFORE scoping any Phase 1 PR that asserts NDLM district codes are LGD codes (Gregor's #1 architectural risk).

```powershell
python tools\ndlm_recon_lgd_districts.py
```

Output: full report at `.runtime/raw/ndlm/_recon/lgd-district-alignment.json`. The key numbers:

- **NDLM-only count** (would FK-drop in writer) -- **MUST be 0**. If non-zero, the writer's `entity_id` FK gate will silently drop rows; introduce a `dim_ndlm_districts.parquet` lookup before lifting.
- **Intersection count** -- joinable rows.
- **yen-gov-only count** -- districts NDLM doesn't report on this endpoint. Often non-zero (NAIP IV is a select-district programme; Kerala / Punjab / many UTs have zero NAIP IV coverage). Not a defect.

## Recipe 3 -- full bulk corpus (all states x both vintages x 4 endpoints)

Walks the full NDLM corpus and writes one snapshot per (state, vintage, endpoint). Idempotent (skips files that exist on disk; pass `--force` to overwrite). Polite (0.2 s default sleep between calls + extra 0.4 s every 5th call). Resilient (3-attempt exponential backoff on 5xx / connection errors).

```powershell
# Default: 36 states x 2 vintages x 4 endpoints = 288 calls, ~3-5 min
python tools\ndlm_download.py

# Subset for debugging:
python tools\ndlm_download.py --states 33,29
python tools\ndlm_download.py --endpoints pashu_aadhaar,nadcp
python tools\ndlm_download.py --years 2024-25

# Re-download even if files exist:
python tools\ndlm_download.py --force

# Slower (if NDLM throttles):
python tools\ndlm_download.py --sleep 0.5
```

Output:

1. Snapshots at `.runtime/raw/ndlm/<vintage>/<endpoint-stem>_state-<stateCd>.json` (gitignored)
2. Summary at `.runtime/raw/ndlm/_summary.json` -- one row per (state, vintage, endpoint) with district counts and byte sizes. Meadow-lift PRs (PR 3+) cite this summary.

Endpoint coverage: 4 of the 5 NDLM source rows in `datasets/taxonomy/sources.parquet` (Owner Registration, Pashu Aadhaar, NADCP, NAIP IV). The 5th (Breeding ABIP/RGM, `src-fb1694ab6a11`) is dashboard-level not per-state-endpoint; covered by a separate discovery PR. See [tools/ndlm_download.py](../../tools/ndlm_download.py) for full design notes.

**Vintage matrix as of 2026-05-26**: `VINTAGE_BODIES` enumerates 32 vintages -- CY 2010..2025 (16 entries) + FY 2010-11..2025-26 (16 entries). A full sweep is ~4608 POST calls (4 endpoints x 36 states x 32 vintages); ~25 min runtime; ~18 MB raw corpus; ~99.7 % success rate (~11 publisher-side HTTP 500s on Owner Reg FY 2025-26 for a handful of states). Re-run regenerates `.runtime/raw/ndlm/_summary.json` for the next meadow-lift PR.

**Be polite to NDLM** -- do not parallelise above 4 concurrent requests; do not lower `--sleep` below 0.1 s.

## Calendar Year vs Financial Year

The body flag `isYearFinancial: true | false` toggles CY vs FY. **Both produce different numbers.** Verified 2026-05-25:

- CY 2024 TN NAIP IV `totalAIs` = **1,396,453**
- FY 2024-25 TN NAIP IV `totalAIs` = **1,529,434**

Per the livestock ingest plan §4: yen-gov **carries both**. The canonical writer's PK `(entity_id, year, period_label, indicator_id)` discriminates: CY -> `period_label="2024"`; FY -> `period_label="2024-25"`. The frontend renderer's URL toggle `?period_basis=cy` picks which to show; `cadence: "annual_fy"` is the citizen-default (Indian govt convention).

## NADCP + Breeding -- upstream-gap CLOSED 2026-05-26

`getNADCPVaccinationDistrictWise` returns `{totalVaccinations: 0, totalOutput: {}}` for **every** combination of `(stateCd, year, isYearFinancial, diseaseCd in {1, 2})` across the full publisher vintage range. Verified 2026-05-26 by the 32-vintage bulk sweep: 1152/1152 NADCP cells empty across 32 vintages x 36 states (130 bytes each). 20+ alternate endpoint name variants (e.g. `getNADCPStateWise`, `getFMDVaccinationDistrictWise`) all HTTP 404. No Swagger / OpenAPI surface to enumerate hidden endpoints.

Breeding (ABIP / RGM): 14-endpoint probe matrix all HTTP 404. NDLM exposes no per-state Breeding API endpoint.

**Verdict**: both indicator families are CATALOGUE-DECLARED + UNFILLED on `/t/agriculture` until DAHD publishes the data. Full evidence + re-evaluation cadence + 4 open follow-ups (DAHD PDF scrape, DevTools capture, RTI, DAHD outreach) at [../research/livestock-ndlm-source-availability.md](../research/livestock-ndlm-source-availability.md).

## See also

- [TODO/20260525-livestock-ndlm-ingest-plan.md](../../TODO/20260525-livestock-ndlm-ingest-plan.md) -- umbrella ingest plan
- [TODO/20260525-pashu-aadhaar-ingest-plan.md](../../TODO/20260525-pashu-aadhaar-ingest-plan.md) -- Pashu Aadhaar honest-renderer call
- [TODO/20260525-topojson-frontend-perf-plan.md](../../TODO/20260525-topojson-frontend-perf-plan.md) -- TopoJSON map adoption (NDLM precedent)
- [docs/concepts/meadow-tier.md](../concepts/meadow-tier.md) -- 5-tier OWID model
- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) -- canonical store contract
