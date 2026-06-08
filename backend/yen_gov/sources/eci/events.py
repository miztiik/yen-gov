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


# (state_code, year) -> EventInfo. Populated for every event the ingest
# pipeline supports. has_partywise=True only for events whose
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

    # Telangana statewise AE panel backfill. The 2014 rows are already scoped
    # to the post-formation Telangana token; undivided Andhra rows stay out of
    # this current-state slice.
    ("S29", 2014): EventInfo("AcGenApr2014", False),  # Telangana
    ("S29", 2018): EventInfo("AcGenDec2018", False),  # Telangana

    # Current Andhra Pradesh statewise AE panel backfill. Only post-split rows
    # are eligible here; pre-2014 undivided Andhra Pradesh stays deferred.
    ("S01", 2014): EventInfo("AcGenMay2014", False),  # Andhra Pradesh

    # Chhattisgarh statewise AE panel backfill. 2008/2013/2018 are November
    # polls even though the panel's month column records December counting.
    ("S26", 2003): EventInfo("AcGenDec2003", False),  # Chhattisgarh
    ("S26", 2008): EventInfo("AcGenNov2008", False),  # Chhattisgarh
    ("S26", 2013): EventInfo("AcGenNov2013", False),  # Chhattisgarh
    ("S26", 2018): EventInfo("AcGenNov2018", False),  # Chhattisgarh

    # Jharkhand statewise AE panel backfill. 2019 stays on the existing
    # Section-10 source; this slice writes 2005/2009/2014 only.
    ("S27", 2005): EventInfo("AcGenFeb2005", False),  # Jharkhand
    ("S27", 2009): EventInfo("AcGenDec2009", False),  # Jharkhand
    ("S27", 2014): EventInfo("AcGenDec2014", False),  # Jharkhand

    # Uttarakhand statewise AE panel backfill. 2017/2022 stay on existing
    # Section-10 sources; this slice writes 2002/2007/2012 only.
    ("S28", 2002): EventInfo("AcGenFeb2002", False),  # Uttarakhand
    ("S28", 2007): EventInfo("AcGenFeb2007", False),  # Uttarakhand
    ("S28", 2012): EventInfo("AcGenJan2012", False),  # Uttarakhand

    # Manipur statewise AE panel backfill. 1974 stays deferred as pre-1977;
    # 2017/2022 stay on existing Section-10 sources.
    ("S14", 1980): EventInfo("AcGenJan1980", False),  # Manipur
    ("S14", 1984): EventInfo("AcGenDec1984", False),  # Manipur
    ("S14", 1990): EventInfo("AcGenFeb1990", False),  # Manipur
    ("S14", 1995): EventInfo("AcGenFeb1995", False),  # Manipur
    ("S14", 2000): EventInfo("AcGenFeb2000", False),  # Manipur
    ("S14", 2002): EventInfo("AcGenFeb2002", False),  # Manipur
    ("S14", 2007): EventInfo("AcGenFeb2007", False),  # Manipur
    ("S14", 2012): EventInfo("AcGenJan2012", False),  # Manipur

    # Mizoram statewise AE panel backfill. 2023 stays on the existing
    # Section-10 source; this slice writes 1978-2018.
    ("S16", 1978): EventInfo("AcGenMay1978", False),  # Mizoram
    ("S16", 1979): EventInfo("AcGenApr1979", False),  # Mizoram
    ("S16", 1984): EventInfo("AcGenApr1984", False),  # Mizoram
    ("S16", 1987): EventInfo("AcGenFeb1987", False),  # Mizoram
    ("S16", 1989): EventInfo("AcGenNov1989", False),  # Mizoram
    ("S16", 1993): EventInfo("AcGenNov1993", False),  # Mizoram
    ("S16", 1998): EventInfo("AcGenNov1998", False),  # Mizoram
    ("S16", 2003): EventInfo("AcGenNov2003", False),  # Mizoram
    ("S16", 2008): EventInfo("AcGenDec2008", False),  # Mizoram
    ("S16", 2013): EventInfo("AcGenNov2013", False),  # Mizoram
    ("S16", 2018): EventInfo("AcGenNov2018", False),  # Mizoram

    # Nagaland statewise AE panel backfill. 1974 stays deferred as pre-1977;
    # 2018/2023 stay on existing Section-10 sources.
    ("S17", 1977): EventInfo("AcGenNov1977", False),  # Nagaland
    ("S17", 1982): EventInfo("AcGenNov1982", False),  # Nagaland
    ("S17", 1987): EventInfo("AcGenNov1987", False),  # Nagaland
    ("S17", 1989): EventInfo("AcGenJan1989", False),  # Nagaland
    ("S17", 1993): EventInfo("AcGenFeb1993", False),  # Nagaland
    ("S17", 1998): EventInfo("AcGenFeb1998", False),  # Nagaland
    ("S17", 2003): EventInfo("AcGenFeb2003", False),  # Nagaland
    ("S17", 2008): EventInfo("AcGenMar2008", False),  # Nagaland
    ("S17", 2013): EventInfo("AcGenFeb2013", False),  # Nagaland

    # Delhi statewise AE panel backfill. 1977/1983 are Metropolitan Council
    # elections in the ECI panel; 2020/2025 stay on existing Section-10 rows.
    ("U05", 1977): EventInfo("AcGenOct1977", False),  # NCT of Delhi
    ("U05", 1983): EventInfo("AcGenMay1983", False),  # NCT of Delhi
    ("U05", 1993): EventInfo("AcGenNov1993", False),  # NCT of Delhi
    ("U05", 1998): EventInfo("AcGenNov1998", False),  # NCT of Delhi
    ("U05", 2003): EventInfo("AcGenDec2003", False),  # NCT of Delhi
    ("U05", 2008): EventInfo("AcGenNov2008", False),  # NCT of Delhi
    ("U05", 2013): EventInfo("AcGenDec2013", False),  # NCT of Delhi
    ("U05", 2015): EventInfo("AcGenFeb2015", False),  # NCT of Delhi

    # Haryana statewise AE panel backfill. 2019/2024 stay on existing rows;
    # this slice writes 1977-2014.
    ("S07", 1977): EventInfo("AcGenOct1977", False),  # Haryana
    ("S07", 1982): EventInfo("AcGenMay1982", False),  # Haryana
    ("S07", 1987): EventInfo("AcGenJun1987", False),  # Haryana
    ("S07", 1991): EventInfo("AcGenMay1991", False),  # Haryana
    ("S07", 1996): EventInfo("AcGenMay1996", False),  # Haryana
    ("S07", 2000): EventInfo("AcGenFeb2000", False),  # Haryana
    ("S07", 2005): EventInfo("AcGenFeb2005", False),  # Haryana
    ("S07", 2009): EventInfo("AcGenOct2009", False),  # Haryana
    ("S07", 2014): EventInfo("AcGenOct2014", False),  # Haryana

    # Kerala statewise AE panel backfill. 2016/2021/2026 stay on existing rows;
    # this slice writes 1977-2011.
    ("S11", 1977): EventInfo("AcGenMar1977", False),  # Kerala
    ("S11", 1980): EventInfo("AcGenJan1980", False),  # Kerala
    ("S11", 1982): EventInfo("AcGenMay1982", False),  # Kerala
    ("S11", 1987): EventInfo("AcGenMar1987", False),  # Kerala
    ("S11", 1991): EventInfo("AcGenJun1991", False),  # Kerala
    ("S11", 1996): EventInfo("AcGenApr1996", False),  # Kerala
    ("S11", 2001): EventInfo("AcGenMay2001", False),  # Kerala
    ("S11", 2006): EventInfo("AcGenMay2006", False),  # Kerala
    ("S11", 2011): EventInfo("AcGenApr2011", False),  # Kerala

    # Punjab statewise AE panel backfill. 2017/2022 stay on existing
    # Section-10 rows; this slice writes 1977-2012.
    ("S19", 1977): EventInfo("AcGenOct1977", False),  # Punjab
    ("S19", 1980): EventInfo("AcGenMay1980", False),  # Punjab
    ("S19", 1985): EventInfo("AcGenSep1985", False),  # Punjab
    ("S19", 1992): EventInfo("AcGenFeb1992", False),  # Punjab
    ("S19", 1997): EventInfo("AcGenFeb1997", False),  # Punjab
    ("S19", 2002): EventInfo("AcGenFeb2002", False),  # Punjab
    ("S19", 2007): EventInfo("AcGenJan2007", False),  # Punjab
    ("S19", 2012): EventInfo("AcGenJan2012", False),  # Punjab

    # Rajasthan statewise AE panel backfill. 2023 stays on existing
    # Section-10 rows; this slice writes 1977-2018.
    ("S20", 1977): EventInfo("AcGenJun1977", False),  # Rajasthan
    ("S20", 1980): EventInfo("AcGenMay1980", False),  # Rajasthan
    ("S20", 1985): EventInfo("AcGenMay1985", False),  # Rajasthan
    ("S20", 1990): EventInfo("AcGenFeb1990", False),  # Rajasthan
    ("S20", 1993): EventInfo("AcGenNov1993", False),  # Rajasthan
    ("S20", 1998): EventInfo("AcGenNov1998", False),  # Rajasthan
    ("S20", 2003): EventInfo("AcGenDec2003", False),  # Rajasthan
    ("S20", 2008): EventInfo("AcGenDec2008", False),  # Rajasthan
    ("S20", 2013): EventInfo("AcGenDec2013", False),  # Rajasthan
    ("S20", 2018): EventInfo("AcGenDec2018", False),  # Rajasthan

    # Karnataka statewise AE panel backfill. 2018/2023 stay on existing
    # Section-10 rows; this slice writes 1978-2013.
    ("S10", 1978): EventInfo("AcGenFeb1978", False),  # Karnataka
    ("S10", 1983): EventInfo("AcGenMay1983", False),  # Karnataka
    ("S10", 1985): EventInfo("AcGenMay1985", False),  # Karnataka
    ("S10", 1989): EventInfo("AcGenNov1989", False),  # Karnataka
    ("S10", 1994): EventInfo("AcGenDec1994", False),  # Karnataka
    ("S10", 1999): EventInfo("AcGenSep1999", False),  # Karnataka
    ("S10", 2004): EventInfo("AcGenApr2004", False),  # Karnataka
    ("S10", 2008): EventInfo("AcGenMay2008", False),  # Karnataka
    ("S10", 2013): EventInfo("AcGenMay2013", False),  # Karnataka

    # Assam statewise AE panel backfill. 2016/2021/2026 stay on existing
    # Section-10/live rows; this slice writes 1978-2011.
    ("S03", 1978): EventInfo("AcGenFeb1978", False),  # Assam
    ("S03", 1983): EventInfo("AcGenFeb1983", False),  # Assam
    ("S03", 1985): EventInfo("AcGenDec1985", False),  # Assam
    ("S03", 1991): EventInfo("AcGenJun1991", False),  # Assam
    ("S03", 1996): EventInfo("AcGenApr1996", False),  # Assam
    ("S03", 2001): EventInfo("AcGenMay2001", False),  # Assam
    ("S03", 2006): EventInfo("AcGenApr2006", False),  # Assam
    ("S03", 2011): EventInfo("AcGenApr2011", False),  # Assam

    # Odisha statewise AE panel backfill. 2024 stays on existing Section-10
    # rows; this slice writes 1974-2019. Early 1974/1977/1980 public pages
    # only expose year-level context, so their event ids retain the panel month.
    ("S18", 1974): EventInfo("AcGenFeb1974", False),  # Odisha
    ("S18", 1977): EventInfo("AcGenOct1977", False),  # Odisha
    ("S18", 1980): EventInfo("AcGenJun1980", False),  # Odisha
    ("S18", 1985): EventInfo("AcGenMar1985", False),  # Odisha
    ("S18", 1990): EventInfo("AcGenFeb1990", False),  # Odisha
    ("S18", 1995): EventInfo("AcGenMar1995", False),  # Odisha
    ("S18", 2000): EventInfo("AcGenFeb2000", False),  # Odisha
    ("S18", 2004): EventInfo("AcGenApr2004", False),  # Odisha
    ("S18", 2009): EventInfo("AcGenApr2009", False),  # Odisha
    ("S18", 2014): EventInfo("AcGenApr2014", False),  # Odisha
    ("S18", 2019): EventInfo("AcGenApr2019", False),  # Odisha

    # West Bengal statewise AE panel backfill. 2026 stays on existing live rows;
    # this slice writes 1977-2021. The 2021 event id follows the regular
    # Mar-Apr polling window even though two seats polled later in September.
    ("S25", 1977): EventInfo("AcGenJun1977", False),  # West Bengal
    ("S25", 1982): EventInfo("AcGenMay1982", False),  # West Bengal
    ("S25", 1987): EventInfo("AcGenApr1987", False),  # West Bengal
    ("S25", 1991): EventInfo("AcGenApr1991", False),  # West Bengal
    ("S25", 1996): EventInfo("AcGenMay1996", False),  # West Bengal
    ("S25", 2001): EventInfo("AcGenMay2001", False),  # West Bengal
    ("S25", 2006): EventInfo("AcGenMay2006", False),  # West Bengal
    ("S25", 2011): EventInfo("AcGenMay2011", False),  # West Bengal
    ("S25", 2016): EventInfo("AcGenMay2016", False),  # West Bengal
    ("S25", 2021): EventInfo("AcGenApr2021", False),  # West Bengal

    # Bihar statewise AE panel backfill. 2025 stays on the existing Section-10
    # source; this slice writes 1977-2020. Bihar 2005 has two elections in one
    # year and is registered in EVENTS_BY_MONTH below instead of EVENTS.
    ("S04", 1977): EventInfo("AcGenOct1977", False),  # Bihar
    ("S04", 1980): EventInfo("AcGenMay1980", False),  # Bihar
    ("S04", 1985): EventInfo("AcGenMar1985", False),  # Bihar
    ("S04", 1990): EventInfo("AcGenFeb1990", False),  # Bihar
    ("S04", 1995): EventInfo("AcGenMar1995", False),  # Bihar
    ("S04", 2000): EventInfo("AcGenFeb2000", False),  # Bihar
    ("S04", 2010): EventInfo("AcGenNov2010", False),  # Bihar
    ("S04", 2015): EventInfo("AcGenNov2015", False),  # Bihar

    # Madhya Pradesh statewise AE panel backfill. Existing 2023 Section-10
    # slice remains the authority; this sequence fills 1977-2018.
    ("S12", 1977): EventInfo("AcGenOct1977", False),  # Madhya Pradesh
    ("S12", 1980): EventInfo("AcGenMay1980", False),  # Madhya Pradesh
    ("S12", 1985): EventInfo("AcGenFeb1985", False),  # Madhya Pradesh
    ("S12", 1990): EventInfo("AcGenFeb1990", False),  # Madhya Pradesh
    ("S12", 1993): EventInfo("AcGenNov1993", False),  # Madhya Pradesh
    ("S12", 1998): EventInfo("AcGenNov1998", False),  # Madhya Pradesh
    ("S12", 2003): EventInfo("AcGenNov2003", False),  # Madhya Pradesh
    ("S12", 2008): EventInfo("AcGenNov2008", False),  # Madhya Pradesh
    ("S12", 2013): EventInfo("AcGenNov2013", False),  # Madhya Pradesh
    ("S12", 2018): EventInfo("AcGenNov2018", False),  # Madhya Pradesh

    # Uttar Pradesh statewise AE panel backfill. Existing 2017/2022 Section-10
    # slices remain the authority; this sequence fills 1974-2012.
    ("S24", 1974): EventInfo("AcGenFeb1974", False),  # Uttar Pradesh
    ("S24", 1977): EventInfo("AcGenJun1977", False),  # Uttar Pradesh
    ("S24", 1980): EventInfo("AcGenMay1980", False),  # Uttar Pradesh
    ("S24", 1985): EventInfo("AcGenFeb1985", False),  # Uttar Pradesh
    ("S24", 1989): EventInfo("AcGenNov1989", False),  # Uttar Pradesh
    ("S24", 1991): EventInfo("AcGenMay1991", False),  # Uttar Pradesh
    ("S24", 1993): EventInfo("AcGenNov1993", False),  # Uttar Pradesh
    ("S24", 1996): EventInfo("AcGenSep1996", False),  # Uttar Pradesh
    ("S24", 2002): EventInfo("AcGenFeb2002", False),  # Uttar Pradesh
    ("S24", 2007): EventInfo("AcGenApr2007", False),  # Uttar Pradesh
    ("S24", 2012): EventInfo("AcGenFeb2012", False),  # Uttar Pradesh

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

    # Goa historical AE panel backfill (ECI Statistical Report
    # transcriptions). Polling months use the public ECI/Wikipedia dates;
    # the panel month column can carry the result/reporting month.
    ("S05", 1989): EventInfo("AcGenNov1989", False),  # Goa
    ("S05", 1994): EventInfo("AcGenNov1994", False),  # Goa
    ("S05", 1999): EventInfo("AcGenJun1999", False),  # Goa
    ("S05", 2002): EventInfo("AcGenMay2002", False),  # Goa
    ("S05", 2007): EventInfo("AcGenJun2007", False),  # Goa
    ("S05", 2012): EventInfo("AcGenMar2012", False),  # Goa

    # Himachal Pradesh historical AE panel backfill (ECI Statistical Report
    # transcriptions). Event ids use the polling month when known; for 1977
    # and 1985 the panel month is retained because the public page only gives
    # year-level date context.
    ("S08", 1977): EventInfo("AcGenOct1977", False),  # Himachal Pradesh
    ("S08", 1982): EventInfo("AcGenMay1982", False),  # Himachal Pradesh
    ("S08", 1985): EventInfo("AcGenMay1985", False),  # Himachal Pradesh
    ("S08", 1990): EventInfo("AcGenFeb1990", False),  # Himachal Pradesh
    ("S08", 1993): EventInfo("AcGenSep1993", False),  # Himachal Pradesh
    ("S08", 1998): EventInfo("AcGenFeb1998", False),  # Himachal Pradesh
    ("S08", 2003): EventInfo("AcGenFeb2003", False),  # Himachal Pradesh
    ("S08", 2007): EventInfo("AcGenNov2007", False),  # Himachal Pradesh
    ("S08", 2012): EventInfo("AcGenNov2012", False),  # Himachal Pradesh

    # 2026-05-17 ephemeral backfill — XLSX dumps held in datasets/ephemeral/
    # for hand-ingest via `eci-statreport-emit-local`. Polling months sourced
    # from Wikipedia/ECI archives; documented in
    # TODO/20260517-ephemeral-ae-ingest.md.

    # May-2016 cohort (polled 16 May 2016, shared with Kerala already pinned).
    ("U07", 2016): EventInfo("AcGenMay2016", False),  # Puducherry
    ("S22", 2016): EventInfo("AcGenMay2016", False),  # Tamil Nadu

    # Tamil Nadu historical AE panel backfill (ECI Statistical Report
    # transcriptions). The frontend catalogue exposes the full sequence;
    # keeping it here preserves the backend/frontend event contract.
    ("S22", 1971): EventInfo("AcGenMar1971", False),  # Tamil Nadu
    ("S22", 1977): EventInfo("AcGenOct1977", False),  # Tamil Nadu
    ("S22", 1980): EventInfo("AcGenJun1980", False),  # Tamil Nadu
    ("S22", 1984): EventInfo("AcGenDec1984", False),  # Tamil Nadu
    ("S22", 1989): EventInfo("AcGenJan1989", False),  # Tamil Nadu
    ("S22", 1991): EventInfo("AcGenFeb1991", False),  # Tamil Nadu
    ("S22", 1996): EventInfo("AcGenFeb1996", False),  # Tamil Nadu
    ("S22", 2001): EventInfo("AcGenMay2001", False),  # Tamil Nadu
    ("S22", 2006): EventInfo("AcGenMay2006", False),  # Tamil Nadu
    ("S22", 2011): EventInfo("AcGenMay2011", False),  # Tamil Nadu

    # Feb-2017 cohort (Punjab/Goa polled 4 Feb; UK 15 Feb; UP 7-phase Feb-Mar).
    ("S19", 2017): EventInfo("AcGenFeb2017", False),  # Punjab
    ("S28", 2017): EventInfo("AcGenFeb2017", False),  # Uttarakhand
    ("S24", 2017): EventInfo("AcGenFeb2017", False),  # Uttar Pradesh

    # Mar-2017 Manipur (polled 4 & 8 Mar 2017).
    ("S14", 2017): EventInfo("AcGenMar2017", False),  # Manipur

    # Gujarat historical AE panel backfill (ECI Statistical Report
    # transcriptions). Polling month comes from the panel month column.
    ("S06", 1962): EventInfo("AcGenFeb1962", False),  # Gujarat
    ("S06", 1967): EventInfo("AcGenFeb1967", False),  # Gujarat
    ("S06", 1972): EventInfo("AcGenMar1972", False),  # Gujarat
    ("S06", 1975): EventInfo("AcGenJun1975", False),  # Gujarat
    ("S06", 1980): EventInfo("AcGenMay1980", False),  # Gujarat
    ("S06", 1985): EventInfo("AcGenMay1985", False),  # Gujarat
    ("S06", 1990): EventInfo("AcGenFeb1990", False),  # Gujarat
    ("S06", 1995): EventInfo("AcGenFeb1995", False),  # Gujarat
    ("S06", 1998): EventInfo("AcGenMar1998", False),  # Gujarat
    ("S06", 2002): EventInfo("AcGenDec2002", False),  # Gujarat
    ("S06", 2007): EventInfo("AcGenDec2007", False),  # Gujarat
    ("S06", 2012): EventInfo("AcGenDec2012", False),  # Gujarat

    # Dec-2017 Gujarat (polled 9 & 14 Dec 2017).
    ("S06", 2017): EventInfo("AcGenDec2017", False),  # Gujarat

    # Maharashtra historical AE panel backfill (ECI Statistical Report
    # transcriptions). Polling month comes from the panel month column.
    ("S13", 1962): EventInfo("AcGenFeb1962", False),  # Maharashtra
    ("S13", 1967): EventInfo("AcGenFeb1967", False),  # Maharashtra
    ("S13", 1972): EventInfo("AcGenMar1972", False),  # Maharashtra
    ("S13", 1978): EventInfo("AcGenFeb1978", False),  # Maharashtra
    ("S13", 1980): EventInfo("AcGenMay1980", False),  # Maharashtra
    ("S13", 1985): EventInfo("AcGenFeb1985", False),  # Maharashtra
    ("S13", 1990): EventInfo("AcGenFeb1990", False),  # Maharashtra
    ("S13", 1995): EventInfo("AcGenMar1995", False),  # Maharashtra
    ("S13", 1999): EventInfo("AcGenOct1999", False),  # Maharashtra
    ("S13", 2004): EventInfo("AcGenOct2004", False),  # Maharashtra
    ("S13", 2009): EventInfo("AcGenOct2009", False),  # Maharashtra
    ("S13", 2014): EventInfo("AcGenOct2014", False),  # Maharashtra
    ("S13", 2019): EventInfo("AcGenOct2019", False),  # Maharashtra

    # Feb-2018 cohort: Tripura, Meghalaya, Nagaland.
    # NULL-cell handling added in statistical_report_detailed._to_int /
    # _to_float / _to_float_or_none: pre-2019 Section-10 XLSX use the
    # literal string "NULL" in vote columns for ACs where no poll was held
    # (Williamnagar Meghalaya AC 43 — countermand; Northern Angami-II
    # Nagaland AC 11 — Neiphiu Rio unopposed). Coerced to 0 / None
    # consistently with other missing tokens.
    ("S23", 2018): EventInfo("AcGenFeb2018", False),  # Tripura
    ("S15", 2018): EventInfo("AcGenFeb2018", False),  # Meghalaya
    ("S17", 2018): EventInfo("AcGenFeb2018", False),  # Nagaland

    # Nov-2018 Mizoram source as supplied was a mislabelled duplicate of the
    # Nagaland XLSX (60 ACs vs Mizoram's actual 40); parked pending a
    # correctly-sourced Mizoram-2018 Statistical Report XLSX.

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

    # Tripura historical AE panel backfill (ECI Statistical Report
    # transcriptions). Existing 2018/2023 Section-10 slices remain the
    # authority; this sequence fills only missing 1977-2013 events.
    ("S23", 1977): EventInfo("AcGenDec1977", False),  # Tripura
    ("S23", 1983): EventInfo("AcGenMay1983", False),  # Tripura
    ("S23", 1988): EventInfo("AcGenFeb1988", False),  # Tripura
    ("S23", 1993): EventInfo("AcGenFeb1993", False),  # Tripura
    ("S23", 1998): EventInfo("AcGenFeb1998", False),  # Tripura
    ("S23", 2003): EventInfo("AcGenFeb2003", False),  # Tripura
    ("S23", 2008): EventInfo("AcGenFeb2008", False),  # Tripura
    ("S23", 2013): EventInfo("AcGenFeb2013", False),  # Tripura

    # Meghalaya historical AE panel backfill (ECI Statistical Report
    # transcriptions). Existing 2018/2023 Section-10 slices remain the
    # authority; this sequence fills only missing 1978-2013 events.
    ("S15", 1978): EventInfo("AcGenFeb1978", False),  # Meghalaya
    ("S15", 1983): EventInfo("AcGenFeb1983", False),  # Meghalaya
    ("S15", 1988): EventInfo("AcGenFeb1988", False),  # Meghalaya
    ("S15", 1993): EventInfo("AcGenFeb1993", False),  # Meghalaya
    ("S15", 1998): EventInfo("AcGenFeb1998", False),  # Meghalaya
    ("S15", 2003): EventInfo("AcGenFeb2003", False),  # Meghalaya
    ("S15", 2008): EventInfo("AcGenMar2008", False),  # Meghalaya
    ("S15", 2013): EventInfo("AcGenFeb2013", False),  # Meghalaya

    # Puducherry historical AE panel backfill (ECI Statistical Report
    # transcriptions). Pre-1977 rows remain deferred; existing 2016/2021
    # Section-10 slices remain the authority.
    ("U07", 1977): EventInfo("AcGenOct1977", False),  # Puducherry
    ("U07", 1980): EventInfo("AcGenMar1980", False),  # Puducherry
    ("U07", 1985): EventInfo("AcGenMay1985", False),  # Puducherry
    ("U07", 1990): EventInfo("AcGenFeb1990", False),  # Puducherry
    ("U07", 1991): EventInfo("AcGenJun1991", False),  # Puducherry
    ("U07", 1996): EventInfo("AcGenApr1996", False),  # Puducherry
    ("U07", 2001): EventInfo("AcGenMay2001", False),  # Puducherry
    ("U07", 2006): EventInfo("AcGenMay2006", False),  # Puducherry
    ("U07", 2011): EventInfo("AcGenApr2011", False),  # Puducherry

    # Sikkim historical AE panel backfill (ECI Statistical Report
    # transcriptions). Existing 2024 Section-10 slice remains the authority.
    ("S21", 1979): EventInfo("AcGenOct1979", False),  # Sikkim
    ("S21", 1985): EventInfo("AcGenMay1985", False),  # Sikkim
    ("S21", 1989): EventInfo("AcGenNov1989", False),  # Sikkim
    ("S21", 1994): EventInfo("AcGenNov1994", False),  # Sikkim
    ("S21", 1999): EventInfo("AcGenOct1999", False),  # Sikkim
    ("S21", 2004): EventInfo("AcGenMay2004", False),  # Sikkim
    ("S21", 2009): EventInfo("AcGenApr2009", False),  # Sikkim
    ("S21", 2014): EventInfo("AcGenApr2014", False),  # Sikkim
    ("S21", 2019): EventInfo("AcGenApr2019", False),  # Sikkim

    # Arunachal Pradesh historical AE panel backfill (ECI Statistical Report
    # transcriptions). Existing 2024 Section-10 slice remains the authority.
    ("S02", 1978): EventInfo("AcGenFeb1978", False),  # Arunachal Pradesh
    ("S02", 1980): EventInfo("AcGenJan1980", False),  # Arunachal Pradesh
    ("S02", 1984): EventInfo("AcGenDec1984", False),  # Arunachal Pradesh
    ("S02", 1990): EventInfo("AcGenMar1990", False),  # Arunachal Pradesh
    ("S02", 1995): EventInfo("AcGenMar1995", False),  # Arunachal Pradesh
    ("S02", 1999): EventInfo("AcGenOct1999", False),  # Arunachal Pradesh
    ("S02", 2004): EventInfo("AcGenOct2004", False),  # Arunachal Pradesh
    ("S02", 2009): EventInfo("AcGenOct2009", False),  # Arunachal Pradesh
    ("S02", 2014): EventInfo("AcGenApr2014", False),  # Arunachal Pradesh
    ("S02", 2019): EventInfo("AcGenApr2019", False),  # Arunachal Pradesh

    # Nov-2023 Rajasthan (joins existing Nov-2023 four-state cohort).
    ("S20", 2023): EventInfo("AcGenNov2023", False),  # Rajasthan
}


# Rare duplicate same-state/same-year elections need month to disambiguate.
# Bihar 2005 had a February election that produced no government, then a
# fresh October-November election later the same year. Keep ordinary callers
# on EVENTS; month-aware callers such as the AE panel adapter pass month.
EVENTS_BY_MONTH: dict[tuple[str, int, int], EventInfo] = {
    ("S04", 2005, 2): EventInfo("AcGenFeb2005", False),  # Bihar
    ("S04", 2005, 11): EventInfo("AcGenNov2005", False),  # Bihar
}


def event_info_for(state_code: str, year: int, month: int | None = None) -> EventInfo:
    """Return EventInfo for (state, year), or raise a directive KeyError.

    Adding a new (state, year) is a code change because the polling month
    that drives event_id naming + the has_partywise observation both
    require human judgement.
    """
    if month is not None:
        by_month = EVENTS_BY_MONTH.get((state_code, year, month))
        if by_month is not None:
            return by_month
    try:
        return EVENTS[(state_code, year)]
    except KeyError as exc:
        coordinate = (
            f"({state_code!r}, {year}, month={month})"
            if month is not None
            else f"({state_code!r}, {year})"
        )
        raise KeyError(
            f"no event registered for {coordinate}; "
            f"extend EVENTS in backend/yen_gov/sources/eci/events.py "
            f"with the polling month + partywise availability. Use EVENTS_BY_MONTH "
            f"when one state has multiple elections in the same year."
        ) from exc


def event_id_for(state_code: str, year: int, month: int | None = None) -> str:
    """Convenience accessor for just the on-disk event_id."""
    return event_info_for(state_code, year, month).event_id


# Back-compat for code reading the old flat shape (admin/eci_recon.py).
EVENT_ID_FOR: dict[tuple[str, int], str] = {
    k: v.event_id for k, v in EVENTS.items()
}
