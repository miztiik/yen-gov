"""Historical Lok Sabha (PC) constituency-identity resolver (EGC-B2 Phase 2).

Maps a TCPD ``(ge_year, State_Name, Constituency_No)`` triple to the canonical
``(state_code, pc_no, delim_year)`` so a historical seat shares its ``pc_id``
with the modern (2024) seat wherever the boundary is continuous.

Design (Fowler verdict, CLAUDE.md section 0a):
  - ``delim_year`` is a pure function of ``ge_year`` (never overridden).
  - Resolution is automatic for every seat UNLESS a reorganization broke the
    1:1 ``(state, Constituency_No) -> (state_code, pc_no)`` map. The break set
    lives in an override-only CSV
    (``datasets/data/entities/pc_historical_crosswalk.csv``); the absence of a
    row IS the identity.

The resolver is pure and free of pipeline I/O so it is unit-testable in
isolation from the (future) GE panel parser.

G8 (2026-06-08): the crosswalk CSV moved out of
``datasets/reference/in/elections/`` into ``datasets/data/entities/`` as part of
the mechanical ``datasets/reference/`` reshape (plan-doc section 9 + section
21.2). The override-only row shape is unchanged.

See also:
    - datasets/schemas/pc-historical-crosswalk.schema.json
    - datasets/data/entities/pc_historical_crosswalk.csv
    - backend/yen_gov/canonical/adapters/eci/identity.py (pc_entity_id)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from yen_gov.sources.eci.ls_constituencywise import _norm, load_state_code_lookup

CROSSWALK_RELPATH = "data/entities/pc_historical_crosswalk.csv"

# Delimitation cycle in force for each Lok Sabha general election. The
# 1976 delimitation governed 1999 + 2004; the 2008 delimitation governs
# every election from 2009. Never overridden by the crosswalk.
DELIM_BY_GE_YEAR: dict[int, int] = {
    1999: 1976,
    2004: 1976,
    2009: 2008,
    2014: 2008,
    2019: 2008,
    2024: 2008,
}


class PcCrosswalkError(Exception):
    """Raised when the historical PC crosswalk cannot resolve a seat."""


@dataclass(frozen=True)
class PcResolution:
    """Resolved canonical identity for one historical PC seat-year."""

    state_code: str
    pc_no: int
    delim_year: int
    match_method: str


def delim_year_for_ge(ge_year: int) -> int:
    """Return the delimitation cycle year in force for ``ge_year``."""
    try:
        return DELIM_BY_GE_YEAR[ge_year]
    except KeyError as exc:
        raise PcCrosswalkError(
            f"no delimitation mapping for Lok Sabha year {ge_year!r}; "
            "extend DELIM_BY_GE_YEAR when adding a new election"
        ) from exc


def _norm_state(value: str | None) -> str:
    """Normalise a TCPD state token (underscores -> spaces) then reuse _norm."""
    return _norm((value or "").replace("_", " "))


def load_pc_crosswalk(
    datasets_root: Path,
) -> dict[tuple[int, str, int], tuple[str, int, str]]:
    """Load the override-only crosswalk.

    Returns ``{(ge_year, norm_state, constituency_no): (state_code, pc_no,
    match_method)}``. Fails fast on a duplicate PK triple.
    """
    path = datasets_root / CROSSWALK_RELPATH
    if not path.exists():
        raise PcCrosswalkError(f"crosswalk file not found: {path.as_posix()}")
    table: dict[tuple[int, str, int], tuple[str, int, str]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for line_no, row in enumerate(reader, start=2):
            key = (
                int(row["ge_year"]),
                _norm_state(row["tcpd_state"]),
                int(row["tcpd_constituency_no"]),
            )
            if key in table:
                raise PcCrosswalkError(
                    f"duplicate crosswalk PK {key!r} at line {line_no}"
                )
            table[key] = (
                row["state_code"],
                int(row["pc_no"]),
                row["match_method"],
            )
    return table


def resolve_pc(
    ge_year: int,
    tcpd_state: str,
    constituency_no: int,
    *,
    crosswalk: dict[tuple[int, str, int], tuple[str, int, str]],
    state_lookup: dict[str, str],
) -> PcResolution:
    """Resolve one TCPD seat-year to canonical ``(state_code, pc_no, delim_year)``.

    Override hit -> use the crosswalk row. Otherwise the automatic rule:
    ``state_code`` from ``state_lookup`` (taxonomy display names) and
    ``pc_no := constituency_no``.
    """
    delim_year = delim_year_for_ge(ge_year)
    norm_state = _norm_state(tcpd_state)
    override = crosswalk.get((ge_year, norm_state, constituency_no))
    if override is not None:
        state_code, pc_no, match_method = override
        return PcResolution(state_code, pc_no, delim_year, match_method)

    state_code = state_lookup.get(norm_state)
    if state_code is None:
        raise PcCrosswalkError(
            f"no state_code for TCPD state {tcpd_state!r} (normalised "
            f"{norm_state!r}) in {ge_year}; add a crosswalk override or an "
            "entities.json display-name alias"
        )
    return PcResolution(state_code, constituency_no, delim_year, "automatic")


def load_crosswalk_and_lookup(
    datasets_root: Path,
) -> tuple[
    dict[tuple[int, str, int], tuple[str, int, str]],
    dict[str, str],
]:
    """Convenience loader returning ``(crosswalk, state_lookup)`` together."""
    return load_pc_crosswalk(datasets_root), load_state_code_lookup(
        datasets_root
    )
