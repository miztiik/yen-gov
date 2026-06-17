"""State display-name -> LGD slug resolver for RBI Handbook ingest.

The RBI Handbook of Statistics on Indian States prints state / UT rows
using display names that vary slightly from yen-gov's canonical LGD
slugs (e.g. "Orissa" vs "odisha", "Jammu & Kashmir" vs
"jammu-and-kashmir", "All India" vs the country entity "IN").

The resolver is built at run time from
``datasets/data/entities/geo.csv`` - the canonical entity list is the
single source of truth (Holy Law #6: no hardcoded 36-row state map) -
plus a small RBI/SRS-dialect override map for spellings the canonical
``name`` / ``aliases`` columns do not carry. It fails loud (returns
``None`` -> caller raises) on anything unmatched, so a missing dialect
surfaces at run time, never as a silent coverage drop.

Pure stdlib (csv + re). No network, no third-party imports.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "COUNTRY_ENTITY_ID",
    "StateResolver",
    "build_state_resolver",
    "normalise_label",
]

# The project's ISO 3166 country entity id (all-India aggregate rows).
COUNTRY_ENTITY_ID = "IN"

# RBI / SRS dialect spellings -> canonical LGD slug. Keys are normalised
# (see :func:`normalise_label`). Only spellings NOT already covered by
# geo.csv ``name`` / ``aliases`` need an entry here.
_RBI_DIALECT_OVERRIDES: dict[str, str] = {
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "pondicherry": "puducherry",
    "nct of delhi": "delhi",
    "nct delhi": "delhi",
    "national capital territory of delhi": "delhi",
    "dadra and nagar haveli": "dadra-and-nagar-haveli-and-daman-and-diu",
    "daman and diu": "dadra-and-nagar-haveli-and-daman-and-diu",
}

# Normalised labels that denote the all-India aggregate row -> country id.
_DEFAULT_ALL_INDIA_LABELS: frozenset[str] = frozenset(
    {
        "india",
        "all india",
        "all india total",
    }
)

_ORDINAL_RE = re.compile(r"^\s*\d{1,3}\s*[.)]\s*")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalise_label(label: str | None) -> str:
    """Collapse a publisher label to a comparison key.

    Strips an optional leading ordinal ("1. Andhra Pradesh"), maps the
    ampersand to "and", lowercases, and reduces every run of non-
    alphanumeric characters to a single space. Returns "" for ``None``
    or blank input.

    >>> normalise_label("1. Jammu & Kashmir")
    'jammu and kashmir'
    >>> normalise_label("Tamil Nadu")
    'tamil nadu'
    """
    if label is None:
        return ""
    s = _ORDINAL_RE.sub("", str(label).strip())
    s = s.replace("&", " and ")
    s = s.lower()
    s = _NON_ALNUM_RE.sub(" ", s)
    return " ".join(s.split())


@dataclass(frozen=True)
class StateResolver:
    """Immutable ``normalised label -> entity_id`` lookup."""

    _by_label: dict[str, str]

    def resolve(self, label: str | None) -> str | None:
        """Return the LGD slug / country id for a raw label, or ``None``.

        Resolution order: all-India aggregate -> RBI dialect override ->
        geo.csv name / alias match. ``None`` means "unmatched"; the
        caller decides whether that is a skip row or a fail-loud error.
        """
        key = normalise_label(label)
        if not key:
            return None
        if key in _DEFAULT_ALL_INDIA_LABELS:
            return COUNTRY_ENTITY_ID
        if key in _RBI_DIALECT_OVERRIDES:
            return _RBI_DIALECT_OVERRIDES[key]
        return self._by_label.get(key)


def build_state_resolver(geo_csv: Path) -> StateResolver:
    """Build a :class:`StateResolver` from ``datasets/data/entities/geo.csv``.

    Indexes every ``entity_kind == "state"`` row (UTs are folded into the
    ``state`` kind in geo.csv) by its ``name`` and each pipe-delimited
    ``aliases`` token. First registration wins, so a canonical name is
    never shadowed by an alias of another entity.

    Raises:
        FileNotFoundError: ``geo_csv`` does not exist.
    """
    if not geo_csv.exists():
        raise FileNotFoundError(geo_csv)
    by_label: dict[str, str] = {}
    with geo_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("entity_kind") != "state":
                continue
            entity_id = (row.get("entity_id") or "").strip()
            if not entity_id:
                continue
            _register(by_label, row.get("name"), entity_id)
            for token in (row.get("aliases") or "").split("|"):
                _register(by_label, token, entity_id)
    return StateResolver(_by_label=by_label)


def _register(by_label: dict[str, str], label: str | None, entity_id: str) -> None:
    key = normalise_label(label)
    if key:
        by_label.setdefault(key, entity_id)
