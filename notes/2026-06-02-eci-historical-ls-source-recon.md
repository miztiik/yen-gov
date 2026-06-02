# EGC-B1: Historical Lok Sabha (1999-2019) source recon

Last Updated: 2026-06-02

Recon for Lane B of [TODO/20260602-elections-experience-gap-closure-plan.md](../TODO/20260602-elections-experience-gap-closure-plan.md). Decides, per general-election year, whether the constituency-wise (PC-grain) result lands on the **ECI-direct** arm or the **TCPD-fallback** arm. User sign-off recorded in the plan-doc Scope-change ledger: ingest direct ECI where ECI publishes a usable constituency-wise file; fall back to TCPD (Lok Dhaba) for years ECI does not. `All_States_GA.csv` (TCPD AC-segment-wise) stays a crosswalk, never the ingest source.

See also: [docs/architecture/decisions/0048-elections-drill-ia.md](../docs/architecture/decisions/0048-elections-drill-ia.md), [docs/concepts/data-provenance.md](../docs/concepts/data-provenance.md), [TODO/20260602-elections-experience-gap-closure-plan.md](../TODO/20260602-elections-experience-gap-closure-plan.md).

## Headline verdict

**ECI does NOT publish pre-2024 Lok Sabha constituency-wise results as xls/xlsx/csv.** For 1999, 2004, 2009, 2014 and 2019 the only durable ECI resource is the "Full Statistical Report" PDF (1999/2004/2009 are multi-volume Vol I/II/III PDFs; 2014 and 2019 likewise PDF). The machine-readable "33 - Constituency-Wise Detailed Result" CSV exists only for the 2024 cycle on `results.eci.gov.in`, a current-cycle resource with no prior-year equivalent. The user's belief is confirmed. **All five target years land on the TCPD-fallback arm.**

## Per-year source map

| year | best source | dataset / file + URL | format | electors? | postal? | grain | pc-* indicators yielded |
|------|-------------|----------------------|--------|-----------|---------|-------|--------------------------|
| 1999 | TCPD-fallback | Lok Dhaba GE constituency-level, `https://lokdhaba.ashoka.edu.in/browse-data?et=GE` (GE, year 1999, AC-segment toggle OFF). ECI alt is PDF-only: Statistical Report 1999 Vol I/II/III via `https://www.eci.gov.in/statistical-reports`. | csv (portal); ECI = pdf-only | yes | no | PC-level (543) directly | votes, vote-share, margin, turnout-pct, total-electors. NOTA = NULL. |
| 2004 | TCPD-fallback | Lok Dhaba GE, same portal, year 2004. ECI alt PDF-only: Statistical Report 2004 Vol I/II/III. | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors. NOTA = NULL. |
| 2009 | TCPD-fallback | Lok Dhaba GE, same portal, year 2009. ECI alt PDF-only: Statistical Report 2009 Vol I/II/III. | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors. NOTA = NULL. First post-2008-delimitation PCs. |
| 2014 | TCPD-fallback | Lok Dhaba GE, same portal, year 2014. ECI alt PDF-only: Statistical Report 2014. data.gov.in mirror unconfirmed (see follow-ups). | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors, **NOTA (from 2014)**. |
| 2019 | TCPD-fallback | Lok Dhaba GE, same portal, year 2019. ECI alt PDF-only: Statistical Report 2019 (Including / Excluding Vellore PC). Durable ECI CSV not found (2019 results.eci.gov.in recycled for current cycle). | csv (portal); ECI = pdf-only | yes | no | PC-level directly | votes, vote-share, margin, turnout-pct, total-electors, **NOTA**. |

## TCPD canonical dataset

**Lok Dhaba** (TCPD-IED, "TCPD Indian Elections Data"), General Election (`et=GE`) constituency-level tables, coverage 1962-2019 (and 2024). ECI-derived (cleaned and tabularised from ECI statistical reports). Provides **PC-level** results directly (543 seats) when the "Show AC segment wise results" toggle is OFF, and carries **Electors and turnout** per constituency. NOTA appears as a candidate row only from 2014. Postal votes are NOT separated (per-candidate Votes are combined EVM+postal). Licence: free for any use.

Required citation: *Ananay Agarwal, Neelesh Agrawal, Saloni Bhogale, Sudheendra Hangal, Francesca Refsum Jensenius, Mohit Kumar, Chinmay Narayan, Basim U Nissa, Priyamvada Trivedi, and Gilles Verniers. 2021. "TCPD Indian Elections Data v2.0", Trivedi Centre for Political Data, Ashoka University.*

Download mechanism: **portal-gated, not a static CSV URL** - `https://lokdhaba.ashoka.edu.in/browse-data?et=GE`, select GE + state + year with AC-segment toggle OFF, then download. Requires the integrated browser to fetch. The GitHub path `ashokayan/TCPD` the user cited returns 404; the canonical product is the Lok Dhaba web portal. Codebook: `https://lokdhaba.ashoka.edu.in/static/media/2022Feb12LokDhabaCodebook.pdf`.

## Per-year honesty caveats (must carry into EGC-B2 ingest)

- **NOTA**: introduced by the Supreme Court order of Sept 2013; first Lok Sabha GE with NOTA was 2014. The NOTA pc-* indicator is NULL for 1999/2004/2009, present for 2014/2019.
- **2008 delimitation**: PC boundaries changed under the 2008 Delimitation Order. 1999/2004 PCs use the old (pre-2008) delimitation; 2009 onward use the current delimitation. Margin/turnout series across the 2009 boundary are not like-for-like at the constituency level and need a `methodology_breaks` annotation (Hans framing).
- **Telangana**: not a separate state until 2 Jun 2014. For 1999/2004/2009 all 17 Telangana-region PCs are filed under Andhra Pradesh; the 2014 GE was the bifurcation election itself. Entity-id assignment for pre-2014 Telangana PCs needs an explicit rule (Hans/Gregor) - the `IN-PC-<delim_year>-<state_code>-<pc_no>` scheme must file them under the AP state code for those years.

## Open follow-ups (deferred to EGC-B2)

- Verify whether `data.gov.in` (Open Government Data Platform India) hosts an ECI-published constituency-wise CSV for 2014 and/or 2019. If a stable, ECI-sourced CSV exists there, those two years could flip to ECI-direct. **Unconfirmed - do not assume.**
- Confirm the exact Lok Dhaba CSV download endpoint/payload by driving the browse-data portal in the integrated browser (capture the network request) so the ingest can be scripted rather than hand-clicked.
- Postal-votes pc-* indicators have no source short of ECI Form-20 PDF tables (out of scope per re-curation-not-digitisation rule); leave NULL.

## Handoff for EGC-B2 (ingest)

- All five years acquire via TCPD-fallback / Lok Dhaba, browser-driven download, AC-segment toggle OFF for PC grain.
- Reuse existing 13 `pc-*` indicators + existing `IN-PC-<delim_year>-<state_code>-<pc_no>` entity scheme. NO new id grammar.
- Convert any non-CSV download to CSV in a one-time documented prep step OUTSIDE the pipeline (CSV-only ingest contract; no xlrd/pandas).
- Honesty guards: NOTA null pre-2014; 2008 methodology_breaks row; Telangana-under-AP for pre-2014; per-(year, delim_year) distinct-PC count assertion (543 floor; never 545).
