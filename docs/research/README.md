# yen-gov Research Notes

**Last Updated**: 2026-05-10

This tier captures **per-topic upstream research** so future maintainers (human or agent) don't have to re-discover what we already evaluated.

A research note is the **answer to "where does this dataset come from, what other sources did we consider, and why did we pick what we picked"**. It is the durable companion to a one-line `sources` URL in an emitted artifact.

## When to add a note

Whenever a new dataset, indicator, or upstream is introduced, add (or update) a note here in the same commit as the source adapter or ingestion script. Holy Law #4 (CLAUDE.md §1) — every design decision is documented; the natural home for "why this upstream" is here.

## Conventions

- One file per topic, kebab-case (e.g. `energy-power-plants.md`).
- H1 title; `Last Updated: YYYY-MM-DD`; `Status:` line (active / superseded / deferred).
- Sections (in order):
  1. **Question** — what we needed.
  2. **Candidates** — every upstream considered, with URL, license, coverage, freshness, format, attribution requirement.
  3. **Decision** — what we picked and the reason.
  4. **Open follow-ups** — known gaps to revisit.
  5. **References** — verbatim URLs verified at the date stamp above.
- Every URL is dated (we record the date we visited it). Web sources rot.
- Every license is named with its SPDX identifier where one exists; "Unspecified" is a valid label per D9 (it tells the truth).
- Cross-link the schema file(s) and source adapter module(s) the note governs.

## Index

| Topic                              | File                                                                       | Status   |
| ---------------------------------- | -------------------------------------------------------------------------- | -------- |
| Aggregator: india-geodata          | [`india-geodata.md`](india-geodata.md)                                     | active   |
| Energy: power plants               | [`energy-power-plants.md`](energy-power-plants.md)                         | active   |
| State GDP (RBI Handbook)           | [`state-gdp-rbi.md`](state-gdp-rbi.md)                                     | planned  |
| Healthcare facilities              | [`healthcare-facilities.md`](healthcare-facilities.md)                     | planned  |
| State government history (CMs)     | [`state-government-history.md`](state-government-history.md)               | planned  |
| License handling (D9 implementation)| [`license-handling.md`](license-handling.md)                              | planned  |

## See also

- [`TODO/SOCIO-ECONOMIC-EXPANSION.md`](../../TODO/SOCIO-ECONOMIC-EXPANSION.md) — the umbrella plan that triggered this tier.
- [`docs/concepts/data-provenance.md`](../concepts/data-provenance.md) — the file-level `sources` contract this complements.
- [CLAUDE.md §12](../../CLAUDE.md) — provenance law.
