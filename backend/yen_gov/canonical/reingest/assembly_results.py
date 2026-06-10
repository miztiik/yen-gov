"""B2b.5.2 assembly election-results emitter (TN pilot; fans out in B2b.5.3).

Reads the local TCPD assembly-elections compilation (``All_States_AE.csv``,
candidate-grain: one row per ``constituency x candidate x poll``) and emits the
two per-election CSV file classes declared in ``datasets/data/_schema/columns.json``:

- ``elections/assembly/state=<slug>/election=<year>/candidacies.csv`` - the
  candidate-grain facts (one row per real candidate; NOTA is excluded - it is a
  ballot option, not a candidate).
- ``elections/assembly/state=<slug>/election=<year>/summary.csv`` - the
  constituency-grain DERIVED projection (one row per AC). The winner / runner-up /
  margin fields are recomputed from the candidacies (argmax votes); the
  electorate-level fields (electors / votes_polled / turnout) are carried from the
  source because they are not derivable from candidate rows alone (parent plan
  section 23.4 + parity invariant 4: "turnout if present").

Binding decisions realised here (parent plan sections 21.3 / 23.4, sub-plan
section 0 + the B2b.5.2 row):

- **Delimitation scoping.** Only the in-force delimitation (TCPD ``DelimID`` whose
  constituency numbering matches the emitted ``electoral.csv`` entities - the 2008
  cycle, ``DELIM_ID_2008 = 4``) is emitted at v1. Historical delimitations carry a
  different ``Constituency_No`` numbering that does not bind to the 2008 electoral
  entities; they are deferred until historical-delimitation entities exist
  (documented coverage note, EL7 pattern).
- **Entity bind.** ``entity_id`` resolves through ``electoral.csv`` on
  ``(state_slug, eci_no == Constituency_No)``. A constituency the spine does not
  carry (a known small LGD-source gap) is SKIPPED, not fabricated - the
  fk-validator would reject an unbindable id, and the summary is recomputed from
  exactly the emitted candidacies so the projection stays internally consistent.
- **One file per distinct election year.** Each ``Year`` is its own self-contained
  election directory (general elections carry the full slate; by-elections carry
  the contested subset). Cross-year reads glob ``election=*`` at read time.
- **party_id resolution at v1.1 (F1.3a, 2026-06-06).** The B2b.5.x v1 writer left
  ``party_id`` null because TCPD's internal ``Party_ID`` does not crosswalk into
  ``entities/parties.csv``. F1.3a closes the gap with a *shortcode* lookup:
  ``parties.csv.short`` (case-insensitive) -> ``parties.csv.party_id``. This
  resolves ~95% of votes-weighted rows (every major recognised party) without
  fabricating an FK (Holy Law #9). Long-tail shorts absent from ``parties.csv``
  stay null - the column + the summary party columns remain nullable, and the
  citizen UI degrades to "IND" / blank for those rows. The crosswalk lives at
  the writer boundary (one lookup per emit, not per row) so a future enrichment
  to ``parties.csv`` is picked up by a simple re-emit. NOTA rows are filtered
  out before this resolution runs so NOTA never collides with the lookup.

No network, no parquet, no ``urls.py`` / ``core.http`` import (a reference would be
a B4-blocking regression). The pure helpers (``build_candidacy_rows``,
``recompute_summary_row``) take in-memory rows so the parity oracle can assert
``summary == recompute(candidacies)`` without touching disk.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.reingest.elections import (
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
    assembly_candidacies_path,
    assembly_summary_path,
)

__all__ = [
    "DELIM_ID_2008",
    "NOTA_PARTY_TOKEN",
    "NOTA_TOKENS",
    "build_candidacy_rows",
    "party_lookup_from_parties_csv",
    "recompute_summary_row",
    "emit_state_assembly",
]

# TCPD DelimID for the in-force (2008) delimitation - the cycle whose
# Constituency_No numbering matches the emitted electoral.csv entities.
DELIM_ID_2008 = "4"

# TCPD marks the "None of the Above" ballot line three different ways across
# years (G1, 2026-06-08): the canonical "NOTA" literal and the long-form
# "None of the Above" / bare "None". All three are ballot options, not
# candidates, and MUST be filtered out of candidacies + summary alike. The
# legacy NOTA_PARTY_TOKEN constant is preserved for backwards-compat callers
# (e.g. parliament_results re-export) but the live filter consults the
# NOTA_TOKENS frozenset.
NOTA_PARTY_TOKEN = "NOTA"
NOTA_TOKENS: frozenset[str] = frozenset({"NOTA", "NONE OF THE ABOVE", "NONE"})

# Closed-enum maps (the validator enforces membership; we map at the boundary).
_SEX_MAP = {"MALE": "M", "FEMALE": "F", "OTHERS": "O", "OTHER": "O", "THIRD": "O"}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _electoral_eci_to_entity(
    electoral_rows: list[dict[str, str]], state_slug: str
) -> dict[int, str]:
    """Map ``eci_no -> entity_id`` for the state's assembly constituencies.

    Only ``entity_kind == 'ac'`` rows for the given state participate; the
    ``eci_no`` column is the per-state ECI ballot serial folded by B2b.5.0c.
    """
    out: dict[int, str] = {}
    for row in electoral_rows:
        if row.get("entity_kind") != "ac" or row.get("state") != state_slug:
            continue
        raw = (row.get("eci_no") or "").strip()
        if not raw:
            continue
        out[int(raw)] = row["entity_id"]
    return out


def party_lookup_from_parties_csv(parties_csv: Path) -> dict[str, str]:
    """Build a TCPD-shortcode -> canonical party_id map (F1.3a v1.2 + G1).

    PR-1 (2026-06-10) — delegates to ``party_resolver.load_resolver`` so the
    central CSV-backed resolver is the single seam for publisher-string ->
    canonical id. The public API (``(parties_csv: Path) -> dict[str, str]``)
    is preserved exactly so the 4 existing call-sites
    (``assembly_results_from_eci``, ``parliament_results``,
    ``parliament_2024_eci``, and this module's own ``emit_state_assembly``)
    stay green without edits.

    Returns ``{upper(short): party_id}`` plus, for every non-empty
    pipe-delimited ``aliases`` value, ``{upper(alias): party_id}`` for each
    alias. TCPD's ``Party`` field uses a dialect different from the canonical
    short in places (CPM vs CPI(M), ADMK vs AIADMK, AAAP vs AAP, TRS vs BRS,
    ...); the ``aliases`` column captures those equivalences as data on disk
    (round-7c inline pipe-delim precedent on geo.csv + electoral.csv) so a
    future enrichment is a one-cell CSV edit, not a code change.

    Backwards compatible: if the ``aliases`` column is absent (older test
    fixtures), only ``upper(short) -> party_id`` mappings are emitted.

    Collisions are an error: if two distinct shorts/aliases would resolve
    to different ``party_id`` values, the loader fails loud (Holy Law #5)
    rather than silently picking one. Same short/alias to the same
    ``party_id`` via two rows is fine (idempotent).

    Pure I/O of one small CSV (~620 rows); the loader's lru-cache keeps
    repeated calls during an emit run cheap.
    """
    # Local import keeps the canonical/reingest module free of a hard
    # canonical-> party_resolver edge at module load (lru_cache lives there).
    from yen_gov.canonical.party_resolver import load_resolver

    if not parties_csv.exists():
        return {}
    return dict(load_resolver(parties_csv).by_alias)


def _int_or_none(value: str | None) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _float_or_none(value: str | None) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    # TCPD records an unpolled / unopposed return as ``nan`` (and very
    # occasionally an inf); those are "no meaningful value", not a number.
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _text_or_none(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _sex(value: str | None) -> str:
    return _SEX_MAP.get((value or "").strip().upper(), "U")


def _candidate_type(row: dict[str, str]) -> str | None:
    if (row.get("Incumbent") or "").strip().upper() == "TRUE":
        return "incumbent"
    if (row.get("Turncoat") or "").strip().upper() == "TRUE":
        return "crossover"
    return "challenger"


def _result(position: int | None, deposit_lost: str | None) -> str:
    if position == 1:
        return "won"
    if (deposit_lost or "").strip().lower() in {"yes", "true", "1"}:
        return "forfeit"
    return "lost"


def _latest_poll_only(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep only the rows from the highest ``Poll_No`` per constituency.

    A countermanded / re-polled constituency carries multiple ``Poll_No``
    generations for the same ``Constituency_No``; the final poll is the valid
    result. Constituencies without a re-poll (the overwhelming majority) are
    untouched.
    """
    max_poll: dict[str, int] = {}
    for row in rows:
        cno = (row.get("Constituency_No") or "").strip()
        poll = _int_or_none(row.get("Poll_No")) or 0
        if cno and (cno not in max_poll or poll > max_poll[cno]):
            max_poll[cno] = poll
    kept: list[dict[str, str]] = []
    for row in rows:
        cno = (row.get("Constituency_No") or "").strip()
        poll = _int_or_none(row.get("Poll_No")) or 0
        if cno and poll == max_poll[cno]:
            kept.append(row)
    return kept


def build_candidacy_rows(
    *,
    source_rows: list[dict[str, str]],
    eci_to_entity: dict[int, str],
    state_slug: str,
    election_year: int,
    source_id: str,
    party_lookup: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], set[int]]:
    """Build the candidacies rows for one (state, year) from source rows.

    Args:
        source_rows: TCPD rows already filtered to one state + delimitation +
            year (highest poll only).
        eci_to_entity: ``eci_no -> electoral.csv entity_id`` for the state.
        state_slug: LGD state slug (mirrored into the ``state`` column + path).
        election_year: the four-digit ``Year``.
        source_id: provenance stamp for every emitted row.
        party_lookup: optional ``upper(short) -> party_id`` map (F1.3a v1.1).
            When provided, the TCPD ``Party`` shortcode is upper-cased and
            looked up; matches yield the canonical ``parties.IN.*`` id; misses
            stay null. When ``None`` (back-compat for tests + the v1 writer),
            every ``party_id`` is null. Built via
            :func:`party_lookup_from_parties_csv` at the driver layer.

    Returns:
        ``(rows, unbound_eci_nos)`` - the candidacy dicts (NOTA excluded, sorted
        deterministically by ``(constituency_no, position, candidate_name)``) and
        the set of ``Constituency_No`` values that did not resolve to an electoral
        entity (skipped; surfaced for the coverage note).
    """
    lookup = party_lookup or {}
    rows: list[dict[str, Any]] = []
    unbound: set[int] = set()
    for src in source_rows:
        raw_party = (src.get("Party") or "").strip()
        if raw_party.upper() in NOTA_TOKENS:
            continue  # NOTA / None of the Above / None are ballot options, not candidates.
        eci_no = _int_or_none(src.get("Constituency_No"))
        if eci_no is None:
            continue
        entity_id = eci_to_entity.get(eci_no)
        if entity_id is None:
            unbound.add(eci_no)
            continue
        position = _int_or_none(src.get("Position"))
        rows.append(
            {
                "entity_id": entity_id,
                "state": state_slug,
                "election_year": election_year,
                "constituency_no": eci_no,
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
    rows.sort(
        key=lambda r: (r["constituency_no"], r["position"], r["candidate_name"])
    )
    return rows, unbound


def _round(value: float | None, places: int = 2) -> float | None:
    return None if value is None else round(value, places)


def recompute_summary_row(
    *,
    entity_id: str,
    state_slug: str,
    election_year: int,
    candidacy_rows: list[dict[str, Any]],
    ac_facts: dict[str, Any],
    source_id: str,
) -> dict[str, Any]:
    """Project one summary row from an AC's candidacy rows + electorate facts.

    winner / runner-up / margin are recomputed from ``candidacy_rows`` (NOTA is
    already excluded); electors / votes_polled / turnout are carried from
    ``ac_facts`` (not derivable from candidate rows). ``candidacy_rows`` MUST be
    non-empty (the caller groups by AC, so every group has >= 1 candidate).

    An UNCONTESTED seat (a single real candidate, e.g. an unopposed return in
    the North-East where TCPD records ``votes=0`` / ``share=nan``) has no
    runner-up: the runner-up + margin fields are emitted null (the contract
    widens them to nullable for exactly this case), and ``winner_share_pct`` is
    null when the source share is non-numeric.
    """
    ranked = sorted(candidacy_rows, key=lambda r: r["votes"], reverse=True)
    winner = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None

    winner_share = winner.get("vote_share_pct")
    runner_share = runner.get("vote_share_pct") if runner else None
    if runner is not None and winner_share is not None and runner_share is not None:
        margin_pct = _round(winner_share - runner_share)
    else:
        margin_pct = None

    return {
        "entity_id": entity_id,
        "state": state_slug,
        "election_year": election_year,
        "constituency_name": winner["constituency_name"],
        "electors": ac_facts.get("electors"),
        "votes_polled": ac_facts.get("votes_polled"),
        "turnout_pct": _round(ac_facts.get("turnout_pct")),
        "winner_candidate": winner["candidate_name"],
        "winner_party_id": winner.get("party_id"),
        "winner_party_short_raw": winner.get("party_short_raw"),
        "winner_votes": winner["votes"],
        "winner_share_pct": _round(winner_share),
        "runnerup_candidate": runner["candidate_name"] if runner else None,
        "runnerup_party_id": runner.get("party_id") if runner else None,
        "runnerup_party_short_raw": runner.get("party_short_raw") if runner else None,
        "runnerup_votes": runner["votes"] if runner else None,
        "margin_votes": (winner["votes"] - runner["votes"]) if runner else None,
        "margin_pct": margin_pct,
        "source_id": source_id,
    }


def emit_state_assembly(
    *,
    ae_csv: Path,
    electoral_csv: Path,
    out_root: Path,
    state_name_tcpd: str,
    state_slug: str,
    source_id: str,
    delim_id: str = DELIM_ID_2008,
    parties_csv: Path | None = None,
) -> dict[int, dict[str, Any]]:
    """Emit candidacies + summary CSVs for every election year of one state.

    Args:
        ae_csv: path to the TCPD ``All_States_AE.csv`` compilation.
        electoral_csv: path to ``datasets/data/entities/electoral.csv`` (entity bind).
        out_root: anchor for ``datasets/elections/`` (repo root; tests pass tmp_path).
        state_name_tcpd: the TCPD ``State_Name`` value (underscore form, e.g.
            ``"Tamil_Nadu"``).
        state_slug: the LGD state slug (e.g. ``"tamil-nadu"``).
        source_id: provenance stamp (resolvable in ``entities/source.csv``).
        delim_id: TCPD ``DelimID`` to emit (default the in-force 2008 cycle).
        parties_csv: optional path to ``datasets/data/entities/parties.csv``
            for the F1.3a v1.1 party-id resolution. When provided, the TCPD
            ``Party`` shortcode is resolved via
            :func:`party_lookup_from_parties_csv` and the resolved
            ``parties.IN.*`` id is written to every candidacy + summary row.
            When ``None`` (back-compat for tests + the v1 writer), every
            ``party_id`` is null.

    Returns:
        ``{year: {"candidacies": Path, "summary": Path, "n_candidacies": int,
        "n_summary": int, "unbound_eci_nos": sorted list}}`` per emitted year.
    """
    if not ae_csv.exists():
        raise FileNotFoundError(ae_csv)
    if not electoral_csv.exists():
        raise FileNotFoundError(electoral_csv)

    eci_to_entity = _electoral_eci_to_entity(_read_csv_rows(electoral_csv), state_slug)
    party_lookup = (
        party_lookup_from_parties_csv(parties_csv) if parties_csv is not None else {}
    )

    state_rows = [
        r
        for r in _read_csv_rows(ae_csv)
        if (r.get("State_Name") or "").strip() == state_name_tcpd
        and (r.get("DelimID") or "").strip() == delim_id
    ]

    by_year: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in state_rows:
        year = _int_or_none(row.get("Year"))
        if year is not None:
            by_year[year].append(row)

    emitted: dict[int, dict[str, Any]] = {}
    for year, year_rows in sorted(by_year.items()):
        final_poll_rows = _latest_poll_only(year_rows)
        candidacy_rows, unbound = build_candidacy_rows(
            source_rows=final_poll_rows,
            eci_to_entity=eci_to_entity,
            state_slug=state_slug,
            election_year=year,
            source_id=source_id,
            party_lookup=party_lookup,
        )
        if not candidacy_rows:
            continue  # every constituency this year was unbindable; nothing to emit.

        # AC-level electorate facts come straight off the source rows.
        ac_facts: dict[str, dict[str, Any]] = {}
        for src in final_poll_rows:
            eci_no = _int_or_none(src.get("Constituency_No"))
            if eci_no is None or eci_no not in eci_to_entity:
                continue
            entity_id = eci_to_entity[eci_no]
            if entity_id not in ac_facts:
                ac_facts[entity_id] = {
                    "electors": _int_or_none(src.get("Electors")),
                    "votes_polled": _int_or_none(src.get("Valid_Votes")),
                    "turnout_pct": _float_or_none(src.get("Turnout_Percentage")),
                }

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for cand in candidacy_rows:
            grouped[cand["entity_id"]].append(cand)

        summary_rows = [
            recompute_summary_row(
                entity_id=entity_id,
                state_slug=state_slug,
                election_year=year,
                candidacy_rows=group,
                ac_facts=ac_facts.get(entity_id, {}),
                source_id=source_id,
            )
            for entity_id, group in grouped.items()
        ]

        cand_path = assembly_candidacies_path(
            out_root=out_root, state_slug=state_slug, election_year=year
        )
        summ_path = assembly_summary_path(
            out_root=out_root, state_slug=state_slug, election_year=year
        )
        write_csv(path=cand_path, file_class=ASSEMBLY_CANDIDACIES_FC, rows=candidacy_rows)
        write_csv(path=summ_path, file_class=ASSEMBLY_SUMMARY_FC, rows=summary_rows)

        emitted[year] = {
            "candidacies": cand_path,
            "summary": summ_path,
            "n_candidacies": len(candidacy_rows),
            "n_summary": len(summary_rows),
            "unbound_eci_nos": sorted(unbound),
        }
    return emitted
