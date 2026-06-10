# The data spine - what yen-gov re-curates, and why

**Last Updated**: 2026-06-04

This is the load-bearing doctrine that says what yen-gov IS, how it differs from a data warehouse, and the five non-negotiables every new family of indicators MUST honour. It REPLACES the off-the-cuff "DATA - SCHEMA - SCALE - ENRICHMENT" slogan that circulated earlier; the slogan's two good instincts (the backend supports the data; the frontend bends to whatever the schema declares) are kept and codified, the slogan itself is retired.

The spine derives from first principles + [FAIR](https://www.go-fair.org/fair-principles/) + [OWID's published practice](owid-alignment.md) + the Max/Hans division of labour. It is the doctrinal spine that [CLAUDE.md section 0a "The One Rule"](../../CLAUDE.md) sits inside. It does NOT replace [`citizen-first.md`](citizen-first.md), [`owid-alignment.md`](owid-alignment.md), or [`schema-is-the-design-system.md`](schema-is-the-design-system.md) - it harmonises them under one spine.

## One-line quotable form

> We do not collect data; we re-curate civic trajectories - question-first, LGD-joinable, methodology-stable, source-cited, and static-served - so the backend supports the data and the frontend bends to it, never the reverse.

## The principle

**yen-gov is a re-curation platform, not a data warehouse.** We do not maximise how much data we hold; we maximise how many honest, comparable civic trajectories a citizen can see and trust. An authoritative-but-mis-framed number is worse than none. A held-but-uncomparable series is worse than a small comparable one. The site's value is the trajectory plus the honesty around it, not the row count.

## Five non-negotiables (in order)

1. **Question-first, not data-first.** Begin with a citizen question + an honest definition (Hans), then a vetted comparable source (Max) - never "we have this dataset, what now?". An authoritative-but-mis-framed number is worse than none. The seven-step procedural form lives in [`citizen-first.md`](citizen-first.md); this is its principled root.
2. **Joinable by issuing-authority identity (FAIR-Interoperable).** Every entity keyed to an LGD / ECI / ISO code, NEVER a display name, so any two indicators merge on geography. The writer stamps the code at emit time; the frontend joins by code in DuckDB-WASM at read time; the display name is for the citizen, not for the join.
3. **Comparable as one methodology-stable series (OWID).** One indicator = one long-format `(entity, period, value)` series; new vintages UPSERT the same `variable_id`; definition shifts get a `methodology_breaks` row, never a quiet redefinition. New publisher of an existing fact = UPSERT or facet, never mint. Base-year rebase = same id + new break row (the "Rosling rule"). See [ADR-0044](indicator-naming.md#adr-0044-grain-over-entity) for the id grammar.
4. **Cite-able by mandatory provenance (FAIR-Reusable, [Holy Law #9](../../CLAUDE.md)).** Every row carries a `source_id` FK to one row in `datasets/data/entities/source.csv`; no anonymous data ever reaches a citizen. The citation ledger is one row per `(producer, title, vintage)` triple, not per fetch event. See [`data-provenance.md`](data-provenance.md).
5. **Accessible by static-first delivery (FAIR-Accessible, [Holy Law #1](../../CLAUDE.md)).** The schema IS the design system: the backend pre-emits everything the citizen needs; the frontend reads the static bundle via DuckDB-WASM `read_csv(columns=...)` and bends to whatever the schema declares (closed renderer set). The backend supports the data; the frontend never restricts it. See [`schema-is-the-design-system.md`](schema-is-the-design-system.md).

## Pipeline of responsibility

A datapoint travels through six persona-owned stages, in this exact order:

```
acquire (Max) -> define (Hans) -> shape/schema (Gregor)
              -> store (CSV writer; LGD/ECI/ISO + source_id stamp)
              -> serve (static bundle; DuckDB-WASM read_csv)
              -> render (Jony + Citizen; closed renderer set)
```

- **acquire (Max).** Scout the upstream publisher; verify the source is the issuing authority for the fact. No anonymous CSV from a Twitter thread.
- **define (Hans).** Frame what the number means in the Indian fiscal-federal context; identify the framing trap before adopting; write the honesty caveat.
- **shape / schema (Gregor).** Decide the column contract (file class, dtypes, nullability, FK targets); run a check-overlap pass against existing variables (no duplicate concept).
- **store (CSV writer).** Emit long-format CSV under `datasets/data/`; stamp the LGD / ECI / ISO `entity_id` and the `source_id` at write time; never `datetime.now` in a value cell.
- **serve (static bundle).** The deployed app is a static build on GitHub Pages; the citizen's browser fetches CSV via HTTP Range and joins via DuckDB-WASM with explicit `columns={...}` maps (typed-read mandate).
- **render (Jony + Citizen).** A closed renderer set (`GeoChoropleth`, `CategoryBar(mode=...)`, `Matrix`, `TimeLine`, `Scatter{size}`, `DumbbellRange`, `Treemap`, `CirclePack`) picks the visual form from the data shape + the indicator's declared `chart_types[]`; the [chart index](../reference/chart-index.md) is the citizen-facing contract. A blank card is impossible (the ranked-bar fallback is guaranteed).

Every stage is owned by exactly one persona. A stage skipped or reversed is a doctrinal violation, regardless of how cleanly the code reads.

## Why this beats the "DATA - SCHEMA - SCALE - ENRICHMENT" slogan

| Slogan word | Failure mode | Spine's replacement |
| --- | --- | --- |
| **DATA**-first | Invites authoritative-but-misleading acquisition ("we have NCRB, what now?") | Split into **acquire (Max) + define (Hans)**; both upstream of schema; Hans frames before Max scouts |
| **ENRICHMENT** | Vague "add value later"; becomes a graveyard of half-tagged rows | Becomes **FAIR joinability + cite-ability as WRITE-TIME properties** (LGD code + `source_id` stamped at emit; not "we'll join later") |
| **SCALE** | "More data is better"; risks methodology drift across vintages | Becomes **OWID methodology-stable comparability** - more entities/years on the same series, never a re-mint |
| **SCHEMA** | Kept and sharpened | Still load-bearing - it IS the design system; the closed renderer set is what makes the frontend bend to the data |

The slogan's two good instincts ("backend supports, not constrains" + "frontend should not restrict data") are already [Holy Laws #1 / #2](../../CLAUDE.md) and the [closed renderer rule](schema-is-the-design-system.md). The spine codifies them; the slogan retires.

## How this harmonises with the other concept docs

- [`citizen-first.md`](citizen-first.md) is the PROCEDURAL form of non-negotiable #1 (question-first). The spine names the principle; citizen-first gives the seven-step pipeline.
- [`owid-alignment.md`](owid-alignment.md) is the FALLBACK rule when a yen-gov-specific answer is missing. The spine names WHY OWID is the reference (methodology-stable comparability + cite-ability are the world's best operational answer at ~10,000-indicator scale); owid-alignment names HOW to invoke it.
- [`schema-is-the-design-system.md`](schema-is-the-design-system.md) is the UI/UX consequence of non-negotiable #5 (the closed renderer set; no per-indicator Svelte code). The spine names the principle; schema-is-the-design-system enforces it at PR review.

All three docs hold; this one sits above them as the single quotable doctrinal source.

## How to invoke this doctrine

When a design proposal might violate one of the five non-negotiables:

1. Name the non-negotiable explicitly (e.g. "this would join on display name, not LGD code - violates #2").
2. If the proposal genuinely cannot be re-shaped to honour the rule, the proposer carries the burden of a written named-divergence entry in the relevant subsystem doc, signed off by Hans + Max per [CLAUDE.md section 0a](../../CLAUDE.md).
3. If the divergence is "I think this is nicer" or "the publisher's CSV already comes that way," default to the rule. Aesthetics and source convenience are not divergence reasons.

When an agent debate is split on a data-shape question (Gregor vs Fowler / Max vs Hans / Jony vs Citizen):

1. Ask: does any answer violate one of the five non-negotiables? If yes, that path is eliminated.
2. Of the survivors, ask: what does OWID do? [`owid-alignment.md`](owid-alignment.md) takes over from here.

## See also

- [`citizen-first.md`](citizen-first.md) - the seven-step procedural form of non-negotiable #1.
- [`owid-alignment.md`](owid-alignment.md) - the fallback when a yen-gov-specific answer is missing.
- [`schema-is-the-design-system.md`](schema-is-the-design-system.md) - the UI/UX consequence of non-negotiable #5.
- [`data-provenance.md`](data-provenance.md) - the citation ledger that makes non-negotiable #4 operational.
- [`../architecture/data/canonical-store.md`](../architecture/data/canonical-store.md) - the operational spec for non-negotiable #5 (where the CSV lives, what the columns are).
- [`../reference/chart-index.md`](../reference/chart-index.md) - the closed renderer set that non-negotiable #5 produces.
- [`../../CLAUDE.md`](../../CLAUDE.md) - the engineering contract; [section 0a "The One Rule"](../../CLAUDE.md) cross-links here.
