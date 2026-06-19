"""ECI source adapters — parsers for results.eci.gov.in pages.

Per docs/architecture/backend/sources-eci.md each page family lives in its own module. After B4-pt2
(2026-06-06) + this PR's residuals cleanup the surviving parsers are:

  - partywise.py                  partywiseresult-<state>.htm  → party seat snapshot
  - statistical_report_detailed.py Section 10 XLSX             → per-AC DetailedResultsRaw
  - ls_constituencywise.py        ECI Report-33 LS CSV         → per-PC PcResultRaw
  - ls_ge_tcpd.py                 TCPD All-States GE CSV       → per-PC historical PcResultRaw
  - people_panel.py               panel CSV                    → ECI panel rows
  - section3.py                   Section 3 Participating-Parties XLSX → ParticipatingParty
  - events.py                     (state, year) → EventInfo registry

Schema-binding mappers live in core/models.py, not here. Adapters return either a model directly
(when the page contains everything needed) or a small adapter-local dataclass (when composition with
another page is required to fill the model).
"""
