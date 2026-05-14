"""RBI Handbook of Statistics on Indian Economy — Table 89 (Centre's Key Deficit Indicators).

Sibling-by-shape of :mod:`yen_gov.sources.rbi_appendix_deficits` (which
ships the same four indicators for the **states-combined** actor): the
HBS-IE Table 89 workbook has the same row-per-fiscal-year × column-per-
indicator layout as the State Finances AppT1, just without the
alternating %-of-GDP rows. We therefore reuse the AppT1 parser
(:func:`yen_gov.sources.rbi_appendix_deficits.parsers.parse_workbook`)
verbatim and only ship a thin orchestrator + Centre-flavoured
indicator metadata.

Closes the asymmetry recorded in ADR-0025 (Step B) — until this adapter
shipped, yen-gov surfaced states-combined deficits but not the Union
Government's own borrowing, leaving citizens with the Factfulness
"Blame instinct" reading that states are profligate while the Centre
only sends money out. In FY24 the Union GFD was ~5.6% of GDP, larger
than states-combined ~3.2%; until both halves are visible side by side,
the data architecture itself misframes responsibility.

Public surface: :func:`ingest` (in :mod:`.ingest`).

See ``docs/architecture/backend/sources-rbi-hbs-ie-centre-deficits.md``
for the operator runbook and indicator catalogue.
"""
