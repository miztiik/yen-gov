"""Pinned URLs for RBI ``State Finances: A Study of Budgets`` Statement workbooks.

RBI publishes ONE XLSX per Statement / Appendix Table on the
annual-publications page. URL slugs include a date stamp (e.g.
``23012026`` = Jan 23, 2026 = the State Finances 2025-26 budgets
edition) plus an opaque hex hash. New editions land each December /
January and the URLs change wholesale — there is no stable redirect.

Recon procedure (run on each new edition)::

    python tools/rbi_recon.py --dump
    # Inspect .runtime/rbi_titles.txt for ``Statement <N>: <title>``
    # lines; copy the URL into the matching entry below.

The ``ingest`` orchestrator resolves URLs in this order:

  1. ``KNOWN_URLS[<indicator_id>][<edition>]`` (this file)
  2. ``$RBI_STATE_FINANCES_<INDICATOR_KEY>_URL`` env-var override
  3. local cache at ``.runtime/raw/rbi/state_finances/<filename>.xlsx``

If none resolves, ingest raises with operator instructions. We never
silently emit indicators without real bytes.

See ``docs/architecture/backend/sources-rbi.md`` for the indicator
contracts and the per-Statement → indicator mapping.
"""
from __future__ import annotations


LISTING_PAGE = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
    "?head=State+Finances+%3A+A+Study+of+Budgets"
)

# Authority page that introduces the publication (used as the second
# entry in each indicator's ``sources[]`` so citizens can audit the
# context, not just the bare XLSX).
RBI_AUTHORITY_URL = LISTING_PAGE


# Per-indicator pinned URLs. Outer key is indicator id; inner key is
# edition stamp ``DDMMYYYY`` so that lexicographic max gives the
# LATEST edition (see ``latest_url``).
#
# Verified Phase C (edition 23012026 = State Finances 2025-26):
KNOWN_URLS: dict[str, dict[str, str]] = {
    "fiscal/outstanding_debt_pct_gsdp": {
        "23012026": (
            "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/"
            "20_ST2301202696AC652FC4CE482EAAD928FC544CD86A.XLSX"
        ),
    },
    # Statement 17: "Devolution and Transfer of Resources from the Centre".
    # Per-state, 3 fiscal years (2023-24 Accounts, 2024-25 RE, 2025-26 BE),
    # stacked Gross | Net* sub-columns under each fiscal year. We extract
    # the Net column (RBI's net-of-adjustments figure).
    "fiscal/net_transfers_from_centre": {
        "23012026": (
            "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/"
            "17_ST2301202683B49BF6F4584A6985B2CCCAA41B020E.XLSX"
        ),
    },
    # Statement 27: "Expenditure on Medical and Public Health and
    # Family Welfare" — per-cent of each state's aggregate expenditure.
    # 18 fiscal years 2008-09 through 2025-26 (last two RE / BE).
    # Includes revenue + capital outlay. Delhi + Puducherry coverage
    # starts 2017-18 (per source footnote).
    "health/state_health_expenditure_pct_total_expenditure": {
        "23012026": (
            "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/"
            "27_ST23012026CC86B1004D0246F9A46EE80264885103.XLSX"
        ),
    },
}


def latest_url(indicator_id: str) -> tuple[str, str] | None:
    """Return ``(edition_stamp, url)`` for the most recent pinned URL of an
    indicator, or ``None`` if no URL has been pinned for it yet."""
    by_edition = KNOWN_URLS.get(indicator_id)
    if not by_edition:
        return None
    edition = max(by_edition.keys())
    return edition, by_edition[edition]
