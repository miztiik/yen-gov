"""ECI (Election Commission of India) source adapters.

Per docs/architecture/backend/overview.md the sources/ layer is allowed to import from core/. Adapters here
parse pages from results.eci.gov.in and turn them into core/models.py models.

Per docs/architecture/backend/sources-eci.md each ECI page type has its own module: partywise.py, constituencywise.py.
URL building is centralised in urls.py to keep parsers focused on HTML.
"""
