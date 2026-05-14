"""State-name → ECI-code map for RBI Handbook ingest.

RBI consistently writes "&" where our reference data uses "and"
(e.g. "Jammu & Kashmir", "Andaman & Nicobar Islands"). The mapping below is the
union of every spelling observed across HBS-IE and HBS-IS workbooks; aliases
that resolve to the same ECI code (e.g. both "Delhi" and "NCT of Delhi" → U05)
are listed explicitly rather than normalised away, because the originating
spelling is itself useful provenance when triaging unmatched rows.

Codes follow the ECI scheme (S01..S29 for states, U01..U09 for UTs); kept here
rather than reading ``datasets/reference/in/states.json`` to keep the ingest
tools dependency-free at run time and traceable in code review.

``ALL_INDIA_NAMES`` carries the column header(s) RBI uses for the all-India
aggregate column that appears in some HBS-IE per-capita tables; resolves to
``IN`` (the project's ISO 3166 country entity id).
"""
from __future__ import annotations

NAME_TO_ECI: dict[str, str] = {
    "Andhra Pradesh": "S01",
    "Arunachal Pradesh": "S02",
    "Assam": "S03",
    "Bihar": "S04",
    "Chhattisgarh": "S26",
    "Goa": "S05",
    "Gujarat": "S06",
    "Haryana": "S07",
    "Himachal Pradesh": "S08",
    "Jammu & Kashmir": "U08",
    "Jharkhand": "S27",
    "Karnataka": "S10",
    "Kerala": "S11",
    "Madhya Pradesh": "S12",
    "Maharashtra": "S13",
    "Manipur": "S14",
    "Meghalaya": "S15",
    "Mizoram": "S16",
    "Nagaland": "S17",
    "Odisha": "S18",
    "Punjab": "S19",
    "Rajasthan": "S20",
    "Sikkim": "S21",
    "Tamil Nadu": "S22",
    "Telangana": "S29",
    "Tripura": "S23",
    "Uttar Pradesh": "S24",
    "Uttarakhand": "S28",
    "West Bengal": "S25",
    "Andaman & Nicobar Islands": "U01",
    "Chandigarh": "U02",
    "Delhi": "U05",
    "NCT of Delhi": "U05",
    "Puducherry": "U07",
    "Lakshadweep": "U04",
    "Ladakh": "U09",
    "Dadra & Nagar Haveli": "U03",
    "Dadra and Nagar Haveli and Daman and Diu": "U03",
    "Daman & Diu": "U03",
}

ALL_INDIA_NAMES: set[str] = {
    "All- India per capita NNI",
    "All-India per capita NNI",
}
