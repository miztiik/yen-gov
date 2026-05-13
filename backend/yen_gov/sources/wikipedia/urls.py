"""URL conventions for en.wikipedia.org pages we scrape.

Two page families today:

  - "List of districts of <State>"                       → districts page
  - "List of constituencies of the <State> Legislative Assembly"
                                                         → AC constituencies

State names use Wikipedia's English title casing (e.g. "Tamil Nadu").
The slug uses underscores, not spaces, and is case-sensitive.

Per docs/architecture/backend/sources-wikipedia.md we map ECI state code → Wikipedia state name via a small
adapter-local table, NOT via a generic name-lookup. The mapping is finite
(36 states/UTs), changes never, and an explicit table fails loudly when
asked about a missing state.
"""

from __future__ import annotations

from urllib.parse import quote

WIKIPEDIA_BASE = "https://en.wikipedia.org/wiki"

# ECI state code → Wikipedia article name (canonical English title).
# Filled out as we add support for each state. Holy Law #6 (no hardcoded
# taxonomy) is satisfied by treating this as adapter-local routing data,
# not as user-facing taxonomy — the user-facing names live in state.schema.json
# data files.
_ECI_TO_WIKI_STATE: dict[str, str] = {
    "S01": "Andhra Pradesh",
    "S02": "Arunachal Pradesh",
    "S03": "Assam",
    "S04": "Bihar",
    "S05": "Goa",
    "S06": "Gujarat",
    "S07": "Haryana",
    "S08": "Himachal Pradesh",
    "S10": "Karnataka",
    "S11": "Kerala",
    "S12": "Madhya Pradesh",
    "S13": "Maharashtra",
    "S14": "Manipur",
    "S15": "Meghalaya",
    "S16": "Mizoram",
    "S17": "Nagaland",
    "S18": "Odisha",
    "S19": "Punjab",
    "S20": "Rajasthan",
    "S21": "Sikkim",
    "S22": "Tamil Nadu",
    "S23": "Tripura",
    "S24": "Uttar Pradesh",
    "S25": "West Bengal",
    "S26": "Chhattisgarh",
    "S27": "Jharkhand",
    "S28": "Uttarakhand",
    "S29": "Telangana",
    "U01": "Andaman and Nicobar Islands",
    "U02": "Chandigarh",
    "U03": "Dadra and Nagar Haveli and Daman and Diu",
    "U04": "Lakshadweep",
    "U05": "Delhi",
    "U07": "Puducherry",
    "U08": "Jammu and Kashmir",
    "U09": "Ladakh",
}


def _wiki_state_name(state_code: str) -> str:
    name = _ECI_TO_WIKI_STATE.get(state_code)
    if name is None:
        raise ValueError(
            f"no Wikipedia state-name mapping for ECI code {state_code!r}; "
            f"add it to sources/wikipedia/urls.py:_ECI_TO_WIKI_STATE"
        )
    return name


def _slug(article_title: str) -> str:
    return quote(article_title.replace(" ", "_"), safe="_(),")


def districts_url(state_code: str) -> str:
    """Wikipedia 'List of districts of <State>' article."""
    state = _wiki_state_name(state_code)
    return f"{WIKIPEDIA_BASE}/{_slug(f'List of districts of {state}')}"


def ac_constituencies_url(state_code: str) -> str:
    """Wikipedia 'List of constituencies of the <State> Legislative Assembly' article."""
    state = _wiki_state_name(state_code)
    return f"{WIKIPEDIA_BASE}/{_slug(f'List of constituencies of the {state} Legislative Assembly')}"


__all__ = ["WIKIPEDIA_BASE", "ac_constituencies_url", "districts_url"]
