"""Add newly-ingested states to per-event ``datasets/events/in/eci/<event>/
election.json`` metadata, creating missing event files where needed.

Idempotent: each event's ``states[]`` is updated to the union of existing +
expected, sorted. New event files are written with the standard envelope.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "datasets" / "events" / "in" / "eci"

# event_id -> (year, month, states_to_ensure)
ENSURE: dict[str, tuple[int, int, list[str]]] = {
    "AcGenMay2016": (2016, 5, ["U07", "S22"]),
    "AcGenFeb2017": (2017, 2, ["S19", "S24", "S28"]),
    "AcGenMar2017": (2017, 3, ["S14"]),
    "AcGenDec2017": (2017, 12, ["S06"]),
    "AcGenFeb2018": (2018, 2, ["S23"]),
    "AcGenApr2021": (2021, 4, ["U07", "S22"]),
    "AcGenFeb2022": (2022, 2, ["S19", "S24", "S28"]),
    "AcGenMar2022": (2022, 3, ["S14"]),
    "AcGenDec2022": (2022, 12, ["S06"]),
    "AcGenFeb2023": (2023, 2, ["S15", "S17", "S23"]),
    "AcGenNov2023": (2023, 11, ["S20"]),
}


def main() -> int:
    created = 0
    updated = 0
    unchanged = 0
    for event_id, (year, month, states) in ENSURE.items():
        path = EVENTS_DIR / event_id / "election.json"
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
            existing = set(doc.get("states") or [])
            new_states = sorted(existing | set(states))
            if new_states != sorted(existing):
                doc["states"] = new_states
                path.write_text(
                    json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                updated += 1
                print(f"updated {event_id}: states={new_states}")
            else:
                unchanged += 1
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = {
                "$schema": "https://yen-gov.github.io/schemas/election.schema.json",
                "$schema_version": "3.1",
                "sources": [],
                "eci_event_id": event_id,
                "scope": "state",
                "body": "AC",
                "year": year,
                "month": month,
                "states": sorted(states),
            }
            path.write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            created += 1
            print(f"created {event_id}: states={sorted(states)}")
    print(f"\ncreated={created} updated={updated} unchanged={unchanged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
