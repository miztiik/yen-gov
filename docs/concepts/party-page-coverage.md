# Party Page Coverage

**Last Updated**: 2026-06-15

> Citizen-facing notes on what every `/parties/<slug>` page on yen-gov shows, where the numbers come from, and the boundaries the data inherits from its publishers. Authored as the consolidation surface for the meta-disclaimers the page previously rendered inline (per [`TODO/20260615-party-page-citizen-fixes-plan.md`](../../TODO/20260615-party-page-citizen-fixes-plan.md) PR-9 + PR-11 + PR-13). Reading this once replaces reading the same italic caveats on every visit.

## What you are looking at

A party page renders six citizen-readable sections, in this order:

1. **Header card** - the party's symbol, name, the latest-election one-liner, and a "Where this party sits today" current-strength strip.
2. **Latest-of one-liners** - one sentence per legislative body (Parliament + State Assemblies) summarising the latest cycle's seats and vote-share, with peak/low framing when the latest is below the all-time peak or above an earlier low.
3. **Long-arc charts** - a Parliament dual-axis chart (seats as bars, vote-share as a line) and a parallel State Assemblies chart. One mark per election cycle the party contested.
4. **Strongholds** - the top constituencies where the party has won the most lifetime cycles, grouped by body, with a click-through to the constituency page when the constituency still exists under the current delimitation.
5. **Alliance context** - "who they ride with" - the recorded pre-poll alliance, per cycle, per jurisdiction.
6. **About this party** - founded / dissolved / recognition / home states / native script / Wikipedia / lineage / aliases.

Each card carries its own publisher pills at the bottom (e.g. ECI, TCPD, MyNeta) - one tap to see exactly which producers + titles + vintages contributed to the numbers on that card.

## What we have data for

The page is honest about its boundaries:

- **Latest cycle per body**. The header one-liners + the KPI strip show the LATEST election cycle the party contested per body, not a rolling average. The long-arc charts show every cycle the party contested.
- **Election-night results, no post-poll tracking**. The seats and vote-share rendered for any cycle are the results as declared by the Election Commission on counting day. The page does NOT track post-election defections, party splits, resignations, or by-elections that landed after the original cycle. This matters most for the "current strength" framing: when the latest cycle is several years old, the seat count is the cycle's election-night verdict, not the legislature's composition today.
- **Cycles ingested, not every cycle publishers carry**. yen-gov's elections corpus reflects the cycles already ingested from ECI / TCPD / MyNeta archives. Older cycles, defunct state-level publishers, and by-elections in some states may exist in publisher records that are not yet on file. When a cycle is missing here, it is missing from yen-gov's ingest queue, not from the historical record.
- **Alliance ledger is recent-decade only**. The "Alliance context" card filters to cycles within the last ten years (`event_year >= currentYear - 10`). Pre-poll alliances from the early 2000s tell the citizen little about how the party is currently positioned. The 10-year cap is a defensible default (see [`TODO/20260615-party-page-citizen-fixes-plan.md`](../../TODO/20260615-party-page-citizen-fixes-plan.md) PR-11); when a major party's list still surfaces too many jurisdictions, the cap can tighten further. The alliance ledger itself is a curator-edited table at [`datasets/data/entities/party_alliances.csv`](../../datasets/data/entities/party_alliances.csv), one row per `(event_id, state, party_id)`.
- **Stronghold definition**. A "stronghold" is a constituency where the party has won the most cycles over its lifetime in that body, ranked by lifetime wins (not by vote-share). The list caps at the top ten per body. Ties are broken by the most recent winning cycle.

## How sources are cited

Every observation row in every yen-gov dataset carries a `source_id` foreign key to one row in the canonical citation ledger at [`datasets/data/entities/source.csv`](../../datasets/data/entities/source.csv). The ledger is keyed on the `(producer, title, vintage)` triple - identity adopted from OWID `origin.*`. There is no per-shard sources array, no embedded URL on an observation row, and no second provenance table for a particular family. One table, one foreign key, one shape.

The publisher pills under each card are derived from the `source_id`s on the rows the card consumes, deduplicated and rendered as a quiet strip. Tapping a pill jumps to the publisher's landing URL (the `url` column on the ledger row). When a producer ships hand-imported or transcribed data, the `url` is empty and the pill is non-clickable.

See [`data-provenance.md`](data-provenance.md) for the full contract, the 5-column schema, and the inline ADR receipts.

## How processing levels work

Each row also carries a closed-enum `processing_level` of either `minor` or `major`:

- `minor` - mechanical processing only (parse + normalise + schema-conform). No discretionary call was made.
- `major` - a discretionary call was made on the row. A non-empty `processing_note` is mandatory and records the rationale on the row itself.

The vocabulary is OWID-verbatim and closed at two values. The per-row scope (rather than per-variable) is a documented yen-gov-specific divergence from OWID. See [`data-quality.md`](data-quality.md#per-row-processing-level-vocabulary) for the full vocabulary and worked examples.

## Why some constituencies link and others do not

The stronghold rows are clickable when the listed constituency still exists under the current delimitation. India's parliamentary and assembly boundaries are re-drawn periodically; a constituency that returned the party three times under a pre-2008 delimitation may have been split, merged, or renamed in the current one. yen-gov's frontend resolves a constituency link only when the row's `entity_id` matches an entry in [`datasets/data/entities/electoral.csv`](../../datasets/data/entities/electoral.csv) for the latest cycle. When it does not match, the row renders as plain text - the lifetime tally is still shown (the wins really happened), but the click-through is suppressed rather than landing on a 404 or a misleading current-delim page.

This is a deliberate "one-shot lookup" gate (see [`TODO/20260615-party-page-citizen-fixes-plan.md`](../../TODO/20260615-party-page-citizen-fixes-plan.md) PR-8b). A multi-delimitation canonical fold that lets every historical constituency click through to its correct boundary footprint is a separate, larger project; until it lands, the gate keeps the rows honest.

## Known limitations

- **By-elections are not first-class**. The corpus is anchored on general / state-cycle elections; by-elections that change a single seat between cycles are not separately surfaced.
- **Pre-1996 vote-share quality varies by state**. The PDF-extracted ECI archives carry occasional rounding mismatches at the state level; long-arc charts may show small inconsistencies in the oldest cycles.
- **Sentinel parties**. Independents (`IND`) and None-of-the-above (`NOTA`) render a stripped-down page - charts and strongholds suppress, since aggregating IND or NOTA across cycles produces meaningless numbers. The header card and metadata footer still render.

## See also

- [`data-provenance.md`](data-provenance.md) - canonical sources table, citation-ledger contract, publisher-pill derivation.
- [`data-quality.md`](data-quality.md#per-row-processing-level-vocabulary) - per-row `processing_level` vocabulary.
- [`citizen-first.md`](citizen-first.md) - the question-first persona pipeline that produced this page.
- [`owid-alignment.md`](owid-alignment.md) - the One Rule (OWID is the canonical reference for socio-economic data modelling).
- [`../../datasets/data/entities/parties.csv`](../../datasets/data/entities/parties.csv) - the canonical parties table.
- [`../../datasets/data/entities/party_alliances.csv`](../../datasets/data/entities/party_alliances.csv) - the curator-edited alliance ledger.
- [`../../datasets/data/entities/electoral.csv`](../../datasets/data/entities/electoral.csv) - the canonical electoral entities used for the delim-existence gate on stronghold rows.
- [`../../TODO/20260615-party-page-citizen-fixes-plan.md`](../../TODO/20260615-party-page-citizen-fixes-plan.md) - the plan-doc that produced the current shape of the page.
