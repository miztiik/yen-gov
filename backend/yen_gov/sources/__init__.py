"""ECI (Election Commission of India) source adapters.

Per docs/architecture/backend/overview.md the sources/ layer is allowed to import from core/. Adapters here
parse pages from results.eci.gov.in and turn them into core/models.py models.

Per docs/architecture/backend/sources-eci.md each ECI page type has its own module (e.g. partywise.py,
statistical_report_detailed.py, ls_constituencywise.py).
"""
