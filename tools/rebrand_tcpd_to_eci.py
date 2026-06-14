"""Rebrand TCPD-flavoured election-corpus rows in
``datasets/data/entities/source.csv`` to the canonical publisher
``Election Commission of India`` and cascade the source_id FK rewrites
across every CSV under ``datasets/data/`` and ``datasets/elections/``.

Identity is derived per ``backend/yen_gov/canonical/citation.py``:
``source_id = "src-" + sha256(f"{producer}|{title}|{vintage}").hexdigest()[:12]``.

Pass 1 (producer + title rebrand of the 2 umbrella rows):
  - Assembly  src-1b7bc1c9d39a  -> src-0c1b8f274551
    producer: Trivedi Centre... Ashoka University -> Election Commission of India
    title:    drop the "(TCPD compilation of ECI returns)" parenthetical
  - LS GE     src-31c65dbec869  -> src-d4b15132ad0e
    producer: Trivedi Centre... Ashoka University -> Election Commission of India
    title:    drop the "(TCPD compilation of ECI returns)" parenthetical

Pass 2 (title-suffix strip on the 5 per-year LS rows; producer already ECI):
    Each row's title was ``General Election to Lok Sabha <year> \u2014
    Constituency-wise candidate results (TCPD compilation of ECI returns)``.
    The em-dash separator and the parenthetical are dropped; new title is
    ``General Election to Lok Sabha <year>``. Also closes the lingering
    ASCII-only violation from the em-dash (CLAUDE.md section 5).
      - src-0099686311a2 -> src-9be18d311190  (2009)
      - src-b2b916daabf9 -> src-8beec592f488  (2019)
      - src-c3e2fd43efa5 -> src-84efcb6e2cc4  (1999)
      - src-cc5ad18c17b4 -> src-85c74b162cce  (2014)
      - src-f8813ce137a0 -> src-6e952de88bcd  (2004)

The third TCPD row (src-4040a970f10c, "Political Parties of India... TCPD
compilation") is TCPD's own derived work (party catalogue, not raw ECI
returns) and is LEFT UNTOUCHED.

vintage and url stay verbatim on every row.

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

# Pass 2: drop the em-dash + "(TCPD compilation of ECI returns)" suffix from
# the 5 per-year ECI LS source rows. Producer is already "Election Commission
# of India"; only the title and the derived source_id change.
STRIP_SUFFIX_OLD_TO_NEW: dict[str, str] = {
    "src-0099686311a2": "src-9be18d311190",  # 2009
    "src-b2b916daabf9": "src-8beec592f488",  # 2019
    "src-c3e2fd43efa5": "src-84efcb6e2cc4",  # 1999
    "src-cc5ad18c17b4": "src-85c74b162cce",  # 2014
    "src-f8813ce137a0": "src-6e952de88bcd",  # 2004
}

STRIP_SUFFIX_NEW_TITLES: dict[str, str] = {
    "src-9be18d311190": "General Election to Lok Sabha 2009",
    "src-8beec592f488": "General Election to Lok Sabha 2019",
    "src-84efcb6e2cc4": "General Election to Lok Sabha 1999",
    "src-85c74b162cce": "General Election to Lok Sabha 2014",
    "src-6e952de88bcd": "General Election to Lok Sabha 2004",
}


def _rewrite_source_csv(
    path: Path,
    mapping: dict[str, str],
    new_titles: dict[str, str],
    new_producer: str | None,
) -> int:
    """Rewrite the 5-col source ledger: replace rows whose source_id is in
    ``mapping`` with their rebranded counterparts (new id + optional new
    producer + new title). When ``new_producer`` is ``None`` the existing
    producer is preserved (title-only/suffix-strip passes). Preserve every
    other row byte-for-byte. Return the count of rows updated."""

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    updated = 0
    out_rows: list[dict[str, str]] = []
    for row in rows:
        old_id = (row.get("source_id") or "").strip()
        if old_id in mapping:
            new_id = mapping[old_id]
            new_row = dict(row)
            new_row["source_id"] = new_id
            if new_producer is not None:
                new_row["producer"] = new_producer
            new_row["title"] = new_titles[new_id]
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


def _cascade_fk_rewrites(
    roots: list[Path],
    mapping: dict[str, str],
) -> tuple[int, int]:
    """Walk every CSV under ``roots``; for any file whose header contains
    ``source_id``, rewrite cells matching keys of ``mapping``. Return
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
                if old_id in mapping:
                    new_row = dict(row)
                    new_row["source_id"] = mapping[old_id]
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

    cascade_roots = [
        repo_root / "datasets" / "data",
        repo_root / "datasets" / "elections",
    ]

    # Pass 1: rebrand the 2 umbrella rows (producer + title).
    pass1_rows = _rewrite_source_csv(
        source_path,
        mapping=OLD_TO_NEW,
        new_titles=NEW_TITLES,
        new_producer=NEW_PRODUCER,
    )
    pass1_cells, pass1_files = _cascade_fk_rewrites(cascade_roots, OLD_TO_NEW)
    print(
        f"pass 1 (umbrella rebrand): {pass1_rows} source rows updated, "
        f"{pass1_cells} FK cells rewritten across {pass1_files} CSV files."
    )

    # Pass 2: strip the em-dash + (TCPD compilation of ECI returns) suffix
    # from the 5 per-year LS rows. Producer unchanged (already ECI).
    pass2_rows = _rewrite_source_csv(
        source_path,
        mapping=STRIP_SUFFIX_OLD_TO_NEW,
        new_titles=STRIP_SUFFIX_NEW_TITLES,
        new_producer=None,
    )
    pass2_cells, pass2_files = _cascade_fk_rewrites(
        cascade_roots, STRIP_SUFFIX_OLD_TO_NEW
    )
    print(
        f"pass 2 (suffix strip): {pass2_rows} source rows updated, "
        f"{pass2_cells} FK cells rewritten across {pass2_files} CSV files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
