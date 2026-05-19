"""ECI Statistical Report people-panel adapter.

Reads a panel CSV that carries the biographic fields ECI publishes in PDF
Statistical Reports (sex, age, education, profession, candidate-level votes)
but does NOT publish in the Section-10 HTML this codebase already ingests.
Source authority is ECI in all cases; the CSV is a frozen input the operator
obtains once and places under ``datasets/ephemeral/``.

This module is pure: it parses, normalises, and slugifies. All I/O lives in
``yen_gov.pipeline.people_ingest``.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

# Adapter id stamped into people.field_provenance.source_id. Publisher
# label, not carrier. Matches ``field_priority`` entries in
# ``config/elections.json``.
ADAPTER_ID = "eci_statreport"

# CSV column -> normalised value mappings. Kept inline; if these grow,
# move to a small lookup module.
_SEX_MAP: dict[str, str | None] = {
    "M": "Male",
    "MALE": "Male",
    "F": "Female",
    "FEMALE": "Female",
    "O": "Other",
    "": None,
}

_CONSTITUENCY_TYPE_OK = {"GEN", "SC", "ST"}

_EDUCATION_OK = {
    "Illiterate",
    "Literate",
    "5th Pass",
    "8th Pass",
    "10th Pass",
    "12th Pass",
    "Graduate",
    "Graduate Professional",
    "Post Graduate",
    "Doctorate",
    "Others",
}

_PROFESSION_OK = {
    "Agriculture",
    "Agricultural Labour",
    "Business",
    "Education",
    "Former Government",
    "Labourer or Daily Wage",
    "Liberal Profession or Professional",
    "Other",
    "Politics",
    "Religious Occupation",
    "Retired or Pension",
    "Salaried Work or Employed",
    "Small Business or Self-employed",
    "Social Work",
    "Student",
    "Traditional Occupation",
    "Unemployed",
}

# CSV uses underscore-separated state names; map to ECI codes for the
# subset we currently ingest. Extend as new state CSVs land.
STATE_NAME_TO_CODE: dict[str, str] = {
    "Tamil_Nadu": "S22",
}


_NOTA_TOKENS = {"NOTA", "NONE OF THE ABOVE"}


@dataclass(frozen=True)
class PersonRow:
    """Normalised one-row view from the panel CSV."""

    election_id: str
    state: str
    ac_code: int
    candidate_slug: str
    name: str
    party_short: str
    votes: int
    position: int
    sex: str | None
    age: int | None
    constituency_type: str | None
    education: str | None
    profession: str | None
    # Carried for the discrepancy comparator; not written into the people
    # artifact (vote facts live on result.constituency, not here).
    valid_votes: int | None
    electors: int | None


def slugify(name: str) -> str:
    """Stable lowercase slug for one person.

    ASCII-fold, lowercase, collapse non-alphanumeric to hyphens, trim
    leading/trailing hyphens. Stable across re-runs of the same input
    (CLAUDE.md §3 identifier convention — slug derives from name; the
    name is the upstream identifier).
    """
    if not name or not name.strip():
        raise ValueError("slugify requires a non-empty name")
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    folded = folded.lower()
    folded = re.sub(r"[^a-z0-9]+", "-", folded)
    folded = folded.strip("-")
    if not folded:
        raise ValueError(f"slugify produced empty slug for name {name!r}")
    return folded


def is_nota(candidate: str) -> bool:
    """True for the rows the panel uses to represent NOTA.

    NOTA rows carry vote totals but no biographics; the people sidecar
    has no place for them (NOTA is on result.constituency.nota).
    """
    return candidate.strip().upper() in _NOTA_TOKENS


def normalise_sex(raw: str) -> str | None:
    token = (raw or "").strip().upper()
    if token not in _SEX_MAP:
        raise ValueError(f"unknown sex value {raw!r} (extend _SEX_MAP)")
    return _SEX_MAP[token]


def normalise_constituency_type(raw: str) -> str | None:
    token = (raw or "").strip().upper()
    if not token:
        return None
    if token not in _CONSTITUENCY_TYPE_OK:
        raise ValueError(f"unknown constituency_type {raw!r}")
    return token


def normalise_education(raw: str) -> str | None:
    token = (raw or "").strip()
    if not token:
        return None
    if token not in _EDUCATION_OK:
        raise ValueError(f"unknown education value {raw!r}")
    return token


def normalise_profession(raw: str) -> str | None:
    token = (raw or "").strip()
    if not token:
        return None
    if token not in _PROFESSION_OK:
        raise ValueError(f"unknown profession value {raw!r}")
    return token


def _as_int(raw: str, *, allow_blank: bool = False) -> int | None:
    token = (raw or "").strip()
    if not token:
        if allow_blank:
            return None
        raise ValueError("expected integer, got blank")
    # CSV sometimes carries floats for ints (Age=60.0); accept and truncate.
    if "." in token:
        return int(float(token))
    return int(token)


def _normalise_age(raw: str) -> int | None:
    """Coerce age outside [18, 120] to None.

    18 is the constitutional minimum (Art. 173(b)); 120 caps obvious
    typos. We treat out-of-range values as not-credibly-declared rather
    than failing the run — the upstream panel has occasional single-digit
    typos (e.g. Age=4) on otherwise valid candidates, and dropping the
    age field is the honest treatment (same semantics as blank).
    """
    value = _as_int(raw, allow_blank=True)
    if value is None:
        return None
    if value < 18 or value > 120:
        return None
    return value


def parse_panel(
    csv_path: Path,
    *,
    election_id: str,
    state_code: str,
    year: int,
) -> list[PersonRow]:
    """Read the panel CSV and return rows for one (state, year) slice.

    Filters by Year + State_Name; drops NOTA rows; raises on any
    unrecognised enum value rather than silently dropping data (fail-fast
    at the boundary per CLAUDE.md §10).
    """
    state_label = next(
        (label for label, code in STATE_NAME_TO_CODE.items() if code == state_code),
        None,
    )
    if state_label is None:
        raise ValueError(
            f"state_code {state_code!r} not in STATE_NAME_TO_CODE; extend the map"
        )

    rows: list[PersonRow] = []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            if raw.get("State_Name") != state_label:
                continue
            if _as_int(raw["Year"]) != year:
                continue
            name = (raw.get("Candidate") or "").strip()
            if not name or is_nota(name):
                continue
            rows.append(
                PersonRow(
                    election_id=election_id,
                    state=state_code,
                    ac_code=_as_int(raw["Constituency_No"]),
                    candidate_slug=slugify(name),
                    name=name,
                    party_short=(raw.get("Party") or "").strip() or "IND",
                    votes=_as_int(raw["Votes"]),
                    position=_as_int(raw["Position"]),
                    sex=normalise_sex(raw.get("Sex", "")),
                    age=_normalise_age(raw.get("Age", "")),
                    constituency_type=normalise_constituency_type(
                        raw.get("Constituency_Type", "")
                    ),
                    education=normalise_education(raw.get("MyNeta_education", "")),
                    profession=normalise_profession(raw.get("TCPD_Prof_Main", "")),
                    valid_votes=_as_int(raw.get("Valid_Votes", ""), allow_blank=True),
                    electors=_as_int(raw.get("Electors", ""), allow_blank=True),
                )
            )
    return rows


# to_people_payload was retired in PR-S.2 (canonical pivot 1.8f). The
# per-candidate JSON sidecar (people.entity v1.0) and its schema were
# deleted; biographic fields now ride on dim_candidates.parquet v1.2
# columns and are UPSERTed by
# ``yen_gov.pipeline.people_ingest.upsert_candidate_bios``. ``ADAPTER_ID``
# above is retained only as a documentation token for the source authority.


def group_by_ac(rows: Iterable[PersonRow]) -> dict[int, list[PersonRow]]:
    """Group rows by ac_code. Within each AC, rows are NOT pre-sorted."""
    out: dict[int, list[PersonRow]] = {}
    for r in rows:
        out.setdefault(r.ac_code, []).append(r)
    return out
