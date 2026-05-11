"""Pinned (state, year) -> event metadata for ECI assembly elections.

Mirrors `categories.py` (which pins the API's `category_id` per Statistical
Report). Where `categories.py` answers *"which Statistical Report is this
election?"*, this answers two related questions:

1. ``event_id`` — what on-disk grouping name should artifacts live under
   in ``datasets/elections/<event_id>/<state>/``? (Citizen-invisible per
   IA-reset doctrine; the catalogue maps this to a display string.)
2. ``has_partywise`` — does ECI's *live results* portal still serve the
   ``results.eci.gov.in/Result<event_id>/partywise...`` page for this
   event? Older cohorts (everything before May 2026) are archived without
   partywise HTML, so the emit pipeline has to skip the numeric-eci_code
   backfill, the winner reconciliation, and the parties.json artifact.

Convention for event_id when the official event has no live-results URL
family of its own: ``AcGen<MonYYYY>`` named after the **polling month** of
the cohort, matching the AcGenMay2026 precedent. Multiple states sharing
a polling month share an event_id (e.g. AcGenJun2024 spans S01/S02/S18/S21
even though those four no longer have a unified live-results page).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventInfo:
    """Per-(state, year) metadata for the emit pipeline."""

    event_id: str
    has_partywise: bool


# (state_code, year) -> EventInfo. Populated for every pin in
# config/eci-pins.json so the admin GUI's "Full ingest" button can run
# on all of them. has_partywise=True only for events whose
# results.eci.gov.in/Result<event_id>/ pages still exist live.
EVENTS: dict[tuple[str, int], EventInfo] = {
    # May-2026 cohort — five states polled together. Live results portal
    # still serves Result<event_id>/partywise...htm for each.
    ("S03", 2026): EventInfo("AcGenMay2026", True),  # Assam
    ("S11", 2026): EventInfo("AcGenMay2026", True),  # Kerala
    ("U07", 2026): EventInfo("AcGenMay2026", True),  # Puducherry
    ("S22", 2026): EventInfo("AcGenMay2026", True),  # Tamil Nadu
    ("S25", 2026): EventInfo("AcGenMay2026", True),  # West Bengal

    # 2024-2025 cohort — Statistical Reports exist on the new ECI API but
    # the live-results portal pages have been retired. Emit runs in
    # "section10-only" mode: per-AC results + summary, no parties.json.
    ("S01", 2024): EventInfo("AcGenJun2024", False),  # Andhra Pradesh (with LS-2024)
    ("S02", 2024): EventInfo("AcGenJun2024", False),  # Arunachal Pradesh
    ("S18", 2024): EventInfo("AcGenJun2024", False),  # Odisha
    ("S21", 2024): EventInfo("AcGenJun2024", False),  # Sikkim
    ("S07", 2024): EventInfo("AcGenOct2024", False),  # Haryana
    ("U08", 2024): EventInfo("AcGenOct2024", False),  # J&K
    ("S13", 2024): EventInfo("AcGenNov2024", False),  # Maharashtra
    ("S27", 2024): EventInfo("AcGenNov2024", False),  # Jharkhand
    ("U05", 2025): EventInfo("AcGenFeb2025", False),  # NCT of Delhi
    ("S04", 2025): EventInfo("AcGenNov2025", False),  # Bihar (Oct-Nov)
}


def event_info_for(state_code: str, year: int) -> EventInfo:
    """Return EventInfo for (state, year), or raise a directive KeyError.

    Adding a new (state, year) is a code change because the polling month
    that drives event_id naming + the has_partywise observation both
    require human judgement.
    """
    try:
        return EVENTS[(state_code, year)]
    except KeyError as exc:
        raise KeyError(
            f"no event registered for ({state_code!r}, {year}); "
            f"extend EVENTS in backend/yen_gov/sources/eci/events.py "
            f"with the polling month + partywise availability."
        ) from exc


def event_id_for(state_code: str, year: int) -> str:
    """Convenience accessor for just the on-disk event_id."""
    return event_info_for(state_code, year).event_id


# Back-compat for code reading the old flat shape (admin/eci_recon.py).
EVENT_ID_FOR: dict[tuple[str, int], str] = {
    k: v.event_id for k, v in EVENTS.items()
}
