"""One-shot Wikipedia scrape for Manipur 60-AC list (post-2008 delim).

HTL ships pre-delimitation 68-AC data for S14, so we cannot bootstrap from
the on-disk geojson. Wikipedia's "List of constituencies of the Manipur
Legislative Assembly" page carries the correct 60-AC table.

Run from repo root: python tools/scrape_manipur_acs.py
"""

from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://en.wikipedia.org/wiki/List_of_constituencies_of_the_Manipur_Legislative_Assembly"
REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "datasets" / "reference" / "in" / "states" / "S14" / "constituencies.json"
SCHEMA_URL = "https://yen-gov.github.io/schemas/constituency.schema.json"
FETCHED_AT = "2026-05-13T00:00:00Z"


class TableScraper(HTMLParser):
    """Pulls cell text out of the first wikitable on the page."""

    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.depth = 0
        self.in_row = False
        self.in_cell = False
        self.row: list[str] = []
        self.cell_text: list[str] = []
        self.rows: list[list[str]] = []
        self.captured = False

    def handle_starttag(self, tag, attrs):
        if tag == "table" and not self.captured:
            attrs_d = dict(attrs)
            if "wikitable" in attrs_d.get("class", ""):
                self.in_table = True
                self.depth = 1
                return
        if self.in_table and tag == "table":
            self.depth += 1
        if self.in_table:
            if tag == "tr":
                self.in_row = True
                self.row = []
            elif tag in ("td", "th"):
                self.in_cell = True
                self.cell_text = []

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.in_table = False
                self.captured = True
            return
        if tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif tag in ("td", "th") and self.in_cell:
            text = "".join(self.cell_text).strip()
            text = re.sub(r"\s+", " ", text)
            self.row.append(text)
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell:
            self.cell_text.append(data)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "yen-gov-scrape/0.1 (https://github.com/yen-gov)",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_acs(rows: list[list[str]]) -> list[dict]:
    """Pick rows shaped like (number, name, district, reservation)."""
    acs: dict[int, dict] = {}
    for r in rows:
        if len(r) < 3:
            continue
        # First numeric cell = AC No
        try:
            no = int(re.sub(r"\D", "", r[0]) or "0")
        except ValueError:
            continue
        if not (1 <= no <= 60):
            continue
        # Name = first non-numeric cell after position 0
        name = ""
        reservation = "GEN"
        for cell in r[1:]:
            cell = cell.strip()
            if cell and not name and not cell.isdigit():
                # Strip footnote refs like [1]
                cell = re.sub(r"\[\d+\]", "", cell).strip()
                name = cell
                continue
        # Reservation: scan cells for SC/ST tags
        joined = " | ".join(r).upper()
        if re.search(r"\bST\b", joined):
            reservation = "ST"
        elif re.search(r"\bSC\b", joined):
            reservation = "SC"
        if name:
            acs[no] = {"eci_no": no, "name": name, "reservation": reservation}
    return [acs[k] for k in sorted(acs)]


def main():
    html = fetch(URL)
    p = TableScraper()
    p.feed(html)
    print(f"raw rows captured: {len(p.rows)}")
    acs = parse_acs(p.rows)
    print(f"parsed ACs: {len(acs)} (expected 60)")
    if len(acs) != 60:
        # Print a sample to debug
        for r in p.rows[:5]:
            print("  ROW:", r)
        raise SystemExit(f"Manipur AC count {len(acs)} != 60; aborting.")

    doc = {
        "$schema": SCHEMA_URL,
        "$schema_version": "4.1",
        "sources": [{
            "url": URL,
            "fetched_at": FETCHED_AT,
            "name": "List of constituencies of the Manipur Legislative Assembly",
            "authority": "Wikipedia (CC BY-SA 4.0)",
        }],
        "state": "S14",
        "body": "AC",
        "status": "provisional",
        "constituencies": acs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    rels = OUT.relative_to(REPO).as_posix()
    res = sum(1 for a in acs if a["reservation"] != "GEN")
    print(f"  wrote {rels}  ({len(acs)} ACs, {res} reserved)")


if __name__ == "__main__":
    main()
