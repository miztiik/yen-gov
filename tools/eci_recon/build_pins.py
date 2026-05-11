"""Build the full pins.json from a sweep of known category_ids.

Produces config/eci-pins.json containing every state assembly election
the new ECI API exposes (2024+ only — 2022/2023 elections are likely on
the old portal as static PDFs and need a separate ingest path).

Mapping from screenshot of statistical-reports landing page (2026-05-11):

  2024: AP(2), Arunachal(3), Odisha(4), Sikkim(5), Haryana(6),
        J&K(7), Maharashtra(8), Jharkhand(9)
  2025: Delhi(10), Bihar(15)
  2026: Assam(23), Kerala(24), Puducherry(25), TN(26), WB(27)

Loksabha 2024 (cid=1) and bye-elections (11-14, 16, 17) are skipped —
state assembly only.
"""

from __future__ import annotations

import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API = "https://www.eci.gov.in/eci-backend/public/api/election-result"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "secret": "ECI@MAIN825",
    "Accept": "application/json",
    "Referer": "https://www.eci.gov.in/statistical-reports",
    "Origin": "https://www.eci.gov.in",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

# (state_code, year, category_id) — state codes per ECI taxonomy.
PINS: list[tuple[str, int, int]] = [
    ("S01", 2024, 2),   # Andhra Pradesh
    ("S02", 2024, 3),   # Arunachal Pradesh
    ("S18", 2024, 4),   # Odisha
    ("S21", 2024, 5),   # Sikkim
    ("S07", 2024, 6),   # Haryana
    ("U08", 2024, 7),   # Jammu & Kashmir
    ("S13", 2024, 8),   # Maharashtra
    ("S27", 2024, 9),   # Jharkhand
    ("U05", 2025, 10),  # NCT of Delhi
    ("S04", 2025, 15),  # Bihar
    ("S03", 2026, 23),  # Assam
    ("S11", 2026, 24),  # Kerala
    ("U07", 2026, 25),  # Puducherry
    ("S22", 2026, 26),  # Tamil Nadu
    ("S25", 2026, 27),  # West Bengal
]

NOTES = {
    ("S04", 2025): "Bihar Oct-Nov 2025. ECI catalogue lists ids 15 and 16 with the same cat_name; 16 has suffix 'S' (likely supplementary). Pinned 15 as the primary.",
    ("U07", 2026): "Confirmed live during U07 onboarding (2026-05-11).",
}


def main() -> None:
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    out_pins: list[dict] = []
    with httpx.Client(headers=HEADERS) as client:
        for state, year, cid in PINS:
            r = client.get(API, params={"category_id": cid}, timeout=20.0)
            r.raise_for_status()
            body = r.json()
            cat_name = body.get("cat_name", "")
            doc_count = len(body.get("results") or [])
            print(f"  {state}/{year} cid={cid:>2} docs={doc_count} :: {cat_name[:70]}")
            entry = {
                "state": state,
                "year": year,
                "category_id": cid,
                "cat_name": cat_name.strip(),
                "confirmed_at": now_iso,
            }
            note_extra = NOTES.get((state, year))
            base_note = f"{doc_count} documents in catalog."
            entry["notes"] = f"{base_note} {note_extra}" if note_extra else base_note
            out_pins.append(entry)

    payload = {
        "$schema": "https://yen-gov.github.io/schemas/eci_pins.schema.json",
        "$schema_version": "1.0",
        "sources": [],
        "pins": out_pins,
    }
    out = Path(__file__).resolve().parents[2] / "config" / "eci-pins.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"\nWrote {out}  ({len(out_pins)} pins)")


if __name__ == "__main__":
    main()
