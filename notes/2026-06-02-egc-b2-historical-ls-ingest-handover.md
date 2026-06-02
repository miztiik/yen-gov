# EGC-B2 historical Lok Sabha ingest - acquisition handover & STOP

**Date**: 2026-06-02
**Row**: EGC-B2 (plan `TODO/20260602-elections-experience-gap-closure-plan.md`)
**Status**: BLOCKED-on-handover (acquisition mechanism confirmed; source backend currently down; full ingest exceeds responsible single-session budget)
**Author agents**: Max (Indicator Scout) + Hans (Governance)
**Predecessor recon**: `notes/2026-06-02-eci-historical-ls-source-recon.md` (EGC-B1, PR #579)

---

## 1. Why this is a STOP, not a half-ingest

EGC-B2 ingests the 1999-2019 Lok Sabha constituency-wise (PC-grain) results. Per the EGC-B1
recon, **all five years (1999, 2004, 2009, 2014, 2019) land on the TCPD fallback arm** - ECI does
not publish pre-2024 LS constituency-wise data in a usable `.xls/.xlsx/.csv` form (PDF-only). The
signed-off acquisition path (Scope-change ledger, plan Section 4, option (a)) is therefore the TCPD
**Lok Dhaba** portal.

This row is an **external-fetch + per-year-verification-at-scale** boundary. Two facts make
auto-execution the wrong move right now:

1. **The Lok Dhaba data backend is currently returning `502 Bad Gateway` (nginx/1.17.5) across
   every data endpoint.** Verified live 2026-06-02 by driving the portal and by direct `POST`
   probes to both `/api/data/api/v1.0/DataDownload` and `/api/data/api/v1.0/getVizData` - both 502.
   No data can be pulled until the upstream recovers. (The portal HTML/React shell loads fine; only
   the data API is down.)
2. **The ingest is a multi-PR, per-year-verified effort** (identity, observations, rollups, writer,
   `ingest-eci-ls` CLI, honesty guards, per-year count tests, conditional schema bump). Each year
   needs eyes-on verification of NOTA presence, Telangana-under-AP filing, turnout/electors
   availability, and the 543-seat floor. Shipping a partial or unverified historical-election series
   would damage citizen trust more than waiting - the same judgement that gated the party-symbol
   batch (see `/memories/lessons.md`: STOP-AT-USER-JUDGMENT-BOUNDARY).

So: this note records the **confirmed acquisition mechanism** + a per-year operator checklist + the
honesty-guard contract, marks EGC-B2 `BLOCKED-on-handover`, and hands back to the user. The plan is
NOT marked complete.

---

## 2. Confirmed acquisition mechanism (verified live 2026-06-02)

Source portal: **TCPD Lok Dhaba** - `https://lokdhaba.ashoka.edu.in/browse-data?et=GE`

It is a **React SPA, portal-gated** - there is no static CSV URL. The browse form drives a backend
data API. Confirmed by inspecting the loaded JS bundle + driving the form:

- **URL param scheme**: `?et=GE&st=<StateName>&an=<assembly_no>`
  - `et=GE` -> General (Lok Sabha) Elections (vs `et=AE` Assembly).
  - `st=<StateName>` -> exact portal state label (e.g. `Bihar`, `Andhra Pradesh`; `All` = all states).
  - `an=<assembly_no>` -> the Lok Sabha number, NOT the calendar year. The portal UI mislabels these
    as "N Assembly (YYYY)" but the URL/data treat them as the GE term number. Mapping for the five
    target years:

    | GE year | `an` (term no.) | UI label shown |
    | --- | --- | --- |
    | 1999 | 13 | "13 Assembly (1999)" |
    | 2004 | 14 | "14 Assembly (2004)" |
    | 2009 | 15 | "15 Assembly (2009)" |
    | 2014 | 16 | "16 Assembly (2014)" |
    | 2019 | 17 | "17 Assembly (2019)" |

- **PC grain vs AC-segment grain**: the form's "Show AC segment wise results" checkbox MUST stay
  **UNCHECKED** to get PC-grain (543-seat constituency-wise) rows. Checked = AC-segment split
  (don't want; that is the lower-fidelity segment file the prior plan over-relied on).

- **Download endpoint** (from the JS bundle, `Constants.baseUrl + path`, `method: "POST"`):
  - `baseUrl = "https://lokdhaba.ashoka.edu.in/api"`
  - download path: `/data/api/v1.0/DataDownload`
  - full: `POST https://lokdhaba.ashoka.edu.in/api/data/api/v1.0/DataDownload`
  - related read endpoints in the same bundle: `/data/api/v1.0/getVizData`,
    `/data/api/v1.0/getMapYear`, `/data/api/v1.0/getMapYearParty`, `/data/api/v1.0/getVizLegend`,
    `/data/api/v1.0/getSearchResults`, `/data/api/v2.0/getDerivedData`.
  - Note: the bundle's `DataDownload` `fetch(...)` block appears commented out in the current
    build; the live "Download Data" button still routes through the same API host, which is what
    502s. The exact request body could not be captured because every call 502'd. **When the backend
    is back up, capture the precise POST body by driving the button with a network listener** (the
    form state is `{ electionType, stateName, assemblyNo[], showACsegment:false }`-shaped).

- **Operator path (UI)**: open the portal -> Election Type = General Elections -> State Name =
  `<state>` (or `All`) -> tick the year checkbox(es) -> leave "Show AC segment wise results"
  UNCHECKED -> click **Download Data**. When healthy this yields a CSV per the selection.

- **License**: TCPD Lok Dhaba data is academic-use; cite TCPD-Lok Dhaba as `source_id` (ECI-derived).
  Same provenance arm as the existing 2024 ingest's TCPD crosswalk.

---

## 3. Per-year operator checklist (run once the backend is healthy)

For EACH of {1999, 2004, 2009, 2014, 2019}:

1. Pull the PC-grain CSV (AC-segment toggle OFF) for `et=GE`, all states (`st=All`) at the year's
   `an` term number (table in s2). Save to a one-time prep area OUTSIDE the pipeline.
2. Convert any non-CSV artifact to CSV in the documented one-time prep step (CSV-only ingest
   contract: stdlib `csv` + DuckDB; NO `xlrd`/`pandas` in `backend`).
3. Verify the row universe: **distinct PC count must be the 543 elected universe** for a
   direct/full-coverage year; never 545 (the 543 elected + 2 nominated Anglo-Indian seats are NOT
   contested constituencies). If a year is only segment-sourced as a stopgap, assert the floor
   `>= 536` + a NAMED missing-seat allow-list - never silently drop seats.
4. Confirm column availability and record per-year in the source map:
   - NOTA column present? (only from 2014 GE onward; **NULL, not zero, for 1999/2004/2009**).
   - turnout/electors columns present? (TCPD segment files generally lack electors -> **turnout +
     electors NULL, never fabricated** for any year whose source lacks them).
   - postal votes column present/separated? (generally not separated -> do not fabricate a split).
5. Telangana handling: for pre-2014 years, Telangana constituencies are filed **under Andhra Pradesh**
   (state code AP). Emit them under AP with Telangana NULL (do not back-project the 2014 bifurcation).

---

## 4. Honesty-guard contract (carry verbatim into the ingest PRs)

These are mandatory (Hans + Max), copied from the EGC-B2 plan row so they cannot drift:

- `segment_approximate` boolean per observation row: `true` only for a year that is segment-sourced
  (grep-confirm whether this is a NEW observation field; if new, additive **MINOR** schema bump only).
- exactly one `methodology_breaks.parquet` row for the **2008 delimitation** (pre/post-2008 PC
  boundaries are not comparable; `delim_year` distinguishes them).
- NOTA **NULL (not zero)** pre-2013 (i.e. for 1999/2004/2009 GEs).
- Telangana-under-AP pre-2014: **NULL (not zero)**, filed under AP.
- turnout/electors **NULL (never fabricated)** for any year whose source lacks electors.
- per-`(year, delim_year)` **distinct-PC count assertion**: 543 elected universe for direct-sourced;
  floor `>= 536` + named missing-seat allow-list for any segment-sourced stopgap year; **never assert 545**.
- per-year `source_id` FK so the postal-inclusive/exclusive + electors-present/absent split is
  auditable from provenance alone.

Reuse the existing Model-C `pc-*` indicators (13) + `IN-PC-<delim_year>-<state_code>-<pc_no>` entity
scheme. **NO new indicator, NO new id grammar.**

---

## 5. Gates (per the EGC-B2 plan row)

- `python -m yen_gov validate --root .` on the touched family.
- per-year count-assertion test (543 floor; never 545).
- pre-flight-ingest exit 0.
- schema bump ONLY if `segment_approximate` is a new observation field (grep-confirm first; additive
  MINOR if so).

---

## 6. Clean-contract argument for stopping here

Everything upstream of the fetch is settled: the source family (TCPD/Lok Dhaba, ECI-derived) is
signed off (Scope-change ledger, plan Section 4); the indicator + entity grammar is reused unchanged;
the honesty guards are fully specified above. The ONLY blockers are (a) the source backend being
live, and (b) per-year operator verification that is unsafe to auto-run unattended at the
trust-sensitivity of national historical election results. Resuming is a clean pick-up: when Lok
Dhaba is back up, run s3 per year, apply s4 guards, ship the ingest PR(s) behind the s5 gates, then
stamp EGC-B2 DONE in the plan-doc. No rework of B1, no scope re-litigation.

**Do not mark the plan complete while EGC-B2 is BLOCKED.**
