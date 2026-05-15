"""Probe ICED air-quality endpoints and pretty-print shape for fixture capture."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common import IcedClient

HOST = "https://icedapi.niti.gov.in"
RUNTIME = Path(".runtime")

ENDPOINTS = [
    ("aq_fgd",             "/climate-environment/environment/air-quality/fgd"),
    ("aq_aqi_map_markers", "/climate-environment/environment/air-quality/aqi-map-markers"),
    ("aq_cpcb_dates",      "/climate-environment/environment/air-quality/cpbc-dates"),
]


def describe(value, depth=0, indent="  "):
    pad = indent * depth
    if isinstance(value, dict):
        keys = list(value.keys())
        print(f"{pad}dict[{len(keys)}] keys={keys}")
        for k in keys[:8]:
            v = value[k]
            print(f"{pad}{indent}{k!r}:", end=" ")
            if isinstance(v, (dict, list)):
                print()
                describe(v, depth + 2)
            else:
                print(repr(v)[:200])
    elif isinstance(value, list):
        print(f"{pad}list[{len(value)}]")
        if value:
            print(f"{pad}{indent}sample[0]:")
            describe(value[0], depth + 2)
    else:
        print(f"{pad}{type(value).__name__}: {value!r}"[:200])


def main():
    c = IcedClient(host=HOST, runtime_root=RUNTIME)
    for name, path in ENDPOINTS:
        print("=" * 70)
        print(f"{name}  {path}")
        print("=" * 70)
        try:
            r = c.get(path)
        except Exception as e:
            print(f"  FAIL: {e}")
            continue
        describe(r.decrypted)
        out = Path(f".runtime/aq_probe_{name}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r.decrypted, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> wrote {out}")
        print()


if __name__ == "__main__":
    main()
