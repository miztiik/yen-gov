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

    # Nov-2023 cohort: four states polled together (counting 2023-12-03).
    # Polling dates: Mizoram + Chhattisgarh-phase-1 (2023-11-07),
    # Chhattisgarh-phase-2 + MP (2023-11-17), Telangana (2023-11-30).
    # Sources: legacy /<state>-legislative-election-2023-statistical-report
    # landing pages routed through static_catalog.py (no /api). Predates
    # the live-results portal redesign so has_partywise=False.
    ("S12", 2023): EventInfo("AcGenNov2023", False),  # Madhya Pradesh
    ("S26", 2023): EventInfo("AcGenNov2023", False),  # Chhattisgarh
    ("S16", 2023): EventInfo("AcGenNov2023", False),  # Mizoram
    ("S29", 2023): EventInfo("AcGenNov2023", False),  # Telangana

    # Historical hand-imports (2016-2023) from old.eci.gov.in Section 10
    # XLSX dumps. No live-results portal; no Statistical Report API.
    # Polling-month event_ids researched against Wikipedia/ECI archives.
    ("S03", 2016): EventInfo("AcGenApr2016", False),  # Assam
    ("S11", 2016): EventInfo("AcGenMay2016", False),  # Kerala
    ("S05", 2017): EventInfo("AcGenFeb2017", False),  # Goa
    ("S08", 2017): EventInfo("AcGenNov2017", False),  # Himachal Pradesh
    ("S10", 2018): EventInfo("AcGenMay2018", False),  # Karnataka
    ("S01", 2019): EventInfo("AcGenApr2019", False),  # Andhra Pradesh (with LS-2019)
    ("S07", 2019): EventInfo("AcGenOct2019", False),  # Haryana
    ("S27", 2019): EventInfo("AcGenDec2019", False),  # Jharkhand
    ("S04", 2020): EventInfo("AcGenNov2020", False),  # Bihar
    ("U05", 2020): EventInfo("AcGenFeb2020", False),  # NCT of Delhi
    ("S03", 2021): EventInfo("AcGenApr2021", False),  # Assam (shared with Kerala-2021)
    ("S11", 2021): EventInfo("AcGenApr2021", False),  # Kerala
    ("S05", 2022): EventInfo("AcGenFeb2022", False),  # Goa
    ("S08", 2022): EventInfo("AcGenNov2022", False),  # Himachal Pradesh
    ("S10", 2023): EventInfo("AcGenMay2023", False),  # Karnataka

    # 2026-05-17 ephemeral backfill — XLSX dumps held in datasets/ephemeral/
    # for hand-ingest via `eci-statreport-emit-local`. Polling months sourced
    # from Wikipedia/ECI archives; documented in
    # TODO/20260517-ephemeral-ae-ingest.md.

    # May-2016 cohort (polled 16 May 2016, shared with Kerala already pinned).
    ("U07", 2016): EventInfo("AcGenMay2016", False),  # Puducherry
    ("S22", 2016): EventInfo("AcGenMay2016", False),  # Tamil Nadu

    # Feb-2017 cohort (Punjab/Goa polled 4 Feb; UK 15 Feb; UP 7-phase Feb-Mar).
    ("S19", 2017): EventInfo("AcGenFeb2017", False),  # Punjab
    ("S28", 2017): EventInfo("AcGenFeb2017", False),  # Uttarakhand
    ("S24", 2017): EventInfo("AcGenFeb2017", False),  # Uttar Pradesh

    # Mar-2017 Manipur (polled 4 & 8 Mar 2017).
    ("S14", 2017): EventInfo("AcGenMar2017", False),  # Manipur

    # Dec-2017 Gujarat (polled 9 & 14 Dec 2017).
    ("S06", 2017): EventInfo("AcGenDec2017", False),  # Gujarat

    # Feb-2018 cohort: Tripura ingested; Meghalaya & Nagaland source XLSX
    # parsed as Layout-C but contain literal "NULL" cells in numeric columns
    # — parked under datasets/ephemeral/parked/ pending parser hardening.
    # Pin only what we can actually ingest; remaining pins land with the
    # parser fix (re-add ("S15", 2018) and ("S17", 2018) then).
    ("S23", 2018): EventInfo("AcGenFeb2018", False),  # Tripura

    # Nov-2018 Mizoram source is also NULL-cell-blocked — parked. Pin lands
    # with the parser fix.

    # Apr-2019 cohort: AP (S01) ingested. Odisha (S18) and Sikkim (S21) ship
    # as legacy BIFF .xls (OLE2 magic D0CF11E0) which openpyxl rejects;
    # parked pending xlrd<2.0 or LibreOffice conversion path. Pin lands then.

    # Oct-2019 Maharashtra (S13) shares the BIFF .xls issue (parked). Haryana
    # (S07) already pinned and ingested.

    # Apr-2021 cohort (shared with Assam/Kerala already pinned).
    ("U07", 2021): EventInfo("AcGenApr2021", False),  # Puducherry
    ("S22", 2021): EventInfo("AcGenApr2021", False),  # Tamil Nadu

    # Feb-2022 cohort (shared with Goa already pinned; UK 14 Feb; UP 7-phase).
    ("S19", 2022): EventInfo("AcGenFeb2022", False),  # Punjab
    ("S28", 2022): EventInfo("AcGenFeb2022", False),  # Uttarakhand
    ("S24", 2022): EventInfo("AcGenFeb2022", False),  # Uttar Pradesh

    # Mar-2022 Manipur (polled 28 Feb & 5 Mar 2022).
    ("S14", 2022): EventInfo("AcGenMar2022", False),  # Manipur

    # Dec-2022 Gujarat (polled 1 & 5 Dec 2022).
    ("S06", 2022): EventInfo("AcGenDec2022", False),  # Gujarat

    # Feb-2023 cohort: Tripura (16 Feb), Meghalaya & Nagaland (27 Feb).
    ("S23", 2023): EventInfo("AcGenFeb2023", False),  # Tripura
    ("S15", 2023): EventInfo("AcGenFeb2023", False),  # Meghalaya
    ("S17", 2023): EventInfo("AcGenFeb2023", False),  # Nagaland

    # Nov-2023 Rajasthan (joins existing Nov-2023 four-state cohort).
    ("S20", 2023): EventInfo("AcGenNov2023", False),  # Rajasthan
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
