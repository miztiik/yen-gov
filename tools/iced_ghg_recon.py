"""Recon GHG drill-down endpoints.

Probes:
  /climate-environment/ghg-emissions/energy            (full GHG, AES)
  /climate-environment/ghg-emissions/ghg-static-values (reference values)
  /climate-environment/ghg-emissions/economy-wide-emission (already used,
       confirm shape / re-cache)

Run from repo root:  python tools/iced_ghg_recon.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common.client import IcedClient  # noqa: E402

ENDPOINTS = [
    ("ghg_economy_wide", "/climate-environment/ghg-emissions/economy-wide-emission"),
    ("ghg_energy_full", "/climate-environment/ghg-emissions/energy"),
    ("ghg_static_values", "/climate-environment/ghg-emissions/ghg-static-values"),
]


def _shape(node, depth=0, max_depth=4):
    pad = "  " * depth
    if isinstance(node, dict):
        out = [f"{pad}dict({len(node)} keys):"]
        for k, v in list(node.items())[:8]:
            kind = type(v).__name__
            if isinstance(v, (list, dict)):
                out.append(f"{pad}  {k!r}: {kind} [{len(v)}]")
                if depth < max_depth:
                    out.append(_shape(v, depth + 2, max_depth))
            else:
                preview = repr(v)[:40]
                out.append(f"{pad}  {k!r}: {kind} {preview}")
        return "\n".join(out)
    if isinstance(node, list) and node:
        out = [f"{pad}list[{len(node)}] of"]
        if depth < max_depth:
            out.append(_shape(node[0], depth + 1, max_depth))
        return "\n".join(out)
    return f"{pad}{type(node).__name__}: {repr(node)[:60]}"


def main() -> None:
    c = IcedClient(host="https://icedapi.niti.gov.in", polite_delay=0.5)
    for name, path in ENDPOINTS:
        print("=" * 78)
        print(f"### {name}    GET {path}")
        try:
            r = c.get(path)
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            continue
        print(f"  url      = {r.url}")
        print(f"  raw_path = {Path(r.raw_path).relative_to(REPO_ROOT).as_posix()}")
        print(f"  top-level type = {type(r.decrypted).__name__}")
        print(_shape(r.decrypted, depth=1))
        if isinstance(r.decrypted, dict):
            for k in ("data", "stateWiseData", "category", "seriesData"):
                v = r.decrypted.get(k)
                if isinstance(v, list) and v:
                    print(f"  sample[{k}][0]: {json.dumps(v[0])[:400]}")


if __name__ == "__main__":
    main()
