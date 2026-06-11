"""Per-event Compare-Aggregator - collapses Shape-B rows into per-AC verdicts.

EIP pipes-and-filters pattern; sibling of ``recon/aggregator.py`` which
verdicts at the party-roster grain. This module verdicts at the
(state, event, constituency_no) grain - one row per AC of the named
event.

Inputs:
  - ``parity_rows``: list of ``ConstituencyParityRow`` (per the Shape-B
    contract in ``recon/shape_b.py``). Each row carries one source's
    claim about the winner of one AC. Distinct ``external_scope`` values
    within one (state, event, constituency_no) group count as distinct
    oracles.

Outputs:
  - list of ``ConstituencyVerdictRow`` - one row per AC observed in the
    inputs. Stable order: sorted by ``constituency_no`` for reproducible
    verdict CSVs.

Verdict rule (Hans section 10 + Fowler machine-decidable per plan
section 0.5 ESCALATE #2):

  - ``VERIFIED``   iff n_oracles_present >= 2 AND all present oracles
                   agree on ``winner_party_id`` AND all present oracles
                   agree on ``winner_candidate_name`` (case-/punctuation-
                   normalised).
  - ``DISPUTED``   iff n_oracles_present >= 2 AND at least one oracle
                   disagrees on EITHER ``winner_party_id`` OR
                   ``winner_candidate_name``.
  - ``UNVERIFIED`` iff n_oracles_present < 2 (single source - cannot
                   corroborate).

The rule is purely structural; no LLM judgement. The aggregator NEVER
mutates the canonical store; it only emits verdict rows for the curator
script downstream (CLAUDE.md section 10 "auto-correct BANNED on
publisher disagreement" + Wave 0 / Hans verdict).

Per Holy Law #9: when an ECI source (yen-gov-elections is sourced from
ECI Statement 10 Detailed Results per the existing candidacies.csv
source_id chain) disagrees with another oracle, the verdict is still
DISPUTED. The curator's job is to record the disposition in the
``curator_note`` + ``curator_source_id`` columns - the aggregator
itself does not pre-resolve. ECI-wins is a CURATOR rule, not an
aggregator rule, so two operators reviewing the same verdict.csv can
both see the raw disagreement.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Literal

from .shape_b import ConstituencyParityRow

Verdict = Literal["VERIFIED", "DISPUTED", "UNVERIFIED"]


@dataclass(frozen=True, slots=True)
class ConstituencyVerdictRow:
    """One row of the per-constituency verdict CSV.

    Field order is the EMISSION order; the verdict CSV header is
    derived from ``fields(ConstituencyVerdictRow)``.
    """

    state: str
    event: str
    constituency_no: int
    constituency_name: str
    n_oracles_present: int
    n_oracles_agreeing_party: int
    n_oracles_agreeing_candidate: int
    yen_gov_winner_party_id: str
    yen_gov_winner_candidate_name: str
    yen_gov_winner_votes: int | None
    other_sources: str
    party_id_alliance: str
    verdict_party: Verdict
    verdict_candidate: Verdict
    verdict: Verdict
    curator_note: str | None = None
    curator_source_id: str | None = None


def verdict_event_csv_header() -> tuple[str, ...]:
    """Header order for the per-constituency verdict CSV."""
    return tuple(f.name for f in fields(ConstituencyVerdictRow))


# Reasonable punctuation noise stripped from candidate names before
# comparison. Different publishers report different conventions:
# yen-gov: "S.vijayakumar"; thecont1: "T.J.GOVINDARAJAN"; ECI: "T J
# GOVINDARAJAN". The normalisation collapses all dots / commas / dashes
# / extra spaces and uppercases. NOT a full name-resolver (that would
# need a dedicated curator-script) but enough to cancel publisher
# stylistic noise on the 90% case.
_CANDIDATE_NORMALISER = re.compile(r"[^A-Za-z0-9]+")


def _normalise_name(name: str) -> str:
    """Normalise a candidate name for cross-publisher comparison.

    Uppercases + collapses any run of non-alphanumeric to a single
    space + strips. ``"S.vijayakumar"`` -> ``"S VIJAYAKUMAR"``;
    ``"T.J.GOVINDARAJAN"`` -> ``"T J GOVINDARAJAN"``; ``"T J
    GOVINDARAJAN"`` -> ``"T J GOVINDARAJAN"``. Identical-after-
    normalisation strings count as agreement.
    """
    return _CANDIDATE_NORMALISER.sub(" ", (name or "").upper()).strip()


def compare_event(
    parity_rows: Iterable[ConstituencyParityRow],
    *,
    party_alliances: dict[tuple[str, str], str] | None = None,
) -> list[ConstituencyVerdictRow]:
    """Collapse Shape-B rows into per-constituency verdict rows.

    Grouping key: ``(state, event, constituency_no)``. Within each
    group, distinct ``external_scope`` values count as distinct oracles.

    The yen-gov side is preferentially used as the "primary" surface
    columns (``yen_gov_winner_party_id`` + ``yen_gov_winner_candidate_name``
    + ``yen_gov_winner_votes``) when the ``"yen-gov-elections"`` scope
    is present in the group. Other sources surface in
    ``other_sources`` as a pipe-delimited string
    (``"scope1:party:candidate:votes|scope2:..."``) ordered by scope
    name for reproducibility.

    Args:
        parity_rows: iterable of Shape-B rows from one or more event
            adapters (yen-gov-elections + zero or more external sources).
        party_alliances: optional ``(party_id, period_label) -> alliance``
            map from ``datasets/data/entities/party_alliances.csv``.
            When provided AND the yen-gov-side party_id has an entry,
            the alliance is surfaced in ``party_id_alliance``; otherwise
            the column is empty (the "alliance not yet curated" badge
            signal per Q6).

    Returns:
        list of ``ConstituencyVerdictRow`` sorted by ``constituency_no``.

    Raises:
        ValueError: a parity row carries ``constituency_no < 1``.
    """
    by_key: dict[tuple[str, str, int], list[ConstituencyParityRow]] = {}
    for row in parity_rows:
        if row.constituency_no < 1:
            raise ValueError(
                f"shape-B row carries invalid constituency_no="
                f"{row.constituency_no!r}; must be 1-based positive."
            )
        key = (row.state, row.event, row.constituency_no)
        by_key.setdefault(key, []).append(row)

    alliances = party_alliances or {}

    verdicts: list[ConstituencyVerdictRow] = []
    for key in sorted(by_key, key=lambda k: k[2]):
        state, event, ac_no = key
        group = by_key[key]
        oracles = sorted({r.external_scope for r in group})
        n_present = len(oracles)

        # yen-gov is the "primary" surface row; pick its values for the
        # leading columns. When yen-gov-elections is missing from the
        # group (degenerate corpus-vs-external-only sweep), the leading
        # columns are filled from the first source alphabetically and
        # the verdict columns still apply.
        yen_gov = next(
            (r for r in group if r.external_scope == "yen-gov-elections"),
            None,
        )
        primary = yen_gov if yen_gov is not None else min(
            group, key=lambda r: r.external_scope
        )

        # Constituency name from yen-gov when available; fall back to
        # the primary source (which is alphabetic-first when yen-gov
        # absent).
        constituency_name = primary.constituency_name

        # Verdict on party_id: agreement iff every present oracle's
        # canonical winner_party_id is identical. We use a set so any
        # disagreement is detected; n_oracles_agreeing_party is the
        # count of oracles that match the modal party_id.
        party_ids = {r.winner_party_id for r in group}
        if len(party_ids) == 1:
            n_agreeing_party = n_present
        else:
            # Count which party_id the most oracles agree on.
            counts: dict[str, int] = {}
            for r in group:
                counts[r.winner_party_id] = counts.get(r.winner_party_id, 0) + 1
            n_agreeing_party = max(counts.values())

        # Verdict on candidate name: same shape, with punctuation
        # normalisation.
        candidate_keys = {_normalise_name(r.winner_candidate_name) for r in group}
        if len(candidate_keys) == 1:
            n_agreeing_candidate = n_present
        else:
            counts_c: dict[str, int] = {}
            for r in group:
                k = _normalise_name(r.winner_candidate_name)
                counts_c[k] = counts_c.get(k, 0) + 1
            n_agreeing_candidate = max(counts_c.values())

        # Apply the Fowler machine-decidable rule per pair-of-dims.
        if n_present < 2:
            verdict_party: Verdict = "UNVERIFIED"
            verdict_candidate: Verdict = "UNVERIFIED"
        else:
            verdict_party = (
                "VERIFIED" if n_agreeing_party == n_present else "DISPUTED"
            )
            verdict_candidate = (
                "VERIFIED" if n_agreeing_candidate == n_present else "DISPUTED"
            )

        # Combined verdict: VERIFIED iff BOTH dims VERIFIED; UNVERIFIED
        # iff EITHER dim UNVERIFIED; otherwise DISPUTED. This is
        # citizen-facing: a row whose party agrees but candidate
        # diverges is still a curator-decision (publisher might have
        # mis-transcribed the candidate name even though party is
        # right).
        if verdict_party == "UNVERIFIED" or verdict_candidate == "UNVERIFIED":
            verdict: Verdict = "UNVERIFIED"
        elif verdict_party == "VERIFIED" and verdict_candidate == "VERIFIED":
            verdict = "VERIFIED"
        else:
            verdict = "DISPUTED"

        # Format other_sources as pipe-delimited
        # "scope:party_id:candidate:votes" for every source EXCEPT the
        # primary. yen-gov as primary is omitted from other_sources;
        # external sources are sorted alphabetically by scope for
        # reproducibility.
        other_rows = [r for r in group if r is not primary]
        other_rows_sorted = sorted(other_rows, key=lambda r: r.external_scope)
        other_parts: list[str] = []
        for r in other_rows_sorted:
            votes_str = "" if r.winner_votes is None else str(r.winner_votes)
            # Pipe-delimit fields with ":"; pipe is the row separator so
            # we don't need to escape it here (no field carries a colon
            # in the citizen-data domain - publisher names + party slugs
            # + integer votes are all colon-free).
            other_parts.append(
                f"{r.external_scope}:{r.winner_party_id}:"
                f"{r.winner_candidate_name}:{votes_str}"
            )
        other_sources_str = "|".join(other_parts)

        # Alliance surfacing per Q6: read the yen-gov-side party_id
        # (the canonical surface) and look up (party_id, event) in
        # the party_alliances map. Empty when unmapped - that's the
        # "alliance not yet curated for this event" badge signal.
        alliance = alliances.get((primary.winner_party_id, event), "")

        verdicts.append(
            ConstituencyVerdictRow(
                state=state,
                event=event,
                constituency_no=ac_no,
                constituency_name=constituency_name,
                n_oracles_present=n_present,
                n_oracles_agreeing_party=n_agreeing_party,
                n_oracles_agreeing_candidate=n_agreeing_candidate,
                yen_gov_winner_party_id=primary.winner_party_id,
                yen_gov_winner_candidate_name=primary.winner_candidate_name,
                yen_gov_winner_votes=primary.winner_votes,
                other_sources=other_sources_str,
                party_id_alliance=alliance,
                verdict_party=verdict_party,
                verdict_candidate=verdict_candidate,
                verdict=verdict,
                curator_note=None,
                curator_source_id=None,
            )
        )

    return verdicts


def write_event_verdict_csv(
    verdicts: list[ConstituencyVerdictRow], path: Path
) -> int:
    """Write per-constituency verdict rows to ``path`` as CSV.

    ``None`` values are serialised as empty strings (the citizen-UI /
    curator never wants the literal ``"None"`` in the ledger). Returns
    the number of rows written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    header = verdict_event_csv_header()
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in verdicts:
            d = asdict(row)
            for k, v in list(d.items()):
                if v is None:
                    d[k] = ""
            writer.writerow(d)
    return len(verdicts)


__all__ = [
    "ConstituencyVerdictRow",
    "Verdict",
    "compare_event",
    "verdict_event_csv_header",
    "write_event_verdict_csv",
]
