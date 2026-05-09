"""Parse 'List of constituencies of the <State> Legislative Assembly' on Wikipedia.

Source of truth for the per-state Assembly Constituency list with reservation
status (GEN/SC/ST) — information that ECI publishes only inside delimitation-
order PDFs. This page is also the canonical mapping from constituency number
to constituency name and parent district.

The article's first wikitable enumerates all N ACs with at minimum these
columns: number, name (which Wikipedia variously labels "Constituency" or
"Name"), and reservation. Columns are matched by header text rather than
fixed position so the parser handles both the TN layout (#|Constituency|
Reserved) and the Kerala layout (No.|Name|Reservation|District|Lok Sabha|
Electorate). District / PC name columns, when present, are not currently
mapped into the schema's `district_id` / `pc_id` — that requires cross-file
resolution (district name → districts.json id, PC name → PC eci_no), which
docs/architecture/backend/sources-wikipedia.md leaves to a follow-up "promote to status=complete" step.

Reservation cell encoding observed on en.wikipedia.org:

  - "-" / "—" / blank / "None"  → GEN (General / unreserved)
  - "SC"                        → SC
  - "ST"                        → ST

Anything else raises ValueError — wide reservation codes invented by Wikipedia
editors must surface as a parser failure, not be silently coerced to GEN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import html as lxml_html

from yen_gov.core.models import (
    ConstituenciesCollection,
    ConstituencyEntry,
    SourceRef,
)


_CITATION_RE = re.compile(r"\[[^\]]+\]")
_GEN_TOKENS = {"", "-", "—", "–", "gen", "general", "none"}
_REQUIRED_COLS = ("number", "name", "reservation")


@dataclass(frozen=True)
class _Row:
    eci_no: int
    name: str
    reservation: str  # GEN | SC | ST
    district_name: str | None  # raw, pre-resolution


def parse_ac_constituencies(
    content: bytes,
    *,
    state_code: str,
    sources: list[SourceRef],
    district_id_by_name: dict[str, str] | None = None,
) -> ConstituenciesCollection:
    """Parse the AC wikitable.

    If ``district_id_by_name`` is supplied (casefolded keys), each AC's
    district name is resolved to a district id and stamped onto
    ``ConstituencyEntry.district_id``. Unmatched names are left absent —
    the entry stays valid under the provisional schema. Status remains
    ``"provisional"`` regardless: promoting to ``"complete"`` also requires
    ``pc_id``, which needs a separate Lok-Sabha-↔-AC mapping (out of scope
    for the Wikipedia AC table alone).
    """
    doc = lxml_html.fromstring(content)
    table, cols = _find_table(doc)
    rows = _parse_rows(table, cols)
    if not rows:
        raise ValueError("constituencies wikitable contained no parseable rows")

    nos = sorted(r.eci_no for r in rows)
    if nos != list(range(1, len(nos) + 1)):
        raise ValueError(f"non-contiguous AC numbers parsed: {nos[:5]}…")

    entries = [
        ConstituencyEntry(
            eci_no=r.eci_no, name=r.name, reservation=r.reservation,
            district_id=_resolve_district_id(r.district_name, district_id_by_name),
        )
        for r in sorted(rows, key=lambda r: r.eci_no)
    ]
    return ConstituenciesCollection(
        sources=sources, state=state_code, body="AC",
        status="provisional",  # Wikipedia bootstrap is always provisional (docs/architecture/data-model.md)
        constituencies=entries,
    )


def _resolve_district_id(
    name: str | None, m: dict[str, str] | None,
) -> str | None:
    """Look up a district id from a Wikipedia AC-table district cell.

    Two-pass match: first the casefolded raw name (strips parenthesised parts
    and citations), then a `_norm`-key fallback that collapses transliteration
    variants common in Indian district names — `Th`↔`T`, doubled consonants,
    interior vowels (`Kasargod`↔`Kasaragod`, `Kanniyakumari`↔`Kanyakumari`,
    `Thiruvallur`↔`Tiruvallur`).
    """
    if not name or not m:
        return None
    key = _strip_parens(name).casefold().strip()
    if key in m:
        return m[key]
    nk = _norm(name)
    return m.get(nk) if nk else None


_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")
_NON_ALPHA_RE = re.compile(r"[^a-z]")
_VOWEL_RE = re.compile(r"[aeiou]")
_DUPE_RE = re.compile(r"(.)\1+")


def _strip_parens(s: str) -> str:
    return _PAREN_RE.sub("", s).strip()


def _norm(s: str) -> str:
    """Collapsed-skeleton key for fuzzy district-name matching.

    Lowercases, strips parens/non-alpha, drops `h`, removes vowels after the
    first character, collapses repeated letters. Designed to be fed into a
    pre-built lookup whose keys were generated the same way; do not call this
    on a single side of a comparison.
    """
    s = _strip_parens(s).casefold()
    s = _NON_ALPHA_RE.sub("", s).replace("h", "")
    if not s:
        return ""
    head, tail = s[0], _VOWEL_RE.sub("", s[1:])
    return _DUPE_RE.sub(r"\1", head + tail)


def build_district_lookup(districts: list[tuple[str, str]]) -> dict[str, str]:
    """Build the {name → id} map for ``parse_ac_constituencies``.

    Accepts ``[(name, id), ...]`` pairs. Each district is indexed under both
    its casefolded raw name and its `_norm` skeleton, so callers don't need
    to know about the two-pass matching.
    """
    out: dict[str, str] = {}
    for name, did in districts:
        out[_strip_parens(name).casefold().strip()] = did
        nk = _norm(name)
        if nk:
            out.setdefault(nk, did)
    return out


def _find_table(doc):
    """Return (table, columns) where columns maps logical names to indexes."""
    for table in doc.xpath('//table[contains(@class, "wikitable")]'):
        headers = [_clean(th.text_content()).lower() for th in table.xpath('.//tr[1]//th')]
        if not headers:
            continue
        cols = _classify_headers(headers)
        if all(k in cols for k in _REQUIRED_COLS):
            return table, cols
    raise ValueError(
        "could not find Wikipedia AC constituencies wikitable "
        "(need columns matching: No., Constituency/Name, Reservation)"
    )


def _classify_headers(headers: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, h in enumerate(headers):
        if "number" not in cols and (
            h in {"#", "no.", "no", "ac no", "constituency no"} or h.startswith("no.")
        ):
            cols["number"] = i
        elif "name" not in cols and (h.startswith("constituency") or h == "name"):
            cols["name"] = i
        elif "reservation" not in cols and ("reserv" in h or "category" in h):
            cols["reservation"] = i
        elif "district" not in cols and h.startswith("district"):
            cols["district"] = i
    return cols


def _parse_rows(table, cols: dict[str, int]) -> list[_Row]:
    out: list[_Row] = []
    needed = max(cols.values()) + 1
    grid = _expand_rowspans(table)
    for row in grid[1:]:  # skip header row
        if len(row) < needed:
            continue
        try:
            no = int(_clean(row[cols["number"]]))
        except ValueError:
            continue
        name = _clean(row[cols["name"]])
        reservation = _normalise_reservation(_clean(row[cols["reservation"]]))
        district_name = (
            _clean(row[cols["district"]]) if "district" in cols else None
        ) or None
        if not name:
            continue
        out.append(_Row(
            eci_no=no, name=name, reservation=reservation,
            district_name=district_name,
        ))
    return out


def _expand_rowspans(table) -> list[list[str]]:
    """Materialise the table as a dense 2D grid honouring rowspan/colspan.

    Wikipedia tables (Kerala AC list) use rowspan on the District / Lok Sabha /
    Reservation columns when consecutive ACs share a value, so a naive
    cell-by-position read sees later rows with fewer cells than the header.
    """
    grid: list[list[str | None]] = []
    pending: dict[tuple[int, int], str] = {}  # (row, col) -> text held by rowspan
    trs = table.xpath("./tr | ./tbody/tr | ./thead/tr")
    for r, tr in enumerate(trs):
        row: list[str | None] = []
        c = 0
        cells = iter(tr.xpath("./th | ./td"))
        cell = next(cells, None)
        while True:
            if (r, c) in pending:
                row.append(pending.pop((r, c)))
                c += 1
                continue
            if cell is None:
                break
            text = cell.text_content() or ""
            try:
                colspan = max(1, int(cell.get("colspan") or "1"))
            except ValueError:
                colspan = 1
            try:
                rowspan = max(1, int(cell.get("rowspan") or "1"))
            except ValueError:
                rowspan = 1
            for dc in range(colspan):
                row.append(text)
                for dr in range(1, rowspan):
                    pending[(r + dr, c + dc)] = text
                c += 1
            cell = next(cells, None)
        # consume any trailing pending cells for this row
        while (r, c) in pending:
            row.append(pending.pop((r, c)))
            c += 1
        grid.append(row)
    return [[(s or "") for s in row] for row in grid]


def _normalise_reservation(text: str) -> str:
    t = text.strip().lower()
    if t in _GEN_TOKENS:
        return "GEN"
    upper = text.strip().upper()
    if upper in {"SC", "ST"}:
        return upper
    raise ValueError(f"unrecognised reservation token: {text!r}")


def _clean(text: str) -> str:
    s = _CITATION_RE.sub("", text or "")
    return " ".join(s.split()).strip()
