"""Parse 'List of districts of <State>' on en.wikipedia.org.

Wikipedia is the fallback source while we lack LGD codes (the gov.in Local
Government Directory's numeric district ids). Per CLAUDE.md §3 the schema
already accommodates that fallback: `district.id_source` is `"lgd"` or
`"wikipedia"`.

The first wikitable on this article enumerates currently-existing districts
with the columns we need: District (name), Code (Wikipedia's 2–3 letter
abbreviation), Headquarters, Estd., Predecessor.

Two-pass design:

  1. Parse rows into a list of (name, code, hq, estd_text, predecessor_text).
  2. Build a name → code map, then resolve `split_from` predecessor strings
     into a list of code ids. Predecessors not found in the table (e.g. an
     original district carved up before any current districts existed) are
     dropped and noted in `notes`.

Date parsing is forgiving: Wikipedia uses "23 November 2007", "1 April 2020",
or just "2007" for older districts. `_parse_estd_date` returns ISO 8601 when
day+month+year are present, else None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from lxml import html as lxml_html

from yen_gov.core.models import DistrictEntry, DistrictsCollection, SourceRef


_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
_DAY_MONTH_YEAR_RE = re.compile(
    r"^\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*$"
)
# Strip Wikipedia citation markers like [12], [a], [note 1].
_CITATION_RE = re.compile(r"\[[^\]]+\]")
# Predecessor cells often list multiple districts on separate lines.
_PREDECESSOR_SPLIT_RE = re.compile(r"\s*[\n,;/]\s*")


@dataclass(frozen=True)
class _Row:
    name: str
    code: str
    headquarters: str | None
    created_on: str | None  # YYYY-MM-DD or None
    predecessors: list[str]  # raw names, pre-resolution


def parse_districts(content: bytes, *, state_code: str, sources: list[SourceRef]) -> DistrictsCollection:
    """Parse the bytes of a Wikipedia 'List of districts of <State>' article.

    Args:
        content: HTML bytes.
        state_code: ECI state code (^[SU]\\d{2}$). Stamped on the model;
            the page itself doesn't carry it.
        sources: provenance to stamp on the artifact.

    Raises ValueError on missing/unrecognised table or empty rows.
    """
    doc = lxml_html.fromstring(content)
    table, cols = _find_districts_table(doc)
    rows = _parse_rows(table, cols)
    if not rows:
        raise ValueError("districts wikitable contained no parseable rows")
    name_to_code = {r.name.casefold(): r.code for r in rows}
    entries = [_to_entry(r, name_to_code) for r in rows]
    return DistrictsCollection(sources=sources, state=state_code, districts=entries)


# A column index map: logical name → 0-based column index in the wikitable.
# Required keys: name, code, headquarters, established. Optional: predecessor.
_REQUIRED_COLS = ("name", "code", "headquarters", "established")


def _find_districts_table(doc):
    """Return (table, columns) where columns maps logical names to indexes.

    Wikipedia state-articles vary in column order and which columns exist:
    Tamil Nadu's table has District|Code|HQ|Estd|Predecessor; Kerala's has
    Code|District|HQ|Established|Population|Area|... and no predecessor.
    Match by header text rather than position.
    """
    for table in doc.xpath('//table[contains(@class, "wikitable")]'):
        headers = [_clean(th.text_content()).lower() for th in table.xpath('.//tr[1]//th')]
        if not headers:
            continue
        cols = _classify_headers(headers)
        if all(k in cols for k in _REQUIRED_COLS):
            return table, cols
    raise ValueError(
        "could not find Wikipedia districts wikitable "
        "(need columns matching: District, Code, Headquarters, Established/Estd)"
    )


def _classify_headers(headers: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, h in enumerate(headers):
        if "code" in cols and "name" in cols and "headquarters" in cols and "established" in cols:
            pass  # keep scanning for optional predecessor
        if "name" not in cols and h.startswith("district"):
            cols["name"] = i
        elif "code" not in cols and h.startswith("code"):
            cols["code"] = i
        elif "headquarters" not in cols and "headquarter" in h:
            cols["headquarters"] = i
        elif "established" not in cols and ("estd" in h or "established" in h):
            cols["established"] = i
        elif "predecessor" not in cols and "predecessor" in h:
            cols["predecessor"] = i
    return cols


def _parse_rows(table, cols: dict[str, int]) -> list[_Row]:
    out: list[_Row] = []
    needed = max(cols.values()) + 1
    for tr in table.xpath(".//tr[position()>1]"):
        cells = tr.xpath("./th | ./td")
        if len(cells) < needed:
            continue
        name = _clean(cells[cols["name"]].text_content())
        code = _clean(cells[cols["code"]].text_content())
        hq = _clean(cells[cols["headquarters"]].text_content()) or None
        estd_text = _clean(cells[cols["established"]].text_content())
        pred_text = (
            _clean(cells[cols["predecessor"]].text_content())
            if "predecessor" in cols else ""
        )
        if not name or not code:
            continue
        if name.casefold() == "total" or code.casefold() == "total":
            continue  # Wikipedia tables sometimes append a totals footer row.
        out.append(_Row(
            name=name,
            code=code,
            headquarters=hq,
            created_on=_parse_estd_date(estd_text),
            predecessors=_split_predecessors(pred_text),
        ))
    return out


def _to_entry(row: _Row, name_to_code: dict[str, str]) -> DistrictEntry:
    resolved: list[str] = []
    unresolved: list[str] = []
    for p in row.predecessors:
        code = name_to_code.get(p.casefold())
        if code is not None and code != row.code:
            resolved.append(code)
        elif p:
            unresolved.append(p)
    notes: str | None = None
    if unresolved:
        notes = f"split_from predecessors not in current district list: {', '.join(unresolved)}"
    return DistrictEntry(
        id=row.code,
        id_source="wikipedia",
        name=row.name,
        headquarters=row.headquarters,
        created_on=row.created_on,
        split_from=resolved or None,
        notes=notes,
    )


# --- helpers ---------------------------------------------------------------

def _clean(text: str) -> str:
    s = _CITATION_RE.sub("", text or "")
    return " ".join(s.split()).strip()


def _split_predecessors(text: str) -> list[str]:
    if not text or text in {"—", "-", "–", "None", "N/A"}:
        return []
    parts = [_clean(p) for p in _PREDECESSOR_SPLIT_RE.split(text)]
    return [p for p in parts if p]


def _parse_estd_date(text: str) -> str | None:
    m = _DAY_MONTH_YEAR_RE.match(text)
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTH_NAMES.get(m.group(2).lower())
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, day).date().isoformat()
    except ValueError:
        return None
