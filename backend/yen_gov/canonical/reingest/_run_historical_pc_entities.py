"""PR-Q7c historical-PC entity minter: mint ``electoral.csv`` rows for the
DelimID 1 / 2 / 3 cohorts (1962 / 1967 / 1976 delimitation cycles) from the
local TCPD ``All_States_GE.csv`` compilation.

PR-Q7c (#TODO) makes the parliament binder delim-aware (lookup filters by
``delim_year`` so the historical and in-force cycles do not collide on
reused ``Constituency_No`` values). This minter ships the historical PC
entity cohorts so the parliament driver
(``_run_parliament_results --delim 3``) can emit candidacies for the 65
parliament events still flagged ``data_status: pending_upstream`` in
``datasets/taxonomy/election_events.json`` (31 general-1999 + 34
general-2004 state slices).

Run from the worktree root (PYTHONPATH set to ``./backend``):

    # dry-run: print the per-(delim, state) entity counts and naming-mode
    # ties; no edit to electoral.csv. Always run this first.
    python -m yen_gov.canonical.reingest._run_historical_pc_entities

    # apply: append the new entity rows to electoral.csv and emit the
    # per-state receipt at datasets/_ops/historical-pc-entities-<DATE>.md.
    python -m yen_gov.canonical.reingest._run_historical_pc_entities --apply

The mint shape (mirror of PR-Q7b's AC minter):

- One ``electoral.csv`` row per ``(State_Name, DelimID, Constituency_No)``
  group, deduped within the run.
- ``entity_id = "IN-PC-<delim_year>-<state_slug>-<eci_no>"`` -- the
  ``delim_year`` prefix (1962/1967/1976) keeps the historical ids distinct
  from the in-force ``IN-PC-2008-*`` cohort even where the trailing
  serial overlaps numerically.
- ``name`` = the most-recent ``Constituency_Name`` for the group (latest
  ``Year``); ties broken by mode, then by alphabetical order. Any tie is
  recorded in the receipt.
- ``aliases`` = pipe-joined deduped set of every historical
  ``Constituency_Name`` variant TCPD carries for the group, EXCLUDING the
  chosen ``name`` (so the binder can find the constituency under multiple
  historical spellings without redundancy with ``name``).
- ``reservation`` = the most-recent valid TCPD ``Constituency_Type``
  (one of ``{GEN, SC, ST}``); ``BL`` and empty rows are skipped. Empty
  string when no valid type is observed.
- ``parent`` = empty (no historical state linkage yet -- the parliament
  binder consults ``state`` directly).
- Defunct TCPD ``State_Name`` values ``{Madras, Mysore,
  Goa_Daman_&_Diu}`` are SKIPPED (same skip rule as the PR-Q7b AC
  minter; these names have no current LGD state slug).
- Idempotency: rows whose derived ``entity_id`` is already present on
  ``electoral.csv`` are SKIPPED. Re-runs are no-ops.

The ``state_slug`` derivation uses the same TCPD slugify shape as
``parliament_results.py::_slugify`` (lowercase + ``_&_`` -> ``-and-`` +
``_`` -> ``-``) so the resulting entity_ids match the slugs the
parliament binder produces for its `state` column. This matches the
existing 2008 PC entity cohort's slug shape (e.g.
``IN-PC-2008-andaman-and-nicobar-islands-eci1``,
``IN-PC-2008-dadra-and-nagar-haveli-and-daman-and-diu-360``); the small
divergence from the canonical geo.csv state slug for U01 +
pre-2020-merged U03 is intentional and matches the parliament binder's
internal contract.

No network, no parquet. Pure CSV append. Validate gate runs separately
via ``python -m yen_gov validate --root .``; FK closure of the new rows
into ``geo.csv`` is exercised by the schema validator.
"""

from __future__ import annotations

import argparse
import csv
import io
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final

from yen_gov.canonical.reingest.assembly_results import TCPD_DELIM_ID_TO_DELIM_YEAR

# Defunct TCPD state names with no current LGD slug. The GE compilation
# spells the pre-1987 Goa-Daman-Diu UT differently from the AE compilation:
# AE has ``Goa_Daman_&_Diu`` (no comma), GE has ``Goa,_Daman_&_Diu``
# (comma after Goa). Both shapes designate the same defunct state and
# both are skipped; the comma form is what actually appears in the GE
# 1967-1984 (DelimID 2 + 3) cohort. ``Madras`` (renamed to TN in 1969)
# and ``Mysore`` (renamed to KA in 1973) carry no current LGD slug
# either. Same skip rule as the PR-Q7b AC minter.
SKIP_STATES: Final[frozenset[str]] = frozenset({
    "Madras",
    "Mysore",
    "Goa_Daman_&_Diu",
    "Goa,_Daman_&_Diu",
})

# DelimID values this minter is responsible for. DelimID 4 (the in-force
# 2008 cycle) is excluded -- those entities are shipped by the earlier
# B2b.5.0 round-7 PRI super-file fold.
HISTORICAL_DELIM_IDS: Final[tuple[str, ...]] = ("1", "2", "3")

# Valid TCPD Constituency_Type values that map to ``electoral.csv``'s
# ``reservation`` enum. ``BL`` (bloc / large multi-member, pre-1962) and
# empty cells degrade to no reservation declared.
RESERVATION_VALUES: Final[frozenset[str]] = frozenset({"GEN", "SC", "ST"})

RECEIPT_PATH: Final[str] = "datasets/_ops/historical-pc-entities-2026-06-12.md"

ELECTORAL_HEADER: Final[tuple[str, ...]] = (
    "entity_id",
    "name",
    "entity_kind",
    "delim_year",
    "state",
    "parent",
    "eci_no",
    "aliases",
    "reservation",
)


def _slugify(tcpd_name: str) -> str:
    """Match ``parliament_results.py::_slugify`` exactly.

    Lowercases the TCPD State_Name, swaps ``_&_`` for ``-and-`` and
    underscores for hyphens. Re-implemented here (rather than imported
    from parliament_results) so this minter has no import dependency on
    the binder module's transitive shape.
    """
    return tcpd_name.lower().replace("_&_", "-and-").replace("_", "-")


def _read_existing_entity_ids(electoral_csv: Path) -> set[str]:
    """Return the set of ``entity_id`` already on disk (PK seen for idempotency)."""
    if not electoral_csv.exists():
        return set()
    with electoral_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return {(row.get("entity_id") or "").strip() for row in reader}


def _ge_iter(ge_csv: Path) -> Iterable[dict[str, str]]:
    """Stream TCPD GE rows; tolerant of the publisher's wide column set."""
    with ge_csv.open(encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def _group_key(row: dict[str, str]) -> tuple[str, str, int] | None:
    """Return ``(State_Name, DelimID, Constituency_No)`` or ``None`` to drop the row."""
    state = (row.get("State_Name") or "").strip()
    delim_id = (row.get("DelimID") or "").strip()
    cons_no_raw = (row.get("Constituency_No") or "").strip()
    if not state or state in SKIP_STATES:
        return None
    if delim_id not in HISTORICAL_DELIM_IDS:
        return None
    if not cons_no_raw.isdigit():
        return None
    return state, delim_id, int(cons_no_raw)


def _year_of(row: dict[str, str]) -> int | None:
    raw = (row.get("Year") or "").strip()
    return int(raw) if raw.isdigit() else None


def _select_name(year_to_names: Mapping[int, list[str]]) -> tuple[str, bool]:
    """Pick the canonical name across years; report whether the pick had a tie.

    Decision shape (mirror of PR-Q7b AC minter):
      1. Take the highest-Year cohort with at least one non-empty name.
      2. Inside that cohort, the most-common name (mode) wins.
      3. On a mode tie, alphabetical sort wins (deterministic).
      4. The ``had_tie`` flag is True iff the mode tied at the top.

    Returns ``("", False)`` when every cohort contributes only empty
    names; the caller is responsible for the fallback name shape.
    """
    for year in sorted(year_to_names, reverse=True):
        names = [n for n in year_to_names[year] if n]
        if not names:
            continue
        counts = Counter(names)
        max_count = max(counts.values())
        winners = sorted(n for n, c in counts.items() if c == max_count)
        return winners[0], len(winners) > 1
    return "", False


def _select_reservation(year_to_types: Mapping[int, list[str]]) -> str:
    """Pick the most-recent valid reservation; empty when none observed."""
    for year in sorted(year_to_types, reverse=True):
        valid = [t for t in year_to_types[year] if t in RESERVATION_VALUES]
        if valid:
            counts = Counter(valid)
            max_count = max(counts.values())
            winners = sorted(t for t, c in counts.items() if c == max_count)
            return winners[0]
    return ""


def _aliases_for(name: str, all_names: Iterable[str]) -> str:
    """Pipe-join deduped historical name variants, excluding the chosen ``name``.

    Case-insensitive dedup but preserves original casing. Sort alphabetical
    so re-runs over the same TCPD vintage produce a byte-stable column.
    """
    seen: dict[str, str] = {}
    chosen_key = name.casefold()
    for n in all_names:
        if not n:
            continue
        key = n.casefold()
        if key == chosen_key:
            continue
        if key not in seen:
            seen[key] = n
    if not seen:
        return ""
    return "|".join(sorted(seen.values(), key=lambda s: s.casefold()))


def build_entity_rows(ge_csv: Path) -> tuple[
    list[dict[str, str]],
    dict[tuple[str, str], int],
    list[tuple[str, str, int, str]],
]:
    """Pure builder: read TCPD GE.csv, return ``(rows, counts, ties)``.

    Args:
        ge_csv: path to ``datasets/ephemeral/All_States_GE.csv``.

    Returns:
        - ``rows``: candidate ``electoral.csv`` rows (PRE-idempotency-skip),
          sorted deterministically by ``(delim_year, state, eci_no)``.
        - ``counts``: per-``(state_slug, delim_id)`` entity count.
        - ``ties``: list of naming-mode ties recorded as
          ``(state_slug, delim_id, eci_no, chosen_name)``.
    """
    name_buckets: dict[tuple[str, str, int], dict[int, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    type_buckets: dict[tuple[str, str, int], dict[int, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in _ge_iter(ge_csv):
        key = _group_key(row)
        if key is None:
            continue
        year = _year_of(row)
        if year is None:
            continue
        name = (row.get("Constituency_Name") or "").strip()
        cons_type = (row.get("Constituency_Type") or "").strip().upper()
        name_buckets[key][year].append(name)
        type_buckets[key][year].append(cons_type)

    out: list[dict[str, str]] = []
    counts: dict[tuple[str, str], int] = Counter()
    ties: list[tuple[str, str, int, str]] = []

    for (state_tcpd, delim_id, eci_no), year_names in name_buckets.items():
        slug = _slugify(state_tcpd)
        delim_year = TCPD_DELIM_ID_TO_DELIM_YEAR[delim_id]
        entity_id = f"IN-PC-{delim_year}-{slug}-{eci_no}"

        chosen_name, had_tie = _select_name(year_names)
        if not chosen_name:
            chosen_name = f"Unnamed constituency {eci_no}"
        if had_tie:
            ties.append((slug, delim_id, eci_no, chosen_name))

        all_names = [n for names in year_names.values() for n in names]
        aliases = _aliases_for(chosen_name, all_names)
        reservation = _select_reservation(type_buckets[(state_tcpd, delim_id, eci_no)])

        out.append({
            "entity_id": entity_id,
            "name": chosen_name,
            "entity_kind": "pc",
            "delim_year": str(delim_year),
            "state": slug,
            "parent": "",
            "eci_no": str(eci_no),
            "aliases": aliases,
            "reservation": reservation,
        })
        counts[(slug, delim_id)] += 1

    out.sort(key=lambda r: (int(r["delim_year"]), r["state"], int(r["eci_no"])))
    return out, dict(counts), ties


def _format_csv_row(row: dict[str, str]) -> str:
    """Render one row in csv.DictWriter's default dialect (POSIX line endings)."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=ELECTORAL_HEADER, lineterminator="\n")
    writer.writerow({k: row.get(k, "") for k in ELECTORAL_HEADER})
    return buf.getvalue()


def append_new_rows(
    electoral_csv: Path,
    candidate_rows: list[dict[str, str]],
) -> tuple[int, int]:
    """Append rows whose ``entity_id`` is not already on disk.

    The existing file content stays byte-stable (no rewrite). The new
    block is sorted by ``(delim_year, state, eci_no)`` per ``build_entity_rows``.

    Returns ``(n_new, n_skipped_existing)``.
    """
    existing = _read_existing_entity_ids(electoral_csv)
    new_rows = [r for r in candidate_rows if r["entity_id"] not in existing]
    skipped = len(candidate_rows) - len(new_rows)
    if not new_rows:
        return 0, skipped
    block = "".join(_format_csv_row(r) for r in new_rows)
    # Defensive: ensure the existing file ends with a newline before append.
    current = electoral_csv.read_text(encoding="utf-8")
    if current and not current.endswith("\n"):
        current = current + "\n"
        electoral_csv.write_text(current, encoding="utf-8", newline="")
    with electoral_csv.open("a", encoding="utf-8", newline="") as fh:
        fh.write(block)
    return len(new_rows), skipped


def render_receipt(
    *,
    counts: dict[tuple[str, str], int],
    ties: list[tuple[str, str, int, str]],
    total_candidate: int,
    total_new: int,
    total_skipped: int,
    apply_mode: bool,
) -> str:
    """Render the per-(state, delim) mint receipt as Markdown."""
    lines: list[str] = [
        "# Historical PC entities mint (PR-Q7c, 2026-06-12)",
        "",
        (
            "DelimID 1 / 2 / 3 cohorts (1962 / 1967 / 1976 cycles) minted from"
            " TCPD's All_States_GE.csv compilation. PR-Q7c made the parliament"
            " binder delim-aware; this receipt records the entity cohort the"
            " parliament emit binds against. Mirror of PR-Q7b's AC minter"
            " (historical-ac-entities-2026-06-12.md) for the PC axis."
        ),
        "",
        f"Mode: {'APPLY' if apply_mode else 'DRY-RUN'}.",
        f"Total candidate rows: {total_candidate}.",
        f"Newly appended to electoral.csv: {total_new}.",
        f"Skipped (entity_id already present): {total_skipped}.",
        "",
        "## Per-(state, delim) entity counts",
        "",
        "| state | delim_id | delim_year | entities |",
        "| --- | --- | --- | --- |",
    ]
    for (slug, delim_id), n in sorted(counts.items()):
        delim_year = TCPD_DELIM_ID_TO_DELIM_YEAR[delim_id]
        lines.append(f"| {slug} | {delim_id} | {delim_year} | {n} |")
    lines.append(f"| **total** | | | {sum(counts.values())} |")
    lines.append("")
    if ties:
        lines.append("## Naming-mode ties (mode tied; deterministic alphabetical pick)")
        lines.append("")
        lines.append("| state | delim_id | eci_no | chosen_name |")
        lines.append("| --- | --- | --- | --- |")
        for slug, delim_id, eci_no, chosen in sorted(ties):
            lines.append(f"| {slug} | {delim_id} | {eci_no} | {chosen} |")
        lines.append("")
    else:
        lines.append("## Naming-mode ties")
        lines.append("")
        lines.append("None observed.")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m yen_gov.canonical.reingest._run_historical_pc_entities",
        description=__doc__,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Append new entity rows to electoral.csv and emit the receipt.",
    )
    parser.add_argument(
        "--ge-csv",
        type=Path,
        default=None,
        help=(
            "Override the path to All_States_GE.csv (defaults to"
            " datasets/ephemeral/All_States_GE.csv under the worktree root,"
            " falling back to the absolute master-worktree path if missing"
            " in a sub-worktree since the file is gitignored)."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    entities = repo_root / "datasets" / "data" / "entities"
    electoral_csv = entities / "electoral.csv"

    if args.ge_csv is not None:
        ge_csv = args.ge_csv
    else:
        local = repo_root / "datasets" / "ephemeral" / "All_States_GE.csv"
        if local.exists():
            ge_csv = local
        else:
            # Fallback: master worktree's copy (gitignored, only on dev box).
            master = Path(
                r"C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov"
                r"\datasets\ephemeral\All_States_GE.csv"
            )
            if not master.exists():
                raise SystemExit(
                    "All_States_GE.csv not found in worktree or master fallback;"
                    " pass --ge-csv <path> explicitly."
                )
            ge_csv = master

    print(f"reading: {ge_csv}")
    candidate_rows, counts, ties = build_entity_rows(ge_csv)
    total_candidate = len(candidate_rows)
    print(f"candidate rows: {total_candidate}")

    if args.apply:
        n_new, n_skipped = append_new_rows(electoral_csv, candidate_rows)
        print(f"appended {n_new} new rows (skipped {n_skipped} already-present)")
    else:
        existing = _read_existing_entity_ids(electoral_csv)
        n_new = sum(1 for r in candidate_rows if r["entity_id"] not in existing)
        n_skipped = total_candidate - n_new
        print(f"DRY-RUN: would append {n_new} new rows (would skip {n_skipped})")

    receipt = render_receipt(
        counts=counts,
        ties=ties,
        total_candidate=total_candidate,
        total_new=n_new,
        total_skipped=n_skipped,
        apply_mode=args.apply,
    )
    if args.apply:
        out_path = repo_root / RECEIPT_PATH
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(receipt + "\n", encoding="utf-8")
        print(f"receipt: {RECEIPT_PATH}")
    else:
        print()
        print(receipt)


if __name__ == "__main__":
    main()
