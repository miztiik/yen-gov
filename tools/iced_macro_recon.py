"""Recon remaining unused ICED economy/demography endpoints."""
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
    ("gdp_trend",            "/economy-demography/key-economic-indicators/gdp-trend"),
    ("gva_trend",            "/economy-demography/key-economic-indicators/gva-trend"),
    ("industrial_production","/economy-demography/key-economic-indicators/industrial-production"),
    ("balance_trendline",    "/economy-demography/key-economic-indicators/balance-trendline"),
    ("per_capita_income_map","/economy-demography/key-economic-indicators/per-capita-income-map"),
    ("demography_actual",    "/economy-demography/demography/demographyActual"),
    ("ghg_static_values",    "/climate-environment/ghg-emissions/ghg-static-values"),
]


def shape(node, depth=0, max_depth=3):
    pad = "  " * depth
    if isinstance(node, dict):
        out = [f"{pad}dict({len(node)} keys):"]
        for k, v in list(node.items())[:8]:
            kind = type(v).__name__
            if isinstance(v, (list, dict)):
                out.append(f"{pad}  {k!r}: {kind} [{len(v)}]")
                if depth < max_depth:
                    out.append(shape(v, depth + 2, max_depth))
            else:
                preview = repr(v)[:50]
                out.append(f"{pad}  {k!r}: {kind} {preview}")
        return "\n".join(out)
    if isinstance(node, list) and node:
        out = [f"{pad}list[{len(node)}] of"]
        if depth < max_depth:
            out.append(shape(node[0], depth + 1, max_depth))
        return "\n".join(out)
    return f"{pad}{type(node).__name__}: {repr(node)[:80]}"


def main() -> None:
    c = IcedClient(host="https://icedapi.niti.gov.in", polite_delay=0.5)
    cv1 = IcedClient(host="https://icedapi.niti.gov.in/v1", polite_delay=0.5)
    for name, path in ENDPOINTS:
        print("=" * 78)
        print(f"### {name}    GET {path}")
        ok = False
        for tag, client in (("v0", c), ("v1", cv1)):
            try:
                r = client.get(path)
                ok = True
                print(f"  HOST {tag}: ok    url = {r.url}")
                print(shape(r.decrypted, depth=1))
                if isinstance(r.decrypted, dict):
                    for k in ("data", "stateWiseData"):
                        v = r.decrypted.get(k)
                        if isinstance(v, list) and v:
                            print(f"  sample[{k}][0]: {json.dumps(v[0])[:300]}")
                            if len(v) > 1:
                                print(f"  sample[{k}][1]: {json.dumps(v[1])[:300]}")
                break
            except Exception as exc:
                msg = str(exc)
                if len(msg) > 120:
                    msg = msg[:120]
                print(f"  HOST {tag}: failed  {type(exc).__name__}: {msg}")
        if not ok:
            print("  ALL HOSTS FAILED")


if __name__ == "__main__":
    main()
