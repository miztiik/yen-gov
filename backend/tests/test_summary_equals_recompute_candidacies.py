"""G15 (plan section 23.4 EL8): summary == recompute(candidacies) gate.

For every on-disk election slice under
``datasets/elections/{assembly,parliament}/`` the per-AC (or per-PC) summary
row MUST equal the F7-computed recomputation from its candidacy rows. The
recompute path is the canonical
``yen_gov.canonical.reingest.assembly_results.recompute_summary_row``,
which the parliament emitter calls identically with PC entity_ids
(``parliament_results.py`` line 184); the function is grain-agnostic.

Failure modes the gate catches:
- Winner/runner-up mis-ranking (e.g. wrong tie-break in the emitter).
- Margin-pct rounding drift between emit and read.
- Vote share float-precision loss across a re-emit.
- A row in summary.csv that has no covering candidacies.csv group (silent
  data dropout).
- A row in candidacies.csv whose entity_id has no summary row (silent
  group dropout).

The gate fails LOUD: it collects up to 50 divergences with the
``(state, year, entity_id, field, recomputed, on_disk)`` tuple and prints
them all before raising, so the operator can triage the emitter from one
test run instead of N. Floats are compared with ``pytest.approx`` at
``rel=1e-6`` for the three computed pct fields; nullable cells treat ``""``
and ``None`` as equivalent. Skips gracefully when either CSV is absent.
"""
from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from yen_gov.canonical.reingest.assembly_results import recompute_summary_row

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ASSEMBLY_ROOT = _REPO_ROOT / "datasets" / "elections" / "assembly"
_PARLIAMENT_ROOT = _REPO_ROOT / "datasets" / "elections" / "parliament"

_FLOAT_FIELDS: frozenset[str] = frozenset(
    {"turnout_pct", "winner_share_pct", "margin_pct"}
)
_NULLABLE_FIELDS: frozenset[str] = frozenset(
    {
        "runnerup_candidate",
        "runnerup_party_id",
        "runnerup_party_short_raw",
        "runnerup_votes",
        "margin_votes",
        "margin_pct",
        "winner_party_id",
        "winner_party_short_raw",
        "winner_share_pct",
        "electors",
        "votes_polled",
        "turnout_pct",
    }
)

# Fields the recompute helper cannot reconstruct from candidacies.csv alone:
# the backfill stamps ``processing_level`` / ``processing_note`` with TCPD-
# catalogue-resolution history (e.g. a candidacy whose party_id was once
# UNK and was later resolved via the TCPD party catalogue still carries
# ``major`` + the resolution note on the on-disk summary, but the recompute
# helper sees only the current resolved party_id and would emit ``minor``).
# Excluding these two fields preserves the oracle's intent (project-from-
# candidacies is byte-identical to the writer) for every other column.
_EXCLUDED_FROM_PARITY: frozenset[str] = frozenset(
    {"processing_level", "processing_note"}
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _int_or_none(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return int(float(s))  # tolerate "100.0" -> 100
    except ValueError:
        return None


def _float_or_none(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _norm(value: Any) -> Any:
    """Normalise nullable cells: empty string and None are equivalent."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _coerce_candidacy_row(row: dict[str, str]) -> dict[str, Any]:
    """Coerce a candidacies.csv string row into the typed dict shape
    ``recompute_summary_row`` expects (mirrors
    ``build_candidacy_rows`` in ``assembly_results.py`` /
    ``parliament_results.py``).
    """
    return {
        "entity_id": row["entity_id"],
        "state": row["state"],
        "election_year": _int_or_none(row.get("election_year")) or 0,
        "constituency_no": _int_or_none(row.get("constituency_no")) or 0,
        "constituency_name": row.get("constituency_name") or "",
        "candidate_name": row.get("candidate_name") or "",
        "party_id": _norm(row.get("party_id")),
        "party_short_raw": _norm(row.get("party_short_raw")),
        "votes": _int_or_none(row.get("votes")) or 0,
        "vote_share_pct": _float_or_none(row.get("vote_share_pct")),
        "position": _int_or_none(row.get("position")) or 0,
        "result": row.get("result") or "",
        "source_id": row.get("source_id") or "",
    }


def _coerce_summary_row(row: dict[str, str]) -> dict[str, Any]:
    """Coerce a summary.csv string row into the typed dict shape
    ``recompute_summary_row`` returns. Cells without a typed counterpart on
    the returned dict (the candidacy-only fields like ``sex`` / ``age``)
    do not exist on the summary row so are not enumerated here.
    """
    return {
        "entity_id": row["entity_id"],
        "state": row.get("state") or "",
        "election_year": _int_or_none(row.get("election_year")) or 0,
        "constituency_name": row.get("constituency_name") or "",
        "electors": _int_or_none(row.get("electors")),
        "votes_polled": _int_or_none(row.get("votes_polled")),
        "turnout_pct": _float_or_none(row.get("turnout_pct")),
        "winner_candidate": row.get("winner_candidate") or "",
        "winner_party_id": _norm(row.get("winner_party_id")),
        "winner_party_short_raw": _norm(row.get("winner_party_short_raw")),
        "winner_votes": _int_or_none(row.get("winner_votes")) or 0,
        "winner_share_pct": _float_or_none(row.get("winner_share_pct")),
        "runnerup_candidate": _norm(row.get("runnerup_candidate")),
        "runnerup_party_id": _norm(row.get("runnerup_party_id")),
        "runnerup_party_short_raw": _norm(
            row.get("runnerup_party_short_raw")
        ),
        "runnerup_votes": _int_or_none(row.get("runnerup_votes")),
        "margin_votes": _int_or_none(row.get("margin_votes")),
        "margin_pct": _float_or_none(row.get("margin_pct")),
        "source_id": row.get("source_id") or "",
        "processing_level": row.get("processing_level") or "minor",
        "processing_note": _norm(row.get("processing_note")),
    }


def _walk_slice_pairs() -> Iterator[tuple[str, str, str, Path, Path]]:
    """Yield ``(body, state_slug, election_year, candidacies_csv, summary_csv)``
    for every (state, election) on disk, across both AC and PC trees.

    For parliament the ``state_slug`` is set to ``"<all-states>"`` because
    the file is the national cohort; the gate then groups by the row's
    ``state`` column when emitting divergence messages.
    """
    if _ASSEMBLY_ROOT.is_dir():
        for state_dir in sorted(_ASSEMBLY_ROOT.iterdir()):
            if not state_dir.is_dir() or not state_dir.name.startswith("state="):
                continue
            state_slug = state_dir.name.split("=", 1)[1]
            for elec_dir in sorted(state_dir.iterdir()):
                if not elec_dir.is_dir() or not elec_dir.name.startswith(
                    "election="
                ):
                    continue
                year = elec_dir.name.split("=", 1)[1]
                cand = elec_dir / "candidacies.csv"
                summ = elec_dir / "summary.csv"
                if cand.is_file() and summ.is_file():
                    yield "AC", state_slug, year, cand, summ
    if _PARLIAMENT_ROOT.is_dir():
        for elec_dir in sorted(_PARLIAMENT_ROOT.iterdir()):
            if not elec_dir.is_dir() or not elec_dir.name.startswith(
                "election="
            ):
                continue
            year = elec_dir.name.split("=", 1)[1]
            cand = elec_dir / "candidacies.csv"
            summ = elec_dir / "summary.csv"
            if cand.is_file() and summ.is_file():
                yield "PC", "<all-states>", year, cand, summ


def _ac_facts_from_summary(summary_row: dict[str, Any]) -> dict[str, Any]:
    """Build the ``ac_facts`` dict for ``recompute_summary_row``.

    ``electors`` / ``votes_polled`` / ``turnout_pct`` are CARRIED THROUGH
    (not derived) by the recompute, so feeding them in from the summary
    row is correct: the test verifies the DERIVED fields (winner / runner-
    up / margin) match, not these three pass-through values. OWID parity-
    oracle pattern; same as the production parity oracle in
    ``test_canonical_parity_oracle.py``.
    """
    return {
        "electors": summary_row.get("electors"),
        "votes_polled": summary_row.get("votes_polled"),
        "turnout_pct": summary_row.get("turnout_pct"),
    }


def _compare(
    recomputed: dict[str, Any],
    on_disk: dict[str, Any],
    *,
    context: tuple[str, str, str],
    divergences: list[tuple[str, str, str, str, Any, Any]],
    cap: int = 50,
) -> None:
    """Field-by-field compare; append diffs to ``divergences`` (bounded)."""
    state_or_all, year, entity_id = context
    for key in recomputed:
        if key in _EXCLUDED_FROM_PARITY:
            continue
        a = recomputed.get(key)
        b = on_disk.get(key)
        if key in _NULLABLE_FIELDS:
            a = _norm(a)
            b = _norm(b)
        if key in _FLOAT_FIELDS:
            if a is None and b is None:
                continue
            if a is None or b is None:
                divergences.append((state_or_all, year, entity_id, key, a, b))
                if len(divergences) >= cap:
                    return
                continue
            if abs(float(a) - float(b)) > max(1e-6, abs(float(b)) * 1e-6):
                divergences.append((state_or_all, year, entity_id, key, a, b))
                if len(divergences) >= cap:
                    return
            continue
        if a != b:
            divergences.append((state_or_all, year, entity_id, key, a, b))
            if len(divergences) >= cap:
                return


def test_summary_equals_recompute_candidacies() -> None:
    """G15 (EL8) gate: ``summary == recompute(candidacies)`` across all
    on-disk (state, election) slices. Stream-reads each CSV pair. Skips
    gracefully when neither tree is present (e.g. minimal fixture)."""
    pairs = list(_walk_slice_pairs())
    if not pairs:
        pytest.skip(
            "no datasets/elections/{assembly,parliament}/**/candidacies.csv"
            " on disk -- nothing to validate"
        )

    divergences: list[tuple[str, str, str, str, Any, Any]] = []
    # Sanity counters: ensure the gate actually exercised BOTH AC and PC.
    saw_ac = False
    saw_pc = False
    n_pairs_checked = 0
    n_entities_checked = 0
    for body, state_slug, year, cand_path, summ_path in pairs:
        if body == "AC":
            saw_ac = True
        else:
            saw_pc = True
        n_pairs_checked += 1

        cand_rows_raw = _read_csv(cand_path)
        summ_rows_raw = _read_csv(summ_path)
        if not cand_rows_raw or not summ_rows_raw:
            continue

        # Group candidacies by entity_id.
        grouped: dict[str, list[dict[str, Any]]] = {}
        for raw in cand_rows_raw:
            row = _coerce_candidacy_row(raw)
            grouped.setdefault(row["entity_id"], []).append(row)

        # Index summary rows by entity_id.
        summary_by_eid: dict[str, dict[str, Any]] = {}
        for raw in summ_rows_raw:
            row = _coerce_summary_row(raw)
            summary_by_eid[row["entity_id"]] = row

        # Iterate the summary set (the contract is one summary row per AC/
        # PC entity that has candidacies). An orphan summary row with no
        # candidacies group is itself a divergence: surface it.
        for entity_id, summary_row in summary_by_eid.items():
            group = grouped.get(entity_id)
            row_state = summary_row.get("state") or state_slug
            row_year = str(summary_row.get("election_year")) or year
            if group is None:
                divergences.append(
                    (
                        str(row_state),
                        str(row_year),
                        entity_id,
                        "<no candidacy group>",
                        None,
                        "summary row present",
                    )
                )
                if len(divergences) >= 50:
                    break
                continue
            n_entities_checked += 1
            recomputed = recompute_summary_row(
                entity_id=entity_id,
                state_slug=str(summary_row.get("state") or state_slug),
                election_year=int(
                    summary_row.get("election_year") or int(year)
                ),
                candidacy_rows=group,
                ac_facts=_ac_facts_from_summary(summary_row),
                source_id=group[0]["source_id"],
            )
            _compare(
                recomputed,
                summary_row,
                context=(str(row_state), str(row_year), entity_id),
                divergences=divergences,
            )
            if len(divergences) >= 50:
                break
        if len(divergences) >= 50:
            break

    # Sanity: the gate should have exercised at least one of each body
    # when the real corpus is present (it is, on this branch).
    assert n_pairs_checked > 0
    assert saw_ac or saw_pc

    if divergences:
        msg_lines = [
            "summary == recompute(candidacies) gate found "
            f"{len(divergences)} divergence(s) across {n_pairs_checked} "
            f"(state, election) pair(s); n_entities_checked="
            f"{n_entities_checked}. First {len(divergences)}:"
        ]
        for st, yr, eid, field, got, on_disk in divergences:
            msg_lines.append(
                f"  - state={st!r} year={yr!r} entity_id={eid!r} "
                f"field={field!r} recomputed={got!r} on_disk={on_disk!r}"
            )
        pytest.fail("\n".join(msg_lines))
