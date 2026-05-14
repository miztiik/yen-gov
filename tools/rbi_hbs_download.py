"""Download a list of RBI Handbook XLSX files with browser headers.

Usage::

    python tools/rbi_hbs_download.py <out_dir> <referer_url> <url1> <name1> <url2> <name2> ...

Names are the local filenames (without .XLSX suffix).
"""
from __future__ import annotations
import io, sys
from pathlib import Path

import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.ms-excel,application/octet-stream,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}


def fetch(url: str, referer: str, dst: Path) -> None:
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("Referer", referer)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if not data.startswith(b"PK\x03\x04"):
        sig = data[:8].hex()
        raise SystemExit(f"  ERROR: not a ZIP/XLSX (signature={sig}) for {url}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(f"  ok  {dst.name}  ({len(data):,} bytes)")


def main() -> None:
    out_dir = Path(sys.argv[1])
    referer = sys.argv[2]
    pairs = sys.argv[3:]
    if len(pairs) % 2 != 0:
        raise SystemExit("URLs and names must be paired")
    for i in range(0, len(pairs), 2):
        url = pairs[i]
        name = pairs[i + 1]
        dst = out_dir / f"{name}.xlsx"
        if dst.exists() and dst.stat().st_size > 1024 and dst.read_bytes()[:4] == b"PK\x03\x04":
            print(f"  skip {dst.name} (cached)")
            continue
        try:
            fetch(url, referer, dst)
        except Exception as e:
            print(f"  FAIL {url}: {e}")


if __name__ == "__main__":
    main()
