"""IndiaVotes party-catalogue scraper.

Single-threaded, 1 req/sec, cache-first (7-day window). Honours the same
politeness contract as ``tools/elections_parity_indiavotes/scrape.py``:
citizen User-Agent, no cookies / referrer / tracking headers, no
recursive crawl, no bulk download. Two endpoints:

  - **Listing**: ``https://www.indiavotes.com/parties`` -- one HTML page
    carrying the top ~60 most-active parties (sorted by LS seats won)
    in a single table.
  - **Detail**:  ``https://www.indiavotes.com/parties/<slug>/`` -- one
    HTML page per party, keyed by the lowercase publisher abbreviation.
    The detail page's ``<h1>`` is the canonical full name as IndiaVotes
    publishes it.

The scraper writes ``datasets/ephemeral/indiavotes-parties/2026-06/cache/...``
HTML pages locally; re-runs within the cache window are zero network
traffic. The cache is gitignored (ephemeral tier per CLAUDE.md section 3);
ONLY the parsed CSV output at ``registered.csv`` is committed.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Politeness contract -- identical to tools/elections_parity_indiavotes.
USER_AGENT = (
    "yen-gov-parity-oracle/0.1 "
    "(one-shot citizen audit; contact via github.com/yen-gov/yen-gov)"
)
REQUEST_INTERVAL_SECONDS = 1.1
REQUEST_TIMEOUT_SECONDS = 30.0
CACHE_MAX_AGE_DAYS = 7

LISTING_URL = "https://www.indiavotes.com/parties"
DETAIL_URL_TEMPLATE = "https://www.indiavotes.com/parties/{slug}/"

# Active-period parser: IV publishes "1952 - 2026" (en-dash). The
# trailing "2026" is IV's data-current-year sentinel, not a dissolution
# date. Anything strictly less than the current year IS treated as a
# dissolution.
_ACTIVE_PERIOD_RE = re.compile(r"(\d{4})\s*[\u2013\u2014\-]\s*(\d{4})")

# IV row column 1 carries "ABBREV - Full Party Name" with an em-dash
# separator. The capture splits the two parts so we get both the
# abbreviation (used as the slug key) and the full citizen-readable name
# without manual string-slicing in the caller.
_ROW_PARTY_RE = re.compile(r"^\s*([^\u2013\u2014\-]+?)\s+[\u2013\u2014\-]+\s+(.+?)\s*$")

# Detail URL slug regex: lowercase alphanumeric + hyphens; matches the
# href shape we observed on the listing page (/parties/inc/, /parties/cpm/,
# /parties/inc-i/). The caller uses this to normalise an arbitrary label
# (publisher short, full-name token) to the slug shape IV expects.
_SLUG_SANITISE_RE = re.compile(r"[^a-z0-9]+")


def slugify(label: str) -> str:
    """Project an arbitrary publisher label to IV's URL-slug shape.

    Lowercased, alphanumerics + collapsed-hyphens only. Returns "" for
    a label that has no alphanumeric content (caller should skip the
    probe rather than fetch /parties//).
    """
    s = _SLUG_SANITISE_RE.sub("-", label.lower()).strip("-")
    return s


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now(tz=timezone.utc).timestamp() - path.stat().st_mtime
    return age < CACHE_MAX_AGE_DAYS * 86400


def fetch_url(
    url: str,
    cache_path: Path,
    *,
    force_refetch: bool = False,
) -> tuple[Path, int]:
    """Fetch ``url`` into ``cache_path`` honouring the politeness contract.

    Returns ``(cache_path, status_code)``. On HTTP error (4xx/5xx) the
    response is NOT cached; the status code is returned so the caller can
    skip / surface. On success the response body is written to
    ``cache_path`` (parent created) and 200 is returned.

    Politeness invariants enforced here:

      - 1.1 req/sec single-threaded (the extra 100ms is slack so IV's
        rate-limiter never sees a burst on a cache miss + retry).
      - Citizen UA; no Cookie / Referer / X-* headers.
      - Cache-first: if the cache file is within ``CACHE_MAX_AGE_DAYS``,
        return immediately (zero network traffic).

    Cache hits return ``(cache_path, 200)`` so the caller's success-branch
    is identical for hits and live fetches.
    """
    if _cache_is_fresh(cache_path) and not force_refetch:
        return cache_path, 200
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, headers=headers) as client:
        time.sleep(REQUEST_INTERVAL_SECONDS)
        try:
            response = client.get(url, follow_redirects=True)
        except httpx.HTTPError:
            return cache_path, 0
    if response.status_code != 200:
        return cache_path, response.status_code
    cache_path.write_text(response.text, encoding="utf-8")
    return cache_path, 200


def parse_listing(html_path: Path) -> list[dict[str, str]]:
    """Parse the /parties listing HTML into per-party row dicts.

    Output row shape (string fields; empty when not present):

        {
          "party_abbreviation": "INC",
          "party_full_name":    "Indian National Congress",
          "slug":               "inc",
          "iv_type":            "national",
          "ls_seats_won":       "3,682",
          "vs_seats_won":       "11,250",
          "contested":          "42,998",
          "active_period_from": "1952",
          "active_period_to":   "2026",
        }

    Tolerant by design: rows that fail to parse the abbreviation /
    full-name split are silently skipped (the IV layout occasionally
    deviates for special-case rows like "IND - Independent" where the
    splitter still works on the em-dash convention but for safety we
    just drop unparseable rows rather than corrupt downstream).
    """
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    table = None
    for candidate in soup.find_all("table"):
        # The single table on /parties has these headers in order:
        # "Party", "Type", "LS seats won", "VS seats won", "Contested", "Active".
        hdrs = [th.get_text(strip=True).lower() for th in candidate.find_all("th")]
        if hdrs and "party" in hdrs[0]:
            table = candidate
            break
    if table is None:
        return []

    rows: list[dict[str, str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 6:
            continue
        # Column 0: party cell carries the href to /parties/<slug>/.
        a = cells[0].find("a")
        slug = ""
        if a is not None and a.has_attr("href"):
            href = a["href"].strip()
            m = re.search(r"/parties/([^/]+)/?", href)
            if m:
                slug = m.group(1).lower()
        cell0_text = cells[0].get_text(separator=" ", strip=True)
        m_party = _ROW_PARTY_RE.match(cell0_text)
        if not m_party:
            continue
        abbrev = m_party.group(1).strip()
        full_name = m_party.group(2).strip()
        if not slug:
            slug = slugify(abbrev)
        iv_type = cells[1].get_text(strip=True).lower()
        ls = cells[2].get_text(strip=True)
        vs = cells[3].get_text(strip=True)
        contested = cells[4].get_text(strip=True)
        active = cells[5].get_text(strip=True)
        m_active = _ACTIVE_PERIOD_RE.search(active)
        from_year = m_active.group(1) if m_active else ""
        to_year = m_active.group(2) if m_active else ""
        rows.append(
            {
                "party_abbreviation": abbrev,
                "party_full_name": full_name,
                "slug": slug,
                "iv_type": iv_type,
                "ls_seats_won": ls,
                "vs_seats_won": vs,
                "contested": contested,
                "active_period_from": from_year,
                "active_period_to": to_year,
            }
        )
    return rows


def parse_detail(html_path: Path, slug: str) -> dict[str, str] | None:
    """Parse a /parties/<slug>/ detail page into the same row shape.

    Detail pages carry the canonical full name in ``<h1>``. The
    abbreviation is the slug uppercased (IV's URL slug IS the
    abbreviation). Type / seat counts / contested / active are NOT
    available on the detail page (those are listing-only), so this
    function returns the minimal {abbrev, full, slug} triple. The
    caller's wider envelope MAY supply the missing fields when known
    (e.g. by intersecting with the listing rows).

    Returns ``None`` when the page lacks an ``<h1>`` (defensive; e.g.
    a 404 page that slipped through the status check).
    """
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if h1 is None:
        return None
    full_name = h1.get_text(strip=True)
    if not full_name:
        return None
    return {
        "party_abbreviation": slug.upper(),
        "party_full_name": full_name,
        "slug": slug,
        "iv_type": "",
        "ls_seats_won": "",
        "vs_seats_won": "",
        "contested": "",
        "active_period_from": "",
        "active_period_to": "",
    }
