"""Pinned URLs for the RBI State Finances workbook.

The RBI annual-publications page hosts each year's edition under a
freshly-numbered PDF + Excel pair. URL slugs include a date suffix
(``Statements_<dd><MMM><yy>.xlsx``) that changes every December when
the new edition lands.

Until Phase B recon completes, this registry is **empty**. The
``ingest`` orchestrator looks here first, falls back to:

  1. ``$RBI_STATE_FINANCES_URL`` env var (operator-pasted URL), then
  2. local ``.runtime/raw/rbi/state_finances/<year>.xlsx`` (operator
     manually downloaded the workbook).

If none of those resolve, ``ingest`` raises ``RBISourceUnavailable``
with instructions for the operator. We never silently emit indicators
without real bytes.

Update procedure (Phase B recon):
  1. Visit the RBI publications page (URL in ``LISTING_PAGE``).
  2. Click the latest *State Finances: A Study of Budgets* link.
  3. Right-click the *Statements* Excel link → Copy link address.
  4. Add an entry to ``KNOWN_URLS`` with the fiscal-year span as key.
  5. Commit. The next admin pipeline run picks it up.
"""
from __future__ import annotations


LISTING_PAGE = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
    "?head=State+Finances+%3A+A+Study+of+Budgets"
)

# Map of "fiscal-year span" → direct XLSX URL. Empty until recon.
# Example shape (do NOT use this URL — it is illustrative):
#   "2024-25": "https://rbidocs.rbi.org.in/rdocs/Publications/PDFs/Statements_18DEC24XXXX.xlsx",
KNOWN_URLS: dict[str, str] = {}


def latest_known_url() -> tuple[str, str] | None:
    """Return ``(fiscal_year_span, url)`` for the most recent pinned URL.

    Returns ``None`` when the registry is empty so the orchestrator can
    fall back to env / local cache.
    """
    if not KNOWN_URLS:
        return None
    fy = max(KNOWN_URLS.keys())  # lexicographic max == most recent FY
    return fy, KNOWN_URLS[fy]
