"""RBI ``State Finances: A Study of Budgets`` Appendix Tables (national).

These appendix tables are the all-India aggregate companion to the
per-state Statements parsed by :mod:`yen_gov.sources.rbi_xlsx`. Each
appendix workbook contains 1–3 sheets where each sheet holds a year
band: rows are *items* (devolution, grants, etc.), columns are
fiscal-year periods. Stitching the sheets gives one continuous
national time series spanning ~20 fiscal years.

This package handles the column-time / row-item shape; the rbi_xlsx
package handles the row-state / column-period (per-state) shape. Two
shapes, two parsers — by intent (Holy Law #5: structural fixes only).
"""
