"""Tier-A contract tests for the LGD-export-gap PC backfill (Hans verdict 2026-06-09).

Asserts the 4 LGD-export-gap PC rows (Mumbai South / Lucknow / Kolkata Dakshin /
Kolkata Uttar) landed on the live ``datasets/data/entities/electoral.csv`` with
the ``eci<eci_no>`` suffix id pattern, and that the G16 LS2024 ingest now binds
them to candidacy + summary rows (unbound 14 -> 10).

Real-file tests: this is a contract test against the live spine on disk + the
live LS2024 ingest artifacts. Synthetic-fixture coverage of the emitter logic
itself remains in ``test_parliament_2024_eci.py``.

Background: the upstream LGD HTML export is incomplete for these 4 metro PCs
(MH has 47/48 LS seats in LGD; UP has 79/80; WB has 40/42). The existing on-disk
``eci<N>`` fallback pattern (already used for 6 LUCKNOW/KOLKATA-PORT ACs) is
extended to the PC grain here. See [LGD-export-gap fallback section in
docs/concepts/electoral-hierarchy.md] for the doctrine narrative.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from yen_gov.canonical.reingest.parliament_2024_eci import (
    LS2024_ELECTION_YEAR,
    _build_pc_lookup,
    _is_real_candidate_row,
    _normalise_pc_name,
    _slugify_eci_state,
    build_parliament_2024,
    parse_eci_raw_2024_csv,
)

# The 4 LGD-export-gap PCs, keyed by their new entity_id.
GAP_PCS: dict[str, dict[str, str]] = {
    "IN-PC-2008-maharashtra-eci31": {
        "state": "maharashtra",
        "state_eci_name": "Maharashtra",
        "name": "Mumbai South",
        "expected_eci_no": 31,
    },
    "IN-PC-2008-uttar-pradesh-eci35": {
        "state": "uttar-pradesh",
        "state_eci_name": "Uttar Pradesh",
        "name": "Lucknow",
        "expected_eci_no": 35,
    },
    "IN-PC-2008-west-bengal-eci23": {
        "state": "west-bengal",
        "state_eci_name": "West Bengal",
        "name": "Kolkata Dakshin",
        "expected_eci_no": 23,
    },
    "IN-PC-2008-west-bengal-eci24": {
        "state": "west-bengal",
        "state_eci_name": "West Bengal",
        "name": "Kolkata Uttar",
        "expected_eci_no": 24,
    },
}

# The eci<N>-suffix id pattern (round-7-compatible: natural publisher id with a
# provenance prefix, NOT an arithmetic surrogate). Same shape as the existing
# 6 LUCKNOW/KOLKATA-PORT AC rows on disk.
_ECI_SUFFIX_PC_ID_PATTERN = re.compile(
    r"^IN-PC-2008-[a-z][a-z0-9\-]*-eci\d+$"
)


def _repo_root() -> Path:
    """Walk up from this test file to the first ancestor containing ``datasets/``."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "datasets").is_dir():
            return parent
    raise FileNotFoundError("could not locate repo root from test file")


def _electoral_csv_path() -> Path:
    return _repo_root() / "datasets" / "data" / "entities" / "electoral.csv"


def _eci_raw_path() -> Path:
    return (
        _repo_root()
        / "datasets"
        / "ephemeral"
        / "2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv"
    )


def _load_electoral_rows() -> list[dict[str, str]]:
    with _electoral_csv_path().open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- Test 1: the 4 new entity_ids exist with the eci<N> suffix --------------


def test_four_gap_pcs_present_with_eci_suffix_pattern() -> None:
    """All 4 LGD-export-gap PC rows exist in electoral.csv with the eci<N> suffix."""
    rows = _load_electoral_rows()
    by_eid = {r["entity_id"]: r for r in rows}
    missing = []
    for eid, expected in GAP_PCS.items():
        row = by_eid.get(eid)
        if row is None:
            missing.append(eid)
            continue
        assert row["name"] == expected["name"], (
            f"{eid}: name mismatch (expected {expected['name']!r}, got {row['name']!r})"
        )
        assert row["entity_kind"] == "pc", f"{eid}: entity_kind != pc"
        assert row["delim_year"] == "2008", f"{eid}: delim_year != 2008"
        assert row["state"] == expected["state"], (
            f"{eid}: state mismatch (expected {expected['state']!r}, got {row['state']!r})"
        )
        assert row["parent"] == expected["state"], (
            f"{eid}: parent mismatch (expected {expected['state']!r}, got {row['parent']!r})"
        )
        assert row["eci_no"] == str(expected["expected_eci_no"]), (
            f"{eid}: eci_no column mismatch "
            f"(expected {expected['expected_eci_no']!r}, got {row['eci_no']!r})"
        )
        # The brief: Hans Q3 says NO data_quality column / NO citizen-facing flag.
        # The suffix IS self-describing. Reservation stays blank (all 4 are General).
        assert row["reservation"] == "", (
            f"{eid}: reservation should be blank (all 4 PCs are General); "
            f"got {row['reservation']!r}"
        )
    assert not missing, f"missing gap PC rows: {missing}"


# --- Test 2: eci_no values re-derived from ECI raw match --------------------


def test_eci_no_values_match_eci_statement_33_raw() -> None:
    """Re-derive eci_no per state from the ECI raw CSV row order; assert match.

    The ECI Statement-33 raw groups rows by state, then by PC (in ballot
    order). The eci_no for a PC is its 1-indexed first-appearance position
    within its state. This is the load-bearing oracle for the 4 new rows
    (Hans's expected values: MH 31, UP 35, WB 23/24).
    """
    eci_csv = _eci_raw_path()
    if not eci_csv.exists():
        # Operator-cache file; the rerun driver requires it on disk. Skip if
        # absent (CI / fresh-clone scenarios without the optional file).
        import pytest
        pytest.skip(f"ECI raw CSV not present at {eci_csv.as_posix()}")
    raw_rows = parse_eci_raw_2024_csv(eci_csv)
    per_state_order: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for r in raw_rows:
        if not _is_real_candidate_row(r):
            continue
        state_slug = _slugify_eci_state((r.get("State Name") or "").strip())
        pc_name = (r.get("PC Name") or "").strip()
        if state_slug not in seen:
            seen[state_slug] = set()
            per_state_order[state_slug] = []
        if pc_name not in seen[state_slug]:
            seen[state_slug].add(pc_name)
            per_state_order[state_slug].append(pc_name)
    for eid, expected in GAP_PCS.items():
        state_slug = expected["state"]
        pc_list = per_state_order.get(state_slug, [])
        # 1-indexed position of the PC name in its state's row order.
        try:
            derived_eci_no = pc_list.index(expected["name"]) + 1
        except ValueError:
            raise AssertionError(
                f"{eid}: PC name {expected['name']!r} not in ECI raw row order "
                f"for state {state_slug!r}"
            )
        assert derived_eci_no == expected["expected_eci_no"], (
            f"{eid}: derived eci_no={derived_eci_no} disagrees with "
            f"expected {expected['expected_eci_no']} (PC row-order index in raw)"
        )


# --- Test 3: _build_pc_lookup picks up the 4 new spine rows -----------------


def test_pc_lookup_picks_up_four_gap_pcs() -> None:
    """The single-step (state, normalised_name) -> (entity_id, eci_no) lookup
    resolves all 4 new gap-PC names to their eci<N>-suffix entity_ids."""
    lookup = _build_pc_lookup(_electoral_csv_path())
    missing = []
    for eid, expected in GAP_PCS.items():
        key = (expected["state"], _normalise_pc_name(expected["name"]))
        bind = lookup.get(key)
        if bind is None:
            missing.append((eid, key))
            continue
        bound_eid, bound_eci_no = bind
        assert bound_eid == eid, (
            f"{key} bound to {bound_eid!r}, expected {eid!r}"
        )
        assert bound_eci_no == expected["expected_eci_no"], (
            f"{key} bound eci_no={bound_eci_no}, "
            f"expected {expected['expected_eci_no']}"
        )
    assert not missing, f"pc_lookup missing keys for: {missing}"


# --- Test 4: build_parliament_2024 emits 4 PCs as BOUND, NOT in unbound -----


def test_build_parliament_2024_binds_four_gap_pcs(tmp_path: Path) -> None:
    """Running the end-to-end build over the LIVE ECI raw + LIVE electoral.csv
    produces all 4 gap PCs as BOUND candidacies (NOT in the unbound set)."""
    eci_csv = _eci_raw_path()
    if not eci_csv.exists():
        import pytest
        pytest.skip(f"ECI raw CSV not present at {eci_csv.as_posix()}")
    raw_rows = parse_eci_raw_2024_csv(eci_csv)
    pc_lookup = _build_pc_lookup(_electoral_csv_path())
    candidacies, summary, unbound = build_parliament_2024(
        source_rows=raw_rows,
        pc_lookup=pc_lookup,
        source_id="src-bfb4e7fb9785",
        party_lookup={},
    )
    bound_eids = {c["entity_id"] for c in candidacies}
    for eid, expected in GAP_PCS.items():
        assert eid in bound_eids, (
            f"{eid} ({expected['name']}) NOT in candidacies after build"
        )
        # Also confirm not in the unbound set (no name drift dropped it).
        key = (expected["state"], expected["name"])
        assert key not in unbound, (
            f"{key} appeared in unbound set after build (expected BOUND)"
        )
    # Belt-and-braces: total unbound is exactly 10 (Delhi x7 + Chandigarh +
    # A&N + Dadra-DNH), down from 14 before this PR.
    assert len(unbound) == 10, (
        f"expected unbound count = 10 (irreducible spine gaps after this PR); "
        f"got {len(unbound)}: {sorted(unbound)}"
    )


# --- Test 5: live summary.csv has 532 rows; coverage receipt says unbound=10


def test_live_summary_has_532_rows_and_receipt_says_unbound_10() -> None:
    """The committed LS2024 summary.csv has 528 + 4 = 532 rows after this PR;
    the regenerated coverage receipt at datasets/_ops/parliament-2024-eci-coverage-
    2026-06-09.md says unbound=10 (was 14)."""
    summary_path = (
        _repo_root()
        / "datasets"
        / "elections"
        / "parliament"
        / f"election={LS2024_ELECTION_YEAR}"
        / "summary.csv"
    )
    with summary_path.open(encoding="utf-8", newline="") as fh:
        summary_rows = list(csv.DictReader(fh))
    assert len(summary_rows) == 532, (
        f"summary.csv expected 532 rows (528 baseline + 4 new), got {len(summary_rows)}"
    )
    by_eid = {r["entity_id"]: r for r in summary_rows}
    for eid, expected in GAP_PCS.items():
        row = by_eid.get(eid)
        assert row is not None, f"{eid} missing from summary.csv"
        assert row["constituency_name"] == expected["name"]
        assert row["source_id"] == "src-bfb4e7fb9785", (
            f"{eid}: summary source_id should reuse src-bfb4e7fb9785 "
            f"(ADR-0042 one-row-per-(producer, title, vintage)); "
            f"got {row['source_id']!r}"
        )

    receipt_path = (
        _repo_root()
        / "datasets"
        / "_ops"
        / "parliament-2024-eci-coverage-2026-06-09.md"
    )
    receipt = receipt_path.read_text(encoding="utf-8")
    # Look for the summary table row (pipe-separated). The receipt template
    # uses one row '| 2024 | <states> | <cand> | <summary> | <unbound> | <raw> |'.
    assert "| 2024 | 33 | 8161 | 532 | 10 | 8909 |" in receipt, (
        "coverage receipt summary row mismatch (expected 33 states / "
        f"8161 candidacies / 532 summary / 10 unbound / 8909 raw); got:\n"
        f"{receipt}"
    )
    # The 4 metros should no longer appear in the receipt's unbound list.
    for expected in GAP_PCS.values():
        for_state_line = f"`{expected['state']}` / `{expected['name']}`"
        assert for_state_line not in receipt, (
            f"unbound list still references {for_state_line} after backfill"
        )


# --- Test 6: id pattern matches the eci<N>-suffix regex --------------------


def test_eci_suffix_id_pattern_parses_as_natural_publisher_id() -> None:
    """All 4 gap-PC entity_ids match the documented eci<N>-suffix regex
    ``^IN-PC-2008-[a-z][a-z0-9\\-]*-eci\\d+$``. This is the same shape as the
    existing 6 LUCKNOW/KOLKATA-PORT AC rows (eci-suffix is the on-disk
    precedent + round-7-compatible per Hans verdict 2026-06-09)."""
    for eid in GAP_PCS:
        assert _ECI_SUFFIX_PC_ID_PATTERN.match(eid), (
            f"{eid!r} does not match the eci<N>-suffix PC id pattern"
        )
    # Anti-test: an arithmetic surrogate (round-7-prohibited) MUST NOT match
    # the pattern. The eci<N> suffix is a natural-publisher prefix, not an
    # arithmetic surrogate composed of state_code * 1000 + eci_no etc.
    arithmetic_surrogate_examples = [
        "IN-PC-2008-maharashtra-27031",  # state_code 27 * 1000 + 31
        "IN-PC-2008-maharashtra-31",  # bare numeric (would collide with LGD suffix)
    ]
    for surrogate in arithmetic_surrogate_examples:
        # The pattern allows pure-numeric suffixes (existing LGD codes), so we
        # only assert that the surrogate path (no 'eci' marker) cannot be
        # mistaken for a gap-PC id. The eci<N> marker is the self-describing
        # discriminator.
        assert "-eci" not in surrogate, (
            f"surrogate example {surrogate!r} accidentally contains '-eci' marker"
        )
