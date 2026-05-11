"""One-shot RBI State Finances URL recon.

Fetches the listing page, extracts every (link_text, href) for .xlsx
attachments under the latest edition, and prints a JSON map suitable for
pasting into backend/yen_gov/sources/rbi_xlsx/urls.py.

Usage:
    python tools/rbi_recon.py
"""
from __future__ import annotations

import re
import sys

import httpx


LISTING = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
    "?head=State+Finances+%3A+A+Study+of+Budgets"
)


def main() -> int:
    r = httpx.get(
        LISTING,
        headers={"User-Agent": "Mozilla/5.0 yen-gov-recon"},
        timeout=30,
        follow_redirects=True,
    )
    print(f"status={r.status_code} bytes={len(r.text)}", file=sys.stderr)

    # The RBI page lays out each year-edition as a table whose rows contain
    # <a href=PublicationsView.aspx?id=N>TITLE</a> followed by an XLSX/PDF
    # download link. Filename hashes carry the publication date stamp
    # (e.g. ``23012026`` = Jan 23, 2026). We isolate the latest edition by
    # finding the most-frequent stamp among all .xlsx hrefs.
    xlsx_hits = re.findall(
        r"href=['\"]?([^'\"\s>]+\.(?:xlsx|XLSX))['\"]?", r.text
    )
    print(f"xlsx links total: {len(xlsx_hits)}", file=sys.stderr)
    if not xlsx_hits:
        print("ERROR: no xlsx links on page", file=sys.stderr)
        return 2

    stamp_re = re.compile(r"(\d{8})")
    from collections import Counter
    stamps = Counter()
    for u in xlsx_hits:
        m = stamp_re.search(u)
        if m:
            stamps[m.group(1)] += 1
    if not stamps:
        print("ERROR: no date stamps in xlsx URLs", file=sys.stderr)
        return 2
    latest_stamp, count = stamps.most_common(1)[0]
    print(f"latest stamp: {latest_stamp} ({count} xlsx files)", file=sys.stderr)

    # For each latest-stamp XLSX, walk back ~600 chars in the source to
    # find the nearest title link.
    title_re = re.compile(
        r"<a class=['\"]link2['\"][^>]*href=[^>]*PublicationsView\.aspx\?id=\d+[^>]*>(.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    pairs: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for u in xlsx_hits:
        if latest_stamp not in u:
            continue
        if u in seen_urls:
            continue
        seen_urls.add(u)
        idx = r.text.find(u)
        window = r.text[max(0, idx - 1200) : idx]
        title_matches = title_re.findall(window)
        title = ""
        if title_matches:
            raw = title_matches[-1]
            title = " ".join(re.sub(r"<[^>]+>", "", raw).split())
        pairs.append((title, u))

    print(f"\nLATEST EDITION (stamp {latest_stamp}):")
    print(f"XLSX attachments matched to titles: {len(pairs)}\n")
    for title, url in pairs:
        print(f"  {title!r}")
        print(f"    -> {url}")

    if "--dump" in sys.argv:
        out = ".runtime/rbi_titles.txt"
        with open(out, "w", encoding="utf-8") as fh:
            for title, url in pairs:
                fh.write(f"{title}\t{url}\n")
        print(f"\nwrote {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
