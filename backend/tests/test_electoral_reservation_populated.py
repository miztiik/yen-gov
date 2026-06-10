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
    """Every AC row MUST have reservation in {GEN, SC, ST}."""
    ac_rows = [r for r in electoral_rows if r["entity_kind"] == "ac"]
    assert ac_rows, "no AC rows in electoral.csv"
    missing = [r for r in ac_rows if r["reservation"] not in ("GEN", "SC", "ST")]
    if missing:
        # Surface first 10 for diagnosis.
        sample = [
            f"  {r['entity_id']} state={r['state']} eci_no={r['eci_no']} reservation={r['reservation']!r}"
            for r in missing[:10]
        ]
        pytest.fail(
            f"{len(missing)} of {len(ac_rows)} AC rows missing reservation:\n"
            + "\n".join(sample)
        )


def test_every_pc_row_has_reservation_in_enum(electoral_rows):
    """Every PC row MUST have reservation in {GEN, SC, ST}."""
    pc_rows = [r for r in electoral_rows if r["entity_kind"] == "pc"]
    assert pc_rows, "no PC rows in electoral.csv"
    missing = [r for r in pc_rows if r["reservation"] not in ("GEN", "SC", "ST")]
    if missing:
        sample = [
            f"  {r['entity_id']} state={r['state']} name={r['name']!r} reservation={r['reservation']!r}"
            for r in missing[:10]
        ]
        pytest.fail(
            f"{len(missing)} of {len(pc_rows)} PC rows missing reservation:\n"
            + "\n".join(sample)
        )


def test_tn_s22_ac_reservation_oracle(electoral_rows):
    """TN S22: 234 ACs with 44 SC + 2 ST + 188 GEN per 2008 Delim Order."""
    tn_ac = [
        r
        for r in electoral_rows
        if r["state"] == "tamil-nadu" and r["entity_kind"] == "ac"
    ]
    assert len(tn_ac) == 234, f"expected 234 TN ACs, got {len(tn_ac)}"
    tally = Counter(r["reservation"] for r in tn_ac)
    assert tally["SC"] == 44, f"expected 44 SC TN ACs, got {tally['SC']}"
    assert tally["ST"] == 2, f"expected 2 ST TN ACs, got {tally['ST']}"
    assert tally["GEN"] == 188, f"expected 188 GEN TN ACs, got {tally['GEN']}"


def test_national_sc_pc_count(electoral_rows):
    """National PC totals: 84 SC per 2008 Delim Order."""
    pc_rows = [r for r in electoral_rows if r["entity_kind"] == "pc"]
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
    """
    pc_rows = [r for r in electoral_rows if r["entity_kind"] == "pc"]
    tally = Counter(r["reservation"] for r in pc_rows)
    assert abs(tally["ST"] - 47) <= 5, (
        f"expected ~47 ST PCs (within +/- 5; brief stop cond #2 threshold), "
        f"got {tally['ST']}"
    )


def test_national_total_pc_count(electoral_rows):
    """Total PC rows: 543 elected per Delim Order; allow +1-2 for LGD register
    duplicates (e.g. DNH-DD Dadar/Dadra spelling variants)."""
    pc_rows = [r for r in electoral_rows if r["entity_kind"] == "pc"]
    # 543 official + 1 known LGD-register spelling-duplicate (Dadar vs Dadra DNH).
    assert 543 <= len(pc_rows) <= 545, (
        f"expected 543-545 PC rows (543 elected + LGD duplicates), got {len(pc_rows)}"
    )


def test_reservation_enum_membership(electoral_rows):
    """All non-null reservation values are in the closed enum."""
    seen = {r["reservation"] for r in electoral_rows if r["reservation"]}
    illegal = seen - {"GEN", "SC", "ST"}
    assert not illegal, f"illegal reservation values: {sorted(illegal)}"
