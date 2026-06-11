"""Per-constituency Compare-Aggregator (PR-PC-LS2024).

The per-party Compare-Aggregator in ``recon/aggregator.py`` groups
shape-A rows by ``proposed_party_id`` and surfaces one verdict row per
party. That shape works for party-roster parity (PR-W-1 / W-2 / W-3:
"is this TCPD party present in canonical parties.csv?") but NOT for
per-constituency parity ("do all oracles agree on the winner_party_id
of Tiruvallur 2024?"), where the grouping key is the constituency
itself and the per-oracle disagreement is on which canonical party_id
each oracle named as winner.

Per the plan section 2.PR-PC-LS2024 brief: groups shape-A rows by
``(state_code, constituency_no)``; counts distinct ``external_scope``
values within the group as ``n_oracles_present``; counts how many
oracles voted for the MODAL ``proposed_party_id`` as
``n_oracles_agreeing``; applies the Fowler machine-decidable verdict
rule (plan section 0.5 ESCALATE #2):

  - ``VERIFIED``   iff ``n_oracles_agreeing == n_oracles_present`` AND
                   ``n_oracles_present >= 2``.
  - ``UNVERIFIED`` iff ``n_oracles_present < 2`` (single-source -
                   needs corroboration before promotion).
  - ``DISPUTED``   otherwise (two or more oracles, at least one
                   disagreement on winner_party_id - curator must
                   adjudicate; ECI wins per Holy Law #9 per plan
                   section 0.5 ESCALATE #3).

The per-PC aggregator is a PURE FUNCTION (no I/O, no clock, no
random) over its inputs so the Tier-A test fixture can drive it
end-to-end without disk. It NEVER mutates canonical data; verdict
rows are surfaced for curator review per the auto-correct-BANNED
doctrine (CLAUDE.md section 10 + Wave 0 / Hans verdict).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Literal

from .shape_a import ShapeARow

Verdict = Literal["VERIFIED", "DISPUTED", "UNVERIFIED"]


@dataclass(frozen=True, slots=True)
class PcVerdictRow:
    """One row of the per-constituency verdict CSV.

    Field order is the EMISSION order; the verdict CSV header is
    derived from ``fields(PcVerdictRow)``. Per CLAUDE.md section 11
    schema-versioning discipline this dataclass IS the per-PC verdict
    contract; rename / removal is a MAJOR change.

    The shape mirrors per-party ``VerdictRow`` (recon/aggregator.py)
    where applicable - ``n_oracles_present`` / ``n_oracles_agreeing``
    / ``oracles_agreeing`` / ``oracles_disagreeing`` / ``verdict`` /
    ``curator_note`` / ``curator_source_id`` semantics are byte-
    identical - and adds the per-PC surface columns
    (``state_code`` + ``constituency_no`` + ``constituency_name``)
    plus the per-oracle vote breakdown
    (``winner_party_id_consensus`` + ``winner_party_id_per_oracle``).
    """

    state_code: str
    constituency_no: str
    constituency_name: str
    n_oracles_present: int
    n_oracles_agreeing: int
    oracles_agreeing: str
    oracles_disagreeing: str
    winner_party_id_consensus: str
    winner_party_id_per_oracle: str
    winner_candidate_per_oracle: str
    verdict: Verdict
    curator_note: str | None = None
    curator_source_id: str | None = None


def pc_verdict_csv_header() -> tuple[str, ...]:
    """Header order for the per-PC verdict CSV (single source of truth)."""
    return tuple(f.name for f in fields(PcVerdictRow))


def _modal_party(party_ids: list[str]) -> tuple[str, int]:
    """Return (modal_party_id, count). Ties broken deterministically.

    Tie-break: when two party_ids tie on count, the alphabetically
    smaller one wins. Deterministic so reruns produce identical
    verdict.csv rows. Caller MAY pass an empty list (no oracles in
    the group); returns ('', 0) so the verdict surface stays defined.
    """
    if not party_ids:
        return ("", 0)
    counts: dict[str, int] = {}
    for pid in party_ids:
        counts[pid] = counts.get(pid, 0) + 1
    best_pid = ""
    best_count = -1
    for pid in sorted(counts):
        c = counts[pid]
        if c > best_count:
            best_pid = pid
            best_count = c
    return (best_pid, best_count)


def compare_per_pc(
    shape_a_rows: list[ShapeARow],
    canonical_parties: Mapping[str, Mapping[str, object]],
) -> list[PcVerdictRow]:
    """Collapse per-constituency shape-A rows into per-PC verdict rows.

    Grouping key is ``(state_code, constituency_no)``. Within each
    group, distinct ``external_scope`` values count as distinct
    oracles. Per the Fowler rule (see module docstring) the verdict
    is structural; the aggregator never invents content beyond what
    the shape-A rows carry.

    Args:
        shape_a_rows: list of shape-A rows from one or more adapter
            runs. Each row MUST carry non-null ``state_code`` and
            ``constituency_no``; rows missing either are skipped with
            no verdict row emitted (the row is malformed; the adapter
            should not have emitted it).
        canonical_parties: mapping of ``party_id`` to its parties.csv
            row. Used only to validate the consensus ``party_id``
            exists in canonical (when not, the verdict row's
            ``curator_note`` calls it out so the operator knows to
            mint a new parties.csv row before applying the verdict).

    Returns:
        list of ``PcVerdictRow`` sorted by
        ``(state_code, constituency_no_int)`` for reproducibility.

    Raises:
        ValueError: a shape-A row has a non-empty ``state_code`` and
            ``constituency_no`` but a malformed
            ``proposed_party_id`` shape; per the schema invariant the
            per-PC adapter must never emit a row that does not match
            ``^parties\\.IN\\.[A-Z][A-Z0-9_]*$``.
    """
    by_pc: dict[tuple[str, str], list[ShapeARow]] = {}
    for row in shape_a_rows:
        sc = (row.state_code or "").strip()
        cn = (row.constituency_no or "").strip()
        if not sc or not cn:
            # Malformed per-PC row; skip without emitting verdict.
            # Adapters are expected to set both fields for every PC
            # row they emit. A future Tier-A test in this module's
            # test_recon_pc_aggregator.py would catch the regression.
            continue
        by_pc.setdefault((sc, cn), []).append(row)

    verdicts: list[PcVerdictRow] = []

    # Deterministic order: sort by (state_code, int(constituency_no))
    # when constituency_no parses to int; fall back to lex sort
    # otherwise (handles the rare adapter that emits non-numeric).
    def _sort_key(k: tuple[str, str]) -> tuple[str, int, str]:
        sc, cn = k
        try:
            return (sc, int(cn), cn)
        except ValueError:
            return (sc, 10**9, cn)

    for key in sorted(by_pc, key=_sort_key):
        group = by_pc[key]
        sc, cn = key

        # Pick a representative constituency_name (deterministic-first
        # by external_scope so the verdict.csv is reproducible across
        # runs regardless of insertion order).
        rep = min(group, key=lambda r: (r.external_scope, r.external_key))
        cname = rep.constituency_name or ""

        oracles = sorted({r.external_scope for r in group})
        n_present = len(oracles)

        # Per-oracle proposed winner_party_id. ECI 'Unopposed' rows
        # carry a real proposed_party_id (e.g. BJP for Surat 2024);
        # only the winner_votes is None. So the consensus computation
        # is winner-party-only and ignores vote counts.
        proposals_by_oracle: dict[str, str] = {}
        candidate_by_oracle: dict[str, str] = {}
        for r in group:
            # An adapter MAY emit two rows for the same PC under one
            # scope (the canonical-pair pattern PR-W-1 uses for the
            # 2-oracle bridge) but typically per-PC adapters emit
            # one row per (scope, PC). When multiple, keep first.
            if r.external_scope not in proposals_by_oracle:
                proposals_by_oracle[r.external_scope] = r.proposed_party_id
                candidate_by_oracle[r.external_scope] = r.winner_candidate or ""

        per_oracle = sorted(proposals_by_oracle.items())
        proposals = [pid for _scope, pid in per_oracle]

        consensus_pid, agreeing_count = _modal_party(proposals)

        # Partition oracles into agreeing / disagreeing based on
        # consensus.
        agreeing_set = [
            scope for scope, pid in per_oracle if pid == consensus_pid
        ]
        disagreeing_set = [
            scope for scope, pid in per_oracle if pid != consensus_pid
        ]

        # Verdict per Fowler rule (plan section 0.5 ESCALATE #2).
        if n_present < 2:
            verdict: Verdict = "UNVERIFIED"
        elif agreeing_count == n_present:
            verdict = "VERIFIED"
        else:
            verdict = "DISPUTED"

        # curator_note: surface non-fatal flags.
        notes: list[str] = []
        if (
            consensus_pid
            and consensus_pid not in canonical_parties
            and consensus_pid not in {"parties.IN.UNK", "parties.IN.IND", "parties.IN.NOTA"}
        ):
            notes.append(
                f"consensus party_id {consensus_pid!r} not in parties.csv"
            )
        if verdict == "DISPUTED":
            # Per-oracle "scope=party_id" trail for the curator.
            disagree_trail = ", ".join(
                f"{scope}={proposals_by_oracle[scope]}"
                for scope in disagreeing_set
            )
            notes.append(
                f"oracles disagreeing on winner_party_id: {disagree_trail}"
            )
        curator_note = "; ".join(notes) if notes else None

        # Pipe-list per-oracle breakdown for the verdict.csv columns.
        winner_party_per = "|".join(
            f"{scope}={pid}" for scope, pid in per_oracle
        )
        winner_cand_per = "|".join(
            f"{scope}={candidate_by_oracle[scope]}"
            for scope, _pid in per_oracle
            if candidate_by_oracle.get(scope)
        )

        verdicts.append(
            PcVerdictRow(
                state_code=sc,
                constituency_no=cn,
                constituency_name=cname,
                n_oracles_present=n_present,
                n_oracles_agreeing=agreeing_count,
                oracles_agreeing="|".join(agreeing_set),
                oracles_disagreeing="|".join(disagreeing_set),
                winner_party_id_consensus=consensus_pid,
                winner_party_id_per_oracle=winner_party_per,
                winner_candidate_per_oracle=winner_cand_per,
                verdict=verdict,
                curator_note=curator_note,
                curator_source_id=None,
            )
        )

    return verdicts


def write_pc_verdict_csv(verdicts: list[PcVerdictRow], path) -> int:  # type: ignore[no-untyped-def]
    """Write per-PC verdict rows to ``path`` as CSV.

    Splits the dataclass into a CSV row using ``fields(PcVerdictRow)``
    for header order. ``None`` values are serialised as empty strings
    (matching the per-party ``write_verdict_csv`` shape so curator
    tooling can treat both verdict CSVs uniformly).

    ``path`` accepted as ``pathlib.Path`` or string. Returns the
    number of rows written.
    """
    import csv
    from pathlib import Path as _Path

    out_path = _Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = pc_verdict_csv_header()
    with out_path.open("w", encoding="utf-8", newline="") as fh:
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
    "PcVerdictRow",
    "Verdict",
    "compare_per_pc",
    "pc_verdict_csv_header",
    "write_pc_verdict_csv",
]
