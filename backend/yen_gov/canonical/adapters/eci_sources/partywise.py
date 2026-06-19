"""Parse ECI partywiseresult-<state>.htm.

The partywise page is a state-level snapshot: one row per party, with seats
won, leading, and total. It does NOT carry vote counts or vote share — those
are only available by aggregating the per-constituency pages. Hence this
parser returns a `PartywiseSnapshot` (an adapter-local dataclass), not a
`ResultSummary` model. Composition into ResultSummary happens upstream once
constituencywise pages have been parsed.

The party name cell is in the form `"Full Name - SHORT"`, e.g.
`"Tamilaga Vettri Kazhagam - TVK"`. Splitting on the last `" - "` is
robust because party full-names occasionally contain a hyphen but never the
exact `" - "` sequence (verified against AcGenMay2026 partywise page).

ECI's numeric party code is embedded in the `<a href>` of the seats column,
e.g. `partywisewinresult-3679S22.htm` → code `3679`. Rows where the seats
cell has no link (a party with 0 wins/leads showing as plain text) yield
`eci_code=None`; pipeline composition can fill it from another source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import html as lxml_html


_HREF_CODE_RE = re.compile(r"partywisewinresult-(\d+)[SU]\d{2}\.htm", re.IGNORECASE)
_TOTAL_AC_RE = re.compile(r"Total\s+AC\s*:\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class PartyRow:
    """One row of the partywise table."""

    full_name: str
    short_name: str
    eci_code: str | None  # numeric string per schema; None if not parseable from href
    seats_won: int
    leading: int
    total: int


@dataclass(frozen=True)
class PartywiseSnapshot:
    """Result of parsing one partywiseresult-<state>.htm page."""

    state_name: str  # human-readable, e.g. "Tamil Nadu"
    total_seats: int  # the "Total AC : N" header
    parties: list[PartyRow]


def parse_partywise(content: bytes) -> PartywiseSnapshot:
    """Parse the bytes of a partywiseresult-<state>.htm page.

    Raises ValueError on structural surprise (missing header, missing table,
    unrecognised cell layout). Surprises mean ECI changed the page; failing
    fast is preferred over producing a misleading snapshot.
    """
    doc = lxml_html.fromstring(content)

    state_name, total_seats = _parse_header(doc)
    parties = _parse_party_rows(doc)
    if not parties:
        raise ValueError("partywise table contained no party rows")
    return PartywiseSnapshot(state_name=state_name, total_seats=total_seats, parties=parties)


def _parse_header(doc) -> tuple[str, int]:
    # Header looks like: <h2><span> <strong> Tamil Nadu</strong> (Total AC : 234)</span></h2>
    h2s = doc.xpath("//h2[.//strong]")
    for h2 in h2s:
        text = " ".join(h2.text_content().split())
        m = _TOTAL_AC_RE.search(text)
        if not m:
            continue
        strong = h2.xpath(".//strong")[0]
        state_name = strong.text_content().strip()
        if not state_name:
            continue
        return state_name, int(m.group(1))
    raise ValueError("partywise page header (state name + Total AC) not found")


def _parse_party_rows(doc) -> list[PartyRow]:
    # Find the partywise data table. There's only one <table class="table"> with
    # the thead "Party | Won | Leading | Total".
    candidates = doc.xpath("//table")
    for table in candidates:
        headers = [th.text_content().strip().lower() for th in table.xpath(".//thead//th")]
        if headers[:4] == ["party", "won", "leading", "total"]:
            return _rows_from_table(table)
    raise ValueError("could not find partywise table (expected thead Party|Won|Leading|Total)")


def _rows_from_table(table) -> list[PartyRow]:
    out: list[PartyRow] = []
    for tr in table.xpath(".//tbody/tr"):
        tds = tr.xpath("./td")
        if len(tds) < 4:
            continue
        name_cell = tds[0].text_content().strip()
        full_name, _, short_name = name_cell.rpartition(" - ")
        if not full_name or not short_name:
            # Skip rows that don't fit the "Full - SHORT" pattern (e.g. footer rows).
            continue
        eci_code = _extract_party_code(tds[1])
        seats_won = _int_or_zero(tds[1].text_content())
        leading = _int_or_zero(tds[2].text_content())
        total = _int_or_zero(tds[3].text_content())
        out.append(PartyRow(
            full_name=full_name.strip(),
            short_name=short_name.strip(),
            eci_code=eci_code,
            seats_won=seats_won,
            leading=leading,
            total=total,
        ))
    return out


def _extract_party_code(td) -> str | None:
    for a in td.xpath(".//a/@href"):
        m = _HREF_CODE_RE.search(a)
        if m:
            return m.group(1)
    return None


def _int_or_zero(text: str) -> int:
    s = text.strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0
