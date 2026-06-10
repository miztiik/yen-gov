"""Tier-A contract tests for the UT-PC eci<N> fallback backfill (this PR, 2026-06-09).

Asserts the 10 UT-classification gap PC rows (Delhi x7 + Chandigarh + Andaman &
Nicobar + Dadar & Nagar Haveli) landed on the live
``datasets/data/entities/electoral.csv`` with the ``eci<eci_no>`` suffix id
pattern, and that the G16 LS2024 ingest now binds them to candidacy + summary
rows (unbound 10 -> 0; the final progression after PR #844 + #849 + this PR).

Real-file tests: this is a contract test against the live spine on disk + the
live LS2024 ingest artifacts. Modelled on
``test_electoral_lgd_export_gap_pcs.py`` (the metro-PC sibling backfill).

Background: the upstream LGD register omits Parliament seats for UTs with
limited Assembly status entirely from its PC enumeration (Delhi has an
Assembly but its 7 PCs were absent at delim=2008; Chandigarh + A&N + DNH+DD
have no Assembly and their PC entries were also absent). The same on-disk
``eci<N>`` fallback pattern (already used for 6 LUCKNOW/KOLKATA-PORT ACs and 4
metro PCs in PR #849) is extended to the 10 UT PCs here. See [LGD-export-gap
fallback section in docs/concepts/electoral-hierarchy.md] for the doctrine
narrative.
"""

from __future__ import annotations

import csv
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

# The 10 UT-classification gap PCs, keyed by their new entity_id.
# The dadra-DNH `Dadar` spelling is the ECI publisher form (verbatim from the
# Statement 33 raw); LGD-canonical `Dadra & Nagar Haveli` exists separately at
# `-361` with `eci_no=1` and is retained for backward compatibility with TCPD
# historical compilations that may use the LGD form.
GAP_PCS: dict[str, dict[str, str | int]] = {
    "IN-PC-2008-andaman-and-nicobar-islands-eci1": {
        "state": "andaman-and-nicobar-islands",
        "name": "Andaman & Nicobar Islands",
        "expected_eci_no": 1,
    },
    "IN-PC-2008-chandigarh-eci1": {
        "state": "chandigarh",
        "name": "Chandigarh",
        "expected_eci_no": 1,
    },
    "IN-PC-2008-dadra-and-nagar-haveli-and-daman-and-diu-eci2": {
        "state": "dadra-and-nagar-haveli-and-daman-and-diu",
        "name": "Dadar & Nagar Haveli",
        "expected_eci_no": 2,
    },
    "IN-PC-2008-delhi-eci1": {
        "state": "delhi",
        "name": "Chandni Chowk",
        "expected_eci_no": 1,
    },
    "IN-PC-2008-delhi-eci2": {
        "state": "delhi",
        "name": "North-East Delhi",
        "expected_eci_no": 2,
    },
    "IN-PC-2008-delhi-eci3": {
        "state": "delhi",
        "name": "East Delhi",
        "expected_eci_no": 3,
    },
    "IN-PC-2008-delhi-eci4": {
        "state": "delhi",
        "name": "New Delhi",
        "expected_eci_no": 4,
    },
    "IN-PC-2008-delhi-eci5": {
        "state": "delhi",
        "name": "North-West Delhi",
        "expected_eci_no": 5,
    },
    "IN-PC-2008-delhi-eci6": {
        "state": "delhi",
        "name": "West Delhi",
        "expected_eci_no": 6,
    },
    "IN-PC-2008-delhi-eci7": {
        "state": "delhi",
        "name": "South Delhi",
        "expected_eci_no": 7,
    },
}

# The eci<N>-suffix id pattern (round-7-compatible: natural publisher id with a
# provenance prefix, NOT an arithmetic surrogate). Same shape as PR #849's 4
# metro PC rows and the existing 6 LUCKNOW/KOLKATA-PORT AC rows on disk.
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


# --- Test 1: the 10 new entity_ids exist with the eci<N> suffix -------------


def test_ten_ut_pcs_present_with_eci_suffix_pattern() -> None:
    """All 10 UT-PC rows exist in electoral.csv with the eci<N> suffix id pattern."""
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
        # Hans Q3 PR #849 verdict: NO data_quality column / NO citizen-facing
        # flag. The eci<N> suffix IS self-describing.
        # PR-E-R (2026-06-10) UPDATE: reservation is now populated from ECI
        # Statement 33 + TCPD GE. The 10 UT PCs are all GEN per 2008 Delim
        # Order EXCEPT Dadar & Nagar Haveli (ST) - the assertion accepts the
        # publisher-stated reservation.
        assert row["reservation"] in ("GEN", "SC", "ST"), (
            f"{eid}: reservation must be in {{GEN, SC, ST}} post PR-E-R; "
            f"got {row['reservation']!r}"
        )
    assert not missing, f"missing UT-PC gap rows: {missing}"


# --- Test 2: eci_no values re-derived from ECI raw match --------------------


def test_eci_no_values_match_eci_statement_33_row_order() -> None:
    """Re-derive eci_no per state from the ECI raw CSV row order; assert match.

    The ECI Statement-33 raw groups rows by state, then by PC (in ballot
    order). The eci_no for a UT-PC fallback row is its 1-indexed first-
    appearance position within its state. This is the load-bearing oracle
    for the 10 new rows (Delhi sorted ballot-order: Chandni Chowk=1,
    North-East Delhi=2, East Delhi=3, New Delhi=4, North-West Delhi=5,
    West Delhi=6, South Delhi=7; Chandigarh + A&N each have a single PC at
    position 1; DNH+DD has 2 PCs - Daman & Diu=1 - already bound via the
    LGD `-360` row - and Dadar & Nagar Haveli=2).
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
        state_slug = str(expected["state"])
        pc_list = per_state_order.get(state_slug, [])
        # 1-indexed position of the PC name in its state's row order.
        try:
            derived_eci_no = pc_list.index(str(expected["name"])) + 1
        except ValueError:
            raise AssertionError(
                f"{eid}: PC name {expected['name']!r} not in ECI raw row order "
                f"for state {state_slug!r}"
            )
        assert derived_eci_no == expected["expected_eci_no"], (
            f"{eid}: derived eci_no={derived_eci_no} disagrees with "
            f"expected {expected['expected_eci_no']} (PC row-order index in raw)"
        )


# --- Test 3: _build_pc_lookup picks up the 10 new spine rows ----------------


def test_pc_lookup_picks_up_ten_ut_gap_pcs() -> None:
    """The single-step (state, normalised_name) -> (entity_id, eci_no) lookup
    resolves all 10 new UT-PC gap names to their eci<N>-suffix entity_ids."""
    lookup = _build_pc_lookup(_electoral_csv_path())
    missing = []
    for eid, expected in GAP_PCS.items():
        key = (str(expected["state"]), _normalise_pc_name(str(expected["name"])))
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


# --- Test 4: build_parliament_2024 emits 10 PCs as BOUND, NOT unbound -------


def test_build_parliament_2024_binds_ten_ut_gap_pcs() -> None:
    """Running the end-to-end build over the LIVE ECI raw + LIVE electoral.csv
    produces all 10 UT gap PCs as BOUND candidacies (NOT in the unbound set)."""
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
        key = (str(expected["state"]), str(expected["name"]))
        assert key not in unbound, (
            f"{key} appeared in unbound set after build (expected BOUND)"
        )
    # Belt-and-braces: total unbound is exactly 0 after this PR (50 -> 14 ->
    # 10 -> 0 across PR #844 + PR #849 + this PR).
    assert len(unbound) == 0, (
        f"expected unbound count = 0 after UT-PC backfill; "
        f"got {len(unbound)}: {sorted(unbound)}"
    )


# --- Test 5: live summary.csv has 542 rows; receipt says unbound=0 ---------


def test_live_summary_has_542_rows_and_receipt_says_unbound_0() -> None:
    """The committed LS2024 summary.csv has 532 + 10 = 542 rows after this PR;
    the regenerated coverage receipt at
    datasets/_ops/parliament-2024-eci-coverage-2026-06-09.md says unbound=0
    (was 10 after PR #849)."""
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
    assert len(summary_rows) == 542, (
        f"summary.csv expected 542 rows (532 baseline after PR #849 + 10 new "
        f"UT PCs in this PR), got {len(summary_rows)}"
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
    # Look for the summary table row (pipe-separated) reflecting the final
    # tally after this PR.
    assert "| 2024 | 36 | 8359 | 542 | 0 | 8909 |" in receipt, (
        "coverage receipt summary row mismatch (expected 36 states / "
        f"8359 candidacies / 542 summary / 0 unbound / 8909 raw); got:\n"
        f"{receipt}"
    )
    # The 10 UT PCs should no longer appear in the receipt's unbound list.
    # (The receipt header section after this PR says '(none -- ...)' instead
    # of listing them, so the explicit-line absence assertion is the test.)
    for expected in GAP_PCS.values():
        for_state_line = f"`{expected['state']}` / `{expected['name']}`"
        assert for_state_line not in receipt, (
            f"unbound list still references {for_state_line} after backfill"
        )


# --- Test 6: id pattern matches the eci<N>-suffix regex --------------------


def test_eci_suffix_id_pattern_parses_as_natural_publisher_id() -> None:
    """All 10 UT-PC entity_ids match the documented eci<N>-suffix regex
    ``^IN-PC-2008-[a-z][a-z0-9\\-]*-eci\\d+$``. Same shape as PR #849's 4
    metro PCs + the existing 6 LUCKNOW/KOLKATA-PORT AC rows. The eci-suffix
    is the on-disk precedent + round-7-compatible per Hans verdict
    2026-06-09 (the `eci` prefix is self-describing - no `data_quality` enum
    needed)."""
    for eid in GAP_PCS:
        assert _ECI_SUFFIX_PC_ID_PATTERN.match(eid), (
            f"{eid!r} does not match the eci<N>-suffix PC id pattern"
        )
    # Anti-test: an arithmetic surrogate (round-7-prohibited) is NOT what
    # this pattern admits. The `eci` infix is the self-describing
    # discriminator that separates this fallback from any future LGD-coded
    # id (numeric-only suffix).
    arithmetic_surrogate_examples = [
        "IN-PC-2008-delhi-7001",  # state_code 7 * 1000 + eci_no 1
        "IN-PC-2008-delhi-1",  # bare numeric (would collide with LGD shape)
    ]
    for surrogate in arithmetic_surrogate_examples:
        assert "-eci" not in surrogate, (
            f"surrogate example {surrogate!r} accidentally contains "
            f"'-eci' marker"
        )
