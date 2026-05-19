"""Show the top-N unresolved party shorts from the gap report."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    path = Path(".runtime/_party_gap_report.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    unresolved = data["unresolved"]
    print(f"Total unresolved shorts: {len(unresolved)}")
    print(f"Top {n} by candidate count:")
    print()
    print(f"  {'SHORT':<16}  {'CAND':>5}  {'EV':>3}  {'ECI':<6}  STATES")
    print(f"  {'-' * 14}  {'-' * 5}  {'-' * 3}  {'-' * 6}  {'-' * 30}")
    cum = 0
    for x in unresolved[:n]:
        states = ",".join(x.get("states", [])[:5])
        cum += x["total_candidates"]
        print(
            f"  {x['short']:<16}  {x['total_candidates']:>5}  {x['n_events']:>3}  "
            f"{(x['eci_code_observed'] or '-'):<6}  {states}"
        )
    total = sum(x["total_candidates"] for x in unresolved)
    print()
    print(f"Cumulative top {n}: {cum} / {total} candidates ({100*cum/total:.1f}%)")


if __name__ == "__main__":
    main()
