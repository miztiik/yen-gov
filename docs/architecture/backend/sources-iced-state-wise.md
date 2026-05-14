# Source: NITI Aayog ICED state-wise deep-dive

**Module**: `backend/yen_gov/sources/iced_state_wise/`
**CLI**: `python -m yen_gov ingest-iced-state-wise [--refresh] [--fy 2024-25 ...]`
**Cache**: `.runtime/raw/iced/stateWiseDeepDive_<FY>.json` (raw encrypted bodies)
**Outputs**: 13 indicators across `datasets/indicators/in/{energy,economy,demography}/`

## What this ships

| Topic | Indicator id | Coverage |
|---|---|---|
| energy | `energy/state_installed_capacity_geographical_mw` | 11 FY × 36 entities + IN |
| energy | `energy/state_installed_capacity_with_alloc_mw` | 11 FY |
| energy | `energy/state_rooftop_solar_capacity_mw` | 9 FY (FY18 onward) |
| energy | `energy/state_electricity_generation_mu` | 11 FY |
| energy | `energy/state_electricity_peak_demand_mw` | 9 FY |
| energy | `energy/state_electricity_sales_mu` | 10 FY |
| energy | `energy/state_atc_losses_pct` | 10 FY |
| energy | `energy/state_acs_arr_gap_inr_per_kwh` | 10 FY |
| economy | `economy/state_gdp_constant_2011_12_inr_lakh_crore` | 10 FY |
| economy | `economy/state_gdp_current_inr_lakh_crore` | 10 FY |
| economy | `economy/state_sectoral_gva_constant_2011_12_inr_lakh_crore` | 10 FY |
| economy | `economy/state_sectoral_gva_current_inr_lakh_crore` | 10 FY |
| demography | `demography/state_population_lakhs` | 11 FY |

Total: ~4,600 long-form rows from 11 fiscal years (FY16–FY26) × up to 37 entities.

## Upstream

ICED (India Climate & Energy Dashboard), published by NITI Aayog at
<https://iced.niti.gov.in/analytics/state-wise-deep-dive>. The dashboard
is an Angular SPA backed by a private REST API at
`https://icedapi.niti.gov.in/`.

The single endpoint we call:

```
GET https://icedapi.niti.gov.in/analytics/stateWiseDeepDive
    ?year=YYYY-YY&state=Comma,Separated,Names
```

One call per fiscal year suffices: it returns *all* indicators for *all*
requested entities in a single ~22 KB response. We therefore make exactly
**11 GETs** to ingest the entire publicly available history.

## The encryption

The endpoint does not return JSON. It returns a JSON-encoded **string**
that is a base64 CryptoJS OpenSSL-format AES-256-CBC ciphertext:

```
"U2FsdGVkX1+<...>"        # outer JSON quotes + Salted__ prefix + base64
```

Decryption is standard `CryptoJS.AES.decrypt(ciphertext, passphrase)`:

1. base64-decode the body
2. read `Salted__` magic + 8-byte salt at offsets `[0:8]` and `[8:16]`
3. derive 32-byte key + 16-byte IV via OpenSSL `EVP_BytesToKey` with MD5
4. AES-256-CBC decrypt with PKCS7 unpadding

The passphrase **`AHten@VP0W3R`** is hardcoded in the Angular bundle
(`main.cb0bb1d44638969b.js`, module 92340 — the env-config object that
also exposes `apiUrl`). Treat it as a recon constant: if it ever rotates,
re-extract via the deobfuscated bundle and update
`backend/yen_gov/sources/iced_state_wise/parsers.py::PASSPHRASE`.

This is **client-side obfuscation, not security**. The dashboard ships
the key to every browser tab; we are decrypting data that the dashboard
itself decrypts and renders for any visitor. The license is GoI-Open.

## The state-name → entity-id mapping

ICED's `states` list contains 36 entities — 28 states + 8 UTs — plus
"All India" as the aggregate. All entity names match the canonical
`datasets/reference/in/states.json` *name* field exactly, with one
exception: ICED writes `"Delhi"` whereas ECI's reference data uses
`"NCT of Delhi"` (entity id `U05`). The mapping table lives in
`parsers.py::ENTITY_MAP`.

Unknown sentinel labels (`"Multiple States"`, `"Location TBD"`, etc.)
that sometimes appear in other ICED endpoints are silently skipped —
they cannot be joined to any geometry.

## Unit annotation caveat (GDP / GVA)

The API's `ecoDemoUnitsArr` field labels GDP and GVA as `"Crores"`, but
the on-page header reads `"Lakh Crore"`. Spot checks against MoSPI's
published all-India FY24 nominal GDP (≈₹296 Lakh Crore = ≈₹296 trillion)
match the API's value of ~187 (constant prices) / ~296 (current prices),
confirming the values are in **Lakh Crore**, not Crore. The shipped
artifact units (`"INR (lakh crore)"`) reflect this. The API's own
annotation is documented as wrong in the indicator `notes`.

## Why no climate indicators (yet)

The decrypted response includes `climateSeq` keys (NO₂, SO₂, PM10, PM2.5)
but the values for the entities sampled (FY24-25 across multiple states)
were uniformly `"N.A."`. Until a future API update populates them with
real data, shipping zero-row artifacts would lie about coverage. To
re-evaluate: drop a year's cache file, run the orchestrator with
`refresh=False` and check the climate columns in
`.runtime/raw/iced/stateWiseDeepDive_<FY>.json`.

## Runtime dependency

`parsers.py` imports `Crypto.Cipher.AES` and `Crypto.Util.Padding.unpad`
from **pycryptodome**. It is therefore a **runtime** backend dependency,
declared in `backend/pyproject.toml` under `[project].dependencies` (not
under `[project.optional-dependencies].dev`) — the source module imports
it unconditionally at module load, so any process that imports
`yen_gov.sources.iced_state_wise.*` (CLI, FastAPI admin, pytest collection)
fails without it. We chose pycryptodome over `cryptography` because the
CryptoJS-OpenSSL key derivation we reproduce (`EVP_BytesToKey` with MD5)
is a thin AES-CBC + PKCS7 use case where pycryptodome's `AES.new(...,
MODE_CBC)` and `pad`/`unpad` map 1:1 to the JS reference, keeping the
parser short and obviously correct.

## What lives where

```
backend/yen_gov/sources/iced_state_wise/
  __init__.py       # doc-only, no re-exports
  parsers.py        # decrypt_cryptojs_openssl, extract_rows, ENTITY_MAP, IndicatorSpec
  ingest.py         # INDICATOR_SPECS catalogue, HTTP fetch + cache, write_artifact wiring

backend/tests/test_sources_iced_state_wise.py
                    # 24 pure tests, no network. AES round-trip via test-only encrypt helper.

datasets/indicators/in/energy/state_*.json
datasets/indicators/in/economy/state_*.json
datasets/indicators/in/demography/state_*.json
                    # 13 schema-stamped artifacts, validated against indicator.schema.json v1.1
```

## Operating recipe

First-time bootstrap:

```powershell
.\.venv\Scripts\python.exe -m yen_gov ingest-iced-state-wise
```

Re-fetch one year (e.g. when the latest FY's RE values land):

```powershell
.\.venv\Scripts\python.exe -m yen_gov ingest-iced-state-wise --refresh --fy 2024-25
```

Re-fetch everything (annually after MoSPI / CEA refresh ICED):

```powershell
.\.venv\Scripts\python.exe -m yen_gov ingest-iced-state-wise --refresh
```

The 11 GETs total are polite enough to need no extra rate-limiting
beyond the ~1.5 s exponential backoff already built into `_fetch_one`.
