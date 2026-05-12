"""Static Statistical Report catalogs for ECI cohorts not exposed via the
2024+ ``/api/election-result?category_id=`` endpoint.

The 2023 cohort (Madhya Pradesh, Chhattisgarh, Mizoram, Telangana) is
published as a fixed bundle of XLSX/PDF files under

    https://www.eci.gov.in/eci-backend/public/all_files/full-statistical-reports/<state-slug>/2023/<Statement>.{xlsx,pdf}

with the same 14 statements as the 2024+ Statistical Report family but
exposed through hand-built landing pages
(``www.eci.gov.in/<state>-legislative-election-2023-statistical-report``)
rather than the cleartext catalog API. We don't fetch the landing pages
at ingest time \u2014 the URL templates above are stable and the statement
list is invariant across the four states (recon: tools/eci_2023_recon.py
on 2026-05-12).

This module synthesises a :class:`CatalogResponse` from those static URLs
so the rest of the Statistical Report pipeline (Section 10 parser,
Section 3 parser, ``compose_result_summary_from_section_10``) reuses
without branching. The 2024+ API path remains unchanged in
:mod:`yen_gov.sources.eci.statistical_report`; the dispatcher in
:func:`resolve_catalog` picks between them.

Adding a new (state, year) is a code change in this file, mirroring the
EVENTS registry in :mod:`yen_gov.sources.eci.events` \u2014 these cohorts are
historical and immutable, so autodiscovery would only add risk.
"""

from __future__ import annotations

from yen_gov.sources.eci.statistical_report import (
    CatalogDocument,
    CatalogResponse,
    ECI_BACKEND_BASE,
    fetch_catalog,
)
from yen_gov.core.http import Fetcher
from yen_gov.sources.eci.categories import (
    STATISTICAL_REPORT_CATEGORY_ID,
    category_id_for,
)


# Canonical 14-statement bundle, ordered as ECI publishes them. The
# (display title, stem) tuple drives the synthesised documents \u2014 stem is
# the filename (no extension) at the static URL.
_STATEMENTS_2023: tuple[tuple[str, str], ...] = (
    ("1 - Other Abbreviations And Description", "Other_Abbreviations_And_Description"),
    ("2 - List of Successful Candidates", "List_of_Successful_Candidates"),
    ("3 - List Of Political Parties Participated", "List_Of_Political_Parties_Participated"),
    ("4 - Highlight", "Highlight"),
    ("5 - Performance of Political Parties", "Performance_of_Political_Parties"),
    ("6 - Electors Data Summary", "Electors_Data_Summary"),
    ("7 - Individual Performance Of Women Candidate", "Individual_Performance_Of_Women_Candidate"),
    ("8 - Constituency Data Summary Report", "Constituency_Data_Summery_Report"),  # ECI's typo, preserved
    ("9 - Candidate Data Summary", "Candidate_Data_Summary"),
    ("10 - Detailed Results", "Detailed_Results"),
    ("11 - AC Wise Number Of Electors", "AC_Wise_Number_Of_Electors"),
    ("12 - AC Wise Voters Information", "AC_Wise_Voters_Information"),
    ("13 - AC Wise Candidate data Summary", "AC_Wise_Candidate_data_Summary"),
    ("14 - Electors Data Summary Annxure-1", "Electors_Data_Summary_Annxure-1"),  # ECI's typo, preserved
)

_STATIC_BASE_2023 = f"{ECI_BACKEND_BASE}/all_files/full-statistical-reports"

# Headers required to fetch from /all_files/full-statistical-reports/.
# The Akamai WAF in front of www.eci.gov.in returns 403 for the static
# legacy path unless the request looks like a top-level browser navigation
# (Mozilla/5.0 alone is NOT enough — verified 2026-05-12, recon at
# tools/eci_2023_recon.py). The 2024+ /api path is more permissive but
# also accepts these headers, so they're safe to pass uniformly when this
# adapter's static path is in play.
STATIC_CATALOG_BROWSER_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.eci.gov.in/statistical-reports",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}

# (state_code, year) -> (state_slug-on-eci, cat_name)
# state_slug is the path component inside the URL (NOT the ECI code).
_STATIC_CATALOGS: dict[tuple[str, int], tuple[str, str]] = {
    ("S12", 2023): ("mp", "Madhya Pradesh Legislative Election 2023 \u2014 Statistical Report"),
    ("S26", 2023): ("chhattisgarh", "Chhattisgarh Legislative Election 2023 \u2014 Statistical Report"),
    ("S16", 2023): ("mizoram", "Mizoram Legislative Election 2023 \u2014 Statistical Report"),
    ("S29", 2023): ("telangana", "Telangana Legislative Election 2023 \u2014 Statistical Report"),
}


def _synthesize_catalog_2023(state_slug: str, cat_name: str) -> CatalogResponse:
    """Build a CatalogResponse from the 2023 static URL template.

    ``id`` and ``category_id`` are synthetic (-1) \u2014 the static path has no
    upstream id family. Consumers that key by ``id`` would be a code smell;
    the only field anyone reads downstream is ``xlsx_url``/``pdf_zip_url``.
    """
    docs = tuple(
        CatalogDocument(
            id=-1,
            title=title,
            xlsx_url=f"{_STATIC_BASE_2023}/{state_slug}/2023/{stem}.xlsx",
            # The 2023 publication does not ship a per-statement ZIP; the
            # individual PDF stands in. Same field name is reused so the
            # downstream catalog walker treats it uniformly.
            pdf_zip_url=f"{_STATIC_BASE_2023}/{state_slug}/2023/{stem}.pdf",
        )
        for title, stem in _STATEMENTS_2023
    )
    return CatalogResponse(
        category_id=-1,
        cat_name=cat_name,
        index_name="Static Statistical Report (2023 cohort)",
        documents=docs,
    )


def has_static_catalog(state_code: str, year: int) -> bool:
    """True if (state, year) is served by the static 2023 path."""
    return (state_code, year) in _STATIC_CATALOGS


def static_catalog_for(state_code: str, year: int) -> CatalogResponse:
    """Return the synthesized static catalog, or raise a directive KeyError.

    The fail-loud message tells the caller which file to extend rather
    than silently returning an empty catalog (per CLAUDE.md \u00a76 / source
    adapter convention).
    """
    try:
        slug, cat_name = _STATIC_CATALOGS[(state_code, year)]
    except KeyError as exc:
        raise KeyError(
            f"no static Statistical Report catalog for ({state_code!r}, {year}); "
            f"extend _STATIC_CATALOGS in "
            f"backend/yen_gov/sources/eci/static_catalog.py"
        ) from exc
    return _synthesize_catalog_2023(slug, cat_name)


def resolve_catalog(
    state_code: str, year: int, *, fetcher: Fetcher,
) -> CatalogResponse:
    """Dispatch to the static-catalog path (no network) or the API catalog.

    Resolution order:

    1. ``config/eci-pins.json`` pin (2024+ family) \u2014 round-trips through
       the cleartext ``/api/election-result?category_id=<id>`` endpoint.
       This is the PRIMARY path; new live cohorts get a pin during recon
       and are never touched here.
    2. Static catalog registry above (2023 cohort) \u2014 synthesised from
       the published URL template, no network call.
    3. KeyError with a directive message that tells the caller exactly
       which two files to consider extending.

    Pinned ids ALWAYS win over the static registry: if a (state, year) is
    in both, the API path is authoritative. This guards against the
    plausible future where ECI republishes the 2023 cohort under the
    unified API \u2014 the static fallback decays into a dead branch the day
    the pin appears.
    """
    if (state_code, year) in STATISTICAL_REPORT_CATEGORY_ID:
        cid = category_id_for(state_code, year)
        return fetch_catalog(cid, fetcher=fetcher)
    if has_static_catalog(state_code, year):
        return static_catalog_for(state_code, year)
    raise KeyError(
        f"no Statistical Report catalog for ({state_code!r}, {year}); "
        f"either pin a category_id in config/eci-pins.json (2024+ API) or "
        f"add a static entry to _STATIC_CATALOGS in "
        f"backend/yen_gov/sources/eci/static_catalog.py (legacy cohorts)"
    )
