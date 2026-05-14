"""RBI Appendix Table 1 (Major Deficit Indicators) - national time series.

Sibling of :mod:`yen_gov.sources.rbi_appendix_national`: same RBI
publication ("State Finances: A Study of Budgets"), different appendix
table. AppT1 has rows = fiscal years (Rs Crore + % GDP interleaved on
alternating rows) and columns = deficit indicators, the transpose of
App T2's row=item shape, so it gets its own parser.

Public surface: :func:`ingest` (in :mod:`.ingest`),
:class:`DeficitSpec` and :func:`parse_workbook` (in :mod:`.parsers`).

See ``docs/architecture/backend/sources-rbi-appendix-deficits.md`` for
the operator runbook and indicator catalogue.
"""
