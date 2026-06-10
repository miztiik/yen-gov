"""Historical-state slug crosswalk for India's post-Independence state-formation events.

Pure function `historical_state_slug(constituency_entity_id, event_year) -> str`.
Given a constituency `entity_id` (e.g. ``IN-PC-2008-S26-1`` for a Chhattisgarh PC
or ``IN-AC-2008-S22-167`` for a Tamil Nadu AC) and the year of an election
event, returns the URL/partition slug of the state that owned the constituency
on `event_year-01-01`.

Algorithm
---------
1. Parse the constituency's CURRENT ECI state code from the entity_id.
   Format: ``IN-(PC|AC)-<delim_year>-<state_code>-<eci_no>``; the state code
   is the 4th hyphen-separated segment matching ``^[SU]\\d{2}$``.
2. Walk the formation events from
   ``datasets/taxonomy/state_formation_events.json`` (sorted ASCENDING by
   ``event_date``).
3. For each event: if the constituency's current state code is in
   ``successor_state_ids`` AND ``event_year < year(event_date)``, the
   constituency historically belonged to the FIRST parent state (per the
   carve-out doctrine: the carved-out child returns its rows to the
   surviving parent). The historical slug is
   ``<parent-modern-slug>-<parent_window_start_year>-<year(event_date) - 1>``.
   The ``parent_window_start_year`` is the editorial start year carried
   on the event row itself (e.g. 1947 for the three 2000 carve-outs of
   MP/UP/Bihar; 1956 for the AP/Telangana 2014 split; 1962 for the
   Goa-Daman-Diu 1987 split). Returning at the FIRST matching event
   walks the lineage backwards correctly when a constituency lives in
   a successor of a successor.
4. If no formation event applies (the year is on/after every formation
   date for the constituency's state, OR the state has no formation
   history), return the constituency's modern-state slug.

The function is PURE -- no side effects, no I/O beyond the one cached JSON
read on first call.

Authored for PR-W1b of TODO/20260609-election-experience-overhaul-plan.md.
ECI codes pinned against the on-disk taxonomy at
``datasets/taxonomy/entities.json`` (Holy Law #3); see the catalogue's
per-row ``notes`` for the brief-vs-on-disk reconciliation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# -----------------------------------------------------------------------------
# Modern-state slug lookup table
# -----------------------------------------------------------------------------
#
# 36 entries -- one per current state (28) and UT (8) row on
# datasets/taxonomy/entities.json. Hand-authored so the helper does not pull
# in the full taxonomy loader (a transitive dep) for a 36-row map. When the
# spine adds or renames a state/UT, update this table in the SAME commit
# (the parity with entities.json is enforced by the test suite).

MODERN_STATE_SLUG_BY_ECI_CODE: dict[str, str] = {
    # States (28 current + S09 historical Jammu and Kashmir state pre-2019)
    "S01": "andhra-pradesh",
    "S02": "arunachal-pradesh",
    "S03": "assam",
    "S04": "bihar",
    "S05": "goa",
    "S06": "gujarat",
    "S07": "haryana",
    "S08": "himachal-pradesh",
    "S09": "jammu-and-kashmir",  # historical state code (pre-2019 J&K state)
    "S10": "karnataka",
    "S11": "kerala",
    "S12": "madhya-pradesh",
    "S13": "maharashtra",
    "S14": "manipur",
    "S15": "meghalaya",
    "S16": "mizoram",
    "S17": "nagaland",
    "S18": "odisha",
    "S19": "punjab",
    "S20": "rajasthan",
    "S21": "sikkim",
    "S22": "tamil-nadu",
    "S23": "tripura",
    "S24": "uttar-pradesh",
    "S25": "west-bengal",
    "S26": "chhattisgarh",
    "S27": "jharkhand",
    "S28": "uttarakhand",
    "S29": "telangana",
    # Union Territories with a current row on entities.json (8)
    "U01": "andaman-and-nicobar",
    "U02": "chandigarh",
    "U03": "dadra-and-nagar-haveli-and-daman-and-diu",
    "U04": "lakshadweep",
    "U05": "delhi",
    "U07": "puducherry",
    "U08": "jammu-and-kashmir",  # current J&K UT (post-2019 reorganisation)
    "U09": "ladakh",
}

# Historical entities (no current entities.json row; carried by the
# state-formation events catalogue's parent_state_ids). Used to render
# the parent state's modern slug when the helper resolves backwards
# through a formation event whose parent has since dissolved (the
# pre-1987 Goa-Daman-Diu UT case).
HISTORICAL_PARENT_SLUG_BY_ECI_CODE: dict[str, str] = {
    "U06": "goa-daman-and-diu",
}

# Default catalogue path -- the worktree-relative source of truth.
DEFAULT_CATALOGUE_PATH = Path("datasets/taxonomy/state_formation_events.json")


@dataclass(frozen=True)
class FormationEvent:
    """A single state-formation event in canonical comparison order."""

    event_id: str
    parent_state_ids: tuple[str, ...]
    successor_state_ids: tuple[str, ...]
    event_year: int  # year(event_date) for the comparison axis
    event_date: str  # ISO date string for diagnostics
    parent_window_start_year: int  # editorial historical-slug window start


@lru_cache(maxsize=4)
def _load_events(catalogue_path: str) -> tuple[FormationEvent, ...]:
    """Load and freeze the formation-events catalogue, sorted by date asc."""
    raw = json.loads(Path(catalogue_path).read_text(encoding="utf-8"))
    rows = raw.get("events", [])
    events: list[FormationEvent] = []
    for row in rows:
        date_str = row["event_date"]
        year = int(date_str.split("-", 1)[0])
        events.append(
            FormationEvent(
                event_id=row["event_id"],
                parent_state_ids=tuple(row["parent_state_ids"]),
                successor_state_ids=tuple(row["successor_state_ids"]),
                event_year=year,
                event_date=date_str,
                parent_window_start_year=int(row["parent_window_start_year"]),
            )
        )
    events.sort(key=lambda e: e.event_date)
    return tuple(events)


def _parse_state_code(entity_id: str) -> str:
    """Extract the current ECI state code from a constituency entity_id.

    Accepts the canonical electoral entity_id shapes:
      - ``IN-PC-<delim_year>-<state_code>-<eci_no>`` (parliament)
      - ``IN-AC-<delim_year>-<state_code>-<eci_no>`` (assembly)

    Returns the 4th hyphen-separated segment. Raises ValueError if the
    segment does not look like an ECI state code (``^[SU]\\d{2}$``).
    """
    parts = entity_id.split("-")
    if len(parts) < 5 or parts[0] != "IN" or parts[1] not in ("PC", "AC"):
        raise ValueError(
            f"entity_id {entity_id!r} does not match the IN-(PC|AC)-<delim>-<state>-<eci_no> shape"
        )
    state_code = parts[3]
    if len(state_code) != 3 or state_code[0] not in ("S", "U") or not state_code[1:].isdigit():
        raise ValueError(
            f"entity_id {entity_id!r} carries non-conforming state code {state_code!r}; expected ^[SU]\\d{{2}}$"
        )
    return state_code


def _modern_slug(state_code: str) -> str:
    """Modern-state slug for a current ECI state/UT code.

    Falls back to the historical-parent lookup for codes that are not
    on the current spine (e.g. U06 Goa-Daman-Diu pre-1987).
    """
    if state_code in MODERN_STATE_SLUG_BY_ECI_CODE:
        return MODERN_STATE_SLUG_BY_ECI_CODE[state_code]
    if state_code in HISTORICAL_PARENT_SLUG_BY_ECI_CODE:
        return HISTORICAL_PARENT_SLUG_BY_ECI_CODE[state_code]
    raise KeyError(
        f"ECI state code {state_code!r} is unknown to MODERN_STATE_SLUG_BY_ECI_CODE; "
        "update backend/yen_gov/canonical/historical_state_slug.py if the spine has "
        "added a new state/UT row."
    )


def historical_state_slug(
    constituency_entity_id: str,
    event_year: int,
    *,
    catalogue_path: str | Path = DEFAULT_CATALOGUE_PATH,
) -> str:
    """Return the historical-state slug for one (constituency, year) pair.

    See module docstring for the algorithm and the historical-slug shape.
    Pure function; the only I/O is one cached JSON read per `catalogue_path`.

    Parameters
    ----------
    constituency_entity_id : str
        Canonical electoral entity_id, e.g. ``IN-PC-2008-S26-1`` or
        ``IN-AC-2008-S22-167``.
    event_year : int
        Year the election was held (e.g. 1952, 2024). Compared against
        each formation event's year (the year-component of `event_date`).
    catalogue_path : str | Path
        Override for the events catalogue. Defaults to the worktree-relative
        ``datasets/taxonomy/state_formation_events.json``.
    """
    state_code = _parse_state_code(constituency_entity_id)
    events = _load_events(str(catalogue_path))

    for event in events:
        if state_code not in event.successor_state_ids:
            continue
        if event_year >= event.event_year:
            continue
        # The constituency belonged to the parent state at that date.
        # By construction every formation event in the canonical
        # catalogue has exactly one parent (`minItems: 1` is the
        # schema floor; the actual seed is 1-parent everywhere).
        parent_code = event.parent_state_ids[0]
        parent_slug = _modern_slug(parent_code)
        parent_window_end = event.event_year - 1
        return f"{parent_slug}-{event.parent_window_start_year}-{parent_window_end}"

    return _modern_slug(state_code)
