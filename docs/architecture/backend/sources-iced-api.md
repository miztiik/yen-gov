# ICED API: how the wire actually works

**Last Updated**: 2026-05-15

> Canonical reference for every yen-gov adapter that talks to NITI Aayog's
> ICED dashboard at <https://iced.niti.gov.in>. Read this before opening a
> second ICED-backed source module — every adapter must reuse
> `backend/yen_gov/sources/iced_common/` rather than re-derive the
> protocol.

## What ICED is

ICED — *India Climate & Energy Dashboard* — is the NITI Aayog public
dashboard at <https://iced.niti.gov.in>. It surfaces ~50 distinct dashboard
pages spanning energy (capacity, generation, distribution, transmission,
fuel sources, end use), climate & environment (GHG emissions, air
quality, water, biodiversity, climate variability), and economy /
demography (GDP, GVA, HDI, per-capita income, per-capita consumption,
industrial production). Most pages render long historical time series:
some go back to 1947 (installed capacity), 1971 (per-capita
consumption), 1994 (GHG inventories). The data underlying each chart is
fetched at view time from a private JSON API. yen-gov treats that API
as the canonical ingest surface for ICED-published data.

## The wire protocol

### Hosts

| Host | Notes |
| --- | --- |
| `https://icedapi.niti.gov.in`        | Versionless API root. ~95 % of endpoints. |
| `https://icedapi.niti.gov.in/v1`     | Versioned root. A small set of endpoints (often newer) live under `/v1`. |
| `https://iced.niti.gov.in`           | The dashboard itself. Used only for the `Origin` and `Referer` headers. |

The bundle sets the API host as a single constant `H` and concatenates
path templates with `${H}<path>`. Both literal hosts (`/` and `/v1`)
appear; new endpoints typically ship under `/v1`.

### Request shape

Every endpoint is a `GET`. Query string is plain
URL-encoded — no signing, no token, no per-request nonce.

Required headers (the upstream rejects bare `python-urllib` UAs in some
configs and 403s when `Origin` / `Referer` are missing):

```
Origin:     https://iced.niti.gov.in
Referer:    https://iced.niti.gov.in/
User-Agent: <browser-style>
Accept:     application/json, text/plain, */*
```

No `Authorization`, no cookie, no anti-CSRF token. The captcha gate
exists only on the user-facing **download-as-XLSX** form
(`/sendEmail` + `/validateRecaptcha`); the JSON endpoints themselves are
unauthenticated.

### Response envelope

Every endpoint returns `HTTP 200` with a body of the form:

```text
"U2FsdGVkX1+...base64..."
```

— a *JSON-quoted base64 string*. Decode the JSON layer (one
`json.loads`), then base64-decode. The decoded bytes start with the
ASCII magic `Salted__` (8 bytes), followed by an 8-byte salt, followed
by AES-256-CBC ciphertext with PKCS#7 padding.

Decrypt to recover the underlying JSON, which is conventionally:

```json
{ "status": 1, "data": <whatever the page needs> }
```

A small number of endpoints return a bare list or scalar inside the
ciphertext rather than the `{status, data}` envelope; parsers must not
hard-assume the wrapper.

## The cipher

| Field | Value |
| --- | --- |
| Algorithm     | AES-256-CBC, PKCS#7 padding |
| Key length    | 32 bytes |
| IV length     | 16 bytes |
| Salt          | 8 bytes, immediately after the `Salted__` magic, sent per-message |
| KDF           | OpenSSL `EVP_BytesToKey` — `MD5(prev \|\| passphrase \|\| salt)` iterated until `key_len + iv_len` bytes produced. **Single iteration**, no PBKDF2. |
| Passphrase    | `AHten@VP0W3R` (ASCII bytes) |
| JS library    | `crypto-js` — `CryptoJS.AES.decrypt(b64String, "passphrase")` does exactly the above when given a string passphrase rather than a raw key. |

This is the OpenSSL `enc -aes-256-cbc -md md5` envelope. It is what
CryptoJS calls "OpenSSL format". A
[~10-line Python replication](#python-replication) sits in
`backend/yen_gov/sources/iced_common/crypto.py`.

### Where the passphrase lives

In the public Angular bundle. Specifically, the production main bundle
shipped to every browser that opens the site:

```text
https://iced.niti.gov.in/main.cb0bb1d44638969b.js   (~11.2 MB minified)
```

contains the constant `KEY:"AHten@VP0W3R"` (env config module, observed
at byte offset ~5 815 108 in the 2026-05-14 build). The decryption
call site is:

```js
extractData(i) {
  const u = b.AES.decrypt(i, U);            // U == KEY constant
  return JSON.parse(u.toString(b.enc.Utf8)) || {};
}
```

`b` is the local alias the bundle gives to `crypto-js`. `U` is the
passphrase constant. The bundle hash (`cb0bb1d44638969b`) rotates each
build, but the constant has been stable across all builds we have
observed. If a future bundle rotates the passphrase, the decrypt path
will throw `ICEDShapeError("AES decrypt/unpad failed …")` and we
re-extract from the new bundle.

### Is this security?

No. It is obfuscation.

The site's own Angular code holds the key in plaintext and decrypts every
response client-side; any browser that loads the page receives the
passphrase. There is no sense in which the passphrase is "secret" — it
is shipped to every user. The encryption keeps casual `curl` users
confused, raises the bar on automated scraping a small amount, and lets
the site interpose its own client-side rate logic — none of which are
security properties.

We replicate the algorithm for one reason: it is the most honest way to
ingest the data. The alternatives are worse:

- **Scraping the rendered DOM** misses everything ECharts paints to
  canvas (which is most of it).
- **Driving a headless browser per page** is slow, flaky, and gives the
  same data as the API call with extra steps.
- **Asking ICED for a feed** has been tried by other journalists; there
  is no public answer and no published API contract.

The data is public — that is the entire point of the dashboard. The
publisher (NITI Aayog) explicitly publishes it for re-use by anyone with
a browser, then ships the encryption key to every browser that asks.
We replicate, attribute every emitted artifact (`sources[].url` is the
exact `icedapi.niti.gov.in/...` URL we fetched, per CLAUDE.md §12), and
do not pretend the obfuscation does anything it doesn't. Captcha-gated
download forms remain off-limits — we do **not** automate
`/sendEmail` or `/validateRecaptcha`, ever.

## Python replication

Living code: `backend/yen_gov/sources/iced_common/crypto.py`. Inline
sketch for documentation completeness:

```python
import base64, hashlib, json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

PASSPHRASE = b"AHten@VP0W3R"

def evp_bytes_to_key(passphrase, salt, key_len=32, iv_len=16):
    out, prev = b"", b""
    while len(out) < key_len + iv_len:
        prev = hashlib.md5(prev + passphrase + salt).digest()
        out += prev
    return out[:key_len], out[key_len:key_len+iv_len]

def decrypt_response(server_body):
    outer = json.loads(server_body)            # JSON-quoted string
    raw = base64.b64decode(outer)
    assert raw[:8] == b"Salted__"
    salt, body = raw[8:16], raw[16:]
    key, iv = evp_bytes_to_key(PASSPHRASE, salt)
    plain = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(body), AES.block_size)
    return json.loads(plain)
```

Verified against four live endpoints on 2026-05-14:
`/websiteLastUpdated`, `/whatsNew?path=...`, `/chart-title` (~300 KB),
`/climate-environment/ghg-emissions/energy` (~150 KB).

## Endpoint catalogue

The bundle reveals **259 distinct API paths** (recon: regex
`` `${H}([^`]+)`  `` over the minified bundle, dedup, sort). They split
into three flavours:

- **Parameter-free** (~140): `GET /<path>`, no template holes.
  Single GET fully reproduces the page data. Safe to bulk-mirror.
- **Path-templated** (~50): `${i}/${m}/${u}` style — page
  controllers resolve placeholders before the call (state codes, plant
  ids, fuel-source codes).
- **Query-templated** (~70): `?year=${i}&state=${m}` style — finite
  domains usually (FY labels, state names from the master list).

The full 259-path list is reproduced verbatim at the end of this doc;
the curated subset we have bound to parsers (or actively reconned)
lives in `backend/yen_gov/sources/iced_common/endpoints.py`. New
adapters MUST add their endpoints to that registry rather than embed
URL strings inline — one place to grep when ICED rotates a path.

### High-priority surfaces (first ingest wave)

| Endpoint | Why it matters |
| --- | --- |
| `/economy-demography/key-economic-indicators/per-capita-consumption` | State-level PFCE per capita, **1971 → 2024** — extends our existing kWh consumption series back 50 years. |
| `/economy-demography/key-economic-indicators/per-capita-income` | NSDP per capita, current prices, **2004-05 → 2023-24** — forward-extends the existing yen-gov per-capita NSDP series. |
| `/economy-demography/key-economic-indicators/per-capita-income-map` | Same series in choropleth-ready form. |
| `/economy-demography/key-economic-indicators/gdp-trend` | National GDP trend, current + constant. |
| `/economy-demography/key-economic-indicators/gva-trend` | National GVA trend, sectoral split. |
| `/economy-demography/key-economic-indicators/hdi-map` | Sub-national HDI choropleth values. |
| `/economy-demography/key-economic-indicators/industrial-production` | IIP series. |
| `/economy-demography/demography/demographyActual` | Population pyramid / age distribution. |
| `/climate-environment/ghg-emissions/energy` | **Despite the name, returns the ENTIRE GHG dataset** including agriculture sub-sectors. ~150 KB. Schema: `{sector, subSector, category, subCategory, year, emission}` × thousands of rows. |
| `/climate-environment/ghg-emissions/economy-wide-emission` | Economy-wide GHG aggregates. |
| `/retired-capacity-plants` | Retired thermal plants by state × source × year. NEW indicator. |
| `/plantPipelineInfo` | Under-construction capacity additions. |
| `/powerPlantsListing` | Master plant registry (subset). |
| `/energy/generation` | National generation by source, time series. |
| `/chart-title` | 296 KB metadata: every chart's title, source attribution, footnote. **Use as the canonical source of `indicator.notes` text** rather than re-paraphrasing. |

### Already covered (don't re-ingest)

13 indicators from `/analytics/stateWiseDeepDive` are already emitted by
[`backend/yen_gov/sources/iced_state_wise/`](sources-iced-state-wise.md).
Anything new must extend, augment, or fill a gap not on that list.

### Air-quality endpoints (registered 2026-05-15, parsers pending)

Eight endpoints under `/climate-environment/environment/air-quality/*`
plus the city-aggregated `/climate-environment/aqmCityWise/aqm-cities`
were probed live on 2026-05-15 (see `tools/iced_full_triage.py` output)
and registered in `endpoints.py` as `aq_*`. Catalogue-only — no parser
binds them yet. Sequencing: `aq_fgd` (thermal-plant FGD compliance) ships
first, `aq_aqi_map_markers` → state-year PM2.5 follows, the other
pollutants come behind that.

**Provenance rule (mandatory):** ICED is a re-publisher of CPCB NAMP
annual-mean station files (the `file` column on `aq_aqi_map_markers`
literally points to `data/AQ_CPCB_UTF8/AQM_<year>_Annual_mean.csv`).
Any artifact emitted from these endpoints MUST list **both** the ICED
API URL we fetched AND the CPCB upstream URL in its `sources` array
(CLAUDE.md §12). Listing only the ICED URL is a governance bug — we
would be implying NITI as the publisher.

**Honesty constraints (do not paper over):**
- `aq_aqi_map_markers` is **station-level**, not state-level. The monitor
  network is uneven and urban-biased (rural districts may have zero
  monitors). State-aggregated rankings are not honest from this dataset.
  Aggregations we publish (e.g. state PM2.5 mean) MUST document the
  method in `methodology_vintage` AND surface the rural-coverage caveat
  on the consuming UI.
- PM2.5 measurements start in 2014; SO₂/NO₂/PM10 start in 2010. Any
  multi-pollutant view declares a `series_break` at 2014 for PM2.5.
- `aq_aqm_cities` is ICED's pre-aggregated city-year rollup with an
  opaque method. Use as a cross-check fixture only; never as the source
  of truth. Compute our own aggregates from `aq_aqi_map_markers`.
- `aq_coal_plant_impact` is **modelled**, not measured. Treat with the
  same caution as any model output before binding to an indicator.

### Wave-2 catalogue expansion (2026-05-17)

Twenty further parameter-free endpoints from the
`tools/iced_full_triage.py` recon (94 "ok new (unbound)" survivors)
were added to `endpoints.py` as catalogue-only entries, raising the
bound catalogue from 35 to 55. Selection criteria: state-level
coverage, distinct topical territory, year+state facet keys so the
endpoint is citizen-renderable without aggregation gymnastics.

Notable groups in the wave:
- **Energy aggregates** (`energy_sector_wise_consumption`,
  `energy_source_wise_supply`) — unblock ephemeral-dataset triage
  candidate #19 (`sectorwise_energy_consumption`) which had no
  publishable source URL before.
- **Discom operations** (`discom_operational_performance_states`,
  `discom_rpo_compliance`) — pair with the existing UDAY/ATC artifacts.
- **RE potential** (`solar_potential_by_state`,
  `wind_potential_by_state`, `bio_energy_potential_by_state`) — unblock
  ephemeral candidate #16 (`re_potential`).
- **Climate variability** (`climate_rainfall_district`,
  `climate_temperature_annual`, `forest_cover_by_state`,
  `land_use_by_state`) — first environment-domain entries beyond air
  quality and GHG.
- **Transport** (`ice_ev_vahan`) — unblocks ephemeral candidate #5
  (`ev_trend`); raw payload is ~6.3 MB so the eventual parser MUST
  filter before emit.

These are **catalogue-only** — no parser binds them yet. The doctrine
unchanged: each indicator that ships from one of these endpoints is a
separate per-indicator commit with its own schema-conformant artifact
and §12 provenance, not a bulk emit.

### `chart_title` snapshot as canonical attribution source

The 296 KB `/chart-title` endpoint catalogues every chart on the ICED
dashboard with its publisher-printed `chart_title`, `footnote`, and
`source` strings. Rather than each adapter re-paraphrasing ICED's
attribution, yen-gov snapshots that catalogue to
`datasets/reference/in/iced-chart-titles.json` via
`tools/emit_iced_chart_titles.py` (schema
`iced-chart-titles.schema.json` v1.0). New ICED-backed indicators
SHOULD look up their backing chart by `id` (or `(page, section)`) and
quote ICED's own `footnote`/`source` strings verbatim in their
`indicator.notes` — per CLAUDE.md §10, the adapter owns the
publisher's vocabulary, no normalisation. The snapshot is
re-emittable; rerun the tool when ICED ships new charts.

## Conventions for new ICED adapters

1. **One module per dashboard page family.** Don't put GHG and HDI in
   the same module just because they happen to come from the same host.
2. **Reuse `iced_common`.** Never re-implement `decrypt_response`,
   never re-spell state names. If `ENTITY_MAP` doesn't recognise an
   incoming name, add it to the shared map (with a comment naming the
   source page); don't maintain a parallel dict.
3. **Cache raw to `.runtime/raw/iced/...`.** The `IcedClient` does this
   automatically. Per ADR-0003 it's a debug snapshot, not a cache;
   re-runs overwrite.
4. **Provenance per CLAUDE.md §12.** The artifact's `sources[].url`
   MUST be the exact `https://icedapi.niti.gov.in/<path>?<query>` URL
   that produced the data (one entry per distinct upstream URL when an
   artifact composes multiple endpoints), never the page URL.
5. **Schema-strict fail-loud.** If the API shape changes, the adapter
   must raise `ICEDShapeError`, not silently emit zero rows.
6. **No DOM scraping fallback.** If the API doesn't return a series we
   want, accept the gap and document it; do not paper over with
   browser-rendered numbers we read off canvas.

## Operational hazards

- **Bundle hash rotates.** When ICED ships a new build the hash in
  `main.<hash>.js` changes; the constant `KEY:"AHten@VP0W3R"` has been
  stable. If a build ever rotates the key, every `IcedClient.get()`
  starts throwing `AES decrypt/unpad failed`. Re-extract via the recon
  recipe in [the recon how-to](../../how-to/iced-extract-passphrase.md).
- **`Origin` / `Referer` enforcement is intermittent.** Some networks
  see 403s without the headers, some don't. We always set them; the
  cost is ~80 bytes per request.
- **Polite delay.** No published rate limit, but we serialize requests
  with a 0.5 s default gap. The dashboard itself parallelises freely;
  we don't, because we have all night.

## See also

- [`backend/yen_gov/sources/iced_common/`](../../../backend/yen_gov/sources/iced_common/__init__.py) — reusable client + crypto + entity map + endpoint registry.
- [`backend/yen_gov/sources/iced_state_wise/`](../../../backend/yen_gov/sources/iced_state_wise/__init__.py) — first ICED adapter (state-wise deep dive).
- [sources-iced-state-wise.md](sources-iced-state-wise.md) — what that adapter ships.
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md) — provenance discipline applied to every emitted artifact.
- [ADR-0003](../decisions/0003-no-fetch-cache.md) — why `.runtime/raw/iced/` is a debug snapshot, not a cache.

---

## Appendix: full 259-endpoint list (recon 2026-05-14)

Verbatim regex match `` `${H}<path>` `` from
`main.cb0bb1d44638969b.js`. Placeholders preserved as `${name}`.

```
/airQualityEmission
/airQualityFilter
/all-data-power-purchase-quantum-and-cost
/allindia-power-purchase-quantum-and-cost
/analytics/aqi-impact-due-to-coal-plants-list
/analytics/daily-demand-vs-temperature-analytics?year=${i}&state=${encodeURIComponent(m)}
/analytics/daily-demand-vs-temperature-filters-analytics
/analytics/discom-accumulated-losses-consumer-saless
/analytics/energy-sales-category-wise
/analytics/ice-ev-vahan
/analytics/indiaCrudeOilPricesVsImport
/analytics/industrialProductivityIndexToElectricityConsumption
/analytics/peak-demand-temperature
/analytics/peak-demand-temperature/cooling-deg-days
/analytics/peak-demand-temperature/count-by-hour
/analytics/peak-demand-temperature/critical-days
/analytics/peak-demand-temperature/max-demand-by-hour
/analytics/peak-demand-temperature/peak-demand-vs-max-temp
/analytics/per-capita-gdp-vs-consumption
/analytics/state-level-re-capacity-potential
/analytics/state-level-re-capacity-potential-filters
/analytics/state-reports/?${i}
/analytics/stateWiseDeepDive?${i}
/capacity-metatable-data
/chart-title
/climate-environment/aqmCityWise/aqm-cities
/climate-environment/bio-diversity/forest-cover-by-state
/climate-environment/bio-diversity/national-park
/climate-environment/bio-diversity/wildlife
/climate-environment/climate-variability/get?${i}
/climate-environment/climate-variability/imd-temperature-rainfall-dates
/climate-environment/climate-variability/imd-temperature-rainfall-stations?year=${i}&month=${m}&tempOrRain=${u}
/climate-environment/climate-variability/rainfall
/climate-environment/climate-variability/temperatureAnnual
/climate-environment/environment/air-quality/aqi-map-markers
/climate-environment/environment/air-quality/co2Emission
/climate-environment/environment/air-quality/cpbc-dates
/climate-environment/environment/air-quality/fgd
/climate-environment/environment/air-quality/gee/${i}?start=${m}&end=${u}
/climate-environment/environment/air-quality/power-plant-list
/climate-environment/environment/air-quality/sentinel-dates
/climate-environment/environment/land
/climate-environment/environment/natural-disaster/${i}
/climate-environment/environment/natural-disaster/power-plant-list
/climate-environment/gas-proportion/gas-wise-proportion
/climate-environment/ghg-emissions/economy-wide-emission
/climate-environment/ghg-emissions/energy
/climate-environment/ghg-emissions/ghg-static-values
/climate-environment/water/ground-water-levels${u}
/climate-environment/water/ground-water-levels-distinct-years
/climate-environment/water/per-capita-water-availability${m}
/climate-environment/water/water-sources${m}
/co-emission-metatable-data
/co-emission-metatable-filter
/coEmissionFilters
/coalLinkage/${i}/${m}
/consumerFilter
/dailyGeneration/${i}
/dailyPeakDemand/${i}
/dailyPeakDemand/last30Days
/data-cards
/demandOperationalFilter
/discom-level-power-purchase-quantum
/discomDemandsCategoryAndHighestTotal
/discomDemandsTariffOrdersParamWise
/discoms
/distinct-values
/economicFilter
/economy-demography/demography/demographyActual
/economy-demography/key-economic-indicators/balance-trendline
/economy-demography/key-economic-indicators/gdp-trend
/economy-demography/key-economic-indicators/gva-trend
/economy-demography/key-economic-indicators/hdi-map
/economy-demography/key-economic-indicators/industrial-production
/economy-demography/key-economic-indicators/per-capita-consumption
/economy-demography/key-economic-indicators/per-capita-income
/economy-demography/key-economic-indicators/per-capita-income-map
/energy-flow
/energy/country-imports?source=${i}
/energy/daily-prices?source=${i}
/energy/electricity/captive-power/captive-power
/energy/electricity/captive-power/captive-power-industry
/energy/electricity/distribution/accumulated-loss-data
/energy/electricity/distribution/accumulated-loss-discom-data
/energy/electricity/distribution/accumulated-loss-whole-data?category=${i}
/energy/electricity/distribution/acs-arr-discom-meta-data
/energy/electricity/distribution/acs-arr-input-sold-data
/energy/electricity/distribution/acs-arr-input-sold-discom-data
/energy/electricity/distribution/acs-arr-input-sold-whole-data?subType=${i}&category=${m}
/energy/electricity/distribution/categoryWiseEnergySalesMix
/energy/electricity/distribution/categoryWiseEnergySalesVsRevenues
/energy/electricity/distribution/consumer-data
/energy/electricity/distribution/consumer-discom-data
/energy/electricity/distribution/consumerProfileStateWholeData
/energy/electricity/distribution/demandTableDataForYear?year=${i}
/energy/electricity/distribution/discomDemandsCategoryAndHighestTotal
/energy/electricity/distribution/discomDemandsTariffOrdersParamWise
/energy/electricity/distribution/distribution-filter?table=${i}&field=${m}
/energy/electricity/distribution/financial-data
/energy/electricity/distribution/financial-discom-data
/energy/electricity/distribution/financialWholeData?subType=${i}&category=${m}
/energy/electricity/distribution/getDataForATandCVsTandDLosses
/energy/electricity/distribution/loadCurveDurationNational?${i}
/energy/electricity/distribution/loadCurveDurationRegional?${i}
/energy/electricity/distribution/loadCurveDurationState?${i}
/energy/electricity/distribution/loadCurveFilters
/energy/electricity/distribution/loadCurveHourlyNational?${i}
/energy/electricity/distribution/loadCurveHourlyRegional?${i}
/energy/electricity/distribution/loadCurveHourlyState?${i}
/energy/electricity/distribution/loadCurveYearly?${i}
/energy/electricity/distribution/operational-data
/energy/electricity/distribution/operational-discom-data
/energy/electricity/distribution/operationalPerformanceStates
/energy/electricity/distribution/rpo
/energy/electricity/distribution/tariff-rate-data
/energy/electricity/generation/daily?${i}
/energy/electricity/generation/plant-info?${i}
/energy/electricity/generation/plant-list?${i}
/energy/electricity/generation/plant-search
/energy/electricity/generation/sub-source-info
/energy/electricity/generation/top-states?${i}
/energy/electricity/transmission/substation-annual
/energy/electricity/transmission/substation-list
/energy/electricity/transmission/substation-plan-wise
/energy/electricity/transmission/transmission-annual
/energy/electricity/transmission/transmission-list
/energy/electricity/transmission/transmission-plan-wise
/energy/end-use/building-appliances
/energy/end-use/demand-agriculture
/energy/end-use/demand-all-india-plantwise
/energy/end-use/demand-fuel-elec-cons
/energy/end-use/demand-fuel-elec-cons?data_type=source
/energy/end-use/industry?${i}
/energy/end-use/transport
/energy/end-use/transport?data_type=electrification
/energy/end-use/transport?data_type=transport
/energy/end-use/transport?year=2000-01&data_type=electrification
/energy/fuel-sources/bio-energy/biofuels
/energy/fuel-sources/bio-energy/potential
/energy/fuel-sources/coal/${i}
/energy/fuel-sources/coal/consumption-broad-category
/energy/fuel-sources/coal/consumption-domestic-sector-wise
/energy/fuel-sources/coal/consumption-domestic-state
/energy/fuel-sources/coal/consumption-overview-domestic
/energy/fuel-sources/coal/consumption-overview-mix
/energy/fuel-sources/coal/consumption-sectors
/energy/fuel-sources/consumption-trend?source=${i}
/energy/fuel-sources/gas/${i}
/energy/fuel-sources/hydro/capacity-by-technology
/energy/fuel-sources/hydro/potential
/energy/fuel-sources/nuclear/capacity-by-technology
/energy/fuel-sources/oil/consumption?${i}
/energy/fuel-sources/oil/consumptionMonthly?${i}
/energy/fuel-sources/oil/consumptionState?${i}
/energy/fuel-sources/oil/consumptionStateProductTrend
/energy/fuel-sources/oil/daily-retail-selling-price
/energy/fuel-sources/oil/fob-monthly
/energy/fuel-sources/oil/import?${i}
/energy/fuel-sources/oil/pipeline?${i}
/energy/fuel-sources/oil/ppSupplyMonthly
/energy/fuel-sources/oil/pricing?${i}
/energy/fuel-sources/oil/productSupply?${i}
/energy/fuel-sources/oil/production
/energy/fuel-sources/oil/productionBasin?${i}
/energy/fuel-sources/oil/productionMonthly?${i}
/energy/fuel-sources/oil/reservesByRegime
/energy/fuel-sources/oil/reservesByState?${i}
/energy/fuel-sources/oil/reservesTrend
/energy/fuel-sources/oil/trade?${i}
/energy/fuel-sources/oil/tradeMonthly?${i}
/energy/fuel-sources/oil/tradePPMonthly?${i}
/energy/fuel-sources/small-hydro/potential
/energy/fuel-sources/solar/irradiance-clicked-data?state=${i}&month=${m}&year=${u}&index=${C}
/energy/fuel-sources/solar/irradiance-dates
/energy/fuel-sources/solar/irradiance?state=${i}&month=${m}&year=${u}
/energy/fuel-sources/solar/potential
/energy/fuel-sources/wind/filters?table=${i}&field=${m}
/energy/fuel-sources/wind/potential
/energy/fuel-sources/wind/speed-clicked-data?${C}
/energy/fuel-sources/wind/speed?state=${i}&month=${m}
/energy/fuel-sources/wind/wind-data-filters
/energy/generation
/energy/powerStatistics
/energy/sectorWiseEnergyConsumption
/energy/sourceWiseEnergySupply
/environmentFilter
/filterDropDownData/${i}/${m}/
/filterDropDownDataReason/${i}/${m}/${u}/
/financialHealthFilter
/forced-outage
/fuelFilter
/fuellinkage
/gee/${i}?start=${m}&end=${u}
/gen-filter-dropdowns
/gen-metatable-data
/generationDemandFilters
/getBase64OfImg?url=
/historicalTrends
/homeMap
/homeMapSubSourceMarkersData
/infographics
/infographics?${i}
/integratedAirQualityFilters
/integratedHomeMap
/latest-date
/logXlsxDownloadRequest
/outage-dropdowns
/outage-metatable-data
/paramFilterBasedDropDown/${i}/
/performanceFilter
/performanceNetFilter
/pipelineReasons
/pipelineUnitData/${i}/${m}
/planned-outage-dropdowns
/planned-outage-metatable-data
/plantBySlug/${i}/${m}/${u}
/plantCost/${i}/${m}/${u}/${C}
/plantCostRE/${i}/${m}
/plantDailyGeneration/${i}/${m}/${u}/${C}
/plantFgdStatus/${i}
/plantForcedOutage/${i}/${m}/${u}/${C}
/plantFuel/${i}/${m}
/plantListBySource
/plantPipelineInfo
/plantPotential/${i}/${m}
/plantSDPerformance/${i}/${m}/${u}
/plantSearch/${i}
/plantTechnical/${i}/${m}/${u}/${C}
/plantUnitPerformance/${i}/${m}/${u}
/plf-metatable-data
/potentialFilter
/power-purchase-quantum-table
/power-quantum-discoms
/powerCostFilter
/powerPlantsListing
/powerPurchaseFilters
/quantum-state-year
/reShare
/retired-capacity-plants
/sendEmail
/state-power-purchase-quantum-and-cost?state=${i}&year=${m}&source=${u}
/stateDailyGeneration/${i}/${m}
/stateDistrictEconomic/${i}/${m}
/stateDistrictPotential/${i}/${m}
/statelevel-power-purchase-quantum-and-cost
/techFilterDropdown/${i}
/technical-metatable-data
/technicalFilter
/temperatureDecadal
/topStates
/transmissionSubstationAnnual
/transmissionSubstationDetails
/transmissionSubstationPlanwise
/turbineMakes/${i}/${m}
/utilizationOutagesFilters
/validateRecaptcha
/waterFilter
/websiteLastUpdated
/whatsNew?path=${encodeURIComponent(i)}
```
