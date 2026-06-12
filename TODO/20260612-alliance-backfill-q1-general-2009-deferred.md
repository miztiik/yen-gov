# Alliance backfill Q1.3 — general-2009 (15th Lok Sabha) — 2026-06-12 — DEFERRED

**Status:** DEFERRED with STOP-AND-SURFACE per Hans R5.3 + plan-doc Q1 row 3 caveat.
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q1 row 3
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §10 anti-patterns (STOP-AND-SURFACE; don't silently invent alliance assignments) · Hans R5.3 ("If Wikipedia's pre-poll alliance table is sparse / contested → skip that event in this PR; surface in handover-doc + plan-doc closure ledger; partial Q1 is fine").

## Wikipedia source consulted

- **Article:** `2009 Indian general election`
- **URL:** https://en.wikipedia.org/wiki/2009_Indian_general_election
- **Retrieval date:** 2026-06-12

## Why this event was deferred

The 2009 Wikipedia main article's `## Coalitions` section names FOUR pre-poll alliances (UPA, NDA, Third Front, Fourth Front) but does NOT enumerate per-party membership in clean tabular form like the 2014 + 2019 articles do. The plan-doc Q1 row 3 brief flagged:

> "the long-tail of regional / one-election fronts" risk is HIGHER for 2009. The Third Front + Fourth Front line-ups in 2009 were messy. CAUTION ... If Wikipedia's pre-poll alliance table for 2009 is sparse / contested, document the ambiguity in the handover-doc and leave those parties unallied.

After reading the 2009 main article in full, THREE specific ambiguities surfaced that warrant Hans curator review BEFORE any rows are committed:

### Ambiguity #1 — Telangana Rashtra Samithi (TRS / now BRS) joined NDA MID-POLL on 10 May 2009

NDA Wikipedia § Timeline § 2009 records:
> "The Telangana Rashtra Samithi in United Andhra Pradesh, joined the NDA on 10 May 2009 and subsequently denied the fact that it joined NDA and clarified that they only extended the support."

Polling in 2009 ran 16 April to 13 May. The TRS-NDA tie-up happened DURING polling and was then DISAVOWED by TRS itself. Was TRS pre-poll NDA-2009? Per Hans R3.4 + R5: ambiguous publisher attribution → leave unallied + surface.

### Ambiguity #2 — Fourth Front (SP + RJD + LJP) status: pre-poll vs post-poll vs UPA-aligned

The 2009 main article § Fourth Front:
> "The Samajwadi Party, Rashtriya Janata Dal and the Lok Janshakti Party failed to reach seat sharing agreements with the Congress and decided to form a new front, hoping to be kingmakers after the election. Despite announcing this front, the constituent parties continued to declare their support for the UPA."

This is the precise pattern Hans's R5.3 flagged: a "front" that simultaneously declared UPA support. Per Hans's "outside support != alliance member" rule, SP + RJD + LJP cannot be both UPA AND Fourth Front members. The Wikipedia article presents both framings without resolution.

Per CLAUDE.md §10 STOP-AND-SURFACE: "Do NOT silently invent alliance assignments." Three plausible interpretations exist (Fourth-Front-only / UPA-only / both), and choosing any of them is a substantive editorial ruling that belongs to Hans + Max, not to an autonomous agent.

### Ambiguity #3 — Third Front (CPI(M)-led) composition was declared close to election eve and shifted during the campaign

The 2009 main article § Third Front:
> "The CPI(M) led the formation of the Third Front for the 2009 election. This front was basically a collection of regional political parties who were neither in UPA nor in the NDA."

But the article does NOT enumerate which regional parties were in the Third Front, beyond the lead CPI(M). The 2009 results table (per-party seat row) similarly does not carry alliance tags. Standard public attribution names CPI(M), CPI, RSP, AIFB (Left Front core) + AIADMK, TDP, BJD, TRS, JD(S), RLD as Third Front constituents — but each of those (a) BJD had its own pre-poll posture, (b) TRS joined NDA mid-poll per Ambiguity #1, (c) RLD's alignment is contested. Six of the ~10 candidate Third Front members have a contested status.

Per Hans R5: when "the Wikipedia article's pre-poll alliance table for 2009 is sparse / contested", DEFER the event.

## What is unambiguous (and could be authored confidently if 2009 were scoped to UPA+NDA ONLY)

If the brief had scoped this PR to ONLY the unambiguous UPA-2009 + NDA-2009 (~16 parties total, all of which sit cleanly in published lists), the deferral wouldn't apply. But the plan-doc Q1 row 3 explicitly included Third Front + Fourth Front coverage ("~35 rows expected"), and the Hans+Max joint verdict on Phase 1b is "all-or-defer per event" — not "partial per alliance".

## STOP-AND-SURFACE ledger row

Per CLAUDE.md §10:

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
| --- | --- | --- | --- |
| Q1.3-defer | 2026-06-12 | DEFER general-2009 from Phase 1b Q1 to a future Phase 1b Q1.3-followup PR. Wikipedia main article does not provide an enumerable per-party pre-poll alliance table for 2009; the Third Front + Fourth Front had three specific ambiguities (TRS-NDA mid-poll join then disavowal; Fourth Front parties simultaneously declared UPA support; Third Front composition contested across ~6 of ~10 candidate members). Per Hans R5.3 explicit instruction, defer. Q1 ships as **Q1-partial** (2 of 3 events: general-2019 + general-2014; general-2009 to follow once Hans confers and supplies a curated NDA-2009 + UPA-2009 + Third Front list, or rules out Third Front + Fourth Front coverage and scopes 2009 to NDA+UPA only). | _Hans curator review pending; this PR ships with this defer-row as the surface_ |

## Path forward (suggested Q1.3-followup brief shape)

Two clean paths the curator could authorise for a future Q1.3-followup PR:

1. **Scope-narrow path**: drop Third Front + Fourth Front coverage from Phase 1b for 2009. Ship only NDA-2009 + UPA-2009 (~16 parties total) on the same `(producer, title, vintage)` triple `("Wikipedia", "2009 Indian general election", "2009-05")` → `src-NEWID`. This is the lowest-ambiguity path; it matches what the plan-doc Q2 + Q3 do (NDA + UPA + state-front only, no Third / Fourth Front).
2. **Curator-supplied list path**: Hans provides a hand-authored 2009 alliance assignment table (similar to the 4 already-curated events that Phase 1 lights up) covering NDA-2009 + UPA-2009 + Third Front + Fourth Front with explicit Hans verdict on the 3 ambiguities above. Subagent then mechanically applies it.

Either path requires Hans sign-off before authoring. This handover-doc carries the receipt for the deferral; the closure of general-2009 belongs in Phase 1b Q1.3-followup.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | open | Q1.3 handover authored as DEFERRAL receipt. 0 rows committed to `party_alliances.csv` for general-2009 in this PR. |
