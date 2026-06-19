"""ECI 2024 Parliament (PC) constituency-wise result CSV parser.

Reads the frozen ECI Report 33 ("Constituency Wise Detailed Result") CSV and
the Report 34 ("Details Of Assembly Segment Of PC") crosswalk, both stdlib
``csv`` only (NO xlrd / pandas per the plan's Gregor verdict).

Report 33 is the PC spine: postal-inclusive, one row per candidate, with the
per-PC totals (``Total Votes Polled In The Constituency``, ``Valid Votes``,
``Total Electors``) repeated on every candidate row of that PC. NOTA is a
candidate row (``Party Name == NOTA``). The file has TWO banner rows before
the real header at ``csv.reader`` row index 2, and trailing footer
pseudo-rows ("Disclaimer", "These statistical reports ...") that are skipped.

Report 33 carries NO ``PC No`` column; ``pc_no`` is sourced from the Report 34
crosswalk on ``(State Name, PC Name)``. Report 34 is EVM-only / AC-segment
grain and is used ONLY for that crosswalk, never as the vote spine.

The parser is a Message Translator at the system boundary (Gregor verdict):
it asserts the expected header cells are present and raises a fail-fast
``LsConstituencywiseError`` naming the missing columns rather than silently
coercing or positionally guessing.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

# Header cells the Report 33 parser depends on. A missing cell aborts the
# parse at the boundary (fail-fast Message Translator), never silently.
REPORT33_REQUIRED_HEADER = (
    "State Name",
    "PC Name",
    "Candidate Name",
    "Party Name",
    "General",
    "Postal",
    "Total",
    "Valid Votes",
    "Total Electors",
)
# Per-PC total-votes column carries an embedded newline in the source file.
_TOTAL_POLLED_HEADER = "Total Votes Polled In\nThe Constituency"
_TOTAL_POLLED_HEADER_FLAT = "Total Votes Polled In The Constituency"

REPORT34_REQUIRED_HEADER = ("State/UT Name", "PC NO", "PC NAME")

_FOOTER_PREFIXES = ("Disclaimer", "Note", "These statistical reports")

_NOTA_TOKENS = {"NOTA", "NONE OF THE ABOVE"}


class LsConstituencywiseError(Exception):
    """Raised when the ECI LS CSV does not match the expected contract."""


@dataclass(frozen=True)
class PcCandidateRaw:
    name: str
    party_name: str
    gender: str | None
    age: int | None
    category: str | None
    general_votes: int
    postal_votes: int
    total_votes: int
    is_nota: bool
    # Biographic enrichment. The ECI Report-33 source leaves these None
    # (ECI does not publish education/profession); the TCPD historical-GE
    # source (``sources/eci/ls_ge_tcpd.py``) fills them. Defaulting to None
    # keeps the 2024 ECI envelope byte-identical.
    education: str | None = None
    profession: str | None = None


@dataclass(frozen=True)
class PcResultRaw:
    state_name: str
    state_code: str
    pc_name: str
    pc_no: int
    total_electors: int | None
    total_votes_polled: int
    valid_votes: int | None
    candidates: tuple[PcCandidateRaw, ...]


def _norm(value: str | None) -> str:
    """Normalise a state/PC name for join + entity-code resolution.

    Strips a trailing parenthetical, collapses whitespace, maps ``&`` to
    ``and`` (ECI uses ``&`` where entities.json uses ``and``), lower-cases.
    """
    text = re.sub(r"\s*\([^)]*\)\s*$", "", value or "").strip()
    text = text.replace("&", "and")
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def _as_int(raw: str | None, *, allow_blank: bool = False) -> int | None:
    text = (raw or "").strip().replace(",", "")
    if not text:
        if allow_blank:
            return None
        raise LsConstituencywiseError(f"expected an integer, got blank: {raw!r}")
    try:
        return int(text)
    except ValueError as exc:  # pragma: no cover - defensive
        raise LsConstituencywiseError(f"unparseable integer: {raw!r}") from exc


def _is_footer(first_cell: str) -> bool:
    return any(first_cell.startswith(prefix) for prefix in _FOOTER_PREFIXES)


def _is_nota(party_name: str, candidate_name: str) -> bool:
    return (
        party_name.strip().upper() in _NOTA_TOKENS
        or candidate_name.strip().upper() in _NOTA_TOKENS
    )


def load_state_code_lookup(datasets_root: Path) -> dict[str, str]:
    """Build ``{normalised_display_name: entity_code}`` for S*/U* entities.

    Also indexes each entity's ``legacy_id`` (when populated) so pre-rename
    historical published names resolve forward to the current entity_code.
    Used by the TCPD LS GE pre-1999 ingest to map e.g. "Madras"->"S22"
    (renamed to Tamil Nadu 1969), "Mysore"->"S10" (renamed to Karnataka
    1973), "Delhi"->"U05" (NCT status from 1991). Same-entity-same-
    boundaries renames only; per-PC reorgs go through the
    pc_historical_crosswalk override path."""
    entities_path = datasets_root / "taxonomy" / "entities.json"
    raw = json.loads(entities_path.read_text(encoding="utf-8"))
    lookup: dict[str, str] = {}
    for row in raw.get("entities", []):
        code = str(row.get("entity_code", ""))
        if code[:1] in ("S", "U"):
            lookup[_norm(str(row.get("display_name", "")))] = code
            legacy = row.get("legacy_id")
            if legacy:
                lookup[_norm(str(legacy))] = code
    return lookup


def _resolve_header(rows: list[list[str]]) -> dict[str, int]:
    """Locate Report 33's header (row index 2) and map column->index.

    Raises ``LsConstituencywiseError`` naming any missing required column.
    """
    if len(rows) <= 3:
        raise LsConstituencywiseError("Report 33 CSV has no data rows")
    header = rows[2]
    index: dict[str, int] = {}
    for i, cell in enumerate(header):
        key = (cell or "").strip()
        if key:
            index.setdefault(key, i)
    # The per-PC total-polled header carries an embedded newline; expose it
    # under its flattened name too so callers can use the readable form.
    if _TOTAL_POLLED_HEADER in index and _TOTAL_POLLED_HEADER_FLAT not in index:
        index[_TOTAL_POLLED_HEADER_FLAT] = index[_TOTAL_POLLED_HEADER]
    missing = [col for col in REPORT33_REQUIRED_HEADER if col not in index]
    if missing:
        raise LsConstituencywiseError(
            "Report 33 CSV header missing required columns: "
            + ", ".join(repr(m) for m in missing)
            + f" (header row was: {header!r})"
        )
    return index


def parse_pc_crosswalk(csv_path: Path) -> dict[tuple[str, str], int]:
    """Parse Report 34 -> ``{(state_norm, pc_norm): pc_no}``.

    Report 34's header is at row index 1 (one banner row). Multiple rows per
    PC (one per AC segment x candidate) collapse to one ``pc_no`` per
    ``(state, pc)``; a contradictory ``pc_no`` for the same key is a fail-fast.
    """
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) <= 2:
        raise LsConstituencywiseError("Report 34 crosswalk CSV has no data rows")
    header = [(c or "").strip() for c in rows[1]]
    missing = [col for col in REPORT34_REQUIRED_HEADER if col not in header]
    if missing:
        raise LsConstituencywiseError(
            "Report 34 crosswalk header missing required columns: "
            + ", ".join(repr(m) for m in missing)
        )
    i_state = header.index("State/UT Name")
    i_pcno = header.index("PC NO")
    i_pcname = header.index("PC NAME")
    crosswalk: dict[tuple[str, str], int] = {}
    for row in rows[2:]:
        if not row or not (row[i_state] or "").strip():
            continue
        if _is_footer((row[i_state] or "").strip()):
            continue
        pc_no = _as_int(row[i_pcno], allow_blank=True)
        if pc_no is None:
            continue
        key = (_norm(row[i_state]), _norm(row[i_pcname]))
        prior = crosswalk.get(key)
        if prior is not None and prior != pc_no:
            raise LsConstituencywiseError(
                f"Report 34 crosswalk has conflicting PC NO for {key!r}: "
                f"{prior} vs {pc_no}"
            )
        crosswalk[key] = pc_no
    return crosswalk


def parse_ls_constituencywise(
    csv_path: Path,
    *,
    crosswalk_path: Path,
    datasets_root: Path,
) -> list[PcResultRaw]:
    """Parse Report 33 into one ``PcResultRaw`` per parliamentary constituency.

    ``pc_no`` is joined from the Report 34 crosswalk on ``(state, pc)``;
    ``state_code`` from ``entities.json`` display names. A PC whose
    ``(state, pc)`` is absent from the crosswalk, or whose state name does not
    resolve to an entity code, is a fail-fast.
    """
    state_codes = load_state_code_lookup(datasets_root)
    crosswalk = parse_pc_crosswalk(crosswalk_path)

    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    index = _resolve_header(rows)

    i_state = index["State Name"]
    i_pc = index["PC Name"]
    i_cand = index["Candidate Name"]
    i_party = index["Party Name"]
    i_general = index["General"]
    i_postal = index["Postal"]
    i_total = index["Total"]
    i_valid = index["Valid Votes"]
    i_electors = index["Total Electors"]
    i_polled = index[_TOTAL_POLLED_HEADER_FLAT]
    i_gender = index.get("Gender")
    i_age = index.get("Age")
    i_category = index.get("Category")

    # Preserve first-seen PC order; aggregate candidate rows per PC.
    grouped: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for row in rows[3:]:
        if not row:
            continue
        state_name = (row[i_state] if i_state < len(row) else "").strip()
        if not state_name or _is_footer(state_name):
            continue
        pc_name = (row[i_pc] if i_pc < len(row) else "").strip()
        if not pc_name:
            continue
        key = (state_name, pc_name)
        candidate = PcCandidateRaw(
            name=(row[i_cand] or "").strip(),
            party_name=(row[i_party] or "").strip(),
            gender=((row[i_gender] or "").strip() or None) if i_gender is not None else None,
            age=_as_int(row[i_age], allow_blank=True) if i_age is not None else None,
            category=((row[i_category] or "").strip() or None) if i_category is not None else None,
            general_votes=_as_int(row[i_general], allow_blank=True) or 0,
            postal_votes=_as_int(row[i_postal], allow_blank=True) or 0,
            total_votes=_as_int(row[i_total], allow_blank=True) or 0,
            is_nota=_is_nota((row[i_party] or ""), (row[i_cand] or "")),
        )
        if key not in grouped:
            order.append(key)
            grouped[key] = {
                "state_name": state_name,
                "pc_name": pc_name,
                "total_electors": _as_int(row[i_electors], allow_blank=True),
                "total_votes_polled": _as_int(row[i_polled], allow_blank=True) or 0,
                "valid_votes": _as_int(row[i_valid], allow_blank=True),
                "candidates": [],
            }
        grouped[key]["candidates"].append(candidate)

    results: list[PcResultRaw] = []
    for key in order:
        state_name, pc_name = key
        norm_key = (_norm(state_name), _norm(pc_name))
        state_code = state_codes.get(_norm(state_name))
        if state_code is None:
            raise LsConstituencywiseError(
                f"state name {state_name!r} does not resolve to an entity code"
            )
        pc_no = crosswalk.get(norm_key)
        if pc_no is None:
            raise LsConstituencywiseError(
                f"PC {pc_name!r} in {state_name!r} absent from Report 34 crosswalk"
            )
        bucket = grouped[key]
        results.append(PcResultRaw(
            state_name=state_name,
            state_code=state_code,
            pc_name=pc_name,
            pc_no=pc_no,
            total_electors=bucket["total_electors"],
            total_votes_polled=bucket["total_votes_polled"],
            valid_votes=bucket["valid_votes"],
            candidates=tuple(bucket["candidates"]),
        ))
    return results
