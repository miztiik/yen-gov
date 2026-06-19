"""ICED state-name → ECI state-id mapping + small numeric helpers.

ICED writes state names as plain English ("Tamil Nadu", "Delhi", "Andaman
and Nicobar Islands"). yen-gov uses ECI codes everywhere downstream
(``S22``, ``U05``, ``U01``). One canonical translation table lives here so
every parser uses the same mapping; new endpoints only need to add a
synonym if ICED ever spells a state differently between pages.

``ENTITY_MAP`` covers all 28 states + 8 UTs + ``All India → IN``. It is
the union of every ``states[]`` array we have observed across every probed
endpoint as of 2026-05-14.
"""
from __future__ import annotations

import re
from typing import Any


# ICED → ECI/state-id mapping. Keys are names as they appear in the API's
# `states` arrays; values are entity_ids used throughout yen-gov.
ENTITY_MAP: dict[str, str] = {
    "All India": "IN",
    "India": "IN",
    # 28 states (ECI S-codes)
    "Andhra Pradesh": "S01",
    "Arunachal Pradesh": "S02",
    "Assam": "S03",
    "Bihar": "S04",
    "Goa": "S05",
    "Gujarat": "S06",
    "Haryana": "S07",
    "Himachal Pradesh": "S08",
    "Karnataka": "S10",
    "Kerala": "S11",
    "Madhya Pradesh": "S12",
    "Maharashtra": "S13",
    "Manipur": "S14",
    "Meghalaya": "S15",
    "Mizoram": "S16",
    "Nagaland": "S17",
    "Odisha": "S18",
    "Orissa": "S18",                 # Pre-2011 spelling, occasionally used.
    "Punjab": "S19",
    "Rajasthan": "S20",
    "Sikkim": "S21",
    "Tamil Nadu": "S22",
    "Tamilnadu": "S22",              # One-word spelling, observed on aqi-map-markers.
    "Tripura": "S23",
    "Uttar Pradesh": "S24",
    "West Bengal": "S25",
    "Chhattisgarh": "S26",
    "Chattisgarh": "S26",            # Variant spelling.
    "Chhatisgarh": "S26",            # Single-'t' typo, observed on the FGD endpoint.
    "Jharkhand": "S27",
    "Uttarakhand": "S28",
    "Uttaranchal": "S28",            # Pre-2007 name, sometimes lingers.
    "Telangana": "S29",
    # 8 UTs (ECI U-codes). ICED's "Delhi" is ECI's "NCT of Delhi".
    "Andaman and Nicobar Islands": "U01",
    "Andaman & Nicobar Islands": "U01",
    "Chandigarh": "U02",
    "Dadra and Nagar Haveli and Daman and Diu": "U03",
    "Dadra & Nagar Haveli and Daman & Diu": "U03",
    "DNH and DD": "U03",
    # Pre-2020 the two halves were separate UTs (legacy ECI U07 / U08); the
    # markers feed retains the old per-half spellings on stations measured
    # before the merger. We collapse them onto the post-merger entity U03 —
    # keeping the legacy codes alive would orphan station-years from charts
    # that only know the current entity. State-year aggregation simply means
    # those station-years are pooled into one U03 mean.
    "Dadra & Nagar Haveli": "U03",
    "Dadra and Nagar Haveli": "U03",
    "Daman & Diu": "U03",
    "Daman and Diu": "U03",
    "Lakshadweep": "U04",
    "Delhi": "U05",
    "NCT of Delhi": "U05",
    "Puducherry": "U07",
    "Pondicherry": "U07",            # Pre-2006 name.
    "Jammu and Kashmir": "U08",
    "Jammu & Kashmir": "U08",
    "Ladakh": "U09",
}


# Null sentinels that ICED emits in numeric cells (Indian formatting + ASCII).
_NULL_TOKENS = frozenset({
    "", "-", "—", "N.A.", "N.A", "NA", "n.a.", "na", "..", "...", "*", "null", "None"
})


def coerce_numeric(raw: Any) -> float | None:
    """Convert one ICED cell value to a float, or ``None`` for null tokens.

    Handles Indian-grouped decimals (``"1,23,456.78"``), western-grouped
    decimals (``"123,456.78"``), bare floats, and the full set of
    null-token strings the API uses interchangeably.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):                     # bool is a subclass of int
        return float(raw)
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if text in _NULL_TOKENS:
        return None
    cleaned = text.replace(",", "").replace("\u2009", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


_FY_RE = re.compile(r"^(\d{4})-(\d{2})$")


def fy_to_period(fy_label: str) -> str:
    """Canonicalise an ICED ``YYYY-YY`` FY label to ``YYYY-04`` (start-of-FY).

    ``"2024-25" -> "2024-04"``. Raises :class:`ValueError` if the label is
    not in the ``YYYY-YY`` form. Indian fiscal year runs April–March, so
    the start month is 04.
    """
    m = _FY_RE.match(fy_label)
    if not m:
        raise ValueError(f"FY label {fy_label!r} does not match YYYY-YY")
    return f"{int(m.group(1)):04d}-04"


# Case-insensitive lookup index. Some endpoints (e.g. the v0
# ``/energy/fuel-sources/coal/consumption-domestic-state`` family) ship
# state names in UPPERCASE; others use Title Case. We keep ENTITY_MAP
# in canonical Title Case (it is the human-readable form) and provide
# this helper so per-source parsers don't each have to title-case +
# fix-and-of-of words manually.
_ENTITY_MAP_CI: dict[str, str] = {k.lower(): v for k, v in ENTITY_MAP.items()}


def lookup_entity(label: str) -> str | None:
    """Case-insensitive lookup of an ICED state-name to its ECI entity_id.

    Returns ``None`` if the label is unmapped (caller decides whether to
    skip + count or escalate). Trims surrounding whitespace before lookup.
    """
    if not isinstance(label, str):
        return None
    key = label.strip().lower()
    if not key:
        return None
    return _ENTITY_MAP_CI.get(key)
