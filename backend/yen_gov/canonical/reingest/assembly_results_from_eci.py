"""ECI Section 10 -> partitioned candidacies + summary emitter.

Bridges the LEGACY ``eci-statreport-emit-local`` output
(``datasets/elections/<event>/<state>/results.csv``, denormalised one-row-per-
candidate) into the NEW partitioned shape the citizen frontend reads:

  ``datasets/elections/assembly/state=<slug>/election=<year>/candidacies.csv``
  ``datasets/elections/assembly/state=<slug>/election=<year>/summary.csv``

WHY a separate module (vs extending ``assembly_results.py``):

  ``assembly_results.py`` reads the TCPD ``All_States_AE.csv`` compilation,
  which lags ECI by months-to-years (TCPD compiled to 2023 as of 2026-06).
  A fresh assembly poll (e.g. AcGenMay2026 - TN/KL/WB/AS/PY) is only
  available through ECI Section 10 Detailed Results XLSXes, which the
  legacy ``eci-statreport-emit-local`` already parses + emits as
  ``results.csv``. This module is the second leg of that pipeline: it
  pivots the legacy CSV into the same partitioned shape ``emit_state_assembly``
  produces from TCPD, reusing ``recompute_summary_row`` + the
  ``ASSEMBLY_CANDIDACIES_FC`` / ``ASSEMBLY_SUMMARY_FC`` file_class validators.

ECI Section 10 columns -> partitioned shape:

  - ``ac_eci_no``           -> ``constituency_no`` + electoral.csv entity bind
  - ``constituency_name``   -> ``constituency_name``
  - ``electors`` / ``votes_polled`` / ``turnout_pct`` -> ``ac_facts``
  - ``candidate_name``      -> ``candidate_name``
  - ``party_short``         -> ``party_short_raw`` (+ ``party_id`` via
                                ``party_lookup_from_parties_csv``)
  - ``votes``               -> ``votes``
  - ``vote_share_pct``      -> ``vote_share_pct``
  - ``rank``                -> ``position`` + ``result``
                                (rank == 1 ? "won" : "lost"; ECI has no
                                deposit-lost flag)
  - ``gender``              -> ``sex`` (M/F/T; U if missing)
  - ``age``                 -> ``age``
  - (no source column for ``education`` / ``profession`` / ``candidate_type``;
    all three nullable in the schema and emitted null - the TCPD-based
    emitter populates them from TCPD-specific columns that ECI does not
    publish. This is the documented degraded path until MyNeta / TCPD
    backfills become available for the cohort.)
  - ``is_nota == 1``        -> SKIP (NOTA is a ballot option, not a candidate;
                                same convention as the TCPD path)

No network. No XLSX parsing here (the legacy command did that already; this
module is pure CSV-in / CSV-out so a follow-up re-parse + re-emit is a
two-step replay, not a re-download).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.reingest.assembly_results import (
    NOTA_TOKENS,
    party_lookup_from_parties_csv,
    recompute_summary_row,
)
from yen_gov.canonical.reingest.elections import (
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
    assembly_candidacies_path,
    assembly_summary_path,
)

__all__ = [
    "build_candidacy_rows_from_eci_legacy",
    "emit_state_assembly_from_eci_legacy",
]


# ---------- small parsers --------------------------------------------------- #


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _sex(raw: Any) -> str | None:
    """Map ECI Section 10 ``gender`` to the schema enum.

    ECI publishes ``M`` / ``F`` / (occasionally) ``T``/``O``; blank for some
    historical countermanded candidates. Schema accepts ``M`` / ``F`` / ``T``
    / ``U`` (unknown). Anything not in the recognised set collapses to ``U``.
    """
    s = (str(raw or "").strip() or "U").upper()
    if s in ("M", "F", "T"):
        return s
    return "U"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _electoral_eci_to_entity(
    electoral_rows: list[dict[str, str]], state_slug: str
) -> dict[int, str]:
    """Build ``eci_no -> entity_id`` for one state from electoral.csv.

    Only assembly (``entity_kind == "ac"``) entities for the given state are
    considered; PC + alliance + other entity kinds are filtered out.
    """
    out: dict[int, str] = {}
    for row in electoral_rows:
        if (row.get("state") or "").strip() != state_slug:
            continue
        if (row.get("entity_kind") or "").strip() != "ac":
            continue
        eci_no = _int_or_none(row.get("eci_no"))
        entity_id = (row.get("entity_id") or "").strip()
        if eci_no is None or not entity_id:
            continue
        out[eci_no] = entity_id
    return out


# ---------- builders -------------------------------------------------------- #


def build_candidacy_rows_from_eci_legacy(
    *,
    source_rows: list[dict[str, str]],
    eci_to_entity: dict[int, str],
    state_slug: str,
    election_year: int,
    source_id: str,
    party_lookup: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], set[int]]:
    """Pivot legacy ``results.csv`` rows into candidacies-shape dicts.

    Returns ``(rows, unbound_eci_nos)`` mirroring
    :func:`assembly_results.build_candidacy_rows`. NOTA rows are excluded
    (``is_nota == 1``); rows whose ``ac_eci_no`` does not bind to an
    ``electoral.csv`` AC entity for ``state_slug`` are skipped and the
    eci_no recorded in ``unbound_eci_nos`` for the coverage receipt.
    """
    lookup = party_lookup or {}
    rows: list[dict[str, Any]] = []
    unbound: set[int] = set()
    for src in source_rows:
        # NOTA filter (`is_nota` is "0"/"1" in the legacy emit).
        if (src.get("is_nota") or "").strip() == "1":
            continue
        raw_party = (src.get("party_short") or "").strip()
        if raw_party.upper() in NOTA_TOKENS:
            continue
        eci_no = _int_or_none(src.get("ac_eci_no"))
        if eci_no is None:
            continue
        entity_id = eci_to_entity.get(eci_no)
        if entity_id is None:
            unbound.add(eci_no)
            continue
        position = _int_or_none(src.get("rank"))
        is_winner = (src.get("is_winner") or "").strip() == "1"
        rows.append(
            {
                "entity_id": entity_id,
                "state": state_slug,
                "election_year": election_year,
                "constituency_no": eci_no,
                "constituency_name": _text_or_none(src.get("constituency_name")) or "",
                "candidate_name": _text_or_none(src.get("candidate_name")) or "",
                "party_id": lookup.get(raw_party.upper()) if raw_party else None,
                "party_short_raw": raw_party or None,
                "votes": _int_or_none(src.get("votes")) or 0,
                "vote_share_pct": _float_or_none(src.get("vote_share_pct")),
                "position": position if position is not None else 0,
                # ECI Section 10 has no "deposit lost" column; the
                # citizen-facing distinction between rank>1 (lost) and
                # rank=1 (won) is all we can infer.
                "result": "won" if is_winner else "lost",
                "sex": _sex(src.get("gender")),
                "age": _int_or_none(src.get("age")),
                # Not present in ECI Section 10 (TCPD has these via MyNeta
                # + manual classification). Emitted null per the
                # schema's nullability; can be backfilled in a follow-on
                # PR once a MyNeta/TCPD slice exists for the cohort.
                "education": None,
                "profession": None,
                "candidate_type": None,
                "source_id": source_id,
            }
        )
    rows.sort(
        key=lambda r: (r["constituency_no"], r["position"], r["candidate_name"])
    )
    return rows, unbound


# ---------- driver ---------------------------------------------------------- #


def emit_state_assembly_from_eci_legacy(
    *,
    eci_legacy_csv: Path,
    electoral_csv: Path,
    out_root: Path,
    state_slug: str,
    election_year: int,
    source_id: str,
    parties_csv: Path | None = None,
) -> dict[str, Any]:
    """Emit candidacies + summary CSVs for one state-year from ECI legacy CSV.

    Args:
        eci_legacy_csv: path to ``datasets/elections/<event>/<state>/results.csv``
            produced by ``eci-statreport-emit-local``.
        electoral_csv: path to ``datasets/data/entities/electoral.csv`` for
            the entity bind.
        out_root: repo-root anchor for ``datasets/elections/`` (tests pass
            ``tmp_path``).
        state_slug: LGD slug (e.g. ``"tamil-nadu"``).
        election_year: four-digit year (e.g. ``2026``).
        source_id: provenance stamp; must already exist in
            ``datasets/data/entities/source.csv``.
        parties_csv: optional ``parties.csv`` for the F1.3a v1.1 party-id
            shortcode resolution. When ``None``, all ``party_id`` columns
            stay null (back-compat for tests).

    Returns:
        ``{"candidacies": Path, "summary": Path, "n_candidacies": int,
        "n_summary": int, "unbound_eci_nos": sorted list}``.
    """
    if not eci_legacy_csv.exists():
        raise FileNotFoundError(eci_legacy_csv)
    if not electoral_csv.exists():
        raise FileNotFoundError(electoral_csv)

    eci_to_entity = _electoral_eci_to_entity(
        _read_csv_rows(electoral_csv), state_slug
    )
    party_lookup = (
        party_lookup_from_parties_csv(parties_csv) if parties_csv is not None else {}
    )

    source_rows = _read_csv_rows(eci_legacy_csv)
    candidacy_rows, unbound = build_candidacy_rows_from_eci_legacy(
        source_rows=source_rows,
        eci_to_entity=eci_to_entity,
        state_slug=state_slug,
        election_year=election_year,
        source_id=source_id,
        party_lookup=party_lookup,
    )

    # AC-level electorate facts: electors / votes_polled / turnout_pct are
    # repeated per candidate in the legacy results.csv (one ECI row per
    # candidacy). Take the first sighting per entity_id - they are
    # invariant within an AC and the source order is constituency-ordered.
    ac_facts: dict[str, dict[str, Any]] = {}
    for src in source_rows:
        eci_no = _int_or_none(src.get("ac_eci_no"))
        if eci_no is None or eci_no not in eci_to_entity:
            continue
        entity_id = eci_to_entity[eci_no]
        if entity_id in ac_facts:
            continue
        ac_facts[entity_id] = {
            "electors": _int_or_none(src.get("electors")),
            "votes_polled": _int_or_none(src.get("votes_polled")),
            "turnout_pct": _float_or_none(src.get("turnout_pct")),
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cand in candidacy_rows:
        grouped[cand["entity_id"]].append(cand)

    summary_rows = [
        recompute_summary_row(
            entity_id=entity_id,
            state_slug=state_slug,
            election_year=election_year,
            candidacy_rows=group,
            ac_facts=ac_facts.get(entity_id, {}),
            source_id=source_id,
        )
        for entity_id, group in grouped.items()
    ]

    cand_path = assembly_candidacies_path(
        out_root=out_root, state_slug=state_slug, election_year=election_year
    )
    summ_path = assembly_summary_path(
        out_root=out_root, state_slug=state_slug, election_year=election_year
    )
    write_csv(path=cand_path, file_class=ASSEMBLY_CANDIDACIES_FC, rows=candidacy_rows)
    write_csv(path=summ_path, file_class=ASSEMBLY_SUMMARY_FC, rows=summary_rows)

    return {
        "candidacies": cand_path,
        "summary": summ_path,
        "n_candidacies": len(candidacy_rows),
        "n_summary": len(summary_rows),
        "unbound_eci_nos": sorted(unbound),
    }
