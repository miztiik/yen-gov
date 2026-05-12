"""One-shot verification that the refactored Section 10 parser handles
both the 2024+ 15-col layout and the 2023 14-col layout.

Not committed as a test (no fixture in repo for 2023 yet); kept as a tools/
script per the recon recipe pattern.
"""

from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.sources.eci.statistical_report_detailed import parse_detailed_results

ROOT = Path(__file__).resolve().parents[1]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
HEADERS_2023 = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Referer": "https://www.eci.gov.in/mp-legislative-election-2023-statistical-report",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}


def show(label: str, content: bytes) -> None:
    raw = parse_detailed_results(content)
    s = raw.sections[0]
    print(f"{label}: {len(raw.sections)} ACs")
    print(
        f"  AC #{s.eci_no} {s.constituency_name!r}  polled={s.polled_total}"
        f"  turnout={s.turnout_pct}  electors={s.total_electors}"
    )
    top = s.candidates[0]
    print(
        f"  top cand: {top.name!r} party={top.party_short}"
        f" votes={top.votes_total} share={top.vote_share_pct}"
    )


def main() -> None:
    tn_2026 = (
        ROOT / ".runtime/raw/eci/eci-backend/public/all_files/election_report"
        / "General_Election_to_the_Legislative_Assembly_of_Tamil_Nadu_2026_2026"
        / "10-Detailed_Results_1778165153.xlsx"
    )
    if tn_2026.exists():
        show("TN-2026 (15-col)", tn_2026.read_bytes())

    url = (
        "https://www.eci.gov.in/eci-backend/public/all_files/"
        "full-statistical-reports/mp/2023/Detailed_Results.xlsx"
    )
    req = urllib.request.Request(url, headers=HEADERS_2023)
    content = urllib.request.urlopen(req, timeout=60).read()
    show("MP-2023 (14-col)", content)


if __name__ == "__main__":
    main()
