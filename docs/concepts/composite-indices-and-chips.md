# Composite indices: when to ingest, when to recompute, when to refuse

> **Status**: Locked doctrine (Hans + Max verdict, 2026-06-03).
> **Acquisition status**: methodology annexure not yet obtained; ingest gated on the pre-ingest blockers below.

## Why this doc exists

yen-gov is asked, periodically, to surface composite indices that rank states - CHIPS (the State of India's Digital Economy / SIDE), the NITI SDG India Index, the NITI India Innovation Index, HDI, and similar. Each one is a single number that bundles 30-60 underlying indicators into a leaderboard. They are politically charged, easy to misuse, and trivially easy to silently corrupt by recomputation.

This doc names the rules every composite index has to clear BEFORE it lands on a citizen surface, so the same fork does not get re-litigated for the next one.

## The headline rule: ingest as published, do NOT recompute

When a composite index is published by a credible body - government, think-tank, multilateral - yen-gov ingests the **published score and rank as a row of canonical observations**, with the publisher named as the source. We do NOT recompute the index from its 30-60 sub-indicators inside yen-gov, even when the sub-indicators are themselves ingestable, for two binding reasons:

1. **Composite indices depend on inputs we cannot decompose.** SIDE's pillars (Connect, Harness, Innovate, Protect, Sustain) lean on ITU / World Bank / GSMA / Ookla series that are global-only - they have no state-level decomposition. A "yen-gov CHIP" recomputed from only the state-decomposable subset would silently diverge from the published number and mislead. Same for HDI (UNDP global denominators), CHIPS (state-only sub-pillars), and most others.

2. **The composite IS a methodology; the methodology shifts edition-to-edition.** Weights, indicator lists, and base years are renegotiated each year. A recomputation in yen-gov would freeze ONE edition's recipe and silently overwrite next year's. The honest model: each edition is its own series; methodology breaks are explicit; trends across breaks are not smoothed.

This is OWID's "methodology-stable comparability" rule (OWID-aligned comparability doctrine, non-negotiable #3) applied to composites.

## Standing rules every composite-index view MUST honour

Apply these to CHIPS / SIDE today and to every future composite without re-litigation:

1. **Preserve the publisher's own state-size split** (e.g. SIDE's large-state vs small-state/UT split at the 1-crore-population line). Never merge into one leaderboard - city-state/UT vs 20-crore-state is the classic unfair comparison and the citizen reads the bigger-state-on-top result as governance failure when it is sample-size artefact.

2. **Render "insufficient data" entities as that, not as worst-rank or blank.** SIDE 2023-2026 cannot score Ladakh + Lakshadweep at full pillar coverage; the published verdict is "not ranked", and yen-gov surfaces it the same way. Blank-implies-zero is the Rosling Gap-instinct trap on its smallest scale.

3. **Pin the edition year as a hard methodology-break boundary.** A smoothed CHIPS trend line across editions with changed weights, changed indicator lists, or changed normalisations is forbidden. Two editions = two series with a visible break, never a continuous line.

4. **Show the score and the score-gap, not just the ordinal rank.** A rank-13 state and a rank-15 state may be within rounding distance on the composite score; rank-only readings exaggerate small differences.

5. **Never overlay ruling-party colour on a single-year composite-index snapshot.** Composite indices are slow-moving infrastructure + central-scheme driven measurements, not CM scorecards; the colour overlay reads as a causal claim the data does not support.

6. **Layer composites ON TOP OF, not above, government primary sources.** When ingested, every composite-index view carries a "Compare with" link to the NITI Aayog SDG India Index (the most authoritative recurring state composite) and any other government primary covering the same domain. Disagreements between composites surface as a methodology note, never silently resolved.

7. **Every composite-index row carries one `source_id` row that discloses funder alignment.** SIDE's source row must record the Prosus / Naspers co-funding of IPCIDE alongside the citation. ICRIER and IPCIDE are credible publishers; the funder alignment is a methodology disclosure, not a polemic, and it lives on the canonical source row where every consumer sees it.

## Pre-ingest blockers (gates for the future ingest PR)

Before any composite-index ingest PR can merge - including any CHIPS / SIDE PR - the following must land first as a `docs/research/<index>-methodology.md` doc:

- **The exact indicator list per edition** (e.g. SIDE 2023, 2024, 2025, 2026 each have their own 50-indicator inventory; record per-edition).
- **The per-pillar weights per edition** (e.g. SIDE's 16 sub-pillar weights; CHIPS top-level weights).
- **The normalisation formula per edition** (min-max? z-score? rank-and-decile? Different choices give different state orderings on identical inputs.)
- **The per-state dropped-pillar list per edition** (which pillars a state was scored on; which it was excluded from with a "not ranked" treatment).
- **The licensing terms of the source tables** (think-tank tables are not automatically open data; reuse without permission is a real legal blocker that surfaces post-merge if unaudited).
- **The per-edition indicator/weight diff vs the previous edition** (the methodology-break ledger; this is what rule 3 above is enforced against).

If any of the above are missing for a given edition, that edition is not ingested. A partial edition is a misleading edition.

## Chart choice (when CHIPS or any composite-index data does land)

- **Default sub-pillar compare**: `HorizontalGroupedBar`. Reads cleanly on mid-tier Android, supports the score-and-score-gap rule (4), allows side-by-side compare across small-state + large-state pools without merging them.
- **Optional secondary view**: `Radar` (the "spider chart" pattern the user has asked for). Allowed only as a SECONDARY view; never the default. Radar charts read poorly on small screens, the spoke-ordering arbitrarily privileges certain pillars, and most citizen audiences misread radar-area as a single-number ranking - recreating exactly the rank-only error rule 4 forbids.
- **Composite-vs-context scatter** (e.g. CHIPS vs per-capita NSDP): `Scatter` with the size axis empty (one indicator pair per chart per the closed-renderer-set doctrine; no bubble redundancy).

`Radar` is NOT part of the base renderer set - keeping it as a secondary-view-only option here is a deliberate fence, not an extension.

## What this doc does NOT do

- It does NOT ingest any composite-index data. That is gated on the pre-ingest blockers above.
- It does NOT commit yen-gov to ever ingesting CHIPS / SIDE specifically. It commits to running every composite-index proposal through these rules.
- It does NOT compute or display a yen-gov-original composite index. We are a re-curation platform, not an index-publisher.

## Cross-references

- [docs/concepts/schema-is-the-design-system.md](schema-is-the-design-system.md) -- closed renderer set and one-card-per-measure doctrine.
- Doctrine: [CLAUDE.md](../../CLAUDE.md) section 5 (design decisions live in `docs/`).
- OWID precedent: composite indices like HDI are ingested-as-published from UNDP; OWID does not recompute them.
