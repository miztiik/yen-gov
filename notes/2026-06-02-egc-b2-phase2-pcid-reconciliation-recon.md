# EGC-B2 Phase 2 recon — historical LS (PC) ingest blocked on a constituency-identity crosswalk

**Date:** 2026-06-02
**Author:** autonomous agent (default)
**Scope:** EGC-B2 row of `docs/archive/plans/20260602-elections-experience-gap-closure-plan.md`
**Status:** Phase 1 SHIPPED (PR #603). Phase 2 (1999–2019 historical PC series) **STOPPED at a judgment boundary** — needs a user decision on how to identify historical constituencies before any ingest.

---

## 1. What already shipped (Phase 1, PR #603, on `main` at `a7da47f8`)

The unified person/candidacy model now supports Lok Sabha (PC) candidacies, and the **2024** general election is fully ingested into it:

- Schema `elections-candidacies` v1.1 → **v1.2** (MINOR, additive + relaxing): `ac_id` no longer required; new optional `pc_id` (`^IN-PC-\d{4}-[SU]\d{2}-\d+$`); `candidacy_key` pattern widened to accept `LsGen`/`LsBye` periods; `schema-compatibility.json` override `accepted_versions` now `["1.1","1.2"]`.
- `CandidacyRow` gains `pc_id` + an `@model_validator` enforcing **exactly one** of `ac_id`/`pc_id`.
- Adapter wiring (`pc_observations.persons_and_candidacies_from_pc`, `eci_ls.build_pc_envelope`) emits PC persons + candidacies; `identity.layer1_person_id_for_pc` added.
- **Result (verified via DuckDB):** 8,359 PC candidacies with `pc_id`; `dim_persons` +8,359 (387,813 → 396,172); 542 distinct `pc_id` (Surat uncontested in 2024 = real ECI characteristic). PC person metadata: 8,359 sex / 8,359 age / 0 education / 0 profession (ECI Report-33 lacks edu/prof — see §4).

This is a complete, correct increment. It is not half-coverage; 2024 is fully and correctly represented.

## 2. Why Phase 2 (1999–2019) stopped

The historical source is TCPD `All_States_GE.csv` (the `_GE` constituency file). Recon (this session) confirms it **does** carry electors / valid votes / turnout / sex / education / profession at PC grain for the in-scope years — so the earlier B1 "TCPD lacks electors/turnout" conclusion (which surveyed the wrong segment file) is **withdrawn**. The data is rich enough.

**The blocker is not data availability — it is constituency *identity*.** A canonical `pc_id` (`IN-PC-<delim>-<state>-<no>`) is the join key the browser uses to assemble a constituency's history. For 1999–2019 there is **no automatic rule** that produces correct `pc_id`s, because India reorganized states and renumbered seats between these elections:

### 2a. Andhra Pradesh ↔ Telangana (2014 bifurcation) — *unavoidable wrong-join*
- 2009 & 2014 GE: **undivided AP**, 42 seats, all under TCPD `Andhra_Pradesh`, both DelimID 4 (2008 delimitation).
- 2019 & 2024 GE: **split** — residual AP 25 seats (S01) + Telangana 17 seats (S29).
- Both eras are the *same* 2008 delimitation (DelimID 4), so delim_year cannot distinguish them. Seat **#1** means **Adilabad (now Telangana)** in 2009/2014 but **Araku (residual AP)** in 2019/2024. Minting `IN-PC-2008-S01-1` for both **conflates two different physical constituencies** — a citizen would see Adilabad's history on Araku's page.

### 2b. Jammu & Kashmir (2019 UT reorganization)
- 2019 GE (May): J&K still a **state (S09)**, 6 seats including Ladakh.
- 2024 GE: J&K is **UT U08** (5 seats) + **Ladakh U09** (1 seat).
- The May-2019 election predates the Oct-2019 reorganization, so 2019 seats are S09-numbered; 2024 are U08/U09-numbered. No automatic bridge.

### 2c. 2000 state trifurcations (affects 1999)
- 1999 GE: 32 states. Chhattisgarh, Jharkhand, Uttarakhand did **not exist** (created Nov 2000), so their seats sit inside **Madhya Pradesh / Bihar / Uttar Pradesh** under 1976-delim numbering.
- 2004 onward: 35 states with the new entities.

### 2d. Merged UTs (Dadra & Nagar Haveli + Daman & Diu → U03 in 2020)
- TCPD lists `Dadra_&_Nagar_Haveli` (1 seat, Constituency_No 1) and `Daman_&_Diu` (1 seat, Constituency_No 1) separately for 1999–2019.
- 2024 canonical merges them into **U03** with pc_no 1 & 2.
- `entities.json` does have historical codes `U03-OLD` and `U06`, **but** the `pc_id` regex `[SU]\d{2}` rejects `U03-OLD` (hyphen + letters). Historical DNH/DD cannot mint a schema-valid `pc_id` without either a new code convention or a deliberate DNH→U03-pc1 / DD→U03-pc2 mapping.

### 2e. Two delimitations
- 1999, 2004 = DelimID 3 → **1976 delimitation**. 2009, 2014, 2019 = DelimID 4 → **2008 delimitation**. (Clean and automatic; this part is fine. It is the *within-delim* reorganizations above that break.)

**Every in-scope year has at least one reorganization edge case. There is no fully-clean year.** An automatic ingest would either (a) silently mis-join (2a/2b), or (b) ship only the clean states and flag the rest (half-coverage). Both damage trust more than waiting. Hence the stop.

## 3. Decision needed from the user — pick a constituency-identity policy

1. **Author an explicit historical PC crosswalk** (recommended for correctness): a small curated table mapping each (year, TCPD state, TCPD Constituency_No) → canonical `(delim_year, state_code, pc_no)`, encoding the AP/TG, J&K, 2000-splits, and DNH/DD merges by hand. Highest fidelity; needs domain sign-off (Hans). Effort: the messy cases are ~42 AP seats × 2 years + 6 J&K + 2 DNH/DD + the 1999 MP/Bihar/UP splits — bounded and reviewable.
2. **Era-scoped identity** — treat each (delim_year + contemporaneous state numbering) as its own entity and **do not promise cross-era continuity**; surface a "constituency boundaries/identity changed" methodology break at 2008 (and note AP/J&K splits). Avoids wrong joins by *not joining*; costs the seamless "one seat through time" story for reorganized seats. Still needs the DNH/DD code question resolved (§2d).
3. **Defer the conflicted states only** — ship the cleanly-mappable states/years now, hold AP/Telangana, J&K, and the 2000-split states until (1) is authored. This is the half-coverage path; flagged here only for completeness — not recommended for election data.

## 4. Other Phase-2 notes (already designed, ready once §3 is decided)

- **Provenance tension to surface in the PR:** profession/education are TCPD-only fields, but the EGC-B2 provenance decision collapses to a single domain-level (ECI) `source_id`. Those TCPD-only fields will therefore carry the ECI/domain `source_id` — must be flagged in the PR body and docs.
- **Metadata coverage by year** (TCPD GE): edu/prof absent in 1999, ~52%/58% in 2004, ~85%+ in 2009–2019; sex ~94–100%; electors/valid/turnout 100%. age is **not** in TCPD GE (NULL for all historical). All map to nullable/optional fields — no schema change beyond Phase 1.
- **Honesty guards already planned:** NOTA NULL pre-2014 (confirmed: first NOTA rows appear 2014, 543 of them); one `methodology_breaks.parquet` row for the 2008 delimitation; per-(year,delim_year) distinct-PC assertion with a **543 floor** (never 545); per-year `source_id` FK; bypoll rows (`Poll_No != 0` / blank month) excluded.
- **Parser shape (ready to build):** mirror `eci_ae_panel.py`; filter `Election_Type == "Lok Sabha Election (GE)"`; group by (year, month) → Period (months: 1999→Sep, 2004–2019→Apr); use TCPD `Constituency_No` as pc_no (no ECI crosswalk needed); read `Sex`/`MyNeta_education`/`TCPD_Prof_Main`. Two small code prerequisites: extend `PcCandidateRaw` (in `ls_constituencywise.py`) with optional `education`/`profession`; change `persons_and_candidacies_from_pc` to read them instead of hardcoded `None`. Generalize `eci_ls.build_pc_envelope` off the hardcoded `LS_2024_EVENT`/`LS_2024_DELIM_YEAR` to a multi-year driver.

## 5. Plan-doc status

EGC-B2 stays **BLOCKED** (not DONE) — refined blocker is now "needs a constituency-identity crosswalk decision (this note §3)", superseding the earlier (incorrect) "TCPD lacks electors/turnout" blocker. Phase 1 (2024 unified-model support) is delivered under PR #603. EGC-A (#582/#583), EGC-B1 (#579), EGC-C (#588) remain DONE.
