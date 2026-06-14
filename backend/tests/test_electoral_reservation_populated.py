"""Tier-A regression: every AC + PC row in electoral.csv has reservation populated.

PR-E-R (2026-06-10) backfilled the ``reservation`` column on
``datasets/data/entities/electoral.csv`` from boundaries_sot (AC primary)
+ TCPD All_States_AE.csv (AC fallback) + TCPD All_States_GE.csv (PC primary)
+ ECI Statement 33 2024/2019 (PC cross-check + tribal-area fallback).

This test enforces that the populated state survives future writer reruns
+ surfaces any regression where a PC or AC row loses its reservation.

The "real-corpus walking" carve-out applies (per existing Tier-A pattern
in ``test_party_id_fk_closure``) - this test reads the COMMITTED on-disk
``datasets/data/entities/electoral.csv``, not a fixture tree.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ELECTORAL_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "electoral.csv"


@pytest.fixture(scope="module")
def electoral_rows() -> list[dict[str, str]]:
    assert ELECTORAL_CSV.exists(), f"missing {ELECTORAL_CSV}"
    with ELECTORAL_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_ac_row_has_reservation_in_enum(electoral_rows):
    """Every in-force-cycle (delim_year=2008) AC row MUST have reservation in {GEN, SC, ST}.

    PR-Q7b (2026-06-12) introduced historical AC entity cohorts under
    ``delim_year`` 1962 / 1967 / 1976 from TCPD's ``All_States_AE.csv``.
    TCPD ``Constituency_Type`` is honestly empty for the pre-reservation
    multi-member ``BL`` bloc constituencies (mostly DelimID 1, years
    1961-1965) and for sporadic later rows where TCPD simply does not
    record a type. The minter writes those rows with empty
    ``reservation`` per ADR; ECI's reservation enum was introduced post
    the 1956 Second Schedule reorganisation and was not applied to every
    historical seat at the publisher level. This test scopes the
    "every row populated" invariant to the in-force 2008 cycle where
    PR-E-R's backfill is the controlling write seam.
    """
    ac_rows = [
        r
        for r in electoral_rows
        if r["entity_kind"] == "ac" and r["delim_year"] == "2008"
    ]
    assert ac_rows, "no in-force AC rows in electoral.csv"
    missing = [r for r in ac_rows if r["reservation"] not in ("GEN", "SC", "ST")]
    if missing:
        # Surface first 10 for diagnosis.
        sample = [
            f"  {r['entity_id']} state={r['state']} eci_no={r['eci_no']} reservation={r['reservation']!r}"
            for r in missing[:10]
        ]
        pytest.fail(
            f"{len(missing)} of {len(ac_rows)} in-force AC rows missing reservation:\n"
            + "\n".join(sample)
        )


def test_every_pc_row_has_reservation_in_enum(electoral_rows):
    """Every in-force-cycle (delim_year=2008) PC row MUST have reservation in {GEN, SC, ST}.

    PR-Q7c (2026-06-12) introduced historical PC entity cohorts under
    ``delim_year`` 1962 / 1967 / 1976 from TCPD's ``All_States_GE.csv``.
    TCPD ``Constituency_Type`` is honestly empty for the pre-reservation
    multi-member ``BL`` bloc constituencies (mostly DelimID 1, years
    1962-1965) and for sporadic later rows where TCPD simply does not
    record a type. The minter writes those rows with empty
    ``reservation`` per ADR; the same scope-tightening doctrine PR-Q7b
    applied to the AC test applies here: pin the "every row populated"
    invariant to the in-force 2008 cycle where PR-E-R's backfill is the
    controlling write seam.
    """
    pc_rows = [
        r
        for r in electoral_rows
        if r["entity_kind"] == "pc" and r["delim_year"] == "2008"
    ]
    assert pc_rows, "no in-force PC rows in electoral.csv"
    missing = [r for r in pc_rows if r["reservation"] not in ("GEN", "SC", "ST")]
    if missing:
        sample = [
            f"  {r['entity_id']} state={r['state']} name={r['name']!r} reservation={r['reservation']!r}"
            for r in missing[:10]
        ]
        pytest.fail(
            f"{len(missing)} of {len(pc_rows)} in-force PC rows missing reservation:\n"
            + "\n".join(sample)
        )


def test_tn_s22_ac_reservation_oracle(electoral_rows):
    """TN S22 in-force cycle: 234 ACs with 44 SC + 2 ST + 188 GEN per 2008 Delim Order.

    Filter to ``delim_year=2008`` so the oracle remains pinned to the
    "2008 Delim Order" universe declared in the docstring even after
    PR-Q7b widened the catalogue with historical 1962/1967/1976 cohorts
    (which add a further 234 TN AC entries each across the older delim
    cycles, hence the total grows to 702 without the filter).
    """
    tn_ac = [
        r
        for r in electoral_rows
        if r["state"] == "tamil-nadu"
        and r["entity_kind"] == "ac"
        and r["delim_year"] == "2008"
    ]
    assert len(tn_ac) == 234, f"expected 234 TN in-force ACs, got {len(tn_ac)}"
    tally = Counter(r["reservation"] for r in tn_ac)
    assert tally["SC"] == 44, f"expected 44 SC TN ACs, got {tally['SC']}"
    assert tally["ST"] == 2, f"expected 2 ST TN ACs, got {tally['ST']}"
    assert tally["GEN"] == 188, f"expected 188 GEN TN ACs, got {tally['GEN']}"


def test_national_sc_pc_count(electoral_rows):
    """National PC totals: 84 SC per 2008 Delim Order.

    PR-Q7c (2026-06-12): scoped to delim_year=2008 so the oracle stays
    pinned to the "2008 Delim Order" universe after the historical
    1962/1967/1976 cohorts widened the catalogue.
    """
    pc_rows = [
        r
        for r in electoral_rows
        if r["entity_kind"] == "pc" and r["delim_year"] == "2008"
    ]
    tally = Counter(r["reservation"] for r in pc_rows)
    assert tally["SC"] == 84, (
        f"expected 84 SC PCs nationwide (2008 Delim Order), got {tally['SC']}"
    )


def test_national_st_pc_count_close_to_oracle(electoral_rows):
    """National PC totals: ~47 ST per 2008 Delim Order.

    Allows +/- 5 to absorb publisher / hand-curation drift on single-seat
    all-tribal areas (Ladakh, Lakshadweep, Mizoram, Nagaland) where ECI
    Stmt 33 candidate-cat derivation + TCPD Constituency_Type sometimes
    flip GEN <-> ST. The brief's stop condition #2 is "> 5 PC divergences",
    so we accept up to 5 absolute drift in the ST count.

    PR-Q7c (2026-06-12): scoped to delim_year=2008 (mirror of SC test).
    """
    pc_rows = [
        r
        for r in electoral_rows
        if r["entity_kind"] == "pc" and r["delim_year"] == "2008"
    ]
    tally = Counter(r["reservation"] for r in pc_rows)
    assert abs(tally["ST"] - 47) <= 5, (
        f"expected ~47 ST PCs (within +/- 5; brief stop cond #2 threshold), "
        f"got {tally['ST']}"
    )


def test_national_total_pc_count(electoral_rows):
    """Total PC rows: 543 elected per Delim Order; allow +1-2 for LGD register
    duplicates (e.g. DNH-DD Dadar/Dadra spelling variants).

    PR-Q7c (2026-06-12): scoped to delim_year=2008 so the 543 oracle
    stays pinned to the in-force cycle after the historical 1962/1967/1976
    cohorts widened the catalogue with ~1494 additional PC entities.
    """
    pc_rows = [
        r
        for r in electoral_rows
        if r["entity_kind"] == "pc" and r["delim_year"] == "2008"
    ]
    # 543 official + 1 known LGD-register spelling-duplicate (Dadar vs Dadra DNH).
    assert 543 <= len(pc_rows) <= 545, (
        f"expected 543-545 PC rows (543 elected + LGD duplicates), got {len(pc_rows)}"
    )


def test_reservation_enum_membership(electoral_rows):
    """All non-null reservation values are in the closed enum."""
    seen = {r["reservation"] for r in electoral_rows if r["reservation"]}
    illegal = seen - {"GEN", "SC", "ST"}
    assert not illegal, f"illegal reservation values: {sorted(illegal)}"
