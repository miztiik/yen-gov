"""Recon ICED power-sector endpoints. Fetches each, dumps shape summary.

Run: ``python tools/iced_power_recon.py`` from repo root.

For each endpoint we print:

- HTTP URL
- top-level type (list / dict / etc.)
- if dict: keys + sample value-types
- if list: length + first-item shape
- a 2-3 row sample so we can design parsers without guessing.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

# Ensure our backend package is importable when run from repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common.client import IcedClient  # noqa: E402

# Path-only endpoints (no query params) we want to inspect.
ENDPOINTS: list[tuple[str, str]] = [
    # name, api_path
    ("power_generation", "/energy/generation"),
    ("power_statistics", "/energy/powerStatistics"),
    ("retired_capacity_plants", "/retired-capacity-plants"),
    ("plant_pipeline_info", "/plantPipelineInfo"),
    ("power_plants_listing", "/powerPlantsListing"),
    ("plant_list_by_source", "/plantListBySource"),
    ("capacity_metatable", "/capacity-metatable-data"),
    ("daily_peak_demand_last_30", "/dailyPeakDemand/last30Days"),
    ("discoms", "/discoms"),
]


def _shape(value: object, *, depth: int = 0) -> str:
    pad = "  " * depth
    if isinstance(value, list):
        if not value:
            return f"{pad}list[0]"
        head = value[0]
        return f"{pad}list[{len(value)}] of\n" + _shape(head, depth=depth + 1)
    if isinstance(value, dict):
        out = [f"{pad}dict({len(value)} keys):"]
        for k, v in list(value.items())[:12]:
            t = type(v).__name__
            sample: str
            if isinstance(v, (list, dict)):
                sample = f"[{len(v)}]" if isinstance(v, list) else f"{{{len(v)} keys}}"
            else:
                s = repr(v)
                sample = s if len(s) <= 50 else s[:47] + "..."
            out.append(f"{pad}  {k!r}: {t} {sample}")
        if len(value) > 12:
            out.append(f"{pad}  ... ({len(value) - 12} more keys)")
        return "\n".join(out)
    return f"{pad}{type(value).__name__} {repr(value)[:80]}"


def main() -> None:
    # Try both hosts: bare and /v1
    client_v0 = IcedClient(runtime_root=REPO_ROOT, polite_delay=0.5)
    client_v1 = IcedClient(host="https://icedapi.niti.gov.in/v1", runtime_root=REPO_ROOT, polite_delay=0.5)
    for name, path in ENDPOINTS:
        print("=" * 78)
        print(f"### {name}    GET {path}")
        resp = None
        for label, c in (("v0", client_v0), ("v1", client_v1)):
            try:
                resp = c.get(path)
                print(f"  HOST: {label} ({c._host})")
                break
            except Exception as exc:
                print(f"  {label} FAILED: {type(exc).__name__}: {str(exc)[:120]}")
        if resp is None:
            continue
        body = resp.decrypted
        print(f"  url           = {resp.url}")
        print(f"  raw_path      = {resp.raw_path.relative_to(REPO_ROOT).as_posix()}")
        print(f"  top-level type = {type(body).__name__}")
        # ICED frequently wraps as {status, data}.
        if isinstance(body, dict) and set(body.keys()) >= {"status", "data"}:
            print(f"  envelope: status={body.get('status')!r}, len(data)={len(body.get('data') or [])}")
            payload = body["data"]
        else:
            payload = body
        print("  shape:")
        print(_shape(payload, depth=2))
        # Sample 2 rows of the deepest list
        sample_target = payload
        # Drill into nested dicts to find a likely list of rows
        if isinstance(payload, dict):
            for k, v in payload.items():
                if isinstance(v, list) and v:
                    sample_target = v
                    print(f"  drilled into key {k!r} (list[{len(v)}])")
                    break
        if isinstance(sample_target, list) and sample_target:
            print(f"  sample[0]: {json.dumps(sample_target[0], default=str, ensure_ascii=False)[:400]}")
            if len(sample_target) > 1:
                print(f"  sample[1]: {json.dumps(sample_target[1], default=str, ensure_ascii=False)[:400]}")


if __name__ == "__main__":
    main()
