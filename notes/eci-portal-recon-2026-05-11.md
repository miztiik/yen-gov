# ECI portal reconnaissance — 2026-05-11

> **Status**: research-only. No code changes follow from this recon directly. Drives Phase 6 sub-phase 6C (LS-2024 + prior-cycle assembly ingest) planning.

## Executive summary

ECI uses **three distinct hosting models** across cycles:

| Era | Model | Ingest strategy |
|---|---|---|
| **May 2026 AC (TN/KL/AS/WB/PY)** | Live HTML portal at `results.eci.gov.in/ResultAcGenMay2026/` | Static HTML scraping — already shipped via `yen_gov/sources/eci/` |
| **LS-2024** | API-only + statistical reports (XLSX/PDF) — no live HTML portal | API client + XLSX parser; optional per-PC PDF cards (543 files) |
| **2024–2025 Assembly Elections (14 states)** | API-only statistical reports — same shape as LS-2024 | Reuse the LS-2024 parser with different `category_id`s |
| **2021 Assembly (TN/KL/AS/WB)** | Archive on `old.eci.gov.in/files/file/<id>-<state>-…/` | TBD — likely a mix of HTML + PDF; one-by-one fetch needed |

Critical insight: the May-2026 portal is the *exception*, not the norm. ECI moved to API-only after LS-2024 and only reverted to a live HTML portal for the May-2026 cycle. Plan the architecture so HTML scraping and API/XLSX ingest are sibling adapters, not "API as a special case of HTML scraping".

## 1. May 2026 AC (already ingested)

**Slug**: `ResultAcGenMay2026`. Hosted at `results.eci.gov.in`.

```
https://results.eci.gov.in/ResultAcGenMay2026/index.htm
https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-{STATE_CODE}.htm
https://results.eci.gov.in/ResultAcGenMay2026/statewise{STATE_CODE}{PAGE_NUM}.htm
https://results.eci.gov.in/ResultAcGenMay2026/Constituencywise{STATE_CODE}{AC_NUMBER}.htm
https://results.eci.gov.in/ResultAcGenMay2026/candidate{STATE_CODE}{AC_NUMBER}.htm
```

Confirmed state codes used in this cycle: `S22` (TN), `S11` (KL), `S03` (AS), `S25` (WB), `U07` (PY).

Server-rendered HTML, no SPA, all 200 OK. No JSON sidecar endpoint discovered.

## 2. LS-2024 — API + statistical reports

**No live HTML portal exists.** All these returned 404:
- `ResultPcGenApril2024/`, `PcGenApril2024/`, `LSResults2024/`, `Result2024PC/`

Two parallel API surfaces:

### 2.A — Statistical reports (`category_id=1`, 42 documents)

```
GET https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=1
```

Returns JSON catalogue of XLSX + PDF files. Notable entries:
- `2-List-of-Successful-Candidates.xlsx` (25 KB)
- `5-Performance-of-Political-Parties.xlsx` (19 KB)
- `7-Candidate-Wise-Detailed-Result.xlsx` (1.2 MB)
- `33-Constituency-Wise-Detailed-Result.xlsx` (3 MB) — **the per-PC summary equivalent of `Constituencywise*.htm`**

Response shape:
```json
{
  "code": 200, "status": 1, "success": true,
  "cat_name": "General Election to Loksabha-2024",
  "totalResults": 42,
  "results": [
    {
      "id": 1, "category_id": 1,
      "title": "1 - Other Abbreviations And Description",
      "pdf_zip_url": "https://www.eci.gov.in/.../1_Other_Abbreviations.pdf",
      "xlsx_url":   "https://www.eci.gov.in/.../1_Other_Abbreviations.xlsx",
      "xls_record_size": "7 KB", "pdf_record_size": "29 KB"
    }
  ]
}
```

### 2.B — Per-PC digital index cards (`category_id=11`, 543 documents — one per PC)

```
GET https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=11
```

Naming pattern: `{StateName}-{PC#}-{ConstituencyName}.{pdf|xlsx}`. Example: `Tamil_Nadu-39-KANNIYAKUMARI.pdf`.

These are scanned/templated index cards with detailed candidate votes — the per-constituency primary source for LS-2024 once the statistical XLSX gives the aggregate frame.

## 3. 2024–2025 Assembly Elections (14 states) — same shape as LS-2024

Each state cycle is its own `category_id` against the same API:

| State | category_id | Notes |
|---|---|---|
| Andhra Pradesh 2024 | 2 | 14 files |
| Arunachal Pradesh 2024 | 3 | 17 files |
| Odisha 2024 | 4 | 14 files |
| Sikkim 2024 | 5 | 14 files |
| Haryana 2024 | 6 | 14 files |
| J&K 2024 | 7 | 14 files |
| Maharashtra 2024 | 8 | 14 files (largest constituency sheet, 735 KB) |
| Jharkhand 2024 | 9 | 14 files |
| Delhi 2024 | 10 | 14 files |
| Bye-elections 2025 | 12–14 | 2–8 files each |

Once the LS-2024 parser exists, every entry above is a config-only addition — `category_id` is the only varying parameter.

## 4. 2021 Assembly Elections — old.eci.gov.in archive

Hosted at `old.eci.gov.in/files/file/<id>-<slug>/`. Documented in prior session notes; not re-fetched here. State codes (`S22`, `S11`, `S03`, `S25`) appear stable across all eras, so when the 2021 portal does serve HTML the existing parsers should mostly carry over.

Action when this work begins: fetch one representative state's 2021 page first to determine whether it serves HTML tables (reuse 2026 parsers) or only PDF/XLSX bundles (reuse LS-2024 XLSX parser). The hosting model determines the parser; the data shape is identical.

## Portal-template inheritance

| Cycle | Domain | Slug pattern | Portal model | Reusable code |
|---|---|---|---|---|
| AC May-2026 | `results.eci.gov.in` | `ResultAcGenMay2026` | live HTML | (the canonical scraper) |
| LS-2024 | `www.eci.gov.in/eci-backend/public/api` | `?category_id=1`, `?category_id=11` | API + XLSX/PDF | new |
| AC 2024–25 (×14) | same | `?category_id=2..15` | API + XLSX/PDF | reuse LS-2024 parser |
| AC 2021 | `old.eci.gov.in` | `/files/file/<id>-…/` | hybrid HTML/PDF | TBD |

## Implications for our pipeline

1. **The HTML scraper is not the universal ingest**. It works for May-2026 because that cycle reverted to the live HTML model. Every other cycle from 2021 onwards needs either an XLSX parser (2024+) or a PDF/archive fetcher (2021).
2. **An API client + XLSX parser is the highest-leverage Phase 6C addition**. One client unlocks LS-2024 + 14 state cycles + every byelection. Per-PC PDF cards (`category_id=11`) are a Phase-6C+ add for higher fidelity.
3. **State codes are stable** across all observed cycles — the existing `categories.py` mapping carries forward. PC numbering for LS uses the same `S22167`-style composite as AC (state code + sequential index within state).
4. **Body enum extension** (`backend/yen_gov` body types) needs to accept `lok_sabha` for LS ingest. PC reference list (543 PCs) needs a one-time backfill from a stable source — the LS-2024 candidate-wise XLSX itself works as the source of truth.
5. **No SPA-rendered portals encountered** — every result surface is either static HTML or a JSON-returning API. No headless browser needed for any era.

## Next concrete steps (Phase 6C plan)

- [ ] Add `body: "lok_sabha"` to the body enum in `backend/yen_gov/core/models.py` and to `election.schema.json` (additive minor bump).
- [ ] Create `backend/yen_gov/sources/eci_api/__init__.py` — HTTP client for `…/election-result?category_id=N` with the same provenance + caching discipline as the HTML scraper (paths POSIX-relative; `sources[]` records each fetched URL + `fetched_at`).
- [ ] Create `backend/yen_gov/sources/eci_xlsx/parsers.py` — openpyxl-based parser for `33-Constituency-Wise-Detailed-Result.xlsx`. One row per (PC, candidate); roll-up code reused from existing event aggregator.
- [ ] Add `datasets/elections/PcGenJune2024/` event metadata (event scope=`india`, body=`lok_sabha`, year=2024, dates filled).
- [ ] Add a one-time backfill script to materialise the 543-PC reference under `datasets/reference/in/parliamentary_constituencies.json` (`$schema` constituency, scoped to `body=lok_sabha`).
- [ ] Write a single LS-2024 state slice (e.g. TN) end-to-end before generalising.
- [ ] Defer per-PC PDF card extraction (`category_id=11`) to a Phase 6C+ follow-up — only useful for forensic reconciliation, not for the primary citizen view.

## Sources

- [https://results.eci.gov.in/ResultAcGenMay2026/](https://results.eci.gov.in/ResultAcGenMay2026/) — fetched 2026-05-11
- [https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm](https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm) — fetched 2026-05-11
- [https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S11.htm](https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S11.htm) — fetched 2026-05-11
- [https://results.eci.gov.in/ResultAcGenMay2026/statewiseS221.htm](https://results.eci.gov.in/ResultAcGenMay2026/statewiseS221.htm) — fetched 2026-05-11
- `https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=1` — fetched 2026-05-11 (LS-2024 statistical reports)
- `https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=11` — fetched 2026-05-11 (LS-2024 per-PC cards)
- `https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=2..15` — fetched 2026-05-11 (state cycles + by-elections)
