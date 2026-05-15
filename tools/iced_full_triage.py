"""Triage every parameter-free ICED endpoint from the 259-path appendix.

Reads the appendix from `docs/architecture/backend/sources-iced-api.md`,
filters out path-templated and query-templated endpoints (those with
`${...}` placeholders), then GETs each remaining path against both v0
and v1 hosts, decrypting where applicable. Writes a triage CSV +
markdown table that scores each by:

- shape (dict / list / scalar)
- top-level keys
- row count (when payload is dict-with-`data` or list)
- size in KB
- detected time / facet keys (year, fy, state, source, etc.)
- already_bound: whether the path is in iced_common.endpoints catalogue

Output: `.runtime/iced_recon/full_triage_<UTC>.csv` + `.md`
"""
from __future__ import annotations

import csv
import io
import json
import re
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

socket.setdefaulttimeout(15)

_EXEC = ThreadPoolExecutor(max_workers=32)


def _call_with_hard_timeout(fn, *args, hard_timeout: float = 18.0, **kwargs):
    """Run fn in a worker thread; raise TimeoutError if it overruns.
    Note: a hung socket call can't be cancelled — we leak the thread but
    the main loop continues."""
    fut = _EXEC.submit(fn, *args, **kwargs)
    try:
        return fut.result(timeout=hard_timeout)
    except FutTimeout as exc:
        raise TimeoutError(f"hard timeout after {hard_timeout}s") from exc

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common import IcedClient, ICEDFetchError  # noqa: E402
from yen_gov.sources.iced_common.endpoints import ENDPOINT_CATALOGUE  # noqa: E402

ADR_PATH = REPO_ROOT / "docs" / "architecture" / "backend" / "sources-iced-api.md"
OUT_DIR = REPO_ROOT / ".runtime" / "iced_recon"


def _load_appendix_paths() -> list[str]:
    text = ADR_PATH.read_text(encoding="utf-8")
    m = re.search(r"## Appendix: full 259-endpoint list[\s\S]+?```\n([\s\S]+?)```", text)
    if not m:
        raise RuntimeError("appendix not found")
    return [line.strip() for line in m.group(1).splitlines() if line.strip().startswith("/")]


def _is_param_free(path: str) -> bool:
    return "${" not in path


def _sniff_keys(rows: list[dict]) -> tuple[set[str], set[str]]:
    time_keys = {"year", "fy", "fyear", "month", "date", "yearMonth", "time"}
    facet_keys = {"state", "source", "category", "sector", "subsector",
                  "industry", "industryItem", "type", "fuel", "item", "group",
                  "discom", "plant", "region", "city", "district"}
    seen_time, seen_facet = set(), set()
    for r in rows[:50]:
        if not isinstance(r, dict):
            continue
        for k in r:
            kl = str(k)
            if kl in time_keys or kl.lower() in time_keys:
                seen_time.add(kl)
            if kl in facet_keys or kl.lower() in facet_keys:
                seen_facet.add(kl)
    return seen_time, seen_facet


def _summarise(decrypted: Any) -> dict[str, Any]:
    info: dict[str, Any] = {
        "shape": type(decrypted).__name__, "top_keys": "", "rows": "",
        "time_keys": "", "facet_keys": "",
    }
    rows: list = []
    if isinstance(decrypted, dict):
        info["top_keys"] = "|".join(sorted(decrypted)[:10])
        for cand in ("data", "stateWiseData", "rows", "result"):
            v = decrypted.get(cand)
            if isinstance(v, list):
                rows = v
                info["rows"] = f"{cand}:{len(v)}"
                break
        if not rows and isinstance(decrypted.get("data"), dict):
            d = decrypted["data"]
            info["rows"] = f"data:dict({len(d)})"
    elif isinstance(decrypted, list):
        rows = decrypted
        info["rows"] = f"list:{len(rows)}"
    if rows and isinstance(rows[0], dict):
        tk, fk = _sniff_keys(rows)
        info["time_keys"] = "|".join(sorted(tk))
        info["facet_keys"] = "|".join(sorted(fk))
    return info


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    progress_path = OUT_DIR / "_triage_progress.log"
    rolling_csv = OUT_DIR / "_triage_rolling.csv"
    progress = progress_path.open("w", encoding="utf-8", buffering=1)

    def say(msg: str) -> None:
        print(msg)
        progress.write(msg + "\n")

    paths = _load_appendix_paths()
    free_paths = [p for p in paths if _is_param_free(p)]
    bound = {ep.path for ep in ENDPOINT_CATALOGUE}
    say(f"appendix paths: {len(paths)}   parameter-free: {len(free_paths)}   already in catalogue: {sum(1 for p in free_paths if p in bound)}")

    # Resume support: if a rolling CSV exists, load already-probed paths.
    already_done: dict[str, dict[str, Any]] = {}
    if rolling_csv.exists():
        with rolling_csv.open("r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                r["already_bound"] = r["already_bound"] in ("True", "true", "1")
                already_done[r["path"]] = r
        say(f"resume: {len(already_done)} paths already in {rolling_csv.name}")

    cv0 = IcedClient(host="https://icedapi.niti.gov.in", polite_delay=0.1, retries=1)
    cv1 = IcedClient(host="https://icedapi.niti.gov.in/v1", polite_delay=0.1, retries=1)

    rows_out: list[dict[str, Any]] = []
    fieldnames = ["path", "host", "status", "size_kb", "shape", "top_keys",
                  "rows", "time_keys", "facet_keys", "already_bound", "error"]
    # Open rolling CSV for append, write header if new.
    new_csv = not rolling_csv.exists()
    rolling_fp = rolling_csv.open("a", encoding="utf-8", newline="")
    rolling_writer = csv.DictWriter(rolling_fp, fieldnames=fieldnames)
    if new_csv:
        rolling_writer.writeheader()
        rolling_fp.flush()

    for i, path in enumerate(sorted(free_paths), 1):
        if path in already_done:
            rows_out.append(already_done[path])
            continue
        result: dict[str, Any] = {
            "path": path, "host": "", "status": "", "size_kb": "",
            "shape": "", "top_keys": "", "rows": "",
            "time_keys": "", "facet_keys": "", "already_bound": path in bound,
            "error": "",
        }
        for tag, client in (("v0", cv0), ("v1", cv1)):
            try:
                r = _call_with_hard_timeout(client.get, path, timeout=10, hard_timeout=18)
            except ICEDFetchError as exc:
                result["error"] = f"{tag}:{type(exc).__name__}:{str(exc)[:80]}"
                continue
            except TimeoutError as exc:
                result["error"] = f"{tag}:HardTimeout:{str(exc)[:80]}"
                continue
            except Exception as exc:
                # Plain JSON endpoints will throw on decrypt; retry decrypt=False.
                try:
                    r = _call_with_hard_timeout(client.get, path, decrypt=False, timeout=10, hard_timeout=18)
                except Exception as exc2:
                    result["error"] = f"{tag}:{type(exc2).__name__}:{str(exc2)[:80]}"
                    continue
            result["host"] = tag
            result["status"] = "ok"
            try:
                payload_size = len(json.dumps(r.decrypted))
            except (TypeError, AttributeError):
                payload_size = 0
            result["size_kb"] = f"{payload_size/1024:.1f}"
            result.update(_summarise(r.decrypted))
            result["error"] = ""
            break
        if not result["status"]:
            result["status"] = "FAIL"
        rows_out.append(result)
        rolling_writer.writerow(result)
        rolling_fp.flush()
        flag = "*" if result["already_bound"] else " "
        say(f"[{i:3d}/{len(free_paths)}] {flag} {result['status']:4s} {result['host']:2s}  {result['rows']:25s} {path}")
    rolling_fp.close()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    csv_path = OUT_DIR / f"full_triage_{ts}.csv"
    md_path = OUT_DIR / f"full_triage_{ts}.md"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# ICED full-endpoint triage — {ts} UTC\n\n")
        f.write(f"Probed {len(rows_out)} parameter-free paths (of {len(paths)} total).\n\n")
        ok = [r for r in rows_out if r["status"] == "ok" and not r["already_bound"]]
        bound_ok = [r for r in rows_out if r["status"] == "ok" and r["already_bound"]]
        fail = [r for r in rows_out if r["status"] == "FAIL"]
        f.write(f"- ok new (unbound):   **{len(ok)}**\n")
        f.write(f"- ok already-bound:   {len(bound_ok)}\n")
        f.write(f"- fail / unreachable: {len(fail)}\n\n")
        f.write("## Unbound endpoints that responded OK\n\n")
        f.write("| path | host | rows | time keys | facet keys | size kB |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in sorted(ok, key=lambda r: r["path"]):
            f.write(f"| `{r['path']}` | {r['host']} | {r['rows']} | {r['time_keys']} | {r['facet_keys']} | {r['size_kb']} |\n")
        f.write("\n## Failed / unreachable\n\n")
        for r in fail:
            f.write(f"- `{r['path']}` — {r['error']}\n")
    print(f"\nwrote {csv_path}\nwrote {md_path}")
    progress.write(f"DONE wrote {csv_path}\n")
    progress.close()
    _EXEC.shutdown(wait=False, cancel_futures=True)
    import os as _os
    _os._exit(0)


if __name__ == "__main__":
    main()
