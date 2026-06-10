"""Parse the TCPD All-States General-Election panel into PC results.

The Trivedi Centre for Political Data (TCPD) ``All_States_GE.csv`` is a
candidate-level panel covering every Parliament general election: one row per
``(constituency, candidate)``. This module filters the panel to a single GE
year and the *original* poll, resolves each constituency to a canonical
``pc_id`` via the historical crosswalk
(:mod:`yen_gov.canonical.adapters.eci.pc_crosswalk`), and emits the same
:class:`~yen_gov.sources.eci.ls_constituencywise.PcResultRaw` shape the ECI
Report-33 parser produces. The canonical PC-envelope builder is therefore
source-agnostic — it does not care whether a year came from ECI Report-33
(2024) or the TCPD panel (1999-2019).

Source notes / honesty guards:

* **Original poll only.** Two 2019 seats (Samastipur, Satara) carry a
  by-election re-poll as ``Poll_No == 1``. We keep ``Poll_No == 0`` (the
  May-2019 general election result) so each year yields exactly its general
  election, never a by-election.
* **Age is null.** The TCPD GE panel does not publish candidate age, so the
  ``age`` field is left ``None`` (the ECI Report-33 path fills it for 2024).
* **Education / profession** come from the panel's ``MyNeta_education`` /
  ``TCPD_Prof_Main`` columns — the TCPD-only enrichment the ECI source lacks.
  The token vocabularies are identical to the assembly people-panel, so the
  shared allowlist normalisers are reused.
* **Votes.** The panel publishes a single ``Votes`` figure per candidate (no
  general/postal split), so ``general_votes``/``postal_votes`` are ``0`` and
  ``total_votes`` carries the figure. ``total_votes_polled`` is the sum of all
  candidate votes (including NOTA); the panel has no rejected-vote column.
"""

from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.adapters.eci.pc_crosswalk import (
    PcCrosswalkError,
    resolve_pc,
)
from yen_gov.sources.eci.ls_constituencywise import PcCandidateRaw, PcResultRaw
from yen_gov.sources.eci.people_panel import (
    normalise_education,
    normalise_profession,
)

#: The only ``Election_Type`` value we ingest from the panel.
GE_ELECTION_TYPE = "Parliament Election (GE)"

#: ``Poll_No`` of the original general-election poll (re-polls are ``1+``).
ORIGINAL_POLL = "0"

_NOTA_TOKENS = {"NOTA", "NONE OF THE ABOVE"}

#: TCPD ``State_Name`` tokens whose normalised form does not match the
#: canonical ``entities.json`` display name. ``resolve_pc``'s automatic path
#: normalises the TCPD token and looks it up in ``entities.json``; for these
#: the norms differ, so we translate to the canonical display name first
#: (Message Translator). These are *spelling* differences, NOT reorganisations
#: — reorganisations live as override rows in the crosswalk CSV. Extend per
#: year as older panels surface (e.g. ``Orissa`` -> ``Odisha`` for pre-2011
#: general elections).
TCPD_STATE_NAME_ALIASES: dict[str, str] = {
    "Delhi": "NCT of Delhi",
}

#: Columns the parser reads; a missing one is a fail-fast at the header.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "State_Name",
    "Constituency_No",
    "Constituency_Name",
    "Year",
    "Poll_No",
    "Election_Type",
    "Candidate",
    "Party",
    "Sex",
    "Votes",
    "Valid_Votes",
    "Electors",
    "MyNeta_education",
    "TCPD_Prof_Main",
)


class LsGeTcpdError(Exception):
    """Raised on a malformed or unresolvable TCPD GE panel row."""


def _is_nota(name: str, party: str) -> bool:
    return (
        name.strip().upper() in _NOTA_TOKENS
        or party.strip().upper() in _NOTA_TOKENS
    )


def _as_int(raw: str | None, *, allow_blank: bool = False) -> int | None:
    text = (raw or "").strip().replace(",", "")
    if not text:
        if allow_blank:
            return None
        raise LsGeTcpdError(f"expected an integer, got blank: {raw!r}")
    try:
        # The panel occasionally carries floats for ints (e.g. ``60.0``).
        return int(float(text)) if "." in text else int(text)
    except ValueError as exc:  # pragma: no cover - defensive
        raise LsGeTcpdError(f"unparseable integer: {raw!r}") from exc


def parse_ls_ge_tcpd(
    csv_path: Path,
    *,
    year: int,
    crosswalk,
    state_lookup,
) -> list[PcResultRaw]:
    """Parse one GE year from the TCPD panel into ``PcResultRaw`` per PC.

    ``crosswalk`` and ``state_lookup`` come from
    :func:`yen_gov.canonical.adapters.eci.pc_crosswalk.load_crosswalk_and_lookup`.
    A constituency whose ``(state, no)`` cannot be resolved to a canonical
    ``(state_code, pc_no)`` is a fail-fast.
    """
    grouped: dict[tuple[str, int], dict] = {}
    order: list[tuple[str, int]] = []

    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise LsGeTcpdError("TCPD GE panel CSV has no header row")
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise LsGeTcpdError(
                "TCPD GE panel CSV missing required columns: "
                + ", ".join(repr(m) for m in missing)
            )

        for row in reader:
            if (row.get("Election_Type") or "").strip() != GE_ELECTION_TYPE:
                continue
            if (row.get("Year") or "").strip() != str(year):
                continue
            if (row.get("Poll_No") or "").strip() != ORIGINAL_POLL:
                continue

            raw_state = (row.get("State_Name") or "").strip()
            cno = _as_int(row.get("Constituency_No"))
            key = (raw_state, cno)
            candidate = PcCandidateRaw(
                name=(row.get("Candidate") or "").strip(),
                party_name=(row.get("Party") or "").strip(),
                gender=((row.get("Sex") or "").strip() or None),
                age=None,  # TCPD GE panel does not publish candidate age.
                category=None,  # candidate social category is not exposed here.
                general_votes=0,
                postal_votes=0,
                total_votes=_as_int(row.get("Votes"), allow_blank=True) or 0,
                is_nota=_is_nota(row.get("Candidate") or "", row.get("Party") or ""),
                education=normalise_education(row.get("MyNeta_education") or ""),
                profession=normalise_profession(row.get("TCPD_Prof_Main") or ""),
            )
            if key not in grouped:
                order.append(key)
                grouped[key] = {
                    "pc_name": (row.get("Constituency_Name") or "").strip(),
                    "electors": _as_int(row.get("Electors"), allow_blank=True),
                    "valid_votes": _as_int(row.get("Valid_Votes"), allow_blank=True),
                    "candidates": [],
                }
            grouped[key]["candidates"].append(candidate)

    results: list[PcResultRaw] = []
    for key in order:
        raw_state, cno = key
        bucket = grouped[key]
        canonical_state = TCPD_STATE_NAME_ALIASES.get(raw_state, raw_state)
        try:
            resolution = resolve_pc(
                year,
                canonical_state,
                cno,
                crosswalk=crosswalk,
                state_lookup=state_lookup,
            )
        except PcCrosswalkError as exc:
            raise LsGeTcpdError(
                f"could not resolve {raw_state!r} #{cno} (GE {year}): {exc}"
            ) from exc
        candidates = bucket["candidates"]
        # No rejected-vote column; the votes we ingest (incl. NOTA) are the
        # polled-valid total.
        polled = sum(c.total_votes for c in candidates)
        results.append(
            PcResultRaw(
                state_name=raw_state,
                state_code=resolution.state_code,
                pc_name=bucket["pc_name"],
                pc_no=resolution.pc_no,
                total_electors=bucket["electors"],
                total_votes_polled=polled,
                valid_votes=bucket["valid_votes"],
                candidates=tuple(candidates),
            )
        )
    return results
