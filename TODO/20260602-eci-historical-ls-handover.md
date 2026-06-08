# EGC-B2 historical Lok Sabha PC ingest — handover (paused)

**Last Updated**: 2026-06-08

**Status**: BLOCKED — pre-existing handover material lifted into this consolidated sub-plan from `notes/` during the G4 closure of the working-docs split. Phase 1 (2024 unified-model PC support) shipped on `main` via PR #603. Phase 2 (1999-2019 historical PC series) STOPPED at a constituency-identity policy decision (see section 3 below).

| Row | Status | What it documents |
| --- | --- | --- |
| LSH-B1 | DONE 2026-06-02 | Per-year source-availability recon (lifted below). Verdict: ECI does NOT publish pre-2024 LS constituency-wise files; all five target years (1999, 2004, 2009, 2014, 2019) land on the TCPD/Lok Dhaba fallback arm. |
| LSH-B2-handover | DONE 2026-06-02 | Acquisition mechanism for the TCPD Lok Dhaba portal verified live; per-year operator checklist + honesty-guard contract recorded (lifted below). |
| LSH-B2-blocker | BLOCKED on user decision | Constituency-identity crosswalk needed before any historical PC ingest can ship cleanly. Three options enumerated in section 3 below. |

**Back-pointers**:

- Master direction (the rip-and-refill plan that supersedes the original EGC plan-doc): [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md).
- Archived original plan: [docs/archive/plans/20260602-elections-experience-gap-closure-plan.md](../docs/archive/plans/20260602-elections-experience-gap-closure-plan.md).
- Phase 1 (2024) shipped via PR #603 on `main` at SHA `a7da47f8`; schema bump `elections-candidacies` v1.1 -> v1.2 (additive optional `pc_id`).

This sub-plan exists so the historical PC ingest can be picked up cleanly under the rip-and-refill direction without re-deriving the source map, the acquisition mechanism, or the constituency-identity blocker.

---

## 1. EGC-B1: per-year source recon (lifted from `notes/2026-06-02-eci-historical-ls-source-recon.md`)

> Historical receipt lifted on 2026-06-08 (G4 closure). User sign-off recorded in the archived plan-doc Scope-change ledger: ingest direct ECI where ECI publishes a usable constituency-wise file; fall back to TCPD (Lok Dhaba) for years ECI does not. `All_States_GA.csv` (TCPD AC-segment-wise) stays a crosswalk, never the ingest source.

### Headline verdict

**ECI does NOT publish pre-2024 Lok Sabha constituency-wise results as xls/xlsx/csv.** For 1999, 2004, 2009, 2014 and 2019 the only durable ECI resource is the "Full Statistical Report" PDF (1999/2004/2009 are multi-volume Vol I/II/III PDFs; 2014 and 2019 likewise PDF). The machine-readable "33 - Constituency-Wise Detailed Result" CSV exists only for the 2024 cycle on `results.eci.gov.in`, a current-cycle resource with no prior-year equivalent. The user's belief is confirmed. **All five target years land on the TCPD-fallback arm.**

### Per-year source map

| year | best source | dataset / file + URL | format | electors? | postal? | grain | pc-* indicators yielded |
|------|-------------|----------------------|--------|-----------|---------|-------|--------------------------|
| 1999 | TCPD-fallback | Lok Dhaba GE constituency-level, `https://lokdhaba.ashoka.edu.in/browse-data?et=GE` (GE, year 1999, AC-segment toggle OFF). ECI alt is PDF-only: Statistical Report 1999 Vol I/II/III via `https://www.eci.gov.in/statistical-reports`. | csv (portal); ECI = pdf-only | yes | no | PC-level (543) directly | votes, vote-share, margin, turnout-pct, total-electors. NOTA = NULL. |
| 2004 | TCPD-fallback | Lok Dhaba GE, same portal, year 2004. ECI alt PDF-only: Statistical Report 2004 Vol I/II/III. | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors. NOTA = NULL. |
| 2009 | TCPD-fallback | Lok Dhaba GE, same portal, year 2009. ECI alt PDF-only: Statistical Report 2009 Vol I/II/III. | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors. NOTA = NULL. First post-2008-delimitation PCs. |
| 2014 | TCPD-fallback | Lok Dhaba GE, same portal, year 2014. ECI alt PDF-only: Statistical Report 2014. data.gov.in mirror unconfirmed (see follow-ups). | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors, **NOTA (from 2014)**. |
| 2019 | TCPD-fallback | Lok Dhaba GE, same portal, year 2019. ECI alt PDF-only: Statistical Report 2019 (Including / Excluding Vellore PC). Durable ECI CSV not found (2019 results.eci.gov.in recycled for current cycle). | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors, **NOTA**. |

### TCPD canonical dataset

**Lok Dhaba** (TCPD-IED, "TCPD Indian Elections Data"), General Election (`et=GE`) constituency-level tables, coverage 1962-2019 (and 2024). ECI-derived (cleaned and tabularised from ECI statistical reports). Provides **PC-level** results directly (543 seats) when the "Show AC segment wise results" toggle is OFF, and carries **Electors and turnout** per constituency. NOTA appears as a candidate row only from 2014. Postal votes are NOT separated (per-candidate Votes are combined EVM+postal). Licence: free for any use.

Required citation: *Ananay Agarwal, Neelesh Agrawal, Saloni Bhogale, Sudheendra Hangal, Francesca Refsum Jensenius, Mohit Kumar, Chinmay Narayan, Basim U Nissa, Priyamvada Trivedi, and Gilles Verniers. 2021. "TCPD Indian Elections Data v2.0", Trivedi Centre for Political Data, Ashoka University.*

Download mechanism: **portal-gated, not a static CSV URL** - `https://lokdhaba.ashoka.edu.in/browse-data?et=GE`, select GE + state + year with AC-segment toggle OFF, then download. Requires the integrated browser to fetch. The GitHub path `ashokayan/TCPD` the user cited returns 404; the canonical product is the Lok Dhaba web portal. Codebook: `https://lokdhaba.ashoka.edu.in/static/media/2022Feb12LokDhabaCodebook.pdf`.

### Per-year honesty caveats (must carry into EGC-B2 ingest)

- **NOTA**: introduced by the Supreme Court order of Sept 2013; first Lok Sabha GE with NOTA was 2014. The NOTA pc-* indicator is NULL for 1999/2004/2009, present for 2014/2019.
- **2008 delimitation**: PC boundaries changed under the 2008 Delimitation Order. 1999/2004 PCs use the old (pre-2008) delimitation; 2009 onward use the current delimitation. Margin/turnout series across the 2009 boundary are not like-for-like at the constituency level and need a `methodology_breaks` annotation (Hans framing).
- **Telangana**: not a separate state until 2 Jun 2014. For 1999/2004/2009 all 17 Telangana-region PCs are filed under Andhra Pradesh; the 2014 GE was the bifurcation election itself. Entity-id assignment for pre-2014 Telangana PCs needs an explicit rule (Hans/Gregor) - the `IN-PC-<delim_year>-<state_code>-<pc_no>` scheme must file them under the AP state code for those years.

### Open follow-ups (deferred to EGC-B2)

- Verify whether `data.gov.in` (Open Government Data Platform India) hosts an ECI-published constituency-wise CSV for 2014 and/or 2019. If a stable, ECI-sourced CSV exists there, those two years could flip to ECI-direct. **Unconfirmed - do not assume.**
- Confirm the exact Lok Dhaba CSV download endpoint/payload by driving the browse-data portal in the integrated browser (capture the network request) so the ingest can be scripted rather than hand-clicked.
- Postal-votes pc-* indicators have no source short of ECI Form-20 PDF tables (out of scope per re-curation-not-digitisation rule); leave NULL.

### Handoff for EGC-B2 (ingest)

- All five years acquire via TCPD-fallback / Lok Dhaba, browser-driven download, AC-segment toggle OFF for PC grain.
- Reuse existing 13 `pc-*` indicators + existing `IN-PC-<delim_year>-<state_code>-<pc_no>` entity scheme. NO new id grammar.
- Convert any non-CSV download to CSV in a one-time documented prep step OUTSIDE the pipeline (CSV-only ingest contract; no xlrd/pandas).
- Honesty guards: NOTA null pre-2014; 2008 methodology_breaks row; Telangana-under-AP for pre-2014; per-(year, delim_year) distinct-PC count assertion (543 floor; never 545).

---

## 2. EGC-B2 acquisition mechanism + operator checklist (lifted from `notes/2026-06-02-egc-b2-historical-ls-ingest-handover.md`)

> Historical receipt lifted on 2026-06-08 (G4 closure). Author agents: Max (Indicator Scout) + Hans (Governance). Predecessor recon: section 1 above.

### Why this is a STOP, not a half-ingest

EGC-B2 ingests the 1999-2019 Lok Sabha constituency-wise (PC-grain) results. Per the EGC-B1 recon, **all five years (1999, 2004, 2009, 2014, 2019) land on the TCPD fallback arm** - ECI does not publish pre-2024 LS constituency-wise data in a usable `.xls/.xlsx/.csv` form (PDF-only). The signed-off acquisition path (Scope-change ledger, archived plan Section 4, option (a)) is therefore the TCPD **Lok Dhaba** portal.

This row is an **external-fetch + per-year-verification-at-scale** boundary. Two facts make auto-execution the wrong move:

1. **The Lok Dhaba data backend was returning `502 Bad Gateway` (nginx/1.17.5) across every data endpoint** at probe time (2026-06-02). Verified live by driving the portal and by direct `POST` probes to both `/api/data/api/v1.0/DataDownload` and `/api/data/api/v1.0/getVizData` - both 502. No data can be pulled until the upstream recovers. (The portal HTML/React shell loaded fine; only the data API was down. Re-probe is the first step of any pickup.)
2. **The ingest is a multi-PR, per-year-verified effort** (identity, observations, rollups, writer, `ingest-eci-ls` CLI, honesty guards, per-year count tests, conditional schema bump). Each year needs eyes-on verification of NOTA presence, Telangana-under-AP filing, turnout/electors availability, and the 543-seat floor. Shipping a partial or unverified historical-election series would damage citizen trust more than waiting - the same judgement that gated the party-symbol batch (see `/memories/lessons.md`: STOP-AT-USER-JUDGMENT-BOUNDARY).

So: this section records the **confirmed acquisition mechanism** + a per-year operator checklist + the honesty-guard contract, marks EGC-B2 `BLOCKED-on-handover`, and hands back to the user. The plan is NOT marked complete.

### Confirmed acquisition mechanism (verified live 2026-06-02)

Source portal: **TCPD Lok Dhaba** - `https://lokdhaba.ashoka.edu.in/browse-data?et=GE`

It is a **React SPA, portal-gated** - there is no static CSV URL. The browse form drives a backend data API. Confirmed by inspecting the loaded JS bundle + driving the form:

- **URL param scheme**: `?et=GE&st=<StateName>&an=<assembly_no>`
  - `et=GE` -> General (Lok Sabha) Elections (vs `et=AE` Assembly).
  - `st=<StateName>` -> exact portal state label (e.g. `Bihar`, `Andhra Pradesh`; `All` = all states).
  - `an=<assembly_no>` -> the Lok Sabha number, NOT the calendar year. The portal UI mislabels these as "N Assembly (YYYY)" but the URL/data treat them as the GE term number. Mapping for the five target years:

    | GE year | `an` (term no.) | UI label shown |
    | --- | --- | --- |
    | 1999 | 13 | "13 Assembly (1999)" |
    | 2004 | 14 | "14 Assembly (2004)" |
    | 2009 | 15 | "15 Assembly (2009)" |
    | 2014 | 16 | "16 Assembly (2014)" |
    | 2019 | 17 | "17 Assembly (2019)" |

- **PC grain vs AC-segment grain**: the form's "Show AC segment wise results" checkbox MUST stay **UNCHECKED** to get PC-grain (543-seat constituency-wise) rows. Checked = AC-segment split (don't want; that is the lower-fidelity segment file the prior plan over-relied on).

- **Download endpoint** (from the JS bundle, `Constants.baseUrl + path`, `method: "POST"`):
  - `baseUrl = "https://lokdhaba.ashoka.edu.in/api"`
  - download path: `/data/api/v1.0/DataDownload`
  - full: `POST https://lokdhaba.ashoka.edu.in/api/data/api/v1.0/DataDownload`
  - related read endpoints in the same bundle: `/data/api/v1.0/getVizData`, `/data/api/v1.0/getMapYear`, `/data/api/v1.0/getMapYearParty`, `/data/api/v1.0/getVizLegend`, `/data/api/v1.0/getSearchResults`, `/data/api/v2.0/getDerivedData`.
  - Note: the bundle's `DataDownload` `fetch(...)` block appears commented out in the current build; the live "Download Data" button still routes through the same API host. When the backend is back up, capture the precise POST body by driving the button with a network listener (the form state is `{ electionType, stateName, assemblyNo[], showACsegment:false }`-shaped).

- **Operator path (UI)**: open the portal -> Election Type = General Elections -> State Name = `<state>` (or `All`) -> tick the year checkbox(es) -> leave "Show AC segment wise results" UNCHECKED -> click **Download Data**. When healthy this yields a CSV per the selection.

- **License**: TCPD Lok Dhaba data is academic-use; cite TCPD-Lok Dhaba as `source_id` (ECI-derived). Same provenance arm as the existing 2024 ingest's TCPD crosswalk.

### Per-year operator checklist (run once the backend is healthy)

For EACH of {1999, 2004, 2009, 2014, 2019}:

1. Pull the PC-grain CSV (AC-segment toggle OFF) for `et=GE`, all states (`st=All`) at the year's `an` term number (table above). Save to a one-time prep area OUTSIDE the pipeline.
2. Convert any non-CSV artifact to CSV in the documented one-time prep step (CSV-only ingest contract: stdlib `csv` + DuckDB; NO `xlrd`/`pandas` in `backend`).
3. Verify the row universe: **distinct PC count must be the 543 elected universe** for a direct/full-coverage year; never 545 (the 543 elected + 2 nominated Anglo-Indian seats are NOT contested constituencies). If a year is only segment-sourced as a stopgap, assert the floor `>= 536` + a NAMED missing-seat allow-list - never silently drop seats.
4. Confirm column availability and record per-year in the source map:
   - NOTA column present? (only from 2014 GE onward; **NULL, not zero, for 1999/2004/2009**).
   - turnout/electors columns present? (TCPD segment files generally lack electors -> **turnout + electors NULL, never fabricated** for any year whose source lacks them).
   - postal votes column present/separated? (generally not separated -> do not fabricate a split).
5. Telangana handling: for pre-2014 years, Telangana constituencies are filed **under Andhra Pradesh** (state code AP). Emit them under AP with Telangana NULL (do not back-project the 2014 bifurcation).

### Honesty-guard contract (carry verbatim into the ingest PRs)

These are mandatory (Hans + Max):

- `segment_approximate` boolean per observation row: `true` only for a year that is segment-sourced (grep-confirm whether this is a NEW observation field; if new, additive **MINOR** schema bump only).
- exactly one `methodology_breaks.parquet` row for the **2008 delimitation** (pre/post-2008 PC boundaries are not comparable; `delim_year` distinguishes them).
- NOTA **NULL (not zero)** pre-2013 (i.e. for 1999/2004/2009 GEs).
- Telangana-under-AP pre-2014: **NULL (not zero)**, filed under AP.
- turnout/electors **NULL (never fabricated)** for any year whose source lacks electors.
- per-`(year, delim_year)` **distinct-PC count assertion**: 543 elected universe for direct-sourced; floor `>= 536` + named missing-seat allow-list for any segment-sourced stopgap year; **never assert 545**.
- per-year `source_id` FK so the postal-inclusive/exclusive + electors-present/absent split is auditable from provenance alone.

Reuse the existing Model-C `pc-*` indicators (13) + `IN-PC-<delim_year>-<state_code>-<pc_no>` entity scheme. **NO new indicator, NO new id grammar.**

### Gates (per the original EGC-B2 plan row)

- `python -m yen_gov validate --root .` on the touched family.
- per-year count-assertion test (543 floor; never 545).
- pre-flight-ingest exit 0.
- schema bump ONLY if `segment_approximate` is a new observation field (grep-confirm first; additive MINOR if so).

### Clean-contract argument for stopping here

Everything upstream of the fetch is settled: the source family (TCPD/Lok Dhaba, ECI-derived) is signed off (archived plan Scope-change ledger); the indicator + entity grammar is reused unchanged; the honesty guards are fully specified. The ONLY blockers are (a) the source backend being live, and (b) per-year operator verification that is unsafe to auto-run unattended at the trust-sensitivity of national historical election results. Resuming is a clean pick-up: when Lok Dhaba is back up, run the per-year checklist, apply the honesty guards, ship the ingest PR(s) behind the gates, then stamp EGC-B2 DONE. No rework of B1, no scope re-litigation.

---

## 3. EGC-B2 Phase 2 blocker: constituency-identity decision needed (lifted from `notes/2026-06-02-egc-b2-phase2-pcid-reconciliation-recon.md`)

> Historical receipt lifted on 2026-06-08 (G4 closure). Author: autonomous agent (default). Phase 1 (2024 unified-model PC support) SHIPPED via PR #603; Phase 2 (1999-2019 historical PC series) **STOPPED at a judgment boundary** - needs a user decision on how to identify historical constituencies before any ingest.

### What already shipped (Phase 1, PR #603, on `main` at `a7da47f8`)

The unified person/candidacy model now supports Lok Sabha (PC) candidacies, and the **2024** general election is fully ingested into it:

- Schema `elections-candidacies` v1.1 -> **v1.2** (MINOR, additive + relaxing): `ac_id` no longer required; new optional `pc_id` (`^IN-PC-\d{4}-[SU]\d{2}-\d+$`); `candidacy_key` pattern widened to accept `LsGen`/`LsBye` periods; `schema-compatibility.json` override `accepted_versions` now `["1.1","1.2"]`.
- `CandidacyRow` gains `pc_id` + an `@model_validator` enforcing **exactly one** of `ac_id`/`pc_id`.
- Adapter wiring (`pc_observations.persons_and_candidacies_from_pc`, `eci_ls.build_pc_envelope`) emits PC persons + candidacies; `identity.layer1_person_id_for_pc` added.
- **Result (verified via DuckDB):** 8,359 PC candidacies with `pc_id`; `dim_persons` +8,359 (387,813 -> 396,172); 542 distinct `pc_id` (Surat uncontested in 2024 = real ECI characteristic). PC person metadata: 8,359 sex / 8,359 age / 0 education / 0 profession (ECI Report-33 lacks edu/prof — see section 4).

This is a complete, correct increment. It is not half-coverage; 2024 is fully and correctly represented.

### Why Phase 2 (1999-2019) stopped

The historical source is TCPD `All_States_GE.csv` (the `_GE` constituency file). Recon (this session) confirms it **does** carry electors / valid votes / turnout / sex / education / profession at PC grain for the in-scope years - so the earlier B1 "TCPD lacks electors/turnout" conclusion (which surveyed the wrong segment file) is **withdrawn**. The data is rich enough.

**The blocker is not data availability - it is constituency *identity*.** A canonical `pc_id` (`IN-PC-<delim>-<state>-<no>`) is the join key the browser uses to assemble a constituency's history. For 1999-2019 there is **no automatic rule** that produces correct `pc_id`s, because India reorganized states and renumbered seats between these elections:

#### 3a. Andhra Pradesh <-> Telangana (2014 bifurcation) — *unavoidable wrong-join*
- 2009 & 2014 GE: **undivided AP**, 42 seats, all under TCPD `Andhra_Pradesh`, both DelimID 4 (2008 delimitation).
- 2019 & 2024 GE: **split** — residual AP 25 seats (S01) + Telangana 17 seats (S29).
- Both eras are the *same* 2008 delimitation (DelimID 4), so delim_year cannot distinguish them. Seat **#1** means **Adilabad (now Telangana)** in 2009/2014 but **Araku (residual AP)** in 2019/2024. Minting `IN-PC-2008-S01-1` for both **conflates two different physical constituencies** — a citizen would see Adilabad's history on Araku's page.

#### 3b. Jammu & Kashmir (2019 UT reorganization)
- 2019 GE (May): J&K still a **state (S09)**, 6 seats including Ladakh.
- 2024 GE: J&K is **UT U08** (5 seats) + **Ladakh U09** (1 seat).
- The May-2019 election predates the Oct-2019 reorganization, so 2019 seats are S09-numbered; 2024 are U08/U09-numbered. No automatic bridge.

#### 3c. 2000 state trifurcations (affects 1999)
- 1999 GE: 32 states. Chhattisgarh, Jharkhand, Uttarakhand did **not exist** (created Nov 2000), so their seats sit inside **Madhya Pradesh / Bihar / Uttar Pradesh** under 1976-delim numbering.
- 2004 onward: 35 states with the new entities.

#### 3d. Merged UTs (Dadra & Nagar Haveli + Daman & Diu -> U03 in 2020)
- TCPD lists `Dadra_&_Nagar_Haveli` (1 seat, Constituency_No 1) and `Daman_&_Diu` (1 seat, Constituency_No 1) separately for 1999-2019.
- 2024 canonical merges them into **U03** with pc_no 1 & 2.
- `entities.json` does have historical codes `U03-OLD` and `U06`, **but** the `pc_id` regex `[SU]\d{2}` rejects `U03-OLD` (hyphen + letters). Historical DNH/DD cannot mint a schema-valid `pc_id` without either a new code convention or a deliberate DNH->U03-pc1 / DD->U03-pc2 mapping.

#### 3e. Two delimitations
- 1999, 2004 = DelimID 3 -> **1976 delimitation**. 2009, 2014, 2019 = DelimID 4 -> **2008 delimitation**. (Clean and automatic; this part is fine. It is the *within-delim* reorganizations above that break.)

**Every in-scope year has at least one reorganization edge case. There is no fully-clean year.** An automatic ingest would either (a) silently mis-join (3a/3b), or (b) ship only the clean states and flag the rest (half-coverage). Both damage trust more than waiting. Hence the stop.

### Decision needed from the user — pick a constituency-identity policy

1. **Author an explicit historical PC crosswalk** (recommended for correctness): a small curated table mapping each (year, TCPD state, TCPD Constituency_No) -> canonical `(delim_year, state_code, pc_no)`, encoding the AP/TG, J&K, 2000-splits, and DNH/DD merges by hand. Highest fidelity; needs domain sign-off (Hans). Effort: the messy cases are ~42 AP seats x 2 years + 6 J&K + 2 DNH/DD + the 1999 MP/Bihar/UP splits — bounded and reviewable.
2. **Era-scoped identity** — treat each (delim_year + contemporaneous state numbering) as its own entity and **do not promise cross-era continuity**; surface a "constituency boundaries/identity changed" methodology break at 2008 (and note AP/J&K splits). Avoids wrong joins by *not joining*; costs the seamless "one seat through time" story for reorganized seats. Still needs the DNH/DD code question resolved (3d above).
3. **Defer the conflicted states only** — ship the cleanly-mappable states/years now, hold AP/Telangana, J&K, and the 2000-split states until (1) is authored. This is the half-coverage path; flagged here only for completeness — not recommended for election data.

### 4. Other Phase-2 notes (already designed, ready once section 3 is decided)

- **Provenance tension to surface in the PR:** profession/education are TCPD-only fields, but the EGC-B2 provenance decision collapses to a single domain-level (ECI) `source_id`. Those TCPD-only fields will therefore carry the ECI/domain `source_id` — must be flagged in the PR body and docs.
- **Metadata coverage by year** (TCPD GE): edu/prof absent in 1999, ~52%/58% in 2004, ~85%+ in 2009-2019; sex ~94-100%; electors/valid/turnout 100%. age is **not** in TCPD GE (NULL for all historical). All map to nullable/optional fields — no schema change beyond Phase 1.
- **Honesty guards already planned:** NOTA NULL pre-2014 (confirmed: first NOTA rows appear 2014, 543 of them); one `methodology_breaks.parquet` row for the 2008 delimitation; per-(year,delim_year) distinct-PC assertion with a **543 floor** (never 545); per-year `source_id` FK; bypoll rows (`Poll_No != 0` / blank month) excluded.
- **Parser shape (ready to build):** mirror `eci_ae_panel.py`; filter `Election_Type == "Lok Sabha Election (GE)"`; group by (year, month) -> Period (months: 1999->Sep, 2004-2019->Apr); use TCPD `Constituency_No` as pc_no (no ECI crosswalk needed); read `Sex`/`MyNeta_education`/`TCPD_Prof_Main`. Two small code prerequisites: extend `PcCandidateRaw` (in `ls_constituencywise.py`) with optional `education`/`profession`; change `persons_and_candidacies_from_pc` to read them instead of hardcoded `None`. Generalize `eci_ls.build_pc_envelope` off the hardcoded `LS_2024_EVENT`/`LS_2024_DELIM_YEAR` to a multi-year driver.

### 5. Status (rip-and-refill direction)

Under the master rip-and-refill plan ([TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md)) the election arm is being repaired (section 10 W3 + section 1 O6 "psephology lab has to be fixed"). When the historical PC ingest is revived on the new long-format CSV foundation, the user-decision in section 3 above is the first gating step; sections 1 and 2 above remain the ingest contract.

EGC-B2 stays **BLOCKED** (not DONE). EGC-A (#582/#583), EGC-B1 (#579), EGC-C (#588) remain DONE in the archived plan.
