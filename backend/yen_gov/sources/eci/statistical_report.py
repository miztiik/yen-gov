"""ECI Statistical Report catalog + downloader (Phase B, current-year slice).

Two pure functions, no parsing:

  - statistical_report_catalog_url(category_id) -> str
        Builds the cleartext catalog URL the new ECI portal exposes for
        2024+ events: /eci-backend/public/api/election-result?category_id=<id>.

  - parse_catalog(content) -> CatalogResponse
        Turns the JSON response into a frozen dataclass: cat_name + a list of
        documents, each with stable xlsx_url and pdf_zip_url permalinks. The
        permalinks (under /eci-backend/public/all_files/election_report/...)
        are safe to persist in sources[]; the time-limited
        /api/download?url=<blob> signed URLs are NOT — see ADR-0016 / the
        authority-hierarchy section of docs/architecture/backend/sources-eci.md.

  - download_documents(catalog, *, fetcher, state_code, year)
        Fetches every (xlsx_url, pdf_zip_url) listed by the catalog through
        the existing Fetcher (so .runtime/raw/ placement is consistent with
        the rest of the adapter — ADR-0003). Returns the list of FetchResults
        so the caller can build sources[] with file-level fetched_at timestamps.

The two-phase split (catalog -> download) mirrors the parser convention in
this package: parsing/identity stays pure; the I/O is a separate call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from yen_gov.core.http import FetchResult, Fetcher

ECI_BACKEND_BASE = "https://www.eci.gov.in/eci-backend/public"


@dataclass(frozen=True)
class CatalogDocument:
    """One row of the Statistical Report catalog.

    Both xlsx_url and pdf_zip_url are the stable
    /all_files/election_report/... permalinks — safe to persist in sources[].
    """

    id: int
    title: str
    xlsx_url: str
    pdf_zip_url: str


@dataclass(frozen=True)
class CatalogResponse:
    """Parsed /api/election-result response.

    cat_name is the human-facing election title (e.g. "General Election to
    the Legislative Assembly of Tamil Nadu 2026"). index_name distinguishes
    the "Copy of Index Cards [Digital]" Statistical Report family from the
    per-AC "Index Cards" family — Phase B targets only the former.
    """

    category_id: int
    cat_name: str
    index_name: str
    documents: tuple[CatalogDocument, ...]


def statistical_report_catalog_url(category_id: int) -> str:
    if category_id < 1:
        raise ValueError(f"category_id must be >= 1, got {category_id}")
    return f"{ECI_BACKEND_BASE}/api/election-result?category_id={category_id}"


def parse_catalog(content: bytes) -> CatalogResponse:
    """Turn the raw JSON response into a CatalogResponse.

    Raises ValueError on structural surprises (missing fields, wrong shape).
    Silent fallback to an empty catalog would let an ECI redesign go
    unnoticed for an entire election cycle — same posture as the HTML
    parsers in this package.
    """
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ECI catalog response is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("status") != 1:
        raise ValueError(
            f"ECI catalog response missing status=1: {payload!r}"[:200]
        )

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("ECI catalog response has no 'results' list")

    docs = []
    for row in results:
        for required in ("id", "title", "xlsx_url", "pdf_zip_url", "category_id"):
            if required not in row:
                raise ValueError(
                    f"ECI catalog row missing {required!r}: {row!r}"[:200]
                )
        docs.append(
            CatalogDocument(
                id=int(row["id"]),
                title=str(row["title"]),
                xlsx_url=str(row["xlsx_url"]),
                pdf_zip_url=str(row["pdf_zip_url"]),
            )
        )

    return CatalogResponse(
        category_id=int(results[0]["category_id"]),
        cat_name=str(payload.get("cat_name") or ""),
        index_name=str(payload.get("index_name") or ""),
        documents=tuple(docs),
    )


def fetch_catalog(category_id: int, *, fetcher: Fetcher) -> CatalogResponse:
    """Convenience: build URL, fetch, parse. Returns the typed response."""
    url = statistical_report_catalog_url(category_id)
    result = fetcher.fetch(url)
    return parse_catalog(result.content)


def download_documents(
    catalog: CatalogResponse,
    *,
    fetcher: Fetcher,
    include_pdf: bool = True,
) -> list[FetchResult]:
    """Fetch every xlsx (and optionally pdf_zip) url listed in the catalog.

    Returns the FetchResults in the order they were fetched so the caller
    can build sources[] entries with file-level fetched_at. The on-disk
    placement is whatever the Fetcher derives from the URL — typically
    .runtime/raw/eci/eci-backend/public/all_files/election_report/<title>/<file>.
    Per ADR-0003 these on-disk paths are NOT persisted in sources[].
    """
    fetched: list[FetchResult] = []
    for doc in catalog.documents:
        fetched.append(fetcher.fetch(doc.xlsx_url))
        if include_pdf:
            fetched.append(fetcher.fetch(doc.pdf_zip_url))
    return fetched


def iter_permalinks(catalog: CatalogResponse) -> Iterable[str]:
    """Yield every stable permalink in catalog order (xlsx then pdf per row)."""
    for doc in catalog.documents:
        yield doc.xlsx_url
        yield doc.pdf_zip_url
