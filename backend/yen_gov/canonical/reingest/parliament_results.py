"""B2b.5.4 parliament (Lok Sabha) election-results emitter.

Reads the local TCPD general-election compilation (``All_States_GE.csv``,
candidate-grain) and emits the two per-election parliament CSV file classes:

- ``elections/parliament/election=<year>/candidacies.csv``
- ``elections/parliament/election=<year>/summary.csv``

Structurally this is the assembly emitter (B2b.5.2 / B2b.5.3) with three
parliament-specific differences (parent plan section 23.4):

1. **Country-wide, one file per LS cycle** - there is no ``state=`` path
   partition; a single ``election=<year>/`` directory holds every state's PCs.
2. **``state`` is a MANDATORY column** - because ``constituency_no`` (the ECI
   pc_no) restarts per state, ``state`` is required for ``(state,
   constituency_no)`` to be unique within the file; without it per-state joins
   break and ``constituency_no`` is ambiguous.
3. **entity bind targets PC entities** - ``entity_id`` resolves through
   ``electoral.csv`` on ``(state_slug, eci_no == Constituency_No)`` for
   ``entity_kind == 'pc'`` rows (``IN-PC-<delim>-<state>-<pc_no>``).

Everything else is shared with the assembly path and imported from
``assembly_results`` (NOTA exclusion, the closed-enum boundary maps, nan->null,
the re-poll-supersede rule, and ``recompute_summary_row`` so the parity oracle
asserts ``summary == recompute(candidacies)`` identically for both axes).

Delimitation scoping + party_id treatment match the assembly pilot: only the
in-force 2008 cycle (``DELIM_ID_2008``) is emitted (its pc_no numbering binds to
``electoral.csv``); ``party_id`` is null at v1 (no TCPD-party -> parties.csv
crosswalk). No network, no parquet, no ``urls.py`` / ``core.http`` import.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.reingest.assembly_results import (
    DELIM_ID_2008,
    NOTA_PARTY_TOKEN,
    NOTA_TOKENS,
    _candidate_type,
    _float_or_none,
    _int_or_none,
    _latest_poll_only,
    _result,
    _sex,
    _text_or_none,
    party_lookup_from_parties_csv,
    recompute_summary_row,
)
from yen_gov.canonical.reingest.elections import (
    PARLIAMENT_CANDIDACIES_FC,
    PARLIAMENT_SUMMARY_FC,
    parliament_candidacies_path,
    parliament_summary_path,
)

__all__ = ["build_parliament_year", "emit_parliament"]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _pc_eci_to_entity(electoral_rows: list[dict[str, str]]) -> dict[tuple[str, int], str]:
    """Map ``(state_slug, eci_no) -> entity_id`` for every PC entity.

    Parliament binds country-wide, so the key carries the state slug (pc_no
    restarts per state). Only ``entity_kind == 'pc'`` rows participate.
    """
    out: dict[tuple[str, int], str] = {}
    for row in electoral_rows:
        if row.get("entity_kind") != "pc":
            continue
        raw = (row.get("eci_no") or "").strip()
        state = row.get("state") or ""
        if not raw or not state:
            continue
        out[(state, int(raw))] = row["entity_id"]
    return out


def _slugify(tcpd_name: str) -> str:
    return tcpd_name.lower().replace("_&_", "-and-").replace("_", "-")


def build_parliament_year(
    *,
    source_rows: list[dict[str, str]],
    pc_eci_to_entity: dict[tuple[str, int], str],
    source_id: str,
    party_lookup: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[tuple[str, int]]]:
    """Build (candidacies, summary, unbound) for ONE LS cycle (all states).

    ``source_rows`` are the TCPD GE rows for one ``Year`` + the in-force
    delimitation. Returns the candidacy rows (NOTA excluded; sorted by
    ``(state, constituency_no, position, candidate_name)``), the recomputed
    summary rows (one per PC), and the set of ``(state_slug, pc_no)`` that did
    not resolve to a PC entity (skipped; surfaced for the coverage note).

    ``party_lookup`` is the optional ``upper(short) -> party_id`` map from
    :func:`assembly_results.party_lookup_from_parties_csv` (F1.3a v1.1).
    """
    lookup = party_lookup or {}
    # Re-poll supersede is per (state, constituency) - prefix the key with state.
    final_rows = _latest_poll_only(
        [
            {**r, "Constituency_No": f"{_slugify(r.get('State_Name') or '')}:{r.get('Constituency_No') or ''}"}
            for r in source_rows
        ]
    )
    # Restore the original Constituency_No after the per-(state,cno) poll filter.
    for r in final_rows:
        r["Constituency_No"] = r["Constituency_No"].split(":", 1)[1]

    candidacies: list[dict[str, Any]] = []
    unbound: set[tuple[str, int]] = set()
    for src in final_rows:
        raw_party = (src.get("Party") or "").strip()
        if raw_party.upper() in NOTA_TOKENS:
            continue
        pc_no = _int_or_none(src.get("Constituency_No"))
        if pc_no is None:
            continue
        state_slug = _slugify(src.get("State_Name") or "")
        entity_id = pc_eci_to_entity.get((state_slug, pc_no))
        if entity_id is None:
            unbound.add((state_slug, pc_no))
            continue
        position = _int_or_none(src.get("Position"))
        candidacies.append(
            {
                "entity_id": entity_id,
                "state": state_slug,
                "election_year": _int_or_none(src.get("Year")),
                "constituency_no": pc_no,
                "constituency_name": _text_or_none(src.get("Constituency_Name")) or "",
                "candidate_name": _text_or_none(src.get("Candidate")) or "",
                "party_id": lookup.get(raw_party.upper()) if raw_party else None,
                "party_short_raw": raw_party or None,
                "votes": _int_or_none(src.get("Votes")) or 0,
                "vote_share_pct": _float_or_none(src.get("Vote_Share_Percentage")),
                "position": position if position is not None else 0,
                "result": _result(position, src.get("Deposit_Lost")),
                "sex": _sex(src.get("Sex")),
                "age": _int_or_none(src.get("Age")),
                "education": _text_or_none(src.get("MyNeta_education")),
                "profession": _text_or_none(src.get("TCPD_Prof_Main_Desc")),
                "candidate_type": _candidate_type(src),
                "source_id": source_id,
            }
        )
    candidacies.sort(
        key=lambda r: (r["state"], r["constituency_no"], r["position"], r["candidate_name"])
    )

    # AC-level (here PC-level) electorate facts come straight off the source rows.
    pc_facts: dict[str, dict[str, Any]] = {}
    for src in final_rows:
        pc_no = _int_or_none(src.get("Constituency_No"))
        if pc_no is None:
            continue
        state_slug = _slugify(src.get("State_Name") or "")
        entity_id = pc_eci_to_entity.get((state_slug, pc_no))
        if entity_id is None or entity_id in pc_facts:
            continue
        pc_facts[entity_id] = {
            "electors": _int_or_none(src.get("Electors")),
            "votes_polled": _int_or_none(src.get("Valid_Votes")),
            "turnout_pct": _float_or_none(src.get("Turnout_Percentage")),
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cand in candidacies:
        grouped[cand["entity_id"]].append(cand)

    summary: list[dict[str, Any]] = [
        recompute_summary_row(
            entity_id=entity_id,
            state_slug=group[0]["state"],
            election_year=group[0]["election_year"],
            candidacy_rows=group,
            ac_facts=pc_facts.get(entity_id, {}),
            source_id=source_id,
        )
        for entity_id, group in grouped.items()
    ]
    return candidacies, summary, unbound


def emit_parliament(
    *,
    ge_csv: Path,
    electoral_csv: Path,
    out_root: Path,
    source_id: str,
    delim_id: str = DELIM_ID_2008,
    parties_csv: Path | None = None,
) -> dict[int, dict[str, Any]]:
    """Emit candidacies + summary CSVs for every in-force LS cycle.

    Returns ``{year: {"candidacies": Path, "summary": Path, "n_candidacies":
    int, "n_summary": int, "states": int, "unbound": sorted list}}``.

    ``parties_csv`` is the optional path to ``datasets/data/entities/parties.csv``
    for F1.3a v1.1 party-id resolution; see
    :func:`assembly_results.emit_state_assembly` for the same contract.
    """
    if not ge_csv.exists():
        raise FileNotFoundError(ge_csv)
    if not electoral_csv.exists():
        raise FileNotFoundError(electoral_csv)

    pc_eci_to_entity = _pc_eci_to_entity(_read_csv_rows(electoral_csv))
    party_lookup = (
        party_lookup_from_parties_csv(parties_csv) if parties_csv is not None else {}
    )

    delim_rows = [
        r for r in _read_csv_rows(ge_csv) if (r.get("DelimID") or "").strip() == delim_id
    ]
    by_year: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in delim_rows:
        year = _int_or_none(row.get("Year"))
        if year is not None:
            by_year[year].append(row)

    emitted: dict[int, dict[str, Any]] = {}
    for year, year_rows in sorted(by_year.items()):
        candidacies, summary, unbound = build_parliament_year(
            source_rows=year_rows,
            pc_eci_to_entity=pc_eci_to_entity,
            source_id=source_id,
            party_lookup=party_lookup,
        )
        if not candidacies:
            continue

        cand_path = parliament_candidacies_path(out_root=out_root, election_year=year)
        summ_path = parliament_summary_path(out_root=out_root, election_year=year)
        write_csv(path=cand_path, file_class=PARLIAMENT_CANDIDACIES_FC, rows=candidacies)
        write_csv(path=summ_path, file_class=PARLIAMENT_SUMMARY_FC, rows=summary)

        emitted[year] = {
            "candidacies": cand_path,
            "summary": summ_path,
            "n_candidacies": len(candidacies),
            "n_summary": len(summary),
            "states": len({c["state"] for c in candidacies}),
            "unbound": sorted(unbound),
        }
    return emitted
