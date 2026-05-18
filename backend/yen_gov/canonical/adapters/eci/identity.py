"""Election-entity identity helpers (canonical-store.md §3a).

All entity_id construction lives here so the rules are testable in isolation
and the rest of the adapter does not hand-format identifier strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PERIOD_RE = re.compile(
    r"^(?P<body>AcGen|LsGen|LsBye|AcBye)"
    r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"(?P<year>\d{4})$"
)

_MONTH_NUM = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


@dataclass(frozen=True)
class Period:
    """Decoded ECI event id.

    period_label = the original string (e.g. "AcGenMay2026") — citizen-facing.
    year = calendar year the contest was held (integer, OWID axis).
    period_seq = month number (1..12). Lets multiple events in the same year
                 sort deterministically without needing a separate column.
    """

    period_label: str
    year: int
    period_seq: int


def parse_period_label(event_id: str) -> Period:
    """Decode an ECI event id like ``AcGenMay2026`` into ``(year, period_seq)``.

    Raises ``ValueError`` for unparseable ids — callers MUST validate at the
    fetch boundary, not silently coerce.
    """
    m = _PERIOD_RE.match(event_id)
    if not m:
        raise ValueError(f"Unparseable ECI event id: {event_id!r}")
    return Period(
        period_label=event_id,
        year=int(m["year"]),
        period_seq=_MONTH_NUM[m["mon"]],
    )


def ac_entity_id(state_code: str, delim_year: int, eci_no: int) -> str:
    """Build an AC entity_id per §3a: ``IN-<state>-AC-<delim_year>-<eci_no>``.

    Examples:
        >>> ac_entity_id("S22", 2008, 167)
        'IN-S22-AC-2008-167'
    """
    if not re.fullmatch(r"[SU]\d{2}", state_code):
        raise ValueError(f"Invalid ECI state code: {state_code!r}")
    if delim_year < 1850 or delim_year > 2100:
        raise ValueError(f"Implausible delimitation year: {delim_year}")
    if eci_no < 1:
        raise ValueError(f"AC ECI number must be positive: {eci_no}")
    return f"IN-{state_code}-AC-{delim_year}-{eci_no}"


def candidate_entity_id(ac_id: str, period_label: str, ballot_serial: int) -> str:
    """Build a per-contest candidate entity_id per §3a.

    Examples:
        >>> candidate_entity_id("IN-S22-AC-2008-167", "AcGenMay2026", 3)
        'IN-S22-AC-2008-167-AcGenMay2026-C03'
    """
    if ballot_serial < 1 or ballot_serial > 99:
        # 99 is a generous ceiling — ACs typically have <40 candidates including
        # NOTA; ballot serials beyond two digits never appear in practice.
        raise ValueError(f"Implausible ballot serial: {ballot_serial}")
    return f"{ac_id}-{period_label}-C{ballot_serial:02d}"


def state_rollup_entity_id(state_code: str, period_label: str) -> str:
    """State-level rollup entity_id per §3a.

    Examples:
        >>> state_rollup_entity_id("S22", "AcGenMay2026")
        'IN-S22-AcGenMay2026'
    """
    if not re.fullmatch(r"[SU]\d{2}", state_code):
        raise ValueError(f"Invalid ECI state code: {state_code!r}")
    return f"IN-{state_code}-{period_label}"


def party_rollup_entity_id(state_code: str, period_label: str, party_slug: str) -> str:
    """Party-per-state-per-election rollup entity_id per §3a.

    ``party_slug`` is the short slug WITHOUT the ``parties.IN.`` prefix —
    e.g. ``"DMK"`` for ``parties.IN.DMK``.

    Examples:
        >>> party_rollup_entity_id("S22", "AcGenMay2026", "DMK")
        'IN-S22-AcGenMay2026-PARTY-DMK'
    """
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", party_slug):
        raise ValueError(f"Invalid party slug: {party_slug!r}")
    state = state_rollup_entity_id(state_code, period_label)
    return f"{state}-PARTY-{party_slug}"
