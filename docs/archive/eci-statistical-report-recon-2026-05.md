# ECI Statistical Report Reconnaissance, May 2026

**Last Updated**: 2026-05-15

> **See also**:
>
> - [ECI source adapter](../architecture/backend/sources-eci.md)
> - [Data sources reference](../reference/data-sources.md#election-commission-of-india-eci)
> - [Identifier reference](../reference/identifiers.md)
> - [No fetch cache ADR](../architecture/decisions/0003-no-fetch-cache.md)

This archive preserves the durable findings from the 2026-05-09 and 2026-05-11 ECI recon notes after the operational decisions moved into the canonical ECI adapter doc. It is historical trace, not an ingest plan.

## Hosting Models Found

| Era | Model | Current yen-gov strategy |
| --- | --- | --- |
| May 2026 AC results | `results.eci.gov.in/ResultAcGenMay2026/` live HTML | Existing HTML scraper and partywise reconciliation. |
| LS 2024 | API-backed Statistical Report catalogues and per-PC digital index cards | Future PC ingest: use API catalogue + XLSX parser; per-PC cards are optional forensic source. |
| 2024-2026 assembly Statistical Reports | API-backed `/eci-backend/public/api/election-result?category_id=<id>` | Current Section 10 path via pinned `config/eci-pins.json`. |
| 2023 assembly Statistical Reports | Static `/all_files/full-statistical-reports/<state-slug>/2023/...` XLSX/PDF bundles | Current static-catalog adapter with browser-like headers. |
| 2021 and earlier assemblies | `old.eci.gov.in/files/file/<id>-<slug>/` permalinks from the hub table | Not ingested yet; fetch one representative state before choosing parser path. |

The durable design implication was that the May 2026 live HTML scraper is one adapter among siblings, not the universal ECI ingest path.

## 2024+ Category Catalogue Findings

The API shape observed on 2026-05-11:

```text
GET https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=<id>
```

The response contains a `cat_name`, `totalResults`, and a `results[]` list of documents with statement title, XLSX URL, PDF URL, and published sizes. Download URLs are time-limited or CDN-shaped operational URLs and must be resolved at fetch time; persisted provenance should cite the public landing/catalogue URL or the fetched statement URL according to the emitter's schema.

Key category ids from that recon:

| Category id | Election family | Notes |
| ---: | --- | --- |
| 1 | General Election to Loksabha 2024 | 42 Statistical Report documents. |
| 11 | LS 2024 per-PC digital index cards | 543 documents, one per PC. Optional higher-fidelity source. |
| 2 | Andhra Pradesh Assembly 2024 | Statistical Report catalogue. |
| 3 | Arunachal Pradesh Assembly 2024 | Statistical Report catalogue. |
| 4 | Odisha Assembly 2024 | Statistical Report catalogue. |
| 5 | Sikkim Assembly 2024 | Statistical Report catalogue. |
| 6 | Haryana Assembly 2024 | Statistical Report catalogue. |
| 7 | Jammu and Kashmir Assembly 2024 | Statistical Report catalogue. |
| 8 | Maharashtra Assembly 2024 | Statistical Report catalogue. |
| 9 | Jharkhand Assembly 2024 | Statistical Report catalogue. |
| 10 | Delhi Assembly 2025 | Statistical Report catalogue. |
| 12-14 | 2025 bye-elections | Small statement catalogues. |

Later recon found that duplicate `cat_name` values are possible and Bihar 2025 needs the Statistical Report catalogue, not the per-AC live-results catalogue. The canonical rule now lives in [Choosing the right catalogue](../architecture/backend/sources-eci.md#choosing-the-right-catalogue).

## Old-Portal Assembly Hub Permalinks

These URLs were extracted from ECI's hardcoded React hub table on 2026-05-09. The legacy host timed out during that run, so the URL inventory is preserved as a hub-table finding, not as a confirmed byte fetch.

### Tamil Nadu (`S22`)

| Year | URL |
| --- | --- |
| 2021 | `https://old.eci.gov.in/files/file/13680-tamil-nadu-general-legislative-election-2021/` |
| 2016 | `https://old.eci.gov.in/files/file/3473-tamil-nadu-general-legislative-election-2016/` |
| 2011 | `https://old.eci.gov.in/files/file/3340-tamil-nadu-2011/` |
| 2006 | `https://old.eci.gov.in/files/file/3339-tamil-nadu-2006/` |
| 2001 | `https://old.eci.gov.in/files/file/3338-tamil-nadu-2001/` |
| 1996 | `https://old.eci.gov.in/files/file/3336-tamil-nadu-1996/` |
| 1991 | `https://old.eci.gov.in/files/file/3335-tamil-nadu-1991/` |
| 1989 | `https://old.eci.gov.in/files/file/3333-tamil-nadu-1989/` |
| 1984 | `https://old.eci.gov.in/files/file/3331-tamil-nadu-1984/` |
| 1980 | `https://old.eci.gov.in/files/file/3328-tamil-nadu-1980/` |
| 1977 | `https://old.eci.gov.in/files/file/3327-tamil-nadu-1977/` |
| 1971 | `https://old.eci.gov.in/files/file/3326-tamil-nadu-1971/` |
| 1967 | `https://old.eci.gov.in/files/file/3325-tamil-nadu-1967/` |

### Kerala (`S11`)

| Year | URL |
| --- | --- |
| 2021 | `https://old.eci.gov.in/files/file/13827-kerala-general-legislative-election-2021/` |
| 2016 | `https://old.eci.gov.in/files/file/3767-kerala-general-legislative-election-2016/` |
| 2011 | `https://old.eci.gov.in/files/file/3763-kerala-2011/` |
| 2006 | `https://old.eci.gov.in/files/file/3762-kerala-2006/` |
| 2001 | `https://old.eci.gov.in/files/file/3760-kerala-2001/` |
| 1996 | `https://old.eci.gov.in/files/file/3759-kerala-1996/` |
| 1991 | `https://old.eci.gov.in/files/file/3758-kerala-1991/` |
| 1987 | `https://old.eci.gov.in/files/file/3756-kerala-1987/` |
| 1982 | `https://old.eci.gov.in/files/file/3755-kerala-1982/` |
| 1980 | `https://old.eci.gov.in/files/file/3754-kerala-1980/` |
| 1977 | `https://old.eci.gov.in/files/file/3753-kerala-1977/` |
| 1970 | `https://old.eci.gov.in/files/file/3752-kerala-1970/` |
| 1967 | `https://old.eci.gov.in/files/file/3751-kerala-1967/` |
| 1965 | `https://old.eci.gov.in/files/file/3749-kerala-1965/` |
| 1960 | `https://old.eci.gov.in/files/file/3748-kerala-1960/` |
| 1957 | `https://old.eci.gov.in/files/file/3746-kerala-1957/` |

### West Bengal (`S25`)

| Year | URL |
| --- | --- |
| 2016 | `https://old.eci.gov.in/files/file/3469-west-bengal-general-legislative-election-2016/` |
| 2011 | `https://old.eci.gov.in/files/file/3195-west-bengal-2011/` |
| 2006 | `https://old.eci.gov.in/files/file/3194-west-bengal-2006/` |
| 2001 | `https://old.eci.gov.in/files/file/3193-west-bengal-2001/` |
| 1996 | `https://old.eci.gov.in/files/file/3192-west-bengal-1996/` |
| 1991 | `https://old.eci.gov.in/files/file/3191-west-bengal-1991/` |
| 1987 | `https://old.eci.gov.in/files/file/3190-west-bengal-1987/` |
| 1982 | `https://old.eci.gov.in/files/file/3189-west-bengal-1982/` |
| 1977 | `https://old.eci.gov.in/files/file/3188-west-bengal-1977/` |
| 1972 | `https://old.eci.gov.in/files/file/3187-west-bengal-1972/` |
| 1971 | `https://old.eci.gov.in/files/file/3186-west-bengal-general-legislative-election-1971/` |
| 1969 | `https://old.eci.gov.in/files/file/3185-west-bengal-general-legislative-election-1969/` |
| 1967 | `https://old.eci.gov.in/files/file/3184-west-bengal-1967/` |
| 1962 | `https://old.eci.gov.in/files/file/3183-west-bengal-1962/` |
| 1957 | `https://old.eci.gov.in/files/file/3182-west-bengal-1957/` |
| 1951 | `https://old.eci.gov.in/files/file/3181-west-bengal-general-legislative-election-1951/` |

## Recon Lessons Retained

- The React hub table, not a public JSON endpoint, exposed many old-portal assembly permalinks.
- `old.eci.gov.in` and `eci.gov.in` were unreachable from the 2026-05-09 local run; repeat from another network before concluding any old permalink is dead.
- ECI's public-bundle `jl()` helper used AES-ECB with key `4WS8851W824R456Y`, but the canonical path did not need it because the hub table and `/api/election-result` gave the required URLs directly.
- Body `PC` already existed in the schema/model stack; LS 2024 does not require a new body enum.
- The highest-leverage future PC ingest is LS-2024 Statistical Report Section 33 plus optional per-PC digital index cards.
