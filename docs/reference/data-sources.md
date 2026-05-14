# Data Sources

**Last Updated**: 2026-05-14

> The "look here first" catalogue. Every external place yen-gov pulls — or might pull — data from is listed below, with what it covers, what format it ships, and when to use (or avoid) it. When enriching data in future, start here.
>
> The hierarchy for **election data** is enforced by the [authority hierarchy for past elections](../architecture/backend/sources-eci.md#authority-hierarchy-for-past-elections): **ECI is the canonical source**; everything else is bootstrap, enrichment, or cross-check. Non-election data (fiscal, energy, demographics) follow per-domain authority — see the per-source sections below.

> **Machine-readable peer**: [`datasets/reference/in/upstream-sources.json`](../../datasets/reference/in/upstream-sources.json) (validated by [`upstream-sources.schema.json`](../../datasets/schemas/upstream-sources.schema.json)) is the canonical, queryable registry. Every upstream — `ingested` / `recon_done` / `candidate` / `skipped` — has one row there with the landing URL, asset URL pattern, format, coverage, ingest status, the backend adapter (when shipped), the indicator ids it produces, and a `skip_reason` when we consciously chose not to ingest. **When in doubt, the JSON wins**; this Markdown is the human reading-room view of the same facts.

## Source authority order

1. **ECI Statistical Reports** — official tabulated post-election results (XLSX/PDF). Canonical for past elections.
2. **ECI Results Portal** (`results.eci.gov.in`) — live/post-poll constituency pages. Canonical for ECI numbering, party affiliations, and current-cycle results.
3. **ECI Delimitation Order 2008** — canonical for AC↔PC↔district mapping and reservation status.
4. **CEO state offices** — canonical for electoral roll counts and polling-station-level data.
5. **Wikipedia constituency lists** — fast bootstrap; never sufficient alone for `status: complete`.
6. **MyNeta** — canonical for candidate affidavits, declared assets, criminal cases. Not for vote counts.

## ECI Statistical Reports — the treasure trove

**Hub**: <https://www.eci.gov.in/statistical-reports>

**Per-election landing URL grammar** (observed):

```
https://www.eci.gov.in/statistical-report/{body}/{year}/{state-code}
```

| Token | Meaning | Example |
| ----- | ------- | ------- |
| `{body}` | `ae` for Assembly Election, `ge` for General (Lok Sabha) Election | `ae` |
| `{year}` | Year the election concluded | `2026` |
| `{state-code}` | ECI's *display* state code used in URL paths (numeric, NOT the same as the `S22`-style code we use internally) | `26` for Tamil Nadu |

**Confirmed mappings** (from URLs the user supplied or pages we have visited):

| Internal (ECI) | Display state code | State |
| -------------- | ------------------ | ----- |
| `S22`          | `26`               | Tamil Nadu |
| `S11`          | TBC                | Kerala |
| `S25`          | TBC                | West Bengal |

The "TBC" rows are confirmed during the [recon pass](../architecture/backend/sources-eci.md#two-phase-rollout) before any tooling depends on them. Mappings are then promoted into [`identifiers.md`](identifiers.md) as a stable lookup.

**Per-election known URLs** (assembly elections, last three cycles for the in-scope states):

| State | 2026 | 2021 | 2016 | 2011 |
| ----- | ---- | ---- | ---- | ---- |
| Tamil Nadu (S22) | <https://www.eci.gov.in/statistical-report/ae/2026/26> | TBC during recon | TBC | TBC |
| Kerala (S11) | n/a (next cycle 2026 TBC) | TBC | TBC | TBC |
| West Bengal (S25) | n/a (next cycle 2026 TBC) | TBC | TBC | TBC |

The recon script ([`tools/eci_recon/`](../../tools/eci_recon/)) populates the TBCs and lists the actual file artifacts (XLSX names, PDF names, sizes) attached to each landing page.

**Signed download URLs**: ECI's "Download" buttons point at `https://www.eci.gov.in/eci-backend/public/api/download?url=<base64-blob>` — the `url` query param is an encrypted/signed reference that is **time-limited**. We MUST NOT persist these URLs in `sources[]`. Persist the human-facing landing URL (`/statistical-report/...`) and, if needed, document the file name extracted from the response headers; re-resolve the signed URL each fetch. (See ADR-0003: no fetch cache; intermediate downloads live in `.runtime/raw/`.)

## ECI Results Portal

**Hub**: <https://results.eci.gov.in/>

**Per-constituency URL grammar**:

```
https://results.eci.gov.in/Result{ElectionEvent}/Constituencywise{State}{ConstNo:03d}.htm
```

Example: `https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22167.htm` → TN AC #167 (Mannargudi) for the May 2026 Assembly General Election.

`{ElectionEvent}` is the ECI's per-event slug (e.g. `AcGenMay2026`, `AcGenApr2021`, `LSGenJun2024`). Slug history: TBC during recon. Documented in [backend/sources-eci.md](../architecture/backend/sources-eci.md).

## ECI Term of the Houses

<https://www.eci.gov.in/term-of-the-houses/>

Lists current Lok Sabha and every state Assembly with constitution and dissolution dates. Use to confirm: "when did the 2021 TN assembly's term end" / "when does the 2026 TN assembly start". Critical for naming election events correctly.

## ECI Delimitation Order 2008

<https://eci.gov.in/delimitation-website/> (PDF per state)

The only legally authoritative source for AC↔PC↔district mapping. Required ECI source for promoting any constituency reference file from `status: provisional` to `status: complete` (see [data-model.md](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle)).

## CEO state portals

| State | URL | Use for |
| ----- | --- | ------- |
| Tamil Nadu | <https://www.elections.tn.gov.in/> / <https://ceotamilnadu.nic.in/> | Electoral roll counts, polling station lists |
| Kerala | <https://www.ceo.kerala.gov.in/> | Same |
| West Bengal | <https://ceowestbengal.nic.in/> | Same |

Format varies wildly across states — usually PDFs; sometimes Excel.

## MyNeta (Association for Democratic Reforms)

**Hub**: <https://www.myneta.info/>

Tamil Nadu specific landing pages:

- 2021 Assembly: <https://www.myneta.info/TamilNadu2021/index.php?action=showWinnersExpense&sortExp=default>
- 2026 Assembly: <https://www.myneta.info/TamilNadu2026/>

Use for **candidate-level enrichment only** — declared assets, criminal cases, education, expense filings. **Do not** use as a source for vote counts; cross-check with ECI before persisting.

## Wikipedia

Bootstrap source for constituency lists, district lists, and election summary tables. Per-state URL grammar (observed):

```
https://en.wikipedia.org/wiki/List_of_constituencies_of_the_<State>_Legislative_Assembly
https://en.wikipedia.org/wiki/<Year>_<State>_Legislative_Assembly_election
https://en.wikipedia.org/wiki/List_of_districts_of_<State>
```

Wikipedia is excellent for fast structured tables and for human-readable history fields (`established_year`, mergers). Per [backend/sources-wikipedia.md](../architecture/backend/sources-wikipedia.md) and CLAUDE.md §10, never the *only* source for a `complete` file.

## RBI — *State Finances: A Study of Budgets* (fiscal indicators)

**Authority/listing page**: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3A+A+Study+of+Budgets>

The Reserve Bank of India publishes this volume annually (typically December–January). It is the **canonical source for cross-state fiscal-indicator series** — own-tax revenue, revenue/fiscal deficit, outstanding debt, interest payments, capital outlay, central transfers — for every state and the two UTs with legislatures (Delhi, Puducherry). RBI compiles it from each state government's Budget documents and applies a uniform classification, which makes the series comparable across states in a way the underlying state budgets are not.

**Layout we depend on**: each Statement / Appendix Table ships as **its own XLSX** on the listing page (87 files in the Jan 23, 2026 edition). URL slugs include a `DDMMYYYY` date stamp and an opaque hex hash, so URLs change wholesale every edition — there is no stable redirect. The pinned-URL registry lives in [`backend/yen_gov/sources/rbi_xlsx/urls.py`](../../backend/yen_gov/sources/rbi_xlsx/urls.py); recon procedure for new editions is in [backend/sources-rbi.md](../architecture/backend/sources-rbi.md).

**Statements currently consumed** (Jan 23, 2026 edition, FY 2025-26 budgets):

| Statement | Title | Indicator id | URL |
| --------- | ----- | ------------ | --- |
| 20 | Total Outstanding Liabilities of State Governments — As per cent of GSDP | `fiscal/outstanding_debt_pct_gsdp` | <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/20_ST2301202696AC652FC4CE482EAAD928FC544CD86A.XLSX> |

More Statements (revenue deficit, fiscal deficit, interest payments, central transfers, capital outlay, own-tax, own non-tax) are queued — see [backend/sources-rbi.md](../architecture/backend/sources-rbi.md) for the per-Statement → indicator mapping and the honesty fields each indicator carries (`direction`, `comparability`, `attribution_geography`, `funding_split`).

**Network note**: RBI's CDN (`rbidocs.rbi.org.in`) rejects non-browser User-Agents with an HTML error page (which then fails XLSX parsing). The `ingest-fiscal-rbi` CLI passes a Chrome-style UA for this source only — every other adapter retains the project's `yen-gov/0.1` UA. Documented inline in `backend/yen_gov/cli.py` at the call site.

**License**: Government of India open publication (`GoI-Open`, redistributable). The license URL on each artifact points at <https://data.gov.in/government-open-data-license-india>.

## RBI — Handbook of Statistics on Indian Economy (national long series)

**Authority/listing page**: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx>

The Handbook is RBI's catch-all annual compendium covering national fiscal, monetary, banking, external-sector, and price series — most going back 30+ years. We ingest two slices today and have several more queued (see registry `status: candidate`):

| Statement | Coverage | Adapter | Indicator ids |
| --------- | -------- | ------- | -------------- |
| Appendix Table 1 (states-aggregate fiscal deficits) | All India, FY80–FY26 | `rbi_appendix_deficits` | `fiscal/states_combined_gross_fiscal_deficit`, `fiscal/states_combined_revenue_deficit`, `fiscal/states_combined_primary_deficit`, `fiscal/states_combined_primary_revenue_deficit` |
| Handbook of Statistics on Indian Economy — Table 89 (Centre's deficits) | All India (Union Government), FY87–FY26 | `rbi_hbs_ie_centre_deficits` | `fiscal/union_gross_fiscal_deficit`, `fiscal/union_revenue_deficit`, `fiscal/union_primary_deficit`, `fiscal/union_primary_revenue_deficit` |
| Appendix Table 2 (Centre transfers to States) | All India aggregate, FY08–FY26 | `rbi_appendix_national` | `fiscal/centre_transfers_to_states_net`, `fiscal/centre_transfers_to_states_tax_devolution`, `fiscal/centre_transfers_to_states_grants`, `fiscal/centre_transfers_to_states_gross` |

Per-edition pinned URLs live in each adapter's `urls.py`; same Chrome-style UA workaround as the State Finances adapter.

## NITI Aayog — ICED state-wise deep dive (energy + economy + demography)

**Page**: <https://iced.niti.gov.in/analytics/state-wise-deep-dive>
**API**: <https://icedapi.niti.gov.in/analytics/stateWiseDeepDive>

ICED is NITI Aayog's energy/climate dashboard, but its `stateWiseDeepDive` endpoint also bundles economy and demography series for free. Coverage = 28 states + 8 UTs + All-India, FY16–FY26 annual, 13 indicators per state-year (see registry `iced.state_wise_deep_dive`). Response is **CryptoJS-OpenSSL AES-256-CBC encrypted JSON** — passphrase extracted from the SPA bundle. Adapter `iced_state_wise` does the decrypt + per-indicator extract; full recon recipe in [backend/sources-iced-state-wise.md](../architecture/backend/sources-iced-state-wise.md). On Windows the adapter uses `urllib` (not httpx) because the icedapi cert chain isn't in `certifi`.

## CEA — monthly Installed Capacity Report

**Hub**: <https://cea.nic.in/installed-capacity-report/?lang=en>
**Asset URL pattern**: `https://cea.nic.in/wp-content/uploads/installed/<YYYY>/<MM>/Website.xlsx`

CEA publishes a monthly XLSX of All-India + per-state nameplate installed capacity by fuel type (coal/gas/hydro/nuclear/renewable/thermal/total). Adapter `cea_installed_capacity` is **operator-fetched** — Windows / many CI images reject `cea.nic.in`'s TLS chain, so the operator runs `Invoke-WebRequest` once per month into `.runtime/raw/cea/installed_capacity_<YYYY>_<MM>.xlsx`; the adapter then parses it with no network. Archive listing at <https://cea.nic.in/archives/?lang=en>; for per-state long history we fall back to ICED (which already exposes 11 years of CEA-published values) rather than back-filling the CEA archive directly.

## data.gov.in — Open Government Data Platform

**Search**: <https://www.data.gov.in/search?title=rbi&type=resources&sortby=_score>
**Resource page grammar**: `https://www.data.gov.in/resource/<slug>`
**API endpoint** (rate-limited demo key): `https://api.data.gov.in/resource/<uuid>?api-key=<key>&format=json&limit=N`

data.gov.in aggregates ministry-supplied datasets, most of which are **Rajya Sabha question dumps** (snapshots tabulating an answer to a specific parliamentary question). The public demo key (`579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b`) caps records at 10/request and 429s after a few pages; a production key requires SMS-OTP registration with PII (declined per user direction 2026-05-14). The working pattern (recon: 2026-05-14):

1. Find the resource on data.gov.in by search or `View More` link.
2. Open the resource page; click `Download` (CSV) — solve the captcha once.
3. Drop into `.runtime/raw/datagovin/<indicator-leaf>.csv`.
4. Pin the UUID + page URL in `backend/yen_gov/sources/datagovin_ogd/urls.py::KNOWN_RESOURCES`.
5. Add a parser entry in `parsers.py::SHIPPED_SPECS`; the adapter writes the indicator artifact.

Currently shipped: `fiscal/centre_transfers_gross` (RS Q1323/2023, FY17–FY23 actuals).

**Recon finding (2026-05-14, RBI search)**: the `?title=rbi` search returns mostly **bank-frauds, RBI-ombudsman-complaints, demonetised-note recovery, internal-debt snapshot** rows — Ministry-of-Finance answers tabulating RBI-reported counts in 3–7 year windows. They do NOT duplicate the canonical RBI long-series we want (Handbook of Statistics, gold reserves, State Finances Statement 8 long series); those live on `rbi.org.in` directly. Status logged as `skipped` in the registry (`data_gov_in.rbi_search_results`) with the rationale; promotion to `candidate` is a per-resource decision when one of them genuinely complements an RBI series.

## What does NOT belong in `sources[]`

(Recap — see [`docs/concepts/data-provenance.md`](../concepts/data-provenance.md) for the canonical rule.)

- **Reference materials a maintainer consulted by hand** — go in commit messages or `notes`, not `sources`.
- **Time-limited signed URLs** (`/eci-backend/public/api/download?url=...`) — persist the landing page URL instead.
- **Search-result pages or portal home pages** — persist the deepest URL the pipeline actually fetched.
- **Files under `.runtime/raw/`** — debug artifacts, not provenance (ADR-0003).

## See also

- [data-coverage-report.md](data-coverage-report.md) — what's actually loaded today, per indicator, with time spans, gaps, and next-step hints. Read this when you want to know *"have we got X yet, and how deep does it go?"*
- [`datasets/reference/in/upstream-sources.json`](../../datasets/reference/in/upstream-sources.json) — machine-readable peer of this doc; the canonical registry.
- [`datasets/schemas/upstream-sources.schema.json`](../../datasets/schemas/upstream-sources.schema.json) — registry schema (v1.0).
- [`docs/concepts/disclaimer.md`](../concepts/disclaimer.md) — user-facing disclaimer wording (boundaries are community-contributed, data is best-effort, etc.); rendered by the app's About page.
- [backend/sources-eci.md](../architecture/backend/sources-eci.md) — ECI results portal adapter conventions and authority hierarchy for past elections.
- [backend/sources-wikipedia.md](../architecture/backend/sources-wikipedia.md) — Wikipedia adapter scope.
- [backend/sources-rbi.md](../architecture/backend/sources-rbi.md) — RBI *State Finances* adapter contract, per-Statement → indicator mapping, recon procedure for new editions.
- [data-model.md](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle) — `status: complete` requires an ECI source.
- [`docs/concepts/data-provenance.md`](../concepts/data-provenance.md) — `sources[]` contract.
- [`docs/concepts/electoral-hierarchy.md`](../concepts/electoral-hierarchy.md) — what each source can authoritatively tell us about.
- [`docs/reference/identifiers.md`](identifiers.md) — `S22` ↔ display-code mapping (populated as recon confirms).
