"""Rebrand the two TCPD-flavoured election-corpus rows in
``datasets/data/entities/source.csv`` to the canonical publisher
``Election Commission of India`` and cascade the source_id FK rewrites
across every CSV under ``datasets/data/`` and ``datasets/elections/``.

Identity is derived per ``backend/yen_gov/canonical/citation.py``:
``source_id = "src-" + sha256(f"{producer}|{title}|{vintage}").hexdigest()[:12]``.

Producer/title changes:
  - Assembly  src-1b7bc1c9d39a  -> src-0c1b8f274551
    producer: Trivedi Centre... Ashoka University -> Election Commission of India
    title:    drop the "(TCPD compilation of ECI returns)" parenthetical
  - LS GE     src-31c65dbec869  -> src-d4b15132ad0e
    producer: Trivedi Centre... Ashoka University -> Election Commission of India
    title:    drop the "(TCPD compilation of ECI returns)" parenthetical

The third TCPD row (src-4040a970f10c, "Political Parties of India... TCPD
compilation") is TCPD's own derived work (party catalogue, not raw ECI
returns) and is LEFT UNTOUCHED.

vintage stays at 2026-06-05 (the operator-snapshot anchor when these LS-AE
data packs were last lifted from TCPD lok-dhaba). url stays at the TCPD
landing page because that is still the citizen-accessible surface.

Idempotent: re-running the script on an already-rebranded corpus produces
zero file rewrites and the same stdout receipt.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


OLD_TO_NEW: dict[str, str] = {
    "src-1b7bc1c9d39a": "src-0c1b8f274551",
    "src-31c65dbec869": "src-d4b15132ad0e",
}

NEW_PRODUCER = "Election Commission of India"
NEW_TITLES: dict[str, str] = {
    "src-0c1b8f274551": "Indian Assembly Elections - Constituency-wise candidate results",
    "src-d4b15132ad0e": "Indian General Elections (Lok Sabha) - Constituency-wise candidate results",
}


def _rewrite_source_csv(path: Path) -> int:
    """Rewrite the 5-col source ledger: replace OLD_TO_NEW rows with their
    rebranded counterparts (new id + new producer + new title). Preserve
    every other row byte-for-byte. Return the count of rows updated."""

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    updated = 0
    out_rows: list[dict[str, str]] = []
    for row in rows:
        old_id = (row.get("source_id") or "").strip()
        if old_id in OLD_TO_NEW:
            new_id = OLD_TO_NEW[old_id]
            new_row = dict(row)
            new_row["source_id"] = new_id
            new_row["producer"] = NEW_PRODUCER
            new_row["title"] = NEW_TITLES[new_id]
            # vintage + url preserved verbatim.
            out_rows.append(new_row)
            updated += 1
        else:
            out_rows.append(row)

    if updated == 0:
        return 0

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(out_rows)
    return updated


def _cascade_fk_rewrites(roots: list[Path]) -> tuple[int, int]:
    """Walk every CSV under ``roots``; for any file whose header contains
    ``source_id``, rewrite cells matching keys of OLD_TO_NEW. Return
    ``(cells_rewritten, files_rewritten)``."""

    cells_rewritten = 0
    files_rewritten = 0

    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.csv"):
            # Skip the source ledger itself; it was handled by
            # ``_rewrite_source_csv`` with the producer/title rebrand.
            if path.name == "source.csv" and path.parent.name == "entities":
                continue

            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                fieldnames = list(reader.fieldnames or [])
                if "source_id" not in fieldnames:
                    continue
                rows = list(reader)

            file_cells = 0
            out_rows: list[dict[str, str]] = []
            for row in rows:
                old_id = (row.get("source_id") or "").strip()
                if old_id in OLD_TO_NEW:
                    new_row = dict(row)
                    new_row["source_id"] = OLD_TO_NEW[old_id]
                    out_rows.append(new_row)
                    file_cells += 1
                else:
                    out_rows.append(row)

            if file_cells == 0:
                continue

            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=fieldnames,
                    lineterminator="\n",
                    quoting=csv.QUOTE_MINIMAL,
                )
                writer.writeheader()
                writer.writerows(out_rows)

            cells_rewritten += file_cells
            files_rewritten += 1

    return cells_rewritten, files_rewritten


def main() -> int:
    here = Path(__file__).resolve().parent
    repo_root = here.parent
    source_path = repo_root / "datasets" / "data" / "entities" / "source.csv"
    if not source_path.exists():
        print(f"error: source ledger not found at {source_path}", file=sys.stderr)
        return 1

    rows_updated = _rewrite_source_csv(source_path)

    cascade_roots = [
        repo_root / "datasets" / "data",
        repo_root / "datasets" / "elections",
    ]
    cells, files = _cascade_fk_rewrites(cascade_roots)

    print(
        f"{rows_updated} source rows updated, "
        f"{cells} FK cells rewritten across {files} CSV files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
