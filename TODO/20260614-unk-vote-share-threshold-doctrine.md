# UNK Party Resolution: Vote-Share Threshold Doctrine

**Date**: 2026-06-14  
**Status**: DECISION CLOSED (user + Fowler + Hans + Max consensus)  
**Applies to**: Old data (<2000) and post-2000 finalization  
**Supersedes**: Arbitrary rank-position heuristics (top-10/11/12)

## Problem

1005 unresolved party UNK rows across yen-gov election corpus (1962-2026) posed two risks:
- **Chasing tails**: Resolving every marginal label adds labour with minimal citizen understanding gain
- **Arbitrary thresholds**: Using "top-10/11/12 party rank" obscures the real criterion (vote share significance)

## Strategic Decision

### Old Data (<2000): Vote-Share Threshold Rule

**Rule**: For each (state, year, election_year) event:
1. Rank all parties (resolved + UNK labels) by votes descending
2. Compute cumulative vote % until reaching 95% threshold
3. All parties within top-95% = significant; keep distinct or resolve
4. All parties outside top-95% (including UNK labels) = marginal; no further resolution required

**Impact (quantified)**:
- 8 UNK labels inside top-95% (4.2M votes) = keep/resolve
- 16 UNK labels outside top-95% (1M votes, 518 rows) = no further labour
- Marginal labels: BAS, BJC, DBP, DNC, GL, JMI, JSMP, KCP, KSP, MIL, PHJ, RJP(G), SJJP, SMP, USP, UTNLF

**Rationale** (Fowler + Hans + Max):
- **Fowler** (Refactoring): No band-aids. Fix the seam (vote-share threshold) instead of arbitrary rank. Recognize historical footnotes are not worth infinite labour.
- **Hans** (Governance): Vote-share threshold is governance-honest. A party with 0.1% votes doesn't affect citizen understanding of electoral outcomes. But don't hide it—mark it clearly.
- **Max** (Indicator Science): OWID precedent: "Rest of World" / "Other" is how global datasets handle long tails at scale. One vote-share threshold per era is battle-tested.

### Post-2000 Data (2000-2026): TCPD Mandatory Resolution

**Rule**: Post-2000 UNK rows MUST be resolved via TCPD or documented as unresolvable.
- Rationale: 2000-2026 is modern era; citizen expectations are higher; TCPD coverage is strong.
- Post-2000 TCPD recognition rate: 45.3% (verified via 183-label correlator pass)
- Remaining post-2000 UNK after TCPD apply: 195 rows across 7 events with winner impact (Bihar 2000/2009, Manipur 2022, Puducherry 2001/2006, UP 2005, Karnataka 2018 parliament)

**Disposition**:
- 7 critical post-2000 events identified; each requires explicit resolution decision OR documented skip reason
- IndiaVotes parity oracle tooling ready (one-state test pending parser hardening)
- ECI correlators available for state/year coverage gaps
- If TCPD + IndiaVotes + ECI cannot resolve, document reason and leave as UNK (but rare)

## Implementation

### Old Data (<2000)

1. Compute vote-share threshold per event (95% cumulative)
2. Identify UNK labels/rows outside threshold
3. Decision for each outside-95% label:
   - **Option A**: Keep as UNK (safest, matches CLAUDE.md §10 "no silent demotion")
   - **Option B**: Group as "OTHERS" bucket in frontend (requires charter/docs update)
   - **Option C**: Leave in corpus as-is with operator note (current path)
4. Keep all inside-95% UNK labels as distinct pending future resolution

### Post-2000 Data (2000-2026)

1. TCPD verdicts already applied (69 mints, 17 aliases)
2. For 7 critical events with UNK winner/top-3:
   - Query IndiaVotes API (parse improvement needed)
   - Cross-check ECI S33 statement
   - If resolved: update candidacies/summary
   - If unresolvable after all oracles: document skip reason + commit
3. No pragmatic threshold applied; exhaustive resolution expected

## Definition of Done

- [ ] Code: `compute_vote_share_buckets.py` tool written + tested
- [ ] Old data analysis: per-event threshold reports generated
- [ ] Post-2000 finalization: 7 critical events documented (decision per event)
- [ ] Doctrine: this file + cross-link in [docs/concepts/indicator-naming.md](docs/concepts/indicator-naming.md) or [docs/archive/plans/](docs/archive/plans/) as closure
- [ ] Commit: all candidacies/summary updates + operator ledger regen

## Closure

Once applied:
1. Old UNK outside-95% labels stop appearing in bug reports / backlog
2. Post-2000 UNK = explicit remaining batch (small, documented)
3. Corpus is governance-honest (top parties clear, tail marginal but visible)

---

See also: 
- [ADR-0044: Grain over entity](docs/concepts/indicator-naming.md#adr-0044-grain-over-entity)
- [Data spine doctrine](docs/concepts/data-spine.md)
- [TCPD integration notes](TODO/20260603-data-and-charting-platform-reset-plan.md) (earlier reference)
