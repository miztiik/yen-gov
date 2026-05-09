"""URL conventions for results.eci.gov.in pages.

Centralising URL building here means the rest of the adapter never hardcodes
host/path templates. If ECI changes their convention next election, exactly
one file changes.

Observed conventions for AcGenMay2026 (per probe on 2026-05-08):

  - Event index: /Result<EventId>/index.htm
  - Partywise:   /Result<EventId>/partywiseresult-<StateCode>.htm
  - Constituency:/Result<EventId>/Constituencywise<StateCode><Number>.htm
                  e.g. ConstituencywiseS22167.htm — note no separator between
                  the state code and the integer constituency number.

EventId is the slug ECI assigns (e.g. AcGenMay2026 for "Assembly General
May 2026"). It is opaque to us; pipeline config supplies it.

These URLs are only valid while ECI is hosting the event. Once the event is
archived ECI sometimes moves it (e.g. to results.eci.gov.in/AcResult... or
behind a year-prefixed path). New events get new URL builders here.
"""

from __future__ import annotations

import re

_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9]+$")
_STATE_CODE_RE = re.compile(r"^[SU]\d{2}$")

ECI_RESULTS_BASE = "https://results.eci.gov.in"


def _validate_event(event_id: str) -> None:
    if not _EVENT_ID_RE.fullmatch(event_id):
        raise ValueError(f"event_id must be alphanumeric, got {event_id!r}")


def _validate_state(state_code: str) -> None:
    if not _STATE_CODE_RE.fullmatch(state_code):
        raise ValueError(f"state_code must match ^[SU]\\d{{2}}$, got {state_code!r}")


def event_index_url(event_id: str) -> str:
    _validate_event(event_id)
    return f"{ECI_RESULTS_BASE}/Result{event_id}/index.htm"


def partywise_state_url(event_id: str, state_code: str) -> str:
    """Party-level summary table for one state in one event."""
    _validate_event(event_id)
    _validate_state(state_code)
    return f"{ECI_RESULTS_BASE}/Result{event_id}/partywiseresult-{state_code}.htm"


def constituencywise_url(event_id: str, state_code: str, eci_no: int) -> str:
    """Per-constituency result page (candidates + NOTA + totals)."""
    _validate_event(event_id)
    _validate_state(state_code)
    if eci_no < 1:
        raise ValueError(f"eci_no must be >= 1, got {eci_no}")
    return f"{ECI_RESULTS_BASE}/Result{event_id}/Constituencywise{state_code}{eci_no}.htm"
