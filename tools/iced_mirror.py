"""Bulk-mirror ICED API endpoints into ``.runtime/raw/iced/`` for triage.

Usage
-----
    python tools/iced_mirror.py [--name <endpoint-name> ...] [--all-free]

Default behaviour with no flags: mirror every parameter-free endpoint in
:data:`yen_gov.sources.iced_common.endpoints.ENDPOINT_CATALOGUE`. With
``--name <id>`` (repeatable), only mirror the named endpoints. With
``--all-free``, mirror every parameter-free endpoint regardless of
catalogue curation.

Writes
------
* ``.runtime/raw/iced/<path>.b64`` — verbatim encrypted HTTP body (so
  parsers can be developed offline).
* ``.runtime/iced_recon/triage_<UTC>.csv`` — one row per endpoint with
  shape, top-level keys, approximate dimensions, time range. This is the
  triage table Hans uses to prioritise indicators.

This script is a **tool**, not part of the production pipeline (per
CLAUDE.md §3 ``tools/`` rules). It imports from
``backend/yen_gov/sources/iced_common`` for the client + crypto so that
production and tooling speak the same protocol; it does not reach into
backend/ runtime modules beyond that.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow ``python tools/iced_mirror.py`` from repo root to import yen_gov.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.sources.iced_common import IcedClient, ICEDFetchError, ICEDShapeError  # noqa: E402
from yen_gov.sources.iced_common.endpoints import (  # noqa: E402
    ENDPOINT_CATALOGUE,
    Endpoint,
    parameter_free,
)


def _setup_utf8() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper) and sys.stdout.encoding.lower() == "utf-8":
        return
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _summarize(decrypted: Any) -> dict[str, Any]:
    """Return a compact dict describing the response shape.

    Heuristic — ``status``, top-level keys, list lengths, year ranges
    detected anywhere in the structure. The CSV consumer treats this as
    advisory: real shape lives in the .b64 cache.
    """
    summary: dict[str, Any] = {
        "type": type(decrypted).__name__,
        "top_keys": "",
        "data_type": "",
        "data_count": "",
        "data_keys": "",
        "year_min": "",
        "year_max": "",
        "rough_size_kb": "",
    }

    if isinstance(decrypted, dict):
        top = sorted(decrypted.keys())
        summary["top_keys"] = "|".join(top[:12])
        data = decrypted.get("data")
        if isinstance(data, list):
            summary["data_type"] = "list"
            summary["data_count"] = str(len(data))
            if data and isinstance(data[0], dict):
                summary["data_keys"] = "|".join(sorted(data[0].keys())[:12])
        elif isinstance(data, dict):
            summary["data_type"] = "dict"
            summary["data_count"] = str(len(data))
            summary["data_keys"] = "|".join(sorted(data.keys())[:12])
    elif isinstance(decrypted, list):
        summary["data_type"] = "list"
        summary["data_count"] = str(len(decrypted))
        if decrypted and isinstance(decrypted[0], dict):
            summary["data_keys"] = "|".join(sorted(decrypted[0].keys())[:12])

    years = _find_years(decrypted)
    if years:
        summary["year_min"] = str(min(years))
        summary["year_max"] = str(max(years))

    summary["rough_size_kb"] = str(round(len(json.dumps(decrypted, default=str)) / 1024, 1))
    return summary


def _find_years(node: Any, found: set[int] | None = None, depth: int = 0) -> set[int]:
    """Walk JSON looking for plausible year integers (1900..2050)."""
    if found is None:
        found = set()
    if depth > 8 or len(found) > 4096:
        return found
    if isinstance(node, dict):
        for k, v in node.items():
            kl = str(k).lower()
            if kl in {"year", "fy", "yr", "fiscalyear", "fiscal_year"} and isinstance(v, (int, str)):
                _add_year(found, v)
            _find_years(v, found, depth + 1)
    elif isinstance(node, list):
        for item in node[:200]:                 # cap per-list scan
            _find_years(item, found, depth + 1)
    return found


def _add_year(found: set[int], v: Any) -> None:
    try:
        if isinstance(v, int):
            iv = v
        else:
            s = str(v).strip().split("-")[0]
            iv = int(s)
        if 1900 <= iv <= 2050:
            found.add(iv)
    except (ValueError, TypeError):
        pass


def main() -> int:
    _setup_utf8()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", action="append", default=[], help="endpoint name from the catalogue (repeatable)")
    p.add_argument("--all-free", action="store_true", help="mirror every parameter-free endpoint")
    args = p.parse_args()

    if args.name:
        wanted = []
        for n in args.name:
            match = next((e for e in ENDPOINT_CATALOGUE if e.name == n), None)
            if match is None:
                print(f"  WARN  unknown endpoint name {n!r}; skipping")
                continue
            wanted.append(match)
        endpoints: tuple[Endpoint, ...] = tuple(wanted)
    elif args.all_free:
        endpoints = parameter_free()
    else:
        endpoints = parameter_free()

    if not endpoints:
        print("nothing to mirror; pass --name <id> or --all-free")
        return 1

    print(f"mirroring {len(endpoints)} endpoint(s)")

    client = IcedClient(runtime_root=REPO_ROOT, polite_delay=0.4)

    triage_rows: list[dict[str, Any]] = []
    ok, fail = 0, 0
    for ep in endpoints:
        url_print = f"{client._host}{ep.path}"  # noqa: SLF001 — read-only for log
        try:
            r = client.get(ep.path)
            summary = _summarize(r.decrypted)
            triage_rows.append({
                "name": ep.name,
                "path": ep.path,
                "status": "ok",
                "fetched_at": r.fetched_at.isoformat(),
                "raw_path": str(r.raw_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                **summary,
                "page_hint": ep.page_hint,
                "notes": ep.notes,
                "error": "",
            })
            ok += 1
            print(f"  OK    {ep.name:42s} {summary['rough_size_kb']:>7s} KB  data={summary['data_type']}/{summary['data_count']}")
        except (ICEDFetchError, ICEDShapeError, Exception) as exc:  # broad: triage script
            triage_rows.append({
                "name": ep.name,
                "path": ep.path,
                "status": "fail",
                "fetched_at": "",
                "raw_path": "",
                "type": "",
                "top_keys": "",
                "data_type": "",
                "data_count": "",
                "data_keys": "",
                "year_min": "",
                "year_max": "",
                "rough_size_kb": "",
                "page_hint": ep.page_hint,
                "notes": ep.notes,
                "error": f"{type(exc).__name__}: {exc}",
            })
            fail += 1
            print(f"  FAIL  {ep.name:42s} {type(exc).__name__}: {exc}")
            if "--debug" in sys.argv:
                traceback.print_exc()

    out_dir = REPO_ROOT / ".runtime" / "iced_recon"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    csv_path = out_dir / f"triage_{stamp}.csv"
    fieldnames = [
        "name", "path", "status", "fetched_at", "raw_path",
        "type", "top_keys", "data_type", "data_count", "data_keys",
        "year_min", "year_max", "rough_size_kb",
        "page_hint", "notes", "error",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in triage_rows:
            w.writerow(row)

    print()
    print(f"wrote triage: {csv_path.relative_to(REPO_ROOT).as_posix()}")
    print(f"summary: ok={ok} fail={fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
