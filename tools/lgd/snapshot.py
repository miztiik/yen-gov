"""tools/lgd/snapshot.py — fetch latest LGD States + Districts CSVs.

Reads from ramSeraph's `opendata` mirror of LGD (Local Government Directory).
The release tag `lgd-latest-extra1` is updated rolling every ~3 months; assets
are named `<component>.<DDMmmYYYY>.csv.7z`. We don't know the exact date, so
we walk backward from today until both `states` and `districts` are found.

Outputs:
  datasets/reference/in/lgd/states-latest.csv
  datasets/reference/in/lgd/states-latest.csv.sources.json
  datasets/reference/in/lgd/districts-latest.csv
  datasets/reference/in/lgd/districts-latest.csv.sources.json

Per CLAUDE.md §4 (tools self-contained) — stdlib + py7zr only. UTF-8 stdout
wrap so non-ASCII state names can be printed on PowerShell (cp1252).
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import py7zr  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
RAW_ROOT = REPO / ".runtime" / "raw" / "lgd"
OUT_ROOT = REPO / "datasets" / "reference" / "in" / "lgd"

RELEASE_TAG = "lgd-latest-extra1"
COMPONENTS = ("States", "Districts")  # canonical filenames on the release
USER_AGENT = "yen-gov/0.1 (+https://github.com/yen-gov/yen-gov)"
LOOKBACK_DAYS = 120  # release cadence is ~90 days; 120 gives margin
WALK_LIMIT = 200  # safety bound, never sweeps more than this many dates


def _date_token(d: datetime) -> str:
    return d.strftime("%d%b%Y")  # e.g. 11May2026


def _asset_url(component: str, token: str) -> str:
    return (
        "https://github.com/ramSeraph/opendata/releases/download/"
        f"{RELEASE_TAG}/{component}.{token}.csv.7z"
    )


def _http_head(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError:
        return -1


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, dest.open("wb") as fh:
        shutil.copyfileobj(resp, fh)


def _extract_csv(archive: Path, raw_dir: Path) -> Path:
    extract_dir = raw_dir / archive.stem.replace(".csv", "_extracted")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive, mode="r") as zf:
        zf.extractall(path=extract_dir)
    csvs = sorted(extract_dir.rglob("*.csv"))
    if len(csvs) != 1:
        raise ValueError(f"{archive.name}: expected 1 csv inside, found {len(csvs)}")
    return csvs[0]


def _resolve_token() -> str:
    """Find the most recent date token where BOTH States and Districts exist."""
    today = datetime.now(timezone.utc).date()
    for offset in range(WALK_LIMIT):
        d = today - timedelta(days=offset)
        token = _date_token(datetime(d.year, d.month, d.day))
        statuses = [_http_head(_asset_url(c, token)) for c in COMPONENTS]
        print(f"  probe {token}: {dict(zip(COMPONENTS, statuses))}")
        if all(s == 200 for s in statuses):
            return token
        if offset >= LOOKBACK_DAYS:
            break
    raise SystemExit(
        f"No LGD release found within {LOOKBACK_DAYS} days walking back from {today}. "
        "Check https://github.com/ramSeraph/opendata/releases/tag/lgd-latest-extra1"
    )


def _write_sidecar(out_csv: Path, url: str, fetched_at: str) -> None:
    sidecar = out_csv.with_suffix(out_csv.suffix + ".sources.json")
    payload = {
        "$schema": "https://yen-gov.github.io/schemas/csv.sources.schema.json",
        "$schema_version": "1.0",
        "$comment": (
            "CLAUDE.md §12 provenance sidecar for the sibling CSV. CSV has no "
            "native top-level metadata slot; this file carries the required "
            "`sources` array on its behalf."
        ),
        "for": out_csv.name,
        "sources": [
            {
                "url": url,
                "fetched_at": fetched_at,
                "name": "Local Government Directory (LGD) — opendata mirror",
                "authority": "Ministry of Panchayati Raj, Government of India (mirror by ramSeraph)",
            }
        ],
    }
    sidecar.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    print(f"Resolving most recent {RELEASE_TAG} release token...")
    token = _resolve_token()
    print(f"  -> using token {token}\n")

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    for component in COMPONENTS:
        url = _asset_url(component, token)
        archive = RAW_ROOT / f"{component}.{token}.csv.7z"
        print(f"{component}: {url}")
        _download(url, archive)
        print(f"  downloaded {archive.stat().st_size:,} bytes")
        csv_inside = _extract_csv(archive, RAW_ROOT)
        out_csv = OUT_ROOT / f"{component.lower()}-latest.csv"
        shutil.copy2(csv_inside, out_csv)
        _write_sidecar(out_csv, url, fetched_at)
        print(f"  wrote {out_csv.relative_to(REPO).as_posix()} ({out_csv.stat().st_size:,} bytes)")

    print("\nDone.")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
