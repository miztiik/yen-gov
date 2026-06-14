"""G16 parliament 2024 election emitter (ECI raw, plan section 21.3 row 37).

Reads the local Election Commission of India "Statement 33" raw CSV
(``2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv``,
candidate-grain) and emits the two per-election parliament CSV file classes
for the LS2024 cycle:

- ``elections/parliament/election=2024/candidacies.csv``
- ``elections/parliament/election=2024/summary.csv``

Why this exists separately from :mod:`parliament_results` (which sources from
TCPD ``All_States_GE.csv``): TCPD's compilation lags the cycle. As of the G16
authoring date (2026-06-09) the TCPD GE snapshot at ``2026-06-05`` carries
cycles through 2021 only; the LS2024 cycle, the largest civic event of the
decade, is missing from the canonical store. This module ingests directly from
the ECI publisher edition so the LS2024 election is available on the same
``elections/parliament/election=<year>/`` shape as the historical cycles. A
later session can reconcile against TCPD once their LS2024 compilation lands.

Three ECI-specific contracts realised here (parent plan section 21.3 / 23.4):

1. **Single-step PC bind** (orchestrator finding 5). ``electoral.csv`` carries
   PC entities with ``eci_no = 0`` for several states (Andhra Pradesh, Bihar,
   Kerala, etc) because the upstream LGD snapshot does not consistently
   populate the ECI ballot serial. The classical two-step bind
   ``(state, pc_name) -> eci_no`` then ``(state, eci_no) -> entity_id`` would
   COLLIDE those PCs onto each other. Instead we build a single-step
   ``(state_slug, normalised_pc_name) -> (entity_id, eci_no_from_spine)``
   lookup (PC name IS unique per state in the spine), and emit the spine's
   ``eci_no`` verbatim into the ``constituency_no`` column (may be ``0`` when
   the spine does not know it - documented schema-correct gap, not a writer
   bug). A future spine improvement that populates the missing ``eci_no``
   values is picked up by a single re-emit.
2. **PC turnout computed, not lifted verbatim** (deviation from the
   orchestrator brief's column pick). The ECI raw carries three per-candidate
   "Over Total ..." columns that are all CANDIDATE-LEVEL shares (candidate
   votes / electors, / polled, / valid respectively). None of them is the
   PC-level turnout that the existing 2009..2019 LS summaries carry. We
   therefore compute ``turnout_pct = (votes_polled / electors) * 100`` from
   the PC-level fields ("Total Votes Polled In The Constituency" and "Total
   Electors") so the LS2024 summary semantics match the historical cycles
   (turnout = polled / electors, not candidate-vote-share-of-electors).
3. **No deposit-lost / incumbent / turncoat / education / profession**
   (publisher gap). The ECI raw does not carry those fields; the schema makes
   them nullable. ``result`` collapses to ``"won"`` / ``"lost"`` for LS2024
   (the ``"forfeit"`` distinction is unavailable - TCPD compilations carry it
   from MyNeta affidavits, which the ECI publisher edition does not include).
   ``candidate_type`` defaults to ``"challenger"`` for the same reason.

Source row: ONE citation for the whole ECI raw file per ADR-0042
(publisher edition vintage; one-origin-per-snapshot). The canonical store
already carries the LS2024 ECI citation at ``src-bfb4e7fb9785`` (owner
"Election Commission of India", title "General Election to Lok Sabha 2024
\u2014 Constituency Wise Detailed Result (Report 33)", vintage "2024"); the
``_run_parliament_2024_eci`` driver derives the same id from the same triple
and the existing row is reused via ``_ensure_source_row`` no-op.

Delimitation: bound to ``IN-PC-2008-<state>-<pc_no>``. LS2024 was held under
the 2008-delim PC boundaries (the 2024 delimitation order takes effect for the
LS2029 cycle).

No network, no parquet, no ``urls.py`` / ``core.http`` import. Pure helpers
(``parse_eci_raw_2024_csv``, ``build_parliament_2024``) take in-memory rows so
the parity-oracle gate can assert ``summary == recompute(candidacies)``
without touching disk.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.name_normaliser import normalise_entity_name
from yen_gov.canonical.processing_quality import derive_processing
from yen_gov.canonical.reingest.assembly_results import (
    NOTA_TOKENS,
    _float_or_none,
    _int_or_none,
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

__all__ = [
    "parse_eci_raw_2024_csv",
    "build_parliament_2024",
    "emit_parliament_2024",
]

# ECI Statement 33 raw CSV column names (with the embedded LF in the
# "polled in the constituency" header preserved by ``csv.DictReader``).
_COL_STATE = "State Name"
_COL_PC = "PC Name"
_COL_CANDIDATE = "Candidate Name"
_COL_GENDER = "Gender"
_COL_AGE = "Age"
_COL_PARTY = "Party Name"
_COL_POLLED = "Total Votes Polled In\nThe Constituency"
_COL_VALID = "Valid Votes"
_COL_VOTES = "Total"
_COL_SHARE_OF_VALID = "Over Total Valid Votes Polled In Constituency"
_COL_ELECTORS = "Total Electors"

# ECI uses publisher-specific state spellings that the LGD slug map does not
# carry directly. The override map handles the ECI-only forms; everything else
# falls through the generic " & " -> " and " + space -> hyphen rule.
_ECI_STATE_OVERRIDES: dict[str, str] = {
    "andaman & nicobar islands": "andaman-and-nicobar-islands",
    "dadra & nagar haveli and daman & diu": "dadra-and-nagar-haveli-and-daman-and-diu",
    "jammu and kashmir": "jammu-and-kashmir",
    "jammu & kashmir": "jammu-and-kashmir",
    "nct of delhi": "delhi",
    "delhi": "delhi",
}

LS2024_ELECTION_YEAR: int = 2024


def parse_eci_raw_2024_csv(path: Path) -> list[dict[str, str]]:
    """Read the ECI Statement 33 raw CSV, skipping the 2-row banner header.

    The raw file's first two lines are the ECI report banner + a quasi-header
    spacing row; the third line is the real ``csv.DictReader`` header. The
    file is BOM-prefixed (``utf-8-sig`` strips it transparently). The embedded
    LF inside the "polled in the constituency" header is properly quoted so
    ``DictReader`` resolves it to the single column key ``_COL_POLLED``.

    Returns the raw row dicts with no filtering applied. Callers (see
    :func:`build_parliament_2024`) drop disclaimer / note rows (empty
    ``PC Name``) and NOTA rows downstream.
    """
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    if len(lines) < 3:
        raise ValueError(f"ECI raw CSV at {path.as_posix()} has fewer than 3 lines")
    body = "".join(lines[2:])
    return list(csv.DictReader(io.StringIO(body)))


def _normalise_pc_name(name: str) -> str:
    """Resolver-side PC name normaliser.

    Delegates to the shared :func:`normalise_entity_name` (case-fold +
    whitespace-collapse + hyphen/underscore/dash-collapse). Lifted to the
    shared module 2026-06-09 by the G16 alias backfill PR; previously this was
    a per-module helper that only collapsed whitespace (and therefore could
    not bind ``Mumbai North East`` <-> ``Mumbai North-East``).
    """
    return normalise_entity_name(name)


def _slugify_eci_state(name: str) -> str:
    """Map an ECI ``State Name`` to its LGD state slug.

    Applies the publisher-specific overrides first (``"NCT OF Delhi"`` ->
    ``"delhi"``, ampersand spellings) then falls through to lowercase + space
    -> hyphen for the bulk of the 36 states/UTs. Empty input returns the empty
    string (callers filter on ``state_slug not in pc_lookup`` rather than
    raising here - keeps the parser pure-data).
    """
    if not name:
        return ""
    lowered = name.strip().lower()
    if lowered in _ECI_STATE_OVERRIDES:
        return _ECI_STATE_OVERRIDES[lowered]
    return lowered.replace(" & ", "-and-").replace(" ", "-")


def _build_pc_lookup(
    electoral_csv: Path,
) -> dict[tuple[str, str], tuple[str, int]]:
    """Single-step ``(state_slug, normalised_pc_name) -> (entity_id, eci_no)``.

    Sidesteps the ``eci_no == 0`` collision documented in the module docstring
    (Andhra Pradesh / Bihar / Kerala carry multiple PCs with ``eci_no = 0`` in
    the LGD-derived spine). PC ``name`` IS unique per state in
    ``electoral.csv`` so the (state, name) key is total.

    Walks BOTH the ``name`` column AND the pipe-delimited ``aliases`` column,
    registering the same ``(entity_id, eci_no)`` value under every normalised
    name variant. This is how publisher-emitted names that differ from the
    LGD-canonical (e.g. ECI ``Bangalore North`` <-> spine ``Bengaluru North``)
    bind: the alias-backfill PR adds the ECI variant to the ``aliases`` cell
    and this lookup picks it up at the next ingest run. Per-state collisions
    are detected and raise ``ValueError`` rather than silently overwriting
    (defensive: collisions would mean two spine PC rows share a name, which
    violates the per-state-name-uniqueness invariant).

    Restricted to ``entity_kind == 'pc'`` AND ``delim_year == '2008'`` (the
    delimitation in force for LS2024).
    """
    out: dict[tuple[str, str], tuple[str, int]] = {}
    with electoral_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("entity_kind") != "pc":
                continue
            if (row.get("delim_year") or "").strip() != "2008":
                continue
            state_slug = (row.get("state") or "").strip()
            if not state_slug:
                continue
            raw_eci = (row.get("eci_no") or "").strip()
            try:
                eci_no = int(raw_eci) if raw_eci else 0
            except ValueError:
                eci_no = 0
            payload = (row["entity_id"], eci_no)
            # Variant set: the canonical ``name`` plus each pipe-delimited alias.
            variants = [(row.get("name") or "").strip()]
            for alias in ((row.get("aliases") or "").split("|")):
                alias = alias.strip()
                if alias:
                    variants.append(alias)
            for variant in variants:
                key = (state_slug, _normalise_pc_name(variant))
                if not key[1]:
                    continue
                existing = out.get(key)
                if existing is not None and existing != payload:
                    raise ValueError(
                        f"PC name collision on (state={state_slug!r}, "
                        f"normalised={key[1]!r}): existing={existing} new={payload}"
                    )
                out[key] = payload
    return out


def _is_real_candidate_row(row: dict[str, str]) -> bool:
    """Drop disclaimer / note / empty rows.

    The ECI raw appends three garbage rows at the tail (a "Note ...", a
    "Disclaimer", and a "These statistical reports ..." text block) where the
    long disclaimer text is stuffed into ``State Name`` and ``PC Name`` is
    empty. The same shape covers blank trailing rows. A single PC-Name-empty
    test cleanly excludes both classes.
    """
    return bool((row.get(_COL_PC) or "").strip() and (row.get(_COL_STATE) or "").strip())


def build_parliament_2024(
    *,
    source_rows: list[dict[str, str]],
    pc_lookup: dict[tuple[str, str], tuple[str, int]],
    source_id: str,
    party_lookup: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[tuple[str, str]]]:
    """Build ``(candidacies, summary, unbound)`` from the ECI raw rows.

    Args:
        source_rows: raw ECI Statement 33 rows (already 2-line-header stripped
            by :func:`parse_eci_raw_2024_csv`).
        pc_lookup: single-step ``(state_slug, normalised_pc_name) ->
            (entity_id, eci_no_from_spine)`` map from :func:`_build_pc_lookup`.
        source_id: provenance stamp (resolvable in ``entities/source.csv``).
        party_lookup: optional ``upper(short) -> party_id`` map from
            :func:`assembly_results.party_lookup_from_parties_csv`.

    Returns:
        Three values:
        - ``candidacies``: NOTA-excluded, position-assigned candidate rows
          (sorted by ``(state, constituency_no, position, candidate_name)``).
        - ``summary``: per-PC recomputed projection
          (one row per bound PC; ``summary == recompute(candidacies)`` by
          construction).
        - ``unbound``: set of ``(state_slug, original_pc_name)`` pairs that
          did not resolve to an ``electoral.csv`` PC entity (Delhi PCs are the
          standing example; surfaced in the coverage receipt, not silently
          dropped).
    """
    lookup = party_lookup or {}

    grouped_raw: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pc_facts: dict[str, dict[str, Any]] = {}
    pc_meta: dict[str, dict[str, str]] = {}
    unbound: set[tuple[str, str]] = set()

    for src in source_rows:
        if not _is_real_candidate_row(src):
            continue
        raw_state = (src.get(_COL_STATE) or "").strip()
        raw_pc = (src.get(_COL_PC) or "").strip()
        state_slug = _slugify_eci_state(raw_state)
        pc_key = (state_slug, _normalise_pc_name(raw_pc))
        bind = pc_lookup.get(pc_key)
        if bind is None:
            unbound.add((state_slug, raw_pc))
            continue
        entity_id, eci_no_spine = bind

        raw_party = (src.get(_COL_PARTY) or "").strip()
        if raw_party.upper() in NOTA_TOKENS:
            continue  # NOTA is a ballot option, not a candidate.

        votes = _int_or_none(src.get(_COL_VOTES)) or 0
        # PR (2026-06-14): see assembly_results.build_candidacy_rows for the
        # processing_level + processing_note doctrine; UNK fall-through is
        # the only fresh-write trigger for ``major``.
        party_id_resolved = lookup.get(raw_party.upper()) or "parties.IN.UNK"
        proc_level, proc_note = derive_processing(party_id_resolved, raw_party)
        cand: dict[str, Any] = {
            "entity_id": entity_id,
            "state": state_slug,
            "election_year": LS2024_ELECTION_YEAR,
            "constituency_no": eci_no_spine,
            "constituency_name": raw_pc,
            "candidate_name": _text_or_none(src.get(_COL_CANDIDATE)) or "",
            # PR-3 (2026-06-10): every candidacy row carries a non-empty
            # canonical party_id. See assembly_results.build_candidacy_rows
            # for the rationale (mirror of party_resolver.SENTINELS['UNK']).
            "party_id": party_id_resolved,
            "party_short_raw": raw_party or None,
            "votes": votes,
            "vote_share_pct": _float_or_none(src.get(_COL_SHARE_OF_VALID)),
            # position filled in after the group sort, below.
            "position": 0,
            # result derived from position once positions are assigned.
            "result": "lost",
            "sex": _sex(src.get(_COL_GENDER)),
            "age": _int_or_none(src.get(_COL_AGE)),
            "education": None,  # ECI raw does not carry MyNeta-style affidavit fields.
            "profession": None,
            "candidate_type": "challenger",
            "source_id": source_id,
            "processing_level": proc_level,
            "processing_note": proc_note,
        }
        grouped_raw[entity_id].append(cand)

        if entity_id not in pc_facts:
            electors = _int_or_none(src.get(_COL_ELECTORS))
            polled = _int_or_none(src.get(_COL_POLLED))
            # PC-level turnout = polled / electors * 100. Computed (not lifted)
            # because the ECI raw's "Over Total ..." columns are all candidate
            # shares; see module docstring section 2.
            if electors and polled is not None and electors > 0:
                turnout_pct: float | None = round(polled / electors * 100.0, 2)
            else:
                turnout_pct = None
            pc_facts[entity_id] = {
                "electors": electors,
                # votes_polled = gross polled (matches the historical-cycle
                # semantics in elections/parliament/election=2019/summary.csv).
                "votes_polled": polled,
                "turnout_pct": turnout_pct,
            }
            pc_meta[entity_id] = {"state": state_slug, "constituency_name": raw_pc}

    # Assign position 1..N per PC by votes descending; derive result.
    candidacies: list[dict[str, Any]] = []
    for entity_id, group in grouped_raw.items():
        ranked = sorted(group, key=lambda r: r["votes"], reverse=True)
        for idx, cand in enumerate(ranked, start=1):
            cand["position"] = idx
            cand["result"] = _result(idx, None)
            candidacies.append(cand)

    candidacies.sort(
        key=lambda r: (r["state"], r["constituency_no"], r["position"], r["candidate_name"])
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cand in candidacies:
        grouped[cand["entity_id"]].append(cand)

    summary: list[dict[str, Any]] = [
        recompute_summary_row(
            entity_id=entity_id,
            state_slug=pc_meta[entity_id]["state"],
            election_year=LS2024_ELECTION_YEAR,
            candidacy_rows=group,
            ac_facts=pc_facts.get(entity_id, {}),
            source_id=source_id,
        )
        for entity_id, group in grouped.items()
    ]

    return candidacies, summary, unbound


def emit_parliament_2024(
    *,
    eci_csv: Path,
    electoral_csv: Path,
    out_root: Path,
    source_id: str,
    parties_csv: Path | None = None,
) -> dict[str, Any]:
    """Emit candidacies + summary CSVs for the LS2024 cycle.

    Args:
        eci_csv: path to the ECI Statement 33 raw CSV
            (``datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv``).
        electoral_csv: path to ``datasets/data/entities/electoral.csv``.
        out_root: anchor for ``datasets/elections/`` (repo root; tests pass
            ``tmp_path``).
        source_id: provenance stamp for every emitted row.
        parties_csv: optional path to ``datasets/data/entities/parties.csv``
            for F1.3a v1.2 + G1 party-id resolution.

    Returns:
        ``{"candidacies": Path, "summary": Path, "n_candidacies": int,
        "n_summary": int, "states": int, "unbound": sorted list, "raw_rows":
        int}`` for the single LS2024 cycle.
    """
    if not eci_csv.exists():
        raise FileNotFoundError(eci_csv)
    if not electoral_csv.exists():
        raise FileNotFoundError(electoral_csv)

    raw_rows = parse_eci_raw_2024_csv(eci_csv)
    pc_lookup = _build_pc_lookup(electoral_csv)
    party_lookup = (
        party_lookup_from_parties_csv(parties_csv) if parties_csv is not None else {}
    )

    candidacies, summary, unbound = build_parliament_2024(
        source_rows=raw_rows,
        pc_lookup=pc_lookup,
        source_id=source_id,
        party_lookup=party_lookup,
    )

    cand_path = parliament_candidacies_path(
        out_root=out_root, election_year=LS2024_ELECTION_YEAR
    )
    summ_path = parliament_summary_path(
        out_root=out_root, election_year=LS2024_ELECTION_YEAR
    )
    write_csv(path=cand_path, file_class=PARLIAMENT_CANDIDACIES_FC, rows=candidacies)
    write_csv(path=summ_path, file_class=PARLIAMENT_SUMMARY_FC, rows=summary)

    return {
        "candidacies": cand_path,
        "summary": summ_path,
        "n_candidacies": len(candidacies),
        "n_summary": len(summary),
        "states": len({c["state"] for c in candidacies}),
        "unbound": sorted(unbound),
        "raw_rows": len(raw_rows),
    }
