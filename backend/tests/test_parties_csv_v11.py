"""PR-0 oracle: parties.csv v1.1 schema + sentinel rows.

Plan: TODO/20260610-electoral-data-quality-and-party-catalogue-plan.md PR-0.

Asserts the v1.1 invariants the rest of the campaign relies on:

1. The file has exactly 18 columns (8 pre-existing + 10 nullable identity-
   metadata columns appended in v1.1).
2. The 3 resolver-fallback sentinels (parties.IN.UNK / parties.IN.IND /
   parties.IN.NOTA) are present with ``is_sentinel`` populated as the string
   ``"true"`` (CSV nullable-boolean encoding from csv_writer._format) and
   ``recognition_scope == "sentinel"``. NOTA additionally carries
   ``founded_year == "2013"``.
3. Every NON-sentinel row has ``is_sentinel`` left empty (CSV-null) -
   the marker is reserved for the 3 resolver-fallback rows.
4. Every row's ``party_id`` matches ``^parties\\.IN\\.[A-Z0-9_]+$`` (round-7
   slug-shape invariant).

No mocks; reads the real on-disk corpus per CLAUDE.md Holy Law #7.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PARTIES_CSV = _REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"

# v1.2 (PR-1 of TODO/20260615-party-page-citizen-fixes-plan.md):
# Holy-Law-#9 + section-12 trailing nullable triple appended. Per L-4
# Path A signoff (additive minor bump 1.1 -> 1.2). The 12 priority
# backfill rows populate this triple via the citation ledger
# (src-a0225819954c) + processing_quality.derive_processing_for_party_
# founded_year_backfill(); every other 2767 row leaves them blank.
_EXPECTED_HEADER = (
    "party_id",
    "short",
    "full",
    "eci_codes",
    "brand_colour",
    "symbol_asset",
    "wikipedia",
    "aliases",
    "recognition_scope",
    "home_state_codes",
    "founded_year",
    "dissolved_year",
    "predecessor_party_ids",
    "successor_party_ids",
    "name_history",
    "claims_to_parent_name",
    "name_native_script",
    "is_sentinel",
    "source_id",
    "processing_level",
    "processing_note",
)

_SENTINELS = ("parties.IN.IND", "parties.IN.NOTA", "parties.IN.UNK")

_PARTY_ID_RE = re.compile(r"^parties\.IN\.[A-Z0-9_]+$")


def _load_rows() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with _PARTIES_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = tuple(reader.fieldnames or ())
        rows = list(reader)
    return header, rows


def test_header_has_exactly_21_columns_in_declared_order() -> None:
    # 21 = 18 v1.1 cols + 3 v1.2 trailing nullable triple (source_id,
    # processing_level, processing_note) per PR-1 of
    # TODO/20260615-party-page-citizen-fixes-plan.md.
    header, _ = _load_rows()
    assert header == _EXPECTED_HEADER, (
        f"parties.csv header drift; expected {_EXPECTED_HEADER}, got {header}"
    )


def test_sentinel_rows_present_and_marked() -> None:
    _, rows = _load_rows()
    by_pid = {r["party_id"]: r for r in rows}
    missing = [pid for pid in _SENTINELS if pid not in by_pid]
    assert missing == [], f"sentinel rows missing from parties.csv: {missing}"
    for pid in _SENTINELS:
        row = by_pid[pid]
        assert row["is_sentinel"] == "true", (
            f"{pid}: is_sentinel must be the string 'true' (CSV nullable-boolean "
            f"encoding), got {row['is_sentinel']!r}"
        )
        assert row["recognition_scope"] == "sentinel", (
            f"{pid}: recognition_scope must be 'sentinel', got "
            f"{row['recognition_scope']!r}"
        )
    assert by_pid["parties.IN.NOTA"]["founded_year"] == "2013", (
        "parties.IN.NOTA: founded_year must be '2013' (NOTA introduced in 2013)"
    )


def test_non_sentinel_rows_leave_is_sentinel_empty() -> None:
    _, rows = _load_rows()
    leaks = [
        r["party_id"]
        for r in rows
        if r["party_id"] not in _SENTINELS and r["is_sentinel"] != ""
    ]
    assert leaks == [], (
        "non-sentinel rows carrying a populated is_sentinel cell: "
        f"{leaks}"
    )


def test_every_party_id_matches_round7_slug_shape() -> None:
    _, rows = _load_rows()
    violations = [r["party_id"] for r in rows if not _PARTY_ID_RE.match(r["party_id"])]
    assert violations == [], (
        "party_id values violating ^parties\\.IN\\.[A-Z0-9_]+$ slug shape: "
        f"{violations}"
    )
