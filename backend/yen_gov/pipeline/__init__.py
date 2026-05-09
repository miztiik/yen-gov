"""Pipeline orchestration: composes source-adapter outputs into emitted artifacts.

Per docs/architecture/backend/overview.md, `pipeline/` is the only layer allowed to import from `sources/`
and `core/` together. It owns:

  - composing identity coordinates (election/state/body) onto parsed pages,
  - threading cross-page data (e.g. party_lookup from partywise into
    constituencywise),
  - aggregating per-constituency results into per-state ResultSummary,
  - the run-level orchestrator (fetch → parse → compose → emit).
"""
