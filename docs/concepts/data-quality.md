# Data quality stance

**Last Updated**: 2026-06-14

yen-gov is a **re-publisher** of Indian governance and statistical
data. We are not a statistical agency. This page exists so that
everyone working in or on the repo — and every citizen who reads the
site — knows what we will and will not do to a number.

## What we do

- Preserve publisher values byte-faithfully where possible.
- Document every transformation we perform: parsing tables, mapping
  geographies, choosing revision vintages, computing declared rollups.
- Annotate every break, caveat, and definitional shift the publisher
  has disclosed (under [`methodology`](folded-indicator.md) on each
  indicator).
- Be loud about gaps. Missing cells are marked **Not collected yet**
  (source expected to publish; we haven't fetched it yet) or
  **Not published by source** (publisher does not separately report
  this geography or period). See [collection-inventory](collection-inventory.md).

## What we do not do

- **No adjustment, smoothing, imputation, correction, or estimation.**
  Errors in the original publication appear here. We update when the
  publisher updates.
- **No filling in of empty cells.** Estimation looks helpful and is
  dishonest. Empty stays empty.
- **No composite "best state" index.** Composites hide trade-offs.
  Citizens compare on one indicator at a time, with the right
  denominator.
- **No "we corrected this row" rows.** If the publisher revised, we
  re-collect and the methodology break is recorded; the original is
  preserved in `.runtime/raw/` until the operator deletes it.

## Trust, in one sentence

Trust the data exactly as far as you trust the publisher. yen-gov's
job is to make their data more accessible without changing what they
said.

## Where this shows up in code

- Indicator schema forbids deriving the published value at any step:
  see [`datasets/schemas/indicator.schema.json`](../../datasets/schemas/indicator.schema.json).
  `rows[].value` is what the publisher said, with conversion only when
  unit and base-year are explicit in the artifact.
- Composers union `sources[]` per-`url`, never per-`(url, fetched_at)`,
  so a re-fetch of the same upstream doesn't multiply the citation —
  the artifact still says "we got this from these N publishers".
- `methodology_breaks: []` means "no breaks documented yet", NOT "no
  breaks exist". The [`/data-completeness`](/data-completeness) view
  flags indicators with documentation_status `stub` so the team can
  prioritise backfill instead of pretending coverage is uniform.

## Companion docs

- [folded-indicator](folded-indicator.md)
- [collection-inventory](collection-inventory.md)
- [data-provenance](data-provenance.md)
- `frontend/src/routes/About.svelte` and `Disclaimer.svelte` mirror
  this page in citizen-facing voice.

## Per-row processing-level vocabulary

A citizen looking at a number on a yen-gov page asks two questions:

1. **Where did this come from?** Answered by [`source_id`](data-provenance.md), which points at the publisher / report / vintage.
2. **What did you do to it?** Answered by `processing_level` + `processing_note`: did the row pass through mechanical processing only (parse, normalise, schema-conform), or did a curator make a discretionary call about it?

The two columns together close the audit loop: `source_id` says where the row came from; `processing_level` + `processing_note` say what we did to it. The pairing is the public receipt for the difference between "publisher said this verbatim" and "publisher said something we had to interpret."

### The two-value vocabulary

The enum is closed at two values: `minor` and `major`. The vocabulary is OWID's, adopted verbatim per [docs/concepts/owid-alignment.md](owid-alignment.md) ("The One Rule"). New values are NOT added without a CLAUDE.md amendment + an updated owid-alignment divergence entry.

**`minor`** — the row was ingested with mechanical processing only: parsing the publisher's verbatim cell, normalising into the canonical column shape (name canonicalisation, ECI code mapping, etc.), schema-conforming the row (column order, nullability, FK validation). No discretionary call was made. A future re-ingest of the same upstream should round-trip byte-identical (modulo the upstream's own corrections).

**`major`** — a discretionary call is recorded on the row. The companion `processing_note` MUST be non-empty and MUST cite the rationale verbatim.

The current `major` triggers in the corpus are exactly three:

1. **Unresolved publisher party label.** `party_id == parties.IN.UNK` rows carry `major` with a note pointing at the UNK ledger (`datasets/_ops/unk-ledger-2026-06-12.csv`); a future curator with a TCPD or ECI catalogue update will resolve them. The publisher's verbatim short survives on `party_short_raw`.
2. **Bihar 2000 BJC.** The TCPD party_id `parties.IN.BJC` (Bharatiya Jan Congress, Bihar 1993-2000) shares the publisher shortcode "BJC" with one other TCPD party (Party_ID 9077). The disambiguation against the 2026-06-14 TCPD catalogue resolves on geographic + temporal evidence; the note cites both candidates explicitly so a future re-ingest does not silently flip the resolution.
3. **Bihar 2000 KSP.** The TCPD party_id `parties.IN.KSP` (Kosal Party) is uniquely resolved against the 2026-06-14 TCPD catalogue; the note carries the receipt.

All other discretionary-call categories (recount adjustments, byelection-merged seats, missing electors / votes_polled / turnout, etc.) are NOT yet in the corpus. When they appear, they extend this list; the enum stays at two values.

### The processing note

`processing_note` is free text, ASCII-only (CLAUDE.md section 5), citizen-readable, and citable in the same shape as the source-pill expander. Format conventions:

- Cite the upstream label verbatim in single quotes when the row's interpretation is ambiguous (e.g. `Publisher label 'BJC' unmatched against TCPD/ECI catalogues`).
- Cite the ledger pointer when the row awaits operator follow-up (`per datasets/_ops/unk-ledger-2026-06-12.csv`).
- Cite the TCPD Party_ID + catalogue date when the discretionary call is a party resolution (`TCPD Party_ID 1411 (Bharatiya Jan Congress)`).

Empty notes are forbidden when `processing_level == "major"`. Notes are forbidden (must be empty string) when `processing_level == "minor"` so the citizen's reading stays predictable: a note is a flag.

### Where this appears today

The two columns ship as the last two columns of every CSV in these four file classes:

- `datasets/elections/assembly/state=<slug>/election=<year>/candidacies.csv`
- `datasets/elections/assembly/state=<slug>/election=<year>/summary.csv`
- `datasets/elections/parliament/election=<year>/candidacies.csv`
- `datasets/elections/parliament/election=<year>/summary.csv`

Schema is at [datasets/data/_schema/columns.json](../../datasets/data/_schema/columns.json); enforced by the per-file CSV column validator (Holy Law #3). The vocabulary is enforced at write time by `backend/yen_gov/canonical/processing_quality.derive_processing` and at validation time by the unit test at `backend/tests/test_processing_level_enum.py` plus the Tier-A header-conformance check.

The columns do NOT yet light up on any citizen-facing surface; that ships in a follow-up UI PR. The two columns are optional fields on the frontend `ElectionResultRow` interface today so the loaders compile + run unchanged.

### OWID alignment (named divergence #6)

OWID's [Metadata reference for ETL](https://docs.owid.io/projects/etl/architecture/metadata/reference/) defines `processing_level` as a **per-variable** field (one tag for the whole indicator / variable / table). yen-gov adopts the vocabulary verbatim but moves the scope to **per-row** as named divergence #6 in [docs/concepts/owid-alignment.md](owid-alignment.md). Why per-row:

- The yen-gov election corpus carries individual records (one candidate per row, one constituency per summary row), each with its own processing history. A per-variable tag would force the whole candidacies.csv to inherit the most-discretionary row's level (any UNK in the file -> the whole file is `major`), which destroys the audit signal.
- The discretionary calls are localised: a single row's party_id may need curator review while every other row in the same CSV is mechanical. The per-row tag lets the citizen see exactly which rows need review.
- The vocabulary is unchanged. A future yen-gov per-variable summary (e.g. on a topic page) can derive `MAX(level)` over the rows + concatenate distinct `processing_note` values; the per-row tag does not preclude per-variable rollups.

## When PC totals come from AC-segment aggregation

The Lok Sabha PC-level summaries for elections 1999, 2004, 2009, 2014, and 2019 are NOT lifted from a direct-PC publisher CSV - TCPD does not publish one for these years. Instead, the PC totals are rolled up from TCPD's per-AC `All_States_GA.csv` row stack: every Assembly Constituency vote count under a PC is summed to that PC's electors / votes_polled / winner_votes / runnerup_votes / margin_votes columns. This is the segment-aggregation method ECI itself documents for delimitation-year analyses; it is reproducible and arithmetically faithful, but it is a derived computation, not a verbatim publisher cell.

Per yen-gov's per-row `processing_level` doctrine (Holy Law #9 + the OWID-aligned vocabulary above), every such PC-summary row carries `processing_level = "major"` and a non-empty `processing_note`:

> PC summary derived from TCPD All_States_GA.csv (AC-segment aggregation to PC level); direct-PC TCPD CSV not published for this LS year.

2024 onward ships from direct-PC TCPD returns and stays `minor`. Per-candidate rows in the same five LS years stay `minor` too - they are name-level vote counts, not aggregations; only the PC summary inherits the AC-segment caveat. Bumping these to `major` is the audit-loop closure that lets a citizen reading a 2009 PC turnout number see the receipt that the number was assembled from AC-grain inputs, not pulled verbatim from a PC-grain publisher cell. The `source_id` FK on the same row still points at the ECI election-returns ledger; the publisher rebrand from TCPD (the compiler) to ECI (the issuing authority) does not change the segment-aggregation provenance carried by `processing_level` + `processing_note`.
