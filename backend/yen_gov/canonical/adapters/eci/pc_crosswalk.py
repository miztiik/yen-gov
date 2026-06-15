"""Historical Parliament (PC) constituency-identity resolver (EGC-B2 Phase 2).

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

# Delimitation cycle in force for each Parliament general election.
#
# Four delimitation cohorts cover every LS GE from 1962 onward (load-bearing
# evidence per the TCPD ``DelimID`` column in
# ``datasets/ephemeral/All_States_GE.csv``):
#
#   - 1962 is its own cohort (DelimID 1, pre-1967 reorganisation).
#   - 1967 + 1971 share the 1967 delimitation (DelimID 2).
#   - 1977-2004 share the 1976 delimitation (DelimID 3); the 1976 boundaries
#     governed nine consecutive general elections.
#   - 2009-2024 share the 2008 delimitation.
#
# Each cohort's by-election years (single-PC by-elections held between two
# general elections on the same boundaries) are listed alongside the GE so the
# parliament-results emitter can bind by-election rows back to the in-force
# PC cohort. The set of years here matches every distinct ``Year`` present in
# ``datasets/ephemeral/All_States_GE.csv`` (PR Row A.5, 2026-06-14).
#
# Never overridden by the crosswalk; ``delim_year`` is a pure function of
# ``ge_year`` (Fowler verdict, CLAUDE.md section 0a).
DELIM_BY_GE_YEAR: dict[int, int] = {
    # DelimID 1 (1962 cohort, pre-1967 reorganisation)
    1962: 1962,
    1963: 1962,
    1964: 1962,
    1965: 1962,
    # DelimID 2 (1967 cohort)
    1967: 1967,
    1968: 1967,
    1969: 1967,
    1970: 1967,
    1971: 1967,
    1972: 1967,
    # DelimID 3 (1976 cohort) -- nine GEs + by-elections 1977-2008
    1977: 1976,
    1978: 1976,
    1979: 1976,
    1980: 1976,
    1981: 1976,
    1982: 1976,
    1984: 1976,
    1985: 1976,
    1986: 1976,
    1987: 1976,
    1988: 1976,
    1989: 1976,
    1990: 1976,
    1991: 1976,
    1992: 1976,
    1993: 1976,
    1994: 1976,
    1995: 1976,
    1996: 1976,
    1997: 1976,
    1998: 1976,
    1999: 1976,
    2000: 1976,
    2001: 1976,
    2002: 1976,
    2003: 1976,
    2004: 1976,
    2005: 1976,
    2006: 1976,
    2007: 1976,
    2008: 1976,
    # DelimID 4 (2008 cohort) -- four GEs + interim by-elections 2009-2025
    2009: 2008,
    2010: 2008,
    2011: 2008,
    2012: 2008,
    2013: 2008,
    2014: 2008,
    2015: 2008,
    2016: 2008,
    2017: 2008,
    2018: 2008,
    2019: 2008,
    2020: 2008,
    2021: 2008,
    2022: 2008,
    2023: 2008,
    2024: 2008,
    2025: 2008,
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
            f"no delimitation mapping for Parliament year {ge_year!r}; "
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
