"""Deep-inspect each macro endpoint payload."""
from __future__ import annotations

import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.iced_common.client import IcedClient  # noqa: E402

c = IcedClient(host="https://icedapi.niti.gov.in", polite_delay=0.5)


def survey(name, path, dim_keys):
    print("=" * 78)
    print(f"### {name}")
    rows = c.get(path).decrypted["data"]
    print(f"  total rows: {len(rows)}")
    for k in dim_keys:
        vals = sorted({str(r.get(k)) for r in rows if r.get(k) is not None})
        print(f"  distinct {k!r}: ({len(vals)}) {vals[:20]}{' ...' if len(vals)>20 else ''}")
    # If 'state' present, show count of states
    if any("state" in r for r in rows):
        states = sorted({r["state"] for r in rows if r.get("state")})
        print(f"  states ({len(states)}): {states[:10]} ...")
    print(f"  first 3 rows:")
    for r in rows[:3]:
        print(f"    {json.dumps(r)}")
    print()


survey("gdp_trend", "/economy-demography/key-economic-indicators/gdp-trend",
       ["priceCategory", "priceType", "trendType", "year"])
survey("gva_trend", "/economy-demography/key-economic-indicators/gva-trend",
       ["industryItem", "trendType", "priceType", "year"])
survey("industrial_production", "/economy-demography/key-economic-indicators/industrial-production",
       ["category", "classification", "year"])
survey("balance_trendline", "/economy-demography/key-economic-indicators/balance-trendline",
       ["item", "year"])
survey("demography_actual", "/economy-demography/demography/demographyActual",
       ["category", "type", "year"])
