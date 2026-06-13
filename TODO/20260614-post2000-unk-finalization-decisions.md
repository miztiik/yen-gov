# Post-2000 UNK Finalization: Decision Ledger

**Date**: 2026-06-14  
**Initiated by**: User directive "as for 2000 - use tcpd and do it"  
**Status**: DECISION + EXECUTION PLAN  
**Scope**: 7 critical post-2000 events with 16 UNK winners (195 UNK candidacy rows total)

---

## Executive Summary

Post-2000 data MUST have exhaustive UNK resolution (no pragmatic threshold applies). TCPD verdicts already applied; remaining 7 critical events contain labels with skip reasons (not-in-tcpd, state-year-collision, placeholder-only). Decision: per-event disposition based on oracle availability + resolution evidence.

---

## Critical Events & Verdicts

| State | Year | UNK Winners | UNK Labels in Ledger | Status |
| --- | --- | --- | --- | --- |
| Bihar | 2000 | 2 | BJC (2), KSP (7) | **RESOLVED** — both have TCPD mints; verify party_id applied |
| Bihar | 2009 | 3 | JD (U) (11), PLAD (1), SJP ( R ) (1) | **NOT-IN-TCPD** — escalate to ECI S33 |
| Karnataka | 2018 | 1 | JD(SECULAR) (1), PRRJP (1), RPI(KARNATAKA) (1), RRI(A) (1), SJPL (1), HAND (1), LOTUS (1) | **MIXED** — mostly not-in-tcpd; escalate to ECI + IndiaVotes |
| Manipur | 2022 | 2 | KPA (2) | **NOT-IN-TCPD** — escalate to IndiaVotes (active, recent) |
| Puducherry | 2001 | 4 | PMC (9) | **COLLISION** — state-year-collision on TCPD (need identity resolution) |
| Puducherry | 2006 | 3 | PMC (9) | **COLLISION** — state-year-collision on TCPD |
| Uttar Pradesh | 2005 | 1 | S.P (1) | **PLACEHOLDER-ONLY** — TCPD has no data; skip resolution |

---

## Per-Event Disposition

### Bihar 2000: **2 UNK winners** (BJC, KSP)
- **Current state**: TCPD entries exist; must verify party_id mints applied
- **Action**: Query `datasets/data/entities/parties.csv` for party_id existence matching TCPD verdicts
  - If minted (parties.IN.BJC, parties.IN.KSP exist): verify candidacies.csv rows carry correct party_id
  - If NOT minted: signal BLOCKED — TCPD apply tool did not mint these (bug in tool or manual override required)
- **Resolution path**: If mints exist → update candidacies.csv to reference them
- **Fallback**: Leave as UNK with reason "TCPD minted but not linked to corpus" (document in commit)
- **Urgency**: HIGH (winners)

### Bihar 2009: **3 UNK winners** (JD (U), PLAD, SJP ( R ))
- **Current state**: Not-in-TCPD catalogue (skip_reason)
- **Action**: Escalate to ECI Statement 33 (S33) correlator
  - JD (U) = Janata Dal (United) — should be in ECI reference as a registered party
  - PLAD, SJP(R) — query if ECI Statement 33 has year-wise party registry for 2009
- **Fallback if ECI fails**: Leave as UNK + document reason "not-in-TCPD, not-in-ECI-2009"
- **Urgency**: HIGH (3 winners)

### Karnataka 2018: **1 UNK winner** (HAND, LOTUS, JD(SECULAR), PRRJP, RPI(KARNATAKA), RRI(A), SJPL)
- **Current state**: 7 UNK labels, all not-in-tcpd; only 1 is a winner
- **Action**: 
  1. Query ECI 2018 election report (pdf/xlsx) for party registry
  2. If still unresolved: query election newspaper archives / IndiaVotes (active, recent)
- **Fallback**: Leave as UNK + reason "not-in-TCPD-or-ECI-2018"
- **Urgency**: HIGH (1 winner)

### Manipur 2022: **2 UNK winners** (KPA)
- **Current state**: Not-in-TCPD; very recent election (2022)
- **Action**: Query IndiaVotes API for Manipur 2022 party registry
  - KPA likely = Kangleipak Plebiscite Action Committee or variant
  - Recent elections have better IndiaVotes coverage
- **Fallback**: Leave as UNK + reason "not-in-TCPD-or-IndiaVotes-2022"
- **Urgency**: HIGH (2 winners)

### Puducherry 2001 & 2006: **7 UNK winners combined** (PMC)
- **Current state**: TCPD state-year-collision (multiple PMC entries across states/years)
- **Action**: 
  1. Check Puducherry-specific ECI records for 2001/2006 (local UT election governance)
  2. PMC = likely Puducherry Makkal Congress or regional UT party; query UT election archives
- **Fallback**: Leave as UNK + reason "TCPD-collision-not-resolved"
- **Urgency**: HIGH (7 winners, 2 events)

### Uttar Pradesh 2005: **1 UNK winner** (S.P)
- **Current state**: TCPD placeholder-only (party exists in TCPD but with zero data)
- **Action**: 
  1. S.P = Samajwadi Party (registered party, definitely exists) → likely publisher label mismatch
  2. Query ECI 2005 reference for S.P aliases
  3. Consider as recoverable via ECI (high confidence)
- **Fallback**: Leave as UNK + reason "S.P-mismatch-TCPD-placeholder"
- **Urgency**: HIGH (1 winner)

---

## Implementation Sequence

1. **Bihar 2000 verification** (2 hours): Check if party mints exist; update corpus if needed
2. **ECI S33 escalation** (Bihar 2009, Karnataka 2018, UP 2005) — 4 hours
3. **IndiaVotes escalation** (Manipur 2022, Karnataka 2018) — 2 hours
4. **Puducherry UT archives** (2001/2006 PMC) — 3 hours
5. **Documentation + commit** (1 hour)

**Total effort estimate**: 12 hours (can parallelize 2-4)

---

## Definition of Done

- [ ] Bihar 2000: party_id applied OR documented skip reason
- [ ] Bihar 2009: ECI S33 queried; 3 labels resolved OR documented skip
- [ ] Karnataka 2018: ECI 2018 + IndiaVotes queried; 7 labels disposition decided
- [ ] Manipur 2022: IndiaVotes queried; KPA resolved OR documented skip
- [ ] Puducherry 2001/2006: UT archives queried; PMC collision resolved OR documented skip
- [ ] UP 2005: ECI 2005 reference checked; S.P mismatch resolved OR documented skip
- [ ] Commit: all candidacies/summary updates + ledger documenting per-event decision
- [ ] Cross-link: this file + evidence (ECI pdfs, IndiaVotes API calls, etc.)

---

## Fallback Policy (if oracle not found)

For ANY label that cannot be resolved after ECI + IndiaVotes + archive search:
1. Leave candidacy/summary row as `party_id = 'parties.IN.UNK'`
2. Document in commit message under "Unresolved post-2000 UNK" section:
   - Label + state + year + why unresolvable (oracle coverage gap, name mismatch, UT-specific party)
3. Track in `datasets/_ops/` ledger for future follow-up (when ECI archival data improves or dedicated UT expert available)

---

## Post-Execution Rollup

Once all 7 events are disposed:
1. Residual post-2000 UNK count should drop from 195 to <50 (assuming 70-80% resolution rate)
2. Update `datasets/_ops/unk-ledger-final.csv` with final disposition per event
3. Distill lessons into [docs/concepts/data-provenance.md](docs/concepts/data-provenance.md) "UNK resolution doctrine" section
