"""Tier-A unit tests for the ac_crosswalk helper (Row A1, ADR-0049).

Pins the bijection-and-completeness invariant that is the single
load-bearing safety net for the eci_no -> lgd_ac_id migration. Pure
in-memory fixtures; no I/O, no corpus walk.

See also:
    - backend/yen_gov/canonical/ac_crosswalk.py
    - TODO/20260530-eci-to-lgd-acid-migration-plan.md Rows A1/A2
"""

from __future__ import annotations

import pytest

from yen_gov.canonical.ac_crosswalk import (
    CrosswalkError,
    assert_bijection,
    lookup_eci_no,
    lookup_lgd_ac_id,
)


def _row(
    state: str,
    eci: int,
    lgd: int | None,
    method: str = "lgd_direct",
) -> dict:
    return {
        "state_code": state,
        "eci_no": eci,
        "lgd_ac_id": lgd,
        "ac_id": f"IN-{state}-AC-2008-{eci}",
        "ac_name": f"AC {eci}",
        "delim_year": 2008,
        "match_method": method,
        "source_id": "src-test",
    }


def _good_rows() -> list[dict]:
    return [
        _row("S22", 1, 28001),
        _row("S22", 2, 28002),
        _row("S01", 5, 28005, method="name_reservation_join"),
        _row("U08", 9, None, method="unmapped"),
    ]


def test_lookup_lgd_ac_id_forward_map() -> None:
    fwd = lookup_lgd_ac_id(_good_rows())
    assert fwd[("S22", 1)] == 28001
    assert fwd[("U08", 9)] is None


def test_lookup_eci_no_reverse_map_skips_unmapped() -> None:
    rev = lookup_eci_no(_good_rows())
    assert rev[28001] == ("S22", 1)
    assert 28009 not in rev  # the unmapped U08 row has no code


def test_assert_bijection_accepts_good_rows() -> None:
    assert_bijection(_good_rows())  # no raise


def test_assert_bijection_completeness_exact_cover() -> None:
    sot = [("S22", 1), ("S22", 2), ("S01", 5), ("U08", 9)]
    assert_bijection(_good_rows(), sot_acs=sot)  # no raise


def test_assert_bijection_rejects_duplicate_pk() -> None:
    rows = _good_rows() + [_row("S22", 1, 99999)]
    with pytest.raises(CrosswalkError, match="duplicate crosswalk PK"):
        assert_bijection(rows)


def test_assert_bijection_rejects_duplicate_lgd_code() -> None:
    rows = _good_rows() + [_row("S03", 7, 28001)]  # reuses S22-1's code
    with pytest.raises(CrosswalkError, match="globally unique"):
        assert_bijection(rows)


def test_assert_bijection_rejects_null_without_unmapped() -> None:
    rows = [_row("S22", 1, None, method="lgd_direct")]
    with pytest.raises(CrosswalkError, match="null/unmapped invariant"):
        assert_bijection(rows)


def test_assert_bijection_rejects_unmapped_with_code() -> None:
    rows = [_row("S22", 1, 28001, method="unmapped")]
    with pytest.raises(CrosswalkError, match="null/unmapped invariant"):
        assert_bijection(rows)


def test_assert_bijection_rejects_unknown_match_method() -> None:
    rows = [_row("S22", 1, 28001, method="guessed")]
    with pytest.raises(CrosswalkError, match="invalid match_method"):
        assert_bijection(rows)


def test_assert_bijection_completeness_missing_sot_ac() -> None:
    sot = [("S22", 1), ("S22", 2), ("S01", 5), ("U08", 9), ("S22", 3)]
    with pytest.raises(CrosswalkError, match="missing"):
        assert_bijection(_good_rows(), sot_acs=sot)


def test_assert_bijection_completeness_extra_row() -> None:
    sot = [("S22", 1), ("S22", 2), ("S01", 5)]  # drops U08-9
    with pytest.raises(CrosswalkError, match="absent from the SoT"):
        assert_bijection(_good_rows(), sot_acs=sot)
