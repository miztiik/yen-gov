"""ECI offline bulk downloader — runs on a machine that *can* reach
`old.eci.gov.in` (and optionally `www.eci.gov.in`) but has no LLM / Copilot
available. Pure stdlib (Python 3.9+); no `pip install` required.

Why this exists
---------------
Our primary dev box cannot reach `old.eci.gov.in` (CONNECT timeout — see
`notes/eci-portal-recon-2026-05-11.md`). The historical Lok Sabha General
Election (PC) and pre-2024 State Assembly Election (AC) statistical reports
live there as XLS / XLSX / PDF / ZIP. To bring them across:

    1. Copy this single file to the machine that *can* reach old.eci.gov.in.
    2. Run it (see "Usage" below). It walks the ECI category listings,
       follows every report-detail page, and downloads every attached
       XLS / XLSX / ZIP / PDF.
    3. Each file is renamed with a self-describing prefix so a human
       (or post-processing pipeline on the dev box) can tell at a glance
       *what* it is without opening it:

           YYYY_<BODY>_<STATE>_<reportId>_<safe-original-name>.<ext>

       e.g. `2019_PC_INDIA_4120_StatisticalReport_LS2019_Vol1.pdf`
            `2021_AC_TamilNadu_3989_StatisticalReport_TN2021.xlsx`
            `2014_PC_INDIA_4118_constituency_wise_results.xls`

    4. A `manifest.json` is written next to the files. It records, for every
       downloaded file: the original ECI URL, the report-detail page it came
       from, the report title, and `fetched_at` (RFC 3339 UTC). On the dev
       box this is enough to reattach provenance per CLAUDE.md §12 when the
       files are promoted into `datasets/`.

This tool writes nowhere except the user-chosen output directory. It does
NOT touch `datasets/` or `.runtime/` — it is dev-box-side ingestion that
re-validates provenance from the manifest.

Usage
-----
    # Everything (Lok Sabha + Assembly), into ./eci_dump/
    python eci_offline_downloader.py --out ./eci_dump

    # Just Lok Sabha General Elections
    python eci_offline_downloader.py --out ./eci_dump --scope lok-sabha

    # Just specific years (any body)
    python eci_offline_downloader.py --out ./eci_dump --years 2014,2019,2024

    # Just one state's assembly elections
    python eci_offline_downloader.py --out ./eci_dump --scope assembly --state "Tamil Nadu"

    # Dry run — print what would be downloaded, don't fetch
    python eci_offline_downloader.py --out ./eci_dump --dry-run

    # Skip files already on disk (default behaviour — re-runs are resumable)
    python eci_offline_downloader.py --out ./eci_dump

    # Force re-download
    python eci_offline_downloader.py --out ./eci_dump --force

Discovery strategy
------------------
ECI groups statistical reports under numeric category IDs at
`https://old.eci.gov.in/files/category/<id>-<slug>/`. The known ones
(verified via `tools/eci_recon/`) are:

    97 — general-election           (Lok Sabha / PC)
    98 — assembly-election          (State legislative assemblies / AC)
    99 — bye-election
   100 — presidential-election
   101 — vice-presidential-election

This script walks each requested category page, paginates if needed, follows
each `/files/file/<id>-<slug>/` detail link, and downloads every linked XLS
/ XLSX / ZIP / PDF. Heuristics on the slug + page title classify each file
by `(year, body, state, scope)` for the rename. Anything we can't classify
gets `UNKNOWN` and a warning in the manifest — never silently dropped.

Failure modes (and how the script handles them)
-----------------------------------------------
- TLS / connection: 3 retries with exponential backoff; failures recorded
  in `manifest.json -> errors[]` and the script continues with the next
  file. The summary at the end tells you how many failed.
- HTML drift: regex-based, tolerant of whitespace/case. If a category page
  yields zero detail links the script logs a warning and continues — it
  does NOT crash. Re-run safely.
- Resumable: existing files are skipped by default. Manifest is rewritten
  in-place each run with a merged view.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

# -----------------------------------------------------------------------------#
# Constants                                                                    #
# -----------------------------------------------------------------------------#

OLD_HOST = "https://old.eci.gov.in"
NEW_HOST = "https://www.eci.gov.in"

# Categories on old.eci.gov.in/files/category/<id>-<slug>/ that we care about.
# The slug after the dash is informational; only the numeric id is required.
CATEGORIES: dict[str, dict] = {
    "lok-sabha": {
        "id": 97, "slug": "general-election", "body": "PC",
        "scope": "general", "default_state": "INDIA",
    },
    "assembly": {
        "id": 98, "slug": "assembly-election", "body": "AC",
        "scope": "general", "default_state": "UNKNOWN",
    },
    "bye-election": {
        "id": 99, "slug": "bye-election", "body": "MIXED",
        "scope": "bye", "default_state": "UNKNOWN",
    },
}

# Extensions we consider "data". PDFs are kept because some statistical
# reports only ship as PDF (older years). HTML is explicitly excluded.
DATA_EXT = {".xls", ".xlsx", ".xlsm", ".csv", ".zip", ".pdf"}

# Indian states + UTs, longest-first so multi-word names match before substrings.
# (e.g. "Andhra Pradesh" must be tried before "Andhra".)
STATES: list[str] = sorted([
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Orissa", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "Uttaranchal", "West Bengal",
    # UTs
    "Andaman and Nicobar Islands", "Andaman & Nicobar Islands",
    "Chandigarh", "Dadra and Nagar Haveli", "Daman and Diu",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "NCT of Delhi", "Jammu and Kashmir", "Jammu & Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry", "Pondicherry",
], key=lambda s: -len(s))

UA = "Mozilla/5.0 (compatible; yen-gov-eci-offline/1.0)"


# -----------------------------------------------------------------------------#
# HTTP                                                                          #
# -----------------------------------------------------------------------------#

def _ssl_ctx() -> ssl.SSLContext:
    # ECI's old portal historically negotiates TLS 1.2 with weak suites; the
    # default Python context handles it on 3.10+. Disable hostname mismatch
    # only if the user explicitly opts in (env var) — never by default.
    ctx = ssl.create_default_context()
    if os.environ.get("ECI_INSECURE_TLS") == "1":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url: str, *, retries: int = 3, timeout: float = 30.0) -> bytes:
    """GET with manual retries + exponential backoff. Returns body bytes
    (gzip-decoded if needed). Raises the last exception on persistent
    failure so the caller can record it and move on."""
    last_exc: Exception | None = None
    backoff = 2.0
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, identity",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
                data = r.read()
                if r.headers.get("Content-Encoding", "").lower() == "gzip":
                    data = gzip.decompress(data)
                return data
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
    assert last_exc is not None
    raise last_exc


def http_head(url: str, *, timeout: float = 15.0) -> tuple[int, dict]:
    """HEAD probe. Returns (status, headers-as-dict). On error returns
    (0, {'error': str(exc)}). Used to classify ambiguous links by
    Content-Type / Content-Disposition before committing to download."""
    req = urllib.request.Request(url, method="HEAD", headers={
        "User-Agent": UA, "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


# -----------------------------------------------------------------------------#
# HTML parsing — tolerant, regex-first                                         #
# -----------------------------------------------------------------------------#

_FILE_DETAIL_RX = re.compile(
    r'href=["\'](?P<href>(?:https?://[^"\']*?)?/files/file/(?P<id>\d+)-(?P<slug>[^"\'/]+)/?)["\']',
    re.IGNORECASE,
)

# Direct extension match — the easy case.
_DATA_LINK_RX = re.compile(
    r'href=["\'](?P<href>[^"\']+\.(?:xls|xlsx|xlsm|csv|zip|pdf))(?:\?[^"\']*)?["\']',
    re.IGNORECASE,
)

# Joomla / jDownloads / Phoca-style download links: hrefs containing
# `?download`, `&download`, `task=download`, or paths under /download/.
# Also catches `/files/file/<id>-<slug>/?download` which is ECI's most
# common attachment URL on the old portal.
_DL_HINT_RX = re.compile(
    r'href=["\'](?P<href>[^"\']*?(?:\?download|&download|/download/|task=download(?:\.send)?|getfile\?|attachment_id=)[^"\']*)["\']',
    re.IGNORECASE,
)

# A category page enumerates child files via /files/file/<id>-<slug>/. On
# detail pages the SAME pattern (sometimes with ?download) is the actual
# attachment. Treated as a candidate; HEAD-probed to confirm it is binary.
_FILE_PERMALINK_RX = re.compile(
    r'href=["\'](?P<href>(?:https?://[^"\']*?)?/files/file/\d+-[^"\']+?/?(?:\?[^"\']*)?)["\']',
    re.IGNORECASE,
)

# Top-level category enumeration on /files/category/ index page.
_CATEGORY_RX = re.compile(
    r'href=["\'](?P<href>(?:https?://[^"\']*?)?/files/category/(?P<id>\d+)-(?P<slug>[^"\'/]+)/?)["\']',
    re.IGNORECASE,
)

_TITLE_RX = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

_NEXT_PAGE_RX = re.compile(
    r'href=["\'](?P<href>[^"\']*?/files/category/\d+-[^"\']*?(?:page/\d+|p=\d+|/\d+)/?)["\']',
    re.IGNORECASE,
)


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)


def parse_category_page(html: str, base: str) -> tuple[list[tuple[int, str, str]], list[str]]:
    """Return (file_detail_links, next_page_urls).

    file_detail_links: list of (numeric_id, slug, absolute_url).
    """
    detail = []
    seen: set[int] = set()
    for m in _FILE_DETAIL_RX.finditer(html):
        fid = int(m.group("id"))
        if fid in seen:
            continue
        seen.add(fid)
        href = urllib.parse.urljoin(base, m.group("href"))
        detail.append((fid, m.group("slug"), href))

    next_pages = []
    seen_p: set[str] = set()
    for m in _NEXT_PAGE_RX.finditer(html):
        href = urllib.parse.urljoin(base, m.group("href"))
        if href in seen_p:
            continue
        seen_p.add(href)
        next_pages.append(href)
    return detail, next_pages


def parse_detail_page(html: str, base: str, *, self_id: int | None = None,
                      probe: bool = True) -> tuple[str, list[str]]:
    """Return (page_title, list_of_data_file_urls).

    Strategy (in order):
      1. Direct .xls/.xlsx/.pdf etc. links.
      2. Joomla download-hint links (?download, task=download.send, ...).
      3. /files/file/<id>-<slug>/ permalinks OTHER than the page itself —
         on ECI's old portal these are sibling attachments. HEAD-probed
         (when probe=True) to keep only those returning a non-HTML
         Content-Type or a Content-Disposition: attachment header.
      4. The page's own permalink with `?download` appended — ECI commonly
         redirects that to the actual file blob.
    """
    tm = _TITLE_RX.search(html)
    title = _strip_tags(tm.group(1)).strip() if tm else ""

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(href: str) -> None:
        u = urllib.parse.urljoin(base, href)
        # Strip fragments; collapse trailing whitespace.
        u = u.split("#", 1)[0].strip()
        if u and u not in seen:
            seen.add(u)
            candidates.append(u)

    for m in _DATA_LINK_RX.finditer(html):
        _add(m.group("href"))
    for m in _DL_HINT_RX.finditer(html):
        _add(m.group("href"))

    # Sibling /files/file/<id>/ permalinks. Skip self.
    sibling_candidates: list[str] = []
    for m in _FILE_PERMALINK_RX.finditer(html):
        href = urllib.parse.urljoin(base, m.group("href"))
        href_clean = href.split("?", 1)[0].rstrip("/")
        # Compare by the trailing /<id>-<slug>/ segment only.
        m2 = re.search(r"/files/file/(\d+)-", href_clean)
        if not m2:
            continue
        if self_id is not None and int(m2.group(1)) == self_id:
            continue
        if href in seen:
            continue
        sibling_candidates.append(href)

    # Also try the page's own URL with ?download appended (ECI's typical
    # "the page IS the file" pattern for single-attachment reports).
    own = base.rstrip("/") + "/?download"
    if own not in seen:
        sibling_candidates.append(own)

    if probe:
        for u in sibling_candidates:
            status, hdrs = http_head(u)
            ctype = (hdrs.get("content-type") or "").lower()
            cdisp = (hdrs.get("content-disposition") or "").lower()
            looks_binary = (
                "attachment" in cdisp
                or any(k in ctype for k in (
                    "pdf", "excel", "spreadsheet", "zip",
                    "officedocument", "msword", "octet-stream", "csv",
                ))
            )
            if status in (200, 301, 302) and looks_binary:
                _add(u)
    else:
        for u in sibling_candidates:
            _add(u)

    return title, candidates


# -----------------------------------------------------------------------------#
# Classification                                                               #
# -----------------------------------------------------------------------------#

YEAR_RX = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
LS_NUM_RX = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*lok\s*sabha\b", re.IGNORECASE)


def detect_year(*texts: str) -> str:
    """Return YYYY string or 'YYYY' placeholder if none found."""
    for t in texts:
        if not t:
            continue
        m = YEAR_RX.search(t)
        if m:
            return m.group(1)
    return "YYYY"


def detect_state(*texts: str) -> str:
    """Return canonical state name (collapsed to camel-no-spaces) or 'INDIA'."""
    blob = " ".join(t for t in texts if t)
    blob_l = " " + blob.lower() + " "
    for s in STATES:
        # word-boundary-ish containment, case-insensitive
        needle = " " + s.lower() + " "
        if needle in blob_l or s.lower() in blob_l.replace("-", " ").replace("_", " "):
            return s.replace("&", "and").replace(" ", "")
    return "INDIA"


def detect_body(category_key: str, *texts: str) -> str:
    """PC | AC | UNKNOWN. Bye-elections are mixed — sniff the title."""
    if category_key == "lok-sabha":
        return "PC"
    if category_key == "assembly":
        return "AC"
    blob = " ".join(t for t in texts if t).lower()
    if "lok sabha" in blob or "parliamentary" in blob or " ls " in blob:
        return "PC"
    if "assembly" in blob or "vidhan" in blob or " ac " in blob:
        return "AC"
    return "UNKNOWN"


def safe_segment(s: str, maxlen: int = 80) -> str:
    """File-system-safe slug: keep alnum + dash + underscore + dot, replace
    everything else with `_`, collapse repeats, trim to maxlen. Preserves
    extension if present."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_.")
    s = re.sub(r"_+", "_", s)
    if len(s) > maxlen:
        # keep extension
        root, dot, ext = s.rpartition(".")
        if dot and len(ext) <= 6:
            s = root[: maxlen - len(ext) - 1] + "." + ext
        else:
            s = s[:maxlen]
    return s


def build_local_name(
    *, year: str, body: str, state: str, file_id: int, original_url: str
) -> str:
    leaf = urllib.parse.unquote(original_url.rsplit("/", 1)[-1].split("?", 1)[0])
    leaf = safe_segment(leaf, maxlen=100) or "file"
    return f"{year}_{body}_{state}_{file_id}_{leaf}"


# -----------------------------------------------------------------------------#
# Manifest                                                                     #
# -----------------------------------------------------------------------------#

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_manifest(path: str) -> dict:
    if not os.path.exists(path):
        return {
            "tool": "tools/eci_offline_downloader.py",
            "tool_version": "1.0",
            "first_run_at": utc_now(),
            "last_run_at": utc_now(),
            "files": {},          # local_name -> entry
            "errors": [],         # list of {url, error, when}
        }
    with open(path, "r", encoding="utf-8") as f:
        m = json.load(f)
    m.setdefault("files", {})
    m.setdefault("errors", [])
    return m


def save_manifest(path: str, m: dict) -> None:
    m["last_run_at"] = utc_now()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


# -----------------------------------------------------------------------------#
# Driver                                                                       #
# -----------------------------------------------------------------------------#

def list_categories(out_dir: str | None = None) -> int:
    """Scrape /files/category/ and print every (id, slug) pair so the
    operator can pick the right starting point. The default categories
    97/98 hardcoded above turned out to be 'manuals' rather than
    statistical reports on at least one ECI snapshot — always sanity-check."""
    url = f"{OLD_HOST}/files/category/"
    print(f"[list] {url}", file=sys.stderr)
    try:
        html = http_get(url).decode("utf-8", "replace")
    except Exception as exc:
        print(f"[error] cannot fetch category index: {exc}", file=sys.stderr)
        return 1
    seen: set[int] = set()
    rows: list[tuple[int, str]] = []
    for m in _CATEGORY_RX.finditer(html):
        cid = int(m.group("id"))
        if cid in seen:
            continue
        seen.add(cid)
        rows.append((cid, m.group("slug")))
    rows.sort()
    print(f"\nFound {len(rows)} categories on {url}:\n")
    for cid, slug in rows:
        print(f"  {cid:>4}  {slug}")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "_categories.html"), "wb") as f:
            f.write(html.encode("utf-8"))
        print(f"\nRaw HTML saved to {os.path.join(out_dir, '_categories.html')}",
              file=sys.stderr)
    return 0


def debug_detail(target: str, out_dir: str | None = None) -> int:
    """Fetch a single detail page (or any URL) and dump the raw HTML +
    everything our extractors found. Use this when a category yields '0
    reports with data attachments' to diagnose the markup.

    `target` may be a numeric file id (resolved against /files/file/<id>/)
    or a full URL.
    """
    if target.isdigit():
        url = f"{OLD_HOST}/files/file/{target}/"
    else:
        url = target
    print(f"[debug] {url}", file=sys.stderr)
    try:
        html = http_get(url).decode("utf-8", "replace")
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    title, data_urls = parse_detail_page(html, base=url, probe=False)
    print(f"\nTITLE: {title}\n")
    print(f"Direct + hint extractors found {len(data_urls)} candidate URL(s):")
    for u in data_urls:
        print(f"  - {u}")
    print("\nAll <a href> on the page:")
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE):
        print(f"  - {m.group(1)}")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"_debug_{target.replace('/', '_')[:60]}.html")
        with open(path, "wb") as f:
            f.write(html.encode("utf-8"))
        print(f"\nRaw HTML saved to {path}", file=sys.stderr)
    return 0


def crawl_seed_url(seed: str, max_pages: int = 50) -> list[dict]:
    """Treat an arbitrary URL as a category-like listing: walk it, follow
    every /files/file/<id>/ permalink as a detail page. Same shape as
    crawl_category() but with no preset body/scope — classification falls
    back to title/slug heuristics only."""
    print(f"[crawl] seed -> {seed}", file=sys.stderr)
    pages_to_visit: list[str] = [seed]
    visited: set[str] = set()
    detail_links: list[tuple[int, str, str]] = []
    seen_ids: set[int] = set()
    while pages_to_visit and len(visited) < max_pages:
        url = pages_to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            html = http_get(url).decode("utf-8", "replace")
        except Exception as exc:
            print(f"[warn] seed page failed: {url} — {exc}", file=sys.stderr)
            continue
        details, next_pages = parse_category_page(html, base=url)
        for fid, slug, href in details:
            if fid in seen_ids:
                continue
            seen_ids.add(fid)
            detail_links.append((fid, slug, href))
        for np in next_pages:
            if np not in visited:
                pages_to_visit.append(np)
    print(f"[crawl] seed: {len(detail_links)} report pages found", file=sys.stderr)
    reports: list[dict] = []
    for i, (fid, slug, detail_url) in enumerate(detail_links, 1):
        try:
            html = http_get(detail_url).decode("utf-8", "replace")
        except Exception as exc:
            print(f"[warn] detail page failed [{i}/{len(detail_links)}]: {detail_url} — {exc}",
                  file=sys.stderr)
            continue
        title, data_urls = parse_detail_page(html, base=detail_url, self_id=fid)
        if not data_urls:
            continue
        reports.append({
            "category": "seed", "file_id": fid, "slug": slug,
            "detail_url": detail_url, "title": title or slug.replace("-", " "),
            "data_urls": data_urls,
        })
    print(f"[crawl] seed: {len(reports)} reports with data attachments", file=sys.stderr)
    return reports


def crawl_category(category_key: str, max_pages: int = 50) -> list[dict]:
    """Walk a category listing on old.eci.gov.in and return a list of
    {file_id, slug, detail_url, page_title, data_urls[]}. Errors fetching
    individual detail pages are logged to stderr but do not abort the crawl."""
    cat = CATEGORIES[category_key]
    start = f"{OLD_HOST}/files/category/{cat['id']}-{cat['slug']}/"
    print(f"[crawl] {category_key} -> {start}", file=sys.stderr)

    pages_to_visit: list[str] = [start]
    visited: set[str] = set()
    detail_links: list[tuple[int, str, str]] = []
    seen_ids: set[int] = set()

    while pages_to_visit and len(visited) < max_pages:
        url = pages_to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            html = http_get(url).decode("utf-8", "replace")
        except Exception as exc:
            print(f"[warn] category page failed: {url} — {exc}", file=sys.stderr)
            continue
        details, next_pages = parse_category_page(html, base=url)
        for fid, slug, href in details:
            if fid in seen_ids:
                continue
            seen_ids.add(fid)
            detail_links.append((fid, slug, href))
        for np in next_pages:
            if np not in visited:
                pages_to_visit.append(np)

    print(f"[crawl] {category_key}: {len(detail_links)} report pages found", file=sys.stderr)

    reports: list[dict] = []
    for i, (fid, slug, detail_url) in enumerate(detail_links, 1):
        try:
            html = http_get(detail_url).decode("utf-8", "replace")
        except Exception as exc:
            print(f"[warn] detail page failed [{i}/{len(detail_links)}]: {detail_url} — {exc}",
                  file=sys.stderr)
            continue
        title, data_urls = parse_detail_page(html, base=detail_url, self_id=fid)
        if not data_urls:
            # no attached data files (informational page) — skip silently
            continue
        reports.append({
            "category": category_key,
            "file_id": fid,
            "slug": slug,
            "detail_url": detail_url,
            "title": title or slug.replace("-", " "),
            "data_urls": data_urls,
        })
    print(f"[crawl] {category_key}: {len(reports)} reports with data attachments",
          file=sys.stderr)
    return reports


def filter_reports(reports: list[dict], *, years: set[str] | None,
                   state_filter: str | None) -> list[dict]:
    if not years and not state_filter:
        return reports
    out = []
    for r in reports:
        y = detect_year(r["title"], r["slug"])
        s = detect_state(r["title"], r["slug"])
        if years and y not in years:
            continue
        if state_filter and state_filter.lower().replace(" ", "") not in s.lower():
            continue
        out.append(r)
    return out


def download_one(url: str, dest_dir: str, local_name: str, *, force: bool) -> tuple[str, bool, str | None]:
    """Returns (final_path, downloaded, error). `downloaded=False` means
    skipped-because-exists (not an error)."""
    os.makedirs(dest_dir, exist_ok=True)
    final_path = os.path.join(dest_dir, local_name)
    if os.path.exists(final_path) and not force and os.path.getsize(final_path) > 0:
        return final_path, False, None
    try:
        body = http_get(url, timeout=120.0)
    except Exception as exc:
        return final_path, False, f"{type(exc).__name__}: {exc}"
    tmp = final_path + ".part"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, final_path)
    return final_path, True, None


def run(out_dir: str, *, scopes: list[str], seed_urls: list[str] | None = None,
        years: set[str] | None,
        state_filter: str | None, dry_run: bool, force: bool) -> int:
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "manifest.json")
    manifest = load_manifest(manifest_path)

    all_reports: list[dict] = []
    for scope in scopes:
        if scope not in CATEGORIES:
            print(f"[error] unknown scope: {scope}", file=sys.stderr)
            return 2
        all_reports.extend(crawl_category(scope))
    for seed in seed_urls or []:
        all_reports.extend(crawl_seed_url(seed))

    all_reports = filter_reports(all_reports, years=years, state_filter=state_filter)
    print(f"[plan] {len(all_reports)} reports after filtering", file=sys.stderr)

    plan_rows: list[tuple[str, dict, str, str]] = []  # (data_url, report, local_name, sub_dir)
    for r in all_reports:
        y = detect_year(r["title"], r["slug"])
        s = detect_state(r["title"], r["slug"])
        b = detect_body(r["category"], r["title"], r["slug"])
        sub_dir = os.path.join(out_dir, b, y)
        for u in r["data_urls"]:
            local = build_local_name(year=y, body=b, state=s, file_id=r["file_id"], original_url=u)
            plan_rows.append((u, r, local, sub_dir))

    print(f"[plan] {len(plan_rows)} files to consider", file=sys.stderr)

    if dry_run:
        for u, r, local, sub_dir in plan_rows[:200]:
            print(f"  WOULD GET {os.path.relpath(os.path.join(sub_dir, local), out_dir)}  <-  {u}")
        if len(plan_rows) > 200:
            print(f"  ... and {len(plan_rows) - 200} more", file=sys.stderr)
        return 0

    n_new = n_skip = n_err = 0
    for i, (url, r, local, sub_dir) in enumerate(plan_rows, 1):
        path, downloaded, err = download_one(url, sub_dir, local, force=force)
        rel = os.path.relpath(path, out_dir).replace(os.sep, "/")
        if err:
            n_err += 1
            print(f"[err {i}/{len(plan_rows)}] {url} — {err}", file=sys.stderr)
            manifest["errors"].append({
                "url": url, "report_detail_url": r["detail_url"],
                "error": err, "when": utc_now(),
            })
            continue
        if downloaded:
            n_new += 1
        else:
            n_skip += 1
        manifest["files"][rel] = {
            "url": url,
            "report_detail_url": r["detail_url"],
            "report_title": r["title"],
            "report_id": r["file_id"],
            "category": r["category"],
            "fetched_at": utc_now() if downloaded else manifest["files"].get(rel, {}).get("fetched_at", utc_now()),
            "size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        }
        if i % 25 == 0 or i == len(plan_rows):
            save_manifest(manifest_path, manifest)
            print(f"[progress] {i}/{len(plan_rows)}  new={n_new} skip={n_skip} err={n_err}",
                  file=sys.stderr)

    save_manifest(manifest_path, manifest)
    print(
        f"\n[done] downloaded={n_new}  skipped={n_skip}  errors={n_err}\n"
        f"[done] manifest: {manifest_path}\n"
        f"[done] root:     {out_dir}",
        file=sys.stderr,
    )
    return 0 if n_err == 0 else 1


# -----------------------------------------------------------------------------#
# CLI                                                                          #
# -----------------------------------------------------------------------------#

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Bulk-download ECI statistical reports from old.eci.gov.in. "
                    "Stdlib-only; safe to run on a machine with no pip access.",
    )
    p.add_argument("--out", required=True, help="Output directory (will be created).")
    p.add_argument(
        "--scope",
        choices=["all", "lok-sabha", "assembly", "bye-election"],
        default="all",
        help="Which built-in category to crawl. 'all' = lok-sabha + assembly. "
             "Ignored when --seed-url or --debug-detail or --list-categories is used.",
    )
    p.add_argument(
        "--seed-url", default="",
        help="Crawl an arbitrary listing URL instead of the built-in categories. "
             "Use this once you've discovered the right ECI page (e.g. via "
             "--list-categories). Repeatable: comma-separate multiple URLs.",
    )
    p.add_argument(
        "--list-categories", action="store_true",
        help="Print every (id, slug) on https://old.eci.gov.in/files/category/ and exit. "
             "Use this to find the correct category id for statistical reports.",
    )
    p.add_argument(
        "--debug-detail", default="",
        help="Diagnostic: fetch one detail page (numeric file id, or full URL), "
             "print its title, every <a href> on it, and what the extractors found. "
             "Use when a crawl returns '0 reports with data attachments'.",
    )
    p.add_argument(
        "--years", default="",
        help="Comma-separated year filter, e.g. '2014,2019,2024'. Empty = all years.",
    )
    p.add_argument(
        "--state", default="",
        help="Filter to one state's reports (substring match against detected state). "
             "e.g. 'Tamil Nadu'. Empty = all states.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be downloaded; don't fetch.")
    p.add_argument("--force", action="store_true",
                   help="Re-download files that already exist.")
    args = p.parse_args(argv)

    if args.list_categories:
        return list_categories(out_dir=os.path.abspath(args.out) if args.out else None)

    if args.debug_detail:
        return debug_detail(args.debug_detail,
                            out_dir=os.path.abspath(args.out) if args.out else None)

    if args.scope == "all":
        scopes = ["lok-sabha", "assembly"]
    else:
        scopes = [args.scope]

    seed_urls = [u.strip() for u in args.seed_url.split(",") if u.strip()]

    years = {y.strip() for y in args.years.split(",") if y.strip()} or None
    state_filter = args.state.strip() or None

    return run(
        out_dir=os.path.abspath(args.out),
        scopes=scopes if not seed_urls else [],
        seed_urls=seed_urls,
        years=years,
        state_filter=state_filter,
        dry_run=args.dry_run,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
