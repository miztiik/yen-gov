"""Register 19 newly-ingested ECI Section-10 state-assembly events into
`datasets/reference/in/election-events.json`.

Idempotent: skips any (state_code, event_id) already present. Preserves
existing entries' field order and `default: true` markers. Sorts events
within each state array by `polled_on` ascending.

Sources for polling dates: ECI press notes + state EC notifications,
cross-referenced with Wikipedia state-assembly-election pages
(all single- or multi-phase first-phase dates).

Run once after the 2016-2023 backfill:

    python tools/register_2016_2023_ae_events.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

CAT = (
    Path(__file__).resolve().parents[1]
    / "datasets" / "reference" / "in" / "election-events.json"
)

# (state_code, event_id, polled_on_iso, display, notes)
# polled_on is the FIRST polling phase when multi-phase.
NEW_EVENTS: list[tuple[str, str, str, str, str]] = [
    ("U07", "AcGenMay2016", "2016-05-16",
     "Puducherry Assembly \u00b7 May 2016",
     "Single-phase poll on 16 May 2016. 30 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S22", "AcGenMay2016", "2016-05-16",
     "Tamil Nadu Assembly \u00b7 May 2016",
     "Single-phase poll on 16 May 2016. 232 ACs (Aravakurichi and "
     "Thanjavur countermanded; held 19 Nov 2016). Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S19", "AcGenFeb2017", "2017-02-04",
     "Punjab Assembly \u00b7 February 2017",
     "Single-phase poll on 4 February 2017. 117 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S24", "AcGenFeb2017", "2017-02-11",
     "Uttar Pradesh Assembly \u00b7 February-March 2017",
     "Seven-phase poll: 11 Feb \u2013 8 Mar 2017. 403 ACs. Ingested "
     "from hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S28", "AcGenFeb2017", "2017-02-15",
     "Uttarakhand Assembly \u00b7 February 2017",
     "Single-phase poll on 15 February 2017. 70 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S14", "AcGenMar2017", "2017-03-04",
     "Manipur Assembly \u00b7 March 2017",
     "Two-phase poll: 4 March, 8 March 2017. 60 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S06", "AcGenDec2017", "2017-12-09",
     "Gujarat Assembly \u00b7 December 2017",
     "Two-phase poll: 9 December, 14 December 2017. 182 ACs. Ingested "
     "from hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S23", "AcGenFeb2018", "2018-02-18",
     "Tripura Assembly \u00b7 February 2018",
     "Single-phase poll on 18 February 2018. 60 ACs (Charilam "
     "countermanded; held 12 March 2018). Ingested from hand-downloaded "
     "ECI Section-10 Statistical Report XLSX."),
    ("U07", "AcGenApr2021", "2021-04-06",
     "Puducherry Assembly \u00b7 April 2021",
     "Single-phase poll on 6 April 2021. 30 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S22", "AcGenApr2021", "2021-04-06",
     "Tamil Nadu Assembly \u00b7 April 2021",
     "Single-phase poll on 6 April 2021. 234 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S19", "AcGenFeb2022", "2022-02-20",
     "Punjab Assembly \u00b7 February 2022",
     "Single-phase poll on 20 February 2022. 117 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S24", "AcGenFeb2022", "2022-02-10",
     "Uttar Pradesh Assembly \u00b7 February-March 2022",
     "Seven-phase poll: 10 February \u2013 7 March 2022. 403 ACs. "
     "Ingested from hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S28", "AcGenFeb2022", "2022-02-14",
     "Uttarakhand Assembly \u00b7 February 2022",
     "Single-phase poll on 14 February 2022. 70 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S14", "AcGenMar2022", "2022-02-28",
     "Manipur Assembly \u00b7 February-March 2022",
     "Two-phase poll: 28 February, 5 March 2022. 60 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S06", "AcGenDec2022", "2022-12-01",
     "Gujarat Assembly \u00b7 December 2022",
     "Two-phase poll: 1 December, 5 December 2022. 182 ACs. Ingested "
     "from hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S15", "AcGenFeb2023", "2023-02-27",
     "Meghalaya Assembly \u00b7 February 2023",
     "Single-phase poll on 27 February 2023. 59 ACs (Sohiong "
     "countermanded; held 22 May 2023). Ingested from hand-downloaded "
     "ECI Section-10 Statistical Report XLSX."),
    ("S17", "AcGenFeb2023", "2023-02-27",
     "Nagaland Assembly \u00b7 February 2023",
     "Single-phase poll on 27 February 2023. 59 ACs (Akuluto seat "
     "uncontested). Ingested from hand-downloaded ECI Section-10 "
     "Statistical Report XLSX."),
    ("S23", "AcGenFeb2023", "2023-02-16",
     "Tripura Assembly \u00b7 February 2023",
     "Single-phase poll on 16 February 2023. 60 ACs. Ingested from "
     "hand-downloaded ECI Section-10 Statistical Report XLSX."),
    ("S20", "AcGenNov2023", "2023-11-25",
     "Rajasthan Assembly \u00b7 November 2023",
     "Single-phase poll on 25 November 2023. 199 ACs (Karanpur "
     "countermanded; held 5 January 2024). Ingested from hand-downloaded "
     "ECI Section-10 Statistical Report XLSX."),
]


def plus_5y_minus_1d(iso: str) -> str:
    d = date.fromisoformat(iso)
    try:
        end = d.replace(year=d.year + 5) - timedelta(days=1)
    except ValueError:  # leap-day edge
        end = d.replace(year=d.year + 5, day=28) - timedelta(days=1)
    return end.isoformat()


def main() -> int:
    doc = json.loads(CAT.read_text(encoding="utf-8"))
    states = doc["states"]

    added = 0
    skipped = 0
    for state_code, event_id, polled_on, display, notes in NEW_EVENTS:
        bucket = states.setdefault(state_code, [])
        if any(e.get("event_id") == event_id for e in bucket):
            skipped += 1
            continue
        bucket.append({
            "event_id": event_id,
            "kind": "assembly",
            "display": display,
            "polled_on": polled_on,
            "term_end_estimated": plus_5y_minus_1d(polled_on),
            "data_status": "complete",
            "notes": notes,
        })
        added += 1

    # Sort each state's events by polled_on ascending; preserve `default: true`.
    for code, bucket in states.items():
        bucket.sort(key=lambda e: e.get("polled_on") or "")

    CAT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"added={added} skipped={skipped} total_states={len(states)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
