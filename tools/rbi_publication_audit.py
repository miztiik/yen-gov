"""Audit local RBI staging dirs against the public site's per-year table counts.

Answers one question per archive edition: "how many tables/files did we
actually download, versus how many are published on rbi.org.in?" - so you know
exactly which years still need another download pass.

This is a LOCAL, offline report. It does NOT touch the network (the public
counts are a committed snapshot below, measured once from the live site via the
integrated browser; refresh them with --expected when RBI publishes a new
edition). The download itself is done by the Tampermonkey userscripts
(tools/rbi_handbook_download.user.js, tools/rbi_state_finances_download.user.js)
inside your own trusted RBI browser session.

Two publications are understood out of the box:

  handbook        Handbook of Statistics on Indian States. One file per table,
                  directly under <root>/<year>/. Spreadsheets only (.xls/.xlsx).
  state-finances  State Finances: A Study of Budgets. Files nested under
                  <root>/<year>/<section>/. Spreadsheets (.xls/.xlsx) plus
                  narrative/twin PDFs (.pdf).

Counting is recursive under each year folder, so both the flat handbook layout
and the nested state-finances layout work.

Examples::

    # Handbook: did the .XLS fix close the 2016 + 2017-industry gap?
    python tools/rbi_publication_audit.py --publication handbook

    # State Finances, spreadsheets only (the data tables):
    python tools/rbi_publication_audit.py --publication state-finances \\
      --root .runtime/raw/rbi/state-finances --mode spreadsheets

    # Point at a different snapshot of expected counts:
    python tools/rbi_publication_audit.py --publication handbook \\
      --expected ./expected.json

Standalone: argparse + stdlib only. No backend imports (tools/ rule).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Extensions that count as a "data table" vs the full file set.
SPREADSHEET_EXTS = {".xls", ".xlsx"}
ALL_EXTS = {".xls", ".xlsx", ".pdf"}

# Public per-year counts, measured 2026-06-25 from the live RBI site (active
# archive tab -> count of rbidocs.rbi.org.in/rdocs/Publications/DOCs anchors).
# These are a snapshot for offline comparison; pass --expected to override when
# RBI publishes a new edition or revises an old one. yen-gov path rule: keep
# these as plain year->count maps, no absolute paths.
EXPECTED = {
    "handbook": {
        # one map: handbook has no PDFs, so spreadsheets == all
        "spreadsheets": {
            "2016": 125, "2017": 129, "2018": 129, "2019": 141, "2020": 153,
            "2021": 157, "2022": 166, "2023": 172, "2024": 180, "2025": 182,
        },
    },
    "state-finances": {
        # spreadsheets = .xls + .xlsx data tables (the machine-readable payload)
        "spreadsheets": {
            "2002": 0, "2003": 0, "2004": 0, "2005": 0, "2006": 276,
            "2007": 161, "2008": 145, "2010": 153, "2011": 148, "2012": 141,
            "2013": 141, "2014": 120, "2015": 125, "2016": 123, "2017": 123,
            "2018": 155, "2019": 85, "2020": 87, "2021": 86, "2023": 174,
            "2024": 87, "2026": 87,
        },
        # all = spreadsheets + narrative/twin PDFs (the full file set)
        "all": {
            "2002": 132, "2003": 125, "2004": 120, "2005": 23, "2006": 568,
            "2007": 339, "2008": 301, "2010": 323, "2011": 313, "2012": 299,
            "2013": 299, "2014": 257, "2015": 266, "2016": 262, "2017": 263,
            "2018": 325, "2019": 183, "2020": 100, "2021": 185, "2023": 372,
            "2024": 187, "2026": 187,
        },
    },
}

DEFAULT_ROOTS = {
    "handbook": ".runtime/raw/rbi/handbook-states",
    "state-finances": ".runtime/raw/rbi/state-finances",
}


def count_local(root: Path, exts: set[str]) -> dict[str, int]:
    """Count files (recursively) under each immediate year subfolder of root.

    A "year folder" is any direct child directory whose name is four digits.
    Counting is recursive so the flat handbook layout (files directly under
    the year) and the nested state-finances layout (files under year/section/)
    both work.
    """
    counts: dict[str, int] = {}
    if not root.exists():
        return counts
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not (len(child.name) == 4 and child.name.isdigit()):
            continue
        counts[child.name] = sum(
            1 for p in child.rglob("*") if p.is_file() and p.suffix.lower() in exts
        )
    return counts


def load_expected(publication: str, mode: str, override: Path | None) -> dict[str, int]:
    """Return the expected year->count map for this publication + mode."""
    if override is not None:
        data = json.loads(override.read_text(encoding="utf-8"))
        # accept either a flat {year: count} or the nested {mode: {year: count}}
        if mode in data and isinstance(data[mode], dict):
            return {str(k): int(v) for k, v in data[mode].items()}
        return {str(k): int(v) for k, v in data.items()}
    pub = EXPECTED.get(publication, {})
    # handbook only has a "spreadsheets" map; fall back to it for "all"
    return pub.get(mode) or pub.get("spreadsheets") or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit local RBI staging dirs vs the public per-year counts.",
    )
    parser.add_argument(
        "--publication",
        choices=sorted(EXPECTED),
        default="handbook",
        help="which RBI publication to audit (default: handbook)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="staging dir whose children are <year> folders "
        "(default: per-publication .runtime path)",
    )
    parser.add_argument(
        "--mode",
        choices=["spreadsheets", "all"],
        default="spreadsheets",
        help="spreadsheets = .xls/.xlsx only; all = + .pdf (default: spreadsheets)",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=None,
        help="path to a JSON {year: count} (or {mode: {year: count}}) override",
    )
    args = parser.parse_args(argv)

    root = args.root or Path(DEFAULT_ROOTS[args.publication])
    exts = ALL_EXTS if args.mode == "all" else SPREADSHEET_EXTS
    expected = load_expected(args.publication, args.mode, args.expected)
    local = count_local(root, exts)

    if not expected and not local:
        print(
            f"nothing to audit: no expected counts for '{args.publication}' and "
            f"no year folders under {root.as_posix()}"
        )
        return 0

    years = sorted(set(expected) | set(local), key=lambda y: int(y))
    print(
        f"RBI {args.publication} audit  (mode={args.mode}, root={root.as_posix()})"
    )
    print(f"{'year':>6} {'have':>6} {'public':>7} {'missing':>8}  status")
    print("-" * 44)
    total_have = total_pub = total_missing = 0
    for year in years:
        have = local.get(year, 0)
        pub = expected.get(year)
        if pub is None:
            print(f"{year:>6} {have:>6} {'   ?':>7} {'   ?':>8}  not in snapshot")
            total_have += have
            continue
        missing = max(pub - have, 0)
        total_have += have
        total_pub += pub
        total_missing += missing
        if have == 0 and pub > 0:
            status = "MISSING - not downloaded"
        elif missing > 0:
            status = f"SHORT by {missing}"
        elif have > pub:
            status = f"ok (+{have - pub} extra)"
        else:
            status = "ok"
        print(f"{year:>6} {have:>6} {pub:>7} {missing:>8}  {status}")
    print("-" * 44)
    print(f"{'TOTAL':>6} {total_have:>6} {total_pub:>7} {total_missing:>8}")
    if total_missing:
        print(
            f"\n{total_missing} file(s) still missing across "
            f"{sum(1 for y in years if max(expected.get(y, 0) - local.get(y, 0), 0))} "
            "edition(s) - run another pass with the Tampermonkey stager."
        )
    else:
        print("\nall editions complete against the snapshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
