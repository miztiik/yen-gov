"""ECI source adapters — parsers for results.eci.gov.in pages.

Per docs/architecture/backend/sources-eci.md each page family lives in its own module:

  - urls.py             URL builders (the only place URL templates live)
  - partywise.py        partywiseresult-<state>.htm  → party seat snapshot
  - constituencywise.py ConstituencyWise<state><n>.htm → ConstituencyResult

Schema-binding parsers (constituencywise → ConstituencyResult) live in
core/models.py, not here. Adapters return either a model directly (when the
page contains everything needed) or a small adapter-local dataclass (when
composition with another page is required to fill the model).
"""
