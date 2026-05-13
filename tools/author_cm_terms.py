"""Author cm_terms.json for all 27 missing legislative jurisdictions.

Per Governance Strategist (chat 2026-05-13):
- 1990-01-01 cut as soft floor (state-formation date for newer states).
- Each PR spell its own term with notes citing the Article 356 invocation.
- Bifurcation states (S04/S27 2000, S12/S26 2000, S24/S28 2000, S01/S29 2014):
  pre-bifurcation terms appear in BOTH successor files with a notes flag.
- Verified ECI party codes used; everything else party_code: null with the
  party abbreviation+name in the term's notes (Holy Law #6: don't invent
  taxonomy — defer party_code resolution to a later parties.json pass).

Run from repo root: python tools/author_cm_terms.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO / "datasets" / "governments" / "in" / "states"
SCHEMA_URL = "https://yen-gov.github.io/schemas/state_government.schema.json"
FETCHED_AT = "2026-05-13T00:00:00Z"
WIKI_AUTH = "Wikipedia (CC BY-SA 4.0)"
ECI_AUTH = "Election Commission of India"

# Verified ECI numeric party codes (sampled from ingested datasets/elections/
# .../parties.json — see tools/bootstrap_constituencies_from_results.py for
# the upstream). Everything else stays null + notes per Holy Law #6.
INC = "742"
BJP = "369"
CPM = "547"
CPI = "544"
RJD = "1420"
TMC = "140"   # AITC / Trinamool — only valid for West Bengal use; not used here
AGP = "83"
IND = "743"


def term(start: str, end: str | None, regime: str, *, party_code=None,
         alliance=None, cm_name=None, notes: str | None = None,
         references: list | None = None) -> dict:
    t: dict = {"start": start, "end": end, "regime": regime,
               "party_code": party_code, "alliance": alliance,
               "cm_name": cm_name}
    if notes:
        t["notes"] = notes
    if references:
        t["references"] = references
    return t


def pr(start: str, end: str | None, reason: str, refs=None) -> dict:
    return term(start, end, "presidents_rule", notes=reason, references=refs)


def write(state: str, sources: list[dict], terms: list[dict]) -> Path:
    doc = {
        "$schema": SCHEMA_URL,
        "$schema_version": "1.0",
        "sources": sources,
        "state": state,
        "terms": terms,
    }
    out = OUT_ROOT / state / "cm_terms.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return out


def wiki_src(slug: str, name: str) -> dict:
    return {"url": f"https://en.wikipedia.org/wiki/{slug}",
            "fetched_at": FETCHED_AT, "name": name, "authority": WIKI_AUTH}


# Shared block: unified Andhra Pradesh CM terms 1990-01-01 → 2014-06-02.
# Appears in BOTH S01 (post-bifurcation AP) and S29 (Telangana) per
# Governance Strategist guidance.
AP_UNIFIED = [
    term("1989-12-03", "1990-12-17", "elected", party_code=INC, alliance=None,
         cm_name="Marri Chenna Reddy",
         notes="Unified Andhra Pradesh pre-bifurcation. INC. Replaced by N. Janardhan Reddy after intra-party leadership change."),
    term("1990-12-17", "1992-10-09", "elected", party_code=INC, alliance=None,
         cm_name="N. Janardhan Reddy",
         notes="Unified Andhra Pradesh pre-bifurcation. INC."),
    term("1992-10-09", "1994-12-12", "elected", party_code=INC, alliance=None,
         cm_name="Kotla Vijaya Bhaskara Reddy",
         notes="Unified Andhra Pradesh pre-bifurcation. INC. Lost the 1994 Assembly election."),
    term("1994-12-12", "1995-09-01", "elected", party_code=None, alliance=None,
         cm_name="N. T. Rama Rao",
         notes="Unified Andhra Pradesh pre-bifurcation. TDP (Telugu Desam Party). NTR's third term; deposed by son-in-law N. Chandrababu Naidu in an intra-party coup."),
    term("1995-09-01", "2004-05-14", "elected", party_code=None, alliance=None,
         cm_name="N. Chandrababu Naidu",
         notes="Unified Andhra Pradesh pre-bifurcation. TDP (Telugu Desam Party). Two terms (1995-1999, 1999-2004). NDA partner from 1998."),
    term("2004-05-14", "2009-09-02", "elected", party_code=INC, alliance="UPA",
         cm_name="Y. S. Rajasekhara Reddy",
         notes="Unified Andhra Pradesh pre-bifurcation. INC. Died in office (helicopter crash, 2 Sep 2009)."),
    term("2009-09-03", "2010-11-25", "elected", party_code=INC, alliance="UPA",
         cm_name="K. Rosaiah",
         notes="Unified Andhra Pradesh pre-bifurcation. INC. Caretaker after YSR's death; resigned amid Telangana agitation."),
    term("2010-11-25", "2014-03-01", "elected", party_code=INC, alliance="UPA",
         cm_name="N. Kiran Kumar Reddy",
         notes="Unified Andhra Pradesh pre-bifurcation. INC. Resigned in protest against the Andhra Pradesh Reorganisation Act 2014."),
    pr("2014-03-01", "2014-06-08", "President's Rule imposed during the bifurcation transition (1 March 2014 – 8 June 2014). State formally bifurcated on 2 June 2014; new Andhra Pradesh and Telangana governments sworn in 8 June 2014."),
]


# ---------------------------------------------------------------------------
# Per-state authored data
# ---------------------------------------------------------------------------

def s01_andhra_pradesh():
    sources = [
        wiki_src("List_of_chief_ministers_of_Andhra_Pradesh",
                 "List of chief ministers of Andhra Pradesh"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/2",
         "fetched_at": FETCHED_AT,
         "name": "Andhra Pradesh Legislative Assembly Election - 2024",
         "authority": ECI_AUTH},
    ]
    terms = list(AP_UNIFIED) + [
        term("2014-06-08", "2019-05-29", "elected", party_code=None,
             alliance="NDA", cm_name="N. Chandrababu Naidu",
             notes="Post-bifurcation Andhra Pradesh, first term. TDP (Telugu Desam Party) in alliance with BJP until split in March 2018."),
        term("2019-05-30", "2024-06-11", "elected", party_code=None,
             alliance=None, cm_name="Y. S. Jagan Mohan Reddy",
             notes="YSRCP (YSR Congress Party). Single five-year term."),
        term("2024-06-12", None, "elected", party_code=None,
             alliance="NDA", cm_name="N. Chandrababu Naidu",
             notes="TDP (Telugu Desam Party) in NDA alliance with Jana Sena and BJP. Fourth term as CM. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenJune2024/partywiseresult-S01.htm", "note": "2024 partywise result."}]),
    ]
    return write("S01", sources, terms)


def s02_arunachal_pradesh():
    sources = [
        wiki_src("List_of_chief_ministers_of_Arunachal_Pradesh",
                 "List of chief ministers of Arunachal Pradesh"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/3",
         "fetched_at": FETCHED_AT,
         "name": "Arunachal Pradesh Legislative Assembly Election - 2024",
         "authority": ECI_AUTH},
    ]
    terms = [
        term("1980-01-18", "1995-01-22", "elected", party_code=INC, alliance=None,
             cm_name="Gegong Apang",
             notes="INC. Long-running term spanning the 1980s and early 1990s; re-elected 1990. (Pre-1990 portion retained for context.)"),
        term("1995-01-22", "1999-01-19", "elected", party_code=None, alliance=None,
             cm_name="Gegong Apang",
             notes="Switched from INC to Arunachal Congress (Mithi). Coalition governments through this period."),
        term("1999-01-19", "2003-08-03", "elected", party_code=INC, alliance=None,
             cm_name="Mukut Mithi",
             notes="Arunachal Congress (Mithi); merged with INC. Replaced by Apang."),
        term("2003-08-03", "2007-04-09", "elected", party_code=None, alliance=None,
             cm_name="Gegong Apang",
             notes="Re-took office; switched to BJP and then to INC. Replaced by Dorjee Khandu after corruption allegations."),
        term("2007-04-09", "2011-04-30", "elected", party_code=INC, alliance="UPA",
             cm_name="Dorjee Khandu",
             notes="INC. Died in office on 30 April 2011 in a helicopter crash."),
        term("2011-05-05", "2011-11-01", "elected", party_code=INC, alliance="UPA",
             cm_name="Jarbom Gamlin",
             notes="INC. Caretaker after Khandu's death; replaced by Nabam Tuki within months."),
        term("2011-11-01", "2016-01-26", "elected", party_code=INC, alliance="UPA",
             cm_name="Nabam Tuki",
             notes="INC. Continued through the 2014 election. Removed during the 2016 constitutional crisis."),
        pr("2016-01-26", "2016-02-19", "President's Rule imposed amid the Arunachal Pradesh constitutional crisis after defections in the INC legislature party. Lifted by Supreme Court intervention."),
        term("2016-02-19", "2016-07-13", "elected", party_code=None, alliance=None,
             cm_name="Kalikho Pul",
             notes="People's Party of Arunachal (PPA) faction. Removed after the Supreme Court restored Nabam Tuki on 13 July 2016."),
        term("2016-07-13", "2016-07-17", "elected", party_code=INC, alliance="UPA",
             cm_name="Nabam Tuki",
             notes="INC. Restored by Supreme Court but lost majority within days."),
        term("2016-07-17", "2016-12-31", "elected", party_code=None, alliance=None,
             cm_name="Pema Khandu",
             notes="People's Party of Arunachal (PPA), then defected to BJP in December 2016."),
        term("2016-12-31", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Pema Khandu",
             notes="BJP. Re-elected 2019 and 2024. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenJune2024/partywiseresult-S02.htm", "note": "2024 partywise result."}]),
    ]
    return write("S02", sources, terms)


def s04_bihar():
    sources = [
        wiki_src("List_of_chief_ministers_of_Bihar",
                 "List of chief ministers of Bihar"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2025/16",
         "fetched_at": FETCHED_AT,
         "name": "Bihar Legislative Assembly Election Statistical Report 2025",
         "authority": ECI_AUTH},
    ]
    terms = [
        term("1990-03-10", "1995-03-28", "elected", party_code=None, alliance=None,
             cm_name="Lalu Prasad Yadav",
             notes="Janata Dal. First term."),
        term("1995-04-04", "1997-07-25", "elected", party_code=None, alliance=None,
             cm_name="Lalu Prasad Yadav",
             notes="Janata Dal (later RJD from July 1997). Resigned over the fodder scam case."),
        term("1997-07-25", "1999-02-11", "elected", party_code=RJD, alliance=None,
             cm_name="Rabri Devi",
             notes="RJD (Rashtriya Janata Dal). Lalu's wife; took over after his resignation."),
        pr("1999-02-12", "1999-03-09", "President's Rule imposed amid the Senari massacre and law-and-order collapse. Revoked when Rabri was reinstated."),
        term("1999-03-09", "2000-03-02", "elected", party_code=RJD, alliance=None,
             cm_name="Rabri Devi", notes="RJD."),
        term("2000-03-03", "2000-03-10", "elected", party_code=None, alliance="NDA",
             cm_name="Nitish Kumar",
             notes="JD(U) / Samata Party. First, very brief NDA-backed term; resigned within a week unable to prove majority."),
        term("2000-03-11", "2005-03-06", "elected", party_code=RJD, alliance="UPA",
             cm_name="Rabri Devi",
             notes="RJD. Resumed office after Nitish's brief tenure."),
        pr("2005-03-07", "2005-11-24", "President's Rule. February 2005 election produced a hung assembly; centre dismissed the assembly. Re-election held in October-November 2005."),
        term("2005-11-24", "2014-05-17", "elected", party_code=None, alliance="NDA",
             cm_name="Nitish Kumar",
             notes="JD(U) in NDA. Two terms (2005-2010, 2010-2014). Resigned after the BJP-JDU split in June 2013 and BJP's poor 2014 LS show."),
        term("2014-05-20", "2015-02-22", "elected", party_code=None, alliance=None,
             cm_name="Jitan Ram Manjhi",
             notes="JD(U). Hand-picked by Nitish; later expelled. Briefly resigned amid intra-party turmoil."),
        term("2015-02-22", "2017-07-26", "elected", party_code=None,
             alliance="Mahagathbandhan",
             cm_name="Nitish Kumar",
             notes="JD(U) in Mahagathbandhan with RJD + INC. Resigned 26 July 2017 over CBI cases against Tejashwi Yadav."),
        term("2017-07-27", "2022-08-09", "elected", party_code=None, alliance="NDA",
             cm_name="Nitish Kumar",
             notes="JD(U) back in NDA with BJP. Continued through the 2020 election. Resigned 9 August 2022 to break with BJP."),
        term("2022-08-10", "2024-01-28", "elected", party_code=None,
             alliance="Mahagathbandhan",
             cm_name="Nitish Kumar",
             notes="JD(U) again with RJD + INC + Left in Mahagathbandhan. Resigned 28 January 2024 to switch back to NDA."),
        term("2024-01-28", None, "elected", party_code=None, alliance="NDA",
             cm_name="Nitish Kumar",
             notes="JD(U) in NDA. Ninth term as CM. Continued after Bihar Assembly Election November 2025. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenNov2025/partywiseresult-S04.htm", "note": "2025 partywise result."}]),
    ]
    return write("S04", sources, terms)


def s05_goa():
    sources = [
        wiki_src("List_of_chief_ministers_of_Goa",
                 "List of chief ministers of Goa"),
    ]
    terms = [
        term("1990-01-25", "1990-04-14", "elected", party_code=None, alliance=None,
             cm_name="Churchill Alemao",
             notes="Progressive Democratic Front. Brief term."),
        term("1990-04-14", "1990-12-14", "elected", party_code=None, alliance=None,
             cm_name="Luis Proto Barbosa",
             notes="Goan People's Party."),
        pr("1990-12-14", "1991-01-25", "President's Rule. Coalition collapse."),
        term("1991-01-25", "1993-05-18", "elected", party_code=INC, alliance=None,
             cm_name="Ravi S. Naik", notes="INC. Replaced by Wilfred de Souza."),
        term("1993-05-18", "1994-04-02", "elected", party_code=INC, alliance=None,
             cm_name="Wilfred de Souza", notes="INC."),
        term("1994-04-02", "1994-12-16", "elected", party_code=INC, alliance=None,
             cm_name="Ravi S. Naik", notes="INC. Brief return."),
        term("1994-12-16", "1998-07-29", "elected", party_code=INC, alliance=None,
             cm_name="Pratapsingh Rane",
             notes="INC. Won 1994 election."),
        term("1998-07-29", "1998-11-26", "elected", party_code=INC, alliance=None,
             cm_name="Wilfred de Souza", notes="INC."),
        term("1998-11-26", "1999-02-09", "elected", party_code=None, alliance=None,
             cm_name="Luizinho Faleiro", notes="INC (Goa Rajiv Congress)."),
        pr("1999-02-09", "1999-06-09", "President's Rule. Hung assembly."),
        term("1999-06-09", "1999-11-24", "elected", party_code=INC, alliance=None,
             cm_name="Luizinho Faleiro", notes="INC."),
        term("1999-11-24", "2000-10-23", "elected", party_code=INC, alliance=None,
             cm_name="Francisco Sardinha", notes="Goa People's Congress / INC."),
        term("2000-10-24", "2005-02-02", "elected", party_code=BJP, alliance="NDA",
             cm_name="Manohar Parrikar",
             notes="BJP. First term. Replaced after defections in 2005."),
        term("2005-02-02", "2007-06-07", "elected", party_code=INC, alliance="UPA",
             cm_name="Pratapsingh Rane", notes="INC."),
        term("2007-06-08", "2012-03-09", "elected", party_code=INC, alliance="UPA",
             cm_name="Digambar Kamat", notes="INC."),
        term("2012-03-09", "2014-11-08", "elected", party_code=BJP, alliance="NDA",
             cm_name="Manohar Parrikar",
             notes="BJP. Resigned to become Union Defence Minister."),
        term("2014-11-08", "2017-03-13", "elected", party_code=BJP, alliance="NDA",
             cm_name="Laxmikant Parsekar", notes="BJP."),
        term("2017-03-14", "2019-03-17", "elected", party_code=BJP, alliance="NDA",
             cm_name="Manohar Parrikar",
             notes="BJP. Returned from Union cabinet. Died in office (pancreatic cancer)."),
        term("2019-03-19", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Pramod Sawant",
             notes="BJP. Sworn in after Parrikar's death; re-elected 2022. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2022/statewise-S05.htm", "note": "2022 result."}]),
    ]
    return write("S05", sources, terms)


def s06_gujarat():
    sources = [
        wiki_src("List_of_chief_ministers_of_Gujarat",
                 "List of chief ministers of Gujarat"),
    ]
    terms = [
        term("1990-03-04", "1990-10-25", "elected", party_code=None, alliance=None,
             cm_name="Chimanbhai Patel",
             notes="Janata Dal (Gujarat) initially in coalition with BJP; switched to INC support October 1990."),
        term("1990-10-25", "1994-02-17", "elected", party_code=INC, alliance=None,
             cm_name="Chimanbhai Patel",
             notes="INC (Patel merged his Janata Dal Gujarat into INC). Died in office."),
        term("1994-02-17", "1995-03-14", "elected", party_code=INC, alliance=None,
             cm_name="Chhabildas Mehta",
             notes="INC. Caretaker after Chimanbhai Patel's death."),
        term("1995-03-14", "1995-10-21", "elected", party_code=BJP, alliance=None,
             cm_name="Keshubhai Patel",
             notes="BJP first term. Forced to resign after Shankersinh Vaghela's rebellion."),
        term("1995-10-21", "1996-09-19", "elected", party_code=BJP, alliance=None,
             cm_name="Suresh Mehta",
             notes="BJP. Replaced by Vaghela's RJP-INC government."),
        pr("1996-09-19", "1996-10-23", "President's Rule. Brief; followed Vaghela's revolt against the BJP government."),
        term("1996-10-23", "1997-10-27", "elected", party_code=None, alliance=None,
             cm_name="Shankersinh Vaghela",
             notes="Rashtriya Janata Party (RJP) with INC support."),
        term("1997-10-28", "1998-03-04", "elected", party_code=None, alliance=None,
             cm_name="Dilip Parikh", notes="RJP with INC support."),
        term("1998-03-04", "2001-10-06", "elected", party_code=BJP, alliance="NDA",
             cm_name="Keshubhai Patel",
             notes="BJP. Replaced by Narendra Modi after Bhuj earthquake handling and intra-party pressure."),
        term("2001-10-07", "2014-05-22", "elected", party_code=BJP, alliance="NDA",
             cm_name="Narendra Modi",
             notes="BJP. Three full terms (2002, 2007, 2012). Resigned to become Prime Minister."),
        term("2014-05-22", "2016-08-03", "elected", party_code=BJP, alliance="NDA",
             cm_name="Anandiben Patel",
             notes="BJP. First woman CM of Gujarat."),
        term("2016-08-07", "2021-09-12", "elected", party_code=BJP, alliance="NDA",
             cm_name="Vijay Rupani",
             notes="BJP. Re-elected 2017. Resigned in 2021 leadership change."),
        term("2021-09-13", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Bhupendra Patel",
             notes="BJP. Re-elected with record majority in 2022. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2022/statewise-S06.htm", "note": "2022 result."}]),
    ]
    return write("S06", sources, terms)


def s07_haryana():
    sources = [
        wiki_src("List_of_chief_ministers_of_Haryana",
                 "List of chief ministers of Haryana"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/6",
         "fetched_at": FETCHED_AT,
         "name": "Haryana Legislative Assembly Election - 2024",
         "authority": ECI_AUTH},
    ]
    terms = [
        term("1987-06-20", "1990-04-02", "elected", party_code=None, alliance=None,
             cm_name="Devi Lal",
             notes="Lok Dal (B). Resigned to become Deputy PM in V. P. Singh government."),
        term("1990-04-02", "1990-07-06", "elected", party_code=None, alliance=None,
             cm_name="Om Prakash Chautala",
             notes="Janata Dal. First brief term."),
        term("1990-07-06", "1990-07-17", "elected", party_code=None, alliance=None,
             cm_name="Banarsi Das Gupta", notes="Janata Dal. Brief."),
        term("1990-07-17", "1991-03-22", "elected", party_code=None, alliance=None,
             cm_name="Om Prakash Chautala", notes="Janata Dal."),
        term("1991-03-22", "1991-04-06", "elected", party_code=None, alliance=None,
             cm_name="Hukam Singh", notes="Janata Dal."),
        pr("1991-04-06", "1991-07-23", "President's Rule before the May 1991 elections."),
        term("1991-07-23", "1996-05-09", "elected", party_code=INC, alliance=None,
             cm_name="Bhajan Lal", notes="INC."),
        term("1996-05-11", "1999-07-23", "elected", party_code=None, alliance="NDA",
             cm_name="Bansi Lal",
             notes="Haryana Vikas Party (HVP) with BJP support."),
        term("1999-07-24", "2005-03-05", "elected", party_code=None, alliance="NDA",
             cm_name="Om Prakash Chautala",
             notes="Indian National Lok Dal (INLD) in alliance with BJP."),
        term("2005-03-05", "2014-10-26", "elected", party_code=INC, alliance="UPA",
             cm_name="Bhupinder Singh Hooda",
             notes="INC. Two terms (2005, 2009)."),
        term("2014-10-26", "2024-03-12", "elected", party_code=BJP, alliance="NDA",
             cm_name="Manohar Lal Khattar",
             notes="BJP. Two terms (2014, 2019). Resigned in March 2024 leadership change ahead of LS election."),
        term("2024-03-12", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Nayab Singh Saini",
             notes="BJP. Continued after the October 2024 election win. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenOct2024/partywiseresult-S07.htm", "note": "2024 partywise result."}]),
    ]
    return write("S07", sources, terms)


def s08_himachal_pradesh():
    sources = [
        wiki_src("List_of_chief_ministers_of_Himachal_Pradesh",
                 "List of chief ministers of Himachal Pradesh"),
    ]
    terms = [
        term("1990-03-05", "1992-12-15", "elected", party_code=BJP, alliance=None,
             cm_name="Shanta Kumar",
             notes="BJP. Dismissed when Article 356 was invoked post-Babri."),
        pr("1992-12-15", "1993-12-03", "President's Rule following the demolition of the Babri Masjid; all four BJP-ruled states dismissed."),
        term("1993-12-03", "1998-03-23", "elected", party_code=INC, alliance=None,
             cm_name="Virbhadra Singh", notes="INC."),
        term("1998-03-24", "2003-03-05", "elected", party_code=BJP, alliance="NDA",
             cm_name="Prem Kumar Dhumal", notes="BJP."),
        term("2003-03-06", "2007-12-30", "elected", party_code=INC, alliance="UPA",
             cm_name="Virbhadra Singh", notes="INC."),
        term("2007-12-30", "2012-12-25", "elected", party_code=BJP, alliance="NDA",
             cm_name="Prem Kumar Dhumal", notes="BJP."),
        term("2012-12-25", "2017-12-27", "elected", party_code=INC, alliance="UPA",
             cm_name="Virbhadra Singh", notes="INC. Final term."),
        term("2017-12-27", "2022-12-11", "elected", party_code=BJP, alliance="NDA",
             cm_name="Jai Ram Thakur", notes="BJP."),
        term("2022-12-11", None, "elected", party_code=INC, alliance=None,
             cm_name="Sukhvinder Singh Sukhu",
             notes="INC. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2022/statewise-S08.htm", "note": "2022 result."}]),
    ]
    return write("S08", sources, terms)


def s10_karnataka():
    sources = [
        wiki_src("List_of_chief_ministers_of_Karnataka",
                 "List of chief ministers of Karnataka"),
    ]
    terms = [
        term("1989-11-30", "1990-10-10", "elected", party_code=INC, alliance=None,
             cm_name="Veerendra Patil",
             notes="INC. Removed by Rajiv Gandhi after communal riots."),
        term("1990-10-17", "1992-11-19", "elected", party_code=INC, alliance=None,
             cm_name="S. Bangarappa", notes="INC. Replaced after corruption charges."),
        term("1992-11-19", "1994-12-11", "elected", party_code=INC, alliance=None,
             cm_name="M. Veerappa Moily", notes="INC."),
        term("1994-12-11", "1996-05-31", "elected", party_code=None, alliance=None,
             cm_name="H. D. Deve Gowda",
             notes="Janata Dal. Resigned to become Prime Minister."),
        term("1996-05-31", "1999-10-07", "elected", party_code=None, alliance=None,
             cm_name="J. H. Patel",
             notes="Janata Dal (later JD-U). Coalition with BJP from 1998."),
        term("1999-10-11", "2004-05-28", "elected", party_code=INC, alliance="UPA",
             cm_name="S. M. Krishna", notes="INC."),
        term("2004-05-28", "2006-01-28", "elected", party_code=INC, alliance="UPA",
             cm_name="Dharam Singh",
             notes="INC + JD(S) coalition. Collapsed when JD(S) switched to BJP."),
        term("2006-02-03", "2007-10-08", "elected", party_code=None, alliance=None,
             cm_name="H. D. Kumaraswamy",
             notes="JD(S) in coalition with BJP. Refused to honour rotation; coalition collapsed."),
        pr("2007-10-09", "2007-11-12", "President's Rule. Coalition collapse."),
        term("2007-11-12", "2007-11-19", "elected", party_code=BJP, alliance=None,
             cm_name="B. S. Yediyurappa",
             notes="BJP. Seven-day term; resigned without seeking confidence vote."),
        pr("2007-11-19", "2008-05-30", "President's Rule before May 2008 election."),
        term("2008-05-30", "2011-08-04", "elected", party_code=BJP, alliance="NDA",
             cm_name="B. S. Yediyurappa",
             notes="BJP. First full BJP government in any south Indian state. Resigned over Lokayukta indictment."),
        term("2011-08-04", "2012-07-12", "elected", party_code=BJP, alliance="NDA",
             cm_name="D. V. Sadananda Gowda", notes="BJP."),
        term("2012-07-12", "2013-05-12", "elected", party_code=BJP, alliance="NDA",
             cm_name="Jagadish Shettar", notes="BJP."),
        term("2013-05-13", "2018-05-17", "elected", party_code=INC, alliance="UPA",
             cm_name="Siddaramaiah", notes="INC. First full term."),
        term("2018-05-17", "2018-05-19", "elected", party_code=BJP, alliance="NDA",
             cm_name="B. S. Yediyurappa",
             notes="BJP. Two-day term; resigned before floor test."),
        term("2018-05-23", "2019-07-23", "elected", party_code=None, alliance=None,
             cm_name="H. D. Kumaraswamy",
             notes="JD(S)-INC coalition. Collapsed after defections (Operation Kamala)."),
        term("2019-07-26", "2021-07-28", "elected", party_code=BJP, alliance="NDA",
             cm_name="B. S. Yediyurappa",
             notes="BJP. Fourth term. Resigned over central party pressure."),
        term("2021-07-28", "2023-05-13", "elected", party_code=BJP, alliance="NDA",
             cm_name="Basavaraj Bommai", notes="BJP."),
        term("2023-05-20", None, "elected", party_code=INC, alliance=None,
             cm_name="Siddaramaiah", notes="INC. Second term. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S10.htm", "note": "2023 result."}]),
    ]
    return write("S10", sources, terms)


def s12_madhya_pradesh():
    sources = [
        wiki_src("List_of_chief_ministers_of_Madhya_Pradesh",
                 "List of chief ministers of Madhya Pradesh"),
    ]
    terms = [
        term("1990-03-05", "1992-12-15", "elected", party_code=BJP, alliance=None,
             cm_name="Sunderlal Patwa",
             notes="BJP. Dismissed when Article 356 was invoked post-Babri."),
        pr("1992-12-15", "1993-12-07", "President's Rule following the demolition of the Babri Masjid."),
        term("1993-12-07", "2003-12-08", "elected", party_code=INC, alliance=None,
             cm_name="Digvijaya Singh",
             notes="INC. Two consecutive terms. Includes Chhattisgarh until 1 November 2000 bifurcation; pre-bifurcation tenure also appears in S26."),
        term("2003-12-08", "2003-12-08", "elected", party_code=BJP, alliance="NDA",
             cm_name="Uma Bharti",
             notes="BJP. Resigned over the Hubli arrest warrant."),
        term("2004-08-23", "2005-11-29", "elected", party_code=BJP, alliance="NDA",
             cm_name="Babulal Gaur", notes="BJP."),
        term("2005-11-29", "2018-12-17", "elected", party_code=BJP, alliance="NDA",
             cm_name="Shivraj Singh Chouhan",
             notes="BJP. Three consecutive terms (2005, 2008, 2013)."),
        term("2018-12-17", "2020-03-23", "elected", party_code=INC, alliance=None,
             cm_name="Kamal Nath",
             notes="INC. Lost majority to Jyotiraditya Scindia's defection."),
        term("2020-03-23", "2023-12-13", "elected", party_code=BJP, alliance="NDA",
             cm_name="Shivraj Singh Chouhan", notes="BJP. Fourth term."),
        term("2023-12-13", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Mohan Yadav", notes="BJP. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S12.htm", "note": "2023 result."}]),
    ]
    return write("S12", sources, terms)


def s13_maharashtra():
    sources = [
        wiki_src("List_of_chief_ministers_of_Maharashtra",
                 "List of chief ministers of Maharashtra"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/8",
         "fetched_at": FETCHED_AT,
         "name": "Maharashtra Legislative Assembly Election 2024",
         "authority": ECI_AUTH},
    ]
    terms = [
        term("1988-06-26", "1991-06-25", "elected", party_code=INC, alliance=None,
             cm_name="Sharad Pawar", notes="INC."),
        term("1991-06-25", "1993-02-22", "elected", party_code=INC, alliance=None,
             cm_name="Sudhakarrao Naik",
             notes="INC. Resigned after Bombay riots."),
        term("1993-03-06", "1995-03-14", "elected", party_code=INC, alliance=None,
             cm_name="Sharad Pawar",
             notes="INC. Tenure included the Bombay serial blasts (March 1993)."),
        term("1995-03-14", "1999-01-31", "elected", party_code=None, alliance=None,
             cm_name="Manohar Joshi",
             notes="Shiv Sena (undivided) in alliance with BJP."),
        term("1999-02-01", "1999-10-17", "elected", party_code=None, alliance=None,
             cm_name="Narayan Rane",
             notes="Shiv Sena (undivided) in alliance with BJP."),
        term("1999-10-18", "2003-01-18", "elected", party_code=INC, alliance="UPA",
             cm_name="Vilasrao Deshmukh",
             notes="INC + NCP coalition (Democratic Front)."),
        term("2003-01-18", "2004-10-30", "elected", party_code=INC, alliance="UPA",
             cm_name="Sushil Kumar Shinde", notes="INC."),
        term("2004-11-01", "2008-12-04", "elected", party_code=INC, alliance="UPA",
             cm_name="Vilasrao Deshmukh",
             notes="INC. Resigned after 26/11 Mumbai attacks."),
        term("2008-12-08", "2010-11-09", "elected", party_code=INC, alliance="UPA",
             cm_name="Ashok Chavan",
             notes="INC. Resigned over Adarsh housing scam."),
        term("2010-11-11", "2014-09-28", "elected", party_code=INC, alliance="UPA",
             cm_name="Prithviraj Chavan", notes="INC."),
        pr("2014-09-28", "2014-10-31", "President's Rule before October 2014 election."),
        term("2014-10-31", "2019-11-08", "elected", party_code=BJP, alliance="NDA",
             cm_name="Devendra Fadnavis",
             notes="BJP. First Brahmin CM in 4 decades; first BJP CM. NDA with Shiv Sena (undivided)."),
        term("2019-11-23", "2019-11-26", "elected", party_code=BJP, alliance=None,
             cm_name="Devendra Fadnavis",
             notes="BJP. 80-hour term with NCP's Ajit Pawar; collapsed when Ajit returned to NCP."),
        term("2019-11-28", "2022-06-29", "elected", party_code=None,
             alliance="Maha Vikas Aghadi",
             cm_name="Uddhav Thackeray",
             notes="Shiv Sena (undivided) in MVA with NCP + INC. Resigned after Eknath Shinde's rebellion."),
        term("2022-06-30", "2024-12-05", "elected", party_code=None,
             alliance="Mahayuti",
             cm_name="Eknath Shinde",
             notes="Shiv Sena (Shinde faction; later allotted bow-and-arrow symbol). Mahayuti with BJP and Ajit Pawar's NCP."),
        term("2024-12-05", None, "elected", party_code=BJP, alliance="Mahayuti",
             cm_name="Devendra Fadnavis",
             notes="BJP. Mahayuti. Sworn in after the November 2024 election. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenNov2024/partywiseresult-S13.htm", "note": "2024 partywise result."}]),
    ]
    return write("S13", sources, terms)


def s14_manipur():
    sources = [
        wiki_src("List_of_chief_ministers_of_Manipur",
                 "List of chief ministers of Manipur"),
    ]
    terms = [
        term("1990-02-23", "1992-04-07", "elected", party_code=None, alliance=None,
             cm_name="R. K. Ranbir Singh",
             notes="Manipur People's Party. Coalition collapsed."),
        pr("1992-01-07", "1992-04-08", "President's Rule. Coalition collapse and law-and-order issues."),
        term("1992-04-08", "1993-12-10", "elected", party_code=INC, alliance=None,
             cm_name="R. K. Dorendro Singh", notes="INC."),
        pr("1993-12-31", "1994-12-13", "President's Rule. Insurgency and political instability."),
        term("1994-12-14", "1997-12-15", "elected", party_code=INC, alliance=None,
             cm_name="Rishang Keishing", notes="INC."),
        term("1997-12-15", "2001-02-15", "elected", party_code=None, alliance=None,
             cm_name="W. Nipamacha Singh",
             notes="Manipur State Congress Party."),
        term("2001-02-15", "2001-06-02", "elected", party_code=None, alliance=None,
             cm_name="Radhabinod Koijam",
             notes="Samata Party. Coalition collapsed."),
        pr("2001-06-02", "2002-03-06", "President's Rule. Coalition instability."),
        term("2002-03-07", "2017-03-15", "elected", party_code=INC, alliance="UPA",
             cm_name="Okram Ibobi Singh",
             notes="INC. Three consecutive terms (2002, 2007, 2012)."),
        term("2017-03-15", "2022-03-21", "elected", party_code=BJP, alliance="NDA",
             cm_name="N. Biren Singh", notes="BJP."),
        term("2022-03-21", "2025-02-13", "elected", party_code=BJP, alliance="NDA",
             cm_name="N. Biren Singh",
             notes="BJP. Second term. Resigned amid the ongoing Meitei-Kuki ethnic conflict."),
        pr("2025-02-13", None, "President's Rule following N. Biren Singh's resignation; BJP unable to find a consensus replacement amid the ongoing ethnic conflict. Ongoing."),
    ]
    return write("S14", sources, terms)


def s15_meghalaya():
    sources = [
        wiki_src("List_of_chief_ministers_of_Meghalaya",
                 "List of chief ministers of Meghalaya"),
    ]
    terms = [
        term("1990-02-08", "1991-10-08", "elected", party_code=None, alliance=None,
             cm_name="B. B. Lyngdoh",
             notes="Hill People's Union (HPU)."),
        pr("1991-10-11", "1992-02-05", "President's Rule. Coalition instability."),
        term("1992-02-05", "1993-02-19", "elected", party_code=INC, alliance=None,
             cm_name="D. D. Lapang", notes="INC. Brief."),
        term("1993-02-19", "1998-02-27", "elected", party_code=INC, alliance=None,
             cm_name="S. C. Marak", notes="INC."),
        term("1998-02-27", "2000-03-08", "elected", party_code=None, alliance=None,
             cm_name="B. B. Lyngdoh",
             notes="United Democratic Party (UDP) in Meghalaya Democratic Alliance."),
        term("2000-03-08", "2001-12-08", "elected", party_code=None, alliance=None,
             cm_name="E. K. Mawlong",
             notes="UDP-led alliance."),
        term("2001-12-08", "2003-03-04", "elected", party_code=None, alliance=None,
             cm_name="Flinder Anderson Khonglam",
             notes="Independent backed by various parties."),
        term("2003-03-04", "2006-06-10", "elected", party_code=INC, alliance="UPA",
             cm_name="D. D. Lapang", notes="INC."),
        term("2006-06-15", "2007-03-10", "elected", party_code=None, alliance=None,
             cm_name="J. D. Rymbai", notes="INC. Caretaker arrangements."),
        term("2007-03-10", "2008-03-04", "elected", party_code=INC, alliance="UPA",
             cm_name="D. D. Lapang", notes="INC."),
        term("2008-03-04", "2008-03-19", "elected", party_code=None, alliance=None,
             cm_name="Donkupar Roy",
             notes="UDP-led Meghalaya Progressive Alliance. Brief; lost confidence vote."),
        pr("2009-03-18", "2009-05-13", "President's Rule. Coalition collapse."),
        term("2009-05-13", "2010-04-19", "elected", party_code=INC, alliance="UPA",
             cm_name="D. D. Lapang", notes="INC."),
        term("2010-04-19", "2013-03-05", "elected", party_code=INC, alliance="UPA",
             cm_name="Mukul Sangma", notes="INC."),
        term("2013-03-05", "2018-03-06", "elected", party_code=INC, alliance="UPA",
             cm_name="Mukul Sangma", notes="INC. Second term."),
        term("2018-03-06", None, "elected", party_code=None, alliance="NDA",
             cm_name="Conrad Sangma",
             notes="National People's Party (NPP) in NDA-allied Meghalaya Democratic Alliance with BJP, UDP and others. Re-elected 2023. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S15.htm", "note": "2023 result."}]),
    ]
    return write("S15", sources, terms)


def s16_mizoram():
    sources = [
        wiki_src("List_of_chief_ministers_of_Mizoram",
                 "List of chief ministers of Mizoram"),
    ]
    terms = [
        term("1989-01-24", "1998-12-03", "elected", party_code=INC, alliance=None,
             cm_name="Lal Thanhawla",
             notes="INC. Two consecutive terms (1989, 1993)."),
        term("1998-12-03", "2008-12-11", "elected", party_code=None, alliance="NDA",
             cm_name="Zoramthanga",
             notes="Mizo National Front (MNF) in NDA. Two consecutive terms."),
        term("2008-12-11", "2018-12-15", "elected", party_code=INC, alliance="UPA",
             cm_name="Lal Thanhawla",
             notes="INC. Two consecutive terms (2008, 2013)."),
        term("2018-12-15", "2023-12-08", "elected", party_code=None, alliance="NDA",
             cm_name="Zoramthanga",
             notes="MNF in NDA."),
        term("2023-12-08", None, "elected", party_code=None, alliance=None,
             cm_name="Lalduhoma",
             notes="Zoram People's Movement (ZPM). Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S16.htm", "note": "2023 result."}]),
    ]
    return write("S16", sources, terms)


def s17_nagaland():
    sources = [
        wiki_src("List_of_chief_ministers_of_Nagaland",
                 "List of chief ministers of Nagaland"),
    ]
    terms = [
        term("1988-01-25", "1990-05-10", "elected", party_code=INC, alliance=None,
             cm_name="S. C. Jamir", notes="INC."),
        term("1990-05-16", "1990-06-19", "elected", party_code=None, alliance=None,
             cm_name="K. L. Chishi", notes="INC. Brief."),
        term("1990-06-19", "1992-04-02", "elected", party_code=None, alliance=None,
             cm_name="Vamuzo Phesao",
             notes="Nagaland People's Council (NPC)."),
        pr("1992-04-02", "1993-02-22", "President's Rule. Coalition collapse and insurgency."),
        term("1993-02-22", "2003-03-06", "elected", party_code=INC, alliance=None,
             cm_name="S. C. Jamir",
             notes="INC. Two consecutive terms (1993, 1998)."),
        term("2003-03-06", "2008-01-03", "elected", party_code=None, alliance="NDA",
             cm_name="Neiphiu Rio",
             notes="Nagaland People's Front (NPF) in Democratic Alliance of Nagaland with BJP."),
        pr("2008-01-03", "2008-03-12", "President's Rule. Brief, before March 2008 election."),
        term("2008-03-12", "2014-05-24", "elected", party_code=None, alliance="NDA",
             cm_name="Neiphiu Rio",
             notes="NPF. Resigned to contest Lok Sabha."),
        term("2014-05-24", "2017-02-22", "elected", party_code=None, alliance="NDA",
             cm_name="T. R. Zeliang", notes="NPF."),
        term("2017-02-22", "2017-07-19", "elected", party_code=None, alliance="NDA",
             cm_name="Shurhozelie Liezietsu", notes="NPF."),
        term("2017-07-19", "2018-03-08", "elected", party_code=None, alliance="NDA",
             cm_name="T. R. Zeliang", notes="NPF."),
        term("2018-03-08", None, "elected", party_code=None, alliance="NDA",
             cm_name="Neiphiu Rio",
             notes="Nationalist Democratic Progressive Party (NDPP) in alliance with BJP. Re-elected 2023. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S17.htm", "note": "2023 result."}]),
    ]
    return write("S17", sources, terms)


def s18_odisha():
    sources = [
        wiki_src("List_of_chief_ministers_of_Odisha",
                 "List of chief ministers of Odisha"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/4",
         "fetched_at": FETCHED_AT,
         "name": "Odisha Legislative Assembly Election - 2024",
         "authority": ECI_AUTH},
    ]
    terms = [
        term("1990-03-05", "1995-03-15", "elected", party_code=None, alliance=None,
             cm_name="Biju Patnaik", notes="Janata Dal."),
        term("1995-03-15", "1999-02-17", "elected", party_code=INC, alliance=None,
             cm_name="J. B. Patnaik",
             notes="INC. Resigned after the supercyclone response and party-internal pressure."),
        term("1999-02-17", "1999-12-06", "elected", party_code=INC, alliance=None,
             cm_name="Giridhar Gamang",
             notes="INC. His vote brought down the Vajpayee government in 1999."),
        term("1999-12-06", "2000-03-05", "elected", party_code=INC, alliance=None,
             cm_name="Hemananda Biswal", notes="INC."),
        term("2000-03-05", "2024-06-12", "elected", party_code=None, alliance=None,
             cm_name="Naveen Patnaik",
             notes="Biju Janata Dal (BJD). Five consecutive terms. NDA partner 2000-2009; non-aligned thereafter. Lost 2024 election."),
        term("2024-06-12", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Mohan Charan Majhi",
             notes="BJP. First BJP CM of Odisha. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenJune2024/partywiseresult-S18.htm", "note": "2024 partywise result."}]),
    ]
    return write("S18", sources, terms)


def s19_punjab():
    sources = [
        wiki_src("List_of_chief_ministers_of_Punjab,_India",
                 "List of chief ministers of Punjab, India"),
    ]
    terms = [
        pr("1987-06-11", "1992-02-25", "President's Rule throughout the Punjab insurgency. Repeatedly extended; lifted only for the February 1992 election."),
        term("1992-02-25", "1995-08-31", "elected", party_code=INC, alliance=None,
             cm_name="Beant Singh",
             notes="INC. Assassinated by Babbar Khalsa suicide bomb on 31 August 1995."),
        term("1995-08-31", "1996-11-21", "elected", party_code=INC, alliance=None,
             cm_name="Harcharan Singh Brar", notes="INC."),
        term("1996-11-21", "1997-02-12", "elected", party_code=INC, alliance=None,
             cm_name="Rajinder Kaur Bhattal", notes="INC. First woman CM of Punjab."),
        term("1997-02-12", "2002-02-26", "elected", party_code=None, alliance="NDA",
             cm_name="Parkash Singh Badal",
             notes="Shiromani Akali Dal (SAD) in NDA with BJP."),
        term("2002-02-26", "2007-03-01", "elected", party_code=INC, alliance="UPA",
             cm_name="Amarinder Singh", notes="INC."),
        term("2007-03-01", "2017-03-16", "elected", party_code=None, alliance="NDA",
             cm_name="Parkash Singh Badal",
             notes="SAD in NDA with BJP. Two consecutive terms (2007, 2012)."),
        term("2017-03-16", "2021-09-18", "elected", party_code=INC, alliance="UPA",
             cm_name="Amarinder Singh",
             notes="INC. Resigned amid intra-party feud."),
        term("2021-09-20", "2022-03-16", "elected", party_code=INC, alliance=None,
             cm_name="Charanjit Singh Channi",
             notes="INC. First Dalit CM of Punjab."),
        term("2022-03-16", None, "elected", party_code=None, alliance=None,
             cm_name="Bhagwant Mann",
             notes="Aam Aadmi Party (AAP). First non-Congress non-Akali government in decades. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2022/statewise-S19.htm", "note": "2022 result."}]),
    ]
    return write("S19", sources, terms)


def s20_rajasthan():
    sources = [
        wiki_src("List_of_chief_ministers_of_Rajasthan",
                 "List of chief ministers of Rajasthan"),
    ]
    terms = [
        term("1990-03-04", "1992-12-15", "elected", party_code=BJP, alliance=None,
             cm_name="Bhairon Singh Shekhawat",
             notes="BJP. Dismissed when Article 356 was invoked post-Babri."),
        pr("1992-12-15", "1993-12-04", "President's Rule following the demolition of the Babri Masjid."),
        term("1993-12-04", "1998-11-29", "elected", party_code=BJP, alliance=None,
             cm_name="Bhairon Singh Shekhawat", notes="BJP."),
        term("1998-12-01", "2003-12-08", "elected", party_code=INC, alliance=None,
             cm_name="Ashok Gehlot", notes="INC. First term."),
        term("2003-12-08", "2008-12-12", "elected", party_code=BJP, alliance="NDA",
             cm_name="Vasundhara Raje", notes="BJP. First woman CM of Rajasthan."),
        term("2008-12-12", "2013-12-13", "elected", party_code=INC, alliance="UPA",
             cm_name="Ashok Gehlot", notes="INC. Second term."),
        term("2013-12-13", "2018-12-17", "elected", party_code=BJP, alliance="NDA",
             cm_name="Vasundhara Raje", notes="BJP. Second term."),
        term("2018-12-17", "2023-12-15", "elected", party_code=INC, alliance=None,
             cm_name="Ashok Gehlot",
             notes="INC. Third term. Survived the 2020 Sachin Pilot revolt."),
        term("2023-12-15", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Bhajan Lal Sharma",
             notes="BJP. Surprise pick. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S20.htm", "note": "2023 result."}]),
    ]
    return write("S20", sources, terms)


def s21_sikkim():
    sources = [
        wiki_src("List_of_chief_ministers_of_Sikkim",
                 "List of chief ministers of Sikkim"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/5",
         "fetched_at": FETCHED_AT,
         "name": "Sikkim Legislative Assembly Election - 2024",
         "authority": ECI_AUTH},
    ]
    terms = [
        term("1989-03-11", "1994-05-17", "elected", party_code=None, alliance=None,
             cm_name="Nar Bahadur Bhandari",
             notes="Sikkim Sangram Parishad. Multiple terms; lost majority in 1994."),
        term("1994-05-18", "1994-12-12", "elected", party_code=None, alliance=None,
             cm_name="Sanchaman Limboo",
             notes="Sikkim Sangram Parishad."),
        term("1994-12-12", "2019-05-27", "elected", party_code=None, alliance="NDA",
             cm_name="Pawan Kumar Chamling",
             notes="Sikkim Democratic Front (SDF). Five consecutive terms; longest-serving CM in Indian history at time of exit. NDA partner from late 1990s."),
        term("2019-05-27", None, "elected", party_code=None, alliance="NDA",
             cm_name="Prem Singh Tamang",
             notes="Sikkim Krantikari Morcha (SKM) in NDA. Re-elected 2024. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenJune2024/partywiseresult-S21.htm", "note": "2024 partywise result."}]),
    ]
    return write("S21", sources, terms)


def s23_tripura():
    sources = [
        wiki_src("List_of_chief_ministers_of_Tripura",
                 "List of chief ministers of Tripura"),
    ]
    terms = [
        term("1988-02-05", "1993-04-10", "elected", party_code=INC, alliance=None,
             cm_name="Sudhir Ranjan Majumdar",
             notes="INC + TUJS coalition until 1992; Samir Ranjan Barman took over February 1992. Aggregated to single INC-led term for brevity."),
        term("1993-04-10", "2018-03-09", "elected", party_code=CPM, alliance=None,
             cm_name="Manik Sarkar",
             notes="CPI(M)-led Left Front. Five consecutive terms; one of India's longest serving CMs. Successor to Dasarath Deb (1993-1998); Sarkar from 1998."),
        term("2018-03-09", "2022-05-15", "elected", party_code=BJP, alliance="NDA",
             cm_name="Biplab Kumar Deb", notes="BJP."),
        term("2022-05-15", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Manik Saha",
             notes="BJP. Re-elected 2023. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S23.htm", "note": "2023 result."}]),
    ]
    return write("S23", sources, terms)


def s24_uttar_pradesh():
    sources = [
        wiki_src("List_of_chief_ministers_of_Uttar_Pradesh",
                 "List of chief ministers of Uttar Pradesh"),
    ]
    terms = [
        term("1989-12-05", "1991-06-24", "elected", party_code=None, alliance=None,
             cm_name="Mulayam Singh Yadav",
             notes="Janata Dal. Includes Uttarakhand until 9 November 2000 bifurcation."),
        term("1991-06-24", "1992-12-06", "elected", party_code=BJP, alliance=None,
             cm_name="Kalyan Singh",
             notes="BJP. Resigned after the demolition of the Babri Masjid on 6 December 1992."),
        pr("1992-12-06", "1993-12-04", "President's Rule following the demolition of the Babri Masjid."),
        term("1993-12-04", "1995-06-03", "elected", party_code=None,
             alliance=None, cm_name="Mulayam Singh Yadav",
             notes="Samajwadi Party (SP) + BSP coalition. Coalition collapsed in the Guest House Episode of 2 June 1995."),
        term("1995-06-03", "1995-10-18", "elected", party_code=None, alliance=None,
             cm_name="Mayawati",
             notes="BSP (Bahujan Samaj Party). First Dalit woman CM of UP. BJP withdrew support."),
        pr("1995-10-18", "1996-10-21", "President's Rule. Hung assembly."),
        pr("1996-10-21", "1997-03-21", "President's Rule continued during attempts to form a government after the 1996 election."),
        term("1997-03-21", "1997-09-21", "elected", party_code=None, alliance=None,
             cm_name="Mayawati",
             notes="BSP-BJP rotation arrangement. Stepped aside per agreement."),
        term("1997-09-21", "1998-02-21", "elected", party_code=BJP, alliance=None,
             cm_name="Kalyan Singh",
             notes="BJP. Coalition unstable."),
        term("1998-02-21", "1998-02-23", "elected", party_code=None, alliance=None,
             cm_name="Jagdambika Pal",
             notes="INC. 48-hour 'midnight CM' episode; Supreme Court restored Kalyan Singh."),
        term("1998-02-23", "1999-11-12", "elected", party_code=BJP, alliance=None,
             cm_name="Kalyan Singh", notes="BJP."),
        term("1999-11-12", "2000-10-28", "elected", party_code=BJP, alliance=None,
             cm_name="Ram Prakash Gupta", notes="BJP."),
        term("2000-10-28", "2002-03-08", "elected", party_code=BJP, alliance="NDA",
             cm_name="Rajnath Singh", notes="BJP."),
        pr("2002-03-08", "2002-05-03", "President's Rule. Hung assembly after February 2002 election."),
        term("2002-05-03", "2003-08-29", "elected", party_code=None, alliance=None,
             cm_name="Mayawati",
             notes="BSP-BJP coalition. Withdrawn by BSP."),
        term("2003-08-29", "2007-05-13", "elected", party_code=None, alliance=None,
             cm_name="Mulayam Singh Yadav", notes="SP."),
        term("2007-05-13", "2012-03-15", "elected", party_code=None, alliance=None,
             cm_name="Mayawati",
             notes="BSP. First single-party majority government in UP since the 1980s."),
        term("2012-03-15", "2017-03-19", "elected", party_code=None, alliance=None,
             cm_name="Akhilesh Yadav", notes="SP."),
        term("2017-03-19", "2022-03-25", "elected", party_code=BJP, alliance="NDA",
             cm_name="Yogi Adityanath", notes="BJP."),
        term("2022-03-25", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Yogi Adityanath",
             notes="BJP. Second consecutive term — first UP CM in 37 years to be re-elected. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2022/statewise-S24.htm", "note": "2022 result."}]),
    ]
    return write("S24", sources, terms)


def s26_chhattisgarh():
    sources = [
        wiki_src("List_of_chief_ministers_of_Chhattisgarh",
                 "List of chief ministers of Chhattisgarh"),
    ]
    terms = [
        # State formed 1 November 2000 by bifurcation from Madhya Pradesh.
        term("2000-11-01", "2003-12-07", "elected", party_code=INC, alliance=None,
             cm_name="Ajit Jogi",
             notes="INC. First CM of Chhattisgarh; appointed at state formation."),
        term("2003-12-07", "2018-12-17", "elected", party_code=BJP, alliance="NDA",
             cm_name="Raman Singh",
             notes="BJP. Three consecutive terms (2003, 2008, 2013)."),
        term("2018-12-17", "2023-12-13", "elected", party_code=INC, alliance=None,
             cm_name="Bhupesh Baghel", notes="INC."),
        term("2023-12-13", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Vishnu Deo Sai",
             notes="BJP. First Adivasi CM of Chhattisgarh. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S26.htm", "note": "2023 result."}]),
    ]
    return write("S26", sources, terms)


def s27_jharkhand():
    sources = [
        wiki_src("List_of_chief_ministers_of_Jharkhand",
                 "List of chief ministers of Jharkhand"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/9",
         "fetched_at": FETCHED_AT,
         "name": "Jharkhand Legislative Assembly Election 2024",
         "authority": ECI_AUTH},
    ]
    terms = [
        # State formed 15 November 2000 by bifurcation from Bihar.
        term("2000-11-15", "2003-03-18", "elected", party_code=BJP, alliance="NDA",
             cm_name="Babulal Marandi",
             notes="BJP. First CM of Jharkhand; appointed at state formation."),
        term("2003-03-18", "2005-03-02", "elected", party_code=BJP, alliance="NDA",
             cm_name="Arjun Munda", notes="BJP."),
        term("2005-03-02", "2005-03-12", "elected", party_code=None, alliance=None,
             cm_name="Shibu Soren",
             notes="JMM (Jharkhand Mukti Morcha). Brief; failed to prove majority."),
        term("2005-03-12", "2006-09-18", "elected", party_code=BJP, alliance="NDA",
             cm_name="Arjun Munda", notes="BJP."),
        term("2006-09-18", "2008-08-27", "elected", party_code=None, alliance=None,
             cm_name="Madhu Koda",
             notes="Independent + UPA-supported. Later jailed for corruption."),
        term("2008-08-27", "2009-01-18", "elected", party_code=None, alliance=None,
             cm_name="Shibu Soren", notes="JMM."),
        pr("2009-01-19", "2009-12-29", "President's Rule. Government collapse."),
        term("2009-12-30", "2010-05-31", "elected", party_code=None, alliance=None,
             cm_name="Shibu Soren",
             notes="JMM in coalition with BJP. Coalition collapsed."),
        pr("2010-06-01", "2010-09-11", "President's Rule. Coalition collapse."),
        term("2010-09-11", "2013-01-18", "elected", party_code=BJP, alliance="NDA",
             cm_name="Arjun Munda",
             notes="BJP. JMM withdrew support."),
        pr("2013-01-18", "2013-07-13", "President's Rule. Coalition collapse."),
        term("2013-07-13", "2014-12-28", "elected", party_code=None, alliance=None,
             cm_name="Hemant Soren", notes="JMM."),
        term("2014-12-28", "2019-12-29", "elected", party_code=BJP, alliance="NDA",
             cm_name="Raghubar Das",
             notes="BJP. First non-tribal CM of Jharkhand."),
        term("2019-12-29", "2024-01-31", "elected", party_code=None, alliance=None,
             cm_name="Hemant Soren",
             notes="JMM-INC-RJD alliance. Resigned 31 January 2024 ahead of arrest by Enforcement Directorate."),
        term("2024-02-02", "2024-07-04", "elected", party_code=None, alliance=None,
             cm_name="Champai Soren",
             notes="JMM. Caretaker after Hemant Soren's resignation."),
        term("2024-07-04", None, "elected", party_code=None, alliance=None,
             cm_name="Hemant Soren",
             notes="JMM-INC alliance. Returned after bail. Continued after November 2024 election win. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenNov2024/partywiseresult-S27.htm", "note": "2024 partywise result."}]),
    ]
    return write("S27", sources, terms)


def s28_uttarakhand():
    sources = [
        wiki_src("List_of_chief_ministers_of_Uttarakhand",
                 "List of chief ministers of Uttarakhand"),
    ]
    terms = [
        # State formed 9 November 2000 by bifurcation from Uttar Pradesh.
        term("2000-11-09", "2001-10-29", "elected", party_code=BJP, alliance="NDA",
             cm_name="Nityanand Swami",
             notes="BJP. First CM of Uttarakhand."),
        term("2001-10-30", "2002-03-01", "elected", party_code=BJP, alliance="NDA",
             cm_name="Bhagat Singh Koshyari", notes="BJP."),
        term("2002-03-02", "2007-03-07", "elected", party_code=INC, alliance="UPA",
             cm_name="Narayan Datt Tiwari",
             notes="INC. Only CM in state's history to complete a full five-year term until that point."),
        term("2007-03-08", "2009-06-23", "elected", party_code=BJP, alliance="NDA",
             cm_name="Bhuvan Chandra Khanduri", notes="BJP."),
        term("2009-06-23", "2011-09-10", "elected", party_code=BJP, alliance="NDA",
             cm_name="Ramesh Pokhriyal", notes="BJP."),
        term("2011-09-11", "2012-03-13", "elected", party_code=BJP, alliance="NDA",
             cm_name="Bhuvan Chandra Khanduri", notes="BJP. Brief return."),
        term("2012-03-13", "2014-01-31", "elected", party_code=INC, alliance="UPA",
             cm_name="Vijay Bahuguna",
             notes="INC. Resigned over response to 2013 Uttarakhand floods."),
        term("2014-02-01", "2017-03-18", "elected", party_code=INC, alliance="UPA",
             cm_name="Harish Rawat",
             notes="INC. Brief 2016 PR spell during Article 356 dispute."),
        pr("2016-03-27", "2016-05-11", "President's Rule. Imposed amid Congress defections; Supreme Court later restored Harish Rawat."),
        term("2017-03-18", "2021-03-10", "elected", party_code=BJP, alliance="NDA",
             cm_name="Trivendra Singh Rawat", notes="BJP."),
        term("2021-03-10", "2021-07-04", "elected", party_code=BJP, alliance="NDA",
             cm_name="Tirath Singh Rawat",
             notes="BJP. Resigned over not being a sitting MLA within 6 months."),
        term("2021-07-04", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Pushkar Singh Dhami",
             notes="BJP. Re-elected 2022. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2022/statewise-S28.htm", "note": "2022 result."}]),
    ]
    return write("S28", sources, terms)


def s29_telangana():
    sources = [
        wiki_src("List_of_chief_ministers_of_Telangana",
                 "List of chief ministers of Telangana"),
    ]
    terms = list(AP_UNIFIED) + [
        term("2014-06-02", "2018-12-13", "elected", party_code=None, alliance=None,
             cm_name="K. Chandrashekar Rao",
             notes="Telangana Rashtra Samithi (TRS); renamed Bharat Rashtra Samithi (BRS) in 2022. First CM of Telangana state."),
        term("2018-12-13", "2023-12-07", "elected", party_code=None, alliance=None,
             cm_name="K. Chandrashekar Rao",
             notes="TRS / BRS. Second term."),
        term("2023-12-07", None, "elected", party_code=INC, alliance=None,
             cm_name="A. Revanth Reddy",
             notes="INC. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/Result2023/statewise-S29.htm", "note": "2023 result."}]),
    ]
    return write("S29", sources, terms)


def u05_delhi():
    sources = [
        wiki_src("List_of_chief_ministers_of_Delhi",
                 "List of chief ministers of Delhi"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2025/10",
         "fetched_at": FETCHED_AT,
         "name": "NCT of Delhi Legislative Assembly Election 2025",
         "authority": ECI_AUTH},
    ]
    terms = [
        # NCT of Delhi got an elected legislative assembly under the 1991
        # 69th Constitutional Amendment; first CM was Madan Lal Khurana
        # sworn in 2 December 1993.
        term("1993-12-02", "1996-02-26", "elected", party_code=BJP, alliance=None,
             cm_name="Madan Lal Khurana",
             notes="BJP. First CM of NCT of Delhi under the 1991 constitutional arrangement. Resigned over Jain hawala case."),
        term("1996-02-26", "1998-10-12", "elected", party_code=BJP, alliance=None,
             cm_name="Sahib Singh Verma",
             notes="BJP. Resigned ahead of November 1998 election after onion-price crisis."),
        term("1998-10-12", "1998-12-03", "elected", party_code=BJP, alliance=None,
             cm_name="Sushma Swaraj",
             notes="BJP. Brief term ahead of election; lost it."),
        term("1998-12-03", "2013-12-28", "elected", party_code=INC, alliance=None,
             cm_name="Sheila Dikshit",
             notes="INC. Three consecutive terms (1998, 2003, 2008)."),
        term("2013-12-28", "2014-02-14", "elected", party_code=None, alliance=None,
             cm_name="Arvind Kejriwal",
             notes="AAP (Aam Aadmi Party). 49-day first term; resigned over Jan Lokpal Bill."),
        pr("2014-02-14", "2015-02-14", "President's Rule. After Kejriwal's resignation, no party formed government; lasted until February 2015 election."),
        term("2015-02-14", "2024-09-21", "elected", party_code=None, alliance=None,
             cm_name="Arvind Kejriwal",
             notes="AAP. Two consecutive terms (2015, 2020). Resigned 21 September 2024 after release on bail in liquor-policy case."),
        term("2024-09-21", "2025-02-20", "elected", party_code=None, alliance=None,
             cm_name="Atishi",
             notes="AAP. Caretaker until February 2025 election."),
        term("2025-02-20", None, "elected", party_code=BJP, alliance="NDA",
             cm_name="Rekha Gupta",
             notes="BJP. First BJP CM of Delhi in 27 years. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenFeb2025/partywiseresult-U05.htm", "note": "2025 partywise result."}]),
    ]
    return write("U05", sources, terms)


def u07_puducherry():
    sources = [
        wiki_src("List_of_chief_ministers_of_Puducherry",
                 "List of chief ministers of Puducherry"),
    ]
    terms = [
        term("1990-03-04", "1991-03-03", "elected", party_code=None, alliance=None,
             cm_name="D. Ramachandran",
             notes="DMK + INC coalition."),
        pr("1991-03-04", "1991-07-04", "President's Rule before June 1991 election."),
        term("1991-07-04", "1996-05-13", "elected", party_code=INC, alliance=None,
             cm_name="V. Vaithilingam", notes="INC."),
        term("1996-05-26", "2000-03-22", "elected", party_code=None, alliance=None,
             cm_name="R. V. Janakiraman",
             notes="DMK in alliance with INC and TMC(M)."),
        term("2000-03-22", "2001-05-14", "elected", party_code=None, alliance=None,
             cm_name="P. Shanmugam", notes="DMK."),
        term("2001-05-14", "2008-09-04", "elected", party_code=None, alliance=None,
             cm_name="N. Rangaswamy",
             notes="INC, then All India N.R. Congress (AINRC) from 2011. Won 2006 as INC."),
        term("2008-09-04", "2011-05-16", "elected", party_code=INC, alliance="UPA",
             cm_name="V. Vaithilingam", notes="INC."),
        term("2011-05-16", "2016-06-06", "elected", party_code=None, alliance="NDA",
             cm_name="N. Rangaswamy",
             notes="AINRC (All India N.R. Congress) in alliance with AIADMK and BJP."),
        term("2016-06-06", "2021-02-22", "elected", party_code=INC, alliance=None,
             cm_name="V. Narayanasamy",
             notes="INC. Lost majority after defections; resigned before floor test."),
        pr("2021-02-25", "2021-05-07", "President's Rule. Hung assembly after Narayanasamy's resignation; held until April 2021 election."),
        term("2021-05-07", None, "elected", party_code=None, alliance="NDA",
             cm_name="N. Rangaswamy",
             notes="AINRC in alliance with BJP. Continuing through May 2026 election cycle. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-U07.htm", "note": "2026 partywise result."}]),
    ]
    return write("U07", sources, terms)


def u08_jammu_and_kashmir():
    sources = [
        wiki_src("List_of_chief_ministers_of_Jammu_and_Kashmir",
                 "List of chief ministers of Jammu and Kashmir"),
        {"url": "https://www.eci.gov.in/statistical-report/ae/2024/7",
         "fetched_at": FETCHED_AT,
         "name": "Jammu and Kashmir Legislative Assembly Election - 2024",
         "authority": ECI_AUTH},
    ]
    terms = [
        pr("1990-01-19", "1996-10-09", "Governor's Rule (later President's Rule from 18 July 1990) at the height of the Kashmir insurgency. Lasted nearly seven years until restoration of elected government after September 1996 elections."),
        term("1996-10-09", "2002-10-18", "elected", party_code=None, alliance=None,
             cm_name="Farooq Abdullah",
             notes="JKN (Jammu & Kashmir National Conference). Aligned with NDA from 1999."),
        pr("2002-10-18", "2002-11-02", "Governor's Rule between elections."),
        term("2002-11-02", "2005-11-02", "elected", party_code=None, alliance=None,
             cm_name="Mufti Mohammad Sayeed",
             notes="JKPDP (Jammu & Kashmir People's Democratic Party) - INC coalition. Rotation arrangement."),
        term("2005-11-02", "2008-07-11", "elected", party_code=INC, alliance="UPA",
             cm_name="Ghulam Nabi Azad",
             notes="INC. Coalition collapsed over Amarnath land transfer protests."),
        pr("2008-07-11", "2009-01-05", "Governor's Rule following Azad's resignation."),
        term("2009-01-05", "2014-12-23", "elected", party_code=None, alliance=None,
             cm_name="Omar Abdullah",
             notes="JKN-INC coalition."),
        pr("2014-12-23", "2015-03-01", "Governor's Rule before government formation."),
        term("2015-03-01", "2016-01-07", "elected", party_code=None, alliance=None,
             cm_name="Mufti Mohammad Sayeed",
             notes="JKPDP-BJP coalition. Died in office."),
        pr("2016-01-08", "2016-04-04", "Governor's Rule following Mufti's death."),
        term("2016-04-04", "2018-06-19", "elected", party_code=None, alliance=None,
             cm_name="Mehbooba Mufti",
             notes="JKPDP-BJP coalition. BJP withdrew support; coalition collapsed."),
        pr("2018-06-19", "2024-10-16", "Governor's Rule (then President's Rule from 19 December 2018). Special status (Article 370) abrogated 5 August 2019; J&K reorganised as a Union Territory effective 31 October 2019. No elected legislative assembly until October 2024."),
        term("2024-10-16", None, "elected", party_code=None, alliance=None,
             cm_name="Omar Abdullah",
             notes="JKN-INC alliance. First elected CM of J&K UT under post-2019 arrangement; UT-CM has reduced powers vs the prior state arrangement. Ongoing.",
             references=[{"url": "https://results.eci.gov.in/AcResultGenOct2024/partywiseresult-U08.htm", "note": "2024 partywise result."}]),
    ]
    return write("U08", sources, terms)


# ---------------------------------------------------------------------------

AUTHORS = [
    s01_andhra_pradesh, s02_arunachal_pradesh, s04_bihar, s05_goa,
    s06_gujarat, s07_haryana, s08_himachal_pradesh, s10_karnataka,
    s12_madhya_pradesh, s13_maharashtra, s14_manipur, s15_meghalaya,
    s16_mizoram, s17_nagaland, s18_odisha, s19_punjab, s20_rajasthan,
    s21_sikkim, s23_tripura, s24_uttar_pradesh, s26_chhattisgarh,
    s27_jharkhand, s28_uttarakhand, s29_telangana, u05_delhi,
    u07_puducherry, u08_jammu_and_kashmir,
]


if __name__ == "__main__":
    for fn in AUTHORS:
        path = fn()
        rel = path.relative_to(REPO).as_posix()
        doc = json.loads(path.read_text(encoding="utf-8"))
        print(f"  wrote {rel}  ({len(doc['terms'])} terms)")
    print(f"\nTotal: {len(AUTHORS)} cm_terms.json files written.")
