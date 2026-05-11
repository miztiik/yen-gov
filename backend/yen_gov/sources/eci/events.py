"""Pinned (state, year) -> event id map for ECI assembly elections.

Mirrors `categories.py` (which pins category_ids). Where `categories.py`
answers *"which Statistical Report is this election?"*, this answers
*"what on-disk event id groups its artifacts under
``datasets/elections/<event_id>/<state>/``?"*.

Keeping the two registries separate lets future events add a Statistical
Report pin **before** they have a parsable per-AC pipeline (raw download
works without an event id; emit needs one).

Per IA-reset doctrine ([TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md])
the event id is **not** citizen-visible; it lives in data files only. The
catalogue maps event id → display string.

Initially populated only with the May-2026 cohort, which is the slice the
current emit pipeline can handle (it cross-fetches a partywise URL from
``results.eci.gov.in/Result<event>/...``). Once N2 ships (Section 4 → no
results-portal dependency), every (state, year) pin in
``config/eci-pins.json`` should also exist here.
"""

from __future__ import annotations

# (state_code, year) -> on-disk event id used for
# datasets/elections/<event>/<state>/ paths AND for the partywise URL
# under results.eci.gov.in/Result<event>/.
EVENT_ID_FOR: dict[tuple[str, int], str] = {
    # May-2026 assembly cohort — five states polled together.
    ("S03", 2026): "AcGenMay2026",  # Assam
    ("S11", 2026): "AcGenMay2026",  # Kerala
    ("U07", 2026): "AcGenMay2026",  # Puducherry
    ("S22", 2026): "AcGenMay2026",  # Tamil Nadu
    ("S25", 2026): "AcGenMay2026",  # West Bengal
}


def event_id_for(state_code: str, year: int) -> str:
    """Look up the event id for one (state, year).

    Raises KeyError with a directive message: extending this map is a
    code change because adding an event today still requires a matching
    ``results.eci.gov.in/Result<event>/`` URL family. After N2 lands
    (Section 4-only emit), the registry can move to JSON config.
    """
    try:
        return EVENT_ID_FOR[(state_code, year)]
    except KeyError as exc:
        raise KeyError(
            f"no event id registered for ({state_code!r}, {year}); "
            f"emit pipeline cannot run without one. "
            f"See TODO/ECI-MULTI-STATE-INGEST-PLAN.md (N2)."
        ) from exc
